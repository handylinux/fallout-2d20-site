#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Тесты книги брони: вёрстка по референсу armor-leather-book.pdf.

Проверяем то, что легко сломать незаметно:
  * геометрию, замеренную по референсу (заголовок, линейка, сетка таблиц,
    сетка модов, матрицы тиров, таблица уникальных модов);
  * правила данных: нет детали зоны — нет ни подписи, ни таблицы, ни строки
    модов, ни колонки в матрице тиров;
  * состав книги: все наборы armor.json / powerArmor.json / clothes.json,
    вторая страница только когда есть что печатать;
  * сам PDF (если установлен PyMuPDF): число страниц, тексты, отсутствие
    наложений подписей на таблицы и lorem ipsum.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import armorbook2pdf as ab  # noqa: E402

DATA = ROOT / "data" / "companion"

try:  # PyMuPDF нужен только для проверок готового PDF
    import pymupdf
except ImportError:  # pragma: no cover
    pymupdf = None


def book() -> ab.Book:
    return ab.Book(DATA)


class GeometryTest(unittest.TestCase):
    """Числа из docs/render/samples/armor-leather-book.pdf."""

    def test_page_title(self):
        self.assertAlmostEqual(ab.TITLE_TOP, 59.80, places=2)
        self.assertAlmostEqual(ab.TITLE_SIZE, 22.0, places=2)
        self.assertAlmostEqual(ab.TITLE_RULE_TOP, 90.43, places=2)
        self.assertAlmostEqual(ab.TITLE_RULE_W, 385.94, places=2)
        self.assertAlmostEqual(ab.TITLE_RULE_H, 2.2, places=2)

    def test_char_grid(self):
        self.assertAlmostEqual(ab.CHAR_TABLE_TOP_UPPER, 167.33, places=2)
        self.assertAlmostEqual(ab.CHAR_TABLE_TOP_LOWER, 330.80, places=2)
        self.assertAlmostEqual(ab.CHAR_ROW_H, 23.30, places=2)
        self.assertAlmostEqual(ab.CHAR_LEFT_X, 327.80, places=2)
        self.assertAlmostEqual(ab.CHAR_RIGHT_X, 448.13, places=2)
        # 6 строк по 23.3 = 307.13 — низ верхних таблиц в референсе
        self.assertAlmostEqual(ab.CHAR_TABLE_TOP_UPPER + 6 * ab.CHAR_ROW_H,
                               307.13, places=2)
        self.assertAlmostEqual(ab.CHAR_TABLE_TOP_LOWER + 6 * ab.CHAR_ROW_H,
                               470.60, places=2)

    def test_char_grid_seven_rows(self):
        """Силовая броня: 7 строк, подпись нижнего ряда не налезает на верх."""
        piece = {"hp": 7}
        geometry = ab.char_grid_geometry([piece])
        self.assertAlmostEqual(geometry["upper_top"] + 7 * ab.CHAR_ROW_H,
                               330.43, places=2)
        self.assertGreaterEqual(geometry["lower_label"],
                                geometry["upper_top"] + 7 * ab.CHAR_ROW_H)
        self.assertGreater(geometry["lower_top"],
                           geometry["lower_label"] + ab.CHAR_PIECE_SIZE_BOT)

    def test_mods_grid(self):
        self.assertAlmostEqual(ab.MODS_GRID_TOP, 658.60, places=2)
        self.assertAlmostEqual(ab.MODS_GRID_BOTTOM, 794.20, places=2)
        self.assertAlmostEqual(sum(ab.MODS_COLS), 431.30, places=2)
        # колонки + подпись = ширина строки
        self.assertAlmostEqual(ab.MODS_LABEL_MIN + sum(ab.MODS_COLS),
                               ab.CONTENT_W, places=1)

    def test_tier_grid(self):
        self.assertAlmostEqual(ab.TIER_GRID_TOP, 159.13, places=2)
        self.assertAlmostEqual(ab.TIER_RIGHT_X, 331.69, places=2)
        self.assertAlmostEqual(sum(ab.TIER_COL_SETS["left"]), 211.80, places=2)
        self.assertAlmostEqual(sum(ab.TIER_COL_SETS["right"]), 202.10, places=2)

    def test_unique_mods_grid(self):
        self.assertAlmostEqual(ab.UNIQ_GRID_TOP, 397.10, places=2)
        self.assertAlmostEqual(ab.UNIQ_HEADER_H, 22.30, places=2)
        self.assertEqual(len(ab.UNIQ_COLS), len(ab.UNIQ_HEADERS))
        self.assertAlmostEqual(sum(ab.UNIQ_COLS), ab.CONTENT_W, places=1)


class DataRulesTest(unittest.TestCase):
    """Правила: чего нет в данных — того нет и в книге."""

    def test_leather_has_no_helmet(self):
        b = book()
        areas = b.areas("armor", "leatherArmor")
        self.assertNotIn("Head", areas)
        self.assertEqual(set(areas), {"Body", "Leg", "Hand"})

    def test_metal_has_helmet(self):
        b = book()
        self.assertIn("Head", b.areas("armor", "metalArmor"))

    def test_power_armor_has_hp_row(self):
        b = book()
        piece = b.tier_pieces("powerArmor", "t45")[0]
        labels = [label for _key, label in ab.stat_fields(piece)]
        self.assertIn("ПРОЧНОСТЬ", labels)
        self.assertGreater(piece["hp"], 0)

    def test_full_body_piece_drawn_once(self):
        b = book()
        pieces = b.tier_pieces("armor", "vaultSecurityArmor")
        slots = ab.char_grid_slots(pieces)
        # две детали: шлем и «на всё тело» — ровно две ячейки, без повторов
        self.assertEqual(len(slots), 2)
        ids = [piece["id"] for _area, piece in slots]
        self.assertEqual(len(ids), len(set(ids)))

    def test_vault_security_has_no_second_page(self):
        b = book()
        spec = ab.Spec("armor", "vaultSecurityArmor")
        self.assertFalse(ab.has_second_page(b, spec))

    def test_leather_has_second_page(self):
        b = book()
        self.assertTrue(ab.has_second_page(b, ab.Spec("armor", "leatherArmor")))

    def test_mods_rows_skip_missing_areas(self):
        b = book()
        labels = [label for label, _ in ab.mods_rows(b, "armor", "leatherArmor")]
        self.assertEqual(labels, ["НАГРУДНИК", "НАРУЧ", "ПОНОЖ", "УНИКАЛЬНАЯ"])

    def test_mods_rows_are_data_driven(self):
        """Строка «ШЛЕМ» появляется только если у шлема есть модификации.

        В armor_mods.json моды есть лишь для тела, рук и ног, поэтому даже
        у металлической брони (шлем в комплекте есть) строки «ШЛЕМ» нет —
        печатать пустую строку нельзя.
        """
        b = book()
        labels = [label for label, _ in ab.mods_rows(b, "armor", "metalArmor")]
        self.assertEqual(labels, ["НАГРУДНИК", "НАРУЧ", "ПОНОЖ", "УНИКАЛЬНАЯ"])
        head_mods = [mod for mod in b.mods
                     if "Head" in (mod.get("protectedAreas") or [])]
        self.assertTrue(not head_mods)
        # а сама деталь «шлем» в комплекте есть и печатается в сетке таблиц
        slots = ab.char_grid_slots(b.tier_pieces("armor", "metalArmor"))
        self.assertIn("Head", [area for area, _piece in slots])

    def test_all_sets_present(self):
        b = book()
        for collection in ("armor", "powerArmor", "clothes"):
            specs = ab.auto_specs(b, collection)
            self.assertTrue(specs, collection)
            for spec in specs:
                self.assertTrue(spec.title, spec.set)
                self.assertTrue(b.tier_pieces(collection, spec.set), spec.set)


class LayoutHelpersTest(unittest.TestCase):
    def setUp(self):
        self.book = book()
        ab.register_fonts()

    def test_cell_lines_breaks_long_word(self):
        narrow = 60.0
        lines = ab.cell_lines("Звукоизолированная", narrow, ab.MODS_FONT)
        self.assertGreater(len(lines), 1)
        for line in lines:
            self.assertLessEqual(ab.sw(line, ab.FONT, ab.MODS_FONT), narrow)

    def test_cell_lines_keeps_short_word_whole(self):
        lines = ab.cell_lines("Мягкая", 70.0, ab.MODS_FONT)
        self.assertEqual(lines, ["Мягкая"])

    def test_lorem_is_placeholder(self):
        self.assertTrue(ab.is_placeholder(
            "Lorem ipsum dolor sit amet, consectetur adipiscing elit."))
        self.assertFalse(ab.is_placeholder(
            "Кожаная броня — практичная и доступная защита пустошей."))

    def test_tier_columns_scale(self):
        cols = ab.tier_columns(ab.TIER_COL_SETS["left"], 3)
        self.assertEqual(cols, list(ab.TIER_COL_SETS["left"]))
        four = ab.tier_columns(ab.TIER_COL_SETS["left"], 4)
        self.assertEqual(len(four), 5)
        two = ab.tier_columns(ab.TIER_COL_SETS["left"], 2)
        self.assertEqual(len(two), 3)
        self.assertAlmostEqual(sum(two), sum(ab.TIER_COL_SETS["left"]), places=1)

    def test_mods_label_fits_longest(self):
        rows = [("НАГРУДНИК", ["Мягкая"]), ("УНИКАЛЬНАЯ", ["Клёпаная кожа"])]
        label_w = ab.mods_label_width(rows)
        widest = max(ab.sw(label, ab.FONT_B, ab.MODS_FONT) for label, _ in rows)
        self.assertGreaterEqual(label_w, widest)
        self.assertLessEqual(label_w + sum(ab.mods_col_widths(label_w)),
                             ab.CONTENT_W + 0.01)


@unittest.skipIf(pymupdf is None, "нужен pymupdf для проверки PDF")
class RenderedPdfTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.book = book()
        cls.leather = Path(cls.tmp.name) / "leather.pdf"
        ab.build_book([ab.Spec("armor", "leatherArmor",
                               intro=["Кожаная броня — практичная и доступная "
                                      "защита пустошей."])],
                      cls.book, cls.leather, cover=False, sections=False)
        cls.full = Path(cls.tmp.name) / "book.pdf"
        specs = []
        for collection in ("armor", "powerArmor", "clothes"):
            specs.extend(ab.auto_specs(cls.book, collection))
        ab.build_book(specs, cls.book, cls.full)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def text(self, pdf: Path, page: int) -> str:
        with pymupdf.open(pdf) as doc:
            return doc[page].get_text()

    def test_leather_pages(self):
        with pymupdf.open(self.leather) as doc:
            self.assertEqual(doc.page_count, 2)
            first = doc[0].get_text()
            second = doc[1].get_text()
        self.assertIn("КОЖАНАЯ БРОНЯ", first)
        self.assertIn("СТАНДАРТНЫЙ КОМПЛЕКТ", first)
        self.assertIn("ПОДДЕРЖИВАЕМЫЕ МОДИФИКАЦИИ", first)
        self.assertIn("ВАРИАНТЫ", second)
        self.assertIn("УКРЕПЛЁННАЯ", second)
        self.assertIn("ТЯЖЁЛАЯ", second)
        self.assertIn("УНИКАЛЬНЫЕ МОДИФИКАЦИИ", second)
        self.assertIn("КОЖАНАЯ БРОНЯ", second)

    def test_leather_has_no_helmet_text(self):
        first = self.text(self.leather, 0)
        self.assertNotIn("ШЛЕМ", first)
        self.assertIn("НАГРУДНИК", first)
        self.assertIn("НАРУЧ", first)
        self.assertIn("ПОНОЖ", first)

    def test_unique_mods_values(self):
        second = self.text(self.leather, 1)
        for value in ("+1", "+2", "+3", "+4", "БРОННИК 1"):
            self.assertIn(value, second)

    def test_description_stays_above_heading(self):
        """Описание (даже обрезанное) не налезает на заголовок модов."""
        long_spec = ab.Spec("armor", "leatherArmor",
                            intro=["Слово " * 400, "Ещё абзац " * 200])
        ab.build_book([long_spec], book(), Path(self.tmp.name) / "long.pdf",
                      cover=False, sections=False)
        with pymupdf.open(Path(self.tmp.name) / "long.pdf") as doc:
            spans = [s for b in doc[0].get_text("dict")["blocks"]
                     for line in b.get("lines", []) for s in line["spans"]]
        heading = [s for s in spans
                   if s["text"] == "ПОДДЕРЖИВАЕМЫЕ МОДИФИКАЦИИ"][0]
        desc = [s for s in spans if s["size"] == ab.DESC_SIZE]
        self.assertTrue(desc)
        lowest = max(s["bbox"][3] for s in desc)
        self.assertLess(lowest, heading["bbox"][1])

    def test_no_lorem_ipsum(self):
        first = self.text(self.leather, 0)
        self.assertNotIn("lorem", first.lower())
        self.assertIn("Кожаная броня", first)

    def test_full_book_sections(self):
        with pymupdf.open(self.full) as doc:
            pages = doc.page_count
            all_text = "\n".join(doc[i].get_text() for i in range(pages))
        self.assertIn("СПРАВОЧНИК БРОНИ", all_text)
        self.assertIn("БРОНЯ", all_text)
        self.assertIn("СИЛОВАЯ БРОНЯ", all_text)
        self.assertIn("ОДЕЖДА", all_text)
        # 15 наборов: 6 брони + 6 силовой + 3 группы одежды
        self.assertGreaterEqual(pages, 15)

    def test_power_armor_page_has_hp_row(self):
        with pymupdf.open(self.full) as doc:
            texts = [doc[i].get_text() for i in range(doc.page_count)]
        t45 = [t for t in texts if "СИЛОВАЯ БРОНЯ Т-45" in t][0]
        self.assertIn("ПРОЧНОСТЬ", t45)

    def test_labels_do_not_overlap_tables(self):
        """Подписи деталей не должны налезать ни на свою, ни на чужую таблицу."""
        with pymupdf.open(self.full) as doc:
            for page in doc:
                spans = []
                for block in page.get_text("dict")["blocks"]:
                    for line in block.get("lines", []):
                        for span in line["spans"]:
                            spans.append(span)
                labels = [s for s in spans if s["text"] in
                          ("ШЛЕМ", "НАГРУДНИК", "НАРУЧ", "ПОНОЖ")
                          and s["size"] >= 12.0]
                # и метки строк таблиц (11 pt, белые), и шапки матриц (10 pt)
                values = [s for s in spans
                          if s["text"] in ("ФИЗ. СУ", "ЭНРГ. СУ", "РАД. СУ")
                          and s["size"] in (11.0, 10.0)]
                for label in labels:
                    for value in values:
                        overlap = (label["bbox"][3] > value["bbox"][1]
                                   and value["bbox"][3] > label["bbox"][1]
                                   and label["bbox"][2] > value["bbox"][0]
                                   and value["bbox"][2] > label["bbox"][0])
                        self.assertFalse(
                            overlap,
                            f'{label["text"]} налезает на {value["text"]} '
                            f'({label["bbox"]} / {value["bbox"]})')


if __name__ == "__main__":
    unittest.main()
