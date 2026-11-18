import unittest
from weapons2cards import Companion
import weapon_mod_policy as policy

class ModPolicyTests(unittest.TestCase):
    def test_recoil_compensating_duplicate_is_suppressed_without_editing_raw_data(self):
        comp = Companion()
        self.assertIn(policy.RECOIL_COMPENSATING_SUPPRESSED_ID, comp.mods)
        self.assertIn(policy.RECOIL_COMPENSATING_CANONICAL_ID, comp.mods)
        self.assertEqual(
            set(comp.mods[policy.RECOIL_COMPENSATING_SUPPRESSED_ID]['applies_to_ids']),
            policy.RECOIL_COMPENSATING_OVERLAP_WEAPON_IDS,
        )
        for weapon_id in policy.RECOIL_COMPENSATING_OVERLAP_WEAPON_IDS:
            stock_ids = comp.slots[weapon_id]['Stock']
            self.assertIn(policy.RECOIL_COMPENSATING_SUPPRESSED_ID, stock_ids)
            self.assertIn(policy.RECOIL_COMPENSATING_CANONICAL_ID, stock_ids)
        canonical = comp.mods[policy.RECOIL_COMPENSATING_CANONICAL_ID]
        self.assertEqual(canonical['fireRateModifier'], {'op': '+', 'value': 1})
        self.assertEqual(canonical['qualityChanges'], [
            {'op': 'gain', 'id': 'quality_two-handed'},
            {'op': 'lose', 'id': 'quality_inaccurate'},
        ])
        self.assertEqual(
            policy.catalog_mod_ids([
                policy.RECOIL_COMPENSATING_SUPPRESSED_ID,
                policy.RECOIL_COMPENSATING_CANONICAL_ID,
            ]),
            [policy.RECOIL_COMPENSATING_CANONICAL_ID],
        )
        self.assertEqual(policy.CATALOG_RUSSIAN_MOD_NAMES[
            policy.RECOIL_COMPENSATING_CANONICAL_ID
        ], 'Ложа с компенсатором отдачи')

    def test_small_unique_and_mixed_sets(self):
        comp = Companion()
        unique = policy.specific_mods(comp, 'weapon_boarding_pistol')
        self.assertEqual(unique, {('Barrel', 'mod_aerodynamic_barrel'), ('Winch', 'mod_protected_winch'), ('Winch', 'mod_reinforced_winch')})
        self.assertEqual(len(policy.specific_mods(comp, 'weapon_assaultron_head_laser')), 4)
        self.assertEqual(policy.specific_mods(comp, 'weapon_laser_musket'), set())

    def test_disagreeing_sources_are_not_assumed_unique(self):
        comp = Companion()
        comp.slots['another_weapon'] = {'Winch': ['mod_protected_winch']}
        self.assertNotIn(('Winch', 'mod_protected_winch'), policy.specific_mods(comp, 'weapon_boarding_pistol'))
        comp.mods['mod_reinforced_winch']['applies_to_ids'] = []
        self.assertNotIn(('Winch', 'mod_reinforced_winch'), policy.specific_mods(comp, 'weapon_boarding_pistol'))

if __name__ == '__main__':
    unittest.main()
