#!/usr/bin/env python3
"""Render a weapon reference card (A4, one weapon per page) to print-ready PDF.

The layout is a faithful port of the Publisher template measured from
docs/render/Справочник оружия-pinkibook-018.pdf:

    page ............ A4 595.28 x 841.89 pt
    content column .. x 36.31 .. 559.58 (184.6 mm)
    title ........... Carlito Bold 21.98 pt, uppercase, centred
    rule ............ 385.94 x 2.28 pt
    subtitle ........ 14.04 pt
    image ........... fit into 21.43 .. 573.93 / 104 .. 304
    stats table ..... 7 cols, header 34.97 pt, body 33.24 pt
    description ..... 12 pt / 17.4 pt, justified
    mods table ...... 50.1 pt label + 6 columns, fills to y 803.35

Input is a presentation-ready card JSON (see data/weapons/cards/).  A card is
produced from the Companion JSON by tools/weapons2cards.py; keeping the two
steps apart means the same card can later feed the web catalog.

Usage:
    python3 tools/weapon2pdf.py data/weapons/cards/combat-rifle.json \
        --out docs/render/out/combat-rifle.pdf

    # Replay the Publisher artwork layer emitted by extract_pdf_images.py.
    python3 tools/weapon2pdf.py data/weapons/cards/combat-rifle.json \
        --out docs/render/out/combat-rifle-manifest.pdf \
        --artwork-manifest docs/render/pdf-extract/publisher-art/artwork-manifest.json
"""

from __future__ import annotations

import argparse
import io
import json
import math
import os
import sys
from dataclasses import dataclass
from typing import Any

from reportlab.lib.colors import Color
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT_DIR = os.path.join(ROOT, "assets", "fonts")

PAGE_W, PAGE_H = A4  # 595.2756 x 841.8898

# --- geometry (points, y measured from the top of the page) -----------------
MARGIN_L = 36.31
CONTENT_R = 559.58
CONTENT_W = CONTENT_R - MARGIN_L

TITLE_TOP = 47.59
TITLE_SIZE = 21.98
RULE_TOP = 78.37
RULE_H = 2.28
RULE_W = 385.94
SUBTITLE_TOP = 87.53
SUBTITLE_SIZE = 14.04

IMAGE_BOX = (21.43, 78.98, 573.93, 331.64)  # x0, y0(top), x1, y1(bottom)

STATS_TOP = 307.39
STATS_HEADER_H = 34.97
STATS_BODY_H = 33.24
STATS_COLS = [36.313, 89.761, 147.74, 205.71, 264.80, 339.03, 421.60, 559.58]
STATS_HEADER_SIZE = 9.96
STATS_HEADER_TIGHT_SIZE = 9.0  # «СКОРОСТЬ СТРЕЛЬБЫ» in two lines
STATS_BODY_SIZE = 9.96

DESC_LEFT = 39.12
DESC_RIGHT = 556.05
DESC_TOP = 404.57
DESC_SIZE = 12.0
DESC_LEADING = 17.4

MODS_HEADING = "ПОДДЕРЖИВАЕМЫЕ МОДИФИКАЦИИ"
MODS_HEADING_TOP = 488.29
MODS_HEADING_GAP = 45.36  # heading top -> table top on the Publisher pages
MODS_HEADING_SIZE = 18.0

MODS_TOP = 533.65
MODS_BOTTOM = 803.35
# Keep the visible 0.6pt grid stroke inside the content column.  The
# Publisher centres a stroke on the coordinate, so the geometric table edge is
# inset by half a stroke rather than allowed to bleed past the margins.
MODS_LEFT = MARGIN_L + 0.3
MODS_LABEL_RIGHT = 86.54
MODS_RIGHT = CONTENT_R - 0.3
MODS_MAX_COLS = 6
# Six-column reference grid; its outer edges follow the stroke-safe bounds.
MODS_EDGES = [MODS_LEFT, 86.54, 167.80, 244.00, 326.04, 404.58, 481.17, MODS_RIGHT]
MODS_LABEL_W = MODS_LABEL_RIGHT - MODS_LEFT
MODS_FONT_SIZE = 9.0
MODS_LEADING = 13.08
MODS_MIN_ROW = 20.73
MODS_ROW_SLOPE = 12.5
MODS_ROW_BASE = 6.0
MODS_H_PAD = 7.2  # total left+right padding inside a mod cell
MODS_LABEL_SIZE = 9.96

PAGE_NUMBER_TOP = 810.91
PAGE_NUMBER_SIZE = 9.96

# Cards without a mods table have ample blank space below their description.
# Keep the original heading position for short copy, but move the explicit
# no-mods notice down when necessary instead of omitting the end of prose.
NO_MODS_DESC_GAP = 20.0
NO_MODS_HEADING_MAX_TOP = PAGE_NUMBER_TOP - MODS_HEADING_SIZE - 12.0

BEIGE = Color(1.0, 0.922, 0.804)  # #FFEBCD
ORANGE = Color(1.0, 0.776, 0.455)  # #FFC674
BLACK = Color(0, 0, 0)
WHITE = Color(1, 1, 1)
RULE_W_PT = 0.6

HEADERS = [
    "ПАТРОН",
    "ТИП УРОНА",
    "УРОН",
    "СКОРОСТЬ СТРЕЛЬБЫ",
    "ДИСТАНЦИЯ",
    "ЭФФЕКТЫ",
    "КАЧЕСТВА",
]

# Calibri/Carlito typographic ascent; PyMuPDF measures text boxes with it.
ASCENT = 0.75

PAPER = os.path.join(ROOT, "assets", "pdf", "paper.jpg")
DAMAGE_ICON = os.path.join(ROOT, "assets", "pdf", "damage-icon.png")

# Schema written by tools/extract_pdf_images.py. Keep the reader independent
# from PyMuPDF so rendering a card needs only the normal PDF requirements.
ARTWORK_MANIFEST_SCHEMA = "fallout-2d20.artwork-manifest/v1"


class ArtworkManifestError(ValueError):
    """A manifest cannot be used safely to reconstruct an artwork layer."""


@dataclass(frozen=True)
class ArtworkLayer:
    """One source-PDF page and the directory containing its exported assets."""

    manifest_path: str
    asset_root: str
    page: dict[str, Any]


def register_fonts() -> None:
    pdfmetrics.registerFont(
        TTFont("Carlito", os.path.join(FONT_DIR, "Carlito-Regular.ttf"))
    )
    pdfmetrics.registerFont(
        TTFont("Carlito-Bold", os.path.join(FONT_DIR, "Carlito-Bold.ttf"))
    )
    pdfmetrics.registerFontFamily(
        "Carlito", normal="Carlito", bold="Carlito-Bold", italic="Carlito",
        boldItalic="Carlito-Bold",
    )


def sw(text: str, font: str, size: float) -> float:
    return pdfmetrics.stringWidth(text, font, size)


def y_from_top(y_top: float) -> float:
    return PAGE_H - y_top


def draw_top(c, x, y_top, text, font, size, align="left"):
    """Draw one line with its typographic top at y_top."""
    text_w = sw(text, font, size)
    if align == "center":
        x -= text_w / 2.0
    elif align == "right":
        x -= text_w
    c.setFillColor(BLACK)
    c.setFont(font, size)
    c.drawString(x, y_from_top(y_top + ASCENT * size), text)
    return text_w


def draw_center_line(c, y_top, text, font, size):
    return draw_top(c, PAGE_W_WORK_CENTER, y_top, text, font, size, "center")


PAGE_W_WORK_CENTER = (MARGIN_L + CONTENT_R) / 2.0


def wrap_text(text: str, font: str, size: float, width: float) -> list[str]:
    words = text.split()
    if not words:
        return []
    lines, cur = [], words[0]
    for word in words[1:]:
        candidate = cur + " " + word
        if sw(candidate, font, size) <= width:
            cur = candidate
        else:
            lines.append(cur)
            cur = word
    lines.append(cur)
    return lines


def draw_justified(c, x, width, y_top, lines, font, size, leading,
                   color=BLACK):
    """Justify all lines but the last, which stays flush left."""
    c.setFillColor(color)
    c.setFont(font, size)
    for i, line in enumerate(lines):
        baseline = y_from_top(y_top + ASCENT * size + i * leading)
        words = line.split()
        if i == len(lines) - 1 or len(words) == 1:
            c.drawString(x, baseline, line)
            continue
        gap = (width - sum(sw(w, font, size) for w in words)) / (len(words) - 1)
        cursor = x
        for word in words:
            c.drawString(cursor, baseline, word)
            cursor += sw(word, font, size) + gap


_PAPER_CACHE = {}


def paper_placement():
    """Bottom-left placement of the cover-fit paper texture."""
    h = PAGE_H * 1.006
    w = h * (2588 / 1690)
    return (PAGE_W - w) / 2.0, (PAGE_H - h) / 2.0, w, h


def draw_paper(c) -> None:
    if not os.path.exists(PAPER):
        return
    x, y, w, h = paper_placement()
    c.drawImage(PAPER, x, y, w, h, preserveAspectRatio=False, mask=None)


def _paper_image():
    if "im" not in _PAPER_CACHE:
        from PIL import Image
        _PAPER_CACHE["im"] = Image.open(PAPER).convert("RGB")
    return _PAPER_CACHE["im"]


def flatten_on_paper(path, box, dpi=300, fit="contain"):
    """Alpha-composite an image onto the exact paper pixels under *box*.

    ReportLab's PNG soft-mask path corrupts the colour data, so images are
    flattened here and drawn as plain opaque bitmaps.  The paper texture is
    sampled with the same transform as draw_paper(), so the result is
    pixel-identical to the background and has no visible rectangle.
    """
    from PIL import Image

    paper = _paper_image()
    iw, ih = paper.size
    x0, y0, x1, y1 = box
    px, py, pw, ph = paper_placement()
    ptop = PAGE_H - (py + ph)

    scale = dpi / 72.0
    W, H = max(1, int(round((x1 - x0) * scale))), max(1, int(round((y1 - y0) * scale)))
    sx0 = (x0 - px) / pw * iw
    sx1 = (x1 - px) / pw * iw
    sy0 = (y0 - ptop) / ph * ih
    sy1 = (y1 - ptop) / ph * ih
    bg = paper.crop((int(round(sx0)), int(round(sy0)),
                     int(round(sx1)), int(round(sy1)))).resize((W, H),
                                                               Image.LANCZOS)

    im = Image.open(path).convert("RGBA")
    box_w, box_h = x1 - x0, y1 - y0
    if fit == "stretch":
        im = im.resize((W, H), Image.LANCZOS)
        bg.paste(im, (0, 0), im)
        return bg
    factor = min(box_w / im.width, box_h / im.height)
    w, h = im.width * factor, im.height * factor
    im = im.resize((max(1, int(round(w * scale))), max(1, int(round(h * scale)))),
                   Image.LANCZOS)
    ox = int(round(((box_w - w) / 2.0) * scale))
    oy = int(round(((box_h - h) / 2.0) * scale))
    bg.paste(im, (ox, oy), im)
    return bg


def flatten_on_color(path, w_pt, h_pt, color, dpi=300):
    from PIL import Image

    scale = dpi / 72.0
    W, H = max(1, int(round(w_pt * scale))), max(1, int(round(h_pt * scale)))
    bg = Image.new("RGB", (W, H),
                   (int(color.red * 255), int(color.green * 255),
                    int(color.blue * 255)))
    im = Image.open(path).convert("RGBA").resize((W, H), Image.LANCZOS)
    bg.paste(im, (0, 0), im)
    return bg


def _image_reader(img, quality=90):
    """Encode a flattened PIL image as JPEG; lossless Flate is 10x bigger."""
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality, optimize=True)
    buf.seek(0)
    return ImageReader(buf)


# --- Publisher artwork manifest -------------------------------------------
#
# The ordinary card image is deliberately simple: it is stretched into a
# fixed box.  A Publisher export is not simple: the original author can rotate
# or skew artwork, clip it to a polygon, re-use it in a second partial
# placement, and change alpha through ExtGState.  These helpers replay that
# layer in native PDF point coordinates, which ReportLab shares with the
# manifest (bottom-left origin).


def load_artwork_manifest(path: str) -> dict[str, Any]:
    """Read and validate the stable artwork-manifest/v1 envelope."""
    full_path = os.path.abspath(path)
    try:
        with open(full_path, encoding="utf-8") as fh:
            manifest = json.load(fh)
    except OSError as exc:
        raise ArtworkManifestError(f"не удалось открыть artwork manifest: {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ArtworkManifestError(f"некорректный JSON artwork manifest: {path}: {exc}") from exc
    if not isinstance(manifest, dict):
        raise ArtworkManifestError("artwork manifest должен быть JSON-объектом")
    if manifest.get("schema") != ARTWORK_MANIFEST_SCHEMA:
        raise ArtworkManifestError(
            "неподдерживаемая schema artwork manifest: "
            f"{manifest.get('schema')!r} (ожидается {ARTWORK_MANIFEST_SCHEMA!r})")
    coordinates = manifest.get("coordinate_system") or {}
    if coordinates.get("origin") != "bottom-left" or coordinates.get("unit") != "point":
        raise ArtworkManifestError(
            "artwork manifest должен использовать PDF points с началом внизу слева")
    if not isinstance(manifest.get("pages"), list):
        raise ArtworkManifestError("в artwork manifest отсутствует массив pages")
    return manifest


def _manifest_page_number(page: dict[str, Any]) -> int | None:
    try:
        return int(page.get("number"))
    except (TypeError, ValueError):
        return None


def artwork_page_for_card(manifest: dict[str, Any], card: dict[str, Any],
                          page_number: int | None = None) -> dict[str, Any]:
    """Select a source page by explicit page, weapon id, then card page.

    A card's ``id`` is preferred over an old or manually changed page number;
    ``--artwork-page`` remains an escape hatch for a card without a Companion
    id or a source page whose title could not be matched during extraction.
    """
    pages = [page for page in manifest.get("pages", []) if isinstance(page, dict)]
    if page_number is not None:
        matches = [page for page in pages
                   if _manifest_page_number(page) == int(page_number)]
        if len(matches) == 1:
            return matches[0]
        if not matches:
            raise ArtworkManifestError(
                f"в artwork manifest нет страницы {page_number}")
        raise ArtworkManifestError(
            f"artwork manifest содержит несколько записей страницы {page_number}")

    weapon_id = card.get("id")
    if weapon_id:
        matches = [page for page in pages if page.get("weapon_id") == weapon_id]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            # Reused titles are rare, but the card's page disambiguates them.
            card_page = card.get("page")
            by_number = [page for page in matches
                         if _manifest_page_number(page) == card_page]
            if len(by_number) == 1:
                return by_number[0]
            raise ArtworkManifestError(
                f"weapon_id {weapon_id!r} найден на нескольких страницах; "
                "укажите --artwork-page")

    try:
        card_page = int(card.get("page"))
    except (TypeError, ValueError):
        card_page = None
    if card_page is not None:
        matches = [page for page in pages if _manifest_page_number(page) == card_page]
        if len(matches) == 1:
            candidate = matches[0]
            candidate_id = candidate.get("weapon_id")
            # A stale fixture page must not silently borrow a different
            # weapon's art. Explicit --artwork-page remains available for a
            # deliberately cross-page placement or an unrecognised title.
            if weapon_id and candidate_id and candidate_id != weapon_id:
                raise ArtworkManifestError(
                    f"страница {card_page} manifest относится к {candidate_id!r}, "
                    f"а не к {weapon_id!r}; укажите --artwork-page только "
                    "если это намеренное размещение")
            return candidate

    detail = f"weapon_id {weapon_id!r}" if weapon_id else "без weapon_id"
    raise ArtworkManifestError(
        f"не найдена страница artwork manifest для карточки ({detail}); "
        "укажите --artwork-page")


def load_artwork_layer(manifest_path: str, card: dict[str, Any],
                       page_number: int | None = None,
                       asset_root: str | None = None) -> ArtworkLayer:
    """Load the source page and choose where its extracted assets live."""
    full_path = os.path.abspath(manifest_path)
    manifest = load_artwork_manifest(full_path)
    page = artwork_page_for_card(manifest, card, page_number)
    root = os.path.abspath(asset_root or os.path.dirname(full_path))
    return ArtworkLayer(manifest_path=full_path, asset_root=root, page=page)


def artwork_page_size(layer: ArtworkLayer) -> tuple[float, float]:
    """Use the source PDF page size when the manifest records one.

    Publisher's A4 export is 595.32 × 841.92 pt rather than ReportLab's
    nominal 595.2756 × 841.8898. The difference is tiny, but retaining it
    prevents the top-left representation of an otherwise exact affine matrix
    from drifting by 0.03 pt during a control re-render.
    """
    size = layer.page.get("size_points")
    if size is None:
        return PAGE_W, PAGE_H
    if not isinstance(size, (list, tuple)) or len(size) != 2:
        raise ArtworkManifestError(
            "size_points страницы artwork manifest должен содержать width и height")
    try:
        width, height = float(size[0]), float(size[1])
    except (TypeError, ValueError) as exc:
        raise ArtworkManifestError(
            "size_points страницы artwork manifest содержит нечисловое значение") from exc
    if width <= 0 or height <= 0:
        raise ArtworkManifestError(
            "size_points страницы artwork manifest должен быть положительным")
    return width, height


def artwork_placements(page: dict[str, Any]) -> list[dict[str, Any]]:
    """Exported image placements in their original painter's order.

    The manifest also describes background textures and tiny rasterized text
    snippets.  Those entries intentionally have no exported ``asset`` and are
    rendered by the normal PDF builder instead.  Every exported placement is
    retained, including repeated uses of the same PNG.
    """
    found: list[tuple[int, int, dict[str, Any]]] = []
    for index, placement in enumerate(page.get("placements") or []):
        if not isinstance(placement, dict) or not placement.get("asset"):
            continue
        try:
            draw_order = int(placement.get("draw_order", index))
        except (TypeError, ValueError):
            draw_order = index
        found.append((draw_order, index, placement))
    return [placement for _order, _index, placement in sorted(found)]


def _manifest_asset_path(layer: ArtworkLayer,
                         placement: dict[str, Any]) -> str:
    asset = placement.get("asset")
    if not isinstance(asset, str) or not asset:
        raise ArtworkManifestError("placement не содержит имени экспортированного asset")
    candidates = [asset] if os.path.isabs(asset) else [
        os.path.join(layer.asset_root, asset),
        os.path.join(os.path.dirname(layer.manifest_path), asset),
    ]
    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate
    raise ArtworkManifestError(
        f"не найден artwork asset {asset!r} для страницы {layer.page.get('number')} "
        f"(искали в {layer.asset_root})")


def _manifest_point(value: Any, label: str) -> tuple[float, float]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ArtworkManifestError(f"некорректная точка {label} в clip path")
    try:
        return float(value[0]), float(value[1])
    except (TypeError, ValueError) as exc:
        raise ArtworkManifestError(f"некорректная точка {label} в clip path") from exc


def _clip_manifest_path(c, clipping: dict[str, Any]) -> None:
    """Intersect the ReportLab clipping region with one manifest clip path."""
    commands = clipping.get("commands")
    if not isinstance(commands, list):
        raise ArtworkManifestError("clip path не содержит commands")
    path = c.beginPath()
    have_geometry = False
    for command in commands:
        if not isinstance(command, dict):
            raise ArtworkManifestError("некорректная команда clip path")
        operator = command.get("op")
        if operator == "move_to":
            x, y = _manifest_point(command.get("points"), "move_to")
            path.moveTo(x, y)
            have_geometry = True
        elif operator == "line_to":
            x, y = _manifest_point(command.get("points"), "line_to")
            path.lineTo(x, y)
            have_geometry = True
        elif operator == "curve_to":
            points = command.get("points")
            if not isinstance(points, (list, tuple)) or len(points) != 3:
                raise ArtworkManifestError("curve_to должен содержать три точки")
            p1 = _manifest_point(points[0], "curve_to[0]")
            p2 = _manifest_point(points[1], "curve_to[1]")
            p3 = _manifest_point(points[2], "curve_to[2]")
            path.curveTo(*p1, *p2, *p3)
            have_geometry = True
        elif operator == "close_path":
            path.close()
        else:
            raise ArtworkManifestError(f"неподдерживаемая команда clip path: {operator!r}")
    if not have_geometry:
        raise ArtworkManifestError("пустой clip path нельзя применить")
    fill_mode = (canvas.FILL_EVEN_ODD if clipping.get("rule") == "even-odd"
                 else canvas.FILL_NON_ZERO)
    c.clipPath(path, stroke=0, fill=0, fillMode=fill_mode)


def _manifest_matrix(placement: dict[str, Any]) -> tuple[float, float, float,
                                                            float, float, float]:
    matrix = placement.get("matrix_pdf")
    if not isinstance(matrix, (list, tuple)) or len(matrix) != 6:
        raise ArtworkManifestError("placement не содержит matrix_pdf из шести чисел")
    try:
        return tuple(float(value) for value in matrix)  # type: ignore[return-value]
    except (TypeError, ValueError) as exc:
        raise ArtworkManifestError("matrix_pdf содержит нечисловое значение") from exc


def _apply_manifest_graphics_state(c, placement: dict[str, Any]) -> None:
    """Apply ExtGState values that ReportLab can faithfully recreate."""
    state = placement.get("graphics_state") or {}
    if not isinstance(state, dict):
        raise ArtworkManifestError("graphics_state placement должен быть объектом")
    for key, setter in (("fill_alpha", c.setFillAlpha),
                        ("stroke_alpha", c.setStrokeAlpha)):
        value = state.get(key)
        if value is None:
            continue
        try:
            alpha = float(value)
        except (TypeError, ValueError) as exc:
            raise ArtworkManifestError(f"{key} должен быть числом") from exc
        if not 0.0 <= alpha <= 1.0:
            raise ArtworkManifestError(f"{key} вне диапазона 0…1")
        setter(alpha)
    blend_mode = state.get("blend_mode")
    if blend_mode:
        try:
            c.setBlendMode(str(blend_mode))
        except Exception as exc:  # ReportLab validates its supported PDF names.
            raise ArtworkManifestError(
                f"неподдерживаемый blend mode {blend_mode!r}") from exc
    if state.get("soft_mask"):
        # Image /SMask is already retained in the exported RGBA asset. A
        # graphics-state soft mask is a separate transparency group and has no
        # pixel payload in v1, so silently pretending to reproduce it is worse
        # than making the limitation visible to the caller.
        raise ArtworkManifestError(
            "graphics-state SMask требует отдельного mask asset; "
            "schema artwork-manifest/v1 хранит только его xref")
    if state.get("transfer_function"):
        raise ArtworkManifestError(
            "transfer function не может быть воспроизведена из schema "
            "artwork-manifest/v1 без исходного PDF")


def draw_artwork_layer(c, layer: ArtworkLayer) -> int:
    """Replay exported artwork on *c* with matrix, clip, alpha and order.

    ``canvas.transform`` and ``drawImage(..., 0, 0, 1, 1)`` are intentional:
    ReportLab writes the same PDF affine concatenation as the Publisher CTM.
    The paths are installed before that transform because manifest points are
    already expressed in page coordinates.
    """
    placements = artwork_placements(layer.page)
    if not placements:
        raise ArtworkManifestError(
            f"на странице {layer.page.get('number')} нет экспортированных artwork placements")
    for placement in placements:
        asset = _manifest_asset_path(layer, placement)
        c.saveState()
        try:
            for clipping in placement.get("clip_paths") or []:
                if not isinstance(clipping, dict):
                    raise ArtworkManifestError("некорректная запись clip_paths")
                _clip_manifest_path(c, clipping)
            _apply_manifest_graphics_state(c, placement)
            c.transform(*_manifest_matrix(placement))
            c.drawImage(ImageReader(asset), 0, 0, 1, 1, mask="auto")
        finally:
            c.restoreState()
    return len(placements)


def place_image(c, path, box, fit="contain") -> None:
    """Draw *path* contained in *box* (top-down coords), alpha over paper."""
    if not path:
        return
    if not os.path.isabs(path):
        path = os.path.join(ROOT, path)
    if not os.path.exists(path):
        print(f"warning: image not found: {path}", file=sys.stderr)
        return
    x0, y0, x1, y1 = box
    img = flatten_on_paper(path, box, fit=fit)
    c.drawImage(_image_reader(img), x0, y_from_top(y1), x1 - x0, y1 - y0,
                mask=None)


def draw_image(c, card, artwork: ArtworkLayer | None = None) -> None:
    """Draw either the ordinary card image or an exact Publisher artwork layer."""
    if artwork is not None:
        draw_artwork_layer(c, artwork)
        return
    place_image(c, card.get("image") or "", IMAGE_BOX, fit="stretch")


def draw_title(c, card) -> None:
    title = card["title"].upper()
    size = TITLE_SIZE
    max_w = 520
    while size > 12 and sw(title, "Carlito-Bold", size) > max_w:
        size -= 0.5
    draw_center_line(c, TITLE_TOP, title, "Carlito-Bold", size)

    c.setFillColor(BLACK)
    c.rect(
        PAGE_W_WORK_CENTER - RULE_W / 2.0, y_from_top(RULE_TOP),
        RULE_W, -RULE_H, stroke=0, fill=1,
    )

    subtitle = "Вес: {weight}, Цена: {cost}, Редкость: {rarity}".format(**card)
    draw_center_line(c, SUBTITLE_TOP, subtitle, "Carlito", SUBTITLE_SIZE)


def draw_cell_text(c, x, y_top, w, h, text, font, size, leading=None,
                   color=BLACK, dy=0.0):
    lines = text.split("\n") if text else []
    if not lines:
        return
    leading = leading or size * 1.2
    block_h = size + (len(lines) - 1) * leading
    start = y_top + (h - block_h) / 2.0 + dy
    c.setFillColor(color)
    c.setFont(font, size)
    for i, line in enumerate(lines):
        baseline = y_from_top(start + ASCENT * size + i * leading)
        c.drawString(x + (w - sw(line, font, size)) / 2.0, baseline, line)


def draw_fitted_cell(c, x, y_top, w, h, text, max_lines=2,
                     start=STATS_BODY_SIZE, min_size=6.5, dy=1.0):
    """Centre a stats value, shrinking and wrapping if it is too long."""
    if not text:
        return
    size = start
    avail = w - 6
    lines = wrap_text(text, "Carlito", size, avail)
    while (len(lines) > max_lines
           or any(sw(line, "Carlito", size) > avail for line in lines)) \
            and size > min_size:
        size -= 0.5
        lines = wrap_text(text, "Carlito", size, avail)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        last = lines[-1]
        while last and sw(last + "…", "Carlito", size) > avail:
            last = last.rsplit(" ", 1)[0] if " " in last else last[:-1]
        lines[-1] = last.rstrip(" .,;:") + "…"
    leading = size * 1.25
    block_h = size + (len(lines) - 1) * leading
    start_y = y_top + (h - block_h) / 2.0 + dy
    c.setFillColor(BLACK)
    c.setFont("Carlito", size)
    for i, line in enumerate(lines):
        c.drawString(x + (w - sw(line, "Carlito", size)) / 2.0,
                     y_from_top(start_y + ASCENT * size + i * leading), line)


def draw_stats(c, card) -> None:
    top = STATS_TOP
    headline = top + STATS_HEADER_H
    bottom = headline + STATS_BODY_H

    # fills
    c.setFillColor(BLACK)
    c.rect(MARGIN_L, y_from_top(top), CONTENT_W, -(bottom - top), 0, 1)
    c.setFillColor(BEIGE)
    c.rect(MARGIN_L, y_from_top(headline), CONTENT_W, -STATS_BODY_H, 0, 1)

    values = [
        card.get("ammo") or "-",
        card.get("damageType") or "-",
        None,  # damage is drawn with the icon
        str(card.get("fireRate", "-")),
        card.get("range") or "-",
        ", ".join(card.get("effects") or []) or "-",
        ", ".join(card.get("qualities") or []) or "-",
    ]

    # header labels
    for i, label in enumerate(HEADERS):
        x0, x1 = STATS_COLS[i], STATS_COLS[i + 1]
        size = STATS_HEADER_SIZE
        if i == 3:
            size = STATS_HEADER_TIGHT_SIZE
            lines = ["СКОРОСТЬ", "СТРЕЛЬБЫ"]
            leading = 15.48
            block_h = size + (len(lines) - 1) * leading
            start = top + (STATS_HEADER_H - block_h) / 2.0 + 1.5
            c.setFillColor(WHITE)
            c.setFont("Carlito-Bold", size)
            for j, line in enumerate(lines):
                c.drawString(
                    x0 + (x1 - x0 - sw(line, "Carlito-Bold", size)) / 2.0,
                    y_from_top(start + ASCENT * size + j * leading),
                    line,
                )
        else:
            draw_cell_text(
                c, x0, top, x1 - x0, STATS_HEADER_H, label,
                "Carlito-Bold", size, color=WHITE, dy=1.5,
            )

    # body labels
    for i, value in enumerate(values):
        x0, x1 = STATS_COLS[i], STATS_COLS[i + 1]
        if i == 2:
            continue
        draw_fitted_cell(c, x0, headline, x1 - x0, STATS_BODY_H, value)

    # damage + CD icon, as one centred group
    x0, x1 = STATS_COLS[2], STATS_COLS[3]
    damage = str(card.get("damage", "-"))
    dmg_w = sw(damage, "Carlito", STATS_BODY_SIZE)
    icon = 19.9
    gap = 1.4
    group_w = dmg_w + gap + icon
    gx = x0 + (x1 - x0 - group_w) / 2.0
    gy = headline + (STATS_BODY_H - icon) / 2.0
    c.setFillColor(BLACK)
    c.setFont("Carlito", STATS_BODY_SIZE)
    c.drawString(
        gx,
        y_from_top(headline + STATS_BODY_H / 2.0 + 0.25 * STATS_BODY_SIZE + 1.0),
        damage,
    )
    if os.path.exists(DAMAGE_ICON):
        badge = flatten_on_color(DAMAGE_ICON, icon, icon, BEIGE)
        c.drawImage(_image_reader(badge), gx + dmg_w + gap,
                    y_from_top(gy + icon), icon, icon, mask=None)

    # grid: verticals, then horizontals so they close the corners
    c.setStrokeColor(BLACK)
    c.setLineWidth(RULE_W_PT)
    for x in STATS_COLS[1:-1]:
        c.setStrokeColor(WHITE)
        c.line(x, y_from_top(top + 0.5), x, y_from_top(headline - 0.5))
        c.setStrokeColor(BLACK)
        c.line(x, y_from_top(headline + 0.5), x, y_from_top(bottom - 0.5))
    for y in (top, headline, bottom):
        c.setStrokeColor(BLACK)
        c.line(MARGIN_L, y_from_top(y), CONTENT_R, y_from_top(y))
    c.setStrokeColor(BLACK)
    c.line(MARGIN_L, y_from_top(top), MARGIN_L, y_from_top(bottom))
    c.line(CONTENT_R, y_from_top(top), CONTENT_R, y_from_top(bottom))


def mods_block(card):
    """(rows, table top, column count) or None when there are no mods."""
    if not any((cat.get("items") or []) for cat in card.get("mods") or []):
        return None
    rows, total, ncols = mods_layout(card)
    avail = MODS_BOTTOM - MODS_TOP
    if total > avail:
        print("warning: mods table overflows the page", file=sys.stderr)
        scale = avail / total
        for row in rows:
            row["h"] *= scale
    top = MODS_BOTTOM - sum(r["h"] for r in rows)
    return rows, top, ncols


def description_bottom_from(block) -> float:
    """Last y the description may reach: just above the mods heading."""
    if block is None:
        return MODS_HEADING_TOP - 10
    return block[1] - MODS_HEADING_GAP - 10


def description_bottom(card) -> float:
    return description_bottom_from(mods_block(card))


def description_layout(card, max_bottom=None):
    """Return complete fitted description lines, or fail before losing text.

    Weapon rules prose is source content, so an ellipsis is not an acceptable
    overflow treatment.  Callers may provide a different bottom edge for
    layouts that place a custom table below the description.
    """
    text = (card.get("description") or "").strip()
    if not text:
        return [], DESC_SIZE, DESC_LEADING
    width = DESC_RIGHT - DESC_LEFT
    size, leading = DESC_SIZE, DESC_LEADING
    if max_bottom is None:
        max_bottom = description_bottom(card)
    lines = wrap_text(text, "Carlito", size, width)
    # The description may use all the room above the mods block; reduce type
    # only when that room cannot contain the complete source copy.
    while ((len(lines) * leading + DESC_TOP > max_bottom
            or any(sw(line, "Carlito", size) > width for line in lines))
           and size > 10):
        size -= 0.5
        leading -= 0.6
        lines = wrap_text(text, "Carlito", size, width)
    max_lines = max(1, int((max_bottom - DESC_TOP) // leading))
    if (len(lines) > max_lines
            or any(sw(line, "Carlito", size) > width for line in lines)):
        raise ValueError(
            f"description of {card.get('id')} does not fit "
            f"({len(lines)} lines, max {max_lines})")
    return lines, size, leading


def description_render_bottom(layout) -> float:
    """Conservative lower edge of a ``description_layout`` block."""
    lines, _size, leading = layout
    return DESC_TOP + len(lines) * leading


def no_mods_description_layout(card):
    """Lay out no-mods prose and a notice without sacrificing its ending."""
    layout = description_layout(
        card, max_bottom=NO_MODS_HEADING_MAX_TOP - NO_MODS_DESC_GAP)
    heading_top = max(MODS_HEADING_TOP,
                      description_render_bottom(layout) + NO_MODS_DESC_GAP)
    return layout, heading_top


def draw_description(c, card, max_bottom=None, layout=None):
    if layout is None:
        layout = description_layout(card, max_bottom=max_bottom)
    lines, size, leading = layout
    if not lines:
        return layout
    draw_justified(c, DESC_LEFT, DESC_RIGHT - DESC_LEFT, DESC_TOP, lines,
                   "Carlito", size, leading)
    return layout


def mods_edges(ncols: int) -> list[float]:
    """Label column + ncols equal mod columns up to the right margin."""
    step = (MODS_RIGHT - MODS_LABEL_RIGHT) / ncols
    return [MODS_LEFT, MODS_LABEL_RIGHT] + [
        MODS_LABEL_RIGHT + step * i for i in range(1, ncols + 1)]


def mods_layout(card) -> tuple[list[dict], float, int]:
    """Return flat rows with wrapped cells; each category starts a block.

    The column count follows the widest category: one mod fills the whole
    width, three mods give three columns, more than six wrap into rows of six.
    """
    mods = card.get("mods") or []
    widest = max((len(cat.get("items") or []) for cat in mods), default=0)
    ncols = max(1, min(MODS_MAX_COLS, widest))
    edges = mods_edges(ncols)
    rows = []
    for cat in mods:
        items = cat.get("items") or []
        chunks = [items[i:i + ncols] for i in range(0, len(items), ncols)] or [[]]
        for ci, chunk in enumerate(chunks):
            cells = []
            sizes = []
            max_lines = 1
            for i in range(ncols):
                text = chunk[i] if i < len(chunk) else ""
                col_w = edges[i + 2] - edges[i + 1] - MODS_H_PAD
                size = MODS_FONT_SIZE
                lines = wrap_text(text, "Carlito", size, col_w)
                # a single long word ("гиростабилизирующая") can be wider
                # than the cell: shrink it, like the stats cells
                while (any(sw(line, "Carlito", size) > col_w for line in lines)
                       and size > 6.5):
                    size -= 0.25
                    lines = wrap_text(text, "Carlito", size, col_w)
                if any(sw(line, "Carlito", size) > col_w for line in lines):
                    print(f"warning: mod name too wide even at 6.5 pt: {text!r}",
                          file=sys.stderr)
                cells.append(lines)
                sizes.append(size)
                max_lines = max(max_lines, len(lines))
            h = max(MODS_MIN_ROW, max_lines * MODS_ROW_SLOPE + MODS_ROW_BASE)
            rows.append({
                "cells": cells,
                "sizes": sizes,
                "h": h,
                "cat_start": ci == 0,
                "cat_end": ci == len(chunks) - 1,
            })
    return rows, sum(r["h"] for r in rows), ncols


def draw_mods(c, card, block=None, no_mods_heading_top=None) -> None:
    mods = card.get("mods") or []

    if block is None:
        block = mods_block(card)
    if block is None:
        draw_center_line(c, no_mods_heading_top or MODS_HEADING_TOP,
                         "НЕТ ПОДДЕРЖИВАЕМЫХ МОДИФИКАЦИЙ",
                         "Carlito-Bold", MODS_HEADING_SIZE)
        return

    rows, top, ncols = block
    edges = mods_edges(ncols)
    bottom = MODS_BOTTOM
    # the heading follows the table, so short tables do not leave a hole
    draw_center_line(c, top - MODS_HEADING_GAP, MODS_HEADING, "Carlito-Bold",
                     MODS_HEADING_SIZE)

    # category fills
    y = top
    color = BEIGE
    ri = 0
    cat_heights = []
    for cat in mods:
        n = max(1, math.ceil(len(cat.get("items") or []) / ncols))
        h = sum(r["h"] for r in rows[ri:ri + n])
        cat_heights.append((n, h))
        c.setFillColor(color)
        c.rect(edges[0], y_from_top(y), edges[-1] - edges[0], -h, 0, 1)
        color = ORANGE if color == BEIGE else BEIGE
        y += h
        ri += n

    # grid
    c.setStrokeColor(BLACK)
    c.setLineWidth(RULE_W_PT)
    y = top
    for row in rows:
        y += row["h"]
        c.line(edges[0], y_from_top(y), edges[-1], y_from_top(y))
    c.line(edges[0], y_from_top(top), edges[-1], y_from_top(top))
    c.line(edges[0], y_from_top(bottom), edges[-1], y_from_top(bottom))
    for x in edges:
        c.line(x, y_from_top(top), x, y_from_top(bottom))

    # black label cells + white separators between them
    y = top
    ri = 0
    for cat, (n, h) in zip(mods, cat_heights):
        c.setFillColor(BLACK)
        c.rect(edges[0], y_from_top(y), MODS_LABEL_W, -h, 0, 1)
        if y > top:
            c.setStrokeColor(WHITE)
            c.setLineWidth(RULE_W_PT)
            c.line(edges[0] + 0.5, y_from_top(y - 0.3),
                   edges[1] - 0.5, y_from_top(y - 0.3))
        y += h
        ri += n

    # labels + cell text
    y = top
    ri = 0
    for cat, (n, h) in zip(mods, cat_heights):
        label = (cat.get("slot") or "").upper()
        size = MODS_LABEL_SIZE
        while size > 7 and sw(label, "Carlito-Bold", size) > MODS_LABEL_W - 6:
            size -= 0.25
        draw_cell_text(c, edges[0], y, MODS_LABEL_W, h, label,
                       "Carlito-Bold", size, color=WHITE)
        ry = y
        for k in range(n):
            row = rows[ri + k]
            for ci, lines in enumerate(row["cells"]):
                if not lines:
                    continue
                x0, x1 = edges[ci + 1], edges[ci + 2]
                size = row["sizes"][ci]
                leading = size * MODS_LEADING / MODS_FONT_SIZE
                block_h = size + (len(lines) - 1) * leading
                start = ry + (row["h"] - block_h) / 2.0 + 0.6
                c.setFillColor(BLACK)
                c.setFont("Carlito", size)
                for li, line in enumerate(lines):
                    c.drawString(
                        x0 + (x1 - x0 - sw(line, "Carlito", size)) / 2.0,
                        y_from_top(start + ASCENT * size + li * leading),
                        line,
                    )
            ry += row["h"]
        y += h
        ri += n


def draw_page_number(c, page: int, total_pages: int | None = None) -> None:
    text = str(page)
    if page % 2 == 0:
        draw_top(c, MARGIN_L + 2.57, PAGE_NUMBER_TOP, text, "Carlito",
                 PAGE_NUMBER_SIZE)
    else:
        draw_top(c, CONTENT_R - 2.57, PAGE_NUMBER_TOP, text, "Carlito",
                 PAGE_NUMBER_SIZE, align="right")


def render_card(card, out_path: str,
                artwork: ArtworkLayer | None = None) -> None:
    c = canvas.Canvas(out_path, pagesize=(artwork_page_size(artwork)
                                          if artwork is not None
                                          else (PAGE_W, PAGE_H)))
    c.setTitle(f"{card.get('title', '')} — справочник оружия")
    c.setAuthor("fallout-2d20.ru")
    draw_paper(c)
    # The Publisher artwork layer, like the ordinary flattened image, stays
    # behind titles, stats and tables.
    draw_image(c, card, artwork)
    draw_title(c, card)
    draw_stats(c, card)
    block = mods_block(card)
    if block is None:
        layout, no_mods_heading_top = no_mods_description_layout(card)
        draw_description(c, card, layout=layout)
        draw_mods(c, card, block, no_mods_heading_top=no_mods_heading_top)
    else:
        draw_description(c, card, max_bottom=description_bottom_from(block))
        draw_mods(c, card, block)
    draw_page_number(c, int(card.get("page") or 0))
    c.showPage()
    c.save()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("card", help="card JSON")
    ap.add_argument("--out", required=True, help="output PDF")
    ap.add_argument("--artwork-manifest", metavar="PATH",
                    help="artwork-manifest.json из extract_pdf_images.py")
    ap.add_argument("--artwork-root", metavar="DIR",
                    help="каталог PNG из manifest (по умолчанию рядом с ним)")
    ap.add_argument("--artwork-page", type=int, metavar="N",
                    help="явно выбрать страницу manifest вместо card id/page")
    args = ap.parse_args(argv)

    register_fonts()
    with open(args.card, encoding="utf-8") as fh:
        card = json.load(fh)
    artwork = None
    if args.artwork_manifest:
        try:
            artwork = load_artwork_layer(args.artwork_manifest, card,
                                         args.artwork_page, args.artwork_root)
        except ArtworkManifestError as exc:
            ap.error(str(exc))
    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
    render_card(card, args.out, artwork=artwork)
    if artwork is not None:
        print("artwork manifest: "
              f"страница {artwork.page.get('number')}, "
              f"размещений: {len(artwork_placements(artwork.page))}")
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
