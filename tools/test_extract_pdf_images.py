"""Tests for tools/extract_pdf_images.py."""

import csv
import json
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

    def test_main_writes_report_contact_sheet_and_manifest(self):
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
        with open(os.path.join(self.out(), "artwork-manifest.json"), encoding="utf-8") as fh:
            manifest = json.load(fh)
        self.assertEqual(manifest["schema"], ex.MANIFEST_SCHEMA)
        self.assertEqual(manifest["audit"]["image_placements"], 4)

    def test_manifest_keeps_every_placement_and_asset_link(self):
        rows = ex.extract(self.pdf, self.out(), 300, 0.9, None, False,
                          {}, False)
        manifest = ex.artwork_manifest(self.pdf, rows, None, {}, False)
        self.assertEqual(len(manifest["pages"]), 2)
        self.assertEqual(manifest["audit"]["image_placements"], 4)
        self.assertEqual(manifest["audit"]["exported_asset_placements"], 2)
        first = manifest["pages"][0]
        self.assertAlmostEqual(first["size_points"][0], 595.2756, places=3)
        self.assertAlmostEqual(first["size_points"][1], 841.8898, places=3)
        self.assertEqual(first["media_box_pdf"], [0.0, 0.0, 595.2756, 841.8898])
        self.assertIsNone(first["crop_box_pdf"])
        self.assertEqual(len(first["placements"]), 2)
        art = next(item for item in first["placements"]
                   if item["xref"] == rows[0]["xref"])
        self.assertEqual(art["asset"], rows[0]["file"])
        self.assertEqual(art["matrix_pdf"], [400.0, 0.0, 0.0, 300.0, 40.0, 400.0])
        self.assertEqual(art["bbox_pdf"], [40.0, 400.0, 440.0, 700.0])
        self.assertEqual(art["clip_paths"], [])

    def test_soft_mask_is_preserved_in_extracted_png(self):
        source = os.path.join(self.dir, "transparent.png")
        Image.new("RGBA", (600, 600), (200, 0, 0, 96)).save(source)
        pdf = os.path.join(self.dir, "transparent.pdf")
        c = canvas.Canvas(pdf)
        c.drawImage(ImageReader(source), 40, 400, width=400, height=300,
                    mask="auto")
        c.showPage()
        c.save()
        rows = ex.extract(pdf, self.out(), 300, 0.9, None, False, {}, False)
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]["smask"])
        with Image.open(os.path.join(self.out(), rows[0]["file"])) as image:
            self.assertIn("A", image.getbands())
            self.assertLess(image.getchannel("A").getextrema()[0], 255)


class GeometryManifestTest(unittest.TestCase):
    def test_parser_preserves_affine_crop_and_graphics_state(self):
        content = b"""q
/Fade gs
10 20 m 110 20 l 100 80 l 10 20 l h W* n
3 -1 0.5 4 100 200 cm
/Art Do
Q
"""
        placements = ex.parse_image_placements(
            content,
            {"Art": {"xref": 7, "width": 600, "height": 400,
                      "bpc": 8, "colorspace": "DeviceRGB",
                      "filter": "DCTDecode", "smask_xref": 8}},
            {"Fade": {"fill_alpha": 0.45, "stroke_alpha": None,
                       "blend_mode": "Multiply", "soft_mask": None}},
        )
        self.assertEqual(len(placements), 1)
        art = placements[0]
        self.assertEqual(art["matrix_pdf"], [3.0, -1.0, 0.5, 4.0, 100.0, 200.0])
        self.assertEqual(art["bbox_pdf"], [100.0, 199.0, 103.5, 204.0])
        self.assertEqual(art["graphics_state"]["fill_alpha"], 0.45)
        self.assertEqual(art["graphics_state"]["blend_mode"], "Multiply")
        self.assertEqual(art["image"]["smask_xref"], 8)
        clip = art["clip_paths"]
        self.assertEqual(clip[0]["rule"], "even-odd")
        self.assertEqual(clip[0]["commands"][0],
                         {"op": "move_to", "points": [10.0, 20.0]})
        self.assertEqual(clip[0]["commands"][-1], {"op": "close_path"})


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
        self.assertEqual(ex.normalize_name("БОЕВОЙ КАРАБИН"), "боевой карабин")
        self.assertEqual(ex.normalize_name("10-мм пистолет"),
                         ex.normalize_name("10 мм пистолет"))
        self.assertEqual(ex.normalize_name("Ёж"), "еж")

    def test_slug_of(self):
        self.assertEqual(ex.slug_of("weapon_10mm_pistol"), "10mm-pistol")


if __name__ == "__main__":
    unittest.main()
