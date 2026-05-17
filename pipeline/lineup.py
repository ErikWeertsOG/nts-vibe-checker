"""Fetch Lowlands 2026 lineup via Wagtail-style API with bios + genres."""
from __future__ import annotations
import json
import re
import time
from pathlib import Path
import httpx

CACHE = Path(__file__).parent.parent / "data" / "cache" / "lowlands_lineup.json"
API_LIST = "https://lowlands.nl/api/pages/"
API_DETAIL = "https://lowlands.nl/api/pages/{id}/"


def _strip_html(s: str) -> str:
    return re.sub(r"<[^>]+>", "", s or "").strip()


def fetch_lineup(force: bool = False) -> list[dict]:
    if CACHE.exists() and not force:
        return json.loads(CACHE.read_text())

    CACHE.parent.mkdir(parents=True, exist_ok=True)
    # batch list with text field included
    with httpx.Client(timeout=30) as c:
        r = c.get(API_LIST, params={"type": "acts.ActPage", "fields": "title,text", "limit": 200})
        r.raise_for_status()
        items = r.json().get("items", [])

        acts = []
        for item in items:
            slug = item["meta"]["htmlUrl"].rstrip("/").split("/")[-1]
            bio = _strip_html(item.get("text") or "")
            acts.append({
                "id": item["id"],
                "slug": slug,
                "name": item["title"],
                "bio": bio,
                "url": item["meta"]["htmlUrl"],
            })

        # enrich top 3 details for sanity-check (optional)
        print(f"  fetched {len(acts)} acts (avg bio length: {sum(len(a['bio']) for a in acts) // max(len(acts),1)} chars)")

    CACHE.write_text(json.dumps(acts, ensure_ascii=False))
    return acts


def enrich_with_genres(acts: list[dict], force: bool = False) -> list[dict]:
    """Add genres + social links per act (separate fetch per act, cached)."""
    detail_cache = CACHE.parent / "lowlands_details.json"
    cache: dict[str, dict] = {}
    if detail_cache.exists() and not force:
        cache = json.loads(detail_cache.read_text())

    todo = [a for a in acts if str(a["id"]) not in cache]
    if todo:
        with httpx.Client(timeout=15) as c:
            for i, a in enumerate(todo):
                try:
                    r = c.get(API_DETAIL.format(id=a["id"]))
                    if r.status_code == 200:
                        d = r.json()
                        cache[str(a["id"])] = {
                            "genres": [g.get("title") for g in d.get("actGenreItems", []) if g.get("title")],
                            "subtitle": d.get("subtitle") or "",
                            "soundcloud": d.get("soundcloudLink") or "",
                            "spotify": d.get("spotifyLink") or "",
                        }
                except Exception as e:
                    print(f"  ! {a['name']}: {e}")
                if (i + 1) % 20 == 0:
                    print(f"  enriched {i+1}/{len(todo)}")
                    detail_cache.write_text(json.dumps(cache, ensure_ascii=False))
                time.sleep(0.05)
        detail_cache.write_text(json.dumps(cache, ensure_ascii=False))

    for a in acts:
        d = cache.get(str(a["id"]), {})
        a["lowlands_genres"] = d.get("genres", [])
        a["subtitle"] = d.get("subtitle", "")
        a["soundcloud"] = d.get("soundcloud", "")
        a["spotify"] = d.get("spotify", "")
    return acts


if __name__ == "__main__":
    acts = fetch_lineup(force=True)
    enrich_with_genres(acts, force=True)
    print(f"\nSample:")
    for a in acts[:3]:
        print(f"  {a['name']}")
        print(f"    genres: {a['lowlands_genres']}")
        print(f"    bio: {a['bio'][:140]}...")
