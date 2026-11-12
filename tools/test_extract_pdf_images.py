"""Tests for tools/extract_pdf_images.py."""

import csv
import os
import tempfile
import unittest

from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from PIL import Image

import extract_pdf_images as ex

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
pdfmetrics.registerFont(TTFont("Carlito-Bold",
                               os.path.join(ROOT, "assets", "fonts",
                                            "Carlito-Bold.ttf")))


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
                         ["p001.png", "p002.png"])
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
        self.assertEqual(set(rows[0]), {"page", "file", "title", "weapon_id",
                                        "xref", "width", "height", "smask"})
        with open(os.path.join(self.out(), "index.html"), encoding="utf-8") as fh:
            html = fh.read()
        self.assertIn("p001.png", html)
        self.assertIn("p002.png", html)


class PageNameTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = self.tmp.name
        self.art = os.path.join(self.dir, "art.png")
        make_image(self.art, 600, "#c00")

    def pdf_with_title(self, title):
        path = os.path.join(self.dir, "page.pdf")
        c = canvas.Canvas(path)
        c.setFont("Carlito-Bold", 22)
        c.drawString(150, 780, title)
        c.drawImage(ImageReader(self.art), 40, 400, width=400, height=300)
        c.showPage()
        c.save()
        return path

    def test_title_is_read_from_the_page(self):
        pdf = self.pdf_with_title("БОЕВОЙ КАРАБИН")
        import pymupdf
        page = pymupdf.open(pdf)[0]
        self.assertEqual(ex.page_title(page), "БОЕВОЙ КАРАБИН")

    def test_title_gives_the_companion_slug(self):
        pdf = self.pdf_with_title("БОЕВОЙ КАРАБИН")
        rows = ex.extract(pdf, self.dir, 300, 0.9, None, False,
                          ex.load_weapons(ex.WEAPONS_JSON), True)
        self.assertEqual(rows[0]["title"], "БОЕВОЙ КАРАБИН")
        self.assertEqual(rows[0]["weapon_id"], "weapon_combat_rifle")
        self.assertEqual(rows[0]["file"], "combat-rifle.png")

    def test_unknown_title_keeps_the_page_name(self):
        pdf = self.pdf_with_title("НЕИЗВЕСТНЫЙ СТВОЛ")
        rows = ex.extract(pdf, self.dir, 300, 0.9, None, False,
                          ex.load_weapons(ex.WEAPONS_JSON), True)
        self.assertEqual(rows[0]["file"], "p001.png")

    def test_full_page_image_is_background(self):
        paper = os.path.join(self.dir, "paper.png")
        make_image(paper, 500, "#eee")
        pdf = os.path.join(self.dir, "bg.pdf")
        c = canvas.Canvas(pdf)
        c.drawImage(ImageReader(paper), 0, 0, width=595, height=842)
        c.drawImage(ImageReader(self.art), 40, 400, width=400, height=300)
        c.showPage()
        c.save()
        rows = ex.extract(pdf, self.dir, 300, 0.9, None, False, {}, False)
        self.assertEqual(len(rows), 1)

    def test_normalize_name(self):
        self.assertEqual(ex.normalize_name("БОЕВОЙ КАРАБИН"), "боевойкарабин")
        self.assertEqual(ex.normalize_name("10-мм пистолет"),
                         ex.normalize_name("10 мм пистолет"))
        self.assertEqual(ex.normalize_name("Ёж"), "еж")

    def test_split_title_and_confirmed_injector(self):
        weapons = ex.load_weapons(ex.WEAPONS_JSON)
        self.assertEqual(ex.match_weapon("ДВУСТВОЛЬНЫЙ ДРОБОВИ К", weapons),
                         "weapon_double_barrel_shotgun")
        self.assertEqual(ex.match_weapon("ПИСТОЛЕТ - ИНЪЕКТОР", weapons),
                         "weapon_pistol_injector")
        self.assertEqual(ex.match_weapon("СТЕН - ИНЪЕКТОР", weapons),
                         "weapon_sten_injector")
        self.assertEqual(ex.match_weapon("НЕИЗВЕСТНОЕ ОРУЖИЕ", weapons), "")

    def test_slug_of(self):
        self.assertEqual(ex.slug_of("weapon_10mm_pistol"), "10mm-pistol")


if __name__ == "__main__":
    unittest.main()
