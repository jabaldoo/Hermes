# data_sources.py - rejestr zrodel danych publicznych + leniwe (lazy) pobieranie realnych zrodel.
# Realnie zintegrowane: Geoportal ORTO (WMTS), Geoportal PRG (WMS), IMGW synop (API),
# KG PSP "Punkty schronienia w Polsce" (dane.gov.pl, CC BY 4.0), Copernicus EMS (proba).
# Reszta - mock_data.json. Kazde realne zrodlo ma fallback, wiec demo dziala offline.
import csv
import io
import json
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


if __name__ == "__main__":
    if "--odswiez-schrony" in sys.argv:
        print(f"Zapisano {odswiez_schrony()} punktow schronienia do {_PLIK_SCHRONOW}")
    else:
        print("Uzycie: python data_sources.py --odswiez-schrony")
