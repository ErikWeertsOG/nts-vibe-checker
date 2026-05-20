#!/usr/bin/env python3
"""Maak een Lowlands-NTS Spotify-playlist via de Spotify Web API.

Anders dan de generatieve `create_playlist`-MCP-tool voegt dit script
**exact** de gekozen tracks toe — één per geselecteerde act, gekozen op
Spotify `popularity` met een exacte artiestnaam-match.

Vereisten:
    pip install niets — alleen stdlib (urllib).
    export SPOTIFY_ACCESS_TOKEN=<jouw token>
    Scopes: playlist-modify-private user-read-private
    Tokens verlopen na ~1 uur; haal een nieuwe als je 401 krijgt.

Gebruik:
    python3 make_playlist.py [MODE] [--public]
    MODE-defaults en uitleg: zie select_acts.py
    --public  maak een publieke playlist (default: private)

Voorbeeld:
    SPOTIFY_ACCESS_TOKEN=... python3 make_playlist.py vibe70
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from select_acts import ACTS_JSON, clean_name, select  # noqa: E402

API = "https://api.spotify.com/v1"


def http(method: str, url: str, token: str, body=None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, method=method, data=data)
    req.add_header("Authorization", f"Bearer {token}")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as r:
            raw = r.read().decode()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        msg = e.read().decode()[:400]
        if e.code == 401:
            raise SystemExit("Spotify 401: token verlopen of ongeldig. Refresh je SPOTIFY_ACCESS_TOKEN.")
        if e.code == 403:
            raise SystemExit(f"Spotify 403: token mist scope (playlist-modify-private)? Detail: {msg}")
        raise SystemExit(f"Spotify {e.code}: {msg}")


def search_top_track(token: str, artist: str) -> dict | None:
    q = urllib.parse.urlencode({"q": f"artist:{artist}", "type": "track", "limit": 20})
    res = http("GET", f"{API}/search?{q}", token)
    items = res.get("tracks", {}).get("items", []) or []
    norm = artist.lower().strip()
    exact = [t for t in items if any(a["name"].lower().strip() == norm for a in t.get("artists", []))]
    pool = exact or items
    if not pool:
        return None
    return max(pool, key=lambda t: t.get("popularity", 0))


def main() -> None:
    args = sys.argv[1:]
    public = "--public" in args
    args = [a for a in args if not a.startswith("--")]
    mode = args[0] if args else "vibe70"

    token = os.environ.get("SPOTIFY_ACCESS_TOKEN")
    if not token:
        raise SystemExit(
            "SPOTIFY_ACCESS_TOKEN niet gezet. Scopes: playlist-modify-private user-read-private.\n"
            "Zie SKILL.md voor hoe je 'm haalt."
        )
    if not ACTS_JSON.exists():
        raise SystemExit(f"acts.json niet gevonden ({ACTS_JSON}) — draai eerst pipeline/build.py.")

    data = json.loads(ACTS_JSON.read_text())
    chosen = select(data["acts"], mode)
    if not chosen:
        raise SystemExit(f"Geen acts voor mode={mode!r}.")

    # de-dupe op opgeschoonde naam, hoogste score wint
    seen, artists = set(), []
    for a in chosen:
        n = clean_name(a["name"])
        if n.lower() in seen:
            continue
        seen.add(n.lower())
        artists.append((n, a.get("score", 0)))

    print(f"# {len(artists)} unieke artiesten geselecteerd (mode={mode})", file=sys.stderr)

    uris: list[str] = []
    found: list[tuple[str, str, int]] = []
    missing: list[str] = []
    for name, score in artists:
        try:
            t = search_top_track(token, name)
        except SystemExit:
            raise
        except Exception as e:
            print(f"  ! {score:3d} | {name:30s} -> error: {e}", file=sys.stderr)
            missing.append(name)
            continue
        if t:
            uris.append(t["uri"])
            found.append((name, t["name"], t.get("popularity", 0)))
            print(f"  + {score:3d} | {name:30s} -> {t['name']} (pop {t.get('popularity', 0)})", file=sys.stderr)
        else:
            missing.append(name)
            print(f"  ! {score:3d} | {name:30s} -> geen track gevonden", file=sys.stderr)
        time.sleep(0.05)

    me = http("GET", f"{API}/me", token)
    title = f"NTS Vibe Checker — Lowlands ({mode})"
    desc = (
        f"Beste nummer per act volgens Spotify popularity. "
        f"Selectie: {mode}, {len(uris)} tracks. Bron: NTS Vibe Checker."
    )
    pl = http(
        "POST",
        f"{API}/users/{me['id']}/playlists",
        token,
        {"name": title, "description": desc, "public": public},
    )
    pid = pl["id"]
    for i in range(0, len(uris), 100):
        http("POST", f"{API}/playlists/{pid}/tracks", token, {"uris": uris[i : i + 100]})

    url = pl["external_urls"]["spotify"]
    print()
    print(f"Playlist: {url}")
    print(f"Tracks toegevoegd: {len(uris)}  |  niet gevonden: {len(missing)}")
    if missing:
        print("Missend:", ", ".join(missing))


if __name__ == "__main__":
    main()
