# Architektura HERMES (demonstrator PoC)

## Pętla informacyjna

```
potrzeba → dron (mesh) → dane (RGB / termowizja) → analiza EDGE (na pokładzie)
   → metadane {sektor, status, pewność, ts, liczba_osób} → sieć mesh → CZK
   → wizualizacja (mapa, mapa ciepła) → decyzja (rekomendacja) → działanie (jednostki, komunikat)
```

Pasek na dole konsoli podświetla etapy pętli w chwili, gdy przechodzi przez nie realne zdarzenie.

## Warstwy

1. **Dron (edge)** — `edge_ai.py` + `anonymizer.py`. Jedyne miejsce, gdzie istnieje obraz.
   Detekcja osób (HOG), twarzy (Haar), anonimizacja (blur / pixel / black). Na zewnątrz — metadane.
2. **Rój i mesh** — `simulator.py` (zamiast ROS2/Gazebo). Dwa tryby BSP: aktywny (głośnik)
   i pasywny (sensor). Co tick:
   - lot do zadania, rozpoznanie sektora, orbita obserwacyjna lub rola przekaźnika,
   - graf łączności (zasięg 4,5 km) i BFS od CZK → liczba skoków dla każdego drona,
   - dron bez ścieżki do CZK buforuje metadane na pokładzie i dosyła je po odzyskaniu łączności,
   - utrata węzła (awaria, niska bateria) → zadania i rola przekaźnika przechodzą na najbliższy wolny
     dron. Brak pojedynczego punktu awarii.
3. **CZK** — `main.py` (FastAPI): REST + WebSocket `/ws` (stan co tick, zdarzenia na żywo).
   Gdy WebSocket jest niedostępny, konsola sama przechodzi na polling HTTP.
   Obraz sytuacji w CZK zmienia się dopiero, gdy metadane faktycznie dotrą przez mesh.
4. **Decyzje** — `czk_logic.py`: status → jednostki + priorytet; ranking najbliższych schronów KG PSP
   (preferencja dostępności całodobowej). Dysponowanie uruchamia działania, po ich zakończeniu sektor
   wraca do OK.
5. **Dane publiczne** — `data_sources.py`: realne pobrania z krótkim timeoutem i cache,
   wywoływane poza pętlą zdarzeń (pula wątków), więc wolne API nie zatrzymuje symulacji.
6. **Frontend** — czysty HTML/JS/CSS, Leaflet + leaflet.heat + Chart.js z CDN. Brak biblioteki z CDN
   nie blokuje reszty konsoli.

## Scenariusze

Skrypty w `mock_data.json → scenariusze` (czytelne dla jury, łatwe do edycji): kroki z czasem misji
(`t` w sekundach), typ `alert` / `info` / `zadanie` (dron, sektor, wykrycie, komunikat, przekaźnik).

## Dlaczego bez Dockera / Kafki / PostGIS / GeoServer

Demonstrator ma ruszyć na dowolnym laptopie w kilka minut. Każdy ciężki komponent ma lekki
odpowiednik (tabela w README). W wersji produkcyjnej HERMES zamienniki należy zastąpić
docelowymi komponentami (Kafka dla skali, PostGIS dla zapytań przestrzennych itd.).
