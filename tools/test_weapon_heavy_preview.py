import tempfile
import json
import re
import unittest
from pathlib import Path

import pymupdf
import weapon2pdf as w
import weapon_heavy_preview as heavy
from weapons2cards import Companion


class HeavyPreviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        w.register_fonts()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.comp = Companion()

    def test_detailed_rows_use_prefix_override_and_real_effects(self):
        rows = heavy.build_rows(self.comp, 'weapon_flamer', {'mod_napalm_fuel': 'Напалмовый'})
        self.assertEqual(len(rows), sum(len(v) for v in self.comp.slots['weapon_flamer'].values()))
        napalm = next(values for slot, values in rows if values[0] == 'Напалм')
        self.assertEqual(napalm[1], 'Напалмовый')
        self.assertIn('Урон: +1 DC', napalm[2])
        self.assertEqual(napalm[3], '+7')

    def test_heavy_page_text_and_details_are_present(self):
        output = self.root / 'flamer.pdf'
        heavy.render_heavy(self.comp, 'weapon_flamer', 61, {}, output)
        with pymupdf.open(output) as doc:
            self.assertEqual(len(doc), 1)
            text = doc[0].get_text()
            for value in ('ОГНЕМЁТ', 'Напалм', 'Огромный', 'Компрессионное', 'ЭФФЕКТЫ'):
                self.assertIn(value, text)
            self.assertIn('61', text.split())
            self.assertNotIn('…', text)

    def test_no_mods_heading_only_once(self):
        output = self.root / 'fatman.pdf'
        heavy.render_heavy(self.comp, 'weapon_fat_man', 60, {}, output)
        with pymupdf.open(output) as doc:
            self.assertEqual(doc[0].get_text().count('НЕТ ПОДДЕРЖИВАЕМЫХ МОДИФИКАЦИЙ'), 1)

    def test_many_mods_use_readable_names_not_detailed_columns(self):
        output = self.root / 'gatling-plasma.pdf'
        info = heavy.render_heavy(self.comp, 'weapon_gatling_plasma', 80, {}, output)
        self.assertEqual(info['mode'], 'names')
        self.assertEqual(info['mod_count'], 17)
        with pymupdf.open(output) as doc:
            text = doc[0].get_text()
            self.assertIn('Укреплённый', text)
            self.assertIn('Глушитель', text)
            self.assertNotIn('ПРЕФИКС', text)
            self.assertNotIn('НАЗВАНИЕ', text)

    def test_detailed_mode_keeps_small_mod_sets(self):
        info = heavy.render_heavy(self.comp, 'weapon_flamer', 61, {}, self.root / 'flamer.pdf')
        self.assertEqual(info['mode'], 'detailed')
        self.assertEqual(info['mod_count'], 6)

    def test_name_only_mods_are_in_shared_reference(self):
        ids = json.loads(heavy.ORDER_FILE.read_text(encoding='utf-8'))
        selected = [wid for wid in ids if len(heavy.build_rows(self.comp, wid, {})) > heavy.MAX_DETAILED_MODS]
        small_ids = json.loads(heavy.small.ORDER.read_text(encoding='utf-8'))
        data, _ = heavy.small.make_mod_data(self.comp, list(dict.fromkeys(small_ids + selected)), {})
        names = {(section['category'], row[0]) for section in data['sections'] for row in section['rows']}
        for wid in selected:
            for slot, values in heavy.build_rows(self.comp, wid, {}):
                category = 'МОДИФИКАЦИИ ' + heavy.small.SLOT_TITLES[slot]
                self.assertIn((category, values[0]), names, (wid, slot, values[0]))

    def test_full_order_renders_every_card_without_losing_description(self):
        ids = json.loads(heavy.ORDER_FILE.read_text(encoding='utf-8'))
        self.assertEqual(len(ids), 21)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(ids[-1], 'weapon_gatling_plasma')
        for i, wid in enumerate(ids):
            output = self.root / f'{i}.pdf'
            info = heavy.render_heavy(self.comp, wid, 60 + i, {}, output)
            if info['font_size'] is not None:
                self.assertGreaterEqual(info['font_size'], 6.5)
            with pymupdf.open(output) as doc:
                self.assertEqual(len(doc), 1)
                text = re.sub(r'\s+', '', doc[0].get_text())
                description = re.sub(r'\s+', '', self.comp.description(wid))
                if description:
                    self.assertIn(description, text, wid)

    def test_does_not_truncate_description_if_no_room(self):
        self.comp.descriptions['weapon_flamer'] = 'Длинное описание ' * 2000
        with self.assertRaises(ValueError):
            heavy.render_heavy(self.comp, 'weapon_flamer', 61, {}, self.root / 'overflow.pdf')
        self.assertFalse((self.root / 'overflow.pdf').exists())


if __name__ == '__main__':
    unittest.main()
