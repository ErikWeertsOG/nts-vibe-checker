#!/usr/bin/env python3
"""Selecteer Lowlands-acts uit acts.json op basis van de NTS-vibe scores.

Output is een opgeschoonde, komma-gescheiden artiestenlijst die rechtstreeks
in de Spotify create_playlist-prompt geplakt kan worden.

Gebruik:
    python3 select_acts.py [MODE]

MODE (default: top25):
    top25         de 25 hoogst scorende acts
    topN          de N hoogst scorende acts, bv. top40
    residents     alleen RESIDENT + NTS-PRESENCE
    vibe70        vibe_score >= 70
    vibe50        vibe_score >= 50
    all           elke act met een Spotify-link

De acts.json wordt gezocht t.o.v. de repo-root, ongeacht waar het script draait.
"""
import json
import re
import sys
from pathlib import Path

ACTS_JSON = Path(__file__).resolve().parents[3] / "frontend" / "public" / "acts.json"


def clean_name(name: str) -> str:
    """Zet een Lowlands-acttitel om naar een zoekbare artiestnaam voor Spotify."""
    # "This Must Be the Pace with Theo Parrish" -> "Theo Parrish"
    if " with " in name:
        name = name.split(" with ", 1)[1]
    # strip trailing parenthetical: "Floating Points (live)" -> "Floating Points"
    name = re.sub(r"\s*\([^)]*\)\s*$", "", name)
    # "Nu Genea Live Band" -> "Nu Genea"
    name = re.sub(r"\s+Live Band$", "", name)
    return name.strip()


def select(acts, mode: str):
    by_score = sorted(
        acts,
        key=lambda a: (a.get("score", 0), a.get("vibe_score", 0)),
        reverse=True,
    )
    if mode == "top25":
        chosen = by_score[:25]
    elif mode.startswith("top") and mode[3:].isdigit():
        chosen = by_score[: int(mode[3:])]
    elif mode == "residents":
        chosen = [a for a in by_score if a.get("category") in ("RESIDENT", "NTS-PRESENCE")]
    elif mode == "vibe70":
        chosen = [a for a in by_score if a.get("vibe_score", 0) >= 70]
    elif mode == "vibe50":
        chosen = [a for a in by_score if a.get("vibe_score", 0) >= 50]
    elif mode == "all":
        chosen = [a for a in by_score if a.get("spotify")]
    else:
        raise SystemExit(f"Onbekende mode: {mode!r}. Zie de docstring voor opties.")
    # NB: niet filteren op opgeslagen spotify-link — de create_playlist-tool
    # zoekt op artiestnaam, dus acts zonder link (bv. Ben UFO) horen er ook bij.
    return chosen


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "top25"
    if not ACTS_JSON.exists():
        raise SystemExit(f"acts.json niet gevonden op {ACTS_JSON} — draai eerst de pipeline.")
    data = json.loads(ACTS_JSON.read_text())
    acts = data["acts"]
    chosen = select(acts, mode)

    # de-dupe op opgeschoonde naam, eerste (hoogste score) wint
    seen, names = set(), []
    for a in chosen:
        n = clean_name(a["name"])
        key = n.lower()
        if key not in seen:
            seen.add(key)
            names.append((n, a.get("score", 0), a.get("category", "")))

    print(f"# mode={mode}  geselecteerd={len(names)}  (bron: acts.json gegenereerd {data.get('generated_at')})")
    for n, s, c in names:
        print(f"{s:3d} | {c:12s} | {n}")
    print()
    print("ARTISTS_CSV=" + ", ".join(n for n, _, _ in names))


if __name__ == "__main__":
    main()
