"""Regression tests for the raster-only PDF compatibility renderer."""

import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw
import pymupdf

import rasterize_pdf


class RasterizePdfTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source.pdf"
        self.output = self.root / "mobile-raster.pdf"
        self.overlay = self.root / "transparent-overlay.png"
        self._make_source()

    def _make_source(self):
        # The test source intentionally has vector text/drawings and a
        # transparent image.  The output must retain the rendered appearance
        # without retaining any of those independently composable objects.
        overlay = Image.new("RGBA", (80, 80), (0, 0, 0, 0))
        ImageDraw.Draw(overlay).ellipse((10, 10, 70, 70), fill=(220, 30, 20, 190))
        overlay.save(self.overlay)

        document = pymupdf.open()
        first = document.new_page(width=200, height=300)
        first.draw_rect(first.rect, color=None, fill=(0.15, 0.30, 0.58))
        first.insert_text((20, 40), "Vector title", fontsize=18, color=(1, 1, 1))
        first.draw_line((20, 55), (180, 55), color=(1, 1, 1), width=2)
        first.insert_image(pymupdf.Rect(60, 80, 140, 160), filename=self.overlay)

        second = document.new_page(width=200, height=300)
        second.draw_rect(second.rect, color=None, fill=(0.95, 0.85, 0.65))
        second.insert_text((20, 120), "Second page", fontsize=22, color=(0, 0, 0))
        document.save(self.source)
        document.close()

    def test_complete_pages_become_single_opaque_jpegs(self):
        stats = rasterize_pdf.rasterize_pdf(
            self.source, self.output, dpi=144, jpeg_quality=88, metadata_locale="en"
        )
        self.assertEqual(stats["pages"], 2)
        self.assertEqual(stats["dpi"], 144)
        self.assertEqual(stats["jpeg_quality"], 88)
        self.assertEqual(stats["metadata_locale"], "en")
        self.assertTrue(stats["source_sha256"])
        self.assertTrue(stats["output_sha256"])
        self.assertGreater(stats["output_bytes"], 1_000)
        self.assertEqual(rasterize_pdf.assert_raster_only(self.output), 2)

        with pymupdf.open(self.source) as source, pymupdf.open(self.output) as output:
            self.assertEqual(output.metadata["title"],
                             "Fallout 2d20 Weapon Catalog — Mobile Raster Edition")
            self.assertNotIn("оружия", output.metadata["title"])
            self.assertEqual(source.page_count, output.page_count)
            for source_page, output_page in zip(source, output):
                self.assertAlmostEqual(source_page.rect.width, output_page.rect.width, places=3)
                self.assertAlmostEqual(source_page.rect.height, output_page.rect.height, places=3)
                self.assertEqual(output_page.get_text(), "")
                self.assertFalse(any(
                    block.get("type") == 0
                    for block in output_page.get_text("rawdict")["blocks"]
                ))
                self.assertEqual(output_page.get_fonts(full=True), [])
                self.assertEqual(output_page.get_drawings(), [])
                self.assertEqual(output_page.get_xobjects(), [])
                images = output_page.get_images(full=True)
                self.assertEqual(len(images), 1)
                self.assertEqual(images[0][1], 0)  # no /SMask
                image = output.extract_image(images[0][0])
                self.assertEqual(image["ext"], "jpeg")
                self.assertFalse(image.get("smask", 0))

    def test_invalid_output_or_settings_fail_before_rendering(self):
        with self.assertRaisesRegex(rasterize_pdf.RasterPdfError, "совпадать"):
            rasterize_pdf.rasterize_pdf(self.source, self.source)
        with self.assertRaisesRegex(rasterize_pdf.RasterPdfError, "DPI"):
            rasterize_pdf.rasterize_pdf(self.source, self.output, dpi=71)
        with self.assertRaisesRegex(rasterize_pdf.RasterPdfError, "JPEG"):
            rasterize_pdf.rasterize_pdf(self.source, self.output, jpeg_quality=101)
        with self.assertRaisesRegex(rasterize_pdf.RasterPdfError, "Локаль"):
            rasterize_pdf.rasterize_pdf(self.source, self.output, metadata_locale="de")


if __name__ == "__main__":
    unittest.main()
