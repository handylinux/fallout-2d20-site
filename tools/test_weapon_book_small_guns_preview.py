import tempfile
import unittest
from pathlib import Path

import pymupdf
import weapon_book_small_guns_preview as preview


class PreviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def source(self, count):
        path = self.root / 'source.pdf'
        with pymupdf.open() as doc:
            for i in range(count):
                p = doc.new_page()
                p.insert_text((30, 30), f'Source {i + 1}')
            doc.save(path)
        return path

    def test_generated_pages_follow_source_and_are_numbered(self):
        source = self.source(14)
        out = self.root / 'preview.pdf'
        self.assertEqual(preview.build_preview(source, out, self.root), 16)
        with pymupdf.open(out) as doc:
            self.assertEqual(len(doc), 16)
            self.assertIn('Source 13', doc[12].get_text())
            for i, title in enumerate(['10-ММ ПИСТОЛЕТ', 'РЕВОЛЬВЕР КАЛИБРА .44', 'СИГНАЛЬНЫЙ ПИСТОЛЕТ']):
                text = doc[13 + i].get_text()
                self.assertIn(title, text)
                self.assertIn(str(14 + i), text.split())

    def test_short_and_same_source_are_rejected(self):
        source = self.source(12)
        with self.assertRaises(ValueError):
            preview.build_preview(source, self.root / 'out.pdf', self.root)
        with self.assertRaises(ValueError):
            preview.build_preview(source, source, self.root)
        self.assertFalse((self.root / 'out.pdf').exists())


if __name__ == '__main__':
    unittest.main()
