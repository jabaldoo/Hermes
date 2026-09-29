# tests/test_rodo.py - zgodnosc RODO: zdarzenia i dane z testow z ludnoscia to wylacznie metadane
# i liczniki - bez obrazu, bez identyfikatorow osob.
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import db  # noqa: E402

DOZWOLONE_KLUCZE_ZDARZENIA = {"id", "ts", "t_sym", "dron_id", "sektor", "lat", "lon", "status", "pewnosc",
                              "liczba_osob", "opis"}


def _bez_obrazu(rekord):
    for klucz, wartosc in rekord.items():
        assert not isinstance(wartosc, (bytes, bytearray)), f"Pole '{klucz}' zawiera dane binarne"
        assert not (isinstance(wartosc, str) and len(wartosc) > 2000), f"Pole '{klucz}' podejrzanie dlugie"


def test_zapisane_zdarzenie_zawiera_wylacznie_metadane(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "BAZA_PLIK", str(tmp_path / "test_hermes.db"))
    db.inicjalizuj_baze()
    zdarzenie = db.zapisz_zdarzenie("D1", "A1", "LUDZIE", 0.87, 3, "Edge AI: wykryto osoby.", lat=51.1, lon=17.0)
    assert set(zdarzenie) <= DOZWOLONE_KLUCZE_ZDARZENIA
    _bez_obrazu(zdarzenie)
    zapisane = db.pobierz_zdarzenia(limit=10)
    assert len(zapisane) == 1 and set(zapisane[0]) <= DOZWOLONE_KLUCZE_ZDARZENIA


def test_dane_ewakuacji_to_tylko_liczniki(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "BAZA_PLIK", str(tmp_path / "test_hermes.db"))
    db.inicjalizuj_baze()
    db.zapisz_ewakuacje({"t_sym": 100, "scenariusz": "alarm", "rodzaj": "realne", "typ": "LUDZIE", "sektor": "C3",
                         "dron_id": "D1", "powiadomieni": 12, "podazyli": 10, "w_schronie": 9, "czas_s": 240,
                         "schron_id": "OZO-1", "schron_adres": "ul. Testowa 1", "odleglosc_km": 0.4})
    wpis = db.pobierz_ewakuacje()[0]
    assert set(wpis) == {"id"} | set(db.KOLUMNY_EWAKUACJI)
    _bez_obrazu(wpis)
