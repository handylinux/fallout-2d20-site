#!/usr/bin/env python3
"""Create a faithful interim front section from the original weapon-book PDF.

Physical source pages 1–9 are copied unchanged: cover, spread, rules and
section divider. This is not a regenerated layout; the source PDF is required.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pymupdf

FRONT_PAGES = 9


def build_front(source: Path, output: Path) -> int:
    source = Path(source)
    output = Path(output)
    if source.resolve() == output.resolve():
        raise ValueError("Выходной файл не должен совпадать с исходным PDF")
    with pymupdf.open(source) as original:
        if original.page_count < FRONT_PAGES:
            raise ValueError(f"В исходном PDF нужно минимум {FRONT_PAGES} страниц")
        with pymupdf.open() as result:
            result.insert_pdf(original, from_page=0, to_page=FRONT_PAGES - 1)
            output.parent.mkdir(parents=True, exist_ok=True)
            result.save(output, garbage=4, deflate=True)
    return FRONT_PAGES


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="исходный справочник PDF")
    parser.add_argument("--out", required=True, type=Path, help="путь к результату")
    args = parser.parse_args(argv)
    try:
        count = build_front(args.source, args.out)
    except (OSError, ValueError, RuntimeError) as exc:
        parser.exit(1, f"Ошибка: {exc}\n")
    print(f"Сохранено {count} страниц: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
