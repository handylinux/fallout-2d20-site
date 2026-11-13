# Сверка оружия: предварительный машинный аудит

Это не глобальная сверка всех источников: первичная эррата, моды, эффекты, качества, боеприпасы и категории здесь не проверены. Сайт сверён лишь для части предметов; остальные не голосуют. Из исходного PDF извлечены вес, цена, редкость и однозначно читаемые числовые ячейки урона и скорострельности. Сопоставление колонок по геометрии требует проверки по исходным страницам. Совпадение точных названий и ID не доказывает идентичность варианта; для публикации требуется проверка. Этот скрипт не меняет PDF или JSON оружия; отдельно отмечены известные применённые поправки, а для остальных применение ещё не проверено.

Вес Pip-Boy 3000 не участвует: значения систематически вдвое меньше; единицы не подтверждены. Преобразование без проверки не выполняется.

Голосование: уникальное большинство строго более половины доступных числовых голосов и минимум три источника; меньшее покрытие и ничьи — на ручную проверку. Отсутствующее, неопознанное и неоднозначное значение не голосует; прочерк, «<1» и выражения вроде «6+1» не подменяются числом. Зафиксированные решения пользователя имеют приоритет. Разные проекты могут использовать общий первоисточник; это голоса записей, не доказательство независимости.

Обработано записей Companion: 146; заголовков PDF извлечено: 83; страниц сайта вручную сверено: 17. Точные однозначные сопоставления: focharactersheet: 122, lonestar: 115, pipboy: 45, pipboy3000: 102.
Расходящихся полей: 129; предварительное большинство: 125; остальные — без решения.

Ссылки на проверенные страницы сайта — в `data/weapon-audit/site-observations.json`. Подтверждённые решения пользователя, например скорострельность абордажного пистолета 0, не отменяются большинством.

Полный машиночитаемый список с голосами: `data/weapon-audit/numeric-audit.json`. Источники и версии: `data/weapon-audit/sources/README.md`, фиксированный коммит 2e66c7dc7c07d1fe1e62b1585e8764f453417193.

| ID | Поле | Голоса по источникам | Предварительный результат |
|---|---|---|---|
| `weapon_gauss_rifle` (Карабин Гаусса) | Редкость | companion: 5; original_pdf стр.20: 4; pipboy: 4; lonestar: 4; focharactersheet: 4; pipboy3000: 4 | большинство 4 — не проверено применение |
| `weapon_double_barrel_shotgun` (Двуствольный дробовик) | Цена | companion: 39; original_pdf стр.24: 39; pipboy: 39; lonestar: 39; focharactersheet: 30; pipboy3000: 39 | большинство 39 — не проверено применение |
| `weapon_gamma_gun` (Гамма-пушка) | Вес | companion: 3; original_pdf стр.84: 4; pipboy: 3; lonestar: 3; focharactersheet: 3 | большинство 3 — не проверено применение |
| `weapon_gamma_gun` (Гамма-пушка) | Цена | companion: 15; original_pdf стр.84: 50; pipboy: 156; lonestar: 156; focharactersheet: 156 | большинство 156 — не проверено применение |
| `weapon_gamma_gun` (Гамма-пушка) | Редкость | companion: 5; original_pdf стр.84: 2; pipboy: 5; lonestar: 5; focharactersheet: 5 | большинство 5 — не проверено применение |
| `weapon_fat_man` (Толстяк) | Цена | companion: 512; original_pdf стр.58: 512; pipboy: 512; lonestar: 352; focharactersheet: 512; pipboy3000: 512 | большинство 512 — не проверено применение |
| `weapon_flamer` (Огнемёт) | Редкость | companion: 3; original_pdf стр.59: 3; pipboy: 3; lonestar: 2; focharactersheet: 3 | большинство 3 — не проверено применение |
| `weapon_heavy_incinerator` (Тяжёлый инсинератор) | Вес | companion: 20; original_pdf стр.61: 16; pipboy: 20; lonestar: 19; focharactersheet: 20 | большинство 20 — не проверено применение |
| `weapon_heavy_incinerator` (Тяжёлый инсинератор) | Цена | companion: 350; original_pdf стр.61: 137; pipboy: 350; lonestar: 804; focharactersheet: 350 | большинство 350 — не проверено применение |
| `weapon_heavy_incinerator` (Тяжёлый инсинератор) | Редкость | companion: 4; original_pdf стр.61: 3; pipboy: 4; lonestar: 3; focharactersheet: 4 | большинство 4 — не проверено применение |
| `weapon_junk_jet` (Хламотрон) | Скорострельность | companion: 1; site: 1; original_pdf стр.62: 0; pipboy: 1; lonestar: 0; focharactersheet: 1; pipboy3000: 1 | большинство 1 — не проверено применение |
| `weapon_junk_jet` (Хламотрон) | Вес | companion: 30; site: 30; original_pdf стр.62: 30; pipboy: 30; lonestar: 20; focharactersheet: 30 | большинство 30 — не проверено применение |
| `weapon_junk_jet` (Хламотрон) | Цена | companion: 285; site: 286; original_pdf стр.62: 286; pipboy: 285; lonestar: 392; focharactersheet: 285; pipboy3000: 285 | большинство 285 — не проверено применение |
| `weapon_junk_jet` (Хламотрон) | Редкость | companion: 3; site: 3; original_pdf стр.62: 3; pipboy: 3; lonestar: 2; focharactersheet: 3; pipboy3000: 3 | большинство 3 — не проверено применение |
| `weapon_minigun` (Миниган) | Цена | companion: 382; original_pdf стр.63: 382; pipboy: 382; lonestar: 302; focharactersheet: 382; pipboy3000: 382 | большинство 382 — не проверено применение |
| `weapon_minigun` (Миниган) | Редкость | companion: 2; original_pdf стр.63: 2; pipboy: 2; lonestar: 3; focharactersheet: 2; pipboy3000: 2 | большинство 2 — не проверено применение |
| `weapon_sword` (Меч) | Цена | companion: 50; site: 50; original_pdf стр.96: 50; pipboy: 50; lonestar: 25; focharactersheet: 50; pipboy3000: 50 | большинство 50 — не проверено применение |
| `weapon_combat_knife` (Боевой нож) | Урон | companion: 3; site: 3; original_pdf стр.97: 4; pipboy: 3; focharactersheet: 3; pipboy3000: 3 | большинство 3 — не проверено применение |
| `weapon_combat_knife` (Боевой нож) | Цена | companion: 25; site: 25; original_pdf стр.97: 25; pipboy: 25; lonestar: 30; focharactersheet: 25; pipboy3000: 25 | большинство 25 — не проверено применение |
| `weapon_combat_knife` (Боевой нож) | Редкость | companion: 1; site: 1; original_pdf стр.97: 1; pipboy: 1; lonestar: 0; focharactersheet: 1; pipboy3000: 1 | большинство 1 — не проверено применение |
| `weapon_machete` (Мачете) | Вес | companion: 2; original_pdf стр.98: 2; pipboy: 2; lonestar: 3; focharactersheet: 2 | большинство 2 — не проверено применение |
| `weapon_machete` (Мачете) | Цена | companion: 25; original_pdf стр.98: 25; pipboy: 25; lonestar: 20; focharactersheet: 25; pipboy3000: 25 | большинство 25 — не проверено применение |
| `weapon_ripper` (Потрошитель) | Вес | companion: 6; site: 6; original_pdf стр.99: 6; pipboy: 6; lonestar: 4; focharactersheet: 6 | большинство 6 — не проверено применение |
| `weapon_ripper` (Потрошитель) | Цена | companion: 50; site: 50; original_pdf стр.99: 50; pipboy: 50; lonestar: 25; focharactersheet: 50; pipboy3000: 50 | большинство 50 — не проверено применение |
| `weapon_shishkebab` (Шиш-кебаб) | Вес | companion: 3; site: 3; original_pdf стр.101: 1; pipboy: 3; lonestar: 5; focharactersheet: 3 | большинство 3 — не проверено применение |
| `weapon_shishkebab` (Шиш-кебаб) | Цена | companion: 200; site: 200; original_pdf стр.101: 20; pipboy: 200; lonestar: 32; focharactersheet: 200; pipboy3000: 200 | большинство 200 — не проверено применение |
| `weapon_shishkebab` (Шиш-кебаб) | Редкость | companion: 3; site: 3; original_pdf стр.101: 0; pipboy: 3; lonestar: 2; focharactersheet: 3; pipboy3000: 3 | большинство 3 — не проверено применение |
| `weapon_switchblade` (Выкидной нож) | Цена | companion: 20; original_pdf стр.100: 20; pipboy: 20; lonestar: 10; focharactersheet: 20; pipboy3000: 20 | большинство 20 — не проверено применение |
| `weapon_baseball_bat` (Бейсбольная бита) | Цена | companion: 25; site: 25; pipboy: 25; lonestar: 20; focharactersheet: 25; pipboy3000: 25 | большинство 25 — не проверено применение |
| `weapon_baseball_bat` (Бейсбольная бита) | Редкость | companion: 1; site: 1; pipboy: 1; lonestar: 0; focharactersheet: 1; pipboy3000: 1 | большинство 1 — не проверено применение |
| `weapon_board` (Дрын) | Цена | companion: 20; pipboy: 20; lonestar: 15; focharactersheet: 20; pipboy3000: 20 | большинство 20 — не проверено применение |
| `weapon_lead_pipe` (Свинцовая труба) | Вес | companion: 3; pipboy: 3; lonestar: 2; focharactersheet: 3 | большинство 3 — не проверено применение |
| `weapon_lead_pipe` (Свинцовая труба) | Цена | companion: 15; pipboy: 15; lonestar: 4; focharactersheet: 15; pipboy3000: 15 | большинство 15 — не проверено применение |
| `weapon_pipe_wrench` (Разводной ключ) | Цена | companion: 30; pipboy: 30; lonestar: 11; focharactersheet: 30; pipboy3000: 30 | большинство 30 — не проверено применение |
| `weapon_pipe_wrench` (Разводной ключ) | Редкость | companion: 1; pipboy: 1; lonestar: 0; focharactersheet: 1; pipboy3000: 1 | большинство 1 — не проверено применение |
| `weapon_pool_cue` (Бильярдный кий) | Цена | companion: 10; lonestar: 12; focharactersheet: 10; pipboy3000: 10 | большинство 10 — не проверено применение |
| `weapon_baton` (Дубинка) | Цена | companion: 15; lonestar: 10; focharactersheet: 15; pipboy3000: 15 | большинство 15 — не проверено применение |
| `weapon_baton` (Дубинка) | Редкость | companion: 1; lonestar: 0; focharactersheet: 1; pipboy3000: 1 | большинство 1 — не проверено применение |
| `weapon_sledgehammer` (Кувалда) | Вес | companion: 12; site: 12; pipboy: 12; lonestar: 3; focharactersheet: 12 | большинство 12 — не проверено применение |
| `weapon_sledgehammer` (Кувалда) | Цена | companion: 40; site: 40; pipboy: 40; lonestar: 30; focharactersheet: 40; pipboy3000: 40 | большинство 40 — не проверено применение |
| `weapon_sledgehammer` (Кувалда) | Редкость | companion: 2; site: 2; pipboy: 2; lonestar: 1; focharactersheet: 2; pipboy3000: 2 | большинство 2 — не проверено применение |
| `weapon_super_sledge` (Супермолот) | Вес | companion: 20; lonestar: 30; focharactersheet: 20 | большинство 20 — не проверено применение |
| `weapon_tire_iron` (Балонный ключ) | Цена | companion: 25; lonestar: 2; focharactersheet: 25; pipboy3000: 25 | большинство 25 — не проверено применение |
| `weapon_tire_iron` (Балонный ключ) | Редкость | companion: 1; lonestar: 0; focharactersheet: 1; pipboy3000: 1 | большинство 1 — не проверено применение |
| `weapon_walking_cane` (Трость) | Вес | companion: 2; pipboy: 2; lonestar: 1; focharactersheet: 2 | большинство 2 — не проверено применение |
| `weapon_walking_cane` (Трость) | Цена | companion: 10; pipboy: 10; lonestar: 3; focharactersheet: 10 | большинство 10 — не проверено применение |
| `weapon_boxing_glove` (Боксерская перчатка) | Цена | companion: 10; pipboy: 10; lonestar: 50; focharactersheet: 10; pipboy3000: 10 | большинство 10 — не проверено применение |
| `weapon_boxing_glove` (Боксерская перчатка) | Редкость | companion: 1; pipboy: 1; lonestar: 2; focharactersheet: 1; pipboy3000: 1 | большинство 1 — не проверено применение |
| `weapon_deathclaw_gauntlet` (Перчатка когтя смерти) | Вес | companion: 10; pipboy: 10; lonestar: 3; focharactersheet: 10 | большинство 10 — не проверено применение |
| `weapon_deathclaw_gauntlet` (Перчатка когтя смерти) | Цена | companion: 75; pipboy: 75; lonestar: 200; focharactersheet: 75; pipboy3000: 75 | большинство 75 — не проверено применение |
| `weapon_knuckles` (Кастет) | Цена | companion: 10; pipboy: 10; lonestar: 25; focharactersheet: 10; pipboy3000: 10 | большинство 10 — не проверено применение |
| `weapon_power_fist` (Силовой кастет) | Урон | companion: 4; pipboy: 4; focharactersheet: 3; pipboy3000: 4 | большинство 4 — не проверено применение |
| `weapon_power_fist` (Силовой кастет) | Вес | companion: 4; pipboy: 4; lonestar: 6; focharactersheet: 4 | большинство 4 — не проверено применение |
| `weapon_power_fist` (Силовой кастет) | Цена | companion: 100; pipboy: 100; lonestar: 50; focharactersheet: 100; pipboy3000: 100 | большинство 100 — не проверено применение |
| `weapon_tomahawk` (Томагавк) | Вес | lonestar: 4; focharactersheet: 1 | **проверить** |
| `weapon_javelin` (Дротик) | Вес | companion: 4; lonestar: 10; focharactersheet: 4 | большинство 4 — не проверено применение |
| `weapon_javelin` (Дротик) | Редкость | companion: 1; lonestar: 2; focharactersheet: 1; pipboy3000: 1 | большинство 1 — не проверено применение |
| `weapon_alien_blaster` (Бластер пришельцев) | Вес | companion: 2; original_pdf стр.91: 2; focharactersheet: 3 | большинство 2 — не проверено применение |
| `weapon_alien_blaster` (Бластер пришельцев) | Цена | companion: 90; original_pdf стр.91: 90; focharactersheet: 125 | большинство 90 — не проверено применение |
| `weapon_alien_blaster` (Бластер пришельцев) | Редкость | companion: 5; original_pdf стр.91: 5; focharactersheet: 3 | большинство 5 — не проверено применение |
| `weapon_tesla_rifle` (Карабин Теслы) | Урон | companion: 4; site: 5; original_pdf стр.87: 5; focharactersheet: 5; pipboy3000: 5 | большинство 5 — в сборке |
| `weapon_cryolator` (Криолятор) | Вес | companion: 14; original_pdf стр.70: 13; focharactersheet: 14 | большинство 14 — не проверено применение |
| `weapon_12_7mm_smg` (12,7-мм пистолет-пулемёт) | Скорострельность | companion: 3; site: 3; original_pdf стр.32: 2; lonestar: 3; focharactersheet: 3; pipboy3000: 3 | большинство 3 — не проверено применение |
| `weapon_12_7mm_smg` (12,7-мм пистолет-пулемёт) | Вес | companion: 5; site: 5; original_pdf стр.32: 13; lonestar: 8; focharactersheet: 5 | большинство 5 — не проверено применение |
| `weapon_12_7mm_smg` (12,7-мм пистолет-пулемёт) | Цена | companion: 510; site: 510; original_pdf стр.32: 144; lonestar: 420; focharactersheet: 510; pipboy3000: 510 | большинство 510 — не проверено применение |
| `weapon_12_7mm_smg` (12,7-мм пистолет-пулемёт) | Редкость | companion: 4; site: 4; original_pdf стр.32: 2; lonestar: 4; focharactersheet: 4; pipboy3000: 4 | большинство 4 — не проверено применение |
| `weapon_25mm_grenade_apw` (Противопехотный 25-мм гранатомёт) | Скорострельность | companion: 1; original_pdf стр.33: 1; lonestar: 2; focharactersheet: 1; pipboy3000: 1 | большинство 1 — не проверено применение |
| `weapon_25mm_grenade_apw` (Противопехотный 25-мм гранатомёт) | Вес | companion: 8; original_pdf стр.33: 8; lonestar: 2; focharactersheet: 8 | большинство 8 — не проверено применение |
| `weapon_25mm_grenade_apw` (Противопехотный 25-мм гранатомёт) | Цена | companion: 420; original_pdf стр.33: 420; lonestar: 30; focharactersheet: 420; pipboy3000: 420 | большинство 420 — не проверено применение |
| `weapon_25mm_grenade_apw` (Противопехотный 25-мм гранатомёт) | Редкость | companion: 4; original_pdf стр.33: 4; lonestar: 2; focharactersheet: 4; pipboy3000: 4 | большинство 4 — не проверено применение |
| `weapon_9mm_pistol` (9-мм пистолет) | Скорострельность | companion: 2; original_pdf стр.34: 2; lonestar: 1; focharactersheet: 2; pipboy3000: 2 | большинство 2 — не проверено применение |
| `weapon_9mm_pistol` (9-мм пистолет) | Вес | companion: 2; original_pdf стр.34: 2; lonestar: 20; focharactersheet: 2 | большинство 2 — не проверено применение |
| `weapon_9mm_pistol` (9-мм пистолет) | Цена | companion: 50; original_pdf стр.34: 50; lonestar: 560; focharactersheet: 50; pipboy3000: 50 | большинство 50 — не проверено применение |
| `weapon_9mm_pistol` (9-мм пистолет) | Редкость | companion: 2; original_pdf стр.34: 2; lonestar: 4; focharactersheet: 2; pipboy3000: 2 | большинство 2 — не проверено применение |
| `weapon_anti_materiel_rifle` (Крупнокалиберная снайперская винтовка) | Вес | companion: 20; original_pdf стр.35: 20; lonestar: 10; focharactersheet: 20 | большинство 20 — не проверено применение |
| `weapon_anti_materiel_rifle` (Крупнокалиберная снайперская винтовка) | Цена | companion: 560; original_pdf стр.35: 560; lonestar: 150; focharactersheet: 560; pipboy3000: 560 | большинство 560 — не проверено применение |
| `weapon_anti_materiel_rifle` (Крупнокалиберная снайперская винтовка) | Редкость | companion: 4; original_pdf стр.35: 4; lonestar: 3; focharactersheet: 4; pipboy3000: 4 | большинство 4 — не проверено применение |
| `weapon_black_powder_blunderbuss` (Пороховой мушкетон) | Вес | companion: 3; original_pdf стр.37: 9; lonestar: 3; focharactersheet: 3 | большинство 3 — не проверено применение |
| `weapon_black_powder_blunderbuss` (Пороховой мушкетон) | Цена | companion: 90; original_pdf стр.37: 55; lonestar: 90; focharactersheet: 90; pipboy3000: 90 | большинство 90 — не проверено применение |
| `weapon_black_powder_blunderbuss` (Пороховой мушкетон) | Редкость | companion: 3; original_pdf стр.37: 2; lonestar: 3; focharactersheet: 3; pipboy3000: 3 | большинство 3 — не проверено применение |
| `weapon_alien_disintegrator` (Дезинтегратор пришельцев) | Урон | companion: 8; site: 8; original_pdf стр.90: 6; focharactersheet: 8; pipboy3000: 8 | большинство 8 — не проверено применение |
| `weapon_alien_disintegrator` (Дезинтегратор пришельцев) | Скорострельность | companion: 7; site: 2; original_pdf стр.90: 3; lonestar: 2; focharactersheet: 2; pipboy3000: 2 | большинство 2 — в сборке |
| `weapon_alien_disintegrator` (Дезинтегратор пришельцев) | Вес | companion: 7; site: 7; original_pdf стр.90: 3; lonestar: 7; focharactersheet: 7 | большинство 7 — не проверено применение |
| `weapon_alien_disintegrator` (Дезинтегратор пришельцев) | Цена | companion: 921; site: 921; original_pdf стр.90: 1536; lonestar: 921; focharactersheet: 921; pipboy3000: 921 | большинство 921 — не проверено применение |
| `weapon_arc_welder` (Дуговая сварка) | Урон | companion: 3; site: 3; original_pdf стр.93: 6; focharactersheet: 3; pipboy3000: 3 | большинство 3 — не проверено применение |
| `weapon_arc_welder` (Дуговая сварка) | Скорострельность | companion: 4; site: 4; original_pdf стр.93: 3; lonestar: 4; focharactersheet: 4; pipboy3000: 4 | большинство 4 — не проверено применение |
| `weapon_arc_welder` (Дуговая сварка) | Вес | companion: 15; site: 15; original_pdf стр.93: 3; lonestar: 15; focharactersheet: 15 | большинство 15 — не проверено применение |
| `weapon_arc_welder` (Дуговая сварка) | Цена | companion: 370; site: 370; original_pdf стр.93: 1536; lonestar: 370; focharactersheet: 370; pipboy3000: 370 | большинство 370 — не проверено применение |
| `weapon_arc_welder` (Дуговая сварка) | Редкость | companion: 4; site: 4; original_pdf стр.93: 5; lonestar: 4; focharactersheet: 4; pipboy3000: 4 | большинство 4 — не проверено применение |
| `weapon_auto_grenade_launcher` (Автоматический гранатомёт) | Цена | companion: 450; original_pdf стр.66: 450; lonestar: 450; focharactersheet: 350; pipboy3000: 450 | большинство 450 — не проверено применение |
| `weapon_sten_injector` (Стен-инжектор) | Урон | companion: 3; original_pdf стр.77: 4 | **проверить** |
| `weapon_sten_injector` (Стен-инжектор) | Скорострельность | companion: 4; original_pdf стр.77: 3 | **проверить** |
| `weapon_pistol_injector` (Пистолет-инжектор) | Урон | companion: 0; site: 5; original_pdf стр.47: 4 | согласовано пользователем: 4 |
| `weapon_pistol_injector` (Пистолет-инжектор) | Скорострельность | companion: 4; site: 0; original_pdf стр.47: 0 | большинство 0 — в сборке |
| `weapon_crossbow` (Арбалет) | Скорострельность | companion: 2; original_pdf стр.55: 2; lonestar: 0; focharactersheet: 0; pipboy3000: 0 | большинство 0 — не проверено применение |
| `weapon_boarding_pistol` (Абордажный пистолет) | Скорострельность | companion: 3; site: 0; original_pdf стр.51: 3 | согласовано пользователем: 0 |
| `weapon_pulse_mine` (Pulse Mine) | Урон | companion: 9; focharactersheet: 6; pipboy3000: 6 | большинство 6 — не проверено применение |
| `weapon_pulse_mine` (Pulse Mine) | Вес | companion: 0.5; lonestar: 1; focharactersheet: 1 | большинство 1 — не проверено применение |
| `weapon_pulse_mine` (Pulse Mine) | Цена | companion: 135; lonestar: 100; focharactersheet: 100; pipboy3000: 100 | большинство 100 — не проверено применение |
| `weapon_bumper_sword` (Большой меч) | Вес | companion: 12; lonestar: 3; focharactersheet: 12 | большинство 12 — не проверено применение |
| `weapon_bumper_sword` (Большой меч) | Цена | companion: 125; lonestar: 90; focharactersheet: 125; pipboy3000: 125 | большинство 125 — не проверено применение |
| `weapon_bumper_sword` (Большой меч) | Редкость | companion: 2; lonestar: 4; focharactersheet: 2; pipboy3000: 2 | большинство 2 — не проверено применение |
| `weapon_ballistic_fist` (Баллистический кулак) | Вес | companion: 6; lonestar: 12; focharactersheet: 6 | большинство 6 — не проверено применение |
| `weapon_ballistic_fist` (Баллистический кулак) | Цена | companion: 150; lonestar: 125; focharactersheet: 150; pipboy3000: 150 | большинство 150 — не проверено применение |
| `weapon_ballistic_fist` (Баллистический кулак) | Редкость | companion: 4; lonestar: 2; focharactersheet: 4; pipboy3000: 4 | большинство 4 — не проверено применение |
| `weapon_cattle_prod` (Электрошокер) | Вес | companion: 3; lonestar: 12; focharactersheet: 3 | большинство 3 — не проверено применение |
| `weapon_cattle_prod` (Электрошокер) | Цена | companion: 90; lonestar: 140; focharactersheet: 90; pipboy3000: 90 | большинство 90 — не проверено применение |
| `weapon_cattle_prod` (Электрошокер) | Редкость | companion: 4; lonestar: 3; focharactersheet: 4; pipboy3000: 4 | большинство 4 — не проверено применение |
| `weapon_chainsaw` (Бензопила) | Вес | companion: 12; lonestar: 1; focharactersheet: 12 | большинство 12 — не проверено применение |
| `weapon_chainsaw` (Бензопила) | Цена | companion: 140; lonestar: 40; focharactersheet: 140; pipboy3000: 140 | большинство 140 — не проверено применение |
| `weapon_chainsaw` (Бензопила) | Редкость | companion: 3; lonestar: 2; focharactersheet: 3; pipboy3000: 3 | большинство 3 — не проверено применение |
| `weapon_death_tambo` (Танбо смерти) | Вес | companion: 1; lonestar: 6; focharactersheet: 1 | большинство 1 — не проверено применение |
| `weapon_death_tambo` (Танбо смерти) | Цена | companion: 40; lonestar: 175; focharactersheet: 40; pipboy3000: 40 | большинство 40 — не проверено применение |
| `weapon_death_tambo` (Танбо смерти) | Редкость | companion: 2; lonestar: 4; focharactersheet: 2; pipboy3000: 2 | большинство 2 — не проверено применение |
| `weapon_displacer_glove` (Перчатка-вытеснитель) | Вес | companion: 6; lonestar: 3; focharactersheet: 6 | большинство 6 — не проверено применение |
| `weapon_displacer_glove` (Перчатка-вытеснитель) | Цена | companion: 175; lonestar: 45; focharactersheet: 175; pipboy3000: 175 | большинство 175 — не проверено применение |
| `weapon_displacer_glove` (Перчатка-вытеснитель) | Редкость | companion: 4; lonestar: 3; focharactersheet: 4; pipboy3000: 4 | большинство 4 — не проверено применение |
| `weapon_cryo_mine` (Крио-мина) | Цена | companion: 50; lonestar: 75; focharactersheet: 50; pipboy3000: 50 | большинство 50 — не проверено применение |
| `weapon_detonator` (Детонатор) | Цена | companion: 75; lonestar: 25; focharactersheet: 75; pipboy3000: 75 | большинство 75 — не проверено применение |
| `weapon_detonator` (Детонатор) | Редкость | companion: 3; lonestar: 2; focharactersheet: 3; pipboy3000: 3 | большинство 3 — не проверено применение |
| `weapon_dynamite` (Динамит) | Вес | companion: 1; lonestar: 2; focharactersheet: 1 | большинство 1 — не проверено применение |
| `weapon_dynamite` (Динамит) | Цена | companion: 25; lonestar: 150; focharactersheet: 25; pipboy3000: 25 | большинство 25 — не проверено применение |
| `weapon_dynamite` (Динамит) | Редкость | companion: 2; lonestar: 3; focharactersheet: 2; pipboy3000: 2 | большинство 2 — не проверено применение |
| `weapon_dynamite_bundle` (Связка динамита) | Вес | companion: 2; lonestar: 1; focharactersheet: 2 | большинство 2 — не проверено применение |
| `weapon_dynamite_bundle` (Связка динамита) | Цена | companion: 150; lonestar: 40; focharactersheet: 150; pipboy3000: 150 | большинство 150 — не проверено применение |
| `weapon_dynamite_bundle` (Связка динамита) | Редкость | companion: 3; lonestar: 2; focharactersheet: 3; pipboy3000: 3 | большинство 3 — не проверено применение |
| `weapon_flash_bang` (Светошумовая граната) | Цена | companion: 40; lonestar: 75; focharactersheet: 40; pipboy3000: 40 | большинство 40 — не проверено применение |
| `weapon_flash_bang` (Светошумовая граната) | Редкость | companion: 2; lonestar: 4; focharactersheet: 2; pipboy3000: 2 | большинство 2 — не проверено применение |
| `weapon_frag_grenade_mirv` (Осколочная граната MIRV) | Цена | companion: 75; lonestar: 200; focharactersheet: 75; pipboy3000: 75 | большинство 75 — не проверено применение |
