# NTS Vibe Checker — Chrome Extension

Injecteert NTS Vibe-badges op festival-line-ups. Data komt uit je NTS Vibe
Checker-deploy (`festivals/index.json` + de per-festival JSON) — geen scoring of
scraping in de extensie zelf.

## Status: v0.2.0 — generiek voor elk festival

- ✅ **Werkt op elke festival-site**: badges verschijnen overal waar de
  zichtbare tekst overeenkomt met een act-naam (naam-matching).
- ✅ Kiest automatisch het juiste festival op basis van het domein
  (`lowlands.nl` → `lowlands`, `hiddengarden.nl` → `hiddengarden`, …) en laadt
  het bijbehorende `festivals/<id>.json` van je deploy.
- ✅ Lowlands houdt zijn precieze slug-matching (cards, headliners, detailpagina
  + "Waarom?"-paneel) — ongewijzigd.
- ✅ Klik op een badge → "Waarom?"-paneel met score, blurb en NTS-links.
- ✅ Popup: festival-kiezer, top 10/25/50 + zoekveld, instelbare data-URL.
- ✅ Cache 24u via `chrome.storage.local`, met stale fallback bij netwerkfout.

## Live scan: badges op ELKE site (klik-om-te-scannen)

Naast de vaste festival-data kun je op een willekeurige website **"Scan deze
pagina"** klikken (knop in de popup). De extensie:

1. zoekt korte, naam-achtige teksten op de pagina (filtert UI-woorden weg);
2. checkt eerst de client-cache (elke artiest wordt maar één keer opgezocht);
3. stuurt alleen de onbekende namen naar de backend `/api/score`;
4. plakt een badge bij elke act met NTS-relevantie (categorie ≠ OFF).

De backend (`api/score.py`, serverless op Vercel) zoekt per naam live NTS op en
laat Claude de "vibe" beoordelen. Vereist op je Vercel-deploy:

- **`ANTHROPIC_API_KEY`** als *Environment Variable* (Project → Settings →
  Environment Variables). Zónder key werkt het ook, maar dan alleen
  presence-scores (NTS-data), geen vibe-oordeel.
- Niets verder nodig: caching gebeurt client-side in de extensie. (Een
  server-side cache zoals Vercel KV kan later, voor lagere kosten bij meerdere
  gebruikers.)

> **Eén onzekerheid die alleen een echte deploy uitwijst:** of NTS-requests
> vanaf Vercel-IP's slagen. Test na deploy met
> `https://<jouw-deploy>/api/score?names=Hunee` — krijg je een `presence_score`
> > 0, dan werkt de NTS-kant. Zo niet (NTS blokkeert het IP), dan vallen de
> presence-scores op 0 terug en zie je alleen vibe-gebaseerde badges.

Kosten: alleen een Claude-call per *nieuwe* artiest; herhaalde scans/bezoeken
komen uit cache.

## Eénmalig: data-URL instellen

De extensie haalt data van een deploy. Standaard `nts-vibe-checker.vercel.app`.
Heb je een eigen deploy? Open de popup → **Instellingen** → vul je deploy-URL in
→ **Opslaan & herladen**. (Zonder deploy met `festivals/index.json` verschijnen
er geen badges.)

## Lokaal laden in Chrome

1. Open `chrome://extensions`
2. Zet **Developer mode** rechtsboven aan
3. Klik **Load unpacked**
4. Selecteer de map `/extension/` in deze repo
5. Open een festival-site waarvoor je data hebt gegenereerd (bv.
   `https://hiddengarden.nl/`) — badges verschijnen naast de act-namen.

> Eerste keer geen badges? Check via de popup of het festival in de lijst staat
> (= het staat in `festivals/index.json` op je deploy) en of de data-URL klopt.

## Iteratie

Geen build step — vanilla JS. Na een wijziging in `src/*`:
- Klik op **reload** bij de extensie in `chrome://extensions`
- Refresh de festival-tab

## Architectuur

```
manifest.json    — MV3, content_script op https://*/*, popup, host permissies
src/storage.js   — deploy-resolutie (host → festival), fetch + 24u cache, naam/slug-index
src/content.js   — DOM-injectie: lowlands=slug-matching, overig=naam-matching + observer
src/badge.css    — badge styles (absoluut voor Lowlands, inline voor generiek)
popup.html/css/js— popup: festival-kiezer, top-N, zoeken, refresh, data-URL
```

## Hoe matching werkt

- **Lowlands** (`lowlands.nl`): slug uit `/acts/<slug>/` — exact, zoals voorheen.
- **Elk ander festival**: de extensie normaliseert act-namen (lowercase, accenten
  weg, `(live)`/`[edit]` weg) en zoekt leaf-elementen waarvan de tekst exact
  gelijk is aan een act-naam. Geen site-specifieke selectors nodig; werkt dus op
  willekeurige festival-sites. Nadeel: bij heel generieke namen kan een enkele
  false match optreden.

`acts.json`/`festivals/<id>.json`-schema staat in `../frontend/src/types.ts`.
Gebruikte velden: `slug`, `name`, `url`, `score`, `presence_score`,
`vibe_score`, `category`, `blurb`, `vibe_reason`, `nts_links`, `overridden`.

## Permissies

`https://*/*` — nodig omdat de extensie op elke festival-site moet kunnen
draaien. Op sites zónder festival-data doet de extensie niets (één gecachete
`index.json`-check, daarna stop). Voor de Chrome Web Store is dit een brede
permissie; voor persoonlijk/unpacked gebruik prima.

## Publicatie

Voor lokaal gebruik is unpacked load voldoende. Voor Chrome Web Store: zip de
hele `/extension/`-map (zonder dotfiles) en upload via het
[Developer Dashboard](https://chrome.google.com/webstore/devconsole).
