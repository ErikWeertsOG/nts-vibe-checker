# NTS Vibe Checker — Chrome Extension

Injecteert NTS Vibe-badges naast acts op [lowlands.nl](https://lowlands.nl). Data komt uit `https://nts-vibe-checker.vercel.app/acts.json` — geen scoring of scraping in de extensie zelf.

## Status: v0.1.0 — werkende eerste versie

- ✅ Badges op acts-overzichtspagina (`/acts/`)
- ✅ Badge + "Waarom?"-paneel op act-detailpagina (`/acts/<slug>/`)
- ✅ MutationObserver + URL-poller voor Nuxt SPA-navigatie
- ✅ Popup met top 10/25/50 + zoekveld
- ✅ Cache 24u via `chrome.storage.local`, met stale fallback bij netwerkfout
- ⏳ "Nu speelt"-modus — wacht op timetable-data in `acts.json`
- ⏳ Icons (16/48/128) — moeten nog gemaakt; Chrome valt nu terug op default

## Lokaal laden in Chrome

1. Open `chrome://extensions`
2. Zet **Developer mode** rechtsboven aan
3. Klik **Load unpacked**
4. Selecteer de map `/extension/` in deze repo
5. Open https://lowlands.nl/acts/ — badges verschijnen op de cards

## Iteratie

Geen build step — vanilla JS. Na een wijziging in `src/*`:
- Klik op **reload** bij de extensie in `chrome://extensions`
- Refresh de lowlands.nl-tab

Wil je hot-reload + TypeScript? Migreer dan naar `@crxjs/vite-plugin` zoals beschreven in `docs/NEXT-chrome-extension.md`.

## Architectuur

```
manifest.json          — MV3, content_script + popup, host permissies
src/storage.js         — fetch + 24u cache van acts.json (gedeeld door content + popup)
src/content.js         — DOM-injectie + MutationObserver voor SPA
src/badge.css          — badge styles, kleuren per categorie
popup.html             — popup markup
src/popup.css          — popup styles
src/popup.js           — popup logica (top-N, zoeken, refresh)
icons/                 — leeg; nog te vullen met 16/48/128 PNG
```

## Data contract

Slug uit URL (`/acts/<slug>/`) is de primary key voor matching. `acts.json`-schema staat in `../frontend/src/types.ts`.

Velden die de extensie gebruikt: `slug`, `name`, `score`, `presence_score`, `vibe_score`, `category`, `blurb`, `vibe_reason`, `nts_links`.

## DOM-selectors (geverifieerd 2026-05-17)

| Pagina | Selector |
|---|---|
| Acts-overzicht | `a.act-list-card__button` |
| Headliners | `.act-list__headliners-item a[href*='/acts/']` |
| Detail | `h1` + `location.pathname` voor slug |

Bij DOM-wijzigingen op lowlands.nl: update `src/content.js`.

## Publicatie

Voor lokaal gebruik is unpacked load voldoende. Voor Chrome Web Store: zip de hele `/extension/`-map (zonder `node_modules` of dotfiles) en upload via [Chrome Web Store Developer Dashboard](https://chrome.google.com/webstore/devconsole). Eenmalig $5 + reviewtijd.
