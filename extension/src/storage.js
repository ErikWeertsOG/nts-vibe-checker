// Fetch + cache acts.json. Shared by content script and popup.
// Cache TTL: 24h. Key in chrome.storage.local.

const ACTS_URL = "https://nts-vibe-checker.vercel.app/acts.json";
const CACHE_KEY = "nts_vibe_payload";
const CACHE_TS_KEY = "nts_vibe_payload_ts";
const TTL_MS = 24 * 60 * 60 * 1000;

async function fetchActsFresh() {
  const res = await fetch(ACTS_URL, { cache: "no-cache" });
  if (!res.ok) throw new Error(`acts.json HTTP ${res.status}`);
  const payload = await res.json();
  await chrome.storage.local.set({
    [CACHE_KEY]: payload,
    [CACHE_TS_KEY]: Date.now(),
  });
  return payload;
}

async function getActsPayload({ forceRefresh = false } = {}) {
  if (!forceRefresh) {
    const cached = await chrome.storage.local.get([CACHE_KEY, CACHE_TS_KEY]);
    const payload = cached[CACHE_KEY];
    const ts = cached[CACHE_TS_KEY];
    if (payload && ts && Date.now() - ts < TTL_MS) {
      return payload;
    }
  }
  try {
    return await fetchActsFresh();
  } catch (err) {
    // Fall back to stale cache if network fails.
    const cached = await chrome.storage.local.get(CACHE_KEY);
    if (cached[CACHE_KEY]) {
      console.warn("[NTS Vibe] using stale cache:", err);
      return cached[CACHE_KEY];
    }
    throw err;
  }
}

// Index by slug for O(1) lookup from content script.
function indexBySlug(payload) {
  const map = new Map();
  for (const act of payload.acts || []) {
    if (act.slug) map.set(act.slug, act);
  }
  return map;
}

// Extract slug from a lowlands.nl/acts/<slug>/ URL or href.
function slugFromHref(href) {
  if (!href) return null;
  try {
    const url = new URL(href, "https://lowlands.nl");
    const m = url.pathname.match(/\/acts\/([^/]+)\/?$/);
    return m ? m[1] : null;
  } catch {
    return null;
  }
}

// Expose to other scripts in the same isolated world.
self.NTSVibe = { getActsPayload, indexBySlug, slugFromHref, ACTS_URL };
