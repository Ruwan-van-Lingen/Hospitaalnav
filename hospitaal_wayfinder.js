/* ============================================================
    DATA — verkry direk vanaf Skema.sql + SeedData.sql
  ============================================================ */
const VLOER_VERANDER_PENALTY_S = 20.0;

const geboue = [
  { id: "MAIN", naam: "Hoofgebou" },
  { id: "SYGEBOU", naam: "Sygebou" },
];

const vloere = [
  { id: "MAIN-G", gebou: "MAIN", level: 0, naam: "Grondvloer" },
  { id: "MAIN-1", gebou: "MAIN", level: 1, naam: "Vlak 1 — Sale" },
  {
    id: "MAIN-2",
    gebou: "MAIN",
    level: 2,
    naam: "Vlak 2 — ICU / Teater",
  },
  { id: "SYGEBOU-G", gebou: "SYGEBOU", level: 0, naam: "Grondvloer" },
  {
    id: "SYGEBOU-1",
    gebou: "SYGEBOU",
    level: 1,
    naam: "Vlak 1 — Radiologie",
  },
];

const nodes = [
  ["MAIN-G-ENT", "MAIN-G", "INGANG", "Hoof Publieke Ingang", 0, 0, null],
  ["MAIN-G-AMB", "MAIN-G", "INGANG", "Ambulans Baai", 0, 20, null],
  [
    "MAIN-G-J01",
    "MAIN-G",
    "AANSLUITING",
    "Voorportaal Kruising",
    10,
    0,
    null,
  ],
  ["MAIN-G-ELV", "MAIN-G", "HUISBAK_GROEP", "Hoof Hysbakke", 15, 5, null],
  ["MAIN-G-STA", "MAIN-G", "TRAPHUIS", "Hoof Trap", 15, 10, null],
  ["MAIN-G-ER", "MAIN-G", "DEPARTEMENT", "Nooddienste", 5, 20, null],
  ["MAIN-G-TUN", "MAIN-G", "TONNEL", "Tonnel na Sygebou", 10, 30, null],

  [
    "MAIN-1-ELV",
    "MAIN-1",
    "HUISBAK_GROEP",
    "Hysbakke Vlak 1",
    15,
    5,
    null,
  ],
  ["MAIN-1-STA", "MAIN-1", "TRAPHUIS", "Trap Vlak 1", 15, 10, null],
  [
    "MAIN-1-J01",
    "MAIN-1",
    "AANSLUITING",
    "Saal Gang Kruising",
    20,
    5,
    null,
  ],
  ["MAIN-1-WARDA", "MAIN-1", "DEPARTEMENT", "Saal A", 25, 0, null],
  ["MAIN-1-WARDB", "MAIN-1", "DEPARTEMENT", "Saal B", 25, 10, null],
  [
    "MAIN-1-BRIDGE",
    "MAIN-1",
    "LUGBRUG",
    "Lugbrug na Sygebou",
    30,
    20,
    null,
  ],

  [
    "MAIN-2-ELV",
    "MAIN-2",
    "HUISBAK_GROEP",
    "Hysbakke Vlak 2",
    15,
    5,
    null,
  ],
  ["MAIN-2-STA", "MAIN-2", "TRAPHUIS", "Trap Vlak 2", 15, 10, null],
  [
    "MAIN-2-J01",
    "MAIN-2",
    "AANSLUITING",
    "ICU Gang Kruising",
    20,
    5,
    "ICU_ONLY",
  ],
  ["MAIN-2-ICU", "MAIN-2", "DEPARTEMENT", "ICU", 25, 0, "ICU_ONLY"],
  [
    "MAIN-2-OR",
    "MAIN-2",
    "DEPARTEMENT",
    "Operasieteaters",
    25,
    10,
    "SLEGS_PERSONEEL",
  ],

  ["SYGEBOU-G-ENT", "SYGEBOU-G", "INGANG", "Sygebou Ingang", 40, 0, null],
  [
    "SYGEBOU-G-J01",
    "SYGEBOU-G",
    "AANSLUITING",
    "Sygebou Voorportaal",
    40,
    10,
    null,
  ],
  [
    "SYGEBOU-G-ELV",
    "SYGEBOU-G",
    "HUISBAK_GROEP",
    "Sygebou Hysbak",
    40,
    15,
    null,
  ],
  [
    "SYGEBOU-G-TUN",
    "SYGEBOU-G",
    "TONNEL",
    "Tonnel na Hoofgebou",
    10,
    30,
    null,
  ],
  [
    "SYGEBOU-G-OUT",
    "SYGEBOU-G",
    "DEPARTEMENT",
    "Pasiënt Ontvangs",
    45,
    10,
    null,
  ],

  [
    "SYGEBOU-1-ELV",
    "SYGEBOU-1",
    "HUISBAK_GROEP",
    "Sygebou Hysbak Vlak 1",
    40,
    15,
    null,
  ],
  [
    "SYGEBOU-1-BRIDGE",
    "SYGEBOU-1",
    "LUGBRUG",
    "Lugbrug na Hoofgebou",
    30,
    20,
    null,
  ],
  ["SYGEBOU-1-RAD", "SYGEBOU-1", "DEPARTEMENT", "Radiologie", 45, 20, null],
].map(([id, vloer, tipe, etiket, x, y, beperkte_groep]) => ({
  id,
  vloer,
  tipe,
  etiket,
  x,
  y,
  beperkte: beperkte_groep,
}));

// [van, na, RandTipe, afstand_m, Basis_gewig_s, wag_penalty_s, vloer_verander, bidirectional]
const randRye = [
  ["MAIN-G-ENT", "MAIN-G-J01", "GANG", 10, 8, 0, 0, 1],
  ["MAIN-G-J01", "MAIN-G-ELV", "GANG", 6, 5, 0, 0, 1],
  ["MAIN-G-J01", "MAIN-G-STA", "GANG", 10, 8, 0, 0, 1],
  ["MAIN-G-J01", "MAIN-G-ER", "GANG", 22, 18, 0, 0, 1],
  ["MAIN-G-AMB", "MAIN-G-ER", "GANG", 6, 5, 0, 0, 1],
  ["MAIN-G-J01", "MAIN-G-TUN", "GANG", 32, 27, 0, 0, 1],

  ["MAIN-G-ELV", "MAIN-1-ELV", "HUISBAK", 0, 8, 25, 1, 1],
  ["MAIN-1-ELV", "MAIN-2-ELV", "HUISBAK", 0, 8, 25, 1, 1],
  ["MAIN-G-ELV", "MAIN-2-ELV", "HUISBAK", 0, 14, 25, 2, 1],
  ["MAIN-G-STA", "MAIN-1-STA", "TRAPPE", 0, 15, 0, 1, 1],
  ["MAIN-1-STA", "MAIN-2-STA", "TRAPPE", 0, 15, 0, 1, 1],

  ["MAIN-1-ELV", "MAIN-1-J01", "GANG", 6, 5, 0, 0, 1],
  ["MAIN-1-STA", "MAIN-1-J01", "GANG", 6, 5, 0, 0, 1],
  ["MAIN-1-J01", "MAIN-1-WARDA", "GANG", 6, 5, 0, 0, 1],
  ["MAIN-1-J01", "MAIN-1-WARDB", "GANG", 6, 5, 0, 0, 1],
  ["MAIN-1-J01", "MAIN-1-BRIDGE", "GANG", 16, 13, 0, 0, 1],

  ["MAIN-2-ELV", "MAIN-2-J01", "GANG", 6, 5, 0, 0, 1],
  ["MAIN-2-STA", "MAIN-2-J01", "GANG", 6, 5, 0, 0, 1],
  ["MAIN-2-J01", "MAIN-2-ICU", "GANG", 6, 5, 0, 0, 1],
  ["MAIN-2-J01", "MAIN-2-OR", "GANG", 6, 5, 0, 0, 1],

  ["SYGEBOU-G-ENT", "SYGEBOU-G-J01", "GANG", 10, 8, 0, 0, 1],
  ["SYGEBOU-G-J01", "SYGEBOU-G-ELV", "GANG", 6, 5, 0, 0, 1],
  ["SYGEBOU-G-J01", "SYGEBOU-G-OUT", "GANG", 6, 5, 0, 0, 1],
  ["SYGEBOU-G-J01", "SYGEBOU-G-TUN", "GANG", 30, 25, 0, 0, 1],

  ["SYGEBOU-G-ELV", "SYGEBOU-1-ELV", "HUISBAK", 0, 8, 25, 1, 1],

  ["SYGEBOU-1-ELV", "SYGEBOU-1-BRIDGE", "GANG", 10, 8, 0, 0, 1],
  ["SYGEBOU-1-ELV", "SYGEBOU-1-RAD", "GANG", 6, 5, 0, 0, 1],

  ["MAIN-1-BRIDGE", "SYGEBOU-1-BRIDGE", "LUGBRUG", 25, 21, 0, 0, 1],
  ["MAIN-G-TUN", "SYGEBOU-G-TUN", "TONNEL", 18, 15, 0, 0, 1],
];

const toegangToestemmings = {
  PUBLIEK: new Set(),
  PERSONEEL: new Set(["SLEGS_PERSONEEL", "ICU_ONLY"]),
  PASIENT_VERVOER: new Set(["SLEGS_PERSONEEL"]),
  NOODGEVAL: new Set(["SLEGS_PERSONEEL", "ICU_ONLY"]),
};
const gebruikerTipeEtikette = {
  PUBLIEK: "Publiek / Besoeker",
  PERSONEEL: "Personeel",
  PASIENT_VERVOER: "Pasiënt Vervoer",
  NOODGEVAL: "Noodgeval",
};

const NODE_KLEURE = {
  AANSLUITING: "#7C8B99",
  HUISBAK_GROEP: "#D97706",
  TRAPHUIS: "#D97706",
  DEUR: "#7C8B99",
  INGANG: "#2E8B57",
  LUGBRUG: "#6D5DD3",
  TONNEL: "#6D5DD3",
  DEPARTEMENT: "#1E6FA8",
};
const RAND_KLEURE = {
  GANG: "#AFC2CB",
  HUISBAK: "#D97706",
  TRAPPE: "#D97706",
  LUGBRUG: "#6D5DD3",
  TONNEL: "#6D5DD3",
};

/* ============================================================
   NODE/VLOER LOOKUPS — gebruik slegs vir tekening van vloer plan 
   Pathfinding kom vanaf die FastAPI / roete eindpunt (graph.astar() 
   wat bediener-kant hardloop), nie van JS nie.
   ============================================================ */
const nodeById = Object.fromEntries(nodes.map((n) => [n.id, n]));
const vloerById = Object.fromEntries(vloere.map((f) => [f.id, f]));

async function fetchRoute(apiBase, beginId, eindeId, gebruikerTipe) {
  const url = `${apiBase.replace(/\/$/, "")}/route?begin=${encodeURIComponent(beginId)}&doel=${encodeURIComponent(eindeId)}&gebruiker_tipe=${encodeURIComponent(gebruikerTipe)}`;
  let resp;
  try {
    resp = await fetch(url);
  } catch (networkErr) {
    return {
      error: "network",
      message: `Kon nie ${apiBase} bereik nie. Loop die API? CORS toegelaat?`,
    };
  }

  let body;
  try {
    body = await resp.json();
  } catch (e) {
    body = null;
  }

  if (!resp.ok) {
    const detail =
      body && body.detail ? body.detail : `HTTP ${resp.status}`;
    return {
      error: resp.status === 403 ? "blocked" : "invalid",
      message: detail,
    };
  }

  return {
    path: body.pad,
    cost: body.geskatte_tyd_sekondes,
    formattedCost: body.geskatte_tyd,
    distance: body.geskatte_afstand_m,
    formattedDistance: body.geskatte_afstand,
    nodeCount: body.node_telling,
  };
}

/* ============================================================
                        UI TOESTANDE
============================================================ */
let huidigeVloer = vloere[0].id;
let laasteResultaat = null; // {pad, koste}

function bestemmingEtiket(item) {
  return `${item.etiket} — ${item.gebou_naam}, ${item.vloer_naam} (${item.node_id})`;
}

async function laaiBestemmings(soekterm, selectId, gekoseId = null) {
  const apiBase = document.getElementById("apiUrl").value.trim();
  const url = `${apiBase.replace(/\/$/, "")}/destinations?q=${encodeURIComponent(soekterm)}&limiet=100`;
  try {
    const response = await fetch(url);
    if (!response.ok) return;
    const data = await response.json();
    const lys = document.getElementById(selectId);
    lys.innerHTML = "";
    data.bestemmings.forEach((item) => {
      const opsie = document.createElement("option");
      opsie.value = item.node_id;
      opsie.textContent = bestemmingEtiket(item);
      lys.appendChild(opsie);
    });
    if (gekoseId && [...lys.options].some((opsie) => opsie.value === gekoseId)) {
      lys.value = gekoseId;
    }
  } catch (_) {
    // Die roete-foutboodskap hanteer 'n API wat nie bereikbaar is nie.
  }
}

function koppelBestemmingSoektog(inputId, selectId) {
  const invoer = document.getElementById(inputId);
  let timer;
  invoer.addEventListener("input", () => {
    clearTimeout(timer);
    timer = setTimeout(() => laaiBestemmings(invoer.value, selectId), 200);
  });
}

function bestemmingId(inputId) {
  return document.getElementById(inputId).value || null;
}

function populateSelects() {
  const utSel = document.getElementById("gebruikerTipe");
  Object.keys(gebruikerTipeEtikette).forEach((k) => {
    const o = document.createElement("option");
    o.value = k;
    o.textContent = gebruikerTipeEtikette[k];
    utSel.appendChild(o);
  });

  koppelBestemmingSoektog("beginSoek", "beginNode");
  koppelBestemmingSoektog("eindSoek", "endNode");
  laaiBestemmings("", "beginNode", "MAIN-G-ENT");
  laaiBestemmings("", "endNode", "SYGEBOU-1-RAD");
}

function renderTabs() {
  const tabsEl = document.getElementById("tabs");
  tabsEl.innerHTML = "";
  const roeterVloere =
    laasteResultaat && laasteResultaat.path
      ? new Set(laasteResultaat.path.map((id) => nodeById[id].vloer))
      : new Set();
  vloere.forEach((f) => {
    const d = document.createElement("div");
    d.className =
      "tab" +
      (f.id === huidigeVloer ? " active" : "") +
      (roeterVloere.has(f.id) ? " on-route" : "");
    d.textContent = `${f.gebou} · ${f.naam}`;
    d.onclick = () => {
      huidigeVloer = f.id;
      renderAll();
    };
    tabsEl.appendChild(d);
  });
}

function renderIndicator() {
  const el = document.getElementById("indicator");
  el.innerHTML = "";
  const roeterVloere =
    laasteResultaat && laasteResultaat.path
      ? new Set(laasteResultaat.path.map((id) => nodeById[id].vloer))
      : new Set();
  vloere.forEach((f) => {
    const row = document.createElement("div");
    row.className =
      "ind-row" +
      (f.id === huidigeVloer ? " current" : "") +
      (roeterVloere.has(f.id) ? " onroute" : "");
    row.innerHTML = `<span class="dot"></span><span>${f.gebou} L${f.level} — ${f.naam}</span>`;
    row.onclick = () => {
      huidigeVloer = f.id;
      renderAll();
    };
    el.appendChild(row);
  });
}

function renderLegend() {
  const el = document.getElementById("legend");
  el.innerHTML = "";
  Object.entries(NODE_KLEURE).forEach(([tipe, color]) => {
    const s = document.createElement("span");
    s.innerHTML = `<span class="swatch" style="background:${color}"></span>${tipe}`;
    el.appendChild(s);
  });
}

// Uitleg konstantes: SCALE spasieer nodes ver genoeg weg van mekaar dat hulle nooit bots nie; PAD_Y reserveer n duidelike band aan die bokant vir die vloer titel so dat dit nooit onder n node etiktt sit nie
const SCALE = 15;
const PAD_X = 55;
const PAD_Y = 90;
const px = (n) => n.x * SCALE + PAD_X;
const py = (n) => n.y * SCALE + PAD_Y;

function renderPlan() {
  const svg = document.getElementById("plan");
  const NS = "http://www.w3.org/2000/svg";
  svg.innerHTML = "";

  const vloerNodes = nodes.filter((n) => n.vloer === huidigeVloer);
  const highlightSet = new Set(
    laasteResultaat && laasteResultaat.path ? laasteResultaat.path : [],
  );
  const verligRande = new Set();
  if (laasteResultaat && laasteResultaat.path) {
    const p = laasteResultaat.path;
    for (let i = 0; i < p.length - 1; i++) {
      verligRande.add(p[i] + "|" + p[i + 1]);
      verligRande.add(p[i + 1] + "|" + p[i]);
    }
  }

  // teken selfde-vloer rande 
  randRye.forEach(([van, na, tipe]) => {
    if (
      nodeById[van].vloer === huidigeVloer &&
      nodeById[na].vloer === huidigeVloer
    ) {
      const a = nodeById[van],
        b = nodeById[na];
      const isHl = verligRande.has(van + "|" + na);
      const line = document.createElementNS(NS, "line");
      line.setAttribute("x1", px(a));
      line.setAttribute("y1", py(a));
      line.setAttribute("x2", px(b));
      line.setAttribute("y2", py(b));
      line.setAttribute(
        "stroke",
        isHl ? "#FFB100" : RAND_KLEURE[tipe] || "#ccc",
      );
      line.setAttribute("stroke-width", isHl ? 5 : 2.2);
      if (isHl) {
        line.setAttribute("stroke-linecap", "round");
      }
      svg.appendChild(line);
    }
  });

  // teken nodes - etikette is gesentreer direk onder (of alternating above ), elke node met n soliede halo sodat hulle leesbaar bly en nie bots in aaneengrensende etikette of gang lyne in nie.
  vloerNodes.forEach((n, i) => {
    const cx = px(n),
      cy = py(n);
    const isHl = highlightSet.has(n.id);
    const g = document.createElementNS(NS, "g");
    g.style.cursor = "pointer";
    g.onclick = () => {
      const beginSel = document.getElementById("beginNode"),
        endSel = document.getElementById("endNode");
      if (!g.dataset.pickedOnce) {
        beginSel.value = n.id;
        g.dataset.pickedOnce = "1";
      } else {
        endSel.value = n.id;
      }
    };

    if (n.beperkte) {
      const ring = document.createElementNS(NS, "circle");
      ring.setAttribute("cx", cx);
      ring.setAttribute("cy", cy);
      ring.setAttribute("r", isHl ? 15 : 11);
      ring.setAttribute("fill", "none");
      ring.setAttribute(
        "stroke",
        n.beperkte === "ICU_ONLY" ? "#E14B4B" : "#6D5DD3",
      );
      ring.setAttribute("stroke-width", 1.6);
      ring.setAttribute("stroke-dasharray", "3,3");
      svg.appendChild(ring);
    }

    const circle = document.createElementNS(NS, "circle");
    circle.setAttribute("cx", cx);
    circle.setAttribute("cy", cy);
    circle.setAttribute("r", isHl ? 9 : 6.5);
    circle.setAttribute("fill", NODE_KLEURE[n.tipe] || "#333");
    circle.setAttribute("stroke", isHl ? "#FFB100" : "#fff");
    circle.setAttribute("stroke-width", isHl ? 2.4 : 1.2);
    g.appendChild(circle);

    // Versprei opeenvolgende etikette onder, bo, regs en links van hul nodes.
    const etiketPosisies = [
      { dx: 0, dy: 20, anchor: "middle" },
      { dx: 0, dy: -21, anchor: "middle" },
      { dx: 14, dy: -5, anchor: "start" },
      { dx: -14, dy: -5, anchor: "end" },
    ];
    const etiketPosisie = etiketPosisies[i % etiketPosisies.length];
    const etiket = n.etiket + (n.beperkte ? ` [${n.beperkte}]` : "");
    const woorde = etiket.split(" ");
    const middelpunt = Math.ceil(woorde.length / 2);
    const etiketLyne =
      woorde.length > 2
        ? [
            woorde.slice(0, middelpunt).join(" "),
            woorde.slice(middelpunt).join(" "),
          ]
        : [etiket];

    const text = document.createElementNS(NS, "text");
    const etiketX = cx + etiketPosisie.dx;
    const etiketY = cy + etiketPosisie.dy;
    text.setAttribute("x", etiketX);
    text.setAttribute("y", etiketY);
    text.setAttribute("text-anchor", etiketPosisie.anchor);
    text.setAttribute("font-size", "9");
    text.setAttribute("font-family", "Inter, sans-serif");
    text.setAttribute("fill", "#12222E");
    text.setAttribute("paint-order", "stroke");
    text.setAttribute("stroke", "#E7EEF2");
    text.setAttribute("stroke-width", "3");
    etiketLyne.forEach((lyn, lynNommer) => {
      const tspan = document.createElementNS(NS, "tspan");
      tspan.setAttribute("x", etiketX);
      tspan.setAttribute("dy", lynNommer === 0 ? 0 : 11);
      tspan.textContent = lyn;
      text.appendChild(tspan);
    });
    g.appendChild(text);

    svg.appendChild(g);
  });

  const title = document.createElementNS(NS, "text");
  const f = vloerById[huidigeVloer];
  title.setAttribute("x", 20);
  title.setAttribute("y", 28);
  title.setAttribute("font-size", "15");
  title.setAttribute("font-weight", "700");
  title.setAttribute("font-family", "Space Grotesk, sans-serif");
  title.setAttribute("fill", "#12222E");
  title.textContent = `${f.gebou} — ${f.naam}`;
  svg.appendChild(title);
}

function renderRoutePanel() {
  const el = document.getElementById("routePanel");
  el.innerHTML = "";
  if (!laasteResultaat) {
    el.innerHTML =
      '<div class="empty-note">Kies "Vanaf" en "Na", dan klik Vind Roete.</div>';
    return;
  }
  if (laasteResultaat.error) {
    el.innerHTML = `<div class="empty-note">${laasteResultaat.message}</div>`;
    return;
  }
  if (!laasteResultaat.path) {
    el.innerHTML = '<div class="empty-note">Geen roete gevind nie.</div>';
    return;
  }
  const ul = document.createElement("ul");
  ul.className = "route-list";
  laasteResultaat.path.forEach((id, i) => {
    const n = nodeById[id];
    const li = document.createElement("li");
    li.innerHTML = `<span>${i + 1}. ${n.etiket}</span><span class="t">${vloerById[n.vloer].gebou} L${vloerById[n.vloer].level}</span>`;
    li.onclick = () => {
      huidigeVloer = n.vloer;
      renderAll();
    };
    ul.appendChild(li);
  });
  el.appendChild(ul);
  const total = document.createElement("div");
  total.className = "route-total";
  total.innerHTML = `<span>Totale tyd</span><span>${laasteResultaat.formattedCost}</span>`;
  el.appendChild(total);
  const totalAfstand = document.createElement("div");
  totalAfstand.className = "route-total";
  totalAfstand.innerHTML = `<span>Totale afstand</span><span>${laasteResultaat.formattedDistance}</span>`;
  el.appendChild(totalAfstand);
}

function renderStatus() {
  const el = document.getElementById("status");
  if (!laasteResultaat) {
    el.textContent = "";
    el.className = "status";
    return;
  }
  if (laasteResultaat.error === "blocked") {
    el.textContent = `⛔ Toegang geweier (403): ${laasteResultaat.message}`;
    el.className = "status blocked";
  } else if (laasteResultaat.error === "invalid") {
    el.textContent = `⚠ Ongeldige versoek: ${laasteResultaat.message}`;
    el.className = "status blocked";
  } else if (laasteResultaat.error === "network") {
    el.textContent = `⚠ ${laasteResultaat.message}`;
    el.className = "status blocked";
  } else if (!laasteResultaat.path) {
    el.textContent = "⛔ Geen roete beskikbaar nie.";
    el.className = "status blocked";
  } else {
    el.textContent = `✓ Roete gevind via API: ${laasteResultaat.nodeCount} node(s), ${laasteResultaat.formattedCost}, ${laasteResultaat.formattedDistance}.`;
    el.className = "status ok";
  }
}

function renderAll() {
  renderTabs();
  renderIndicator();
  renderPlan();
  renderRoutePanel();
  renderStatus();
}

document.getElementById("findBtn").onclick = async () => {
  const begin = bestemmingId("beginNode");
  const end = bestemmingId("endNode");
  const ut = document.getElementById("gebruikerTipe").value;
  const apiBase = document.getElementById("apiUrl").value.trim();

  if (!begin || !end) {
    laasteResultaat = {
      error: "invalid",
      message: "Kies asseblief 'n geldige beginpunt en bestemming uit die soeklys.",
    };
    renderAll();
    return;
  }

  const btn = document.getElementById("findBtn");
  btn.disabled = true;
  btn.textContent = "Soek...";
  document.getElementById("status").textContent = "⏳ Roep API aan...";
  document.getElementById("status").className = "status";

  laasteResultaat = await fetchRoute(apiBase, begin, end, ut);

  btn.disabled = false;
  btn.textContent = "Vind Roete";
  if (laasteResultaat.path) huidigeVloer = nodeById[begin].vloer;
  renderAll();
};
document.getElementById("clearBtn").onclick = () => {
  laasteResultaat = null;
  renderAll();
};

populateSelects();
renderLegend();
renderAll();
