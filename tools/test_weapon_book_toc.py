import tempfile
import unittest
from pathlib import Path

import pymupdf

import weapon_book_toc as toc


class WeaponBookTocTests(unittest.TestCase):
    def test_renderer_layout_english(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'toc.pdf'
            entries = [
                [1, 'Small Guns', 13],
                [2, '10mm Pistol', 14],
                [2, 'Anti-Materiel Rifle', 15],
                [2, 'Small Guns Modifications', 9],
            ]
            pages = toc.render_toc_pages(entries, out)
            self.assertEqual(pages, 1)
            with pymupdf.open(out) as doc:
                text = doc[0].get_text()
                self.assertIn('TABLE OF CONTENTS', text)
                for _lvl, title, page in entries:
                    self.assertIn(title, text)
                self.assertIn('13', text)
                self.assertIn('15', text)

    def test_renderer_layout_russian(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'toc.pdf'
            entries = [
                [1, 'СТРЕЛКОВОЕ ОРУЖИЕ', 16],
                [2, '10-мм пистолет', 17],
                [2, 'МОДИФИКАЦИИ СТРЕЛКОВОГО ОРУЖИЯ', 12],
            ]
            pages = toc.render_toc_pages(entries, out, title=toc.TOC_TITLE_RU)
            self.assertEqual(pages, 1)
            with pymupdf.open(out) as doc:
                text = doc[0].get_text()
                self.assertIn('ОГОЛОВЛЕНИЕ', text)
                for _lvl, title, page in entries:
                    self.assertIn(title, text)
                self.assertIn('16', text)
                self.assertIn('17', text)

    def test_two_columns_fill_second_page(self):
        entries = [[2, f'Weapon {i}', i] for i in range(1, 161)]
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'toc.pdf'
            pages = toc.render_toc_pages(entries, out)
            self.assertGreaterEqual(pages, 2)
            with pymupdf.open(out) as doc:
                self.assertEqual(doc.page_count, pages)
                all_text = ''.join(doc[i].get_text() for i in range(pages))
                self.assertIn('Weapon 1', all_text)
                self.assertIn('Weapon 160', all_text)

    def test_blank_page(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'blank.pdf'
            toc.make_blank_page(7, out)
            with pymupdf.open(out) as doc:
                self.assertEqual(doc.page_count, 1)
                self.assertIn('7', doc[0].get_text())


if __name__ == '__main__':
    unittest.main()
