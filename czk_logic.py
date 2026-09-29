# czk_logic.py - reguly CZK: typy incydentow -> sluzby (Policja / PSP / ZRM), priorytety,
# format wspolrzednych dla sluzb oraz wybor najblizszych schronow.
import math

# prowadzenie = dron z glosnikiem prowadzi ludzi do schronu; komunikat = natychmiastowe ostrzezenie
TYPY = {
    "POMOC":      {"nazwa": "Osoby poszkodowane / uwięzione", "sluzby": ["ZRM", "PSP"], "priorytet": 1},
    "WYPADEK":    {"nazwa": "Wypadek drogowy", "sluzby": ["Policja", "ZRM", "PSP"], "priorytet": 1},
    "POZAR":      {"nazwa": "Pożar", "sluzby": ["PSP", "ZRM"], "priorytet": 1},
    "ZAGROZENIE": {"nazwa": "Zagrożenie natychmiastowe", "sluzby": ["Policja", "PSP"], "priorytet": 1, "komunikat": True},
    "PANIKA":     {"nazwa": "Panika w tłumie", "sluzby": ["Policja"], "priorytet": 2, "prowadzenie": True},
    "LUDZIE":     {"nazwa": "Osoby w strefie zagrożenia", "sluzby": [], "priorytet": 2, "prowadzenie": True},
    "ZATOR":      {"nazwa": "Zator / zablokowana droga", "sluzby": ["Policja"], "priorytet": 3},
}
STATUSY = ("OK",) + tuple(TYPY)
NAZWY_SLUZB = {"Policja": "Policja", "PSP": "Straż Pożarna (PSP)", "ZRM": "Pogotowie (ZRM)"}

# Zaopatrzenie medyczne zrzucane przez BSP - wg typu incydentu, w kolejnosci waznosci
ZAOPATRZENIE_WG_TYPU = {
    "POMOC": ["Opaska uciskowa", "Opatrunek hemostatyczny", "Koc termiczny NRC", "Chusta trójkątna"],
    "WYPADEK": ["Opatrunek hemostatyczny", "Koc termiczny NRC", "Bandaż elastyczny", "Opaska uciskowa"],
    "POZAR": ["Żel na oparzenia", "Koc termiczny NRC", "Woda 0,33 l", "Maseczka do RKO"],
}

_KARA_DOSTEPNOSCI_KM = 0.4


def rekomenduj_akcje(typ, sektor_id=None, liczba_osob=0):
    t = TYPY.get(typ)
    if t is None:
        return {"sektor": sektor_id, "status": typ, "jednostki_rekomendowane": [], "priorytet": 9,
                "opis": "Brak zagrożenia.", "prowadzenie": False, "liczba_osob": liczba_osob}
    return {
        "sektor": sektor_id, "status": typ, "opis": t["nazwa"],
        "jednostki_rekomendowane": list(t["sluzby"]), "priorytet": t["priorytet"],
        "prowadzenie": t.get("prowadzenie", False), "liczba_osob": liczba_osob,
    }


_AKCJE_DRONA = {
    "prowadzenie": "Wyślij drona z głośnikiem — poprowadzi ludzi do najbliższego schronu",
    "zrzut": "Wyślij drona z apteczką — zrzut zaopatrzenia medycznego",
    "ostrzezenie": "Wyślij drona z głośnikiem — ostrzeże ludzi w rejonie",
    "obserwacja": "Wyślij drona do obserwacji miejsca zdarzenia",
}


def akcja_drona(typ, osoby):
    """Co zrobi dron, jesli operator zdecyduje sie go wyslac. Zwraca (rodzaj, opis dla operatora)."""
    if typ in ("LUDZIE", "PANIKA") and osoby > 0:
        rodzaj = "prowadzenie"
    elif typ in ZAOPATRZENIE_WG_TYPU and osoby > 0:
        rodzaj = "zrzut"
    elif typ == "ZAGROZENIE":
        rodzaj = "ostrzezenie"
    else:
        rodzaj = "obserwacja"
    return rodzaj, _AKCJE_DRONA[rodzaj]


def posortuj_rekomendacje_wg_priorytetu(lista):
    return sorted(lista, key=lambda r: (r["priorytet"], -r.get("liczba_osob", 0)))


def status_sektora(typy_aktywne):
    """Status sektora = najpilniejszy aktywny incydent w nim (albo OK)."""
    if not typy_aktywne:
        return "OK"
    return min(typy_aktywne, key=lambda t: (TYPY[t]["priorytet"], list(TYPY).index(t)))


def wspolrzedne_txt(lat, lon):
    return f"{abs(lat):.5f}° {'N' if lat >= 0 else 'S'}, {abs(lon):.5f}° {'E' if lon >= 0 else 'W'}"


def odleglosc_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def najblizsze_schrony(lat, lon, punkty, n=3, wyklucz=None):
    """n najlepszych punktow schronienia KG PSP; obiekty calodobowe preferowane (kara odleglosci dla pozostalych)."""
    ocenione = []
    for p in punkty:
        if wyklucz and wyklucz(p):
            continue
        d = odleglosc_km(lat, lon, p["lat"], p["lon"])
        kara = 0.0 if p.get("dostepnosc") == "Całodobowa" else _KARA_DOSTEPNOSCI_KM
        ocenione.append((d + kara, d, p))
    ocenione.sort(key=lambda x: x[0])
    return [dict(p, odleglosc_km=round(d, 2)) for _, d, p in ocenione[:n]]


def wybierz_zaopatrzenie(typ, zapas, maks=2):
    """Ktore przedmioty dron zrzuca dla danego incydentu (po 1 szt., najwyzej `maks`)."""
    return [p for p in ZAOPATRZENIE_WG_TYPU.get(typ, []) if zapas.get(p, 0) > 0][:maks]
