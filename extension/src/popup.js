// Popup UI for NTS Vibe Checker — pick a festival and browse its acts.

const NV = self.NTSVibe;

const listEl = document.getElementById("list");
const searchEl = document.getElementById("search");
const metaEl = document.getElementById("meta");
const refreshEl = document.getElementById("refresh");
const festivalEl = document.getElementById("festival");
const baseInput = document.getElementById("baseUrl");
const saveBaseEl = document.getElementById("saveBase");
const webappEl = document.getElementById("webapp");
const filterButtons = Array.from(document.querySelectorAll(".filters button"));

let festivals = [];
let currentEntry = null;
let allActs = [];
let topN = 10;
let query = "";

function categoryLabel(c) {
  return c === "RESIDENT" ? "BAAS" : c === "NTS-VIBE" ? "VIBE" : c === "NTS-PRESENCE" ? "PRES" : c;
}

function render() {
  let acts = allActs.slice();
  if (query) {
    const q = query.toLowerCase();
    acts = acts.filter((a) => a.name.toLowerCase().includes(q));
  } else if (topN !== "all") {
    acts = acts.slice(0, topN);
  }

  listEl.innerHTML = "";
  if (!acts.length) {
    const li = document.createElement("li");
    li.textContent = "Geen acts gevonden.";
    listEl.appendChild(li);
    return;
  }

  for (const act of acts) {
    const li = document.createElement("li");

    const badge = document.createElement("div");
    badge.className = `badge cat-${act.category}`;
    badge.textContent = Math.round(act.score);

    const info = document.createElement("div");
    info.className = "info";

    const name = document.createElement("div");
    name.className = "name";
    if (act.url) {
      const a = document.createElement("a");
      a.href = act.url;
      a.target = "_blank";
      a.rel = "noopener";
      a.textContent = act.name;
      name.appendChild(a);
    } else {
      name.textContent = act.name;
    }

    const blurb = document.createElement("div");
    blurb.className = "blurb";
    const prefix = act.overridden ? "HANDMATIG · " : "";
    blurb.textContent = `${prefix}${categoryLabel(act.category)} · ${act.blurb || ""}`;

    info.appendChild(name);
    info.appendChild(blurb);
    li.appendChild(badge);
    li.appendChild(info);
    listEl.appendChild(li);
  }
}

function setMeta(payload) {
  const date = payload.generated_at ? new Date(payload.generated_at) : null;
  const when = date ? date.toLocaleDateString("nl-NL", { day: "numeric", month: "short" }) : "?";
  metaEl.textContent = `${payload.acts.length} acts · data van ${when}`;
}

async function loadFestival(id, { forceRefresh = false } = {}) {
  currentEntry = festivals.find((f) => f.id === id) || festivals[0];
  if (!currentEntry) { metaEl.textContent = "Geen festivals gevonden."; return; }
  metaEl.textContent = "Laden…";
  try {
    const payload = await NV.getPayloadForEntry(currentEntry, { forceRefresh });
    allActs = (payload.acts || []).slice().sort((a, b) => b.score - a.score);
    setMeta(payload);
    render();
  } catch (err) {
    metaEl.textContent = "Kon data niet laden.";
    console.error(err);
  }
}

async function activeTabFestivalId() {
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (tab && tab.url) return NV.festivalIdForHost(new URL(tab.url).hostname);
  } catch { /* ignore */ }
  return null;
}

async function init() {
  const base = await NV.getBaseUrl();
  baseInput.value = base;
  webappEl.href = base;

  festivals = await NV.getIndex();
  festivalEl.innerHTML = "";
  for (const f of festivals) {
    const opt = document.createElement("option");
    opt.value = f.id;
    opt.textContent = f.name;
    festivalEl.appendChild(opt);
  }

  const activeId = await activeTabFestivalId();
  const def = activeId && festivals.some((f) => f.id === activeId) ? activeId : festivals[0]?.id;
  if (!def) { metaEl.textContent = "Geen festivals gevonden."; return; }
  festivalEl.value = def;
  await loadFestival(def);
}

searchEl.addEventListener("input", (e) => { query = e.target.value.trim(); render(); });

filterButtons.forEach((btn) => {
  btn.addEventListener("click", () => {
    filterButtons.forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    const v = btn.dataset.top;
    topN = v === "all" ? "all" : parseInt(v, 10);
    render();
  });
});

festivalEl.addEventListener("change", () => loadFestival(festivalEl.value));
refreshEl.addEventListener("click", () => loadFestival(festivalEl.value, { forceRefresh: true }));
saveBaseEl.addEventListener("click", async () => {
  const v = baseInput.value.trim();
  if (!v) return;
  await NV.setBaseUrl(v);
  // Clear cached index/payloads so the new deploy is used immediately.
  try {
    const all = await chrome.storage.local.get(null);
    const keys = Object.keys(all).filter((k) => k.startsWith("ntsvc_index") || k.startsWith("ntsvc_payload"));
    if (keys.length) await chrome.storage.local.remove(keys);
  } catch { /* ignore */ }
  await init();
});

init();
