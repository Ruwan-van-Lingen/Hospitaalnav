/**==========================================================================================
 * admin.js
 * =========
 * Kliëntkant-logika vir die Hospitaalsluitingsadministrasieblad (/admin).
 *
 * Hierdie lêer hanteer:
 *   • Aanmelding en afmelding (POST /admin/login, POST /admin/logout).
 *   • Laai van die gebou-/vloer-/nodusstruktuur (GET /admin/map).
 *   • Tekening van die interaktiewe keuseboom (gebou → vloer → nodusse).
 *   • Aktivering van 'n nuwe sluiting, insluitend ontruimingsmodus (POST /admin/incident).
 *   • Kansellering van die aktiewe sluiting (DELETE /admin/incident).
 *   • Vertoon van die aktiewe insidentstatus bo-aan die vorm.
 *   • Veiligheids- en netwerkanalise vir dekking, verbinding en deurvloei.
 *
 * Alles kommunikeer met die FastAPI-agterkant via die api()-hulpfunksie,
 * wat JSON stuur en ontvang en HTTP-foute as JavaScript-foute gooi.
 */

const loginPaneel = document.getElementById("loginPaneel");
const adminPaneel = document.getElementById("adminPaneel");
const boodskap = document.getElementById("boodskap");
const loginBoodskap = document.getElementById("loginBoodskap");
const loginKnoppie = document.getElementById("loginBtn");

/** Stoor die kaartdata (geboue, vloere, nodusse, noodkodes, insident) in geheue. */
let kaartData = null;

/** Identifiseer die jongste kaartlaai sodat 'n ou antwoord nie die paneel kan verander nie. */
let laaiVolgorde = 0;

// ---------------------------------------------------------------------------
// API-hulpfunksie
// ---------------------------------------------------------------------------

/**
 * Stuur 'n JSON API-versoek na die bediener en gee die ontlede antwoord terug.
 * Gooi 'n fout met die bediener se foutboodskap as die versoek misluk.
 *
 * @param {string} path    - Relatiewe URL, bv. "/admin/login".
 * @param {object} options - Opsionele fetch-opsies (method, body, ens.).
 * @returns {Promise<any>} - Ontlede JSON-antwoord.
 */
async function api(path, options = {}) {
  let response;
  try {
    response = await fetch(path, {
      credentials: "same-origin",
      ...options,
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    });
  } catch (_) {
    throw new Error("Kon nie die bediener bereik nie. Probeer asseblief weer.");
  }
  let body = null;
  try { body = await response.json(); } catch (_) { }
  if (!response.ok) {
    throw new Error(typeof body?.detail === "string"
      ? body.detail
      : `Die versoek het misluk (HTTP ${response.status}).`);
  }
  return body;
}

// ---------------------------------------------------------------------------
// Keusestruktuur-hulpfunksies
// ---------------------------------------------------------------------------

/**
 * Gee alle noduskassies binne die opgegee houer terug.
 * @param {Element} container - DOM-element om binne te soek.
 * @returns {HTMLInputElement[]}
 */
function nodeCheckboxes(container) {
  return [...container.querySelectorAll('input[data-kind="node"]')];
}

/**
 * Werk ouer-kassies (gebou en vloer) by op grond van hulle kinders se toestand.
 * 'n Ouer is:
 *   • Gemerk (✓)  as AL sy kinders gemerk is.
 *   • Onbepaald (—) as SOMMIGE kinders gemerk is.
 *   • Ongemerk   as GEEN kinders gemerk is nie.
 * Werk ook die "N nodusse"-teller in die afdelingsopskrif by.
 */
function werkOuersBy() {
  // Werk vloer-kassies by op grond van hul nodus-kinders.
  document.querySelectorAll('input[data-kind="floor"]').forEach((vloer) => {
    const groep = vloer.closest(".tree-floor-wrap");
    const kinders = nodeCheckboxes(groep);
    const gekies = kinders.filter((item) => item.checked).length;
    vloer.checked = gekies === kinders.length && kinders.length > 0;
    vloer.indeterminate = gekies > 0 && gekies < kinders.length;
  });

  // Werk gebou-kassies by op grond van hul nodus-kinders (alle vloere saam).
  document.querySelectorAll('input[data-kind="building"]').forEach((gebou) => {
    const groep = gebou.closest(".tree-group");
    const kinders = nodeCheckboxes(groep);
    const gekies = kinders.filter((item) => item.checked).length;
    gebou.checked = gekies === kinders.length && kinders.length > 0;
    gebou.indeterminate = gekies > 0 && gekies < kinders.length;
  });

  // Werk die keusetelling in die kopteks by.
  const totaal = document.querySelectorAll('input[data-kind="node"]:checked').length;
  document.getElementById("keuseTelling").textContent =
    `${totaal} nodus${totaal === 1 ? "" : "se"}`;
}

/**
 * Skep 'n etiket-element met 'n kassie binne-in.
 *
 * @param {string} kind  - Kassietipe: 'node', 'floor' of 'building'.
 * @param {string} label - Sigbare teks langs die kassie.
 * @param {string} value - Waarde van die kassie (die nodus-ID vir nodusse).
 * @returns {{ ry: HTMLLabelElement, input: HTMLInputElement }}
 */
function maakCheckbox(kind, label, value = "") {
  const ry = document.createElement("label");
  const input = document.createElement("input");
  input.type = "checkbox";
  input.dataset.kind = kind;
  input.value = value;
  ry.append(input, document.createTextNode(label));
  return { ry, input };
}

// ---------------------------------------------------------------------------
// Tekening van die keuseboom
// ---------------------------------------------------------------------------

/**
 * Teken die gebou → vloer → nodusstruktuur as 'n geneste kassie-boom.
 *
 * Die boom word uit kaartData.geboue gebou. Elke nodus-kassie dra die
 * node-ID as sy waarde, sodat die insidentvorm dit direk kan gebruik.
 * Nodusse wat tans in die aktiewe insident is, word vooraf gemerk.
 */
function renderBoom() {
  const boom = document.getElementById("boom");
  boom.innerHTML = "";

  kaartData.geboue.forEach((gebou) => {
    const groep = document.createElement("div");
    groep.className = "tree-group";

    // Gebou-vlak kassie — merk/ontmerk alle nodusse in die gebou.
    const gebouKeuse = maakCheckbox("building", gebou.naam);
    groep.appendChild(gebouKeuse.ry);

    gebou.vloere.forEach((vloer) => {
      const vloerWrap = document.createElement("div");
      vloerWrap.className = "tree-floor-wrap";

      // Vloer-vlak kassie — merk/ontmerk alle nodusse op hierdie vloer.
      const vloerKeuse = maakCheckbox("floor", vloer.naam);
      vloerKeuse.ry.className = "tree-floor";
      vloerWrap.appendChild(vloerKeuse.ry);

      // Nodus-kassies in 'n tweekolomrooster.
      const nodes = document.createElement("div");
      nodes.className = "tree-nodes";
      vloer.nodes.forEach((node) => {
        const nodeKeuse = maakCheckbox("node", node.etiket, node.node_id);
        // Wys die tipe-kode regs van die etiket vir konteks.
        const tipe = document.createElement("span");
        tipe.className = "node-type";
        tipe.textContent = node.tipe_kode;
        nodeKeuse.ry.appendChild(tipe);
        nodes.appendChild(nodeKeuse.ry);
        nodeKeuse.input.addEventListener("change", werkOuersBy);
      });

      // Vloerkassie: merk of ontmerk alle nodusse op hierdie vloer.
      vloerKeuse.input.addEventListener("change", () => {
        nodeCheckboxes(vloerWrap).forEach((n) => (n.checked = vloerKeuse.input.checked));
        werkOuersBy();
      });

      vloerWrap.appendChild(nodes);
      groep.appendChild(vloerWrap);
    });

    // Geboukassie: merk of ontmerk alle nodusse in die gebou.
    gebouKeuse.input.addEventListener("change", () => {
      nodeCheckboxes(groep).forEach((n) => (n.checked = gebouKeuse.input.checked));
      werkOuersBy();
    });

    boom.appendChild(groep);
  });

  // Merk nodusse wat reeds in die aktiewe insident is as vooraf-gemerk.
  const aktief = new Set(kaartData.incident.blocked_node_ids || []);
  nodeCheckboxes(boom).forEach((n) => (n.checked = aktief.has(n.value)));
  werkOuersBy();
}

// ---------------------------------------------------------------------------
// Vertoon van die insidentstatus
// ---------------------------------------------------------------------------

/**
 * Wys of verberg die aktiewe insident-kaartstrokie bo-aan die adminblad.
 * Sluit in: insidentnaam, beskrywing, nodustelling en ontruimingsmodusvlag.
 *
 * @param {object} insident - Insidentobjek soos teruggegee deur die API.
 */
function renderInsident(insident) {
  const paneel = document.getElementById("aktiewePaneel");
  paneel.hidden = !insident.active;
  if (!insident.active) return;

  document.getElementById("aktieweTitel").textContent = insident.name;
  document.getElementById("aktieweBeskrywing").textContent =
    insident.description || "Geen beskrywing verskaf nie.";

  // Outomatiese insidente kry 'n duideliker boodskap as 'n rou nodus-telling
  // (bv. "algehele grendel" i.p.v. "26 geslote nodus(se)").
  const nodesEl = document.getElementById("aktieweNodes");
  if (insident.outomaties_modus === "SLUIT_ALLES") {
    nodesEl.textContent = "🔒 Algehele grendel — die hele hospitaal is tans ontoeganklik.";
  } else if (insident.outomaties_modus === "ONTRUIM_ALMAL") {
    nodesEl.textContent = "🔥 Outomatiese ontruiming — geen spesifieke nodusse is geblokkeer nie.";
  } else {
    nodesEl.textContent = `${insident.blocked_node_ids.length} geslote nodus(se)`;
  }

  // Wys die ontruimingsmoduswaarskuwing slegs as die vlag aktief is.
  const ontruimRy = document.getElementById("aktieweOntruim");
  ontruimRy.hidden = !insident.ontruimings_modus;
}

/**
 * Pas die vorm aan volgens die tans gekose noodkode en merk die nodusse wat
 * daardie tipe by verstek sluit. Gewone tipes se voorafkeuses bly wysigbaar;
 * outomatiese tipes is 'n leesalleen-voorskou van bediener-afgedwonge gedrag.
 * Die bediener dwing hierdie gedrag in elk geval af (sien main.py), maar die
 * Koppelvlak hoort dit te weerspieël sodat die admin nie 'n noduskeuse of
 * ontruimingskassie sien wat eintlik geen effek sal hê nie.
 */
function opdateerVormVirKode() {
  const kodeSel = document.getElementById("kode");
  const outomaties = kodeSel.selectedOptions[0]?.dataset.outomaties || "";
  const seleksieKaart = document.querySelector(".selection");
  const ontruimToggle = document.querySelector(".ontruim-toggle");
  const nota = document.getElementById("kodeOutomatiesNota");
  const vooraf = new Set(
    JSON.parse(kodeSel.selectedOptions[0]?.dataset.voorafNodusse || "[]"),
  );
  const nodusse = nodeCheckboxes(seleksieKaart);

  seleksieKaart.hidden = false;
  nodusse.forEach((node) => {
    node.checked = outomaties === "SLUIT_ALLES" || vooraf.has(node.value);
    node.disabled = Boolean(outomaties);
  });
  document
    .querySelectorAll('input[data-kind="floor"], input[data-kind="building"]')
    .forEach((keuse) => (keuse.disabled = Boolean(outomaties)));
  werkOuersBy();

  if (outomaties === "ONTRUIM_ALMAL") {
    ontruimToggle.hidden = true;
    nota.hidden = false;
    nota.textContent =
      "🔥 Hierdie noodkode ontruim almal na die naaste nooduitgang en sluit geen spesifieke nodusse nie.";
  } else if (outomaties === "SLUIT_ALLES") {
    ontruimToggle.hidden = true;
    nota.hidden = false;
    nota.textContent =
      "🔒 Hierdie noodkode sluit die HELE hospitaal outomaties — geen roetes sal beskikbaar wees totdat die insident gekanselleer word nie.";
  } else {
    ontruimToggle.hidden = false;
    nota.hidden = true;
  }
}

// ---------------------------------------------------------------------------
// Veiligheids- en netwerkanalise
// ---------------------------------------------------------------------------

/** Vul die deurvloeibron-keuselys met al die nodusse uit die adminkaart. */
function vulAnaliseBronne() {
  const bronKeuse = document.getElementById("analiseBron");
  const vorigeWaarde = bronKeuse.value;
  bronKeuse.innerHTML = "";
  let eersteGewoneNodus = "";

  kaartData.geboue.forEach((gebou) => {
    gebou.vloere.forEach((vloer) => {
      vloer.nodes.forEach((node) => {
        const opsie = document.createElement("option");
        opsie.value = node.node_id;
        opsie.textContent = `${node.etiket} — ${gebou.naam}, ${vloer.naam}`;
        bronKeuse.appendChild(opsie);
        if (!eersteGewoneNodus && !node.is_nooduitgang) eersteGewoneNodus = node.node_id;
      });
    });
  });

  // 'n options-versameling het nie self 'n .map nie, daarom eers na 'n gewone lys.
  const waardes = [...bronKeuse.options].map((opsie) => opsie.value);
  bronKeuse.value = waardes.includes(vorigeWaarde)
    ? vorigeWaarde
    : (eersteGewoneNodus || waardes[0] || "");
}

/** Werk een opsommingskaart se status, detail en kleurtoestand by. */
function stelMetriek(kaartId, statusId, detailId, status, detail, toestand) {
  const kaart = document.getElementById(kaartId);
  kaart.className = `metriek ${toestand || ""}`.trim();
  document.getElementById(statusId).textContent = status;
  document.getElementById(detailId).textContent = detail;
}

/** Vervang 'n analise-detaillys sonder om API-teks as HTML uit te voer. */
function vulAnaliseLys(lysId, items, leëBoodskap, formateer) {
  const lys = document.getElementById(lysId);
  lys.innerHTML = "";
  const waardes = items.length ? items : [null];
  waardes.forEach((item) => {
    const ry = document.createElement("li");
    ry.textContent = item === null ? leëBoodskap : formateer(item);
    lys.appendChild(ry);
  });
}

/** Merk bestaande syfers as verouderd nadat die aktiewe sluiting verander. */
function merkAnaliseVerouderd() {
  const analiseBoodskap = document.getElementById("analiseBoodskap");
  analiseBoodskap.className = "analise-boodskap";
  analiseBoodskap.textContent =
    "Die sluiting het verander. Voer die analise weer uit vir huidige resultate.";
}

/**
 * Laai die drie bestaande adminontledings parallel en wys elke resultaat
 * onafhanklik. Een mislukte ontleding verberg dus nie die ander twee nie.
 */
async function laaiVeiligheidsanalise() {
  const knoppie = document.getElementById("analiseBtn");
  const analiseBoodskap = document.getElementById("analiseBoodskap");
  const gebruiker = document.getElementById("analiseGebruiker").value;
  const bron = document.getElementById("analiseBron").value;

  if (!bron) {
    analiseBoodskap.className = "analise-boodskap fout";
    analiseBoodskap.textContent = "Geen bronnodus is beskikbaar vir die deurvloei-ontleding nie.";
    return;
  }

  knoppie.disabled = true;
  knoppie.textContent = "Ontleed…";
  analiseBoodskap.className = "analise-boodskap";
  analiseBoodskap.textContent = "Veiligheids- en netwerkdata word bereken…";

  const gebruikerParameter = encodeURIComponent(gebruiker);
  const bronParameter = encodeURIComponent(bron);
  const [spanUitslag, dekkingUitslag, vloeiUitslag] = await Promise.allSettled([
    api("/analise/spanboom"),
    api(`/admin/dekking-kontrole?gebruiker_tipe=${gebruikerParameter}`),
    api(`/analise/maks_vloei?bron=${bronParameter}&gebruiker_tipe=${gebruikerParameter}`),
  ]);

  if (spanUitslag.status === "fulfilled") {
    const data = spanUitslag.value;
    stelMetriek(
      "verbindingKaart", "verbindingStatus", "verbindingDetail",
      data.is_verbind ? "Verbind" : `${data.aantal_komponente} komponente`,
      `${data.aantal_nodusse} nodusse, ${data.aantal_kante} kante · ${data.totale_gewig}`,
      data.is_verbind ? "goed" : "gevaar",
    );
  } else {
    stelMetriek(
      "verbindingKaart", "verbindingStatus", "verbindingDetail",
      "Kon nie bereken nie", spanUitslag.reason.message, "gevaar",
    );
  }

  if (dekkingUitslag.status === "fulfilled") {
    const data = dekkingUitslag.value;
    const veilig = data.onbereikbaar_telling === 0;
    stelMetriek(
      "dekkingKaart", "dekkingStatus", "dekkingDetail",
      veilig ? "Alle nodusse bereikbaar" : `${data.onbereikbaar_telling} risiko-nodus(se)`,
      `${data.totaal_nodusse - data.onbereikbaar_telling} van ${data.totaal_nodusse} het 'n veilige uitgang`,
      veilig ? "goed" : "gevaar",
    );
    vulAnaliseLys(
      "onbereikbaarLys",
      data.onbereikbaar,
      "Geen onbereikbare nodusse gevind nie.",
      (item) => `${item.node_id} — ${item.rede === "nodus_geblokkeer" ? "nodus is gesluit" : "geen bereikbare uitgang"}`,
    );
  } else {
    stelMetriek(
      "dekkingKaart", "dekkingStatus", "dekkingDetail",
      "Kon nie bereken nie", dekkingUitslag.reason.message, "gevaar",
    );
    vulAnaliseLys("onbereikbaarLys", [], dekkingUitslag.reason.message, () => "");
  }

  if (vloeiUitslag.status === "fulfilled") {
    const data = vloeiUitslag.value;
    stelMetriek(
      "vloeiKaart", "vloeiStatus", "vloeiDetail",
      data.reeds_by_uitgang
        ? "Reeds by uitgang"
        : `${data.maks_vloei_persone_per_s} persone/s`,
      data.reeds_by_uitgang
        ? "Geen verdere netwerkbeweging is nodig nie."
        : `${data.bottelnek_kante.length} bottelnek-kant(e) vanaf ${data.bron_node}`,
      data.reeds_by_uitgang || data.maks_vloei_persone_per_s > 0 ? "goed" : "waarskuwing",
    );
    vulAnaliseLys(
      "bottelnekLys",
      data.bottelnek_kante,
      data.reeds_by_uitgang ? "Die bron is reeds 'n nooduitgang." : "Geen bottelnekke gevind nie.",
      (item) => `${item.van} → ${item.na}: ${item.kapasiteit} persone/s`,
    );
  } else {
    stelMetriek(
      "vloeiKaart", "vloeiStatus", "vloeiDetail",
      "Geen veilige vloei", vloeiUitslag.reason.message, "gevaar",
    );
    vulAnaliseLys("bottelnekLys", [], vloeiUitslag.reason.message, () => "");
  }

  const foutTelling = [spanUitslag, dekkingUitslag, vloeiUitslag]
    .filter((uitslag) => uitslag.status === "rejected").length;
  analiseBoodskap.className = `analise-boodskap${foutTelling ? " fout" : ""}`;
  analiseBoodskap.textContent = foutTelling
    ? `${3 - foutTelling} van 3 ontledings is voltooi; sien die gemerkte fout(e).`
    : `Analise voltooi om ${new Date().toLocaleTimeString("af-ZA")}.`;
  knoppie.disabled = false;
  knoppie.textContent = "Voer analise uit";
}

// ---------------------------------------------------------------------------
// Bladsy-inisialisering
// ---------------------------------------------------------------------------

/**
 * Laai die adminkaart (geboue, noodkodes, insident) en wys die adminpaneel.
 * Word geroep nadat aanmelding suksesvol is, of by laai as 'n sessie
 * reeds aktief is.
 */
async function laaiAdmin() {
  const hierdieVersoek = ++laaiVolgorde;
  const nuweKaartData = await api("/admin/map");
  if (hierdieVersoek !== laaiVolgorde) return false;

  kaartData = nuweKaartData;
  loginPaneel.hidden = true;
  adminPaneel.hidden = false;

  // Vul die noodkode-keuselys met opsies uit die databasis. Elke opsie dra
  // sy outomaties_modus as 'n data-attribuut sodat opdateerVormVirKode() dit
  // sonder 'n verdere API-oproep kan lees.
  const kode = document.getElementById("kode");
  kode.innerHTML = "";
  kaartData.noodkodes.forEach((item) => {
    const opsie = document.createElement("option");
    opsie.textContent = item.naam;
    opsie.value = item.kode_id;
    opsie.dataset.outomaties = item.outomaties_modus || "";
    opsie.dataset.voorafNodusse = JSON.stringify(item.vooraf_node_ids || []);
    kode.appendChild(opsie);
  });

  renderBoom();
  renderInsident(kaartData.incident);
  opdateerVormVirKode();
  vulAnaliseBronne();
  return true;
}

// ---------------------------------------------------------------------------
// Gebeurtenishanteerders
// ---------------------------------------------------------------------------

/** Aanmeld-vorm: stuur bewyse na /admin/login en laai die adminpaneel. */
document.getElementById("loginForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  // Maak enige sessiekontrole wat reeds loop ongeldig voordat aanmelding begin.
  laaiVolgorde += 1;
  loginBoodskap.textContent = "";
  loginKnoppie.disabled = true;
  loginKnoppie.textContent = "Meld aan…";
  try {
    await api("/admin/login", {
      method: "POST",
      body: JSON.stringify({
        gebruikersnaam: document.getElementById("gebruikersnaam").value,
        wagwoord: document.getElementById("wagwoord").value,
      }),
    });
    document.getElementById("wagwoord").value = ""; // Verwyder wagwoord uit die DOM.
    await laaiAdmin();
  } catch (error) {
    loginBoodskap.textContent = error.message;
  } finally {
    loginKnoppie.disabled = false;
    loginKnoppie.textContent = "Meld aan";
  }
});

/** Wissel die vorm se sigbaarheid elke keer as die admin 'n ander noodkode kies. */
document.getElementById("kode").addEventListener("change", opdateerVormVirKode);

/** Begin die leesalleen veiligheids- en netwerkanalise op aanvraag. */
document.getElementById("analiseBtn").addEventListener("click", laaiVeiligheidsanalise);

/** Insidentvorm: bevestig dan aktiveer die sluiting met die gekose nodusse. */
document.getElementById("incidentForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  boodskap.textContent = "";

  const kodeSel = document.getElementById("kode");
  const outomaties = kodeSel.selectedOptions[0]?.dataset.outomaties || "";

  // Vir outomatiese noodkodes word geen nodus-keuse benodig of gestuur nie —
  // die bediener bepaal self die geblokkeerde nodusse/ontruimingsvlag.
  let node_ids = [];
  if (!outomaties) {
    node_ids = nodeCheckboxes(document)
      .filter((n) => n.checked)
      .map((n) => n.value);
    if (!node_ids.length) {
      boodskap.textContent = "Kies minstens een nodus.";
      return;
    }
  }

  const bevestigBoodskap =
    outomaties === "ONTRUIM_ALMAL"
      ? "Aktiveer outomatiese ontruiming vir ALMAL?"
      : outomaties === "SLUIT_ALLES"
        ? "Aktiveer 'n algehele grendel vir die HELE hospitaal?"
        : `Aktiveer die sluiting vir ${node_ids.length} nodus(se)?`;
  if (!confirm(bevestigBoodskap)) return;

  try {
    const insident = await api("/admin/incident", {
      method: "POST",
      body: JSON.stringify({
        kode_id: kodeSel.value,
        beskrywing: document.getElementById("beskrywing").value,
        node_ids,
        ontruimings_modus: document.getElementById("ontruimingsModus").checked,
      }),
    });
    kaartData.incident = insident;
    renderInsident(insident);
    merkAnaliseVerouderd();
    boodskap.textContent = "Sluiting is suksesvol geaktiveer.";
  } catch (error) {
    boodskap.textContent = error.message;
  }
});

/** Kanselleer die aktiewe sluiting en stel die vorm terug na sy verstekstand. */
document.getElementById("clearIncidentBtn").addEventListener("click", async () => {
  if (!confirm("Kanselleer die aktiewe sluiting?")) return;
  try {
    const insident = await api("/admin/incident", { method: "DELETE" });
    kaartData.incident = insident;
    document.getElementById("incidentForm").reset();
    opdateerVormVirKode();
    renderInsident(insident);
    merkAnaliseVerouderd();
    boodskap.textContent = "Die sluiting is gekanselleer.";
  } catch (error) {
    boodskap.textContent = error.message;
  }
});

/** Meld die admin af en wys die aanmeldvorm weer. */
document.getElementById("logoutBtn").addEventListener("click", async () => {
  try {
    await api("/admin/logout", { method: "POST" });
    adminPaneel.hidden = true;
    loginPaneel.hidden = false;
    kaartData = null;
    boodskap.textContent = "";
    loginBoodskap.textContent = "";
  } catch (error) {
    boodskap.textContent = error.message;
  }
});

// ---------------------------------------------------------------------------
// Aanvanklike laai
// ---------------------------------------------------------------------------
// Probeer die adminkaart laai sodra die bladsy oopmaak.
// As 'n geldige sessie-koekie reeds bestaan (bv. ná 'n bladsy-herlaai),
// word die adminpaneel direk vertoon sonder dat aanmelding nodig is.
// By 'n sessie-mislukking val dit stilweg terug na die aanmeldvorm.
const aanvanklikeVersoek = laaiVolgorde + 1;
laaiAdmin().catch(() => {
  if (laaiVolgorde === aanvanklikeVersoek) {
    loginPaneel.hidden = false;
    adminPaneel.hidden = true;
  }
});
