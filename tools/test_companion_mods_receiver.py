import unittest

import companion_mods_receiver as c


class ReceiverConverterTests(unittest.TestCase):
    def test_effect_operations_and_localization(self):
        mod = {'damageModifier': {'op': 'set', 'value': 7},
               'rangeModifier': {'op': '-', 'value': 1},
               'effectChanges': [{'op': 'gain', 'id': 'effect_piercing_x', 'value': 1}],
               'qualityChanges': [{'op': 'remove', 'id': 'quality_inaccurate'}],
               'ammoOverride': 'ammo_308'}
        result = c.effect_text(mod, {'effect_piercing_x': 'Проникающий'},
                               {'quality_inaccurate': 'Неточное'}, {'ammo_308': 'Патрон .308'})
        for expected in ('Урон: установить 7 DC', 'уменьшить на 1 зону',
                         'Проникающий 1', 'Убрать качество «Неточное»', 'Патрон .308'):
            self.assertIn(expected, result)

    def test_unknown_or_missing_values_are_visible(self):
        self.assertEqual(c.number(None), '?')
        self.assertEqual(c.effect_text({}, {}, {}, {}), 'Не указано')
        self.assertIn('missing_id', c.effect_text({'effectChanges': [{'op': 'gain', 'id': 'missing_id'}]}, {}, {}, {}))
        self.assertIn('multiply', c.effect_text({'damageModifier': {'op': 'multiply', 'value': 3}}, {}, {}, {}))

    def test_candidates_are_not_guessed_and_collisions_are_reported(self):
        mods = [{'id': 'a', 'slot': 'Receiver'}, {'id': 'b', 'slot': 'Receiver'}]
        book = {'rows': [['Имя', 'префикс', 'эффект', '-', '+1', '-']]}
        data, report = c.generate(mods, {'a': 'Имя', 'b': 'Имя'}, {}, {}, {}, book)
        self.assertEqual(len(data['rows']), 2)
        self.assertIn('Неоднозначное название', report)
        self.assertIn('`a`', report)
        self.assertIn('`b`', report)

    def test_editable_prefix_does_not_change_mod_name(self):
        mods = [{'id': 'a', 'slot': 'Receiver', 'cost': 3}]
        book = {'rows': [['Имя', 'Префикс из книги', 'эффект', '-', '+3', '-']]}
        data, report = c.generate(mods, {'a': 'Имя'}, {}, {}, {}, book,
                                  {'a': 'Новый префикс'})
        self.assertEqual(data['rows'][0][0], 'Имя')
        self.assertEqual(data['rows'][0][1], 'Новый префикс')
        self.assertIn('Различия в сравнимых полях: префикс', report)
        fallback, _ = c.generate(mods, {'a': 'Имя'}, {}, {}, {}, book, {})
        self.assertEqual(fallback['rows'][0][1], 'Имя')

    def test_real_data_is_not_lost_and_difference_is_reported(self):
        mods = c.load(c.COMP / 'equipment/weapon_mods.json')
        data, report = c.generate(mods, c.index(c.EQUIP / 'weapon_mods.json'),
            c.index(c.SYSTEM / 'damageEffects.json'), c.index(c.SYSTEM / 'qualities.json'),
            c.index(c.EQUIP / 'ammo/ammo_types.json'), c.load(c.BOOK))
        self.assertEqual(len(data['rows']), sum(m.get('slot') == 'Receiver' for m in mods))
        self.assertIn('`mod_357_receiver`', report)
        self.assertIn('Различия в сравнимых полях: перки', report)
        self.assertIn('Эффекты требуют смысловой сверки', report)
        self.assertTrue(all(len(row) == 6 for row in data['rows']))


if __name__ == '__main__':
    unittest.main()
