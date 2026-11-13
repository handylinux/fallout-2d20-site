import unittest
from unittest.mock import patch
import audit_weapon_sources as a


class NumericAuditTest(unittest.TestCase):
    def test_uncertain_values_do_not_vote(self):
        for value in (None, '', '—', '<1', '6+1', '2–4', True):
            self.assertIsNone(a.number(value))
        self.assertEqual(a.number('4 БК', 'pipboy', 'damage'), '4')
        self.assertEqual(a.number('0'), '0')
        self.assertEqual(a.number('1,50'), '1.5')

    def test_duplicate_source_names_are_not_joined(self):
        rows = [{'name': 'same'}, {'name': 'same'}, {'name': 'only'}]
        self.assertEqual(set(a.unique_index(rows, lambda r: r['name'])), {'only'})

    def test_audit_covers_every_weapon_and_does_not_count_ambiguous_weight_units(self):
        data = a.run()
        self.assertEqual(len(data['comparisons']), data['weapon_count'] * len(a.FIELDS))
        for row in data['comparisons']:
            if row['field'] == 'weight':
                self.assertNotIn('pipboy3000', row['votes'])
        self.assertEqual(data['pdf_headers_extracted'], 83)
        page = next(row for row in data['comparisons'] if row['weapon_id'] == 'weapon_sledgehammer' and row['field'] == 'cost')
        self.assertIsNone(page['original_pdf_page'])
        sword = next(row for row in data['comparisons'] if row['weapon_id'] == 'weapon_sword' and row['field'] == 'cost')
        self.assertEqual(sword['votes']['original_pdf'], '50')
        self.assertEqual(sword['original_pdf_page'], 96)
        pistol = next(row for row in data['comparisons'] if row['weapon_id'] == 'weapon_boarding_pistol' and row['field'] == 'fireRate')
        self.assertEqual(pistol['votes']['original_pdf'], '3')
        self.assertEqual(pistol['approved_by_user'], '0')
        injector_damage = next(row for row in data['comparisons'] if row['weapon_id'] == 'weapon_pistol_injector' and row['field'] == 'damage')
        self.assertEqual(injector_damage['approved_by_user'], '4')
        self.assertEqual(injector_damage['book_value'], '4')
        melee_rate = next(row for row in data['comparisons'] if row['weapon_id'] == 'weapon_sword' and row['field'] == 'fireRate')
        self.assertNotIn('original_pdf', melee_rate['votes'])

if __name__ == '__main__':
    unittest.main()
