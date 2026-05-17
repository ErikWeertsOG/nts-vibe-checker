"""Score Lowlands acts on NTS vibe."""
from __future__ import annotations
import re
import time
import httpx

API = "https://www.nts.live/api/v2"


def normalize(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def count_episodes(client: httpx.Client, show_alias: str) -> int:
    """Cheap episode count for a show."""
    r = client.get(f"{API}/shows/{show_alias}/episodes", params={"limit": 1})
    if r.status_code != 200:
        return 0
    try:
        return r.json().get("metadata", {}).get("resultset", {}).get("count", 0)
    except Exception:
        return 0


def description_mentions(act_name: str, shows: list[dict]) -> list[dict]:
    """Find shows whose description mentions this act (likely guest spots).

    Uses word-boundary regex and skips very short or generic names to
    cut down on false positives (e.g. 'sor' matching 'tresor')."""
    needle = act_name.lower().strip()
    # too-short or generic single-word names → too noisy
    if len(needle) < 5 or needle in {"speed", "iconic", "new wave", "celeste", "nala", "keo", "sor"}:
        # only accept exact show-name matches for these
        pat = re.compile(rf"^{re.escape(needle)}$", re.I)
        return [s for s in shows
                if pat.match((s.get("name") or "").strip().lower())
                and normalize(s.get("name", "")) != normalize(act_name)]
    pat = re.compile(rf"\b{re.escape(needle)}\b", re.I)
    hits = []
    for s in shows:
        haystack = ((s.get("description") or "") + " " + (s.get("name") or "")).lower()
        if pat.search(haystack):
            if normalize(s.get("name", "")) == normalize(act_name):
                continue
            hits.append(s)
    return hits


def score_act(
    act: dict,
    own_show: dict | None,
    mentions: list[dict],
    episode_count: int,
    in_mixtape: bool = False,
) -> dict:
    """Compute presence score (hard NTS data only) + reasoning."""
    reasons = []
    nts_links = []
    score = 0

    if own_show:
        slug = own_show.get("show_alias")
        url = f"https://www.nts.live/shows/{slug}"
        nts_links.append({"label": f"Eigen NTS-show: {own_show['name'].strip()}", "url": url})
        if episode_count >= 50:
            score = 100
            reasons.append(f"Vaste NTS-resident ({episode_count} episodes)")
        elif episode_count >= 10:
            score = 92
            reasons.append(f"Eigen NTS-show ({episode_count} episodes)")
        elif episode_count >= 1:
            score = 85
            reasons.append(f"Eigen NTS-show ({episode_count} episodes)")
        else:
            score = 80
            reasons.append("Eigen NTS-show in catalogus")

    if mentions and not own_show:
        # mentioned in N other show descriptions = invited as guest
        n = len(mentions)
        if n >= 3:
            score = max(score, 65)
            reasons.append(f"Genoemd in {n} NTS-shows (regelmatig te gast)")
        elif n == 2:
            score = max(score, 55)
            reasons.append("Genoemd in 2 NTS-shows")
        elif n == 1:
            score = max(score, 40)
            reasons.append("Genoemd in 1 NTS-show")
        for m in mentions[:3]:
            slug = m.get("show_alias")
            nts_links.append({"label": f"Vermeld op: {m['name'].strip()}", "url": f"https://www.nts.live/shows/{slug}"})

    if mentions and own_show:
        reasons.append(f"Plus {len(mentions)} guest-spots op andere shows")

    if in_mixtape:
        if score == 0:
            score = 70
            reasons.append("Gecredit op een NTS Infinite Mixtape (geen eigen show)")
        elif not own_show:
            score = max(score, 75)
            reasons.append("Ook gecredit op een NTS Infinite Mixtape")
        else:
            reasons.append("Ook in NTS Infinite Mixtape credits")

    if score == 0:
        reasons.append("Geen NTS-aanwezigheid gevonden")

    return {
        **act,
        "presence_score": score,
        "reasons": reasons,
        "nts_links": nts_links,
        "own_show": own_show.get("show_alias") if own_show else None,
        "nts_genres": [g.get("value") for g in (own_show or {}).get("genres", [])],
        "nts_moods": [m.get("value") for m in (own_show or {}).get("moods", [])],
        "nts_description": (own_show or {}).get("description"),
        "episode_count": episode_count,
    }


def in_mixtape_credits(name: str, credits: set[str]) -> bool:
    """Case-insensitive match against mixtape credits, also tries 'with X' variants."""
    n = normalize(name)
    if not n:
        return False
    for c in credits:
        if normalize(c) == n:
            return True
        # check 'X & Y' or 'X and Y' credit forms vs single-name act
        for part in re.split(r"\s+(?:&|and|w/|with)\s+", c, flags=re.I):
            if normalize(part) == n:
                return True
    return False


def score_all(
    acts: list[dict],
    lookup: dict,
    show_index: list[dict],
    mixtape_credits: set[str],
) -> list[dict]:
    results = []
    with httpx.Client(timeout=15) as client:
        for i, act in enumerate(acts):
            own = lookup.get(act["name"])
            ep_count = count_episodes(client, own["show_alias"]) if own else 0
            mentions = description_mentions(act["name"], show_index)
            mix = in_mixtape_credits(act["name"], mixtape_credits)
            results.append(score_act(act, own, mentions, ep_count, mix))
            if (i + 1) % 20 == 0:
                print(f"  scored {i+1}/{len(acts)}")
            if own:
                time.sleep(0.1)
    return results


def combine(presence_scored: list[dict], vibe_judgments: dict[str, dict]) -> list[dict]:
    """Merge presence + vibe into final score and category."""
    for a in presence_scored:
        v = vibe_judgments.get(a["slug"], {})
        a["vibe_score"] = int(v.get("vibe", 0) or 0)
        a["vibe_reason"] = v.get("reason", "")
        a["blurb"] = v.get("blurb", "")
        p = a["presence_score"]
        a["score"] = max(p, a["vibe_score"])
        # category for badge
        if p >= 80:
            a["category"] = "RESIDENT"
        elif p >= 50:
            a["category"] = "NTS-PRESENCE"
        elif a["vibe_score"] >= 70:
            a["category"] = "NTS-VIBE"
        elif a["vibe_score"] >= 40:
            a["category"] = "ADJACENT"
        else:
            a["category"] = "OFF"
    presence_scored.sort(key=lambda x: (-x["score"], -x["presence_score"]))
    return presence_scored
