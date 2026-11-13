import json
import tempfile
import unittest
from pathlib import Path
import pymupdf
import build_weapon_catalog as book
from weapons2cards import Companion


class CompleteWorkingCatalogTest(unittest.TestCase):
    def test_catalog_and_intentional_exclusions(self):
        source = Path('Справочник оружия.pdf')
        if not source.exists():
            self.skipTest('Source PDF not present')
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / 'catalog.pdf'
            info = book.build(source, output)
            self.assertEqual(info['pages'], 172)
            self.assertEqual(info['closing'], [168, 169, 170, 171, 172])
            with pymupdf.open(output) as doc:
                self.assertIn('ЛАЗЕРНЫЙ ПИСТОЛЕТ ИНСТИТУТА', doc[133].get_text())
                self.assertIn('КУЛАКИ', doc[135].get_text())
                self.assertIn('ПЛАЗМЕННАЯ МИНА', doc[160].get_text())
                self.assertIn('МОДИФИКАЦИИ ТРЕБУЮТ ПРОВЕРКИ', doc[160].get_text())
                self.assertNotIn('Тяжёлый ствол', doc[160].get_text())
        root = Path('data/weapons')
        filenames = ['small-guns-order.json', 'heavy-guns-order.json', 'energy-guns-order.json', 'melee-original-order.json']
        included = set(sum([json.loads((root / name).read_text(encoding='utf-8')) for name in filenames], []))
        included.update(sum(json.loads((root / 'remaining-order.json').read_text(encoding='utf-8')).values(), []))
        self.assertEqual(set(Companion().weapons) - included,
                         {'weapon_unarmed_attack', 'weapon_straight_razor', 'weapon_assaultron_head'})

if __name__ == '__main__':
    unittest.main()
