"""Orchestrator: scrape → match → score-presence → judge-vibe → timetable → write acts.json."""
from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path

from lineup import fetch_lineup, enrich_with_genres
from nts import fetch_show_index, lookup_acts, fetch_mixtape_credits
from score import score_all, combine
from vibe import judge_all
from timetable import (
    fetch_pdf, parse_pdf, match_slots_with_fixup, enrich_acts,
    diff_slots, SLOTS_CACHE, PREV_SLOTS_CACHE,
)

OUT = Path(__file__).parent.parent / "frontend" / "public" / "acts.json"
TIMETABLE_URL = "https://lowlands.nl/media/documents/LL26_Blokkenschema.pdf"


def main():
    print("[1/6] Lowlands lineup (with bios)...")
    acts = fetch_lineup()
    acts = enrich_with_genres(acts)
    print(f"  {len(acts)} acts, {sum(1 for a in acts if a['bio']) } with bio")

    print("[2/6] NTS data...")
    shows = fetch_show_index()
    credits = fetch_mixtape_credits()
    print(f"  {len(shows)} shows / {len(credits)} mixtape credits")

    print("[3/6] NTS presence per act...")
    names = [a["name"] for a in acts]
    lookup = lookup_acts(names)
    hits = sum(1 for v in lookup.values() if v)
    print(f"  {hits}/{len(names)} have own NTS show")

    print("[4/6] Score presence...")
    scored = score_all(acts, lookup, shows, credits)

    print("[5/6] Judge vibe (Claude)...")
    judgments = judge_all(scored)
    final = combine(scored, judgments)

    print("[6/6] Timetable...")
    raw_slots: list = []
    try:
        pdf, changed = fetch_pdf(TIMETABLE_URL)
        print(f"  pdf: {'CHANGED — reparsing' if changed else 'unchanged (using cache)'}")
        slots = parse_pdf(pdf)
        raw_slots = [s.to_dict() for s in slots]

        # Show what moved since the last run (helps spot upstream schedule edits)
        if PREV_SLOTS_CACHE.exists():
            try:
                prev = json.loads(PREV_SLOTS_CACHE.read_text())
                d = diff_slots(prev, raw_slots)
                if d["added"] or d["removed"] or d["moved"]:
                    print(f"  diff: +{len(d['added'])} added, -{len(d['removed'])} removed, "
                          f"~{len(d['moved'])} moved")
                    for s in d["added"][:5]:
                        print(f"    + {s['day']} {s['stage']} {s['start_time']}  {s['name']}")
                    for s in d["removed"][:5]:
                        print(f"    - {s['day']} {s['stage']} {s['start_time']}  {s['name']}")
                    for m in d["moved"][:5]:
                        print(f"    ~ {m['from']['name']}: "
                              f"{m['from']['stage']} {m['from']['start_time']} → "
                              f"{m['to']['stage']} {m['to']['start_time']}")
            except Exception as e:
                print(f"  diff: skipped ({e})")

        match_map = match_slots_with_fixup(slots, final)
        final = enrich_acts(final, match_map)
        matched_acts = sum(1 for a in final if a.get("sets"))
        print(f"  {len(slots)} slots · matched to {matched_acts} acts")
    except Exception as e:
        print(f"  ! timetable step failed: {e}")

    payload = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "acts": final,
        "timetable": raw_slots,
        "stats": {
            "total": len(final),
            "with_own_show": hits,
            "with_presence": sum(1 for a in final if a["presence_score"] > 0),
            "with_vibe_50_plus": sum(1 for a in final if a["vibe_score"] >= 50),
            "with_vibe_70_plus": sum(1 for a in final if a["vibe_score"] >= 70),
            "with_timetable": sum(1 for a in final if a.get("sets")),
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
        sets = a.get("sets") or []
        when = ""
        if sets:
            s = sets[0]
            when = f"  ⏱  {s['day'][-5:]} {s['stage']:8} {s['start_time']}"
        print(f"  {a['score']:3d}  p:{ps:3d} v:{vs:3d}  [{cat:13}]  {a['name']}{when}")


if __name__ == "__main__":
    main()
