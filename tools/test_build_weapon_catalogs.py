"""Tests for the single-command synchronized weapon catalogue release."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import build_weapon_catalogs as release


ROOT = Path(__file__).resolve().parent.parent
PUBLISHER = ROOT / "Справочник оружия.pdf"


class SynchronizedCatalogueReleaseTests(unittest.TestCase):
    def test_unapproved_source_fails_before_any_build_output_is_created(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "different-publisher-export.pdf"
            source.write_bytes(b"not the approved Publisher PDF")
            output = root / "published"
            with self.assertRaisesRegex(release.CatalogReleaseError, "SHA-256"):
                release.build_catalogues(source, output, root / "report.md")
            self.assertFalse(output.exists())

    def test_orchestrator_uses_one_manifest_and_publishes_a_complete_pair_in_order(self):
        """The launcher owns the otherwise easy-to-forget sequencing details."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "Справочник оружия.pdf"
            source.write_bytes(b"approved fixture")
            output = root / "published"
            report = root / "review" / release.RUSSIAN_REPORT
            output.mkdir()
            # Seed a previous release to exercise replacement rather than just
            # writing into an empty directory.
            for name in release.PUBLISHED_ARTIFACTS:
                (output / name).write_bytes(b"old-" + name.encode("utf-8"))
            report.parent.mkdir()
            report.write_text("old report", encoding="utf-8")
            events: list[str] = []

            def fake_extract(source_path: Path, artwork_dir: Path) -> Path:
                events.append("extract")
                self.assertEqual(source_path, source)
                artwork_dir.mkdir(parents=True)
                manifest = artwork_dir / "artwork-manifest.json"
                manifest.write_text("{}", encoding="utf-8")
                return manifest

            def fake_russian(source_path: Path, vector: Path, **kwargs):
                events.append("russian")
                self.assertEqual(source_path, source)
                self.assertEqual(kwargs["artwork_manifest"].name, "artwork-manifest.json")
                self.assertEqual(kwargs["artwork_root"], kwargs["artwork_manifest"].parent)
                self.assertFalse(kwargs["rasterize_cover"])
                self.assertEqual(kwargs["report"].name, release.RUSSIAN_REPORT)
                vector.write_bytes(b"new-russian-vector")
                kwargs["artwork_coverage"].write_text("{}", encoding="utf-8")
                kwargs["report"].write_text("new Russian review report", encoding="utf-8")
                return {"pages": 176, "toc_pages": 2, "cover": {"rasterized": False}}

            def fake_english(source_path: Path, vector: Path, **kwargs):
                events.append("english")
                self.assertEqual(source_path, source)
                self.assertEqual(kwargs["artwork_manifest"].name, "artwork-manifest.json")
                self.assertEqual(kwargs["artwork_root"], kwargs["artwork_manifest"].parent)
                vector.write_bytes(b"new-english-vector")
                kwargs["artwork_coverage"].write_text("{}", encoding="utf-8")
                return {"pages": 180, "cards": 144, "toc_pages": 2, "outline_entries": 160}

            def fake_raster(source_path: Path, mobile: Path, **kwargs):
                locale = kwargs["metadata_locale"]
                events.append(f"mobile:{locale}")
                self.assertEqual(kwargs["dpi"], release.rasterize_pdf.DEFAULT_DPI)
                self.assertEqual(kwargs["jpeg_quality"],
                                 release.rasterize_pdf.DEFAULT_JPEG_QUALITY)
                mobile.write_bytes(f"new-{locale}-mobile".encode("ascii"))
                return {
                    "pages": 176 if locale == "ru" else 180,
                    "dpi": kwargs["dpi"],
                    "jpeg_quality": kwargs["jpeg_quality"],
                    "metadata_locale": locale,
                }

            def fake_validate(staging: Path):
                events.append("validate")
                self.assertTrue(all((staging / name).is_file()
                                    for name in release.PUBLISHED_ARTIFACTS))
                return {
                    "validated": True,
                    "sha256": {name: f"fake-{name}" for name in release.PUBLISHED_ARTIFACTS},
                }

            with mock.patch.object(release, "_validate_source") as source_guard, \
                    mock.patch.object(release, "_extract_artwork", side_effect=fake_extract), \
                    mock.patch.object(release.russian, "build", side_effect=fake_russian), \
                    mock.patch.object(release.english, "build", side_effect=fake_english), \
                    mock.patch.object(release.rasterize_pdf, "rasterize_pdf", side_effect=fake_raster), \
                    mock.patch.object(release, "validate_release", side_effect=fake_validate):
                result = release.build_catalogues(source, output, report)

            source_guard.assert_called_once_with(source)
            self.assertEqual(events, [
                "extract", "russian", "english", "mobile:ru", "mobile:en", "validate",
            ])
            self.assertTrue(result["validation"]["validated"])
            self.assertEqual(result["russian"]["vector"]["output"],
                             str(output / release.RUSSIAN_VECTOR))
            self.assertEqual(result["english"]["vector"]["output"],
                             str(output / release.ENGLISH_VECTOR))
            self.assertEqual(result["mobile"]["english"]["metadata_locale"], "en")
            self.assertEqual(result["report"]["output"], str(report))
            self.assertTrue(result["report"]["sha256"])
            self.assertEqual((output / release.RUSSIAN_VECTOR).read_bytes(),
                             b"new-russian-vector")
            self.assertEqual((output / release.ENGLISH_VECTOR).read_bytes(),
                             b"new-english-vector")
            self.assertEqual((output / release.RUSSIAN_MOBILE).read_bytes(),
                             b"new-ru-mobile")
            self.assertEqual((output / release.ENGLISH_MOBILE).read_bytes(),
                             b"new-en-mobile")
            self.assertEqual(report.read_text(encoding="utf-8"), "new Russian review report")

    @unittest.skipUnless(PUBLISHER.is_file(), "Publisher source is not present")
    def test_fresh_pair_meets_the_release_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = release.build_catalogues(PUBLISHER, root / "books", root / "report.md")["validation"]
        self.assertEqual(result["pages"], {"ru": 176, "en": 180})
        self.assertEqual(result["cards"], release.EXPECTED_CARDS)
        self.assertEqual(result["artwork"], release.EXPECTED_ARTWORK_COUNTS)
        self.assertEqual(set(result["sha256"]), set(release.PUBLISHED_ARTIFACTS))


if __name__ == "__main__":
    unittest.main()
