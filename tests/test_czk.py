# tests/test_czk.py - reguly CZK: typy incydentow -> sluzby, priorytety, wspolrzedne, schrony, apteczki.
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from czk_logic import (akcja_drona, najblizsze_schrony, posortuj_rekomendacje_wg_priorytetu, rekomenduj_akcje,  # noqa: E402
                       status_sektora, wspolrzedne_txt, wybierz_zaopatrzenie)


def test_wypadek_alarmuje_policje_pogotowie_i_straz():
    assert set(rekomenduj_akcje("WYPADEK")["jednostki_rekomendowane"]) == {"Policja", "ZRM", "PSP"}


def test_pozar_alarmuje_straz():
    assert "PSP" in rekomenduj_akcje("POZAR")["jednostki_rekomendowane"]


def test_zator_alarmuje_policje():
    assert rekomenduj_akcje("ZATOR")["jednostki_rekomendowane"] == ["Policja"]


def test_pomoc_alarmuje_pogotowie():
    assert "ZRM" in rekomenduj_akcje("POMOC")["jednostki_rekomendowane"]


def test_akcja_drona_zalecana_operatorowi():
    assert akcja_drona("LUDZIE", 8)[0] == "prowadzenie"
    assert akcja_drona("PANIKA", 20)[0] == "prowadzenie"
    assert akcja_drona("POMOC", 2)[0] == "zrzut"
    assert akcja_drona("POZAR", 0)[0] == "obserwacja"
    assert akcja_drona("ZAGROZENIE", 0)[0] == "ostrzezenie"
    assert akcja_drona("ZATOR", 0)[0] == "obserwacja"


def test_status_sektora_to_najpilniejszy_incydent():
    assert status_sektora([]) == "OK"
    assert status_sektora(["ZATOR", "WYPADEK", "LUDZIE"]) == "WYPADEK"


def test_sortowanie_wg_priorytetu():
    posortowane = posortuj_rekomendacje_wg_priorytetu(
        [rekomenduj_akcje("ZATOR"), rekomenduj_akcje("POMOC"), rekomenduj_akcje("LUDZIE")])
    assert [r["status"] for r in posortowane] == ["POMOC", "LUDZIE", "ZATOR"]


def test_wspolrzedne_dla_sluzb():
    assert wspolrzedne_txt(51.1012345, 17.0456789) == "51.10123° N, 17.04568° E"


def test_najblizsze_schrony_preferuja_dostep_calodobowy_i_pomijaja_wykluczone():
    punkty = [
        {"id": "blisko-na-zadanie", "lat": 51.1001, "lon": 17.0501, "dostepnosc": "Na żądanie"},
        {"id": "troche-dalej-24h", "lat": 51.1020, "lon": 17.0500, "dostepnosc": "Całodobowa"},
        {"id": "w-strefie", "lat": 51.1000, "lon": 17.0500, "dostepnosc": "Całodobowa"},
    ]
    wynik = najblizsze_schrony(51.1000, 17.0500, punkty, n=2, wyklucz=lambda p: p["id"] == "w-strefie")
    assert [p["id"] for p in wynik] == ["troche-dalej-24h", "blisko-na-zadanie"]


def test_zrzut_zaopatrzenia_tylko_z_tego_co_dron_ma():
    zapas = {"Opaska uciskowa": 0, "Opatrunek hemostatyczny": 1, "Koc termiczny NRC": 2}
    assert wybierz_zaopatrzenie("POMOC", zapas) == ["Opatrunek hemostatyczny", "Koc termiczny NRC"]
    assert wybierz_zaopatrzenie("ZATOR", zapas) == []
