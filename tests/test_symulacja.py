# tests/test_symulacja.py - zgloszenia do operatora, decyzje, prowadzenie do schronow, strefy, mesh ze stacjami.
import asyncio
import os
import random
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import db  # noqa: E402
import simulator  # noqa: E402


@pytest.fixture
def sym(tmp_path, monkeypatch):
    random.seed(7)
    monkeypatch.setattr(db, "BAZA_PLIK", str(tmp_path / "test_hermes.db"))
    db.inicjalizuj_baze()
    db.zaladuj_sektory_z_mocka()
    return simulator.Symulator()


def _ticki(s, n, co_tick=None):
    async def _run():
        for _ in range(n):
            await s.tick()
            if co_tick:
                co_tick()
    asyncio.run(_run())


def _operator_wysyla_drony(s):
    """Operator akceptuje kazde nowe zgloszenie: wysyla drona."""
    def _decyduj():
        for i in list(s.incydenty.values()):
            if i["aktywny"] and i["dostarczony"] and i["decyzja"] is None:
                s.decyzja(i["id"], "dron")
    return _decyduj


def test_zgloszenia_czekaja_na_operatora_i_nic_nie_jest_wysylane_automatycznie(sym):
    sym.uruchom_scenariusz("powodz")
    _ticki(sym, 160)
    typy = [i["typ"] for i in sym.incydenty.values()]
    assert typy.count("LUDZIE") == 3 and typy.count("ZATOR") == 1
    assert all(i["decyzja"] is None and i["akcja"] is None for i in sym.incydenty.values())
    statusy = {z["status"] for z in db.pobierz_zdarzenia(limit=5000)}
    assert "SLUZBY" not in statusy and "ZRZUT" not in statusy and "EWAKUACJA" not in statusy
    assert [w for w in db.pobierz_ewakuacje() if w["typ"] != "KOMUNIKAT"] == []


def test_zgloszenie_ma_zdjecie_a_liczba_osob_tylko_gdy_widac_je_na_zdjeciu(sym):
    sym.uruchom_scenariusz("powodz")
    _ticki(sym, 160)
    pub = sym.incydenty_publiczne()
    assert pub and all(p["zdjecie"] and p["zdjecie"]["url"].startswith("/api/zdjecie/") for p in pub)
    for p in pub:
        katalog = next(z for z in sym.katalog_zdjec if z["plik"] in p["zdjecie"]["url"])
        assert p["osoby_na_zdjeciu"] == katalog.get("osoby", 0)


def test_operator_wysyla_drona_prowadzenie_do_schronu(sym):
    sym.uruchom_scenariusz("alarm")
    _ticki(sym, 300, _operator_wysyla_drony(sym))
    ewak = [w for w in db.pobierz_ewakuacje() if w["typ"] != "KOMUNIKAT"]
    assert ewak, "zadna grupa nie zostala doprowadzona do schronu"
    for w in ewak:
        assert 0 <= w["w_schronie"] <= w["podazyli"] <= w["powiadomieni"]
    assert any(w["typ"] == "PANIKA" for w in ewak)
    assert all(not i["aktywny"] for i in sym.incydenty.values()), "zgloszenia powinny zostac zamkniete"


def test_operator_wysyla_drona_z_apteczka(sym):
    sym.uruchom_scenariusz("pozar", "las")
    _ticki(sym, 150, _operator_wysyla_drony(sym))
    pomoc = [i for i in sym.incydenty.values() if i["typ"] == "POMOC"]
    assert len(pomoc) == 2 and all(i["zrzut"] for i in pomoc)
    assert "ZRZUT" in {z["status"] for z in db.pobierz_zdarzenia(limit=5000)}


def test_przekazanie_sluzbom_i_odrzucenie_zamykaja_zgloszenie(sym):
    sym.uruchom_scenariusz("powodz")
    _ticki(sym, 160)
    zator = next(i for i in sym.incydenty.values() if i["typ"] == "ZATOR")
    ludzie = next(i for i in sym.incydenty.values() if i["typ"] == "LUDZIE")
    assert sym.decyzja(zator["id"], "sluzby")
    assert not zator["aktywny"]
    alert = [z["opis"] for z in db.pobierz_zdarzenia(limit=5000) if z["status"] == "SLUZBY"][0]
    assert "Policja" in alert and "° N" in alert
    assert sym.decyzja(ludzie["id"], "odrzuc")
    assert not ludzie["aktywny"]
    assert not sym.decyzja(ludzie["id"], "dron")


def test_cwiczenia_maja_nizsze_posluszenstwo_niz_realny_alarm(sym):
    for klucz in ("alarm", "cwiczenia", "alarm", "cwiczenia"):
        sym.uruchom_scenariusz(klucz)
        _ticki(sym, 300, _operator_wysyla_drony(sym))

    def proc(rodzaj):
        w = [x for x in db.pobierz_ewakuacje() if x["rodzaj"] == rodzaj and x["typ"] == "LUDZIE"]
        return sum(x["podazyli"] for x in w) / sum(x["powiadomieni"] for x in w)

    assert proc("realne") > proc("ćwiczenie")


def test_drony_nigdy_nie_wlatuja_w_strefe_wojskowa(sym):
    assert sym.strefy, "brak stref wojskowych (data/strefy_wojskowe.json)"
    naruszenia = []

    def sprawdz():
        for d in sym.drony.values():
            if d["zywy"] and sym._w_strefie(d["lat"], d["lon"]):
                naruszenia.append((d["id"], d["lat"], d["lon"]))
        _operator_wysyla_drony(sym)()

    for klucz in ("patrol", "pozar", "alarm"):
        sym.uruchom_scenariusz(klucz)
        _ticki(sym, 250, sprawdz)
    assert not naruszenia


@pytest.mark.parametrize("wariant", ["las", "dom", "blok", "magazyn"])
def test_warianty_pozaru_patrol_rejonu_i_zgloszenia(sym, wariant):
    sym.uruchom_scenariusz("pozar", wariant)
    o = sym.obszar
    rejon = [d for d in sym.drony.values() if d["obszar"]]
    assert sym.wariant == wariant and 1 <= len(rejon) == o["drony"] <= 2
    # zadania scenariusza dostaje tylko grupa rejonu - pozostale drony dalej patroluja miasto
    assert {k["dron"] for k in sym.kroki if k["typ"] == "zadanie"} <= {d["id"] for d in rejon}
    _ticki(sym, 160)
    assert all(d["faza"] == "patrol" or d["faza"] in ("rtb", "ladowanie") for d in sym.drony.values() if not d["obszar"])
    assert sym.incydenty, "wariant nie wygenerowal zgloszen"
    for d in rejon:
        if d["faza"] == "patrol":
            assert simulator._km((d["lat"], d["lon"]), (o["lat"], o["lon"])) < o["r_km"] + 2.5
    stan = sym.stan()["scenariusz"]
    assert stan["wariant"] == wariant and stan["ogniska"]


def test_powodz_prowadzi_poza_strefe_zalewowa_a_nie_do_schronu(sym):
    sym.uruchom_scenariusz("powodz")
    _ticki(sym, 400, _operator_wysyla_drony(sym))
    prowadzone = [i for i in sym.incydenty.values() if i["rodzaj_akcji"] == "prowadzenie" and i["schron"]]
    assert prowadzone
    for i in prowadzone:
        cel = i["schron"]
        assert cel["do"] != "do schronu"
        assert not simulator._w_wielokacie(simulator._xy((cel["lat"], cel["lon"])), sym.zalew_xy)


def test_deszcz_uziemia_czesc_floty_reszta_w_wersji_deszczowej(sym):
    sym.uruchom_scenariusz("powodz")  # 21 mm/h
    uziemione = [d for d in sym.drony.values() if d["faza"] == "uziemiony"]
    lecace = [d for d in sym.drony.values() if d["faza"] != "uziemiony"]
    assert uziemione and 4 <= len(lecace) < len(sym.drony)
    assert all(d["odporny"] for d in lecace) and not any(d["odporny"] for d in uziemione)
    pozycje = {d["id"]: (d["lat"], d["lon"]) for d in uziemione}
    _ticki(sym, 60, _operator_wysyla_drony(sym))
    assert all((d["lat"], d["lon"]) == pozycje[d["id"]] and d["faza"] == "uziemiony" for d in uziemione)
    sym.uruchom_scenariusz("patrol")  # bez opadu - lata cala flota w wersji standardowej
    assert not any(d["faza"] == "uziemiony" or d["odporny"] for d in sym.drony.values())


def _wykrycie_testowe(sym, dron_id="D1"):
    d = sym.drony[dron_id]
    d["bateria"] = 100.0
    sid = sym._sektor_dla(d["lat"], d["lon"]) or "C3"
    sym._wykrycie(d, sid, "WYPADEK", 2, "zdarzenie testowe", 0.9)
    return d, max(sym.incydenty.values(), key=lambda i: i["id"])


def test_dron_czuwa_przy_wykrytym_zdarzeniu_az_do_przyjazdu_sluzb(sym):
    sym.uruchom_scenariusz("patrol")
    d, inc = _wykrycie_testowe(sym)
    odleglosci = []
    _ticki(sym, 30, lambda: odleglosci.append(simulator._km((d["lat"], d["lon"]), (inc["lat"], inc["lon"]))))
    assert d["faza"] == "czuwa" and d["czuwa"]["inc"] == inc["id"]
    assert max(odleglosci[5:]) < 0.35, "dron powinien krazyc blisko zdarzenia"
    assert len({(round(d["lat"], 5), round(d["lon"], 5))}) == 1 and len(set(map(lambda x: round(x, 4), odleglosci))) > 3
    assert sym.decyzja(inc["id"], "sluzby")
    _ticki(sym, simulator.CZUWANIE_SLUZBY - 3)
    assert d["faza"] == "czuwa", "po przekazaniu sluzbom dron czeka na ich przyjazd"
    _ticki(sym, 5)
    assert d["faza"] == "patrol" and d["czuwa"] is None


def test_odrzucenie_zwalnia_drona_a_brak_decyzji_ma_limit(sym):
    sym.uruchom_scenariusz("patrol")
    d, inc = _wykrycie_testowe(sym, "D1")
    _ticki(sym, 5)
    assert sym.decyzja(inc["id"], "odrzuc")
    _ticki(sym, 1)
    assert d["faza"] == "patrol"
    d2, inc2 = _wykrycie_testowe(sym, "D3")
    _ticki(sym, simulator.CZUWANIE_MAKS_BEZ_DECYZJI + 2)
    assert d2["faza"] != "czuwa" and inc2["aktywny"] and inc2["decyzja"] is None


def test_planer_omija_wielokat():
    s = simulator.Symulator.__new__(simulator.Symulator)
    kwadrat = [(51.10, 17.00), (51.10, 17.02), (51.11, 17.02), (51.11, 17.00)]
    s.strefy = [{"id": "X", "nazwa": "X", "w": [simulator._xy(p) for p in [kwadrat[0], kwadrat[1], kwadrat[2], kwadrat[3]]], "cache": {}}]
    trasa = s._planuj((51.105, 16.98), (51.105, 17.04))
    assert len(trasa) >= 2
    punkty = [(51.105, 16.98)] + trasa
    w, bb = s._strefa(s.strefy[0], 0)
    assert not any(simulator._odcinek_przecina_wielokat(simulator._xy(a), simulator._xy(b), w, bb) for a, b in zip(punkty, punkty[1:]))


def test_stacje_przekaznikowe_sa_wezlami_mesh(sym):
    sym.uruchom_scenariusz("patrol")
    _ticki(sym, 5)
    assert all(d["hops"] is not None for d in sym.drony.values())
    assert len(sym.drony) == 8 and len(sym.stacje) >= 6
    sym.przelacz_stacje("RE-7")
    assert not sym.stacje["RE-7"]["zywa"]
    _ticki(sym, 5)
    sym.przelacz_stacje("RE-7")
    assert sym.stacje["RE-7"]["zywa"]


def test_utrata_przekaznika_samonaprawa_mesh(sym):
    sym.uruchom_scenariusz("pozar", "las")
    _ticki(sym, 60)
    przekaznik = [d["id"] for d in sym.drony.values() if d["faza"] == "przekaznik"]
    assert len(przekaznik) == 1
    sym.przelacz_wezel(przekaznik[0])
    _ticki(sym, 70)
    assert [d for d in sym.drony.values() if d["zywy"] and d["faza"] == "przekaznik"]
    for d in sym.drony.values():
        if d["zywy"]:
            assert d["hops"] is not None
            assert d["bufor"] == []
