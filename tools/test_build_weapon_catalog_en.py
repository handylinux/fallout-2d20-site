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

    def test_tables_follow_compatibility_not_mod_names(self):
        companion = catalog.Companion()
        cards = catalog.ordered_cards(companion)
        rare = catalog._rare_mod_ids(companion, cards)
        prefixes = catalog.companion_mods_en.load_prefixes()
        tables = catalog._category_mod_data(companion, catalog._category_cards(cards), rare, prefixes)
        names = {category: {row[0] for section in table["sections"] for row in section["rows"]}
                 for category, table in tables.items()}
        self.assertIn(".308 Receiver", names["Light Weapons"])
        self.assertNotIn(".308 Receiver", names["Melee Weapons"])
        self.assertIn("Recoil Compensating Stock", names["Energy Weapons"])
        self.assertNotIn("Explosive Weapons", names)
        self.assertNotIn("Thrown Weapons", names)
        self.assertFalse(companion.mod_rows("weapon_plasma_mine"))

    def test_rarity_counts_distinct_published_weapons_not_slot_or_chapter(self):
        companion = catalog.Companion()
        cards = catalog.ordered_cards(companion)
        rare = catalog._rare_mod_ids(companion, cards)
        self.assertEqual(len(rare), 91)
        self.assertIn("mod_25mm_receiver", rare)  # One published weapon.
        self.assertIn("mod_heavy_barrel", rare)  # Two published weapons, not the plasma mine.
        self.assertNotIn("mod_recoil_compensating_stock", rare)
        self.assertNotIn("mod_recoil_compensating", rare)

    def test_overflow_keeps_details_immediately_after_the_card(self):
        companion = catalog.Companion()
        card = companion.card("weapon_auto_grenade_launcher")
        card["page"] = 42
        rare = catalog._rare_mod_ids(companion, catalog.ordered_cards(companion))
        prefixes = catalog.companion_mods_en.load_prefixes()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "weapon.pdf"
            with patch.object(catalog.detailed_card, "render_heavy",
                              side_effect=catalog.detailed_card.DetailedModsLayoutError):
                continuation = catalog._render_weapon(companion, card, path, None, rare, prefixes)
            with pymupdf.open(path) as main, pymupdf.open(continuation) as detail:
                self.assertIn("DETAILS ON NEXT PAGE", main[0].get_text())
                text = detail[0].get_text()
                self.assertIn("AUTO GRENADE LAUNCHER — MODIFICATIONS", text)
                self.assertIn("25mm Receiver", text)
                self.assertIn("Heavy Barrel", text)
                self.assertIn("43", text.splitlines())

    def test_undocumented_qualities_are_audited_but_not_printed_as_rules(self):
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
            self.assertEqual(result["pages"], 176)
            self.assertEqual(result["pages"] % 4, 0)
            self.assertEqual(result["cards"], 144)
            self.assertEqual(result["toc_pages"], 2)
            self.assertEqual(result["outline_entries"], 159)
            self.assertEqual(result["artwork"]["counts"], {
                "no-manifest-page": 143, "replayed": 1,
            })
            self.assertTrue(coverage.is_file())
            self.assertEqual(len(result["references"]["damage_effects"]), 2)
            self.assertEqual(len(result["references"]["weapon_qualities"]), 3)
            self.assertEqual(len(result["modifications"]), 5)
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
                self.assertEqual(len(outline), 159)

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
                self.assertNotIn("SHREDDER", qualities)
                mods = document[result["modifications"]["Light Weapons"] - 1].get_text()
                self.assertIn("DAMAGE EFFECTS", effects)
                self.assertIn("BURST", effects)
                self.assertIn("WEAPON QUALITIES", qualities)
                self.assertIn("ACCURATE", qualities)
                self.assertIn("SMALL GUNS MODIFICATIONS", mods)
                self.assertIn("MODIFICATION", mods)
                self.assertIn(".308 Receiver", mods)

                for category, first_card in (("Light Weapons", ".357 Magnum Revolver"),
                                             ("Heavy Weapons", ".50 Cal Machine Gun"),
                                             ("Energy Weapons", "Acid Soaker")):
                    start = result["modifications"][category]
                    end = next(page for _, name, page in outline if name == first_card)
                    stock_mods = " ".join("".join(
                        document[page - 1].get_text() for page in range(start, end)
                    ).split())
                    self.assertEqual(stock_mods.count("Recoil Compensating Stock"), 1)
                    self.assertIn("Recoil Compensating Stock Recoil-Compensated Fire Rate: +1; "
                                  "Add Quality: Two-Handed; Remove Quality: Inaccurate", stock_mods)
                    self.assertNotIn("Recoil-Compensating", stock_mods)
                for weapon_id in ("weapon_gauss_rifle", "weapon_light_machine_gun",
                                  "weapon_pump_action_shotgun"):
                    stock_card = " ".join(document[result["card_pages"][weapon_id] - 1]
                                          .get_text().split())
                    self.assertEqual(stock_card.count("Recoil Compensating"), 1)
                    self.assertIn("Recoil Compensating Stock", stock_card)
                    self.assertNotIn("Close Quarters", stock_card)

                self.assertEqual(result["continuation_pages"], {})
                companion = catalog.Companion()
                rare = catalog._rare_mod_ids(companion, catalog.ordered_cards(companion))
                detailed_count = 0
                for weapon_id, page in result["card_pages"].items():
                    expected = catalog._published_mod_ids(companion, weapon_id) & rare
                    if not expected:
                        continue
                    detailed_count += 1
                    text = " ".join(document[page - 1].get_text().split())
                    self.assertIn("DETAILED MODIFICATIONS", text)
                    for mid in expected:
                        self.assertIn(companion.mods_en[mid]["name"], text, weapon_id)
                self.assertEqual(detailed_count, 47)

                def card_text(weapon_id):
                    return " ".join(document[result["card_pages"][weapon_id] - 1].get_text().split())

                launcher = card_text("weapon_auto_grenade_launcher")
                self.assertIn("OTHER SUPPORTED MODIFICATIONS BARREL Long", launcher)
                self.assertIn("25mm Receiver 25mm Damage: 4", launcher)
                self.assertIn("Gun Nut 3, Science! 1", launcher)
                for weapon_id in ("weapon_auto_grenade_launcher", "weapon_50_cal_machine_gun"):
                    self.assertIn("Heavy Barrel Heavy Damage: +1 ; Add Effect: Vicious 3 35 Gun Nut 2",
                                  card_text(weapon_id))
                heavy_mods = document[result["modifications"]["Heavy Weapons"] - 1].get_text()
                self.assertNotIn("Heavy Barrel", heavy_mods)
                self.assertNotIn("25mm Receiver", heavy_mods)

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
