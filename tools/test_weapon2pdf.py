"""Tests for tools/weapon2pdf.py (A4 weapon reference cards)."""

import json
import os
import tempfile
import unittest

from PIL import Image

import weapon2pdf as w

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CARD_PATH = os.path.join(ROOT, "data", "weapons", "cards", "combat-rifle.json")

w.register_fonts()


def base_card():
    with open(CARD_PATH, encoding="utf-8") as fh:
        return json.load(fh)


class WrapTextTests(unittest.TestCase):
    def test_words_are_preserved(self):
        text = "Укреплённый проникающий автоматический"
        lines = w.wrap_text(text, "Carlito", 9, 70)
        self.assertEqual(" ".join(lines), text)

    def test_lines_fit_the_width(self):
        text = "Короткий оптический ночного видения"
        lines = w.wrap_text(text, "Carlito", 9, 60)
        for line in lines:
            self.assertLessEqual(w.sw(line, "Carlito", 9), 60 + 0.01)

    def test_long_word_is_not_dropped(self):
        lines = w.wrap_text("сверхдлинноеслово", "Carlito", 9, 10)
        self.assertEqual(lines, ["сверхдлинноеслово"])


class ModsLayoutTests(unittest.TestCase):
    def test_rows_split_after_six_items(self):
        card = base_card()
        card["mods"] = [{"slot": "РЕСИВЕР",
                         "items": [f"Мод {i}" for i in range(8)]}]
        rows, _, ncols = w.mods_layout(card)
        self.assertEqual(ncols, 6)
        self.assertEqual(len(rows), 2)
        self.assertEqual([len([c for c in r["cells"] if c]) for r in rows],
                         [6, 2])
        self.assertTrue(rows[0]["cat_start"])
        self.assertTrue(rows[-1]["cat_end"])

    def test_column_count_follows_the_widest_category(self):
        card = base_card()
        card["mods"] = [
            {"slot": "РЕСИВЕР", "items": ["Один", "Два", "Три"]},
            {"slot": "СТВОЛ", "items": ["Четыре"]},
        ]
        rows, _, ncols = w.mods_layout(card)
        self.assertEqual(ncols, 3)
        self.assertEqual(len(rows[0]["cells"]), 3)

    def test_single_mod_fills_the_whole_width(self):
        card = base_card()
        card["mods"] = [{"slot": "СТВОЛ", "items": ["Единственный"]}]
        rows, _, ncols = w.mods_layout(card)
        self.assertEqual(ncols, 1)
        self.assertEqual(len(rows[0]["cells"]), 1)
        edges = w.mods_edges(1)
        self.assertAlmostEqual(edges[1], w.MODS_LABEL_RIGHT, places=2)
        self.assertAlmostEqual(edges[2], w.MODS_RIGHT, places=2)
        self.assertAlmostEqual(edges[2] - edges[1],
                               w.MODS_RIGHT - w.MODS_LABEL_RIGHT, places=2)

    def test_edges_cover_the_table_width(self):
        for ncols in (1, 2, 3, 4, 5, 6):
            edges = w.mods_edges(ncols)
            self.assertAlmostEqual(edges[0], w.MODS_LEFT, places=2)
            self.assertAlmostEqual(edges[1], w.MODS_LABEL_RIGHT, places=2)
            self.assertAlmostEqual(edges[-1], w.MODS_RIGHT, places=2)
            self.assertEqual(len(edges), ncols + 2)

    def test_long_mod_word_shrinks_to_fit_its_cell(self):
        card = {
            "title": "Тест",
            "mods": [{"slot": "СТВОЛ", "items": [
                "Квантовая гиростабилизирующая линза", "Мод", "Мод", "Мод",
                "Мод", "Мод"]}],
        }
        rows, _, ncols = w.mods_layout(card)
        edges = w.mods_edges(ncols)
        col_w = edges[2] - edges[1] - w.MODS_H_PAD
        self.assertLess(rows[0]["sizes"][0], w.MODS_FONT_SIZE)
        for line in rows[0]["cells"][0]:
            self.assertLessEqual(w.sw(line, "Carlito", rows[0]["sizes"][0]),
                                 col_w)

    def test_normal_mods_keep_the_base_size(self):
        card = base_card()
        rows, _, _ = w.mods_layout(card)
        self.assertTrue(all(size == w.MODS_FONT_SIZE
                            for row in rows for size in row["sizes"]))

    def test_empty_mods_is_reported(self):
        card = base_card()
        card["mods"] = [{"slot": "СТВОЛ", "items": []}]
        rows, _, ncols = w.mods_layout(card)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["cells"], [[] for _ in range(ncols)])

    def test_rows_keep_their_content_height(self):
        card = base_card()
        card["mods"] = [
            {"slot": "РЕСИВЕР", "items": ["Один"]},
            {"slot": "СТВОЛ", "items": ["Два"]},
            {"slot": "ЛОЖА", "items": ["Три"]},
            {"slot": "ДУЛО", "items": ["Четыре"]},
        ]
        rows, total, _ = w.mods_layout(card)
        for row in rows:
            self.assertAlmostEqual(row["h"], w.MODS_MIN_ROW, places=2)
        self.assertAlmostEqual(total, 4 * w.MODS_MIN_ROW, places=2)

    def test_single_row_is_not_stretched(self):
        card = base_card()
        card["mods"] = [{"slot": "РЕСИВЕР", "items": ["Один"]}]
        rows, total, _ = w.mods_layout(card)
        self.assertAlmostEqual(rows[0]["h"], w.MODS_MIN_ROW, places=2)
        self.assertLess(total, w.MODS_BOTTOM - w.MODS_TOP)


class ArtworkManifestTests(unittest.TestCase):
    """Publisher placement data is selected and replayed, never approximated."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.asset = os.path.join(self.tmp.name, "art.png")
        Image.new("RGBA", (20, 10), (180, 40, 20, 255)).save(self.asset)
        self.path = os.path.join(self.tmp.name, "artwork-manifest.json")
        self.manifest = {
            "schema": w.ARTWORK_MANIFEST_SCHEMA,
            "coordinate_system": {"unit": "point", "origin": "bottom-left"},
            "pages": [{
                "number": 18,
                "weapon_id": "weapon_combat_rifle",
                "placements": [{
                    "resource": "ArtLater",
                    "xref": 9,
                    "draw_order": 7,
                    "matrix_pdf": [100, -20, 10, 80, 40, 500],
                    "clip_paths": [{
                        "rule": "even-odd",
                        "commands": [
                            {"op": "move_to", "points": [50, 580]},
                            {"op": "line_to", "points": [140, 560]},
                            {"op": "line_to", "points": [130, 490]},
                            {"op": "line_to", "points": [40, 510]},
                            {"op": "close_path"},
                        ],
                    }],
                    "graphics_state": {
                        "fill_alpha": 0.5,
                        "stroke_alpha": 1.0,
                        "blend_mode": "Multiply",
                        "soft_mask": None,
                        "transfer_function": None,
                    },
                    "asset": "art.png",
                }, {
                    "resource": "ArtEarlier",
                    "xref": 9,
                    "draw_order": 2,
                    "matrix_pdf": [30, 0, 0, 20, 20, 700],
                    "clip_paths": [],
                    "graphics_state": {
                        "fill_alpha": 1.0,
                        "stroke_alpha": 1.0,
                        "blend_mode": "Normal",
                        "soft_mask": None,
                        "transfer_function": None,
                    },
                    "asset": "art.png",
                }, {
                    "resource": "Unexported",
                    "xref": 10,
                    "draw_order": 1,
                    "matrix_pdf": [1, 0, 0, 1, 0, 0],
                    "asset": None,
                }],
            }],
        }
        self.write_manifest()

    def write_manifest(self):
        with open(self.path, "w", encoding="utf-8") as fh:
            json.dump(self.manifest, fh)

    def test_layer_selects_card_id_and_preserves_repeated_asset_placements(self):
        card = {"id": "weapon_combat_rifle", "page": 999}
        layer = w.load_artwork_layer(self.path, card)
        self.assertEqual(layer.page["number"], 18)
        self.assertEqual(layer.asset_root, self.tmp.name)
        self.assertEqual([item["resource"] for item in w.artwork_placements(layer.page)],
                         ["ArtEarlier", "ArtLater"])
        self.assertEqual(w._manifest_asset_path(layer, layer.page["placements"][0]),
                         self.asset)

    def test_explicit_manifest_page_overrides_card_identity(self):
        self.manifest["pages"].append({
            "number": 24,
            "weapon_id": "",
            "placements": [],
        })
        self.write_manifest()
        layer = w.load_artwork_layer(self.path, {"id": "unknown", "page": 1},
                                     page_number=24)
        self.assertEqual(layer.page["number"], 24)

    def test_stale_card_page_cannot_silently_borrow_another_weapons_art(self):
        self.manifest["pages"].append({
            "number": 26,
            "weapon_id": "weapon_pipe_gun",
            "placements": [],
        })
        self.write_manifest()
        with self.assertRaisesRegex(w.ArtworkManifestError, "weapon_pipe_gun"):
            w.load_artwork_layer(self.path,
                                 {"id": "weapon_baseball_bat", "page": 26})
        # Explicit selection remains available for an intentional exception.
        layer = w.load_artwork_layer(self.path,
                                     {"id": "weapon_baseball_bat", "page": 26},
                                     page_number=26)
        self.assertEqual(layer.page["weapon_id"], "weapon_pipe_gun")

    def test_schema_and_missing_asset_fail_loudly(self):
        self.manifest["schema"] = "not-a-schema"
        self.write_manifest()
        with self.assertRaises(w.ArtworkManifestError):
            w.load_artwork_layer(self.path, {"id": "weapon_combat_rifle"})

        self.manifest["schema"] = w.ARTWORK_MANIFEST_SCHEMA
        self.write_manifest()
        layer = w.load_artwork_layer(self.path, {"id": "weapon_combat_rifle"})
        os.unlink(self.asset)
        with self.assertRaises(w.ArtworkManifestError):
            w._manifest_asset_path(layer, layer.page["placements"][0])


class ArtworkManifestRenderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import pymupdf
        except ImportError:  # pragma: no cover - dev dependency
            raise unittest.SkipTest("pymupdf is not installed")
        cls.fitz = pymupdf

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.asset = os.path.join(self.tmp.name, "art.png")
        Image.new("RGBA", (20, 10), (180, 40, 20, 255)).save(self.asset)
        self.path = os.path.join(self.tmp.name, "artwork-manifest.json")
        self.matrix = [100, -20, 10, 80, 40, 500]
        manifest = {
            "schema": w.ARTWORK_MANIFEST_SCHEMA,
            "coordinate_system": {"unit": "point", "origin": "bottom-left"},
            "pages": [{
                "number": 18,
                "weapon_id": "weapon_combat_rifle",
                "size_points": [600, 850],
                "placements": [{
                    "resource": "Art",
                    "xref": 9,
                    "draw_order": 7,
                    "matrix_pdf": self.matrix,
                    "clip_paths": [{
                        "rule": "even-odd",
                        "commands": [
                            {"op": "move_to", "points": [50, 580]},
                            {"op": "line_to", "points": [140, 560]},
                            {"op": "line_to", "points": [130, 490]},
                            {"op": "line_to", "points": [40, 510]},
                            {"op": "close_path"},
                        ],
                    }],
                    "graphics_state": {
                        "fill_alpha": 0.5,
                        "stroke_alpha": 1.0,
                        "blend_mode": "Multiply",
                        "soft_mask": None,
                        "transfer_function": None,
                    },
                    "asset": "art.png",
                }, {
                    # Same exported PNG, deliberately a second use of it.
                    "resource": "ArtRepeat",
                    "xref": 9,
                    "draw_order": 2,
                    "matrix_pdf": [30, 0, 0, 20, 20, 700],
                    "clip_paths": [],
                    "graphics_state": {
                        "fill_alpha": 1.0,
                        "stroke_alpha": 1.0,
                        "blend_mode": "Normal",
                        "soft_mask": None,
                        "transfer_function": None,
                    },
                    "asset": "art.png",
                }],
            }],
        }
        with open(self.path, "w", encoding="utf-8") as fh:
            json.dump(manifest, fh)

    def test_renderer_replays_matrix_clip_and_extgstate(self):
        layer = w.load_artwork_layer(self.path,
                                     {"id": "weapon_combat_rifle", "page": 18})
        output = os.path.join(self.tmp.name, "card.pdf")
        w.render_card(base_card(), output, artwork=layer)
        doc = self.fitz.open(output)
        page = doc[0]
        art_images = [item for item in page.get_image_info(xrefs=True)
                      if item["width"] == 20 and item["height"] == 10]
        # The repeated use of one asset remains two PDF draws, in draw_order.
        self.assertEqual(len(art_images), 2)
        # ``card.image`` is not fitted into IMAGE_BOX as a second approximation.
        self.assertFalse(any(item["width"] == 1119 and item["height"] == 439
                             for item in page.get_image_info(xrefs=True)))
        info = next(item for item in art_images
                    if abs(item["transform"][0] - self.matrix[0]) < 0.01)
        a, b, c, d, e, f = self.matrix
        transform = info["transform"]
        # PyMuPDF reports a top-left space; this is the exact coordinate
        # conversion of the bottom-left PDF matrix retained in the manifest.
        expected = (a, -b, -c, d, e + c, 850 - f - d)
        self.assertAlmostEqual(page.rect.width, 600, places=3)
        self.assertAlmostEqual(page.rect.height, 850, places=3)
        for actual, wanted in zip(transform, expected):
            self.assertAlmostEqual(actual, wanted, places=3)
        self.assertIn(b"W*", page.read_contents())
        extgstates = "\n".join(
            doc.xref_object(xref, compressed=False)
            for xref in range(1, doc.xref_length())
        )
        self.assertIn("/BM /Multiply", extgstates)
        self.assertIn("/ca .5", extgstates)


class RenderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import pymupdf
        except ImportError:  # pragma: no cover - dev dependency
            raise unittest.SkipTest("pymupdf is not installed")
        cls.fitz = pymupdf

    def render(self, card):
        tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        tmp.close()
        self.addCleanup(os.unlink, tmp.name)
        w.render_card(card, tmp.name)
        return self.fitz.open(tmp.name)

    def test_page_size_and_number(self):
        doc = self.render(base_card())
        self.assertEqual(doc.page_count, 1)
        page = doc[0]
        self.assertAlmostEqual(page.rect.width, 595.28, places=1)
        self.assertAlmostEqual(page.rect.height, 841.89, places=1)
        text = page.get_text()
        self.assertIn("ПОДДЕРЖИВАЕМЫЕ МОДИФИКАЦИИ", text)
        self.assertIn("БОЕВОЙ КАРАБИН", text)
        self.assertIn("Вес: 11, Цена: 117, Редкость: 2", text)
        self.assertIn("\n18", text)

    def test_mods_table_reaches_bottom_margin(self):
        page = self.render(base_card())[0]
        lines = [it["rect"] for it in page.get_drawings()
                 if it["type"] == "s" and it["rect"].width > 400]
        self.assertTrue(lines)
        self.assertAlmostEqual(max(r.y1 for r in lines), w.MODS_BOTTOM,
                               delta=0.6)

    def test_empty_mods_message(self):
        card = base_card()
        card["mods"] = []
        page = self.render(card)[0]
        text = page.get_text()
        self.assertEqual(text.count("НЕТ ПОДДЕРЖИВАЕМЫХ МОДИФИКАЦИЙ"), 1)
        self.assertNotIn("ПОДДЕРЖИВАЕМЫЕ МОДИФИКАЦИИ", text)

    def test_one_mod_table_sits_on_the_bottom_rule(self):
        card = base_card()
        card["mods"] = [{"slot": "РЕСИВЕР", "items": ["Укреплённый"]}]
        page = self.render(card)[0]
        lines = [it["rect"] for it in page.get_drawings()
                 if it["type"] == "s" and it["rect"].width > 400]
        bottom = max(r.y1 for r in lines)
        top = min(r.y0 for r in lines if r.y1 > w.MODS_TOP)
        self.assertAlmostEqual(bottom, w.MODS_BOTTOM, delta=0.6)
        self.assertLess(bottom - top, 2 * w.MODS_MIN_ROW)

    def test_heading_follows_a_short_table(self):
        card = base_card()
        card["mods"] = [{"slot": "РЕСИВЕР", "items": ["Один"]}]
        page = self.render(card)[0]
        ys = [s["bbox"][1] for b in page.get_text("dict")["blocks"]
              for line in b.get("lines", []) for s in line["spans"]
              if "ПОДДЕРЖИВАЕМЫЕ" in s["text"]]
        self.assertTrue(ys)
        heading_top = min(ys)
        self.assertGreater(heading_top, w.MODS_TOP)
        self.assertAlmostEqual(heading_top + w.MODS_HEADING_GAP,
                               w.MODS_BOTTOM - w.MODS_MIN_ROW, delta=4)

    def test_heading_is_always_the_same_gap_above_the_table(self):
        for items in (["Один"],
                      [f"Мод номер {i}" for i in range(8)]):
            card = base_card()
            card["mods"] = [{"slot": "РЕСИВЕР", "items": items}]
            page = self.render(card)[0]
            heading_top = min(
                s["bbox"][1] for b in page.get_text("dict")["blocks"]
                for line in b.get("lines", []) for s in line["spans"]
                if "ПОДДЕРЖИВАЕМЫЕ" in s["text"])
            table_top = min(
                it["rect"].y0 for it in page.get_drawings()
                if it["type"] == "s" and it["rect"].width > 400
                and it["rect"].y0 > w.MODS_TOP - 20)
            self.assertAlmostEqual(heading_top + w.MODS_HEADING_GAP,
                                   table_top, delta=2)

    def test_long_description_uses_the_space_above_the_mods(self):
        card = base_card()
        card["mods"] = [{"slot": "РЕСИВЕР", "items": ["Один"]}]
        card["description"] = " ".join(f"Слово{i}" for i in range(110))
        page = self.render(card)[0]
        text = page.get_text()
        self.assertNotIn("…", text)
        self.assertIn("Слово109", text)

    def test_description_bottom_follows_the_table(self):
        card = base_card()
        card["mods"] = [{"slot": "РЕСИВЕР", "items": ["Один"]}]
        short = w.description_bottom(card)
        card["mods"] = [{"slot": "РЕСИВЕР",
                         "items": [f"Мод {i}" for i in range(8)]}]
        tall = w.description_bottom(card)
        self.assertGreater(short, tall)
        self.assertAlmostEqual(
            short, w.MODS_BOTTOM - w.MODS_MIN_ROW - w.MODS_HEADING_GAP - 10,
            places=1)

    def test_page_number_side_alternates(self):
        even = self.render(base_card())[0]
        odd_card = base_card()
        odd_card["page"] = 19
        odd = self.render(odd_card)[0]

        def number_x(page, number):
            for block in page.get_text("dict")["blocks"]:
                for line in block.get("lines", []):
                    for span in line["spans"]:
                        if span["text"].strip() == str(number):
                            return span["bbox"][0]
            raise AssertionError("page number not found")

        self.assertLess(number_x(even, 18), 60)
        self.assertGreater(number_x(odd, 19), 500)


class CardFixtureTests(unittest.TestCase):
    def test_revolver_card_is_consistent(self):
        path = os.path.join(ROOT, "data", "weapons", "cards", "revolver-44.json")
        with open(path, encoding="utf-8") as fh:
            card = json.load(fh)
        self.assertEqual(card["id"], "weapon_44_pistol")
        self.assertEqual(card["page"], 15)
        self.assertEqual([c["slot"] for c in card["mods"]],
                         ["РЕСИВЕР", "СТВОЛ", "РУКОЯТЬ", "ПРИЦЕЛ"])

    def test_reference_card_is_consistent(self):
        card = base_card()
        self.assertEqual(card["slug"] if "slug" in card else card["id"],
                         "weapon_combat_rifle")
        self.assertEqual(len(card["mods"]), 6)
        self.assertEqual(card["mods"][0]["slot"], "РЕСИВЕР")
        self.assertEqual(len(card["mods"][0]["items"]), 15)


if __name__ == "__main__":
    unittest.main()
