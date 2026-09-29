# simulator.py - silnik symulacji roju HERMES (zamiast ROS2/Gazebo).
# - scenariusze (mock_data.json -> "scenariusze"), 8 dronow bazujacych na stacjach-przekaznikach (range extenders),
# - zgloszenia do OPERATORA: typ, wspolrzedne, zanonimizowane zdjecie; operator decyduje: wyslac drona,
#   przekazac sluzbom czy odrzucic - system niczego nie wysyla automatycznie,
# - drony z glosnikiem prowadza grupy do najblizszych schronow KG PSP; wyniki (ilu posluchalo) trafiaja do analizy,
# - omijanie stref zakazu lotow (wielokaty wokol terenow wojskowych z OSM), siec mesh ze stacjami.
import asyncio
import heapq
import json
import math
import os
import random
import traceback
from collections import Counter, deque

import czk_logic
import data_sources
import db
import edge_ai

_TUTAJ = os.path.dirname(os.path.abspath(__file__))

SEK_NA_TICK = 5
INTERWAL_S = 0.5
KROK_KM = 0.2
KROK_PROWADZENIA_KM = 0.05     # tempo marszu grupy za dronem (czas misji jest skompresowany)
ZASIEG_MESH_KM = 4.5
TICKI_SKANU = 4
TICKI_WEZWANIA = 4
TICKI_OBSERWACJI = 10
ORBITA_KM = 0.35
ORBITA_PRZEKAZNIKA_KM = 0.15
ZUZYCIE_BATERII = 0.12
LADOWANIE = 3.0
PROG_RTB = 20.0
MARGINES_STREFY_KM = 0.15      # dron trzyma sie tyle od granicy strefy zakazu lotow
KM_NA_STOPIEN_LAT = 111.2
KM_NA_STOPIEN_LON = 69.93
LAT0, LON0 = 51.10, 17.05
MAKS_OCZEKUJACYCH = 8          # w patrolu nowe zgloszenia wstrzymane, gdy operator ma tyle nierozpatrzonych

WAGI_PATROLU = {"LUDZIE": 18, "ZATOR": 14, "WYPADEK": 14, "POMOC": 10, "POZAR": 7, "PANIKA": 7, "ZAGROZENIE": 4}
SZANSA_WYKRYCIA_PATROL = 0.012
OPISY_PATROLU = {
    "LUDZIE": ["grupa osób w rejonie zagrożenia", "osoby przy zamkniętym przejściu"],
    "ZATOR": ["zablokowany przejazd", "zator na skrzyżowaniu"],
    "WYPADEK": ["zderzenie dwóch samochodów", "potrącenie pieszego", "samochód w rowie"],
    "POMOC": ["osoba leżąca, brak ruchu", "osoba z urazem po upadku"],
    "POZAR": ["dym z budynku mieszkalnego", "pożar budynku gospodarczego"],
    "PANIKA": ["tłum w chaotycznym ruchu — panika", "gwałtowna ucieczka grupy osób"],
    "ZAGROZENIE": ["niewybuch (pozostałość wojenna) na placu budowy", "wyciek gazu — ludzie w pobliżu",
                   "uszkodzona konstrukcja budynku — ryzyko zawalenia"],
}
OSOBY_PATROLU = {"LUDZIE": (4, 16), "PANIKA": (8, 25), "WYPADEK": (1, 4), "POMOC": (1, 2),
                 "POZAR": (0, 3), "ZAGROZENIE": (0, 0), "ZATOR": (0, 0)}

# Model reakcji ludnosci (demonstracyjny): prawdopodobienstwo, ze osoba podazy za dronem / zareaguje na komunikat
PODAZANIE = {("realne", "LUDZIE"): 0.84, ("realne", "PANIKA"): 0.63,
             ("ćwiczenie", "LUDZIE"): 0.55, ("ćwiczenie", "PANIKA"): 0.42}
REAKCJA_KOMUNIKATU = {"realne": 0.72, "ćwiczenie": 0.38}

OPIS_FAZY = {
    "baza": "Na stacji — gotowy", "lot": "Przelot → {s}", "skan": "Rozpoznanie {s} (edge AI)",
    "orbita": "Obserwacja {s} — analiza ruchu tłumu", "przekaznik": "Przekaźnik mesh — {s}",
    "patrol": "Patrol regionu — szuka osób w panice i zagrożeń",
    "rtb": "Powrót na stację (bateria)", "ladowanie": "Wymiana baterii i uzupełnienie apteczki",
    "utracony": "UTRACONY — brak telemetrii", "wezwanie": "Wzywa grupę przez głośnik ({s})",
    "prowadzi": "Prowadzi grupę w bezpieczne miejsce", "obserwuje": "Na miejscu zdarzenia ({s})",
    "uziemiony": "Uziemiony na stacji — opad powyżej limitu IP43",
}

# Flota a pogoda: standardowe BSP (IP43) lataja najwyzej w lekkim deszczu. Przy mocniejszym opadzie startuja
# tylko drony w wersji deszczowej (IP55, mocniejsze silniki) - jest ich mniej, reszta zostaje na stacjach.
LIMIT_OPADU_STD_MM_H = 4.0
SILNY_OPAD_MM_H = 12.0
SPEC_STD = "IP43 · deszcz do 4 mm/h · wiatr do 36 km/h"
SPEC_DESZCZ = "IP55 · deszcz do 25 mm/h · wiatr do 54 km/h"

# Komunikaty z glosnika, gdy dron nie prowadzi ludzi, tylko dziala na miejscu zdarzenia
KOMUNIKAT_ODSUNIECIA = {
    "pozar_budynek": "Uwaga! Trwa akcja gaśnicza. Odsuń się od budynku na co najmniej 100 metrów "
                     "i zostaw wolny przejazd dla straży pożarnej.",
    "patrol": "Uwaga! To miejsce jest niebezpieczne. Odejdź na bezpieczną odległość i nie utrudniaj pracy służb.",
}
KOMUNIKAT_USPOKOJENIA = ("Uwaga! Zachowaj spokój i nie biegnij. Odejdź powoli na otwartą przestrzeń "
                         "i pomóż osobom, które upadły.")
RODZAJE_Z_GLOSNIKIEM = ("prowadzenie", "ostrzezenie", "odsuniecie", "uspokojenie")
RODZAJE_NA_MIEJSCU = ("zrzut", "ostrzezenie", "odsuniecie", "uspokojenie", "obserwacja")


def _wczytaj_mock():
    with open(os.path.join(_TUTAJ, "mock_data.json"), "r", encoding="utf-8") as f:
        return json.load(f)


def _wczytaj_katalog_zdjec():
    sciezka = os.path.join(_TUTAJ, "data", "zdjecia", "katalog.json")
    if not os.path.exists(sciezka):
        return []
    with open(sciezka, "r", encoding="utf-8") as f:
        return json.load(f)["zdjecia"]


# ---------------------------------------------------------------- geometria (km, uklad lokalny)

def _xy(p):
    return ((p[1] - LON0) * KM_NA_STOPIEN_LON, (p[0] - LAT0) * KM_NA_STOPIEN_LAT)


def _ll(q):
    return (LAT0 + q[1] / KM_NA_STOPIEN_LAT, LON0 + q[0] / KM_NA_STOPIEN_LON)


def _km(a, b):
    return math.hypot((a[0] - b[0]) * KM_NA_STOPIEN_LAT, (a[1] - b[1]) * KM_NA_STOPIEN_LON)


def _w_wielokacie(p, w):
    x, y = p
    wewnatrz = False
    for i in range(len(w)):
        (x1, y1), (x2, y2) = w[i - 1], w[i]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            wewnatrz = not wewnatrz
    return wewnatrz


def _odcinki_sie_przecinaja(p1, p2, q1, q2):
    def orient(a, b, c):
        v = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
        return (v > 1e-12) - (v < -1e-12)
    o1, o2, o3, o4 = orient(p1, p2, q1), orient(p1, p2, q2), orient(q1, q2, p1), orient(q1, q2, p2)
    return o1 != o2 and o3 != o4


def _odcinek_przecina_wielokat(a, b, w, bb):
    if max(a[0], b[0]) < bb[0] or min(a[0], b[0]) > bb[2] or max(a[1], b[1]) < bb[1] or min(a[1], b[1]) > bb[3]:
        return False
    if _w_wielokacie(a, w) or _w_wielokacie(b, w):
        return True
    return any(_odcinki_sie_przecinaja(a, b, w[i - 1], w[i]) for i in range(len(w)))


def _najblizszy_na_brzegu(p, w):
    najlepszy, odl_min = None, 1e18
    for i in range(len(w)):
        (x1, y1), (x2, y2) = w[i - 1], w[i]
        dx, dy = x2 - x1, y2 - y1
        t = max(0.0, min(1.0, ((p[0] - x1) * dx + (p[1] - y1) * dy) / ((dx * dx + dy * dy) or 1e-12)))
        q = (x1 + t * dx, y1 + t * dy)
        d = math.hypot(q[0] - p[0], q[1] - p[1])
        if d < odl_min:
            najlepszy, odl_min = q, d
    return najlepszy


def _przecina(p0, p1, r):
    """Czy odcinek p0-p1 (lat, lon) przecina prostokat r = (lat_min, lat_max, lon_min, lon_max)."""
    w = [_xy((r[0], r[2])), _xy((r[0], r[3])), _xy((r[1], r[3])), _xy((r[1], r[2]))]
    return _odcinek_przecina_wielokat(_xy(p0), _xy(p1), w, (w[0][0], w[0][1], w[2][0], w[2][1]))


class Symulator:
    def __init__(self):
        self.mock = _wczytaj_mock()
        self.baza = self.mock["baza"]
        self.sektory_def = {s["id"]: s for s in self.mock["sektory"]}
        self.stacje = {s["id"]: dict(s, zywa=True) for s in self.mock["stacje"]}
        self.strefy = [{"id": s["id"], "nazwa": s["nazwa"], "w": [_xy(p) for p in s["polygon"]], "cache": {}}
                       for s in data_sources.pobierz_strefy_wojskowe()["strefy"]]
        self.schrony = [p for p in data_sources.pobierz_schrony()["punkty"]
                        if not self._w_strefie(p["lat"], p["lon"])]
        self.katalog_zdjec = _wczytaj_katalog_zdjec()
        # wielokaty do wyboru celu ewakuacji: strefa zalewowa Odry i obrys Lasu Osobowickiego
        odra = data_sources.pobierz_odre()
        zalew = odra["strefa_zalewowa"] if odra else self.mock["hydrografia_mock"]["strefa_zalewowa"]
        self.zalew_xy = [_xy(p) for p in zalew]
        self.las_xy = [_xy(p) for p in self.mock["lasy_bdl_mock"]["las"]]
        self.broadcast = None
        self.pauza = False
        self.predkosc = 1
        self.uruchom_scenariusz("patrol")

    # ------------------------------------------------------------------ strefy zakazu lotow

    def _strefa(self, s, margines_km):
        """Wielokat strefy odsuniety o margines (w km) + jego bbox - liczone raz i zapamietywane."""
        klucz = round(margines_km, 4)
        if klucz not in s["cache"]:
            w = data_sources.odsun_wielokat(s["w"], margines_km) if margines_km > 0 else s["w"]
            bb = (min(p[0] for p in w), min(p[1] for p in w), max(p[0] for p in w), max(p[1] for p in w))
            s["cache"][klucz] = (w, bb)
        return s["cache"][klucz]

    def _w_strefie(self, lat, lon, margines_km=0.0):
        p = _xy((lat, lon))
        for s in self.strefy:
            w, bb = self._strefa(s, margines_km)
            if bb[0] <= p[0] <= bb[2] and bb[1] <= p[1] <= bb[3] and _w_wielokacie(p, w):
                return s
        return None

    def _koliduje(self, a, b):
        pa, pb = _xy(a), _xy(b)
        return [s for s in self.strefy if _odcinek_przecina_wielokat(pa, pb, *self._strefa(s, MARGINES_STREFY_KM * 0.6))]

    def _poza_strefa(self, p):
        """Punkt wewnatrz strefy (z marginesem) przesuwamy na najblizsza krawedz dozwolonej przestrzeni."""
        s = self._w_strefie(p[0], p[1], MARGINES_STREFY_KM)
        if s is None:
            return tuple(p)
        w, _ = self._strefa(s, MARGINES_STREFY_KM * 1.05)
        return _ll(_najblizszy_na_brzegu(_xy(p), w))

    def _planuj(self, a, b):
        """Trasa omijajaca strefy: graf widocznosci na wierzcholkach stref (z marginesem) + Dijkstra."""
        b = self._poza_strefa(b)
        poczatek = []
        if self._w_strefie(a[0], a[1], MARGINES_STREFY_KM * 0.6):
            a = self._poza_strefa(a)
            poczatek = [a]
        if not self._koliduje(a, b):
            return poczatek + [b]
        wezly = [tuple(a), tuple(b)]
        pa, pb = _xy(a), _xy(b)
        korytarz = (min(pa[0], pb[0]) - 1.5, min(pa[1], pb[1]) - 1.5, max(pa[0], pb[0]) + 1.5, max(pa[1], pb[1]) + 1.5)
        for s in self.strefy:
            w, bb = self._strefa(s, MARGINES_STREFY_KM)
            if bb[2] < korytarz[0] or bb[0] > korytarz[2] or bb[3] < korytarz[1] or bb[1] > korytarz[3]:
                continue  # strefy daleko od korytarza lotu nie wplywaja na trase
            for q in w:
                n = _ll(q)
                if not self._w_strefie(n[0], n[1], MARGINES_STREFY_KM * 0.9):
                    wezly.append(n)
        dist, poprz, kolejka = {0: 0.0}, {}, [(0.0, 0)]
        while kolejka:
            d, i = heapq.heappop(kolejka)
            if i == 1:
                break
            if d > dist.get(i, 1e9):
                continue
            for j in range(len(wezly)):
                if j == i:
                    continue
                nd = d + _km(wezly[i], wezly[j])
                if nd < dist.get(j, 1e9) and not self._koliduje(wezly[i], wezly[j]):
                    dist[j], poprz[j] = nd, i
                    heapq.heappush(kolejka, (nd, j))
        if 1 not in poprz:
            return poczatek + [b]
        trasa, i = [], 1
        while i != 0:
            trasa.append(wezly[i])
            i = poprz[i]
        return poczatek + trasa[::-1]

    # ------------------------------------------------------------------ scenariusz

    def uruchom_scenariusz(self, klucz, wariant=None):
        scen = self.mock["scenariusze"][klucz]
        # scenariusz z wariantami (np. pozar: las / dom / blok / magazyn) - wariant losowany przy kazdym starcie
        warianty = scen.get("warianty") or {}
        self.wariant = (wariant if wariant in warianty else random.choice(list(warianty))) if warianty else None
        if self.wariant:
            scen = {**scen, **warianty[self.wariant]}
        self.scenariusz_id = klucz
        self.scenariusz = scen
        self.obszar = scen.get("obszar")
        self.rodzaj = scen.get("rodzaj", "realne")
        self.kroki = [dict(k, stan="oczekuje") for k in scen["kroki"]]
        self.czas = 0
        self.tick_nr = 0
        self.pogoda = dict(scen["pogoda"])
        self.sektory = {sid: {"status": "OK", "osoby": 0} for sid in self.sektory_def}
        self.incydenty = {}
        self.nr_incydentu = 0
        self.nr_zdjecia = {}
        self.linki = []
        self.w_schronie_scenariusz = 0
        self.zrzuty = 0
        self.do_wyslania = [{"typ": "reset"}]
        for s in self.stacje.values():
            s["zywa"] = True
        patrol = klucz == "patrol"
        baterie = [100, 64, 88, 31, 95, 77, 58, 90] if patrol else [100, 93, 97, 88, 96, 91, 94, 99]
        self.drony = {}
        for i, d in enumerate(self.mock["drony"]):
            trasa = self._losowa_trasa(d["stacja"])
            lat, lon = random.choice(trasa) if patrol else self._przy_stacji(d["stacja"], i)
            self.drony[d["id"]] = {
                "id": d["id"], "nazwa": d["nazwa"], "tryb": d["tryb"], "sensor": d["sensor"], "stacja": d["stacja"],
                "lat": lat, "lon": lon, "kurs": 0.0, "bateria": float(baterie[i % len(baterie)]),
                "zywy": True, "faza": "patrol",
                "zadanie": None, "kolejka": [], "cel": None, "skan": 0, "plan": [], "plan_cel": None,
                "orbita_kat": random.uniform(0, 2 * math.pi), "orbita_r": 0.0,
                "twarze": 0, "bufor": [], "hops": 1, "hops_poprz": 1, "nadaje": 0,
                "trasa": trasa, "trasa_idx": random.randrange(len(trasa)), "postoj": 0,
                "predkosc": random.uniform(0.75, 1.25), "orbita_kier": random.choice((1, -1)),
                "zapas": dict(d["zaopatrzenie"]), "zapas_start": dict(d["zaopatrzenie"]), "obszar": False,
                "odporny": False,
            }
        if self.obszar:
            # drony najblizsze miejscu zdarzenia przechodza na patrol wokol niego, reszta pilnuje swoich regionow
            srodek = (self.obszar["lat"], self.obszar["lon"])
            wg_odl = sorted(self.drony.values(), key=lambda d: _km((d["lat"], d["lon"]), srodek))
            grupa = wg_odl[:self.obszar.get("drony", 3)]
            # skrypt nadaje komunikat glosowy - w grupie musi byc dron z glosnikiem (najblizszy taki)
            if any(k.get("komunikat") for k in self.kroki) and not any(d["tryb"] == "aktywny" for d in grupa):
                grupa[-1] = next(d for d in wg_odl if d["tryb"] == "aktywny")
            for d in grupa:
                d["obszar"], d["trasa"], d["trasa_idx"] = True, self._trasa_drona(d, obszar=True), 0
        info_floty = self._dostosuj_flote_do_pogody()
        self._przydziel_drony_krokom()
        db.resetuj_misje()
        if info_floty:
            self._zdarzenie(None, None, "INFO", info_floty)
        self._przelicz_mesh()
        self._wykonaj_kroki_scenariusza()

    def _dostosuj_flote_do_pogody(self):
        """
        Deszcz powyzej limitu standardowych BSP: w powietrzu tylko 4-5 dronow w wersji deszczowej (IP55),
        pozostale uziemione na stacjach. Zostaja drony potrzebne w skrypcie scenariusza, a reszta miejsc
        przypada dronom z mozliwie odleglych stacji, zeby pokrycie miasta bylo rownomierne.
        """
        opad = self.pogoda.get("opad_mm_h", 0)
        if opad < LIMIT_OPADU_STD_MM_H:
            return None
        n_lot = 4 if opad >= SILNY_OPAD_MM_H else 5
        wymagane = {k["dron"] for k in self.kroki if k.get("dron")} | {d["id"] for d in self.drony.values() if d["obszar"]}
        lecace = [d for d in self.drony.values() if d["id"] in wymagane]
        reszta = [d for d in self.drony.values() if d["id"] not in wymagane]
        if not any(d["tryb"] == "aktywny" for d in lecace):  # co najmniej jeden dron z glosnikiem
            glosnik = next((d for d in reszta if d["tryb"] == "aktywny"), None)
            if glosnik:
                lecace.append(glosnik)
                reszta.remove(glosnik)
        while len(lecace) < n_lot and reszta:
            stacje = [self.stacje[d["stacja"]] for d in lecace]
            d = max(reszta, key=lambda x: min((_km((self.stacje[x["stacja"]]["lat"], self.stacje[x["stacja"]]["lon"]),
                                                   (s["lat"], s["lon"])) for s in stacje), default=0))
            lecace.append(d)
            reszta.remove(d)
        for d in lecace:
            d["odporny"] = True
            d["predkosc"] *= 0.9  # ciezsza konstrukcja - nieco wolniejszy przelot
        for i, d in enumerate(reszta):
            d["faza"], d["hops"], d["hops_poprz"] = "uziemiony", None, None
            d["lat"], d["lon"] = self._przy_stacji(d["stacja"], i)
        drony_txt = "drony" if 2 <= len(lecace) % 10 <= 4 and not 12 <= len(lecace) % 100 <= 14 else "dronów"
        return (f'Opad {opad:g} mm/h przekracza limit standardowych BSP (IP43, do {LIMIT_OPADU_STD_MM_H:g} mm/h). '
                f'W powietrzu: {len(lecace)} {drony_txt} w wersji deszczowej (IP55). '
                f'Pozostałe ({len(reszta)}) czekają na stacjach.')

    def _kontekst(self):
        """Rodzaj sytuacji - od niego zalezy, co dron proponuje operatorowi (schron tylko przy alarmie)."""
        if self.scenariusz_id in ("alarm", "cwiczenia"):
            return "schron"
        if self.scenariusz_id == "powodz":
            return "powodz"
        if self.scenariusz_id == "pozar":
            return "pozar_las" if self.wariant == "las" else "pozar_budynek"
        return "patrol"

    def _cel_prowadzenia(self, lat, lon):
        """Dokad dron prowadzi ludzi: schron (alarm), budynek poza strefa zalewowa (powodz), skraj lasu (pozar lasu)."""
        kontekst = self._kontekst()
        if kontekst == "pozar_las":
            p, w = _xy((lat, lon)), self.las_xy
            cx, cy = sum(q[0] for q in w) / len(w), sum(q[1] for q in w) / len(w)
            brzeg = _najblizszy_na_brzegu(p, w) if _w_wielokacie(p, w) else p
            dx, dy = brzeg[0] - cx, brzeg[1] - cy
            dl = math.hypot(dx, dy) or 1.0
            cel = self._poza_strefa(_ll((brzeg[0] + dx / dl * 0.35, brzeg[1] + dy / dl * 0.35)))
            return {"id": "ZBIORKA", "adres": "punkt zbiórki na skraju lasu", "lat": cel[0], "lon": cel[1],
                    "odleglosc_km": round(_km((lat, lon), cel), 2), "do": "do punktu zbiórki poza lasem",
                    "w": "w punkcie zbiórki", "adres_w_komunikacie": False, "dopisek": " Oddalaj się od dymu."}
        if kontekst == "powodz":
            # schron w piwnicy przy powodzi to pulapka - wybieramy budynek z listy KG PSP lezacy poza strefa zalewowa
            cel = czk_logic.najblizsze_schrony(lat, lon, self.schrony, n=1,
                                               wyklucz=lambda s: _w_wielokacie(_xy((s["lat"], s["lon"])), self.zalew_xy))
            if not cel:
                return None
            return dict(cel[0], do="w bezpieczne miejsce poza strefą zalewową", w="w bezpiecznym miejscu",
                        adres_w_komunikacie=True, dopisek=" Nie schodź do piwnic ani garaży podziemnych.")
        cel = czk_logic.najblizsze_schrony(lat, lon, self.schrony, n=1)
        if not cel:
            return None
        return dict(cel[0], do="do schronu", w="w schronie", adres_w_komunikacie=True, dopisek="")

    def _przydziel_drony_krokom(self):
        """
        Kroki z 'punkt' zamiast sektora / bez drona: sektor z pozycji, dron - najmniej obciazony, potem najblizszy.
        Zdarzenie z rejonem (np. pozar): wszystkie zadania dostaje tylko grupa rejonu (1-2 drony), reszta roju
        dalej patroluje miasto. Przekaznik mesh dostaje osobny dron, zeby kolejne zadania nie sciagaly go z pozycji.
        """
        zadania = [k for k in self.kroki if k["typ"] == "zadanie"]
        grupa = [d for d in self.drony.values() if d["obszar"]]
        uzyte = Counter() if grupa else Counter(k["dron"] for k in zadania if k.get("dron"))
        przekazniki = set()
        for k in sorted(zadania, key=lambda k: not k.get("przekaznik")):
            if k.get("punkt") and not k.get("sektor"):
                k["sektor"] = self._sektor_dla(*k["punkt"]) or min(
                    self.sektory_def, key=lambda sid: _km(self._srodek_sektora(sid), k["punkt"]))
            if grupa:
                kandydaci = [d for d in grupa if d["id"] not in przekazniki] or grupa
            elif k.get("dron"):
                continue
            else:
                kandydaci = [d for d in self.drony.values() if d["faza"] != "uziemiony"]
            if k.get("komunikat") and not k.get("wykrycie"):  # sam komunikat glosowy - tylko dron z glosnikiem
                kandydaci = [d for d in kandydaci if d["tryb"] == "aktywny"] or kandydaci
            cel = k.get("punkt") or self._srodek_sektora(k["sektor"])
            d = min(kandydaci, key=lambda d: (uzyte[d["id"]], _km((d["lat"], d["lon"]), cel)))
            k["dron"] = d["id"]
            uzyte[d["id"]] += 1
            if k.get("przekaznik") and len(grupa) > 1:
                przekazniki.add(d["id"])

    def _petla(self, srodek, r_min, r_max):
        """Losowa petla patrolowa: inna liczba punktow, promien, kierunek i ksztalt dla kazdego drona."""
        n = random.randint(4, 7)
        start, kier = random.uniform(0, 2 * math.pi), random.choice((1, -1))
        punkty = []
        for i in range(n):
            kat = start + kier * i * 2 * math.pi / n + random.uniform(-0.4, 0.4)
            r = random.uniform(r_min, r_max)
            lat = min(max(srodek[0] + r * math.cos(kat) / KM_NA_STOPIEN_LAT, 51.052), 51.148)
            lon = min(max(srodek[1] + r * math.sin(kat) / KM_NA_STOPIEN_LON, 16.952), 17.148)
            punkty.append(self._poza_strefa((lat, lon)))
        return punkty

    def _losowa_trasa(self, stacja_id):
        s = self.stacje[stacja_id]
        return self._petla((s["lat"], s["lon"]), 0.5, 1.7)

    def _trasa_drona(self, d, obszar=None):
        if (d["obszar"] if obszar is None else obszar) and self.obszar:
            o = self.obszar
            return self._petla((o["lat"], o["lon"]), 0.25 * o["r_km"], o["r_km"])
        return self._losowa_trasa(d["stacja"])

    def _przy_stacji(self, stacja_id, i=0):
        s = self.stacje[stacja_id]
        kat = i * math.pi / 3
        return (s["lat"] + 0.0005 * math.sin(kat), s["lon"] + 0.0008 * math.cos(kat))

    def _najblizsza_stacja(self, lat, lon):
        zywe = [s for s in self.stacje.values() if s["zywa"]]
        if not zywe:
            return None
        return min(zywe, key=lambda s: czk_logic.odleglosc_km(lat, lon, s["lat"], s["lon"]))

    def _wykonaj_kroki_scenariusza(self):
        for idx, k in enumerate(self.kroki):
            if k["stan"] != "oczekuje" or k["t"] > self.czas:
                continue
            if k["typ"] == "alert":
                k["stan"] = "wykonany"
                self._zdarzenie(None, None, "ALERT", f'{k["zrodlo"]}: {k["opis"]}')
            elif k["typ"] == "info":
                k["stan"] = "wykonany"
                self._zdarzenie(None, None, "INFO", k["opis"])
            elif k["typ"] == "alarm":
                k["stan"] = "wykonany"
                self._alarm(k["tresc"])
            elif k["typ"] == "zadanie":
                k["stan"] = "w toku"
                zadanie = {"rodzaj": "rozpoznanie", "sektor": k["sektor"], "punkt": k.get("punkt"), "wykrycie": k.get("wykrycie"),
                           "komunikat": k.get("komunikat", False), "przekaznik": k.get("przekaznik", False),
                           "krok": idx}
                dron = self.drony[k["dron"]]
                if not dron["zywy"] or dron["faza"] in ("rtb", "ladowanie", "uziemiony"):
                    dron = self._wybierz_wykonawce(zadanie, wyklucz=dron) or dron
                dron["kolejka"].append(zadanie)

    def _opis_kroku(self, k):
        if k["typ"] in ("alert", "info"):
            return k["opis"]
        if k["typ"] == "alarm":
            return f'Drony z głośnikiem nadają: „{k["tresc"]}”'
        czesci = []
        if k.get("przekaznik"):
            czesci.append("przekaźnik mesh")
        if k.get("wykrycie"):
            czesci.append(f'rozpoznanie ({czk_logic.TYPY[k["wykrycie"]["typ"]]["nazwa"].lower()})')
        if k.get("komunikat"):
            czesci.append("komunikat głosowy")
        return f'{self.drony[k["dron"]]["nazwa"]} → {k["sektor"]}: {" + ".join(czesci)}'

    # ------------------------------------------------------------------ zdarzenia / mesh

    def _zdarzenie(self, dron_id, sektor, status, opis, pewnosc=1.0, osoby=0, extra=None, lat=None, lon=None):
        """Zdarzenie od drona bez lacznosci trafia do bufora pokladowego (store-and-forward)."""
        ev = {"dron_id": dron_id, "sektor": sektor, "status": status, "pewnosc": pewnosc, "liczba_osob": osoby,
              "opis": opis, "t_sym": self.czas, "extra": extra or {}, "lat": lat, "lon": lon}
        dron = self.drony.get(dron_id) if dron_id else None
        if dron is not None and dron["hops"] is None:
            dron["bufor"].append(ev)
            return
        self._dostarcz(ev)

    def _dostarcz(self, ev, opoznienie_s=None):
        opis = ev["opis"]
        if opoznienie_s:
            opis += f" [z bufora mesh, opóźnienie {opoznienie_s} s]"
        zapis = db.zapisz_zdarzenie(ev["dron_id"], ev["sektor"], ev["status"], ev["pewnosc"], ev["liczba_osob"],
                                    opis, t_sym=ev["t_sym"], lat=ev.get("lat"), lon=ev.get("lon"))
        inc = self.incydenty.get(ev["extra"].get("inc_id"))
        if inc is not None and ev["status"] in czk_logic.TYPY:
            inc["dostarczony"] = True  # operator wie o zgloszeniu dopiero, gdy dotarlo przez mesh
            self._odswiez_sektory()
        zapis.update(ev["extra"])
        self.do_wyslania.append({"typ": "zdarzenie", "dane": zapis})

    def _ev_sys(self, dron_id, status, opis, sektor=None, extra=None, lat=None, lon=None):
        return {"dron_id": dron_id, "sektor": sektor, "status": status, "pewnosc": 1.0, "liczba_osob": 0,
                "opis": opis, "t_sym": self.czas, "extra": extra or {}, "lat": lat, "lon": lon}

    def _przelicz_mesh(self):
        """CZK i stacje (range extenders) sa spiete lacza szkieletowym; drony lacza sie radiowo z kazdym wezlem w zasiegu."""
        stale = [("CZK", self.baza["lat"], self.baza["lon"])]
        stale += [(s["id"], s["lat"], s["lon"]) for s in self.stacje.values() if s["zywa"]]
        # uziemiony dron stoi wylaczony na stacji - nie jest wezlem sieci
        drony = [(d["id"], d["lat"], d["lon"]) for d in self.drony.values() if d["zywy"] and d["faza"] != "uziemiony"]
        sasiedzi = {w[0]: [] for w in stale + drony}
        self.linki = []
        for i, a in enumerate(drony):
            for b in drony[i + 1:] + stale:
                odl = czk_logic.odleglosc_km(a[1], a[2], b[1], b[2])
                if odl <= ZASIEG_MESH_KM:
                    sasiedzi[a[0]].append(b[0])
                    sasiedzi[b[0]].append(a[0])
                    self.linki.append({"a": [a[1], a[2]], "b": [b[1], b[2]], "jakosc": round(1 - odl / ZASIEG_MESH_KM, 2)})
        hops = {w[0]: (0 if w[0] == "CZK" else 1) for w in stale}
        kolejka = deque(hops)
        while kolejka:
            w = kolejka.popleft()
            for s in sasiedzi[w]:
                if s not in hops:
                    hops[s] = hops[w] + 1
                    kolejka.append(s)
        for d in self.drony.values():
            d["hops_poprz"] = d["hops"]
            d["hops"] = hops.get(d["id"]) if d["zywy"] else None

    def _obsluz_zmiany_lacznosci(self):
        for d in self.drony.values():
            if not d["zywy"] or d["faza"] == "uziemiony":
                continue
            if d["hops_poprz"] is not None and d["hops"] is None:
                self._dostarcz(self._ev_sys(d["id"], "MESH",
                               f'CZK: brak łączności z {d["nazwa"]} — dron kontynuuje misję autonomicznie, '
                               f'metadane buforowane na pokładzie.'))
            if d["hops"] is not None and d["bufor"]:
                n = len(d["bufor"])
                for ev in d["bufor"]:
                    self._dostarcz(ev, opoznienie_s=self.czas - ev["t_sym"])
                d["bufor"] = []
                self._dostarcz(self._ev_sys(d["id"], "MESH",
                               f'{d["nazwa"]}: łączność przywrócona ({d["hops"]} skok.) — dostarczono {n} pakiet(y) z bufora.'))

    # ------------------------------------------------------------------ ruch

    def _krok_do(self, d, cel, krok):
        dy = (cel[0] - d["lat"]) * KM_NA_STOPIEN_LAT
        dx = (cel[1] - d["lon"]) * KM_NA_STOPIEN_LON
        odl = math.hypot(dx, dy)
        if odl > 1e-6:
            d["kurs"] = (math.degrees(math.atan2(dx, dy)) + 360) % 360
        if odl <= krok:
            d["lat"], d["lon"] = cel[0], cel[1]
            return True
        d["lat"] += dy / odl * krok / KM_NA_STOPIEN_LAT
        d["lon"] += dx / odl * krok / KM_NA_STOPIEN_LON
        return False

    def _lec(self, d, cel, krok=None, loguj=False):
        cel = tuple(cel)
        if krok is None:
            krok = KROK_KM * d.get("predkosc", 1.0)
        if d["plan_cel"] != cel:
            d["plan"] = self._planuj((d["lat"], d["lon"]), cel)
            d["plan_cel"] = cel
            if loguj and len(d["plan"]) > 1:
                strefy = {s["id"] for s in self._koliduje((d["lat"], d["lon"]), cel)}
                if strefy:
                    self._zdarzenie(d["id"], None, "INFO",
                                    f'{d["nazwa"]}: trasa omija strefę zakazu lotów {", ".join(sorted(strefy))} '
                                    f'(punkty zwrotne: {len(d["plan"]) - 1}).')
        if not d["plan"]:
            return True
        if self._krok_do(d, d["plan"][0], krok):
            d["plan"].pop(0)
        return not d["plan"]

    def _orbituj(self, d, srodek, promien=ORBITA_KM):
        """
        Krazenie nad punktem. Gdy kolejny punkt okregu wpada w strefe zakazu lotow, dron zawraca
        i lata tam i z powrotem po dozwolonym luku (zamiast stac i przeskakiwac na druga strone okregu).
        """
        kier = d.get("orbita_kier", 1)
        r = min(promien, d["orbita_r"] + 0.07)
        for _ in range(2):
            kat = d["orbita_kat"] + 0.28 * d.get("predkosc", 1.0) * kier
            lat = srodek[0] + r * math.cos(kat) / KM_NA_STOPIEN_LAT
            lon = srodek[1] + r * math.sin(kat) / KM_NA_STOPIEN_LON
            if not self._w_strefie(lat, lon, MARGINES_STREFY_KM):
                d["orbita_kat"], d["orbita_kier"] = kat, kier
                d["orbita_r"], d["lat"], d["lon"] = r, lat, lon
                d["kurs"] = (math.degrees(kat) + 90 * kier) % 360
                d["plan_cel"] = None
                return
            kier = -kier
        # oba sasiednie punkty zablokowane - najblizszy wolny punkt okregu, o ile lezy w zasiegu jednego kroku drona
        for n in range(2, 12):
            for znak in (1, -1):
                kat = d["orbita_kat"] + 0.28 * n * znak
                lat = srodek[0] + r * math.cos(kat) / KM_NA_STOPIEN_LAT
                lon = srodek[1] + r * math.sin(kat) / KM_NA_STOPIEN_LON
                if _km((lat, lon), (d["lat"], d["lon"])) <= KROK_KM and not self._w_strefie(lat, lon, MARGINES_STREFY_KM):
                    d["orbita_kat"], d["orbita_kier"] = kat, znak
                    d["orbita_r"], d["lat"], d["lon"] = r, lat, lon
                    d["kurs"] = (math.degrees(kat) + 90 * znak) % 360
                    d["plan_cel"] = None
                    return
        # nadal brak miejsca - ciasniejsze kolo, a gdy srodek lezy w marginesie strefy, przesun go na zewnatrz
        d["orbita_r"] = max(0.0, d["orbita_r"] - 0.1)
        if d["cel"] is not None and self._w_strefie(srodek[0], srodek[1], MARGINES_STREFY_KM):
            d["cel"] = list(self._poza_strefa(srodek))

    def _srodek_sektora(self, sid):
        s = self.sektory_def[sid]
        return [s["lat_centrum"], s["lon_centrum"]]

    def _sektor_dla(self, lat, lon):
        for s in self.sektory_def.values():
            if s["lat_min"] <= lat < s["lat_max"] and s["lon_min"] <= lon < s["lon_max"]:
                return s["id"]
        return None

    # ------------------------------------------------------------------ krok drona

    def _krok_drona(self, d):
        if d["faza"] == "uziemiony":
            return
        if d["nadaje"] > 0:
            d["nadaje"] -= 1
        if d["faza"] not in ("ladowanie", "baza"):
            d["bateria"] = max(0.0, d["bateria"] - ZUZYCIE_BATERII)

        if d["bateria"] < PROG_RTB and d["faza"] not in ("rtb", "ladowanie", "baza"):
            stacja = self._najblizsza_stacja(d["lat"], d["lon"])
            d["stacja_rtb"] = stacja["id"] if stacja else None
            self._zdarzenie(d["id"], None, "INFO", f'{d["nazwa"]}: bateria {d["bateria"]:.0f}% — lot na stację '
                            f'{stacja["id"] + " " + stacja["nazwa"] if stacja else "CZK"}, zadania przekazane.')
            self._przekaz_zadania(d)
            d["faza"] = "rtb"

        if d["faza"] == "rtb":
            s = self.stacje.get(d.get("stacja_rtb") or "")
            cel = (s["lat"], s["lon"]) if s and s["zywa"] else (self.baza["lat"], self.baza["lon"])
            if self._lec(d, cel):
                d["faza"] = "ladowanie"
            return
        if d["faza"] == "ladowanie":
            d["bateria"] = min(100.0, d["bateria"] + LADOWANIE)
            if d["bateria"] >= 100.0:
                uzupelnione = d["zapas"] != d["zapas_start"]
                d["zapas"] = dict(d["zapas_start"])
                d["faza"] = "patrol"
                self._zdarzenie(d["id"], None, "INFO", f'{d["nazwa"]}: bateria wymieniona'
                                + (", apteczka uzupełniona" if uzupelnione else "") + " — gotowy do misji.")
            return

        if d["zadanie"] is None and d["kolejka"]:
            self._rozpocznij_zadanie(d, d["kolejka"].pop(0))
        if d["zadanie"] is not None:
            self._wykonuj_zadanie(d, d["zadanie"])
            return

        if d["faza"] in ("orbita", "przekaznik") and d["cel"]:
            self._orbituj(d, d["cel"], ORBITA_PRZEKAZNIKA_KM if d["faza"] == "przekaznik" else ORBITA_KM)
        elif d["faza"] == "patrol":
            punkt = d["trasa"][d["trasa_idx"]]
            if d["postoj"] > 0:
                d["postoj"] -= 1
                self._orbituj(d, d["postoj_pkt"], 0.12)
            elif self._lec(d, punkt):
                d["trasa_idx"] += 1
                if d["trasa_idx"] >= len(d["trasa"]):
                    d["trasa"], d["trasa_idx"] = self._trasa_drona(d), 0
                if random.random() < 0.3:  # chwilowe krazenie nad osiagnietym punktem
                    d["postoj"], d["postoj_pkt"], d["orbita_r"] = random.randint(2, 6), punkt, 0.0
            if self.scenariusz_id == "patrol":
                self._losowe_wykrycie(d)

    def _rozpocznij_zadanie(self, d, z):
        d["skan"], d["orbita_r"] = 0, 0.0
        if z.get("inc") is not None:
            inc = self.incydenty.get(z["inc"])
            if inc is None or not inc["aktywny"]:
                return
            d["cel"] = [inc["g_lat"], inc["g_lon"]] if z["rodzaj"] == "prowadzenie" else [inc["lat"], inc["lon"]]
            d["cel"] = list(self._poza_strefa(d["cel"]))
        elif z.get("punkt"):  # konkretny adres zdarzenia (np. plonacy budynek) - tylko drobny rozrzut
            s = (z["punkt"][0] + random.uniform(-0.0006, 0.0006), z["punkt"][1] + random.uniform(-0.0009, 0.0009))
            d["cel"] = list(self._poza_strefa(s))
        else:
            s = self._srodek_sektora(z["sektor"])
            if not z.get("przekaznik"):  # przekaznik trzyma dokladna pozycje, zeby nie wypasc z zasiegu
                s = (s[0] + random.uniform(-0.003, 0.003), s[1] + random.uniform(-0.004, 0.004))
            d["cel"] = list(self._poza_strefa(s))
        d["zadanie"] = z
        d["faza"] = "lot"

    def _wykonuj_zadanie(self, d, z):
        if z["rodzaj"] == "prowadzenie":
            self._prowadz(d, z)
            return
        if z["rodzaj"] in RODZAJE_NA_MIEJSCU:
            self._akcja_na_miejscu(d, z)
            return
        if d["faza"] == "lot":
            if self._lec(d, d["cel"], loguj=True):
                d["faza"] = "skan"
            return
        self._orbituj(d, d["cel"], ORBITA_PRZEKAZNIKA_KM if z.get("przekaznik") else ORBITA_KM)
        d["skan"] += 1
        if d["skan"] < TICKI_SKANU:
            return
        sid = z["sektor"]
        if z.get("wykrycie"):
            w = z["wykrycie"]
            self._wykrycie(d, sid, w["typ"], w["osoby"], w["opis"], round(random.uniform(0.81, 0.97), 2))
        if z.get("komunikat"):
            self._komunikat(d, sid, z.get("tresc") or self._tresc_komunikatu(sid))
        if z.get("przekaznik"):
            self._zdarzenie(d["id"], sid, "MESH", f'{d["nazwa"]}: pozycja przekaźnika mesh w {sid} zajęta.')
        if z.get("krok") is not None:
            self.kroki[z["krok"]]["stan"] = "wykonany"
        d["zadanie"] = None
        # dron z grupy rejonu zdarzenia wraca do patrolu wokol niego, pozostale krazą nad miejscem rozpoznania
        d["faza"] = "przekaznik" if z.get("przekaznik") else ("patrol" if d["obszar"] else "orbita")

    def _akcja_na_miejscu(self, d, z):
        """Zadanie zlecone przez operatora: dolot, akcja (zrzut / komunikat z glosnika), obserwacja, raport."""
        inc = self.incydenty.get(z["inc"])
        if inc is None or not inc["aktywny"]:
            d["zadanie"], d["faza"] = None, "orbita"
            return
        inc["wykonawca"] = d["id"]
        if d["faza"] == "lot":
            if not self._lec(d, d["cel"], loguj=True):
                return
            inc["akcja"] = "w_toku"
            if z["rodzaj"] == "zrzut":
                przedmioty = czk_logic.wybierz_zaopatrzenie(inc["typ"], d["zapas"])
                if przedmioty:
                    self._zrzuc(d, inc, przedmioty)
            elif z["rodzaj"] == "ostrzezenie":
                self._komunikat(d, inc["sektor"], f'Uwaga! W pobliżu wykryto zagrożenie: {inc["opis"]}. '
                                                  f'Natychmiast opuść ten rejon i nie zbliżaj się.')
            elif z["rodzaj"] == "odsuniecie":
                kontekst = self._kontekst()
                self._komunikat(d, inc["sektor"], KOMUNIKAT_ODSUNIECIA.get(kontekst, KOMUNIKAT_ODSUNIECIA["patrol"]))
            elif z["rodzaj"] == "uspokojenie":
                self._komunikat(d, inc["sektor"], KOMUNIKAT_USPOKOJENIA, statystyka=False)
            d["faza"], d["skan"] = "obserwuje", 0
            return
        self._orbituj(d, d["cel"], ORBITA_PRZEKAZNIKA_KM)
        d["skan"] += 1
        if d["skan"] >= TICKI_OBSERWACJI:
            inc["akcja"] = "zakonczona"
            wynik = {"zrzut": "zaopatrzenie dostarczone", "ostrzezenie": "ludzie ostrzeżeni",
                     "odsuniecie": "ludzie odsunięci na bezpieczną odległość", "uspokojenie": "tłum uspokojony",
                     "obserwacja": "obserwacja zakończona"}[z["rodzaj"]]
            inc["wynik"] = f'{d["nazwa"]}: {wynik}' + (f' ({", ".join(inc["zrzut"])})' if inc["zrzut"] else "")
            self._zdarzenie(d["id"], inc["sektor"], "INFO",
                            f'{d["nazwa"]}: zgłoszenie #{inc["id"]} — {wynik}, dron wraca do zadań.',
                            extra={"inc_id": inc["id"]})
            d["zadanie"], d["faza"] = None, "patrol" if d["obszar"] else "orbita"

    # ------------------------------------------------------------------ zgloszenia i decyzje operatora

    def _wybierz_zdjecie(self, typ):
        pasujace = [z for z in self.katalog_zdjec if typ in z["typy"]]
        tagi = {self.scenariusz_id, f"{self.scenariusz_id}:{self.wariant}"}
        lepsze = [z for z in pasujace if tagi & set(z.get("scenariusze", []))]
        ogolne = [z for z in pasujace if not z.get("scenariusze")]
        pula = lepsze or ogolne or pasujace
        if not pula:
            return None
        n = self.nr_zdjecia.get(typ, random.randrange(len(pula)))
        self.nr_zdjecia[typ] = n + 1
        return pula[n % len(pula)]

    def _wykrycie(self, d, sid, typ, osoby, opis, pewnosc):
        lat, lon = self._poza_strefa((d["lat"] + random.uniform(-0.0012, 0.0012), d["lon"] + random.uniform(-0.0018, 0.0018)))
        self.nr_incydentu += 1
        zdjecie = self._wybierz_zdjecie(typ)
        inc = {
            "id": self.nr_incydentu, "typ": typ, "sektor": sid, "lat": lat, "lon": lon, "osoby": osoby,
            "opis": opis, "t": self.czas, "dron_id": d["id"], "aktywny": True, "dostarczony": False,
            # liczba osob na zdjeciu tylko, gdy katalog ja podaje (pole 'osoby' jest opcjonalne)
            "zdjecie": zdjecie, "osoby_na_zdjeciu": zdjecie.get("osoby", 0) if zdjecie else 0,
            "decyzja": None, "sluzby_powiadomione": False, "akcja": None, "rodzaj_akcji": None,
            "wykonawca": None, "schron": None, "g_lat": lat, "g_lon": lon,
            "podazyli": None, "w_schronie": None, "t_wezwania": None, "zrzut": [], "wynik": None,
        }
        self.incydenty[inc["id"]] = inc
        twarze = random.randint(max(0, osoby - 3), osoby) if osoby else 0
        d["twarze"] += twarze
        tekst = f'{d["sensor"]}: {opis}. Poz.: {czk_logic.wspolrzedne_txt(lat, lon)}. Zgłoszenie ze zdjęciem czeka na decyzję operatora.'
        self._zdarzenie(d["id"], sid, typ, tekst, pewnosc, inc["osoby_na_zdjeciu"],
                        extra={"inc_id": inc["id"], "zgloszenie": True}, lat=lat, lon=lon)

    def decyzja(self, inc_id, akcja):
        """Decyzja operatora: 'dron' (wyslij drona), 'sluzby' (przekaz sluzbom), 'odrzuc'."""
        inc = self.incydenty.get(inc_id)
        if inc is None or not inc["aktywny"] or not inc["dostarczony"]:
            return False
        nazwa = czk_logic.TYPY[inc["typ"]]["nazwa"]
        if akcja == "dron":
            if inc["akcja"] is not None:
                return False
            inc["decyzja"] = "dron"
            inc["rodzaj_akcji"], _ = czk_logic.akcja_drona(inc["typ"], inc["osoby"], self._kontekst())
            inc["akcja"] = "oczekuje"
            self._dostarcz(self._ev_sys(None, "DECYZJA", f'Operator zlecił wysłanie drona do zgłoszenia #{inc["id"]} ({nazwa}, {inc["sektor"]}).',
                                        sektor=inc["sektor"], extra={"inc_id": inc["id"]}))
            self._przydziel_wykonawce(inc)
        elif akcja == "sluzby":
            if inc["sluzby_powiadomione"] or not czk_logic.TYPY[inc["typ"]]["sluzby"]:
                return False
            inc["sluzby_powiadomione"] = True
            inc["decyzja"] = inc["decyzja"] or "sluzby"
            sluzby = ", ".join(czk_logic.NAZWY_SLUZB[j] for j in czk_logic.TYPY[inc["typ"]]["sluzby"])
            self._dostarcz(self._ev_sys(None, "SLUZBY", f'Operator przekazał zgłoszenie #{inc["id"]} → {sluzby}: {nazwa} — '
                                        f'{czk_logic.wspolrzedne_txt(inc["lat"], inc["lon"])} (sektor {inc["sektor"]}).',
                                        sektor=inc["sektor"], extra={"inc_id": inc["id"]}, lat=inc["lat"], lon=inc["lon"]))
            if inc["akcja"] is None:
                self._zamknij(inc, "przekazano służbom")
        elif akcja == "odrzuc":
            if inc["akcja"] in ("przydzielona", "w_toku"):
                return False
            inc["decyzja"] = "odrzucone"
            self._zamknij(inc, "odrzucone przez operatora — bez działań")
        else:
            return False
        return True

    def _zrzuc(self, d, inc, przedmioty):
        for p in przedmioty:
            d["zapas"][p] -= 1
        inc["zrzut"] += przedmioty
        self.zrzuty += 1
        self._zdarzenie(d["id"], inc["sektor"], "ZRZUT",
                        f'{d["nazwa"]}: zrzut zaopatrzenia medycznego — {", ".join(przedmioty)} (po 1 szt.). '
                        f'Poz.: {czk_logic.wspolrzedne_txt(inc["lat"], inc["lon"])}.',
                        extra={"inc_id": inc["id"]}, lat=inc["lat"], lon=inc["lon"])

    def _losowe_wykrycie(self, d):
        if random.random() > SZANSA_WYKRYCIA_PATROL:
            return
        sid = self._sektor_dla(d["lat"], d["lon"])
        if sid is None or sum(1 for i in self.incydenty.values() if i["aktywny"]) >= MAKS_OCZEKUJACYCH:
            return
        typ = random.choices(list(WAGI_PATROLU), weights=list(WAGI_PATROLU.values()))[0]
        osoby = random.randint(*OSOBY_PATROLU[typ])
        opis = random.choice(OPISY_PATROLU[typ])
        if typ in ("LUDZIE", "PANIKA"):
            # o panice decyduje klasyfikator ruchu edge AI na (symulowanych) torach sylwetek
            ocena = edge_ai.ocen_panike(self._symuluj_tory(osoby, typ == "PANIKA"))
            typ = "PANIKA" if ocena["panika"] else "LUDZIE"
            opis = f'{OPISY_PATROLU[typ][0]} (ruch {ocena["predkosc"]} m/s, chaos kierunków {ocena["chaos"]})'
        self._wykrycie(d, sid, typ, osoby, opis, round(random.uniform(0.66, 0.95), 2))

    @staticmethod
    def _symuluj_tory(n, panika):
        if panika:
            return [(v * math.cos(k), v * math.sin(k)) for v, k in
                    ((random.uniform(2.6, 5.5), random.uniform(0, 2 * math.pi)) for _ in range(n))]
        kierunek = random.uniform(0, 2 * math.pi)
        return [(v * math.cos(k), v * math.sin(k)) for v, k in
                ((random.uniform(0.6, 1.6), kierunek + random.uniform(-0.6, 0.6)) for _ in range(n))]

    def _obsluz_incydenty(self):
        for inc in list(self.incydenty.values()):
            if not inc["aktywny"] or not inc["dostarczony"]:
                continue
            if inc["akcja"] == "oczekuje":
                self._przydziel_wykonawce(inc)
            elif inc["akcja"] == "zakonczona":
                self._zamknij(inc, inc["wynik"] or "działanie drona zakończone")

    def _zamknij(self, inc, wynik):
        inc["aktywny"] = False
        inc["t_zamkniecia"] = self.czas
        inc["wynik"] = wynik
        nazwa = czk_logic.TYPY[inc["typ"]]["nazwa"]
        self._dostarcz(self._ev_sys(None, "OK", f'Zgłoszenie #{inc["id"]} — {nazwa} ({inc["sektor"]}) zamknięte: {wynik}.',
                                    sektor=inc["sektor"], extra={"inc_id": inc["id"]}, lat=inc["lat"], lon=inc["lon"]))
        self._odswiez_sektory()

    def _odswiez_sektory(self):
        aktywne = [i for i in self.incydenty.values() if i["aktywny"] and i["dostarczony"]]
        for sid in self.sektory_def:
            w_sektorze = [i for i in aktywne if i["sektor"] == sid]
            nowy = {"status": czk_logic.status_sektora([i["typ"] for i in w_sektorze]),
                    "osoby": sum(i["osoby_na_zdjeciu"] for i in w_sektorze)}
            if nowy != self.sektory[sid]:
                self.sektory[sid] = nowy
                db.aktualizuj_sektor(sid, nowy["status"], nowy["osoby"])

    # ------------------------------------------------------------------ wykonawcy zadan operatora

    def _najblizszy(self, lat, lon, warunek):
        kandydaci = [x for x in self.drony.values()
                     if x["zywy"] and x["faza"] not in ("rtb", "ladowanie", "uziemiony") and warunek(x)]
        if not kandydaci:
            return None
        return min(kandydaci, key=lambda x: czk_logic.odleglosc_km(x["lat"], x["lon"], lat, lon)
                   + 2 * len(x["kolejka"]) + (3 if x["zadanie"] else 0))

    @staticmethod
    def _zajety_zleceniem(x):
        return (x["zadanie"] is not None and x["zadanie"].get("inc") is not None) or any(z.get("inc") is not None for z in x["kolejka"])

    def _przydziel_wykonawce(self, inc):
        rodzaj = inc["rodzaj_akcji"]
        if rodzaj in RODZAJE_Z_GLOSNIKIEM:
            warunek = lambda x: x["tryb"] == "aktywny" and not self._zajety_zleceniem(x)
        elif rodzaj == "zrzut":
            warunek = lambda x: bool(czk_logic.wybierz_zaopatrzenie(inc["typ"], x["zapas"])) and not self._zajety_zleceniem(x)
        else:
            warunek = lambda x: not self._zajety_zleceniem(x)
        d = self._najblizszy(inc["g_lat"], inc["g_lon"], warunek)
        if d is None:
            if rodzaj == "zrzut" and not any(czk_logic.wybierz_zaopatrzenie(inc["typ"], x["zapas"]) for x in self.drony.values() if x["zywy"]):
                inc["rodzaj_akcji"] = "obserwacja"  # zaden dron nie ma juz potrzebnych srodkow
            return
        if rodzaj == "prowadzenie" and inc["schron"] is None:
            # "schron" = cel prowadzenia: schron, budynek poza strefa zalewowa albo punkt zbiorki - zaleznie od sytuacji
            inc["schron"] = self._cel_prowadzenia(inc["lat"], inc["lon"])
            if inc["schron"] is None:
                inc["rodzaj_akcji"] = "obserwacja"
                return
        inc["akcja"] = "przydzielona"
        inc["wykonawca"] = d["id"]
        d["kolejka"].insert(0, {"rodzaj": rodzaj, "inc": inc["id"], "sektor": inc["sektor"]})
        s = inc["schron"]
        cel = {"prowadzenie": f'poprowadzi {inc["osoby"]} os. {s["do"]}: {s["adres"]} ({s["odleglosc_km"]} km)' if s else "",
               "zrzut": "leci z apteczką", "ostrzezenie": "leci ostrzec ludzi w rejonie",
               "odsuniecie": "leci odsunąć ludzi od miejsca zdarzenia", "uspokojenie": "leci uspokoić tłum",
               "obserwacja": "leci obserwować miejsce zdarzenia"}[rodzaj]
        self._dostarcz(self._ev_sys(d["id"], "EWAKUACJA" if rodzaj == "prowadzenie" else "DECYZJA",
                                    f'{d["nazwa"]} {cel} (zgłoszenie #{inc["id"]}, {inc["sektor"]}).',
                                    sektor=inc["sektor"], extra={"inc_id": inc["id"]}))

    # ------------------------------------------------------------------ prowadzenie do schronu

    def _prefiks_komunikatu(self, typ=None):
        if typ == "PANIKA":
            return "Zachowaj spokój. "
        if self.scenariusz.get("prefiks"):
            return self.scenariusz["prefiks"]
        return {"alarm": "Alarm powietrzny. ", "cwiczenia": "To jest alarm próbny. ",
                "powodz": "Zagrożenie powodziowe. ", "pozar": "Pożar lasu. "}.get(self.scenariusz_id, "")

    def _prowadz(self, d, z):
        inc = self.incydenty.get(z["inc"])
        if inc is None or not inc["aktywny"] or inc["schron"] is None:
            d["zadanie"], d["faza"] = None, "orbita"
            return
        inc["wykonawca"] = d["id"]
        if d["faza"] == "lot":
            if self._lec(d, (inc["g_lat"], inc["g_lon"]), loguj=True):
                if inc["podazyli"] is None:
                    d["faza"], d["skan"] = "wezwanie", 0
                    s = inc["schron"]
                    dokad = f'{s["do"]}: {s["adres"]}' if s.get("adres_w_komunikacie", True) else s["do"]
                    tresc = (f'Uwaga! {self._prefiks_komunikatu(inc["typ"])}Proszę iść za dronem — prowadzę '
                             f'{dokad}.{s.get("dopisek", "")}')
                    self._komunikat(d, inc["sektor"], tresc, statystyka=False)
                    inc["t_wezwania"] = self.czas
                else:
                    d["faza"] = "prowadzi"
            return
        if d["faza"] == "wezwanie":
            d["skan"] += 1
            if d["skan"] >= TICKI_WEZWANIA:
                inc["podazyli"] = self._oblicz_podazanie(inc)
                inc["akcja"] = "w_toku"
                nie = inc["osoby"] - inc["podazyli"]
                self._zdarzenie(d["id"], inc["sektor"], "EWAKUACJA",
                                f'{d["nazwa"]} prowadzi {inc["podazyli"]}/{inc["osoby"]} os. {inc["schron"]["do"]}: '
                                f'{inc["schron"]["adres"]}.' + (f" Na komunikat nie reaguje {nie} os." if nie else ""),
                                extra={"inc_id": inc["id"]})
                d["faza"] = "prowadzi"
            return
        cel = (inc["schron"]["lat"], inc["schron"]["lon"])
        dotarl = self._lec(d, cel, krok=KROK_PROWADZENIA_KM)
        wstecz = math.radians(d["kurs"] + 180)
        inc["g_lat"] = d["lat"] + 0.03 * math.cos(wstecz) / KM_NA_STOPIEN_LAT
        inc["g_lon"] = d["lon"] + 0.03 * math.sin(wstecz) / KM_NA_STOPIEN_LON
        if dotarl:
            self._zakoncz_prowadzenie(d, inc)

    def _oblicz_podazanie(self, inc):
        p = PODAZANIE.get((self.rodzaj, inc["typ"]), 0.7)
        if self.pogoda.get("opad_mm_h", 0) > 5:
            p -= 0.05
        p = min(0.97, max(0.1, p + random.uniform(-0.1, 0.1)))
        return sum(random.random() < p for _ in range(inc["osoby"]))

    def _zakoncz_prowadzenie(self, d, inc):
        inc["g_lat"], inc["g_lon"] = inc["schron"]["lat"], inc["schron"]["lon"]
        inc["w_schronie"] = max(0, inc["podazyli"] - (random.randint(0, 1) if inc["podazyli"] > 5 else 0))
        inc["akcja"] = "zakonczona"
        inc["wynik"] = f'{inc["w_schronie"]} os. {inc["schron"]["w"]}'
        self.w_schronie_scenariusz += inc["w_schronie"]
        czas_s = self.czas - (inc["t_wezwania"] or inc["t"])
        proc = round(100 * inc["podazyli"] / inc["osoby"]) if inc["osoby"] else 0
        db.zapisz_ewakuacje({
            "t_sym": self.czas, "scenariusz": self.scenariusz_id, "rodzaj": self.rodzaj, "typ": inc["typ"],
            "sektor": inc["sektor"], "dron_id": d["id"], "powiadomieni": inc["osoby"], "podazyli": inc["podazyli"],
            "w_schronie": inc["w_schronie"], "czas_s": czas_s, "schron_id": inc["schron"]["id"],
            "schron_adres": inc["schron"]["adres"], "odleglosc_km": inc["schron"]["odleglosc_km"],
        })
        self._zdarzenie(d["id"], inc["sektor"], "EWAKUACJA",
                        f'Ewakuacja zakończona ({inc["sektor"]}): {inc["w_schronie"]} os. {inc["schron"]["w"]} '
                        f'({inc["schron"]["adres"]}). Za dronem poszło {proc}% osób, czas {czas_s // 60}:{czas_s % 60:02d}.',
                        osoby=inc["w_schronie"], extra={"inc_id": inc["id"], "analiza": True})
        d["zadanie"], d["faza"], d["cel"] = None, "orbita", [inc["schron"]["lat"], inc["schron"]["lon"]]

    # ------------------------------------------------------------------ komunikaty glosowe

    def _tresc_komunikatu(self, sid):
        # schron podajemy tylko przy alarmie; przy powodzi - budynek poza strefa zalewowa, w innych sytuacjach nic
        kontekst = self._kontekst()
        dokad = ""
        if kontekst in ("schron", "powodz"):
            srodek = self._srodek_sektora(sid)
            cel = self._cel_prowadzenia(srodek[0], srodek[1])
            if cel:
                dokad = (f" Najbliższy schron: {cel['adres']}." if kontekst == "schron"
                         else f" Bezpieczne miejsce poza strefą zalewową: {cel['adres']}.{cel['dopisek']}")
        teksty = {
            "powodz": "Uwaga! Zagrożenie powodziowe. Natychmiast opuść strefę zalewową.",
            "alarm": "Uwaga! Alarm powietrzny. Natychmiast udaj się do schronu.",
            "cwiczenia": "Uwaga! To jest alarm próbny w ramach ćwiczeń. Proszę udać się do schronu.",
        }
        tekst = self.scenariusz.get("tresc_komunikatu") or teksty.get(self.scenariusz_id)
        return (tekst or "Uwaga! Komunikat systemu HERMES. Zachowaj ostrożność i stosuj się do poleceń służb.") + dokad

    def _komunikat(self, d, sid, tresc, statystyka=True):
        d["nadaje"] = 8
        extra = {"glos": tresc}
        if statystyka and sid:
            w_zasiegu = max(5, int(self.sektory_def[sid]["ludnosc_szac"] * random.uniform(0.15, 0.3)))
            p = min(0.95, max(0.1, REAKCJA_KOMUNIKATU.get(self.rodzaj, 0.6) + random.uniform(-0.1, 0.1)))
            reakcja = sum(random.random() < p for _ in range(w_zasiegu))
            db.zapisz_ewakuacje({"t_sym": self.czas, "scenariusz": self.scenariusz_id, "rodzaj": self.rodzaj,
                                 "typ": "KOMUNIKAT", "sektor": sid, "dron_id": d["id"],
                                 "powiadomieni": w_zasiegu, "podazyli": reakcja})
            extra["analiza"] = True
            tresc_logu = f'{d["nazwa"]} (głośnik) → {sid}: „{tresc}” Zareagowało {reakcja} z {w_zasiegu} osób w zasięgu.'
        else:
            tresc_logu = f'{d["nazwa"]} (głośnik) → {sid}: „{tresc}”'
        self._zdarzenie(d["id"], sid, "KOMUNIKAT", tresc_logu, extra=extra, lat=d["lat"], lon=d["lon"])

    def _alarm(self, tresc):
        """Komunikat o zagrozeniu nadawany natychmiast przez wszystkie drony z glosnikiem."""
        for d in self.drony.values():
            if d["zywy"] and d["tryb"] == "aktywny" and d["faza"] not in ("rtb", "ladowanie", "uziemiony"):
                sid = self._sektor_dla(d["lat"], d["lon"]) or "C2"
                schron = self.schrony_dla(sid, 1)
                self._komunikat(d, sid, tresc + (f" Najbliższy schron: {schron[0]['adres']}." if schron else ""))

    def komunikat_reczny(self, dron_id):
        d = self.drony[dron_id]
        sid = self._sektor_dla(d["lat"], d["lon"]) or "C2"
        self._komunikat(d, sid, self._tresc_komunikatu(sid))

    # ------------------------------------------------------------------ odpornosc roju

    def _wybierz_wykonawce(self, zadanie, wyklucz=None):
        if zadanie.get("inc") is not None:
            inc = self.incydenty.get(zadanie["inc"])
            if inc is None:
                return None
            cel = (inc["g_lat"], inc["g_lon"])
        else:
            cel = self._srodek_sektora(zadanie["sektor"])
        wymaga_glosnika = zadanie["rodzaj"] in RODZAJE_Z_GLOSNIKIEM or (zadanie.get("komunikat") and not zadanie.get("wykrycie"))
        return self._najblizszy(cel[0], cel[1], lambda x: x is not wyklucz and (x["tryb"] == "aktywny" or not wymaga_glosnika))

    def _przekaz_zadania(self, d):
        zadania = ([d["zadanie"]] if d["zadanie"] else []) + d["kolejka"]
        if d["faza"] == "przekaznik" and d["cel"]:
            sid = self._sektor_dla(*d["cel"])
            if sid:
                zadania.insert(0, {"rodzaj": "rozpoznanie", "sektor": sid, "przekaznik": True, "krok": None})
        d["zadanie"], d["kolejka"] = None, []
        for z in zadania:
            nowy = self._wybierz_wykonawce(z, wyklucz=d)
            if nowy is None:
                inc = self.incydenty.get(z.get("inc"))
                if inc is not None and inc["aktywny"]:
                    inc["akcja"] = "oczekuje" if inc["podazyli"] is None else "w_toku"
                self._dostarcz(self._ev_sys(None, "MESH", f'Brak wolnego BSP do przejęcia zadania w {z["sektor"]}.'))
                continue
            if z.get("inc") is not None:
                nowy["kolejka"].insert(0, z)
            else:
                nowy["kolejka"].append(z)
            rola = {"prowadzenie": "prowadzenie grupy", "zrzut": "zrzut zaopatrzenia", "ostrzezenie": "ostrzeżenie ludzi",
                    "odsuniecie": "odsunięcie ludzi", "uspokojenie": "uspokojenie tłumu",
                    "obserwacja": "obserwację"}.get(z["rodzaj"], "rolę przekaźnika" if z.get("przekaznik") else "zadanie")
            self._dostarcz(self._ev_sys(nowy["id"], "MESH",
                           f'Rój: {nowy["nazwa"]} przejmuje {rola} w {z["sektor"]} od {d["nazwa"]}.'))

    def przelacz_wezel(self, dron_id):
        d = self.drony[dron_id]
        if d["zywy"]:
            utracone = len(d["bufor"])
            d["zywy"] = False
            d["hops"] = None
            self._dostarcz(self._ev_sys(d["id"], "MESH",
                           f'Utrata węzła {d["nazwa"]} (symulowana awaria)'
                           + (f", utracono {utracone} niedostarczonych pakietów" if utracone else "")
                           + ". Rój rekonfiguruje sieć — brak pojedynczego punktu awarii."))
            self._przekaz_zadania(d)
            d["bufor"] = []
            d["faza"] = "utracony"
        else:
            d.update({"zywy": True, "bateria": 100.0, "zadanie": None, "kolejka": [], "bufor": [], "plan": [],
                      "plan_cel": None, "zapas": dict(d["zapas_start"]),
                      "faza": "patrol"})
            d["lat"], d["lon"] = self._przy_stacji(d["stacja"], int(d["id"][1:]))
            self._dostarcz(self._ev_sys(d["id"], "MESH", f'{d["nazwa"]}: nowy BSP startuje ze stacji {d["stacja"]}.'))
        self._przelicz_mesh()

    def przelacz_stacje(self, stacja_id):
        s = self.stacje[stacja_id]
        s["zywa"] = not s["zywa"]
        if s["zywa"]:
            opis = f'Stacja {s["id"]} {s["nazwa"]}: przywrócona — węzeł wraca do sieci mesh.'
        else:
            opis = (f'Awaria stacji {s["id"]} {s["nazwa"]} (symulacja) — drony w regionie przełączają się '
                    f'na sąsiednie stacje i inne drony (mesh).')
        self._dostarcz(self._ev_sys(None, "MESH", opis, lat=s["lat"], lon=s["lon"]))
        self._przelicz_mesh()

    # ------------------------------------------------------------------ widoki dla CZK

    def schrony_dla(self, sid, n=3):
        s = self._srodek_sektora(sid)
        return czk_logic.najblizsze_schrony(s[0], s[1], self.schrony, n=n)

    def incydent_publiczny(self, i):
        t = czk_logic.TYPY[i["typ"]]
        rodzaj, zalecenie = czk_logic.akcja_drona(i["typ"], i["osoby"], self._kontekst())
        wyk = self.drony.get(i["wykonawca"]) if i["wykonawca"] else None
        zdj = i["zdjecie"]
        return {
            "id": i["id"], "typ": i["typ"], "nazwa": t["nazwa"], "priorytet": t["priorytet"], "sektor": i["sektor"],
            "lat": round(i["lat"], 5), "lon": round(i["lon"], 5), "wsp": czk_logic.wspolrzedne_txt(i["lat"], i["lon"]),
            "opis": i["opis"], "t": i["t"], "aktywny": i["aktywny"], "zglaszajacy": self.drony[i["dron_id"]]["nazwa"],
            "osoby_na_zdjeciu": i["osoby_na_zdjeciu"],
            "zdjecie": {"url": f'/api/zdjecie/{zdj["plik"]}', "autor": zdj["autor"], "licencja": zdj["licencja"],
                        "zrodlo": zdj["zrodlo"], "opis": zdj["opis"]} if zdj else None,
            "decyzja": i["decyzja"], "czeka": i["aktywny"] and i["decyzja"] is None,
            "sluzby": t["sluzby"], "sluzby_powiadomione": i["sluzby_powiadomione"],
            "zalecenie": zalecenie, "rodzaj_akcji": i["rodzaj_akcji"] or rodzaj, "akcja": i["akcja"],
            "wykonawca": wyk["nazwa"] if wyk else None, "schron": i["schron"], "osoby_grupy": i["osoby"],
            "podazyli": i["podazyli"], "w_schronie": i["w_schronie"], "zrzut": i["zrzut"], "wynik": i["wynik"],
        }

    def incydenty_publiczne(self):
        znane = [i for i in self.incydenty.values() if i["dostarczony"]]
        aktywne = sorted((i for i in znane if i["aktywny"]),
                         key=lambda i: (i["decyzja"] is not None, czk_logic.TYPY[i["typ"]]["priorytet"], i["t"]))
        zamkniete = sorted((i for i in znane if not i["aktywny"]), key=lambda i: -i["t_zamkniecia"])[:8]
        return [self.incydent_publiczny(i) for i in aktywne + zamkniete]

    def grupy_publiczne(self):
        wynik = []
        for i in self.incydenty.values():
            if not (i["aktywny"] and i["rodzaj_akcji"] == "prowadzenie" and i["akcja"] in ("przydzielona", "w_toku") and i["schron"]):
                continue
            wynik.append({"inc_id": i["id"], "lat": round(i["g_lat"], 5), "lon": round(i["g_lon"], 5),
                          "n": i["podazyli"] if i["podazyli"] is not None else i["osoby"],
                          "prowadzona": i["akcja"] == "w_toku",
                          "pozostali": (i["osoby"] - i["podazyli"]) if i["podazyli"] is not None else 0,
                          "start": [round(i["lat"], 5), round(i["lon"], 5)],
                          "schron": [i["schron"]["lat"], i["schron"]["lon"]]})
        return wynik

    def drony_publiczne(self):
        wynik = []
        for d in self.drony.values():
            cel_sektor = d["zadanie"]["sektor"] if d["zadanie"] else None
            sektor = cel_sektor or self._sektor_dla(d["lat"], d["lon"]) or "—"
            wynik.append({
                "id": d["id"], "nazwa": d["nazwa"], "tryb": d["tryb"], "sensor": d["sensor"], "stacja": d["stacja"],
                "lat": round(d["lat"], 5), "lon": round(d["lon"], 5), "kurs": round(d["kurs"]),
                "bateria": round(d["bateria"], 1), "zywy": d["zywy"], "faza": d["faza"],
                "status_misji": ("Patrol rejonu zdarzenia — rozpoznanie z powietrza" if d["faza"] == "patrol" and d["obszar"]
                                 else OPIS_FAZY.get(d["faza"], d["faza"]).format(s=sektor)),
                "odporny": d["odporny"], "spec": SPEC_DESZCZ if d["odporny"] else SPEC_STD,
                "sektor": self._sektor_dla(d["lat"], d["lon"]), "hops": d["hops"],
                "twarze": d["twarze"], "kolejka": len(d["kolejka"]) + (1 if d["zadanie"] else 0),
                "bufor": len(d["bufor"]), "nadaje": d["nadaje"] > 0,
                "zapas": d["zapas"], "zapas_start": d["zapas_start"],
            })
        return wynik

    def stan(self):
        licznik = Counter(s["status"] for s in self.sektory.values())
        aktywne = [i for i in self.incydenty.values() if i["aktywny"] and i["dostarczony"]]
        return {
            "czas": self.czas, "pauza": self.pauza, "predkosc": self.predkosc,
            "scenariusz": {
                "id": self.scenariusz_id, "nazwa": self.scenariusz["nazwa"], "opis": self.scenariusz["opis"],
                "rodzaj": self.rodzaj, "warstwy": self.scenariusz["warstwy"], "wariant": self.wariant,
                "ogniska": self.scenariusz.get("ogniska"), "obszar": self.obszar,
                "godzina_startu": self.scenariusz.get("godzina_startu", "12:00"),
                "kroki": [{"t": k["t"], "opis": self._opis_kroku(k), "stan": k["stan"], "typ": k["typ"]}
                          for k in self.kroki],
            },
            "pogoda": self.pogoda,
            "drony": self.drony_publiczne(),
            "stacje": [{"id": s["id"], "zywa": s["zywa"]} for s in self.stacje.values()],
            "linki": self.linki,
            "sektory": [{"id": sid, "status": s["status"]} for sid, s in self.sektory.items()],
            "incydenty": [{"id": i["id"], "typ": i["typ"], "lat": round(i["lat"], 5), "lon": round(i["lon"], 5),
                           "osoby_na_zdjeciu": i["osoby_na_zdjeciu"], "czeka": i["decyzja"] is None} for i in aktywne],
            "grupy": self.grupy_publiczne(),
            "licznik": {k: licznik.get(k, 0) for k in czk_logic.STATUSY},
            "statystyki": {
                "czeka": sum(1 for i in aktywne if i["decyzja"] is None),
                "twarze": sum(d["twarze"] for d in self.drony.values()),
                "incydenty": len(aktywne),
                "w_schronie": self.w_schronie_scenariusz,
                "zrzuty": self.zrzuty,
                "wezly": sum(1 for d in self.drony.values() if d["zywy"] and d["hops"] is not None),
                "wezly_razem": len(self.drony),
                "stacje": sum(1 for s in self.stacje.values() if s["zywa"]),
                "stacje_razem": len(self.stacje),
            },
        }

    # ------------------------------------------------------------------ petla

    def _pogoda_dryf(self):
        if self.tick_nr % 6:
            return
        p = self.pogoda
        p["temperatura_c"] = round(p["temperatura_c"] + random.uniform(-0.2, 0.2), 1)
        p["wiatr_kmh"] = max(0, round(p["wiatr_kmh"] + random.uniform(-2, 2)))
        if p["opad_mm_h"] > 0:
            p["opad_mm_h"] = round(max(0.5, p["opad_mm_h"] + random.uniform(-1.5, 1.5)), 1)

    async def tick(self):
        self.tick_nr += 1
        self.czas += SEK_NA_TICK
        self._wykonaj_kroki_scenariusza()
        for d in self.drony.values():
            if d["zywy"]:
                self._krok_drona(d)
        self._przelicz_mesh()
        self._obsluz_zmiany_lacznosci()
        self._obsluz_incydenty()
        self._pogoda_dryf()
        if self.tick_nr % 4 == 0:
            db.zapisz_drony(self.drony_publiczne())
        await self.wyslij()

    async def wyslij(self):
        if self.broadcast is None:
            return
        paczka, self.do_wyslania = self.do_wyslania, []
        for wiadomosc in paczka:
            await self.broadcast(wiadomosc)
        await self.broadcast({"typ": "stan", "dane": self.stan()})

    async def petla(self):
        while True:
            if not self.pauza:
                try:
                    await self.tick()
                except Exception:
                    traceback.print_exc()
            await asyncio.sleep(INTERWAL_S / self.predkosc)


sym = None  # instancja tworzona przy starcie aplikacji (main.py)
