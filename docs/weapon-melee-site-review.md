# Проверка модификаций ближнего и рукопашного боя

Проверка по страницам сайта пользователя, не по первичному документу эрраты.
При совпадении ID Companion эффекты и цена не обязательно совпадают у разных
предметов. Поэтому общие таблицы на этом этапе убраны, а краткие таблицы
помещены на страницы каждого оружия. Поправки хранятся отдельно в
`data/weapons/melee-site-mod-overrides.json`, исходный Companion не меняется.

- [Кувалда](https://www.fallout-2d20.ru/oruzhie/oruzhie-blizhnego-boya/kuvalda): прокалывающая +1 БК, +5 вес, +18; тяжёлая +2 БК, +9 вес, +30. Это не моды трубы, хотя Companion присваивает им общие `mod_heavy` и `mod_puncturing` со значениями других предметов.
- [Бейсбольная бита](https://www.fallout-2d20.ru/oruzhie/oruzhie-blizhnego-boya/bejsbolnaya-bita) и [алюминиевая](https://www.fallout-2d20.ru/oruzhie/oruzhie-blizhnego-boya/alyuminievaya-bejsbolnaya-bita): категория сайта «Бита», пять модов; значения для каждой биты перенесены отдельно, включая различие требований перков.
- [Боксерская перчатка](https://www.fallout-2d20.ru/oruzhie/oruzhie-blizhnego-boya/bokserskaya-perchatka), [кастет](https://www.fallout-2d20.ru/oruzhie/oruzhie-blizhnego-boya/kastet), [силовой кастет](https://www.fallout-2d20.ru/oruzhie/oruzhie-blizhnego-boya/silovoj-kastet) и [перчатка когтя смерти](https://www.fallout-2d20.ru/oruzhie/oruzhie-blizhnego-boya/perchatka-kogtya-smerti): моды действительно есть у рукопашного оружия, но параметры отличаются от некоторых одноимённых модов ближнего боя; применены постраничные значения сайта. Сопоставление «Колючая» перчатки с `mod_puncturing` и «Шипастая» с `mod_spiked` служит техническим отображением, а не доказательством идентичности записей.
- [Меч](https://www.fallout-2d20.ru/oruzhie/oruzhie-blizhnego-boya/mech): категория «Лезвие». Сайт и Companion расходятся по наличию скрытого лезвия; на странице оставлен расширенный список Companion, изменения требуют дальнейшей сверки.
- По сайту записаны категории и/или параметры для [дрына](https://www.fallout-2d20.ru/oruzhie/oruzhie-blizhnego-boya/dryn), [трубы](https://www.fallout-2d20.ru/oruzhie/oruzhie-blizhnego-boya/svintsovaya-truba), [ключа](https://www.fallout-2d20.ru/oruzhie/oruzhie-blizhnego-boya/razvodnoj-klyuch), [скалки](https://www.fallout-2d20.ru/oruzhie/oruzhie-blizhnego-boya/skalka), [кия](https://www.fallout-2d20.ru/oruzhie/oruzhie-blizhnego-boya/bilyardnyj-kij), [дубинки](https://www.fallout-2d20.ru/oruzhie/oruzhie-blizhnego-boya/dubinka), [баллонного ключа](https://www.fallout-2d20.ru/oruzhie/oruzhie-blizhnego-boya/balonnyj-klyuch), [трости](https://www.fallout-2d20.ru/oruzhie/oruzhie-blizhnego-boya/trost), [супермолота](https://www.fallout-2d20.ru/oruzhie/oruzhie-blizhnego-boya/supermolot) и [клинка штурмотрона](https://www.fallout-2d20.ru/oruzhie/oruzhie-blizhnego-boya/klinok-shturmotrona). Супермолот на сайте имеет вкладку «Бита»; не переназначаем её без проверки.
- [Гранатомёт со слезоточивым газом](https://www.fallout-2d20.ru/oruzhie/tyazhjoloe-oruzhie/granatomet-so-slezotochivym-gazom) расположен в тяжёлом разделе исходного PDF и на сайте, но Companion маркирует его `SMALL_GUNS` / `Light`. Категория книги сохранена; игровой навык требует отдельной проверки.

Остальные предметы и категории не проверены полностью. «Не уточнён» на странице
означает, что категория пока не установлена, а не что у модификации нет места
установки. Потребуется сверка дополнительных книг и эрраты.
