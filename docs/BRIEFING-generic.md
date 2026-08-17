# Briefing — Generieke "NTS Vibe Checker" voor élke muzieksite (URL → Claude-extractie)

Dit document is een **complete, zelfstandige overdracht**. Geef het in z'n geheel mee aan een
verse Claude Code-sessie in een lege repository en die sessie kan de generieke versie bouwen
zónder toegang tot een andere repo. Alle context, prompts, schema's en design-tokens staan
hieronder ingebakken.

**Wat dit is:** een variant van de NTS Vibe Checker die **niet aan één festival vastzit**. Je geeft
een willekeurige line-up- of festivalpagina-URL; Claude haalt de artiestennamen uit de HTML; daarna
checkt de pipeline elke artiest tegen NTS Radio (harde data + esthetisch oordeel) en schrijft het
resultaat naar `acts.json`. Werkt voor elke muzieksite waarvan de line-up in de pagina staat.

> Verschil met de Lowlands-versie: daar werd de line-up via de Lowlands-API opgehaald
> (één specifieke bron). Hier is die ene bron vervangen door een **generieke extractor-laag**.
> Al het andere (NTS-matching, vibe-oordeel, acts.json, frontend) is in essentie hetzelfde.

---

## 0. Kernidee: één laag verandert

```
Lowlands-versie:   [Lowlands API] → acts → NTS-scoring → vibe → acts.json → frontend
Generieke versie:  [URL → Claude-extractie] → acts → NTS-scoring → vibe → acts.json → frontend
                    ^^^^^^^^^^^^^^^^^^^^^^^^
                    enige nieuwe/vervangen laag
```

De "source adapter" is nu een **LLM-extractor**: geef elke line-up-URL, hij levert een
genormaliseerde lijst `{name, url?, genres?, bio?}` op. De rest van de pipeline weet niet (en hoeft
niet te weten) van welke site de namen komen.

---

## 1. Concept

Voor een opgegeven festival/line-up-URL: scoor elke act op "NTS-gehalte" — zou
[NTS Radio](https://www.nts.live) deze artiest draaien of programmeren?

- **Presence-score (harde data):** eigen NTS-show, guest-spots, Infinite-Mixtape-credit. Uit de NTS API.
- **Vibe-score (Claude-oordeel):** past de act *esthetisch* bij NTS, ook zonder NTS-historie?
- **Eindscore** = `max(presence, vibe)` → categorie/badge (RESIDENT … OFF SPECTRUM).

Output is één statisch `acts.json` dat de frontend (en evt. overlay) consumeert. Clients doen geen
scoring.

---

## 2. Architectuur

```
   ┌──────────────────────────────────────────────────────────────┐
   │ PIPELINE (Python, lokaal)                                      │
   │  extract.py → URL ophalen, HTML opschonen,                     │
   │               Claude haalt artiesten eruit → acts[]            │   ← NIEUW (de kern van deze variant)
   │  nts.py     → NTS shows / slug-lookup / mixtape-credits        │
   │  score.py   → presence-score uit harde NTS-data                │
   │  vibe.py    → Claude beoordeelt aesthetic fit (+ blurb)        │
   │  build.py   → orkestreert alles → schrijft acts.json           │
   └────────────────────────────┬─────────────────────────────────┘
                                │  frontend/public/acts.json
                                ▼
   ┌──────────────────────────────────────────────────────────────┐
   │ FRONTEND (Vite + React + Tailwind, deploy op Vercel)           │
   │  laadt acts.json, sorteerbare/filterbare lijst, thema via config│
   └──────────────────────────────────────────────────────────────┘
```

De browser-overlay (badges injecteren ÓP de festivalsite) is inherent site-specifiek en valt buiten
de generieke kern. Bewaar dat voor een optionele fase 2 per site.

---

## 3. Tech-stack

| Onderdeel | Stack |
|---|---|
| Pipeline | Python 3, `httpx`, `anthropic` SDK, `selectolax` of `beautifulsoup4` (HTML opschonen), `Pillow` (icons, optioneel) |
| LLM | Claude via Anthropic API. **Extractie op een goedkoop model (Haiku)** — het is filteren, geen redeneren. **Vibe-oordeel op het nieuwste Sonnet.** |
| Frontend | Vite 5 + React 18 + TypeScript + Tailwind 3 |
| Hosting | Vercel (auto-deploy bij push naar `main`) |

`pipeline/requirements.txt`: `httpx`, `anthropic`, `selectolax` (of `beautifulsoup4`), `pillow` (optioneel).

---

## 4. De extractor-laag (NIEUW — de kern van deze variant) — `extract.py`

Doel: van een willekeurige line-up-URL naar een schone lijst acts, **token-zuinig**. Leidend
principe: **stuur zo min mogelijk (en liefst nul) tekst naar het LLM.** Strategie in volgorde
goedkoop → duur; stop zodra je een goede lijst hebt.

### Token-budget — de regels (lees dit eerst)
1. **Structured-first = 0 tokens.** Voor de meeste muziek-/festivalsites kan de hele extractie
   zónder LLM (Stap A). Het LLM is de uitzondering, niet de regel.
2. **Stuur nooit ruwe HTML naar het LLM.** Markup is pure token-verspilling. Reduceer eerst tot een
   platte, ontdubbelde lijst kandidaat-strings (Stap B) — dat scheelt typisch 95%+ aan tokens.
3. **Cache alles op schijf** (ruwe fetch + extractie-resultaat, gekeyd op URL-hash). Een herhaalde
   run kost 0 tokens.
4. **Goedkoop model voor extractie** (Haiku): het is filteren, geen redeneren.
5. **Eén call, geen chunking** tenzij de kandidatenlijst écht groot is — pre-filtering maakt
   chunking meestal overbodig.

### Stap A — Structured data eerst (gratis, geen LLM)
Veel sites bevatten de line-up al machineleesbaar. Probeer in volgorde; bij succes: klaar.
1. **JSON-LD**: `<script type="application/ld+json">` met `MusicEvent` / `Festival` / `MusicGroup`,
   velden `performer[]` / `subEvent[].performer` / `name`. Vaak de volledige line-up, exact gespeld.
2. **Framework-data-blobs**: `__NEXT_DATA__` (`<script id="__NEXT_DATA__">`), `window.__NUXT__`,
   `window.__INITIAL_STATE__`. Bevatten meestal de line-up-JSON van SPA's — parse als JSON, geen LLM.
3. **Voor de hand liggend API-endpoint**: soms een `/api/.../acts` of `/api/pages?type=...` in de
   HTML/Network — fetch die direct (zoals de Lowlands Wagtail-API deed).

Geeft A een plausibele lijst (≥ ~10 namen)? Skip de LLM volledig.

### Stap B — token-zuinige LLM-extractie (alleen als A faalt)
1. **Fetch** met `httpx`, realistische `User-Agent`, `follow_redirects=True`, timeout ~30s.
   Cache de ruwe HTML in `data/cache/`.
2. **Hard pre-filteren tot kandidaat-strings** (dit is waar je de tokens bespaart). Verwijder
   `<script>`, `<style>`, `<svg>`, `<head>`, `nav`, `footer`. Verzamel dan alleen tekst uit
   kandidaat-elementen — anchor-teksten (`<a>`, met hun `href`), list-items en headings. Maak er een
   **ontdubbelde, newline-gescheiden platte lijst** van. Pas goedkope heuristiek toe om ruis weg te
   gooien vóór het LLM: drop regels die een URL/datum/tijd zijn, te lang zijn (volzinnen),
   navigatie-/cookie-/ticketwoorden bevatten, of leeg zijn. Een 500KB-pagina wordt zo een paar KB.
   Tip: detecteer de container met de meeste herhaalde link-structuur (de line-up-grid) en neem
   alleen díe.
3. **Eén Claude-call** (Haiku) op die kandidatenlijst met de system-prompt hieronder. Vraag compacte
   JSON (geen whitespace), bounded `max_tokens`. Alleen chunken als de lijst > ~6k tokens; merge +
   dedup achteraf.
4. **Normaliseren**: per item `{name, url, genres, bio}`; `slug = slugify(name)`; dedup
   case-insensitive op slug; filter lege/onzin-namen.

> Stuur het LLM dus een **lijst kandidaat-namen om te filteren**, niet de pagina om te parsen. Dat is
> het verschil tussen ~2k en ~50k input-tokens.

### Extractor system-prompt (concreet — overnemen; werkt op een kandidaten-lijst)
```
Je extraheert artiest-/act-namen uit de line-up van een muziek- of festivalpagina.

Geef ALLEEN echte muzikale acts terug. NIET: podia/stages, dagen, tijden, sponsors, menu-items,
ticket-/cookie-CTA's, navigatie, redactionele kopjes, of "en vele anderen"-placeholders.

Regels:
- Behoud de exacte schrijfwijze van de naam, inclusief modifiers als "(live)", "b2b", "&",
  hoofdletters en diakritieken.
- Als direct bij de naam een detail-URL, genre of korte omschrijving staat, neem die mee;
  anders laat je het veld leeg.
- Splits geen samengestelde namen (laat "A b2b B" of "A & B" staan zoals ze er staan).
- Dedupliceer.

Output: één strikt JSON-array, niets daarbuiten:
[{"name": "...", "url": "", "genres": [], "bio": ""}]
```

User-message: de **ontdubbelde kandidaten-lijst** (newline-gescheiden, geen HTML), met de instructie
"Filter de echte acts uit deze kandidaat-regels." Zet de system-prompt op `cache_control: ephemeral`
zodat herhaalde calls (bij chunking) de prompt-tokens cachen.

### Robuustheid / gotchas van de extractor
- **JS-gerenderde SPA's**: als de ruwe HTML nauwelijks namen bevat (lijst < ~5), is de line-up
  client-side gerenderd. Mitigatie: leun op Stap A (JSON-LD / data-blobs / API-endpoint). Pas als
  dat ook faalt: optioneel een headless render (Playwright) toevoegen, óf de namenlijst-fallback
  (gebruiker plakt de namen). Documenteer dit als bekende beperking.
- **Hallucinatie**: de prompt dwingt "alleen wat op de pagina staat". Valideer steekproefsgewijs;
  log de telling ("extracted N acts") zoals de pipeline al doet.
- **Bio's/genres zijn vaak leeg** bij pure namenlijsten — dat is prima, de vibe-stap kan op
  artiestkennis oordelen (zie §6).

### Output van extract.py
Lijst van `{slug, name, bio, genres, url}` — exact wat de rest van de pipeline verwacht. (In de
Lowlands-versie kwam `slug` uit de URL; hier `slug = slugify(name)`.)

---

## 5. NTS-laag (ongewijzigd t.o.v. Lowlands-versie) — `nts.py` + `score.py`

### 5a. NTS API `https://www.nts.live/api/v2`
- `GET /shows/{slug}` — werkt voor élke show, geen offset-limiet. **Hoofd-probe.** Genereer
  slug-kandidaten uit de naam (zie hieronder), probeer op volgorde.
- `GET /shows?limit=24&offset=N` — alfabetisch, **caps rond offset 1000 (HTTP 422 daarboven)**,
  dekt ~A–N. Alleen voor het doorzoeken van show-descriptions op guest-mentions.
- `GET /shows/{alias}/episodes?limit=1` — `metadata.resultset.count` = goedkope episode-telling.
- `GET /mixtapes` — `results[].credits[].name` = Infinite-Mixtape-credits.

**Slug-strategie:** `slugify(name)` = lowercase, haakjes/`(live)` weg, non-alfanumeriek weg,
spaties → koppeltekens. Kandidaten specifiek → algemeen: basis-slug, dan zonder trailing modifiers
(`-live`, `-dj-set`, `-b2b`…), dan losse delen alléén bij expliciete multi-artist-signalen
(`with`, `&`, `b2b`, `vs`, `+`). Kandidaten < 4 tekens weglaten.

**Guest-mention matching:** zoek de naam met word-boundary regex in show-`description` + `name`.
Skip namen < 5 tekens of generieke woorden (alleen exacte show-naam-match toestaan) om false
positives te beperken.

### 5b. Presence-score — `score.py`
| Signaal | Score |
|---|---|
| Eigen NTS-show, ≥50 episodes (resident) | 100 |
| Eigen NTS-show, ≥10 episodes | 92 |
| Eigen NTS-show, ≥1 episode | 85 |
| Eigen NTS-show in catalogus (0 episodes) | 80 |
| Genoemd in ≥3 andere show-descriptions | 65 |
| Genoemd in 2 show-descriptions | 55 |
| Genoemd in 1 show-description | 40 |
| Infinite-Mixtape-credit (zonder eigen show) | 70–75 |
| Niets gevonden | 0 |

Bewaar per regel een leesbare reden + NTS-link.

### 5c. Combineren + categorieën
```
score = max(presence_score, vibe_score)
if   presence >= 80: category = "RESIDENT"
elif presence >= 50: category = "NTS-PRESENCE"
elif vibe     >= 70: category = "NTS-VIBE"
elif vibe     >= 40: category = "ADJACENT"
else:                category = "OFF"
```
Sorteren: `(-score, -presence_score)`.

### 5d. Overrides — `pipeline/overrides.json`
JSON per slug die `vibe` / `vibe_reason` / `blurb` corrigeert wanneer Claude ernaast zit; gezette
acts krijgen `"overridden": true` (frontend toont "HANDMATIG"). Optioneel maar handig.

---

## 6. Vibe-laag — `vibe.py` (system-prompt letterlijk overnemen)

Claude krijgt naam + bio + genres + bekende presence-signalen en geeft JSON terug:
`{ "vibe": 0-100, "reason": "...", "blurb": "..." }`. Model: nieuwste Sonnet. Antwoord parsen als
eerste `{...}`-JSON-object. Cache per slug op schijf.

**Token-zuinig (belangrijk hier — dit is de duurste stap, 1 call per act):**
- **Prompt caching**: de grote system-prompt (§6) is identiek voor élke act → zet
  `cache_control: ephemeral` zodat alleen het korte per-act-user-bericht "verse" tokens kost. Bij
  ~100+ acts scheelt dit het leeuwendeel.
- **Schijf-cache per slug**: nooit dezelfde act twee keer beoordelen.
- **Batch-API** (optioneel): draai alle acts via de Message Batches API voor ~50% lagere kosten als
  je geen directe respons nodig hebt.
- Houd de bio kort (cap ~1200 tekens) en `max_tokens` laag (~500).

**Belangrijk voor deze variant:** bij generieke extractie is er vaak géén bio. Pas de
user-template aan zodat Claude dan op eigen artiestkennis oordeelt:
> "Geen bio beschikbaar — beoordeel op basis van wat je over deze artiest weet (scene, label,
> samenwerkingen, geluid). Als de naam onbekend is, geef een lage-zekerheid-inschatting en zeg dat
> in 'reason'."

(Optioneel: een verrijkingsstap die per onbekende naam wat context ophaalt — bv. een korte
web-search of MusicBrainz — vóór het vibe-oordeel. Niet nodig voor v1.)

### Vibe system-prompt (verbatim — dit bepaalt de kwaliteit)
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

User-template (vibe):
```
Act: {name}
Beschrijving: {bio of "(geen bio beschikbaar — beoordeel op artiestkennis)"}
Genres: {comma-separated of "n/a"}
{nts_signal}        ← "NTS-aanwezigheid: geen — beoordeel puur op aesthetic fit." óf
                      "Bekende NTS-aanwezigheid: {redenen} (presence score N)"

Beoordeel.
```

---

## 7. Data-contract: `acts.json` (gegeneraliseerd)

Zelfde als de Lowlands-versie, maar **bron-neutraal**: Lowlands-specifieke velden zijn generiek
gemaakt en er is een `source`-blok toegevoegd.

```ts
// frontend/src/types.ts
export type NtsLink = { label: string; url: string };
export type Category = "RESIDENT" | "NTS-PRESENCE" | "NTS-VIBE" | "ADJACENT" | "OFF";

export type Act = {
  slug: string;            // slugify(name) — primary key
  name: string;
  url: string;             // detail-URL indien geëxtraheerd, anders ""
  bio: string;             // vaak "" bij generieke extractie
  genres: string[];        // (heette lowlands_genres in de oude versie)
  links: NtsLink[];        // generieke externe links (soundcloud/spotify/etc) i.p.v. losse velden

  score: number;
  presence_score: number;
  vibe_score: number;
  vibe_reason: string;
  category: Category;

  reasons: string[];
  overridden: boolean;
  nts_links: NtsLink[];
  own_show: string | null;
  nts_genres: string[];
  nts_moods: string[];
  nts_description: string | null;
  episode_count: number;
  blurb: string;
};

export type Payload = {
  generated_at: string;    // ISO "...Z"
  source: {                // NIEUW: van welke pagina komt deze line-up
    festival: string;      // bv. "Down The Rabbit Hole 2026" (uit config of geëxtraheerd)
    url: string;           // de line-up-URL
    extracted_at: string;
  };
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

---

## 8. Config — `pipeline/config.json` (of CLI-args)

Maak de pipeline herbruikbaar zonder code te wijzigen:
```json
{
  "festival": "Down The Rabbit Hole 2026",
  "lineup_url": "https://...",
  "theme": "default"
}
```
`build.py` leest dit (of accepteert `--url` / `--festival` als CLI-args). Zo draai je dezelfde
pipeline voor elk festival. Cache-bestanden per host scheiden (bv. `data/cache/<host>/`) zodat
verschillende festivals elkaar niet overschrijven.

---

## 9. Frontend — generiek thema

Behoud de structuur van de Lowlands-versie (sorteerbare lijst, twee tabs "VIBE 40+" / "ALLE",
zoekveld, expandbare kaarten met score-bars + blurb + NTS-links), maar:

- **Titel** uit `source.festival`: "{festival} — NTS VIBE CHECKER".
- **Thema als config** i.p.v. hardcoded Lowlands-merk. Behoud een neutraal default-thema dat de
  badge-kleurcodering aanhoudt:

| Categorie | Badge-bg | Tekst | Label |
|---|---|---|---|
| RESIDENT | rood `#b80028` | cream | "NTS RESIDENT" |
| NTS-PRESENCE | blauw `#1371c3` | cream | "NTS PRESENCE" |
| NTS-VIBE | cyaan `#d9fff9` | indigo | "NTS VIBE" |
| ADJACENT | grijs/transp. | cream | "ADJACENT" |
| OFF | indigo `#1b1464` | cream/40 | "OFF SPECTRUM" |

Default-tokens (uit de Lowlands-versie, prima als neutraal startpunt): bg `#0d0840`, surface
`#1b1464`, accent-rood `#b80028`, cyaan `#d9fff9`, cream `#ffebe7`. Display-font Bebas Neue
(fallback Oswald/Impact), body Inter. **Zero rounding** (`borderRadius.DEFAULT: "0"`), all-caps
display, kleine `.ll-tag`-labels, platte `.ll-btn`-knoppen. Wie per festival wil herthema'en, zet
de kleuren in een `theme`-object dat via CSS-variabelen wordt toegepast.

Frontend laadt `/acts.json` op dezelfde origin (mee-gedeployd).

---

## Bonus § — Timetable-integratie (optioneel per-festival adapter)

Naast "welke acts scoren hoog?" wil je uiteindelijk ook "**welke high-scorers spelen wanneer, op
welke stage, en met welke overlap?**". Dat betekent per act een `sets`-veld met `{day, stage,
start_time}` in `acts.json`, en een frontend-tab die dat rendert als tijdrooster met NTS-kleur per
blok, plus een NU-modus tijdens het festival zelf.

**Bron per festival verschilt.** Waar de line-up-URL vaak SSR-HTML/JSON-LD levert, is het
blokkenschema meestal een **PDF**, soms een aparte JSON-endpoint, soms een niet-scrapebare app.
Dit is dus een echt **adapter**-vraagstuk: één klein contract, meerdere implementaties.

### Adapter-contract

```python
def fetch_timetable(source: str | Path) -> list[Slot]: ...
class Slot: day: str; stage: str; name: str; start_time: str
```

De rest van de pipeline weet niets van bron. Na `fetch_timetable` doe je `match_slots(slots, acts)`
en `enrich_acts(acts, match_map)` — die logica is site-agnostisch (zie hieronder).

### Adapter-varianten
1. **PDF-blokkenschema** (Lowlands, Down The Rabbit Hole, veel klassiekers). Parse met
   `pdfplumber`: haal chars + words uit elke pagina, cluster op x-coördinaat rond de tijd-tokens,
   herbouw namen op char-niveau (gap `< 0.5pt` → mergen, anders spatie — dat vangt zowel dicht
   gekernde comedy-letters als normale woordafstanden). Detecteer meerdere tijdrijen (echte
   start-times vs decoratieve half-uur-liniaal) en pak de bovenste. Filter categorielabels
   (COMEDY / THEATER / LITERATUUR) door hun eigen bounding-box.
2. **HTML/JSON schema** (soms `MusicEvent`/`subEvent` JSON-LD op de line-up-pagina met velden
   `startDate` / `location.name`). Als aanwezig: 0 tokens, direct parseerbaar.
3. **Aparte API-endpoint** (soms `/api/schedule` of iets vergelijkbaars — kijk in het Network-tabblad).
4. **Handmatige import** als laatste fallback: laat de gebruiker een CSV/JSON plakken.

### Matching-strategie (site-agnostisch)

Slot-namen komen uit de bron; act-slugs uit `acts.json`. Match in volgorde:
1. **Exact slug**: `slugify(slot.name) == act.slug`.
2. **Genormaliseerde naam** (lowercase, diakritieken weg, alleen alfanum) exact gelijk.
3. **Substring op slug**: `slot-slug` bevat een `act-slug` als volledig hyphen-token-run
   (vangt "richie-hawtin-dex-efx-x0x" → "richie-hawtin").
4. **Bi-directionele norm-substring**: kleine parser-artefacten
   (`"worldpeac dmt"` → `"worldpeace-dmt"`).
5. **`difflib.get_close_matches(cutoff=0.85)`** als laatste vangnet.

Non-matches (workshops, niet-muziek stages, kleine openers die niet in `acts.json` zitten) blijven
in de output — de frontend rendert ze in de OFF-kleur zonder score.

### Data-uitbreiding

Voeg toe aan de payload:
```ts
Act.sets?: { day: string; stage: string; start_time: string; raw_name?: string }[]
Payload.timetable?: { day; stage; name; start_time }[]   // ALLE ruwe slots, ook onmatched
```

`sets` is per-act (0..N optredens); `timetable` is de complete grid inclusief non-music/non-matched
zodat de frontend een compleet rooster kan tonen zonder alleen de gescoorde acts te zien.

### Frontend-view (grid + NU-modus)

- **Grid**: horizontaal scrollend tijdrooster per dag. Rijen = stages, kolommen = 15-min-ticks van
  09:30 → 05:00 (next day). Blokken gekleurd naar `category` (RESIDENT rood, NTS-VIBE cyaan, etc.).
  Sticky stage-label links, sticky tijdheader boven. Klik op blok → paneel met blurb + vibe-reason
  + links.
- **NU-modus**: als de huidige tijd binnen een festivaldag valt (inclusief 00:00–05:00 = "gisteren
  laat"), teken een verticale rode "NU"-lijn op de tijdpositie en auto-scroll naar dat punt. Highlight
  blokken die op dit moment spelen met een ring.
- **Filters**: categorie-drempel (ALLES / 40+ / VIBE 70+ / PRESENCE) om ruis te dimmen.
- **Wrap over middernacht**: converteer HH:MM naar "minuten sinds 09:30" — tijden < 09:30 krijgen
  +24u. Zo passen 02:00-slots naast 22:00 op dezelfde festivalrij.

### Static-source resilience (belangrijk bij PDF-bronnen)

Een PDF is een dode drop: geen etag-hint dat het schema veranderde, geen structured diff. Bouw
daar deze vier lagen omheen zodat het niet echt "statisch" voelt:

1. **Freshness-check bij elke fetch.** Stuur `If-Modified-Since` / `If-None-Match` mee met de vorige
   response-headers; als 304 → cache gebruiken, klaar. Bij 200 → SHA-256 van de bytes vergelijken
   met de vorige — pas parsen als de hash echt anders is. Bespaart tokens én laat je duidelijk zien
   wanneer de bron écht wijzigde.
2. **Diff-log tussen runs.** Roteer de vorige `slots.json` naar `slots.prev.json` vóór je de nieuwe
   schrijft. Een simpele `diff_slots(prev, current)` levert `{added, removed, moved}` (waarbij
   "moved" = zelfde `(day, name)` maar andere stage/tijd). Print dat in de build-log — je ziet zo
   direct welke acts verzet/geschrapt/toegevoegd zijn.
3. **LLM-name-fixup als laatste redmiddel voor parser-artefacten.** Als na alle rule-based
   matching er nog ongematchte slots én ongematchte canonieke acts overblijven, stuur je ze
   samen naar een goedkoop model (Haiku) met de opdracht: "map de PDF-namen naar canonieke namen
   als het overduidelijk hetzelfde artiest is, bij twijfel niet mappen." Cache de mapping op
   sha256 van de input-set — dan draait het LLM alleen als de stragglers wijzigen. Vangt
   "WORLDPEAC DMT" → "Worldpeace DMT" en "AND THE JEAN TEASERS" → "Teen Jesus and the Jean
   Teasers" af zonder dat je fuzzy-thresholds hoeft te tunen tot ze false-positives geven.
4. **Dagelijkse CI-refresh.** GitHub Action (cron 06:00 UTC + `workflow_dispatch`) die alléén de
   timetable-stap draait — geen line-up-fetch, geen vibe-judging. Als `acts.json` wijzigt: commit
   + push → Vercel deployt automatisch. Zo staat de laatste editie altijd live zonder handmatig
   ingrijpen.

Schrijf `timetable_updated_at` in de payload zodat de frontend "X uur geleden bijgewerkt" kan
tonen — kleine UX-touch die vertrouwen wekt tijdens het festival.

### Gotchas van PDF-parsing (bespaart je een middag)

- Meerdere y-rijen met times in dezelfde stage-band betekent óf twee visuele lijnen voor
  leesbaarheid (theater/comedy vs muziek in dezelfde rij, zeer dicht bij elkaar — mergen) óf een
  decoratieve half-uur-liniaal ver onder de echte tijden (skip). Drempel: als een tweede rij > 8pt
  onder de topmost tijd zit, skippen.
- Woord-bounding-boxes van `pdfplumber` bevatten descenders → categorielabel-boxen kunnen chars van
  de rij eronder "vangen". Filter op `top ± 2pt`, niet op de volle word-height.
- Sommige PDF's spellen namen als losse glyphs met tiny x-gaps (design-effect). Char-level
  reconstructie met gap-drempel is robuuster dan op woord-niveau werken.
- Padding rond time-tokens: naam-start ligt vaak 5–60pt rechts van de tijd (afhankelijk van
  slot-lengte); tolereer ~5pt links van de tijd zodat kort-vóór-de-tijd tekst nog binnen het blok
  valt.

---

## 10. Setup & run

```bash
# Pipeline
cd pipeline
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt          # httpx, anthropic, selectolax/bs4, (pillow)
export ANTHROPIC_API_KEY=...             # of pipeline/.env
python build.py --url "https://<festival>/line-up" --festival "Naam 2026"
#   → extract → NTS-scoring → vibe → frontend/public/acts.json

# Frontend
cd ../frontend
npm install && npm run dev               # of npm run build → dist/
```

`build.py` orkestreert: `extract` → NTS-data → presence-score → vibe-judgment → `combine` →
`acts.json` + print top-20. Alle netwerk- en LLM-stappen cachen naar `data/cache/`; herhaald draaien
is goedkoop. `.gitignore`: `node_modules/`, `dist/`, `.venv/`, `data/cache/`, `.env`.

---

## 11. Deploy (Vercel)

`vercel.json`:
```json
{
  "buildCommand": "cd frontend && npm install && npm run build",
  "outputDirectory": "frontend/dist",
  "framework": null
}
```
`acts.json` wordt mee-gedeployd op `https://<domein>/acts.json`. (Wil je meerdere festivals naast
elkaar tonen: schrijf `acts-<slug>.json` per festival en laat de frontend kiezen — optioneel, v2.)

---

## 12. Mappenstructuur

```
/pipeline/
  build.py          # orchestrator (leest config / CLI-args)
  extract.py        # URL → HTML → JSON-LD/blob/LLM-extractie → acts[]   ← de nieuwe laag
  nts.py            # NTS API + slug-lookup + mixtapes
  score.py          # presence-score + combine + overrides
  vibe.py           # Claude vibe-judgment (system-prompt §6)
  config.json       # festival + lineup_url + theme
  overrides.json    # handmatige correcties per slug
  requirements.txt
/frontend/
  index.html, vite.config.ts, tailwind.config.js, postcss.config.js, tsconfig.json, package.json
  src/{ main.tsx, App.tsx, types.ts (§7), theme.ts, index.css }
  public/{ acts.json (gegenereerd), manifest.webmanifest, icons }
/vercel.json
/README.md
```

---

## 13. Herbouw-volgorde

1. **Extractor** — `extract.py`: Stap A (JSON-LD / data-blobs / API-endpoint), dan Stap B
   (opschonen + Claude-extractie + dedup). Test op 2–3 verschillende festivalsites; controleer de
   namen-telling en steekproef de output.
2. **NTS-laag** — `nts.py` + `score.py`: presence-scoring op de geëxtraheerde namen. Print top-20.
3. **Vibe-laag** — `vibe.py` met de system-prompt uit §6 (cache!), name-only-afhandeling. `combine()`.
4. **acts.json** — schrijf met `source`-blok + stats.
5. **Frontend** — generiek thema (§9), titel uit `source.festival`. Laadt `/acts.json`.
6. **Deploy** — Vercel; controleer dat `acts.json` live staat.
7. **(Optioneel) overrides + per-site overlay** — fase 2.

---

## 14. Gotchas

- **JS-gerenderde SPA's**: ruwe HTML mist soms de namen → leun op JSON-LD/data-blobs/API; anders
  Playwright of namenlijst-fallback. Belangrijkste risico van deze aanpak — bouw Stap A goed.
- **Extractie-ruis**: stages/tijden/sponsors meegenomen → de prompt sluit die uit; valideer + dedup.
- **Token-kosten**: stuur nooit ruwe HTML naar het LLM — reduceer eerst tot een ontdubbelde
  kandidaten-lijst (§4), gebruik Haiku voor extractie, en cache alles op schijf.
- **Name-only vibe**: bij geen bio leunt Claude op artiestkennis; onbekende namen krijgen een
  lage-zekerheid-score — laat dat in `reason` blijken.
- **NTS `/shows` offset cap (~1000 → 422)**: vertrouw op directe slug-lookup, niet op de listing.
- **False positives bij guest-mentions**: korte/generieke namen apart afhandelen.
- **Model**: gebruik het nieuwste beschikbare Sonnet/Opus-model voor zowel extractie als vibe.
- **Domein-URL**: zet het deploy-domein als enige hardcoded waarde (frontend laadt relatief
  `/acts.json`, dus eigenlijk nergens nodig — houd het zo).

---

## 15. Kant-en-klare openingsprompt voor de nieuwe sessie

> Ik wil een **generieke NTS Vibe Checker** bouwen in deze (lege) repository: ik geef een
> willekeurige festival-/line-up-URL, Claude haalt de artiesten uit de HTML, en de pipeline checkt
> elke artiest tegen NTS Radio (harde NTS-data + esthetisch Claude-oordeel) → `acts.json` → een
> kleine React-frontend. Hieronder staat een volledige briefing met de architectuur, de
> extractor-aanpak, de exacte Claude-prompts (extractie + vibe), het `acts.json`-datacontract, de
> NTS-API-quirks en de design-tokens. Lees het helemaal en bouw in de volgorde uit §13, te beginnen
> met `extract.py` (JSON-LD/data-blob eerst, dan LLM-extractie uit opgeschoonde HTML). Stel me eerst
> deze vragen: (1) welke line-up-URL gebruiken we als eerste testcase? (2) heb ik een
> `ANTHROPIC_API_KEY` klaar? (3) wil je een neutraal default-thema of meteen per-festival themable?
>
> [plak hier de rest van dit document, §1 t/m §14]
```
```
