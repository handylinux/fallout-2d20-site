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
import json
import os
import re
import sys

try:
    import pymupdf
except ImportError:  # pragma: no cover - dependency hint
    print("нужен pymupdf: python3 -m pip install pymupdf pillow", file=sys.stderr)
    raise SystemExit(2)


WEAPONS_JSON = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "companion", "i18n", "ru-RU", "data", "equipment", "weapons",
    "weapons.json")


# Подтверждённое различие между заголовком книги и названием Companion.
ALIASES = {"пистолетинъектор": "weapon_pistol_injector",
           "стенинъектор": "weapon_sten_injector"}


def normalize_name(text: str) -> str:
    """«БОЕВОЙ КАРАБИН» и «Боевой карабин» -> «боевойкарабин».

    Пробелы и дефисы выкидываются: Publisher рвёт заголовок на куски по
    кернингу («ДВУСТВОЛЬНЫЙ ДРОБОВИ» + «К»), и склеивать их с пробелами
    нельзя. Для сравнения с weapons.json это не мешает.
    """
    text = (text or "").casefold().replace("ё", "е")
    return re.sub(r"[^0-9a-zа-я]+", "", text)


def slug_of(weapon_id: str) -> str:
    """weapon_10mm_pistol -> 10mm-pistol (как в tools/weapons2cards.py)."""
    name = weapon_id[len("weapon_"):] if weapon_id.startswith("weapon_") \
        else weapon_id
    return name.replace("_", "-")


def match_weapon(title: str, weapons: dict[str, str]) -> str:
    key = normalize_name(title)
    if not key:
        return ""
    if key in weapons:
        return weapons[key]
    if key in ALIASES:
        return ALIASES[key]
    return ""


def load_weapons(path: str | None) -> dict[str, str]:
    if not path or not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    return {normalize_name(item.get("name") or ""): item["id"]
            for item in data if item.get("name")}


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


def page_title(page) -> str:
    """Самая крупная надпись в верхней части страницы — название оружия.

    Publisher рисует заголовок с трекингом, поэтому одна строка может прийти
    несколькими спанами («ДВУСТВОЛЬНЫЙ ДРОБОВИ» + «К»). Склеиваем спаны
    строки без разделителя и берём строку с самым крупным кеглем.
    """
    lines: list[tuple[float, str]] = []
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            spans = [s for s in line["spans"]
                     if (s["text"] or "").strip() and s["bbox"][1] <= 130]
            if not spans:
                continue
            spans.sort(key=lambda s: s["bbox"][0])
            size = max(round(s["size"], 1) for s in spans)
            text = "".join(s["text"] for s in spans)
            lines.append((size, text.strip()))
    if not lines:
        return ""
    top = max(size for size, _ in lines)
    return " ".join(text for size, text in lines if size >= top - 0.5).strip()


def image_pixmap(doc, xref: int, smask: int = 0):
    """Convert to RGB and apply the PDF soft mask if one exists."""
    pix = pymupdf.Pixmap(doc, xref)
    if pix.colorspace is None:
        return None
    if pix.colorspace.n != 3:
        pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
    if smask:
        if pix.alpha:
            pix = pymupdf.Pixmap(pix, 0)
        mask = pymupdf.Pixmap(doc, smask)
        pix = pymupdf.Pixmap(pix, mask)
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
            name_from_page: bool = True,
            min_area: int = 60000) -> list[dict]:
    doc = pymupdf.open(pdf)
    page_ids = [p - 1 for p in pages] if pages else list(range(doc.page_count))
    skip = set() if keep_repeated else repeated_xrefs(doc, page_ids, share)
    weapons = weapons or {}
    os.makedirs(out_dir, exist_ok=True)

    rows: list[dict] = []
    done: set[int] = set()
    used_names: set[str] = set()
    for pno in page_ids:
        if not 0 <= pno < doc.page_count:
            continue
        page = doc[pno]
        title = page_title(page) if name_from_page else ""
        weapon_id = match_weapon(title, weapons)
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
            if min(width, height) < min_size or width * height < min_area:
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
            suffix = index
            while name in used_names:  # two pages of the same weapon
                suffix += 1
                name = f"{base}-{suffix}.png"
            used_names.add(name)
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
    ap.add_argument("--min-size", type=int, default=100,
                    help="минимальная сторона картинки в пикселях (100)")
    ap.add_argument("--min-area", type=int, default=60000,
                    help="минимальная площадь картинки в пикселях (60000)")
    ap.add_argument("--share", type=float, default=0.5,
                    help="доля страниц, с которой картинка считается текстурой")
    ap.add_argument("--keep-repeated", action="store_true",
                    help="не выкидывать повторяющиеся картинки")
    ap.add_argument("--weapons", default=WEAPONS_JSON,
                    help="weapons.json компаньона для имён по названию страницы")
    ap.add_argument("--no-page-names", action="store_true",
                    help="не читать название со страницы, оставить pNNN-01.png")
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
    if not args.no_page_names and not weapons:
        print("weapons.json не найден — имена будут вида p018-01.png",
              file=sys.stderr)
    rows = extract(args.pdf, args.out, args.min_size, args.share, pages,
                   args.keep_repeated, weapons, not args.no_page_names,
                   args.min_area)
    with open(os.path.join(args.out, "report.csv"), "w", newline="",
              encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["page", "file", "title",
                                                "weapon_id", "xref", "width",
                                                "height", "smask"])
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
