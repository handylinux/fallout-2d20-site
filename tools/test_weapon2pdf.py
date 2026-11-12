"""Tests for tools/weapon2pdf.py (A4 weapon reference cards)."""

import json
import os
import tempfile
import unittest

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

    def test_table_is_always_stretched_to_the_bottom(self):
        card = base_card()
        card["mods"] = [
            {"slot": "РЕСИВЕР", "items": ["Один"]},
            {"slot": "СТВОЛ", "items": ["Два"]},
            {"slot": "ЛОЖА", "items": ["Три"]},
            {"slot": "ДУЛО", "items": ["Четыре"]},
        ]
        rows, total, _ = w.mods_layout(card)
        avail = w.MODS_BOTTOM - w.MODS_TOP
        extra = (avail - total) / len(rows)
        self.assertAlmostEqual(total + extra * len(rows), avail, places=1)

    def test_single_row_still_reaches_the_bottom(self):
        card = base_card()
        card["mods"] = [{"slot": "РЕСИВЕР", "items": ["Один"]}]
        rows, total, _ = w.mods_layout(card)
        avail = w.MODS_BOTTOM - w.MODS_TOP
        extra = (avail - total) / len(rows)
        self.assertAlmostEqual(total + extra, avail, places=1)


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

    def test_one_mod_table_reaches_the_bottom(self):
        card = base_card()
        card["mods"] = [{"slot": "РЕСИВЕР", "items": ["Укреплённый"]}]
        page = self.render(card)[0]
        lines = [it["rect"] for it in page.get_drawings()
                 if it["type"] == "s" and it["rect"].width > 400]
        self.assertAlmostEqual(max(r.y1 for r in lines), w.MODS_BOTTOM,
                               delta=0.6)

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
