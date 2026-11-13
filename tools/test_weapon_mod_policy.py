import unittest
from weapons2cards import Companion
import weapon_mod_policy as policy

class ModPolicyTests(unittest.TestCase):
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
