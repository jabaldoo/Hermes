# anonymizer.py - anonimizacja twarzy NA POKLADZIE DRONA (edge), zanim cokolwiek opuszcza BSP.
# Zasada RODO by design: ta funkcja jest jedynym miejscem w systemie, ktore "widzi" surowa klatke
# z kamera. Do CZK nigdy nie trafia obraz - patrz edge_ai.py i simulator.py.
import cv2
import numpy as np
import os

_cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
face_cascade = cv2.CascadeClassifier(_cascade_path)

TRYBY_DOZWOLONE = ("blur", "pixel", "black")


def wykryj_twarze(klatka_bgr):
    """Zwraca liste prostokatow (x, y, w, h) wykrytych twarzy na klatce BGR."""
    szara = cv2.cvtColor(klatka_bgr, cv2.COLOR_BGR2GRAY)
    szara = cv2.equalizeHist(szara)
    twarze = face_cascade.detectMultiScale(
        szara, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30)
    )
    return twarze


def zaanonimizuj(klatka_bgr, twarze, tryb="blur"):
    """
    Nadpisuje regiony twarzy w klatce (na kopii) i zwraca zmodyfikowana klatke.
    Region kazdej twarzy jest dodatkowo powiekszany o margines (wlosy/broda/usy tez
    moga zdradzac tozsamosc), a blur laczy silna pikselizacje z rozmyciem gaussowskim,
    zeby detektor nie zdolal ponownie "zlapac" krawedzi oczu/nosa/ust po anonimizacji.
    """
    if tryb not in TRYBY_DOZWOLONE:
        tryb = "blur"
    wynik = klatka_bgr.copy()
    wys_ramki, szer_ramki = wynik.shape[:2]

    for (x, y, w, h) in twarze:
        margines = int(0.25 * max(w, h))
        x0 = max(0, x - margines)
        y0 = max(0, y - margines)
        x1 = min(szer_ramki, x + w + margines)
        y1 = min(wys_ramki, y + h + margines)
        roi = wynik[y0:y1, x0:x1]
        if roi.size == 0:
            continue

        if tryb == "blur":
            szer_roi, wys_roi = roi.shape[1], roi.shape[0]
            mala = cv2.resize(roi, (max(4, szer_roi // 12), max(4, wys_roi // 12)),
                               interpolation=cv2.INTER_LINEAR)
            rozmyta = cv2.resize(mala, (szer_roi, wys_roi), interpolation=cv2.INTER_LINEAR)
            jadro = max(31, (min(szer_roi, wys_roi) // 2) | 1)
            rozmyta = cv2.GaussianBlur(rozmyta, (jadro, jadro), 0)
            wynik[y0:y1, x0:x1] = rozmyta
        elif tryb == "pixel":
            mala = cv2.resize(roi, (8, 8), interpolation=cv2.INTER_LINEAR)
            wynik[y0:y1, x0:x1] = cv2.resize(mala, (x1 - x0, y1 - y0), interpolation=cv2.INTER_NEAREST)
        elif tryb == "black":
            wynik[y0:y1, x0:x1] = 0
    return wynik


def anonimizuj_klatke(klatka_bgr, tryb="blur"):
    """
    Pelny pipeline edge: detekcja + anonimizacja.
    Zwraca (klatka_zanonimizowana, liczba_wykrytych_twarzy).
    To jedyna funkcja, ktora powinna byc wywolywana z zewnatrz tego modulu.
    """
    twarze = wykryj_twarze(klatka_bgr)
    zanonimizowana = zaanonimizuj(klatka_bgr, twarze, tryb=tryb)
    return zanonimizowana, len(twarze)


def wczytaj_tryb_z_env():
    """Odczytuje ANON_MODE z .env / zmiennych srodowiskowych, domyslnie 'blur'."""
    tryb = os.environ.get("ANON_MODE", "blur").strip().lower()
    return tryb if tryb in TRYBY_DOZWOLONE else "blur"


def klatka_na_jpeg_bytes(klatka_bgr):
    """Koduje klatke BGR do bajtow JPEG (do podgladu demo w UI)."""
    ok, bufor = cv2.imencode(".jpg", klatka_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
    if not ok:
        raise RuntimeError("Nie udalo sie zakodowac klatki do JPEG")
    return bufor.tobytes()
