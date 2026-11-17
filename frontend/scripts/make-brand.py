"""Builds the Baithak logo, mark and favicons into frontend/public.

The mark: a jharoka arch (the brand red) with two people sitting side by side on a gaddi
cushion under a lamp. A baithak is the room where people sit together and talk.

Run from frontend/ (fonttools reads the woff2 from the installed Fraunces package):
    uv run --no-project --with fonttools==4.61.0 --with brotli --with pillow==13.0.0 \\
        python -I scripts/make-brand.py
PNG files are rendered with resvg (resvg-py).
"""

import io
import json
from pathlib import Path

from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
from PIL import Image
from resvg_py import svg_to_bytes

FRONTEND = Path(__file__).resolve().parent.parent
PUBLIC = FRONTEND / "public"
FONT = FRONTEND / "node_modules/@fontsource-variable/fraunces/files/fraunces-latin-full-normal.woff2"

TOMATO = "#c73a1e"
TOMATO_DARK_MODE = "#e04527"
CREAM = "#fbf8f2"
MUSTARD = "#e3b12c"
INK = "#1f1a15"
INK_DARK_MODE = "#f3ece0"
SAND = "#fbf8f2"

# The mark lives in a 200 x 200 box.
ARCH = (
    "M30 196V100C30 62 58 44 82 30C92 24 98 16 100 6"
    "C102 16 108 24 118 30C142 44 170 62 170 100V196Z"
)
# Two people sitting side by side, heads turned a little toward each other, with a diya (oil
# lamp) on the floor between them and the open arch above.
PEOPLE = (
    '<circle cx="68" cy="99" r="13"/><circle cx="132" cy="99" r="13"/>'
    '<path d="M42 168V140C42 123 53 116 65 116C77 116 88 123 88 140V168Z"/>'
    '<path d="M112 168V140C112 123 123 116 135 116C147 116 158 123 158 140V168Z"/>'
)
DIYA = (
    '<path d="M100 132C106 140 107 146 100 152C93 146 94 140 100 132Z"/>'
    '<path d="M89 156H111C111 163 106 167 100 167C94 167 89 163 89 156Z"/>'
)
CUSHION = '<rect x="36" y="171" width="128" height="14" rx="7"/>'


def mark(arch: str = TOMATO) -> str:
    return (
        f'<path fill="{arch}" class="arch" d="{ARCH}"/>'
        f'<g fill="{CREAM}">{PEOPLE}</g>'
        f'<g fill="{MUSTARD}">{DIYA}{CUSHION}</g>'
    )


def wordmark() -> tuple[str, tuple[float, float, float, float]]:
    font = instantiateVariableFont(
        TTFont(FONT), {"wght": 640, "opsz": 144, "SOFT": 100, "WONK": 1}
    )
    glyphs, cmap, hmtx = font.getGlyphSet(), font.getBestCmap(), font["hmtx"]
    pen, bounds, x = SVGPathPen(glyphs), BoundsPen(glyphs), 0.0
    for char in "baithak":
        name = cmap[ord(char)]
        flip = (1, 0, 0, -1, x, 0)  # fonts are y-up, SVG is y-down
        glyphs[name].draw(TransformPen(pen, flip))
        glyphs[name].draw(TransformPen(bounds, flip))
        x += hmtx[name][0] - 10
    assert bounds.bounds is not None
    return pen.getCommands(), bounds.bounds


ADAPTIVE_STYLE = (
    "<style>@media (prefers-color-scheme: dark){"
    f".ink{{fill:{INK_DARK_MODE}}}.arch{{fill:{TOMATO_DARK_MODE}}}}}</style>"
)


def logo_svg(background: str | None) -> str:
    """The 4:3 logo, 1200 x 900: the mark above the wordmark."""
    d, (x0, y0, x1, y1) = wordmark()
    width, height = 1200, 900
    word_width = 700
    scale = word_width / (x1 - x0)
    word_height = (y1 - y0) * scale
    mark_size = 400
    gap = 56
    top = (height - (mark_size + gap + word_height)) / 2
    mark_x = (width - mark_size) / 2
    word_x = (width - word_width) / 2 - x0 * scale
    word_y = top + mark_size + gap - y0 * scale
    bg = f'<rect width="{width}" height="{height}" fill="{background}"/>' if background else ""
    style = "" if background else ADAPTIVE_STYLE
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}" role="img" aria-label="Baithak">'
        f"<title>Baithak</title>{style}{bg}"
        f'<g transform="translate({mark_x} {top}) scale({mark_size / 200})">{mark()}</g>'
        f'<path class="ink" fill="{INK}" '
        f'transform="translate({word_x:.2f} {word_y:.2f}) scale({scale:.5f})" d="{d}"/>'
        "</svg>\n"
    )


def mark_svg() -> str:
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200" role="img" '
        f'aria-label="Baithak"><title>Baithak</title>{ADAPTIVE_STYLE}{mark()}</svg>\n'
    )


def favicon_svg() -> str:
    # Small sizes drop the diya and crop the sides so the two people stay readable.
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="5 6 190 190">'
        f"{ADAPTIVE_STYLE}"
        f'<path fill="{TOMATO}" class="arch" d="{ARCH}"/>'
        f'<g fill="{CREAM}">{PEOPLE}</g><g fill="{MUSTARD}">{CUSHION}</g></svg>\n'
    )


def tile_svg(size: int) -> str:
    """Square icon on the cream background, for home screens that ignore transparency."""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200" width="{size}" '
        f'height="{size}"><rect width="200" height="200" fill="{SAND}"/>'
        f'<g transform="translate(24 22) scale(0.76)">{mark()}</g></svg>\n'
    )


def render(svg: str, out: Path, width: int) -> None:
    out.write_bytes(bytes(svg_to_bytes(svg_string=svg, width=width)))


def main() -> None:
    PUBLIC.mkdir(exist_ok=True)
    (PUBLIC / "logo.svg").write_text(logo_svg(None), encoding="utf-8", newline="\n")
    (PUBLIC / "logo-mark.svg").write_text(mark_svg(), encoding="utf-8", newline="\n")
    (PUBLIC / "favicon.svg").write_text(favicon_svg(), encoding="utf-8", newline="\n")
    render(logo_svg(SAND), PUBLIC / "logo.png", 1200)
    render(tile_svg(180), PUBLIC / "apple-touch-icon.png", 180)
    render(tile_svg(512), PUBLIC / "icon-512.png", 512)

    sizes = [16, 32, 48]
    frames = []
    for size in sizes:
        png = PUBLIC / f"favicon-{size}.png"
        render(favicon_svg(), png, size)
        frames.append(Image.open(io.BytesIO(png.read_bytes())).convert("RGBA"))
        png.unlink()
    frames[-1].save(PUBLIC / "favicon.ico", sizes=[(s, s) for s in sizes], append_images=frames[:-1])
    print(json.dumps(sorted(p.name for p in PUBLIC.iterdir())))


if __name__ == "__main__":
    main()
