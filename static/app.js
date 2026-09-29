// app.js — konsola CZK systemu HERMES.
// Stan przychodzi z backendu przez WebSocket (/ws); gdy WS niedostepny — automatyczny fallback na polling HTTP.
"use strict";

const CFG = document.body.dataset;
const STATUSY = ["OK", "POMOC", "WYPADEK", "POZAR", "ZAGROZENIE", "PANIKA", "LUDZIE", "ZATOR"];
const TYPY_INC = STATUSY.slice(1);
const KOLOR = {
  OK: "#2fd98f", LUDZIE: "#ffd23f", PANIKA: "#ff6bd6", ZATOR: "#ff9f43", WYPADEK: "#8b9dff", POZAR: "#ff5a1f",
  POMOC: "#ff3355", ZAGROZENIE: "#b56cff", ALERT: "#ff3355", INFO: "#7aa2ff", KOMUNIKAT: "#7cc4ff", MESH: "#7cc4ff",
  SLUZBY: "#60a5fa", EWAKUACJA: "#34d399", ZRZUT: "#e2e8f0", DECYZJA: "#7cc4ff",
};
const NAZWA = { OK: "OK", LUDZIE: "LUDZIE", PANIKA: "PANIKA", ZATOR: "ZATOR", WYPADEK: "WYPADEK", POZAR: "POŻAR",
  POMOC: "POMOC", ZAGROZENIE: "ZAGROŻENIE", ALERT: "ALERT", INFO: "INFO", KOMUNIKAT: "KOMUNIKAT", MESH: "MESH",
  SLUZBY: "SŁUŻBY", EWAKUACJA: "EWAKUACJA", ZRZUT: "ZRZUT", DECYZJA: "DECYZJA" };
const KATEGORIA = { OK: "sluzby", SLUZBY: "sluzby", ZRZUT: "sluzby", DECYZJA: "sluzby", EWAKUACJA: "ludzie", KOMUNIKAT: "ludzie",
  MESH: "mesh", ALERT: "system", INFO: "system" };
TYPY_INC.forEach((t) => { KATEGORIA[t] = "wykrycia"; });
const NAZWY_SLUZB = { Policja: "Policja", PSP: "Straż (PSP)", ZRM: "Pogotowie (ZRM)" };
const KOLORY_REGIONOW = ["#7fa9d6", "#c9ab72", "#a293cf", "#6fb096", "#c98ea0", "#8d9fcf", "#c99c7c", "#98b57c"];
const ANTENA_SVG = '<svg viewBox="0 0 26 30"><path d="M13 12 7 29h2.4l1.2-3.6h4.8l1.2 3.6H19zm-1.6 11.2L13 18.4l1.6 4.8z" fill="currentColor"/><circle cx="13" cy="9" r="2.6" fill="currentColor"/><path d="M7.6 3.6a7.6 7.6 0 0 0 0 10.8M18.4 3.6a7.6 7.6 0 0 1 0 10.8M4.4 1a11.6 11.6 0 0 0 0 16M21.6 1a11.6 11.6 0 0 1 0 16" stroke="currentColor" stroke-width="1.7" fill="none" stroke-linecap="round"/></svg>';

const svg = (d, vb = "0 0 24 24") => `<svg viewBox="${vb}" aria-hidden="true">${d}</svg>`;
const AUTO = '<path d="M5 11l1.6-4.2A2 2 0 0 1 8.5 5.5h7a2 2 0 0 1 1.9 1.3L19 11h1a1 1 0 0 1 1 1v5h-2v2h-3v-2H8v2H5v-2H3v-5a1 1 0 0 1 1-1zm2.2 0h9.6l-1.1-3.2H8.3zM7 15.2a1.3 1.3 0 1 0 0-2.6 1.3 1.3 0 0 0 0 2.6zm10 0a1.3 1.3 0 1 0 0-2.6 1.3 1.3 0 0 0 0 2.6z"/>';
const IKONY = {
  LUDZIE: svg('<circle cx="9" cy="7" r="3.2"/><path d="M2.5 20c0-3.6 2.9-6.5 6.5-6.5s6.5 2.9 6.5 6.5z"/><circle cx="17" cy="8" r="2.6"/><path d="M15.8 13.6c3.3-.3 5.7 2.3 5.7 6.4h-4.2c0-2.5-.5-4.6-1.5-6.4z"/>'),
  PANIKA: svg('<circle cx="14.5" cy="3.8" r="2.2"/><path d="m10 8.3 3.3-1.3 3 3.2 3.2.8-.5 1.9-3.9-1-1.2-1.3-1 3.5 2.6 2.5V22h-2v-5.2l-2.8-2.5-1 4.2L5 21l-1-1.7 3.4-2 1.4-4.6.8-2.9-1.6.7-.9 3-1.9-.5 1.1-4z"/>'),
  ZATOR: svg(AUTO),
  WYPADEK: svg(`<g transform="rotate(-16 11 13)">${AUTO}</g><path d="m19.5 1 .9 2.6 2.6.9-2.6.9-.9 2.6-.9-2.6-2.6-.9 2.6-.9z"/>`),
  POZAR: svg('<path d="M12 2c1 3.5-1.5 5-1.5 7.5 0 1.4 1 2.5 2.3 2.5 1.6 0 2.4-1.4 2.2-3 2.5 1.7 4 4.3 4 7 0 3.9-3.1 6-7 6s-7-2.6-7-6.3C5 11.8 10.5 8 12 2z"/>'),
  POMOC: svg('<path d="M9 3h6v6h6v6h-6v6H9v-6H3V9h6z"/>'),
  ZAGROZENIE: svg('<circle cx="10" cy="14.5" r="7"/><path d="m14.6 8.2 2-2 1.4 1.4-2 2zM18.2 4.3l1-1.8 1.1.6-1 1.8zm1.6 2.6 2-.3.2 1.2-2 .3z"/>'),
  OK: svg('<path d="M9.5 16.2 5.3 12l-1.4 1.4 5.6 5.6L20.1 8.4 18.7 7z"/>'),
  ALERT: svg('<path fill-rule="evenodd" d="M12 2 1 21h22zm0 5 7.5 12.5h-15zM11 10h2v5h-2zm0 6.5h2v2h-2z"/>'),
  INFO: svg('<path d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zm1 15h-2v-6h2zm0-8h-2V7h2z"/>'),
  KOMUNIKAT: svg('<path d="M3 9v6h4l5 4V5L7 9zm13.5 3a4.5 4.5 0 0 0-2.5-4v8a4.5 4.5 0 0 0 2.5-4zM14 3.2v2.1a7 7 0 0 1 0 13.4v2.1a9 9 0 0 0 0-17.6z"/>'),
  MESH: svg('<circle cx="12" cy="5" r="2.6"/><circle cx="5" cy="18" r="2.6"/><circle cx="19" cy="18" r="2.6"/><path d="M11.2 7.3 5.9 15.6l1.3.8 5.3-8.3zm1.6 0-1.3.8 5.3 8.3 1.3-.8zM7.6 17.3h8.8v1.5H7.6z"/>'),
  SLUZBY: svg('<path d="M7 11a5 5 0 0 1 10 0v6H7zM4 18.5h16V22H4zM11 1.5h2v3h-2zM3.3 4.9l1.4-1.4 2.1 2.1-1.4 1.4zm14.5.7 2.1-2.1 1.4 1.4-2.1 2.1z"/>'),
  EWAKUACJA: svg('<path d="M12 2 4 5v6c0 5 3.4 9.5 8 11 4.6-1.5 8-6 8-11V5zm0 4.2 4 1.5V11c0 3-1.7 5.8-4 7z"/>'),
  ZRZUT: svg('<path fill-rule="evenodd" d="M9 3h6v3h5a1 1 0 0 1 1 1v12a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5zm2 2v1h2V5zm0 5v3H8v2h3v3h2v-3h3v-2h-3v-3z"/>'),
  PIN: svg('<path d="M12 2a7 7 0 0 0-7 7c0 5.2 7 13 7 13s7-7.8 7-13a7 7 0 0 0-7-7zm0 9.5A2.5 2.5 0 1 1 12 6.5a2.5 2.5 0 0 1 0 5z"/>'),
  DESZCZ: svg('<path d="M17.5 8.5a5.5 5.5 0 0 0-10.7-1A4.5 4.5 0 0 0 7 16.5h10.5a4 4 0 0 0 0-8zM8 18l-1.2 3h1.6L9.6 18zm4 0-1.2 3h1.6l1.2-3zm4 0-1.2 3h1.6l1.2-3z"/>'),
  SLONCE: svg('<circle cx="12" cy="12" r="4.5"/><path d="M11 1h2v4h-2zm0 18h2v4h-2zM1 11h4v2H1zm18 0h4v2h-4zM4.2 5.6l1.4-1.4 2.8 2.8L7 8.4zm11.4 11.4 1.4-1.4 2.8 2.8-1.4 1.4zM4.2 18.4l2.8-2.8 1.4 1.4-2.8 2.8zM15.6 7l2.8-2.8 1.4 1.4L17 8.4z"/>'),
  CHMURA: svg('<path d="M17.5 9.5a5.5 5.5 0 0 0-10.7-1A4.5 4.5 0 0 0 7 17.5h10.5a4 4 0 0 0 0-8z"/>'),
  PAUZA: svg('<path d="M7 5h3.5v14H7zm6.5 0H17v14h-3.5z"/>'),
  START: svg('<path d="M7 4.5v15l12.5-7.5z"/>'),
  GLOSNIK_ON: svg('<path d="M3 9v6h4l5 4V5L7 9zm13.5 3a4.5 4.5 0 0 0-2.5-4v8a4.5 4.5 0 0 0 2.5-4zM14 3.2v2.1a7 7 0 0 1 0 13.4v2.1a9 9 0 0 0 0-17.6z"/>'),
  GLOSNIK_OFF: svg('<path d="M3 9v6h4l5 4V5L7 9zm13.6 3 2.7-2.7-1.3-1.3-2.7 2.7-2.7-2.7-1.3 1.3 2.7 2.7-2.7 2.7 1.3 1.3 2.7-2.7 2.7 2.7 1.3-1.3z"/>'),
};
const SCHRON_SVG = (h24) => `<svg viewBox="0 0 24 26"><path d="M12 1 2 5v7c0 6.3 4.3 11.4 10 13 5.7-1.6 10-6.7 10-13V5z" fill="${h24 ? "#0f5132" : "#0b2f25"}" stroke="${h24 ? "#bbf7d0" : "#34d399"}" stroke-width="2"/><path d="M6.8 13.6 12 9.2l5.2 4.4V18H6.8z" fill="${h24 ? "#bbf7d0" : "#34d399"}"/></svg>`;

const DRON_SVG = `<svg class="dron-svg" viewBox="-18 -18 36 36" aria-hidden="true">
  <g stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><line x1="-9" y1="-9" x2="9" y2="9"/><line x1="9" y1="-9" x2="-9" y2="9"/></g>
  <g fill="none" stroke="currentColor" stroke-width="1.5">
    <circle class="rotor" cx="-9" cy="-9" r="5.2" stroke-dasharray="6 3"/><circle class="rotor" cx="9" cy="-9" r="5.2" stroke-dasharray="6 3"/>
    <circle class="rotor" cx="-9" cy="9" r="5.2" stroke-dasharray="6 3"/><circle class="rotor" cx="9" cy="9" r="5.2" stroke-dasharray="6 3"/>
  </g>
  <rect x="-4" y="-5.5" width="8" height="11" rx="2.6" fill="currentColor"/>
  <path d="M0-15.5 3.4-10H-3.4z" fill="currentColor"/>
</svg>`;

const ui = { stan: null, ids: new Set(), dzwiek: false, zakladka: "incydenty", sygSektorow: "", sygKrokow: "",
  sygStat: "", trybAnon: "blur", ws: null, polling: null, ostatnieId: 0, incDane: [], incPodswietlony: null };

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const tplus = (s) => { s = Math.max(0, s | 0); return `T+${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`; };
const mmss = (s) => `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, "0")}`;
const proc = (v) => (v === null || v === undefined ? "—" : `${Math.round(v)}%`);

async function post(url) {
  const r = await fetch(url, { method: "POST" });
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
  return r.json();
}
async function pobierz(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(r.statusText);
  return r.json();
}
function throttle(fn, ms) {
  let czeka = false, ponownie = false;
  return function wywolaj() {
    if (czeka) { ponownie = true; return; }
    czeka = true;
    fn();
    setTimeout(() => { czeka = false; if (ponownie) { ponownie = false; wywolaj(); } }, ms);
  };
}

// ====================================================================== MAPA

const M = { mapa: null, bazowe: {}, prg: null, ulice: null, sektory: {}, def: {}, etykiety: [], drony: {}, mesh: [], schrony: null,
  strefy: null, budynki: null, podswietlenie: null, scen: {}, pingi: {}, grupy: {}, stacje: {}, regiony: null, zasiegi: null, kolorStacji: {} };

function inicjalizujMape() {
  const mapa = L.map("mapa", { zoomControl: false, zoomSnap: 0.25 });
  M.mapa = mapa;
  L.control.zoom({ position: "bottomleft" }).addTo(mapa);
  // pRzeka nad regionami, sektorami i lączami mesh - inaczej Odra ginie w centrum miasta pod nakladkami
  [["pRegiony", 350], ["pScen", 360], ["pStrefy", 370], ["pSektory", 380], ["pMesh", 430], ["pBudynki", 435], ["pRzeka", 440],
    ["pSchrony", 445], ["pUlice", 455], ["pEtykiety", 460], ["pStacje", 610], ["pGrupy", 620]]
    .forEach(([n, z]) => { mapa.createPane(n).style.zIndex = z; });
  mapa.getPane("pUlice").style.pointerEvents = "none";
  mapa.getPane("pRzeka").style.pointerEvents = "none";
  // nazwy ulic (etykiety OSM) nad ortofotomapa - dopiero po przyblizeniu; OSM i Ciemna maja wlasne etykiety
  // kafle CARTO ida przez backend (/kafle/carto/...), ktory dokleja klucz API z .env
  M.ulice = L.tileLayer("/kafle/carto/dark_only_labels/{z}/{x}/{y}.png",
    { pane: "pUlice", minZoom: 15, maxZoom: 19, className: "warstwa-ulice", attribution: "Etykiety © OpenStreetMap © CARTO" });

  M.bazowe = {
    osm: L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 19, className: "warstwa-osm", attribution: "© OpenStreetMap" }),
    orto: L.tileLayer(CFG.ortoWmts, { maxZoom: 19, className: "warstwa-orto", attribution: 'Ortofotomapa © <a href="https://www.geoportal.gov.pl">GUGiK</a>' }),
    ciemna: L.tileLayer("/kafle/carto/dark_all/{z}/{x}/{y}.png", { maxZoom: 19, attribution: "© OpenStreetMap © CARTO" }),
  };
  M.baza = "osm";
  M.bazowe.osm.addTo(mapa);
  M.prg = L.tileLayer.wms(CFG.prgWms, { layers: "A03_Granice_gmin", format: "image/png", transparent: true, version: "1.3.0", className: "warstwa-prg", attribution: "PRG © GUGiK" });
  mapa.on("zoomstart", () => mapa.getContainer().classList.add("bez-animacji"));
  mapa.on("zoomend", () => {
    // z daleka tylko schrony calodobowe - inaczej 1200+ ikon zakrywa mape
    mapa.getContainer().classList.toggle("oddalona", mapa.getZoom() < 14);
    setTimeout(() => mapa.getContainer().classList.remove("bez-animacji"), 50);
  });
  M.podswietlenie = L.layerGroup().addTo(mapa);
}

function dopasujWidok() {
  M.mapa.once("zoomend", () => M.mapa.getContainer().classList.toggle("oddalona", M.mapa.getZoom() < 14));
  const b = L.latLngBounds(Object.values(M.def).flatMap((s) => [[s.lat_min, s.lon_min], [s.lat_max, s.lon_max]]));
  M.mapa.fitBounds(b, { padding: [16, 16] });
}

const ikonaHtml = (html) => L.divIcon({ className: "", iconSize: [0, 0], html });

function zbudujWarstwyStatyczne(w) {
  w.sektory.forEach((s) => { M.def[s.id] = s; });
  dopasujWidok();
  w.sektory.forEach((s) => {
    // sektory nie reaguja na klikniecie - klik w mape nie otwiera zadnych okienek
    const r = L.rectangle([[s.lat_min, s.lon_min], [s.lat_max, s.lon_max]], { pane: "pSektory", stroke: false, interactive: false,
      fillColor: "#9fb4d8", fillOpacity: 0.03 }).addTo(M.mapa);
    M.sektory[s.id] = r;
    M.etykiety.push(L.marker([s.lat_max, s.lon_min], { pane: "pEtykiety", interactive: false,
      icon: L.divIcon({ className: "etykieta-sektora", html: `<span>${s.id}</span>`, iconSize: null, iconAnchor: [-5, -4] }) }).addTo(M.mapa));
  });

  // strefy zakazu lotow: obrys terenu wojskowego (OSM) + bufor; wewnatrz faktyczne granice terenow
  M.strefy = L.layerGroup(w.strefy_zakazane.flatMap((s) => {
    const n = s.polygon.length;
    const srodek = [s.polygon.reduce((a, p) => a + p[0], 0) / n, s.polygon.reduce((a, p) => a + p[1], 0) / n];
    return [
      L.polygon(s.polygon, { pane: "pStrefy", className: "strefa-zakazu", color: "#ff3355", weight: 2, dashArray: "8 5", interactive: false }),
      ...s.tereny.map((t) => L.polygon(t, { pane: "pStrefy", color: "#ff6b81", weight: 1.2, fill: false, interactive: false, className: "teren-wojskowy" })),
      L.marker(srodek, { pane: "pEtykiety", interactive: false,
        icon: ikonaHtml(`<div class="etykieta-strefy"><b>ZAKAZ LOTÓW BSP</b><span>${esc(s.nazwa)}</span></div>`) }),
    ];
  })).addTo(M.mapa);

  // stacje-przekazniki (range extenders) i ich regiony wg granic osiedli
  w.stacje.forEach((s, i) => { M.kolorStacji[s.id] = KOLORY_REGIONOW[i % KOLORY_REGIONOW.length]; });
  M.regiony = L.layerGroup(w.osiedla.map((o) => L.polygon(o.polygon, { pane: "pRegiony", interactive: false,
    stroke: false, fillColor: M.kolorStacji[o.stacja], fillOpacity: 0.07 }))).addTo(M.mapa);
  M.zasiegi = L.layerGroup(w.stacje.map((s) => L.circle([s.lat, s.lon], { pane: "pRegiony", radius: w.zasieg_km * 1000, interactive: false,
    color: M.kolorStacji[s.id], weight: 1, dashArray: "3 6", fill: false })));
  w.stacje.forEach((s) => {
    const regiony = w.osiedla.filter((o) => o.stacja === s.id).map((o) => o.nazwa);
    M.stacje[s.id] = L.marker([s.lat, s.lon], { pane: "pStacje", icon: ikonaHtml(
      `<div class="stacja" style="--k:${M.kolorStacji[s.id]};color:${M.kolorStacji[s.id]}">${ANTENA_SVG}<span>${esc(s.id)}</span></div>`) })
      .bindTooltip(`<b>${esc(s.id)} · ${esc(s.nazwa)}</b><br>Stacja-przekaźnik mesh + baza ładowania<br><small>Region: ${esc(regiony.join(", "))}</small>`, { direction: "top", offset: [0, -30] })
      .addTo(M.mapa);
  });
  M.stacjeDane = w.stacje;

  M.budynki = L.layerGroup(w.budynki.map((b) => L.rectangle(
    [[b.lat_min - 0.0004, b.lon_min - 0.0006], [b.lat_max + 0.0004, b.lon_max + 0.0006]],
    { pane: "pBudynki", color: "#ff2d2d", weight: 2, fill: true, fillOpacity: 0.05, className: "budynek-wysoki" })
    .bindTooltip(`<b>${esc(b.nazwa || "Wysoki budynek")}</b> — ${b.wysokosc_m} m<br>Przeszkoda lotnicza (OpenStreetMap)`))).addTo(M.mapa);
  $("#liczba-budynkow").textContent = w.budynki.length;

  const scen = M.scen;
  // Odra (OSM): ciemna obwodka + jasny nurt + plynace kreski, zeby rzeka odcinala sie od kazdej mapy bazowej
  scen.odra = L.layerGroup([
    L.polyline(w.odra, { pane: "pRzeka", color: "#03101f", weight: 13, opacity: 0.8, lineCap: "round", lineJoin: "round", interactive: false }),
    L.polyline(w.odra, { pane: "pRzeka", color: "#2fd4ff", weight: 7, opacity: 1, lineCap: "round", lineJoin: "round", interactive: false }),
    L.polyline(w.odra, { pane: "pRzeka", color: "#e8fbff", weight: 2, opacity: 0.9, dashArray: "3 14", className: "odra-nurt", interactive: false }),
  ]);
  scen.strefa_zalewowa = L.polygon(w.strefa_zalewowa, { pane: "pScen", stroke: false, fillColor: "#1d7fe0", fillOpacity: 0.35 })
    .bindTooltip("Strefa zalewowa wzdłuż Odry (model: 450 m od nurtu)", { sticky: true });
  scen.las = L.polygon(w.las, { pane: "pScen", color: "#22c55e", weight: 1.2, fillColor: "#16a34a", fillOpacity: 0.22 })
    .bindTooltip("Las Osobowicki — obszar BDL (mock)", { sticky: true });
  scen.ogniska = L.layerGroup();
  ustawOgniska(w.ogniska);

  L.marker([w.baza.lat, w.baza.lon], { zIndexOffset: 500, icon: ikonaHtml(`<div class="baza-czk"><svg viewBox="0 0 24 24"><path d="M12 2 21 7v10l-9 5-9-5V7z" fill="#050b15" stroke="#7cc4ff" stroke-width="1.6"/><path d="M12 7.5v8m-3.5-6a5 5 0 0 1 7 0m-9-2a8 8 0 0 1 11 0" stroke="#7cc4ff" stroke-width="1.5" fill="none" stroke-linecap="round"/></svg><span>CZK</span></div>`) })
    .bindTooltip(`<b>${esc(w.baza.nazwa)}</b><br>Węzeł główny sieci mesh`, { direction: "top" }).addTo(M.mapa);
}

async function zaladujSchrony() {
  const dane = await pobierz("/api/schrony");
  M.schrony = L.layerGroup(dane.punkty.map((p) => {
    const h24 = p.dostepnosc === "Całodobowa";
    return L.marker([p.lat, p.lon], { pane: "pSchrony", icon: L.divIcon({ className: "", iconSize: [0, 0],
      html: `<div class="schron-ikona${h24 ? " h24" : ""}">${SCHRON_SVG(h24)}</div>` }) })
      .bindPopup(`<div class="popup-tytul">Miejsce schronienia</div><div>${esc(p.adres)}</div>
        <div>Dostępność: <b>${esc(p.dostepnosc)}</b></div><div class="popup-meta">${esc(p.id)} · KG PSP / dane.gov.pl</div>`);
  }));
  if ($("#w-schrony").checked) M.schrony.addTo(M.mapa);
  $("#liczba-schronow").textContent = dane.punkty.length;
  $("#schrony-opis").innerHTML = `Na mapie <b>${dane.punkty.length}</b> punktów schronienia z obszaru demo — oficjalny zbiór KG PSP „Punkty schronienia w Polsce” (dane.gov.pl, CC BY 4.0, aktualizacja co tydzień${dane.pobrano ? `, pobrano ${esc(dane.pobrano)}` : ""}). Przy alarmie drony prowadzą grupy do najbliższego schronu (preferowane całodobowe), omijając strefy wojskowe. Przy powodzi wybierają budynek poza strefą zalewową, a przy pożarze lasu — punkt zbiórki poza lasem.`;
}

// ---------------------------------------------------------------- aktualizacje mapy

function aktualizujSektory(lista) {
  const syg = lista.map((s) => `${s.id}${s.status}`).join();
  if (syg === ui.sygSektorow) return false;
  ui.sygSektorow = syg;
  lista.forEach((s) => {
    const alarm = s.status !== "OK";
    M.sektory[s.id].setStyle({ fillColor: alarm ? KOLOR[s.status] : "#9fb4d8", fillOpacity: alarm ? 0.12 : 0.03 });
  });
  return true;
}

function etykietaPingu(i) {
  // liczba osob tylko wtedy, gdy osoby na pewno widac na zdjeciu zgloszenia
  return `${NAZWA[i.typ]}${i.osoby_na_zdjeciu ? ` · ${i.osoby_na_zdjeciu} os.` : ""}${i.czeka ? " · CZEKA" : ""}`;
}

function aktualizujIncydenty(lista) {
  const obecne = new Set();
  lista.forEach((i) => {
    obecne.add(String(i.id));
    let m = M.pingi[i.id];
    if (!m) {
      m = L.marker([i.lat, i.lon], { pane: "pGrupy", zIndexOffset: 800,
        icon: ikonaHtml(`<div class="ping k-${i.typ}"><i></i><i></i><b>!</b><span class="ping-et"></span></div>`) }).addTo(M.mapa);
      m.on("click", () => pokazZgloszenie(i.id));
      M.pingi[i.id] = m;
    }
    const el = m.getElement()?.firstElementChild;
    if (!el) return;
    const et = el.querySelector(".ping-et");
    const tekst = etykietaPingu(i);
    if (et.textContent !== tekst) et.textContent = tekst;
    el.classList.toggle("podswietlony", ui.incPodswietlony === i.id);
    el.classList.toggle("rozpatrzony", !i.czeka);
  });
  Object.keys(M.pingi).forEach((id) => { if (!obecne.has(id)) { M.pingi[id].remove(); delete M.pingi[id]; } });
}

function kropki(n) {
  return `<span class="grupa-kropki">${"<i></i>".repeat(Math.max(1, Math.min(12, n)))}</span>`;
}

function aktualizujGrupy(grupy) {
  const obecne = new Set();
  grupy.forEach((g) => {
    const k = String(g.inc_id);
    obecne.add(k);
    let o = M.grupy[k];
    if (!o) {
      o = {
        idzie: L.marker([g.lat, g.lon], { pane: "pGrupy", interactive: false, icon: L.divIcon({ className: "znacznik-dron", iconSize: [0, 0], html: "" }) }).addTo(M.mapa),
        zostali: L.marker(g.start, { pane: "pGrupy", interactive: false, icon: ikonaHtml("") }),
        linia: L.polyline([[g.lat, g.lon], g.schron], { pane: "pMesh", color: "#34d399", weight: 2.5, dashArray: "2 7", className: "trasa-ewak", interactive: false }).addTo(M.mapa),
        syg: "",
      };
      M.grupy[k] = o;
    }
    o.idzie.setLatLng([g.lat, g.lon]);
    o.linia.setLatLngs([[g.lat, g.lon], g.schron]);
    const syg = `${g.n}|${g.prowadzona}|${g.pozostali}`;
    if (syg !== o.syg) {
      o.syg = syg;
      const el = o.idzie.getElement();
      if (el) el.innerHTML = `<div class="grupa${g.prowadzona ? " prowadzona" : ""}">${kropki(g.n)}<b>${g.n}</b></div>`;
      if (g.pozostali > 0) {
        o.zostali.setIcon(ikonaHtml(`<div class="grupa pozostali">${kropki(g.pozostali)}<b>${g.pozostali} nie idzie</b></div>`));
        if (!M.mapa.hasLayer(o.zostali)) o.zostali.addTo(M.mapa);
      }
    }
  });
  Object.keys(M.grupy).forEach((k) => {
    if (obecne.has(k)) return;
    const o = M.grupy[k];
    [o.idzie, o.zostali, o.linia].forEach((l) => l.remove());
    delete M.grupy[k];
  });
}

function aktualizujDrony(drony) {
  drony.forEach((d) => {
    let m = M.drony[d.id];
    if (!m) {
      m = L.marker([d.lat, d.lon], { zIndexOffset: 1000, icon: L.divIcon({ className: "znacznik-dron", iconSize: [0, 0],
        html: `<div class="dron"><div class="dron-fale"><i></i><i></i><i></i></div>${DRON_SVG}<div class="dron-etykieta"></div></div>` }) }).addTo(M.mapa);
      m.on("click", () => { przelaczZakladke("flota"); podswietlDrona(d.id); });
      M.drony[d.id] = m;
    } else {
      m.setLatLng([d.lat, d.lon]);
    }
    const el = m.getElement()?.firstElementChild;
    if (!el) return;
    el.className = ["dron", d.tryb, d.nadaje && "nadaje", !d.zywy && "utracony", d.zywy && d.hops === null && "offline",
      (d.faza === "rtb" || d.faza === "ladowanie") && "rtb", d.faza === "prowadzi" && "prowadzi",
      d.faza === "uziemiony" && "uziemiony"].filter(Boolean).join(" ");
    el.querySelector(".dron-svg").style.transform = `rotate(${d.kurs}deg)`;
    el.querySelector(".dron-etykieta").innerHTML = !d.zywy ? `${d.id} · UTRACONY`
      : d.faza === "uziemiony" ? `${d.id} · UZIEMIONY (DESZCZ)`
      : `${d.id} · ${Math.round(d.bateria)}%${d.faza === "prowadzi" ? " · PROWADZI" : ""}${d.bufor ? ` · <em>BUF ${d.bufor}</em>` : d.hops === null ? " · <em>OFFLINE</em>" : ""}`;
  });
}

function aktualizujMesh(linki) {
  const widoczne = $("#w-mesh").checked;
  while (M.mesh.length < linki.length) M.mesh.push(L.polyline([[0, 0], [0, 0]], { pane: "pMesh", className: "mesh-link", color: "#1f58a6", interactive: false }));
  M.mesh.forEach((l, i) => {
    const k = linki[i];
    if (!k || !widoczne) { if (M.mapa.hasLayer(l)) l.remove(); return; }
    l.setLatLngs([k.a, k.b]);
    l.setStyle({ weight: 1.8 + 2.4 * k.jakosc, opacity: 0.7 + 0.3 * k.jakosc });
    if (!M.mapa.hasLayer(l)) l.addTo(M.mapa);
  });
}

// ogniska zaleza od wylosowanego wariantu pozaru (las, dom, blok, hala) - [lat, lon, promien_m]
function ustawOgniska(lista) {
  const syg = JSON.stringify(lista || []);
  if (syg === M.sygOgnisk) return;
  M.sygOgnisk = syg;
  M.scen.ogniska.clearLayers();
  (lista || []).forEach(([lat, lon, r]) => L.circle([lat, lon], { pane: "pScen", radius: r || 320, color: "#ff5a36", weight: 1.5,
    fillColor: "#ff5a36", fillOpacity: 0.35, className: "ognisko", interactive: false }).addTo(M.scen.ogniska));
}

function aktualizujWarstwyScenariusza(warstwy, ogniska) {
  if (ogniska) ustawOgniska(ogniska);
  const pokaz = $("#w-scen").checked;
  Object.entries(M.scen).forEach(([k, warstwa]) => {
    const ma = pokaz && warstwy.includes(k);
    if (ma && !M.mapa.hasLayer(warstwa)) warstwa.addTo(M.mapa);
    if (!ma && M.mapa.hasLayer(warstwa)) warstwa.remove();
  });
}

function podswietlIncydent(inc) {
  M.podswietlenie.clearLayers();
  ui.incPodswietlony = inc ? inc.id : null;
  $$(".ping").forEach((p) => p.classList.remove("podswietlony"));
  if (!inc) return;
  M.pingi[inc.id]?.getElement()?.firstElementChild?.classList.add("podswietlony");
  if (inc.schron && inc.aktywny) {
    L.polyline([[inc.lat, inc.lon], [inc.schron.lat, inc.schron.lon]], { pane: "pMesh", color: "#34d399", weight: 2.5, dashArray: "2 7", className: "trasa-ewak", interactive: false }).addTo(M.podswietlenie);
    L.circleMarker([inc.schron.lat, inc.schron.lon], { pane: "pMesh", radius: 14, color: "#34d399", weight: 2.5, fill: false, interactive: false }).addTo(M.podswietlenie);
  }
}

function aktualizujStacje(stacje) {
  stacje.forEach((s) => {
    const el = M.stacje[s.id]?.getElement()?.firstElementChild;
    if (el) el.classList.toggle("awaria", !s.zywa);
  });
  const syg = stacje.map((s) => `${s.id}${s.zywa}`).join() + (ui.stan?.drony || []).map((d) => d.stacja).join();
  if (syg === ui.sygStacji || !M.stacjeDane) return;
  ui.sygStacji = syg;
  const zywe = Object.fromEntries(stacje.map((s) => [s.id, s.zywa]));
  $("#lista-stacji").innerHTML = M.stacjeDane.map((s) => {
    const drony = (ui.stan?.drony || []).filter((d) => d.stacja === s.id).map((d) => d.nazwa);
    return `<div class="stacja-wiersz${zywe[s.id] ? "" : " awaria"}" style="--k:${M.kolorStacji[s.id]}"><i></i>
      <div><b>${esc(s.id)}</b> ${esc(s.nazwa)}<br><small>${zywe[s.id] ? "online" : "AWARIA"} · baza: ${esc(drony.join(", ") || "—")}</small></div>
      <button data-stacja="${esc(s.id)}">${zywe[s.id] ? "Awaria" : "Przywróć"}</button></div>`;
  }).join("");
}

// ====================================================================== STAN

function obsluzStan(s) {
  ui.stan = s;
  document.body.classList.toggle("pauza", s.pauza);
  M.mapa.getContainer().style.setProperty("--tick", `${0.5 / s.predkosc}s`);
  $("#zegar").textContent = tplus(s.czas);
  $("#btn-pauza").innerHTML = s.pauza ? IKONY.START : IKONY.PAUZA;
  $$("#seg-scenariusz button").forEach((b) => b.classList.toggle("aktywny", b.dataset.scen === s.scenariusz.id));
  $$("#seg-predkosc button").forEach((b) => b.classList.toggle("aktywny", +b.dataset.x === s.predkosc));
  const hud = $("#hud-scenariusz");
  if (hud.textContent !== s.scenariusz.nazwa) hud.textContent = s.scenariusz.nazwa;
  // nowy wariant ze wskazanym rejonem zdarzenia (np. plonacy budynek) - mapa podlatuje w jego okolice
  const sygScen = `${s.scenariusz.id}|${s.scenariusz.wariant}`;
  if (sygScen !== ui.sygScen) {
    const o = s.scenariusz.obszar;
    if (o) M.mapa.flyTo([o.lat, o.lon], o.r_km > 1.2 ? 14 : 15, { duration: 1.2 });
    else if (ui.sygScen && ui.bylObszar) dopasujWidok();
    ui.sygScen = sygScen;
    ui.bylObszar = !!o;
  }

  renderujMisje(s.scenariusz);
  renderujPogode(s.pogoda, s.scenariusz.godzina_startu, s.czas);
  aktualizujSektory(s.sektory);
  aktualizujIncydenty(s.incydenty);
  aktualizujGrupy(s.grupy);
  aktualizujDrony(s.drony);
  aktualizujMesh(s.linki);
  aktualizujWarstwyScenariusza(s.scenariusz.warstwy, s.scenariusz.ogniska);
  renderujStatystyki(s);
  renderujFlote(s.drony);
  aktualizujStacje(s.stacje);

  const czeka = s.incydenty.filter((i) => i.czeka);
  const licznik = $("#licznik-inc");
  licznik.hidden = czeka.length === 0;
  licznik.textContent = czeka.length;
  const sygCzeka = czeka.map((i) => i.id).join();
  if (sygCzeka !== ui.sygCzeka) {
    ui.sygCzeka = sygCzeka;
    odswiezIncydenty();
  } else if (ui.zakladka === "incydenty") {
    odswiezIncydentyT();
  }
}

function renderujMisje(sc) {
  const syg = sc.id + sc.kroki.map((k) => k.stan).join();
  if (syg === ui.sygKrokow) return;
  ui.sygKrokow = syg;
  const tag = $("#misja-tag");
  tag.textContent = sc.id === "patrol" ? "PATROL" : sc.rodzaj === "ćwiczenie" ? "ĆWICZENIA" : "SCENARIUSZ";
  tag.classList.toggle("cwiczenie", sc.rodzaj === "ćwiczenie");
  $("#misja-nazwa").textContent = sc.nazwa;
  $("#misja-opis").textContent = sc.opis;
  const kroki = sc.kroki;
  const wykonane = kroki.filter((k) => k.stan === "wykonany").length;
  const biezacy = kroki.find((k) => k.stan === "w toku") || [...kroki].reverse().find((k) => k.stan === "wykonany");
  $("#misja-krok").textContent = kroki.length
    ? (biezacy ? `${tplus(biezacy.t)} · ${biezacy.opis}` : "Oczekiwanie na pierwszy krok")
    : "Patrol ciągły — wykrycia losowe (ważone). Wybierz scenariusz u góry.";
  const segmenty = kroki.length || 10;
  $("#misja-postep").innerHTML = Array.from({ length: segmenty }, (_, i) => {
    if (!kroki.length) return "<i></i>";
    return `<i class="${kroki[i].stan === "wykonany" ? "gotowy" : kroki[i].stan === "w toku" ? "teraz" : ""}"></i>`;
  }).join("");
  $("#misja-postep-opis").textContent = kroki.length ? `${wykonane} z ${kroki.length} kroków wykonanych` : "brak skryptu scenariusza";
}

// godzina w scenariuszu = godzina startu scenariusza + czas symulacji
function godzinaScenariusza(start, czas) {
  const [h, m] = (start || "12:00").split(":").map(Number);
  const min = (h * 60 + m + Math.floor(czas / 60)) % 1440;
  return `${String(Math.floor(min / 60)).padStart(2, "0")}:${String(min % 60).padStart(2, "0")}`;
}

const LIMIT_OPADU_STD = 4; // mm/h - powyzej lataja tylko drony w wersji deszczowej (IP55)
const liczbaPl = (x, n = 1) => x.toFixed(n).replace(".", ",");

function renderujPogode(p, start, czas) {
  const ik = p.opad_mm_h > 0 ? IKONY.DESZCZ : p.temperatura_c >= 28 ? IKONY.SLONCE : IKONY.CHMURA;
  const ulewa = p.opad_mm_h >= LIMIT_OPADU_STD;
  const html = `<span class="pg" title="Godzina w scenariuszu"><small>GODZINA</small><b>${godzinaScenariusza(start, czas)}</b></span>`
    + `<span class="pg">${ik}<small>TEMP.</small><b>${liczbaPl(p.temperatura_c)}°C</b></span>`
    + `<span class="pg"><small>WIATR</small><b>${Math.round(p.wiatr_kmh)} km/h</b></span>`
    + `<span class="pg${ulewa ? " ulewa" : ""}"${ulewa ? ` title="Opad powyżej limitu standardowych BSP (${LIMIT_OPADU_STD} mm/h) — latają tylko drony w wersji deszczowej IP55"` : ""}>`
    + `<small>OPAD</small><b>${p.opad_mm_h > 0 ? `${liczbaPl(p.opad_mm_h)} mm/h` : "brak"}</b></span>`;
  const chip = $("#chip-pogoda");
  if (chip.innerHTML !== html) chip.innerHTML = html;
  chip.title = `Warunki w scenariuszu (symulowane): ${p.opis}`;
}

let wykres;
function inicjalizujWykres() {
  if (typeof Chart === "undefined") return;
  wykres = new Chart($("#wykres"), {
    type: "doughnut",
    data: { labels: STATUSY.map((s) => NAZWA[s]), datasets: [{ data: [25, 0, 0, 0, 0, 0, 0, 0], backgroundColor: STATUSY.map((s) => KOLOR[s]), borderWidth: 0, spacing: 2, borderRadius: 3 }] },
    options: { cutout: "74%", responsive: false, animation: { duration: 500 }, plugins: { legend: { display: false } } },
  });
}

function renderujStatystyki(s) {
  const syg = JSON.stringify([s.licznik, s.statystyki]);
  if (syg === ui.sygStat) return;
  ui.sygStat = syg;
  if (wykres) { wykres.data.datasets[0].data = STATUSY.map((k) => s.licznik[k] || 0); wykres.update(); }
  $("#kpi-zagrozone").textContent = 25 - (s.licznik.OK || 0);
  $("#legenda-statusow").innerHTML = STATUSY.map((k) =>
    `<li class="k-${k}${s.licznik[k] ? "" : " zero"}"><i></i><span>${NAZWA[k]}</span><b>${s.licznik[k] || 0}</b></li>`).join("");
  const st = s.statystyki;
  $("#kpi-czeka").textContent = st.czeka;
  $("#kpi-incydenty").textContent = st.incydenty;
  $("#kpi-schron").textContent = st.w_schronie;
  $("#kpi-zrzuty").textContent = st.zrzuty;
  $("#kpi-mesh").textContent = `${st.wezly}/${st.wezly_razem}`;
  $("#kpi-stacje").textContent = `${st.stacje}/${st.stacje_razem}`;
}

// ====================================================================== ZDARZENIA

function obsluzZdarzenie(z, cicho = false) {
  if (ui.ids.has(z.id)) return;
  ui.ids.add(z.id);
  ui.ostatnieId = Math.max(ui.ostatnieId, z.id);
  dodajDoFeedu(z, cicho);
  const wykrycie = TYPY_INC.includes(z.status) && z.dron_id;
  if (cicho) {
    if (wykrycie) ustawPakiet(z, false);
    return;
  }
  if (z.status === "ALERT" || z.status === "INFO") swiecPetle([0]);
  else if (wykrycie) { swiecPetle([1, 2, 3, 4, 5]); ustawPakiet(z, true); }
  else if (z.status === "DECYZJA") swiecPetle([6]);
  else if (z.status === "SLUZBY") swiecPetle([6, 7]);
  else if (["KOMUNIKAT", "ZRZUT", "EWAKUACJA", "OK"].includes(z.status)) swiecPetle([7]);

  if (z.status === "ALERT") toast(z, "ALERT");
  else if (z.status === "MESH" && /Utrata|Awaria|brak łączności/.test(z.opis)) toast(z, "MESH");
  if (z.glos) powiedz(z.glos);
  if (ui.dzwiek && (z.status === "ALERT" || z.zgloszenie)) sygnal();
  if (z.analiza && ui.zakladka === "analiza") odswiezAnalizeT();
}

function dodajDoFeedu(z, cicho) {
  const li = document.createElement("li");
  li.className = `ev k-${z.status}${cicho ? "" : " nowe"}${z.lat ? " klikalne" : ""}`;
  li.dataset.kat = KATEGORIA[z.status] || "system";
  const dron = z.dron_id && ui.stan?.drony.find((d) => d.id === z.dron_id);
  const meta = [
    dron ? `<span>${esc(dron.nazwa)}</span>` : z.dron_id ? `<span>${esc(z.dron_id)}</span>` : "<span>CZK</span>",
    z.liczba_osob ? `<span>${z.liczba_osob} os.</span>` : "",
    TYPY_INC.includes(z.status) && z.dron_id ? `<span>pewność ${Math.round(z.pewnosc * 100)}%</span>` : "",
  ].join("");
  li.innerHTML = `<div class="ev-ikona">${IKONY[z.status] || IKONY.INFO}</div>
    <div><div class="ev-gora"><span class="ev-tytul">${NAZWA[z.status] || esc(z.status)}${z.sektor ? ` · ${esc(z.sektor)}` : ""}</span>
    <span class="ev-czas">${tplus(z.t_sym)}</span></div><div class="ev-opis">${esc(z.opis)}</div><div class="ev-meta">${meta}</div></div>`;
  if (z.lat) li.addEventListener("click", () => M.mapa.flyTo([z.lat, z.lon], 15.5, { duration: 0.8 }));
  const feed = $("#feed");
  feed.prepend(li);
  while (feed.children.length > 150) feed.lastChild.remove();
}

function ustawPakiet(z, flash) {
  const el = $("#ostatni-pakiet");
  el.style.setProperty("--k", KOLOR[z.status]);
  el.innerHTML = `<span class="st">${NAZWA[z.status]}</span><span>${esc(z.sektor)}</span>`;
  $("#pk-czas").textContent = (z.ts || "").slice(11, 19) || "--:--:--";
  $("#pk-pewnosc").textContent = `pewność ${Math.round(z.pewnosc * 100)}%`;
  $("#pk-osoby").textContent = z.liczba_osob ? `${z.liczba_osob} os.` : "brak";
  const dron = ui.stan?.drony.find((d) => d.id === z.dron_id);
  $("#pk-dron").textContent = dron ? dron.nazwa : (z.dron_id || "—");
  if (flash) { el.classList.remove("flash"); void el.offsetWidth; el.classList.add("flash"); }
}

let petlaTimery = [];
function swiecPetle(indeksy) {
  const etapy = $$("#etapy li");
  petlaTimery.forEach(clearTimeout);
  petlaTimery = [];
  etapy.forEach((e) => e.classList.remove("swieci"));
  indeksy.forEach((idx, n) => petlaTimery.push(setTimeout(() => etapy[idx].classList.add("swieci"), n * 140)));
  petlaTimery.push(setTimeout(() => etapy.forEach((e) => e.classList.remove("swieci")), indeksy.length * 140 + 1600));
}

function toast(z, tytul) {
  const kont = $("#toasty");
  const el = document.createElement("div");
  el.className = "toast";
  el.style.setProperty("--k", KOLOR[z.status] || KOLOR.INFO);
  el.innerHTML = `${IKONY[z.status] || IKONY.INFO}<b>${esc(tytul)}</b><span>${esc(z.opis)}</span>`;
  kont.prepend(el);
  while (kont.children.length > 3) kont.lastChild.remove();
  setTimeout(() => { el.classList.add("znika"); setTimeout(() => el.remove(), 320); }, 5000);
}

function resetujWidok() {
  ui.ids.clear();
  ui.ostatnieId = 0;
  ui.sygSektorow = ui.sygKrokow = ui.sygStat = "";
  ui.incPodswietlony = null;
  $("#feed").innerHTML = "";
  $("#ostatni-pakiet").innerHTML = '<span class="st">—</span><span>—</span>';
  ["#pk-osoby", "#pk-dron"].forEach((s) => { $(s).textContent = "—"; });
  $("#pk-czas").textContent = "--:--:--";
  $("#pk-pewnosc").textContent = "pewność —";
  M.podswietlenie.clearLayers();
  ui.incDane = [];
  ui.sygCzeka = "";
  ui.sygListyInc = "";
  if (ui.zakladka === "incydenty") renderujIncydenty([]);
}

// ====================================================================== DZWIEK

function powiedz(tekst) {
  if (!ui.dzwiek || !("speechSynthesis" in window)) return;
  const u = new SpeechSynthesisUtterance(tekst);
  u.lang = "pl-PL";
  u.rate = 1.03;
  const glos = speechSynthesis.getVoices().find((v) => v.lang?.toLowerCase().startsWith("pl"));
  if (glos) u.voice = glos;
  speechSynthesis.speak(u);
}

let audioCtx;
function sygnal() {
  try {
    audioCtx = audioCtx || new AudioContext();
    [0, 0.18].forEach((t) => {
      const o = audioCtx.createOscillator(), g = audioCtx.createGain();
      o.frequency.value = 880;
      g.gain.setValueAtTime(0.0001, audioCtx.currentTime + t);
      g.gain.exponentialRampToValueAtTime(0.12, audioCtx.currentTime + t + 0.02);
      g.gain.exponentialRampToValueAtTime(0.0001, audioCtx.currentTime + t + 0.14);
      o.connect(g).connect(audioCtx.destination);
      o.start(audioCtx.currentTime + t);
      o.stop(audioCtx.currentTime + t + 0.15);
    });
  } catch { /* brak Web Audio */ }
}

// ====================================================================== POLACZENIE

function ustawPolaczenie(tryb) {
  const chip = $("#chip-link");
  chip.className = `stat stat-link ${tryb}`;
  chip.querySelector("span").textContent = { ws: "LIVE · WebSocket", http: "LIVE · HTTP", off: "OFFLINE — ponawiam" }[tryb];
  chip.title = { ws: "Połączenie na żywo z backendem (WebSocket)", http: "WebSocket niedostępny — odświeżanie przez HTTP co 1 s", off: "Brak połączenia z backendem HERMES" }[tryb];
  const lacze = $("#petla-status");
  lacze.className = `pakiet-lacze ${tryb}`;
  lacze.querySelector("span").textContent = { ws: "Gotowy — łącze na żywo", http: "Łącze zastępcze (HTTP)", off: "Brak łącza z CZK" }[tryb];
}

function obsluzWiadomosc(w) {
  if (w.typ === "init") {
    resetujWidok();
    w.zdarzenia.forEach((z) => obsluzZdarzenie(z, true));
    obsluzStan(w.stan);
  } else if (w.typ === "reset") {
    resetujWidok();
  } else if (w.typ === "zdarzenie") {
    obsluzZdarzenie(w.dane);
  } else if (w.typ === "stan") {
    obsluzStan(w.dane);
  }
}

function polaczWS() {
  const ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`);
  ui.ws = ws;
  let otwarty = false;
  const limit = setTimeout(() => { if (!otwarty) ws.close(); }, 4000);
  ws.onopen = () => { otwarty = true; clearTimeout(limit); zatrzymajPolling(); ustawPolaczenie("ws"); };
  ws.onmessage = (e) => obsluzWiadomosc(JSON.parse(e.data));
  ws.onclose = () => {
    clearTimeout(limit);
    if (ui.ws !== ws) return;
    ui.ws = null;
    uruchomPolling();
    setTimeout(polaczWS, 3000);
  };
}

function uruchomPolling() {
  if (ui.polling) return;
  const krok = async () => {
    try {
      const [stan, zdarzenia] = await Promise.all([pobierz("/api/stan"), pobierz("/api/zdarzenia?limit=40")]);
      if (ui.stan && (stan.czas < ui.stan.czas || stan.scenariusz.id !== ui.stan.scenariusz.id)) resetujWidok();
      const pierwszy = ui.ostatnieId === 0;
      zdarzenia.reverse().forEach((z) => obsluzZdarzenie(z, pierwszy));
      obsluzStan(stan);
      if (!ui.ws || ui.ws.readyState !== WebSocket.OPEN) ustawPolaczenie("http");
    } catch {
      ustawPolaczenie("off");
    }
  };
  krok();
  ui.polling = setInterval(krok, 1000);
}

function zatrzymajPolling() {
  clearInterval(ui.polling);
  ui.polling = null;
}

// ====================================================================== ZAKLADKI

function przelaczZakladke(nazwa) {
  ui.zakladka = nazwa;
  $$(".zakladki button").forEach((b) => b.classList.toggle("aktywna", b.dataset.tab === nazwa));
  $$(".tab").forEach((t) => t.classList.toggle("widoczna", t.id === `tab-${nazwa}`));
  if (nazwa === "rodo" && !ui.anonZaladowane) zaladujAnonimizacje();
  if (nazwa === "incydenty") { ui.sygListyInc = ""; odswiezIncydenty(); }
  if (nazwa === "analiza") odswiezAnalize();
}

// ---------------------------------------------------------------- incydenty

function htmlFoto(i) {
  const f = i.zdjecie;
  if (!f) return "";
  return `<figure class="foto"><img src="${esc(f.url)}" alt="${esc(f.opis)}" loading="lazy">
    <span class="foto-et">TWARZE ZAMAZANE</span>
    ${i.osoby_na_zdjeciu ? `<span class="foto-osoby">${i.osoby_na_zdjeciu} os. na zdjęciu</span>` : ""}
    <figcaption>${esc(f.opis)} · fot. <a href="${esc(f.zrodlo)}" target="_blank" rel="noopener">${esc(f.autor)}</a>, ${esc(f.licencja)}</figcaption></figure>`;
}

function htmlPrzyciskowDecyzji(i) {
  const sluzby = i.sluzby.map((j) => NAZWY_SLUZB[j]).join(" + ");
  const czeka = i.czeka;
  const moznaSluzby = i.aktywny && i.sluzby.length && !i.sluzby_powiadomione;
  return `${czeka ? `<button class="btn-dec wyslij" data-decyzja="dron" data-id="${i.id}">Wyślij drona</button>` : ""}
    ${moznaSluzby ? `<button class="btn-dec sluzby" data-decyzja="sluzby" data-id="${i.id}">Przekaż: ${esc(sluzby)}</button>` : ""}
    ${czeka ? `<button class="btn-dec odrzuc" data-decyzja="odrzuc" data-id="${i.id}">Odrzuć</button>` : ""}`;
}

function htmlAkcjiDrona(i) {
  if (!i.akcja) return "";
  // cel prowadzenia zalezy od sytuacji: schron (alarm), budynek poza strefa zalewowa (powodz), punkt zbiorki (las)
  const s = i.schron;
  const gdzie = s ? `<b>${esc(s.adres)}</b> (${s.odleglosc_km} km${s.dostepnosc === "Całodobowa" ? ", 24h" : ""})` : "";
  const kto = esc(i.wykonawca || "dron");
  const teksty = {
    prowadzenie: {
      oczekuje: "Czeka na wolnego drona z głośnikiem.",
      przydzielona: `${kto} leci do grupy → ${esc(s?.do || "")}: ${gdzie}`,
      w_toku: `${kto} prowadzi <b>${i.podazyli}/${i.osoby_grupy}</b> os. → ${gdzie}`,
      zakonczona: `<b>${i.w_schronie}</b> os. ${esc(s?.w || "")}: ${gdzie}`,
    },
    zrzut: { oczekuje: "Czeka na drona z apteczką.", przydzielona: `${kto} leci z apteczką`, w_toku: `${kto} na miejscu — zrzut wykonany, trwa obserwacja`, zakonczona: "Zaopatrzenie dostarczone" },
    ostrzezenie: { oczekuje: "Czeka na drona z głośnikiem.", przydzielona: `${kto} leci ostrzec ludzi`, w_toku: `${kto} nadaje ostrzeżenie`, zakonczona: "Ludzie ostrzeżeni" },
    odsuniecie: { oczekuje: "Czeka na drona z głośnikiem.", przydzielona: `${kto} leci na miejsce zdarzenia`, w_toku: `${kto} prosi ludzi o odsunięcie się`, zakonczona: "Ludzie odsunięci na bezpieczną odległość" },
    uspokojenie: { oczekuje: "Czeka na drona z głośnikiem.", przydzielona: `${kto} leci do tłumu`, w_toku: `${kto} uspokaja tłum i wskazuje wyjście`, zakonczona: "Tłum uspokojony" },
    obserwacja: { oczekuje: "Czeka na wolnego drona.", przydzielona: `${kto} leci na miejsce`, w_toku: `${kto} obserwuje miejsce zdarzenia`, zakonczona: "Obserwacja zakończona" },
  };
  return `<div class="inc-linia">${IKONY.EWAKUACJA}<span>${teksty[i.rodzaj_akcji]?.[i.akcja] || ""}</span></div>`;
}

function htmlStanuZgloszenia(i) {
  if (!i.aktywny) return `<div class="inc-stan">ZAMKNIĘTE — ${esc(i.wynik || "")}</div>`;
  if (i.czeka) return '<div class="inc-stan czeka">CZEKA NA DECYZJĘ OPERATORA</div>';
  const czesci = [];
  if (i.decyzja === "dron") czesci.push("wysłano drona");
  if (i.sluzby_powiadomione) czesci.push("przekazano służbom");
  return `<div class="inc-stan">DECYZJA: ${czesci.join(" + ").toUpperCase()}</div>`;
}

function renderujIncydenty(lista) {
  const kont = $("#lista-inc");
  if (!lista.length) { kont.innerHTML = '<p class="pusto">Brak zgłoszeń — rój patroluje.</p>'; return; }
  const syg = JSON.stringify(lista);
  if (syg === ui.sygListyInc) return;
  ui.sygListyInc = syg;
  kont.innerHTML = lista.map((i) => `
    <article class="inc k-${i.typ}${i.aktywny ? "" : " zamkniety"}" data-id="${i.id}">
      <div class="inc-gora"><span class="prio">P${i.priorytet}</span><span class="inc-nazwa">${esc(i.nazwa)}</span>
        <span class="inc-sektor">#${i.id} · ${esc(i.sektor)} · ${tplus(i.t)}</span></div>
      ${i.aktywny ? htmlFoto(i) : ""}
      <p>${esc(i.opis)} <span class="inc-sektor">— zgłasza ${esc(i.zglaszajacy)}</span></p>
      <div class="wsp">${IKONY.PIN}<span>${esc(i.wsp)}</span><button data-kopiuj="${i.lat}, ${i.lon}">kopiuj</button></div>
      ${htmlStanuZgloszenia(i)}${i.czeka ? `<div class="zg-zalecenie"><b>Zalecenie:</b> ${esc(i.zalecenie)}</div>` : ""}${htmlAkcjiDrona(i)}
      ${i.zrzut.length ? `<div class="inc-linia zrzut">${IKONY.ZRZUT}<span>Zrzut z drona: ${esc(i.zrzut.join(", "))}</span></div>` : ""}
      ${i.aktywny ? `<div class="inc-decyzje">${htmlPrzyciskowDecyzji(i)}</div>` : ""}
    </article>`).join("");
}

// klik w ping na mapie - zgloszenie otwiera sie w zakladce "Zgloszenia" (decyzje podejmuje sie tam)
function pokazZgloszenie(id) {
  przelaczZakladke("incydenty");
  setTimeout(() => {
    const karta = $(`.inc[data-id="${id}"]`);
    if (!karta) return;
    karta.scrollIntoView({ behavior: "smooth", block: "center" });
    karta.classList.add("wskazane");
    setTimeout(() => karta.classList.remove("wskazane"), 1600);
  }, 200);
}

async function odswiezIncydenty() {
  try {
    ui.incDane = await pobierz("/api/incydenty");
  } catch { return; }
  if (ui.zakladka === "incydenty") renderujIncydenty(ui.incDane);
}

async function podejmijDecyzje(przycisk) {
  $$(`[data-id="${przycisk.dataset.id}"][data-decyzja]`).forEach((b) => { b.disabled = true; });
  try { await post(`/api/decyzja/${przycisk.dataset.id}/${przycisk.dataset.decyzja}`); } catch { /* juz rozpatrzone */ }
  ui.sygListyInc = "";
  await odswiezIncydenty();
}
const odswiezIncydentyT = throttle(odswiezIncydenty, 1000);

// ---------------------------------------------------------------- flota

function zbudujKarteFloty(d) {
  const el = document.createElement("article");
  el.className = "fk";
  el.dataset.id = d.id;
  el.innerHTML = `
    <div class="fk-gora"><span class="fk-id">${d.id}</span><span class="fk-nazwa">${esc(d.nazwa)}</span>
      <span class="fk-tryb">${d.tryb === "aktywny" ? "AKTYWNY · przewodnik" : "PASYWNY"}<br>${esc(d.sensor)}</span></div>
    <div class="fk-status"></div>
    <div class="fk-spec"></div>
    <div class="fk-bateria"><div class="pasek"><i></i></div><span class="fk-bat"></span></div>
    <div class="fk-metryki">
      <div><span>Mesh</span><b class="m-mesh"></b></div><div><span>Twarze</span><b class="m-twarze"></b></div>
      <div><span>Zadania</span><b class="m-zad"></b></div><div><span>Bufor</span><b class="m-buf"></b></div>
    </div>
    <div class="apteczka"><div class="apteczka-tytul">${IKONY.ZRZUT}Apteczka do zrzutu</div><ul></ul></div>
    <div class="fk-akcje">${d.tryb === "aktywny" ? `<button class="glos" data-id="${d.id}">Komunikat głosowy</button>` : ""}
      <button class="awaria" data-wezel="${d.id}">Symuluj awarię</button></div>`;
  return el;
}

function renderujFlote(drony) {
  const kont = $("#lista-flota");
  drony.forEach((d) => {
    let el = kont.querySelector(`[data-id="${d.id}"]`);
    if (!el) { el = zbudujKarteFloty(d); kont.appendChild(el); }
    el.classList.toggle("aktywny", d.tryb === "aktywny");
    el.classList.toggle("utracony", !d.zywy);
    el.classList.toggle("uziemiony", d.faza === "uziemiony");
    el.querySelector(".fk-status").textContent = d.status_misji;
    const spec = `${d.odporny ? "Wersja deszczowa" : "Wersja standardowa"} · ${d.spec}`;
    const specEl = el.querySelector(".fk-spec");
    if (specEl.textContent !== spec) specEl.textContent = spec;
    specEl.classList.toggle("odporny", d.odporny);
    const pasek = el.querySelector(".pasek i");
    pasek.style.width = `${d.bateria}%`;
    pasek.className = d.bateria < 20 ? "niska" : d.bateria < 45 ? "srednia" : "";
    el.querySelector(".fk-bat").textContent = `${Math.round(d.bateria)}%`;
    const mesh = el.querySelector(".m-mesh");
    mesh.textContent = !d.zywy ? "—" : d.hops === null ? "OFFLINE" : `${d.hops} skok`;
    mesh.classList.toggle("zly", d.zywy && d.hops === null);
    el.querySelector(".m-twarze").textContent = d.twarze;
    el.querySelector(".m-zad").textContent = d.kolejka;
    const buf = el.querySelector(".m-buf");
    buf.textContent = d.bufor;
    buf.classList.toggle("zly", d.bufor > 0);
    const apteczka = Object.entries(d.zapas).map(([nazwa, n]) =>
      `<li class="${n === 0 ? "brak" : n < d.zapas_start[nazwa] ? "malo" : ""}">${esc(nazwa)}<b>×${n}</b></li>`).join("");
    const ul = el.querySelector(".apteczka ul");
    if (ul.innerHTML !== apteczka) ul.innerHTML = apteczka;
    const btn = el.querySelector("[data-wezel]");
    btn.textContent = d.zywy ? "Symuluj awarię" : "Przywróć (nowy BSP)";
    btn.className = d.zywy ? "awaria" : "przywroc";
    const glos = el.querySelector(".glos");
    if (glos) glos.disabled = !d.zywy || d.faza === "uziemiony";
  });
}

function podswietlDrona(id) {
  $$(".fk").forEach((e) => e.classList.toggle("podswietlony", e.dataset.id === id));
  $(`.fk[data-id="${id}"]`)?.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

// ---------------------------------------------------------------- analiza

async function odswiezAnalize() {
  let a;
  try { a = await pobierz("/api/analiza"); } catch { return; }
  const r = a.razem;
  $("#an-ewak").textContent = r.ewakuacje;
  $("#an-podazanie").textContent = proc(r.podazanie_proc);
  $("#an-dotarcie").textContent = proc(r.dotarcie_proc);
  $("#an-czas").textContent = r.sr_czas_s === null ? "—" : mmss(r.sr_czas_s);
  const re = a.wg_rodzaju.realne, cw = a.wg_rodzaju["ćwiczenie"];
  const t = a.wg_typu;
  const wiersz = (nazwa, r1, r2) => `<tr><td>${nazwa}</td><td class="liczba">${proc(r1)}</td><td class="liczba">${proc(r2)}</td></tr>`;
  $("#tabela-typow tbody").innerHTML =
    wiersz("Podążyło za dronem (wszyscy)", re.podazanie_proc, cw.podazanie_proc)
    + wiersz("— grupy spokojne", t["realne|LUDZIE"], t["ćwiczenie|LUDZIE"])
    + wiersz("— osoby w panice", t["realne|PANIKA"], t["ćwiczenie|PANIKA"])
    + wiersz("Dotarło w bezpieczne miejsce", re.dotarcie_proc, cw.dotarcie_proc)
    + wiersz("Reakcja na komunikat głosowy", re.reakcja_proc, cw.reakcja_proc);
  $("#tabela-ewak tbody").innerHTML = a.ostatnie.length ? a.ostatnie.map((w) => {
    const rodzaj = w.rodzaj === "ćwiczenie" ? '<span class="badge cwiczenie">ĆWICZ.</span>' : '<span class="badge realne">REALNE</span>';
    const wynik = w.typ === "KOMUNIKAT"
      ? `<span class="liczba">${w.podazyli}/${w.powiadomieni}</span><small>zareagowało na komunikat</small>`
      : `<span class="liczba">${w.podazyli}/${w.powiadomieni}</span> podążyło · dotarło ${w.w_schronie}<small>${esc(w.schron_adres)} · ${mmss(w.czas_s || 0)}</small>`;
    return `<tr><td>${(w.ts || "").slice(11, 19)}</td><td>${rodzaj}<small>${w.typ === "KOMUNIKAT" ? "komunikat" : NAZWA[w.typ]}</small></td><td>${esc(w.sektor)}</td><td>${wynik}</td></tr>`;
  }).join("") : '<tr><td colspan="4" class="pusto">Brak danych — uruchom „Alarm RCB” lub „Alarm próbny”.</td></tr>';
}
const odswiezAnalizeT = throttle(odswiezAnalize, 1500);

// ---------------------------------------------------------------- rodo i dane

// klatki testowe z samples/ zmieniaja sie co kilka sekund w losowej kolejnosci (bez powtorzen w jednej rundzie)
const ANON_ZMIANA_MS = 7000;

function nastepnaProbka() {
  if (!ui.anonKolejka?.length) {
    const lista = (ui.anonProbki || []).filter((p) => p !== ui.anonPlik);
    for (let i = lista.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [lista[i], lista[j]] = [lista[j], lista[i]];
    }
    ui.anonKolejka = lista;
  }
  return ui.anonKolejka.shift();
}

async function zaladujAnonimizacje(nowaKlatka = false) {
  if (nowaKlatka && ui.anonLaduje) return; // poprzednia klatka jeszcze sie liczy - pomijamy ten takt rotacji
  ui.anonZaladowane = true;
  ui.anonLaduje = true;
  const kont = $("#porownanie");
  kont.style.opacity = 0.5;
  try {
    const plik = nowaKlatka ? nastepnaProbka() : ui.anonPlik;
    const r = await fetch(`/api/anonimizacja/demo?tryb=${ui.trybAnon}${plik ? `&plik=${encodeURIComponent(plik)}` : ""}`,
      { signal: AbortSignal.timeout(12000) });
    if (!r.ok) throw new Error(r.statusText);
    const d = await r.json();
    ui.anonPlik = d.plik;
    ui.anonProbki = d.probki;
    $("#img-przed").src = `data:image/jpeg;base64,${d.oryginal_base64}`;
    $("#img-po").src = `data:image/jpeg;base64,${d.zanonimizowany_base64}`;
    const p = d.pakiet_do_czk;
    $("#rp-status").textContent = NAZWA[p.status] || p.status;
    $("#rp-osoby").textContent = p.liczba_osob;
    $("#rp-pewnosc").textContent = `${Math.round(p.pewnosc * 100)}%`;
  } catch {
    $("#rp-status").textContent = "brak klatki";
  }
  ui.anonLaduje = false;
  kont.style.opacity = 1;
}

async function zaladujZrodla() {
  const zrodla = await pobierz("/api/zrodla");
  $("#tabela-zrodel tbody").innerHTML = zrodla.map((z) => {
    const realne = z.typ_uzycia.startsWith("realne");
    return `<tr><td><b>${esc(z.nazwa)}</b><small>${esc(z.jak)}</small></td><td><span class="badge ${realne ? "zrodlo-realne" : "mock"}">${esc(z.typ_uzycia)}</span></td></tr>`;
  }).join("");
}

const KIERUNKI = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"];

function zbudujKompas() {
  const ns = "http://www.w3.org/2000/svg";
  const g = $("#kompas-podzialka");
  for (let st = 0; st < 360; st += 10) {
    const duza = st % 30 === 0;
    const r1 = duza ? 45 : 48, r2 = 53;
    const a = ((st - 90) * Math.PI) / 180;
    const linia = document.createElementNS(ns, "line");
    linia.setAttribute("x1", 60 + r1 * Math.cos(a)); linia.setAttribute("y1", 60 + r1 * Math.sin(a));
    linia.setAttribute("x2", 60 + r2 * Math.cos(a)); linia.setAttribute("y2", 60 + r2 * Math.sin(a));
    if (duza) linia.setAttribute("class", "duza");
    g.appendChild(linia);
  }
  [["N", 0], ["E", 90], ["S", 180], ["W", 270]].forEach(([t, st]) => {
    const a = ((st - 90) * Math.PI) / 180;
    const el = document.createElementNS(ns, "text");
    el.setAttribute("x", 60 + 37 * Math.cos(a)); el.setAttribute("y", 60 + 37 * Math.sin(a));
    el.textContent = t;
    g.appendChild(el);
  });
}

// IMGW podaje pomiar co godzine - kompas lekko "oddycha" wokol niego (porywy, zmiennosc kierunku)
const wiatr = { st: null, kmh: 0, dSt: 0, dKmh: 0 };

function rysujKompas() {
  if (wiatr.st === null) return;
  const st = wiatr.st + wiatr.dSt;
  const kmh = Math.max(0, wiatr.kmh + wiatr.dKmh);
  const norm = ((Math.round(st) % 360) + 360) % 360;
  $("#kompas-st").textContent = norm;
  $("#kompas-kier").textContent = KIERUNKI[Math.round(norm / 22.5) % 16];
  $("#kompas-kmh").textContent = `${Math.round(kmh)} km/h`;
  $("#kompas-strzalka").style.transform = `rotate(${st}deg)`;
}

function ustawKompas(stopnie, kmh) {
  if (stopnie === null || stopnie === undefined) return;
  wiatr.st = stopnie;
  wiatr.kmh = kmh;
  rysujKompas();
}

function drganieKompasu() {
  const los = (a) => (Math.random() - 0.5) * a;
  wiatr.dSt = Math.max(-9, Math.min(9, wiatr.dSt * 0.8 + los(6)));
  wiatr.dKmh = Math.max(-2.5, Math.min(2.5, wiatr.dKmh * 0.75 + los(1.8)));
  rysujKompas();
}

async function zaladujImgw() {
  const chip = $("#chip-imgw");
  try {
    const { imgw } = await pobierz("/api/pogoda");
    if (!imgw) throw new Error();
    chip.classList.remove("wyszarzony");
    chip.innerHTML = `<small>IMGW</small><b>${esc(imgw.stacja)} ${imgw.temperatura_c.toFixed(1)}°C · ${imgw.wiatr_kmh} km/h</b>`;
    ustawKompas(imgw.kierunek_wiatru_st, imgw.wiatr_kmh);
    chip.title = `Pogoda bieżąca IMGW-PIB (${imgw.pomiar}): wilgotność ${imgw.wilgotnosc_proc}%, ciśnienie ${imgw.cisnienie_hpa} hPa, opad ${imgw.opad_mm} mm`;
  } catch {
    chip.classList.add("wyszarzony");
    chip.innerHTML = "<small>IMGW</small><b>offline</b>";
    chip.title = "API IMGW niedostępne — demo działa na pogodzie scenariusza";
  }
}

// ====================================================================== STEROWANIE

function podlaczSterowanie() {
  $$("#seg-scenariusz button").forEach((b) => b.addEventListener("click", () => post(`/api/sym/scenariusz/${b.dataset.scen}`)));
  $("#btn-restart").addEventListener("click", () => post(`/api/sym/scenariusz/${ui.stan?.scenariusz.id || "patrol"}`));
  $("#btn-pauza").addEventListener("click", () => post("/api/sym/pauza"));
  $$("#seg-predkosc button").forEach((b) => b.addEventListener("click", () => post(`/api/sym/predkosc/${b.dataset.x}`)));

  $("#btn-dzwiek").innerHTML = IKONY.GLOSNIK_OFF;
  $("#btn-dzwiek").addEventListener("click", () => {
    ui.dzwiek = !ui.dzwiek;
    $("#btn-dzwiek").innerHTML = ui.dzwiek ? IKONY.GLOSNIK_ON : IKONY.GLOSNIK_OFF;
    $("#btn-dzwiek").classList.toggle("wlaczony", ui.dzwiek);
    if (ui.dzwiek) powiedz("Komunikaty głosowe włączone.");
    else if ("speechSynthesis" in window) speechSynthesis.cancel();
  });

  $$(".zakladki button").forEach((b) => b.addEventListener("click", () => przelaczZakladke(b.dataset.tab)));
  $$("#filtry button").forEach((b) => b.addEventListener("click", () => {
    $$("#filtry button").forEach((x) => x.classList.toggle("aktywny", x === b));
    $("#feed").dataset.filtr = b.dataset.f;
  }));
  $$("#seg-warstwy button").forEach((b) => b.addEventListener("click", () => {
    $$("#seg-warstwy button").forEach((x) => x.classList.toggle("aktywny", x === b));
    $$(".warstwy-lista").forEach((l) => { l.hidden = l.dataset.grupa !== b.dataset.grupa; });
  }));

  const obsluzKlikZgloszenia = async (e) => {
    const kop = e.target.closest("[data-kopiuj]");
    if (kop) {
      try { await navigator.clipboard.writeText(kop.dataset.kopiuj); kop.textContent = "skopiowano"; } catch { kop.textContent = kop.dataset.kopiuj; }
      return true;
    }
    if (e.target.closest("a")) return true;
    const dec = e.target.closest("[data-decyzja]");
    if (dec) { await podejmijDecyzje(dec); return true; }
    return false;
  };
  const listaInc = $("#lista-inc");
  listaInc.addEventListener("click", async (e) => {
    if (await obsluzKlikZgloszenia(e)) return;
    const karta = e.target.closest(".inc");
    if (karta) {
      const i = ui.incDane.find((x) => x.id === +karta.dataset.id);
      if (i) M.mapa.flyTo([i.lat, i.lon], 16, { duration: 0.8 });
    }
  });
  $("#lista-stacji").addEventListener("click", async (e) => {
    const b = e.target.closest("[data-stacja]");
    if (!b) return;
    b.disabled = true;
    try { await post(`/api/sym/stacja/${b.dataset.stacja}`); } catch { /* stacja nieznana */ }
  });
  listaInc.addEventListener("mouseover", (e) => {
    const karta = e.target.closest(".inc");
    if (karta && +karta.dataset.id !== ui.incPodswietlony) podswietlIncydent(ui.incDane.find((x) => x.id === +karta.dataset.id));
  });
  listaInc.addEventListener("mouseleave", () => podswietlIncydent(null));

  $("#lista-flota").addEventListener("click", async (e) => {
    const b = e.target.closest("button");
    if (!b) return;
    b.disabled = true;
    try {
      if (b.dataset.wezel) await post(`/api/sym/wezel/${b.dataset.wezel}`);
      else if (b.classList.contains("glos")) await post(`/api/glos/${b.dataset.id}`);
    } catch (err) { toast({ status: "INFO", opis: err.message }, "INFO"); }
    setTimeout(() => { b.disabled = false; }, 600);
  });

  $("#btn-wyczysc").addEventListener("click", async () => { await post("/api/analiza/wyczysc"); odswiezAnalize(); });

  $$("#seg-anon button").forEach((b) => b.addEventListener("click", () => {
    $$("#seg-anon button").forEach((x) => x.classList.toggle("aktywny", x === b));
    ui.trybAnon = b.dataset.tryb;
    zaladujAnonimizacje();
  }));
  const suwak = $("#suwak");
  suwak.addEventListener("input", () => $("#porownanie").style.setProperty("--p", `${suwak.value}%`));

  // nakladka z nazwami ulic tylko nad ortofotomapa - OSM i Ciemna maja je w samych kaflach (bez dublowania napisow)
  const ustawUlice = () => {
    const pokaz = $("#w-ulice").checked && M.baza === "orto";
    if (pokaz && !M.mapa.hasLayer(M.ulice)) M.ulice.addTo(M.mapa);
    if (!pokaz && M.mapa.hasLayer(M.ulice)) M.ulice.remove();
  };
  $$('input[name="baza"]').forEach((r) => r.addEventListener("change", () => {
    Object.entries(M.bazowe).forEach(([k, w]) => { if (k === r.value) w.addTo(M.mapa); else w.remove(); });
    M.bazowe[r.value].bringToBack();
    M.baza = r.value;
    ustawUlice();
  }));
  $("#w-ulice").addEventListener("change", ustawUlice);
  const przelacz = (id, warstwa) => $(id).addEventListener("change", (e) => {
    const w = warstwa();
    if (w) e.target.checked ? w.addTo(M.mapa) : w.remove();
  });
  przelacz("#w-prg", () => M.prg);
  przelacz("#w-schrony", () => M.schrony);
  przelacz("#w-regiony", () => M.regiony);
  przelacz("#w-zasieg", () => M.zasiegi);
  przelacz("#w-strefy", () => M.strefy);
  przelacz("#w-budynki", () => M.budynki);
  $("#w-sektory").addEventListener("change", (e) => {
    Object.values(M.sektory).concat(M.etykiety).forEach((w) => (e.target.checked ? w.addTo(M.mapa) : w.remove()));
  });
  $("#w-mesh").addEventListener("change", () => ui.stan && aktualizujMesh(ui.stan.linki));
  $("#w-scen").addEventListener("change", () => ui.stan && aktualizujWarstwyScenariusza(ui.stan.scenariusz.warstwy));

  document.addEventListener("keydown", (e) => {
    if (e.target.matches("input, textarea") || e.metaKey || e.ctrlKey || e.altKey) return;
    if (e.code === "Space") { e.preventDefault(); post("/api/sym/pauza"); }
    const scen = { Digit1: "patrol", Digit2: "powodz", Digit3: "pozar", Digit4: "alarm", Digit5: "cwiczenia" }[e.code];
    if (scen) post(`/api/sym/scenariusz/${scen}`);
  });
}

// ====================================================================== START

window.addEventListener("DOMContentLoaded", async () => {
  ustawPolaczenie("off");
  inicjalizujMape();
  inicjalizujWykres();
  zbudujKompas();
  podlaczSterowanie();
  for (;;) {
    try {
      zbudujWarstwyStatyczne(await pobierz("/api/warstwy"));
      break;
    } catch {
      ustawPolaczenie("off");
      await new Promise((r) => setTimeout(r, 2000));
    }
  }
  polaczWS();
  const zHasha = location.hash.slice(1);
  if ($(`#tab-${zHasha}`)) przelaczZakladke(zHasha);
  zaladujSchrony().catch(() => { $("#schrony-opis").textContent = "Brak snapshotu schronów — uruchom: python data_sources.py --odswiez-schrony"; });
  zaladujZrodla().catch(() => {});
  zaladujImgw();
  setInterval(zaladujImgw, 10 * 60 * 1000);
  setInterval(drganieKompasu, 1600);
  setInterval(() => { if (ui.zakladka === "rodo" && !document.hidden) zaladujAnonimizacje(true); }, ANON_ZMIANA_MS);
});
