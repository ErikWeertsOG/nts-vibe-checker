---
title: Lowlands
url: https://lowlands.nl
extracted_at: 2026-05-17
tokens:
  colors:
    primary: "#B80028"          # vivid tomato red — dominant brand color
    primary_dark: "#262626"     # near-black for high-contrast surfaces
    accent_blue: "#1371C3"      # used for tags/links
    accent_cyan: "#D9FFF9"      # mint-cyan, button text on dark
    accent_indigo: "#1B1464"    # deep purple, button bg + headers
    cream: "#FFEBE7"            # soft warm offwhite, occasional bg
    text_default: "#262626"
    text_on_dark: "#D9FFF9"
  typography:
    font_display: "\"Bruta Condensed\", \"Bebas Neue\", \"Oswald\", sans-serif"
    font_body: "Averta, \"Helvetica Neue\", Helvetica, Arial, sans-serif"
    font_decorative: "\"LL25 ColorBender\", \"LL25 Solid\""
    h1_size: "clamp(64px, 12vw, 220px)"
    h2_size: "clamp(40px, 6vw, 96px)"
    body_size: "20px"
    line_height_body: "26px"
    transform_display: "uppercase"
    letter_spacing_display: "0"
  spacing:
    base_unit: "8px"
    section_padding_y: "0"      # full-bleed sections, no padding
  radius:
    btn: "0px"                  # square corners everywhere
    card: "0px"
---

# Design System — Lowlands.nl

## Visual identity
Maximalist, candy-pop psychedelic. Elke sectie is een **full-bleed kleurenveld** met 3D-pixel-art "tentvormen" en gigantische verstrobeerde all-caps wordmarks (UPDATES, PROGRAMMA, TICKETS, FAQ). De homepage is bijna een toolkit van color-stories — warm oranje-bruin → electric mint → hot pink → deep purple — die het festival-gevoel van overstimulering en gelaagdheid uitdrukken.

De brand-identity steunt op:
1. **Contrast tussen rauw en geordend.** Wilde compositie, maar strakke typografie.
2. **All-caps display** in een geometrisch-condensed font.
3. **Zero rounding.** Alle UI (buttons, cards, tags) heeft scherpe hoeken — geen rounded corners.
4. **Saturatie.** Vrijwel geen pastels; kleuren zijn vol of er is een hoog-contrast donker.

## Color palette

| Token | Hex | Usage |
|---|---|---|
| `primary` | `#B80028` | Body color base, brand red |
| `accent_indigo` | `#1B1464` | Button backgrounds, deep accents |
| `accent_cyan` | `#D9FFF9` | Text on dark buttons, links |
| `accent_blue` | `#1371C3` | Secondary links, info |
| `primary_dark` | `#262626` | Body text on light, surfaces |
| `cream` | `#FFEBE7` | Soft warm background |

## Typography
- **Display:** `Bruta Condensed` — heavy condensed sans-serif, all-caps, ultra-tight. Lowlands gebruikt 'm voor *alle* wordmarks en hero-text.
- **Body:** `Averta` — geometric sans, neutrale companion van Bruta. 20px regular met 26px line-height.
- **Decoratief:** `LL25 ColorBender` / `LL25 Solid` — custom 3D-pixel display fonts voor de wordmarks zelf. Niet web-distributable; vervangen door display alternatieven.

Web-safe alternatieven voor agents: **Bebas Neue** of **Oswald** (Google Fonts) benaderen Bruta Condensed redelijk.

## Buttons / CTAs
- **Vorm:** rechthoekig, scherpe hoeken (`border-radius: 0`).
- **Bg:** vaak `accent_indigo` (#1B1464) met `accent_cyan` text. Top-right "SIMPLE | MENU" is hét kanonieke voorbeeld.
- **Padding:** beperkt (~12-16px horizontaal, 8-12px verticaal).
- **Type:** all-caps, Bruta Condensed of vergelijkbaar, vetter dan body.
- **Geen rounded, geen drop shadow, geen gradients.** Plat en stempel-achtig.

## Layout principes
- **Full-bleed sections** met sterk verschillende kleurpalette per sectie.
- **Sticky tagline** onderaan ("A campingflight to Lowlands paradise / 21+22+23 augustus 2026").
- **Vaste header rechtsboven** (compact menu): "SIMPLE | MENU" — twee aaneengeplakte buttons.
- **Cookies pillbox** linksonder als zwevende oval (de enige rounded vorm op de site).

## Voice
- **Direct en kort.** "SIMPLE", "MENU", "UPDATES", "PROGRAMMA" — labels, geen zinnen.
- **Nederlandstalig.** Tutoyeert.
- **Speels, anti-corporate.** De copywriting durft kinderachtig of cryptisch te zijn.
- **Festival-jargon.** "Campingflight", "Lowlands Paradise" — geen uitleg, je weet 't of niet.

## Toepassing op NTS Vibe Checker
Cherry-picks voor onze site (NTS Vibe Checker is data-densitiet, dus we hoeven niet maximalistisch te zijn):

1. **Background:** vervang puur zwart met diep-indigo `#1B1464` of dieper variant → zelfde "donker maar warm" gevoel.
2. **Score-badge "RESIDENT":** brand-rood `#B80028` met cyan-cream text → directe Lowlands-referentie.
3. **Score-badge "VIBE":** mint-cyan `#D9FFF9` met indigo text.
4. **Buttons / filter tabs:** scherpe hoeken (radius 0), indigo bg, cyan text, all-caps Bruta Condensed alternative (Bebas Neue).
5. **H1 / "NTS VIBE CHECKER":** Bebas Neue, all-caps, extra-large, condensed.
6. **Section labels in cards** (GENRES, NTS-SPOREN): klein, Bebas Neue all-caps, in cyan.
7. **Houden zoals het is:** sparse layout, expandable cards, score-bars — Lowlands is chaotisch maar we hebben informatie te tonen.
