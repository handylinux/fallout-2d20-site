# -*- coding: utf-8 -*-
"""Regression tests for sppb2html.

Run with:  python3 -m unittest discover -s tools -v
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

import sppb2html

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"


def load(name: str):
    pages = sppb2html.load_pages(DATA / name)
    assert len(pages) == 1
    page = pages[0]
    by_id = {row["id"]: row for row in page.rows}
    return page, by_id


def expected_counts(page, by_id):
    """Count what should end up in the HTML."""
    stats = {"sections": 0, "columns": 0, "addons": 0, "tables": 0}

    def walk_row(row):
        stats["sections"] += 1
        for column in row.get("columns") or []:
            if not sppb2html.truthy(column.get("visibility", True)):
                continue
            stats["columns"] += 1
            for addon in column.get("addons") or []:
                if sppb2html.truthy(addon.get("visibility", True)):
                    walk_addon(addon)

    def walk_row_ref(ref):
        row = by_id.get(ref.get("id"))
        if row:
            walk_row(row)

    def walk_addon(addon):
        stats["addons"] += 1
        settings = addon.get("settings") or {}
        name = addon.get("name")
        if name == "row":
            row = by_id.get(addon.get("id"))
            if row:
                walk_row(row)
        elif name == "tab":
            for item in settings.get("sp_tab_item") or []:
                for ref in item.get("content") or []:
                    walk_row_ref(ref)
        elif name == "accordion":
            for item in settings.get("sp_accordion_item") or []:
                for ref in item.get("content") or []:
                    walk_row_ref(ref)
        elif name == "table_advanced":
            stats["tables"] += 1
            for item in settings.get("sp_table_advanced_item") or []:
                for sub in item.get("content") or []:
                    if sppb2html.truthy(sub.get("visibility", True)):
                        walk_addon(sub)
            for row in settings.get("table_advanced_item") or []:
                for cell in row.get("table_advanced_item") or []:
                    for sub in cell.get("content") or []:
                        if sppb2html.truthy(sub.get("visibility", True)):
                            walk_addon(sub)
        elif name == "text_block":
            stats["tables"] += len(re.findall(r"<table\b", settings.get("text") or "", re.I))

    for row in page.rows:
        if row.get("parent") or not sppb2html.truthy(row.get("visibility", True)):
            continue
        walk_row(row)
    return stats


class RenderTest(unittest.TestCase):
    def render(self, name):
        page, by_id = load(name)
        markup, renderer = sppb2html.render_page(
            page, asset_base=sppb2html.DEFAULT_SITE, link_base=sppb2html.DEFAULT_SITE
        )
        return page, by_id, markup, renderer

    def test_counts_supermutant(self):
        page, by_id, markup, renderer = self.render("supermutant.sppb.json")
        expected = expected_counts(page, by_id)
        self.assertEqual(dict(renderer.stats), expected)
        self.assertEqual(expected["sections"], 3)
        self.assertEqual(expected["columns"], 5)
        self.assertEqual(expected["tables"], 4)
        self.assertIn(f"sections={expected['sections']}", markup)

    def test_counts_power_armor(self):
        page, by_id, markup, renderer = self.render("ekskavatornaya-silovaya-bronya.sppb.json")
        expected = expected_counts(page, by_id)
        self.assertEqual(dict(renderer.stats), expected)
        self.assertEqual(expected["sections"], 29)
        self.assertEqual(expected["columns"], 34)
        self.assertEqual(expected["tables"], 26)

    def test_bestiary_hub(self):
        _, _, markup, renderer = self.render("bestiarij.sppb.json")
        self.assertEqual(renderer.stats["sections"], 2)
        self.assertEqual(renderer.stats["columns"], 5)
        self.assertEqual(renderer.stats["addons"], 13)
        self.assertEqual(renderer.stats["tables"], 0)
        # скрытая третья карточка «РОБОТЫ» во втором ряду не рендерится
        self.assertNotIn("column-5c6da0db", markup)
        self.assertEqual(markup.count('class="cta"'), 3)
        for href in (
            "bestiarij/zhivotnye-i-nasekomye",
            "bestiarij/raiders",
            "bestiarij/supermutanty",
        ):
            self.assertIn(href, markup)
        # кнопка: зарезервированная ширина под стрелки и анимация
        self.assertIn(
            ".cta span:nth-child(2){width:20px;margin-left:30px;position:relative;top:12%;"
            "transition:.5s;margin-right:0}",
            markup,
        )
        self.assertIn(".cta:hover span:nth-child(2){transition:.5s;margin-right:45px}", markup)
        self.assertIn("@keyframes cta-color-anim", markup)
        # заголовки карточек — как на хабе
        self.assertIn(
            "#sp-page-builder .sppb-addon-heading .sppb-addon-title{"
            "font-size:1.25rem;font-weight:400;line-height:1.3;text-transform:uppercase;"
            "letter-spacing:.02em;margin:0}",
            markup,
        )
        # карточки одинаковой высоты, кнопка прижата к низу
        self.assertIn("#sp-page-builder .sppb-addon-raw_html{margin-top:auto}", markup)

    def test_bootstrap_widths_are_taken_from_settings(self):
        _, _, markup, _ = self.render("supermutant.sppb.json")
        # 6+6 section: two half-width columns that stack on mobile
        self.assertIn("sppb-col-xl-6 sppb-col-lg-6 sppb-col-md-6 sppb-col-sm-12 sppb-col-12", markup)
        # 3+9 nested row inside the right column
        self.assertIn("sppb-col-xl-3 sppb-col-lg-3 sppb-col-md-3 sppb-col-sm-12 sppb-col-12", markup)
        self.assertIn("sppb-col-xl-9 sppb-col-lg-9 sppb-col-md-9 sppb-col-sm-12 sppb-col-12", markup)

    def test_mobile_description_clone(self):
        _, _, markup, _ = self.render("supermutant.sppb.json")
        body = markup.split("<body", 1)[1]
        self.assertIn("supermutant-desc-mobile", body)
        self.assertIn("supermutant-desc-original", body)
        # клон стоит после картинки и до правой колонки с характеристиками
        self.assertLess(body.index("supermutant-desc-mobile"), body.index("column-44a9ecf5"))
        self.assertIn(".supermutant-desc-mobile{display:none}", markup)
        self.assertIn("@media (max-width: 767.98px)", markup)

    def test_trait_headings_match_table_header(self):
        _, _, markup, _ = self.render("supermutant.sppb.json")
        # ОСОБЕННОСТИ/ИНВЕНТАРЬ — тот же кегль, что у шапки таблицы АТАКИ
        self.assertRegex(
            markup,
            r"#sppb-addon-b9917d63-\w+ \.sppb-addon-title,\s*"
            r"#sppb-addon-878d886e-\w+ \.sppb-addon-title\{"
            r"font-size:1rem;line-height:1\.5;padding:6px 0\}",
        )
        # текст этих блоков — как в ячейках таблиц
        for addon in ("d1d0a1ed", "b6817113", "8cb14d9b", "70dad39f"):
            self.assertIn(f"#sppb-addon-{addon}-", markup)
        self.assertIn(
            "font-size:1rem;line-height:1.5}\n@media (max-width: 767.98px)",
            markup,
        )

    def test_paddings_and_colors(self):
        _, _, supermutant, _ = self.render("supermutant.sppb.json")
        # section padding from JSON (xl only -> base rule)
        self.assertRegex(supermutant, r"#section-3869a425-\w+ \{ padding: 15px 0px 5px 0px")
        # the black trait/inventory heading with white text
        self.assertRegex(
            supermutant,
            r"#sppb-addon-b9917d63-\w+ \{ background-color: #000; color: rgb\(255, 255, 255\); \}",
        )
        # beige trait box + its padding
        self.assertRegex(
            supermutant,
            r"#sppb-addon-d1d0a1ed-\w+ \{ padding: 5px 0px 5px 0px; background-color: rgb\(255, 228, 181\); \}",
        )
        # image width from image_width
        self.assertIn('style="width: 300px"', supermutant)
        # shortcodes are converted
        self.assertIn("images/CD.png", supermutant)
        self.assertNotIn("{/CD}", supermutant)

        _, _, armor, _ = self.render("ekskavatornaya-silovaya-bronya.sppb.json")
        # cream section with the yellow offset shadow, 5% side margins
        self.assertRegex(
            armor,
            r"#section-43e6f971-\w+ \{ padding: 25px 0px 25px 0px; margin: 0px 5% 0px 5%; "
            r"background-color: #f8f1da; box-shadow: 7px 7px 0px 0px #e1b91e; \}",
        )
        # tab colours
        self.assertIn("background-color: #F2C74B; color: #333333", armor)
        self.assertIn("background-color: #3366FF; color: #FFFFFF", armor)
        # accordion item background + border radius
        self.assertIn("background-color: #FFFFFF", armor)
        self.assertIn("border-radius: 4px", armor)
        # advanced table header / rows
        self.assertIn("background-color: #000000", armor)
        self.assertIn("background-color: #F8F1DA", armor)
        # custom CSS from the accordion addon is carried over
        self.assertIn(".sppb-addon-table-main td {color: #000;}", armor)

    def test_cleanup(self):
        for name in ("supermutant.sppb.json", "ekskavatornaya-silovaya-bronya.sppb.json"):
            _, _, markup, renderer = self.render(name)
            self.assertNotIn("<mce:", markup)
            self.assertNotIn("{/CD}", markup)
            self.assertNotRegex(markup, r"\{[А-Яа-я]")
            self.assertEqual(renderer.warnings, [])
            self.assertIn('<html lang="ru">', markup)
            # every generated document is self-contained
            self.assertNotIn("<link", markup)
            self.assertNotIn("<script src", markup)

    def test_tabs_and_accordion_markup(self):
        _, _, armor, _ = self.render("ekskavatornaya-silovaya-bronya.sppb.json")
        self.assertIn('role="tablist"', armor)
        self.assertIn('id="sppb-tab1-1"', armor)
        self.assertIn('role="tabpanel"', armor)
        self.assertEqual(armor.count('class="sppb-accordion-item'), 21)
        # accordions are closed by default (openitem = hide)
        self.assertEqual(armor.count("aria-expanded=\"true\""), 0)

    def test_loader_formats(self):
        # raw array and phpMyAdmin dump both load through the same code path
        page, _ = load("supermutant.sppb.json")
        self.assertEqual(page.title, "Супермутант")
        self.assertEqual(page.language, "ru")
        wrapper = json.loads((DATA / "supermutant.sppb.json").read_text(encoding="utf-8"))
        self.assertEqual(json.loads(wrapper["template"])[0]["id"][:8], "3869a425")


if __name__ == "__main__":
    unittest.main()
