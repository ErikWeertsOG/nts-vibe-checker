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

For Lowlands specifically, a sixth step attaches the blokkenschema PDF: each
matched act gets a `sets` field, and the payload gains a top-level `timetable`
list plus a `timetable_updated_at` timestamp.
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
from timetable import (
    fetch_pdf, parse_pdf, match_slots_with_fixup, enrich_acts,
    diff_slots, PREV_SLOTS_CACHE,
)

PUBLIC = Path(__file__).parent.parent / "frontend" / "public"
LOWLANDS_URL = "https://lowlands.nl/acts/"
LOWLANDS_TIMETABLE_URL = "https://lowlands.nl/media/documents/LL26_Blokkenschema.pdf"


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


def _attach_lowlands_timetable(final: list[dict]) -> tuple[list[dict], list[dict], str | None]:
    """For Lowlands: parse the blokkenschema PDF, match slots to acts, return
    (final_with_sets, raw_slots, iso_timestamp). On any failure returns
    (final, [], None) so the pipeline still succeeds."""
    try:
        pdf, changed = fetch_pdf(LOWLANDS_TIMETABLE_URL)
        print(f"  pdf: {'CHANGED — reparsing' if changed else 'unchanged (using cache)'}")
        slots = parse_pdf(pdf)
        raw = [s.to_dict() for s in slots]

        if PREV_SLOTS_CACHE.exists():
            try:
                prev = json.loads(PREV_SLOTS_CACHE.read_text())
                d = diff_slots(prev, raw)
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
        return final, raw, datetime.utcnow().isoformat() + "Z"
    except Exception as e:
        print(f"  ! timetable step failed: {e}")
        return final, [], None


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

    # Lowlands-only: attach the blokkenschema PDF.
    raw_slots: list[dict] = []
    timetable_ts: str | None = None
    if meta["id"] == "lowlands":
        print("[6/6] Timetable (Lowlands)...")
        final, raw_slots, timetable_ts = _attach_lowlands_timetable(final)

    payload: dict = {
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
    if raw_slots:
        payload["timetable"] = raw_slots
        payload["timetable_updated_at"] = timetable_ts
        payload["stats"]["with_timetable"] = sum(1 for a in final if a.get("sets"))

    out = _output_path(meta["id"])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    _update_index(meta, payload)

    print(f"\nWrote {out}")
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
