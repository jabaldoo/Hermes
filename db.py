# db.py - warstwa SQLite (hermes.db). Zero konfiguracji, zero zewnetrznej bazy.
# Tabela zdarzen przechowuje WYLACZNIE metadane - nie ma w schemacie zadnej kolumny na obraz.
import json
import os
import sqlite3
from datetime import datetime, timezone

BAZA_PLIK = os.environ.get("HERMES_DB") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "hermes.db")


def polacz():
    conn = sqlite3.connect(BAZA_PLIK)
    conn.row_factory = sqlite3.Row
    return conn


def inicjalizuj_baze():
    conn = polacz()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS sektory (
            id TEXT PRIMARY KEY, nazwa TEXT, wiersz INTEGER, kolumna TEXT,
            lat_min REAL, lat_max REAL, lon_min REAL, lon_max REAL,
            lat_centrum REAL, lon_centrum REAL, ludnosc_szac INTEGER,
            status TEXT DEFAULT 'OK', liczba_osob INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS drony (
            id TEXT PRIMARY KEY, nazwa TEXT, tryb TEXT, sensor TEXT,
            bateria REAL, status_misji TEXT, liczba_zanonimizowanych_twarzy INTEGER DEFAULT 0,
            lat REAL, lon REAL
        );
        CREATE TABLE IF NOT EXISTS zdarzenia (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT, t_sym INTEGER, dron_id TEXT, sektor TEXT,
            status TEXT, pewnosc REAL, liczba_osob INTEGER, opis TEXT
        );
    """)
    conn.commit()
    conn.close()


def zaladuj_sektory_z_mocka(sciezka_json="mock_data.json"):
    """Zasiewa tabele sektorow z mock_data.json (idempotentnie)."""
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), sciezka_json), encoding="utf-8") as f:
        dane = json.load(f)
    conn = polacz()
    for s in dane["sektory"]:
        conn.execute(
            """INSERT OR REPLACE INTO sektory (id, nazwa, wiersz, kolumna, lat_min, lat_max, lon_min, lon_max,
               lat_centrum, lon_centrum, ludnosc_szac, status, liczba_osob)
               VALUES (?,?,?,?,?,?,?,?,?,?,?, 'OK', 0)""",
            (s["id"], s["nazwa"], s["wiersz"], s["kolumna"], s["lat_min"], s["lat_max"], s["lon_min"],
             s["lon_max"], s["lat_centrum"], s["lon_centrum"], s["ludnosc_szac"]),
        )
    conn.commit()
    conn.close()


def resetuj_misje():
    """Czysci zdarzenia i statusy sektorow - wywolywane przy starcie kazdego scenariusza."""
    conn = polacz()
    conn.execute("DELETE FROM zdarzenia")
    conn.execute("UPDATE sektory SET status='OK', liczba_osob=0")
    conn.execute("DELETE FROM drony")
    conn.commit()
    conn.close()


def teraz_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def zapisz_zdarzenie(dron_id, sektor, status, pewnosc, liczba_osob, opis="", t_sym=0):
    conn = polacz()
    ts = teraz_iso()
    cur = conn.execute(
        """INSERT INTO zdarzenia (ts, t_sym, dron_id, sektor, status, pewnosc, liczba_osob, opis)
           VALUES (?,?,?,?,?,?,?,?)""",
        (ts, t_sym, dron_id, sektor, status, pewnosc, liczba_osob, opis),
    )
    zdarzenie_id = cur.lastrowid
    conn.commit()
    conn.close()
    return {"id": zdarzenie_id, "ts": ts, "t_sym": t_sym, "dron_id": dron_id, "sektor": sektor,
            "status": status, "pewnosc": pewnosc, "liczba_osob": liczba_osob, "opis": opis}


def aktualizuj_sektor(sektor_id, status, liczba_osob):
    conn = polacz()
    conn.execute("UPDATE sektory SET status=?, liczba_osob=? WHERE id=?", (status, liczba_osob, sektor_id))
    conn.commit()
    conn.close()


def zapisz_drony(drony):
    """Zapis stanu calej floty w jednej transakcji."""
    conn = polacz()
    conn.executemany(
        """INSERT OR REPLACE INTO drony (id, nazwa, tryb, sensor, bateria, status_misji,
           liczba_zanonimizowanych_twarzy, lat, lon) VALUES (?,?,?,?,?,?,?,?,?)""",
        [(d["id"], d["nazwa"], d["tryb"], d["sensor"], d["bateria"], d["status_misji"],
          d["twarze"], d["lat"], d["lon"]) for d in drony],
    )
    conn.commit()
    conn.close()


def pobierz_sektory():
    conn = polacz()
    wynik = [dict(r) for r in conn.execute("SELECT * FROM sektory ORDER BY wiersz, kolumna")]
    conn.close()
    return wynik


def pobierz_drony():
    conn = polacz()
    wynik = [dict(r) for r in conn.execute("SELECT * FROM drony ORDER BY id")]
    conn.close()
    return wynik


def pobierz_zdarzenia(limit=200):
    conn = polacz()
    wynik = [dict(r) for r in conn.execute("SELECT * FROM zdarzenia ORDER BY id DESC LIMIT ?", (limit,))]
    conn.close()
    return wynik


def liczba_sektorow_wg_statusu():
    conn = polacz()
    wynik = {r["status"]: r["n"] for r in conn.execute("SELECT status, COUNT(*) AS n FROM sektory GROUP BY status")}
    conn.close()
    return wynik
