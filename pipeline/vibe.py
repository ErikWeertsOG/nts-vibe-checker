"""Claude-judged aesthetic NTS-vibe score per act.

Independent from NTS-presence (which is hard data). This is: 'would NTS
actually play / book this artist based on their sound, scene, label,
collaborators and ethos?' Trained on what makes NTS NTS."""
from __future__ import annotations
import json
import os
import re
from pathlib import Path
from anthropic import Anthropic

from blurbs import _load_dotenv  # reuses .env loader

CACHE = Path(__file__).parent.parent / "data" / "cache" / "vibe_judgments.json"
MODEL = "claude-sonnet-4-6"

SYSTEM = """Je beoordeelt of een muziekact bij NTS Radio past — niet of ze al op NTS hebben gespeeld, maar of NTS ze AUTHENTIEK zou willen draaien of programmeren.

NTS is een Londens internetstation dat zich onderscheidt door:
- Crate-digging, leftfield, non-algoritmische curatie
- Genre-fluïditeit: ambient, dub, jazz, post-punk, global/exotica, experimentele electronics, broken beat, gospel, library music, modulair, kosmische muziek, deep house/techno (vooral underground), no wave, drone, footwork, gqom, kuduro, dancehall (alleen ondergrond), zero-budget DIY
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
- **Multidisciplinaire collectieven** die muziek combineren met mode, kunst, video (Bijlmer-scene zoals SMIB, NY-collectieven zoals Standing on the Corner)
- **Protest/politieke hip-hop** met DIY of punk-energie (NTS heeft veel programma's gewijd aan radicale hip-hop, b.v. shows van Mike, Pink Siifu, kant van Death Grips/JPEGMAFIA, NL: Typhoon's politiekere werk, IJsland)
- **Niche Nederlandstalige acts** met scene-aansluiting: experimentele beats, dubpoëzie, art-rap, jazz-fusion (b.v. Sevdaliza, Sef's leftfield werk, Eefje de Visser's experimentele kant, Goldband's lo-fi vroege werk)
- Avant-pop/art-pop met productie die afwijkt van Top 40-formules

WAT GEEN NTS-vibe (score laag):
- Mainstream radio-pop, Top 40-singles met geprogrammeerde Spotify-distributie
- Generieke EDM, big-room house, hands-up, hardstyle
- **Mainstream NL hip-hop met radio-singles** (Antoon, Frenna chart-werk, Snelle, generieke nederhop) — let op: dit is een SMAAL segment, niet "alle NL hip-hop"
- Stadion-rock zonder undergroundwortels
- Radio-vriendelijke singer-songwriters
- Festival-fillers zonder eigen scene-aansluiting

VUISTREGELS bij twijfel:
1. Heeft de act een eigen label, of staat 'ie bij een onafhankelijk label? → punten omhoog
2. Werkt de act vaak samen met experimentele/leftfield producers? → punten omhoog
3. Is de productie ruwer of meer art-school dan radio-glad? → punten omhoog
4. Is er een politieke, DIY of artistieke missie achter het werk? → punten omhoog
5. Klinkt het als iets dat een NTS-dj zou kunnen mixen tussen ambient en footwork? → punten omhoog
6. Is de productie radio-glad én de teksten over uitgaan/feest/lifestyle? → punten omlaag
7. Wordt de act geprogrammeerd op de hoofdpodia van álle festivals? → meestal punten omlaag (uitzondering: cult-artiesten zoals JPEGMAFIA, Turnstile)

Output: één strikt JSON-object, niets daarbuiten:
{
  "vibe": <int 0-100>,
  "reason": "<korte zin, ~15 woorden, waarom deze score>",
  "blurb": "<2 zinnen, NTS-redactionele toon — droog, feitelijk, crate-digger-bewoording, GEEN hype, GEEN marketing>"
}

Voor zeer lage vibe (<20): blurb is één droge zin dat het buiten NTS-spectrum valt."""

USER_TEMPLATE = """Act: {name}
Lowlands beschrijving: {bio}
Lowlands genres: {genres}
{nts_signal}

Beoordeel."""


def _build_nts_signal(act_with_score: dict) -> str:
    s = act_with_score.get("presence_score", 0)
    if s == 0:
        return "NTS-aanwezigheid: geen — beoordeel puur op aesthetic fit."
    bits = act_with_score.get("reasons", [])
    return f"Bekende NTS-aanwezigheid: {' / '.join(bits)} (presence score {s})"


def _extract_json(text: str) -> dict | None:
    """Pull first {...} JSON object from text."""
    m = re.search(r"\{[^{}]*?\}", text, re.S)
    if not m:
        # try greedier — multiple braces
        m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def judge(client: Anthropic, act: dict) -> dict:
    bio = (act.get("bio") or "")[:1200]
    user = USER_TEMPLATE.format(
        name=act["name"],
        bio=bio or "(geen bio beschikbaar)",
        genres=", ".join(act.get("lowlands_genres") or []) or "n/a",
        nts_signal=_build_nts_signal(act),
    )
    msg = client.messages.create(
        model=MODEL,
        max_tokens=500,
        system=[{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user}],
    )
    raw = msg.content[0].text.strip()
    parsed = _extract_json(raw)
    if not parsed:
        return {"vibe": 0, "reason": "parse error", "blurb": "", "_raw": raw[:200]}
    return parsed


_load_dotenv()


def judge_all(acts_with_presence: list[dict], force: bool = False) -> dict[str, dict]:
    cache: dict[str, dict] = {}
    if CACHE.exists() and not force:
        cache = json.loads(CACHE.read_text())

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("  WARNING: no ANTHROPIC_API_KEY — skipping vibe judgments")
        return cache

    client = Anthropic(api_key=api_key)
    todo = [a for a in acts_with_presence if a["slug"] not in cache]
    print(f"  judging {len(todo)} acts (cached: {len(cache)})")

    CACHE.parent.mkdir(parents=True, exist_ok=True)
    for i, act in enumerate(todo):
        try:
            cache[act["slug"]] = judge(client, act)
        except Exception as e:
            print(f"  ! {act['name']}: {e}")
            cache[act["slug"]] = {"vibe": 0, "reason": f"err: {e}", "blurb": ""}
        if (i + 1) % 10 == 0:
            print(f"  {i+1}/{len(todo)}")
            CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=2))

    CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=2))
    return cache
