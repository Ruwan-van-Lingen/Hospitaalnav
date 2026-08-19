/* ============================================================
    
  ============================================================ */

const loginPaneel = document.getElementById("loginPaneel");
const adminPaneel = document.getElementById("adminPaneel");
const boodskap = document.getElementById("boodskap");
let kaartData = null;

async function api(path, options = {}) {
  const response = await fetch(path, {
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  let body = null;
  try { body = await response.json(); } catch (_) {}
  if (!response.ok) throw new Error(body?.detail || `HTTP ${response.status}`);
  return body;
}

function nodeCheckboxes(container) {
  return [...container.querySelectorAll('input[data-kind="node"]')];
}

function werkOuersBy() {
  document.querySelectorAll('input[data-kind="floor"]').forEach((vloer) => {
    const groep = vloer.closest(".tree-floor-wrap");
    const kinders = nodeCheckboxes(groep);
    const gekies = kinders.filter((item) => item.checked).length;
    vloer.checked = gekies === kinders.length && kinders.length > 0;
    vloer.indeterminate = gekies > 0 && gekies < kinders.length;
  });
  document.querySelectorAll('input[data-kind="building"]').forEach((gebou) => {
    const groep = gebou.closest(".tree-group");
    const kinders = nodeCheckboxes(groep);
    const gekies = kinders.filter((item) => item.checked).length;
    gebou.checked = gekies === kinders.length && kinders.length > 0;
    gebou.indeterminate = gekies > 0 && gekies < kinders.length;
  });
  const totaal = document.querySelectorAll('input[data-kind="node"]:checked').length;
  document.getElementById("keuseTelling").textContent = `${totaal} nodus${totaal === 1 ? "" : "se"}`;
}

function maakCheckbox(kind, label, value = "") {
  const ry = document.createElement("label");
  const input = document.createElement("input");
  input.type = "checkbox"; input.dataset.kind = kind; input.value = value;
  ry.append(input, document.createTextNode(label));
  return { ry, input };
}

function renderBoom() {
  const boom = document.getElementById("boom");
  boom.innerHTML = "";
  kaartData.geboue.forEach((gebou) => {
    const groep = document.createElement("div"); groep.className = "tree-group";
    const gebouKeuse = maakCheckbox("building", gebou.naam);
    groep.appendChild(gebouKeuse.ry);
    gebou.vloere.forEach((vloer) => {
      const vloerWrap = document.createElement("div"); vloerWrap.className = "tree-floor-wrap";
      const vloerKeuse = maakCheckbox("floor", vloer.naam);
      vloerKeuse.ry.className = "tree-floor"; vloerWrap.appendChild(vloerKeuse.ry);
      const nodes = document.createElement("div"); nodes.className = "tree-nodes";
      vloer.nodes.forEach((node) => {
        const nodeKeuse = maakCheckbox("node", node.etiket, node.node_id);
        const tipe = document.createElement("span"); tipe.className = "node-type"; tipe.textContent = node.tipe_kode;
        nodeKeuse.ry.appendChild(tipe); nodes.appendChild(nodeKeuse.ry);
        nodeKeuse.input.addEventListener("change", werkOuersBy);
      });
      vloerKeuse.input.addEventListener("change", () => { nodeCheckboxes(vloerWrap).forEach((n) => n.checked = vloerKeuse.input.checked); werkOuersBy(); });
      vloerWrap.appendChild(nodes); groep.appendChild(vloerWrap);
    });
    gebouKeuse.input.addEventListener("change", () => { nodeCheckboxes(groep).forEach((n) => n.checked = gebouKeuse.input.checked); werkOuersBy(); });
    boom.appendChild(groep);
  });
  const aktief = new Set(kaartData.incident.blocked_node_ids || []);
  nodeCheckboxes(boom).forEach((n) => n.checked = aktief.has(n.value));
  werkOuersBy();
}

function renderInsident(insident) {
  const paneel = document.getElementById("aktiewePaneel");
  paneel.hidden = !insident.active;
  if (!insident.active) return;
  document.getElementById("aktieweTitel").textContent = insident.name;
  document.getElementById("aktieweBeskrywing").textContent = insident.description || "Geen beskrywing verskaf nie.";
  document.getElementById("aktieweNodes").textContent = `${insident.blocked_node_ids.length} geslote nodus(se)`;
}

async function laaiAdmin() {
  kaartData = await api("/admin/map");
  loginPaneel.hidden = true; adminPaneel.hidden = false;
  const kode = document.getElementById("kode"); kode.innerHTML = "";
  kaartData.noodkodes.forEach((item) => kode.add(new Option(item.naam, item.kode_id)));
  renderBoom(); renderInsident(kaartData.incident);
}

document.getElementById("loginForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    await api("/admin/login", { method:"POST", body:JSON.stringify({ gebruikersnaam:document.getElementById("gebruikersnaam").value, wagwoord:document.getElementById("wagwoord").value }) });
    document.getElementById("wagwoord").value = ""; await laaiAdmin();
  } catch (error) { loginPaneel.querySelector("p").textContent = error.message; }
});

document.getElementById("incidentForm").addEventListener("submit", async (event) => {
  event.preventDefault(); boodskap.textContent = "";
  const node_ids = nodeCheckboxes(document).filter((n) => n.checked).map((n) => n.value);
  if (!node_ids.length) { boodskap.textContent = "Kies minstens een nodus."; return; }
  if (!confirm(`Aktiveer die sluiting vir ${node_ids.length} nodus(se)?`)) return;
  try {
    const insident = await api("/admin/incident", { method:"POST", body:JSON.stringify({ kode_id:document.getElementById("kode").value, beskrywing:document.getElementById("beskrywing").value, node_ids }) });
    kaartData.incident = insident; renderInsident(insident); boodskap.textContent = "Sluiting is suksesvol geaktiveer.";
  } catch (error) { boodskap.textContent = error.message; }
});

document.getElementById("clearIncidentBtn").addEventListener("click", async () => {
  if (!confirm("Kanselleer die aktiewe sluiting?")) return;
  try { const insident = await api("/admin/incident", { method:"DELETE" }); kaartData.incident = insident; nodeCheckboxes(document).forEach((n) => n.checked = false); werkOuersBy(); renderInsident(insident); } catch (error) { boodskap.textContent = error.message; }
});
document.getElementById("logoutBtn").addEventListener("click", async () => { await api("/admin/logout", { method:"POST" }); adminPaneel.hidden = true; loginPaneel.hidden = false; });

laaiAdmin().catch(() => { loginPaneel.hidden = false; adminPaneel.hidden = true; });
