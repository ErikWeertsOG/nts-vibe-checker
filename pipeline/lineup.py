"""Fetch Lowlands 2026 lineup from sitemap.xml."""
import re
import httpx
from urllib.parse import unquote

SITEMAP = "https://lowlands.nl/sitemap.xml"
ACT_RE = re.compile(r"https://lowlands\.nl/acts/([^/<]+)/")


def slug_to_name(slug: str) -> str:
    name = unquote(slug).replace("-", " ").strip()
    return " ".join(w.capitalize() if not w.isupper() else w for w in name.split())


def fetch_lineup() -> list[dict]:
    xml = httpx.get(SITEMAP, timeout=30).text
    slugs = ACT_RE.findall(xml)
    seen, acts = set(), []
    for slug in slugs:
        if slug in seen or slug == "":
            continue
        seen.add(slug)
        acts.append({
            "slug": slug,
            "name": slug_to_name(slug),
            "url": f"https://lowlands.nl/acts/{slug}/",
        })
    return acts


if __name__ == "__main__":
    acts = fetch_lineup()
    print(f"Found {len(acts)} acts")
    for a in acts[:10]:
        print(f"  {a['name']}  ({a['slug']})")
