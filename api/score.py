"""Live per-artist NTS scoring — Vercel serverless function.

POST /api/score   body: {"names": ["Floating Points", "Coldplay", ...]}
GET  /api/score?names=Floating%20Points,Coldplay

Returns: {"results": {"<name>": <act|null>, ...}}

Self-contained on purpose: mirrors the batch pipeline (pipeline/nts.py,
score.py, vibe.py) but inlined so it bundles cleanly as a serverless function.
Presence scoring uses only NTS HTTP data (free). The aesthetic "vibe" score
needs ANTHROPIC_API_KEY in the environment; without it the endpoint still works
and returns presence-only results (vibe = 0).
"""
from http.server import BaseHTTPRequestHandler
from concurrent.futures import ThreadPoolExecutor
import json
import os
import re
import time
from urllib.parse import urlparse, parse_qs

import httpx

API = "https://www.nts.live/api/v2"
MODEL = "claude-sonnet-4-6"
MAX_NAMES = 40
NTS_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
    "Accept": "application/json",
}

VIBE_SYSTEM = """Je beoordeelt of een muziekact bij NTS Radio past — niet of ze al op NTS hebben gespeeld, maar of NTS ze AUTHENTIEK zou willen draaien of programmeren.

NTS is een Londens internetstation dat zich onderscheidt door:
- Crate-digging, leftfield, non-algoritmische curatie
- Genre-fluiditeit: ambient, dub, jazz, post-punk, global/exotica, experimentele electronics, broken beat, gospel, library music, modulair, kosmische muziek, deep house/techno (vooral underground), no wave, drone, footwork, gqom, kuduro, dancehall (alleen ondergrond), zero-budget DIY
- Underground voorop: independent labels (Hessle Audio, Honest Jon's, Dekmantel, Awesome Tapes From Africa, Pre, Sound Signature, Whities, Honey Soundsystem, Ostgut Ton, Black Truffle, Editions Mego, Mexican Summer kant)
- Aesthetic: cult, kennersmuziek, sub-cultureel, scene-driven — niet voor de massa
- Steden: Londen, Berlijn, Manchester, Amsterdam-Bijlmer/noord, Bristol, Lisbon, NY underground, Detroit, Tokyo experimenteel

KRITIEK — TAAL/REGIO IS GEEN UITSLUITINGSGROND:
NTS draait regelmatig Nederlandstalige, Franse, Portugese, Arabische artiesten. Dat een act in het Nederlands rapt of zingt zegt NIETS over NTS-fit. Wat telt is scene-credibility, niet taal.

WAT WEL NTS-vibe (score hoog):
- Experimentele/underground electronica, ambient, drone
- Eclectische crate-diggers, dj's met diepe selecties
- Post-punk, no-wave, leftfield gitaarbands met arty kant
- Jazz/jazz-adjacent (spiritueel, vrij, fusion-randen)
- Global music met curator-aanpak (geen exoticisme)
- DIY, kleine labels, scene-leiders zonder pop-aspiraties
- Hardcore/punk MET artistiek bewustzijn (zoals Turnstile, niet generieke deathcore)
- Multidisciplinaire collectieven die muziek combineren met mode, kunst, video
- Protest/politieke hip-hop met DIY of punk-energie
- Niche Nederlandstalige acts met scene-aansluiting: experimentele beats, dubpoezie, art-rap, jazz-fusion
- Avant-pop/art-pop met productie die afwijkt van Top 40-formules

WAT GEEN NTS-vibe (score laag):
- Mainstream radio-pop, Top 40-singles met geprogrammeerde Spotify-distributie
- Generieke EDM, big-room house, hands-up, hardstyle
- Mainstream NL hip-hop met radio-singles (een SMAL segment, niet "alle NL hip-hop")
- Stadion-rock zonder undergroundwortels
- Radio-vriendelijke singer-songwriters
- Festival-fillers zonder eigen scene-aansluiting

Output: een strikt JSON-object, niets daarbuiten:
{
  "vibe": <int 0-100>,
  "reason": "<korte zin, ~15 woorden, waarom deze score>",
  "blurb": "<2 zinnen, NTS-redactionele toon — droog, feitelijk, crate-digger-bewoording, GEEN hype, GEEN marketing>"
}

Voor zeer lage vibe (<20): blurb is een droge zin dat het buiten NTS-spectrum valt."""


def normalize(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def slugify(name: str) -> str:
    s = (name or "").lower().strip()
    s = re.sub(r"\(.*?\)", "", s)
    s = re.sub(r"[^a-z0-9\s-]", "", s)
    s = re.sub(r"\s+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s


def candidate_slugs(name: str) -> list[str]:
    base = slugify(name)
    cands = [base]
    bare = re.sub(r"-(live|dj-set|b2b|presents|all-night-long|set)$", "", base)
    if bare != base:
        cands.append(bare)
    parts = re.split(r"\s+(?:with|w/|&|and|b2b|vs|\+)\s+", name or "", flags=re.I)
    if len(parts) >= 2:
        for p in parts:
            ps = slugify(p)
            if ps and len(ps) >= 4:
                cands.append(ps)
    return [c for c in dict.fromkeys(cands) if c and len(c) >= 4]


_MIX_CREDITS = None


def mixtape_credits() -> set[str]:
    global _MIX_CREDITS
    if _MIX_CREDITS is not None:
        return _MIX_CREDITS
    creds: set[str] = set()
    try:
        r = httpx.get(f"{API}/mixtapes", timeout=15, headers=NTS_HEADERS)
        if r.status_code == 200:
            for m in r.json().get("results", []):
                for c in m.get("credits", []):
                    n = (c.get("name") or "").strip()
                    if n:
                        creds.add(normalize(n))
    except (httpx.HTTPError, OSError):
        pass
    _MIX_CREDITS = creds
    return creds


def in_mixtape(name: str) -> bool:
    n = normalize(name)
    if not n:
        return False
    return n in mixtape_credits()


def nts_artist_page(client: httpx.Client, name: str) -> str | None:
    """NTS canonical artist URLs are /artists/<id>-<slug>. The platform also
    serves /artists/<slug> and redirects/resolves to the canonical one — so a
    200 there proves the artist plays/appears on NTS even without hosting.
    Returns the final URL when found."""
    slug = slugify(name)
    if not slug or len(slug) < 3:
        return None
    try:
        r = client.get(f"https://www.nts.live/artists/{slug}",
                       follow_redirects=True, timeout=8)
    except (httpx.HTTPError, OSError):
        return None
    if r.status_code != 200:
        return None
    final = str(r.url).lower()
    if "/artists/" not in final:
        return None
    # Defensive: confirm the response actually mentions this artist's slug
    # somewhere on the page, so we don't badge on generic fallback pages.
    body = r.text.lower()
    needle = slug.replace("-", "")
    if needle not in body.replace("-", ""):
        return None
    return str(r.url)


def nts_presence(client: httpx.Client, name: str) -> dict:
    """Presence score from hard NTS data: own show + episode count + mixtape
    + 'plays on NTS' artist-page fallback."""
    own = None
    for slug in candidate_slugs(name):
        try:
            r = client.get(f"{API}/shows/{slug}")
        except (httpx.HTTPError, OSError):
            continue
        if r.status_code == 200:
            own = r.json()
            break
        time.sleep(0.03)

    episodes = 0
    if own:
        try:
            er = client.get(f"{API}/shows/{own['show_alias']}/episodes", params={"limit": 1})
            if er.status_code == 200:
                episodes = er.json().get("metadata", {}).get("resultset", {}).get("count", 0)
        except (httpx.HTTPError, OSError):
            pass

    score = 0
    reasons: list[str] = []
    links: list[dict] = []

    if own:
        alias = own.get("show_alias")
        links.append({"label": f"Eigen NTS-show: {own.get('name', '').strip()}",
                      "url": f"https://www.nts.live/shows/{alias}"})
        if episodes >= 50:
            score, msg = 100, f"Vaste NTS-resident ({episodes} episodes)"
        elif episodes >= 10:
            score, msg = 92, f"Eigen NTS-show ({episodes} episodes)"
        elif episodes >= 1:
            score, msg = 85, f"Eigen NTS-show ({episodes} episodes)"
        else:
            score, msg = 80, "Eigen NTS-show in catalogus"
        reasons.append(msg)

    mix = in_mixtape(name)
    if mix:
        if score == 0:
            score = 70
            reasons.append("Gecredit op een NTS Infinite Mixtape (geen eigen show)")
        elif not own:
            score = max(score, 75)
            reasons.append("Ook gecredit op een NTS Infinite Mixtape")
        else:
            reasons.append("Ook in NTS Infinite Mixtape credits")

    if score == 0:
        artist_url = nts_artist_page(client, name)
        if artist_url:
            score = 60
            reasons.append("Speelt op NTS (geen eigen show)")
            links.append({"label": f"NTS-artiest: {name}", "url": artist_url})

    if score == 0:
        reasons.append("Geen NTS-aanwezigheid gevonden")

    return {
        "presence_score": score,
        "reasons": reasons,
        "nts_links": links,
        "nts_genres": [g.get("value") for g in (own or {}).get("genres", [])],
    }


_anthropic_client = None


def _get_anthropic():
    global _anthropic_client
    if _anthropic_client is not None:
        return _anthropic_client
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return None
    try:
        from anthropic import Anthropic
        _anthropic_client = Anthropic(api_key=key)
    except Exception:
        _anthropic_client = None
    return _anthropic_client


def _extract_json(text: str):
    m = re.search(r"\{[^{}]*?\}", text, re.S) or re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def judge_vibe(name: str, presence: dict) -> dict:
    client = _get_anthropic()
    if client is None:
        return {"vibe": 0, "reason": "", "blurb": ""}
    p = presence.get("presence_score", 0)
    if p == 0:
        signal = "NTS-aanwezigheid: geen — beoordeel puur op aesthetic fit."
    else:
        signal = f"Bekende NTS-aanwezigheid: {' / '.join(presence.get('reasons', []))} (presence score {p})"
    genres = ", ".join(presence.get("nts_genres") or []) or "n/a"
    user = f"Act: {name}\nFestival-beschrijving: (geen bio beschikbaar)\nFestival-genres: {genres}\n{signal}\n\nBeoordeel."
    try:
        msg = client.messages.create(
            model=MODEL,
            max_tokens=500,
            system=[{"type": "text", "text": VIBE_SYSTEM, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user}],
        )
        parsed = _extract_json(msg.content[0].text.strip())
        if parsed:
            return parsed
    except Exception:
        pass
    return {"vibe": 0, "reason": "", "blurb": ""}


def categorize(presence: int, vibe: int) -> str:
    if presence >= 80:
        return "RESIDENT"
    if presence >= 50:
        return "NTS-PRESENCE"
    if vibe >= 70:
        return "NTS-VIBE"
    if vibe >= 40:
        return "ADJACENT"
    return "OFF"


def score_name(client: httpx.Client, name: str) -> dict:
    presence = nts_presence(client, name)
    vibe = judge_vibe(name, presence)
    p = int(presence.get("presence_score", 0) or 0)
    v = int(vibe.get("vibe", 0) or 0)
    return {
        "name": name,
        "slug": slugify(name) or normalize(name),
        "url": None,
        "presence_score": p,
        "vibe_score": v,
        "score": max(p, v),
        "category": categorize(p, v),
        "blurb": vibe.get("blurb", ""),
        "vibe_reason": vibe.get("reason", ""),
        "nts_links": presence.get("nts_links", []),
        "overridden": False,
    }


def _score_one_safe(name: str) -> dict | None:
    """Each worker gets its own client so threads don't share connections."""
    try:
        with httpx.Client(timeout=10, headers=NTS_HEADERS) as c:
            return score_name(c, name)
    except Exception as e:
        print(f"score error for {name!r}: {e}")
        return None


def score_many(names: list[str]) -> dict:
    out: dict = {}
    seen: dict[str, str] = {}  # normalized -> first display name
    unique: list[str] = []
    for raw in names[:MAX_NAMES]:
        name = (raw or "").strip()
        if not name:
            continue
        key = normalize(name)
        if not key:
            continue
        if key in seen:
            continue
        seen[key] = name
        unique.append(name)

    # Parallelise so the extra artist-page fetch fits inside Vercel's 10s
    # serverless timeout even for full chunks.
    if unique:
        with ThreadPoolExecutor(max_workers=12) as pool:
            results = list(pool.map(_score_one_safe, unique))
        for name, res in zip(unique, results):
            out[name] = res

    # Echo dedup'd display names back as aliases.
    for raw in names[:MAX_NAMES]:
        name = (raw or "").strip()
        key = normalize(name) if name else ""
        if key and name not in out and seen.get(key) in out:
            out[name] = out[seen[key]]
    return out


class handler(BaseHTTPRequestHandler):
    def _send(self, code: int, payload: dict):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        qs = parse_qs(urlparse(self.path).query)
        raw = (qs.get("names", [""])[0]) or ""
        names = [n for n in raw.split(",") if n.strip()]
        if not names:
            return self._send(400, {"error": "pass ?names=a,b,c"})
        self._send(200, {"results": score_many(names)})

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            data = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, json.JSONDecodeError):
            return self._send(400, {"error": "invalid JSON body"})
        names = data.get("names") or []
        if not isinstance(names, list) or not names:
            return self._send(400, {"error": "body must be {\"names\": [...]}"})
        self._send(200, {"results": score_many(names)})
