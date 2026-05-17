// Inject NTS Vibe badges onto lowlands.nl act cards and detail pages.
// Reads from `self.NTSVibe` populated by storage.js.

(function () {
  const { getActsPayload, indexBySlug, slugFromHref } = self.NTSVibe;

  let actsBySlug = null;
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

  function buildBadge(act, { detail = false } = {}) {
    const el = document.createElement("div");
    el.className = `ntsvc-badge ${categoryClass(act.category)}`;
    if (detail) el.classList.add("ntsvc-badge--detail");
    el.dataset.ntsvcSlug = act.slug;
    el.title = `${act.name} — ${categoryLabel(act.category)} (${act.score})`;

    const score = document.createElement("span");
    score.className = "ntsvc-score";
    score.textContent = Math.round(act.score);

    const label = document.createElement("span");
    label.className = "ntsvc-label";
    label.textContent = categoryLabel(act.category);

    el.appendChild(score);
    el.appendChild(label);
    return el;
  }

  function injectOnCard(cardEl) {
    if (cardEl.dataset.ntsvcInjected === "1") return;
    const href = cardEl.getAttribute("href");
    const slug = slugFromHref(href);
    if (!slug) return;
    const act = actsBySlug.get(slug);
    if (!act) {
      // Mark as processed so we don't keep retrying.
      cardEl.dataset.ntsvcInjected = "miss";
      return;
    }
    cardEl.classList.add("ntsvc-host");
    cardEl.appendChild(buildBadge(act));
    cardEl.dataset.ntsvcInjected = "1";
  }

  function injectOnDetailPage() {
    const slug = slugFromHref(location.pathname);
    if (!slug) return;
    // Already injected for this slug?
    const existing = document.querySelector(".ntsvc-floating");
    if (existing) {
      if (existing.dataset.ntsvcSlug === slug) return;
      existing.remove(); // stale from previous detail page
    }
    const act = actsBySlug.get(slug);
    if (!act) return;

    const floating = document.createElement("div");
    floating.className = "ntsvc-floating";
    floating.dataset.ntsvcSlug = slug;

    const badge = buildBadge(act, { detail: true });
    floating.appendChild(badge);

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
    if (!actsBySlug) return;
    // Acts overview cards
    const cards = document.querySelectorAll("a.act-list-card__button");
    cards.forEach(injectOnCard);

    // Headliner items may wrap an <a> — try to find act links inside.
    document.querySelectorAll(".act-list__headliners-item a[href*='/acts/']").forEach((a) => {
      if (a.dataset.ntsvcInjected) return;
      const slug = slugFromHref(a.getAttribute("href"));
      if (!slug) return;
      const act = actsBySlug.get(slug);
      if (!act) { a.dataset.ntsvcInjected = "miss"; return; }
      a.classList.add("ntsvc-host");
      // Avoid stacking by checking for an existing badge inside this anchor.
      if (!a.querySelector(".ntsvc-badge")) a.appendChild(buildBadge(act));
      a.dataset.ntsvcInjected = "1";
    });

    // Detail page
    if (/^\/acts\/[^/]+\/?$/.test(location.pathname)) {
      injectOnDetailPage();
    } else {
      removeFloatingIfOffDetail();
    }
  }

  // Debounced scan to handle rapid mutations during SPA navigation.
  let scanTimer = null;
  function scheduleScan() {
    clearTimeout(scanTimer);
    scanTimer = setTimeout(scan, 150);
  }

  function startObserver() {
    const observer = new MutationObserver(scheduleScan);
    observer.observe(document.body, { childList: true, subtree: true });

    // Watch for SPA URL changes (Nuxt doesn't always fire popstate on link clicks).
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
        const payload = await getActsPayload();
        actsBySlug = indexBySlug(payload);
        console.log(`[NTS Vibe] loaded ${actsBySlug.size} acts`);
        scan();
        startObserver();
      } catch (err) {
        console.error("[NTS Vibe] failed to load acts.json:", err);
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
