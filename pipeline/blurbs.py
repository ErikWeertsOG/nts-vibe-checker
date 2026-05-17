"""Generate NTS-style blurbs explaining why each act fits NTS-vibe."""
from __future__ import annotations
import json
import os
from pathlib import Path
from anthropic import Anthropic


def _load_dotenv():
    p = Path(__file__).parent / ".env"
    if p.exists():
        for line in p.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip()
            if not os.environ.get(k):  # override empty values too
                os.environ[k] = v

_load_dotenv()

CACHE = Path(__file__).parent.parent / "data" / "cache" / "blurbs.json"
MODEL = "claude-sonnet-4-6"

SYSTEM = """Je schrijft korte, droge, feitelijke blurbs in de redactionele toon van NTS Radio.
Stijl: helder, beknopt, crate-digger-bewoording, geen hype-taal, geen uitroeptekens, geen marketing-clichés.
Engels OF Nederlands — kies de taal van de input. Voor Engelse artistnamen schrijf je Engels, voor Nederlandse Nederlands.
Lengte: 2 zinnen, max ~50 woorden. Geen quotes, geen titel. Begin direct met inhoud.

Goede voorbeelden van NTS-toon:
- "Detroit-geboren, Berlijn-gestationeerd. Hunee draait dwars door house, soul, jazz en exotica zonder ooit op autopilot te gaan."
- "Floating Points heeft een PhD in neurowetenschappen en bouwt zijn livesets met dezelfde precisie. Modulaire synths, gospel-piano, broken beat — alles past."

Slechte voorbeelden (vermijden):
- "Een geweldige artiest die je niet mag missen!"
- "Met zijn unieke stijl tovert hij elke dansvloer om in..."
"""

USER_TEMPLATE = """Schrijf een NTS-stijl blurb voor: {name}

Wat we weten:
- Score op NTS-vibe: {score}/100
- {reasons}
- NTS-genres: {genres}
- NTS-show beschrijving: {nts_desc}

Schrijf 2 zinnen die uitleggen waarom dit een NTS-act is. Bij score 0: schrijf 1 droge zin dat ze niet op NTS-radar staan."""


def generate_blurb(client: Anthropic, act: dict) -> str:
    user = USER_TEMPLATE.format(
        name=act["name"],
        score=act["score"],
        reasons="; ".join(act.get("reasons", [])) or "geen",
        genres=", ".join(act.get("genres") or []) or "onbekend",
        nts_desc=(act.get("nts_description") or "n.v.t.")[:400],
    )
    msg = client.messages.create(
        model=MODEL,
        max_tokens=200,
        system=[
            {"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}
        ],
        messages=[{"role": "user", "content": user}],
    )
    return msg.content[0].text.strip()


def generate_all(scored: list[dict], force: bool = False) -> dict[str, str]:
    cache: dict[str, str] = {}
    if CACHE.exists() and not force:
        cache = json.loads(CACHE.read_text())

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("  WARNING: no ANTHROPIC_API_KEY — skipping blurbs")
        return cache

    client = Anthropic(api_key=api_key)
    todo = [a for a in scored if a["name"] not in cache]
    print(f"  generating {len(todo)} blurbs (cached: {len(cache)})")

    CACHE.parent.mkdir(parents=True, exist_ok=True)
    for i, act in enumerate(todo):
        try:
            cache[act["name"]] = generate_blurb(client, act)
        except Exception as e:
            print(f"  ! {act['name']}: {e}")
            cache[act["name"]] = ""
        if (i + 1) % 10 == 0:
            print(f"  {i+1}/{len(todo)}")
            CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=2))

    CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=2))
    return cache
