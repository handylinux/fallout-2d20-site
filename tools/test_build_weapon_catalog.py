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
            self.assertEqual(info['pages'], 176)
            self.assertEqual(info['pages'] % 4, 0)
            self.assertEqual(info['toc_pages'], 2)
            self.assertEqual(info['closing'], [171, 172, 173, 174, 176])
            with pymupdf.open(output) as doc:
                text = lambda n: doc[n-1].get_text()
                # Printed TOC sits on pages 4-5, right after the STAND BY spread
                toc_pages = [n for n in range(1, len(doc) + 1) if 'ОГОЛОВЛЕНИЕ' in doc[n-1].get_text()]
                self.assertEqual(toc_pages, [4, 5])
                toc_text = ''.join(doc[n-1].get_text() for n in toc_pages)
                weapon_entries = [(t, p) for lvl, t, p in info['toc']
                                  if lvl == 2 and 'МОДИФИКАЦИИ' not in t]
                self.assertEqual(len(weapon_entries), 143)
                for title, _page in weapon_entries:
                    self.assertIn(title, toc_text)
                lines = [l.strip() for l in toc_text.splitlines() if l.strip()]
                idx = next(i for i, l in enumerate(lines) if 'Гатлинг-плазма' in l)
                self.assertRegex(lines[idx + 1], r'^\d+$')
                self.assertEqual(int(lines[idx + 1]),
                                 dict((t, p) for _l, t, p in info['toc'])['Гатлинг-плазма'])

                self.assertIn('ЛАЗЕРНЫЙ ПИСТОЛЕТ ИНСТИТУТА', text(info['weapons']['energy'][0]))
                energy_first = text(info['references']['energy'][0])
                energy_second = text(info['references']['energy'][1])
                self.assertNotIn('МОДИФИКАЦИИ КОНДЕНСАТОРА', energy_first)
                self.assertIn('МОДИФИКАЦИИ КОНДЕНСАТОРА', energy_second)
                energy_second_compact = ' '.join(energy_second.split())
                for name in ('Тюнер бета-волн', 'Усиленный конденсатор',
                             'Фотонная мешалка', 'Возбудитель фотонов'):
                    self.assertIn(name, energy_second_compact)
                self.assertIn('КУЛАКИ', text(info['weapons']['unarmed'][0]))
                glove = text(info['weapons']['unarmed'][2])
                self.assertIn('ПЕРЧАТКА', glove)
                self.assertIn('Свинцовая', glove)
                self.assertIn('Кузнец', glove)
                self.assertNotIn('Боксерская перчатка:', glove)
                self.assertIn('МЕТАТЕЛЬНОЕ ОРУЖИЕ', text(info['weapons']['thrown'][0]-1))
                self.assertIn('ВЗРЫВЧАТКА', text(info['weapons']['explosives'][0]-1))
                pulse_mine = text(info['weapons']['explosives'][0])
                self.assertIn('Оглушение', pulse_mine)
                self.assertIn('Цена: 100', pulse_mine)
                self.assertIn('6\n', pulse_mine)
                self.assertNotIn('Средняя', pulse_mine)
                self.assertNotIn('Medium', pulse_mine)
                self.assertIn('Взрыв', pulse_mine)
                self.assertNotIn('Врыв', pulse_mine)
                mine = text(info['weapons']['explosives'][14])
                self.assertIn('ПЛАЗМЕННАЯ МИНА', mine)
                self.assertIn('НЕТ ПОДДЕРЖИВАЕМЫХ МОДИФИКАЦИЙ', mine)
                self.assertNotIn('Тяжёлый ствол', mine)
                words = doc[84].get_text('words')
                capacitor = next(x for x in words if x[4] == '6-зарядный')
                magazine = next(x for x in words if x[4] == 'МАГАЗИНА')
                self.assertGreater(magazine[1] - capacitor[3], 15)
                self.assertIn('Редкость: 4', text(23))
                self.assertIn('Цена: 156', text(90))
                self.assertIn('0\nСредняя', text(58))
                pistol = doc[49].get_text()
                self.assertIn('ПИСТОЛЕТ-ИНЪЕКТОР', pistol)
                self.assertIn('Яд', pistol)
                self.assertIn('Усмирение 3', pistol)
                self.assertNotIn('Усмирение X', pistol)
                self.assertIn('0\nБлизкая', pistol)
                sten = text(81)
                self.assertIn('СТЕН-ИНЪЕКТОР', sten)
                self.assertIn('3\nСредняя', sten)
                self.assertIn('Усмирение 3', sten)
                self.assertIn('Яд', sten)
                self.assertNotIn('Усмирение X', sten)
                self.assertTrue(any(word[4] == '4' and 340 < word[1] < 390 for word in doc[80].get_text('words')))
                injector = doc[49]
                self.assertTrue(any(word[4] == '4' and 340 < word[1] < 390 for word in injector.get_text('words')))
                grid = doc[86]
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
