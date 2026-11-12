"""Tests for tools/weapons2cards.py (Companion JSON → card JSON)."""

import unittest

import weapons2cards as cards


class CompanionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.comp = cards.Companion()

    def test_slugify(self):
        self.assertEqual(cards.slugify("weapon_10mm_pistol"), "10mm-pistol")
        self.assertEqual(cards.slugify("weapon_44_pistol").replace("-", ""),
                         "44pistol")

    def test_light_pistol_card(self):
        card = cards.build_card(self.comp, "weapon_10mm_pistol", page=18)
        self.assertEqual(card["title"], "10-мм пистолет")
        self.assertEqual(card["ammo"], "10-мм")
        self.assertEqual(card["damageType"], "Физический")
        self.assertEqual(card["range"], "Близкая")
        self.assertEqual(card["damage"], 4)
        self.assertEqual(card["qualities"], ["Вплотную", "Надежное"])
        self.assertEqual(card["page"], 18)

    def test_slots_are_in_book_order(self):
        card = cards.build_card(self.comp, "weapon_10mm_pistol")
        self.assertEqual([m["slot"] for m in card["mods"]],
                         ["РЕСИВЕР", "СТВОЛ", "РУКОЯТЬ", "МАГАЗИН",
                          "ПРИЦЕЛ", "ДУЛО"])

    def test_mods_follow_companion_order(self):
        card = cards.build_card(self.comp, "weapon_10mm_pistol")
        receiver = card["mods"][0]["items"]
        self.assertEqual(receiver[:4], ["Продвинутый", "Бронебойный",
                                        "Автоматический бронебойный",
                                        "Для автоогня"])

    def test_energy_weapon(self):
        card = cards.build_card(self.comp, "weapon_cryolator")
        self.assertEqual(card["damageType"], "Энергетический")
        self.assertEqual(card["effects"], ["Очередь"])
        self.assertIn("Изнуряющий", card["qualities"])

    def test_combined_damage_type(self):
        self.assertEqual(self.comp.damage_type(["energy", "physical"]),
                         "Энергетический и Физический")

    def test_melee_has_no_range(self):
        card = cards.build_card(self.comp, "weapon_switchblade")
        self.assertEqual(card["range"], "-")

    def test_missing_weapon_raises(self):
        with self.assertRaises(KeyError):
            cards.build_card(self.comp, "weapon_nope")


if __name__ == "__main__":
    unittest.main()
