#!/usr/bin/env python3
"""Вытащить картинки из PDF (например, из книги, собранной в Publisher).

    python3 tools/extract_pdf_images.py book.pdf --out art/

Что делает:
  * проходит по страницам и достаёт все встроенные изображения;
  * выкидывает мелочь (иконки), повторяющуюся текстуру бумаги и дубликаты;
  * сохраняет PNG (CMYK-картинки конвертируются в RGB, альфа-канал
    приклеивается из SMask);
  * имена вида p018-02.png — страница и порядковый номер на странице;
  * рядом кладёт index.html — контактный лист с номерами страниц, чтобы
    быстро понять, где какое оружие;
  * report.csv — страница, xref, размеры, фильтр, имя файла.

Зависимости: pymupdf, pillow (pip install pymupdf pillow).
"""

from __future__ import annotations

import argparse
import csv
import html
import os
import sys

try:
    import pymupdf
except ImportError:  # pragma: no cover - dependency hint
    print("нужен pymupdf: python3 -m pip install pymupdf pillow", file=sys.stderr)
    raise SystemExit(2)


def image_pixmap(doc, xref: int):
    """CMYK/Gray/alpha-safe pixmap for an image xref."""
    pix = pymupdf.Pixmap(doc, xref)
    if pix.colorspace is None:
        return None
    if pix.colorspace.n not in (1, 3) or pix.alpha:
        pix = pymupdf.Pixmap(pymupdf.csRGB, pix)  # drops alpha, converts CMYK
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
            pages: list[int] | None, keep_repeated: bool) -> list[dict]:
    doc = pymupdf.open(pdf)
    page_ids = [p - 1 for p in pages] if pages else list(range(doc.page_count))
    skip = set() if keep_repeated else repeated_xrefs(doc, page_ids, share)
    os.makedirs(out_dir, exist_ok=True)

    rows: list[dict] = []
    done: set[int] = set()
    for pno in page_ids:
        if not 0 <= pno < doc.page_count:
            continue
        index = 0
        for img in doc[pno].get_images(full=True):
            xref, smask, width, height = img[0], img[1], img[2], img[3]
            if xref in done:
                continue
            if xref in skip:
                done.add(xref)
                continue
            if width < min_size or height < min_size:
                done.add(xref)
                continue
            pix = image_pixmap(doc, xref)
            if pix is None:
                done.add(xref)
                continue
            index += 1
            name = f"p{pno + 1:03d}-{index:02d}.png"
            path = os.path.join(out_dir, name)
            pix.save(path)
            done.add(xref)
            rows.append({
                "page": pno + 1,
                "file": name,
                "xref": xref,
                "width": width,
                "height": height,
                "smask": smask or "",
            })
            print(f"  p{pno + 1:03d} {width}x{height} -> {name}")
    return rows


def contact_sheet(rows: list[dict], out_dir: str) -> str:
    cards = []
    for r in rows:
        cards.append(
            f'<figure><img src="{html.escape(r["file"])}" loading="lazy">'
            f'<figcaption>стр. {r["page"]} · {r["width"]}×{r["height"]}'
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
                    help="минимальная сторона картинки в пикселях (300)")
    ap.add_argument("--share", type=float, default=0.5,
                    help="доля страниц, с которой картинка считается текстурой")
    ap.add_argument("--keep-repeated", action="store_true",
                    help="не выкидывать повторяющиеся картинки")
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

    rows = extract(args.pdf, args.out, args.min_size, args.share, pages,
                   args.keep_repeated)
    with open(os.path.join(args.out, "report.csv"), "w", newline="",
              encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["page", "file", "xref",
                                                "width", "height", "smask"])
        writer.writeheader()
        writer.writerows(rows)
    if not args.no_html:
        contact_sheet(rows, args.out)
    print(f"готово: {len(rows)} картинок в {args.out}/")
    if not rows:
        print("ничего не нашлось — попробуй --min-size 100 --keep-repeated",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
