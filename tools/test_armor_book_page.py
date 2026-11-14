# -*- coding: utf-8 -*-
"""Тесты тестовой страницы брони в стиле книги оружия."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from armor_book_page import Companion, render_mods_table, render_page, set_totals

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "companion"
SPEC = json.loads((ROOT / "data" / "armor-pages" / "leather-armor-book.json").read_text(encoding="utf-8"))


class LeatherBookPageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.companion = Companion(DATA)
        cls.html = render_page(SPEC, cls.companion)

    def test_book_style_elements(self) -> None:
        # фон и гамма книги оружия
        self.assertIn("assets/pdf/paper.jpg", self.html)
        self.assertIn("#ffebcd", self.html)
        self.assertIn("#ffc674", self.html)
        # шрифты книги
        self.assertIn("Carlito-Regular.ttf", self.html)
        self.assertIn("Carlito-Bold.ttf", self.html)
        # заголовок и линейка
        self.assertIn("Кожаная броня", self.html)
        self.assertIn("ab-rule", self.html)

    def test_base_cards(self) -> None:
        self.assertEqual(self.html.count('<article class="ab-card">'), 3)
        self.assertIn("Кожаный Нагрудник", self.html)
        self.assertIn("Кожаный Понож", self.html)
        self.assertIn("Кожаный Наруч", self.html)

    def test_tier_delta_tables(self) -> None:
        self.assertIn("Укреплённая", self.html)
        self.assertIn("Тяжёлая", self.html)
        self.assertEqual(self.html.count('<table class="ab-delta-table">'), 2)
        # дельта для укреплённого нагрудника: +1 ФИЗ, +1 ЭНРГ
        self.assertIn("+1", self.html)

    def test_mods_table_like_weapon_book(self) -> None:
        # столбец метки + колонки модов, чередование бежевого/оранжевого
        self.assertIn("Поддерживаемые модификации", self.html)
        self.assertIn("ab-mod-label", self.html)
        self.assertIn("ab-fill-beige", self.html)
        self.assertIn("ab-fill-orange", self.html)
        # названия модов
        for name in ("Мягкая", "Асбестовая подкладка", "Плотная", "Парирующая"):
            self.assertIn(name, self.html)

    def test_unique_mods_block(self) -> None:
        self.assertIn("УНИКАЛЬНЫЙ", self.html)
        self.assertIn("Вываренная кожа", self.html)
        self.assertIn("Клёпаная кожа", self.html)

    def test_set_totals(self) -> None:
        comp = self.companion
        set_data = comp.armor["leatherArmor"]
        pieces = [p for p in set_data["tiers"]["standard"]["pieces"]]
        totals = set_totals(pieces)
        self.assertEqual(totals["weight"], 9)   # 5 + 2 + 2
        self.assertEqual(totals["cost"], 43)    # 25 + 10 + 8
        self.assertEqual(totals["rarity"], 1)


if __name__ == "__main__":
    unittest.main()
