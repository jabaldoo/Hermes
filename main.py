# main.py - HERMES: Hazard Evacuation, Response and Mesh Embedded System
# Demonstrator PoC. Start: python -m uvicorn main:app --reload
# Zero Dockera - FastAPI + SQLite + asyncio + WebSocket, frontend bez build-stepu.
import asyncio
import base64
import csv
import io
import json
import os
from contextlib import asynccontextmanager

import cv2
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

import data_sources
import db
import simulator
import czk_logic
from anonymizer import TRYBY_DOZWOLONE, anonimizuj_klatke, klatka_na_jpeg_bytes, wczytaj_tryb_z_env
from edge_ai import przetworz_klatke_na_pokladzie

load_dotenv()

TUTAJ = os.path.dirname(os.path.abspath(__file__))


class MenadzerPolaczen:
    """Klienci WebSocket panelu CZK - rozglaszanie stanu i zdarzen na zywo."""

    def __init__(self):
        self.aktywni: list[WebSocket] = []

    async def dolacz(self, ws: WebSocket):
        await ws.accept()
        self.aktywni.append(ws)

    def odlacz(self, ws: WebSocket):
        if ws in self.aktywni:
            self.aktywni.remove(ws)

    async def rozglos(self, wiadomosc: dict):
        for ws in list(self.aktywni):
            try:
                await ws.send_json(wiadomosc)
            except Exception:
                self.odlacz(ws)


menadzer = MenadzerPolaczen()


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.inicjalizuj_baze()
    db.zaladuj_sektory_z_mocka()
    simulator.sym = simulator.Symulator()
    simulator.sym.broadcast = menadzer.rozglos
    zadanie = asyncio.create_task(simulator.sym.petla())
    print("[HERMES] Symulacja wystartowala. Otworz http://127.0.0.1:8000")
    yield
    zadanie.cancel()


app = FastAPI(title="HERMES demonstrator", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=os.path.join(TUTAJ, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(TUTAJ, "templates"))


def _sym():
    return simulator.sym


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(status_code=204)


@app.get("/", response_class=HTMLResponse)
async def strona_glowna(request: Request):
    return templates.TemplateResponse(request, "index.html", {
        "orto_wmts": data_sources.GEOPORTAL_ORTO_WMTS,
        "prg_wms": data_sources.GEOPORTAL_PRG_WMS,
    })


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await menadzer.dolacz(ws)
    try:
        await ws.send_json({"typ": "init", "stan": _sym().stan(),
                            "zdarzenia": list(reversed(db.pobierz_zdarzenia(limit=80)))})
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        menadzer.odlacz(ws)


# ---------------------------------------------------------------- stan i sterowanie symulacja

@app.get("/api/stan")
async def api_stan():
    return _sym().stan()


@app.post("/api/sym/scenariusz/{klucz}")
async def api_scenariusz(klucz: str):
    if klucz not in _sym().mock["scenariusze"]:
        raise HTTPException(404, "Nieznany scenariusz")
    _sym().uruchom_scenariusz(klucz)
    _sym().pauza = False
    await _sym().wyslij()
    return {"scenariusz": klucz}


@app.post("/api/sym/pauza")
async def api_pauza():
    _sym().pauza = not _sym().pauza
    await _sym().wyslij()
    return {"pauza": _sym().pauza}


@app.post("/api/sym/predkosc/{x}")
async def api_predkosc(x: int):
    if x not in (1, 2, 4):
        raise HTTPException(400, "Dozwolone: 1, 2, 4")
    _sym().predkosc = x
    await _sym().wyslij()
    return {"predkosc": x}


@app.post("/api/sym/wezel/{dron_id}")
async def api_wezel(dron_id: str):
    if dron_id not in _sym().drony:
        raise HTTPException(404, "Nieznany dron")
    _sym().przelacz_wezel(dron_id)
    await _sym().wyslij()
    return {"dron": dron_id, "zywy": _sym().drony[dron_id]["zywy"]}


@app.post("/api/glos/{dron_id}")
async def api_glos(dron_id: str):
    d = _sym().drony.get(dron_id)
    if d is None or not d["zywy"]:
        raise HTTPException(404, "Dron niedostepny")
    if d["tryb"] != "aktywny":
        raise HTTPException(400, "Dron pasywny nie ma glosnika")
    _sym().komunikat_reczny(dron_id)
    await _sym().wyslij()
    return {"dron": dron_id}


@app.post("/api/sym/stacja/{stacja_id}")
async def api_stacja(stacja_id: str):
    if stacja_id not in _sym().stacje:
        raise HTTPException(404, "Nieznana stacja")
    _sym().przelacz_stacje(stacja_id)
    await _sym().wyslij()
    return {"stacja": stacja_id, "zywa": _sym().stacje[stacja_id]["zywa"]}


# ---------------------------------------------------------------- CZK: zgloszenia i decyzje operatora

@app.get("/api/incydenty")
async def api_incydenty():
    return _sym().incydenty_publiczne()


@app.post("/api/decyzja/{inc_id}/{akcja}")
async def api_decyzja(inc_id: int, akcja: str):
    if akcja not in ("dron", "sluzby", "odrzuc"):
        raise HTTPException(400, "Dozwolone: dron, sluzby, odrzuc")
    if not _sym().decyzja(inc_id, akcja):
        raise HTTPException(409, "Zgloszenie zamkniete lub decyzja juz podjeta")
    await _sym().wyslij()
    return {"incydent": inc_id, "akcja": akcja}


_zdjecia_cache = {}


@app.get("/api/zdjecie/{plik}")
def api_zdjecie(plik: str):
    """
    Zdjecie zgloszenia dla operatora. Twarze sa anonimizowane (jak na pokladzie BSP) zanim obraz
    opusci serwer; plik wybierany wylacznie z katalogu (brak dostepu do dowolnych sciezek).
    """
    wpis = next((z for z in _sym().katalog_zdjec if z["plik"] == plik), None)
    if wpis is None:
        raise HTTPException(404, "Brak zdjecia")
    tryb = wczytaj_tryb_z_env()
    if (plik, tryb) not in _zdjecia_cache:
        klatka = cv2.imread(os.path.join(TUTAJ, "data", "zdjecia", wpis["plik"]))
        if klatka is None:
            raise HTTPException(404, "Brak zdjecia")
        zanonimizowana, _ = anonimizuj_klatke(klatka, tryb=tryb)
        _zdjecia_cache[(plik, tryb)] = klatka_na_jpeg_bytes(zanonimizowana)
    return Response(_zdjecia_cache[(plik, tryb)], media_type="image/jpeg",
                    headers={"Cache-Control": "public, max-age=3600"})


# ---------------------------------------------------------------- analiza testow z ludnoscia

def _proc(a, b):
    return round(100 * a / b, 1) if b else None


def _agreguj(wpisy):
    prow = [w for w in wpisy if w["typ"] != "KOMUNIKAT"]
    kom = [w for w in wpisy if w["typ"] == "KOMUNIKAT"]

    def podsumuj(p, k):
        czasy = [w["czas_s"] for w in p if w["czas_s"] is not None]
        return {
            "ewakuacje": len(p),
            "powiadomieni": sum(w["powiadomieni"] for w in p),
            "podazyli": sum(w["podazyli"] for w in p),
            "w_schronie": sum(w["w_schronie"] or 0 for w in p),
            "podazanie_proc": _proc(sum(w["podazyli"] for w in p), sum(w["powiadomieni"] for w in p)),
            "dotarcie_proc": _proc(sum(w["w_schronie"] or 0 for w in p), sum(w["powiadomieni"] for w in p)),
            "sr_czas_s": round(sum(czasy) / len(czasy)) if czasy else None,
            "komunikaty": len(k),
            "reakcja_proc": _proc(sum(w["podazyli"] for w in k), sum(w["powiadomieni"] for w in k)),
        }

    wg_rodzaju = {r: podsumuj([w for w in prow if w["rodzaj"] == r], [w for w in kom if w["rodzaj"] == r])
                  for r in ("realne", "ćwiczenie")}
    wg_typu = {f"{r}|{t}": _proc(sum(w["podazyli"] for w in prow if w["rodzaj"] == r and w["typ"] == t),
                                 sum(w["powiadomieni"] for w in prow if w["rodzaj"] == r and w["typ"] == t))
               for r in ("realne", "ćwiczenie") for t in ("LUDZIE", "PANIKA")}
    return {"razem": podsumuj(prow, kom), "wg_rodzaju": wg_rodzaju, "wg_typu": wg_typu, "ostatnie": wpisy[:30]}


@app.get("/api/analiza")
async def api_analiza():
    return _agreguj(db.pobierz_ewakuacje())


@app.post("/api/analiza/wyczysc")
async def api_analiza_wyczysc():
    db.wyczysc_ewakuacje()
    return {"ok": True}


@app.get("/api/eksport/ewakuacje.csv")
async def eksport_ewakuacji():
    wpisy = db.pobierz_ewakuacje(limit=100000)
    bufor = io.StringIO()
    pisarz = csv.DictWriter(bufor, fieldnames=["id", *db.KOLUMNY_EWAKUACJI])
    pisarz.writeheader()
    pisarz.writerows(wpisy)
    return StreamingResponse(io.BytesIO(bufor.getvalue().encode("utf-8-sig")), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=hermes_testy_ewakuacji.csv"})


# ---------------------------------------------------------------- stan (odczyt z bazy)

@app.get("/api/sektory")
async def api_sektory():
    return db.pobierz_sektory()


@app.get("/api/drony")
async def api_drony():
    return _sym().drony_publiczne()


@app.get("/api/zdarzenia")
async def api_zdarzenia(limit: int = 200):
    return db.pobierz_zdarzenia(limit=limit)


@app.get("/api/statystyki")
async def api_statystyki():
    return db.liczba_sektorow_wg_statusu()


# ---------------------------------------------------------------- anonimizacja - RODO by design

@app.get("/api/anonimizacja/demo")
def api_anonimizacja_demo(tryb: str | None = None):
    """
    Uruchamia prawdziwy pipeline edge AI (HOG + Haar + anonimizacja) na klatce testowej
    samples/test_face.jpg. Oryginal jest zwracany WYLACZNIE do porownania w panelu demo -
    w systemie operacyjnym oryginalna klatka nigdy nie opuszcza pokladu drona.
    """
    sciezka = os.path.join(TUTAJ, "samples", "test_face.jpg")
    klatka = cv2.imread(sciezka)
    if klatka is None:
        return JSONResponse({"blad": "Brak lub uszkodzony plik samples/test_face.jpg"}, status_code=404)

    tryb = tryb if tryb in TRYBY_DOZWOLONE else wczytaj_tryb_z_env()
    metadane, zanonimizowana = przetworz_klatke_na_pokladzie(klatka, tryb_anonimizacji=tryb)
    osoby = max(metadane["liczba_osob"], metadane["liczba_zanonimizowanych_twarzy"])

    return {
        "tryb_anonimizacji": tryb,
        "liczba_wykrytych_twarzy": metadane["liczba_zanonimizowanych_twarzy"],
        "oryginal_base64": base64.b64encode(klatka_na_jpeg_bytes(klatka)).decode("ascii"),
        "zanonimizowany_base64": base64.b64encode(klatka_na_jpeg_bytes(zanonimizowana)).decode("ascii"),
        "pakiet_do_czk": {"sektor": "DEMO", "status": "LUDZIE" if osoby else "OK",
                          "pewnosc": metadane["pewnosc"], "ts": db.teraz_iso(), "liczba_osob": osoby},
    }


# ---------------------------------------------------------------- dane publiczne

@app.get("/api/zrodla")
async def api_zrodla():
    return data_sources.pobierz_liste_zrodel()


@app.get("/api/pogoda")
def api_pogoda():
    # Endpoint synchroniczny: FastAPI wykonuje go w puli watkow, wiec wolne IMGW nie blokuje symulacji.
    return {"imgw": data_sources.pobierz_imgw_pogode()}


@app.get("/api/cems")
def api_cems():
    return data_sources.pobierz_copernicus_ems_aktywne()


@app.get("/api/schrony")
async def api_schrony():
    return data_sources.pobierz_schrony()


@app.get("/api/warstwy")
async def api_warstwy():
    m = _sym().mock
    stacje = m["stacje"]
    osiedla = []
    for o in data_sources.pobierz_osiedla()["osiedla"]:
        # region stacji = osiedla, ktorych srodek lezy najblizej danej stacji
        stacja = min(stacje, key=lambda s: czk_logic.odleglosc_km(o["centrum"][0], o["centrum"][1], s["lat"], s["lon"]))
        osiedla.append({"nazwa": o["nazwa"], "polygon": o["polygon"], "stacja": stacja["id"]})
    strefy = data_sources.pobierz_strefy_wojskowe()
    return {
        "sektory": m["sektory"],
        "baza": m["baza"],
        "stacje": stacje,
        "osiedla": osiedla,
        "odra": m["hydrografia_mock"]["odra"],
        "strefa_zalewowa": m["hydrografia_mock"]["strefa_zalewowa"],
        "las": m["lasy_bdl_mock"]["las"],
        "ogniska": m["lasy_bdl_mock"]["ogniska"],
        "strefy_zakazane": strefy["strefy"],
        "strefy_zrodlo": strefy.get("zrodlo", ""),
        "budynki": data_sources.pobierz_budynki()["budynki"],
        "zasieg_km": simulator.ZASIEG_MESH_KM,
        "scenariusze": {k: v["nazwa"] for k, v in m["scenariusze"].items()},
    }


@app.get("/api/mock/{klucz}")
async def api_mock(klucz: str):
    return _sym().mock.get(klucz, [])


# ---------------------------------------------------------------- eksport (wylacznie metadane)

@app.get("/api/eksport/json")
async def eksport_json():
    bufor = json.dumps(db.pobierz_zdarzenia(limit=10000), ensure_ascii=False, indent=2).encode("utf-8")
    return StreamingResponse(io.BytesIO(bufor), media_type="application/json",
                             headers={"Content-Disposition": "attachment; filename=hermes_zdarzenia.json"})


@app.get("/api/eksport/csv")
async def eksport_csv():
    zdarzenia = db.pobierz_zdarzenia(limit=10000)
    bufor = io.StringIO()
    if zdarzenia:
        pisarz = csv.DictWriter(bufor, fieldnames=list(zdarzenia[0].keys()))
        pisarz.writeheader()
        pisarz.writerows(zdarzenia)
    return StreamingResponse(io.BytesIO(bufor.getvalue().encode("utf-8-sig")), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=hermes_zdarzenia.csv"})
