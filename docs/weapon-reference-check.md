# Сверка английского каталога оружия с внешними выгрузками

Проверено по reference-data из Fallout-2d20-companion, commit
`2e66c7dc7c07d1fe1e62b1585e8764f453417193`.
Сравнение выполнено с полями каталога Companion; совпадение текста не
считалось доказательством правильности механики.

## Английские названия

| Выгрузка | Записей | Сопоставление с текущим EN-списком Companion |
|---|---:|---|
| `focharactersheet_weapons.json` | 134 | 126 названий совпадают дословно без учёта регистра; 8 не совпали |
| `lonestar_weapons.json` | 127 | 117 названий совпадают дословно без учёта регистра; 10 не совпали |
| `pipboy3000_weapons.json` | 136 | нет поля с отображаемым именем; у 100 записей ID механически сопоставился с ID Companion, 36 остались без прямого соответствия |
| `weapons.json` (Pip-Boy) | 63 | русские `name_ru`, поэтому не источник английских названий |

Таким образом, текущие английские названия Companion подтверждаются двумя
EN-справочниками для большинства совпавших записей. Несовпавшие названия —
альтернативные варианты или другие позиции; автоматом переименовывать их
нельзя без отдельного решения.

## Описания

У `focharactersheet`, Lone Star и Pip-Boy 3000 в этих JSON нет полей
`description`, `flavour` или другого текстового описания оружия. Описания в
PDF поэтому берутся из Companion EN `flavour`; сверить их с этими выгрузками
невозможно.

## Статы, термины и моды

Сверены названия боеприпасов, типы урона, эффекты, качества, скорострельность,
дальность, вес, цена, редкость и списки модификаций там, где записи можно
сопоставить.

- При сравнении точных EN-названий расхождения в выбранных числовых полях
  (вес, цена, редкость, урон и/или скорострельность — по наличию поля в
  источнике) найдены у 17 из 126 записей focharactersheet и у 53 из 117
  Lone Star. Например, у Gauss Rifle расходится редкость; у Double-Barrel
  Shotgun — цена; у Power Fist — урон. Значение `damageRating` Lone Star не
  сравнивалось напрямую с отдельным числом `damage`, поскольку схемы могут
  кодировать его по-разному.
- У Pip-Boy 3000 в 93 из 100 сопоставленных записей числовой вес равен
  половине значения Companion; в 7 остальных парах есть исключения (в том
  числе `0` в источнике при `<1` в Companion). Это системное расхождение
  шкалы, а не основание переносить числа без нормализации. Остальные поля
  тоже имеют отдельные расхождения.
- В EN-справочниках встречаются другие формы названия патрона (например,
  `Energy Cell` / `Fusion Cell`, а также названия без слова `Round`). Эти
  варианты сохранены в сверке, а не подменены молча.
- Списки и написания модификаций, эффектов и качеств отличаются между
  приложениями. Простое сравнение строк не позволяет отличить другую
  редакцию/схему данных от ошибки.

## Решение для PDF

В PDF использованы текущие поля Companion: это сохраняет одну согласованную
схему статов и привязок модов. EN-названия сверены по внешним справочникам;
для не совпавших вариантов Companion оставлен без автоматического
переименования. Числа и термины, по которым источники расходятся, не
подменялись на вариант одного приложения. Для карточек без описаний в
Companion EN описания не сочинялись.

Institute Laser отнесён к Energy Weapons по `weaponType` в данных Companion.

## Ссылки на источники

- [README reference-data и список источников](https://github.com/rpg-companios/Fallout-2d20-companion/blob/main/docs/reference-data/README.md)
- [Pip-Boy 3000: weapons](https://github.com/rpg-companios/Fallout-2d20-companion/blob/main/docs/reference-data/pipboy3000_weapons.json)
- [focharactersheet: weapons](https://github.com/rpg-companios/Fallout-2d20-companion/blob/main/docs/reference-data/focharactersheet_weapons.json)
- [Lone Star: weapons](https://github.com/rpg-companios/Fallout-2d20-companion/blob/main/docs/reference-data/lonestar_weapons.json)
- [Pip-Boy (RU): weapons](https://github.com/rpg-companios/Fallout-2d20-companion/blob/main/docs/reference-data/weapons.json)
- [Сводный аудит оружия upstream](https://github.com/rpg-companios/Fallout-2d20-companion/blob/main/docs/reference-data/WEAPON-AUDIT.md)
