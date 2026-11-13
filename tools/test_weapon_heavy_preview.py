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

    def test_unverified_plasma_does_not_claim_either_fake_mods_or_no_mods(self):
        output = self.root / 'gatling-plasma.pdf'
        info = heavy.render_heavy(self.comp, 'weapon_gatling_plasma', 80, {}, output)
        self.assertEqual(info['mode'], 'unverified')
        with pymupdf.open(output) as doc:
            text = doc[0].get_text()
            self.assertIn('МОДИФИКАЦИИ ТРЕБУЮТ ПРОВЕРКИ', text)
            self.assertNotIn('Укреплённый', text)
            self.assertNotIn('НЕТ ПОДДЕРЖИВАЕМЫХ', text)

    def test_source_drone_has_no_mods(self):
        output = self.root / 'drone.pdf'
        heavy.render_source_heavy(self.comp, 'weapon_drone_cannon', 74, 'Справочник оружия.pdf', 72, output)
        with pymupdf.open(output) as doc:
            text = doc[0].get_text()
            self.assertIn('НЕТ ПОДДЕРЖИВАЕМЫХ МОДИФИКАЦИЙ', text)
            self.assertNotIn('Укреплённый', text)

    def test_detailed_mode_keeps_small_mod_sets(self):
        info = heavy.render_heavy(self.comp, 'weapon_flamer', 61, {}, self.root / 'flamer.pdf')
        self.assertEqual(info['mode'], 'detailed')
        self.assertEqual(info['mod_count'], 6)

    def test_heavy_mods_are_not_extracted_to_a_shared_table(self):
        self.assertFalse(hasattr(heavy, 'heavy_reference_data'))
        self.assertFalse(hasattr(heavy, 'confirmed_common_mod_data'))

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

    def test_full_book_uses_source_blocks_and_preserves_descriptions(self):
        ids = json.loads(heavy.ORDER_FILE.read_text(encoding='utf-8'))
        output = self.root / 'book.pdf'
        result = heavy.build('Справочник оружия.pdf', output, ids)
        self.assertNotIn('mods_pages', result)
        with pymupdf.open(output) as doc:
            entire_book = '\n'.join(page.get_text() for page in doc)
            self.assertNotIn('МОДИФИКАЦИИ ТЯЖЁЛОГО ОРУЖИЯ', entire_book)
            self.assertNotIn('Измельчитель — ракетная установка', entire_book)
            self.assertNotIn('Тяжёлый — пулемёт', entire_book)
            for wid in ('weapon_junk_jet', 'weapon_gauss_minigun', 'weapon_eugene'):
                card_text = doc[result['divider'] + ids.index(wid)].get_text()
                self.assertIn('Прицел стрелка', card_text)
                self.assertIn('перебросить кубик места', card_text.lower())
            minigun = doc[result['divider'] + ids.index('weapon_minigun')].get_text()
            self.assertIn('Ускоренный', minigun)
            minigun_compact = re.sub(r'-\s*\n\s*', '', minigun)
            minigun_compact = re.sub(r'\s+', ' ', minigun_compact)
            self.assertIn('Уменьшите дистанцию на 1 зону', minigun_compact)
            launcher = doc[result['divider'] + ids.index('weapon_missile_launcher')].get_text()
            self.assertIn('Четырехствольный', launcher)
            self.assertIn('+2 Скорость стрельбы', launcher)
            for i, wid in enumerate(ids):
                text = re.sub(r'\s+', '', doc[result['divider'] + i].get_text())
                desc = re.sub(r'\s+', '', self.comp.description(wid))
                if desc:
                    self.assertIn(desc, text, wid)
            drone = doc[result['divider'] + ids.index('weapon_drone_cannon')].get_text()
            self.assertIn('НЕТ ПОДДЕРЖИВАЕМЫХ МОДИФИКАЦИЙ', drone)
            plasma = doc[result['divider'] + ids.index('weapon_gatling_plasma')].get_text()
            self.assertIn('ПОДДЕРЖИВАЕМЫЕ МОДИФИКАЦИИ', plasma)
            self.assertNotIn('МОДИФИКАЦИИ ТРЕБУЮТ ПРОВЕРКИ', plasma)
            self.assertNotIn('Укреплённый', plasma)
            for name in ('Портированный', 'Удобная ложа', 'Коллиматорный', 'Фокусировщик', 'Разделитель луча'):
                self.assertIn(name, plasma)
            self.assertIn('+81', plasma)
            self.assertIn('+90', plasma)
            self.assertIn('«Отдача» (6)', plasma)

    def test_does_not_truncate_description_if_no_room(self):
        self.comp.descriptions['weapon_flamer'] = 'Длинное описание ' * 2000
        with self.assertRaises(ValueError):
            heavy.render_heavy(self.comp, 'weapon_flamer', 61, {}, self.root / 'overflow.pdf')
        self.assertFalse((self.root / 'overflow.pdf').exists())


if __name__ == '__main__':
    unittest.main()
