"""Orchestrator: extract line-up -> match NTS -> presence-score -> vibe -> JSON.

Usage:
    python build.py                      # Lowlands (default) -> public/acts.json
    python build.py <festival-url>       # any festival   -> public/festivals/<id>.json
    python build.py <url> --force        # ignore caches
    python build.py <url> --method=llm   # force LLM extraction (skip structured)

Lowlands keeps its dedicated rich adapter and its canonical output path, so the
no-argument run behaves exactly as before. Every other URL goes through the
generic extractor and is written as a separate festival file plus an index
entry, leaving Lowlands untouched.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

from extract import extract_acts
from nts import fetch_show_index, lookup_acts, fetch_mixtape_credits, nts_available
from score import score_all, combine
from vibe import judge_all

PUBLIC = Path(__file__).parent.parent / "frontend" / "public"
LOWLANDS_URL = "https://lowlands.nl/acts/"


def _output_path(fid: str) -> Path:
    if fid == "lowlands":
        return PUBLIC / "acts.json"
    return PUBLIC / "festivals" / f"{fid}.json"


def _update_index(meta: dict, payload: dict) -> None:
    idx_path = PUBLIC / "festivals" / "index.json"
    idx_path.parent.mkdir(parents=True, exist_ok=True)
    index = {"festivals": []}
    if idx_path.exists():
        try:
            index = json.loads(idx_path.read_text())
        except json.JSONDecodeError:
            pass
    fid = meta["id"]
    file_url = "/acts.json" if fid == "lowlands" else f"/festivals/{fid}.json"
    entry = {
        "id": fid,
        "name": meta["name"],
        "file": file_url,
        "total": payload["stats"]["total"],
        "generated_at": payload["generated_at"],
    }
    rest = [f for f in index.get("festivals", []) if f.get("id") != fid]
    index["festivals"] = rest + [entry]
    index["festivals"].sort(key=lambda f: (f["id"] != "lowlands", f["name"].lower()))
    idx_path.write_text(json.dumps(index, ensure_ascii=False, indent=2))


def build(url: str, force: bool = False, method: str = "auto") -> dict:
    print(f"[1/5] Extract line-up: {url}")
    meta, acts = extract_acts(url, force=force, method=method)
    print(f"  {meta['name']}: {len(acts)} acts ({sum(1 for a in acts if a.get('bio'))} with bio)")

    print("[2/5] NTS data...")
    if nts_available():
        shows = fetch_show_index(force=force)
        credits = fetch_mixtape_credits(force=force)
        names = [a["name"] for a in acts]
        lookup = lookup_acts(names, force=force)
        hits = sum(1 for v in lookup.values() if v)
    else:
        print("  ! NTS unreachable — presence scoring skipped (vibe only)")
        shows, credits, lookup, hits = [], set(), {}, 0
    print(f"  {len(shows)} shows / {len(credits)} mixtape credits / {hits} own shows")

    print("[3/5] Presence score...")
    scored = score_all(acts, lookup, shows, credits)

    print("[4/5] Vibe judgment (Claude)...")
    judgments = judge_all(scored, force=force)

    print("[5/5] Combine + write...")
    final = combine(scored, judgments)

    payload = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "festival": {"id": meta["id"], "name": meta["name"], "url": meta["url"]},
        "acts": final,
        "stats": {
            "total": len(final),
            "with_own_show": hits,
            "with_presence": sum(1 for a in final if a["presence_score"] > 0),
            "with_vibe_50_plus": sum(1 for a in final if a["vibe_score"] >= 50),
            "with_vibe_70_plus": sum(1 for a in final if a["vibe_score"] >= 70),
        },
    }

    out = _output_path(meta["id"])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    _update_index(meta, payload)

    print(f"\nWrote {out}")
    print("\nTop 20:")
    for a in final[:20]:
        print(f"  {a['score']:3d}  p:{a['presence_score']:3d} v:{a['vibe_score']:3d}  "
              f"[{a['category']:13}]  {a['name']}")
    return payload


def main():
    args = [a for a in sys.argv[1:]]
    force = "--force" in args
    method = "auto"
    for a in args:
        if a.startswith("--method="):
            method = a.split("=", 1)[1]
    positional = [a for a in args if not a.startswith("--")]
    url = positional[0] if positional else LOWLANDS_URL
    build(url, force=force, method=method)


if __name__ == "__main__":
    main()
