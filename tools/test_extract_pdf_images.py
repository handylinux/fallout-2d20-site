"""Tests for tools/extract_pdf_images.py."""

import csv
import os
import tempfile
import unittest

from reportlab.lib.colors import Color
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from PIL import Image

import extract_pdf_images as ex


def make_image(path, size, color):
    Image.new("RGB", (size, size), color).save(path)


def make_pdf(path, images):
    """images: list of (path, width_pt, height_pt) per page."""
    c = canvas.Canvas(path)
    for page_images in images:
        for img_path, w, h in page_images:
            c.drawImage(ImageReader(img_path), 40, 400, width=w, height=h)
        c.showPage()
    c.save()


class ExtractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = self.tmp.name
        self.red = os.path.join(self.dir, "red.png")
        self.blue = os.path.join(self.dir, "blue.png")
        self.icon = os.path.join(self.dir, "icon.png")
        make_image(self.red, 600, "#c00")
        make_image(self.blue, 600, "#00c")
        make_image(self.icon, 40, "#0c0")
        self.pdf = os.path.join(self.dir, "book.pdf")
        make_pdf(self.pdf, [
            [(self.red, 400, 300), (self.icon, 20, 20)],
            [(self.blue, 400, 300), (self.icon, 20, 20)],
        ])

    def out(self):
        return os.path.join(self.dir, "art")

    def test_big_images_are_extracted_per_page(self):
        rows = ex.extract(self.pdf, self.out(), 300, 0.9, None, False)
        self.assertEqual([r["page"] for r in rows], [1, 2])
        self.assertEqual([r["file"] for r in rows],
                         ["p001-01.png", "p002-01.png"])
        for row in rows:
            self.assertTrue(os.path.exists(os.path.join(self.out(),
                                                        row["file"])))

    def test_small_images_are_skipped(self):
        rows = ex.extract(self.pdf, self.out(), 300, 0.9, None, False)
        self.assertEqual(len(rows), 2)

    def test_same_image_on_every_page_is_treated_as_texture(self):
        pdf = os.path.join(self.dir, "texture.pdf")
        make_pdf(pdf, [[(self.red, 400, 300)], [(self.red, 400, 300)]])
        rows = ex.extract(pdf, self.out(), 300, 0.5, None, False)
        self.assertEqual(rows, [])

    def test_keep_repeated_flag(self):
        pdf = os.path.join(self.dir, "texture.pdf")
        make_pdf(pdf, [[(self.red, 400, 300)], [(self.red, 400, 300)]])
        rows = ex.extract(pdf, self.out(), 300, 0.5, None, True)
        self.assertEqual(len(rows), 1)

    def test_pages_selection(self):
        rows = ex.extract(self.pdf, self.out(), 300, 0.9, [2], False)
        self.assertEqual([r["page"] for r in rows], [2])

    def test_main_writes_report_and_contact_sheet(self):
        code = ex.main([self.pdf, "--out", self.out(), "--min-size", "300",
                        "--share", "0.9"])
        self.assertEqual(code, 0)
        with open(os.path.join(self.out(), "report.csv"), encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        self.assertEqual(len(rows), 2)
        self.assertEqual(set(rows[0]), {"page", "file", "xref", "width",
                                        "height", "smask"})
        with open(os.path.join(self.out(), "index.html"), encoding="utf-8") as fh:
            html = fh.read()
        self.assertIn("p001-01.png", html)
        self.assertIn("p002-01.png", html)


if __name__ == "__main__":
    unittest.main()
