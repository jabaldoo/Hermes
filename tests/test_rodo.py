# tests/test_rodo.py - test zgodnosci RODO: zadne zdarzenie zapisywane do bazy/eksportu
# nie moze zawierac obrazu (tylko metadane: sektor, status, pewnosc, ts, liczba_osob).
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import db  # noqa: E402

DOZWOLONE_KLUCZE_ZDARZENIA = {"id", "ts", "t_sym", "dron_id", "sektor", "status", "pewnosc", "liczba_osob", "opis"}


def test_zapisane_zdarzenie_zawiera_wylacznie_metadane(tmp_path, monkeypatch):
    baza_tymczasowa = tmp_path / "test_hermes.db"
    monkeypatch.setattr(db, "BAZA_PLIK", str(baza_tymczasowa))

    db.inicjalizuj_baze()
    zdarzenie = db.zapisz_zdarzenie("D1", "A1", "LUDZIE", 0.87, 3, "Edge AI: wykryto osoby.")

    assert set(zdarzenie.keys()) <= DOZWOLONE_KLUCZE_ZDARZENIA

    for klucz, wartosc in zdarzenie.items():
        if isinstance(wartosc, (bytes, bytearray)):
            raise AssertionError(f"Pole '{klucz}' zawiera dane binarne (potencjalnie obraz)")
        if isinstance(wartosc, str) and len(wartosc) > 2000:
            raise AssertionError(f"Pole '{klucz}' jest podejrzanie dlugie - moze zawierac zakodowany obraz")

    zapisane = db.pobierz_zdarzenia(limit=10)
    assert len(zapisane) == 1
    assert set(zapisane[0].keys()) <= DOZWOLONE_KLUCZE_ZDARZENIA
