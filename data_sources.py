# data_sources.py - rejestr zrodel danych publicznych + leniwe (lazy) pobieranie realnych zrodel.
# Realnie zintegrowane: Geoportal ORTO (WMTS), Geoportal PRG (WMS), IMGW synop (API),
# KG PSP "Punkty schronienia w Polsce" (dane.gov.pl, CC BY 4.0), Copernicus EMS (proba).
# Reszta - mock_data.json. Kazde realne zrodlo ma fallback, wiec demo dziala offline.
import csv
import io
import json
import math
import os
import sys
import time

import requests

_TUTAJ = os.path.dirname(os.path.abspath(__file__))
_PLIK_SCHRONOW = os.path.join(_TUTAJ, "data", "schrony_wroclaw.json")
_TIMEOUT = (2, 4)  # (polaczenie, odczyt) - krotko, zeby nic nie wisialo w trakcie pokazu

GEOPORTAL_ORTO_WMTS = (
    "https://mapy.geoportal.gov.pl/wss/service/PZGIK/ORTO/WMTS/StandardResolution"
    "?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=ORTOFOTOMAPA&STYLE=default"
    "&FORMAT=image/jpeg&TILEMATRIXSET=EPSG:3857&TILEMATRIX=EPSG:3857:{z}&TILEROW={y}&TILECOL={x}"
)
GEOPORTAL_PRG_WMS = "https://mapy.geoportal.gov.pl/wss/service/PZGIK/PRG/WMS/AdministrativeBoundaries"
IMGW_SYNOP_WROCLAW = "https://danepubliczne.imgw.pl/api/data/synop/id/12424"
SCHRONY_CSV_URL = "https://api.dane.gov.pl/resources/1393918,punkty-schronienia-dane-csv/file"
COPERNICUS_EMS_URL = "https://emergency.copernicus.eu/mapping/list-of-activations-rapid"

ZRODLA_DANYCH = [
    {"nazwa": "Geoportal - Ortofotomapa", "typ_uzycia": "realne (WMTS)",
     "url": "https://mapy.geoportal.gov.pl/wss/service/PZGIK/ORTO/WMTS/StandardResolution",
     "jak": "Domyslna warstwa tla mapy (EPSG:3857)"},
    {"nazwa": "Geoportal - PRG (granice)", "typ_uzycia": "realne (WMS)",
     "url": GEOPORTAL_PRG_WMS, "jak": "Nakladka granic gmin (A03_Granice_gmin)"},
    {"nazwa": "KG PSP - Punkty schronienia w Polsce", "typ_uzycia": "realne (dane.gov.pl, CC BY 4.0)",
     "url": "https://dane.gov.pl/pl/dataset/28058", "jak": "Schrony na mapie + najblizsze schrony w rekomendacjach CZK"},
    {"nazwa": "OpenStreetMap - wysokie budynki", "typ_uzycia": "realne (Overpass, ODbL)",
     "url": "https://www.openstreetmap.org", "jak": "Czerwone ramki: przeszkody lotnicze >= 40 m"},
    {"nazwa": "OpenStreetMap - tereny wojskowe", "typ_uzycia": "realne (Overpass, ODbL)",
     "url": "https://www.openstreetmap.org", "jak": "Strefy zakazu lotow: obrys terenow wojskowych + bufor 250 m (model; oficjalne strefy: dronemap.pansa.pl)"},
    {"nazwa": "OpenStreetMap - osiedla Wroclawia", "typ_uzycia": "realne (Overpass, ODbL)",
     "url": "https://www.openstreetmap.org", "jak": "Regiony stacji-przekaznikow (range extenders) wg granic osiedli"},
    {"nazwa": "Wikimedia Commons - zdjecia zgloszen", "typ_uzycia": "realne (CC0 / CC BY / CC BY-SA)",
     "url": "https://commons.wikimedia.org", "jak": "Zdjecia pogladowe przy zgloszeniach dla operatora (twarze anonimizowane)"},
    {"nazwa": "CARTO - etykiety OSM", "typ_uzycia": "realne (kafle)",
     "url": "https://carto.com/basemaps", "jak": "Nazwy ulic nad ortofotomapa po przyblizeniu"},
    {"nazwa": "IMGW - meteo (synop)", "typ_uzycia": "realne (API)",
     "url": IMGW_SYNOP_WROCLAW, "jak": "Pogoda live w naglowku (stacja Wroclaw)"},
    {"nazwa": "Copernicus EMS", "typ_uzycia": "realne (proba pobrania)",
     "url": COPERNICUS_EMS_URL, "jak": "Lista aktywacji - fallback do mocka"},
    {"nazwa": "Geoportal - BDOT10k/BDOO", "typ_uzycia": "mock",
     "url": "https://mapy.geoportal.gov.pl", "jak": "Drogi/mosty w scenariuszu (ZATOR)"},
    {"nazwa": "Geoportal - NMT/NMPT", "typ_uzycia": "mock",
     "url": "https://mapy.geoportal.gov.pl", "jak": "Wysokosci w mock_data.json"},
    {"nazwa": "Geoportal - LiDAR", "typ_uzycia": "mock",
     "url": "https://mapy.geoportal.gov.pl", "jak": "Atrybut sektora"},
    {"nazwa": "Geoportal - hydrografia", "typ_uzycia": "mock",
     "url": "https://mapy.geoportal.gov.pl", "jak": "Przebieg Odry i strefa zalewowa w scenariuszu powodzi"},
    {"nazwa": "Geoportal - zdjecia lotnicze", "typ_uzycia": "mock",
     "url": "https://mapy.geoportal.gov.pl", "jak": "Przykladowe klatki w samples/"},
    {"nazwa": "Lasy Panstwowe - BDL", "typ_uzycia": "mock",
     "url": "https://www.bdl.lasy.gov.pl/portal/", "jak": "Obszar lesny w scenariuszu pozaru"},
    {"nazwa": "dane.gov.pl", "typ_uzycia": "realne + mock",
     "url": "https://dane.gov.pl", "jak": "Zbior schronow (realny) + lista zbiorow w UI"},
    {"nazwa": "IMGW - hydro", "typ_uzycia": "mock",
     "url": "https://danepubliczne.imgw.pl/api/data/hydro", "jak": "Stan Odry w scenariuszu powodzi"},
    {"nazwa": "IMGW - radar", "typ_uzycia": "mock",
     "url": "https://danepubliczne.imgw.pl", "jak": "Opad w pogodzie scenariusza"},
    {"nazwa": "Copernicus - Sentinel", "typ_uzycia": "mock",
     "url": "https://dataspace.copernicus.eu", "jak": "Metadane zobrazowan"},
    {"nazwa": "CEMS Early Warning", "typ_uzycia": "mock",
     "url": "https://emergency.copernicus.eu/", "jak": "Alert startowy w scenariuszach"},
]

_cache = {}


def _z_cache(klucz, ttl_s, funkcja):
    """Prosty cache w pamieci - realne API odpytujemy najwyzej raz na ttl_s sekund."""
    teraz = time.time()
    if klucz in _cache and teraz - _cache[klucz][0] < ttl_s:
        return _cache[klucz][1]
    wartosc = funkcja()
    _cache[klucz] = (teraz, wartosc)
    return wartosc


def _realne_wlaczone():
    return os.environ.get("UZYWAJ_REALNYCH_ZRODEL", "1") == "1"


def _wczytaj_mock():
    with open(os.path.join(_TUTAJ, "mock_data.json"), "r", encoding="utf-8") as f:
        return json.load(f)


def pobierz_liste_zrodel():
    return ZRODLA_DANYCH


def pobierz_imgw_pogode():
    """
    Pogoda live ze stacji synoptycznej IMGW Wroclaw (id 12424). Funkcja blokujaca -
    wywolywac z endpointu synchronicznego (FastAPI uruchamia go w puli watkow).
    Zwraca None, gdy zrodlo niedostepne - UI pokazuje wtedy tylko pogode scenariusza.
    """
    if not _realne_wlaczone():
        return None

    def _pobierz():
        try:
            r = requests.get(IMGW_SYNOP_WROCLAW, timeout=_TIMEOUT)
            r.raise_for_status()
            s = r.json()
            return {
                "stacja": s.get("stacja"),
                "temperatura_c": float(s.get("temperatura") or 0),
                "wiatr_kmh": round(float(s.get("predkosc_wiatru") or 0) * 3.6),
                "kierunek_wiatru_st": int(float(s.get("kierunek_wiatru") or 0)),
                "wilgotnosc_proc": float(s.get("wilgotnosc_wzgledna") or 0),
                "opad_mm": float(s.get("suma_opadu") or 0),
                "cisnienie_hpa": float(s.get("cisnienie") or 0),
                "pomiar": f"{s.get('data_pomiaru')} {s.get('godzina_pomiaru')}:00",
                "zrodlo": "IMGW-PIB (live)",
            }
        except Exception as e:
            print(f"[data_sources] IMGW niedostepne: {e}")
            return None

    return _z_cache("imgw", 600, _pobierz)


def pobierz_copernicus_ems_aktywne():
    if not _realne_wlaczone():
        return _wczytaj_mock()["copernicus_ems_mock"]

    def _pobierz():
        try:
            requests.get(COPERNICUS_EMS_URL, timeout=_TIMEOUT).raise_for_status()
            return [{"id": "EMS-LIVE", "status": "zrodlo osiagalne",
                     "info": "Pelne parsowanie aktywacji poza zakresem PoC"}] + _wczytaj_mock()["copernicus_ems_mock"]
        except Exception:
            return _wczytaj_mock()["copernicus_ems_mock"]

    return _z_cache("ems", 600, _pobierz)


def pobierz_schrony():
    """Punkty schronienia KG PSP w obszarze demo - z lokalnego snapshotu (dziala offline)."""
    if not os.path.exists(_PLIK_SCHRONOW):
        return {"zrodlo": "brak snapshotu - uruchom: python data_sources.py --odswiez-schrony", "punkty": []}
    with open(_PLIK_SCHRONOW, "r", encoding="utf-8") as f:
        return json.load(f)


def odswiez_schrony(bbox=(51.05, 16.95, 51.15, 17.15)):
    """
    Pobiera aktualny zbior KG PSP "Punkty schronienia w Polsce" (CSV, ~15 MB, aktualizacja
    co tydzien) z dane.gov.pl i zapisuje punkty z obszaru demo do data/schrony_wroclaw.json.
    """
    lat_min, lon_min, lat_max, lon_max = bbox
    r = requests.get(SCHRONY_CSV_URL, timeout=(5, 120))
    r.raise_for_status()
    czytnik = csv.DictReader(io.StringIO(r.content.decode("utf-8-sig")))
    punkty = []
    for w in czytnik:
        try:
            lat = float(w["Szerokosc geograficzna"])
            lon = float(w["Dlugosc geograficzna"])
        except (ValueError, KeyError):
            continue
        if lat_min <= lat <= lat_max and lon_min <= lon <= lon_max:
            punkty.append({
                "id": w["Identyfikator publiczny"],
                "lat": round(lat, 6),
                "lon": round(lon, 6),
                "adres": w["Adres"],
                "dostepnosc": w["Dostepnosc"],
            })
    wynik = {
        "zrodlo": "KG PSP - Punkty schronienia w Polsce (dane.gov.pl, CC BY 4.0)",
        "url": "https://dane.gov.pl/pl/dataset/28058",
        "pobrano": time.strftime("%Y-%m-%d"),
        "punkty": punkty,
    }
    os.makedirs(os.path.dirname(_PLIK_SCHRONOW), exist_ok=True)
    with open(_PLIK_SCHRONOW, "w", encoding="utf-8") as f:
        json.dump(wynik, f, ensure_ascii=False, separators=(",", ":"))
    return len(punkty)


_PLIK_BUDYNKOW = os.path.join(_TUTAJ, "data", "wysokie_budynki.json")
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
PROG_WYSOKOSCI_M = 40


def _wysokosc_m(tagi):
    for klucz, mnoznik in (("height", 1.0), ("building:levels", 3.0)):
        wartosc = (tagi.get(klucz) or "").replace(",", ".").replace("m", "").strip()
        try:
            return round(float(wartosc) * mnoznik, 1)
        except ValueError:
            continue
    return 0.0


def przetworz_osm_budynki(elementy):
    budynki = []
    for e in elementy:
        tagi, bb = e.get("tags", {}), e.get("bounds")
        h = _wysokosc_m(tagi)
        if bb and h >= PROG_WYSOKOSCI_M:
            budynki.append({"osm_id": e["id"], "nazwa": tagi.get("name", ""), "wysokosc_m": h,
                            "lat_min": bb["minlat"], "lon_min": bb["minlon"],
                            "lat_max": bb["maxlat"], "lon_max": bb["maxlon"]})
    return sorted(budynki, key=lambda b: -b["wysokosc_m"])


def odswiez_budynki(bbox=(51.05, 16.95, 51.15, 17.15)):
    """Wysokie budynki (>= 40 m) z OpenStreetMap (Overpass API, ODbL) - przeszkody lotnicze dla BSP."""
    s, w, n, e = bbox
    q = (f'[out:json][timeout:90];('
         f'way["building"]["height"~"^([4-9][0-9]|[1-9][0-9][0-9])"]({s},{w},{n},{e});'
         f'way["building"]["building:levels"~"^(1[4-9]|[2-9][0-9])$"]({s},{w},{n},{e});'
         f'way["man_made"="tower"]["height"~"^([4-9][0-9]|[1-9][0-9][0-9])"]({s},{w},{n},{e}););out tags bb;')
    r = requests.post(OVERPASS_URL, data={"data": q}, timeout=(5, 150),
                      headers={"User-Agent": "HERMES-demo/1.0", "Accept": "application/json"})
    r.raise_for_status()
    zapisz_budynki(przetworz_osm_budynki(r.json()["elements"]))


def zapisz_budynki(budynki):
    os.makedirs(os.path.dirname(_PLIK_BUDYNKOW), exist_ok=True)
    with open(_PLIK_BUDYNKOW, "w", encoding="utf-8") as f:
        json.dump({"zrodlo": "OpenStreetMap (Overpass API), © współtwórcy OpenStreetMap, ODbL",
                   "prog_m": PROG_WYSOKOSCI_M, "pobrano": time.strftime("%Y-%m-%d"), "budynki": budynki},
                  f, ensure_ascii=False, separators=(",", ":"))
    return len(budynki)


def pobierz_budynki():
    if not os.path.exists(_PLIK_BUDYNKOW):
        return {"zrodlo": "brak snapshotu - uruchom: python data_sources.py --odswiez-budynki", "budynki": []}
    with open(_PLIK_BUDYNKOW, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------- geometria (przygotowanie danych offline)

_LAT0, _LON0 = 51.10, 17.05
_KM_LAT, _KM_LON = 111.2, 69.93
_PLIK_STREF = os.path.join(_TUTAJ, "data", "strefy_wojskowe.json")
_PLIK_OSIEDLI = os.path.join(_TUTAJ, "data", "osiedla.json")
BUFOR_STREFY_KM = 0.25


def _do_km(lat, lon):
    return ((lon - _LON0) * _KM_LON, (lat - _LAT0) * _KM_LAT)


def _z_km(x, y):
    return [round(_LAT0 + y / _KM_LAT, 6), round(_LON0 + x / _KM_LON, 6)]


def _otoczka(punkty):
    """Otoczka wypukla (monotone chain), wynik w kolejnosci przeciwnej do ruchu wskazowek zegara."""
    p = sorted(set(punkty))
    if len(p) < 3:
        return p

    def krzyz(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    dol, gora = [], []
    for q in p:
        while len(dol) >= 2 and krzyz(dol[-2], dol[-1], q) <= 0:
            dol.pop()
        dol.append(q)
    for q in reversed(p):
        while len(gora) >= 2 and krzyz(gora[-2], gora[-1], q) <= 0:
            gora.pop()
        gora.append(q)
    return dol[:-1] + gora[:-1]


def _uprosc_wielokat(w, maks):
    """Visvalingam: usuwa wierzcholki o najmniejszym wplywie na ksztalt, az zostanie `maks`."""
    w = list(w)
    while len(w) > maks:
        def pole(i):
            a, b, c = w[i - 1], w[i], w[(i + 1) % len(w)]
            return abs((b[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (b[1] - a[1]))
        w.pop(min(range(len(w)), key=pole))
    return w


def odsun_wielokat(w, d):
    """Offset wielokata wypuklego (CCW) na zewnatrz o d km, z ograniczeniem ostrych naroznikow."""
    wynik = []
    n = len(w)
    for i in range(n):
        a, b, c = w[i - 1], w[i], w[(i + 1) % n]
        normalne = []
        for p, q in ((a, b), (b, c)):
            dx, dy = q[0] - p[0], q[1] - p[1]
            dl = math.hypot(dx, dy) or 1
            normalne.append((dy / dl, -dx / dl))
        bx, by = normalne[0][0] + normalne[1][0], normalne[0][1] + normalne[1][1]
        bl = math.hypot(bx, by) or 1
        bx, by = bx / bl, by / bl
        cos = bx * normalne[0][0] + by * normalne[0][1]
        dlugosc = min(d / max(cos, 1e-6), 2 * d)
        wynik.append((b[0] + bx * dlugosc, b[1] + by * dlugosc))
    return wynik


def przetworz_strefy_wojskowe(elementy, bbox=(51.05, 16.95, 51.15, 17.15)):
    """
    Tereny wojskowe z OSM (landuse=military) -> klastry -> otoczka wypukla -> bufor 250 m.
    Model demonstracyjny strefy zakazu lotow BSP; oficjalne strefy geograficzne: dronemap.pansa.pl.
    """
    obiekty = []
    for e in elementy:
        geom = e.get("geometry") or [g for m in e.get("members", []) for g in (m.get("geometry") or [])]
        if len(geom) < 3:
            continue
        pkt = [_do_km(g["lat"], g["lon"]) for g in geom]
        bb = e["bounds"]
        if bb["maxlat"] < bbox[0] - 0.01 or bb["minlat"] > bbox[2] + 0.01 or bb["maxlon"] < bbox[1] - 0.01 or bb["minlon"] > bbox[3] + 0.01:
            continue
        obiekty.append({"nazwa": e.get("tags", {}).get("name", ""), "pkt": pkt,
                        "bb": (min(p[0] for p in pkt), min(p[1] for p in pkt), max(p[0] for p in pkt), max(p[1] for p in pkt))})
    rodzic = list(range(len(obiekty)))

    def korzen(i):
        while rodzic[i] != i:
            rodzic[i] = rodzic[rodzic[i]]
            i = rodzic[i]
        return i
    for i, a in enumerate(obiekty):
        for j in range(i + 1, len(obiekty)):
            b = obiekty[j]["bb"]
            dx = max(0, max(a["bb"][0], b[0]) - min(a["bb"][2], b[2]))
            dy = max(0, max(a["bb"][1], b[1]) - min(a["bb"][3], b[3]))
            if math.hypot(dx, dy) < 0.4:
                rodzic[korzen(i)] = korzen(j)
    klastry = {}
    for i, o in enumerate(obiekty):
        klastry.setdefault(korzen(i), []).append(o)
    strefy = []
    for grupa in sorted(klastry.values(), key=lambda g: -sum(len(o["pkt"]) for o in g)):
        otoczka = _uprosc_wielokat(_otoczka([p for o in grupa for p in o["pkt"]]), 10)
        if len(otoczka) < 3:
            continue
        strefa = odsun_wielokat(otoczka, BUFOR_STREFY_KM)
        nazwy = sorted({o["nazwa"] for o in grupa if o["nazwa"]})
        strefy.append({
            "id": f"W-{len(strefy) + 1}",
            "nazwa": nazwy[0] if nazwy else "Teren wojskowy",
            "obiekty_wojskowe": nazwy,
            "polygon": [_z_km(*p) for p in strefa],
            "tereny": [[_z_km(*p) for p in o["pkt"]] for o in grupa],
        })
    return strefy


def odswiez_strefy_wojskowe():
    q = ('[out:json][timeout:120];(way["landuse"="military"](51.03,16.92,51.17,17.18);'
         'relation["landuse"="military"](51.03,16.92,51.17,17.18););out geom;')
    r = requests.post(OVERPASS_URL, data={"data": q}, timeout=(5, 180), headers={"User-Agent": "HERMES-demo/1.0"})
    r.raise_for_status()
    return zapisz_strefy(przetworz_strefy_wojskowe(r.json()["elements"]))


def zapisz_strefy(strefy):
    os.makedirs(os.path.dirname(_PLIK_STREF), exist_ok=True)
    with open(_PLIK_STREF, "w", encoding="utf-8") as f:
        json.dump({"zrodlo": "Tereny wojskowe: OpenStreetMap (landuse=military), © współtwórcy OSM, ODbL. "
                             "Bufor 250 m — model demonstracyjny; oficjalne strefy: dronemap.pansa.pl",
                   "bufor_m": int(BUFOR_STREFY_KM * 1000), "pobrano": time.strftime("%Y-%m-%d"), "strefy": strefy},
                  f, ensure_ascii=False, separators=(",", ":"))
    return len(strefy)


def pobierz_strefy_wojskowe():
    if not os.path.exists(_PLIK_STREF):
        return {"strefy": []}
    with open(_PLIK_STREF, "r", encoding="utf-8") as f:
        return json.load(f)


def _zszyj_pierscienie(drogi):
    """Laczy linie (listy punktow) w zamkniete pierscienie po wspolnych koncach."""
    drogi = [list(d) for d in drogi if len(d) >= 2]
    pierscienie = []
    while drogi:
        pierscien = drogi.pop(0)
        zmiana = True
        while pierscien[0] != pierscien[-1] and zmiana:
            zmiana = False
            for i, d in enumerate(drogi):
                if d[0] == pierscien[-1]:
                    pierscien += d[1:]
                elif d[-1] == pierscien[-1]:
                    pierscien += d[::-1][1:]
                else:
                    continue
                drogi.pop(i)
                zmiana = True
                break
        pierscienie.append(pierscien)
    return pierscienie


def _douglas_peucker(pkt, tol):
    if len(pkt) < 3:
        return pkt
    (x1, y1), (x2, y2) = pkt[0], pkt[-1]
    dl = math.hypot(x2 - x1, y2 - y1) or 1e-9
    odl = [abs((x2 - x1) * (y1 - y) - (x1 - x) * (y2 - y1)) / dl for x, y in pkt[1:-1]]
    i = max(range(len(odl)), key=odl.__getitem__)
    if odl[i] <= tol:
        return [pkt[0], pkt[-1]]
    return _douglas_peucker(pkt[:i + 2], tol)[:-1] + _douglas_peucker(pkt[i + 1:], tol)


def przetworz_osiedla(elementy, bbox=(51.05, 16.95, 51.15, 17.15)):
    """Osiedla Wroclawia (granice administracyjne OSM) przycinane do obszaru demo."""
    osiedla = []
    for e in elementy:
        drogi = [[(round(g["lon"], 6), round(g["lat"], 6)) for g in m["geometry"]]
                 for m in e.get("members", []) if m.get("role") == "outer" and m.get("geometry")]
        pierscienie = [p for p in _zszyj_pierscienie(drogi) if len(p) > 3]
        if not pierscienie:
            continue
        km = [[_do_km(lat, lon) for lon, lat in p] for p in pierscienie]
        pierscien = max(km, key=lambda p: abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(p, p[1:] + p[:1]))))
        # pierscien zamkniety: dzielimy w punkcie najdalszym od poczatku, zeby DP mial niezdegenerowana cieciwe
        k = max(range(len(pierscien)), key=lambda i: math.dist(pierscien[0], pierscien[i]))
        uproszczony = _douglas_peucker(pierscien[:k + 1], 0.02)[:-1] + _douglas_peucker(pierscien[k:], 0.02)[:-1]
        lat = [_z_km(*p)[0] for p in uproszczony]
        lon = [_z_km(*p)[1] for p in uproszczony]
        if max(lat) < bbox[0] or min(lat) > bbox[2] or max(lon) < bbox[1] or min(lon) > bbox[3]:
            continue
        sx = sum(p[0] for p in uproszczony) / len(uproszczony)
        sy = sum(p[1] for p in uproszczony) / len(uproszczony)
        osiedla.append({"nazwa": e["tags"].get("name", "?"), "polygon": [_z_km(*p) for p in uproszczony],
                        "centrum": _z_km(sx, sy)})
    return sorted(osiedla, key=lambda o: o["nazwa"])


def odswiez_osiedla():
    q = ('[out:json][timeout:150];area["name"="Wrocław"]["boundary"="administrative"]["admin_level"="6"]->.w;'
         '(relation["boundary"="administrative"]["admin_level"="9"](area.w););out geom;')
    r = requests.post(OVERPASS_URL, data={"data": q}, timeout=(5, 200), headers={"User-Agent": "HERMES-demo/1.0"})
    r.raise_for_status()
    return zapisz_osiedla(przetworz_osiedla(r.json()["elements"]))


def zapisz_osiedla(osiedla):
    with open(_PLIK_OSIEDLI, "w", encoding="utf-8") as f:
        json.dump({"zrodlo": "Osiedla Wrocławia: OpenStreetMap (admin_level=9), © współtwórcy OSM, ODbL",
                   "pobrano": time.strftime("%Y-%m-%d"), "osiedla": osiedla}, f, ensure_ascii=False, separators=(",", ":"))
    return len(osiedla)


def pobierz_osiedla():
    if not os.path.exists(_PLIK_OSIEDLI):
        return {"osiedla": []}
    with open(_PLIK_OSIEDLI, "r", encoding="utf-8") as f:
        return json.load(f)


if __name__ == "__main__":
    if "--odswiez-strefy" in sys.argv:
        print(f"Zapisano {odswiez_strefy_wojskowe()} stref wojskowych")
    elif "--odswiez-osiedla" in sys.argv:
        print(f"Zapisano {odswiez_osiedla()} osiedli")
    elif "--odswiez-schrony" in sys.argv:
        print(f"Zapisano {odswiez_schrony()} punktow schronienia do {_PLIK_SCHRONOW}")
    elif "--odswiez-budynki" in sys.argv:
        odswiez_budynki()
        print(f"Zapisano {len(pobierz_budynki()['budynki'])} wysokich budynkow do {_PLIK_BUDYNKOW}")
    else:
        print("Uzycie: python data_sources.py --odswiez-schrony | --odswiez-budynki | --odswiez-strefy | --odswiez-osiedla")
