# simulator.py - silnik symulacji roju HERMES (zamiast ROS2/Gazebo).
# Scenariusze (mock_data.json -> "scenariusze"), lot dronow, siec mesh z routingiem wieloskokowym,
# store-and-forward przy utracie lacznosci, samonaprawa sieci po utracie wezla, powrot do bazy
# przy niskiej baterii oraz zamkniecie petli decyzyjnej (dysponowanie jednostek -> zakonczenie dzialan).
# Do CZK trafiaja wylacznie metadane: {sektor, status, pewnosc, ts, liczba_osob}.
import asyncio
import json
import math
import os
import random
import traceback
from collections import Counter, deque

import czk_logic
import data_sources
import db

_TUTAJ = os.path.dirname(os.path.abspath(__file__))

SEK_NA_TICK = 5            # tyle sekund czasu misji mija w jednym ticku
INTERWAL_S = 0.5           # realny odstep miedzy tickami przy predkosci 1x
KROK_KM = 0.2              # przelot drona na tick
ZASIEG_MESH_KM = 4.5       # zasieg lacza radiowego wezel-wezel
TICKI_SKANU = 4            # czas rozpoznania sektora przez edge AI
ORBITA_KM = 0.35
ZUZYCIE_BATERII = 0.12     # % na tick
LADOWANIE = 3.0            # % na tick (wymiana/ladowanie w bazie)
PROG_RTB = 20.0            # ponizej - powrot do bazy
CZAS_DZIALAN_S = 90        # czas misji sluzb po zadysponowaniu (czas symulacji)
KM_NA_STOPIEN_LAT = 111.2
KM_NA_STOPIEN_LON = 69.93  # dla szerokosci ~51.1 N

WAGI_PATROLU = {"OK": 55, "LUDZIE": 22, "ZATOR": 12, "POMOC": 11}
SZANSA_WYKRYCIA_PATROL = 0.035

OPIS_FAZY = {
    "baza": "W bazie — gotowy",
    "lot": "Przelot → {s}",
    "skan": "Rozpoznanie {s} (edge AI)",
    "orbita": "Obserwacja {s}",
    "przekaznik": "Przekaźnik mesh — {s}",
    "patrol": "Patrol",
    "rtb": "Powrót do bazy (bateria)",
    "ladowanie": "Wymiana baterii",
    "utracony": "UTRACONY — brak telemetrii",
}


def _wczytaj_mock():
    with open(os.path.join(_TUTAJ, "mock_data.json"), "r", encoding="utf-8") as f:
        return json.load(f)


class Symulator:
    def __init__(self):
        self.mock = _wczytaj_mock()
        self.baza = self.mock["baza"]
        self.sektory_def = {s["id"]: s for s in self.mock["sektory"]}
        self.jednostki = {j["typ"]: j for j in self.mock["jednostki"]}
        self.schrony = data_sources.pobierz_schrony()["punkty"]
        self.broadcast = None
        self.pauza = False
        self.predkosc = 1
        self.uruchom_scenariusz("patrol")

    # ------------------------------------------------------------------ scenariusz

    def uruchom_scenariusz(self, klucz):
        scen = self.mock["scenariusze"][klucz]
        self.scenariusz_id = klucz
        self.scenariusz = scen
        self.kroki = [dict(k, stan="oczekuje") for k in scen["kroki"]]
        self.czas = 0
        self.tick_nr = 0
        self.pogoda = dict(scen["pogoda"])
        self.sektory = {sid: {"status": "OK", "osoby": 0} for sid in self.sektory_def}
        self.dysponowane = {}
        self.linki = []
        self.do_wyslania = [{"typ": "reset"}]
        patrol = klucz == "patrol"
        baterie = [100, 64, 88, 31] if patrol else [100, 93, 97, 88]
        self.drony = {}
        for i, d in enumerate(self.mock["drony"]):
            if patrol:
                lat, lon = d["trasa_patrolu"][0]
            else:
                lat, lon = self._obok_bazy(i)
            self.drony[d["id"]] = {
                "id": d["id"], "nazwa": d["nazwa"], "tryb": d["tryb"], "sensor": d["sensor"],
                "lat": lat, "lon": lon, "kurs": 0.0, "bateria": float(baterie[i % len(baterie)]),
                "zywy": True, "faza": "patrol" if patrol else "baza",
                "zadanie": None, "kolejka": [], "cel": None, "skan": 0,
                "orbita_kat": random.uniform(0, 2 * math.pi), "orbita_r": 0.0,
                "twarze": 0, "bufor": [], "hops": 1, "hops_poprz": 1, "nadaje": 0,
                "trasa": d["trasa_patrolu"], "trasa_idx": 1,
            }
        db.resetuj_misje()
        self._przelicz_mesh()
        self._wykonaj_kroki_scenariusza()

    def _obok_bazy(self, i):
        kat = i * math.pi / 2
        return (self.baza["lat"] + 0.0006 * math.sin(kat), self.baza["lon"] + 0.0009 * math.cos(kat))

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
            elif k["typ"] == "zadanie":
                k["stan"] = "w toku"
                zadanie = {"sektor": k["sektor"], "wykrycie": k.get("wykrycie"),
                           "komunikat": k.get("komunikat", False), "przekaznik": k.get("przekaznik", False),
                           "krok": idx}
                dron = self.drony[k["dron"]]
                if not dron["zywy"] or dron["faza"] in ("rtb", "ladowanie"):
                    dron = self._wybierz_wykonawce(zadanie, wyklucz=dron) or dron
                dron["kolejka"].append(zadanie)

    def _opis_kroku(self, k):
        if k["typ"] in ("alert", "info"):
            return k["opis"]
        czesci = []
        if k.get("przekaznik"):
            czesci.append("przekaźnik mesh")
        if k.get("wykrycie"):
            czesci.append("rozpoznanie edge AI")
        if k.get("komunikat"):
            czesci.append("komunikat głosowy")
        return f'{self.drony[k["dron"]]["nazwa"]} → {k["sektor"]}: {" + ".join(czesci)}'

    # ------------------------------------------------------------------ zdarzenia / mesh store-and-forward

    def _zdarzenie(self, dron_id, sektor, status, opis, pewnosc=1.0, osoby=0, extra=None):
        """Zdarzenie od drona bez lacznosci z CZK trafia do bufora pokladowego (store-and-forward)."""
        ev = {"dron_id": dron_id, "sektor": sektor, "status": status, "pewnosc": pewnosc,
              "liczba_osob": osoby, "opis": opis, "t_sym": self.czas, "extra": extra or {}}
        dron = self.drony.get(dron_id) if dron_id else None
        if dron is not None and dron["hops"] is None:
            dron["bufor"].append(ev)
            return
        self._dostarcz(ev)

    def _dostarcz(self, ev, opoznienie_s=None):
        opis = ev["opis"]
        if opoznienie_s:
            opis += f" [z bufora mesh, opóźnienie {opoznienie_s} s]"
        zapis = db.zapisz_zdarzenie(ev["dron_id"], ev["sektor"], ev["status"], ev["pewnosc"],
                                    ev["liczba_osob"], opis, t_sym=ev["t_sym"])
        # Obraz sytuacji w CZK zmienia sie dopiero, gdy metadane faktycznie dotra do CZK.
        if ev["sektor"] and ev["status"] in czk_logic.STATUSY:
            self.sektory[ev["sektor"]] = {"status": ev["status"], "osoby": ev["liczba_osob"]}
            db.aktualizuj_sektor(ev["sektor"], ev["status"], ev["liczba_osob"])
        zapis.update(ev["extra"])
        self.do_wyslania.append({"typ": "zdarzenie", "dane": zapis})

    def _przelicz_mesh(self):
        wezly = [("CZK", self.baza["lat"], self.baza["lon"])]
        wezly += [(d["id"], d["lat"], d["lon"]) for d in self.drony.values() if d["zywy"]]
        sasiedzi = {w[0]: [] for w in wezly}
        self.linki = []
        for i in range(len(wezly)):
            for j in range(i + 1, len(wezly)):
                a, b = wezly[i], wezly[j]
                odl = czk_logic.odleglosc_km(a[1], a[2], b[1], b[2])
                if odl <= ZASIEG_MESH_KM:
                    sasiedzi[a[0]].append(b[0])
                    sasiedzi[b[0]].append(a[0])
                    self.linki.append({"a": [a[1], a[2]], "b": [b[1], b[2]],
                                       "jakosc": round(1 - odl / ZASIEG_MESH_KM, 2)})
        hops = {"CZK": 0}
        kolejka = deque(["CZK"])
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
            if not d["zywy"]:
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

    def _ev_sys(self, dron_id, status, opis, sektor=None, extra=None):
        return {"dron_id": dron_id, "sektor": sektor, "status": status, "pewnosc": 1.0,
                "liczba_osob": 0, "opis": opis, "t_sym": self.czas, "extra": extra or {}}

    # ------------------------------------------------------------------ ruch

    def _lec(self, d, cel):
        dy = (cel[0] - d["lat"]) * KM_NA_STOPIEN_LAT
        dx = (cel[1] - d["lon"]) * KM_NA_STOPIEN_LON
        odl = math.hypot(dx, dy)
        if odl > 1e-6:
            d["kurs"] = (math.degrees(math.atan2(dx, dy)) + 360) % 360
        if odl <= KROK_KM:
            d["lat"], d["lon"] = cel[0], cel[1]
            return True
        d["lat"] += dy / odl * KROK_KM / KM_NA_STOPIEN_LAT
        d["lon"] += dx / odl * KROK_KM / KM_NA_STOPIEN_LON
        return False

    def _orbituj(self, d, srodek):
        d["orbita_r"] = min(ORBITA_KM, d["orbita_r"] + 0.07)
        d["orbita_kat"] += 0.28
        d["lat"] = srodek[0] + d["orbita_r"] * math.cos(d["orbita_kat"]) / KM_NA_STOPIEN_LAT
        d["lon"] = srodek[1] + d["orbita_r"] * math.sin(d["orbita_kat"]) / KM_NA_STOPIEN_LON
        d["kurs"] = (math.degrees(d["orbita_kat"]) + 90) % 360

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
        if d["nadaje"] > 0:
            d["nadaje"] -= 1
        if d["faza"] not in ("ladowanie", "baza"):
            d["bateria"] = max(0.0, d["bateria"] - ZUZYCIE_BATERII)

        if d["bateria"] < PROG_RTB and d["faza"] not in ("rtb", "ladowanie", "baza"):
            self._zdarzenie(d["id"], None, "INFO",
                            f'{d["nazwa"]}: bateria {d["bateria"]:.0f}% — powrót do bazy, zadania przekazane.')
            self._przekaz_zadania(d)
            d["faza"] = "rtb"

        if d["faza"] == "rtb":
            if self._lec(d, (self.baza["lat"], self.baza["lon"])):
                d["faza"] = "ladowanie"
            return
        if d["faza"] == "ladowanie":
            d["bateria"] = min(100.0, d["bateria"] + LADOWANIE)
            if d["bateria"] >= 100.0:
                d["faza"] = "patrol" if self.scenariusz_id == "patrol" else "baza"
                self._zdarzenie(d["id"], None, "INFO", f'{d["nazwa"]}: bateria wymieniona — gotowy do misji.')
            return

        if d["zadanie"] is None and d["kolejka"]:
            d["zadanie"] = d["kolejka"].pop(0)
            s = self._srodek_sektora(d["zadanie"]["sektor"])
            d["cel"] = [s[0] + random.uniform(-0.003, 0.003), s[1] + random.uniform(-0.004, 0.004)]
            d["skan"] = 0
            d["orbita_r"] = 0.0
            d["faza"] = "lot"

        z = d["zadanie"]
        if z is not None:
            if d["faza"] == "lot":
                if self._lec(d, d["cel"]):
                    d["faza"] = "skan"
                return
            self._orbituj(d, d["cel"])
            d["skan"] += 1
            if d["skan"] >= TICKI_SKANU:
                self._wykonaj_zadanie(d, z)
                d["zadanie"] = None
                d["faza"] = "przekaznik" if z.get("przekaznik") else "orbita"
            return

        if d["faza"] in ("orbita", "przekaznik"):
            self._orbituj(d, d["cel"])
        elif d["faza"] == "patrol":
            if self._lec(d, d["trasa"][d["trasa_idx"]]):
                d["trasa_idx"] = (d["trasa_idx"] + 1) % len(d["trasa"])
            self._losowe_wykrycie(d)

    def _wykonaj_zadanie(self, d, z):
        sid = z["sektor"]
        if z.get("wykrycie"):
            w = z["wykrycie"]
            osoby = w["osoby"]
            twarze = random.randint(max(0, osoby - 3), osoby) if osoby else 0
            d["twarze"] += twarze
            opis = f'{d["sensor"]}: {w["opis"]}.'
            if osoby:
                opis += f" Edge AI: {twarze} twarzy zanonimizowanych na pokładzie."
            self._zdarzenie(d["id"], sid, w["status"], opis, round(random.uniform(0.81, 0.97), 2), osoby)
        if z.get("komunikat"):
            self._komunikat(d, sid)
        if z.get("przekaznik"):
            self._zdarzenie(d["id"], sid, "MESH", f'{d["nazwa"]}: pozycja przekaźnika mesh w {sid} zajęta.')
        if z.get("krok") is not None:
            self.kroki[z["krok"]]["stan"] = "wykonany"

    def _losowe_wykrycie(self, d):
        if random.random() > SZANSA_WYKRYCIA_PATROL:
            return
        sid = self._sektor_dla(d["lat"], d["lon"])
        if sid is None or sid in self.dysponowane:
            return
        status = random.choices(list(WAGI_PATROLU), weights=list(WAGI_PATROLU.values()))[0]
        if status == "OK":
            if self.sektory[sid]["status"] != "OK":
                self._zdarzenie(d["id"], sid, "OK", f'{d["sensor"]}: weryfikacja — brak zagrożenia.',
                                round(random.uniform(0.86, 0.98), 2), 0)
            return
        osoby = 0 if status == "ZATOR" else random.randint(2, 12)
        opisy = {"LUDZIE": "osoby w strefie zagrożenia", "ZATOR": "zablokowany przejazd",
                 "POMOC": "osoba poszkodowana — brak ruchu"}
        twarze = random.randint(max(0, osoby - 3), osoby) if osoby else 0
        d["twarze"] += twarze
        opis = f'{d["sensor"]}: {opisy[status]}.'
        if osoby:
            opis += f" Edge AI: {twarze} twarzy zanonimizowanych na pokładzie."
        self._zdarzenie(d["id"], sid, status, opis, round(random.uniform(0.66, 0.95), 2), osoby)

    def _tresc_komunikatu(self, sid):
        schron = self.schrony_dla(sid, 1)
        dokad = f" Najbliższe miejsce schronienia: {schron[0]['adres']}." if schron else ""
        if self.scenariusz_id == "powodz":
            return "Uwaga! Zagrożenie powodziowe. Natychmiast opuść strefę zalewową." + dokad
        if self.scenariusz_id == "pozar":
            return "Uwaga! Pożar lasu. Natychmiast opuść las, kieruj się pod wiatr." + dokad
        return "Uwaga! Komunikat ćwiczebny systemu HERMES. Opuść strefę." + dokad

    def _komunikat(self, d, sid):
        tresc = self._tresc_komunikatu(sid)
        d["nadaje"] = 8
        self._zdarzenie(d["id"], sid, "KOMUNIKAT", f'{d["nazwa"]} (głośnik) → {sid}: „{tresc}”',
                        extra={"glos": tresc})

    # ------------------------------------------------------------------ odpornosc roju

    def _wybierz_wykonawce(self, zadanie, wyklucz=None):
        cel = self._srodek_sektora(zadanie["sektor"])
        kandydaci = [x for x in self.drony.values()
                     if x is not wyklucz and x["zywy"] and x["faza"] not in ("rtb", "ladowanie")]
        if not kandydaci:
            return None
        return min(kandydaci, key=lambda x: czk_logic.odleglosc_km(x["lat"], x["lon"], cel[0], cel[1])
                   + 3 * len(x["kolejka"]) + (2 if x["zadanie"] else 0))

    def _przekaz_zadania(self, d):
        zadania = ([d["zadanie"]] if d["zadanie"] else []) + d["kolejka"]
        if d["faza"] == "przekaznik" and d["cel"]:
            sid = self._sektor_dla(*d["cel"])
            if sid:
                zadania.insert(0, {"sektor": sid, "przekaznik": True, "krok": None})
        d["zadanie"], d["kolejka"] = None, []
        for z in zadania:
            nowy = self._wybierz_wykonawce(z, wyklucz=d)
            if nowy is None:
                self._dostarcz(self._ev_sys(None, "MESH", f'Brak wolnego BSP do przejęcia zadania {z["sektor"]}.'))
                continue
            nowy["kolejka"].append(z)
            rola = "rolę przekaźnika" if z.get("przekaznik") else "zadanie"
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
            d.update({"zywy": True, "bateria": 100.0, "zadanie": None, "kolejka": [], "bufor": [],
                      "faza": "patrol" if self.scenariusz_id == "patrol" else "baza"})
            d["lat"], d["lon"] = self._obok_bazy(int(d["id"][1:]))
            self._dostarcz(self._ev_sys(d["id"], "MESH", f'{d["nazwa"]}: nowy BSP dołącza do roju z bazy.'))
        self._przelicz_mesh()

    # ------------------------------------------------------------------ decyzje CZK

    def schrony_dla(self, sid, n=3):
        s = self._srodek_sektora(sid)
        return czk_logic.najblizsze_schrony(s[0], s[1], self.schrony, n=n)

    def rekomendacje(self):
        lista = []
        for sid, s in self.sektory.items():
            if s["status"] == "OK":
                continue
            r = czk_logic.rekomenduj_akcje(s["status"], sid, s["osoby"])
            r["w_realizacji"] = sid in self.dysponowane
            r["schrony"] = self.schrony_dla(sid, 3) if s["status"] in ("LUDZIE", "POMOC") else []
            r["centrum"] = self._srodek_sektora(sid)
            lista.append(r)
        return czk_logic.posortuj_rekomendacje_wg_priorytetu(lista)

    def dysponuj(self, sid):
        s = self.sektory.get(sid)
        if s is None or s["status"] == "OK" or sid in self.dysponowane:
            return None
        rek = czk_logic.rekomenduj_akcje(s["status"], sid, s["osoby"])
        schron = self.schrony_dla(sid, 1)[0] if s["status"] in ("LUDZIE", "POMOC") and self.schrony else None
        self.dysponowane[sid] = {"koniec": self.czas + CZAS_DZIALAN_S, "status": s["status"],
                                 "osoby": s["osoby"], "schron": schron}
        cel = self._srodek_sektora(sid)
        opis = f'CZK zadysponowało: {", ".join(rek["jednostki_rekomendowane"])} → {sid}'
        if schron:
            opis += f'; ewakuacja do: {schron["adres"]} ({schron["odleglosc_km"]} km)'
        trasy = [{"typ": j, "z": [self.jednostki[j]["lat"], self.jednostki[j]["lon"]], "do": cel}
                 for j in rek["jednostki_rekomendowane"] if j in self.jednostki]
        czas_real = CZAS_DZIALAN_S / SEK_NA_TICK * INTERWAL_S / self.predkosc
        self._dostarcz(self._ev_sys(None, "DZIALANIE", opis, sektor=sid,
                                    extra={"trasy": trasy, "czas_real_s": czas_real,
                                           "schron": [schron["lat"], schron["lon"]] if schron else None}))
        return self.dysponowane[sid]

    def _rozstrzygnij_dysponowania(self):
        for sid, info in list(self.dysponowane.items()):
            if self.czas < info["koniec"]:
                continue
            del self.dysponowane[sid]
            if info["status"] == "ZATOR":
                wynik = "przejazd udrożniony"
            elif info["status"] == "POMOC":
                wynik = f'{info["osoby"]} os. przekazano Zespołowi Ratownictwa Medycznego'
            else:
                gdzie = f' ({info["schron"]["adres"]})' if info["schron"] else ""
                wynik = f'ewakuowano {info["osoby"]} os. do miejsca schronienia{gdzie}'
            self._dostarcz(self._ev_sys(None, "OK", f"Sektor {sid}: {wynik}. Status: OK.", sektor=sid))

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
        self._rozstrzygnij_dysponowania()
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

    # ------------------------------------------------------------------ widok stanu

    def drony_publiczne(self):
        wynik = []
        for d in self.drony.values():
            sektor = (self.zadanie_sektor(d) or self._sektor_dla(d["lat"], d["lon"]) or "—")
            wynik.append({
                "id": d["id"], "nazwa": d["nazwa"], "tryb": d["tryb"], "sensor": d["sensor"],
                "lat": round(d["lat"], 5), "lon": round(d["lon"], 5), "kurs": round(d["kurs"]),
                "bateria": round(d["bateria"], 1), "zywy": d["zywy"], "faza": d["faza"],
                "status_misji": OPIS_FAZY.get(d["faza"], d["faza"]).format(s=sektor),
                "sektor": self._sektor_dla(d["lat"], d["lon"]), "hops": d["hops"],
                "twarze": d["twarze"], "kolejka": len(d["kolejka"]) + (1 if d["zadanie"] else 0),
                "bufor": len(d["bufor"]), "nadaje": d["nadaje"] > 0,
            })
        return wynik

    @staticmethod
    def zadanie_sektor(d):
        if d["zadanie"]:
            return d["zadanie"]["sektor"]
        return None

    def stan(self):
        licznik = Counter(s["status"] for s in self.sektory.values())
        return {
            "czas": self.czas, "pauza": self.pauza, "predkosc": self.predkosc,
            "scenariusz": {
                "id": self.scenariusz_id, "nazwa": self.scenariusz["nazwa"], "opis": self.scenariusz["opis"],
                "warstwy": self.scenariusz["warstwy"],
                "kroki": [{"t": k["t"], "opis": self._opis_kroku(k), "stan": k["stan"], "typ": k["typ"]}
                          for k in self.kroki],
            },
            "pogoda": self.pogoda,
            "baza": self.baza,
            "drony": self.drony_publiczne(),
            "linki": self.linki,
            "sektory": [{"id": sid, "status": s["status"], "osoby": s["osoby"],
                         "w_realizacji": sid in self.dysponowane} for sid, s in self.sektory.items()],
            "licznik": {k: licznik.get(k, 0) for k in czk_logic.STATUSY},
            "statystyki": {
                "osoby": sum(s["osoby"] for s in self.sektory.values() if s["status"] != "OK"),
                "twarze": sum(d["twarze"] for d in self.drony.values()),
                "w_realizacji": len(self.dysponowane),
                "wezly": sum(1 for d in self.drony.values() if d["zywy"] and d["hops"] is not None),
                "wezly_razem": len(self.drony),
            },
        }


sym = None  # instancja tworzona przy starcie aplikacji (main.py)
