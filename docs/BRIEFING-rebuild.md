# Briefing — NTS / Lowlands Vibe Checker herbouwen in een nieuwe repo

Dit document is een **complete, zelfstandige overdracht**. Geef het in z'n geheel mee aan een
verse Claude Code-sessie (in een lege/andere repository) en die sessie kan het hele project
opnieuw bouwen zónder toegang tot de originele repo. Alle context, prompts, schema's en
design-tokens staan hieronder ingebakken.

> Bijnaam in de wandelgangen: "Lowlands Fibechecker". Officiële naam: **NTS Vibe Checker**.

---

## 0. Kan dat — in een andere repo bouwen?

Ja. Het project bestaat uit losse, goed afgebakende onderdelen (data-pipeline → `acts.json` →
frontend + overlay). Er is geen harde koppeling aan de oude repo behalve één URL waar `acts.json`
vandaan komt; die pas je aan naar het nieuwe deploy-domein. Plak dit document in de eerste prompt
van de nieuwe sessie (zie §13 voor een kant-en-klare openingsprompt).

---

## 1. Wat is het

Een mini web-app + overlay die **elke act van Lowlands 2026 scoort op "NTS-gehalte"**: zou
[NTS Radio](https://www.nts.live) deze artiest draaien of programmeren? De score combineert twee dingen:

1. **Presence-score (harde data):** heeft de act aantoonbaar een eigen NTS-show, guest-spots, of
   een Infinite-Mixtape-credit? Puur uit de NTS API.
2. **Vibe-score (Claude-oordeel):** past de act *esthetisch* bij NTS op basis van bio + genres,
   ook als ze nog nooit op NTS zijn geweest? Geoordeeld door Claude met een streng "wat-is-NTS"-rubriek.

De eindscore = `max(presence, vibe)`. Daaruit volgt een categorie/badge (RESIDENT … OFF SPECTRUM).

Output is één statisch bestand `acts.json` dat door alle clients (web-app, browser-extensie,
bookmarklet) wordt geconsumeerd. De clients doen **geen** scoring — ze zijn dunne viewers.

---

## 2. Architectuur

```
   ┌─────────────────────────────────────────────────────────┐
   │ PIPELINE (Python, lokaal draaien)                         │
   │   lineup.py  → Lowlands acts + bio + genres (Wagtail API) │
   │   nts.py     → NTS shows / slug-lookup / mixtape-credits  │
   │   score.py   → presence-score uit harde NTS-data          │
   │   vibe.py    → Claude beoordeelt aesthetic fit (+ blurb)  │
   │   build.py   → orchestreert alles → schrijft acts.json    │
   └───────────────────────────┬─────────────────────────────┘
                               │  frontend/public/acts.json
                               ▼
   ┌─────────────────────────────────────────────────────────┐
   │ FRONTEND (Vite + React + Tailwind, deploy op Vercel)      │
   │   laadt acts.json, toont sorteerbare/filterbare lijst     │
   │   Lowlands-huisstijl, expandbare kaarten, score-bars      │
   └─────────────────────────────────────────────────────────┘
                               │  zelfde acts.json (zelfde domein)
                               ▼
   ┌─────────────────────────────────────────────────────────┐
   │ OVERLAY-CLIENTS op lowlands.nl                             │
   │   • Chrome-extensie (Manifest V3, content-script badges)  │
   │   • Bookmarklet (inject.js) — werkt overal, ook desktop   │
   │   • iOS Userscript (Safari, Userscripts-app)              │
   └─────────────────────────────────────────────────────────┘
```

Belangrijk principe: **scoring gebeurt één keer in de pipeline**. Alle viewers lezen hetzelfde
`acts.json`. Schema-wijzigingen dus altijd op één plek (zie §6).

---

## 3. Tech-stack

| Onderdeel | Stack |
|---|---|
| Pipeline | Python 3, `httpx`, `anthropic` SDK, `Pillow` (icons) |
| LLM | Claude via Anthropic API, model `claude-sonnet-4-6` (vibe + blurbs) |
| Frontend | Vite 5 + React 18 + TypeScript + Tailwind 3 |
| Hosting | Vercel (auto-deploy bij push naar `main`) |
| Extensie | Manifest V3, vanilla JS content-script + popup |
| Mobiel | PWA-manifest, bookmarklet, iOS userscript |

`pipeline/requirements.txt`: `httpx`, `anthropic`, `pillow`.

`frontend/package.json` deps: `react`, `react-dom`. Dev-deps: `vite`, `@vitejs/plugin-react`,
`typescript`, `tailwindcss`, `postcss`, `autoprefixer`, `@types/react`, `@types/react-dom`.

---

## 4. Het scoring-model (de kern — exact overnemen)

### 4a. Presence-score (harde NTS-data) — `score.py`

Per act, op basis van NTS API-lookups:

| Signaal | Score |
|---|---|
| Eigen NTS-show, ≥50 episodes (resident) | 100 |
| Eigen NTS-show, ≥10 episodes | 92 |
| Eigen NTS-show, ≥1 episode | 85 |
| Eigen NTS-show in catalogus (0 episodes) | 80 |
| Genoemd in ≥3 andere show-descriptions (regelmatig te gast) | 65 |
| Genoemd in 2 show-descriptions | 55 |
| Genoemd in 1 show-description | 40 |
| Gecredit op een NTS Infinite Mixtape (zonder eigen show) | 70–75 |
| Niets gevonden | 0 |

`max(...)` van de toepasselijke regels. Bij elke regel wordt een leesbare reden + NTS-link bewaard.

### 4b. Vibe-score (Claude-oordeel) — `vibe.py`

Onafhankelijk van presence. Claude krijgt naam + bio + Lowlands-genres + bekende presence-signalen
en geeft een JSON terug: `{ "vibe": 0-100, "reason": "...", "blurb": "..." }`.
**De volledige system-prompt staat in §7 — neem die letterlijk over, dat is de "secret sauce".**

### 4c. Combineren + categorieën — `combine()` in `score.py`

```
score = max(presence_score, vibe_score)

if presence >= 80:      category = "RESIDENT"
elif presence >= 50:    category = "NTS-PRESENCE"
elif vibe >= 70:        category = "NTS-VIBE"
elif vibe >= 40:        category = "ADJACENT"
else:                   category = "OFF"
```

Sorteren: `(-score, -presence_score)`.

### 4d. Handmatige overrides — `pipeline/overrides.json`

Soms zit Claude ernaast (bv. een Bijlmer-collectief dat eruitziet als "mainstream nederhop" maar
juist heel NTS is). Een JSON-bestand met override per **slug** corrigeert `vibe`, `vibe_reason`
en/of `blurb`. Overschreven acts krijgen `"overridden": true` (frontend toont een "HANDMATIG"-label).

Voorbeeld:
```json
{
  "_comment": "Overrides keyed by Lowlands slug. Velden optioneel.",
  "smib": {
    "vibe": 78,
    "vibe_reason": "Bijlmer-collectief dat hip-hop, kunst en mode samenvoegt — exact het multidisciplinaire scene-werk dat NTS programmeert.",
    "blurb": "SMIB is geen 'mainstream nederhop'-act maar een Bijlmer-collectief van rappers, designers en videomakers die hip-hop, mode en visuele kunst onder één naam draaien."
  }
}
```

---

## 5. Databronnen + API-quirks (cruciaal — bespaart uren)

### 5a. Lowlands lineup — Wagtail-style API

- Lijst: `GET https://lowlands.nl/api/pages/?type=acts.ActPage&fields=title,text&limit=200`
  - Geeft `items[]`; per item: `id`, `title` (=act-naam), `text` (=bio, bevat HTML → strippen),
    `meta.htmlUrl` (laatste pad-segment = **slug**, de primary key).
- Detail (per act, voor genres/socials): `GET https://lowlands.nl/api/pages/{id}/`
  - Velden: `actGenreItems[].title` (genres), `subtitle`, `soundcloudLink`, `spotifyLink`.
- ~126 acts in 2026. Cache de responses lokaal (`data/cache/`), want je draait dit vaak.
- **Lowlands.nl is een Nuxt SPA** — relevant voor de overlay (zie §9), niet voor de pipeline.

### 5b. NTS — `https://www.nts.live/api/v2`

- `GET /shows/{slug}` — werkt voor élke show, geen offset-limiet. **Dit is de hoofd-probe.**
  Genereer slug-kandidaten uit de act-naam (zie slugify-strategie hieronder), probeer ze op volgorde.
- `GET /shows?limit=24&offset=N` — alfabetisch, maar **caps rond offset 1000** (daarboven HTTP 422).
  Dekt dus grofweg A–N. Gebruik dit alleen om show-descriptions te doorzoeken voor guest-mentions,
  niet als enige bron.
- `GET /shows/{alias}/episodes?limit=1` — `metadata.resultset.count` = goedkope episode-telling.
- `GET /mixtapes` — `results[].credits[].name` = artiesten gecredit op Infinite Mixtapes.

**Slug-strategie (NTS):** `slugify(name)` = lowercase, haakjes weg (`(live)` etc.), non-alfanumeriek
weg, spaties → koppeltekens. Kandidaten van specifiek → algemeen: basis-slug, dan zonder trailing
modifiers (`-live`, `-dj-set`, `-b2b`, …), dan losse delen alléén bij expliciete multi-artist-signalen
in de originele naam (`with`, `&`, `b2b`, `vs`, `+`). Filter kandidaten < 4 tekens weg.

**Guest-mention matching:** zoek act-naam met word-boundary regex in show-`description` + `name`.
Skip namen < 5 tekens of generieke woorden (`speed`, `iconic`, `new wave`, `celeste`, `nala`,
`keo`, `sor`) → die alleen op exacte show-naam-match, anders te veel false positives.

---

## 6. Het data-contract: `acts.json`

Dit is het enige koppelvlak tussen pipeline en alle viewers. **Wijzig het schema op één plek.**

```ts
// frontend/src/types.ts
export type NtsLink = { label: string; url: string };
export type Category = "RESIDENT" | "NTS-PRESENCE" | "NTS-VIBE" | "ADJACENT" | "OFF";

export type Act = {
  slug: string;            // "floating-points-live" — primary key, = laatste segment van lowlands.nl/acts/<slug>/
  name: string;            // "Floating Points (live)"
  url: string;             // canonieke Lowlands-URL
  bio: string;
  lowlands_genres: string[];
  subtitle: string;
  soundcloud: string;
  spotify: string;

  score: number;           // 0-100 eindscore = max(presence, vibe)
  presence_score: number;
  vibe_score: number;
  vibe_reason: string;     // korte zin, waarom deze vibe-score
  category: Category;

  reasons: string[];       // presence-redenen (mensleesbaar)
  overridden: boolean;     // true als overrides.json toegepast
  nts_links: NtsLink[];
  own_show: string | null; // NTS show_alias
  nts_genres: string[];
  nts_moods: string[];
  nts_description: string | null;
  episode_count: number;
  blurb: string;           // 2 zinnen NTS-redactionele toon
};

export type Payload = {
  generated_at: string;    // ISO, "...Z"
  acts: Act[];
  stats: {
    total: number;
    with_own_show: number;
    with_presence: number;
    with_vibe_50_plus: number;
    with_vibe_70_plus: number;
  };
};
```

De extensie kopieert dit type naar `extension/src/types.ts` (of importeert het).
**Matching tussen overlay en data gaat altijd via `slug` uit de URL**, nooit via naam-fuzzy.

---

## 7. De Claude-prompts (letterlijk overnemen — dit bepaalt de kwaliteit)

Twee LLM-stappen. Beide met `claude-sonnet-4-6`, system-prompt met `cache_control: ephemeral`.
Antwoord parsen als JSON (regex eerste `{...}`-object). Cache per slug in `data/cache/`.

### 7a. Vibe-judgment — system-prompt (`vibe.py`)

```
Je beoordeelt of een muziekact bij NTS Radio past — niet of ze al op NTS hebben gespeeld, maar of NTS ze AUTHENTIEK zou willen draaien of programmeren.

NTS is een Londens internetstation dat zich onderscheidt door:
- Crate-digging, leftfield, non-algoritmische curatie
- Genre-fluïditeit: ambient, dub, jazz, post-punk, global/exotica, experimentele electronics, broken beat, gospel, library music, modulair, kosmische muziek, deep house/techno (vooral underground), no wave, drone, footwork, gqom, kuduro, dancehall (alleen ondergrond), zero-budget DIY
- Underground voorop: independent labels (Hessle Audio, Honest Jon's, Dekmantel, Awesome Tapes From Africa, Pre, Sound Signature, Whities, Honey Soundsystem, Ostgut Ton, Black Truffle, Editions Mego, Mexican Summer kant)
- Aesthetic: cult, kennersmuziek, sub-cultureel, scene-driven — niet voor de massa
- Steden: Londen, Berlijn, Manchester, Amsterdam-Bijlmer/noord, Bristol, Lisbon, NY underground, Detroit, Tokyo experimenteel

KRITIEK — TAAL/REGIO IS GEEN UITSLUITINGSGROND:
NTS draait regelmatig Nederlandstalige, Franse, Portugese, Arabische artiesten. Dat een act in het Nederlands rapt of zingt zegt NIETS over NTS-fit. Wat telt is scene-credibility, niet taal.

WAT WEL NTS-vibe (score hoog):
- Experimentele/underground electronica, ambient, drone
- Eclectische crate-diggers, dj's met diepe selecties
- Post-punk, no-wave, leftfield gitaarbands met arty kant
- Jazz/jazz-adjacent (spiritueel, vrij, fusion-randen)
- Global music met curator-aanpak (geen exoticisme)
- DIY, kleine labels, scene-leiders zonder pop-aspiraties
- Hardcore/punk MET artistiek bewustzijn (zoals Turnstile, niet generieke deathcore)
- Multidisciplinaire collectieven die muziek combineren met mode, kunst, video (Bijlmer-scene zoals SMIB, NY-collectieven zoals Standing on the Corner)
- Protest/politieke hip-hop met DIY of punk-energie (NTS heeft veel programma's gewijd aan radicale hip-hop, b.v. shows van Mike, Pink Siifu, kant van Death Grips/JPEGMAFIA, NL: Typhoon's politiekere werk, IJsland)
- Niche Nederlandstalige acts met scene-aansluiting: experimentele beats, dubpoëzie, art-rap, jazz-fusion (b.v. Sevdaliza, Sef's leftfield werk, Eefje de Visser's experimentele kant, Goldband's lo-fi vroege werk)
- Avant-pop/art-pop met productie die afwijkt van Top 40-formules

WAT GEEN NTS-vibe (score laag):
- Mainstream radio-pop, Top 40-singles met geprogrammeerde Spotify-distributie
- Generieke EDM, big-room house, hands-up, hardstyle
- Mainstream NL hip-hop met radio-singles (Antoon, Frenna chart-werk, Snelle, generieke nederhop) — let op: dit is een SMAAL segment, niet "alle NL hip-hop"
- Stadion-rock zonder undergroundwortels
- Radio-vriendelijke singer-songwriters
- Festival-fillers zonder eigen scene-aansluiting

VUISTREGELS bij twijfel:
1. Heeft de act een eigen label, of staat 'ie bij een onafhankelijk label? → punten omhoog
2. Werkt de act vaak samen met experimentele/leftfield producers? → punten omhoog
3. Is de productie ruwer of meer art-school dan radio-glad? → punten omhoog
4. Is er een politieke, DIY of artistieke missie achter het werk? → punten omhoog
5. Klinkt het als iets dat een NTS-dj zou kunnen mixen tussen ambient en footwork? → punten omhoog
6. Is de productie radio-glad én de teksten over uitgaan/feest/lifestyle? → punten omlaag
7. Wordt de act geprogrammeerd op de hoofdpodia van álle festivals? → meestal punten omlaag (uitzondering: cult-artiesten zoals JPEGMAFIA, Turnstile)

Output: één strikt JSON-object, niets daarbuiten:
{
  "vibe": <int 0-100>,
  "reason": "<korte zin, ~15 woorden, waarom deze score>",
  "blurb": "<2 zinnen, NTS-redactionele toon — droog, feitelijk, crate-digger-bewoording, GEEN hype, GEEN marketing>"
}

Voor zeer lage vibe (<20): blurb is één droge zin dat het buiten NTS-spectrum valt.
```

User-message template (vibe):
```
Act: {name}
Lowlands beschrijving: {bio (max ~1200 tekens)}
Lowlands genres: {comma-separated genres}
{nts_signal}

Beoordeel.
```
Waarbij `{nts_signal}` óf "NTS-aanwezigheid: geen — beoordeel puur op aesthetic fit." is, óf
"Bekende NTS-aanwezigheid: {redenen} (presence score N)".

### 7b. Blurb-toon (los hulpscript `blurbs.py`, optioneel — vibe.py levert al een blurb)

System-prompt kern (toon-referentie, handig om te hergebruiken):
```
Je schrijft korte, droge, feitelijke blurbs in de redactionele toon van NTS Radio.
Stijl: helder, beknopt, crate-digger-bewoording, geen hype-taal, geen uitroeptekens, geen marketing-clichés.
Engels OF Nederlands — kies de taal van de input.
Lengte: 2 zinnen, max ~50 woorden. Geen quotes, geen titel. Begin direct met inhoud.

Goede voorbeelden:
- "Detroit-geboren, Berlijn-gestationeerd. Hunee draait dwars door house, soul, jazz en exotica zonder ooit op autopilot te gaan."
- "Floating Points heeft een PhD in neurowetenschappen en bouwt zijn livesets met dezelfde precisie. Modulaire synths, gospel-piano, broken beat — alles past."

Slechte voorbeelden (vermijden):
- "Een geweldige artiest die je niet mag missen!"
- "Met zijn unieke stijl tovert hij elke dansvloer om in..."
```

---

## 8. Design system — Lowlands.nl huisstijl

Maximalistisch, candy-pop, **zero rounding** (alle hoeken scherp), all-caps display-type, volle
saturatie. De web-app is data-dicht dus we cherry-picken: donker-warme indigo achtergrond,
kleur-gecodeerde score-badges, scherpe knoppen, condensed all-caps koppen.

### Kleuren (Tailwind `ll`-namespace / CSS-vars)

| Token | Hex | Gebruik |
|---|---|---|
| `ll-red` | `#b80028` | merk-rood, RESIDENT-badge, accenten |
| `ll-indigo` | `#1b1464` | knop-bg, surfaces, borders |
| `ll-indigo-deep` | `#0d0840` | pagina-achtergrond |
| `ll-cyan` | `#d9fff9` | tekst op donker, NTS-VIBE-badge, links |
| `ll-blue` | `#1371c3` | NTS-PRESENCE-badge, secundaire links |
| `ll-cream` | `#ffebe7` | lichte tekst |
| `ll-ink` | `#262626` | donkere tekst op licht |

### Typografie
- **Display/koppen:** Bebas Neue (fallback Oswald, Impact), all-caps, `letter-spacing ~0.02em`.
- **Body:** Inter (fallback Helvetica Neue, Arial), 400/500/700.
- Laden via Google Fonts: `family=Bebas+Neue&family=Inter:wght@400;500;700`.

### Herbruikbare CSS-classes (in `index.css`)
- `.ll-tag` — Bebas Neue, uppercase, `letter-spacing 0.08em`, 11px, line-height 1 (kleine labels).
- `.ll-btn` — Bebas Neue, uppercase, `border-radius:0`, padding `10px 14px`, color-transition.
- `.ll-display` — grote display-variant.

### Badge-styling per categorie (web + overlay)
| Categorie | Achtergrond | Tekst | Label web | Label overlay |
|---|---|---|---|---|
| RESIDENT | `ll-red` | cream | "NTS RESIDENT" | "NTS BAAS" |
| NTS-PRESENCE | `ll-blue` | cream | "NTS PRESENCE" | "PRESENCE" |
| NTS-VIBE | `ll-cyan` | indigo | "NTS VIBE" | "VIBE" |
| ADJACENT | cream/30 | cream | "ADJACENT" | "ADJACENT" |
| OFF | indigo | cream/40 | "OFF SPECTRUM" | "OFF" |

Tailwind config: extend `colors.ll.*` zoals boven, `fontFamily.display`/`.body`, en
`borderRadius.DEFAULT: "0"`.

---

## 9. De overlay-clients op lowlands.nl

Doel: op lowlands.nl naast elke act-naam automatisch een NTS-badge tonen, plus op detail-pagina's
een floating widget met een "Waarom?"-paneel (blurb + vibe_reason + NTS-links). Alle clients lezen
hetzelfde gehoste `acts.json` (cache 24u).

### Lowlands DOM-targets (geverifieerd, BEM-classes, redelijk stabiel)
| Pagina | URL-pattern | Selector |
|---|---|---|
| Acts-overzicht | `lowlands.nl/acts/` | `a.act-list-card__button` (`href` bevat slug) |
| Headliners | `lowlands.nl/acts/` | `.act-list__headliners-item a[href*='/acts/']` |
| Act-detail | `lowlands.nl/acts/<slug>/` | slug uit URL; `h1` voor naam |

### Gotcha: Nuxt SPA
Lowlands is een Nuxt SPA. Initiële DOM is SSR'd, maar client-side navigatie herlaadt de pagina niet.
Gebruik daarom een **`MutationObserver` op `document.body`** (debounced ~150ms) plus een interval
(~500ms) dat `location.href` watcht, om badges opnieuw te injecteren bij navigatie. Markeer al
verwerkte elementen met een `data-`attribuut zodat je niet dubbel injecteert. CSS-isolatie via
eigen prefix (`ntsvc-`) en injected stylesheet.

### Drie distributievormen
1. **Chrome-extensie (Manifest V3)** — voor de planningsfase op desktop.
   - `manifest.json`: `permissions: ["storage"]`, `host_permissions` voor `lowlands.nl/*` +
     het acts.json-domein, content-script (`storage.js` + `content.js`) + `badge.css` op
     `https://lowlands.nl/*` `run_at: document_idle`, en een `action.default_popup`.
   - `storage.js`: fetch `acts.json` + cache via `chrome.storage.local` (24u), `indexBySlug`,
     `slugFromHref` helper.
   - `content.js`: injectie-logica + observer (hierboven).
   - Popup: top-N lijst + zoek (en later "wat speelt nu?" zodra timetable bestaat).
2. **Bookmarklet** — werkt overal zonder installatie. Eén regel die `inject.js?t=<ts>` van het
   deploy-domein in de pagina laadt. `inject.js` doet hetzelfde als het content-script maar
   standalone. Cache-bust met timestamp.
3. **iOS Userscript** — Safari + gratis "Userscripts"-app, "New Remote" naar
   `<domein>/ntsvc.user.js`. Draait automatisch op lowlands.nl. (Chrome-extensies werken niet
   op iOS, daarom dit pad.)

Een `InstallModal` in de web-app legt per platform (desktop/iOS/Android) uit hoe te installeren,
met kopieerbare bookmarklet en userscript-URL.

---

## 10. Mobiel / PWA

- `frontend/public/manifest.webmanifest`: standalone, portrait, `background_color #0d0840`,
  `theme_color #b80028`, icons 192/512/512-maskable, `lang: nl`.
- Icons worden gegenereerd door `pipeline/icons.py` (Pillow): indigo vlak + rode inset + "NTS VIBE
  CHECKER" in cyaan. Maakt ook `apple-touch-icon.png` (180) en favicons (16/32).
- **Service worker: let op.** Er stond een SW die gebruikers op stale builds vastzette. Huidige
  staat = **kill-switch SW** (`sw.js`) die zichzelf unregistert, alle caches leegt en open clients
  herlaadt. Advies voor de herbouw: **begin zónder service worker.** Voeg pas een echte
  network-first-voor-HTML SW toe als de site stabiel is op mobiel, anders krijg je
  cache-vastloop-bugs. (PWA "add to home screen" werkt prima zonder SW.)

---

## 11. Setup & run

```bash
# Pipeline
cd pipeline
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt          # httpx, anthropic, pillow
export ANTHROPIC_API_KEY=...             # of pipeline/.env met ANTHROPIC_API_KEY=...
python build.py                          # → schrijft frontend/public/acts.json
python icons.py                          # (eenmalig) PWA-icons genereren

# Frontend
cd ../frontend
npm install
npm run dev                              # lokaal
npm run build                            # productie → dist/
```

`build.py` orkestreert: lineup → NTS-data → presence-score → vibe-judgment → `combine` → schrijft
`acts.json` + print top-20. Alle netwerk-stappen cachen naar `data/cache/` (gitignore'd), dus
herhaald draaien is goedkoop; gebruik `force=True` per fetch-functie om te verversen.

`.gitignore` minimaal: `node_modules/`, `dist/`, `.venv/`, `data/cache/`, `.env`.

---

## 12. Deploy (Vercel)

`vercel.json`:
```json
{
  "buildCommand": "cd frontend && npm install && npm run build",
  "outputDirectory": "frontend/dist",
  "framework": null
}
```
Auto-deploy bij push naar `main`. `acts.json` wordt mee-gedeployd als statisch bestand op
`https://<jouw-domein>/acts.json` — dát is de URL die je in de extensie/bookmarklet/userscript
hardcodet. **Vervang overal het oude `nts-vibe-checker.vercel.app` door je nieuwe domein.**

---

## 13. Aanbevolen mappenstructuur

```
/pipeline/
  build.py          # orchestrator
  lineup.py         # Lowlands Wagtail API
  nts.py            # NTS API + slug-lookup + mixtapes
  score.py          # presence-score + combine + overrides
  vibe.py           # Claude vibe-judgment (system-prompt §7a)
  blurbs.py         # (optioneel) losse blurb-generator
  icons.py          # PWA-icon generatie (Pillow)
  overrides.json    # handmatige correcties per slug
  requirements.txt
/frontend/
  index.html
  vite.config.ts
  tailwind.config.js
  postcss.config.js
  tsconfig.json
  package.json
  src/
    main.tsx
    App.tsx         # lijst, tabs (vibe 40+ / alle), zoek, expandbare kaarten
    InstallModal.tsx
    types.ts        # data-contract §6
    index.css       # Lowlands-tokens + .ll-* classes
  public/
    acts.json       # ← pipeline-output (gegenereerd)
    manifest.webmanifest
    inject.js       # bookmarklet-payload
    ntsvc.user.js   # iOS userscript
    sw.js           # (optioneel; begin zonder)
    icon-*.png / favicon-*.png / apple-touch-icon.png
/extension/         # (optioneel, fase 2)
  manifest.json
  popup.html
  src/{storage.js, content.js, badge.css, popup.js, popup.css, types.js}
/docs/
  DESIGN-lowlands.md
/vercel.json
/README.md
```

---

## 14. Herbouw-volgorde (aanbevolen)

1. **Pipeline-skelet** — `lineup.py` (Lowlands API) → cache → ruwe acts met bio + genres. Verifieer
   ~126 acts.
2. **NTS-laag** — `nts.py` slug-lookup + mixtape-credits; `score.py` presence-scoring. Print top-20
   presence.
3. **Vibe-laag** — `vibe.py` met de system-prompt uit §7a (cache!). `combine()` + categorieën.
   Schrijf `acts.json`.
4. **Overrides** — `overrides.json` voor de paar gevallen waar Claude ernaast zit.
5. **Frontend** — Vite/React/Tailwind, design-tokens §8, lijst + filters + expandbare kaarten + zoek.
   Laadt `/acts.json`.
6. **Deploy** — Vercel, `vercel.json`, controleer dat `acts.json` live staat.
7. **Mobiel** — PWA-manifest + icons (`icons.py`). (SW overslaan in eerste instantie.)
8. **Overlay** (optioneel, fase 2) — bookmarklet + userscript eerst (laagdrempelig), Chrome-extensie
   daarna. Hardcode het nieuwe acts.json-domein.

---

## 15. Open punten / gotchas

- **NTS `/shows` offset cap (~1000 → 422):** vertrouw op directe slug-lookup, niet op de listing.
- **False positives bij guest-mentions:** korte/generieke namen apart afhandelen (zie §5b).
- **Nuxt SPA:** MutationObserver + URL-watch nodig in de overlay (zie §9).
- **Service worker:** begin zonder; oude SW veroorzaakte stale-build-vastlopers (zie §10).
- **Timetable ontbreekt nog:** Lowlands publiceert tijdtafels 1–2 weken vóór het festival
  (21–23 aug 2026). Een "wat speelt nu?"-modus vereist `set_time` + `stage` per act. Voeg t.z.t.
  een `timetable.py`-stap toe die dit in `acts.json` injecteert; viewers lezen die velden, scrapen niets.
  Bronnen op betrouwbaarheid: Lowlands eigen API (`actDateItems`, was leeg op 2026-05-17 → check vanaf juli),
  dan Festileaks.
- **Domein-URL:** zoek-en-vervang het oude Vercel-domein overal vóór deploy.
- **Model-naam:** pipeline gebruikt `claude-sonnet-4-6`. Gebruik het nieuwste beschikbare
  Sonnet/Opus-model in de nieuwe sessie als dat verstandiger is.

---

## 16. Kant-en-klare openingsprompt voor de nieuwe sessie

> Ik wil de **NTS Vibe Checker** opnieuw bouwen in deze (lege) repository. Hieronder staat een
> volledige briefing met de architectuur, het scoring-model, de exacte Claude-prompts, het
> `acts.json`-datacontract, de Lowlands- en NTS-API-quirks en de design-tokens. Lees het helemaal
> en bouw het project op in de volgorde uit §14, te beginnen met de Python-pipeline (lineup → NTS →
> presence-score → Claude vibe-judgment → `acts.json`). Frontend en deploy daarna; de
> browser-overlay is fase 2. Stel me eerst deze vragen: (1) op welk domein gaat dit deployen
> (voor de hardcoded acts.json-URL)? (2) heb ik een `ANTHROPIC_API_KEY` klaarstaan? (3) wil je de
> Chrome-extensie + bookmarklet in deze sessie, of eerst alleen web-app + pipeline?
>
> [plak hier de rest van dit document, §1 t/m §15]
```
```
