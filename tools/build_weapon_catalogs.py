#!/usr/bin/env python3
"""Build, validate, and publish the synchronized Russian and English catalogues.

This is the canonical release entry point.  It regenerates exact Publisher
artwork extraction in a temporary directory, builds both vector catalogues,
creates their mobile raster editions, validates the shared 144-card inventory,
and only then replaces the six published artifacts.

Run from the repository root:

    python3 tools/build_weapon_catalogs.py

The checked-in Publisher PDF hash, exact artwork manifest hash, inventory, and
cover policies are deliberate release constraints.  A different source export
must be reviewed and the constants below intentionally updated rather than
silently becoming a new catalogue source.
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

import build_weapon_catalog as russian
import build_weapon_catalog_en as english
import extract_pdf_images as extractor
import rasterize_pdf

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE = ROOT / "Справочник оружия.pdf"
DEFAULT_OUTPUT_DIR = ROOT / "docs" / "render" / "samples"

# The source and manifest are pinned so a future release cannot accidentally
# mix another Publisher export with the approved catalogue artwork provenance.
EXPECTED_SOURCE_SHA256 = "48c85e12c5eca695e0c4a4fc3a8bf9276d4fb1d1715b6a62f4b0f9c26ffdbd35"
EXPECTED_MANIFEST_SHA256 = "77e8ef9a4a8097ee7a6248d97373a5368e895648d1d5af1c33de752dab9df1a2"
EXPECTED_ARTWORK_ASSETS = 81
EXPECTED_ARTWORK_COUNTS = {
    "manifest-page-without-exported-artwork": 6,
    "no-manifest-page": 61,
    "replayed": 77,
}
EXPECTED_CARDS = 144
EXPECTED_RUSSIAN_PAGES = 176
EXPECTED_ENGLISH_PAGES = 180
EXPECTED_ENGLISH_METADATA = {
    "title": "Fallout 2d20 Wasteland Arsenal — English Edition",
    "creator": "tools/build_weapon_catalog_en.py",
}
EXPECTED_MOBILE_METADATA = {
    "ru": {
        "title": "Справочник оружия — мобильная растровая версия",
        "creator": "tools/rasterize_pdf.py",
    },
    "en": {
        "title": "Fallout 2d20 Weapon Catalog — Mobile Raster Edition",
        "creator": "tools/rasterize_pdf.py",
    },
}

# These are the confirmed non-weapon records.  The same inventory must be used
# by the Russian and English editions; Unarmed Attack and Assaultron Head Laser
# are explicitly retained as independent cards.
EXCLUDED_WEAPON_IDS = frozenset({
    "weapon_assaultron_head",
    "weapon_straight_razor",
})
REQUIRED_WEAPON_STATUSES = {
    "weapon_assaultron_head_laser": "replayed",
    "weapon_institute_laser": "no-manifest-page",
    "weapon_unarmed_attack": "no-manifest-page",
}

RUSSIAN_VECTOR = "book-weapon-catalog.pdf"
RUSSIAN_MOBILE = "book-weapon-catalog-mobile-raster.pdf"
RUSSIAN_COVERAGE = "book-weapon-catalog-artwork-coverage.json"
# This review report is intentionally ignored: it is regenerated on every
# release and records source-data diagnostics that are useful to the publisher
# but are not a public artifact.
RUSSIAN_REPORT = "book-weapon-catalog-report.md"
DEFAULT_REPORT = ROOT / "docs" / "render" / "out" / RUSSIAN_REPORT
ENGLISH_VECTOR = "book-weapon-catalog-en.pdf"
ENGLISH_MOBILE = "book-weapon-catalog-en-mobile-raster.pdf"
ENGLISH_COVERAGE = "book-weapon-catalog-en-artwork-coverage.json"
PUBLISHED_ARTIFACTS = (
    RUSSIAN_VECTOR,
    RUSSIAN_MOBILE,
    RUSSIAN_COVERAGE,
    ENGLISH_VECTOR,
    ENGLISH_MOBILE,
    ENGLISH_COVERAGE,
)


class CatalogReleaseError(RuntimeError):
    """The synchronized release does not meet an approved catalogue contract."""


def sha256_file(path: Path) -> str:
    """Return the SHA-256 digest for a file without loading it all at once."""
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CatalogReleaseError(message)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CatalogReleaseError(f"Cannot read JSON audit {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise CatalogReleaseError(f"JSON audit must be an object: {path}")
    return value


def _validate_source(source: Path) -> None:
    _require(source.is_file(), f"Publisher source PDF is missing: {source}")
    actual = sha256_file(source)
    _require(
        actual == EXPECTED_SOURCE_SHA256,
        "Publisher source SHA-256 differs from the approved export; review the "
        "source and intentionally update the release contract before publishing "
        f"(expected {EXPECTED_SOURCE_SHA256}, got {actual}).",
    )


def _extract_artwork(source: Path, artwork_dir: Path) -> Path:
    """Regenerate the exact extraction used by both editions in staging."""
    artwork_dir.mkdir(parents=True, exist_ok=True)
    titles = extractor.load_weapons(extractor.WEAPONS_JSON)
    _require(bool(titles), f"Cannot load Publisher title mappings: {extractor.WEAPONS_JSON}")
    titles.update(extractor.load_title_aliases(extractor.TITLE_ALIASES_JSON))
    rows = extractor.extract(
        str(source), str(artwork_dir), 300, 0.5, None, False, titles, True
    )
    _require(
        len(rows) == EXPECTED_ARTWORK_ASSETS,
        f"Expected {EXPECTED_ARTWORK_ASSETS} exported Publisher artwork assets, got {len(rows)}",
    )
    manifest = extractor.artwork_manifest(str(source), rows, None, titles, True)
    manifest_path = artwork_dir / "artwork-manifest.json"
    extractor.write_artwork_manifest(manifest, str(manifest_path))
    _require(
        sha256_file(manifest_path) == EXPECTED_MANIFEST_SHA256,
        "Regenerated Publisher artwork manifest differs from the approved "
        "extraction; inspect the source/extractor before publishing.",
    )
    return manifest_path


def _coverage(path: Path, edition: str) -> dict[str, Any]:
    coverage = _read_json(path)
    _require(coverage.get("enabled") is True, f"{edition}: artwork coverage is disabled")
    _require(
        coverage.get("counts") == EXPECTED_ARTWORK_COUNTS,
        f"{edition}: unexpected artwork coverage counts: {coverage.get('counts')!r}",
    )
    manifest = coverage.get("manifest")
    _require(isinstance(manifest, dict), f"{edition}: artwork coverage has no manifest")
    _require(
        manifest.get("sha256") == EXPECTED_MANIFEST_SHA256,
        f"{edition}: artwork coverage refers to an unapproved manifest",
    )
    source = manifest.get("source")
    _require(
        isinstance(source, dict) and source.get("sha256") == EXPECTED_SOURCE_SHA256,
        f"{edition}: artwork coverage refers to an unapproved Publisher source",
    )
    weapons = coverage.get("weapons")
    _require(isinstance(weapons, dict), f"{edition}: coverage has no weapon map")
    _require(
        len(weapons) == EXPECTED_CARDS,
        f"{edition}: coverage records {len(weapons)} cards, expected {EXPECTED_CARDS}",
    )
    _require(
        not (EXCLUDED_WEAPON_IDS & set(weapons)),
        f"{edition}: excluded non-weapons are still present: "
        f"{sorted(EXCLUDED_WEAPON_IDS & set(weapons))}",
    )
    for weapon_id, status in REQUIRED_WEAPON_STATUSES.items():
        record = weapons.get(weapon_id)
        _require(
            isinstance(record, dict) and record.get("status") == status,
            f"{edition}: {weapon_id} must have artwork status {status!r}",
        )
    return coverage


def _toc_lines(document: pymupdf.Document, pages: tuple[int, ...]) -> list[str]:
    return [
        line.strip()
        for number in pages
        for line in document[number - 1].get_text().splitlines()
        if line.strip()
    ]


def _validate_contents(document: pymupdf.Document, title: str,
                       sections: dict[str, tuple[str, ...]]) -> list[list]:
    """Require the printed map, bookmarks and modification-page headings to agree."""
    lines = _toc_lines(document, (4, 5))
    _require(lines.count(title) == 2, f"Missing printed {title} on pages 4–5")
    printed = [line for line in lines if line != title and line.replace(" ", "").strip(".")]
    outline = document.get_toc(simple=True)
    targets = [page for _, _, page in outline]
    _require(printed == [value for _, name, page in outline for value in (name, str(page))],
             f"Printed {title} differs from PDF bookmarks")
    _require(targets == sorted(targets), f"{title} jumps backwards between chapters")
    chapter = None
    found = {name: [] for name in sections}
    mod_headings = {heading for headings in sections.values() for heading in headings}
    for level, name, page in outline:
        if level == 1:
            chapter = name
        if name in mod_headings:
            _require(level == 2 and chapter in sections,
                     f"{name!r} is not nested under a weapon chapter")
            _require(name in document[page - 1].get_text(),
                     f"{name!r} does not start on its advertised page {page}")
            found[chapter].append(name)
    _require(all(found[name] == list(headings) for name, headings in sections.items()),
             f"Incorrect modification subsections in {title}: {found}")
    return outline


def _validate_layered_cover(page: pymupdf.Page, locale: str) -> None:
    kind, group = page.parent.xref_get_key(page.xref, "Group")
    _require(kind == "dict" and "/Transparency" in group,
             f"{locale} cover is missing its Publisher transparency group")
    _require(any(image[1] for image in page.get_images(full=True)),
             f"{locale} cover is missing its soft masks (SMask)")
    _require(len(page.get_drawings()) == 5,
             f"{locale} cover does not preserve the original rules and panels")


def _validate_russian(vector: Path) -> None:
    with pymupdf.open(vector) as document:
        _require(document.page_count == EXPECTED_RUSSIAN_PAGES,
                 f"Russian catalogue has {document.page_count} pages, expected {EXPECTED_RUSSIAN_PAGES}")
        _validate_layered_cover(document[0], "Russian")
        _require("РУКОВОДСТВО БРАТСТВА" in document[0].get_text(),
                 "Russian Publisher cover text is missing")
        outline = _validate_contents(document, "ОГЛАВЛЕНИЕ", {
            "СТРЕЛКОВОЕ ОРУЖИЕ": ("МОДИФИКАЦИИ СТРЕЛКОВОГО ОРУЖИЯ",),
            "ЭНЕРГЕТИЧЕСКОЕ ОРУЖИЕ": (
                "МОДИФИКАЦИИ ЭНЕРГЕТИЧЕСКОГО ОРУЖИЯ",
                russian.TITLES["energy"],
            ),
        })
        lines = [name for _, name, _ in outline]
        for title in ("Рукопашная атака", "Головной лазер Штурмотрона", "Мугнумномикон"):
            _require(title in lines, f"Russian printed TOC is missing {title!r}")
        for title in ("Голова ассаултрона", "Опасная бритва", "Магнумномикон"):
            _require(title not in lines, f"Russian printed TOC unexpectedly contains {title!r}")
        text = "".join(page.get_text() for page in document)
        _require("РУКОПАШНАЯ АТАКА" in text, "Russian Unarmed Attack card is missing")
        _require("ГОЛОВНОЙ ЛАЗЕР ШТУРМОТРОНА" in text,
                 "Russian Assaultron Head Laser card is missing")


def _validate_english(vector: Path) -> None:
    with pymupdf.open(vector) as document:
        _require(document.page_count == EXPECTED_ENGLISH_PAGES,
                 f"English catalogue has {document.page_count} pages, expected {EXPECTED_ENGLISH_PAGES}")
        cover_page = document[0]
        _validate_layered_cover(cover_page, "English")
        cover = cover_page.get_text()
        _require("BROTHERHOOD FIELD GUIDE" in cover and "WASTELAND ARSENAL" in cover,
                 "English localised cover text is missing")
        _require(not english._has_cyrillic(cover), "English cover still contains Russian text")
        for key, expected in EXPECTED_ENGLISH_METADATA.items():
            _require(document.metadata.get(key) == expected,
                     f"English canonical metadata {key!r} is not {expected!r}")
        outline = _validate_contents(document, "TABLE OF CONTENTS", {
            "SMALL GUNS": ("SMALL GUNS MODIFICATIONS", "SMALL GUNS — SPECIFIC MODIFICATIONS"),
            "HEAVY GUNS": ("HEAVY GUNS — SPECIFIC MODIFICATIONS",),
            "ENERGY GUNS": ("ENERGY GUNS MODIFICATIONS", "ENERGY GUNS — SPECIFIC MODIFICATIONS"),
            "MELEE WEAPONS": ("MELEE WEAPONS MODIFICATIONS",),
        })
        titles = [title for _level, title, _page in outline]
        _require(len(outline) == 160, f"English outline has {len(outline)} entries, expected 160")
        for title in ("Assaultron Head", "Straight Razor", "OTHER WEAPONS", "WEAPON MODIFICATIONS",
                      "HEAVY GUNS MODIFICATIONS", "UNARMED WEAPONS MODIFICATIONS"):
            _require(title not in titles, f"English outline unexpectedly contains {title!r}")
        for title, page in (("Assaultron Head Laser", 86), ("Institute Laser", 95),
                            ("Unarmed Attack", 173)):
            _require([2, title, page] in outline,
                     f"English outline is missing {title!r} on page {page}")


def _validate_mobile_metadata(path: Path, locale: str) -> None:
    """Make a mobile PDF's viewer metadata agree with its content locale."""
    with pymupdf.open(path) as document:
        for key, expected in EXPECTED_MOBILE_METADATA[locale].items():
            _require(document.metadata.get(key) == expected,
                     f"{locale} mobile metadata {key!r} is not {expected!r}")


def validate_release(output_dir: Path | str = DEFAULT_OUTPUT_DIR) -> dict[str, Any]:
    """Validate a complete paired publication without changing any files."""
    output_dir = Path(output_dir)
    paths = {name: output_dir / name for name in PUBLISHED_ARTIFACTS}
    missing = [str(path) for path in paths.values() if not path.is_file()]
    _require(not missing, "Published catalogue artifacts are missing: " + ", ".join(missing))

    russian_coverage = _coverage(paths[RUSSIAN_COVERAGE], "Russian")
    english_coverage = _coverage(paths[ENGLISH_COVERAGE], "English")
    _require(
        russian_coverage["weapons"] == english_coverage["weapons"],
        "Russian and English artwork inventories diverge",
    )
    _validate_russian(paths[RUSSIAN_VECTOR])
    _validate_english(paths[ENGLISH_VECTOR])
    _require(
        rasterize_pdf.assert_raster_only(paths[RUSSIAN_MOBILE]) == EXPECTED_RUSSIAN_PAGES,
        "Russian mobile catalogue does not meet the raster-only contract",
    )
    _require(
        rasterize_pdf.assert_raster_only(paths[ENGLISH_MOBILE]) == EXPECTED_ENGLISH_PAGES,
        "English mobile catalogue does not meet the raster-only contract",
    )
    _validate_mobile_metadata(paths[RUSSIAN_MOBILE], "ru")
    _validate_mobile_metadata(paths[ENGLISH_MOBILE], "en")
    return {
        "pages": {"ru": EXPECTED_RUSSIAN_PAGES, "en": EXPECTED_ENGLISH_PAGES},
        "cards": EXPECTED_CARDS,
        "artwork": EXPECTED_ARTWORK_COUNTS,
        "sha256": {name: sha256_file(path) for name, path in paths.items()},
    }


def _publish(staging: Path, output_dir: Path, report_output: Path) -> None:
    """Replace a validated release and its Russian review report together.

    Each individual ``os.replace`` call is atomic.  The backup-and-rollback
    guard keeps a filesystem failure from leaving an old Russian report beside
    a new book pair (or a mixture of old and new published artifacts).
    """
    targets = [(staging / name, output_dir / name) for name in PUBLISHED_ARTIFACTS]
    targets.append((staging / RUSSIAN_REPORT, report_output))
    resolved = [target.resolve() for _staged, target in targets]
    _require(len(set(resolved)) == len(resolved),
             "Publication targets must be distinct")
    for staged, target in targets:
        _require(staged.is_file(), f"Staged publication artifact is missing: {staged}")
        target.parent.mkdir(parents=True, exist_ok=True)

    backup = staging / "previous-published-artifacts"
    backup.mkdir()
    moved_old: list[tuple[Path, Path]] = []
    published: list[Path] = []
    try:
        for index, (_staged, target) in enumerate(targets):
            if target.exists():
                previous = backup / f"{index:02d}-{target.name}"
                os.replace(target, previous)
                moved_old.append((previous, target))
        for staged, target in targets:
            os.replace(staged, target)
            published.append(target)
    except Exception:
        for target in published:
            if target.exists():
                target.unlink()
        for previous, target in moved_old:
            os.replace(previous, target)
        raise


def build_catalogues(source: Path | str = DEFAULT_SOURCE,
                     output_dir: Path | str = DEFAULT_OUTPUT_DIR,
                     report_output: Path | str = DEFAULT_REPORT) -> dict[str, Any]:
    """Stage and publish the approved RU/EN catalogue pair in release order."""
    source = Path(source)
    output_dir = Path(output_dir)
    report_output = Path(report_output)
    _validate_source(source)
    output_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix=".weapon-catalogues-", dir=output_dir) as work:
        staging = Path(work)
        artwork_dir = staging / "publisher-art"
        manifest = _extract_artwork(source, artwork_dir)

        russian_stats = russian.build(
            source,
            staging / RUSSIAN_VECTOR,
            report=staging / RUSSIAN_REPORT,
            artwork_manifest=manifest,
            artwork_root=artwork_dir,
            artwork_coverage=staging / RUSSIAN_COVERAGE,
            rasterize_cover=False,
        )
        english_stats = english.build(
            source,
            staging / ENGLISH_VECTOR,
            artwork_manifest=manifest,
            artwork_root=artwork_dir,
            artwork_coverage=staging / ENGLISH_COVERAGE,
        )
        russian_mobile = rasterize_pdf.rasterize_pdf(
            staging / RUSSIAN_VECTOR,
            staging / RUSSIAN_MOBILE,
            dpi=rasterize_pdf.DEFAULT_DPI,
            jpeg_quality=rasterize_pdf.DEFAULT_JPEG_QUALITY,
            metadata_locale="ru",
        )
        english_mobile = rasterize_pdf.rasterize_pdf(
            staging / ENGLISH_VECTOR,
            staging / ENGLISH_MOBILE,
            dpi=rasterize_pdf.DEFAULT_DPI,
            jpeg_quality=rasterize_pdf.DEFAULT_JPEG_QUALITY,
            metadata_locale="en",
        )
        validation = validate_release(staging)
        _require((staging / RUSSIAN_REPORT).is_file(),
                 "Russian build did not create its review report")
        _publish(staging, output_dir, report_output)

    artifact_hashes = validation["sha256"]
    return {
        "source": str(source),
        "source_sha256": sha256_file(source),
        "russian": {
            "pages": russian_stats["pages"],
            "toc_pages": russian_stats["toc_pages"],
            "vector": {
                "output": str(output_dir / RUSSIAN_VECTOR),
                "sha256": artifact_hashes[RUSSIAN_VECTOR],
            },
            "coverage": {
                "output": str(output_dir / RUSSIAN_COVERAGE),
                "sha256": artifact_hashes[RUSSIAN_COVERAGE],
            },
            "cover": {
                "rasterized": russian_stats["cover"]["rasterized"],
                "dpi": russian_stats["cover"].get("dpi"),
                "jpeg_quality": russian_stats["cover"].get("jpeg_quality"),
            },
        },
        "english": {
            "pages": english_stats["pages"],
            "cards": english_stats["cards"],
            "toc_pages": english_stats["toc_pages"],
            "outline_entries": english_stats["outline_entries"],
            "vector": {
                "output": str(output_dir / ENGLISH_VECTOR),
                "sha256": artifact_hashes[ENGLISH_VECTOR],
            },
            "coverage": {
                "output": str(output_dir / ENGLISH_COVERAGE),
                "sha256": artifact_hashes[ENGLISH_COVERAGE],
            },
        },
        "mobile": {
            "russian": {
                "pages": russian_mobile["pages"],
                "dpi": russian_mobile["dpi"],
                "jpeg_quality": russian_mobile["jpeg_quality"],
                "metadata_locale": russian_mobile["metadata_locale"],
                "output": str(output_dir / RUSSIAN_MOBILE),
                "sha256": artifact_hashes[RUSSIAN_MOBILE],
            },
            "english": {
                "pages": english_mobile["pages"],
                "dpi": english_mobile["dpi"],
                "jpeg_quality": english_mobile["jpeg_quality"],
                "metadata_locale": english_mobile["metadata_locale"],
                "output": str(output_dir / ENGLISH_MOBILE),
                "sha256": artifact_hashes[ENGLISH_MOBILE],
            },
        },
        "report": {
            "output": str(report_output),
            "sha256": sha256_file(report_output),
        },
        "validation": validation,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE,
                        help=f"approved Publisher source (default: {DEFAULT_SOURCE.name})")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUTPUT_DIR,
                        help="directory for the six published catalogue artifacts")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT,
                        help="Russian build review report (default: docs/render/out/...)")
    parser.add_argument("--check", action="store_true",
                        help="validate the existing paired publication without rebuilding it")
    args = parser.parse_args(argv)
    try:
        if args.check:
            _validate_source(args.source)
            result = validate_release(args.out_dir)
        else:
            result = build_catalogues(args.source, args.out_dir, args.report)
    except (CatalogReleaseError, OSError, RuntimeError, ValueError) as exc:
        parser.exit(1, f"Catalogue release failed: {exc}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
