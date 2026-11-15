#!/usr/bin/env python3
"""Interim book preview: source pages 1–13 and three generated weapon pages.

The first 13 pages (including the mod tables) are copied from the source PDF,
not regenerated. The weapon pages are built from Companion data without weapon illustrations by default.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
import tempfile

import pymupdf
import weapon2pdf
from weapons2cards import Companion, build_card, slugify

SOURCE_PAGES = 13
ORDER_FILE = Path(__file__).resolve().parent.parent / "data/weapons/small-guns-order.json"
WEAPONS = ("weapon_10mm_pistol", "weapon_44_pistol", "weapon_flare_gun")


def build_preview(source: Path, output: Path, image_dir: Path, weapons=WEAPONS,
                  with_images: bool = False) -> int:
    source, output, image_dir = Path(source), Path(output), Path(image_dir)
    if source.resolve() == output.resolve():
        raise ValueError("Выходной файл не должен совпадать с исходным PDF")
    weapons = tuple(weapons)
    if len(set(weapons)) != len(weapons):
        raise ValueError("Оружие в списке повторяется")
    with pymupdf.open(source) as original:
        if original.page_count < SOURCE_PAGES:
            raise ValueError(f"В исходном PDF нужно минимум {SOURCE_PAGES} страниц")
        companion = Companion()
        unknown = [wid for wid in weapons if wid not in companion.weapons]
        if unknown:
            raise ValueError("Неизвестные ID оружия: " + ", ".join(unknown))
        weapon2pdf.register_fonts()
        with tempfile.TemporaryDirectory() as temp, pymupdf.open() as result:
            result.insert_pdf(original, from_page=0, to_page=SOURCE_PAGES - 1)
            for index, wid in enumerate(weapons):
                image_path = ""
                if with_images:
                    image = (image_dir / (slugify(wid) + ".png")).resolve()
                    if image.is_file():
                        image_path = str(image)
                    else:
                        print(f"Нет изображения: {wid}", file=sys.stderr)
                card = build_card(companion, wid, page=SOURCE_PAGES + index + 1,
                                  image=image_path)
                page_file = Path(temp) / f"{index}.pdf"
                weapon2pdf.render_card(card, str(page_file))
                with pymupdf.open(page_file) as page:
                    result.insert_pdf(page)
            output.parent.mkdir(parents=True, exist_ok=True)
            result.save(output, garbage=4, deflate=True)
    return SOURCE_PAGES + len(weapons)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="исходный справочник PDF")
    parser.add_argument("--image-dir", type=Path, default=Path("art"))
    parser.add_argument("--with-images", action="store_true", help="необязательно: добавить изображения оружия")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--full", action="store_true", help="весь стрелковый раздел по сохранённому порядку")
    args = parser.parse_args(argv)
    try:
        weapons = json.loads(ORDER_FILE.read_text(encoding="utf-8")) if args.full else WEAPONS
        count = build_preview(args.source, args.out, args.image_dir, weapons, args.with_images)
    except (OSError, ValueError, RuntimeError) as exc:
        parser.exit(1, f"Ошибка: {exc}\n")
    print(f"Сохранено {count} страниц: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
