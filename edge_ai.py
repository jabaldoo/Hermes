# edge_ai.py - detekcja osob/pojazdow na pokladzie drona + wywolanie anonimizacji twarzy.
# Uzywa wbudowanego w OpenCV detektora HOG (bez dodatkowych ciezkich zaleznosci typu ONNX/YOLO).
# WYNIK TEJ WARSTWY TO WYLACZNIE METADANE: {sektor, status, pewnosc, ts, liczba_osob}.
# Surowa/zanonimizowana klatka NIGDY nie jest wysylana do CZK jako czesc strumienia operacyjnego -
# moze byc uzyta wylacznie lokalnie do panelu demonstracyjnego "oryginal vs zanonimizowany".
import math

import cv2
import numpy as np

from anonymizer import anonimizuj_klatke, face_cascade, wczytaj_tryb_z_env

_hog = cv2.HOGDescriptor()
_hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())


def _pewnosc_twarzy(klatka_bgr):
    """Pewnosc detekcji twarzy: znormalizowana waga ostatniego stopnia kaskady Haar (0-1)."""
    szara = cv2.equalizeHist(cv2.cvtColor(klatka_bgr, cv2.COLOR_BGR2GRAY))
    _, _, wagi = face_cascade.detectMultiScale3(
        szara, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30), outputRejectLevels=True
    )
    if len(wagi) == 0:
        return 0.0
    return round(1 - math.exp(-float(np.max(wagi)) / 2.5), 2)


def wykryj_ludzi(klatka_bgr):
    """Zwraca liste prostokatow wykrytych sylwetek ludzi (pieszy detector HOG)."""
    prostokaty, wagi = _hog.detectMultiScale(
        klatka_bgr, winStride=(8, 8), padding=(8, 8), scale=1.05
    )
    return prostokaty, wagi


def przetworz_klatke_na_pokladzie(klatka_bgr, tryb_anonimizacji=None):
    """
    Pelny pipeline edge AI wykonywany NA DRONIE:
      1) detekcja ludzi (HOG) -> liczba_osob, pewnosc
      2) detekcja + anonimizacja twarzy (przed jakimkolwiek wyslaniem danych)
    Zwraca:
      metadane: dict {liczba_osob, pewnosc, liczba_zanonimizowanych_twarzy}
      podglad_zanonimizowany: klatka BGR (WYLACZNIE do lokalnego podgladu demo, nie do CZK)
    """
    if tryb_anonimizacji is None:
        tryb_anonimizacji = wczytaj_tryb_z_env()

    prostokaty, wagi = wykryj_ludzi(klatka_bgr)
    liczba_osob = len(prostokaty)
    pewnosc = float(np.mean(wagi)) if len(wagi) > 0 else 0.0
    pewnosc = round(min(max(pewnosc, 0.0), 1.0) if pewnosc <= 1.0 else min(pewnosc / 2.0, 0.99), 2)

    podglad_zanonimizowany, liczba_twarzy = anonimizuj_klatke(klatka_bgr, tryb=tryb_anonimizacji)
    if liczba_twarzy and not liczba_osob:
        # zblizenie (np. portret) - sylwetki HOG brak, osobe potwierdza detektor twarzy
        pewnosc = _pewnosc_twarzy(klatka_bgr)

    metadane = {
        "liczba_osob": liczba_osob,
        "pewnosc": pewnosc,
        "liczba_zanonimizowanych_twarzy": liczba_twarzy,
    }
    return metadane, podglad_zanonimizowany
