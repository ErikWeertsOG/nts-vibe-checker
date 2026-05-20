---
name: lowlands-nts-playlist
description: Maak een Spotify-playlist van Lowlands-acts op basis van de NTS-vibe scores uit de NTS Vibe Checker. Gebruik dit wanneer de gebruiker vraagt om een Lowlands/NTS playlist in Spotify, een "vibe playlist", of acts wil omzetten naar een afspeellijst op basis van de scores in acts.json.
---

# Lowlands NTS-vibe playlist → Spotify

Bouwt een Spotify-playlist met **het best scorende nummer per act**, gekozen
uit `frontend/public/acts.json` op basis van de NTS-vibe scores die de
pipeline al heeft berekend.

## Wanneer gebruiken

- "Maak een Lowlands NTS-playlist in Spotify"
- "Zet de top-acts op een afspeellijst"
- "Playlist van alleen de NTS-residents" / "alles met vibe ≥ 70"

## Twee paden — kies de juiste

| Pad | Tool | Resultaat | Wanneer |
|---|---|---|---|
| **A. Web API** (default) | `make_playlist.py` + `SPOTIFY_ACCESS_TOKEN` | **Exacte** playlist: één best-scorend nummer per act, alle acts gedekt | Token beschikbaar — dit is de echte route |
| B. Generatief (fallback) | Spotify MCP `create_playlist` | Beschrijving → Spotify kiest zelf. **Slaat lijsten plat** tot een paar artiesten; mist acts | Geen token en de gebruiker accepteert een benadering |

**Default = pad A.** Stel pad B alleen voor als de gebruiker geen token kan
geven én genoegen neemt met een onnauwkeurige selectie.

## Wat je nodig hebt

1. `frontend/public/acts.json` (output van `pipeline/build.py`). Ontbreekt
   het of is het leeg? Stop en vraag de gebruiker eerst `cd pipeline &&
   python build.py` te draaien — verzin geen acts.
2. **Voor pad A:** `SPOTIFY_ACCESS_TOKEN` als env-var, scopes
   `playlist-modify-private user-read-private`. Verloopt na ~1 uur.

### Token verkrijgen (eenmalig)

Spotify heeft de oude developer-console afgeschaft, dus gebruik de
Authorization Code flow:

1. Ga naar https://developer.spotify.com/dashboard en maak een app aan.
   Vul `http://127.0.0.1:8888/callback` als Redirect URI in. Noteer
   `CLIENT_ID` en `CLIENT_SECRET`.
2. Open in een browser:
   `https://accounts.spotify.com/authorize?response_type=code&client_id=<CLIENT_ID>&scope=playlist-modify-private%20user-read-private&redirect_uri=http://127.0.0.1:8888/callback`
3. Akkoord geven; je wordt geredirect naar `127.0.0.1:8888/callback?code=…`.
   Kopieer de `code`-parameter uit de URL (de pagina zelf zal niet laden,
   dat hoeft ook niet).
4. Wissel code in voor een token:
   ```bash
   curl -X POST https://accounts.spotify.com/api/token \
     -d grant_type=authorization_code \
     -d code=<CODE> \
     -d redirect_uri=http://127.0.0.1:8888/callback \
     -u "<CLIENT_ID>:<CLIENT_SECRET>"
   ```
   In de response staat `access_token`. Exporteer 'm:
   ```bash
   export SPOTIFY_ACCESS_TOKEN=<access_token>
   ```

## Stappen

### 1. Bepaal de selectie-modus

Default: `vibe70`. Vraag indien onduidelijk welke selectie de gebruiker wil.

| Mode | Selectie |
|---|---|
| `vibe70` (default) | `vibe_score >= 70` — alle NTS-waardige acts (~64) |
| `vibe50` | `vibe_score >= 50` — ruimer (~87) |
| `top25` | de 25 hoogst scorende acts |
| `topN` (bv. `top40`) | de N hoogst scorende acts |
| `residents` | alleen `RESIDENT` + `NTS-PRESENCE` |
| `all` | elke act met een Spotify-link |

### 2. Pad A — Web API (default, exact)

Vanuit de repo-root, met `SPOTIFY_ACCESS_TOKEN` gezet:

```bash
python3 .claude/skills/lowlands-nts-playlist/make_playlist.py vibe70
```

Wat het script doet:
- leest `acts.json`, filtert op de modus, schoont artiestnamen
  (`(live)`-suffix, `... with X` → `X`, `Live Band`-suffix),
- zoekt per artiest via `GET /v1/search?q=artist:<naam>&type=track`,
  filtert op exacte artiest-match en kiest de track met de hoogste
  `popularity`,
- maakt een **privé** playlist (`--public` voor publiek),
- voegt tracks toe in batches van 100,
- print de echte Spotify-link uit `external_urls.spotify` en welke acts
  geen track opleverden.

Geef de gebruiker de link en het overzicht (gevonden vs. missend). Bij 401
zegt 't script dat het token verlopen is; vraag een nieuwe.

### 3. Pad B — Generatieve fallback (alleen als geen token)

Roep dan de Spotify MCP `create_playlist`-tool aan met een prompt die
begint met "Create a playlist called …", de gekozen artiesten noemt en
expliciet om brede dekking vraagt. Belangrijke regels voor dit pad:

- **Verwacht dat de tool de lijst platslaat.** Zeg er eerlijk bij dat het
  een benadering is en dat niet alle artiesten gegarandeerd voorkomen.
- **Kort de link NOOIT in.** Gebruik letterlijk de `deep_link_uri` /
  `desktop_uri` uit het tool-resultaat — een kale
  `open.spotify.com/playlist/<id>` zonder de `nl=`-query geeft 404.
- **Generatief = vluchtig.** De gebruiker moet de playlist in Spotify
  openen én opslaan, anders verdwijnt 'ie.
- `language`: ondersteund zijn `en, fr, it, de, es, pt`. Bij Nederlands
  → `language="en"`, prompt in Engels, **artiestnamen exact** behouden.

## Belangrijke regels

- **Scores zijn leidend.** Selecteer puur op `score`/`vibe_score`/
  `category` uit `acts.json`. Voeg geen artiesten toe op eigen smaak.
- **Pad A is default.** Stel pad B alleen voor als token onmogelijk is.
- **Eén best-scorende track per artiest** (sortering op Spotify
  `popularity`, met exacte artiest-match). Geen subjectieve keuzes.
- **acts.json ontbreekt?** Stop en vraag de gebruiker de pipeline te
  draaien — niet zelf data verzinnen.
- **Geen verzonnen of ingekorte URLs.** Alleen wat de API/tool teruggeeft.
