"""Light-weight timetable refresh: no lineup fetch, no vibe judging.

Reads the current acts.json, re-fetches the blokkenschema PDF (with
If-Modified-Since / hash comparison), re-parses if changed, applies matching +
LLM fixup, writes acts.json back. Prints a diff summary.

Intended to be run daily by CI so the deployed timetable stays fresh without
paying the full pipeline's Claude-vibe-judgment cost.
"""
from __future__ import annotations
import json
import sys
from datetime import datetime
from pathlib import Path

from timetable import (
    fetch_pdf, parse_pdf, match_slots_with_fixup, enrich_acts, diff_slots,
    PREV_SLOTS_CACHE,
)

ACTS_JSON = Path(__file__).parent.parent / "frontend" / "public" / "acts.json"
TIMETABLE_URL = "https://lowlands.nl/media/documents/LL26_Blokkenschema.pdf"


def main() -> int:
    if not ACTS_JSON.exists():
        print(f"! {ACTS_JSON} not found — run full pipeline first.", file=sys.stderr)
        return 2

    payload = json.loads(ACTS_JSON.read_text())
    acts = payload["acts"]

    print(f"[refresh-timetable] fetching {TIMETABLE_URL}")
    pdf, changed = fetch_pdf(TIMETABLE_URL)
    if not changed and payload.get("timetable"):
        # PDF unchanged AND we already have timetable data → nothing to do.
        print("[refresh-timetable] pdf unchanged, existing timetable kept — no write")
        return 0

    slots = parse_pdf(pdf)
    raw_slots = [s.to_dict() for s in slots]

    # Sanity check: if the new parse dropped >20% of slots or lost an entire
    # festival day, refuse to overwrite. The published PDF may have changed
    # shape (parser regression) or the upstream file may be temporarily bad.
    prev_slots = payload.get("timetable") or []
    if prev_slots:
        prev_n = len(prev_slots)
        prev_days = {s["day"] for s in prev_slots}
        new_days = {s["day"] for s in raw_slots}
        missing_days = prev_days - new_days
        if missing_days:
            print(f"! REFUSING TO WRITE: new parse lost days {sorted(missing_days)}",
                  file=sys.stderr)
            return 3
        if len(raw_slots) < prev_n * 0.8:
            print(f"! REFUSING TO WRITE: new parse has {len(raw_slots)} slots "
                  f"vs previous {prev_n} (>20% drop). Inspect the PDF.",
                  file=sys.stderr)
            return 3

    if PREV_SLOTS_CACHE.exists():
        try:
            prev = json.loads(PREV_SLOTS_CACHE.read_text())
            d = diff_slots(prev, raw_slots)
            print(f"[refresh-timetable] diff: +{len(d['added'])} / -{len(d['removed'])} / "
                  f"~{len(d['moved'])}")
            for s in d["added"][:10]:
                print(f"  + {s['day']} {s['stage']} {s['start_time']}  {s['name']}")
            for s in d["removed"][:10]:
                print(f"  - {s['day']} {s['stage']} {s['start_time']}  {s['name']}")
            for m in d["moved"][:10]:
                print(f"  ~ {m['from']['name']}: "
                      f"{m['from']['stage']} {m['from']['start_time']} → "
                      f"{m['to']['stage']} {m['to']['start_time']}")
        except Exception as e:
            print(f"[refresh-timetable] diff skipped ({e})")

    match_map = match_slots_with_fixup(slots, acts)
    acts = enrich_acts(acts, match_map)

    payload["acts"] = acts
    payload["timetable"] = raw_slots
    payload["timetable_updated_at"] = datetime.utcnow().isoformat() + "Z"
    payload.setdefault("stats", {})["with_timetable"] = sum(1 for a in acts if a.get("sets"))

    ACTS_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"[refresh-timetable] wrote {ACTS_JSON}")
    print(f"  {len(slots)} slots · {payload['stats']['with_timetable']} acts with sets")
    return 0


if __name__ == "__main__":
    sys.exit(main())
