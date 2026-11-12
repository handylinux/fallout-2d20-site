import tempfile
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

    def test_does_not_truncate_description_if_no_room(self):
        self.comp.descriptions['weapon_flamer'] = 'Длинное описание ' * 2000
        with self.assertRaises(ValueError):
            heavy.render_heavy(self.comp, 'weapon_flamer', 61, {}, self.root / 'overflow.pdf')
        self.assertFalse((self.root / 'overflow.pdf').exists())


if __name__ == '__main__':
    unittest.main()
