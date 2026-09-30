# uruchom.py - start demonstratora HERMES: wolny port, serwer uvicorn i automatyczne otwarcie przegladarki.
# Wywolywany przez start.bat (mozna tez recznie: .venv\Scripts\python.exe uruchom.py).
import os
import socket
import sys
import threading
import time
import webbrowser

TUTAJ = os.path.dirname(os.path.abspath(__file__))
HOST = "127.0.0.1"


def wolny_port(start=8000, ile=30):
    """Pierwszy wolny port od 8000 w gore (8000 bywa zajety przez inne programy)."""
    for port in range(start, start + ile):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((HOST, port))
                return port
            except OSError:
                continue
    raise SystemExit(f"Brak wolnego portu w zakresie {start}-{start + ile - 1}.")


def otworz_przegladarke(url, port, limit_s=60):
    """Otwiera przegladarke dopiero, gdy serwer odpowiada."""
    koniec = time.time() + limit_s
    while time.time() < koniec:
        try:
            with socket.create_connection((HOST, port), timeout=1):
                webbrowser.open(url)
                return
        except OSError:
            time.sleep(0.5)


def main():
    os.chdir(TUTAJ)
    sys.path.insert(0, TUTAJ)
    port = int(os.environ.get("HERMES_PORT") or wolny_port())
    url = f"http://{HOST}:{port}"
    print(f"\n  HERMES dziala pod adresem:  {url}")
    print("  Przegladarka otworzy sie automatycznie. Aby zatrzymac serwer, zamknij to okno albo nacisnij Ctrl+C.\n",
          flush=True)
    if os.environ.get("HERMES_BEZ_PRZEGLADARKI") != "1":
        threading.Thread(target=otworz_przegladarke, args=(url, port), daemon=True).start()

    import uvicorn
    uvicorn.run("main:app", host=HOST, port=port, log_level="warning")


if __name__ == "__main__":
    main()
