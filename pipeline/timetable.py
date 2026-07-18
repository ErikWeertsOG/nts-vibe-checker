"""Parse the Lowlands blokkenschema PDF and inject set-times into acts.

The PDF has three pages (one per festival day) with a fixed grid: stages as rows
and time-columns from 09:30 → 05:00. Each stage row lists act names above their
start-time. Some acts wrap onto multiple text-lines, and comedy/theatre stages
render names as widely-spaced letters — we reconstruct at the char level and
key off the time-tokens as block boundaries.
"""
from __future__ import annotations
import difflib
import json
import re
import unicodedata
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path

import httpx
import pdfplumber

CACHE_DIR = Path(__file__).parent.parent / "data" / "cache"
PDF_CACHE = CACHE_DIR / "blokkenschema.pdf"
SLOTS_CACHE = CACHE_DIR / "timetable_slots.json"

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


def fetch_pdf(url: str, force: bool = False) -> Path:
    """Download the blokkenschema PDF (cached)."""
    if PDF_CACHE.exists() and not force:
        return PDF_CACHE
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    r = httpx.get(url, timeout=60, follow_redirects=True)
    r.raise_for_status()
    PDF_CACHE.write_bytes(r.content)
    return PDF_CACHE


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
    """Parse the blokkenschema into flat Slot records."""
    out: list[Slot] = []
    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages):
            day = DAYS[i] if i < len(DAYS) else f"page-{i+1}"
            out.extend(_parse_page(page, day))
    SLOTS_CACHE.parent.mkdir(parents=True, exist_ok=True)
    SLOTS_CACHE.write_text(json.dumps([s.to_dict() for s in out], ensure_ascii=False, indent=2))
    return out


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

    if unmatched:
        print(f"  timetable: {len(unmatched)} unmatched slots (non-music or naming differences):")
        for s in unmatched[:20]:
            print(f"    {s.day} {s.stage} {s.start_time}  {s.name}")
        if len(unmatched) > 20:
            print(f"    ... and {len(unmatched) - 20} more")
    return dict(result)


def enrich_acts(acts: list[dict], match_map: dict[str, list[dict]]) -> list[dict]:
    """Attach `sets` list to each act (empty if no timetable match)."""
    for a in acts:
        a["sets"] = match_map.get(a["slug"], [])
    return acts


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
