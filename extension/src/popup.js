// Popup UI for NTS Vibe Checker.

const { getActsPayload } = self.NTSVibe;

const listEl = document.getElementById("list");
const searchEl = document.getElementById("search");
const metaEl = document.getElementById("meta");
const refreshEl = document.getElementById("refresh");
const filterButtons = Array.from(document.querySelectorAll(".filters button"));

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

    const a = document.createElement("a");
    a.href = `https://lowlands.nl/acts/${act.slug}/`;
    a.target = "_blank";
    a.rel = "noopener";
    a.textContent = act.name;
    a.className = "name";

    const name = document.createElement("div");
    name.className = "name";
    name.appendChild(a);

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

async function load({ forceRefresh = false } = {}) {
  metaEl.textContent = "Laden…";
  try {
    const payload = await getActsPayload({ forceRefresh });
    allActs = (payload.acts || []).slice().sort((a, b) => b.score - a.score);
    setMeta(payload);
    render();
  } catch (err) {
    metaEl.textContent = "Kon data niet laden.";
    console.error(err);
  }
}

searchEl.addEventListener("input", (e) => {
  query = e.target.value.trim();
  render();
});

filterButtons.forEach((btn) => {
  btn.addEventListener("click", () => {
    filterButtons.forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    const v = btn.dataset.top;
    topN = v === "all" ? "all" : parseInt(v, 10);
    render();
  });
});

refreshEl.addEventListener("click", () => load({ forceRefresh: true }));

load();
