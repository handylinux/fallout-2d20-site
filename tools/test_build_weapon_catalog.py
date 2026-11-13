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
            self.assertEqual(info['pages'], 173)
            self.assertEqual(info['closing'], [169, 170, 171, 172, 173])
            with pymupdf.open(output) as doc:
                text = lambda n: doc[n-1].get_text()
                self.assertIn('ЛАЗЕРНЫЙ ПИСТОЛЕТ ИНСТИТУТА', text(info['weapons']['energy'][0]))
                self.assertIn('КУЛАКИ', text(info['weapons']['unarmed'][0]))
                glove = text(info['weapons']['unarmed'][2])
                self.assertIn('ПЕРЧАТКА', glove)
                self.assertIn('Свинцовая', glove)
                self.assertIn('Кузнец', glove)
                self.assertNotIn('Боксерская перчатка:', glove)
                self.assertIn('МЕТАТЕЛЬНОЕ ОРУЖИЕ', text(info['weapons']['thrown'][0]-1))
                self.assertIn('ВЗРЫВЧАТКА', text(info['weapons']['explosives'][0]-1))
                pulse_mine = text(info['weapons']['explosives'][0])
                self.assertIn('Средняя', pulse_mine)
                self.assertNotIn('Medium', pulse_mine)
                mine = text(info['weapons']['explosives'][14])
                self.assertIn('ПЛАЗМЕННАЯ МИНА', mine)
                self.assertIn('МОДИФИКАЦИИ ТРЕБУЮТ ПРОВЕРКИ', mine)
                self.assertNotIn('Тяжёлый ствол', mine)
                words = doc[82].get_text('words')
                capacitor = next(x for x in words if x[4] == '6-зарядный')
                magazine = next(x for x in words if x[4] == 'МАГАЗИНА')
                self.assertGreater(magazine[1] - capacitor[3], 15)
                pistol = doc[47].get_text()
                self.assertIn('ПИСТОЛЕТ-ИНЖЕКТОР', pistol)
                self.assertIn('0\nБлизкая', pistol)
                injector = doc[47]
                self.assertTrue(any(word[4] == '4' and 340 < word[1] < 390 for word in injector.get_text('words')))
                grid = doc[85]
                frames = [d['rect'] for d in grid.get_drawings() if d.get('type') == 's' and abs((d.get('width') or 0)-.7) < .01]
                word = [x for x in grid.get_text('words') if x[4] == 'КОНДЕНСАТОР'][0]
                self.assertTrue(any(r.y0 < word[1] and r.y1 > word[3] for r in frames))
        root = Path('data/weapons')
        filenames = ['small-guns-order.json', 'heavy-guns-order.json', 'energy-guns-order.json', 'melee-original-order.json']
        included = set(sum([json.loads((root / name).read_text(encoding='utf-8')) for name in filenames], []))
        included.update(sum(json.loads((root / 'remaining-order.json').read_text(encoding='utf-8')).values(), []))
        self.assertEqual(set(Companion().weapons) - included,
                         {'weapon_unarmed_attack', 'weapon_straight_razor', 'weapon_assaultron_head'})

if __name__ == '__main__':
    unittest.main()
