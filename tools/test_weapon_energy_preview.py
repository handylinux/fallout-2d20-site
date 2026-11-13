import tempfile
import unittest
from pathlib import Path
import pymupdf
import weapon_energy_preview as energy

class EnergyPreviewTest(unittest.TestCase):
    def test_preview_reference_order_numbering_and_cards(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'book.pdf'
            report = Path(tmp) / 'report.md'
            result = energy.build('Справочник оружия.pdf', output, report)
            self.assertEqual(result, {'pages': 87, 'references': [81, 82, 83], 'divider': 84, 'weapons': [85, 86, 87]})
            with pymupdf.open(output) as doc:
                self.assertIn('МОДИФИКАЦИИ ЭНЕРГЕТИЧЕСКОГО ОРУЖИЯ', doc[80].get_text())
                reference = doc[82].get_text()
                self.assertIn('УНИКАЛЬНЫЙ КОНДЕНСАТОР', reference)
                for value in ('3-зарядный', '4-зарядный', '5-зарядный', '6-зарядный'):
                    self.assertIn(value, reference)
                self.assertEqual(doc[83].get_text().strip(), '84')
                for index, title in enumerate(['ЛАЗЕРНЫЙ МУШКЕТ', 'ЛАЗЕРНЫЙ ПИСТОЛЕТ', 'ПЛАЗМЕННЫЙ ПИСТОЛЕТ']):
                    text = doc[84 + index].get_text()
                    self.assertIn(title, text)
                    self.assertEqual(text.count('ПОДДЕРЖИВАЕМЫЕ МОДИФИКАЦИИ'), 1)
                    self.assertIn('КОНДЕНСАТОР', text)
                self.assertIn('Особенность:', doc[84].get_text())
                self.assertIn('отдельной сверки', report.read_text(encoding='utf8'))

    def test_reference_unique_mods_order_and_prefix_override(self):
        from weapons2cards import Companion
        data, problems = energy.musket_reference(Companion(), {'mod_three_crank_capacitor': 'Проверочный'})
        rows = data['sections'][0]['rows']
        self.assertEqual([r[0] for r in rows], ['3-зарядный', '4-зарядный', '5-зарядный', '6-зарядный'])
        self.assertEqual(rows[0][1], 'Проверочный')
        self.assertEqual(rows[0][3], '—')
        self.assertIn('расходует 3 заряда на атаку', rows[0][2])
        self.assertTrue(any('weight' in p for p in problems))

    def test_full_energy_section_matches_source_order_and_keeps_specials(self):
        import json
        import re
        from weapons2cards import Companion
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'full.pdf'
            result = energy.build('Справочник оружия.pdf', output, full=True)
            self.assertEqual(result['pages'], 98)
            self.assertEqual(result['divider'], 84)
            ids = json.loads(energy.ORDER.read_text(encoding='utf8'))
            comp = Companion()
            with pymupdf.open(output) as doc:
                ref = doc[82].get_text()
                for value in ('ЛАЗЕРНЫЙ МУШКЕТ', 'Термоядерный магазин'):
                    self.assertIn(re.sub(r'\s+', '', value), re.sub(r'\s+', '', ref))
                self.assertNotIn('ГОЛОВНОЙ ЛАЗЕР ШТУРМОТРОНА', ref)
                self.assertNotIn('MK III', ref)
                for i, wid in enumerate(ids):
                    text = re.sub(r'\s+', '', doc[84 + i].get_text())
                    desc = re.sub(r'\s+', '', comp.description(wid))
                    if desc:
                        self.assertIn(desc, text, wid)
                    self.assertIn('МОДИФИКАЦИ', text, wid)
                head = doc[97].get_text()
                self.assertIn('Энергоячейка', head)
                self.assertIn('Проникающий 1', head)
                self.assertIn('Особенность:', head)
                self.assertIn('УНИКАЛЬНЫЙ', head)
                self.assertIn('ПРЕФИКС', head)
                for mod in ('MK III', 'MK IV', 'MK V', 'MK VI'):
                    self.assertEqual(head.splitlines().count(mod), 2)
                self.assertIn('расходует 3 заряда на атаку', head)
                self.assertIn('расходует 6 зарядов на атаку', head)
                self.assertIn('робототехнике', head)
                self.assertIn('Наука! 3', head)
                self.assertNotIn('Ствол X', head)
                self.assertIn('Наука! 1', head)
                self.assertNotIn('Science!', head)
                self.assertNotIn('Science!', ref)
                alien = doc[94].get_text()
                self.assertIn('Радиационный', alien)
                self.assertIn('Порочный', alien)
                self.assertIn('Особенности:', alien)
                for n in (92, 93):
                    self.assertIn('МОДИФИКАЦИИ НЕИЗВЕСТНЫ', doc[n].get_text())

    def test_refuses_to_overwrite_source(self):
        with self.assertRaises(ValueError):
            energy.build('Справочник оружия.pdf', 'Справочник оружия.pdf')

if __name__ == '__main__':
    unittest.main()
