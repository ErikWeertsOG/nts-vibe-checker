"""Fetch & cache NTS data.

NTS API quirks:
  * /shows pagination caps at offset ~1000 (returns 422 above), alphabetical.
    So listing covers roughly A-N. To find later-letter shows we lean on
    direct slug lookup.
  * /shows/{slug} works for ANY show, no offset issue. This is our main probe.
"""
from __future__ import annotations
import json
import re
import time
from pathlib import Path
import httpx

DATA = Path(__file__).parent.parent / "data" / "cache"
SHOWS_CACHE = DATA / "nts_shows.json"
LOOKUP_CACHE = DATA / "nts_slug_lookup.json"
MIXTAPES_CACHE = DATA / "nts_mixtapes.json"
API = "https://www.nts.live/api/v2"
MAX_OFFSET = 1000  # hard cap; above this NTS returns 422


def fetch_show_index(force: bool = False) -> list[dict]:
    """Listing of NTS shows (alphabetically capped at ~1000, A-N range)."""
    if SHOWS_CACHE.exists() and not force:
        return json.loads(SHOWS_CACHE.read_text())

    DATA.mkdir(parents=True, exist_ok=True)
    all_shows, offset, limit = [], 0, 24
    try:
        with httpx.Client(timeout=30) as client:
            while offset <= MAX_OFFSET:
                r = client.get(f"{API}/shows", params={"limit": limit, "offset": offset})
                if r.status_code == 422:
                    break
                r.raise_for_status()
                results = r.json().get("results", [])
                if not results:
                    break
                all_shows.extend(results)
                print(f"  fetched {len(all_shows)}")
                offset += limit
                time.sleep(0.1)
    except (httpx.HTTPError, OSError) as e:
        print(f"  ! NTS show index unreachable ({e}); continuing without it")
        return all_shows

    SHOWS_CACHE.write_text(json.dumps(all_shows))
    return all_shows


def nts_available() -> bool:
    """Quick reachability probe so a network-down run skips NTS cleanly
    instead of poisoning the slug-lookup cache with false negatives."""
    try:
        r = httpx.get(f"{API}/shows", params={"limit": 1}, timeout=10)
        return r.status_code == 200
    except (httpx.HTTPError, OSError):
        return False


def slugify(name: str) -> str:
    s = name.lower().strip()
    s = re.sub(r"\(.*?\)", "", s)  # drop "(live)" etc
    s = re.sub(r"[^a-z0-9\s-]", "", s)
    s = re.sub(r"\s+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s


def candidate_slugs(name: str) -> list[str]:
    """Slug candidates ordered most-specific to least-specific.

    Conservative on splitting — only split when the name explicitly signals
    a multi-artist booking ('with', '&', 'b2b', 'vs', '+')."""
    base = slugify(name)
    cands: list[str] = [base]
    # strip trailing modifiers ((live), (dj set), etc)
    bare = re.sub(r"-(live|dj-set|b2b|presents|all-night-long|set)$", "", base)
    if bare != base:
        cands.append(bare)
    # explicit splits in ORIGINAL name (not slug, to avoid false splits)
    parts = re.split(r"\s+(?:with|w/|&|and|b2b|vs|\+)\s+", name, flags=re.I)
    if len(parts) >= 2:
        for p in parts:
            ps = slugify(p)
            if ps and len(ps) >= 4:
                cands.append(ps)
    return [c for c in dict.fromkeys(cands) if c and len(c) >= 4]


def fetch_mixtape_credits(force: bool = False) -> set[str]:
    """Return set of NTS resident/guest names credited in any infinite mixtape."""
    if MIXTAPES_CACHE.exists() and not force:
        return set(json.loads(MIXTAPES_CACHE.read_text()))
    DATA.mkdir(parents=True, exist_ok=True)
    try:
        r = httpx.get(f"{API}/mixtapes", timeout=30)
        r.raise_for_status()
    except (httpx.HTTPError, OSError) as e:
        print(f"  ! NTS mixtapes unreachable ({e}); continuing without it")
        return set()
    names = set()
    for m in r.json().get("results", []):
        for c in m.get("credits", []):
            n = c.get("name", "").strip()
            if n:
                names.add(n)
    MIXTAPES_CACHE.write_text(json.dumps(sorted(names)))
    return names


def lookup_slug(client: httpx.Client, slug: str) -> dict | None:
    try:
        r = client.get(f"{API}/shows/{slug}")
    except (httpx.HTTPError, OSError):
        return None
    if r.status_code == 200:
        return r.json()
    return None


def lookup_acts(act_names: list[str], force: bool = False) -> dict[str, dict | None]:
    """For each act name, try slug-direct lookup against NTS /shows/{slug}.
    Returns dict: act_name -> show data or None."""
    cache: dict[str, dict | None] = {}
    if LOOKUP_CACHE.exists() and not force:
        cache = json.loads(LOOKUP_CACHE.read_text())

    todo = [n for n in act_names if n not in cache]
    if not todo:
        return cache

    DATA.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=15) as client:
        for i, name in enumerate(todo):
            found = None
            for slug in candidate_slugs(name):
                show = lookup_slug(client, slug)
                if show:
                    found = show
                    break
                time.sleep(0.05)
            cache[name] = found
            if (i + 1) % 20 == 0:
                print(f"  looked up {i+1}/{len(todo)}")
                LOOKUP_CACHE.write_text(json.dumps(cache))

    LOOKUP_CACHE.write_text(json.dumps(cache))
    return cache


if __name__ == "__main__":
    print("Fetching show index...")
    shows = fetch_show_index(force=True)
    print(f"  {len(shows)} shows indexed (A-N range)")
    print("\nDirect slug test:")
    with httpx.Client(timeout=10) as c:
        for n in ["Hunee", "Theo Parrish", "Floating Points", "Made-Up Artist"]:
            for s in candidate_slugs(n):
                res = lookup_slug(c, s)
                if res:
                    print(f"  {n}: HIT on slug '{s}' -> '{res['name'].strip()}'")
                    break
            else:
                print(f"  {n}: no NTS show")
