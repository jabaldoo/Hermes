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
from anonymizer import TRYBY_DOZWOLONE, klatka_na_jpeg_bytes, wczytaj_tryb_z_env
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
    sektor = _sym()._sektor_dla(d["lat"], d["lon"]) or "C3"
    _sym()._komunikat(d, sektor)
    await _sym().wyslij()
    return {"dron": dron_id, "sektor": sektor}


# ---------------------------------------------------------------- CZK: rekomendacje i dysponowanie

@app.get("/api/rekomendacje")
async def api_rekomendacje():
    return _sym().rekomendacje()


@app.post("/api/dysponuj/{sektor}")
async def api_dysponuj(sektor: str):
    wynik = _sym().dysponuj(sektor)
    if wynik is None:
        raise HTTPException(409, "Sektor bez zagrozenia lub juz w realizacji")
    await _sym().wyslij()
    return wynik


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
    return {
        "sektory": m["sektory"],
        "baza": m["baza"],
        "jednostki": m["jednostki"],
        "odra": m["hydrografia_mock"]["odra"],
        "strefa_zalewowa": m["hydrografia_mock"]["strefa_zalewowa"],
        "las": m["lasy_bdl_mock"]["las"],
        "ogniska": m["lasy_bdl_mock"]["ogniska"],
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
