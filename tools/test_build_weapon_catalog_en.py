"""Tests for the English catalogue assembler."""

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image
import pymupdf

import build_weapon_catalog_en as catalog
import weapon2pdf as w


class EnglishCatalogBuildTests(unittest.TestCase):
    def test_catalog_uses_english_labels_outline_and_exact_id_artwork(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "publisher.pdf"
            source.write_bytes(b"exact-Publisher-source-fixture")
            asset = root / "art.png"
            Image.new("RGBA", (20, 10), (180, 40, 20, 200)).save(asset)
            manifest = root / "artwork-manifest.json"
            manifest.write_text(json.dumps({
                "schema": w.ARTWORK_MANIFEST_SCHEMA,
                "coordinate_system": {"unit": "point", "origin": "bottom-left"},
                "source": {"sha256": hashlib.sha256(source.read_bytes()).hexdigest()},
                "pages": [{
                    "number": 14,
                    "weapon_id": "weapon_10mm_pistol",
                    "size_points": [600, 850],
                    "placements": [{
                        "xref": 265,
                        "draw_order": 4,
                        "matrix_pdf": [100, -20, 10, 80, 40, 500],
                        "clip_paths": [],
                        "graphics_state": {
                            "fill_alpha": 1, "stroke_alpha": 1,
                            "blend_mode": "Normal", "soft_mask": None,
                            "transfer_function": None,
                        },
                        "asset": "art.png",
                    }],
                }],
            }), encoding="utf-8")
            output = root / "english.pdf"
            result = catalog.build(source, output, artwork_manifest=manifest,
                                   artwork_root=root)
            self.assertEqual(result["pages"], 146)
            self.assertEqual(result["cards"], 146)
            self.assertEqual(result["outline_entries"], 154)
            self.assertEqual(result["artwork"]["counts"], {
                "no-manifest-page": 145, "replayed": 1,
            })
            with pymupdf.open(output) as document:
                self.assertEqual(document.page_count, 146)
                outline = document.get_toc(simple=True)
                self.assertEqual(outline[0], [1, "Light Weapons", 1])
                self.assertEqual(outline[1], [2, ".357 Magnum Revolver", 1])
                self.assertIn([2, "10mm Pistol", 3], outline)
                text = document[0].get_text()
                self.assertIn("Weight:", text)
                self.assertIn("DAMAGE", text)
                self.assertIn("SUPPORTED MODIFICATIONS", text)
                self.assertNotIn("Вес:", text)
                self.assertNotIn("ПОДДЕРЖИВАЕМЫЕ", text)

                # The exact-ID match is page 3 in English ordering. It retains
                # the manifest matrix; page 1 must not borrow it by position.
                self.assertFalse(any(item["width"] == 20 and item["height"] == 10
                                     for item in document[0].get_image_info(xrefs=True)))
                art = next(item for item in document[2].get_image_info(xrefs=True)
                           if item["width"] == 20 and item["height"] == 10)
                expected = (100, 20, -10, 80, 50, 270)
                for actual, wanted in zip(art["transform"], expected):
                    self.assertAlmostEqual(actual, wanted, places=3)


if __name__ == "__main__":
    unittest.main()
