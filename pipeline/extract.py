"""Generic festival line-up extractor.

Goal: given ANY festival / line-up URL, produce a list of acts in the same
shape the rest of the pipeline expects, while being token-frugal:

  Step A — structured data (free, no LLM): JSON-LD (MusicEvent/performer),
           __NEXT_DATA__ blobs, __NUXT__ blobs. If this yields a healthy
           number of names we stop here.
  Step B — LLM extraction (cheap model) on a DE-DUPLICATED candidate list of
           short text snippets pulled from the HTML. We NEVER send raw HTML to
           the model — only a cleaned, deduped list of candidate strings.

Lowlands keeps its dedicated rich adapter (lineup.py) so it behaves exactly as
before (bio + genres + socials from the Wagtail API). Any URL containing
"lowlands.nl" routes there; everything else goes through the generic path.

Act dict shape (matches downstream expectations):
    { slug, name, url, bio, genres, lowlands_genres, subtitle,
      soundcloud, spotify }
"""
from __future__ import annotations

import html as _html
import json
import os
import re
import time
from pathlib import Path
from urllib.parse import urlparse, urljoin

import httpx

CACHE = Path(__file__).parent.parent / "data" / "cache"

# Cheap model for name extraction. Vibe judgment uses the bigger model.
EXTRACT_MODEL = os.environ.get("NTS_EXTRACT_MODEL", "claude-haiku-4-5")

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "nl-NL,nl;q=0.9,en;q=0.8",
}

# Obvious non-artist UI strings to drop from Step B candidates.
STOPWORDS = {
    "tickets", "ticket", "menu", "home", "nieuws", "news", "contact", "info",
    "line-up", "lineup", "line up", "programma", "program", "schedule",
    "more", "lees meer", "read more", "meer", "all", "alle", "filter",
    "search", "zoek", "cookie", "cookies", "accept", "accepteer", "weiger",
    "privacy", "faq", "shop", "merch", "festival", "over ons", "about",
    "nederlands", "english", "deutsch", "français", "volgende", "vorige",
    "next", "previous", "close", "sluiten", "deel", "share", "facebook",
    "instagram", "twitter", "tiktok", "youtube", "spotify", "soundcloud",
    "newsletter", "nieuwsbrief", "subscribe", "aanmelden", "login", "account",
    "back", "terug", "day", "dag", "stage", "podium", "main", "see all",
}


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def slugify(name: str) -> str:
    s = name.lower().strip()
    s = re.sub(r"\(.*?\)", "", s)
    s = re.sub(r"[^a-z0-9\s-]", "", s)
    s = re.sub(r"\s+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s


def clean_text(s: str) -> str:
    s = _html.unescape(s or "")
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def festival_id_from_url(url: str) -> str:
    host = (urlparse(url).hostname or url).lower()
    if host.startswith("www."):
        host = host[4:]
    label = host.split(".")[0]
    return slugify(label) or "festival"


def fetch_html(url: str, force: bool = False) -> str:
    fid = festival_id_from_url(url)
    cache_file = CACHE / f"html_{fid}.html"
    if cache_file.exists() and not force:
        return cache_file.read_text(encoding="utf-8")
    CACHE.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=30, follow_redirects=True, headers=BROWSER_HEADERS) as c:
        r = c.get(url)
        r.raise_for_status()
        html = r.text
    cache_file.write_text(html, encoding="utf-8")
    return html


# --------------------------------------------------------------------------- #
# Step A — structured data
# --------------------------------------------------------------------------- #
def _walk(node, fn):
    """Depth-first walk calling fn(key, value) for every dict entry."""
    if isinstance(node, dict):
        for k, v in node.items():
            fn(k, v)
            _walk(v, fn)
    elif isinstance(node, list):
        for v in node:
            _walk(v, fn)


def _names_from_performer(perf) -> list[str]:
    out = []
    if isinstance(perf, str):
        out.append(perf)
    elif isinstance(perf, dict):
        n = perf.get("name")
        if isinstance(n, str):
            out.append(n)
    elif isinstance(perf, list):
        for p in perf:
            out.extend(_names_from_performer(p))
    return out


def extract_from_jsonld(html: str) -> list[str]:
    names: list[str] = []
    blocks = re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html, re.S | re.I,
    )
    for raw in blocks:
        raw = raw.strip()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        roots = data if isinstance(data, list) else [data]
        for root in roots:
            if isinstance(root, dict) and "@graph" in root:
                roots = roots + (root["@graph"] if isinstance(root["@graph"], list) else [])

        def collect(_k, v):
            if isinstance(v, dict):
                t = v.get("@type", "")
                types = t if isinstance(t, list) else [t]
                if any(str(x).lower() in {"musicgroup", "person", "performinggroup"} for x in types):
                    n = v.get("name")
                    if isinstance(n, str):
                        names.append(n)
            if _k in ("performer", "performers", "byArtist"):
                names.extend(_names_from_performer(v))

        for root in roots:
            _walk(root, collect)
    return names


def _extract_json_script(html: str, script_id: str) -> dict | None:
    m = re.search(
        rf'<script[^>]+id=["\']{re.escape(script_id)}["\'][^>]*>(.*?)</script>',
        html, re.S | re.I,
    )
    if not m:
        return None
    try:
        return json.loads(m.group(1).strip())
    except json.JSONDecodeError:
        return None


def _names_from_blob(data) -> list[str]:
    """Heuristic: collect names from arrays that sit under an artist/act/lineup
    key and whose items are dicts with a name/title field."""
    names: list[str] = []
    KEY = re.compile(r"artist|act|line[\s_-]?up|performer|program|playing", re.I)

    def visit(key, val):
        if isinstance(val, list) and key and KEY.search(str(key)):
            for item in val:
                if isinstance(item, dict):
                    for nk in ("name", "title", "artist", "artistName", "displayName"):
                        n = item.get(nk)
                        if isinstance(n, str) and n.strip():
                            names.append(n.strip())
                            break
                elif isinstance(item, str) and item.strip():
                    names.append(item.strip())

    _walk(data, visit)
    return names


def extract_from_next(html: str) -> list[str]:
    data = _extract_json_script(html, "__NEXT_DATA__")
    return _names_from_blob(data) if data else []


def extract_from_nuxt(html: str) -> list[str]:
    # __NUXT__ is a JS expression; try to grab a JSON-looking object after `=`.
    m = re.search(r"window\.__NUXT__\s*=\s*(\{.*?\})\s*;?\s*</script>", html, re.S)
    if not m:
        return []
    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError:
        return []
    return _names_from_blob(data)


# --------------------------------------------------------------------------- #
# Step B — candidate list + cheap LLM
# --------------------------------------------------------------------------- #
def build_candidate_list(html: str, limit: int = 800) -> list[str]:
    """Pull short text snippets that could be artist names from the HTML and
    return a de-duplicated, cleaned list of strings (never raw HTML)."""
    # strip script/style entirely
    body = re.sub(r"<(script|style|noscript)\b[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)

    chunks: list[str] = []
    # anchor + heading + list-item + common card/title element inner text
    for m in re.finditer(
        r"<(?:a|h1|h2|h3|h4|li|span|div|p)\b[^>]*>(.*?)</(?:a|h1|h2|h3|h4|li|span|div|p)>",
        body, re.S | re.I,
    ):
        txt = clean_text(m.group(1))
        if txt:
            chunks.append(txt)

    seen: dict[str, str] = {}
    for c in chunks:
        if not (2 <= len(c) <= 60):
            continue
        words = c.split()
        if len(words) > 6:
            continue
        if not re.search(r"[A-Za-zÀ-ÿ]", c):
            continue
        low = c.lower()
        if low in STOPWORDS:
            continue
        if re.search(r"https?://|www\.|@|©|\bcookie", low):
            continue
        if low not in seen:
            seen[low] = c
        if len(seen) >= limit:
            break
    return list(seen.values())


def _anthropic_client():
    from anthropic import Anthropic
    try:
        from blurbs import _load_dotenv
        _load_dotenv()
    except Exception:
        pass
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY not set — needed for Step B extraction")
    return Anthropic(api_key=key)


EXTRACT_SYSTEM = """Je krijgt een lijst losse tekstfragmenten die van een festival-line-up-pagina zijn geschraapt. De lijst bevat artiest-/act-namen door elkaar met navigatie, knoppen, datums en andere ruis.

Geef ALLEEN de echte muziekartiest-/act-/dj-namen terug. Regels:
- Behoud de originele schrijfwijze.
- Geen navigatie, knoppen, podiumnamen, dagen, datums, tijden, genres, plaatsnamen of marketingteksten.
- Geen duplicaten.
- Als iets duidelijk geen artiestnaam is, laat het weg.
- Twijfel je sterk, laat het weg (liever missen dan ruis).

Antwoord met één strikt JSON-object, niets daarbuiten:
{ "artists": ["Naam 1", "Naam 2", ...] }"""


def llm_extract(candidates: list[str]) -> list[str]:
    if not candidates:
        return []
    client = _anthropic_client()
    payload = "\n".join(f"- {c}" for c in candidates)
    msg = client.messages.create(
        model=EXTRACT_MODEL,
        max_tokens=4000,
        system=[{"type": "text", "text": EXTRACT_SYSTEM, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": f"Fragmenten:\n{payload}\n\nGeef de artiestnamen."}],
    )
    raw = msg.content[0].text.strip()
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        return []
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return []
    out = data.get("artists", [])
    return [a.strip() for a in out if isinstance(a, str) and a.strip()]


# --------------------------------------------------------------------------- #
# orchestration
# --------------------------------------------------------------------------- #
MIN_STRUCTURED = 8  # below this we fall back to Step B


def _dedupe_names(names: list[str]) -> list[str]:
    seen: dict[str, str] = {}
    for n in names:
        n = clean_text(n)
        if not n:
            continue
        key = slugify(n)
        if len(key) < 2:
            continue
        if key not in seen:
            seen[key] = n
    return list(seen.values())


def extract_festival_meta(url: str, html: str = "") -> dict:
    name = ""
    if html:
        m = re.search(r'<meta[^>]+property=["\']og:site_name["\'][^>]+content=["\']([^"\']+)', html, re.I)
        if m:
            name = clean_text(m.group(1))
        if not name:
            m = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
            if m:
                name = clean_text(m.group(1)).split("|")[0].split("–")[0].strip()
    fid = festival_id_from_url(url)
    if not name:
        name = fid.replace("-", " ").title()
    return {"id": fid, "name": name, "url": url}


def extract_acts(url: str, force: bool = False, method: str = "auto") -> tuple[dict, list[dict]]:
    """Return (festival_meta, acts). `method`: auto|structured|llm."""
    # Lowlands keeps its rich dedicated adapter — behaves exactly as before.
    if "lowlands.nl" in (urlparse(url).hostname or ""):
        from lineup import fetch_lineup, enrich_with_genres
        acts = enrich_with_genres(fetch_lineup(force=force), force=force)
        for a in acts:
            a.setdefault("genres", a.get("lowlands_genres", []))
        meta = {"id": "lowlands", "name": "Lowlands", "url": url}
        return meta, acts

    html = fetch_html(url, force=force)
    meta = extract_festival_meta(url, html)
    fid = meta["id"]

    cache_file = CACHE / f"extract_{fid}.json"
    if cache_file.exists() and not force:
        cached = json.loads(cache_file.read_text())
        return cached["festival"], cached["acts"]

    names: list[str] = []
    source = "none"
    if method in ("auto", "structured"):
        for fn in (extract_from_jsonld, extract_from_next, extract_from_nuxt):
            got = _dedupe_names(fn(html))
            if len(got) > len(names):
                names = got
                source = fn.__name__
    if method == "llm" or (method == "auto" and len(names) < MIN_STRUCTURED):
        cands = build_candidate_list(html)
        llm_names = _dedupe_names(llm_extract(cands))
        if len(llm_names) > len(names):
            names = llm_names
            source = "llm_extract"

    acts = []
    for n in names:
        acts.append({
            "slug": slugify(n),
            "name": n,
            "url": url,
            "bio": "",
            "genres": [],
            "lowlands_genres": [],
            "subtitle": "",
            "soundcloud": "",
            "spotify": "",
        })

    CACHE.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(
        {"festival": meta, "acts": acts, "_source": source},
        ensure_ascii=False, indent=2,
    ))
    print(f"  extracted {len(acts)} acts via {source}")
    return meta, acts


if __name__ == "__main__":
    import sys
    target = sys.argv[1] if len(sys.argv) > 1 else "https://hiddengarden.nl/"
    meta, acts = extract_acts(target, force="--force" in sys.argv)
    print(f"\n{meta['name']} ({meta['id']}) — {len(acts)} acts")
    for a in acts[:40]:
        print("  ", a["name"])
