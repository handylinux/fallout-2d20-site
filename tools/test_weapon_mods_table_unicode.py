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

    def test_damage_icons_are_inline_and_only_in_effect_cells(self):
        row = ['Название DC', 'Префикс', 'Урон: +1 DC; затем +2 DC; ACDC', '–', '+20', 'Перк']
        table.render({'title': 'Таблица', 'category': 'Ресивер', 'rows': [row]}, self.out)
        with pymupdf.open(self.out) as doc:
            page = doc[0]
            self.assertIn('Название DC', page.get_text())
            self.assertIn('ACDC', page.get_text())
            images = {img[0] for img in page.get_images() if img[2:4] == (41, 41)}
            self.assertEqual(len(images), 1)
            rects = page.get_image_rects(next(iter(images)))
            self.assertEqual(len(rects), 2)
            raw = page.get_text('rawdict')
            semicolons = [char for block in raw['blocks'] for line in block.get('lines', [])
                          for span in line.get('spans', []) for char in span.get('chars', [])
                          if char['c'] == ';']
            self.assertEqual(len(semicolons), 2)
            for rect, char in zip(sorted(rects, key=lambda r: r.x0),
                                  sorted(semicolons, key=lambda c: c['bbox'][0])):
                self.assertGreaterEqual(char['bbox'][0] - rect.x1, table.DAMAGE_GAP - .05)
            left = table.w.MARGIN_L + sum(table.COL_WIDTHS[:2])
            right = left + table.COL_WIDTHS[2]
            for rect in rects:
                self.assertGreaterEqual(rect.x0, left)
                self.assertLessEqual(rect.x1, right)
                self.assertGreaterEqual(rect.y0, table.TABLE_TOP + table.HEADER_H + table.CATEGORY_H)
                self.assertLessEqual(rect.y1, table.PAGE_BOTTOM)

    def test_icon_width_used_when_wrapping(self):
        font = pymupdf.Font(fontfile=table.REGULAR)
        text = table.damage_tokens('Урон +1 DC, ещё +2 DC')
        lines = table.wrap(text, font, 55)
        self.assertEqual(' '.join(lines), text)
        self.assertTrue(all(table.inline_width(line, font) <= 55 for line in lines))

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
