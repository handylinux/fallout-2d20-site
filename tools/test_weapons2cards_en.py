"""Regression tests for the English Companion card adapter."""

import unittest

import weapons2cards_en as cards


class EnglishCompanionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.companion = cards.Companion()

    def test_complete_weapon_coverage(self):
        built = [self.companion.card(weapon_id)
                 for weapon_id in self.companion.weapons]
        self.assertEqual(len(built), 146)
        self.assertEqual(len({card["id"] for card in built}), 146)

    def test_institute_laser_is_an_energy_weapon(self):
        card = self.companion.card("weapon_institute_laser")
        self.assertEqual(card["title"], "Institute Laser")
        self.assertEqual(card["category"], "Energy Weapons")

    def test_incomplete_range_localisation_uses_confirmed_english_equivalent(self):
        card = self.companion.card("weapon_atom_staff")
        self.assertEqual(card["range"], "Close")

    def test_weapon_mods_stay_attached_to_their_own_weapon(self):
        card = self.companion.card("weapon_gatling_gun")
        expected_ids = self.companion.slots["weapon_gatling_gun"]
        expected_names = [self.companion.mods_en[mod_id]["name"]
                          for slot_ids in expected_ids.values()
                          for mod_id in slot_ids]
        actual_names = [name for row in card["mods"] for name in row["items"]]
        self.assertCountEqual(actual_names, expected_names)

    def test_english_labels_and_description_are_used(self):
        card = self.companion.card("weapon_10mm_pistol")
        self.assertEqual(card["title"], "10mm Pistol")
        self.assertEqual(card["labels"]["weight"], "Weight")
        self.assertEqual(card["labels"]["headers"], [
            "AMMO", "DAMAGE\nTYPE", "DAMAGE", "FIRE\nRATE", "RANGE", "EFFECTS",
            "QUALITIES",
        ])
        self.assertIn("10mm pistol", card["description"])

    def test_catalog_excludes_only_confirmed_non_weapons(self):
        cards_in_order = cards.ordered_cards(self.companion)
        card_ids = {card["id"] for card in cards_in_order}
        self.assertEqual(set(self.companion.weapons) - card_ids,
                         cards.CATALOG_EXCLUDED_IDS)
        self.assertNotIn("weapon_assaultron_head", card_ids)
        self.assertNotIn("weapon_straight_razor", card_ids)
        self.assertIn("weapon_assaultron_head_laser", card_ids)
        self.assertIn("weapon_unarmed_attack", card_ids)

    def test_order_is_stable_and_numbers_every_page(self):
        cards_in_order = cards.ordered_cards(self.companion)
        self.assertEqual(len(cards_in_order), 144)
        self.assertEqual([card["page"] for card in cards_in_order],
                         list(range(1, 145)))
        self.assertEqual(cards_in_order[0]["category"], "Light Weapons")
        # Straight Razor was the only Other card and is intentionally absent.
        self.assertEqual(cards_in_order[-1]["category"], "Unarmed Weapons")


if __name__ == "__main__":
    unittest.main()
