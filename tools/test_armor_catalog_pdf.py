# -*- coding: utf-8 -*-
"""Тесты каталога брони, силовой брони и одежды в PDF."""

from __future__ import annotations

import unittest
from pathlib import Path

from armor_catalog_pdf import (
    build_catalog_html,
    build_css,
    main,
)
from armor2page import Companion

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "companion"


class ArmorCatalogTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.companion = Companion(DATA)
        cls.html = build_catalog_html(cls.companion)

    def test_all_armor_sets(self) -> None:
        for name in ("Рейдерская броня", "Кожаная броня",
                     "Металлическая броня", "Боевая броня",
                     "Броня синтов", "Броня охранника Волт-Тек"):
            self.assertIn(name, self.html)

    def test_all_power_armor_sets(self) -> None:
        for name in ("Каркас", "Силовая броня рейдера",
                     "Силовая броня Т-45", "Силовая броня Т-51",
                     "Силовая броня Т-60", "Силовая броня X-01"):
            self.assertIn(name, self.html)

    def test_clothing_groups_and_items(self) -> None:
        # одежда из данных — группы и предметы
        self.assertIn("Костюмы", self.html)
        self.assertIn("Обмундирование", self.html)
        self.assertIn("Головные уборы", self.html)
        self.assertIn("Портупея", self.html)
        self.assertIn("Костюм бродяги", self.html)
        self.assertIn("Обычная шляпа", self.html)

    def test_clothing_reserved(self) -> None:
        # зарезервированные места под картинку/описание есть у одежды
        self.assertIn("ОДЕЖДА", self.html)
        self.assertIn("ИЗОБРАЖЕНИЕ", self.html)
        self.assertIn("ОПИСАНИЕ", self.html)

    def test_image_and_desc_placeholders(self) -> None:
        # зарезервированные места под изображение и описание
        self.assertIn("ИЗОБРАЖЕНИЕ", self.html)
        self.assertIn("ОПИСАНИЕ", self.html)

    def test_stat_rows_present(self) -> None:
        # характеристики реального текста
        self.assertIn("ФИЗ. СУ", self.html)
        self.assertIn("ЭНРГ. СУ", self.html)
        self.assertIn("РАД. СУ", self.html)
        self.assertIn("ВЕС", self.html)
        self.assertIn("ЦЕНА", self.html)
        self.assertIn("РЕДКОСТЬ", self.html)

    def test_power_armor_has_hp(self) -> None:
        # силовая броня — ПРОЧНОСТЬ
        self.assertIn("ПРОЧНОСТЬ", self.html)

    def test_item_names_from_data(self) -> None:
        # названия предметов из i18n
        self.assertIn("Кожаный Нагрудник", self.html)
        self.assertIn("Шлем Т-45", self.html)

    def test_fonts_registered(self) -> None:
        css = build_css()
        self.assertIn("@font-face", css)
        self.assertIn("Carlito-Regular.ttf", css)
        self.assertIn("Carlito-Bold.ttf", css)

    def test_cards_avoid_break(self) -> None:
        # карточки не ломаются при переносе страницы
        self.assertIn("page-break-inside:avoid", build_css())

    def test_main_builds_pdf(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "catalog.pdf"
            rc = main(["--data", str(DATA), "--out", str(out)])
            self.assertEqual(rc, 0)
            self.assertTrue(out.exists())
            self.assertGreater(out.stat().st_size, 0)


if __name__ == "__main__":
    unittest.main()
