"""Regression tests for the English editable weapon-modification reference."""

import unittest

import companion_mods_en as mods
from weapons2cards_en import Companion


class EnglishModificationReferenceTests(unittest.TestCase):
    def test_every_companion_mod_is_localised_and_listed_once(self):
        companion = Companion()
        data, diagnostics = mods.make_mod_data(companion)
        self.assertEqual(diagnostics, [])
        self.assertEqual(data["title"], "WEAPON MODIFICATIONS")
        self.assertEqual(data["headers"], list(mods.HEADERS))
        self.assertEqual(len(data["sections"]), 20)
        rows = [row for section in data["sections"] for row in section["rows"]]
        self.assertEqual(len(rows), len(companion.base_mods))
        self.assertEqual(len(rows), 164)
        self.assertTrue(all(len(row) == 6 for row in rows))
        self.assertTrue(all(not any("\u0400" <= char <= "\u04ff" for char in value)
                            for row in rows for value in row))
        self.assertEqual(data["sections"][0]["category"], "RECEIVER MODIFICATIONS")
        self.assertEqual(data["sections"][-1]["category"], "UNIQUE MODIFICATIONS")

    def test_duplicate_legacy_damage_type_is_rendered_once(self):
        companion = Companion()
        text = mods.effect_text(companion.base_mods["mod_electrified"], companion)
        self.assertEqual(text.count("Damage Type: Energy"), 1)
        self.assertIn("Damage: +2 DC", text)


if __name__ == "__main__":
    unittest.main()
