# -*- coding: utf-8 -*-
"""Тесты генератора страниц брони."""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from armor2page import Companion, render_page

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "companion"
SPEC = json.loads((ROOT / "data" / "armor-pages" / "leather-armor.json").read_text(encoding="utf-8"))


class LeatherPageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.companion = Companion(DATA)
        cls.html = render_page(SPEC, cls.companion)

    def test_standard_cards(self) -> None:
        self.assertEqual(self.html.count('<article class="armor-card">'), 3)
        self.assertIn("Кожаный Нагрудник", self.html)
        self.assertIn("<td>25</td>", self.html)  # цена обычного нагрудника
        self.assertIn("Стандартная", self.html)

    def test_delta_tables(self) -> None:
        self.assertEqual(self.html.count('<table class="sppb-table armor-delta-table">'), 2)
        for title in ("Укреплённая", "Тяжёлая"):
            self.assertIn(f'>{title}</button>', self.html)
        # укреплённый нагрудник: +1 ФИЗ, +1 ЭНРГ, +5 вес, +25 цена
        self.assertIn(
            '<th scope="row">ФИЗ. СУ</th><td>+1</td><td>+1</td><td>+1</td>',
            self.html,
        )
        self.assertIn('<th scope="row">ВЕС</th><td>+5</td><td>+3</td><td>+3</td>', self.html)

    def test_tabs_and_accordions(self) -> None:
        for title in ("Категории", "Модификации обшивки", "Улучшения"):
            self.assertIn(f'>{title}</button>', self.html)
        self.assertEqual(self.html.count('class="armor-tab-toggle"'), 3)
        self.assertEqual(self.html.count('class="sppb-accordion-item">'), 19)  # 2 + 12 + 5
        self.assertEqual(self.html.count('data-label="Модификация"'), 17)

    def test_tab_panels_are_closed_by_default(self) -> None:
        self.assertEqual(self.html.count('class="armor-tab-panel"'), 3)
        self.assertEqual(len(re.findall(r'class="armor-tab-panel"[^>]* hidden', self.html)), 3)
        self.assertNotIn('<ul class="sppb-tabs-nav"', self.html)

    def test_one_accordion_per_tab(self) -> None:
        # обработчик закрывает соседние спойлеры внутри панели вкладки
        self.assertIn(".armor-tab-panel .sppb-accordion-toggle", self.html)
        self.assertIn("function closeItem", self.html)

    def test_layout_order(self) -> None:
        hero = self.html[self.html.index('<div class="armor-container armor-hero">'):]
        self.assertLess(hero.index('armor-hero-media'), hero.index('armor-hero-stats'))
        self.assertGreater(self.html.index('<div class="armor-container armor-lead">'), self.html.index('<div class="armor-container armor-hero">'))

    def test_mobile_table_css(self) -> None:
        self.assertIn(".armor-mods-table td::before", self.html)
        self.assertIn("content:attr(data-label)", self.html)
        self.assertIn("background:#000;color:#fff", self.html)
        self.assertIn(".armor-delta-mobile{display:grid", self.html)
        self.assertIn(".armor-tab-panel{display:none", self.html)
        self.assertIn(".armor-tab.is-open .armor-tab-panel{display:block}", self.html)

    def test_mobile_delta_tables(self) -> None:
        self.assertEqual(self.html.count('class="armor-delta-mobile-piece"'), 6)  # 2 уровня × 3 детали
        self.assertIn('<th colspan="2">НАГРУДНИК</th>', self.html)

    def test_mod_effect_and_areas(self) -> None:
        self.assertIn("+2 к сопротивлению взрывным повреждениям.", self.html)
        self.assertIn("Бронник 1", self.html)
        self.assertIn("Тело, Руки, Ноги", self.html)

    def test_no_python_artifacts(self) -> None:
        self.assertNotIn('"None"', self.html)
        self.assertNotIn("{title}", self.html)
        self.assertNotIn("{esc(", self.html)


if __name__ == "__main__":
    unittest.main()
