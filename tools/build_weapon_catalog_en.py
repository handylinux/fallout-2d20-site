#!/usr/bin/env python3
"""Build the complete English Fallout 2d20 weapon reference book.

The English edition is a full print book rather than a stack of cards: it
contains an illustrated localised cover, opening spread, printed contents,
damage-effect and weapon-quality references, an editable English modification
reference, illustrated Publisher section dividers, all 144 confirmed English
cards, and the source closing sequence. Weapon artwork is intentionally stricter than
all other page decoration: a card can replay a Publisher layer only when the
exact same ``weapon_id`` appears in the supplied extraction manifest.
"""
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from typing import Any

import pymupdf
from reportlab.lib.colors import Color
from reportlab.pdfgen import canvas

import companion_mods_en
import weapon2pdf as w
import weapon_book_cover as book_cover
import weapon_book_toc as toc_render
import weapon_heavy_preview as detailed_card
import weapon_energy_preview as publisher_energy
import weapon_catalog_en_mods as catalogue_mods
import weapon_mods_table_unicode as mod_tables
from weapon_catalog_artwork import ArtworkResolver
from weapons2cards_en import CATALOG_EXCLUDED_IDS, Companion, ordered_cards

ROOT = Path(__file__).resolve().parent.parent
REFERENCE_DATA = ROOT / "data" / "weapon-book" / "catalog-en-reference.json"

# The four physical Publisher dividers are already English illustrated magazine
# covers.  They are retained as dividers, not used as an artwork fallback for a
# weapon card.  Later Companion categories did not exist in that print run and
# receive deliberately non-weapon, typographic dividers.
CATEGORY_PRESENTATION: dict[str, dict[str, Any]] = {
    "Light Weapons": {"title": "SMALL GUNS", "source_page": 13},
    "Heavy Weapons": {"title": "HEAVY GUNS", "source_page": 57},
    "Energy Weapons": {"title": "ENERGY GUNS", "source_page": 80},
    "Explosive Weapons": {"title": "EXPLOSIVES"},
    "Melee Weapons": {"title": "MELEE WEAPONS", "source_page": 95},
    "Thrown Weapons": {"title": "THROWN WEAPONS"},
    "Unarmed Weapons": {"title": "UNARMED WEAPONS"},
    "Other Weapons": {"title": "OTHER WEAPONS"},
}

REFERENCE_TITLE = {
    "damage_effects": "DAMAGE EFFECTS",
    "weapon_qualities": "WEAPON QUALITIES",
}

# Page-body geometry (top-down coordinates), tuned to the existing cards and
# table pages so the opening reads as one volume.
REF_LEFT = 39.0
REF_RIGHT = 556.0
REF_TOP = 108.0
REF_BOTTOM = 787.0
REF_FONT_SIZE = 10.5
REF_LEADING = 14.0
REF_ENTRY_GAP = 7.0
REF_INTRO_GAP = 17.0
REF_TEXT_INDENT = 16.0


class EnglishCatalogError(ValueError):
    """Raised when the complete English edition cannot be safely assembled."""


def _has_cyrillic(value: str) -> bool:
    return any("\u0400" <= char <= "\u04ff" for char in value)


def _load_reference_data(path: Path = REFERENCE_DATA) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EnglishCatalogError(f"Unable to read English reference data: {path}") from exc
    if not isinstance(data, dict):
        raise EnglishCatalogError("English reference data must be an object")
    for kind in REFERENCE_TITLE:
        section = data.get(kind)
        if not isinstance(section, dict) or not isinstance(section.get("title"), str):
            raise EnglishCatalogError(f"English reference section is missing: {kind}")
        if not isinstance(section.get("intro"), str) or not isinstance(section.get("entries"), list):
            raise EnglishCatalogError(f"English reference section is malformed: {kind}")
        for item in section["entries"]:
            if not isinstance(item, dict) or not isinstance(item.get("id"), str) \
                    or not isinstance(item.get("text"), str):
                raise EnglishCatalogError(f"English reference entry is malformed: {item!r}")
    return data


def _reference_label(identifier: str, item: dict[str, Any], companion: Companion,
                     kind: str) -> str:
    """Resolve a printed reference heading without silently translating labels."""
    explicit = item.get("label")
    if explicit is not None:
        if not item.get("source_only") or not isinstance(explicit, str) or not explicit:
            raise EnglishCatalogError(f"Invalid explicit reference label for {identifier}")
        return explicit
    labels = companion.effects if kind == "damage_effects" else companion.qualities
    localized = (labels.get(identifier) or {}).get("name")
    if not isinstance(localized, str) or not localized:
        raise EnglishCatalogError(f"Missing English Companion reference label: {identifier}")
    # The canonical UI label omits a variable marker for the two parameterised
    # rules.  The marker is rule notation, not a replacement translation.
    if identifier == "effect_piercing_x":
        return localized + " X"
    if identifier == "quality_ammo-hungry_x":
        return localized + " X"
    return localized


def _validate_reference_data(reference: dict[str, Any], companion: Companion) -> None:
    effect_ids = {entry["id"] for entry in reference["damage_effects"]["entries"]}
    quality_section = reference["weapon_qualities"]
    quality_ids = {entry["id"] for entry in quality_section["entries"]
                   if not entry.get("source_only")}
    # Companion also has names used by modifications with no verified rule
    # prose. Audit them as data, but don't render them as glossary entries.
    undocumented = quality_section.get("undocumented_ids", [])
    if not isinstance(undocumented, list) or any(not isinstance(item, str) for item in undocumented):
        raise EnglishCatalogError("Undocumented quality IDs must be a list of strings")
    undocumented_ids = set(undocumented)
    if len(undocumented_ids) != len(undocumented) or quality_ids & undocumented_ids:
        raise EnglishCatalogError("Undocumented quality IDs are duplicate or already defined")
    quality_ids |= undocumented_ids
    missing_effects = set(companion.effects) - effect_ids
    extra_effects = effect_ids - set(companion.effects)
    missing_qualities = set(companion.qualities) - quality_ids
    extra_qualities = quality_ids - set(companion.qualities)
    if missing_effects or extra_effects or missing_qualities or extra_qualities:
        raise EnglishCatalogError(
            "English reference IDs diverge from the Companion snapshot: "
            f"effects missing={sorted(missing_effects)} extra={sorted(extra_effects)}; "
            f"qualities missing={sorted(missing_qualities)} extra={sorted(extra_qualities)}"
        )
    for kind in REFERENCE_TITLE:
        for entry in reference[kind]["entries"]:
            label = _reference_label(entry["id"], entry, companion, kind)
            if _has_cyrillic(label) or _has_cyrillic(entry["text"]):
                raise EnglishCatalogError(f"Non-English visible reference text for {entry['id']}")


def _wrap_words(text: str, font: str, size: float, width: float) -> list[str]:
    """Word-wrap copy without ever splitting an individual word into letters."""
    lines: list[str] = []
    for paragraph in text.split("\n"):
        words = paragraph.split()
        if not words:
            lines.append("")
            continue
        current = words[0]
        if w.sw(current, font, size) > width:
            raise EnglishCatalogError(f"Reference word does not fit the column: {current}")
        for word in words[1:]:
            if w.sw(word, font, size) > width:
                raise EnglishCatalogError(f"Reference word does not fit the column: {word}")
            candidate = current + " " + word
            if w.sw(candidate, font, size) <= width:
                current = candidate
            else:
                lines.append(current)
                current = word
        lines.append(current)
    return lines


def _entry_layout(label: str, body: str) -> tuple[list[str], list[str]]:
    """Return the first and continuation body lines for one reference rule."""
    label_width = w.sw(label, "Carlito-Bold", REF_FONT_SIZE)
    first_width = REF_RIGHT - (REF_LEFT + REF_TEXT_INDENT + label_width + 4.0)
    continuation_width = REF_RIGHT - (REF_LEFT + REF_TEXT_INDENT)
    if first_width < 70:
        # None of the current canonical labels comes close to this, but making
        # the failure explicit avoids a clipped title if localisation changes.
        raise EnglishCatalogError(f"Reference label too wide for the first line: {label}")
    words = body.split()
    if not words:
        return [], []
    first: list[str] = []
    while words:
        candidate = " ".join(first + [words[0]])
        if w.sw(candidate, "Carlito", REF_FONT_SIZE) <= first_width:
            first.append(words.pop(0))
        else:
            break
    if not first:
        # The label owns the first line and prose starts at the normal indent.
        rest = _wrap_words(body, "Carlito", REF_FONT_SIZE, continuation_width)
        return [], rest
    rest = _wrap_words(" ".join(words), "Carlito", REF_FONT_SIZE, continuation_width) if words else []
    return [" ".join(first)], rest


def render_reference_pages(section: dict[str, Any], companion: Companion, kind: str,
                           output: Path, page_start: int) -> int:
    """Render one editable English reference section and return page count."""
    if page_start < 1:
        raise EnglishCatalogError("Reference pages need a positive printed page number")
    w.register_fonts()
    title = str(section["title"])
    intro = str(section["intro"])
    entries: list[tuple[str, list[str], list[str], bool]] = []
    items = section["entries"] + [{"id": identifier, "text": "Needs clarification."}
                                  for identifier in section.get("undocumented_ids", [])]
    for item in items:
        label = _reference_label(str(item["id"]), item, companion, kind).upper()
        first, rest = _entry_layout(label, str(item["text"]))
        page_break = item.get("page_break_before", False)
        if not isinstance(page_break, bool):
            raise EnglishCatalogError(f"Invalid reference page break for {item['id']}")
        entries.append((label, first, rest, page_break))

    output.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(output), pagesize=(w.PAGE_W, w.PAGE_H))
    pages = 0
    y_top = REF_TOP

    def start_page(continued: bool) -> None:
        nonlocal pages, y_top
        if pages:
            c.showPage()
        pages += 1
        w.draw_paper(c)
        heading = title if not continued else title + " · CONTINUED"
        size = w.TITLE_SIZE
        while size > 12 and w.sw(heading, "Carlito-Bold", size) > w.CONTENT_W:
            size -= .5
        w.draw_center_line(c, w.TITLE_TOP, heading, "Carlito-Bold", size)
        c.setFillColor(w.BLACK)
        c.rect(w.PAGE_W_WORK_CENTER - w.RULE_W / 2.0, w.y_from_top(w.RULE_TOP),
               w.RULE_W, -w.RULE_H, stroke=0, fill=1)
        w.draw_page_number(c, page_start + pages - 1)
        y_top = REF_TOP
        if not continued:
            intro_lines = _wrap_words(intro, "Carlito", REF_FONT_SIZE, REF_RIGHT - REF_LEFT)
            for line in intro_lines:
                w.draw_top(c, REF_LEFT, y_top, line, "Carlito", REF_FONT_SIZE)
                y_top += REF_LEADING
            y_top += REF_INTRO_GAP

    start_page(False)
    for label, first, rest, page_break in entries:
        if page_break:
            start_page(True)
        line_count = 1 + len(rest) if first else 1 + len(rest)
        # A label without a first prose fragment takes a line of its own.
        height = line_count * REF_LEADING + REF_ENTRY_GAP
        if height > REF_BOTTOM - REF_TOP:
            raise EnglishCatalogError(f"Reference entry is too tall for one page: {label}")
        if y_top + height > REF_BOTTOM:
            start_page(True)
        # solid bullet avoids depending on a specific Unicode glyph in Carlito
        c.setFillColor(w.BLACK)
        c.rect(REF_LEFT, w.y_from_top(y_top + REF_FONT_SIZE * .73), 5.0, -5.0,
               stroke=0, fill=1)
        w.draw_top(c, REF_LEFT + REF_TEXT_INDENT, y_top, label, "Carlito-Bold", REF_FONT_SIZE)
        label_width = w.sw(label, "Carlito-Bold", REF_FONT_SIZE)
        if first:
            w.draw_top(c, REF_LEFT + REF_TEXT_INDENT + label_width + 4.0, y_top,
                       first[0], "Carlito", REF_FONT_SIZE)
        y_top += REF_LEADING
        for line in rest:
            w.draw_top(c, REF_LEFT + REF_TEXT_INDENT, y_top, line, "Carlito", REF_FONT_SIZE)
            y_top += REF_LEADING
        y_top += REF_ENTRY_GAP
    c.save()
    return pages


def _renumber_source_page(page: pymupdf.Page, final_number: int, source_number: int) -> None:
    """Replace only a source footer page number, preserving the page artwork."""
    words = [word for word in page.get_text("words")
             if word[4] == str(source_number) and word[1] > 800]
    if len(words) != 1:
        raise EnglishCatalogError(
            f"Cannot uniquely locate source page number {source_number} for renumbering"
        )
    page.add_redact_annot(pymupdf.Rect(words[0][:4]), fill=False, cross_out=False)
    page.apply_redactions(images=0, graphics=0, text=0)
    page.insert_font(fontname="catalogpagenum", fontfile=mod_tables.REGULAR)
    font = pymupdf.Font(fontfile=mod_tables.REGULAR)
    label = str(final_number)
    x = (w.MARGIN_L + 2.57 if final_number % 2 == 0
         else w.CONTENT_R - 2.57 - font.text_length(label, fontsize=9.96))
    page.insert_text((x, w.PAGE_NUMBER_TOP + 9.96 * .75), label,
                     fontname="catalogpagenum", fontsize=9.96, color=(0, 0, 0))


def _append_source_page(result: pymupdf.Document, original: pymupdf.Document,
                        source_number: int) -> int:
    result.insert_pdf(original, from_page=source_number - 1, to_page=source_number - 1)
    _renumber_source_page(result[-1], len(result), source_number)
    return len(result)


def _render_generated_divider(title: str, page_number: int, output: Path) -> None:
    """Render a Companion-only category divider without borrowing weapon art."""
    w.register_fonts()
    c = canvas.Canvas(str(output), pagesize=(w.PAGE_W, w.PAGE_H))
    w.draw_paper(c)
    c.setStrokeColor(Color(.18, .18, .18))
    c.setLineWidth(1.0)
    cx, cy = w.PAGE_W_WORK_CENTER, w.PAGE_H / 2.0
    for radius in (124, 94, 64):
        c.circle(cx, cy, radius, stroke=1, fill=0)
    c.setFillColor(Color(.18, .18, .18))
    c.rect(cx - 5, cy - 5, 10, 10, stroke=0, fill=1)
    w.draw_center_line(c, 276, "WEAPON REFERENCE", "Carlito", 12)
    size = 31.0
    while size > 15 and w.sw(title, "Carlito-Bold", size) > w.CONTENT_W - 28:
        size -= .5
    w.draw_center_line(c, 322, title, "Carlito-Bold", size)
    c.setFillColor(w.BLACK)
    c.rect(w.PAGE_W_WORK_CENTER - w.RULE_W / 2.0, w.y_from_top(372),
           w.RULE_W, -w.RULE_H, stroke=0, fill=1)
    w.draw_page_number(c, page_number)
    c.showPage()
    c.save()


def _append_generated_divider(result: pymupdf.Document, title: str, temp: Path) -> int:
    page_number = len(result) + 1
    path = temp / f"divider-{page_number}.pdf"
    _render_generated_divider(title, page_number, path)
    with pymupdf.open(path) as divider:
        result.insert_pdf(divider)
    return len(result)


def _category_cards(cards: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Group cards while omitting an otherwise empty presentation category."""
    grouped: dict[str, list[dict[str, Any]]] = {
        category: [] for category in CATEGORY_PRESENTATION
    }
    for card in cards:
        category = str(card["category"])
        if category not in CATEGORY_PRESENTATION:
            raise EnglishCatalogError(f"No English category presentation for {category}")
        grouped[category].append(card)
    if not cards:
        raise EnglishCatalogError("English catalogue has no cards")
    # `Other Weapons` was represented only by Straight Razor. Once that
    # confirmed non-weapon is excluded, do not emit an empty divider or TOC
    # entry merely because Companion retains the raw record.
    return grouped


# A compact English table is the default for dense inventories. Where the
# Publisher card actually had a parameter table, preserve that layout for
# slightly longer lists as long as type and prose still fit on the card.
SPARSE_MOD_LIMIT = 6
PUBLISHER_DETAIL_LIMIT = 8
PUBLISHER_MOD_CARD_PAGES = {
    "weapon_crossbow": 55,
    "weapon_bow": 56,
    **detailed_card.SOURCE_PAGES,
    **publisher_energy.SOURCE_PAGES,
}


def _render_detailed_weapon(companion: Companion, card: dict[str, Any], path: Path,
                            rows: list[catalogue_mods.Row], layer=None) -> None:
    detailed_card.render_heavy(
        companion, card["id"], card["page"], {}, path, card=card,
        rows=[(slot, values) for slot, *values in rows],
        mod_table_headers=("SLOT", *companion_mods_en.HEADERS),
        document_title_suffix="weapon catalogue", artwork=layer, shared_mods=[], fit_all_rows=True,
    )


def _detailed_cards(source: Path, companion: Companion, grouped: dict[str, list[dict[str, Any]]],
                    rows_by_weapon: dict[str, list[catalogue_mods.Row]], trial: Path) -> set[str]:
    """Keep sparse, weapon-specific tables only if the actual card has room."""
    with pymupdf.open(source) as original:
        publisher_detailed = {wid for wid, number in PUBLISHER_MOD_CARD_PAGES.items()
                              if "ПРЕФИКС" in original[number - 1].get_text().split()}
    result = set()
    w.register_fonts()
    for cards in grouped.values():
        shared = set(catalogue_mods.shared_rows((card["id"] for card in cards), rows_by_weapon))
        for card in cards:
            wid = card["id"]
            rows = rows_by_weapon[wid]
            limit = PUBLISHER_DETAIL_LIMIT if wid in publisher_detailed else SPARSE_MOD_LIMIT
            if (wid in catalogue_mods.UNVERIFIED_WEAPON_IDS or len(rows) > limit
                    or not set(rows) - shared):
                continue
            try:
                _render_detailed_weapon(companion, card, trial, rows)
            except detailed_card.DetailedModsLayoutError:
                continue
            result.add(wid)
    return result


def _category_mod_data(grouped: dict[str, list[dict[str, Any]]],
                       rows_by_weapon: dict[str, list[catalogue_mods.Row]],
                       detailed_ids: set[str]) -> dict[str, list[dict[str, Any]]]:
    """Every name-only row has either a shared reference or a specific entry."""
    tables = {}
    for category, cards in grouped.items():
        shared = set(catalogue_mods.shared_rows((card["id"] for card in cards), rows_by_weapon))
        compact = [card for card in cards if card["id"] not in detailed_ids]
        title = CATEGORY_PRESENTATION[category]["title"]
        chapter_tables = []
        cited = {row for card in compact if card["id"] not in catalogue_mods.UNVERIFIED_WEAPON_IDS
                 for row in rows_by_weapon[card["id"]]} & shared
        if cited:
            chapter_tables.append(catalogue_mods.table_data(f"{title} MODIFICATIONS", sorted(cited)))
        specific = []
        for card in compact:
            wid = card["id"]
            unverified = wid in catalogue_mods.UNVERIFIED_WEAPON_IDS
            own = [row for row in rows_by_weapon[wid] if unverified or row not in shared]
            if own:
                specific.append(catalogue_mods.specific_section(card["title"], own, unverified=unverified))
        if specific:
            chapter_tables.append({"title": f"{title} — SPECIFIC MODIFICATIONS",
                                   "headers": list(companion_mods_en.HEADERS), "sections": specific, "specific": True})
        if chapter_tables:
            tables[category] = chapter_tables
    return tables


def _render_weapon(companion: Companion, card: dict[str, Any], path: Path,
                   artwork: ArtworkResolver | None, rows: list[catalogue_mods.Row], *,
                   detailed: bool) -> None:
    """Render exactly one modification block on each weapon page."""
    wid = card["id"]
    layer = artwork.layer_for(wid) if artwork is not None and artwork.enabled else None
    if detailed:
        _render_detailed_weapon(companion, card, path, rows, layer)
    else:
        labels = dict(card["labels"])
        if wid in catalogue_mods.UNVERIFIED_WEAPON_IDS:
            labels["mods_heading"] = "MODIFICATIONS — COMPATIBILITY NEEDS CLARIFICATION"
        compact = {**card, "labels": labels, "mods": catalogue_mods.card_mod_names(companion, rows)}
        w.render_card(compact, str(path), artwork=layer)


def _append_pdf(result: pymupdf.Document, path: Path) -> int:
    with pymupdf.open(path) as generated:
        result.insert_pdf(generated)
        return generated.page_count


def _assemble(source: Path, output: Path, companion: Companion,
              grouped: dict[str, list[dict[str, Any]]], reference: dict[str, Any],
              mod_data: dict[str, list[dict[str, Any]]], rows_by_weapon: dict[str, list[catalogue_mods.Row]],
              detailed_ids: set[str],
              *, toc_pdf: Path | None,
              artwork: ArtworkResolver | None) -> dict[str, Any]:
    """Assemble one pass and return the stable printed/outline contents map."""
    entries: list[list[Any]] = []
    category_pages: dict[str, int] = {}
    reference_pages: dict[str, list[int]] = {}
    mod_pages: dict[str, int] = {}
    card_pages: dict[str, int] = {}
    specific_pages: dict[str, int] = {}
    card_count = sum(map(len, grouped.values()))

    with tempfile.TemporaryDirectory() as directory:
        temp = Path(directory)
        cover = temp / "cover-en.pdf"
        book_cover.make_localized_cover(source, cover)
        with pymupdf.open(source) as original, pymupdf.open() as result:
            if original.page_count < 106:
                raise EnglishCatalogError("Publisher source PDF needs all 106 pages")
            _append_pdf(result, cover)
            book_cover.restore_transparency_group(original[0], result[0])
            for source_page in (2, 3):
                _append_source_page(result, original, source_page)
            if toc_pdf is not None:
                _append_pdf(result, toc_pdf)

            for kind in ("damage_effects", "weapon_qualities"):
                ref_path = temp / f"{kind}.pdf"
                start = len(result) + 1
                rendered = render_reference_pages(reference[kind], companion, kind,
                                                  ref_path, start)
                actual = _append_pdf(result, ref_path)
                if actual != rendered:
                    raise EnglishCatalogError(f"Reference page count changed for {kind}")
                pages = list(range(start, start + actual))
                reference_pages[kind] = pages
                entries.append([1, REFERENCE_TITLE[kind], start])

            arsenal_page = _append_source_page(result, original, 9)
            entries.append([1, "ARSENAL", arsenal_page])

            for category in CATEGORY_PRESENTATION:
                if not grouped[category]:
                    continue
                configuration = CATEGORY_PRESENTATION[category]
                title = str(configuration["title"])
                source_page = configuration.get("source_page")
                if source_page is not None:
                    divider_page = _append_source_page(result, original, int(source_page))
                else:
                    divider_page = _append_generated_divider(result, title, temp)
                category_pages[category] = divider_page
                entries.append([1, title, divider_page])
                for data in mod_data.get(category, []):
                    mod_start = len(result) + 1
                    mod_path = temp / f"mods-{mod_start}.pdf"
                    mod_tables.render(data, mod_path, page_start=mod_start)
                    _append_pdf(result, mod_path)
                    page_map = specific_pages if data.get("specific") else mod_pages
                    page_map[category] = mod_start
                    entries.append([2, data["title"], mod_start])
                for card in grouped[category]:
                    number = len(result) + 1
                    rendered_card = dict(card)
                    rendered_card["page"] = number
                    path = temp / f"card-{number:03d}.pdf"
                    _render_weapon(companion, rendered_card, path, artwork, rows_by_weapon[card["id"]],
                                   detailed=card["id"] in detailed_ids)
                    _append_pdf(result, path)
                    card_pages[str(card["id"])] = number
                    entries.append([2, str(card["title"]), number])

            closing: list[int] = []
            for source_page in range(102, 106):
                closing.append(_append_source_page(result, original, source_page))
            # Retain the source back cover as the final page.  Padding goes
            # immediately before it so the completed book is print-signature
            # friendly without changing that closing art.
            padding = (-(len(result) + 1)) % 4
            for index in range(padding):
                blank = temp / f"closing-pad-{index}.pdf"
                toc_render.make_blank_page(len(result) + 1, blank)
                _append_pdf(result, blank)
            closing.append(_append_source_page(result, original, 106))

            if len(card_pages) != card_count:
                raise EnglishCatalogError("Not every English weapon card was rendered")
            if len(result) % 4:
                raise EnglishCatalogError("Complete English book must end on a multiple of four pages")
            result.set_toc(entries)
            result.set_metadata({
                "title": "Fallout 2d20 Wasteland Arsenal — English Edition",
                "author": "handylinux/fallout-2d20-site",
                "subject": "Complete English weapon reference with exact Publisher artwork provenance",
                "keywords": "Fallout 2d20, weapons, English, Arsenal, Publisher artwork",
                "creator": "tools/build_weapon_catalog_en.py",
                "producer": "PyMuPDF",
            })
            output.parent.mkdir(parents=True, exist_ok=True)
            # A release build must be byte-reproducible.  A new PyMuPDF
            # document otherwise receives random trailer IDs even when all
            # source data, layout and artwork are unchanged.
            result.save(str(output), garbage=4, deflate=True, use_objstms=1,
                        no_new_id=True)
            total = len(result)

    if toc_pdf is None:
        toc_pages = 0
    else:
        with pymupdf.open(toc_pdf) as rendered_toc:
            toc_pages = rendered_toc.page_count
    return {
        "pages": total,
        "cards": card_count,
        "toc": entries,
        "toc_pages": toc_pages,
        "references": reference_pages,
        "modifications": mod_pages,
        "categories": category_pages,
        "card_pages": card_pages,
        "specific_modifications": specific_pages,
        "detailed_cards": sorted(detailed_ids),
        "closing": closing,
    }


def build(
    source: str | Path,
    output: str | Path,
    *,
    artwork_manifest: str | Path | None = None,
    artwork_root: str | Path | None = None,
    artwork_coverage: str | Path | None = None,
    with_toc: bool = True,
) -> dict[str, Any]:
    """Build the complete English book and its exact-ID artwork audit."""
    source = Path(source)
    output = Path(output)
    if source.resolve() == output.resolve():
        raise EnglishCatalogError("Output PDF must not overwrite the Publisher source")
    if not source.is_file():
        raise EnglishCatalogError(f"Publisher source PDF is missing: {source}")

    companion = Companion()
    cards = ordered_cards(companion)
    card_ids = {str(card["id"]) for card in cards}
    expected_ids = set(companion.weapons) - CATALOG_EXCLUDED_IDS
    if card_ids != expected_ids or len(cards) != 144:
        raise EnglishCatalogError(
            "English catalogue must contain 144 unique confirmed weapons; "
            f"missing={sorted(expected_ids - card_ids)} extra={sorted(card_ids - expected_ids)}"
        )
    if any(_has_cyrillic(str(value)) for card in cards
           for value in (card["title"], card["description"], card["range"])):
        raise EnglishCatalogError("English card adapter emitted Cyrillic visible text")
    reference = _load_reference_data()
    _validate_reference_data(reference, companion)
    grouped = _category_cards(cards)
    rows_by_weapon = catalogue_mods.weapon_rows(companion, card_ids)

    with tempfile.TemporaryDirectory() as directory:
        temp = Path(directory)
        detailed_ids = _detailed_cards(source, companion, grouped, rows_by_weapon, temp / "fit.pdf")
        mod_data = _category_mod_data(grouped, rows_by_weapon, detailed_ids)
        if with_toc:
            # First pass establishes references, table pagination and card
            # locations without giving an artwork resolver a chance to record
            # a non-final pass.  The printed TOC is then iterated to a stable
            # page count just like the Russian book builder.
            preliminary = _assemble(source, temp / "preliminary.pdf", companion, grouped,
                                    reference, mod_data, rows_by_weapon, detailed_ids, toc_pdf=None, artwork=None)
            toc_without_offset = preliminary["toc"]
            toc_pdf = temp / "toc.pdf"
            offset = 0
            for _ in range(6):
                toc_render.render_toc_pages(
                    [[level, title, page + offset]
                     for level, title, page in toc_without_offset],
                    toc_pdf, title=toc_render.TOC_TITLE_EN,
                )
                with pymupdf.open(toc_pdf) as printed:
                    printed_pages = printed.page_count
                if printed_pages == offset:
                    break
                offset = printed_pages
            else:
                raise EnglishCatalogError("English printed TOC page count did not converge")
            expected_toc = [[level, title, page + offset]
                            for level, title, page in toc_without_offset]
        else:
            toc_pdf = None
            offset = 0
            expected_toc = []

        artwork = ArtworkResolver(artwork_manifest, artwork_root, source)
        stats = _assemble(source, output, companion, grouped, reference, mod_data, rows_by_weapon, detailed_ids,
                          toc_pdf=toc_pdf, artwork=artwork)
        if with_toc and stats["toc"] != expected_toc:
            raise EnglishCatalogError("English TOC numbering changed between assembly passes")

    if artwork.enabled:
        artwork.assert_all_available_layers_requested()
    coverage = artwork.coverage()
    if artwork_coverage is not None:
        artwork.write_coverage(artwork_coverage)
    stats["toc_pages"] = offset
    stats["outline_entries"] = len(stats["toc"])
    stats["artwork"] = coverage
    return stats


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Publisher PDF used for dividers and exact card artwork")
    parser.add_argument("--out", required=True, type=Path,
                        help="published complete English weapon book PDF")
    parser.add_argument("--artwork-manifest", type=Path,
                        help="artwork-manifest.json from this exact Publisher PDF")
    parser.add_argument("--artwork-root", type=Path,
                        help="directory of extracted exact artwork PNGs")
    parser.add_argument("--artwork-coverage", type=Path,
                        help="write exact artwork provenance coverage JSON here")
    parser.add_argument("--no-toc", action="store_true",
                        help="omit the printed English table of contents for technical inspection")
    args = parser.parse_args(argv)
    try:
        result = build(args.source, args.out, artwork_manifest=args.artwork_manifest,
                       artwork_root=args.artwork_root,
                       artwork_coverage=args.artwork_coverage, with_toc=not args.no_toc)
    except (OSError, RuntimeError, ValueError) as exc:
        parser.exit(1, f"Error: {exc}\n")
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
