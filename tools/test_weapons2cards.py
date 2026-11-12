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

    def test_energy_weapon_slots_are_data_driven(self):
        card = cards.build_card(self.comp, "weapon_plasma_gun")
        self.assertEqual([m["slot"] for m in card["mods"]],
                         ["СТВОЛ", "КОНДЕНСАТОР", "РУКОЯТЬ", "ЛОЖА",
                          "ПРИЦЕЛ"])

    def test_capacitor_label_comes_from_companion(self):
        self.assertEqual(self.comp.slot_label("Capacitor"), "КОНДЕНСАТОР")
        self.assertEqual(self.comp.slot_label("Nozzle"), "СОПЛО")
        self.assertEqual(self.comp.slot_label("Winch"), "ЛЕБЁДКА")

    def test_effects_are_mapped_and_joined(self):
        card = cards.build_card(self.comp, "weapon_tesla_cannon")
        self.assertEqual(card["effects"], ["Дуга", "Проникающий 2"])

    def test_three_effect_weapon(self):
        card = cards.build_card(self.comp, "weapon_fat_man")
        self.assertEqual(card["effects"],
                         ["Порочный", "Разрушающий", "Радиоактивный"])

    def test_weapon_without_effects(self):
        card = cards.build_card(self.comp, "weapon_10mm_pistol")
        self.assertEqual(card["effects"], [])

    def test_dish_and_camera_use_the_companion_labels(self):
        self.assertEqual(self.comp.slot_label("Dish"), "ДИСК")
        self.assertEqual(self.comp.slot_label("Camera"), "КАМЕРА")

    def test_unique_slot_is_labelled(self):
        self.assertEqual(self.comp.slot_label("Unique"), "УНИКАЛЬНЫЙ")

    def test_unique_mods_of_a_melee_weapon(self):
        card = cards.build_card(self.comp, "weapon_sword")
        self.assertEqual([m["slot"] for m in card["mods"]], ["УНИКАЛЬНЫЙ"])
        self.assertEqual(card["mods"][0]["items"],
                         ["Электризованное", "Электризованное зазубренное",
                          "Зазубренное", "Скрытое", "Электрошокер"])

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
