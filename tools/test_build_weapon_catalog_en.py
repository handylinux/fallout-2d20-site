import re
import tempfile
import unittest
from pathlib import Path

import pymupdf

import build_weapon_catalog_en as cat


def catalog_ids() -> list[str]:
    small = cat.load_json(cat.SMALL_ORDER)
    heavy = cat.load_json(cat.HEAVY_ORDER)
    energy = list(cat.load_json(cat.ENERGY_ORDER))
    energy.insert(energy.index('weapon_assaultron_head_laser') + 1, 'weapon_institute_laser')
    melee = cat.load_json(cat.MELEE_ORDER)
    rem = cat.load_json(cat.REMAINING_ORDER)
    return small + heavy + energy + melee + rem['unarmed'] + rem['thrown'] + rem['explosives']


class EnglishCatalogDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = cat.EnglishCatalogData()
        cls.all_ids = catalog_ids()

    def test_all_143_catalog_weapons_resolve_in_clean_english(self):
        self.assertEqual(len(self.all_ids), 143)
        self.assertEqual(len(set(self.all_ids)), 143)
        for wid in self.all_ids:
            card = self.data.build_card(wid, page=1)
            self.assertTrue(card['title'], wid)
            self.assertGreaterEqual(len(card['description']), 50, wid)
            blob = ' '.join([
                card['title'], str(card['ammo']), str(card['damageType']),
                str(card['range']), *card['effects'], *card['qualities'], card['description'],
                *(item for row in card['mods'] for item in [row['slot'], *row['items']]),
            ])
            self.assertFalse(re.search(r'[а-яА-ЯёЁ]', blob), f'Cyrillic leaked in {wid}')
            self.assertNotIn('Targetting', blob, wid)
            self.assertNotIn('Recoil X', blob, wid)
            self.assertNotIn('Muzzle Break', blob, wid)

    def test_numeric_fixes_and_bogus_template_filtering(self):
        for wid in ('weapon_alien_atomizer', 'weapon_alien_disintegrator', 'weapon_microwave_emitter', 'weapon_drone_cannon', 'weapon_plasma_mine'):
            self.assertEqual(self.data.applicable_slots(wid), {}, wid)

        self.assertEqual(self.data.build_card('weapon_underwater_gun', 1)['effects'], ['Piercing 2'])
        self.assertIn('Recoil 7', self.data.build_card('weapon_bumper_sword', 1)['qualities'])
        self.assertIn('Ammo-Hungry 5', self.data.build_card('weapon_tesla_cannon', 1)['qualities'])

        caster = self.data.build_card('weapon_plasma_caster', 1)
        self.assertEqual(caster['ammo'], 'Plasma Cartridge')
        self.assertEqual(caster['damageType'], 'Physical and Energy')
        self.assertIn('Recoil 8', caster['qualities'])

        boarding = self.data.build_card('weapon_boarding_pistol', 1)
        self.assertEqual(boarding['fireRate'], 0)
        self.assertEqual(boarding['effects'], ['Piercing 1', 'Special*'])
        self.assertEqual(len(self.data.detailed_rows('weapon_boarding_pistol')), 4)

        monicon = self.data.build_card('weapon_magnum_monicon', 1)
        self.assertEqual(monicon['damageType'], 'Special')

        self.assertEqual(len(self.data.heavy_site_mods['weapon_gatling_plasma']['mods']), 5)
        self.assertEqual(self.data.qualities['quality_targetting_computer']['name'], 'Targeting Computer')
        self.assertEqual(self.data.format_number(None), '—')
        self.assertEqual(self.data.format_number(0), '—')
        self.assertEqual(self.data.mod_name('mod_3_charge_camera'), '3-Shot Chamber')
        self.assertEqual(self.data.mod_name('mod_muzzle_break'), 'Muzzle Brake')


class BuildWeaponCatalogEnTests(unittest.TestCase):
    def test_build_full_english_catalog_pdf(self):
        source = cat.ROOT / 'Справочник оружия.pdf'
        if not source.is_file():
            self.skipTest('Source PDF not present')
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'catalog-en.pdf'
            report = Path(tmp) / 'report.md'
            stats = cat.build_with_toc(source, out, report)
            self.assertEqual(stats['weapons'], 143)
            self.assertEqual(stats['pages'] % 4, 0)
            self.assertGreaterEqual(stats['toc_pages'], 1)
            self.assertTrue(report.is_file())

            with pymupdf.open(out) as doc:
                toc_titles = [entry[1] for entry in doc.get_toc()]
                self.assertIn('Cover', toc_titles)
                self.assertIn('Damage Effects', toc_titles)
                self.assertIn('Weapon Qualities', toc_titles)
                self.assertIn('Institute Laser', toc_titles)
                self.assertIn('Gatling Plasma', toc_titles)

                cover_text = doc[0].get_text()
                self.assertIn('VOLUME 1', cover_text)
                self.assertIn('BROTHERHOOD MANUAL', cover_text)
                self.assertIn('WASTELAND ARSENAL', cover_text)
                self.assertNotIn('ТОМ', cover_text)

                toc_pages_text = ''
                toc_page_indices = []
                for i, page in enumerate(doc, 1):
                    text = page.get_text()
                    if 'TABLE OF CONTENTS' in text:
                        toc_page_indices.append(i)
                        toc_pages_text += text + '\n'
                self.assertEqual(len(toc_page_indices), stats['toc_pages'])
                self.assertGreaterEqual(len(toc_page_indices), 1)

                # Every weapon must be listed in the printed TOC with a page number
                data = cat.EnglishCatalogData()
                names = [data.weapons_en[wid]['name'] for wid in catalog_ids()]
                for name in names:
                    self.assertIn(name, toc_pages_text, f'TOC missing {name}')

                # A sample entry carries the correct final page number
                toc_page_map = {title: page for _lvl, title, page in stats['toc']}
                lines = [l.strip() for l in toc_pages_text.splitlines() if l.strip()]
                idx = next(i for i, l in enumerate(lines) if 'Gatling Plasma' in l)
                self.assertRegex(lines[idx + 1], r'^\d+$')
                self.assertEqual(int(lines[idx + 1]), toc_page_map['Gatling Plasma'])

                for i, page in enumerate(doc, 1):
                    pymupdf.TOOLS.mupdf_warnings()
                    text = page.get_text()
                    warnings = pymupdf.TOOLS.mupdf_warnings()
                    self.assertFalse(warnings, f'Page {i} MuPDF warning: {warnings}')
                    self.assertFalse(re.search(r'[а-яА-ЯёЁ]', text), f'Page {i} contains Cyrillic')
                    self.assertFalse(re.search(r'(?<!\w)DC(?!\w)', text), f'Page {i} has raw DC token')


if __name__ == '__main__':
    unittest.main()
