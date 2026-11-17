import unittest
from pathlib import Path

import pymupdf
import weapon2pdf as w
import weapon_table_borders as borders


class SourceTableBordersTest(unittest.TestCase):
    def test_source_reference_tables_fit_and_keep_text(self):
        source = Path('Справочник оружия.pdf')
        if not source.exists():
            self.skipTest('Source PDF not present')
        with pymupdf.open(source) as original, pymupdf.open() as result:
            for source_number, expected in ((78, 2), (79, 4)):
                page = result.new_page(width=w.PAGE_W, height=w.PAGE_H)
                clip = pymupdf.Rect(0, 0, w.PAGE_W, 807)
                boxes = borders.place_source_block(page, original, source_number-1, clip, 0)
                self.assertEqual(len(boxes), expected)
                frames = [d for d in page.get_drawings() if d.get('type') == 's' and abs(d.get('width', 0) - borders.BORDER_WIDTH) < .01]
                self.assertEqual(len(frames), expected)
                for frame in frames:
                    self.assertGreaterEqual(frame['rect'].x0 - borders.BORDER_WIDTH / 2, w.MARGIN_L - .01)
                    self.assertLessEqual(frame['rect'].x1 + borders.BORDER_WIDTH / 2, w.CONTENT_R + .01)
                    self.assertLessEqual(frame['rect'].y1 + borders.BORDER_WIDTH / 2, w.PAGE_H)
                source_words = [x[4] for x in original[source_number-1].get_text('words', clip=clip)]
                result_words = [x[4] for x in page.get_text('words')]
                self.assertEqual(source_words, result_words)

    def test_generated_grid_stroke_is_inside_margins(self):
        self.assertGreaterEqual(w.MODS_LEFT - w.RULE_W_PT / 2, w.MARGIN_L)
        self.assertLessEqual(w.MODS_RIGHT + w.RULE_W_PT / 2, w.CONTENT_R)


if __name__ == '__main__':
    unittest.main()
