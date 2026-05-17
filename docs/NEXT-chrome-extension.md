# Briefing — Chrome Extension follow-up

Hand dit document over aan een nieuwe Claude-sessie als je de Chrome-extensie wilt bouwen. Het bevat alle context die je nodig hebt om koud te starten zonder de eerdere sessie te lezen.

---

## Wat is er al

Er bestaat een **werkende web-app** voor de NTS Vibe Checker:

- **Live**: https://nts-vibe-checker.vercel.app
- **Repo**: https://github.com/ErikWeertsOG/nts-vibe-checker (lokaal: `/Users/erikweerts/NTS vibe checker/`)
- **Data**: `https://nts-vibe-checker.vercel.app/acts.json` — gegenereerd door een Python-pipeline die Lowlands lineup + NTS data + Claude-vibe-judgments combineert
- **Stack**: Vite + React + Tailwind, ge-deployd op Vercel met auto-deploy bij push naar `main`

De extensie hoeft geen scoring opnieuw te doen — die wordt al gedaan in de pipeline van de hoofd-repo en als JSON uitgeleverd.

## Doel van de extensie

Op alle Lowlands-eigendomspagina's automatisch een **NTS Vibe-badge** injecteren naast elke act-naam, zodat de gebruiker bij het scrollen door het programma direct ziet wat NTS-baas materiaal is. Plus een popup met "wat speelt er NU"-mode zodra de timetable beschikbaar is.

**Niet doen**: opnieuw scoren, opnieuw scrapen, eigen UI bouwen die los staat van Lowlands. De extensie is een **dunne viewer** bovenop de bestaande data.

## Architectuur-keuze

**Aanbevolen**: één map `/extension/` in deze repo toevoegen, gepubliceerd als losse Chrome Web Store entry maar onder dezelfde versiebeheer. Voordelen:
- `acts.json`-schema-wijzigingen in de pipeline blijven gesyncd met wat de extensie verwacht
- Eén plek voor design-tokens (`docs/DESIGN-lowlands.md`)
- Ervaringen tussen web + extensie vergelijkbaar te houden

**Niet doen**: aparte repo. Dan loopt het schema uit elkaar.

## Data contract

De extensie haalt op laad-tijd één keer `https://nts-vibe-checker.vercel.app/acts.json` op (cache 24h via `chrome.storage.local`). Schema is gedefinieerd in `/frontend/src/types.ts` — kopieer die naar `/extension/src/types.ts` of importeer via build-step.

Relevante velden per act:
```ts
{
  slug: string;          // "floating-points-live" — matcht laatste segment in lowlands.nl/acts/<slug>/
  name: string;          // "Floating Points (live)"
  score: number;         // 0-100, finale score
  presence_score: number;
  vibe_score: number;
  category: "RESIDENT" | "NTS-PRESENCE" | "NTS-VIBE" | "ADJACENT" | "OFF";
  blurb: string;         // 2-zin NTS-stijl beschrijving
  vibe_reason: string;
  nts_links: { label: string; url: string }[];
  // ...meer in types.ts
}
```

**Matching-strategie**: gebruik de **slug uit de URL** (`/acts/<slug>/`) als primary key. Naamfuzzy is rommelig — slug is exact.

## Lowlands DOM-targets

Verified op 2026-05-17. Class-namen zijn BEM en lijken stabiel (te kwetsbaar voor één-letter wijzigingen, robuust genoeg voor maandenlang gebruik).

| Pagina | URL-pattern | Selector voor act-elementen |
|---|---|---|
| Acts-overzicht | `lowlands.nl/acts/` | `a.act-list-card__button` (126 stuks; `href` bevat slug) |
| Act detail | `lowlands.nl/acts/<slug>/` | `h1` voor naam; slug uit URL |
| Headliners block | `lowlands.nl/acts/` | `.act-list__headliners-item` |
| Updates / Programma (toekomstig) | TBD | onbekend tot timetable live is |

**Strategie voor act-overzicht**: voor elk `act-list-card__button`-element, lees `href`, extract slug, look up in acts.json, prepend/overlay een badge-element. Plaats absoluut gepositioneerd in de hoek van de card-image. CSS-isolatie via `all: initial` of een shadow-DOM-host.

**Strategie voor detail-pagina**: één badge naast de `<h1>` met de naam, plus desgewenst een uitklap-knop "waarom?" die de blurb + vibe_reason + nts_links toont in een floating panel.

## Manifest V3 specifics

```json
{
  "manifest_version": 3,
  "name": "NTS Vibe Checker — Lowlands 2026",
  "version": "0.1.0",
  "permissions": ["storage"],
  "host_permissions": [
    "https://lowlands.nl/*",
    "https://nts-vibe-checker.vercel.app/*"
  ],
  "content_scripts": [{
    "matches": ["https://lowlands.nl/*"],
    "js": ["content.js"],
    "css": ["badge.css"],
    "run_at": "document_idle"
  }],
  "action": {
    "default_popup": "popup.html"
  }
}
```

**Belangrijke gotcha**: Lowlands is een **Nuxt SPA**. Initial DOM is wel SSR'd (HTML server-rendered), maar client-side navigatie verandert geen pageload. Gebruik een `MutationObserver` op `document.body` om act-cards te detecteren wanneer de gebruiker tussen pagina's klikt. Of luister op `popstate` + URL-changes.

## Design

Hergebruik exact dezelfde tokens als de web-app, gedocumenteerd in `/docs/DESIGN-lowlands.md`:

- **Badge-bg per categorie**: RESIDENT = `#B80028` (rood), NTS-VIBE = `#D9FFF9` (cyaan), NTS-PRESENCE = `#1371C3` (blauw), ADJACENT = grijs, OFF = donker
- **Font**: Bebas Neue (laad via Google Fonts in de injected CSS) of fallback Impact/Oswald
- **Vorm**: square corners (radius 0), max 36×36px voor compacte badges, of 48×48px voor detail-pagina

Badge-HTML zou minimaal moeten zijn:
```html
<div class="ntsvc-badge ntsvc-cat-resident" data-score="100">
  <span class="ntsvc-score">100</span>
  <span class="ntsvc-label">NTS BAAS</span>
</div>
```

## Popup ("nu"-modus)

Knop in de browser-toolbar opent een paneel (~360×600px) met:
- **"Wat speelt nu?"** — toont top 5 NTS-vibe-acts die binnen 30 min spelen (vereist timetable-data, zie hieronder)
- **Filter top-N** — top 10/25/50 NTS-baas acts uit `acts.json`
- **Snelle zoek** — typ naam, badge + blurb verschijnen

## Timetable-vraagstuk

Lowlands publiceert tijdtafels meestal 1-2 weken voor het festival (festival is 21-23 augustus 2026). Tot dan is de "nu"-modus niet bruikbaar.

**Bronnen voor timetable, in volgorde van betrouwbaarheid:**

1. **Lowlands API zelf** — onderzoeken of `actDateItems` veld (zit al in `lowlands.nl/api/pages/<id>/`) gevuld is zodra timetable bekend wordt. Was leeg op 2026-05-17. → herhalen check vanaf juli.
2. **Festileaks** — `festileaks.com/lowlands/timetable/` heeft historisch tijden, ververst wanneer Lowlands publiceert.
3. **Lowlands officiële app** — native, geen scraping mogelijk vanuit chrome extensie.

**Implementatie-tactiek**: voeg een stap toe aan de Python-pipeline (`pipeline/timetable.py`) die timetable-data ophaalt en in `acts.json` injecteert als `set_time` + `stage` per act. Extensie leest die velden, doet niets nieuws. Geen scraping in de extensie zelf.

## Alternatief track: mobile PWA

Erik gaf aan dat hij dit **op het festival op zijn telefoon** wil gebruiken. Chrome extensies werken niet op iOS Safari of de Lowlands-app. Overweeg dus ook:

- De bestaande web-app responsive houden (al grotendeels gedaan)
- "Add to Home Screen" PWA-manifest toevoegen aan `frontend/public/manifest.webmanifest`
- "Nu spelen"-modus in de bestaande site die op huidige tijd filtert

De chrome-extensie is voor de **planningsfase** (pre-festival, op laptop op werk, browsen door Lowlands.nl). De PWA is voor **tijdens 't festival** (mobiel, snelle check).

Voor deze sessie focus op de chrome-extensie. PWA komt daarna.

## Mappenstructuur voorstel

```
/extension/
  manifest.json
  src/
    content.ts         # injection logic + MutationObserver
    popup.ts           # popup UI
    storage.ts         # acts.json fetch + cache via chrome.storage
    types.ts           # gekopieerd uit ../frontend/src/types.ts
    badge.css          # geïnjecteerde styles met CSS-isolatie
  popup.html
  icons/
    icon-16.png icon-48.png icon-128.png
  package.json
  vite.config.ts       # Vite + CRX plugin
  README.md            # publicatie-instructies Chrome Web Store
```

Gebruik **`@crxjs/vite-plugin`** voor de build. Dat geeft je hot-reload tijdens dev en correcte Manifest V3 bundling.

## Opdracht voor de nieuwe sessie

Stop dit document in de eerste prompt van een nieuwe Claude-sessie samen met:

> Ik wil een chrome-extensie bouwen die de NTS Vibe Checker data toont als badges op lowlands.nl. Lees `docs/NEXT-chrome-extension.md` in de repo `/Users/erikweerts/NTS vibe checker/` — daar staat alle context. Maak een werkende eerste versie volgens dat plan. Begin met het opzetten van de map `/extension/`, de manifest, en de injection op de acts-overzichtspagina. Detail-pagina + popup daarna.

## Open vragen voor Erik bij start

Stel deze vragen aan Erik bij de eerste sessie als ze nog niet beantwoord zijn:

1. **Chrome Web Store publicatie**: alleen lokaal testen, of écht in de store gepubliceerd? (Store = $5 eenmalig + review-tijd; lokaal laden via `chrome://extensions` is gratis en direct)
2. **Badge-positie**: rechtsboven over de act-afbeelding, of náást de naam onder de afbeelding?
3. **Filter-modus**: één toggle "verberg OFF-spectrum acts op lowlands.nl" — wil je die?
4. **PWA-pad parallel**: zal ik in deze sessie ook de bestaande site PWA-ready maken, of houden we dat voor weer een aparte sessie?

## Niet vergeten

- Houd de `acts.json` URL hard-coded én de extensie zelf-updatend (cache busting elke 24u)
- Test op lowlands.nl/acts/ + minimaal 3 random act-detail pagina's
- Voeg een sectie toe aan de hoofd-repo README dat de extensie bestaat
- Commit de extensie naar de bestaande GitHub repo onder `/extension/`
