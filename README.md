# NTS Vibe Checker

Score elke festival-act op NTS-vibe: zou [NTS Radio](https://www.nts.live) deze
artiest draaien of programmeren? Werkt op **elke** festival-/line-up-URL.
Statische web-app + data-pipeline.

## Hoe werkt het

1. **Pipeline** (Python, lokaal):
   - `extract.py` haalt de acts uit een line-up-URL — token-zuinig:
     **Stap A** structured data (JSON-LD `MusicEvent`/`performer`, `__NEXT_DATA__`,
     `__NUXT__`); **Stap B** een goedkoop Claude-model op een *ontdubbelde
     kandidatenlijst* van korte tekstfragmenten (nooit ruwe HTML).
     Lowlands houdt zijn eigen rijke API-adapter (bio + genres + socials).
   - `nts.py` + `score.py` matchen elke act tegen de NTS-API (eigen show,
     guest-spots, mixtape-credits) → harde **presence-score**.
   - `vibe.py` laat Claude de *aesthetic fit* beoordelen → **vibe-score** + blurb.
   - `build.py` orkestreert alles en schrijft één JSON per festival.
2. **Frontend** (Vite + React + Tailwind) laadt die JSON, toont een
   gesorteerde/filterbare lijst met per-festival thema en een festival-switcher.

Eindscore = `max(presence, vibe)` → categorie (RESIDENT … OFF SPECTRUM).

## Pipeline runnen

```bash
cd pipeline
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY=...            # of zet 'm in pipeline/.env

python build.py                         # Lowlands (default) -> public/acts.json
python build.py https://festival.nl/    # ander festival   -> public/festivals/<id>.json
python build.py <url> --force           # caches negeren
python build.py <url> --method=llm      # forceer LLM-extractie (sla structured over)
```

Output: `frontend/public/acts.json` (Lowlands) en
`frontend/public/festivals/<id>.json` + `festivals/index.json` (overige festivals).

> **Netwerk:** de pipeline moet draaien waar `nts.live` en de festival-site
> bereikbaar zijn (je laptop, of een Claude Code-sessie met een open
> network-policy). Is NTS onbereikbaar, dan degradeert de pipeline netjes:
> presence-score 0, scoring puur op vibe. Zie
> https://code.claude.com/docs/en/claude-code-on-the-web voor network-policies.

## Frontend dev

```bash
cd frontend
npm install
npm run dev        # of: npm run build
```

De web-app kiest het festival via `?f=<id>` (default = eerste in
`festivals/index.json`, t.w. Lowlands) en past automatisch het bijbehorende
thema toe (`src/index.css`, `[data-theme="..."]`).

## Een nieuw festival toevoegen

1. `python build.py <line-up-url>` — schrijft `festivals/<id>.json` + index-entry.
2. (Optioneel) een eigen thema: voeg een `[data-theme="<id>"]`-blok toe in
   `frontend/src/index.css` en map het in `THEME_BY_ID` in `src/App.tsx`.
3. (Optioneel) handmatige correcties: `pipeline/overrides.json`, keyed op slug.

## Scoring rubric (strict NTS)

| Signaal | Presence |
|---|---|
| Eigen NTS-show (resident, ≥50 episodes) | 100 |
| Eigen NTS-show (≥1 episode) | 85–92 |
| Regelmatig te gast (genoemd in shows) | 40–65 |
| Infinite Mixtape-credit | 70–75 |
| Niets gevonden | 0 |

De vibe-score (0–100) komt los daarvan uit Claude's oordeel over aesthetic fit.
