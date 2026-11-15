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
        # Матрица из шлема и трёх частей справа не пересекает край набора.
        bounded = ab.bounded_tier_columns(ab.TIER_RIGHT_X,
                                          ab.TIER_COL_SETS["right"], 4)
        self.assertEqual(len(bounded), 5)
        self.assertLessEqual(ab.TIER_RIGHT_X + sum(bounded),
                             ab.CONTENT_R + 0.01)

    def test_mods_label_fits_longest(self):
        rows = [("НАГРУДНИК", ["Мягкая"]), ("УНИКАЛЬНАЯ", ["Клёпаная кожа"])]
        label_w = ab.mods_label_width(rows)
        widest = max(ab.sw(label, ab.FONT_B, ab.MODS_FONT) for label, _ in rows)
        self.assertGreaterEqual(label_w, widest)
        self.assertLessEqual(label_w + sum(ab.mods_col_widths(label_w)),
                             ab.CONTENT_W + 0.01)


class RoundTwoTest(unittest.TestCase):
    """Прогал между таблицами, моды силовой брони, страницы одежды."""

    def setUp(self):
        self.book = book()
        ab.register_fonts()

    # -- прогал между рядами таблиц -------------------------------------

    def test_gap_between_char_rows(self):
        """Нижний ряд таблиц не приклеен к верхнему: подпись — в прогале."""
        geometry = ab.char_grid_geometry([{}])
        upper_bottom = geometry["upper_top"] + 6 * ab.CHAR_ROW_H
        self.assertGreater(geometry["lower_label"] - upper_bottom,
                           ab.CHAR_ROW_GAP)
        # подпись — по центру прогала, а не у кромки верхней таблицы
        self.assertAlmostEqual(geometry["lower_label"] - upper_bottom,
                               ab.CHAR_ROW_GAP + ab.CHAR_ROW_GAP_EXTRA / 2.0,
                               places=2)
        # прогал больше, чем в референсе (23.67), и таблица ниже подписи
        self.assertGreater(geometry["lower_top"] - upper_bottom, 23.67)
        self.assertGreater(geometry["lower_top"],
                           geometry["lower_label"] + ab.CHAR_PIECE_SIZE_BOT)

    def test_gap_scales_with_rows(self):
        """Семь строк — тоже прогал, а не наложение."""
        geometry = ab.char_grid_geometry([{"hp": 7}])
        upper_bottom = geometry["upper_top"] + 7 * ab.CHAR_ROW_H
        self.assertGreater(geometry["lower_label"], upper_bottom)

    # -- моды силовой брони --------------------------------------------

    def test_pa_mods_have_three_groups(self):
        grid = self.book.pa_mods_grid("t45")
        labels = [label for label, _ in grid]
        self.assertEqual(labels, ["СИСТЕМА", "ОБШИВКА", "УЛУЧШЕНИЯ"])
        system = dict(grid)["СИСТЕМА"]
        self.assertIn("Датчик", system)
        self.assertIn("Реакторный узел", system)
        armour = dict(grid)["ОБШИВКА"]
        self.assertIn("Титановая обшивка", armour)
        levels = dict(grid)["УЛУЧШЕНИЯ"]
        self.assertEqual(levels[:2], ["Т-45b · шлем", "Т-45c · шлем"])

    def test_pa_frame_has_no_mods(self):
        """У каркаса модов нет — блок не печатается вовсе."""
        self.assertEqual(self.book.pa_mods_grid("frame"), [])

    def test_raider_pa_has_no_plating(self):
        labels = [label for label, _ in self.book.pa_mods_grid("raiderPower")]
        self.assertNotIn("ОБШИВКА", labels)
        self.assertIn("СИСТЕМА", labels)

    def test_x01_has_no_winterized_plating(self):
        """В helper антифризное покрытие X-01 не положено — и в книге его нет."""
        armour = dict(self.book.pa_mods_grid("x01"))["ОБШИВКА"]
        self.assertNotIn("Антифризное покрытие", armour)
        self.assertIn("Призматическая обшивка", armour)

    def test_pa_upgrades_belong_to_own_set(self):
        """У Т-45 нет улучшений X-01 (Mk II…Mk VI) и наоборот."""
        t45 = dict(self.book.pa_mods_grid("t45"))["УЛУЧШЕНИЯ"]
        self.assertTrue(all(name.startswith("Т-45") for name in t45), t45)
        x01 = dict(self.book.pa_mods_grid("x01"))["УЛУЧШЕНИЯ"]
        self.assertTrue(all(name.startswith("Mk") for name in x01), x01)
        helmet = next(piece for piece in self.book.tier_pieces("powerArmor", "t45")
                      if ab.area_of(piece) == "Head")
        upgrade_groups = {mod["upgradeGroup"]
                          for mod in self.book.pa_mods_for_piece("t45", helmet)
                          if mod.get("modSlot") == "amelioration"}
        self.assertEqual(upgrade_groups, set(ab.PA_UPGRADE_GROUPS["t45"]))

    # -- раскладка сетки модов -----------------------------------------

    def test_every_mod_is_drawn(self):
        """Ни один мод не теряется: строк столько, сколько нужно на все."""
        rows = [("СИСТЕМА", [f"мод {i}" for i in range(21)]),
                ("ОБШИВКА", [f"плита {i}" for i in range(6)])]
        layout = ab.fit_mods_grid(rows)
        drawn = sum(len(row[0]) for section in layout["sections"]
                    for row in section["rows"])
        self.assertEqual(drawn, len(rows[0][1]) + len(rows[1][1]))

    def test_mods_grid_stays_on_page(self):
        for key in self.book.power_armor:
            rows = self.book.pa_mods_grid(key)
            if not rows:
                continue
            layout = ab.fit_mods_grid(rows)
            # сетка не залезает на описание и не уходит под номер страницы
            self.assertGreater(layout["top"], ab.DESC_TOP, key)
            self.assertLessEqual(layout["bottom"], ab.PAGE_NUMBER_TOP, key)

    def test_cells_have_padding(self):
        """Перенос строк считает поля ячейки — текст не упирается в рамку."""
        rows = [("СИСТЕМА", ["Форсированные сервоприводы"])]
        layout = ab.fit_mods_grid(rows)
        section = layout["sections"][0]
        width = layout["col_widths"][0]
        for lines in section["rows"][0][0]:
            for line in lines:
                self.assertLessEqual(ab.sw(line, ab.FONT, layout["font"]),
                                     width - 2 * ab.CELL_PAD + 0.01)

    # -- одежда --------------------------------------------------------

    def test_clothes_one_page_per_item(self):
        specs = ab.auto_specs(self.book, "clothes")
        items = [item for group in self.book.clothes["clothes"]
                 for item in group["items"]]
        self.assertEqual(len(specs), len(items))
        self.assertEqual([spec.item for spec in specs],
                         [item["id"] for item in items])
        self.assertTrue(all(spec.title for spec in specs))
        blouse = next(spec for spec in specs if spec.item == "clothing_blouse")
        self.assertEqual(blouse.title, "Блузка")

    def test_clothes_mods_from_helper(self):
        """Плетение и подкладки — только у вещей, которым они положены."""
        b = self.book
        self.assertTrue(b.clothes_mod_groups("clothing_vault_jumpsuit"))
        labels = [label for label, _ in
                  b.clothes_mod_groups("clothing_vault_jumpsuit")]
        self.assertIn("ТКАНЕВАЯ ОСНОВА", labels)
        self.assertIn("ПОДКЛАДКА КОМБИНЕЗОНА", labels)
        self.assertEqual(b.clothes_mod_groups("headwear_skull_mask"), [])

    def test_clothes_stat_table_rows(self):
        """Таблица характеристик предмета — те же строки, что у брони."""
        b = self.book
        item = b.clothes_item("headwear", "headwear_casual_hat")
        labels = [label for _key, label in ab.stat_fields(item)]
        self.assertEqual(labels, ["ФИЗ. СУ", "ЭНРГ. СУ", "РАД. СУ",
                                  "ВЕС", "ЦЕНА", "РЕДКОСТЬ"])


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
        # 6 комплектов брони, 6 силовой брони и 32 страницы одежды.
        self.assertEqual(pages, 53)

    def test_clothes_page_title_is_drawn_once_and_translated(self):
        """У страницы вещи один заголовок; англоязычной «Blouse» в книге нет."""
        clothes = ab.auto_specs(self.book, "clothes")
        with pymupdf.open(self.full) as doc:
            pages = [page.get_text().splitlines() for page in doc]
        for spec in clothes:
            title = spec.title.upper()
            matches = [lines for lines in pages if lines and lines[0] == title]
            self.assertEqual(len(matches), 1, title)
            self.assertEqual(matches[0].count(title), 1, title)
        all_text = "\n".join("\n".join(lines) for lines in pages)
        self.assertIn("БЛУЗКА", all_text)
        self.assertNotIn("BLOUSE", all_text)

    def test_all_supported_mods_are_rendered(self):
        """Тексты всех модов из сеток действительно попали в итоговый PDF."""
        with pymupdf.open(self.full) as doc:
            pages = {page.get_text().splitlines()[0]: "".join(
                page.get_text().split()) for page in doc if page.get_text().splitlines()}
        for key in self.book.power_armor:
            page = pages[self.book.set_title("powerArmor", key).upper()]
            for _label, names in self.book.pa_mods_grid(key):
                for name in names:
                    self.assertIn("".join(name.split()), page, (key, name))
        for spec in ab.auto_specs(self.book, "clothes"):
            page = pages[spec.title.upper()]
            item = self.book.clothes_item(spec.set, spec.item)
            for _label, names in ab.clothes_mods_rows(self.book, item):
                for name in names:
                    self.assertIn("".join(name.split()), page, (spec.item, name))

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
