"""Tests for the interim original-PDF front section."""
import tempfile
import unittest
from pathlib import Path

import pymupdf
import weapon_book_front as front


class FrontTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def source(self, count):
        path = self.root / 'source.pdf'
        with pymupdf.open() as doc:
            for i in range(count):
                page = doc.new_page(width=400 + i, height=600)
                page.insert_text((20, 30), f'Page {i + 1}')
            doc.save(path)
        return path

    def test_preserves_first_nine_pages_and_order(self):
        source = self.source(11)
        output = self.root / 'out' / 'front.pdf'
        self.assertEqual(front.build_front(source, output), 9)
        with pymupdf.open(output) as doc:
            self.assertEqual(doc.page_count, 9)
            for i, page in enumerate(doc):
                self.assertIn(f'Page {i + 1}', page.get_text())
                self.assertEqual(page.rect.width, 400 + i)

    def test_short_source_does_not_create_output(self):
        source = self.source(8)
        output = self.root / 'front.pdf'
        with self.assertRaises(ValueError):
            front.build_front(source, output)
        self.assertFalse(output.exists())

    def test_source_cannot_be_overwritten(self):
        source = self.source(9)
        with self.assertRaises(ValueError):
            front.build_front(source, source)
        with pymupdf.open(source) as doc:
            self.assertEqual(doc.page_count, 9)


if __name__ == '__main__':
    unittest.main()
