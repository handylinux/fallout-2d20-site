#!/usr/bin/env python3
"""Извлечь иллюстрации и их PDF-геометрию из книги Publisher.

    python3 tools/extract_pdf_images.py book.pdf --out art/

Что делает:
  * проходит по страницам и достаёт встроенные изображения;
  * выкидывает из набора ассетов мелочь (иконки), повторяющуюся бумажную
    текстуру и дубликаты, но сохраняет *все* появления изображений в
    манифесте;
  * сохраняет PNG, включая alpha-канал /SoftMask, если он есть;
  * имена вида p018-02.png — страница и порядковый номер на странице;
  * рядом кладёт index.html — контактный лист с номерами страниц;
  * report.csv — обратносуместимый короткий список извлечённых ассетов;
  * artwork-manifest.json — координаты, affine-матрицы, clipping paths,
    SoftMask и graphics state каждого появления картинки на странице.

Манифест использует исходную PDF-систему координат: points, начало в левом
нижнем углу страницы. ``matrix_pdf`` — PDF CTM ``[a, b, c, d, e, f]``:
``(x, y) -> (a*x + c*y + e, b*x + d*y + f)``. Он нужен генератору, чтобы
сохранить заданные в Publisher размер, поворот, crop и прозрачность
иллюстраций, не расставляя их вручную.

Зависимости: pymupdf, pillow (pip install pymupdf pillow).
"""

from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import html
import json
import os
import re
import sys
from typing import Any, Iterator

try:
    import pymupdf
except ImportError:  # pragma: no cover - dependency hint
    print("нужен pymupdf: python3 -m pip install pymupdf pillow", file=sys.stderr)
    raise SystemExit(2)


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEAPONS_JSON = os.path.join(
    ROOT, "data", "companion", "i18n", "ru-RU", "data", "equipment", "weapons",
    "weapons.json")
TITLE_ALIASES_JSON = os.path.join(ROOT, "data", "weapons",
                                  "publisher-artwork-title-aliases.ru.json")


def normalize_name(text: str) -> str:
    """«БОЕВОЙ КАРАБИН» и «Боевой карабин» -> «боевой карабин»."""
    text = (text or "").casefold().replace("ё", "е")
    text = re.sub(r"[^0-9a-zа-я]+", " ", text)
    return " ".join(text.split())


def compact_name(text: str) -> str:
    """A title key resilient to Publisher's intra-word line-break spaces.

    The Publisher PDF sometimes extracts ``ДРОБОВИ К`` or ``25 - М М`` as
    separate text spans.  Collapsing *all* normalized separators lets those
    headings match their Companion names without guessing from page numbers.
    """
    return re.sub(r"\s+", "", normalize_name(text))


def match_weapon_title(title: str, weapons: dict[str, str]) -> str:
    """Return one unambiguous weapon ID for a Publisher page heading.

    Exact normalized spelling remains preferred.  The compact fallback is
    deliberately accepted only when it identifies one ID, so it cannot turn a
    broken heading into a silent arbitrary artwork assignment.
    """
    normalized = normalize_name(title)
    direct = weapons.get(normalized)
    if direct:
        return direct
    compact = compact_name(title)
    candidates = {weapon_id for name, weapon_id in weapons.items()
                  if compact_name(name) == compact}
    return next(iter(candidates)) if len(candidates) == 1 else ""


def load_title_aliases(path: str | None) -> dict[str, str]:
    """Read explicitly audited page-title aliases, if a file was supplied."""
    if not path or not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    aliases = data.get("aliases", []) if isinstance(data, dict) else []
    if not isinstance(aliases, list):
        raise ValueError("title aliases должен содержать массив aliases")
    result = {}
    for item in aliases:
        if not isinstance(item, dict):
            raise ValueError("некорректная запись title alias")
        title, weapon_id = item.get("title"), item.get("weapon_id")
        if not isinstance(title, str) or not isinstance(weapon_id, str) or not weapon_id:
            raise ValueError("title alias должен содержать title и weapon_id")
        key = normalize_name(title)
        previous = result.get(key)
        if previous and previous != weapon_id:
            raise ValueError(f"неоднозначный title alias: {title!r}")
        result[key] = weapon_id
    return result


def slug_of(weapon_id: str) -> str:
    """weapon_10mm_pistol -> 10mm-pistol (как в tools/weapons2cards.py)."""
    name = weapon_id[len("weapon_"):] if weapon_id.startswith("weapon_") \
        else weapon_id
    return name.replace("_", "-")


def load_weapons(path: str | None) -> dict[str, str]:
    if not path or not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    return {normalize_name(item.get("name") or ""): item["id"]
            for item in data if item.get("name")}


MANIFEST_SCHEMA = "fallout-2d20.artwork-manifest/v1"
IDENTITY_MATRIX = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
_PDF_WS = b"\x00\t\n\f\r "
_PDF_DELIMITERS = b"()<>[]{}/%"
_PDF_NUMBER = re.compile(r"^[+-]?(?:\d+\.\d*|\.\d+|\d+)(?:[Ee][+-]?\d+)?$")
_PATH_END_OPERATORS = {"n", "S", "s", "f", "F", "f*", "B", "B*", "b", "b*"}


def pdf_matrix_multiply(left: tuple[float, float, float, float, float, float],
                        right: tuple[float, float, float, float, float, float]
                        ) -> tuple[float, float, float, float, float, float]:
    """Return the PDF concatenation ``left * right`` of two affine CTMs."""
    a1, b1, c1, d1, e1, f1 = left
    a2, b2, c2, d2, e2, f2 = right
    return (
        a1 * a2 + c1 * b2,
        b1 * a2 + d1 * b2,
        a1 * c2 + c1 * d2,
        b1 * c2 + d1 * d2,
        a1 * e2 + c1 * f2 + e1,
        b1 * e2 + d1 * f2 + f1,
    )


def pdf_matrix_point(matrix: tuple[float, float, float, float, float, float],
                     x: float, y: float) -> list[float]:
    """Transform a point from image/path space into PDF page coordinates."""
    a, b, c, d, e, f = matrix
    return [a * x + c * y + e, b * x + d * y + f]


def _round_number(value: float, digits: int = 6) -> float:
    """Stable manifest numbers without meaningless PDF floating-point noise."""
    rounded = round(float(value), digits)
    return 0.0 if rounded == -0.0 else rounded


def _round_values(value: Any) -> Any:
    if isinstance(value, float):
        return _round_number(value)
    if isinstance(value, tuple):
        return [_round_values(item) for item in value]
    if isinstance(value, list):
        return [_round_values(item) for item in value]
    if isinstance(value, dict):
        return {key: _round_values(item) for key, item in value.items()}
    return value


def _skip_pdf_literal(data: bytes, pos: int) -> int:
    """Skip a PDF literal string, including escaped and nested parentheses."""
    depth = 1
    pos += 1
    while pos < len(data) and depth:
        char = data[pos]
        if char == ord("\\"):
            pos += 2
            continue
        if char == ord("("):
            depth += 1
        elif char == ord(")"):
            depth -= 1
        pos += 1
    return pos


def _skip_pdf_hex(data: bytes, pos: int) -> int:
    """Skip a hexadecimal string (``<...>``; dictionaries are handled apart)."""
    end = data.find(b">", pos + 1)
    return len(data) if end < 0 else end + 1


def _skip_pdf_array(data: bytes, pos: int) -> int:
    """Skip an array while respecting strings, nested arrays and dictionaries."""
    depth = 1
    pos += 1
    while pos < len(data) and depth:
        if data[pos] == ord("("):
            pos = _skip_pdf_literal(data, pos)
        elif data.startswith(b"<<", pos):
            pos = _skip_pdf_dictionary(data, pos)
        elif data[pos] == ord("["):
            depth += 1
            pos += 1
        elif data[pos] == ord("]"):
            depth -= 1
            pos += 1
        elif data[pos] == ord("<"):
            pos = _skip_pdf_hex(data, pos)
        else:
            pos += 1
    return pos


def _skip_pdf_dictionary(data: bytes, pos: int) -> int:
    """Skip a ``<< ... >>`` dictionary in a page content stream."""
    depth = 1
    pos += 2
    while pos < len(data) and depth:
        if data[pos] == ord("("):
            pos = _skip_pdf_literal(data, pos)
        elif data.startswith(b"<<", pos):
            depth += 1
            pos += 2
        elif data.startswith(b">>", pos):
            depth -= 1
            pos += 2
        elif data[pos] == ord("["):
            pos = _skip_pdf_array(data, pos)
        elif data[pos] == ord("<"):
            pos = _skip_pdf_hex(data, pos)
        else:
            pos += 1
    return pos


def pdf_content_tokens(data: bytes) -> Iterator[str | None]:
    """Yield top-level PDF content tokens without interpreting text payloads.

    A full PDF parser is unnecessary here: Publisher writes image placements as
    regular ``q … cm /Image Do Q`` blocks.  This small tokenizer deliberately
    treats strings, arrays and dictionaries as opaque operands, so text content
    cannot be mistaken for drawing operators.
    """
    pos = 0
    size = len(data)
    while pos < size:
        while pos < size and data[pos] in _PDF_WS:
            pos += 1
        if pos >= size:
            break
        if data[pos] == ord("%"):
            while pos < size and data[pos] not in b"\r\n":
                pos += 1
            continue
        if data[pos] == ord("("):
            pos = _skip_pdf_literal(data, pos)
            yield None
            continue
        if data.startswith(b"<<", pos):
            pos = _skip_pdf_dictionary(data, pos)
            yield None
            continue
        if data[pos] == ord("["):
            pos = _skip_pdf_array(data, pos)
            yield None
            continue
        if data[pos] == ord("<"):
            pos = _skip_pdf_hex(data, pos)
            yield None
            continue
        start = pos
        if data[pos] == ord("/"):
            pos += 1
        while pos < size and data[pos] not in _PDF_WS + _PDF_DELIMITERS:
            pos += 1
        # A slash is a delimiter, so advance through a complete PDF name.
        if data[start] == ord("/") and pos == start + 1:
            while pos < size and data[pos] not in _PDF_WS + _PDF_DELIMITERS:
                pos += 1
        token = data[start:pos].decode("latin1", "replace")
        if not token:
            pos += 1
            continue
        # Inline images are not resources that can be reliably re-used. Skip
        # their binary payload instead of letting its bytes corrupt the token
        # stream. Publisher pages under consideration use XObject images.
        if token == "BI":
            yield token
            match = re.search(rb"(?:^|\s)ID\s", data[pos:])
            if match:
                image_start = pos + match.end()
                end = re.search(rb"\sEI(?:\s|$)", data[image_start:])
                pos = image_start + end.end() if end else size
            continue
        yield token


def _as_number(token: str | None) -> float | None:
    if token is None or not _PDF_NUMBER.fullmatch(token):
        return None
    return float(token)


def _last_numbers(values: list[str | None], count: int) -> list[float] | None:
    if len(values) < count:
        return None
    numbers = [_as_number(value) for value in values[-count:]]
    return None if any(value is None for value in numbers) else numbers  # type: ignore[return-value]


def _last_name(values: list[str | None]) -> str | None:
    for value in reversed(values):
        if isinstance(value, str) and value.startswith("/"):
            return value[1:]
    return None


def _path_point(matrix: tuple[float, float, float, float, float, float],
                x: float, y: float) -> list[float]:
    return [_round_number(value) for value in pdf_matrix_point(matrix, x, y)]


def _append_path_command(path: list[dict], operator: str, values: list[float],
                         matrix: tuple[float, float, float, float, float, float]) -> None:
    if operator == "m":
        path.append({"op": "move_to", "points": _path_point(matrix, values[0], values[1])})
    elif operator == "l":
        path.append({"op": "line_to", "points": _path_point(matrix, values[0], values[1])})
    elif operator == "c":
        path.append({
            "op": "curve_to",
            "points": [
                _path_point(matrix, values[0], values[1]),
                _path_point(matrix, values[2], values[3]),
                _path_point(matrix, values[4], values[5]),
            ],
        })
    elif operator == "re":
        x, y, width, height = values
        path.extend([
            {"op": "move_to", "points": _path_point(matrix, x, y)},
            {"op": "line_to", "points": _path_point(matrix, x + width, y)},
            {"op": "line_to", "points": _path_point(matrix, x + width, y + height)},
            {"op": "line_to", "points": _path_point(matrix, x, y + height)},
            {"op": "close_path"},
        ])


def _matrix_bbox(matrix: tuple[float, float, float, float, float, float]) -> list[float]:
    """Axis-aligned page-space bounds of the transformed unit image square."""
    corners = [pdf_matrix_point(matrix, x, y)
               for x, y in ((0.0, 0.0), (1.0, 0.0), (0.0, 1.0), (1.0, 1.0))]
    return [_round_number(min(point[0] for point in corners)),
            _round_number(min(point[1] for point in corners)),
            _round_number(max(point[0] for point in corners)),
            _round_number(max(point[1] for point in corners))]


def _clip_path_bounds(path: dict) -> list[float] | None:
    """Return bounds for a recorded clipping path, if it has point commands."""
    points: list[list[float]] = []
    for command in path.get("commands", []):
        value = command.get("points")
        if not value:
            continue
        # move_to / line_to hold one point; curve_to holds three.
        if isinstance(value[0], (int, float)):
            points.append(value)
        else:
            points.extend(value)
    if not points:
        return None
    return [min(point[0] for point in points), min(point[1] for point in points),
            max(point[0] for point in points), max(point[1] for point in points)]


def _is_page_clip(path: dict, width: float, height: float,
                  tolerance: float = 0.75) -> bool:
    """Whether a clipping path is merely Publisher's full-page safety clip."""
    bounds = _clip_path_bounds(path)
    if bounds is None:
        return False
    return (bounds[0] <= tolerance and bounds[1] <= tolerance
            and bounds[2] >= width - tolerance and bounds[3] >= height - tolerance)


def _default_graphics_state() -> dict[str, Any]:
    return {
        "resource": None,
        "fill_alpha": 1.0,
        "stroke_alpha": 1.0,
        "blend_mode": "Normal",
        "soft_mask": None,
        "transfer_function": None,
    }


def _copy_state(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "ctm": tuple(state["ctm"]),
        "clip_paths": copy.deepcopy(state["clip_paths"]),
        "graphics_state": dict(state["graphics_state"]),
    }


def parse_image_placements(content: bytes, image_resources: dict[str, dict],
                           graphics_states: dict[str, dict] | None = None) -> list[dict]:
    """Parse Publisher-style image operations from one page content stream.

    Each result retains the raw PDF CTM and every active clipping path in
    PDF page coordinates.  The parser accepts ordinary PDF graphics operators;
    unknown operators simply terminate their operand list, which is enough for
    a mixed text/vector/page stream.
    """
    graphics_states = graphics_states or {}
    state: dict[str, Any] = {
        "ctm": IDENTITY_MATRIX,
        "clip_paths": [],
        "graphics_state": _default_graphics_state(),
    }
    stack: list[dict[str, Any]] = []
    operands: list[str | None] = []
    path: list[dict] = []
    pending_clip: str | None = None
    draw_order = 0
    placements: list[dict] = []

    def finish_path() -> None:
        nonlocal path, pending_clip
        if pending_clip and path:
            state["clip_paths"].append({
                "rule": pending_clip,
                "commands": copy.deepcopy(path),
            })
        path = []
        pending_clip = None

    for token in pdf_content_tokens(content):
        if token is None or token.startswith("/") or _as_number(token) is not None:
            operands.append(token)
            continue
        operator = token
        values = operands
        operands = []

        if operator == "q":
            stack.append(_copy_state(state))
            continue
        if operator == "Q":
            if stack:
                state = stack.pop()
            continue
        if operator == "cm":
            numbers = _last_numbers(values, 6)
            if numbers:
                state["ctm"] = pdf_matrix_multiply(state["ctm"], tuple(numbers))
            continue
        if operator == "gs":
            name = _last_name(values)
            if name:
                change = graphics_states.get(name, {})
                state["graphics_state"]["resource"] = name
                state["graphics_state"].update({
                    key: value for key, value in change.items() if value is not None
                })
            continue
        command_sizes = {"m": 2, "l": 2, "c": 6, "re": 4}
        if operator in command_sizes:
            numbers = _last_numbers(values, command_sizes[operator])
            if numbers:
                _append_path_command(path, operator, numbers, state["ctm"])
            continue
        if operator == "h":
            path.append({"op": "close_path"})
            continue
        if operator == "W":
            pending_clip = "nonzero"
            continue
        if operator == "W*":
            pending_clip = "even-odd"
            continue
        if operator == "Do":
            draw_order += 1
            name = _last_name(values)
            image = image_resources.get(name or "")
            if image:
                matrix = tuple(state["ctm"])
                placement = {
                    "resource": name,
                    "xref": image["xref"],
                    "draw_order": draw_order,
                    "matrix_pdf": [_round_number(value) for value in matrix],
                    "bbox_pdf": _matrix_bbox(matrix),
                    "clip_paths": copy.deepcopy(state["clip_paths"]),
                    "graphics_state": _round_values(state["graphics_state"]),
                    "image": {
                        key: image[key] for key in ("width", "height", "bpc", "colorspace",
                                                     "filter", "smask_xref", "decode_array") if key in image
                    },
                }
                placements.append(placement)
            continue
        if operator in _PATH_END_OPERATORS:
            finish_path()
    return placements


def image_resource_map(page, doc=None) -> dict[str, dict]:
    """Map PDF XObject resource names to image metadata for a page.

    ``/Decode`` is recorded as an audit flag. It may remap raw sample values,
    unlike Publisher's UI brightness/contrast controls, which are normally
    already baked into the embedded raster at export time.
    """
    resources: dict[str, dict] = {}
    for item in page.get_images(full=True):
        xref, smask, width, height, bpc = item[:5]
        colorspace = item[5]
        name = item[7]
        image_filter = item[8]
        image_object = doc.xref_object(xref, compressed=False) if doc else ""
        resources[name] = {
            "xref": xref,
            "width": width,
            "height": height,
            "bpc": bpc,
            "colorspace": colorspace,
            "filter": image_filter,
            "smask_xref": smask or None,
            "decode_array": "/Decode" in image_object,
        }
    return resources


def _dictionary_after(text: str, name: str) -> str:
    """Return the direct ``<<...>>`` dictionary after a resource name."""
    start = text.find(f"/{name}")
    if start < 0:
        return ""
    start = text.find("<<", start)
    if start < 0:
        return ""
    depth = 1
    pos = start + 2
    while pos < len(text) and depth:
        if text.startswith("<<", pos):
            depth += 1
            pos += 2
        elif text.startswith(">>", pos):
            depth -= 1
            pos += 2
        else:
            pos += 1
    return text[start + 2:pos - 2] if depth == 0 else ""


def _resource_object(doc, page) -> str:
    page_object = doc.xref_object(page.xref, compressed=False)
    indirect = re.search(r"/Resources\s+(\d+)\s+\d+\s+R", page_object)
    if indirect:
        return doc.xref_object(int(indirect.group(1)), compressed=False)
    return page_object


def page_box_pdf(doc, page, name: str) -> list[float] | None:
    """Read a MediaBox / CropBox in inherited raw PDF page coordinates."""
    xref = page.xref
    seen: set[int] = set()
    while xref and xref not in seen:
        seen.add(xref)
        text = doc.xref_object(xref, compressed=False)
        match = re.search(
            rf"/{name}\s*\[\s*([+-]?(?:\d+\.\d*|\.\d+|\d+))\s+"
            rf"([+-]?(?:\d+\.\d*|\.\d+|\d+))\s+"
            rf"([+-]?(?:\d+\.\d*|\.\d+|\d+))\s+"
            rf"([+-]?(?:\d+\.\d*|\.\d+|\d+))\s*\]", text)
        if match:
            return [_round_number(float(value)) for value in match.groups()]
        parent = re.search(r"/Parent\s+(\d+)\s+\d+\s+R", text)
        xref = int(parent.group(1)) if parent else 0
    return None


def _graphics_state_values(doc, xref: int) -> dict[str, Any]:
    text = doc.xref_object(xref, compressed=False)

    def number(key: str) -> float | None:
        match = re.search(rf"/{key}\s+([+-]?(?:\d+\.\d*|\.\d+|\d+))\b", text)
        return float(match.group(1)) if match else None

    blend = re.search(r"/BM\s*/([^\s/<>()\[\]]+)", text)
    soft_mask = re.search(r"/SMask\s+(\d+)\s+\d+\s+R", text)
    transfer = re.search(r"/(TR2?)\s+([^\s]+)", text)
    return {
        "fill_alpha": number("ca"),
        "stroke_alpha": number("CA"),
        "blend_mode": blend.group(1) if blend else None,
        "soft_mask": int(soft_mask.group(1)) if soft_mask else None,
        "transfer_function": transfer.group(2) if transfer else None,
    }


def graphics_state_map(doc, page) -> dict[str, dict]:
    """Resolve a page's ExtGState names into useful transparency metadata."""
    resources = _dictionary_after(_resource_object(doc, page), "ExtGState")
    out: dict[str, dict] = {}
    for name, xref in re.findall(r"/([^\s/]+)\s+(\d+)\s+\d+\s+R", resources):
        out[name] = _graphics_state_values(doc, int(xref))
    return out


def _sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _selected_page_ids(doc, pages: list[int] | None) -> list[int]:
    wanted = [page - 1 for page in pages] if pages else list(range(doc.page_count))
    return [page for page in wanted if 0 <= page < doc.page_count]


def artwork_manifest(pdf: str, rows: list[dict], pages: list[int] | None,
                     weapons: dict[str, str] | None = None,
                     name_from_page: bool = True) -> dict:
    """Build a per-*appearance* image geometry manifest for a source PDF.

    ``extract()`` deduplicates exported image assets for convenience. This
    function intentionally does not: the same XObject may be placed on several
    pages with different crop, rotation or scale, and every placement matters
    to a faithful rebuild.
    """
    doc = pymupdf.open(pdf)
    weapons = weapons or {}
    assets = {int(row["xref"]): row["file"] for row in rows}
    selected = _selected_page_ids(doc, pages)
    all_pages: list[dict] = []
    totals = {
        "image_placements": 0,
        "exported_asset_placements": 0,
        "cropped_placements": 0,
        "rotated_placements": 0,
        "soft_mask_placements": 0,
        "transfer_function_placements": 0,
        "decode_array_placements": 0,
        "transfer_function_tokens": 0,
    }
    for pno in selected:
        page = doc[pno]
        title = page_title(page) if name_from_page else ""
        content = b"".join(doc.xref_stream(xref) for xref in page.get_contents())
        placements = parse_image_placements(content, image_resource_map(page, doc),
                                            graphics_state_map(doc, page))
        for placement in placements:
            asset = assets.get(int(placement["xref"]))
            placement["asset"] = asset or None
            placement["exported"] = bool(asset)
            placement["classification"] = "art" if asset else "unexported"
            placement["crop_paths"] = [
                path for path in placement["clip_paths"]
                if not _is_page_clip(path, page.rect.width, page.rect.height)
            ]
            placement["has_custom_crop"] = bool(placement["crop_paths"])
            totals["image_placements"] += 1
            totals["exported_asset_placements"] += int(bool(asset))
            totals["cropped_placements"] += int(placement["has_custom_crop"])
            matrix = placement["matrix_pdf"]
            totals["rotated_placements"] += int(
                abs(matrix[1]) > 1e-6 or abs(matrix[2]) > 1e-6)
            totals["soft_mask_placements"] += int(
                bool(placement["image"].get("smask_xref"))
                or bool(placement["graphics_state"].get("soft_mask")))
            totals["transfer_function_placements"] += int(
                bool(placement["graphics_state"].get("transfer_function")))
            totals["decode_array_placements"] += int(
                bool(placement["image"].get("decode_array")))
        totals["transfer_function_tokens"] += content.count(b"/TR ") + content.count(b"/TR2 ")
        all_pages.append({
            "number": pno + 1,
            "title": title,
            "weapon_id": match_weapon_title(title, weapons),
            "size_points": [_round_number(page.rect.width), _round_number(page.rect.height)],
            "media_box_pdf": page_box_pdf(doc, page, "MediaBox"),
            "crop_box_pdf": page_box_pdf(doc, page, "CropBox"),
            "rotation": page.rotation,
            "placements": placements,
        })
    metadata = {key: value for key, value in doc.metadata.items() if value}
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "coordinate_system": {
            "unit": "point",
            "origin": "bottom-left",
            "matrix_pdf": "[a, b, c, d, e, f]; (x, y) -> (a*x + c*y + e, b*x + d*y + f)",
            "clip_paths": "Commands are already in PDF page coordinates.",
        },
        "source": {
            "file": os.path.basename(pdf),
            "sha256": _sha256(pdf),
            "page_count": doc.page_count,
            "metadata": metadata,
        },
        "assets": [{
            "xref": int(row["xref"]),
            "file": row["file"],
            "source_page": row["page"],
            "width": row["width"],
            "height": row["height"],
            "smask_xref": int(row["smask"]) if row.get("smask") else None,
        } for row in rows],
        "pages": all_pages,
        "audit": {
            **totals,
            "brightness_contrast": (
                "PDF has no standard brightness/contrast slider. If no transfer "
                "function is recorded, Publisher baked that adjustment into pixels."
            ),
        },
    }
    doc.close()
    return _round_values(manifest)


def write_artwork_manifest(manifest: dict, path: str) -> None:
    """Write a human-reviewable, stable UTF-8 artwork placement manifest."""
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def background_xrefs(page) -> set[int]:
    """Картинки, растянутые на всю страницу (текстура бумаги)."""
    out = set()
    for img in page.get_images(full=True):
        xref = img[0]
        try:
            rects = page.get_image_rects(xref)
        except Exception:  # pragma: no cover - old pymupdf
            continue
        for rect in rects:
            if (rect.width >= page.rect.width * 0.85
                    and rect.height >= page.rect.height * 0.85):
                out.add(xref)
    return out


# Publisher exports several legitimate horizontal weapon illustrations with a
# 258–279 px short side.  Testing both native dimensions against ``min_size``
# silently drops them, even though they occupy a large card area.  The native
# longest side still filters UI icons; rendered coverage filters decorative
# rules such as a 6×822 px vertical strip.
MIN_RENDERED_ART_SHARE = 0.05


def is_artwork_candidate(page, xref: int, width: int, height: int,
                         min_size: int) -> bool:
    """Whether an image is large enough *and* visibly substantial on a page.

    ``min_size`` applies to the longer native edge.  The placement must cover
    at least five percent of the page, which admits wide Publisher weapon art
    while excluding thin ornaments whose long edge happens to be large.
    """
    if max(width, height) < min_size:
        return False
    try:
        placements = page.get_image_rects(xref)
    except Exception:  # pragma: no cover - compatibility fallback
        return min(width, height) >= min_size
    page_area = page.rect.width * page.rect.height
    return any(rect.width * rect.height >= page_area * MIN_RENDERED_ART_SHARE
               for rect in placements)


def page_title(page) -> str:
    """Самая крупная надпись в верхней части страницы — название оружия."""
    best: list[tuple[float, str]] = []
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            for span in line["spans"]:
                text = (span["text"] or "").strip()
                if not text or span["bbox"][1] > 130:
                    continue
                best.append((round(span["size"], 1), text))
    if not best:
        return ""
    top = max(size for size, _ in best)
    return " ".join(text for size, text in best if size >= top - 0.5).strip()


def _pixmap_alpha_matches_mask(pix, mask) -> bool:
    """Whether PyMuPDF has actually copied *mask* into ``pix``'s alpha plane.

    Some PyMuPDF builds report an alpha channel on an image with ``/SMask``
    while filling that channel with opaque 255 values.  Treating ``pix.alpha``
    as sufficient in that case silently turns transparent Publisher artwork
    into a black rectangle.  Comparing the planes lets us retain versions
    which already combined the mask without attempting the invalid
    ``Pixmap(rgba, mask)`` constructor call.
    """
    if not pix.alpha or pix.width != mask.width or pix.height != mask.height:
        return False
    if mask.n != 1:
        return False
    samples = pix.samples
    alpha = samples[pix.n - 1::pix.n]
    return alpha == mask.samples


def image_pixmap(doc, xref: int, smask: int = 0):
    """Return a PNG-safe pixmap without discarding a PDF SoftMask.

    PyMuPDF versions differ: some already combine an image XObject's
    ``/SMask`` into the alpha plane, while others expose an all-opaque alpha
    channel.  In the latter case we first remove that alpha plane and only
    then attach the real grayscale mask; attaching it directly to RGBA raises
    ``color pixmap must not have an alpha channel``.  CMYK is converted to RGB
    while preserving the final alpha channel.
    """
    pix = pymupdf.Pixmap(doc, xref)
    if pix.colorspace is None:
        return None
    if pix.colorspace.n not in (1, 3):
        pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
    if smask:
        mask = pymupdf.Pixmap(doc, smask)
        if not _pixmap_alpha_matches_mask(pix, mask):
            # ``Pixmap(pix, 0)`` deliberately removes PyMuPDF's synthetic or
            # stale alpha plane so the actual /SMask can be attached safely.
            color = pymupdf.Pixmap(pix, 0) if pix.alpha else pix
            pix = pymupdf.Pixmap(color, mask)
    return pix


def repeated_xrefs(doc, pages: list[int], share: float) -> set[int]:
    """Images that show up on a large share of pages (paper texture etc.)."""
    seen: dict[int, set[int]] = {}
    for pno in pages:
        for img in doc[pno].get_images(full=True):
            seen.setdefault(img[0], set()).add(pno)
    limit = max(2, int(len(pages) * share))
    return {xref for xref, where in seen.items() if len(where) >= limit}


def extract(pdf: str, out_dir: str, min_size: int, share: float,
            pages: list[int] | None, keep_repeated: bool,
            weapons: dict[str, str] | None = None,
            name_from_page: bool = True) -> list[dict]:
    doc = pymupdf.open(pdf)
    page_ids = _selected_page_ids(doc, pages)
    skip = set() if keep_repeated else repeated_xrefs(doc, page_ids, share)
    weapons = weapons or {}
    os.makedirs(out_dir, exist_ok=True)

    rows: list[dict] = []
    done: set[int] = set()
    for pno in page_ids:
        if not 0 <= pno < doc.page_count:
            continue
        page = doc[pno]
        title = page_title(page) if name_from_page else ""
        weapon_id = match_weapon_title(title, weapons)
        base = slug_of(weapon_id) if weapon_id else f"p{pno + 1:03d}"

        background = background_xrefs(page)
        candidates = []
        for img in page.get_images(full=True):
            xref, smask, width, height = img[0], img[1], img[2], img[3]
            if xref in done or xref in skip:
                done.add(xref)
                continue
            if xref in background and not keep_repeated:
                done.add(xref)
                continue
            if not is_artwork_candidate(page, xref, width, height, min_size):
                done.add(xref)
                continue
            candidates.append((width * height, xref, smask, width, height))
        # the weapon art is the biggest picture on the page; keep the rest
        # as <slug>-2.png, <slug>-3.png
        candidates.sort(reverse=True)
        for index, (_, xref, smask, width, height) in enumerate(candidates, 1):
            pix = image_pixmap(doc, xref, smask)
            if pix is None:
                done.add(xref)
                continue
            name = f"{base}.png" if index == 1 else f"{base}-{index}.png"
            path = os.path.join(out_dir, name)
            pix.save(path)
            done.add(xref)
            rows.append({
                "page": pno + 1,
                "file": name,
                "title": title,
                "weapon_id": weapon_id,
                "xref": xref,
                "width": width,
                "height": height,
                "smask": smask or "",
            })
            print(f"  p{pno + 1:03d} {width}x{height} -> {name}")
    doc.close()
    return rows


def contact_sheet(rows: list[dict], out_dir: str) -> str:
    cards = []
    for r in rows:
        cards.append(
            f'<figure><img src="{html.escape(r["file"])}" loading="lazy">'
            f'<figcaption>стр. {r["page"]}'
            f'{(" · " + html.escape(r["title"])) if r.get("title") else ""}'
            f' · {r["width"]}×{r["height"]}'
            f'<br><code>{html.escape(r["file"])}</code></figcaption></figure>')
    page = f"""<!doctype html>
<html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Картинки из PDF</title>
<style>
body{{font:14px/1.4 system-ui,sans-serif;background:#252525;color:#ffeecd;margin:0;padding:16px}}
h1{{font-size:18px;margin:0 0 16px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:12px}}
figure{{margin:0;background:#171717;border:2px solid #4a4a4a;border-radius:4px;padding:8px}}
img{{width:100%;height:160px;object-fit:contain;background:#fff}}
figcaption{{font-size:12px;color:#ffc674;margin-top:6px}}
code{{color:#fff}}
</style></head><body>
<h1>Картинки из PDF — {len(rows)} шт.</h1>
<div class="grid">{''.join(cards)}</div>
</body></html>
"""
    path = os.path.join(out_dir, "index.html")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(page)
    return path


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("pdf")
    ap.add_argument("--out", default="pdf-images")
    ap.add_argument("--pages", help="страницы через запятую или 12-40")
    ap.add_argument("--min-size", type=int, default=300,
                    help="минимальная длинная сторона artwork в пикселях (300)")
    ap.add_argument("--share", type=float, default=0.5,
                    help="доля страниц, с которой картинка считается текстурой")
    ap.add_argument("--keep-repeated", action="store_true",
                    help="не выкидывать повторяющиеся картинки")
    ap.add_argument("--weapons", default=WEAPONS_JSON,
                    help="weapons.json компаньона для имён по названию страницы")
    ap.add_argument("--title-aliases", default=TITLE_ALIASES_JSON,
                    help="JSON с явно проверенными aliases заголовков Publisher")
    ap.add_argument("--no-page-names", action="store_true",
                    help="не читать название со страницы, оставить pNNN-01.png")
    ap.add_argument("--manifest", metavar="PATH",
                    help="куда записать artwork-manifest.json (по умолчанию в --out)")
    ap.add_argument("--no-manifest", action="store_true",
                    help="не создавать манифест расположения изображений")
    ap.add_argument("--no-html", action="store_true")
    args = ap.parse_args(argv)

    pages = None
    if args.pages:
        pages = []
        for chunk in args.pages.split(","):
            chunk = chunk.strip()
            if "-" in chunk:
                a, b = chunk.split("-", 1)
                pages.extend(range(int(a), int(b) + 1))
            elif chunk:
                pages.append(int(chunk))

    weapons = {} if args.no_page_names else load_weapons(args.weapons)
    if not args.no_page_names:
        weapons.update(load_title_aliases(args.title_aliases))
    if not args.no_page_names and not weapons:
        print("weapons.json не найден — имена будут вида p018-01.png",
              file=sys.stderr)
    rows = extract(args.pdf, args.out, args.min_size, args.share, pages,
                   args.keep_repeated, weapons, not args.no_page_names)
    with open(os.path.join(args.out, "report.csv"), "w", newline="",
              encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["page", "file", "title",
                                                "weapon_id", "xref", "width",
                                                "height", "smask"])
        writer.writeheader()
        writer.writerows(rows)
    if not args.no_manifest:
        manifest_path = args.manifest or os.path.join(args.out, "artwork-manifest.json")
        manifest = artwork_manifest(args.pdf, rows, pages, weapons,
                                    not args.no_page_names)
        write_artwork_manifest(manifest, manifest_path)
        audit = manifest["audit"]
        print("манифест: "
              f"{manifest_path} — размещений: {audit['image_placements']}, "
              f"crop: {audit['cropped_placements']}, "
              f"поворотов: {audit['rotated_placements']}, "
              f"SoftMask: {audit['soft_mask_placements']}")
    if not args.no_html:
        contact_sheet(rows, args.out)
    print(f"готово: {len(rows)} картинок в {args.out}/")
    if not rows:
        print("ничего не нашлось — попробуй --min-size 100 --keep-repeated",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
