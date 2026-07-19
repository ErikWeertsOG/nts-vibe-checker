"""Parse the Lowlands blokkenschema PDF and inject set-times into acts.

The PDF has three pages (one per festival day) with a fixed grid: stages as rows
and time-columns from 09:30 → 05:00. Each stage row lists act names above their
start-time. Some acts wrap onto multiple text-lines, and comedy/theatre stages
render names as widely-spaced letters — we reconstruct at the char level and
key off the time-tokens as block boundaries.
"""
from __future__ import annotations
import difflib
import hashlib
import json
import os
import re
import unicodedata
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path

import httpx
import pdfplumber

CACHE_DIR = Path(__file__).parent.parent / "data" / "cache"
PDF_CACHE = CACHE_DIR / "blokkenschema.pdf"
PDF_META_CACHE = CACHE_DIR / "blokkenschema.meta.json"
SLOTS_CACHE = CACHE_DIR / "timetable_slots.json"
PREV_SLOTS_CACHE = CACHE_DIR / "timetable_slots.prev.json"
LLM_FIXUP_CACHE = CACHE_DIR / "timetable_llm_fixup.json"

# Order matches the visual layout of the PDF (Fri / Sat / Sun 2026).
DAYS = ["2026-08-21", "2026-08-22", "2026-08-23"]

STAGE_NAMES = {"ALPHA", "BRAVO", "HEINEKEN", "LIMA", "INDIA", "X-RAY",
               "HACIENDA", "JULIET", "ECHO", "ADONIS"}
NON_MUSIC_STAGES = {"ADONIS", "ECHO"}  # spoken word / literature
CATEGORY_WORDS = {"COMEDY", "THEATER", "DANS", "LITERATUUR"}
TIME_RE = re.compile(r"^\d{2}:\d{2}$")


@dataclass
class Slot:
    day: str
    stage: str
    name: str
    start_time: str  # "HH:MM"

    def to_dict(self) -> dict:
        return asdict(self)


def fetch_pdf(url: str, force: bool = False) -> tuple[Path, bool]:
    """Download the blokkenschema PDF. Returns (path, changed).

    Uses If-Modified-Since / If-None-Match when we have prior metadata, and
    falls back to a content-hash comparison — so we know whether to redo the
    downstream work or reuse cached slot data.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    prev_meta = {}
    if PDF_META_CACHE.exists():
        try:
            prev_meta = json.loads(PDF_META_CACHE.read_text())
        except Exception:
            prev_meta = {}
    headers = {}
    if not force and PDF_CACHE.exists():
        if "etag" in prev_meta:
            headers["If-None-Match"] = prev_meta["etag"]
        if "last_modified" in prev_meta:
            headers["If-Modified-Since"] = prev_meta["last_modified"]

    with httpx.Client(timeout=60, follow_redirects=True) as client:
        r = client.get(url, headers=headers)

    if r.status_code == 304 and PDF_CACHE.exists():
        return PDF_CACHE, False

    r.raise_for_status()
    new_bytes = r.content
    new_hash = hashlib.sha256(new_bytes).hexdigest()
    changed = new_hash != prev_meta.get("sha256")

    PDF_CACHE.write_bytes(new_bytes)
    PDF_META_CACHE.write_text(json.dumps({
        "url": url,
        "sha256": new_hash,
        "etag": r.headers.get("etag", ""),
        "last_modified": r.headers.get("last-modified", ""),
        "fetched_at": r.headers.get("date", ""),
        "bytes": len(new_bytes),
    }, indent=2))
    return PDF_CACHE, changed


def _chars_to_string(chars: list[dict], gap_space: float = 0.5) -> str:
    """Rebuild a name from raw pdfplumber chars.

    Within a visual line, chars whose horizontal gap to the previous char is
    < gap_space are concatenated without a space (Lowlands' comedy stages
    render names as visually-spaced individual glyphs that we want to fuse
    back into words). Line breaks always insert a space.
    """
    if not chars:
        return ""
    by_y = defaultdict(list)
    for c in chars:
        by_y[round(c["top"] / 2) * 2].append(c)
    lines = []
    for y in sorted(by_y):
        line = sorted(by_y[y], key=lambda c: c["x0"])
        parts = [line[0]["text"]]
        for prev, cur in zip(line, line[1:]):
            gap = cur["x0"] - prev["x1"]
            parts.append(cur["text"] if gap < gap_space else " " + cur["text"])
        lines.append("".join(parts).strip())
    return " ".join(s for s in lines if s).strip()


def _parse_page(page, day: str) -> list[Slot]:
    words = page.extract_words(x_tolerance=1.5, y_tolerance=2)
    chars = page.chars

    stage_positions = sorted(
        (w["top"], w["text"]) for w in words
        if w["x0"] < 60 and w["text"] in STAGE_NAMES
    )
    if not stage_positions:
        return []

    bands = []
    for i, (y, name) in enumerate(stage_positions):
        y_end = stage_positions[i + 1][0] - 5 if i + 1 < len(stage_positions) else page.height
        bands.append((name, y - 5, y_end))

    slots: list[Slot] = []
    for stage, y0, y1 in bands:
        band_words = [w for w in words if y0 <= w["top"] < y1]
        time_toks = [w for w in band_words if TIME_RE.match(w["text"])]
        if not time_toks:
            continue
        # If multiple time-rows exist and one is > 8pt below the topmost, it's a
        # decorative ruler (e.g. ADONIS' half-hour grid). Keep only the topmost cluster.
        topmost_y = min(w["top"] for w in time_toks)
        time_toks = sorted(
            (w for w in time_toks if w["top"] - topmost_y <= 8),
            key=lambda w: w["x0"],
        )
        times_max_y = max(w["top"] for w in time_toks)

        # Candidate name-chars: in this band, above the times row, not the stage-name column.
        name_chars = [c for c in chars
                      if y0 <= c["top"] < min(y1, times_max_y - 1)
                      and c["x0"] > 55]

        def in_word_top_row(c, boxes):
            # pdfplumber's word bottom includes descenders — use top ± tight range instead.
            return any(x0 <= c["x0"] < x1 and top - 1 <= c["top"] <= top + 2
                       for x0, x1, top in boxes)

        time_boxes = [(t["x0"], t["x1"], t["top"]) for t in time_toks]
        name_chars = [c for c in name_chars if not in_word_top_row(c, time_boxes)]

        cat_boxes = [(w["x0"], w["x1"], w["top"]) for w in band_words
                     if w["text"].upper() in CATEGORY_WORDS]
        name_chars = [c for c in name_chars if not in_word_top_row(c, cat_boxes)]

        # Bucket chars into blocks defined by consecutive time-tokens.
        block_bounds = []
        for i, t in enumerate(time_toks):
            start = t["x0"] - 5  # tolerate names printed a couple points left of the time
            end = time_toks[i + 1]["x0"] - 5 if i + 1 < len(time_toks) else page.width + 100
            block_bounds.append((start, end))

        buckets: list[list[dict]] = [[] for _ in time_toks]
        for c in name_chars:
            for i, (s, e) in enumerate(block_bounds):
                if s <= c["x0"] < e:
                    buckets[i].append(c)
                    break

        for t, bucket in zip(time_toks, buckets):
            name = _chars_to_string(bucket)
            if not name or name == stage:
                continue
            slots.append(Slot(day=day, stage=stage, name=name, start_time=t["text"]))
    return slots


def parse_pdf(path: Path) -> list[Slot]:
    """Parse the blokkenschema into flat Slot records. Also rotates the previous
    cache so `diff_slots(prev, current)` can show what changed between runs.
    """
    out: list[Slot] = []
    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages):
            day = DAYS[i] if i < len(DAYS) else f"page-{i+1}"
            out.extend(_parse_page(page, day))
    SLOTS_CACHE.parent.mkdir(parents=True, exist_ok=True)
    if SLOTS_CACHE.exists():
        PREV_SLOTS_CACHE.write_text(SLOTS_CACHE.read_text())
    SLOTS_CACHE.write_text(json.dumps([s.to_dict() for s in out], ensure_ascii=False, indent=2))
    return out


def diff_slots(prev: list[dict], current: list[dict]) -> dict:
    """Return {added, removed, moved} between two slot lists.

    Keys on (day, stage, name); a move is same name+day but different stage or
    start_time. Anything else is either fully added or fully removed.
    """
    def key(s):  # matches on name-in-day, so a rescheduled act is a 'move'
        return (s["day"], s["stage"], s["start_time"], s["name"])
    def name_key(s):
        return (s["day"], s["name"])

    prev_set = {key(s) for s in prev}
    cur_set = {key(s) for s in current}
    added = [s for s in current if key(s) not in prev_set]
    removed = [s for s in prev if key(s) not in cur_set]

    # Detect moves: same (day, name) pair on both sides but different stage/time.
    prev_by_name = {name_key(s): s for s in prev}
    cur_by_name = {name_key(s): s for s in current}
    moved = []
    added_final, removed_final = [], []
    added_names = {name_key(s) for s in added}
    removed_names = {name_key(s) for s in removed}
    for s in added:
        if name_key(s) in removed_names:
            moved.append({"from": prev_by_name[name_key(s)], "to": s})
        else:
            added_final.append(s)
    for s in removed:
        if name_key(s) not in added_names:
            removed_final.append(s)
    return {"added": added_final, "removed": removed_final, "moved": moved}


# ---------- Matching Slot → Act -------------------------------------------------

def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if unicodedata.category(c) != "Mn")


def _norm(name: str) -> str:
    """Lower, no diacritics, letters+digits only."""
    return re.sub(r"[^a-z0-9]+", "", _strip_accents(name).lower())


def _slugify_name(name: str) -> str:
    """Same normalization the Lowlands API uses to make slugs from names."""
    s = _strip_accents(name).lower().strip()
    s = re.sub(r"\(.*?\)", "", s)                 # drop "(live)" etc.
    s = re.sub(r"[^a-z0-9\s-]", "", s)
    s = re.sub(r"\s+", "-", s).strip("-")
    s = re.sub(r"-+", "-", s)
    return s


def match_slots(slots: list[Slot], acts: list[dict]) -> dict[str, list[dict]]:
    """Return { act_slug: [set-info, ...] } for every slot that could be matched.

    Matching order: exact slug → normalized name → token-substring on slug
    (e.g. 'richie-hawtin-dex-efx-x0x' matches 'richie-hawtin').
    """
    by_slug = {a["slug"]: a for a in acts}
    by_norm_name = {_norm(a["name"]): a for a in acts}

    result: dict[str, list[dict]] = defaultdict(list)
    unmatched: list[Slot] = []

    for s in slots:
        set_info = {"day": s.day, "stage": s.stage, "start_time": s.start_time,
                    "raw_name": s.name}
        # 1. exact slug
        slug = _slugify_name(s.name)
        if slug in by_slug:
            result[slug].append(set_info)
            continue
        # 2. normalized name
        n = _norm(s.name)
        if n in by_norm_name:
            result[by_norm_name[n]["slug"]].append(set_info)
            continue
        # 3. token-substring: slot slug contains an act slug (as full hyphen-token run)
        matched = False
        for a_slug in by_slug:
            if len(a_slug) < 6:
                continue
            if slug == a_slug or slug.startswith(a_slug + "-") or slug.endswith("-" + a_slug) \
               or f"-{a_slug}-" in slug:
                result[a_slug].append(set_info)
                matched = True
                break
        if matched:
            continue
        # 4. bi-directional norm-substring (catches parser artifacts like
        #    'worldpeac dmt' → 'worldpeace dmt', 'nederlands orkest' → 'noord nederlands orkest')
        if len(n) >= 6:
            for norm_name, a in by_norm_name.items():
                if n in norm_name or norm_name in n:
                    result[a["slug"]].append(set_info)
                    matched = True
                    break
        if matched:
            continue
        # 5. difflib fuzzy match as last resort (ratio ≥ 0.85)
        if len(n) >= 5:
            best = difflib.get_close_matches(n, list(by_norm_name.keys()), n=1, cutoff=0.85)
            if best:
                result[by_norm_name[best[0]]["slug"]].append(set_info)
                continue
        unmatched.append(s)

    return dict(result)


def enrich_acts(acts: list[dict], match_map: dict[str, list[dict]]) -> list[dict]:
    """Attach `sets` list to each act (empty if no timetable match)."""
    for a in acts:
        a["sets"] = match_map.get(a["slug"], [])
    return acts


# ---------- LLM name-fixup for parser artifacts --------------------------------

LLM_FIXUP_MODEL = "claude-haiku-4-5-20251001"  # cheap model — this is filtering, not reasoning

_LLM_SYSTEM = """Je krijgt twee lijsten:
1. TIMETABLE_NAMES — namen zoals ze uit een PDF-schema zijn gehaald. Sommige zijn
   licht corrupt door OCR-achtige artefacten (missende letter, kapotte kerning,
   afgekapte woorden).
2. ACT_NAMES — de canonieke, correct gespelde artiestennamen.

Voor ELKE naam in TIMETABLE_NAMES die duidelijk hetzelfde artiest is als één in
ACT_NAMES (ondanks de corruptie), geef je een mapping. Alleen echte matches
opnemen. Bij twijfel: NIET mappen.

Regels:
- Geen algemene fuzzy-guessing. Een match moet fonetisch/typografisch
  overduidelijk zijn ("WORLDPEAC DMT" ↔ "Worldpeace DMT", "AND THE JEAN TEASERS"
  ↔ "Teen Jesus and the Jean Teasers").
- "YOGA", "SOUL LINEDANCE WORKSHOP" enzovoort zijn geen artiesten — mappen niet
  toevoegen als er geen kandidaat is.
- Behoud de originele TIMETABLE_NAME als sleutel exact zoals gegeven.

Output: één strikt JSON-object, niets daarbuiten:
{
  "matches": [
    {"pdf_name": "<TIMETABLE_NAME>", "act_name": "<ACT_NAME>"},
    ...
  ]
}
"""


def llm_fixup(unmatched_slots: list[Slot], unmatched_acts: list[dict],
              force: bool = False) -> dict[str, str]:
    """Return {pdf_name: act_slug} for parser-artifact matches. Cached on disk.

    Cache key = sha256(sorted names) so we only re-query when the input set
    genuinely changes.
    """
    if not unmatched_slots or not unmatched_acts:
        return {}

    pdf_names = sorted({s.name for s in unmatched_slots})
    act_names = sorted({a["name"] for a in unmatched_acts})
    cache_key = hashlib.sha256(
        (json.dumps(pdf_names) + "||" + json.dumps(act_names)).encode()
    ).hexdigest()[:16]

    cache: dict = {}
    if LLM_FIXUP_CACHE.exists() and not force:
        try:
            cache = json.loads(LLM_FIXUP_CACHE.read_text())
        except Exception:
            cache = {}
    if cache.get("key") == cache_key:
        return cache.get("mapping", {})

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("  llm_fixup: no ANTHROPIC_API_KEY — skipping")
        return {}

    try:
        from anthropic import Anthropic
    except ImportError:
        print("  llm_fixup: anthropic SDK not installed — skipping")
        return {}

    user = (
        "TIMETABLE_NAMES:\n" + "\n".join(f"- {n}" for n in pdf_names) +
        "\n\nACT_NAMES:\n" + "\n".join(f"- {n}" for n in act_names) +
        "\n\nGeef de mapping als JSON."
    )
    client = Anthropic(api_key=api_key)
    msg = client.messages.create(
        model=LLM_FIXUP_MODEL,
        max_tokens=1000,
        system=[{"type": "text", "text": _LLM_SYSTEM, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user}],
    )
    raw = msg.content[0].text.strip()
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        print("  llm_fixup: could not parse response")
        return {}
    try:
        parsed = json.loads(m.group(0))
    except json.JSONDecodeError:
        return {}

    slug_by_name = {a["name"]: a["slug"] for a in unmatched_acts}
    mapping: dict[str, str] = {}
    for pair in parsed.get("matches", []):
        pn, an = pair.get("pdf_name"), pair.get("act_name")
        if pn in pdf_names and an in slug_by_name:
            mapping[pn] = slug_by_name[an]

    LLM_FIXUP_CACHE.write_text(json.dumps({"key": cache_key, "mapping": mapping}, indent=2))
    print(f"  llm_fixup: {len(mapping)} additional matches from Claude")
    return mapping


def match_slots_with_fixup(slots: list[Slot], acts: list[dict],
                           force_llm: bool = False) -> dict[str, list[dict]]:
    """Rule-based matching, then LLM fixup for the stragglers."""
    result = match_slots(slots, acts)
    matched_keys = {(s["day"], s["stage"], s["start_time"], s["raw_name"])
                    for sets in result.values() for s in sets}
    unmatched = [s for s in slots
                 if (s.day, s.stage, s.start_time, s.name) not in matched_keys]
    matched_slugs = set(result.keys())
    unmatched_acts = [a for a in acts if a["slug"] not in matched_slugs]

    fixup = llm_fixup(unmatched, unmatched_acts, force=force_llm)
    for s in unmatched:
        if s.name in fixup:
            result.setdefault(fixup[s.name], []).append({
                "day": s.day, "stage": s.stage, "start_time": s.start_time,
                "raw_name": s.name,
            })
    return result


# ---------- CLI ------------------------------------------------------------------

def main():
    import sys
    url = sys.argv[1] if len(sys.argv) > 1 else \
        "https://lowlands.nl/media/documents/LL26_Blokkenschema.pdf"
    force = "--force" in sys.argv
    pdf = fetch_pdf(url, force=force)
    slots = parse_pdf(pdf)
    print(f"Parsed {len(slots)} slots from {pdf}")
    per = defaultdict(list)
    for s in slots:
        per[(s.day, s.stage)].append(s)
    for (d, stg), ss in sorted(per.items()):
        print(f"\n{d} · {stg}  ({len(ss)})")
        for s in ss:
            print(f"  {s.start_time}  {s.name}")


if __name__ == "__main__":
    main()
