import tempfile
import unittest
from pathlib import Path
import pymupdf
import weapon_melee_preview as melee


class MeleeBookTest(unittest.TestCase):
    def test_melee_pages_and_specific_mods_not_in_reference(self):
        source = Path('Справочник оружия.pdf')
        if not source.exists():
            self.skipTest('Source PDF not present')
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'book.pdf'
            info = melee.build(source, output)
            self.assertEqual(info['pages'], 131)
            self.assertEqual(info['weapons'], list(range(101, 132)))
            with pymupdf.open(output) as doc:
                reference = doc[98].get_text()
                sword = doc[100].get_text()
                shish = doc[105].get_text()
                self.assertIn('Зазубренное', reference)
                self.assertNotIn('Электризованное', reference)
                self.assertNotIn('Дополнительные воспламенительные', reference)
                self.assertIn('Электризованное', sword)
                self.assertIn('УНИКАЛЬНЫЙ', sword)
                self.assertIn('УНИКАЛЬНЫЙ', shish)
                self.assertIn('widespread', sword)
                self.assertNotIn('wideРазброс', sword)

if __name__ == '__main__':
    unittest.main()
