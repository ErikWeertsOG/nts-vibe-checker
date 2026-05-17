"""Generate PWA icons in NTS Vibe Checker visual identity."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).parent.parent / "frontend" / "public"

# Lowlands palette
INDIGO_DEEP = (13, 8, 64)
RED = (184, 0, 40)
CYAN = (217, 255, 249)


def font(size: int):
    """Try Bebas Neue / Oswald / Impact-like installed fonts; fall back to default."""
    candidates = [
        "/System/Library/Fonts/HelveticaNeue.ttc",
        "/Library/Fonts/Bebas Neue.ttf",
        "/System/Library/Fonts/Supplemental/Impact.ttf",
        "/System/Library/Fonts/Supplemental/Arial Black.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    for c in candidates:
        if Path(c).exists():
            try:
                return ImageFont.truetype(c, size)
            except Exception:
                pass
    return ImageFont.load_default()


def make(size: int, path: Path, maskable: bool = False):
    img = Image.new("RGB", (size, size), INDIGO_DEEP)
    d = ImageDraw.Draw(img)

    # safe area for maskable: 80%
    margin = int(size * 0.08) if maskable else 0
    inner = size - 2 * margin

    # red square inset
    red_inset = int(inner * 0.08)
    d.rectangle(
        [(margin + red_inset, margin + red_inset),
         (margin + inner - red_inset, margin + inner - red_inset)],
        fill=RED,
    )

    # NTS text in cyan
    f = font(int(inner * 0.42))
    text = "NTS"
    bbox = d.textbbox((0, 0), text, font=f)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    tx = (size - tw) // 2 - bbox[0]
    ty = int(size * 0.13) + margin
    d.text((tx, ty), text, fill=CYAN, font=f)

    # VIBE smaller below
    f2 = font(int(inner * 0.18))
    bbox2 = d.textbbox((0, 0), "VIBE", font=f2)
    tw2 = bbox2[2] - bbox2[0]
    d.text(((size - tw2) // 2 - bbox2[0], int(size * 0.55) + margin),
           "VIBE", fill=CYAN, font=f2)

    # CHECKER even smaller
    f3 = font(int(inner * 0.10))
    bbox3 = d.textbbox((0, 0), "CHECKER", font=f3)
    tw3 = bbox3[2] - bbox3[0]
    d.text(((size - tw3) // 2 - bbox3[0], int(size * 0.72) + margin),
           "CHECKER", fill=CYAN, font=f3)

    img.save(path, "PNG", optimize=True)
    print(f"  wrote {path.name} ({size}px)")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    make(192, OUT / "icon-192.png")
    make(512, OUT / "icon-512.png")
    make(512, OUT / "icon-512-maskable.png", maskable=True)
    make(180, OUT / "apple-touch-icon.png")  # iOS specific
    make(32, OUT / "favicon-32.png")
    # also write a 16x16 favicon for the tab
    make(16, OUT / "favicon-16.png")


if __name__ == "__main__":
    main()
