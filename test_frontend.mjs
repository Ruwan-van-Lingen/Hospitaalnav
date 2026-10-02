/** Koppelvlakregressietoetse sonder bykomende pakkette: node --test test_frontend.mjs. */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";

const bron = readFileSync(new URL("./hospitaal_wayfinder.js", import.meta.url), "utf8");
const adminBron = readFileSync(new URL("./admin.js", import.meta.url), "utf8");

// 'n Klein DOM-dubbel toets asinkrone gebruikersgedrag; visuele uitleg word apart nagegaan.
class Element {
  constructor(naam = "div") {
    this.naam = naam;
    this.children = [];
    this.dataset = {};
    this.style = {};
    this.listeners = {};
    this.attributes = {};
    this.classList = { add() {} };
    this._teks = "";
    this._waarde = null;
    this.disabled = false;
  }
  set innerHTML(waarde) { this.children = []; this._html = waarde; this._teks = ""; }
  get innerHTML() { return this._html || ""; }
  set textContent(waarde) { this._teks = String(waarde); this.children = []; }
  get textContent() { return this._teks + this.children.map((kind) => kind.textContent).join(""); }
  set value(waarde) { this._waarde = waarde; }
  get value() { return this._waarde ?? (this.options[0]?.value || ""); }
  get options() { return this.children.filter((kind) => kind.naam === "option"); }
  get selectedOptions() { return this.options.filter((kind) => kind.value === this.value); }
  appendChild(kind) { this.children.push(kind); return kind; }
  append(...kinders) { this.children.push(...kinders); }
  addEventListener(naam, funksie) { this.listeners[naam] = funksie; }
  setAttribute(naam, waarde) { this.attributes[naam] = waarde; }
  getBBox() { return { x: 60, y: 90, width: 40, height: 20 }; }
  querySelectorAll() { return []; }
  querySelector() { return new Element(); }
}

const antwoord = (data, status = 200) => ({
  ok: status >= 200 && status < 300,
  status,
  async json() { return data; },
});
const geenInsident = { active: false, blocked_node_ids: [] };
const roete = {
  pad: ["MAIN-G-ENT", "MAIN-G-J01"],
  geskatte_tyd_sekondes: 8,
  geskatte_tyd: "8s",
  geskatte_afstand_m: 10,
  geskatte_afstand: "10 m",
  node_telling: 2,
};
const bestemming = (node_id, etiket = node_id) => ({
  node_id, etiket, gebou_naam: "Hoofgebou", vloer_naam: "Grondvloer",
});
const wagVirAntwoorde = () => new Promise((klaar) => setImmediate(klaar));

async function koppelvlak(bronkode = bron, fetchFunksie = null) {
  const elemente = new Map();
  const dokument = {
    hidden: false,
    getElementById(id) {
      if (!elemente.has(id)) elemente.set(id, new Element());
      return elemente.get(id);
    },
    createElement: (naam) => new Element(naam),
    createElementNS: (_, naam) => new Element(naam),
    createTextNode(teks) {
      const node = new Element("#text");
      node.textContent = teks;
      return node;
    },
    querySelectorAll: () => [],
    querySelector: () => new Element(),
  };
  const konteks = vm.createContext({
    document: dokument,
    window: { location: { protocol: "https:", origin: "https://hospitaal.voorbeeld" } },
    setTimeout, clearTimeout,
    setInterval() {},
    fetch: fetchFunksie || (async (url) => url.endsWith("/incident")
      ? antwoord(geenInsident)
      : antwoord({ bestemmings: [bestemming("MAIN-G-ENT"), bestemming("SYGEBOU-1-RAD")] })),
  });
  vm.runInContext(bronkode, konteks);
  await wagVirAntwoorde();
  return { konteks, element: (id) => dokument.getElementById(id), lees: (kode) => vm.runInContext(kode, konteks) };
}

test("gebruik die blad se bedieneradres vir 'n afgeleë ontplooiing", async () => {
  const { element } = await koppelvlak();
  assert.equal(element("apiUrl").value, "https://hospitaal.voorbeeld");
});

test("409 bly 409 en foutteks word nie as HTML uitgevoer nie", async () => {
  const { konteks, element, lees } = await koppelvlak();
  const teks = '<img src=x onerror="alert(1)">';
  konteks.fetch = async () => antwoord({ detail: teks }, 409);
  await lees('fetchRoute("", "A", "B", "PUBLIEK").then((r) => { laasteResultaat = r; renderAll(); })');
  assert.match(element("status").textContent, /409/);
  assert.doesNotMatch(element("status").textContent, /403/);
  assert.equal(element("routePanel").children[0].textContent, teks);
  assert.equal(element("routePanel").children[0].innerHTML, "");
});

test("ongeldige JSON-roetedata gee 'n leesbare fout", async () => {
  const { konteks, lees } = await koppelvlak();
  konteks.fetch = async () => antwoord(null);
  const uitslag = await lees('fetchRoute("", "A", "B", "PUBLIEK")');
  assert.equal(uitslag.error, "invalid");
});

test("bediener se nooduitgang word ook op die gewone roete-eindpunt gewys", async () => {
  const { konteks, lees } = await koppelvlak();
  konteks.fetch = async () => antwoord({ ...roete, uitgang_node: "MAIN-G-ENT" });
  const uitslag = await lees('fetchRoute("", "A", "B", "PUBLIEK")');
  assert.equal(uitslag.uitgang, "MAIN-G-ENT");
});

test("nuwe sluiting wis 'n ou roete en heropening herstel die keuse-etiket", async () => {
  const { konteks, element, lees } = await koppelvlak();
  lees('laasteResultaat = { path: ["MAIN-G-ENT"] }');
  konteks.fetch = async () => antwoord({ active: true, blocked_node_ids: ["MAIN-G-ENT"], name: "Toets" });
  await lees("laaiInsident()");
  assert.equal(lees("laasteResultaat"), null);
  assert.equal(element("beginNode").value, "");
  assert.equal(element("beginNode").options[0].disabled, true);
  assert.match(element("beginNode").options[0].textContent, /\[GESLUIT\]/);
  konteks.fetch = async () => antwoord(geenInsident);
  await lees("laaiInsident()");
  assert.equal(element("beginNode").options[0].disabled, false);
  assert.doesNotMatch(element("beginNode").options[0].textContent, /GESLUIT/);
});

test("herstel tydens 'n hangende roete voorkom dat die ou antwoord terugkeer", async () => {
  const { konteks, element, lees } = await koppelvlak();
  let voltooi;
  konteks.fetch = async (url) => url.endsWith("/incident")
    ? antwoord(geenInsident)
    : new Promise((klaar) => { voltooi = klaar; });
  const hangend = element("findBtn").onclick();
  await wagVirAntwoorde();
  assert.equal(typeof voltooi, "function");
  element("clearBtn").onclick();
  voltooi(antwoord(roete));
  await hangend;
  assert.equal(lees("laasteResultaat"), null);
  assert.equal(element("findBtn").disabled, false);
});

test("onbevestigde insidentstatus verhinder roeteberekening", async () => {
  const { konteks, element, lees } = await koppelvlak();
  const versoeke = [];
  konteks.fetch = async (url) => { versoeke.push(url); throw new Error("Verbinding onderbreek"); };
  await element("findBtn").onclick();
  assert.equal(versoeke.length, 1);
  assert.match(versoeke[0], /\/incident$/);
  assert.equal(lees("laasteResultaat.error"), "network");
  assert.equal(element("findBtn").disabled, false);
});

test("ouer bestemmingsoektogte kan nie nuwer resultate oorskryf nie", async () => {
  const { konteks, element, lees } = await koppelvlak();
  const hangend = [];
  konteks.fetch = () => new Promise((klaar) => hangend.push(klaar));
  const eerste = lees('laaiBestemmings("eerste", "beginNode")');
  const tweede = lees('laaiBestemmings("tweede", "beginNode")');
  hangend[1](antwoord({ bestemmings: [bestemming("NUUT")] }));
  await tweede;
  hangend[0](antwoord({ bestemmings: [bestemming("OUD")] }));
  await eerste;
  assert.equal(element("beginNode").options[0].value, "NUUT");
});

test("opeenvolgende kaartklikke kies begin en bestemming op verskillende nodusse", async () => {
  const { element, lees } = await koppelvlak();
  const nodusse = () => element("plan").children.filter((kind) => kind.naam === "g");
  nodusse()[0].onclick();
  assert.equal(element("beginNode").value, lees("nodes[0].id"));
  assert.equal(element("beginSoek").value, lees("nodes[0].etiket"));
  assert.match(element("status").textContent, /Klik nou op 'n bestemming/);
  nodusse()[1].onclick();
  assert.equal(element("beginNode").value, lees("nodes[0].id"));
  assert.equal(element("endNode").value, lees("nodes[1].id"));
  assert.equal(element("eindSoek").value, lees("nodes[1].etiket"));
  assert.match(element("status").textContent, /Bestemming gekies/);
});

test("dieselfde tweede kaartklik kan nie ook die bestemming wees nie", async () => {
  const { element } = await koppelvlak();
  const nodusse = () => element("plan").children.filter((kind) => kind.naam === "g");
  nodusse()[0].onclick();
  const vorigeBestemming = element("endNode").value;
  nodusse()[0].onclick();
  assert.equal(element("endNode").value, vorigeBestemming);
  assert.match(element("status").textContent, /ander nodus/);
});

test("adminversoeke behou JSON-opskrifte en vertaal netwerkfoute", async () => {
  const { konteks, lees } = await koppelvlak(adminBron);
  let opsies;
  konteks.fetch = async (_, options) => { opsies = options; return antwoord({}); };
  await lees('api("/admin/login", { headers: { "X-Toets": "ja" } })');
  assert.equal(opsies.headers["Content-Type"], "application/json");
  assert.equal(opsies.headers["X-Toets"], "ja");
  konteks.fetch = async () => { throw new Error("Failed to fetch"); };
  await assert.rejects(lees('api("/admin/logout")'), /Kon nie die bediener bereik nie/);
});

test("mislukte adminafmelding wys die fout en hou die paneel oop", async () => {
  const { konteks, element } = await koppelvlak(adminBron);
  element("adminPaneel").hidden = false;
  konteks.fetch = async () => { throw new Error("Verbinding onderbreek"); };
  await element("logoutBtn").listeners.click();
  assert.equal(element("adminPaneel").hidden, false);
  assert.match(element("boodskap").textContent, /Kon nie die bediener bereik nie/);
});

test("suksesvolle adminaanmelding laai en wys die adminpaneel", async () => {
  const adminKaart = {
    geboue: [],
    noodkodes: [{ kode_id: "GEEL", naam: "Kode Geel", vooraf_node_ids: [] }],
    incident: geenInsident,
  };
  const fetchFunksie = async (url) => url === "/admin/map"
    ? antwoord(adminKaart)
    : antwoord({ success: true });
  const { element } = await koppelvlak(adminBron, fetchFunksie);
  element("gebruikersnaam").value = "admin";
  element("wagwoord").value = "admin";

  await element("loginForm").listeners.submit({ preventDefault() {} });

  assert.equal(element("loginPaneel").hidden, true);
  assert.equal(element("adminPaneel").hidden, false);
  assert.equal(element("wagwoord").value, "");
  assert.equal(element("loginBtn").disabled, false);
  assert.equal(element("kode").options[0].value, "GEEL");
});

test("'n ou sessiekontrole kan nie suksesvolle aanmelding wegsteek nie", async () => {
  let verwerpOuKontrole;
  let kaartVersoeke = 0;
  const adminKaart = { geboue: [], noodkodes: [], incident: geenInsident };
  const fetchFunksie = async (url) => {
    if (url === "/admin/map" && kaartVersoeke++ === 0) {
      return new Promise((_, verwerp) => { verwerpOuKontrole = verwerp; });
    }
    return antwoord(url === "/admin/map" ? adminKaart : { success: true });
  };
  const { element } = await koppelvlak(adminBron, fetchFunksie);
  await element("loginForm").listeners.submit({ preventDefault() {} });
  verwerpOuKontrole(new Error("Ou sessie het verval"));
  await wagVirAntwoorde();

  assert.equal(element("loginPaneel").hidden, true);
  assert.equal(element("adminPaneel").hidden, false);
});

test("veiligheids- en netwerkanalise wys al drie resultate", async () => {
  const adminKaart = {
    geboue: [{
      naam: "Hoofgebou",
      vloere: [{
        naam: "Grondvloer",
        nodes: [{ node_id: "MAIN-G-ER", etiket: "Ongevalle", tipe_kode: "DEPARTEMENT", is_nooduitgang: 0 }],
      }],
    }],
    noodkodes: [],
    incident: geenInsident,
  };
  const fetchFunksie = async (url) => {
    if (url === "/admin/map") return antwoord(adminKaart);
    if (url === "/analise/spanboom") return antwoord({
      is_verbind: true, aantal_komponente: 1, aantal_nodusse: 26,
      aantal_kante: 25, totale_gewig: "2m 10s",
    });
    if (url.startsWith("/admin/dekking-kontrole")) return antwoord({
      totaal_nodusse: 26, onbereikbaar_telling: 1,
      onbereikbaar: [{ node_id: "MAIN-2-ICU", rede: "geen_bereikbare_uitgang" }],
    });
    if (url.startsWith("/analise/maks_vloei")) return antwoord({
      bron_node: "MAIN-G-ER", maks_vloei_persone_per_s: 4,
      reeds_by_uitgang: false,
      bottelnek_kante: [{ van: "MAIN-G-ER", na: "MAIN-G-J01", kapasiteit: 4 }],
    });
    return antwoord({});
  };
  const { element } = await koppelvlak(adminBron, fetchFunksie);

  await element("analiseBtn").listeners.click();

  assert.equal(element("verbindingStatus").textContent, "Verbind");
  assert.match(element("dekkingStatus").textContent, /1 risiko-nodus/);
  assert.match(element("vloeiStatus").textContent, /4 persone\/s/);
  assert.match(element("onbereikbaarLys").textContent, /MAIN-2-ICU/);
  assert.match(element("bottelnekLys").textContent, /MAIN-G-ER/);
  assert.equal(element("analiseBtn").disabled, false);
});

test("een mislukte ontleding verberg nie die ander veiligheidsresultate nie", async () => {
  const adminKaart = {
    geboue: [{ naam: "Hoofgebou", vloere: [{
      naam: "Grondvloer",
      nodes: [{ node_id: "MAIN-G-ENT", etiket: "Ingang", is_nooduitgang: 1 }],
    }] }],
    noodkodes: [],
    incident: geenInsident,
  };
  const fetchFunksie = async (url) => {
    if (url === "/admin/map") return antwoord(adminKaart);
    if (url === "/analise/spanboom") return antwoord({
      is_verbind: true, aantal_nodusse: 1, aantal_kante: 0, totale_gewig: "0s",
    });
    if (url.startsWith("/admin/dekking-kontrole")) return antwoord({
      totaal_nodusse: 1, onbereikbaar_telling: 0, onbereikbaar: [],
    });
    return antwoord({ detail: "Geen toegelate ontruimingsvloei beskikbaar nie." }, 409);
  };
  const { element } = await koppelvlak(adminBron, fetchFunksie);

  await element("analiseBtn").listeners.click();

  assert.equal(element("verbindingStatus").textContent, "Verbind");
  assert.equal(element("dekkingStatus").textContent, "Alle nodusse bereikbaar");
  assert.equal(element("vloeiStatus").textContent, "Geen veilige vloei");
  assert.match(element("analiseBoodskap").textContent, /2 van 3/);
});
