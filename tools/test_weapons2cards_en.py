import unittest

import weapons2cards_en as cards


class EnglishCompanionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.companion = cards.Companion()

    def test_complete_weapon_coverage(self):
        built = [self.companion.card(wid) for wid in self.companion.weapons]
        self.assertEqual(len(built), 146)
        self.assertEqual(len({card["id"] for card in built}), 146)

    def test_institute_laser_is_energy_weapon(self):
        card = self.companion.card("weapon_institute_laser")
        self.assertEqual(card["title"], "Institute Laser")
        self.assertEqual(card["category"], "Energy Weapons")

    def test_incomplete_range_localization_uses_companion_english_equivalent(self):
        card = self.companion.card("weapon_atom_staff")
        self.assertEqual(card["range"], "Close")

    def test_weapon_mods_stay_attached_to_their_own_weapon(self):
        card = self.companion.card("weapon_gatling_gun")
        expected_ids = self.companion.slots["weapon_gatling_gun"]
        expected_names = [self.companion.mods_en[mid]["name"]
                          for slot_ids in expected_ids.values() for mid in slot_ids]
        actual_names = [name for row in card["mods"] for name in row["items"]]
        self.assertCountEqual(actual_names, expected_names)

    def test_english_labels_and_description_are_used(self):
        card = self.companion.card("weapon_10mm_pistol")
        self.assertEqual(card["title"], "10mm Pistol")
        self.assertEqual(card["labels"]["weight"], "Weight")
        self.assertIn("10mm pistol", card["description"])
        self.assertIn("Small", card["description"])


if __name__ == "__main__":
    unittest.main()
