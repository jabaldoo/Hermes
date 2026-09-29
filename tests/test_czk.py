# tests/test_czk.py - test logiki rekomendacji CZK.
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from czk_logic import najblizsze_schrony, posortuj_rekomendacje_wg_priorytetu, rekomenduj_akcje  # noqa: E402


def test_najblizsze_schrony_preferuja_dostep_calodobowy():
    punkty = [
        {"id": "blisko-na-zadanie", "lat": 51.1001, "lon": 17.0501, "dostepnosc": "Na żądanie"},
        {"id": "troche-dalej-24h", "lat": 51.1020, "lon": 17.0500, "dostepnosc": "Całodobowa"},
        {"id": "daleko-24h", "lat": 51.1400, "lon": 17.0500, "dostepnosc": "Całodobowa"},
    ]
    wynik = najblizsze_schrony(51.1000, 17.0500, punkty, n=2)
    assert [p["id"] for p in wynik] == ["troche-dalej-24h", "blisko-na-zadanie"]
    assert wynik[0]["odleglosc_km"] < 0.5


def test_status_ludzie_rekomenduje_osp_psp():
    rek = rekomenduj_akcje("LUDZIE", sektor_id="B2", liczba_osob=5)
    assert "OSP" in rek["jednostki_rekomendowane"]
    assert "PSP" in rek["jednostki_rekomendowane"]


def test_status_zator_rekomenduje_policje():
    rek = rekomenduj_akcje("ZATOR", sektor_id="C3")
    assert rek["jednostki_rekomendowane"] == ["Policja"]


def test_status_pomoc_rekomenduje_karetke():
    rek = rekomenduj_akcje("POMOC", sektor_id="A1", liczba_osob=2)
    assert "Karetka" in rek["jednostki_rekomendowane"]


def test_status_ok_bez_jednostek():
    rek = rekomenduj_akcje("OK", sektor_id="A1")
    assert rek["jednostki_rekomendowane"] == []


def test_sortowanie_wg_priorytetu_pomoc_najwyzej():
    rekomendacje = [
        rekomenduj_akcje("ZATOR", sektor_id="C3"),
        rekomenduj_akcje("POMOC", sektor_id="A1"),
        rekomenduj_akcje("LUDZIE", sektor_id="B2"),
    ]
    posortowane = posortuj_rekomendacje_wg_priorytetu(rekomendacje)
    assert posortowane[0]["status"] == "POMOC"
    assert posortowane[-1]["status"] == "ZATOR"
