# drogi.py - siec drog (OpenStreetMap, snapshot w data/drogi.json) do prowadzenia ludzi przez drona.
# Dron prowadzi grupe ulicami, nie "po prostej": trasa i wybor schronu licza sie po odleglosci drogowej.
import heapq
import math

KM_NA_STOPIEN_LAT = 111.2
KM_NA_STOPIEN_LON = 69.93
_KOMORKA = 0.004          # siatka indeksu przestrzennego (ok. 450 x 280 m)
MAKS_DOJSCIE_KM = 0.35    # tak daleko od drogi moze lezec start / cel (np. schron w glebi osiedla)


def _km(a, b):
    return math.hypot((a[0] - b[0]) * KM_NA_STOPIEN_LAT, (a[1] - b[1]) * KM_NA_STOPIEN_LON)


class SiecDrog:
    def __init__(self, dane, zablokowany=None):
        """`zablokowany(lat, lon)` - wezly, ktorych trasa nie moze przecinac (np. strefy zakazu lotow)."""
        self.wezly = [(la / 1e5, lo / 1e5) for la, lo in dane["wezly"]]
        wolne = [not (zablokowany and zablokowany(*p)) for p in self.wezly]
        self.sasiedzi = [[] for _ in self.wezly]
        for i, j in dane["krawedzie"]:
            if wolne[i] and wolne[j]:
                d = _km(self.wezly[i], self.wezly[j])
                self.sasiedzi[i].append((j, d))
                self.sasiedzi[j].append((i, d))
        self.siatka = {}
        for i, p in enumerate(self.wezly):
            if self.sasiedzi[i]:
                self.siatka.setdefault(self._komorka(p), []).append(i)

    @staticmethod
    def _komorka(p):
        return int(p[0] // _KOMORKA), int(p[1] // _KOMORKA)

    def najblizszy_wezel(self, lat, lon, maks_km=MAKS_DOJSCIE_KM):
        k = self._komorka((lat, lon))
        najlepszy, odl = None, maks_km
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for i in self.siatka.get((k[0] + dx, k[1] + dy), ()):
                    d = _km((lat, lon), self.wezly[i])
                    if d < odl:
                        najlepszy, odl = i, d
        return najlepszy

    def _sciezka(self, poprz, koniec):
        wynik = []
        while koniec is not None:
            wynik.append(self.wezly[koniec])
            koniec = poprz.get(koniec)
        return wynik[::-1]

    def najblizszy_cel(self, start, cele, maks_km=8.0):
        """
        Dijkstra od punktu startu do najblizszego (po drogach) z celow.
        `cele` - slownik {wezel: obiekt}. Zwraca (obiekt, trasa [(lat, lon), ...], dlugosc_km) albo None.
        """
        s = self.najblizszy_wezel(*start)
        if s is None:
            return None
        dist, poprz, kolejka = {s: 0.0}, {s: None}, [(0.0, s)]
        while kolejka:
            d, w = heapq.heappop(kolejka)
            if d > dist.get(w, 1e9):
                continue
            if w in cele:
                return cele[w], self._sciezka(poprz, w), d
            if d > maks_km:
                break
            for v, dl in self.sasiedzi[w]:
                nd = d + dl
                if nd < dist.get(v, 1e9):
                    dist[v], poprz[v] = nd, w
                    heapq.heappush(kolejka, (nd, v))
        return None

    def trasa(self, a, b, maks_km=12.0):
        """Najkrotsza trasa po drogach z punktu a do punktu b (A*). Zwraca (trasa, dlugosc_km) albo None."""
        s, c = self.najblizszy_wezel(*a), self.najblizszy_wezel(*b)
        if s is None or c is None:
            return None
        cel = self.wezly[c]
        dist, poprz, kolejka = {s: 0.0}, {s: None}, [(_km(self.wezly[s], cel), s)]
        while kolejka:
            _, w = heapq.heappop(kolejka)
            d = dist[w]
            if w == c:
                return self._sciezka(poprz, w), d
            if d > maks_km:
                break
            for v, dl in self.sasiedzi[w]:
                nd = d + dl
                if nd < dist.get(v, 1e9):
                    dist[v], poprz[v] = nd, w
                    heapq.heappush(kolejka, (nd + _km(self.wezly[v], cel), v))
        return None


def uprosc(trasa, tol_km=0.004):
    """Douglas-Peucker - mniej punktow do wysylki przez WebSocket i plynniejszy ruch drona."""
    if len(trasa) < 3:
        return list(trasa)
    a, b = trasa[0], trasa[-1]
    ax, ay = a[1] * KM_NA_STOPIEN_LON, a[0] * KM_NA_STOPIEN_LAT
    bx, by = b[1] * KM_NA_STOPIEN_LON, b[0] * KM_NA_STOPIEN_LAT
    dl = math.hypot(bx - ax, by - ay) or 1e-9
    najdalej, i_max = -1.0, 0
    for i in range(1, len(trasa) - 1):
        px, py = trasa[i][1] * KM_NA_STOPIEN_LON, trasa[i][0] * KM_NA_STOPIEN_LAT
        d = abs((bx - ax) * (ay - py) - (ax - px) * (by - ay)) / dl
        if d > najdalej:
            najdalej, i_max = d, i
    if najdalej <= tol_km:
        return [a, b]
    return uprosc(trasa[:i_max + 1], tol_km)[:-1] + uprosc(trasa[i_max:], tol_km)
