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
        """Внешняя 6+6: изображение слева, вложенные таблицы 2×2 справа."""
        self.assertAlmostEqual(ab.CHAR_TABLE_TOP_UPPER, 167.33, places=2)
        self.assertAlmostEqual(ab.CHAR_ROW_H, 23.30, places=2)
        # Внешняя строка делит контент строго пополам; левая col-6 полностью
        # отдана иллюстрации, правая — вложенной сетке характеристик.
        self.assertAlmostEqual(ab.CHAR_OUTER_COL_W, ab.CONTENT_W / 2.0, places=2)
        self.assertAlmostEqual(ab.IMAGE_BOX[0], ab.MARGIN_L, places=2)
        self.assertAlmostEqual(ab.IMAGE_BOX[2], ab.CHAR_GRID_X, places=2)
        self.assertAlmostEqual(ab.CHAR_GRID_X, ab.MARGIN_L + ab.CHAR_OUTER_COL_W,
                               places=2)
        # Две вложенные col-6 и явный gutter занимают ровно правую половину.
        self.assertAlmostEqual(ab.CHAR_LEFT_X, ab.CHAR_GRID_X, places=2)
        self.assertAlmostEqual(ab.CHAR_TABLE_W["left"], ab.CHAR_INNER_TABLE_W,
                               places=2)
        self.assertAlmostEqual(ab.CHAR_TABLE_W["right"], ab.CHAR_INNER_TABLE_W,
                               places=2)
        horizontal_gap = ab.CHAR_RIGHT_X - (ab.CHAR_LEFT_X + ab.CHAR_TABLE_W["left"])
        self.assertAlmostEqual(horizontal_gap, ab.CHAR_COL_GAP, places=2)
        self.assertGreaterEqual(horizontal_gap, 12.0)
        self.assertAlmostEqual(ab.CHAR_RIGHT_X + ab.CHAR_TABLE_W["right"],
                               ab.CONTENT_R, places=2)
        # 6 строк по 23.3 = 307.13 — низ верхних таблиц.
        self.assertAlmostEqual(ab.CHAR_TABLE_TOP_UPPER + 6 * ab.CHAR_ROW_H,
                               307.13, places=2)

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

    def test_cell_lines_keeps_long_word_whole(self):
        narrow = 60.0
        lines = ab.cell_lines("Звукоизолированная", narrow, ab.MODS_FONT)
        self.assertEqual(lines, ["Звукоизолированная"])

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

    def test_mod_cell_shrinks_instead_of_breaking_word(self):
        """Длинное слово остаётся целым, а не «Сервопривод / ы» в ячейке."""
        cell = ab.fitted_mod_cell("Сервоприводы движения", 66.0, ab.MODS_FONT)
        self.assertEqual(cell["lines"], ["Сервоприводы", "движения"])
        self.assertLess(cell["font"], ab.MODS_FONT)
        for line in cell["lines"]:
            self.assertLessEqual(ab.sw(line, ab.FONT, cell["font"]),
                                 66.0 - 2 * ab.CELL_PAD + 0.01)


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
        # Это именно заметный провал, а не лишь технический отступ референса.
        self.assertGreater(geometry["lower_top"] - upper_bottom, 60.0)
        self.assertGreater(geometry["lower_label"] - upper_bottom, 25.0)
        self.assertGreater(geometry["lower_top"],
                           geometry["lower_label"] + ab.CHAR_PIECE_SIZE_BOT)

    def test_gap_scales_with_rows(self):
        """Семь строк — тоже прогал, а не наложение."""
        geometry = ab.char_grid_geometry([{"hp": 7}])
        upper_bottom = geometry["upper_top"] + 7 * ab.CHAR_ROW_H
        self.assertGreater(geometry["lower_label"], upper_bottom)

    # -- моды силовой брони --------------------------------------------

    def test_pa_common_list_and_unique_details_are_separated(self):
        """На листе 1 — общие моды, на листе 2 — 20 уникальных улучшений."""
        grid = self.book.pa_mods_grid("t45")
        self.assertEqual([label for label, _ in grid], ["СИСТЕМА", "ОБШИВКА"])
        system = dict(grid)["СИСТЕМА"]
        self.assertIn("Датчик", system)
        self.assertIn("Реакторный узел", system)
        armour = dict(grid)["ОБШИВКА"]
        self.assertIn("Титановая обшивка", armour)

        upgrades = self.book.pa_upgrade_mods("t45")
        names = [self.book.mod_names[mod["id"]] for mod in upgrades]
        self.assertEqual(len(upgrades), 20)
        self.assertEqual(names[:4], ["Т-45b · шлем", "Т-45b · нагрудник",
                                     "Т-45b · наручи", "Т-45b · поножи"])
        self.assertEqual(names[-1], "Т-45f · поножи")
        common_ids = self.book.pa_common_mod_ids()
        self.assertFalse({mod["id"] for mod in upgrades} & common_ids)

    def test_pa_common_catalog_has_effects_and_real_slots(self):
        common = self.book.pa_common_mods()
        self.assertEqual(len(common), 27)
        scrubber = next(mod for mod in common if mod["id"] == "pa_systeme_epurateurradiations")
        self.assertIn("Игнорируйте радиационный урон", ab.mod_effect_text(self.book, scrubber))
        self.assertEqual(self.book.pa_compatible_areas(scrubber), ["Head"])
        plating = next(mod for mod in common if mod["id"] == "pa_blindage_titane")
        self.assertEqual(self.book.pa_compatible_areas(plating),
                         ["Head", "Body", "Hand", "Leg"])

    def test_pa_frame_has_no_mods(self):
        """У каркаса модов нет — блок не печатается вовсе."""
        self.assertEqual(self.book.pa_mods_grid("frame"), [])
        self.assertEqual(self.book.pa_upgrade_matrix("frame"), ([], []))

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
        """У Т-45 нет Mk II…Mk VI, а у X-01 нет ступеней Т-45."""
        t45 = self.book.pa_upgrade_mods("t45")
        self.assertTrue(all(self.book.mod_names[mod["id"]].startswith("Т-45")
                            for mod in t45), t45)
        x01 = self.book.pa_upgrade_mods("x01")
        self.assertTrue(all(self.book.mod_names[mod["id"]].startswith("Mk")
                            for mod in x01), x01)
        self.assertEqual(len(t45), 20)
        self.assertEqual(len(x01), 20)
        helmet = next(piece for piece in self.book.tier_pieces("powerArmor", "t45")
                      if ab.area_of(piece) == "Head")
        upgrade_groups = {mod["upgradeGroup"]
                          for mod in self.book.pa_mods_for_piece("t45", helmet)
                          if mod.get("modSlot") == "amelioration"}
        self.assertEqual(upgrade_groups, set(ab.PA_UPGRADE_GROUPS["t45"]))

    def test_pa_exclusive_systems_stay_with_their_model(self):
        """Вваренная арматура рейдеров и ЭМИ-защита X-01 не попадают в каталог."""
        raider = self.book.pa_unique_mods_for_set("raiderPower")
        x01 = self.book.pa_unique_mods_for_set("x01")
        self.assertIn("Вваренная арматура",
                      [self.book.mod_names[mod["id"]] for mod in raider])
        self.assertIn("ЭМИ-защита",
                      [self.book.mod_names[mod["id"]] for mod in x01])
        common = {mod["id"] for mod in self.book.pa_common_mods()}
        self.assertFalse({mod["id"] for mod in raider} & common)
        self.assertFalse({mod["id"] for mod in x01} & common)

    def test_pa_source_has_no_paint_slot(self):
        """Не добавляем окраски: в источнике helper их для силовой брони нет."""
        self.assertEqual({mod["modSlot"] for mod in self.book.power_armor_mods},
                         {"systeme", "blindage", "amelioration"})

    # -- раскладка сетки модов -----------------------------------------

    def test_every_mod_is_drawn(self):
        """Ни один мод не теряется: строк столько, сколько нужно на все."""
        rows = [("СИСТЕМА", [f"мод {i}" for i in range(21)]),
                ("ОБШИВКА", [f"плита {i}" for i in range(6)])]
        layout = ab.fit_mods_grid(rows)
        drawn = sum(len(row[0]) for section in layout["sections"]
                    for row in section["rows"])
        self.assertEqual(drawn, len(rows[0][1]) + len(rows[1][1]))

    def test_pa_common_grid_fits_on_first_page(self):
        """Короткий список общих модов остаётся на первом листе модели."""
        for key in self.book.power_armor:
            rows = self.book.pa_mods_grid(key)
            if not rows:
                continue
            layout = ab.fit_mods_grid(rows)
            self.assertGreaterEqual(layout["top"], ab.MODS_GRID_TOP, key)
            self.assertLessEqual(layout["bottom"], ab.MODS_GRID_BOTTOM, key)
            self.assertLessEqual(layout["bottom"], ab.PAGE_NUMBER_TOP, key)

    def test_cells_have_padding_without_word_fragments(self):
        """Строки не упираются в рамку и длинное слово не разрезается."""
        rows = [("СИСТЕМА", ["Форсированные сервоприводы"])]
        layout = ab.fit_mods_grid(rows)
        cells = layout["sections"][0]["rows"][0][0]
        width = layout["col_widths"][0]
        self.assertEqual(" ".join(cells[0]["lines"]),
                         "Форсированные сервоприводы")
        for cell in cells:
            for line in cell["lines"]:
                self.assertLessEqual(ab.sw(line, ab.FONT, cell["font"]),
                                     width - 2 * ab.CELL_PAD + 0.01)

    def test_pa_detail_cells_fit_without_word_fragments(self):
        """Каталог эффектов и уникальные таблицы не режут слова по буквам."""
        # Проверяем по отдельности, потому что у двух типов таблиц разная
        # сетка колонок и разный внутренний отступ.
        for row in ab.pa_detail_rows(self.book, self.book.pa_common_mods()):
            for index, (cell, width) in enumerate(zip(row["cells"], ab.PA_DETAIL_COLS)):
                font = ab.FONT_B if index == 0 else ab.FONT
                for line in cell["lines"]:
                    self.assertLessEqual(ab.sw(line, font, cell["font"]),
                                         width - 2 * ab.PA_DETAIL_PAD + 0.01)
        for row in ab.pa_unique_rows(self.book, self.book.pa_upgrade_mods("t45")):
            for index, (cell, width) in enumerate(zip(row["cells"], ab.PA_UNIQUE_COLS)):
                font = ab.FONT_B if index == 0 else ab.FONT
                for line in cell["lines"]:
                    self.assertLessEqual(ab.sw(line, font, cell["font"]),
                                         width - 2 * ab.PA_UNIQUE_PAD + 0.01)
        long_name = next(row for row in ab.pa_detail_rows(
            self.book, self.book.pa_common_mods())
            if "Фотоэлектрическое" in " ".join(row["cells"][0]["lines"]))
        self.assertEqual(" ".join(long_name["cells"][0]["lines"]),
                         "Фотоэлектрическое покрытие")

    def test_all_mod_grid_words_stay_whole(self):
        """Ни одна сетка не режет длинное русское слово посередине."""
        rows_by_set = [ab.mods_rows(self.book, "armor", key)
                       for key in self.book.armor]
        rows_by_set += [ab.clothes_mods_rows(
            self.book, self.book.clothes_item(spec.set, spec.item))
            for spec in ab.auto_specs(self.book, "clothes")]
        rows_by_set += [self.book.pa_mods_grid(key)
                        for key in self.book.power_armor]
        for rows in rows_by_set:
            if not rows:
                continue
            layout = ab.fit_mods_grid(rows)
            cells = [cell for section in layout["sections"]
                     for row, _height in section["rows"] for cell in row]
            expected = [name for _label, names in rows for name in names]
            actual = [" ".join(cell["lines"]) for cell in cells]
            self.assertEqual(actual, expected)

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
        # 6 комплектов брони, 6 силовой брони, 5 страниц её уникальных
        # модификаций, 3 страницы общего каталога и 32 страницы одежды.
        self.assertEqual(pages, 61)
        self.assertIn("МОДИФИКАЦИИ СИЛОВОЙ БРОНИ", all_text)
        self.assertIn("ОБЩИЙ СПРАВОЧНИК", all_text)

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
        """Общие эффекты и уникальные моды каждой модели попали в PDF."""
        with pymupdf.open(self.full) as doc:
            source_pages = [(page.get_text().splitlines(), "".join(page.get_text().split()))
                            for page in doc if page.get_text().splitlines()]
        pages = {lines[0]: text for lines, text in source_pages}

        catalog = "".join(text for lines, text in source_pages
                            if lines[0] == "МОДИФИКАЦИИ СИЛОВОЙ БРОНИ")
        self.assertEqual(len([1 for lines, _text in source_pages
                              if lines[0] == "МОДИФИКАЦИИ СИЛОВОЙ БРОНИ"]),
                         len(ab.pa_common_catalog_pages(self.book)))
        for mod in self.book.pa_common_mods():
            name = self.book.mod_names[mod["id"]]
            self.assertIn("".join(name.split()), catalog, name)
            effect = ab.pa_effect_text(self.book, mod)
            self.assertNotEqual(effect, "—", name)
            self.assertIn("".join(effect.split()), catalog, name)

        for key in self.book.power_armor:
            title_raw = self.book.set_title("powerArmor", key).upper()
            title = "".join(title_raw.split())
            standard = [text for lines, text in source_pages if lines[0] == title_raw]
            self.assertEqual(len(standard), 1, key)
            for _label, names in self.book.pa_mods_grid(key):
                for name in names:
                    self.assertIn("".join(name.split()), standard[0], (key, name))

            unique_pages = [text for lines, text in source_pages
                            if lines[0] == "УНИКАЛЬНЫЕ МОДИФИКАЦИИ" and title in text]
            if key == "frame":
                self.assertFalse(unique_pages)
                continue
            self.assertEqual(len(unique_pages), 1, key)
            page = unique_pages[0]
            for mod in self.book.pa_unique_mods_for_set(key):
                name = self.book.mod_names[mod["id"]].replace(" · ", " ")
                self.assertIn("".join(name.split()), page, (key, name))
                effect = ab.mod_effect_text(self.book, mod)
                if effect:
                    self.assertIn("".join(effect.split()), page, (key, name))

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
