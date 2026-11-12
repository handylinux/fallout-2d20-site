#!/usr/bin/env python3
"""Interim book preview: source pages 1–13 and three generated weapon pages.

The first 13 pages (including the mod tables) are copied from the source PDF,
not regenerated. The three weapon pages are built from Companion data.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import tempfile

import pymupdf
import weapon2pdf
from weapons2cards import Companion, build_card, slugify

SOURCE_PAGES = 13
WEAPONS = ("weapon_10mm_pistol", "weapon_44_pistol", "weapon_flare_gun")


def build_preview(source: Path, output: Path, image_dir: Path) -> int:
    source, output, image_dir = Path(source), Path(output), Path(image_dir)
    if source.resolve() == output.resolve():
        raise ValueError("Выходной файл не должен совпадать с исходным PDF")
    with pymupdf.open(source) as original:
        if original.page_count < SOURCE_PAGES:
            raise ValueError(f"В исходном PDF нужно минимум {SOURCE_PAGES} страниц")
        companion = Companion()
        weapon2pdf.register_fonts()
        with tempfile.TemporaryDirectory() as temp, pymupdf.open() as result:
            result.insert_pdf(original, from_page=0, to_page=SOURCE_PAGES - 1)
            for index, wid in enumerate(WEAPONS):
                image = image_dir / (slugify(wid) + ".png")
                card = build_card(companion, wid, page=SOURCE_PAGES + index + 1,
                                  image=str(image) if image.is_file() else "")
                page_file = Path(temp) / f"{index}.pdf"
                weapon2pdf.render_card(card, str(page_file))
                with pymupdf.open(page_file) as page:
                    result.insert_pdf(page)
            output.parent.mkdir(parents=True, exist_ok=True)
            result.save(output, garbage=4, deflate=True)
    return SOURCE_PAGES + len(WEAPONS)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="исходный справочник PDF")
    parser.add_argument("--image-dir", type=Path, default=Path("art"))
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        count = build_preview(args.source, args.out, args.image_dir)
    except (OSError, ValueError, RuntimeError) as exc:
        parser.exit(1, f"Ошибка: {exc}\n")
    print(f"Сохранено {count} страниц: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
