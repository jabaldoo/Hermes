# tests/test_anonymizer.py - test jednostkowy anonimizacji twarzy (RODO by design).
# Uruchomienie: pytest tests/test_anonymizer.py  (lub: python -m pytest tests)
import os
import sys

import cv2

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from anonymizer import wykryj_twarze, zaanonimizuj, anonimizuj_klatke  # noqa: E402
from edge_ai import ocen_panike  # noqa: E402


def test_spokojny_marsz_to_nie_panika():
    tory = [(1.2, 0.1), (1.1, -0.1), (1.3, 0.0), (1.0, 0.2), (1.2, -0.2)]
    assert not ocen_panike(tory)["panika"]


def test_szybki_chaotyczny_ruch_to_panika():
    tory = [(3.5, 0), (-3.2, 0.5), (0, 3.8), (0.3, -3.6), (2.5, 2.5), (-2.8, -2.2)]
    wynik = ocen_panike(tory)
    assert wynik["panika"] and wynik["chaos"] > 0.55

_TUTAJ = os.path.dirname(__file__)
_SCIEZKA_TESTOWA = os.path.join(_TUTAJ, "..", "samples", "test_face.jpg")


def _wczytaj_klatke_testowa():
    assert os.path.exists(_SCIEZKA_TESTOWA), (
        "Brak pliku samples/test_face.jpg - dodaj przykladowa klatke z widoczna twarza "
        "przed uruchomieniem tego testu."
    )
    klatka = cv2.imread(_SCIEZKA_TESTOWA)
    assert klatka is not None, "Nie udalo sie wczytac samples/test_face.jpg"
    return klatka


def test_detektor_znajduje_co_najmniej_jedna_twarz_przed_anonimizacja():
    klatka = _wczytaj_klatke_testowa()
    twarze = wykryj_twarze(klatka)
    assert len(twarze) >= 1, "Detektor Haar nie znalazl zadnej twarzy na klatce testowej"


def test_po_anonimizacji_detektor_nie_znajduje_juz_twarzy_blur():
    klatka = _wczytaj_klatke_testowa()
    twarze = wykryj_twarze(klatka)
    assert len(twarze) >= 1

    zanonimizowana = zaanonimizuj(klatka, twarze, tryb="blur")
    twarze_po = wykryj_twarze(zanonimizowana)
    assert len(twarze_po) == 0, "Po anonimizacji (blur) detektor nadal znajduje twarze"


def test_po_anonimizacji_detektor_nie_znajduje_juz_twarzy_pixel():
    klatka = _wczytaj_klatke_testowa()
    twarze = wykryj_twarze(klatka)
    assert len(twarze) >= 1

    zanonimizowana = zaanonimizuj(klatka, twarze, tryb="pixel")
    twarze_po = wykryj_twarze(zanonimizowana)
    assert len(twarze_po) == 0, "Po anonimizacji (pixel) detektor nadal znajduje twarze"


def test_po_anonimizacji_detektor_nie_znajduje_juz_twarzy_black():
    klatka = _wczytaj_klatke_testowa()
    twarze = wykryj_twarze(klatka)
    assert len(twarze) >= 1

    zanonimizowana = zaanonimizuj(klatka, twarze, tryb="black")
    twarze_po = wykryj_twarze(zanonimizowana)
    assert len(twarze_po) == 0, "Po anonimizacji (black) detektor nadal znajduje twarze"


def test_pipeline_anonimizuj_klatke_zwraca_liczbe_twarzy():
    klatka = _wczytaj_klatke_testowa()
    zanonimizowana, liczba_twarzy = anonimizuj_klatke(klatka, tryb="blur")
    assert liczba_twarzy >= 1
    assert zanonimizowana.shape == klatka.shape

    # oryginal nie moze zostac zmodyfikowany "w miejscu" - funkcja pracuje na kopii
    twarze_oryginal_po_wywolaniu = wykryj_twarze(klatka)
    assert len(twarze_oryginal_po_wywolaniu) >= 1
