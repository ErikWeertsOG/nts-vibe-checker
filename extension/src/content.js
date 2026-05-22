// Inject NTS Vibe badges onto festival line-up pages.
//
// Two modes:
//  - lowlands.nl: precise slug matching against /acts/<slug>/ cards + detail
//    page (unchanged behaviour).
//  - any other festival site: name-based matching — find leaf elements whose
//    text equals an act name and drop an inline badge next to it. No
//    site-specific selectors needed.
//
// Which festival's data loads is decided by storage.js from the hostname.

(function () {
  const NV = self.NTSVibe;
  const host = location.hostname.replace(/^www\./, "");
  const isLowlands = host === "lowlands.nl" || host.endsWith(".lowlands.nl");

  let actsBySlug = null;
  let actsByName = null;
  let pending = null;

  function categoryClass(category) {
    switch (category) {
      case "RESIDENT": return "ntsvc-cat-resident";
      case "NTS-VIBE": return "ntsvc-cat-nts-vibe";
      case "NTS-PRESENCE": return "ntsvc-cat-nts-presence";
      case "ADJACENT": return "ntsvc-cat-adjacent";
      case "OFF":
      default: return "ntsvc-cat-off";
    }
  }

  function categoryLabel(category) {
    switch (category) {
      case "RESIDENT": return "NTS BAAS";
      case "NTS-VIBE": return "VIBE";
      case "NTS-PRESENCE": return "PRESENCE";
      case "ADJACENT": return "ADJACENT";
      case "OFF":
      default: return "OFF";
    }
  }

  function buildBadge(act, { detail = false, inline = false } = {}) {
    const el = document.createElement("div");
    el.className = `ntsvc-badge ${categoryClass(act.category)}`;
    if (detail) el.classList.add("ntsvc-badge--detail");
    if (inline) el.classList.add("ntsvc-badge--inline");
    el.dataset.ntsvcSlug = act.slug || "";
    el.title = `${act.name} — ${categoryLabel(act.category)} (${Math.round(act.score)})`;

    const score = document.createElement("span");
    score.className = "ntsvc-score";
    score.textContent = Math.round(act.score);

    const label = document.createElement("span");
    label.className = "ntsvc-label";
    label.textContent = categoryLabel(act.category);

    el.appendChild(score);
    el.appendChild(label);

    if (inline || detail) {
      el.style.cursor = "pointer";
      el.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        showPanel(act);
      });
    }
    return el;
  }

  // ---- Lowlands (slug) mode -------------------------------------------------
  function injectOnCard(cardEl) {
    if (cardEl.dataset.ntsvcInjected === "1") return;
    const slug = NV.slugFromHref(cardEl.getAttribute("href"));
    if (!slug) return;
    const act = actsBySlug.get(slug);
    if (!act) { cardEl.dataset.ntsvcInjected = "miss"; return; }
    cardEl.classList.add("ntsvc-host");
    cardEl.appendChild(buildBadge(act));
    cardEl.dataset.ntsvcInjected = "1";
  }

  function injectOnDetailPage() {
    const slug = NV.slugFromHref(location.pathname);
    if (!slug) return;
    const existing = document.querySelector(".ntsvc-floating");
    if (existing) {
      if (existing.dataset.ntsvcSlug === slug) return;
      existing.remove();
    }
    const act = actsBySlug.get(slug);
    if (!act) return;

    const floating = document.createElement("div");
    floating.className = "ntsvc-floating";
    floating.dataset.ntsvcSlug = slug;
    floating.appendChild(buildBadge(act, { detail: true }));

    const why = document.createElement("button");
    why.className = "ntsvc-why";
    why.textContent = "Waarom?";
    why.addEventListener("click", () => showPanel(act));
    floating.appendChild(why);

    document.body.appendChild(floating);
  }

  function removeFloatingIfOffDetail() {
    if (!/^\/acts\/[^/]+\/?$/.test(location.pathname)) {
      document.querySelectorAll(".ntsvc-floating, .ntsvc-panel").forEach((el) => el.remove());
    }
  }

  function scanLowlands() {
    document.querySelectorAll("a.act-list-card__button").forEach(injectOnCard);

    document.querySelectorAll(".act-list__headliners-item a[href*='/acts/']").forEach((a) => {
      if (a.dataset.ntsvcInjected) return;
      const slug = NV.slugFromHref(a.getAttribute("href"));
      if (!slug) return;
      const act = actsBySlug.get(slug);
      if (!act) { a.dataset.ntsvcInjected = "miss"; return; }
      a.classList.add("ntsvc-host");
      if (!a.querySelector(".ntsvc-badge")) a.appendChild(buildBadge(act));
      a.dataset.ntsvcInjected = "1";
    });

    if (/^\/acts\/[^/]+\/?$/.test(location.pathname)) injectOnDetailPage();
    else removeFloatingIfOffDetail();
  }

  // ---- Generic (name) mode --------------------------------------------------
  const GENERIC_SEL = "a,span,div,li,h1,h2,h3,h4,h5,p,strong,b,em,figcaption,td";

  function scanGeneric() {
    if (!actsByName) return;
    const els = document.querySelectorAll(GENERIC_SEL);
    for (const el of els) {
      if (el.dataset.ntsvcInjected) continue;
      if (el.children.length) continue;           // leaf text nodes only
      if (el.closest(".ntsvc-badge, .ntsvc-panel, .ntsvc-floating")) continue;
      const txt = (el.textContent || "").trim();
      if (txt.length < 3 || txt.length > 60) continue;
      const key = NV.normName(txt);
      if (key.length < 3) continue;
      const act = actsByName.get(key);
      if (!act) continue;
      el.dataset.ntsvcInjected = "1";
      if (!el.parentNode) continue;
      el.insertAdjacentElement("afterend", buildBadge(act, { inline: true }));
    }
  }

  // ---- Shared panel ---------------------------------------------------------
  function showPanel(act) {
    document.querySelectorAll(".ntsvc-panel").forEach((p) => p.remove());
    const panel = document.createElement("div");
    panel.className = "ntsvc-panel";

    const close = document.createElement("button");
    close.className = "ntsvc-panel-close";
    close.textContent = "×";
    close.addEventListener("click", () => panel.remove());

    const h3 = document.createElement("h3");
    h3.textContent = `${categoryLabel(act.category)} · ${Math.round(act.score)}`;
    if (act.overridden) {
      const tag = document.createElement("span");
      tag.className = "ntsvc-manual";
      tag.textContent = "HANDMATIG";
      h3.appendChild(tag);
    }

    const title = document.createElement("p");
    title.className = "ntsvc-meta";
    title.textContent = act.name;

    const meta = document.createElement("p");
    meta.className = "ntsvc-meta";
    meta.textContent = `Presence ${Math.round(act.presence_score)} · Vibe ${Math.round(act.vibe_score)}`;

    const blurb = document.createElement("p");
    blurb.textContent = act.blurb || "";

    const reason = document.createElement("p");
    reason.innerHTML = act.vibe_reason ? `<em>${escapeHtml(act.vibe_reason)}</em>` : "";

    panel.appendChild(close);
    panel.appendChild(h3);
    panel.appendChild(title);
    panel.appendChild(meta);
    if (act.blurb) panel.appendChild(blurb);
    if (act.vibe_reason) panel.appendChild(reason);

    if (act.nts_links && act.nts_links.length) {
      const linksTitle = document.createElement("p");
      linksTitle.className = "ntsvc-meta";
      linksTitle.textContent = "NTS";
      panel.appendChild(linksTitle);
      const ul = document.createElement("ul");
      for (const link of act.nts_links.slice(0, 6)) {
        const li = document.createElement("li");
        const a = document.createElement("a");
        a.href = link.url;
        a.textContent = link.label;
        a.target = "_blank";
        a.rel = "noopener";
        li.appendChild(a);
        ul.appendChild(li);
      }
      panel.appendChild(ul);
    }

    document.body.appendChild(panel);
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;",
    })[c]);
  }

  function scan() {
    if (isLowlands) scanLowlands();
    else scanGeneric();
  }

  let scanTimer = null;
  function scheduleScan() {
    clearTimeout(scanTimer);
    scanTimer = setTimeout(scan, 150);
  }

  function startObserver() {
    const observer = new MutationObserver(scheduleScan);
    observer.observe(document.body, { childList: true, subtree: true });

    let lastUrl = location.href;
    setInterval(() => {
      if (location.href !== lastUrl) {
        lastUrl = location.href;
        scheduleScan();
      }
    }, 500);
  }

  async function init() {
    if (pending) return pending;
    pending = (async () => {
      try {
        const payload = await NV.getPayloadForHost(host);
        if (!payload) return; // no festival data deployed for this site
        actsBySlug = NV.indexBySlug(payload);
        actsByName = NV.indexByName(payload);
        const fest = payload.festival ? payload.festival.name : host;
        console.log(`[NTS Vibe] ${actsByName.size} acts loaded for ${fest}`);
        scan();
        startObserver();
      } catch (err) {
        console.error("[NTS Vibe] failed to load festival data:", err);
      }
    })();
    return pending;
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, { once: true });
  } else {
    init();
  }
})();
