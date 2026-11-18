"""Regression tests for strict Publisher artwork use in the full weapon book."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image

import weapon2pdf as w
from weapon_catalog_artwork import ArtworkResolver, CatalogArtworkError

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / 'docs/render/pdf-extract/publisher-art/artwork-manifest.json'
ART_ROOT = MANIFEST.parent
SOURCE = ROOT / 'Справочник оружия.pdf'

w.register_fonts()


class ArtworkResolverTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        Image.new('RGBA', (20, 10), (180, 40, 20, 200)).save(root / 'art.png')
        self.manifest_path = root / 'artwork-manifest.json'
        self.manifest_path.write_text(json.dumps({
            'schema': w.ARTWORK_MANIFEST_SCHEMA,
            'coordinate_system': {'unit': 'point', 'origin': 'bottom-left'},
            'source': {'sha256': 'unused-without-source.pdf'},
            'pages': [{
                'number': 24,
                'weapon_id': 'weapon_double_barrel_shotgun',
                'size_points': [600, 850],
                'placements': [{
                    'xref': 468, 'draw_order': 4,
                    'matrix_pdf': [100, -20, 10, 80, 40, 500],
                    'clip_paths': [],
                    'graphics_state': {'fill_alpha': 1, 'stroke_alpha': 1,
                                       'blend_mode': 'Normal', 'soft_mask': None,
                                       'transfer_function': None},
                    'asset': 'art.png',
                }],
            }, {
                'number': 26,
                'weapon_id': 'weapon_pipe_gun',
                'placements': [],
            }],
        }, ensure_ascii=False), encoding='utf-8')

    def test_resolver_never_falls_back_to_catalog_page_number(self):
        resolver = ArtworkResolver(self.manifest_path)
        layer = resolver.layer_for('weapon_double_barrel_shotgun')
        self.assertIsNotNone(layer)
        self.assertEqual(layer.page['number'], 24)
        # A final book page that happens to equal the pipe-gun source page is
        # still no artwork for this other weapon, rather than a borrowed image.
        self.assertIsNone(resolver.layer_for('weapon_baseball_bat'))
        self.assertIsNone(resolver.layer_for('weapon_pipe_gun'))
        coverage = resolver.coverage()
        self.assertEqual(coverage['counts']['replayed'], 1)
        self.assertEqual(coverage['weapons']['weapon_baseball_bat']['status'],
                         'no-manifest-page')
        self.assertEqual(coverage['weapons']['weapon_pipe_gun']['status'],
                         'manifest-page-without-exported-artwork')

    def test_source_hash_mismatch_fails_before_any_card_is_rendered(self):
        source = Path(self.tmp.name) / 'other-source.pdf'
        source.write_bytes(b'not the Publisher export')
        with self.assertRaises(CatalogArtworkError):
            ArtworkResolver(self.manifest_path, source_pdf=source)


@unittest.skipUnless(MANIFEST.exists() and SOURCE.exists(),
                     'Publisher PDF artwork extraction is not present')
class PublisherPage24RegressionTests(unittest.TestCase):
    """Page 24 had broken Publisher title spans and a rotated cropped SMask art."""

    def test_double_barrel_layer_is_exactly_replayed(self):
        try:
            import pymupdf
        except ImportError:  # pragma: no cover - dependency hint
            self.skipTest('pymupdf is not installed')
        resolver = ArtworkResolver(MANIFEST, ART_ROOT, SOURCE)
        layer = resolver.layer_for('weapon_double_barrel_shotgun')
        self.assertIsNotNone(layer)
        self.assertEqual(layer.page['number'], 24)
        placement = next(item for item in layer.page['placements']
                         if item.get('xref') == 468)
        self.assertEqual(placement['asset'], 'double-barrel-shotgun.png')
        self.assertEqual(placement['matrix_pdf'],
                         [434.73, -85.906, 62.688, 317.24, 36.9, 520.84])
        self.assertTrue(placement['has_custom_crop'])

        card = {
            'id': 'weapon_double_barrel_shotgun',
            'title': 'Двуствольный дробовик',
            'page': 27,
            'weight': 9, 'cost': 39, 'rarity': 1,
            'mods': [], 'description': '',
        }
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'double-barrel.pdf'
            w.render_card(card, str(output), artwork=layer)
            page = pymupdf.open(output)[0]
            matching = [item for item in page.get_image_info(xrefs=True)
                        if item['width'] == 923 and item['height'] == 673]
            self.assertEqual(len(matching), 1)
            a, b, c, d, e, f = placement['matrix_pdf']
            height = layer.page['size_points'][1]
            expected = (a, -b, -c, d, e + c, height - f - d)
            for actual, wanted in zip(matching[0]['transform'], expected):
                self.assertAlmostEqual(actual, wanted, places=3)
            self.assertTrue(matching[0]['has-mask'])
            self.assertIn(b'W*', page.read_contents())

    def test_institute_laser_has_no_substitute_publisher_layer(self):
        """A missing exact ID stays blank rather than borrowing Laser Gun art."""
        resolver = ArtworkResolver(MANIFEST, ART_ROOT, SOURCE)
        self.assertIsNone(resolver.layer_for('weapon_institute_laser'))
        coverage = resolver.coverage()
        self.assertEqual(coverage['weapons']['weapon_institute_laser']['status'],
                         'no-manifest-page')
        laser_gun = resolver.layer_for('weapon_laser_gun')
        self.assertIsNotNone(laser_gun)
        self.assertEqual(laser_gun.page['weapon_id'], 'weapon_laser_gun')


if __name__ == '__main__':
    unittest.main()
