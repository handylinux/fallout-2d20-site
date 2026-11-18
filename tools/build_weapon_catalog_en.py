#!/usr/bin/env python3
"""Build the English weapon catalogue with exact Publisher artwork replay.

English text comes from the vendored Companion ``en-EN`` localisation.  A
Publisher layer is used only when the shared artwork manifest identifies the
same ``weapon_id``; the final English page number is never used as a fallback.
"""
from __future__ import annotations

import argparse
import tempfile
from pathlib import Path
from typing import Any

import pymupdf

import weapon2pdf as w
from weapon_catalog_artwork import ArtworkResolver
from weapons2cards_en import Companion, ordered_cards


class EnglishCatalogError(ValueError):
    """Raised when an English catalogue cannot be safely assembled."""


def build(
    source: str | Path,
    output: str | Path,
    *,
    artwork_manifest: str | Path | None = None,
    artwork_root: str | Path | None = None,
    artwork_coverage: str | Path | None = None,
) -> dict[str, Any]:
    """Build 146 English cards and an outline, optionally replaying artwork.

    ``artwork_manifest`` belongs to the exact Publisher PDF named by ``source``.
    All matching layers retain their original matrix, crop and alpha via the
    same strict resolver used for the Russian catalogue.
    """
    source = Path(source)
    output = Path(output)
    if source.resolve() == output.resolve():
        raise EnglishCatalogError("Output PDF must not overwrite the Publisher source")
    if not source.is_file():
        raise EnglishCatalogError(f"Publisher source PDF is missing: {source}")

    companion = Companion()
    cards = ordered_cards(companion)
    if len(cards) != 146 or len({card["id"] for card in cards}) != len(cards):
        raise EnglishCatalogError("English Companion cards must contain 146 unique weapons")

    artwork = ArtworkResolver(artwork_manifest, artwork_root, source)
    w.register_fonts()
    output.parent.mkdir(parents=True, exist_ok=True)
    toc: list[list[Any]] = []
    category_pages: dict[str, int] = {}

    with tempfile.TemporaryDirectory() as directory:
        temp = Path(directory)
        with pymupdf.open() as result:
            previous_category = ""
            for index, card in enumerate(cards, start=1):
                category = str(card["category"])
                page_number = len(result) + 1
                if category != previous_category:
                    toc.append([1, category, page_number])
                    category_pages[category] = page_number
                    previous_category = category
                toc.append([2, str(card["title"]), page_number])

                layer = artwork.layer_for(str(card["id"])) if artwork.enabled else None
                page_pdf = temp / f"card-{index:03d}.pdf"
                w.render_card(card, str(page_pdf), artwork=layer)
                with pymupdf.open(page_pdf) as rendered:
                    result.insert_pdf(rendered)

            if len(result) != len(cards):
                raise EnglishCatalogError("Rendered English page count does not match card count")
            result.set_toc(toc)
            result.set_metadata({
                "title": "Fallout 2d20 Weapon Catalog",
                "author": "handylinux/fallout-2d20-site",
                "subject": "English weapon reference catalogue with Publisher artwork provenance",
                "keywords": "Fallout 2d20, weapons, English, Publisher artwork",
                "creator": "tools/build_weapon_catalog_en.py",
                "producer": "PyMuPDF",
            })
            result.save(str(output), garbage=4, deflate=True, use_objstms=1)

    if artwork.enabled:
        artwork.assert_all_available_layers_requested()
    coverage = artwork.coverage()
    if artwork_coverage is not None:
        artwork.write_coverage(artwork_coverage)
    return {
        "pages": len(cards),
        "cards": len(cards),
        "categories": category_pages,
        "outline_entries": len(toc),
        "artwork": coverage,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Publisher PDF used to extract artwork")
    parser.add_argument("--out", required=True, type=Path,
                        help="published English catalogue PDF")
    parser.add_argument("--artwork-manifest", type=Path,
                        help="artwork-manifest.json from this exact Publisher PDF")
    parser.add_argument("--artwork-root", type=Path,
                        help="directory of extracted artwork PNGs")
    parser.add_argument("--artwork-coverage", type=Path,
                        help="write exact artwork provenance coverage JSON here")
    args = parser.parse_args(argv)
    try:
        result = build(args.source, args.out, artwork_manifest=args.artwork_manifest,
                       artwork_root=args.artwork_root,
                       artwork_coverage=args.artwork_coverage)
    except (OSError, RuntimeError, ValueError) as exc:
        parser.exit(1, f"Error: {exc}\n")
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
