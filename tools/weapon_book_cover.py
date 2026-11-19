"""Localize the approved Publisher cover without flattening or covering its artwork."""
from __future__ import annotations

import hashlib
from io import BytesIO
from pathlib import Path
import re

import pymupdf
from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"
FONTS = {
    "regular": FONT_DIR / "Carlito-Regular.ttf",
    "bold": FONT_DIR / "Carlito-Bold.ttf",
    "display": FONT_DIR / "Anton-Regular.ttf",
}
# The title operators are specific to this Publisher export. On a different
# export, fail closed rather than deleting a similarly named illustration.
SOURCE_STREAM_SHA256 = "03be355195438fc71826ec4ff67137407b3311fab9921b788a61c1d7c48f2743"
GRAIN_START = b" EMC  /P <</MCID 22>> BDC"


def restore_transparency_group(source: pymupdf.Page, target: pymupdf.Page) -> None:
    """Preserve the Publisher inline page group that insert_pdf drops."""
    kind, group = source.parent.xref_get_key(source.xref, "Group")
    if kind == "dict":
        target.parent.xref_set_key(target.xref, "Group", group)


def _draw_title(page: pymupdf.Page, title: str, baseline: float, font_id: str,
                size: float, color: tuple[float, float, float], max_width: float) -> None:
    path = FONTS[font_id]
    font = pymupdf.Font(fontfile=str(path))
    size = min(size, max_width / font.text_length(title, fontsize=1))
    x = (page.rect.width - font.text_length(title, fontsize=size)) / 2

    # Only the shadow is an image, with a soft mask; the text remains selectable
    # and the rest of the page is never rasterized.
    scale = 6
    pad = 24
    shadow_font = ImageFont.truetype(str(path), round(size * scale))
    left, top, right, bottom = shadow_font.getbbox(title, anchor="ls")
    mask = Image.new("L", (right - left + 2 * pad, bottom - top + 2 * pad))
    ImageDraw.Draw(mask).text((pad - left, pad - top), title, font=shadow_font,
                              anchor="ls", fill=145)
    tile = Image.new("RGBA", mask.size, (15, 20, 29))
    tile.putalpha(mask.filter(ImageFilter.GaussianBlur(radius=scale * .85)))
    png = BytesIO()
    tile.save(png, format="PNG")
    x0 = x + (left - pad) / scale + .7
    y0 = baseline + (top - pad) / scale + 1.65
    page.insert_image(pymupdf.Rect(x0, y0, x0 + tile.width / scale,
                                   y0 + tile.height / scale), stream=png.getvalue())
    page.insert_text((x, baseline), title, fontname=font_id, fontsize=size, color=color)


def make_localized_cover(source: Path, output: Path) -> None:
    """Replace Russian title placements, keeping the original grain above the text."""
    with pymupdf.open(source) as original, pymupdf.open() as cover:
        page = original[0]
        content = page.read_contents()
        if hashlib.sha256(content).hexdigest() != SOURCE_STREAM_SHA256 or len(page.get_contents()) != 1:
            raise ValueError("English cover requires the approved Publisher cover content stream")
        (stream_xref,) = page.get_contents()
        before, grain = content.split(GRAIN_START, 1)
        # These image operators are the Russian glyph fills and their effects.
        # The source rules, cream strip, art, background and masks stay intact.
        before = re.sub(rb"/Image(?:23|25|34|38|40|42|49|53) Do(?= Q)", b"", before)
        before = re.sub(rb"BT\s*/F[3456] \d+\.\d+ Tf\b.*?\bET\b", b"", before, flags=re.S)
        for font_id, path in FONTS.items():
            page.insert_font(fontname=font_id, fontfile=str(path))
        yellow = (.98, .76, .06)
        _draw_title(page, "VOLUME 1", 56.04, "regular", 28, yellow, 130)
        _draw_title(page, "BROTHERHOOD FIELD GUIDE", 131.18, "bold", 51.96, yellow, 505)
        _draw_title(page, "WASTELAND ARSENAL", 776.38, "display", 44.5, (.025, .025, .025), 365)
        # PyMuPDF may add q/Q wrapper streams around pre-existing content; only
        # move the new text/shadow operators to the original typography layer.
        new_streams = [original.xref_stream(xref) for xref in page.get_contents() if xref != stream_xref]
        title_streams = [item for item in new_streams if re.search(rb"\b(?:BT|Do)\b", item)]
        if len(title_streams) != 6:
            raise ValueError("Unexpected PDF streams while composing the English cover")
        original.update_stream(stream_xref, before + b"\n" + b"\n".join(title_streams)
                               + b"\n" + GRAIN_START + grain)
        original.xref_set_key(page.xref, "Contents", f"{stream_xref} 0 R")
        cover.insert_pdf(original, from_page=0, to_page=0)
        restore_transparency_group(page, cover[0])
        cover.save(output, garbage=4, deflate=True)
