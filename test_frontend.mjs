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

async function koppelvlak(bronkode = bron) {
  const elemente = new Map();
  const dokument = {
    hidden: false,
    getElementById(id) {
      if (!elemente.has(id)) elemente.set(id, new Element());
      return elemente.get(id);
    },
    createElement: (naam) => new Element(naam),
    createElementNS: (_, naam) => new Element(naam),
    querySelectorAll: () => [],
    querySelector: () => new Element(),
  };
  const konteks = vm.createContext({
    document: dokument,
    window: { location: { protocol: "https:", origin: "https://hospitaal.voorbeeld" } },
    setTimeout, clearTimeout,
    setInterval() {},
    fetch: async (url) => url.endsWith("/incident")
      ? antwoord(geenInsident)
      : antwoord({ bestemmings: [bestemming("MAIN-G-ENT"), bestemming("SYGEBOU-1-RAD")] }),
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
  const { element } = await koppelvlak();
  const nodusse = () => element("plan").children.filter((kind) => kind.naam === "g");
  nodusse()[0].onclick();
  const begin = element("beginNode").value;
  nodusse()[1].onclick();
  assert.equal(element("beginNode").value, begin);
  assert.notEqual(element("endNode").value, begin);
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
