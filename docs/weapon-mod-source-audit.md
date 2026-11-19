# Сверка модификаций оружия: подтверждённые решения

Сравнивается одно и то же оружие, слот и вариант мода. Совпадающее значение
двух источников имеет приоритет над одиночным; при 1:1 между Publisher и
Companion используется Publisher. Отсутствие записи — не голос за другую
версию. Сравнение не меняет исходный снимок Companion.

## Первая партия

Источник Publisher — `Справочник оружия.pdf` в корне репозитория. Сверены
`weapon_mod_slots.json` и `weapon_mods.json` из `data/weapon-book/companion/`,
а также [совместимость в Helper на ревизии 39d2cd7](https://github.com/handylinux/Fallout-2d20-helper/blob/39d2cd769d6ff47bfdb12a9a43c6ac3cde10a1ab/back/src/db/seed/data/itemModCompatibility.ts).
У следующих четырёх видов оружия в `BIG_GUNS_COMPATIBILITY` Helper нет
строк. В частности, `Laser Gatling` — не обычный `Gatling Gun`, а `Minigun`
— не `Eugene`. Для них исходные оружейные таблицы Publisher/Companion
сравниваются без третьего голоса.

| Оружие | Стр. Publisher | Пример расхождения | Публикуем в EN |
|---|---:|---|---|
| Broadsider («Залп») | 67 | Long Barrel: Companion +6 к цене и удаляет Close Quarters | +1 зона, вес +3, цена +135, Gun Nut 3 |
| Gatling Gun (обычный Гатлинг) | 68 | Long: Companion вес +1, цена +20, Gun Nut 1 | +1 зона, вес +2, цена +158, Gun Nut 4 |
| Harpoon Gun (гарпуномёт) | 73 | Short Scope: Companion добавляет Accurate, цена +11 | Добавляет Reliable, вес +1, цена +28, Gun Nut 1 |
| Eugene | 75 | Tri-Barrel: Companion +2 DC и −2 к скорости стрельбы, Gun Nut 4 | +1 к скорости стрельбы, вес +3, цена +75, Gun Nut 3 |

Полные английские строки, а не глобальные замены одноимённых модов, записаны
в [`publisher-mod-variants.en.json`](../data/weapon-book/publisher-mod-variants.en.json).
Страницы RU для этой партии уже воспроизводят свои таблицы Publisher. Для
остального оружия EN пока используются данные Companion, а не обещание, что
они совпадают с исходником. Известный конфликт связей Gatling Plasma выделен
отдельно: список слотов Companion сохранён на карточке EN с пометкой о
неподтверждённой совместимости и не участвует в подсчёте общих модов. У русской версии есть отдельная сверка этой
карточки с сайтом, которую предстоит согласовать для EN.
