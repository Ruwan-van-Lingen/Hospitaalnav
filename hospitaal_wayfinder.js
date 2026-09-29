/**===========================================================================================
 * hospitaal_wayfinder.js
 * =======================
 * Interaktiewe webkoppelvlak vir die Hospitaalnavigasiestelsel (/ui).
 *
 * Hierdie lêer bevat:
 *   • Statiese topologiese grafiekdata (nodusse, rande, vloere, geboue)
 *     wat direk vanuit Skema.sql + SeedData.sql afgelei is en kliëntkant
 *     gebruik word vir SVG-tekening.
 *   • Roeteberekening via die FastAPI-agterkant (/route of /route/ontruim).
 *     A* loop bedienerkant (HospitaalGrafiek.py) — hierdie lêer stuur
 *     slegs die versoek en vertoon die resultaat.
 *   • SVG-vloerplan-tekening: nodusse, rande, paduitligging, etiketplasing.
 *   • Vloer-oortjies en die hysbak-styl vloerindikator (sykolom).
 *   • Soekveld-integrasie met /destinations vir mensleesbare bestemmings.
 *   • Ontruimingsmodus-ondersteuning: die waarskuwingsbanier en /route/ontruim-aanroep.
 *
 * Kaart-oorsigmodus (OORSIG_ID)
 * --------------------------------
 * Die "Oorsig — Alle Vloere"-oortjie vertoon alle vloere in lae op een SVG-kaart.
 * Nodusse wat presies dieselfde (x, y) koördinate deel oor vloere (bv.
 * hysbakke) word net een keer geteken. Vertikale hysbak- en trap-rande word in
 * oorsigmodus oorgeslaan omdat hulle as onsigbare lyne sou teken.
 *
 * Etiketplasing
 * -----------------
 * Die plasingsalgoritme probeer 8 kandidaatposisies per etiket en kies
 * die posisie met die minste botsings teen ander etikette, noduspunte en
 * ganglyne. Dit verhoed dat etikette oor mekaar of oor punte lê.
 */


const geboue = [
  { id: "MAIN", naam: "Hoofhospitaalgebou" },
  { id: "SYGEBOU", naam: "Sygebou" },
];

const vloere = [
  { id: "MAIN-G", gebou: "MAIN", level: 0, naam: "Grondvloer" },
  { id: "MAIN-1", gebou: "MAIN", level: 1, naam: "Vlak 1 — Sale" },
  {
    id: "MAIN-2",
    gebou: "MAIN",
    level: 2,
    naam: "Vlak 2 — Intensiewe sorg / Operasieteaters",
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
  ["MAIN-G-ENT", "MAIN-G", "INGANG", "Hoofingang", 0, 0, null],
  ["MAIN-G-AMB", "MAIN-G", "INGANG", "Ambulansbaai", 0, 20, null],
  [
    "MAIN-G-J01",
    "MAIN-G",
    "AANSLUITING",
    "Voorportaalaansluiting",
    10,
    0,
    null,
  ],
  ["MAIN-G-ELV", "MAIN-G", "HUISBAK_GROEP", "Hoofhysbakgroep", 15, 5, null],
  ["MAIN-G-STA", "MAIN-G", "TRAPHUIS", "Hooftraphuis", 15, 10, null],
  ["MAIN-G-ER", "MAIN-G", "DEPARTEMENT", "Nooddienste", 5, 20, null],
  ["MAIN-G-TUN", "MAIN-G", "TONNEL", "Tonnel na Sygebou", 10, 30, null],

  [
    "MAIN-1-ELV",
    "MAIN-1",
    "HUISBAK_GROEP",
    "Hysbakgroep Vlak 1",
    15,
    5,
    null,
  ],
  ["MAIN-1-STA", "MAIN-1", "TRAPHUIS", "Traphuis Vlak 1", 15, 10, null],
  [
    "MAIN-1-J01",
    "MAIN-1",
    "AANSLUITING",
    "Saalgangaansluiting",
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
    "Hysbakgroep Vlak 2",
    15,
    5,
    null,
  ],
  ["MAIN-2-STA", "MAIN-2", "TRAPHUIS", "Traphuis Vlak 2", 15, 10, null],
  [
    "MAIN-2-J01",
    "MAIN-2",
    "AANSLUITING",
    "Intensiewesorgaansluiting",
    20,
    5,
    "SLEGS_ICU",
  ],
  ["MAIN-2-ICU", "MAIN-2", "DEPARTEMENT", "Intensiewe sorg", 25, 0, "SLEGS_ICU"],
  [
    "MAIN-2-OR",
    "MAIN-2",
    "DEPARTEMENT",
    "Operasieteater",
    25,
    10,
    "SLEGS_PERSONEEL",
  ],

  ["SYGEBOU-G-ENT", "SYGEBOU-G", "INGANG", "Sygebou-ingang", 40, 0, null],
  [
    "SYGEBOU-G-J01",
    "SYGEBOU-G",
    "AANSLUITING",
    "Sygebou-voorportaalaansluiting",
    40,
    10,
    null,
  ],
  [
    "SYGEBOU-G-ELV",
    "SYGEBOU-G",
    "HUISBAK_GROEP",
    "Sygebou-hysbak",
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
    "Uitpasiëntontvangs",
    45,
    10,
    null,
  ],

  [
    "SYGEBOU-1-ELV",
    "SYGEBOU-1",
    "HUISBAK_GROEP",
    "Sygebou-hysbak Vlak 1",
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

// Volgorde: begin, einde, randtipe, afstand, basistyd, wagtyd, vloerverskil, tweerigting.
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

const gebruikerTipeEtikette = {
  PUBLIEK: "Publiek / Besoeker",
  PERSONEEL: "Personeel",
  PASIENT_VERVOER: "Pasiëntvervoer",
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

// Spesiale vloerwaarde wat die oorsigmodus (alle vloere gelaag) verteenwoordig.
const OORSIG_ID = "OORSIG";
// Elke vloer kry sy eie kleur in oorsigmodus, sodat gelaagde nodusse (bv.
// hysbakke wat doelbewus dieselfde x/y oor vloere heen deel) onderskei kan word.
const VLOER_KLEURE_PALET = ["#2E8B57", "#1E6FA8", "#D97706", "#6D5DD3", "#E14B4B", "#C7A008"];
const VLOER_KLEURE = Object.fromEntries(
  vloere.map((f, i) => [f.id, VLOER_KLEURE_PALET[i % VLOER_KLEURE_PALET.length]]),
);

/* ============================================================
   NODUS- EN VLOERINDEKSE — slegs vir die tekening van die vloerplan.
   Die FastAPI-roete-eindpunt bereken die roete op die bediener.
   ============================================================ */
const nodeById = Object.fromEntries(nodes.map((n) => [n.id, n]));
const vloerById = Object.fromEntries(vloere.map((f) => [f.id, f]));

async function fetchRoute(apiBase, beginId, eindeId, gebruikerTipe) {
  const basis = apiBase.replace(/\/$/, "");

  // Tydens ontruimingsmodus word die bestemming geïgnoreer en word die
  // naaste nooduitgang via 'n afsonderlike eindpunt bepaal.
  const ontruim = aktieweInsident.active && aktieweInsident.ontruimings_modus;
  const url = ontruim
    ? `${basis}/route/ontruim?begin=${encodeURIComponent(beginId)}&gebruiker_tipe=${encodeURIComponent(gebruikerTipe)}`
    : `${basis}/route?begin=${encodeURIComponent(beginId)}&doel=${encodeURIComponent(eindeId)}&gebruiker_tipe=${encodeURIComponent(gebruikerTipe)}`;

  let resp;
  try {
    resp = await fetch(url);
  } catch (networkErr) {
    return {
      error: "network",
      message: "Kon nie die roetebediener bereik nie. Probeer asseblief weer.",
    };
  }

  let body;
  try {
    body = await resp.json();
  } catch (e) {
    body = null;
  }

  if (!resp.ok) {
    const detail = typeof body?.detail === "string"
      ? body.detail
      : `Die roeteversoek het misluk (HTTP ${resp.status}).`;
    return {
      error: resp.status === 403 || resp.status === 409 ? "blocked" : "invalid",
      message: detail,
      status: resp.status,
    };
  }

  if (!body || !Array.isArray(body.pad)) {
    return { error: "invalid", message: "Die bediener het geen geldige roetedata teruggestuur nie." };
  }

  return {
    path: body.pad,
    cost: body.geskatte_tyd_sekondes,
    formattedCost: body.geskatte_tyd,
    distance: body.geskatte_afstand_m,
    formattedDistance: body.geskatte_afstand,
    nodeCount: body.node_telling,
    // Wys die nooduitgang se naam in die roete-paneel as ons in ontruimingsmodus is.
    uitgang: body.uitgang_node || null,
  };
}

/* ============================================================
                        KOPPELVLAKTOESTAND
============================================================ */
let huidigeVloer = OORSIG_ID;
let laasteResultaat = null;
let aktieweInsident = { active: false, blocked_node_ids: [] };
let insidentVersoek = 0;
let roeteVersoek = 0;
let roeteBesig = false;
let volgendeKaartKeuse = "beginNode";

async function laaiInsident(herteken = true) {
  const apiBase = document.getElementById("apiUrl").value.trim();
  const versoek = ++insidentVersoek;
  try {
    const response = await fetch(`${apiBase.replace(/\/$/, "")}/incident`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const insident = await response.json();
    if (versoek !== insidentVersoek || apiBase !== document.getElementById("apiUrl").value.trim()) return false;
    const verander = JSON.stringify(insident) !== JSON.stringify(aktieweInsident);
    aktieweInsident = insident;
    if (verander) laasteResultaat = null;
    const banier = document.getElementById("incidentBanner");
    banier.hidden = !aktieweInsident.active;
    if (aktieweInsident.active) {
      // Wys 'n spesiale boodskap as ontruimingsmodus aktief is.
      const ontruimTeks = aktieweInsident.ontruimings_modus
        ? "🚨 ONTRUIMINGSMODUS — Kies 'n beginpunt en klik Vind Roete vir die naaste nooduitgang."
        : aktieweInsident.description || "Roetes word rondom die geslote gebied bereken.";
      document.getElementById("incidentTitle").textContent = `Aktiewe sluiting: ${aktieweInsident.name}`;
      document.getElementById("incidentDescription").textContent = ontruimTeks;
    }
    // Werk bestaande opsies by sonder om die gebruiker se soekterme te verloor.
    merkGesloteBestemmings();
    document.getElementById("endNode").disabled = Boolean(insident.active && insident.ontruimings_modus);
    document.getElementById("eindSoek").disabled = document.getElementById("endNode").disabled;
    if (herteken && verander) renderAll();
    return true;
  } catch (_) {
    if (versoek === insidentVersoek) {
      laasteResultaat = { error: "network", message: "Kon nie die huidige sluitings bevestig nie. Probeer asseblief weer." };
      if (herteken) renderAll();
    }
    return false;
  }
}

function merkGesloteBestemmings() {
  const gesluit = new Set(aktieweInsident.active ? aktieweInsident.blocked_node_ids || [] : []);
  ["beginNode", "endNode"].forEach((id) => {
    const lys = document.getElementById(id);
    [...lys.options].forEach((opsie) => {
      opsie.disabled = gesluit.has(opsie.value);
      opsie.textContent = opsie.textContent.replace(/ \[GESLUIT\]$/, "") + (opsie.disabled ? " [GESLUIT]" : "");
    });
    if (lys.selectedOptions[0]?.disabled) {
      // Moet nooit stilweg 'n ander vertrekpunt kies wanneer die huidige een sluit nie.
      lys.value = "";
    }
  });
}

function bestemmingEtiket(item) {
  return `${item.etiket} — ${item.gebou_naam}, ${item.vloer_naam} (${item.node_id})`;
}

// Slegs die jongste versoek per keuselys mag sy resultate vertoon.
const bestemmingVersoeke = new Map();

async function laaiBestemmings(soekterm, selectId, gekoseId = null) {
  const apiBase = document.getElementById("apiUrl").value.trim();
  const versoek = (bestemmingVersoeke.get(selectId) || 0) + 1;
  bestemmingVersoeke.set(selectId, versoek);
  const url = `${apiBase.replace(/\/$/, "")}/destinations?q=${encodeURIComponent(soekterm)}&limiet=100`;
  try {
    const response = await fetch(url);
    if (bestemmingVersoeke.get(selectId) !== versoek) return;
    if (!response.ok) {
      wysBestemmingFout(`⚠ Kon nie bestemmings laai nie (HTTP ${response.status}).`);
      return;
    }
    const data = await response.json();
    if (bestemmingVersoeke.get(selectId) !== versoek) return;
    const lys = document.getElementById(selectId);
    lys.innerHTML = "";
    if (!data.bestemmings.length) {
      const opsie = document.createElement("option");
      opsie.value = "";
      opsie.textContent = "Geen bestemmings gevind nie";
      lys.appendChild(opsie);
    }
    data.bestemmings.forEach((item) => {
      const opsie = document.createElement("option");
      opsie.value = item.node_id;
      opsie.textContent = bestemmingEtiket(item);
      lys.appendChild(opsie);
    });
    if (gekoseId && [...lys.options].some((opsie) => opsie.value === gekoseId)) {
      lys.value = gekoseId;
    }
    merkGesloteBestemmings();
  } catch (netwerkFout) {
    if (bestemmingVersoeke.get(selectId) !== versoek) return;
    wysBestemmingFout("⚠ Kon nie bestemmings laai nie. Probeer asseblief weer.");
  }
}

/** Wys 'n foutboodskap in die hoof-statusreël (dieselfde element as renderStatus() gebruik). */
function wysBestemmingFout(boodskap) {
  const el = document.getElementById("status");
  el.textContent = boodskap;
  el.className = "status blocked";
}

function koppelBestemmingSoektog(inputId, selectId) {
  const invoer = document.getElementById(inputId);
  let timer;
  invoer.addEventListener("input", () => {
    wisRoete();
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
      ? new Set(laasteResultaat.path.map((id) => nodeById[id]?.vloer).filter(Boolean))
      : new Set();

  const oorsig = document.createElement("button");
  oorsig.type = "button";
  oorsig.className =
    "tab" +
    (huidigeVloer === OORSIG_ID ? " active" : "") +
    (roeterVloere.size > 1 ? " on-route" : "");
  oorsig.textContent = "Oorsig — Alle Vloere";
  oorsig.onclick = () => {
    huidigeVloer = OORSIG_ID;
    renderAll();
  };
  tabsEl.appendChild(oorsig);

  vloere.forEach((f) => {
    const d = document.createElement("button");
    d.type = "button";
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
      ? new Set(laasteResultaat.path.map((id) => nodeById[id]?.vloer).filter(Boolean))
      : new Set();
  vloere.forEach((f) => {
    const row = document.createElement("button");
    row.type = "button";
    row.className =
      "ind-row" +
      (f.id === huidigeVloer ? " current" : "") +
      (roeterVloere.has(f.id) ? " onroute" : "");
    row.innerHTML = `<span class="dot" style="background:${VLOER_KLEURE[f.id]}"></span><span>${f.gebou} L${f.level} — ${f.naam}</span>`;
    row.onclick = () => {
      huidigeVloer = f.id;
      renderAll();
    };
    el.appendChild(row);
  });
  // Laaste in die DOM = eerste bo-aan, want .indicator gebruik column-reverse.
  const oorsigRow = document.createElement("button");
  oorsigRow.type = "button";
  oorsigRow.className =
    "ind-row" +
    (huidigeVloer === OORSIG_ID ? " current" : "") +
    (roeterVloere.size > 1 ? " onroute" : "");
  oorsigRow.innerHTML = `<span class="dot"></span><span>Oorsig — Alle Vloere</span>`;
  oorsigRow.onclick = () => {
    huidigeVloer = OORSIG_ID;
    renderAll();
  };
  el.appendChild(oorsigRow);
}

function renderLegend() {
  const el = document.getElementById("legend");
  el.innerHTML = "";
  Object.entries(NODE_KLEURE).forEach(([tipe, color]) => {
    const s = document.createElement("span");
    s.innerHTML = `<span class="swatch" style="background:${color}"></span>${tipe}`;
    el.appendChild(s);
  });
  const skeiding = document.createElement("span");
  skeiding.textContent = "•";
  skeiding.style.opacity = "0.4";
  el.appendChild(skeiding);
  vloere.forEach((f) => {
    const s = document.createElement("span");
    s.innerHTML = `<span class="swatch" style="background:${VLOER_KLEURE[f.id]}"></span>${f.gebou} · ${f.naam}`;
    el.appendChild(s);
  });
}

// Uitlegkonstantes:
// SCALE plaas nodusse ver genoeg uitmekaar om oorvleueling te voorkom.
// PAD_Y laat ruimte bo-aan vir die vloertitel, sodat dit nie ’n nodusetiket oorvleuel nie.
const SCALE = 15;
const PAD_X = 55;
const PAD_Y = 90;
const px = (n) => n.x * SCALE + PAD_X;
const py = (n) => n.y * SCALE + PAD_Y;

function renderPlan() {
  const svg = document.getElementById("plan");
  const NS = "http://www.w3.org/2000/svg";
  svg.innerHTML = "";

  const oorsigModus = huidigeVloer === OORSIG_ID;
  // In oorsigmodus word elke vloer se nodusse in lae op dieselfde kaart vertoon
  // (die hele kampus deel reeds een koördinaatstelsel: hysbakke en trappe het doelbewus 
  // identiese x/y oor vloere heen). Andersins word net die huidige vloer se nodusse gewys.
  const vloerNodes = oorsigModus
    ? [...new Map(nodes.map((n) => [`${n.x},${n.y}`, n])).values()]
    : nodes.filter((n) => n.vloer === huidigeVloer);
  const vloerLyne = [];
  const geplaasdeEtikette = [];
  const highlightSet = new Set(
    laasteResultaat && laasteResultaat.path ? laasteResultaat.path : [],
  );
  const blockedSet = new Set(aktieweInsident.blocked_node_ids || []);
  const verligRande = new Set();
  if (laasteResultaat && laasteResultaat.path) {
    const p = laasteResultaat.path;
    for (let i = 0; i < p.length - 1; i++) {
      verligRande.add(p[i] + "|" + p[i + 1]);
      verligRande.add(p[i + 1] + "|" + p[i]);
    }
  }
  // Bepaal die posisie om 'n nodus te teken.
  const vertoonPosisie = (n) => ({ x: px(n), y: py(n) });

  // Teken rande — in oorsigmodus word alle vloere se gange, lugbrûe en
  // tonnels gewys (vertikale hysbak-/trap-rande word oorgeslaan omdat hul
  // eindpunte doelbewus saamval en dus as onsigbare stippellyne sou teken);
  // andersins net die huidige vloer se rande.
  randRye.forEach(([van, na, tipe]) => {
    const magTeken = oorsigModus
      ? tipe !== "HUISBAK" && tipe !== "TRAPPE"
      : nodeById[van].vloer === huidigeVloer &&
      nodeById[na].vloer === huidigeVloer;
    if (magTeken) {
      const a = nodeById[van],
        b = nodeById[na];
      const aPos = vertoonPosisie(a);
      const bPos = vertoonPosisie(b);
      vloerLyne.push({ x1: aPos.x, y1: aPos.y, x2: bPos.x, y2: bPos.y });
      const isHl = verligRande.has(van + "|" + na);
      // 'n Rand word rooi geteken as BEIDE eindpunte geblokkeer is —
      // dit wys die geslote area as 'n samehangende rooi sone eerder
      // as net geïsoleerde rooi kolle.
      const isBlocked = blockedSet.has(van) && blockedSet.has(na);
      const line = document.createElementNS(NS, "line");
      line.setAttribute("x1", aPos.x);
      line.setAttribute("y1", aPos.y);
      line.setAttribute("x2", bPos.x);
      line.setAttribute("y2", bPos.y);
      line.setAttribute(
        "stroke",
        isHl ? "#FFB100" : isBlocked ? "#D94B4B" : RAND_KLEURE[tipe] || "#ccc",
      );
      line.setAttribute("stroke-width", isHl ? 5 : isBlocked ? 3.5 : 2.2);
      if (isHl || isBlocked) {
        line.setAttribute("stroke-linecap", "round");
      }
      if (oorsigModus) line.setAttribute("opacity", "0.75");
      svg.appendChild(line);
    }
  });

  // Teken die nodusse met ’n soliede buitelyn sodat hulle duidelik sigbaar bly.
  // Plaas elke etiket onder of, waar nodig, bo die nodus om oorvleueling
  // met aangrensende etikette en ganglyne te beperk.
  vloerNodes.forEach((n, i) => {
    const posisie = vertoonPosisie(n);
    const cx = posisie.x,
      cy = posisie.y;
    const isHl = highlightSet.has(n.id);
    const isBlocked = blockedSet.has(n.id);
    const g = document.createElementNS(NS, "g");
    g.style.cursor = isBlocked ? "not-allowed" : "pointer";
    if (isBlocked) g.classList.add("blocked-node");
    g.onclick = () => {
      if (isBlocked) return;
      const ontruim = aktieweInsident.active && aktieweInsident.ontruimings_modus;
      const keuseId = ontruim ? "beginNode" : volgendeKaartKeuse;
      const keuse = document.getElementById(keuseId);
      if (![...keuse.options].some((opsie) => opsie.value === n.id)) {
        const opsie = document.createElement("option");
        opsie.value = n.id;
        opsie.textContent = n.etiket;
        keuse.appendChild(opsie);
      }
      keuse.value = n.id;
      volgendeKaartKeuse = keuseId === "beginNode" ? "endNode" : "beginNode";
      wisRoete();
    };

    if (oorsigModus) {
      const vloerHalo = document.createElementNS(NS, "circle");
      vloerHalo.setAttribute("cx", cx);
      vloerHalo.setAttribute("cy", cy);
      vloerHalo.setAttribute("r", isHl ? 13 : 10);
      vloerHalo.setAttribute("fill", "none");
      vloerHalo.setAttribute("stroke", VLOER_KLEURE[n.vloer]);
      vloerHalo.setAttribute("stroke-width", 2.5);
      vloerHalo.setAttribute("opacity", "0.9");
      g.appendChild(vloerHalo);
    }

    if (n.beperkte) {
      const ring = document.createElementNS(NS, "circle");
      ring.setAttribute("cx", cx);
      ring.setAttribute("cy", cy);
      ring.setAttribute("r", isHl ? 15 : 11);
      ring.setAttribute("fill", "none");
      ring.setAttribute(
        "stroke",
        n.beperkte === "SLEGS_ICU" ? "#E14B4B" : "#6D5DD3",
      );
      ring.setAttribute("stroke-width", 1.6);
      ring.setAttribute("stroke-dasharray", "3,3");
      svg.appendChild(ring);
    }

    const circle = document.createElementNS(NS, "circle");
    circle.setAttribute("cx", cx);
    circle.setAttribute("cy", cy);
    circle.setAttribute("r", isHl ? 9 : 6.5);
    circle.setAttribute("fill", isBlocked ? "#E14B4B" : NODE_KLEURE[n.tipe] || "#333");
    circle.setAttribute("stroke", isBlocked ? "#7b1414" : isHl ? "#FFB100" : "#fff");
    circle.setAttribute("stroke-width", isBlocked || isHl ? 2.4 : 1.2);
    g.appendChild(circle);

    // Probeer verskeie posisies en kies die een met die minste botsings.
    const etiketPosisies = [
      { dx: 0, dy: 20, anchor: "middle" },
      { dx: 0, dy: -21, anchor: "middle" },
      { dx: 14, dy: -5, anchor: "start" },
      { dx: -14, dy: -5, anchor: "end" },
      { dx: 12, dy: 18, anchor: "start" },
      { dx: -12, dy: 18, anchor: "end" },
      { dx: 12, dy: -18, anchor: "start" },
      { dx: -12, dy: -18, anchor: "end" },
    ];
    const beginPosisie = i % 4;
    const kandidaatPosisies = [
      ...etiketPosisies.slice(beginPosisie, 4),
      ...etiketPosisies.slice(0, beginPosisie),
      ...etiketPosisies.slice(4),
    ];
    const etiket = n.etiket + (isBlocked ? " [GESLUIT]" : n.beperkte ? ` [${n.beperkte}]` : "");
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
    text.setAttribute("font-size", "9");
    text.setAttribute("font-family", "Inter, sans-serif");
    text.setAttribute("fill", "#12222E");
    text.setAttribute("paint-order", "stroke");
    text.setAttribute("stroke", "#E7EEF2");
    text.setAttribute("stroke-width", "3");
    etiketLyne.forEach((lyn, lynNommer) => {
      const tspan = document.createElementNS(NS, "tspan");
      tspan.setAttribute("dy", lynNommer === 0 ? 0 : 11);
      tspan.textContent = lyn;
      text.appendChild(tspan);
    });
    g.appendChild(text);
    svg.appendChild(g);

    // -----------------------------------------------------------------------
    // Geometriese hulpfunksies vir etiketplasing
    // -----------------------------------------------------------------------

    // Botsingstoets vir twee asbelynde reghoeke (AABB).
    // Teorie: twee reghoeke oorvleuel as en slegs as hulle BEIDE op die
    // x-as EN op die y-as oormekaar projekteer. Die "spasie"-buffer
    // vergroot elke reghoek effektief sodat etikette 'n minimumwit-
    // ruimte tussen mekaar behou (verstekwaarde: 3px).
    const reghoekeOorvleuel = (a, b, spasie = 3) =>
      a.x < b.x + b.width + spasie &&
      a.x + a.width + spasie > b.x &&
      a.y < b.y + b.height + spasie &&
      a.y + a.height + spasie > b.y;
    
    // Toets of 'n punt (x, y) binne 'n asbelynde reghoek b val.
    // Die spasie-buffer vergroot die reghoek sodat nodusse wat naby
    // maar nie binne die etiketteks val nie, steeds as "botsing" beskou word.
    const puntInReghoek = (x, y, b, spasie = 2) =>
      x >= b.x - spasie &&
      x <= b.x + b.width + spasie &&
      y >= b.y - spasie &&
      y <= b.y + b.height + spasie;
    
    // Kruisproduk-oriëntasietoets (skaalmaat van die 2D kruisproduk AB × AC).
    // Bereken die z-komponent van die kruisproduk van vektore AB en AC:
    //   AB = (bx-ax, by-ay),  AC = (cx-ax, cy-ay)
    //   z  = (bx-ax)(cy-ay) - (by-ay)(cx-ax)
    // Interpretasie van die teken:
    //   > 0 : C lê links van AB  (teenkloksgewys)
    //   < 0 : C lê regs van AB   (kloksgewys)
    //   = 0 : A, B, C is kollineêr (op een lyn)
    // Bepaal aan watter kant van 'n lynstuk die ander segment se eindpunte lê.
    const orientasie = (ax, ay, bx, by, cx2, cy2) =>
      (bx - ax) * (cy2 - ay) - (by - ay) * (cx2 - ax);

    // Toets of lynsegmente AB en CD mekaar sny met kruisprodukte:
    //   Stap 1 — Begrensingskastoets: as die begrensings-
    //            kasse van AB en CD nie oorvleuel nie, kan die segmente onmoontlik
    //            kruis — goedkoop vroeë afwysing.
    //   Stap 2 — Oriëntasietoets: segment AB sny CD as en slegs as C en D aan
    //            TEENOORGESTELDE kante van lyn AB lê (orientasie-produkte ≤ 0),
    //            EN A en B aan teenoorgestelde kante van CD lê.
    //            Die ≤ 0 (eerder as < 0) dek die randgeval waar eindpunte
    //            presies op die teenoorgestelde segment lê (kollineêr).
    const segmenteKruis = (a, b, c, d) =>
      Math.max(a.x, b.x) >= Math.min(c.x, d.x) &&
      Math.max(c.x, d.x) >= Math.min(a.x, b.x) &&
      Math.max(a.y, b.y) >= Math.min(c.y, d.y) &&
      Math.max(c.y, d.y) >= Math.min(a.y, b.y) &&
      orientasie(a.x, a.y, b.x, b.y, c.x, c.y) *
      orientasie(a.x, a.y, b.x, b.y, d.x, d.y) <=
      0 &&
      orientasie(c.x, c.y, d.x, d.y, a.x, a.y) *
      orientasie(c.x, c.y, d.x, d.y, b.x, b.y) <=
      0;
    
    // Toets of 'n lynstuk 'n asbelynde reghoek sny.
    // Tweeledige strategie:
    //   1. Vinnige geval: as ENIGE eindpunt van die lyn binne die reghoek
    //      val (puntInReghoek), kruis die lyn noodwendig die reghoek.
    //   2. Randgeval: 'n lyn kan deur 'n reghoek steek sonder dat enige
    //      eindpunt daarin val (bv. 'n diagonale lyn wat hoek tot hoek
    //      deurstoot). Vir hierdie geval word segmenteKruis() geroep teen
    //      elkeen van die vier sye van die reghoek (gedefinieer as vier
    //      opeenvolgende hoekpunte) — as enige sy gesny word, gee true terug.
    const lynKruisReghoek = (lyn, b) => {
      if (
        puntInReghoek(lyn.x1, lyn.y1, b) ||
        puntInReghoek(lyn.x2, lyn.y2, b)
      ) {
        return true;
      }
      const hoeke = [
        { x: b.x, y: b.y },
        { x: b.x + b.width, y: b.y },
        { x: b.x + b.width, y: b.y + b.height },
        { x: b.x, y: b.y + b.height },
      ];
      const begin = { x: lyn.x1, y: lyn.y1 };
      const einde = { x: lyn.x2, y: lyn.y2 };
      return hoeke.some((hoek, hoekNommer) =>
        segmenteKruis(
          begin,
          einde,
          hoek,
          hoeke[(hoekNommer + 1) % hoeke.length],
        ),
      );
    };

    // -----------------------------------------------------------------------
    // Kandidaat-posisie-tellingslus
    // Elke kandidaatposisie kry 'n botsingtelling; die laagste telling wen.
    // Groter strawwe gee voorkeur aan leesbare etikette binne die kaart.
    //
    //   kandidaatNommer (+0 … +7)
    //     Kies vroeë kandidate as alles gelyk is — beslis gelykopuitslae
    //     ten gunste van voorspelbare visuele uitleg.
    //
    //   Buite SVG-grense (+100 000 per oortreding)
    //     'n Etiket buite die tekengebied kry 'n swaar straf.
    //
    //   Ander-etiket-botsings (+10 000 elk)
    //     Etikette oor mekaar is erger as 'n etiket oor 'n noduspunt —
    //     dit maak die kaart onleesbaar vir meer mense tegelyk.
    //
    //   Noduspunt binne etiket (+3 000 elk)
    //     'n Etiket wat 'n noduspunt oorvleuel verbloem die grafiek-
    //     topologie, maar is minder erg as tekste wat mekaar dek.
    //
    //   Ganglyn kruis etiket (+500 elk)
    //     Ganglyne wat agter etiketteks deurloop is visueel hinderlik,
    //     maar aanvaarbaar as geen beter posisie beskikbaar is nie.
    // -----------------------------------------------------------------------

    let beste = null;
    kandidaatPosisies.forEach((posisie, kandidaatNommer) => {
      const x = cx + posisie.dx;
      const y = cy + posisie.dy;
      text.setAttribute("x", x);
      text.setAttribute("y", y);
      text.setAttribute("text-anchor", posisie.anchor);
      [...text.children].forEach((tspan) => tspan.setAttribute("x", x));

      // Gebruik die kandidaatindeks om gelykopuitslae voorspelbaar te beslis.
      const boks = text.getBBox();
      // Straf swaar as enige deel van die etiket buite die SVG-tekengebied val.
      let telling = kandidaatNommer;
      if (
        boks.x < 8 ||
        boks.y < 42 ||
        boks.x + boks.width > 772 ||
        boks.y + boks.height > 552
      ) {
        telling += 100000;
      }
      // Etiket-op-etiket oorvleueling: hoogste prioriteit na buiteperke.
      telling +=
        geplaasdeEtikette.filter((ander) =>
          reghoekeOorvleuel(boks, ander, 5),
        ).length * 10000;
      // Noduspunt binne die etiketteks: tweede prioriteit.
      telling +=
        vloerNodes.filter(
          (ander) => {
            const anderPosisie = vertoonPosisie(ander);
            return ander.id !== n.id &&
              puntInReghoek(anderPosisie.x, anderPosisie.y, boks, 9);
          },
        ).length * 3000;
      // Ganglyn wat die etiket kruis: laagste prioriteit.
      telling +=
        vloerLyne.filter((lyn) => lynKruisReghoek(lyn, boks)).length * 500;

      if (!beste || telling < beste.telling) {
        beste = {
          posisie,
          x,
          y,
          telling,
          boks: {
            x: boks.x,
            y: boks.y,
            width: boks.width,
            height: boks.height,
          },
        };
      }
    });

    text.setAttribute("x", beste.x);
    text.setAttribute("y", beste.y);
    text.setAttribute("text-anchor", beste.posisie.anchor);
    [...text.children].forEach((tspan) => tspan.setAttribute("x", beste.x));
    geplaasdeEtikette.push(beste.boks);
  });

  const title = document.createElementNS(NS, "text");
  const f = vloerById[huidigeVloer];
  title.setAttribute("x", 20);
  title.setAttribute("y", 28);
  title.setAttribute("font-size", "15");
  title.setAttribute("font-weight", "700");
  title.setAttribute("font-family", "Space Grotesk, sans-serif");
  title.setAttribute("fill", "#12222E");
  // In oorsigmodus is huidigeVloer === OORSIG_ID, wat nie in vloerById bestaan nie.
  // Gebruik 'n veilige terugvalwaarde sodat die funksie nie misluk nie.
  title.textContent = f ? `${f.gebou} — ${f.naam}` : "Oorsig — Alle Vloere";
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
    const nota = document.createElement("div");
    nota.className = "empty-note";
    nota.textContent = laasteResultaat.message;
    el.appendChild(nota);
    return;
  }
  if (!laasteResultaat.path) {
    el.innerHTML = '<div class="empty-note">Geen roete gevind nie.</div>';
    return;
  }
  // As ons in ontruimingsmodus is, wys die nooduitgang se naam prominent.
  if (laasteResultaat.uitgang) {
    const uitgang = nodeById[laasteResultaat.uitgang];
    const uitEl = document.createElement("div");
    uitEl.style.cssText = "background:#8f2525;color:#fff;border-radius:6px;padding:8px 10px;margin-bottom:10px;font-family:'IBM Plex Mono',monospace;font-size:12px;";
    uitEl.textContent = `🚨 Nooduitgang: ${uitgang ? uitgang.etiket : laasteResultaat.uitgang}`;
    el.appendChild(uitEl);
  }

  const ul = document.createElement("ul");
  ul.className = "route-list";
  laasteResultaat.path.forEach((id, i) => {
    const n = nodeById[id];
    const li = document.createElement("li");
    const etiket = document.createElement("span");
    etiket.textContent = `${i + 1}. ${n?.etiket || id}`;
    const vloer = document.createElement("span");
    vloer.className = "t";
    vloer.textContent = n ? `${vloerById[n.vloer].gebou} Vlak ${vloerById[n.vloer].level}` : "";
    li.append(etiket, vloer);
    li.onclick = () => {
      if (!n) return;
      huidigeVloer = n.vloer;
      renderAll();
    };
    ul.appendChild(li);
  });
  el.appendChild(ul);
  [
    ["Totale tyd", laasteResultaat.formattedCost],
    ["Totale afstand", laasteResultaat.formattedDistance],
  ].forEach(([naam, waarde]) => {
    const ry = document.createElement("div");
    ry.className = "route-total";
    const etiket = document.createElement("span");
    etiket.textContent = naam;
    const totaal = document.createElement("span");
    totaal.textContent = waarde ?? "Onbekend";
    ry.append(etiket, totaal);
    el.appendChild(ry);
  });
}

function renderStatus() {
  const el = document.getElementById("status");
  if (!laasteResultaat) {
    el.textContent = "";
    el.className = "status";
    return;
  }
  if (laasteResultaat.error === "blocked") {
    el.textContent = `⛔ Roete geblokkeer (${laasteResultaat.status}): ${laasteResultaat.message}`;
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
    el.textContent = `✓ Roete gevind: ${laasteResultaat.nodeCount} nodus(se), ${laasteResultaat.formattedCost}, ${laasteResultaat.formattedDistance}.`;
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

function wisRoete() {
  // Laat antwoorde vir 'n vorige keuse mag nie 'n nuwe keuse of herstel oorskryf nie.
  roeteVersoek++;
  roeteBesig = false;
  laasteResultaat = null;
  const knoppie = document.getElementById("findBtn");
  knoppie.disabled = false;
  knoppie.textContent = "Vind Roete";
  renderAll();
}

document.getElementById("findBtn").onclick = async () => {
  const versoek = ++roeteVersoek;
  roeteBesig = true;
  laasteResultaat = null;
  renderAll();
  const btn = document.getElementById("findBtn");
  btn.disabled = true;
  btn.textContent = "Soek...";
  document.getElementById("status").textContent = "⏳ Bereken roete...";
  document.getElementById("status").className = "status";

  try {
    // Herbevestig sluitings voor elke roete, ook wanneer die blad lank oop was.
    if (!(await laaiInsident(false)) || versoek !== roeteVersoek) return;
    const begin = bestemmingId("beginNode");
    const end = bestemmingId("endNode");
    const ut = document.getElementById("gebruikerTipe").value;
    const apiBase = document.getElementById("apiUrl").value.trim();
    const ontruimModus = aktieweInsident.active && aktieweInsident.ontruimings_modus;
    if (!begin || (!end && !ontruimModus)) {
      laasteResultaat = {
        error: "invalid",
        message: ontruimModus
          ? "Kies asseblief 'n geldige beginpunt uit die soeklys."
          : "Kies asseblief 'n geldige beginpunt en bestemming uit die soeklys.",
      };
      return;
    }
    const resultaat = await fetchRoute(apiBase, begin, end, ut);
    if (versoek !== roeteVersoek) return;
    laasteResultaat = resultaat;
    if (resultaat.path && nodeById[begin]) huidigeVloer = nodeById[begin].vloer;
  } catch (_) {
    if (versoek === roeteVersoek) {
      laasteResultaat = { error: "network", message: "Die roete kon nie bereken word nie. Probeer asseblief weer." };
    }
  } finally {
    if (versoek === roeteVersoek) {
      roeteBesig = false;
      btn.disabled = false;
      btn.textContent = "Vind Roete";
      renderAll();
    }
  }
};
document.getElementById("clearBtn").onclick = () => {
  volgendeKaartKeuse = "beginNode";
  wisRoete();
};

["beginNode", "endNode", "gebruikerTipe"].forEach((id) => {
  document.getElementById(id).addEventListener("change", wisRoete);
});
document.getElementById("apiUrl").addEventListener("change", () => {
  wisRoete();
  laaiBestemmings(document.getElementById("beginSoek").value, "beginNode");
  laaiBestemmings(document.getElementById("eindSoek").value, "endNode");
  laaiInsident();
});

// Gebruik die blad se bediener; 'n plaaslike HTML-voorskou kan die adres handmatig stel.
if (/^https?:$/.test(window.location.protocol)) {
  document.getElementById("apiUrl").value = window.location.origin;
}
renderLegend();
renderAll();
populateSelects();
laaiInsident();
// Hou reeds oop kaarte op datum nadat 'n administrateur 'n insident verander.
setInterval(() => {
  if (!document.hidden && !roeteBesig) laaiInsident();
}, 15000);
