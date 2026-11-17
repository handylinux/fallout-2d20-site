#!/usr/bin/env python3
"""Create a raster-only PDF compatibility edition.

The source PDF is rendered normally first, then each *complete page* is stored
as one opaque RGB JPEG.  This is deliberately different from flattening an
individual transparent weapon PNG: the Publisher affine transform, crop,
alpha and the page background have already been composited by the source PDF
renderer before the page is rasterised.  The resulting PDF has no selectable
text, font resources, vector drawings, transparent image masks, or separately
transformable artwork layers on its pages.

It is intended as a fallback for PDF viewers which incorrectly compose image
layers.  Keep the vector source PDF as the canonical, print-quality edition.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

import pymupdf

DEFAULT_DPI = 200
DEFAULT_JPEG_QUALITY = 85


class RasterPdfError(ValueError):
    """Raised when a requested raster PDF cannot meet its content contract."""


def sha256_file(path: Path) -> str:
    """Return the SHA-256 of *path* without loading the whole file at once."""
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_settings(dpi: int, jpeg_quality: int) -> None:
    if dpi < 72:
        raise RasterPdfError("DPI должен быть не меньше 72")
    if not 1 <= jpeg_quality <= 100:
        raise RasterPdfError("Качество JPEG должно быть от 1 до 100")


def assert_raster_only(path: Path) -> int:
    """Validate the raster-only page-content promise and return page count.

    A page may have exactly one JPEG image and nothing that can render as text,
    vector graphics, a form XObject, an annotation, or a separate alpha mask.
    Metadata is intentionally outside this per-page content contract.
    """
    with pymupdf.open(path) as document:
        if document.needs_pass:
            raise RasterPdfError("Нельзя проверить защищённый паролем PDF")
        pages = document.page_count
        if pages == 0:
            raise RasterPdfError("Растровый PDF не содержит страниц")
        for number, page in enumerate(document, start=1):
            # rawdict includes the one expected image as a type-1 block.  Only
            # type-0 blocks are text, so do not mistake that page image for
            # selectable text content.
            if any(block.get("type") == 0 for block in page.get_text("rawdict")["blocks"]):
                raise RasterPdfError(f"Страница {number}: найден текстовый блок")
            if page.get_fonts(full=True):
                raise RasterPdfError(f"Страница {number}: найдены шрифтовые ресурсы")
            if page.get_drawings():
                raise RasterPdfError(f"Страница {number}: найдена векторная графика")
            if page.get_xobjects():
                raise RasterPdfError(f"Страница {number}: найден form XObject")
            if page.first_annot is not None:
                raise RasterPdfError(f"Страница {number}: найдена аннотация")
            images = page.get_images(full=True)
            if len(images) != 1:
                raise RasterPdfError(
                    f"Страница {number}: ожидается ровно один JPEG, получено {len(images)}"
                )
            image = images[0]
            # Tuple item 1 is the /SMask xref. It must be zero for an opaque
            # JPEG; extract_image is checked too because it reads the object.
            if image[1]:
                raise RasterPdfError(f"Страница {number}: у JPEG есть alpha-маска")
            extracted = document.extract_image(image[0])
            if extracted.get("ext") not in {"jpeg", "jpg"}:
                raise RasterPdfError(
                    f"Страница {number}: ожидается JPEG, получен {extracted.get('ext')!r}"
                )
            if extracted.get("smask", 0):
                raise RasterPdfError(f"Страница {number}: у JPEG есть SMask")
    return pages


def rasterize_pdf(
    source: Path | str,
    output: Path | str,
    *,
    dpi: int = DEFAULT_DPI,
    jpeg_quality: int = DEFAULT_JPEG_QUALITY,
) -> dict[str, Any]:
    """Render every source page into one opaque JPEG in a new PDF.

    The output is written atomically only after ``assert_raster_only`` verifies
    it.  All page geometry and order are retained, but bookmarks, text layers,
    annotations and other interactive/vector PDF features intentionally are not.
    """
    source = Path(source)
    output = Path(output)
    _validate_settings(dpi, jpeg_quality)
    if not source.is_file():
        raise RasterPdfError(f"Не найден исходный PDF: {source}")
    if source.resolve() == output.resolve():
        raise RasterPdfError("Выходной файл не может совпадать с исходным PDF")

    output.parent.mkdir(parents=True, exist_ok=True)
    source_sha256 = sha256_file(source)
    temp_handle = tempfile.NamedTemporaryFile(
        prefix=f".{output.stem}.", suffix=".pdf", dir=output.parent, delete=False
    )
    temp_path = Path(temp_handle.name)
    temp_handle.close()
    # PyMuPDF writes a new file and expects that destination not to exist.
    temp_path.unlink()

    try:
        with pymupdf.open(source) as source_document:
            if source_document.needs_pass:
                raise RasterPdfError("Исходный PDF защищён паролем")
            if source_document.page_count == 0:
                raise RasterPdfError("Исходный PDF не содержит страниц")
            raster_document = pymupdf.open()
            try:
                for source_page in source_document:
                    # alpha=False is applied only after the *whole page* has
                    # been rendered, so source artwork transparency is first
                    # composed correctly against its actual page background.
                    pixmap = source_page.get_pixmap(
                        dpi=dpi, colorspace=pymupdf.csRGB, alpha=False, annots=True
                    )
                    jpeg = pixmap.tobytes("jpeg", jpg_quality=jpeg_quality)
                    page = raster_document.new_page(
                        width=source_page.rect.width, height=source_page.rect.height
                    )
                    page.insert_image(page.rect, stream=jpeg, keep_proportion=False)
                raster_document.set_metadata(
                    {
                        "title": "Справочник оружия — мобильная растровая версия",
                        "author": "handylinux/fallout-2d20-site",
                        "subject": (
                            f"Одна непрозрачная RGB JPEG-страница на лист; {dpi} DPI, "
                            f"JPEG quality {jpeg_quality}"
                        ),
                        "keywords": "Fallout 2d20, оружие, мобильная совместимость, raster",
                        "creator": "tools/rasterize_pdf.py",
                        "producer": "PyMuPDF",
                    }
                )
                raster_document.save(
                    temp_path,
                    garbage=4,
                    clean=True,
                    deflate=True,
                    deflate_images=True,
                    use_objstms=1,
                    no_new_id=True,
                )
            finally:
                raster_document.close()

        pages = assert_raster_only(temp_path)
        os.replace(temp_path, output)
    finally:
        if temp_path.exists():
            temp_path.unlink()

    return {
        "pages": pages,
        "dpi": dpi,
        "jpeg_quality": jpeg_quality,
        "source": str(source),
        "source_sha256": source_sha256,
        "output": str(output),
        "output_bytes": output.stat().st_size,
        "output_sha256": sha256_file(output),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="исходный PDF с финальной вёрсткой")
    parser.add_argument("--out", type=Path, required=True, help="путь к raster-only PDF")
    parser.add_argument("--dpi", type=int, default=DEFAULT_DPI,
                        help=f"разрешение рендеринга (по умолчанию {DEFAULT_DPI})")
    parser.add_argument("--jpeg-quality", type=int, default=DEFAULT_JPEG_QUALITY,
                        help=f"качество JPEG от 1 до 100 (по умолчанию {DEFAULT_JPEG_QUALITY})")
    args = parser.parse_args()
    print(json.dumps(
        rasterize_pdf(args.source, args.out, dpi=args.dpi, jpeg_quality=args.jpeg_quality),
        ensure_ascii=False,
        indent=2,
    ))


if __name__ == "__main__":
    main()
