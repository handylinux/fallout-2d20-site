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
            self.assertEqual(result, {'pages': 86, 'references': [81, 82], 'divider': 83, 'weapons': [84, 85, 86]})
            with pymupdf.open(output) as doc:
                self.assertIn('МОДИФИКАЦИИ ЭНЕРГЕТИЧЕСКОГО ОРУЖИЯ', doc[80].get_text())
                self.assertEqual(doc[82].get_text().strip(), '83')
                for index, title in enumerate(['ЛАЗЕРНЫЙ МУШКЕТ', 'ЛАЗЕРНЫЙ ПИСТОЛЕТ', 'ПЛАЗМЕННЫЙ ПИСТОЛЕТ']):
                    text = doc[83 + index].get_text()
                    self.assertIn(title, text)
                    self.assertEqual(text.count('ПОДДЕРЖИВАЕМЫЕ МОДИФИКАЦИИ'), 1)
                    self.assertIn('КОНДЕНСАТОР', text)
                self.assertIn('Особенность:', doc[83].get_text())
                self.assertIn('отдельной сверки', report.read_text(encoding='utf8'))

    def test_refuses_to_overwrite_source(self):
        with self.assertRaises(ValueError):
            energy.build('Справочник оружия.pdf', 'Справочник оружия.pdf')

if __name__ == '__main__':
    unittest.main()
