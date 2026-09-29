# czk_logic.py - reguly rekomendacji dzialan dla Centrum Zarzadzania Kryzysowego (CZK).
# Proste i deterministyczne - latwe do wytlumaczenia jury i do audytu decyzji.
import math

STATUSY = ("OK", "LUDZIE", "ZATOR", "POMOC")

_REGULY = {
    "POMOC": {"jednostki": ["Karetka", "PSP"], "priorytet": 1,
              "opis": "Osoby poszkodowane / uwięzione — natychmiastowa pomoc."},
    "LUDZIE": {"jednostki": ["OSP", "PSP"], "priorytet": 2,
               "opis": "Osoby w strefie zagrożenia — ewakuacja do miejsca schronienia."},
    "ZATOR": {"jednostki": ["Policja"], "priorytet": 3,
              "opis": "Zator utrudniający ewakuację i dojazd służb — udrożnienie, objazd."},
    "OK": {"jednostki": [], "priorytet": 4, "opis": "Brak zagrożenia w sektorze."},
}

# Kara (w km) dla schronow niedostepnych calodobowo - przy ewakuacji liczy sie pewny dostep.
_KARA_DOSTEPNOSCI_KM = 0.4


def rekomenduj_akcje(status_sektora, sektor_id=None, liczba_osob=0):
    regula = _REGULY.get(status_sektora, _REGULY["OK"])
    return {
        "sektor": sektor_id,
        "status": status_sektora,
        "jednostki_rekomendowane": regula["jednostki"],
        "priorytet": regula["priorytet"],
        "opis": regula["opis"],
        "liczba_osob": liczba_osob,
    }


def posortuj_rekomendacje_wg_priorytetu(lista_rekomendacji):
    """Nizszy priorytet = pilniejsze; przy remisie wiecej osob wyzej."""
    return sorted(lista_rekomendacji, key=lambda r: (r["priorytet"], -r.get("liczba_osob", 0)))


def odleglosc_km(lat1, lon1, lat2, lon2):
    """Odleglosc po kuli ziemskiej (haversine)."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def najblizsze_schrony(lat, lon, punkty, n=3):
    """
    Zwraca n najlepszych punktow schronienia KG PSP dla ewakuacji z punktu (lat, lon).
    Preferowane sa obiekty dostepne calodobowo (pozostale dostaja kare odleglosci).
    """
    ocenione = []
    for p in punkty:
        d = odleglosc_km(lat, lon, p["lat"], p["lon"])
        kara = 0.0 if p.get("dostepnosc") == "Całodobowa" else _KARA_DOSTEPNOSCI_KM
        ocenione.append((d + kara, d, p))
    ocenione.sort(key=lambda x: x[0])
    return [dict(p, odleglosc_km=round(d, 2)) for _, d, p in ocenione[:n]]
