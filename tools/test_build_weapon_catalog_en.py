"""Tests for the complete English weapon-book assembler."""

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
    @staticmethod
    def _publisher_fixture(path: Path) -> None:
        """Make a 106-page source-shaped PDF with numbered source footers."""
        document = pymupdf.open()
        try:
            for number in range(1, 107):
                page = document.new_page(width=w.PAGE_W, height=w.PAGE_H)
                # Match the source convention closely enough for the strict
                # renumbering code: one unique number below y=800.
                x = 39 if number % 2 == 0 else 546
                page.insert_text((x, 819), str(number), fontsize=9.96,
                                 fontname="helv", color=(0, 0, 0))
            document.save(path, garbage=4, deflate=True)
        finally:
            document.close()

    def test_complete_catalog_has_front_matter_references_toc_and_exact_id_artwork(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "publisher.pdf"
            self._publisher_fixture(source)
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
            coverage = root / "coverage.json"
            result = catalog.build(source, output, artwork_manifest=manifest,
                                   artwork_root=root, artwork_coverage=coverage)
            self.assertEqual(result["pages"], 176)
            self.assertEqual(result["pages"] % 4, 0)
            self.assertEqual(result["cards"], 144)
            self.assertEqual(result["toc_pages"], 2)
            self.assertEqual(result["outline_entries"], 175)
            self.assertEqual(result["artwork"]["counts"], {
                "no-manifest-page": 143, "replayed": 1,
            })
            self.assertTrue(coverage.is_file())
            self.assertEqual(len(result["references"]["damage_effects"]), 2)
            self.assertEqual(len(result["references"]["weapon_qualities"]), 3)
            self.assertEqual(len(result["modifications"]), 20)
            self.assertEqual(len(result["categories"]), 7)
            self.assertNotIn("Other Weapons", result["categories"])
            self.assertEqual(len(result["card_pages"]), 144)
            self.assertNotIn("weapon_assaultron_head", result["card_pages"])
            self.assertNotIn("weapon_straight_razor", result["card_pages"])
            self.assertIn("weapon_assaultron_head_laser", result["card_pages"])
            self.assertIn("weapon_unarmed_attack", result["card_pages"])
            self.assertEqual(result["closing"], [171, 172, 173, 174, 176])

            with pymupdf.open(output) as document:
                self.assertEqual(document.page_count, 176)
                # The release builder suppresses PyMuPDF's random trailer IDs
                # so an unchanged catalogue can be reproduced byte-for-byte.
                self.assertNotIn("/ID", document.pdf_trailer())
                outline = document.get_toc(simple=True)
                self.assertEqual(outline[0], [1, "DAMAGE EFFECTS", 6])
                self.assertIn([1, "WEAPON MODIFICATIONS", 12], outline)
                self.assertIn([1, "SMALL GUNS", 20], outline)
                self.assertIn([2, "10mm Pistol", result["card_pages"]["weapon_10mm_pistol"]],
                              outline)
                self.assertIn([2, "Assaultron Head Laser",
                               result["card_pages"]["weapon_assaultron_head_laser"]], outline)
                self.assertIn([2, "Unarmed Attack",
                               result["card_pages"]["weapon_unarmed_attack"]], outline)
                outline_titles = [title for _level, title, _page in outline]
                self.assertNotIn("Assaultron Head", outline_titles)
                self.assertNotIn("Straight Razor", outline_titles)
                self.assertNotIn("OTHER WEAPONS", outline_titles)
                self.assertEqual(len(outline), 175)

                cover = document[0].get_text()
                self.assertIn("BROTHERHOOD FIELD GUIDE", cover)
                self.assertIn("WASTELAND ARSENAL", cover)
                self.assertNotIn("РУКОВОДСТВО", cover)
                toc = document[3].get_text()
                self.assertIn("TABLE OF CONTENTS", toc)
                self.assertIn("DAMAGE EFFECTS", toc)
                effects = document[result["references"]["damage_effects"][0] - 1].get_text()
                qualities = document[result["references"]["weapon_qualities"][0] - 1].get_text()
                mods = document[result["modifications"]["RECEIVER MODIFICATIONS"] - 1].get_text()
                self.assertIn("DAMAGE EFFECTS", effects)
                self.assertIn("BURST", effects)
                self.assertIn("WEAPON QUALITIES", qualities)
                self.assertIn("ACCURATE", qualities)
                self.assertIn("WEAPON MODIFICATIONS", mods)
                self.assertIn("MODIFICATION", mods)
                self.assertIn(".308 Receiver", mods)

                stock_mods = " ".join(document[
                    result["modifications"]["STOCK MODIFICATIONS"] - 1
                ].get_text().split())
                self.assertIn(
                    "Recoil Compensating Stock Recoil-Compensated Fire Rate: +1; "
                    "Add Quality: Two-Handed; Remove Quality: Inaccurate",
                    stock_mods,
                )
                self.assertNotIn("Recoil-Compensating", stock_mods)
                self.assertNotIn(
                    "Range: +1 zone; Add Quality: Two-Handed; Remove Quality: Inaccurate; "
                    "Add Quality: Close Quarters",
                    stock_mods,
                )
                for weapon_id in ("weapon_gauss_rifle", "weapon_light_machine_gun",
                                  "weapon_pump_action_shotgun"):
                    stock_card = " ".join(document[result["card_pages"][weapon_id] - 1]
                                          .get_text().split())
                    self.assertEqual(stock_card.count("Recoil Compensating"), 1)
                    self.assertIn("Recoil Compensating Stock", stock_card)
                    self.assertNotIn("Close Quarters", stock_card)

                # The exact-ID match retains its manifest matrix. An earlier
                # card must remain artless rather than borrowing it by position.
                no_art_page = result["card_pages"]["weapon_357_magnum_revolver"] - 1
                self.assertFalse(any(item["width"] == 20 and item["height"] == 10
                                     for item in document[no_art_page].get_image_info(xrefs=True)))
                art_page = result["card_pages"]["weapon_10mm_pistol"] - 1
                art = next(item for item in document[art_page].get_image_info(xrefs=True)
                           if item["width"] == 20 and item["height"] == 10)
                expected = (100, 20, -10, 80, 50, 270)
                for actual, wanted in zip(art["transform"], expected):
                    self.assertAlmostEqual(actual, wanted, places=3)


if __name__ == "__main__":
    unittest.main()
