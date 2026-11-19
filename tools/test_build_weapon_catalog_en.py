"""Tests for the complete English weapon-book assembler."""

import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

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
            with pymupdf.open(catalog.ROOT / "Справочник оружия.pdf") as original:
                document.insert_pdf(original, from_page=0, to_page=0)
                catalog.book_cover.restore_transparency_group(original[0], document[0])
            for number in range(2, 107):
                page = document.new_page(width=w.PAGE_W, height=w.PAGE_H)
                # Match the source convention closely enough for the strict
                # renumbering code: one unique number below y=800.
                x = 39 if number % 2 == 0 else 546
                page.insert_text((x, 819), str(number), fontsize=9.96,
                                 fontname="helv", color=(0, 0, 0))
            document.save(path, garbage=4, deflate=True)
        finally:
            document.close()

    def test_publisher_cover_localization_preserves_art_and_transparency(self):
        source = catalog.ROOT / "Справочник оружия.pdf"
        with tempfile.TemporaryDirectory() as directory:
            proof = Path(directory) / "cover.pdf"
            catalog.book_cover.make_localized_cover(source, proof)
            with pymupdf.open(source) as original, pymupdf.open(proof) as localized:
                raw, page = original[0], localized[0]
                self.assertEqual(raw.rect, page.rect)
                self.assertEqual(original.xref_get_key(raw.xref, "Group"),
                                 localized.xref_get_key(page.xref, "Group"))
                # Compare the actual artwork and original graphical elements,
                # excluding title bands and sequence numbers.
                art = pymupdf.Rect(0, 180, raw.rect.width, 725)
                self.assertEqual(raw.get_pixmap(clip=art).samples, page.get_pixmap(clip=art).samples)
                self.assertEqual([{k: v for k, v in item.items() if k != "seqno"}
                                  for item in raw.get_drawings()],
                                 [{k: v for k, v in item.items() if k != "seqno"}
                                  for item in page.get_drawings()])
                visible = page.get_text()
                self.assertFalse(catalog._has_cyrillic(visible))
                for title in ("VOLUME 1", "BROTHERHOOD FIELD GUIDE", "WASTELAND ARSENAL"):
                    self.assertEqual(visible.count(title), 1)
                # Three title shadows with soft masks are placed before the
                # original final grain image, not above it.
                drawn = page.get_image_info(xrefs=True)
                by_id = {item[0]: item[1] for item in page.get_images()}
                self.assertEqual(len(drawn), 10)  # 7 retained placements and 3 shadows.
                self.assertTrue(all(by_id[item["xref"]] for item in drawn[-4:-1]))

    def test_shared_index_counts_identical_variants_within_one_chapter(self):
        same = ("Barrel", "Long", "Long", "Range: +1 zone", "1", "20", "Gun Nut 1")
        specific = (*same[:4], "2", "158", "Gun Nut 4")
        by_weapon = {"a": [same, same], "b": [same], "c": [same], "d": [specific], "elsewhere": [same]}
        self.assertEqual(catalog.catalogue_mods.shared_rows("abcd", by_weapon), [])
        by_weapon["d"] = [same]
        self.assertEqual(catalog.catalogue_mods.shared_rows("abcd", by_weapon), [same])

    def test_publisher_tiebreak_does_not_override_a_mod_for_other_weapons(self):
        companion = catalog.Companion()
        rows = catalog.catalogue_mods.weapon_rows(companion, {"weapon_broadsider", "weapon_laser_musket"})
        broadsider = next(row for row in rows["weapon_broadsider"] if row[1] == "Long Barrel")
        self.assertEqual(broadsider[-2:], ("135", "Gun Nut 3"))
        self.assertIn("Range: +1 zone", broadsider)
        self.assertEqual(len(rows["weapon_broadsider"]), 4)
        self.assertNotIn(broadsider, rows["weapon_laser_musket"])

    def test_overflow_keeps_details_immediately_after_the_card(self):
        companion = catalog.Companion()
        card = companion.card("weapon_auto_grenade_launcher")
        card["page"] = 42
        rows = catalog.catalogue_mods.weapon_rows(companion, {card["id"]})[card["id"]]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "weapon.pdf"
            with patch.object(catalog.detailed_card, "render_heavy",
                              side_effect=catalog.detailed_card.DetailedModsLayoutError):
                continuation = catalog._render_weapon(companion, card, path, None, rows)
            with pymupdf.open(path) as main, pymupdf.open(continuation) as detail:
                self.assertIn("MODIFICATIONS — SEE NEXT PAGE", main[0].get_text())
                self.assertNotIn("MODIFICATION\nPREFIX", main[0].get_text())
                text = detail[0].get_text()
                self.assertIn("AUTO GRENADE LAUNCHER — MODIFICATIONS", text)
                self.assertIn("25mm Receiver", text)
                self.assertIn("Heavy Barrel", text)
                self.assertIn("43", text.splitlines())

    def test_undocumented_qualities_are_audited_separately_from_known_rules(self):
        companion = catalog.Companion()
        reference = catalog._load_reference_data()
        catalog._validate_reference_data(reference, companion)
        section = reference["weapon_qualities"]
        defined = {item["id"] for item in section["entries"]}
        self.assertEqual(defined & set(section["undocumented_ids"]), set())
        self.assertEqual(len(section["undocumented_ids"]), 5)
        section["undocumented_ids"].append("quality_bayonet")
        with self.assertRaisesRegex(catalog.EnglishCatalogError, "already defined"):
            catalog._validate_reference_data(reference, companion)

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
            self.assertEqual(result["pages"], 184)
            self.assertEqual(result["pages"] % 4, 0)
            self.assertEqual(result["cards"], 144)
            self.assertEqual(result["toc_pages"], 2)
            self.assertEqual(result["outline_entries"], 157)
            self.assertEqual(result["artwork"]["counts"], {
                "no-manifest-page": 143, "replayed": 1,
            })
            self.assertTrue(coverage.is_file())
            self.assertEqual(len(result["references"]["damage_effects"]), 2)
            self.assertEqual(len(result["references"]["weapon_qualities"]), 3)
            self.assertEqual(len(result["modifications"]), 3)
            self.assertEqual(len(result["categories"]), 7)
            self.assertNotIn("Other Weapons", result["categories"])
            self.assertEqual(len(result["card_pages"]), 144)
            self.assertNotIn("weapon_assaultron_head", result["card_pages"])
            self.assertNotIn("weapon_straight_razor", result["card_pages"])
            self.assertIn("weapon_assaultron_head_laser", result["card_pages"])
            self.assertIn("weapon_unarmed_attack", result["card_pages"])
            self.assertEqual(result["closing"], [178, 179, 180, 181, 184])

            with pymupdf.open(output) as document:
                self.assertEqual(document.page_count, 184)
                # The release builder suppresses PyMuPDF's random trailer IDs
                # so an unchanged catalogue can be reproduced byte-for-byte.
                self.assertNotIn("/ID", document.pdf_trailer())
                outline = document.get_toc(simple=True)
                self.assertEqual(outline[0], [1, "DAMAGE EFFECTS", 6])
                self.assertIn([1, "SMALL GUNS", 12], outline)
                self.assertNotIn("WEAPON MODIFICATIONS", [entry[1] for entry in outline])
                self.assertEqual(outline, result["toc"])
                for category, start in result["modifications"].items():
                    title = catalog.CATEGORY_PRESENTATION[category]["title"]
                    divider = result["categories"][category]
                    self.assertEqual(start, divider + 1)
                    index = outline.index([1, title, divider])
                    self.assertEqual(outline[index + 1], [2, f"{title} MODIFICATIONS", start])
                    self.assertIn(f"{title} MODIFICATIONS", document[start - 1].get_text())
                self.assertNotIn("Explosive Weapons", result["modifications"])
                self.assertNotIn("Thrown Weapons", result["modifications"])
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
                self.assertEqual(len(outline), 157)

                cover = document[0].get_text()
                self.assertIn("BROTHERHOOD FIELD GUIDE", cover)
                self.assertIn("WASTELAND ARSENAL", cover)
                self.assertNotIn("РУКОВОДСТВО", cover)
                toc = document[3].get_text()
                self.assertIn("TABLE OF CONTENTS", toc)
                self.assertIn("DAMAGE EFFECTS", toc)
                effects = document[result["references"]["damage_effects"][0] - 1].get_text()
                qualities = " ".join(" ".join(document[page - 1].get_text().split())
                                     for page in result["references"]["weapon_qualities"])
                self.assertIn("RE-ROLL HIT LOCATION You may re-roll the hit location die.", qualities)
                self.assertIn("BAYONET A bayonet can be used for a melee attack", qualities)
                self.assertIn("Large Bayonet instead deals 5 Combat Dice", qualities)
                self.assertNotIn("Companion lists this as a modification quality", qualities)
                self.assertNotIn("Publisher export", qualities)
                self.assertIn("SHREDDER Needs clarification.", qualities)
                self.assertEqual(qualities.count("Needs clarification."), 5)
                mods = document[result["modifications"]["Light Weapons"] - 1].get_text()
                self.assertIn("DAMAGE EFFECTS", effects)
                self.assertIn("BURST", effects)
                self.assertIn("WEAPON QUALITIES", qualities)
                self.assertIn("ACCURATE", qualities)
                self.assertIn("SMALL GUNS MODIFICATIONS", mods)
                self.assertIn("MODIFICATION", mods)
                self.assertIn(".38 Receiver", mods)

                self.assertNotIn("Heavy Weapons", result["modifications"])
                self.assertEqual(set(result["continuation_pages"]), {
                    "weapon_assault_rifle", "weapon_combat_rifle", "weapon_combat_shotgun",
                    "weapon_pipe_gun", "weapon_radium_rifle",
                })

                def card_text(weapon_id):
                    return " ".join(document[result["card_pages"][weapon_id] - 1].get_text().split())

                for weapon_id in ("weapon_gauss_pistol", "weapon_gauss_rifle"):
                    self.assertGreater(result["card_pages"][weapon_id], result["categories"]["Light Weapons"])
                    self.assertLess(result["card_pages"][weapon_id], result["categories"]["Heavy Weapons"])

                for weapon_id, phrase in (
                    ("weapon_broadsider", "Long Barrel Long Range: +1 zone 3 135 Gun Nut 3"),
                    ("weapon_gatling_gun", "Long Long Range: +1 zone 2 158 Gun Nut 4"),
                    ("weapon_harpoon_gun", "Short Scope Sighted Add Quality: Reliable 1 28 Gun Nut 1"),
                    ("weapon_eugene", "Tri-Barrel Tri-Barrel Fire Rate: +1 3 75 Gun Nut 3"),
                ):
                    card = card_text(weapon_id)
                    self.assertIn(phrase, card)
                    self.assertEqual(card.count("SUPPORTED MODIFICATIONS"), 1)
                    self.assertNotIn("OTHER SUPPORTED MODIFICATIONS", card)
                self.assertIn("MODIFICATIONS — COMPATIBILITY NEEDS CLARIFICATION", card_text("weapon_gatling_plasma"))

                for weapon_id in ("weapon_gauss_rifle", "weapon_light_machine_gun",
                                  "weapon_pump_action_shotgun"):
                    stock_card = card_text(weapon_id)
                    self.assertIn("Recoil Compensating Stock", stock_card)
                    self.assertNotIn("Recoil-Compensating ", stock_card)

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
