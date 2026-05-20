---
name: lowlands-nts-playlist
description: Maak een Spotify-playlist van Lowlands-acts op basis van de NTS-vibe scores uit de NTS Vibe Checker. Roep deze skill aan wanneer iemand vraagt om een Lowlands- of NTS-playlist in Spotify, een "vibe playlist", of acts wil omzetten naar een afspeellijst op basis van de NTS-vibe scores. De skill is portable — `acts.json` zit naast deze SKILL.md.
---

# Lowlands NTS-vibe playlist → Spotify (portable)

Bouwt een Spotify-playlist met de Lowlands-acts die het hoogst scoren op de
NTS-vibe checker. De scores zitten ingebakken in `acts.json` naast deze
SKILL.md, dus deze skill werkt **zelfstandig** — in Claude.ai chat, Cowork
of Claude Code.

## Wanneer aanroepen

- "Maak een Lowlands NTS-playlist in Spotify"
- "Zet de top-NTS-acts op een Spotify-afspeellijst"
- "Vibe-playlist op basis van de NTS Vibe Checker"
- "Playlist van alleen de residents" / "alles met vibe ≥ 70"

## Bestanden in deze skill

- `acts.json` — de data (126 Lowlands-acts met NTS-vibe scores).
- `select_acts.py` — filtert & schoont artiestnamen op (`(live)`,
  `… with X`, `Live Band`-suffix).
- `make_playlist.py` — maakt een **exacte** playlist via de Spotify Web API
  (vereist een access-token).
- `SKILL.md` — dit document.

## Selectiemodi

Default = `vibe70`. Bevestig kort welke modus de gebruiker wil; default als
ze het niet zeggen.

| Mode | Selectie |
|---|---|
| `vibe70` (default) | `vibe_score >= 70` — alle NTS-waardige acts (~64) |
| `vibe50` | `vibe_score >= 50` — ruimer (~87) |
| `top25` | de 25 hoogst scorende acts |
| `topN` (bv. `top40`) | de N hoogst scorende acts |
| `residents` | alleen `RESIDENT` + `NTS-PRESENCE` |
| `all` | elke act met een Spotify-link |

## Twee paden — kies de juiste

| Pad | Hoe | Resultaat | Wanneer |
|---|---|---|---|
| **A. Exact (Spotify Web API)** | code execution + `make_playlist.py` + access-token | Eén best-scorend nummer per act, alle acts gedekt, exact | Gebruiker kan een Spotify-token aanleveren |
| **B. Generatief (Spotify connector)** | de `create_playlist`-tool van de Spotify connector | Spotify kiest zelf tracks uit een prompt. **Slaat lange lijsten plat** — niet elke artiest komt voor | Geen token; gebruiker accepteert benadering |

**Default = A** als de host code kan draaien (Claude.ai chat met Code
Interpreter, Cowork, Claude Code). Pad B is alleen acceptabel als A
echt niet kan.

---

## Pad A — Exacte playlist via Spotify Web API

### A1. Vraag om een access-token

De gebruiker heeft eenmalig een Spotify access-token nodig met scopes
`playlist-modify-private user-read-private`. Tokens verlopen na ~1 uur.

Geef ze deze instructie als ze nog geen token hebben:

> 1. Maak een Spotify-app op https://developer.spotify.com/dashboard.
>    Voeg `http://127.0.0.1:8888/callback` toe als Redirect URI. Noteer
>    `CLIENT_ID` en `CLIENT_SECRET`.
> 2. Open in een browser:
>    `https://accounts.spotify.com/authorize?response_type=code&client_id=<CLIENT_ID>&scope=playlist-modify-private%20user-read-private&redirect_uri=http://127.0.0.1:8888/callback`
> 3. Akkoord geven; je wordt geredirect naar `…/callback?code=…`. Kopieer
>    de `code`-parameter (de pagina hoeft niet te laden).
> 4. Wissel de code om voor een token:
>    ```bash
>    curl -X POST https://accounts.spotify.com/api/token \
>      -d grant_type=authorization_code \
>      -d code=<CODE> \
>      -d redirect_uri=http://127.0.0.1:8888/callback \
>      -u "<CLIENT_ID>:<CLIENT_SECRET>"
>    ```
>    Pak `access_token` uit de response. Plak die hier.

### A2. Draai het script

In code execution (de gebruiker plakt het token; behandel het als geheim
en echo het niet terug):

```bash
SPOTIFY_ACCESS_TOKEN=<token> python3 make_playlist.py <mode>
# bv: SPOTIFY_ACCESS_TOKEN=BQ... python3 make_playlist.py vibe70
# voeg --public toe voor een publieke playlist
```

Wat het doet:
- leest `acts.json`, filtert op de modus, schoont namen op,
- zoekt per artiest via `GET /v1/search?q=artist:<naam>&type=track`,
  filtert op exacte artiest-match en kiest de track met de hoogste
  `popularity`,
- maakt een **privé** playlist (`--public` → publiek),
- voegt tracks toe in batches van 100,
- print de Spotify-link uit `external_urls.spotify` en een lijst gemiste
  acts.

Geef de gebruiker:
- de echte playlist-link uit de scriptoutput,
- aantallen (gevonden / gemist), en
- de namen van eventuele gemiste acts.

Bij 401: het token is verlopen of mist een scope — vraag een nieuwe.

---

## Pad B — Generatieve fallback (alleen als A niet kan)

1. Draai `python3 select_acts.py <mode>` (of voer de logica in code uit) en
   neem alleen de namen uit de `ARTISTS_CSV=…`-regel — niet zelf uitbreiden.
2. Roep de Spotify `create_playlist`-tool aan met dit sjabloon:

```
Create a playlist called "NTS Vibe Checker — Lowlands (<mode>)" featuring
these Lowlands acts: <ARTISTS_CSV>. EVERY artist must appear with one or
two of their best, most popular tracks — aim for full coverage across all
artists. NTS Radio aesthetic: leftfield electronic, deep house, techno,
club, jazz, breakbeat, experimental.
```

Regels voor dit pad:

- **Verwacht dat de tool de lijst platslaat.** Vertel de gebruiker
  expliciet dat het een benadering is — niet elke act zit er
  gegarandeerd in.
- **Kort de link NOOIT in.** Plak letterlijk de `deep_link_uri` of
  `desktop_uri` uit het tool-resultaat. Een kale
  `open.spotify.com/playlist/<id>` zonder de `nl=`-query geeft 404.
- **Generatief = vluchtig.** Zeg dat de gebruiker de playlist in Spotify
  moet openen en opslaan/in bibliotheek toevoegen, anders verdwijnt 'ie.
- `language`: ondersteund zijn `en, fr, it, de, es, pt`. Bij Nederlands
  → zet `language="en"`, schrijf de prompt in het Engels, maar laat
  **artiestnamen exact** staan.

---

## Belangrijke regels

- **Scores zijn leidend.** Selecteer puur op `score`/`vibe_score`/
  `category` uit `acts.json`. Voeg geen artiesten toe op eigen smaak.
- **Pad A is default als code uitvoeren kan.** Pad B alleen als A
  onmogelijk is.
- **Eén best-scorende track per artiest** in pad A (Spotify `popularity`,
  exacte artiest-match). Geen subjectieve keuzes.
- **Tokens zijn geheim.** Niet teruggeven in chat, niet loggen, niet
  committen.
- **Geen verzonnen of ingekorte URLs.** Alleen wat de API of tool
  teruggeeft.
