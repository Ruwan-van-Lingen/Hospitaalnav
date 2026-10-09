/**===========================================================================================
 * hospitaal_wayfinder.js
 * =======================
 * Interaktiewe webkoppelvlak vir die Hospitaalnavigasiestelsel (/ui).
 *
 * Hierdie lêer bevat:
 *   • Kaartdata (nodusse, rande, vloere, geboue) wat by opstart van die
 *     bediener se GET /kaart gelaai word (die databasis is die enigste bron)
 *     en kliëntkant gebruik word vir SVG-tekening.
 *   • Roeteberekening via die FastAPI-agterkant (/route). Tydens ontruiming
 *     skakel die bediener self oor na die naaste nooduitgang.
 *     A* loop bedienerkant (HospitaalGrafiek.py) — hierdie lêer stuur
 *     slegs die versoek en vertoon die resultaat.
 *   • SVG-vloerplan-tekening: nodusse, rande, paduitligging, etiketplasing.
 *   • Vloer-oortjies en die hysbak-styl vloerindikator (sykolom).
 *   • Soekveld-integrasie met /destinations vir mensleesbare bestemmings.
 *   • Ontruimingsmodus-ondersteuning: die waarskuwingsbanier, die gedeaktiveerde
 *     bestemmingskeuse en die nooduitgang-blokkie in die roetepaneel.
 *
 * Kaart-oorsigmodus (OORSIG_ID)
 * --------------------------------
 * Die "Oorsig — Alle Vloere"-oortjie vertoon alle vloere in lae op een SVG-kaart.
 * Hysbak- en traphuisnodusse wat deur vertikale rande verbind is, vorm een
 * visuele groep met 'n gedeelde etiket. Elke vloer se kleiner noduspunt bly
 * afsonderlik klikbaar. Ander gelaagde nodusse kry klein vloerverskuiwings.
 *
 * Etiketplasing
 * -----------------
 * Die plasingsalgoritme probeer 8 kandidaatposisies per etiket en kies
 * die posisie met die minste botsings teen ander etikette, noduspunte en
 * ganglyne. Dit verhoed dat etikette oor mekaar of oor punte lê.
 */


// Kaartdata word by opstart deur laaiKaart() uit die bediener (GET /kaart) gevul.
// Dit is doelbewus nie hier ingetik nie: die databasis is die enigste bron,
// sodat die kaart en die roete-algoritmes nooit verskillende data sien nie.
let geboue = [];
let vloere = [];
let nodes = [];
// Volgorde: begin, einde, randtipe (die kaart het net dit nodig om te teken).
let randRye = [];

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
// Word in bouKaartIndekse() gevul sodra die vloere gelaai is.
let VLOER_KLEURE = {};

/* ============================================================
   NODUS- EN VLOERINDEKSE — slegs vir die tekening van die vloerplan.
   Die FastAPI-roete-eindpunt bereken die roete op die bediener.
   ============================================================ */
// Word in bouKaartIndekse() gevul nadat die kaart gelaai is.
let nodeById = {};
let vloerById = {};

/**
 * Bou groepe uit werklike vertikale rande eerder as uit soortgelyke name.
 * Só word slegs dieselfde fisiese hysbak of traphuis oor verskillende vloere
 * saamgegroepeer; toevallige gelyke koördinate bly aparte plekke.
 */
function bouVertikaleGroepe() {
  const bure = new Map();
  randRye.forEach(([van, na, tipe]) => {
    if (tipe !== "HUISBAK" && tipe !== "TRAPPE") return;
    if (!bure.has(van)) bure.set(van, []);
    if (!bure.has(na)) bure.set(na, []);
    bure.get(van).push(na);
    bure.get(na).push(van);
  });

  const besoek = new Set();
  const groepe = [];
  bure.forEach((_, beginId) => {
    if (besoek.has(beginId)) return;
    const stapel = [beginId];
    const nodusse = [];
    while (stapel.length) {
      const id = stapel.pop();
      if (besoek.has(id)) continue;
      besoek.add(id);
      nodusse.push(nodeById[id]);
      (bure.get(id) || []).forEach((buurId) => stapel.push(buurId));
    }

    nodusse.sort(
      (a, b) => vloerById[a.vloer].level - vloerById[b.vloer].level,
    );
    const leier = nodusse[0];
    groepe.push({
      id: `VERTIKAAL-${leier.id}`,
      naam: leier.etiket,
      leier,
      nodusse,
    });
  });
  return groepe;
}

let vertikaleGroepe = [];
let vertikaleGroepByNode = {};

/**
 * Bou al die naslaantabelle uit die gelaaide kaartdata. Moet elke keer loop
 * nadat nodes, vloere en randRye gevul is, want hulle hang almal daarvan af.
 */
function bouKaartIndekse() {
  nodeById = Object.fromEntries(nodes.map((n) => [n.id, n]));
  vloerById = Object.fromEntries(vloere.map((f) => [f.id, f]));
  VLOER_KLEURE = Object.fromEntries(
    vloere.map((f, i) => [f.id, VLOER_KLEURE_PALET[i % VLOER_KLEURE_PALET.length]]),
  );
  vertikaleGroepe = bouVertikaleGroepe();
  vertikaleGroepByNode = Object.fromEntries(
    vertikaleGroepe.flatMap((groep) =>
      groep.nodusse.map((nodus) => [nodus.id, groep]),
    ),
  );
}

/**
 * Haal die kaart van die bediener en vul die kaartveranderlikes.
 * Gooi 'n fout as die bediener nie bereik kan word of 'n fout terugstuur nie;
 * die aanroeper wys dan 'n foutboodskap.
 */
async function laaiKaart() {
  const apiBase = document.getElementById("apiUrl").value.trim();
  const response = await fetch(`${apiBase.replace(/\/$/, "")}/kaart`);
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  const data = await response.json();

  // Hernoem die databasiskolomme na die kort name wat die tekenkode gebruik.
  geboue = data.geboue.map((g) => ({ id: g.gebou_id, naam: g.naam }));
  vloere = data.vloere.map((v) => ({
    id: v.vloer_id,
    gebou: v.gebou_id,
    level: v.level_nommer,
    naam: v.naam,
  }));
  nodes = data.nodes.map((n) => ({
    id: n.node_id,
    vloer: n.vloer_id,
    tipe: n.tipe_kode,
    etiket: n.etiket,
    x: n.pos_x,
    y: n.pos_y,
    beperkte: n.beperkte_groep,
  }));
  randRye = data.rande.map((r) => [r.van_node, r.na_node, r.rand_tipe]);
  bouKaartIndekse();
}

async function fetchRoute(apiBase, beginId, eindeId, gebruikerTipe) {
  const basis = apiBase.replace(/\/$/, "");

  // Die bediener besluit self of dit 'n gewone roete of 'n ontruiming is, op
  // grond van die insident wat op daardie oomblik aktief is. Tydens ontruiming
  // word die bestemming geïgnoreer; ons stuur dan die beginpunt as plekhouer,
  // omdat die bestemmingskeuse gedeaktiveer en dalk leeg is maar /route 'n
  // doel vereis.
  const doel = eindeId || beginId;
  const url = `${basis}/route?begin=${encodeURIComponent(beginId)}&doel=${encodeURIComponent(doel)}&gebruiker_tipe=${encodeURIComponent(gebruikerTipe)}`;

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

/** Formateer 'n kaartnodus presies soos 'n bestemming wat vanaf die API kom. */
function kaartNodusEtiket(nodus) {
  const vloer = vloerById[nodus.vloer];
  const gebou = geboue.find((item) => item.id === vloer?.gebou);
  return `${nodus.etiket} — ${gebou?.naam || "Onbekende gebou"}, ${vloer?.naam || nodus.vloer} (${nodus.id})`;
}

/** Voeg 'n geklikte nodus by 'n keuselys indien die soekresultate dit nie bevat nie. */
function versekerNodusOpsie(keuse, nodus) {
  if (![...keuse.options].some((opsie) => opsie.value === nodus.id)) {
    const opsie = document.createElement("option");
    opsie.value = nodus.id;
    opsie.textContent = kaartNodusEtiket(nodus);
    keuse.appendChild(opsie);
  }
}

/**
 * Eerste kaartklik kies die bron; die volgende geldige, ander nodus kies die bestemming.
 * Daarna begin die siklus weer by die bron. In ontruimingsmodus word slegs 'n bron gekies.
 */
function kiesNodusOpKaart(nodus, isGeblokkeer = false) {
  if (isGeblokkeer) return;

  const ontruim = aktieweInsident.active && aktieweInsident.ontruimings_modus;
  const keuseId = ontruim ? "beginNode" : volgendeKaartKeuse;
  const begin = document.getElementById("beginNode");
  const status = document.getElementById("status");

  if (keuseId === "endNode" && nodus.id === begin.value) {
    status.textContent = "⚠ Kies 'n ander nodus as bestemming.";
    status.className = "status blocked";
    return;
  }

  const keuse = document.getElementById(keuseId);
  versekerNodusOpsie(keuse, nodus);
  keuse.value = nodus.id;

  const soekId = keuseId === "beginNode" ? "beginSoek" : "eindSoek";
  document.getElementById(soekId).value = nodus.etiket;

  volgendeKaartKeuse = ontruim || keuseId === "endNode" ? "beginNode" : "endNode";
  wisRoete();

  if (ontruim) {
    status.textContent = `Bron gekies: ${nodus.etiket}. Kies “Vind Roete” vir die naaste uitgang.`;
  } else if (keuseId === "beginNode") {
    status.textContent = `Bron gekies: ${nodus.etiket}. Klik nou op 'n bestemming.`;
  } else {
    status.textContent = `Bestemming gekies: ${nodus.etiket}. Die roete is gereed om bereken te word.`;
  }
  status.className = "status ok";
}

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

/** Gee die stel vloer-ID's waardeur die huidige roete loop (leeg as daar geen roete is nie). */
function kryRoeterVloere() {
  if (!laasteResultaat || !laasteResultaat.path) return new Set();
  return new Set(laasteResultaat.path.map((id) => nodeById[id]?.vloer).filter(Boolean));
}

function renderTabs() {
  const tabsEl = document.getElementById("tabs");
  tabsEl.innerHTML = "";
  const roeterVloere = kryRoeterVloere();

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
  const roeterVloere = kryRoeterVloere();
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

// Uitleggrense stem met die SVG se viewBox ooreen. Ruim kantmarges keer dat
// lang departementname buite die kaart afgesny word.
const KAART_BREEDTE = 780;
const KAART_HOOGTE = 560;
const KAART_MARGE_X = 115;
const KAART_BO_MARGE = 78;
const KAART_ONDER_MARGE = 62;
const MAKS_SKaal = 14;
const OORSIG_VERSKUIWINGS = [
  { x: -28, y: -22 },
  { x: 0, y: -30 },
  { x: 28, y: -22 },
  { x: -20, y: 24 },
  { x: 20, y: 24 },
];

/** Breek 'n lang kaartetiket by woordgrense in kort, leesbare lyne. */
function breekEtiketLyne(teks, maksimumKarakters = 20, maksimumLyne = 3) {
  const lyne = [];
  teks.split(/\s+/).filter(Boolean).forEach((woord) => {
    const huidige = lyne[lyne.length - 1];
    if (!huidige || (`${huidige} ${woord}`).length > maksimumKarakters) {
      lyne.push(woord);
    } else {
      lyne[lyne.length - 1] = `${huidige} ${woord}`;
    }
  });
  if (lyne.length <= maksimumLyne) return lyne;
  return [
    ...lyne.slice(0, maksimumLyne - 1),
    lyne.slice(maksimumLyne - 1).join(" "),
  ];
}

/** Plaas die vloerlede van 'n vertikale groep rondom een gedeelde middelpunt. */
function vertikaleGroepVerskuiwing(groep, nodus) {
  const indeks = groep.nodusse.findIndex((item) => item.id === nodus.id);
  const totaal = groep.nodusse.length;
  const hoek = -Math.PI / 2 + (2 * Math.PI * indeks) / totaal;
  const radius = totaal === 2 ? 8 : 10;
  return {
    x: Math.cos(hoek) * radius,
    y: Math.sin(hoek) * radius,
  };
}

// Verskeie moontlike plekke vir 'n etiket relatief tot sy nodus. Nader
// posisies word eerste probeer; die verder posisies skakel die laaste
// oorvleuelings in digte oorsigaansigte uit.
const ETIKET_POSISIES = [
  { dx: 0, dy: 24, anchor: "middle" },
  { dx: 0, dy: -26, anchor: "middle" },
  { dx: 18, dy: -4, anchor: "start" },
  { dx: -18, dy: -4, anchor: "end" },
  { dx: 22, dy: 20, anchor: "start" },
  { dx: -22, dy: 20, anchor: "end" },
  { dx: 22, dy: -20, anchor: "start" },
  { dx: -22, dy: -20, anchor: "end" },
  { dx: 0, dy: 39, anchor: "middle" },
  { dx: 0, dy: -41, anchor: "middle" },
  { dx: 34, dy: 3, anchor: "start" },
  { dx: -34, dy: 3, anchor: "end" },
  { dx: 44, dy: 24, anchor: "start" },
  { dx: -44, dy: 24, anchor: "end" },
  { dx: 44, dy: -24, anchor: "start" },
  { dx: -44, dy: -24, anchor: "end" },
  { dx: 0, dy: 54, anchor: "middle" },
  { dx: 0, dy: -56, anchor: "middle" },
];

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

function renderPlan() {
  const svg = document.getElementById("plan");
  const NS = "http://www.w3.org/2000/svg";
  svg.innerHTML = "";

  const oorsigModus = huidigeVloer === OORSIG_ID;
  // In oorsigmodus word ALLE nodusse geteken. Vertikale vervoer word visueel
  // gegroepeer; ander gelaagde nodusse kry klein vloerverskuiwings.
  const vloerNodes = oorsigModus
    ? nodes
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
  // Pas die huidige aansig dinamies binne die kaart. Elke vloer gebruik dus die
  // beskikbare ruimte, terwyl die volledige kampus steeds veilig binnepas.
  const xWaardes = vloerNodes.map((n) => n.x);
  const yWaardes = vloerNodes.map((n) => n.y);
  const minimumX = Math.min(...xWaardes);
  const maksimumX = Math.max(...xWaardes);
  const minimumY = Math.min(...yWaardes);
  const maksimumY = Math.max(...yWaardes);
  const spanX = Math.max(maksimumX - minimumX, 1);
  const spanY = Math.max(maksimumY - minimumY, 1);
  const beskikbareBreedte = KAART_BREEDTE - 2 * KAART_MARGE_X;
  const beskikbareHoogte = KAART_HOOGTE - KAART_BO_MARGE - KAART_ONDER_MARGE;
  const skaal = Math.min(
    MAKS_SKaal,
    beskikbareBreedte / spanX,
    beskikbareHoogte / spanY,
  );
  const inhoudBreedte = spanX * skaal;
  const inhoudHoogte = spanY * skaal;
  const oorsprongX = KAART_MARGE_X + (beskikbareBreedte - inhoudBreedte) / 2;
  const oorsprongY = KAART_BO_MARGE + (beskikbareHoogte - inhoudHoogte) / 2;
  const vloerIndeks = Object.fromEntries(vloere.map((vloer, indeks) => [vloer.id, indeks]));
  const basisPosisie = (n) => ({
    x: oorsprongX + (n.x - minimumX) * skaal,
    y: oorsprongY + (n.y - minimumY) * skaal,
  });
  const vertoonPosisie = (n) => {
    const groep = vertikaleGroepByNode[n.id];
    const verskuiwing = !oorsigModus
      ? { x: 0, y: 0 }
      : groep
        ? vertikaleGroepVerskuiwing(groep, n)
        : OORSIG_VERSKUIWINGS[vloerIndeks[n.vloer] % OORSIG_VERSKUIWINGS.length];
    const basis = basisPosisie(n);
    return {
      x: basis.x + verskuiwing.x,
      y: basis.y + verskuiwing.y,
    };
  };
  // Oorsigrande eindig by die groep se enkele middelpunt. Wanneer die groep
  // met sweef oopvou, bly die lyne dus netjies aan die groep gekoppel.
  const randPosisie = (n) =>
    oorsigModus && vertikaleGroepByNode[n.id]
      ? basisPosisie(n)
      : vertoonPosisie(n);

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
      const aPos = randPosisie(a);
      const bPos = randPosisie(b);
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

  // Elke vertikale groep kry een SVG-houer. Die houer wys normaalweg net die
  // saamgestelde middelpunt en vou sy vloerlede oop wanneer die gebruiker sweef.
  const groepVertoonToestande = new Map();
  if (oorsigModus) {
    vertikaleGroepe.forEach((groep) => {
      const houer = document.createElementNS(NS, "g");
      houer.dataset.vertikaleGroep = groep.id;
      houer.style.cursor = "pointer";
      const toestand = {
        houer,
        lede: [],
        leierPunte: [],
        saamgevouElemente: [],
      };
      const stelOop = (isOop) => {
        toestand.lede.forEach((lid, indeks) => {
          lid.style.display = isOop || indeks === 0 ? "" : "none";
        });
        toestand.leierPunte.forEach((element) => {
          element.style.display = isOop ? "" : "none";
        });
        toestand.saamgevouElemente.forEach((element) => {
          element.style.display = isOop ? "none" : "";
        });
        houer.dataset.isOop = String(isOop);
      };
      houer.onmouseenter = () => stelOop(true);
      houer.onmouseleave = () => stelOop(false);
      toestand.stelOop = stelOop;
      groepVertoonToestande.set(groep.id, toestand);
      svg.appendChild(houer);
    });
  }

  // 'n Onmiddellike SVG-sweefkaart vervang lang permanente oorsigetikette.
  // Dit hou die kaart rustig sonder om enige nodusbesonderhede weg te steek.
  let aktieweHulpmiddel = null;
  const verbergHulpmiddel = () => {
    if (aktieweHulpmiddel) aktieweHulpmiddel.style.display = "none";
  };
  const wysHulpmiddel = (n, groep, cx, cy) => {
    verbergHulpmiddel();
    const vloer = vloerById[n.vloer];
    const gebou = geboue.find((item) => item.id === vloer?.gebou);
    const besonderhede = groep
      ? `${groep.nodusse.length} gekoppelde vloere: ${groep.nodusse
        .map((item) => vloerById[item.vloer].naam)
        .join(", ")}`
      : `${gebou?.naam || "Onbekende gebou"} · ${vloer?.naam || n.vloer}`;
    const lyne = [
      n.etiket,
      ...breekEtiketLyne(besonderhede, 38, 2),
      ...(n.beperkte ? [`Toegang: ${n.beperkte.replaceAll("_", " ")}`] : []),
    ];
    const breedte = Math.min(
      260,
      Math.max(150, Math.max(...lyne.map((lyn) => lyn.length)) * 5.7 + 20),
    );
    const hoogte = 18 + lyne.length * 13;
    const x = Math.max(8, Math.min(cx + 14, KAART_BREEDTE - breedte - 8));
    const y = Math.max(44, Math.min(cy - hoogte - 12, KAART_HOOGTE - hoogte - 8));
    const kaart = document.createElementNS(NS, "g");
    kaart.dataset.hulpmiddel = n.id;
    kaart.setAttribute("pointer-events", "none");

    const agtergrond = document.createElementNS(NS, "rect");
    agtergrond.setAttribute("x", x);
    agtergrond.setAttribute("y", y);
    agtergrond.setAttribute("width", breedte);
    agtergrond.setAttribute("height", hoogte);
    agtergrond.setAttribute("rx", 5);
    agtergrond.setAttribute("fill", "#102634");
    agtergrond.setAttribute("stroke", "#D9A21B");
    agtergrond.setAttribute("stroke-width", 1);
    agtergrond.setAttribute("opacity", "0.97");
    kaart.appendChild(agtergrond);

    lyne.forEach((lyn, indeks) => {
      const teks = document.createElementNS(NS, "text");
      teks.setAttribute("x", x + 10);
      teks.setAttribute("y", y + 17 + indeks * 13);
      teks.setAttribute("font-size", indeks === 0 ? "10" : "8.5");
      teks.setAttribute("font-weight", indeks === 0 ? "700" : "400");
      teks.setAttribute("font-family", "Inter, sans-serif");
      teks.setAttribute("fill", indeks === 0 ? "#fff" : "#D8E5EB");
      teks.textContent = lyn;
      kaart.appendChild(teks);
    });
    aktieweHulpmiddel = kaart;
    svg.appendChild(kaart);
  };

  // Teken die nodusse met ’n soliede buitelyn sodat hulle duidelik sigbaar bly.
  // Plaas elke etiket onder of, waar nodig, bo die nodus om oorvleueling
  // met aangrensende etikette en ganglyne te beperk.
  vloerNodes.forEach((n, i) => {
    const posisie = vertoonPosisie(n);
    const cx = posisie.x,
      cy = posisie.y;
    const groep = oorsigModus ? vertikaleGroepByNode[n.id] : null;
    const isGroepLeier = groep?.leier.id === n.id;
    const groepToestand = groep ? groepVertoonToestande.get(groep.id) : null;
    const isHl = highlightSet.has(n.id);
    const isBlocked = blockedSet.has(n.id);
    const isBegin = document.getElementById("beginNode").value === n.id;
    const isEinde = document.getElementById("endNode").value === n.id;
    const g = document.createElementNS(NS, "g");
    g.dataset.nodeId = n.id;
    g.dataset.vloer = n.vloer;
    if (groep) {
      g.dataset.groepId = groep.id;
      g.dataset.groepGrootte = String(groep.nodusse.length);
      g.dataset.groepLid = n.id;
      groepToestand.lede.push(g);
      if (!isGroepLeier) g.style.display = "none";
    }
    g.style.cursor = isBlocked ? "not-allowed" : "pointer";
    if (isBlocked) g.classList.add("blocked-node");
    if (isBegin) g.classList.add("bron-node");
    if (isEinde) g.classList.add("bestemming-node");
    g.onclick = () => kiesNodusOpKaart(n, isBlocked);
    g.onmouseenter = () => wysHulpmiddel(n, groep, cx, cy);
    g.onmouseleave = verbergHulpmiddel;

    const hulpmiddelTeks = document.createElementNS(NS, "title");
    hulpmiddelTeks.textContent = groep && isGroepLeier
      ? `${groep.naam} — ${groep.nodusse.map((item) => vloerById[item.vloer].naam).join(", ")}`
      : `${n.etiket} (${n.id})`;
    g.appendChild(hulpmiddelTeks);

    if (groep && isGroepLeier) {
      const middel = basisPosisie(n);
      const groepHalo = document.createElementNS(NS, "circle");
      groepHalo.setAttribute("cx", middel.x);
      groepHalo.setAttribute("cy", middel.y);
      groepHalo.setAttribute("r", 19);
      groepHalo.setAttribute("fill", "rgba(217, 119, 6, 0.08)");
      groepHalo.setAttribute("stroke", NODE_KLEURE[n.tipe]);
      groepHalo.setAttribute("stroke-width", 2);
      groepHalo.setAttribute("stroke-dasharray", "4,3");
      g.appendChild(groepHalo);
    }

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
      if (groep && isGroepLeier) {
        vloerHalo.style.display = "none";
        groepToestand.leierPunte.push(vloerHalo);
      }
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
    circle.setAttribute("r", isHl || isBegin || isEinde ? 9 : 6.5);
    circle.setAttribute("fill", isBlocked ? "#E14B4B" : NODE_KLEURE[n.tipe] || "#333");
    circle.setAttribute(
      "stroke",
      isBlocked ? "#7b1414" : isBegin ? "#1565C0" : isEinde ? "#2E7D32" : isHl ? "#FFB100" : "#fff",
    );
    circle.setAttribute("stroke-width", isBlocked || isHl || isBegin || isEinde ? 3 : 1.2);
    g.appendChild(circle);
    if (groep && isGroepLeier) {
      circle.style.display = "none";
      groepToestand.leierPunte.push(circle);

      const middel = basisPosisie(n);
      const saamgevouPunt = document.createElementNS(NS, "circle");
      saamgevouPunt.setAttribute("cx", middel.x);
      saamgevouPunt.setAttribute("cy", middel.y);
      saamgevouPunt.setAttribute("r", isHl || isBegin || isEinde ? 10 : 8.5);
      saamgevouPunt.setAttribute("fill", NODE_KLEURE[n.tipe]);
      saamgevouPunt.setAttribute("stroke", isHl ? "#FFB100" : "#fff");
      saamgevouPunt.setAttribute("stroke-width", isHl ? 3 : 1.8);
      g.appendChild(saamgevouPunt);

      const groepTelling = document.createElementNS(NS, "text");
      groepTelling.setAttribute("x", middel.x);
      groepTelling.setAttribute("y", middel.y + 3.2);
      groepTelling.setAttribute("text-anchor", "middle");
      groepTelling.setAttribute("font-size", "8");
      groepTelling.setAttribute("font-weight", "700");
      groepTelling.setAttribute("font-family", "Inter, sans-serif");
      groepTelling.setAttribute("fill", "#fff");
      groepTelling.setAttribute("pointer-events", "none");
      groepTelling.textContent = String(groep.nodusse.length);
      g.appendChild(groepTelling);
      groepToestand.saamgevouElemente.push(saamgevouPunt, groepTelling);
    }

    // Die groep se ander vloerlede behou hul eie klikbare punte en hulpmiddels,
    // maar slegs die leier teken die gedeelde etiket.
    if (groep && !isGroepLeier) {
      groepToestand.houer.appendChild(g);
      return;
    }

    // Aansluitings se lang name word in die oorsig eers op sweef gewys. Hulle
    // punte en rande bly sigbaar, en 'n aktiewe/geslote aansluiting behou sy
    // etiket sodat belangrike roete-inligting nooit versteek word nie.
    const wysPermanenteEtiket = !oorsigModus ||
      groep ||
      n.tipe !== "AANSLUITING" ||
      isHl ||
      isBlocked ||
      isBegin ||
      isEinde;
    if (!wysPermanenteEtiket) {
      svg.appendChild(g);
      return;
    }

    // Probeer verskeie posisies en kies die een met die minste botsings.
    const beginPosisie = i % 4;
    const kandidaatPosisies = [
      ...ETIKET_POSISIES.slice(beginPosisie, 4),
      ...ETIKET_POSISIES.slice(0, beginPosisie),
      ...ETIKET_POSISIES.slice(4),
    ];
    const groepGeblokkeer = groep
      ? groep.nodusse.filter((item) => blockedSet.has(item.id)).length
      : 0;
    const groepStatus = groepGeblokkeer === groep?.nodusse.length
      ? " [GESLUIT]"
      : groepGeblokkeer > 0
        ? " [DEELS GESLUIT]"
        : "";
    const basisEtiket = groep
      ? `${groep.naam} (${groep.nodusse.length} vloere)`
      : n.etiket;
    const etiket = basisEtiket + (groep
      ? groepStatus
      : isBlocked
        ? " [GESLUIT]"
        : n.beperkte && !oorsigModus
          ? ` [${n.beperkte}]`
          : "");
    const etiketLyne = breekEtiketLyne(etiket, oorsigModus ? 18 : 24, 3);

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
    if (groepToestand) {
      groepToestand.houer.appendChild(g);
      groepToestand.stelOop(false);
    } else {
      svg.appendChild(g);
    }

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
    const etiketMiddel = groep ? basisPosisie(n) : { x: cx, y: cy };
    kandidaatPosisies.forEach((posisie, kandidaatNommer) => {
      const x = etiketMiddel.x + posisie.dx;
      const y = etiketMiddel.y + posisie.dy;
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
  if (oorsigModus) {
    const wenk = document.createElementNS(NS, "text");
    wenk.setAttribute("x", 20);
    wenk.setAttribute("y", 47);
    wenk.setAttribute("font-size", "8.5");
    wenk.setAttribute("font-family", "Inter, sans-serif");
    wenk.setAttribute("fill", "#58707D");
    wenk.textContent = "Beweeg oor 'n nodus vir volle besonderhede.";
    svg.appendChild(wenk);
  }
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

[
  ["beginNode", "endNode"],
  ["endNode", "beginNode"],
].forEach(([id, volgende]) => {
  document.getElementById(id).addEventListener("change", () => {
    volgendeKaartKeuse = volgende;
    wisRoete();
  });
});
document.getElementById("gebruikerTipe").addEventListener("change", wisRoete);
document.getElementById("apiUrl").addEventListener("change", async () => {
  // 'n Ander bediener het dalk 'n ander kaart, so laai dit weer.
  try {
    await laaiKaart();
    huidigeVloer = OORSIG_ID;
  } catch (_) {
    wysBestemmingFout("⚠ Kon nie die hospitaalkaart van hierdie bediener laai nie.");
    return;
  }
  wisRoete();
  laaiBestemmings(document.getElementById("beginSoek").value, "beginNode");
  laaiBestemmings(document.getElementById("eindSoek").value, "endNode");
  laaiInsident();
});

// Gebruik die blad se bediener; 'n plaaslike HTML-voorskou kan die adres handmatig stel.
if (/^https?:$/.test(window.location.protocol)) {
  document.getElementById("apiUrl").value = window.location.origin;
}

/** Laai eers die kaart; slegs daarna kan die kaart, legende en lyste geteken word. */
async function begin() {
  try {
    await laaiKaart();
  } catch (_) {
    wysBestemmingFout("⚠ Kon nie die hospitaalkaart laai nie. Herlaai asseblief die bladsy.");
    return;
  }
  renderLegend();
  renderAll();
  populateSelects();
  laaiInsident();
  // Hou reeds oop kaarte op datum nadat 'n administrateur 'n insident verander.
  setInterval(() => {
    if (!document.hidden && !roeteBesig) laaiInsident();
  }, 15000);
}
begin();
