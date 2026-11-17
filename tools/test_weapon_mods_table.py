import tempfile
import unittest
from pathlib import Path

import pymupdf
import weapon_mods_table as table


class ModTableTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name) / 'mods.pdf'

    def test_multiple_pages_keep_all_rows_and_repeat_headings(self):
        rows = [[f'Мод {i:03}', 'Префикс', 'Эффект < +1 & -2', '-', '+20', '–']
                for i in range(100)]
        table.render({'title': 'МОДИФИКАЦИИ', 'category': 'РЕСИВЕР', 'rows': rows}, self.output)
        with pymupdf.open(self.output) as doc:
            self.assertGreater(len(doc), 1)
            text = ''.join(page.get_text() for page in doc)
            for i in range(100):
                self.assertEqual(text.count(f'Мод {i:03}'), 1)
            self.assertIn('Эффект < +1 & -2', text)
            for page in doc:
                self.assertIn('МОДИФИКАЦИЯ', page.get_text())
                self.assertIn('РЕСИВЕР', page.get_text())

    def test_invalid_rows_are_not_silently_truncated(self):
        with self.assertRaises(ValueError):
            table.render({'title': 'Тест', 'category': 'Тест', 'rows': [['one']]}, self.output)
        self.assertFalse(self.output.exists())

    def test_geometry_fits_content_column(self):
        self.assertAlmostEqual(sum(table.COL_WIDTHS), table.w.CONTENT_W)


if __name__ == '__main__':
    unittest.main()
