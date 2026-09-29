# tests/test_symulacja.py - scenariusze demo daja oczekiwany obraz sytuacji, a siec mesh sie samonaprawia.
import asyncio
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import db  # noqa: E402
import simulator  # noqa: E402


@pytest.fixture
def sym(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "BAZA_PLIK", str(tmp_path / "test_hermes.db"))
    db.inicjalizuj_baze()
    db.zaladuj_sektory_z_mocka()
    return simulator.Symulator()


def _ticki(s, n):
    async def _run():
        for _ in range(n):
            await s.tick()
    asyncio.run(_run())


def _statusy(s):
    return {sid: v["status"] for sid, v in s.sektory.items() if v["status"] != "OK"}


def test_scenariusz_powodz_3x_ludzie_1x_zator(sym):
    sym.uruchom_scenariusz("powodz")
    _ticki(sym, 120)
    statusy = list(_statusy(sym).values())
    assert statusy.count("LUDZIE") == 3
    assert statusy.count("ZATOR") == 1
    rek = sym.rekomendacje()
    jednostki = {j for r in rek for j in r["jednostki_rekomendowane"]}
    assert {"OSP", "Policja"} <= jednostki
    assert all(r["schrony"] for r in rek if r["status"] == "LUDZIE")


def test_scenariusz_pozar_2x_pomoc(sym):
    sym.uruchom_scenariusz("pozar")
    _ticki(sym, 80)
    statusy = list(_statusy(sym).values())
    assert statusy.count("POMOC") == 2
    rek = sym.rekomendacje()
    assert rek[0]["status"] == "POMOC"
    assert {"PSP", "Karetka"} <= set(rek[0]["jednostki_rekomendowane"])


def test_utrata_przekaznika_samonaprawa_mesh(sym):
    sym.uruchom_scenariusz("pozar")
    _ticki(sym, 60)
    assert sym.drony["D1"]["faza"] == "przekaznik"

    sym.przelacz_wezel("D1")
    _ticki(sym, 60)

    przekazniki = [d for d in sym.drony.values() if d["zywy"] and d["faza"] == "przekaznik"]
    assert przekazniki, "Zaden dron nie przejal roli przekaznika"
    for d in sym.drony.values():
        if d["zywy"]:
            assert d["hops"] is not None, f'{d["id"]} nadal bez lacznosci'
            assert d["bufor"] == []


def test_dysponowanie_zamyka_petle(sym):
    sym.uruchom_scenariusz("powodz")
    _ticki(sym, 120)
    sektor = next(sid for sid, st in _statusy(sym).items() if st == "LUDZIE")
    assert sym.dysponuj(sektor) is not None
    assert sym.dysponuj(sektor) is None  # drugie dysponowanie tego samego sektora odrzucone
    _ticki(sym, simulator.CZAS_DZIALAN_S // simulator.SEK_NA_TICK + 1)
    assert sym.sektory[sektor]["status"] == "OK"
