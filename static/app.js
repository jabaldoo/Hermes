// app.js — konsola CZK systemu HERMES.
// Stan przychodzi z backendu przez WebSocket (/ws); gdy WS niedostepny — automatyczny fallback na polling HTTP.
"use strict";

const CFG = document.body.dataset;
const STATUSY = ["OK", "LUDZIE", "ZATOR", "POMOC"];
const KOLOR = {
  OK: "#2fd98f", LUDZIE: "#ffd23f", ZATOR: "#ff8a3d", POMOC: "#ff4d63",
  ALERT: "#ff4d63", INFO: "#7aa2ff", KOMUNIKAT: "#f5c451", MESH: "#45e3ff", DZIALANIE: "#b18cff",
};
const NAZWA_STATUSU = { OK: "OK", LUDZIE: "LUDZIE", ZATOR: "ZATOR", POMOC: "POMOC", ALERT: "ALERT",
  INFO: "INFO", KOMUNIKAT: "KOMUNIKAT", MESH: "MESH", DZIALANIE: "DZIAŁANIE" };
const KATEGORIA = { OK: "wykrycia", LUDZIE: "wykrycia", ZATOR: "wykrycia", POMOC: "wykrycia",
  DZIALANIE: "dzialania", KOMUNIKAT: "dzialania", MESH: "mesh", ALERT: "system", INFO: "system" };

const svg = (d) => `<svg viewBox="0 0 24 24" aria-hidden="true">${d}</svg>`;
const IKONY = {
  LUDZIE: svg('<circle cx="9" cy="7" r="3.2"/><path d="M2.5 20c0-3.6 2.9-6.5 6.5-6.5s6.5 2.9 6.5 6.5z"/><circle cx="17" cy="8" r="2.6"/><path d="M15.8 13.6c3.3-.3 5.7 2.3 5.7 6.4h-4.2c0-2.5-.5-4.6-1.5-6.4z"/>'),
  ZATOR: svg('<path d="M5 11l1.6-4.2A2 2 0 0 1 8.5 5.5h7a2 2 0 0 1 1.9 1.3L19 11h1a1 1 0 0 1 1 1v5h-2v2h-3v-2H8v2H5v-2H3v-5a1 1 0 0 1 1-1zm2.2 0h9.6l-1.1-3.2H8.3zM7 15.2a1.3 1.3 0 1 0 0-2.6 1.3 1.3 0 0 0 0 2.6zm10 0a1.3 1.3 0 1 0 0-2.6 1.3 1.3 0 0 0 0 2.6z"/>'),
  POMOC: svg('<path d="M9 3h6v6h6v6h-6v6H9v-6H3V9h6z"/>'),
  OK: svg('<path d="M9.5 16.2 5.3 12l-1.4 1.4 5.6 5.6L20.1 8.4 18.7 7z"/>'),
  ALERT: svg('<path fill-rule="evenodd" d="M12 2 1 21h22zm0 5 7.5 12.5h-15zM11 10h2v5h-2zm0 6.5h2v2h-2z"/>'),
  INFO: svg('<path d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zm1 15h-2v-6h2zm0-8h-2V7h2z"/>'),
  KOMUNIKAT: svg('<path d="M3 9v6h4l5 4V5L7 9zm13.5 3a4.5 4.5 0 0 0-2.5-4v8a4.5 4.5 0 0 0 2.5-4zM14 3.2v2.1a7 7 0 0 1 0 13.4v2.1a9 9 0 0 0 0-17.6z"/>'),
  MESH: svg('<circle cx="12" cy="5" r="2.6"/><circle cx="5" cy="18" r="2.6"/><circle cx="19" cy="18" r="2.6"/><path d="M11.2 7.3 5.9 15.6l1.3.8 5.3-8.3zm1.6 0-1.3.8 5.3 8.3 1.3-.8zM7.6 17.3h8.8v1.5H7.6z"/>'),
  DZIALANIE: svg('<path d="M2 7h12v8h1.2l2.3-4.5H21a1 1 0 0 1 1 1V17h-1.4a2.6 2.6 0 0 1-5 0H9.4a2.6 2.6 0 0 1-5 0H2zm2.5 2v2.5h3V9zm5 0v2.5h3V9zM7 18.2a1.2 1.2 0 1 0 0-2.4 1.2 1.2 0 0 0 0 2.4zm11 0a1.2 1.2 0 1 0 0-2.4 1.2 1.2 0 0 0 0 2.4z"/>'),
  SCHRON: svg('<path d="M12 2 4 5v6c0 5 3.4 9.5 8 11 4.6-1.5 8-6 8-11V5zm0 4.2 4 1.5V11c0 3-1.7 5.8-4 7z"/>'),
  DESZCZ: svg('<path d="M17.5 8.5a5.5 5.5 0 0 0-10.7-1A4.5 4.5 0 0 0 7 16.5h10.5a4 4 0 0 0 0-8zM8 18l-1.2 3h1.6L9.6 18zm4 0-1.2 3h1.6l1.2-3zm4 0-1.2 3h1.6l1.2-3z"/>'),
  SLONCE: svg('<circle cx="12" cy="12" r="4.5"/><path d="M11 1h2v4h-2zm0 18h2v4h-2zM1 11h4v2H1zm18 0h4v2h-4zM4.2 5.6l1.4-1.4 2.8 2.8L7 8.4zm11.4 11.4 1.4-1.4 2.8 2.8-1.4 1.4zM4.2 18.4l2.8-2.8 1.4 1.4-2.8 2.8zM15.6 7l2.8-2.8 1.4 1.4L17 8.4z"/>'),
  CHMURA: svg('<path d="M17.5 9.5a5.5 5.5 0 0 0-10.7-1A4.5 4.5 0 0 0 7 17.5h10.5a4 4 0 0 0 0-8z"/>'),
  PAUZA: svg('<path d="M7 5h3.5v14H7zm6.5 0H17v14h-3.5z"/>'),
  START: svg('<path d="M7 4.5v15l12.5-7.5z"/>'),
  GLOSNIK_ON: svg('<path d="M3 9v6h4l5 4V5L7 9zm13.5 3a4.5 4.5 0 0 0-2.5-4v8a4.5 4.5 0 0 0 2.5-4zM14 3.2v2.1a7 7 0 0 1 0 13.4v2.1a9 9 0 0 0 0-17.6z"/>'),
  GLOSNIK_OFF: svg('<path d="M3 9v6h4l5 4V5L7 9zm13.6 3 2.7-2.7-1.3-1.3-2.7 2.7-2.7-2.7-1.3 1.3 2.7 2.7-2.7 2.7 1.3 1.3 2.7-2.7 2.7 2.7 1.3-1.3z"/>'),
};

const DRON_SVG = `<svg class="dron-svg" viewBox="-18 -18 36 36" aria-hidden="true">
  <g stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><line x1="-9" y1="-9" x2="9" y2="9"/><line x1="9" y1="-9" x2="-9" y2="9"/></g>
  <g fill="none" stroke="currentColor" stroke-width="1.5">
    <circle class="rotor" cx="-9" cy="-9" r="5.2" stroke-dasharray="6 3"/><circle class="rotor" cx="9" cy="-9" r="5.2" stroke-dasharray="6 3"/>
    <circle class="rotor" cx="-9" cy="9" r="5.2" stroke-dasharray="6 3"/><circle class="rotor" cx="9" cy="9" r="5.2" stroke-dasharray="6 3"/>
  </g>
  <rect x="-4" y="-5.5" width="8" height="11" rx="2.6" fill="currentColor"/>
  <path d="M0-15.5 3.4-10H-3.4z" fill="currentColor"/>
</svg>`;

const ui = {
  stan: null, ids: new Set(), dzwiek: false, zakladka: "zdarzenia", sygSektorow: "", sygKrokow: "",
  sygStat: "", trybAnon: "blur", polaczenie: "off", ws: null, polling: null, ostatnieId: 0,
};

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const tplus = (s) => { s = Math.max(0, s | 0); return `T+${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`; };
const pseudo = (n) => { const x = Math.sin(n * 12.9898) * 43758.5453; return x - Math.floor(x); };

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

// ====================================================================== MAPA

const M = { mapa: null, bazowe: {}, prg: null, sektory: {}, def: {}, etykiety: [], odznaki: {}, drony: {},
  mesh: [], heat: null, schrony: null, podswietlenie: null, scen: {}, jednostkiStale: null, akcje: {}, bazaZn: null };

function inicjalizujMape() {
  const mapa = L.map("mapa", { zoomControl: false, zoomSnap: 0.25, attributionControl: true });
  M.mapa = mapa;
  L.control.zoom({ position: "topleft" }).addTo(mapa);
  [["pScen", 360], ["pSektory", 380], ["pMesh", 430], ["pSchrony", 440], ["pEtykiety", 460], ["pJednostki", 640]]
    .forEach(([n, z]) => { mapa.createPane(n).style.zIndex = z; });

  M.bazowe = {
    orto: L.tileLayer(CFG.ortoWmts, { maxZoom: 19, className: "warstwa-orto",
      attribution: 'Ortofotomapa © <a href="https://www.geoportal.gov.pl">GUGiK</a>' }),
    ciemna: L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
      { maxZoom: 19, subdomains: "abcd", attribution: "© OpenStreetMap © CARTO" }),
    osm: L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png",
      { maxZoom: 19, className: "warstwa-osm", attribution: "© OpenStreetMap" }),
  };
  M.bazowe.orto.addTo(mapa);
  M.prg = L.tileLayer.wms(CFG.prgWms, { layers: "A03_Granice_gmin", format: "image/png", transparent: true,
    version: "1.3.0", className: "warstwa-prg", attribution: "PRG © GUGiK" });

  mapa.on("zoomstart", () => mapa.getContainer().classList.add("bez-animacji"));
  mapa.on("zoomend", () => setTimeout(() => mapa.getContainer().classList.remove("bez-animacji"), 50));
  M.podswietlenie = L.layerGroup().addTo(mapa);
}

function dopasujWidok() {
  const b = L.latLngBounds(Object.values(M.def).flatMap((s) => [[s.lat_min, s.lon_min], [s.lat_max, s.lon_max]]));
  const waski = innerWidth <= 1020;
  const lewa = waski ? 20 : parseInt(getComputedStyle(document.documentElement).getPropertyValue("--lewa-w")) + 40;
  const prawa = waski ? 20 : parseInt(getComputedStyle(document.documentElement).getPropertyValue("--prawa-w")) + 40;
  M.mapa.fitBounds(b, { paddingTopLeft: [lewa, waski ? 130 : 90], paddingBottomRight: [prawa, waski ? innerHeight * 0.48 : 110] });
}

function zbudujWarstwyStatyczne(w) {
  w.sektory.forEach((s) => { M.def[s.id] = s; });
  dopasujWidok();

  w.sektory.forEach((s) => {
    const r = L.rectangle([[s.lat_min, s.lon_min], [s.lat_max, s.lon_max]], { pane: "pSektory", weight: 0.8,
      color: "rgba(220,235,255,0.35)", fillColor: "#9fb4d8", fillOpacity: 0.03 }).addTo(M.mapa);
    r.bindPopup(() => popupSektora(s.id));
    M.sektory[s.id] = r;
    M.etykiety.push(L.marker([s.lat_max, s.lon_min], { pane: "pEtykiety", interactive: false,
      icon: L.divIcon({ className: "etykieta-sektora", html: `<span>${s.id}</span>`, iconSize: null, iconAnchor: [-5, -4] }) }).addTo(M.mapa));
  });

  const scen = M.scen;
  scen.odra = L.polyline(w.odra, { pane: "pScen", color: "#5aa9ff", weight: 5, opacity: 0.85, lineCap: "round" });
  scen.strefa_zalewowa = L.polygon(w.strefa_zalewowa, { pane: "pScen", color: "#5aa9ff", weight: 1, dashArray: "4 5",
    fillColor: "#3b82f6", fillOpacity: 0.2 }).bindTooltip("Strefa zalewowa (hydrografia — mock)", { sticky: true });
  scen.las = L.polygon(w.las, { pane: "pScen", color: "#22c55e", weight: 1.2, fillColor: "#16a34a", fillOpacity: 0.22 })
    .bindTooltip("Las Osobowicki — obszar BDL (mock)", { sticky: true });
  scen.ogniska = L.layerGroup(w.ogniska.map((p) => L.circle(p, { pane: "pScen", radius: 320, color: "#ff5a36",
    weight: 1.5, fillColor: "#ff5a36", fillOpacity: 0.35, className: "ognisko" })));

  M.bazaZn = L.marker([w.baza.lat, w.baza.lon], { zIndexOffset: 500, icon: L.divIcon({ className: "", iconSize: [0, 0],
    html: `<div class="baza-czk"><svg viewBox="0 0 24 24"><path d="M12 2 21 7v10l-9 5-9-5V7z" fill="#05080f" stroke="#45e3ff" stroke-width="1.6"/><path d="M12 7.5v8m-3.5-6a5 5 0 0 1 7 0m-9-2a8 8 0 0 1 11 0" stroke="#45e3ff" stroke-width="1.5" fill="none" stroke-linecap="round"/></svg><span>CZK</span></div>` }) })
    .bindPopup(`<div class="popup-tytul">${esc(w.baza.nazwa)}</div><div class="popup-meta">Węzeł główny sieci mesh</div>`).addTo(M.mapa);

  M.jednostkiStale = L.layerGroup(w.jednostki.map((j) => L.marker([j.lat, j.lon], { pane: "pEtykiety", interactive: false,
    icon: L.divIcon({ className: "", iconSize: [0, 0], html: `<div class="jednostka-stala">${esc(j.typ)}</div>` }) }))).addTo(M.mapa);

  if (L.heatLayer) {
    M.heat = L.heatLayer([], { radius: 38, blur: 30, maxZoom: 14, minOpacity: 0.25,
      gradient: { 0.2: "#1e3a8a", 0.45: "#45e3ff", 0.65: "#ffd23f", 0.85: "#ff8a3d", 1: "#ff4d63" } }).addTo(M.mapa);
  }
}

function popupSektora(id) {
  const d = M.def[id];
  const s = ui.stan?.sektory.find((x) => x.id === id) || { status: "OK", osoby: 0 };
  return `<div class="popup-tytul">Sektor ${id} · <span style="color:${KOLOR[s.status]}">${s.status}</span></div>
    <div>Osoby wykryte: <b>${s.osoby}</b>${s.w_realizacji ? " · <b style='color:#b18cff'>działania w toku</b>" : ""}</div>
    <div class="popup-meta">szac. ludność ${d.ludnosc_szac} · NMT ${d.wysokosc_npm_m ?? "—"} m n.p.m. (mock)</div>`;
}

async function zaladujSchrony() {
  const dane = await pobierz("/api/schrony");
  const renderer = L.canvas({ pane: "pSchrony", padding: 0.3 });
  M.schrony = L.layerGroup(dane.punkty.map((p) => {
    const h24 = p.dostepnosc === "Całodobowa";
    return L.circleMarker([p.lat, p.lon], { renderer, radius: h24 ? 3.4 : 2.6, stroke: h24, color: "#bbf7d0", weight: 1,
      fillColor: "#34d399", fillOpacity: h24 ? 0.95 : 0.6 })
      .bindPopup(`<div class="popup-tytul">Miejsce schronienia</div><div>${esc(p.adres)}</div>
        <div>Dostępność: <b>${esc(p.dostepnosc)}</b></div><div class="popup-meta">${esc(p.id)} · KG PSP / dane.gov.pl</div>`);
  }));
  if ($("#w-schrony").checked) M.schrony.addTo(M.mapa);
  $("#liczba-schronow").textContent = dane.punkty.length;
  $("#schrony-opis").innerHTML = `Na mapie <b>${dane.punkty.length}</b> punktów schronienia z obszaru demo — oficjalny zbiór
    KG PSP „Punkty schronienia w Polsce” (dane.gov.pl, CC BY 4.0, aktualizacja co tydzień${dane.pobrano ? `, pobrano ${esc(dane.pobrano)}` : ""}).
    CZK wskazuje najbliższe schrony w rekomendacjach, a drony podają adres w komunikatach głosowych.`;
}

// ---------------------------------------------------------------- aktualizacje mapy

function aktualizujSektory(lista) {
  const syg = lista.map((s) => `${s.id}${s.status}${s.osoby}${s.w_realizacji ? 1 : 0}`).join();
  if (syg === ui.sygSektorow) return false;
  ui.sygSektorow = syg;
  const widoczne = $("#w-sektory").checked;
  lista.forEach((s) => {
    const r = M.sektory[s.id];
    const alarm = s.status !== "OK";
    r.setStyle({ color: alarm ? KOLOR[s.status] : "rgba(220,235,255,0.35)", weight: alarm ? 1.6 : 0.8,
      fillColor: alarm ? KOLOR[s.status] : "#9fb4d8", fillOpacity: alarm ? 0.2 : 0.03, dashArray: s.w_realizacji ? "7 4" : null });
    r.getElement()?.classList.toggle("sektor-realizacja", s.w_realizacji);
    ustawOdznake(s, widoczne);
  });
  aktualizujHeat(lista);
  return true;
}

function ustawOdznake(s, widoczne) {
  let m = M.odznaki[s.id];
  if (s.status === "OK" || !widoczne) {
    if (m) { m.remove(); delete M.odznaki[s.id]; }
    return;
  }
  const html = `<div class="odznaka st-${s.status}${s.w_realizacji ? " w-realizacji" : ""}">${IKONY[s.status]}${s.osoby ? `<b>${s.osoby}</b>` : ""}</div>`;
  if (!m) {
    const d = M.def[s.id];
    m = L.marker([d.lat_centrum, d.lon_centrum], { pane: "pEtykiety", icon: L.divIcon({ className: "", iconSize: [0, 0], html }) }).addTo(M.mapa);
    m.on("click", () => M.sektory[s.id].openPopup([d.lat_centrum, d.lon_centrum]));
    M.odznaki[s.id] = m;
  } else if (m.getElement() && m.getElement().innerHTML !== html) {
    m.getElement().innerHTML = html;
  }
}

function aktualizujHeat(lista) {
  if (!M.heat) return;
  const pkt = [];
  if ($("#w-heat").checked) {
    lista.forEach((s, idx) => {
      if (s.status === "OK") return;
      const d = M.def[s.id];
      const inten = s.status === "ZATOR" ? 0.35 : Math.min(1, 0.35 + s.osoby / 14);
      const n = s.status === "ZATOR" ? 3 : 4 + Math.min(10, s.osoby);
      for (let i = 0; i < n; i++) {
        const a = pseudo(idx * 31 + i) * Math.PI * 2, r = 0.15 + pseudo(idx * 17 + i * 7) * 0.6;
        pkt.push([d.lat_centrum + Math.sin(a) * r * 0.009, d.lon_centrum + Math.cos(a) * r * 0.015, inten]);
      }
    });
  }
  M.heat.setLatLngs(pkt);
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
      (d.faza === "rtb" || d.faza === "ladowanie") && "rtb"].filter(Boolean).join(" ");
    el.querySelector(".dron-svg").style.transform = `rotate(${d.kurs}deg)`;
    el.querySelector(".dron-etykieta").innerHTML = d.zywy
      ? `${d.id} · ${Math.round(d.bateria)}%${d.bufor ? ` · <em>BUF ${d.bufor}</em>` : d.hops === null ? " · <em>OFFLINE</em>" : ""}`
      : `${d.id} · UTRACONY`;
  });
}

function aktualizujMesh(linki) {
  const widoczne = $("#w-mesh").checked;
  while (M.mesh.length < linki.length) {
    M.mesh.push(L.polyline([[0, 0], [0, 0]], { pane: "pMesh", className: "mesh-link", color: "#45e3ff", interactive: false }));
  }
  M.mesh.forEach((l, i) => {
    const k = linki[i];
    if (!k || !widoczne) { if (M.mapa.hasLayer(l)) l.remove(); return; }
    l.setLatLngs([k.a, k.b]);
    l.setStyle({ weight: 1.6 + 2.4 * k.jakosc, opacity: 0.55 + 0.45 * k.jakosc });
    if (!M.mapa.hasLayer(l)) l.addTo(M.mapa);
  });
}

function aktualizujWarstwyScenariusza(warstwy) {
  const pokaz = $("#w-scen").checked;
  Object.entries(M.scen).forEach(([k, warstwa]) => {
    const ma = pokaz && warstwy.includes(k);
    if (ma && !M.mapa.hasLayer(warstwa)) warstwa.addTo(M.mapa);
    if (!ma && M.mapa.hasLayer(warstwa)) warstwa.remove();
  });
}

function podswietlRekomendacje(r) {
  M.podswietlenie.clearLayers();
  if (!r) return;
  const d = M.def[r.sektor];
  L.rectangle([[d.lat_min, d.lon_min], [d.lat_max, d.lon_max]], { pane: "pMesh", color: "#fff", weight: 2.5, fill: false, interactive: false }).addTo(M.podswietlenie);
  r.schrony.forEach((p, i) => {
    L.polyline([r.centrum, [p.lat, p.lon]], { pane: "pMesh", color: "#34d399", weight: 2, dashArray: "2 6", className: "trasa-ewak", interactive: false }).addTo(M.podswietlenie);
    L.circleMarker([p.lat, p.lon], { pane: "pMesh", radius: i === 0 ? 9 : 7, color: "#34d399", weight: 2.5, fillColor: "#05080f", fillOpacity: 0.7, interactive: false }).addTo(M.podswietlenie);
  });
}

function animujDzialanie(z) {
  usunDzialanie(z.sektor, true);
  const grupa = L.layerGroup().addTo(M.mapa);
  M.akcje[z.sektor] = grupa;
  const d = M.def[z.sektor];
  const cel = [d.lat_centrum, d.lon_centrum];
  if (z.schron) {
    L.polyline([cel, z.schron], { pane: "pMesh", color: "#34d399", weight: 2.5, dashArray: "2 7", className: "trasa-ewak", interactive: false }).addTo(grupa);
    L.circleMarker(z.schron, { pane: "pMesh", radius: 9, color: "#34d399", weight: 2.5, fillColor: "#05080f", fillOpacity: 0.7 })
      .bindTooltip("Punkt ewakuacji (schron KG PSP)").addTo(grupa);
  }
  const czas = Math.max(3000, (z.czas_real_s || 8) * 1000 * 0.7);
  (z.trasy || []).forEach((t, i) => {
    const doPkt = [t.do[0] + (i - 0.5) * 0.0016, t.do[1] + (i - 0.5) * 0.0024];
    L.polyline([t.z, doPkt], { pane: "pMesh", color: "#b18cff", weight: 1.5, opacity: 0.55, dashArray: "4 6", interactive: false }).addTo(grupa);
    const m = L.marker(t.z, { pane: "pJednostki", interactive: false,
      icon: L.divIcon({ className: "", iconSize: [0, 0], html: `<div class="jednostka j-${esc(t.typ)}">${esc(t.typ)}</div>` }) }).addTo(grupa);
    const start = performance.now() + i * 300;
    const krok = (teraz) => {
      if (M.akcje[z.sektor] !== grupa) return;
      const p = Math.min(1, Math.max(0, (teraz - start) / czas));
      const e = p < 0.5 ? 2 * p * p : 1 - Math.pow(-2 * p + 2, 2) / 2;
      m.setLatLng([t.z[0] + (doPkt[0] - t.z[0]) * e, t.z[1] + (doPkt[1] - t.z[1]) * e]);
      if (p < 1) requestAnimationFrame(krok);
    };
    requestAnimationFrame(krok);
  });
}

function usunDzialanie(sektor, natychmiast = false) {
  const g = M.akcje[sektor];
  if (!g) return;
  delete M.akcje[sektor];
  setTimeout(() => g.remove(), natychmiast ? 0 : 2500);
}

function wyczyscDzialania() {
  Object.keys(M.akcje).forEach((s) => usunDzialanie(s, true));
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

  renderujMisje(s.scenariusz);
  renderujPogode(s.pogoda);
  const zmianaSektorow = aktualizujSektory(s.sektory);
  aktualizujDrony(s.drony);
  aktualizujMesh(s.linki);
  aktualizujWarstwyScenariusza(s.scenariusz.warstwy);
  renderujStatystyki(s);
  renderujFlote(s.drony);

  const oczekujace = s.sektory.filter((x) => x.status !== "OK" && !x.w_realizacji).length;
  const licznik = $("#licznik-decyzji");
  licznik.hidden = oczekujace === 0;
  licznik.textContent = oczekujace;
  if (zmianaSektorow && ui.zakladka === "decyzje" && ui.rekWyswietlone) odswiezRekomendacje(false);
}

function renderujMisje(sc) {
  const syg = sc.id + sc.kroki.map((k) => k.stan).join();
  if (syg === ui.sygKrokow) return;
  ui.sygKrokow = syg;
  $("#misja-tag").textContent = sc.id === "patrol" ? "PATROL" : "SCENARIUSZ";
  $("#misja-nazwa").textContent = sc.nazwa;
  $("#misja-opis").textContent = sc.opis;
  $("#misja-kroki").innerHTML = sc.kroki.length
    ? sc.kroki.map((k) => `<li class="${k.stan.replace(" ", "-")} ${k.typ}"><time>${tplus(k.t)}</time>${esc(k.opis)}</li>`).join("")
    : `<li class="w-toku">Rój w trybie patrolu — wykrycia losowe (ważone). Wybierz scenariusz u góry, aby odtworzyć sytuację kryzysową.</li>`;
}

function renderujPogode(p) {
  const ik = p.opad_mm_h > 0 ? IKONY.DESZCZ : p.temperatura_c >= 28 ? IKONY.SLONCE : IKONY.CHMURA;
  const html = `${ik}<small>SCEN.</small>${p.temperatura_c.toFixed(1)}°C · ${p.wiatr_kmh} km/h${p.opad_mm_h > 0 ? ` · ${p.opad_mm_h} mm/h` : ` · RH ${p.wilgotnosc_proc}%`}`;
  const chip = $("#chip-pogoda");
  if (chip.innerHTML !== html) chip.innerHTML = html;
  chip.title = `Pogoda w scenariuszu (symulowana): ${p.opis}`;
}

let wykres;
function inicjalizujWykres() {
  if (typeof Chart === "undefined") return; // brak CDN nie moze zatrzymac reszty konsoli
  wykres = new Chart($("#wykres"), {
    type: "doughnut",
    data: { labels: STATUSY, datasets: [{ data: [25, 0, 0, 0], backgroundColor: STATUSY.map((s) => KOLOR[s]), borderWidth: 0, spacing: 2, borderRadius: 3 }] },
    options: { cutout: "74%", responsive: false, animation: { duration: 500 }, plugins: { legend: { display: false }, tooltip: { enabled: true } } },
  });
}

function renderujStatystyki(s) {
  const syg = JSON.stringify([s.licznik, s.statystyki]);
  if (syg === ui.sygStat) return;
  ui.sygStat = syg;
  if (wykres) {
    wykres.data.datasets[0].data = STATUSY.map((k) => s.licznik[k]);
    wykres.update();
  }
  $("#kpi-zagrozone").textContent = 25 - s.licznik.OK;
  $("#legenda-statusow").innerHTML = STATUSY.map((k) =>
    `<li style="color:${KOLOR[k]}">${IKONY[k]}<span style="color:var(--text)">${k}</span><b>${s.licznik[k]}</b></li>`).join("");
  $("#kpi-osoby").textContent = s.statystyki.osoby;
  $("#kpi-twarze").textContent = s.statystyki.twarze;
  $("#kpi-realizacja").textContent = s.statystyki.w_realizacji;
  $("#kpi-mesh").textContent = `${s.statystyki.wezly}/${s.statystyki.wezly_razem}`;
}

// ====================================================================== ZDARZENIA

function obsluzZdarzenie(z, cicho = false) {
  if (ui.ids.has(z.id)) return;
  ui.ids.add(z.id);
  ui.ostatnieId = Math.max(ui.ostatnieId, z.id);
  dodajDoFeedu(z, cicho);

  if (z.status === "OK" && z.sektor && !z.dron_id) usunDzialanie(z.sektor);
  if (cicho) {
    if (z.dron_id && STATUSY.includes(z.status)) ustawPakiet(z, false);
    return;
  }
  if (z.status === "DZIALANIE" && z.sektor) animujDzialanie(z);

  if (z.status === "ALERT" || z.status === "INFO") swiecPetle([0]);
  else if (STATUSY.includes(z.status) && z.dron_id) { swiecPetle([1, 2, 3, 4, 5]); ustawPakiet(z, true); }
  else if (z.status === "KOMUNIKAT") swiecPetle([7]);
  else if (z.status === "DZIALANIE") swiecPetle([6, 7]);
  else if (z.status === "OK") swiecPetle([7]);

  if (z.status === "ALERT") toast(z, "ALERT");
  if (z.status === "POMOC") toast(z, `POMOC · ${z.sektor}`);
  if (z.status === "MESH" && /Utrata|brak łączności/.test(z.opis)) toast(z, "MESH");
  if (z.glos) powiedz(z.glos);
  if (ui.dzwiek && (z.status === "ALERT" || z.status === "POMOC")) sygnal();
}

function dodajDoFeedu(z, cicho) {
  const li = document.createElement("li");
  li.className = `ev k-${z.status}${cicho ? "" : " nowe"}${z.sektor ? " klikalne" : ""}`;
  li.dataset.kat = KATEGORIA[z.status] || "system";
  const dron = z.dron_id && ui.stan?.drony.find((d) => d.id === z.dron_id);
  const meta = [
    dron ? `<span>${esc(dron.nazwa)}</span>` : z.dron_id ? `<span>${esc(z.dron_id)}</span>` : "<span>CZK</span>",
    z.liczba_osob ? `<span>${z.liczba_osob} os.</span>` : "",
    STATUSY.includes(z.status) && z.dron_id ? `<span>pewność ${Math.round(z.pewnosc * 100)}%</span>` : "",
  ].join("");
  li.innerHTML = `<div class="ev-ikona">${IKONY[z.status] || IKONY.INFO}</div>
    <div><div class="ev-gora"><span class="ev-tytul">${NAZWA_STATUSU[z.status] || esc(z.status)}${z.sektor ? ` · ${esc(z.sektor)}` : ""}</span>
    <span class="ev-czas">${tplus(z.t_sym)}</span></div><div class="ev-opis">${esc(z.opis)}</div><div class="ev-meta">${meta}</div></div>`;
  if (z.sektor && M.def[z.sektor]) {
    li.addEventListener("click", () => {
      const d = M.def[z.sektor];
      M.mapa.flyTo([d.lat_centrum, d.lon_centrum], 14, { duration: 0.8 });
      setTimeout(() => M.sektory[z.sektor].openPopup([d.lat_centrum, d.lon_centrum]), 850);
    });
  }
  const feed = $("#feed");
  feed.prepend(li);
  while (feed.children.length > 150) feed.lastChild.remove();
}

function ustawPakiet(z, flash) {
  const godz = (z.ts || "").slice(11, 19);
  const p = { sektor: z.sektor, status: z.status, pewnosc: z.pewnosc, ts: godz, liczba_osob: z.liczba_osob };
  const el = $("#ostatni-pakiet");
  el.innerHTML = "{ " + Object.entries(p).map(([k, v]) => `<span class="k">${k}</span>: <span class="v">${esc(JSON.stringify(v))}</span>`).join(", ")
    + ` }  <span class="k">· obraz: 0 B</span>`;
  if (flash) { el.classList.remove("flash"); void el.offsetWidth; el.classList.add("flash"); }
}

let petlaTimery = [];
function swiecPetle(indeksy) {
  const etapy = $$("#etapy li");
  petlaTimery.forEach(clearTimeout);
  petlaTimery = [];
  etapy.forEach((e) => e.classList.remove("swieci"));
  indeksy.forEach((idx, n) => {
    petlaTimery.push(setTimeout(() => etapy[idx].classList.add("swieci"), n * 140));
  });
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
  setTimeout(() => { el.classList.add("znika"); setTimeout(() => el.remove(), 320); }, 5200);
}

function resetujWidok() {
  ui.ids.clear();
  ui.ostatnieId = 0;
  ui.sygSektorow = ui.sygKrokow = ui.sygStat = "";
  $("#feed").innerHTML = "";
  $("#ostatni-pakiet").textContent = "oczekiwanie na metadane z roju…";
  wyczyscDzialania();
  M.podswietlenie.clearLayers();
  if (ui.zakladka === "decyzje") odswiezRekomendacje(false);
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
  } catch { /* brak Web Audio - pomijamy */ }
}

// ====================================================================== POLACZENIE

function ustawPolaczenie(tryb) {
  ui.polaczenie = tryb;
  const chip = $("#chip-link");
  chip.className = `chip chip-link ${tryb}`;
  chip.querySelector("span").textContent = { ws: "LIVE · WebSocket", http: "LIVE · HTTP", off: "OFFLINE — ponawiam" }[tryb];
  chip.title = { ws: "Połączenie na żywo z backendem (WebSocket)", http: "WebSocket niedostępny — odświeżanie przez HTTP co 1 s",
    off: "Brak połączenia z backendem HERMES" }[tryb];
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
      const restart = ui.stan && (stan.czas < ui.stan.czas || stan.scenariusz.id !== ui.stan.scenariusz.id);
      if (restart) resetujWidok();
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

// ====================================================================== ZAKLADKI: DECYZJE / FLOTA / RODO / DANE

function przelaczZakladke(nazwa) {
  ui.zakladka = nazwa;
  $$(".zakladki button").forEach((b) => b.classList.toggle("aktywna", b.dataset.tab === nazwa));
  $$(".tab").forEach((t) => t.classList.toggle("widoczna", t.id === `tab-${nazwa}`));
  if (nazwa === "rodo" && !ui.anonZaladowane) zaladujAnonimizacje();
  if (nazwa === "decyzje" && ui.rekWyswietlone) odswiezRekomendacje(false);
}

let rekDane = [];
async function odswiezRekomendacje(animuj = true) {
  const lista = await pobierz("/api/rekomendacje");
  rekDane = lista;
  ui.rekWyswietlone = true;
  if (animuj) swiecPetle([5, 6]);
  const kont = $("#lista-rek");
  if (!lista.length) {
    kont.innerHTML = `<p class="pusto">Brak aktywnych zagrożeń — wszystkie sektory OK.</p>`;
    return;
  }
  kont.innerHTML = lista.map((r, i) => `
    <article class="rek P${r.priorytet}${animuj ? " nowa" : ""}" data-i="${i}">
      <div class="rek-gora"><span class="prio">P${r.priorytet}</span><span class="rek-sektor">${esc(r.sektor)}</span>
        <span class="status-pill" style="--k:${KOLOR[r.status]}">${r.status}</span>
        <span class="rek-osoby">${r.liczba_osob ? `${r.liczba_osob} os.` : ""}</span></div>
      <p>${esc(r.opis)}</p>
      <div class="jednostki">${r.jednostki_rekomendowane.map((j) => `<span class="jedn">${esc(j)}</span>`).join("")}</div>
      ${r.schrony.length ? `<div class="schrony"><span class="schrony-tytul">Najbliższe schrony (KG PSP)</span>${r.schrony.map((p) => `
        <div class="schron">${IKONY.SCHRON}<span>${esc(p.adres)}</span>${p.dostepnosc === "Całodobowa" ? '<span class="h24">24H</span>' : ""}<span class="odl">${p.odleglosc_km} km</span></div>`).join("")}</div>` : ""}
      <div class="rek-akcje">${r.w_realizacji ? '<span class="w-realizacji-tag">W REALIZACJI</span>'
        : `<button class="btn-dysponuj" data-sektor="${esc(r.sektor)}">Zadysponuj ${esc(r.jednostki_rekomendowane.join(" + "))}</button>`}</div>
    </article>`).join("");
}

function zbudujKarteFloty(d) {
  const el = document.createElement("article");
  el.className = "fk";
  el.dataset.id = d.id;
  el.innerHTML = `
    <div class="fk-gora"><span class="fk-id">${d.id}</span><span class="fk-nazwa">${esc(d.nazwa)}</span>
      <span class="fk-tryb">${d.tryb === "aktywny" ? "AKTYWNY" : "PASYWNY"}<br>${esc(d.sensor)}</span></div>
    <div class="fk-status"></div>
    <div class="fk-bateria"><div class="pasek"><i></i></div><span class="fk-bat"></span></div>
    <div class="fk-metryki">
      <div><span>Mesh</span><b class="m-mesh"></b></div><div><span>Twarze</span><b class="m-twarze"></b></div>
      <div><span>Zadania</span><b class="m-zad"></b></div><div><span>Bufor</span><b class="m-buf"></b></div>
    </div>
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
    el.querySelector(".fk-status").textContent = d.status_misji;
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
    const btn = el.querySelector("[data-wezel]");
    btn.textContent = d.zywy ? "Symuluj awarię" : "Przywróć (nowy BSP)";
    btn.className = d.zywy ? "awaria" : "przywroc";
    const glos = el.querySelector(".glos");
    if (glos) glos.disabled = !d.zywy;
  });
}

function podswietlDrona(id) {
  $$(".fk").forEach((e) => e.classList.toggle("podswietlony", e.dataset.id === id));
  $(`.fk[data-id="${id}"]`)?.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

async function zaladujAnonimizacje() {
  ui.anonZaladowane = true;
  const kont = $("#porownanie");
  kont.style.opacity = 0.5;
  try {
    const d = await pobierz(`/api/anonimizacja/demo?tryb=${ui.trybAnon}`);
    $("#img-przed").src = `data:image/jpeg;base64,${d.oryginal_base64}`;
    $("#img-po").src = `data:image/jpeg;base64,${d.zanonimizowany_base64}`;
    const json = JSON.stringify(d.pakiet_do_czk, null, 2);
    $("#pakiet-json").textContent = json;
    $("#pakiet-rozmiar").textContent = `${new Blob([JSON.stringify(d.pakiet_do_czk)]).size} B · obraz: 0 B · twarze zanonim.: ${d.liczba_wykrytych_twarzy}`;
  } catch {
    $("#pakiet-json").textContent = "Brak klatki testowej samples/test_face.jpg";
  }
  kont.style.opacity = 1;
}

async function zaladujZrodla() {
  const zrodla = await pobierz("/api/zrodla");
  $("#tabela-zrodel tbody").innerHTML = zrodla.map((z) => {
    const realne = z.typ_uzycia.startsWith("realne");
    return `<tr><td><b>${esc(z.nazwa)}</b><small>${esc(z.jak)}</small></td>
      <td><span class="badge ${realne ? "realne" : "mock"}">${esc(z.typ_uzycia)}</span></td></tr>`;
  }).join("");
}

async function zaladujImgw() {
  const chip = $("#chip-imgw");
  try {
    const { imgw } = await pobierz("/api/pogoda");
    if (!imgw) throw new Error();
    chip.classList.remove("wyszarzony");
    chip.innerHTML = `<small>IMGW</small>${esc(imgw.stacja)} ${imgw.temperatura_c.toFixed(1)}°C · ${imgw.wiatr_kmh} km/h`;
    chip.title = `Pogoda bieżąca IMGW-PIB (${imgw.pomiar}): wilgotność ${imgw.wilgotnosc_proc}%, ciśnienie ${imgw.cisnienie_hpa} hPa, opad ${imgw.opad_mm} mm`;
  } catch {
    chip.classList.add("wyszarzony");
    chip.innerHTML = "<small>IMGW</small>offline";
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

  $("#btn-rekomenduj").addEventListener("click", () => odswiezRekomendacje(true));
  const listaRek = $("#lista-rek");
  listaRek.addEventListener("click", async (e) => {
    const btn = e.target.closest(".btn-dysponuj");
    if (btn) {
      btn.disabled = true;
      try { await post(`/api/dysponuj/${btn.dataset.sektor}`); } catch { /* sektor juz obsluzony */ }
      odswiezRekomendacje(false);
      return;
    }
    const karta = e.target.closest(".rek");
    if (karta) {
      const d = M.def[rekDane[karta.dataset.i].sektor];
      M.mapa.flyTo([d.lat_centrum, d.lon_centrum], 14, { duration: 0.8 });
    }
  });
  listaRek.addEventListener("mouseover", (e) => {
    const karta = e.target.closest(".rek");
    if (karta && karta.dataset.i !== ui.rekPodswietlona) {
      ui.rekPodswietlona = karta.dataset.i;
      podswietlRekomendacje(rekDane[karta.dataset.i]);
    }
  });
  listaRek.addEventListener("mouseleave", () => { ui.rekPodswietlona = null; podswietlRekomendacje(null); });

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

  $$("#seg-anon button").forEach((b) => b.addEventListener("click", () => {
    $$("#seg-anon button").forEach((x) => x.classList.toggle("aktywny", x === b));
    ui.trybAnon = b.dataset.tryb;
    zaladujAnonimizacje();
  }));
  const suwak = $("#suwak");
  suwak.addEventListener("input", () => $("#porownanie").style.setProperty("--p", `${suwak.value}%`));

  $$('input[name="baza"]').forEach((r) => r.addEventListener("change", () => {
    Object.entries(M.bazowe).forEach(([k, w]) => { if (k === r.value) w.addTo(M.mapa); else w.remove(); });
    M.bazowe[r.value].bringToBack();
  }));
  const przelacz = (id, warstwa) => $(id).addEventListener("change", (e) => {
    const w = warstwa();
    if (w) e.target.checked ? w.addTo(M.mapa) : w.remove();
  });
  przelacz("#w-prg", () => M.prg);
  przelacz("#w-schrony", () => M.schrony);
  przelacz("#w-jednostki", () => M.jednostkiStale);
  $("#w-sektory").addEventListener("change", (e) => {
    Object.values(M.sektory).concat(M.etykiety).forEach((w) => (e.target.checked ? w.addTo(M.mapa) : w.remove()));
    ui.sygSektorow = "";
    if (ui.stan) aktualizujSektory(ui.stan.sektory);
  });
  $("#w-heat").addEventListener("change", () => ui.stan && aktualizujHeat(ui.stan.sektory));
  $("#w-mesh").addEventListener("change", () => ui.stan && aktualizujMesh(ui.stan.linki));
  $("#w-scen").addEventListener("change", () => ui.stan && aktualizujWarstwyScenariusza(ui.stan.scenariusz.warstwy));

  document.addEventListener("keydown", (e) => {
    if (e.target.matches("input, textarea") || e.metaKey || e.ctrlKey || e.altKey) return;
    if (e.code === "Space") { e.preventDefault(); post("/api/sym/pauza"); }
    const scen = { Digit1: "patrol", Digit2: "powodz", Digit3: "pozar" }[e.code];
    if (scen) post(`/api/sym/scenariusz/${scen}`);
  });
}

// ====================================================================== START

window.addEventListener("DOMContentLoaded", async () => {
  ustawPolaczenie("off");
  inicjalizujMape();
  inicjalizujWykres();
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
  if ($(`#tab-${zHasha}`)) {
    przelaczZakladke(zHasha);
    if (zHasha === "decyzje") setTimeout(() => odswiezRekomendacje(true), 800);
  }
  zaladujSchrony().catch(() => { $("#schrony-opis").textContent = "Brak snapshotu schronów — uruchom: python data_sources.py --odswiez-schrony"; });
  zaladujZrodla().catch(() => {});
  zaladujImgw();
  setInterval(zaladujImgw, 10 * 60 * 1000);
});
