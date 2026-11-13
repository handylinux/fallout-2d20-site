import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pymupdf
import build_small_guns_book as book
import companion_mods_receiver as conv
from weapons2cards import Companion


class SmallGunsBookTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_every_slot_mod_has_a_row(self):
        comp = Companion()
        ids = json.loads(book.ORDER.read_text(encoding='utf-8'))
        data, problems = book.make_mod_data(comp, ids, conv.load(conv.PREFIXES))
        expected = {(slot, mid) for wid in ids for slot, mods in (comp.slots.get(wid) or {}).items() for mid in mods}
        self.assertEqual(sum(len(section['rows']) for section in data['sections']), len(expected))
        self.assertTrue(any(section['category'] == 'МОДИФИКАЦИИ ЛЕБЁДКИ' for section in data['sections']))
        self.assertFalse(any('нет записи мода' in x for x in problems))

    def test_small_reference_uses_skill_not_book_position(self):
        comp = Companion()
        ids = ['weapon_10mm_pistol', 'weapon_gauss_rifle', 'weapon_underwater_gun']
        self.assertEqual(book.small_guns_reference_ids(comp, ids), ['weapon_10mm_pistol'])
        with self.assertRaises(ValueError):
            book.small_guns_reference_ids(comp, ['unknown'])

    def test_small_unique_mods_go_on_weapon_page_not_reference(self):
        output = self.root / 'full.pdf'
        report = self.root / 'report.md'
        result = book.build('Справочник оружия.pdf', output, report)
        self.assertEqual(result['mods_pages'], 4)
        with pymupdf.open(output) as doc:
            reference = ' '.join(p.get_text() for p in doc[9:13])
            self.assertNotIn('Аэродинамический', reference)
            self.assertNotIn('МОДИФИКАЦИИ ЛЕБЁДКИ', reference)
            text = next(p.get_text() for p in doc if 'АБОРДАЖНЫЙ ПИСТОЛЕТ' in p.get_text())
            self.assertIn('УНИКАЛЬНЫЙ', text)
            self.assertNotIn('Не указано', text)
            self.assertIn('ЛЕБЁДКА', text)
            self.assertIn('Проникающий 2', text)
            self.assertIn('Ненадёжное', text)
            self.assertIn('Наука! 2', text)
            self.assertIn('на расстояние до двух зон', text)
        self.assertIn('weapon-boarding-comparison.md', report.read_text(encoding='utf-8'))

    def test_unknown_mod_remains_visible(self):
        comp = Companion()
        comp.slots['weapon_10mm_pistol'] = {'Receiver': ['mod_unknown_test']}
        data, problems = book.make_mod_data(comp, ['weapon_10mm_pistol'], {})
        self.assertIn('mod_unknown_test', data['sections'][0]['rows'][0][0])
        self.assertIn('Нет данных', data['sections'][0]['rows'][0])
        self.assertTrue(any('mod_unknown_test' in p for p in problems))

    def test_lose_quality_interpreted(self):
        text = conv.effect_text({'qualityChanges': [{'op': 'lose', 'id': 'x'}]}, {}, {'x': 'Неточное'}, {})
        self.assertEqual(text, 'Убрать качество «Неточное»')

    def test_book_order_and_page_numbers_follow_mods(self):
        source = self.root / 'source.pdf'
        order = self.root / 'order.json'
        order.write_text(json.dumps(['weapon_10mm_pistol', 'weapon_44_pistol']), encoding='utf-8')
        with pymupdf.open() as doc:
            for i in range(13):
                p = doc.new_page()
                p.insert_text((40, 818), str(i + 1))
            doc.save(source)
        output = self.root / 'out.pdf'
        report = self.root / 'report.md'
        with patch.object(book, 'ORDER', order):
            result = book.build(source, output, report)
        with pymupdf.open(output) as doc:
            self.assertEqual(len(doc), result['pages'])
            div = result['divider']
            self.assertEqual(div, 9 + result['mods_pages'] + 1)
            divider_words = [w[4] for w in doc[div - 1].get_text('words')]
            self.assertEqual(divider_words, [str(div)])
            self.assertIn('10-ММ ПИСТОЛЕТ', doc[div].get_text())
            self.assertIn(str(div + 1), doc[div].get_text().split())
            self.assertIn('РЕВОЛЬВЕР КАЛИБРА .44', doc[div + 1].get_text())
        self.assertIn('Разделитель', report.read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
