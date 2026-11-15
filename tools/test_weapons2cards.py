"""Tests for tools/weapons2cards.py (Companion JSON → card JSON)."""

import unittest
import json
import os
import shutil
import tempfile
from unittest.mock import patch

import weapons2cards as cards


class CompanionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.comp = cards.Companion()

    def test_working_copy_edits_drive_cards(self):
        with tempfile.TemporaryDirectory() as tmp:
            copy = os.path.join(tmp, 'companion')
            shutil.copytree(cards.COMP, copy)
            ru = os.path.join(copy, 'i18n', 'ru-RU', 'data')
            names = os.path.join(ru, 'equipment', 'weapons', 'weapons.json')
            with open(names, encoding='utf-8') as f:
                items = json.load(f)
            next(x for x in items if x['id'] == 'weapon_10mm_pistol')['name'] = 'Изменённый пистолет'
            with open(names, 'w', encoding='utf-8') as f:
                json.dump(items, f, ensure_ascii=False)
            with patch.object(cards, 'COMP', copy), patch.object(cards, 'RU', ru):
                result = cards.build_card(cards.Companion(), 'weapon_10mm_pistol')
            self.assertEqual(result['title'], 'Изменённый пистолет')
            self.assertEqual(self.comp.weapon_name('weapon_10mm_pistol'), '10-мм пистолет')

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

    def test_multiple_ammo_types_are_preserved(self):
        self.assertEqual(self.comp.ammo_name(self.comp.weapons['weapon_gatling_laser']),
                         'Энергоячейка / Ядерный блок')
        self.assertIn('[unknown_ammo]', self.comp.ammo_name({'ammoId': 'ammo_fusion_core,unknown_ammo'}))

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

    def test_mod_names_do_not_repeat_the_weapon_name(self):
        ripper = cards.build_card(self.comp, 'weapon_ripper')
        self.assertEqual(ripper['mods'][0]['items'][:2],
                         ['Изогнутое лезвие', 'Удлиненное лезвие'])
        for mod_id in ('mod_curved_blade', 'mod_electrified', 'mod_extended_blade',
                       'mod_extra_claw', 'mod_extra_heavy', 'mod_heavy',
                       'mod_hooked', 'mod_lead_lining'):
            self.assertNotIn(':', self.comp.mods_ru[mod_id]['name'])
        with open(os.path.join(cards.ROOT, 'data/weapon-book/mod-prefixes.ru.json'), encoding='utf-8') as source:
            prefixes = json.load(source)
        for mod_id in ('mod_curved_blade', 'mod_electrified', 'mod_extended_blade',
                       'mod_extra_claw', 'mod_extra_heavy', 'mod_heavy',
                       'mod_hooked', 'mod_lead_lining'):
            self.assertNotIn(':', prefixes[mod_id])

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

    def test_canonical_quality_and_effect_terms(self):
        self.assertEqual(self.comp.qualities['quality_debilitating']['name'], 'Изнуряющий')
        self.assertEqual(self.comp.qualities['quality_concealed']['name'], 'Скрытное')
        self.assertEqual(self.comp.qualities['quality_placed']['name'], 'Установка')
        self.assertEqual(self.comp.qualities['quality_parry']['name'], 'Парирование')
        self.assertEqual(self.comp.effects['effect_freeze']['name'], 'Заморозка')
        self.assertEqual(self.comp.effects['effect_stun']['name'], 'Оглушение')

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
