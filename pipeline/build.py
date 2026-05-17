"""Orchestrator: scrape → match → score-presence → judge-vibe → write acts.json."""
from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path

from lineup import fetch_lineup, enrich_with_genres
from nts import fetch_show_index, lookup_acts, fetch_mixtape_credits
from score import score_all, combine
from vibe import judge_all

OUT = Path(__file__).parent.parent / "frontend" / "public" / "acts.json"


def main():
    print("[1/5] Lowlands lineup (with bios)...")
    acts = fetch_lineup()
    acts = enrich_with_genres(acts)
    print(f"  {len(acts)} acts, {sum(1 for a in acts if a['bio']) } with bio")

    print("[2/5] NTS data...")
    shows = fetch_show_index()
    credits = fetch_mixtape_credits()
    print(f"  {len(shows)} shows / {len(credits)} mixtape credits")

    print("[3/5] NTS presence per act...")
    names = [a["name"] for a in acts]
    lookup = lookup_acts(names)
    hits = sum(1 for v in lookup.values() if v)
    print(f"  {hits}/{len(names)} have own NTS show")

    print("[4/5] Score presence...")
    scored = score_all(acts, lookup, shows, credits)

    print("[5/5] Judge vibe (Claude)...")
    judgments = judge_all(scored)

    final = combine(scored, judgments)

    payload = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "acts": final,
        "stats": {
            "total": len(final),
            "with_own_show": hits,
            "with_presence": sum(1 for a in final if a["presence_score"] > 0),
            "with_vibe_50_plus": sum(1 for a in final if a["vibe_score"] >= 50),
            "with_vibe_70_plus": sum(1 for a in final if a["vibe_score"] >= 70),
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"\nWrote {OUT}")
    print("\nTop 20:")
    for a in final[:20]:
        cat = a["category"]
        ps = a["presence_score"]
        vs = a["vibe_score"]
        print(f"  {a['score']:3d}  p:{ps:3d} v:{vs:3d}  [{cat:13}]  {a['name']}")


if __name__ == "__main__":
    main()
