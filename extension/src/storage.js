// Fetch + cache festival data. Shared by content script and popup.
//
// Which festival to load is resolved from the deployed festivals/index.json,
// keyed on the current site's hostname (lowlands.nl -> "lowlands", etc.).
// The deploy base URL defaults to the public Vercel app but can be overridden
// from the popup so you can point it at your own deploy.

const DEFAULT_BASE_URL = "https://nts-vibe-checker.vercel.app";
const TTL_MS = 24 * 60 * 60 * 1000;

async function getBaseUrl() {
  try {
    const { ntsvc_base_url } = await chrome.storage.local.get("ntsvc_base_url");
    return String(ntsvc_base_url || DEFAULT_BASE_URL).replace(/\/+$/, "");
  } catch {
    return DEFAULT_BASE_URL;
  }
}

async function setBaseUrl(url) {
  await chrome.storage.local.set({ ntsvc_base_url: String(url).replace(/\/+$/, "") });
}

// Mirror of the pipeline's festival_id_from_url(): strip www, take the first
// domain label, slugify. Keeps extension ids aligned with index.json ids.
function festivalIdForHost(host) {
  host = String(host || "").toLowerCase().replace(/^www\./, "");
  const label = host.split(".")[0] || "";
  return label.replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "") || "festival";
}

async function cachedFetch(url, cacheKey, { forceRefresh = false } = {}) {
  const tsKey = cacheKey + "_ts";
  if (!forceRefresh) {
    const c = await chrome.storage.local.get([cacheKey, tsKey]);
    if (c[cacheKey] && c[tsKey] && Date.now() - c[tsKey] < TTL_MS) return c[cacheKey];
  }
  try {
    const res = await fetch(url, { cache: "no-cache" });
    if (!res.ok) throw new Error(`${url} HTTP ${res.status}`);
    const data = await res.json();
    await chrome.storage.local.set({ [cacheKey]: data, [tsKey]: Date.now() });
    return data;
  } catch (err) {
    const c = await chrome.storage.local.get(cacheKey);
    if (c[cacheKey]) {
      console.warn("[NTS Vibe] using stale cache:", err);
      return c[cacheKey];
    }
    throw err;
  }
}

async function getIndex({ forceRefresh = false } = {}) {
  const base = await getBaseUrl();
  try {
    const idx = await cachedFetch(`${base}/festivals/index.json`, "ntsvc_index", { forceRefresh });
    if (Array.isArray(idx?.festivals) && idx.festivals.length) return idx.festivals;
  } catch (err) {
    console.warn("[NTS Vibe] index.json unavailable:", err);
  }
  // Fallback: a lone Lowlands deploy that predates the index.
  return [{ id: "lowlands", name: "Lowlands", file: "/acts.json" }];
}

async function getPayloadForEntry(entry, { forceRefresh = false } = {}) {
  const base = await getBaseUrl();
  const url = base + (entry.file || "/acts.json");
  return cachedFetch(url, `ntsvc_payload_${entry.id}`, { forceRefresh });
}

async function getPayloadForHost(host, opts = {}) {
  const id = festivalIdForHost(host);
  const festivals = await getIndex(opts);
  const entry = festivals.find((f) => f.id === id);
  if (!entry) return null; // no festival data for this site
  return getPayloadForEntry(entry, opts);
}

function indexBySlug(payload) {
  const map = new Map();
  for (const act of payload?.acts || []) if (act.slug) map.set(act.slug, act);
  return map;
}

// Normalize a name for fuzzy DOM matching: lowercase, strip diacritics,
// drop (live)/[edit]-style suffixes, collapse non-alphanumerics to spaces.
function normName(s) {
  return String(s || "")
    .toLowerCase()
    .normalize("NFD").replace(/[\u0300-\u036f]/g, "")
    .replace(/\(.*?\)/g, " ")
    .replace(/\[.*?\]/g, " ")
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

function indexByName(payload) {
  const map = new Map();
  for (const act of payload?.acts || []) {
    const k = normName(act.name);
    if (k.length >= 3 && !map.has(k)) map.set(k, act);
  }
  return map;
}

// ---- Live scoring (click-to-scan on any site) ----------------------------
// Each artist is scored once and cached client-side, so repeated scans and
// revisits cost nothing. Negative results (not on NTS) are cached too.
const LIVE_TTL_MS = 30 * 24 * 60 * 60 * 1000;
const LIVE_CHUNK = 40;

// Versioned prefix: bump when scoring logic changes meaningfully, so old
// negative-cache entries don't suppress fresh lookups.
const LIVE_VERSION = "v2";
function liveKey(name) {
  return `ntsvc_live_${LIVE_VERSION}_` + normName(name).replace(/\s+/g, "_");
}

async function getCachedLive(names) {
  const keys = names.map(liveKey);
  const got = await chrome.storage.local.get(keys);
  const hits = {};
  const misses = [];
  for (const name of names) {
    const e = got[liveKey(name)];
    if (e && e.ts && Date.now() - e.ts < LIVE_TTL_MS) hits[name] = e.act;
    else misses.push(name);
  }
  return { hits, misses };
}

async function setCachedLive(results) {
  const toSet = {};
  for (const [name, act] of Object.entries(results)) {
    toSet[liveKey(name)] = { act: act || null, ts: Date.now() };
  }
  if (Object.keys(toSet).length) await chrome.storage.local.set(toSet);
}

async function liveScoreChunk(names) {
  const base = await getBaseUrl();
  const res = await fetch(`${base}/api/score`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ names }),
  });
  if (!res.ok) throw new Error(`/api/score HTTP ${res.status}`);
  const data = await res.json();
  return data.results || {};
}

// Lowlands-only: extract slug from a /acts/<slug>/ URL or href.
function slugFromHref(href) {
  if (!href) return null;
  try {
    const url = new URL(href, location.origin || "https://lowlands.nl");
    const m = url.pathname.match(/\/acts\/([^/]+)\/?$/);
    return m ? m[1] : null;
  } catch {
    return null;
  }
}

self.NTSVibe = {
  getIndex, getPayloadForEntry, getPayloadForHost,
  indexBySlug, indexByName, normName, slugFromHref,
  festivalIdForHost, getBaseUrl, setBaseUrl, DEFAULT_BASE_URL,
  getCachedLive, setCachedLive, liveScoreChunk, LIVE_CHUNK,
};
