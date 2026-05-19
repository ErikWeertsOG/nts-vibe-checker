---
name: lowlands-nts-playlist
description: Maak een Spotify-playlist van Lowlands-acts op basis van de NTS-vibe scores uit de NTS Vibe Checker. Gebruik dit wanneer de gebruiker vraagt om een Lowlands/NTS playlist in Spotify, een "vibe playlist", of acts wil omzetten naar een afspeellijst op basis van de scores in acts.json.
---

# Lowlands NTS-vibe playlist → Spotify

Bouwt een Spotify-playlist uit de hoogst scorende Lowlands-acts volgens de
NTS-vibe scores die de pipeline al heeft berekend en in
`frontend/public/acts.json` heeft gezet.

## Wanneer gebruiken

- "Maak een Lowlands NTS-playlist in Spotify"
- "Zet de top-acts op een afspeellijst"
- "Playlist van alleen de NTS-residents" / "alles met vibe ≥ 70"

## Wat je nodig hebt

1. `frontend/public/acts.json` moet bestaan (output van `pipeline/build.py`).
   Bestaat het niet? Zeg dat de gebruiker eerst de pipeline moet draaien
   (`cd pipeline && python build.py`) — verzin geen acts.
2. Een Spotify `create_playlist` MCP-tool die een playlist maakt uit een
   natuurlijke-taal beschrijving. **Belangrijke beperking:** deze tool
   accepteert geen exacte tracklijst — hij genereert zelf tracks per
   artiest. De playlist is dus een *benadering* van de selectie: de juiste
   artiesten, maar Spotify kiest de nummers.

## Stappen

### 1. Bepaal de selectie-modus

Vraag de gebruiker welke selectie, of gebruik de default `top25`. Modes:

| Mode | Selectie |
|---|---|
| `top25` (default) | 25 hoogst scorende acts |
| `topN` (bv. `top40`) | N hoogst scorende acts |
| `residents` | alleen `RESIDENT` + `NTS-PRESENCE` |
| `vibe70` | `vibe_score >= 70` |
| `vibe50` | `vibe_score >= 50` |
| `all` | elke act met een Spotify-link |

### 2. Haal de opgeschoonde artiestenlijst op

Draai het meegeleverde script vanuit de repo-root:

```bash
python3 .claude/skills/lowlands-nts-playlist/select_acts.py <mode>
```

Het script:
- leest `acts.json`, sorteert op `score` (tiebreak `vibe_score`),
- past de gekozen mode toe,
- schoont titels op tot zoekbare artiestnamen:
  - `"Floating Points (live)"` → `Floating Points` (parenthese eraf),
  - `"This Must Be the Pace with Theo Parrish"` → `Theo Parrish` (deel na "with"),
  - `"Nu Genea Live Band"` → `Nu Genea` ("Live Band"-suffix eraf),
- de-dupet op naam (hoogste score wint),
- print onderaan een regel `ARTISTS_CSV=<komma-gescheiden namen>`.

Neem **alleen** de namen uit `ARTISTS_CSV` — niet zelf acts toevoegen of
herschrijven. De scores zijn de enige bron van waarheid.

### 3. Roep de Spotify create_playlist-tool aan

- `language`: kies op basis van de taal van de gebruiker. Ondersteund:
  `en, fr, it, de, es, pt`. Schrijft de gebruiker Nederlands (of een andere
  niet-ondersteunde taal)? Zet `language="en"` en schrijf de prompt in het
  Engels, maar **laat de artiestnamen exact staan** zoals in `ARTISTS_CSV`.
- `prompt`: begin met "Create a playlist called ...", geef een titel met
  jaar en modus, plak de `ARTISTS_CSV` namen, en beschrijf de NTS-esthetiek.

Prompt-sjabloon (vul `{TITEL}` en `{ARTISTS_CSV}` in):

```
Create a playlist called "{TITEL}" featuring these Lowlands acts: {ARTISTS_CSV}.
The vibe is the NTS Radio aesthetic: leftfield electronic, deep house, techno,
club, jazz-leaning, breakbeat and experimental — curated and adventurous.
```

Titel-conventie: `NTS Vibe Checker — Lowlands <jaar> (<modus-omschrijving>)`,
bv. `NTS Vibe Checker — Lowlands 2026 (Top 25)`. Leid het jaar af uit de
context van `acts.json` (`generated_at`) of de Lowlands-editie; gok niet als
het onduidelijk is — vraag het dan.

### 4. Rapporteer terug

Geef de gebruiker de **volledige, onbewerkte** `deep_link_uri` (of
`desktop_uri`) uit het tool-resultaat, plus het aantal geselecteerde acts en
de gebruikte modus.

> **Kort de link NOOIT in.** De `create_playlist`-tool maakt een generatieve
> AI-playlist (`"is_lazy_loaded": true`, `"playlist_subtitle_metadata":
> {"type": "GENERATIVE"}`). De link bevat een verplichte `nl=`-parameter die
> de playlist materialiseert. Een kale `open.spotify.com/playlist/<id>`
> zonder die query geeft een **404**. Plak de link exact zoals de tool 'm
> teruggeeft; construeer nooit zelf een Spotify-URL.

> **Zeg er expliciet bij:** dit is een tijdelijke generatieve playlist. De
> gebruiker moet 'm in Spotify openen (dán worden de tracks geladen) én
> **opslaan / aan de bibliotheek toevoegen**, anders verdwijnt 'ie weer en
> is hij later niet meer terug te vinden via de search-tool.

## Belangrijke regels

- **Scores zijn leidend.** Selecteer puur op `score`/`vibe_score`/`category`
  uit `acts.json`. Voeg geen artiesten toe op eigen smaak.
- **Geen exacte tracklijst mogelijk** met de `create_playlist`-tool; wees
  hierover eerlijk tegen de gebruiker (benadering, geen 1-op-1 kopie).
- **Geen verzonnen of ingekorte URLs.** Alleen de volledige link uit het
  tool-resultaat tonen — inkorten breekt de generatieve playlist (404).
- **Generatief = vluchtig.** Altijd benoemen dat de gebruiker de playlist
  moet openen en opslaan, anders is hij weg.
- **acts.json ontbreekt of is leeg?** Stop en zeg dat de pipeline eerst moet
  draaien — niet zelf data verzinnen.
