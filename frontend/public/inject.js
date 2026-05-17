/* NTS Vibe Checker — universal inject script.
 * Runs in any context that can fetch + manipulate the DOM:
 *   - Loaded by bookmarklet from any browser
 *   - @require'd by userscript managers (iOS Safari Userscripts, Tampermonkey)
 *
 * Idempotent: safe to re-execute. Won't double-inject.
 * Source of truth — keep behaviour in sync with /extension/src/content.js. */

(function () {
  if (window.__NTSVC_INJECTED__) {
    console.log("[NTS Vibe] already loaded — re-scanning");
    if (window.__NTSVC_RESCAN__) window.__NTSVC_RESCAN__();
    return;
  }
  window.__NTSVC_INJECTED__ = true;

  const ACTS_URL = "https://nts-vibe-checker.vercel.app/acts.json";

  // ---------- CSS ----------
  const css = `
    .ntsvc-badge { position: absolute; top: 8px; right: 8px; z-index: 20;
      display: inline-flex; flex-direction: column; align-items: center; justify-content: center;
      min-width: 44px; min-height: 44px; padding: 4px 6px;
      font-family: Impact, "Bebas Neue", "Oswald", "Arial Narrow", sans-serif !important;
      font-weight: 400; line-height: 1; text-transform: uppercase; letter-spacing: 0.02em;
      border-radius: 0 !important; box-shadow: 0 2px 0 rgba(0,0,0,0.25);
      pointer-events: none; user-select: none; }
    .ntsvc-badge .ntsvc-score { font-size: 22px; line-height: 1; }
    .ntsvc-badge .ntsvc-label { font-size: 9px; margin-top: 2px; letter-spacing: 0.04em; }
    .ntsvc-floating { position: fixed; left: 20px; bottom: 20px; z-index: 99998;
      display: flex; align-items: center; gap: 8px; pointer-events: auto; }
    .ntsvc-badge--detail { position: relative; top: auto; right: auto;
      min-width: 72px; min-height: 72px; pointer-events: auto; }
    .ntsvc-badge--detail .ntsvc-score { font-size: 32px; }
    .ntsvc-badge--detail .ntsvc-label { font-size: 11px; margin-top: 4px; }
    .ntsvc-cat-resident      { background: #B80028; color: #FFEBE7; }
    .ntsvc-cat-nts-vibe      { background: #D9FFF9; color: #1B1464; }
    .ntsvc-cat-nts-presence  { background: #1371C3; color: #D9FFF9; }
    .ntsvc-cat-adjacent      { background: #5a5a5a; color: #FFEBE7; }
    .ntsvc-cat-off           { background: #262626; color: #FFEBE7; opacity: 0.85; }
    .ntsvc-host { position: relative; }
    .ntsvc-why { display: inline-block; margin-left: 8px; padding: 6px 10px;
      background: #1B1464; color: #D9FFF9;
      font-family: Impact, "Bebas Neue", sans-serif !important;
      font-size: 12px; letter-spacing: 0.05em; text-transform: uppercase;
      border: 0; border-radius: 0 !important; cursor: pointer; vertical-align: middle; }
    .ntsvc-why:hover { background: #2a1f8c; }
    .ntsvc-panel { position: fixed; left: 20px; bottom: 110px; width: 360px; max-width: calc(100vw - 40px);
      max-height: 70vh; overflow-y: auto; z-index: 2147483647; padding: 20px;
      background: #1B1464; color: #D9FFF9;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
      font-size: 14px; line-height: 1.5; box-shadow: 0 10px 40px rgba(0,0,0,0.5); }
    .ntsvc-panel h3 { margin: 0 0 8px 0;
      font-family: Impact, "Bebas Neue", "Oswald", sans-serif;
      font-size: 24px; text-transform: uppercase; letter-spacing: 0.02em;
      display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
    .ntsvc-panel h3 .ntsvc-manual { display: inline-block; background: #B80028; color: #FFEBE7;
      font-family: Impact, "Bebas Neue", sans-serif; font-size: 10px;
      letter-spacing: 0.08em; padding: 3px 6px; line-height: 1; }
    .ntsvc-panel .ntsvc-panel-close { position: absolute; top: 8px; right: 12px;
      background: transparent; border: 0; color: #D9FFF9; font-size: 24px; cursor: pointer; line-height: 1; }
    .ntsvc-panel p { margin: 6px 0; }
    .ntsvc-panel a { color: #D9FFF9; text-decoration: underline; }
    .ntsvc-panel ul { margin: 6px 0; padding-left: 18px; }
    .ntsvc-panel .ntsvc-meta { font-size: 11px; opacity: 0.75; text-transform: uppercase; letter-spacing: 0.05em; }
    @media (max-width: 640px) {
      .ntsvc-floating { left: 8px; bottom: 8px; }
      .ntsvc-panel { left: 8px; right: 8px; bottom: 90px; width: auto; max-width: none; }
    }
  `;
  const style = document.createElement("style");
  style.id = "ntsvc-styles";
  style.textContent = css;
  document.head.appendChild(style);

  // ---------- helpers ----------
  function categoryClass(c) {
    return {
      "RESIDENT": "ntsvc-cat-resident",
      "NTS-VIBE": "ntsvc-cat-nts-vibe",
      "NTS-PRESENCE": "ntsvc-cat-nts-presence",
      "ADJACENT": "ntsvc-cat-adjacent",
    }[c] || "ntsvc-cat-off";
  }
  function categoryLabel(c) {
    return { "RESIDENT": "NTS BAAS", "NTS-VIBE": "VIBE", "NTS-PRESENCE": "PRESENCE", "ADJACENT": "ADJACENT" }[c] || "OFF";
  }
  function slugFromHref(href) {
    if (!href) return null;
    try {
      const u = new URL(href, "https://lowlands.nl");
      const m = u.pathname.match(/^\/acts\/([^/]+)\/?$/);
      return m ? m[1] : null;
    } catch { return null; }
  }
  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;"
    })[c]);
  }

  // ---------- DOM building ----------
  function buildBadge(act, detail = false) {
    const el = document.createElement("div");
    el.className = `ntsvc-badge ${categoryClass(act.category)}`;
    if (detail) el.classList.add("ntsvc-badge--detail");
    el.dataset.ntsvcSlug = act.slug;
    el.title = `${act.name} — ${categoryLabel(act.category)} (${act.score})`;
    const s = document.createElement("span");
    s.className = "ntsvc-score";
    s.textContent = Math.round(act.score);
    const l = document.createElement("span");
    l.className = "ntsvc-label";
    l.textContent = categoryLabel(act.category);
    el.appendChild(s); el.appendChild(l);
    return el;
  }

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

    const meta = document.createElement("p");
    meta.className = "ntsvc-meta";
    meta.textContent = `Presence ${Math.round(act.presence_score)} · Vibe ${Math.round(act.vibe_score)}`;

    const blurb = document.createElement("p");
    blurb.textContent = act.blurb || "";

    const reason = document.createElement("p");
    reason.innerHTML = act.vibe_reason ? `<em>${escapeHtml(act.vibe_reason)}</em>` : "";

    panel.appendChild(close);
    panel.appendChild(h3);
    panel.appendChild(meta);
    if (act.blurb) panel.appendChild(blurb);
    if (act.vibe_reason) panel.appendChild(reason);

    if (act.nts_links && act.nts_links.length) {
      const t = document.createElement("p");
      t.className = "ntsvc-meta";
      t.textContent = "NTS";
      panel.appendChild(t);
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

  // ---------- injection logic ----------
  let actsBySlug = null;

  function injectOnCard(cardEl) {
    if (cardEl.dataset.ntsvcInjected === "1") return;
    const slug = slugFromHref(cardEl.getAttribute("href"));
    if (!slug) return;
    const act = actsBySlug.get(slug);
    if (!act) { cardEl.dataset.ntsvcInjected = "miss"; return; }
    cardEl.classList.add("ntsvc-host");
    cardEl.appendChild(buildBadge(act));
    cardEl.dataset.ntsvcInjected = "1";
  }

  function injectOnDetailPage() {
    const slug = slugFromHref(location.pathname);
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

    floating.appendChild(buildBadge(act, true));

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

  function scan() {
    if (!actsBySlug) return;
    document.querySelectorAll("a.act-list-card__button").forEach(injectOnCard);
    document.querySelectorAll(".act-list__headliners-item a[href*='/acts/']").forEach((a) => {
      if (a.dataset.ntsvcInjected) return;
      const slug = slugFromHref(a.getAttribute("href"));
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

  let scanTimer = null;
  function scheduleScan() { clearTimeout(scanTimer); scanTimer = setTimeout(scan, 150); }
  window.__NTSVC_RESCAN__ = scheduleScan;

  // ---------- bootstrap ----------
  (async () => {
    try {
      const r = await fetch(ACTS_URL, { cache: "default" });
      if (!r.ok) throw new Error("HTTP " + r.status);
      const payload = await r.json();
      actsBySlug = new Map((payload.acts || []).map((a) => [a.slug, a]));
      console.log(`[NTS Vibe] loaded ${actsBySlug.size} acts`);
      scan();

      const obs = new MutationObserver(scheduleScan);
      obs.observe(document.body, { childList: true, subtree: true });

      let lastUrl = location.href;
      setInterval(() => {
        if (location.href !== lastUrl) {
          lastUrl = location.href;
          scheduleScan();
        }
      }, 500);

      // Bonus: small toast confirming we loaded
      const toast = document.createElement("div");
      toast.className = "ntsvc-panel";
      toast.style.cssText = "left:50%;bottom:auto;top:20px;width:auto;transform:translateX(-50%);padding:10px 16px;font-size:13px";
      toast.textContent = `NTS Vibe geladen — ${actsBySlug.size} acts`;
      document.body.appendChild(toast);
      setTimeout(() => toast.remove(), 2500);
    } catch (err) {
      console.error("[NTS Vibe] failed:", err);
      alert("NTS Vibe Checker: kon data niet laden. " + err.message);
    }
  })();
})();
