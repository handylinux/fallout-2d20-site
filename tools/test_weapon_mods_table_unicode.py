import tempfile
import unittest
from pathlib import Path

import pymupdf
import weapon_mods_table_unicode as table


class UnicodeTableTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.out = Path(self.tmp.name) / 'table.pdf'

    def test_unicode_fonts_and_editable_cyrillic(self):
        data = {'title': 'МОДИФИКАЦИИ', 'category': 'РЕСИВЕР',
                'rows': [['Укреплённый', 'Префикс', 'Урон +1', '–', '+20', 'Фанатик оружия']]}
        table.render(data, self.out)
        with pymupdf.open(self.out) as doc:
            text = doc[0].get_text()
            self.assertIn('Укреплённый', text)
            self.assertIn('Фанатик оружия', text)
            fonts = doc[0].get_fonts()
            self.assertTrue(all(f[2] == 'Type0' and f[5] == 'Identity-H' for f in fonts))
            self.assertEqual(len(fonts), 2)

    def test_multi_page_has_all_rows_and_repeated_header(self):
        rows = [[f'Мод {i:03}', 'Префикс', 'Эффект < & >', '-', '+20', 'Перки'] for i in range(100)]
        table.render({'title': 'МОДИФИКАЦИИ', 'category': 'РЕСИВЕР', 'rows': rows}, self.out)
        with pymupdf.open(self.out) as doc:
            self.assertGreater(len(doc), 1)
            text = ''.join(p.get_text() for p in doc)
            for i in range(100):
                self.assertEqual(text.count(f'Мод {i:03}'), 1)
            for page in doc:
                self.assertIn('РЕСИВЕР', page.get_text())
                self.assertIn('ЭФФЕКТЫ', page.get_text())

    def test_long_word_is_not_truncated(self):
        font = pymupdf.Font(fontfile=table.REGULAR)
        value = 'Длинноесловобезпробелов'
        self.assertEqual(''.join(table.wrap(value, font, 35)), value)
        self.assertTrue(all(font.text_length(line, fontsize=table.SIZE) <= 35 for line in table.wrap(value, font, 35)))

    def test_rejects_oversize_row(self):
        data = {'title': 'Тест', 'category': 'Ресивер', 'rows': [['слово ' * 10000, '', '', '', '', '']]}
        with self.assertRaises(ValueError):
            table.render(data, self.out)
        self.assertFalse(self.out.exists())


if __name__ == '__main__':
    unittest.main()
