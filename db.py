# db.py - warstwa SQLite (hermes.db). Zero konfiguracji, zero zewnetrznej bazy.
# Zadna tabela nie ma kolumny na obraz - tylko metadane i liczniki.
import json
import os
import sqlite3
from datetime import datetime, timezone

BAZA_PLIK = os.environ.get("HERMES_DB") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "hermes.db")

KOLUMNY_EWAKUACJI = ("ts", "t_sym", "scenariusz", "rodzaj", "typ", "sektor", "dron_id", "powiadomieni",
                     "podazyli", "w_schronie", "czas_s", "schron_id", "schron_adres", "odleglosc_km")


def polacz():
    conn = sqlite3.connect(BAZA_PLIK)
    conn.row_factory = sqlite3.Row
    return conn


def inicjalizuj_baze():
    conn = polacz()
    kolumny = {r["name"] for r in conn.execute("PRAGMA table_info(zdarzenia)")}
    if kolumny and "lat" not in kolumny:
        conn.execute("DROP TABLE zdarzenia")  # stary schemat - zdarzenia i tak sa czyszczone co scenariusz
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
            ts TEXT, t_sym INTEGER, dron_id TEXT, sektor TEXT, lat REAL, lon REAL,
            status TEXT, pewnosc REAL, liczba_osob INTEGER, opis TEXT
        );
        CREATE TABLE IF NOT EXISTS ewakuacje (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT, t_sym INTEGER, scenariusz TEXT, rodzaj TEXT, typ TEXT, sektor TEXT, dron_id TEXT,
            powiadomieni INTEGER, podazyli INTEGER, w_schronie INTEGER, czas_s INTEGER,
            schron_id TEXT, schron_adres TEXT, odleglosc_km REAL
        );
    """)
    conn.commit()
    conn.close()


def zaladuj_sektory_z_mocka(sciezka_json="mock_data.json"):
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
    """Czysci zdarzenia i statusy sektorow. Dane o ewakuacjach (testy z ludnoscia) zostaja."""
    conn = polacz()
    conn.execute("DELETE FROM zdarzenia")
    conn.execute("UPDATE sektory SET status='OK', liczba_osob=0")
    conn.execute("DELETE FROM drony")
    conn.commit()
    conn.close()


def teraz_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def zapisz_zdarzenie(dron_id, sektor, status, pewnosc, liczba_osob, opis="", t_sym=0, lat=None, lon=None):
    conn = polacz()
    ts = teraz_iso()
    lat = round(lat, 6) if lat is not None else None
    lon = round(lon, 6) if lon is not None else None
    cur = conn.execute(
        """INSERT INTO zdarzenia (ts, t_sym, dron_id, sektor, lat, lon, status, pewnosc, liczba_osob, opis)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (ts, t_sym, dron_id, sektor, lat, lon, status, pewnosc, liczba_osob, opis),
    )
    zdarzenie_id = cur.lastrowid
    conn.commit()
    conn.close()
    return {"id": zdarzenie_id, "ts": ts, "t_sym": t_sym, "dron_id": dron_id, "sektor": sektor, "lat": lat,
            "lon": lon, "status": status, "pewnosc": pewnosc, "liczba_osob": liczba_osob, "opis": opis}


def aktualizuj_sektor(sektor_id, status, liczba_osob):
    conn = polacz()
    conn.execute("UPDATE sektory SET status=?, liczba_osob=? WHERE id=?", (status, liczba_osob, sektor_id))
    conn.commit()
    conn.close()


def zapisz_drony(drony):
    conn = polacz()
    conn.executemany(
        """INSERT OR REPLACE INTO drony (id, nazwa, tryb, sensor, bateria, status_misji,
           liczba_zanonimizowanych_twarzy, lat, lon) VALUES (?,?,?,?,?,?,?,?,?)""",
        [(d["id"], d["nazwa"], d["tryb"], d["sensor"], d["bateria"], d["status_misji"],
          d["twarze"], d["lat"], d["lon"]) for d in drony],
    )
    conn.commit()
    conn.close()


def zapisz_ewakuacje(wpis):
    """Wynik testu z ludnoscia: ilu powiadomiono, ilu podazylo za dronem, ilu dotarlo do schronu."""
    wpis = dict(wpis, ts=teraz_iso())
    conn = polacz()
    conn.execute(f"INSERT INTO ewakuacje ({', '.join(KOLUMNY_EWAKUACJI)}) VALUES ({', '.join('?' * len(KOLUMNY_EWAKUACJI))})",
                 [wpis.get(k) for k in KOLUMNY_EWAKUACJI])
    conn.commit()
    conn.close()
    return wpis


def pobierz_ewakuacje(limit=1000):
    conn = polacz()
    wynik = [dict(r) for r in conn.execute("SELECT * FROM ewakuacje ORDER BY id DESC LIMIT ?", (limit,))]
    conn.close()
    return wynik


def wyczysc_ewakuacje():
    conn = polacz()
    conn.execute("DELETE FROM ewakuacje")
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
