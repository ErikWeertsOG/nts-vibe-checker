"""Orchestrator: scrape → match → score → blurb → write acts.json."""
from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path

from lineup import fetch_lineup
from nts import fetch_show_index, lookup_acts, fetch_mixtape_credits
from score import score_all
from blurbs import generate_all

OUT = Path(__file__).parent.parent / "frontend" / "public" / "acts.json"


def main():
    print("[1/5] Lowlands lineup...")
    acts = fetch_lineup()
    print(f"  {len(acts)} acts")

    print("[2/5] NTS show index...")
    shows = fetch_show_index()
    print(f"  {len(shows)} shows")

    print("[3/5] NTS slug lookup per act + mixtape credits...")
    names = [a["name"] for a in acts]
    lookup = lookup_acts(names)
    hits = sum(1 for v in lookup.values() if v)
    print(f"  {hits}/{len(names)} have own NTS show")
    credits = fetch_mixtape_credits()
    print(f"  {len(credits)} mixtape credits cached")

    print("[4/5] Scoring...")
    scored = score_all(acts, lookup, shows, credits)
    nonzero = [a for a in scored if a["score"] > 0]
    print(f"  {len(nonzero)}/{len(scored)} acts with NTS-vibe > 0")

    print("[5/5] Blurbs (Claude)...")
    blurbs = generate_all(scored)
    for a in scored:
        a["blurb"] = blurbs.get(a["name"], "")

    payload = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "acts": scored,
        "stats": {
            "total": len(scored),
            "with_own_show": hits,
            "with_any_signal": len(nonzero),
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"\nWrote {OUT}")
    print("\nTop 10:")
    for a in scored[:10]:
        print(f"  {a['score']:3d}  {a['name']}")


if __name__ == "__main__":
    main()
