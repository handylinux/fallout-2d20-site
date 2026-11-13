# SPPB → HTML: прототипы страниц из JSON

В репозитории лежит экспорт сайта на **SP Page Builder 5** (Joomla). Этот набор
файлов превращает JSON-прототипы в чистые статические HTML-страницы: с той же
сеткой, шириной колонок, отступами, цветaми, фонами, таблицами и поведением
табов/аккордеонов.

```
data/supermutant.sppb.json                    исходный JSON (как прислали)
data/bestiarij.sppb.json                      хаб «Бестиарий» (карточки категорий)
data/ekskavatornaya-silovaya-bronya.sppb.json
tools/sppb2html.py                            конвертер (Python 3, без зависимостей)
pages/supermutant.html                        готовый прототип
pages/ekskavatornaya-silovaya-bronya.html     готовый прототип
pages/index.html                              список прототипов
docs/catalog.md                               архитектура справочника и синтаксис ссылок
jos_sppagebuilder.zip                         дамп таблицы jos_sppagebuilder (366 страниц)
```

## Быстрый старт

```bash
# один файл
python3 tools/sppb2html.py data/supermutant.sppb.json -o pages/supermutant.html

# несколько файлов + индекс
python3 tools/sppb2html.py data/*.sppb.json -o pages --index

# все страницы из дампа базы
python3 tools/sppb2html.py jos_sppagebuilder.zip --all -o build/site --index

# только несколько страниц по названию
python3 tools/sppb2html.py jos_sppagebuilder.zip --all --only "силовая" -o build/site
```

Картинки и ссылки по умолчанию переписываются на `https://www.fallout-2d20.ru/`,
поэтому прототип сразу выглядит «как на сайте». Для полностью локальной версии:

```bash
python3 tools/sppb2html.py data/supermutant.sppb.json -o out.html \
  --asset-base "" --link-base ""
```

## Что именно переносится

### Секции (rows)

| JSON | HTML/CSS |
|---|---|
| `layout` (`6+6`, `3+9`, `12`) | подсказка, **не** источник истины |
| `columns[].settings.width` | `sppb-col-{bp}-{n}` (Bootstrap-сетка 12 колонок) |
| `padding`, `margin` (xl/lg/md/sm/xs) | CSS + media-запросы для каждого брейкпоинта |
| `background_type` + `background_color` / `background_image` / `background_gradient` | `background-*` |
| `background_repeat/size/attachment/position` | переносятся как есть |
| `columns_gap` | CSS-переменная `--sppb-gutter` c media-запросами |
| `no_gutter` | класс `sppb-no-gutter` (нулевые отступы колонок) |
| `fullscreen` | `sppb-section-fullwidth` (контейнер на всю ширину) |
| `columns_align_center` | `sppb-row--align-center` |
| `row_border*`, `row_boxshadow` | рамка и тень секции |
| `hidden_xl…hidden_xs` | `sppb-hidden-*` |
| `class`, `id` | переносятся в атрибуты |

### Колонки

* Ширина берётся из `width` для **каждого** брейкпоинта. Пустое значение
  наследует десктопное (`xl`) — как в SPPB.
* `padding`, `margin`, фон, `use_border` + `border_width`/`border_color`,
  `border_radius`, `boxshadow`, `items_align_center`, `hidden_*`.
* Если ширина не кратна 1/12, генерируется точный процент вместо класса.

### Аддоны

Поддержаны: `heading`, `text_block`, `image`, `row` (вложенный ряд), `tab`,
`accordion`, `table_advanced`, `raw_html`, `empty_space`, `divider`, `button`,
`feature`, `navigation`; `module` и `articles` выводятся заметной заглушкой
(это динамика Joomla, её нет в JSON).

Общие настройки аддонов (`global_padding`, `global_margin`,
`global_background_*`, `global_border_*`, `global_boxshadow`,
`global_border_radius`, `global_text_color`, `global_link_color`, `class`,
`hidden_*`, `global_custom_position`) переносятся на обёртку аддона.
`global_custom_css` добавляется в конец `<style>` — как это делает SPPB.

### Таблицы

* Таблицы внутри `text_block` сохраняются как есть (включая inline-стили),
  оборачиваются в `.sppb-table-wrap` для горизонтального скролла на мобильных.
* `table_advanced` собирается в настоящую `<table>`: первая строка
  `sp_table_advanced_item` → `<thead><th>`, строки `table_advanced_item` →
  `<tbody><td>`, в каждой ячейке рендерятся свои аддоны. Переносятся
  `header_color`, `header_bg_color`, `tr_bg_color`, `td_second_bg_color`,
  `table_text_alignment`, отступы/рамки, если заданы.

### Поведение

* Табы: переключение по клику, клавиши ←/→, активный таб подсвечивается,
  прямые ссылки вида `#sppb-tab1-1` работают.
* Аккордеон: `openitem = hide/show`, ARIA-атрибуты, `+ / −`.
* Всё на нативном JS, без jQuery и без сборки.

## Важные находки по данным

1. **Количество колонок надо брать из `width`, а не из `layout`.**
   В прототипе «Экскаваторная силовая броня» у ряда `6+6+6+6` у всех четырёх
   колонок стоит `width.xl = 50%` — на десктопе это сетка 2×2, а не 4 в ряд.
2. **Пустые значения брейкпоинтов наследуют десктоп.** Например, у секции
   задан только `xl: "15px 0px 5px 0px"` — этот отступ действует на всех
   ширинах, пока не переопределён.
3. **`visibility = false` у аддона = он выключен.** В «Супермутанте» так
   скрыты три текстовых блока (их же нет и на живом сайте).
4. **Цвет фона применяется, даже если `background_type = "none"`.**
   Бeжевые плашки черт/инвентаря заданы только через
   `global_background_color`; если смотреть на `background_type`, они пропадут.
5. **`global_text_color` у заголовка — это цвет текста на плашке.**
   У «ОСОБЕННОСТИ»/«ИНВЕНТАРЬ» одновременно `background_color: #000` и
   `text_color: #fff`, поэтому заголовок — белая надпись на чёрной полосе.
6. **`{/CD}`** — шорткод Joomla-плагина, на сайте превращается в иконку
   боевого кубика (`images/CD.png`). Конвертер делает то же самое.
7. **`{Термин}`** (например `{Иммунитет к радиации}`) — шорткод другого
   плагина, которого нет в экспорте. Конвертер выводит термин жирным
   (`<strong class="sppb-term">`), но не подставляет описание: словаря
   терминов в выгрузке нет.
8. В текстах встречаются мусорные теги TinyMCE `<mce:root>` — они вычищаются.
9. Значения вида `"   "`, `"5px 0px 5px px"` нормализуются, чтобы не ломать
   CSS-декларацию.

## Ограничения

* **Шапка/подвал/шрифты Joomla-шаблона не входят в JSON.** Прототип — это
  содержимое страницы в собственной нейтральной обёртке (Bootstrap-подобная
  базовая типографика и контейнер 1140px). Если нужен полный «вид сайта»,
  нужно отдельно подключить CSS шаблона.
* `module` и `articles` — динамические аддоны; в JSON нет их содержимого.
* Изображения не скачиваются (в выгрузке только пути). По умолчанию они
  грузятся с живого сайта; для офлайна положите `images/` рядом и запустите
  с `--asset-base ""`.
* Анимации, параллакс и «while scroll» пока не воспроизводятся (в этих
  страницах они выключены).

## Мобильные клоны аддонов

Если на мобильном блок должен стоять в другом месте, а на ПК — как есть,
в JSON-обёртке страницы задаётся `mobile_clone`:

```json
"mobile_clone": {
  "from": "a7bc860b-0a4f-47ad-bb61-bcb846041dbd",
  "into": "17b8fea5-0c28-46c8-81a7-756bb57fea51",
  "after": "55c47558-e190-44c2-b64e-879be0b5fb69",
  "class": "supermutant-desc-mobile",
  "hide_class": "supermutant-desc-original"
}
```

Аддон `from` клонируется в колонку `into` сразу после `after`, получает новый
`id` и класс `class`; секция-источник получает `hide_class`. Показ/скрытие —
обычным CSS в поле `css`:

```css
.supermutant-desc-mobile{display:none}
@media (max-width: 767.98px){
  .supermutant-desc-mobile{display:block}
  .supermutant-desc-original{display:none}
}
```

Так в `data/supermutant.sppb.json` описание на мобильном оказывается под
картинкой, а на ПК остаётся внизу. Текст хранится в одном месте — клон
собирается при загрузке страницы.

## Хаб категорий

`data/bestiarij.sppb.json` — страница «Бестиарий»: пять карточек-колонок
(заголовок, картинка, кнопка «Подробнее»). Кнопка лежит в аддоне `raw_html`,
её оформление и анимация стрелок заданы в поле `css` обёртки страницы и
подключаются в общий `<style>`.

Особенности вёрстки этой страницы (тоже в `css`):

* колонки-карточки — `display:flex`, чтобы кнопка прижималась к низу
  (`margin-top:auto`) и карточки в ряду были одной высоты;
* возвращены боковые отступы колонок (в JSON у них `padding: 30px 0 20px`,
  из-за чего карточки слипались);
* заголовки карточек — 20px, без жирности, в верхнем регистре, как на сайте;
* ширина картинок берётся из `image_width` каждого аддона (300/180/230 px).

## Как расширять

Добавить новый аддон — это один метод в `Renderer`:

```python
def addon_carousel(self, addon, selector, settings):
    ...
    return "<div class=\"...\">...</div>"
```

Имя метода — `addon_<name>` из JSON. Если метода нет, в HTML попадёт заметная
заглушка, а CLI вернёт предупреждение.

## Проверка

```bash
python3 -m unittest discover -s tools -v
```

Тест сверяет количество секций/колонок/аддонов/таблиц с исходным JSON,
проверяет ключевые CSS-правила (отступы, цвета, ширины), отсутствие
шорткодов и мусорных тегов.

В конце каждого HTML есть комментарий с фактическими счётчиками:

```html
<!-- sppb2html: sections=29 columns=34 addons=333 tables=26 -->
```

## Что сгенерировано сейчас

| файл | секции | колонки | аддоны | таблицы |
|---|---|---|---|---|
| `pages/bestiarij.html` | 2 | 5 | 13 | 0 |
| `pages/supermutant.html` | 3 | 5 | 17 | 4 |
| `pages/ekskavatornaya-silovaya-bronya.html` | 29 | 34 | 333 | 26 |

---

# Генератор страниц брони (`tools/armor2page.py`)

Собирает страницу брони из данных компаньона в оформлении «Экскаваторной
силовой брони»: заголовок, картинка, карточки характеристик (ФИЗ/ЭНРГ/РАД,
вес, цена, редкость), вкладки модификаций и аккордеоны с таблицами.

## Что где лежит

| что | файл |
|---|---|
| данные компаньона | `data/companion/equipment/*.json` |
| русские названия | `data/companion/i18n/ru-RU/data/equipment/armor/*.json` |
| описание страницы | `data/armor-pages/*.json` |
| оформление | `ARMOR_CSS` в `tools/armor2page.py` |
| результат | `pages/armor/*.html` + `pages/armor/index.html` |

Данные компаньона — копия `modules/fallout/{data,i18n}` из
`rpg-companios/Fallout-2d20-companion`. Обновить копию:

```bash
git clone --depth 1 https://github.com/rpg-companios/Fallout-2d20-companion.git /tmp/companion
tools/sync_companion_data.sh /tmp/companion
```

## Запуск

```bash
python3 tools/armor2page.py                     # все страницы из data/armor-pages
python3 tools/armor2page.py --only leather-armor
```

## Как добавить страницу

Скопируйте `data/armor-pages/leather-armor.json`, поменяйте:

* `set` — ключ из `armor.json` (`raiderArmor`, `metalArmor`, …) или
  `powerArmor.json` (`t45`, `t51`, …), плюс `collection`: `armor` или `powerArmor`;
* `slug` и `title` — имя файла и заголовок;
* `image`, `back`, `intro` — картинка, ссылка «назад» и вступительный текст
  (если лора нет, можно оставить lorem ipsum);
* `tier_titles` — подписи уровней (`standard`, `sturdy`, `heavy`);
* `hero` — главный блок: `tier` (какой уровень показывать слева) и `side`
  (`left`/`right`, с какой стороны карточки, картинка — с другой);
* `tabs_title` — заголовок над вкладками;
* `tabs` — вкладки по порядку:
  * `{"type": "tiers", "title": "Категории", "tiers": ["sturdy", "heavy"]}` —
    спойлеры с таблицами «дельта от стандартного уровня»;
  * `{"type": "mods", "title": "…", "categories": ["standardMods"]}` —
    аккордеоны модификаций из `armor_mods.json` / `uniq_armor_mods.json`.

Характеристики, названия деталей, модификации и эффекты берутся из JSON
компаньона — руками их дублировать не нужно.

## Поведение

* Базовый уровень (по умолчанию `standard`) — главный блок: картинка слева,
  карточки справа (сторону задаёт `hero.side`); описание идёт под этим блоком.
  Остальные уровни — во вкладке «Категории».
* Вкладки — раскрывающиеся секции: содержимое по умолчанию скрыто, панель
  открывается сразу под нажатой вкладкой; можно открыть несколько.
* Внутри вкладки одновременно открыт максимум один спойлер: открыли
  «Тяжёлую» — «Укреплённая» закрылась.
* Внутри «Категорий» — спойлер на уровень и таблица: строки — характеристики,
  столбцы — детали, значения — дельта от стандартного уровня (`+1`, `0`, `−2`).
* Название детали в карточке — из i18n; заголовок карточки — по зоне
  (`Body` → НАГРУДНИК, `Hand` → НАРУЧ, `Leg` → ПОНОЖ, `Head` → ШЛЕМ).
* Модификации фильтруются по зонам сета; если показывать нечего, вкладка
  не выводится.
* Эффекты берутся из `armor_effects.json` (русские описания), стат-модификаторы
  (`+3 к ЭНРГ. СУ`) собираются из `statModifiers`.
* На экранах до 768px:
  * таблицы модификаций разворачиваются в вертикальные: слева категория
    (`Модификация`, `Эффект`, …) с тёмным фоном и белым шрифтом, справа значение
    с тем же фоном, что и на ПК;
  * «Категории» показывают каждую деталь отдельной таблицей в две колонки
    (`характеристика → дельта`), цвета ячеек сохраняются.
* Страница самодостаточная: CSS и JS встроены, внешняя только картинка.

## Ограничения

* В репозитории компаньона **нет модификаций силовой брони** — у таких страниц
  раздела модификаций не будет, пока данные не появятся.
* Лора и картинок в данных снаряжения нет — они задаются в JSON страницы.
* Пока генерируется только броня (`armor.json` и `powerArmor.json`).

---

# PDF-справочник оружия (`tools/weapon2pdf.py`)

Собирает страницу оружия A4 один-в-один с PDF, свёрстанным в Publisher:
заголовок, линейка, «Вес / Цена / Редкость», картинка, таблица статов,
описание и таблица модификаций (колонок столько, сколько модов в самой
большой категории — от 1 до 6; строки по высоте содержимого, таблица
строится от нижнего поля вверх).

```
data/weapons/cards/combat-rifle.json   карточка (страница 18 из Publisher)
data/weapons/cards/revolver-44.json    карточка «Револьвер калибра .44»
data/weapons/cards/10mm-pistol.json    пример: лёгкое оружие
data/weapons/cards/gatling-gun.json    пример: тяжёлое оружие
data/weapons/cards/cryolator.json      пример: энергетическое оружие
data/weapons/cards/plasma-gun.json     пример: энергооружие со слотом «КОНДЕНСАТОР»
tools/weapons2cards.py                 Companion JSON → карточки
tools/weapon2pdf.py                    генератор PDF
assets/fonts/Carlito-*.ttf             шрифт (OFL, метрический клон Calibri)
assets/pdf/paper.jpg                   бумажная текстура из PDF
assets/pdf/weapons/*.png               картинки оружия (из книги: tools/extract_pdf_images.py)
tools/extract_pdf_images.py            вытащить картинки из PDF книги
docs/weapon-pdf.md                     геометрия, кегли, правила, пробелы в данных
```

```bash
python3 -m pip install -r tools/requirements-pdf.txt
python3 tools/weapon2pdf.py data/weapons/cards/combat-rifle.json \
    --out docs/render/out/combat-rifle.pdf
python3 tools/weapon2pdf.py data/weapons/cards/revolver-44.json \
    --out docs/render/out/revolver-44.pdf

# вытащить изображения из книги (в том числе иллюстрации разделов)
python3 tools/extract_pdf_images.py "Справочник оружия.pdf" --out art/
# По умолчанию короткая сторона >=100 пикселей, площадь >=60000 пикселей;
# параметры --min-size и --min-area позволяют изменить пороги.
# имена берутся с самой страницы: заголовок «БОЕВОЙ КАРАБИН» → weapon_combat_rifle
# → art/combat-rifle.png (тот же слаг, что у карточки); если заголовок не
# совпал с weapons.json — art/p018.png, а в report.csv пустой weapon_id
# art/index.html — контактный лист со страницами, art/report.csv — таблица

# карточка из данных компаньона (описание — английское flavour)
python3 tools/weapons2cards.py weapon_10mm_pistol --page 18 \
    --image assets/pdf/weapons/combat-rifle.png
python3 tools/weapon2pdf.py data/weapons/cards/10mm-pistol.json \
    --out docs/render/out/10mm-pistol.pdf

# набор и русские метки слотов берутся из weapon_mod_slots.json и
# i18n/ru-RU/screens-weaponsAndArmor.json (weapon.modSlots) — у каждого типа
# оружия свои категории (энергооружие: «КОНДЕНСАТОР», «СОПЛО» и т. д.)
python3 tools/weapons2cards.py weapon_plasma_gun --page 21 \
    --image assets/pdf/weapons/combat-rifle.png
python3 tools/weapon2pdf.py data/weapons/cards/plasma-gun.json \
    --out docs/render/out/plasma-gun.pdf
```

Тесты (`tools/test_weapon2pdf.py`) проверяют перенос строк, разбиение
категории на строки по 6 модов, растяжение таблицы до нижнего поля, номер
страницы на внешнем поле и рендер PDF (если установлен PyMuPDF).

### Начало книги: промежуточная сборка

`weapon_book_front.py` копирует физические страницы 1–9 исходного PDF без
перевёрстки: обложку, разворот, эффекты, качества и разделитель. Это временный
этап сборки, а не генерация этих страниц из данных. Нужен исходный PDF.

```bash
python tools/weapon_book_front.py "Справочник оружия.pdf" --out docs/render/out/book-front.pdf
```

Выходной путь должен отличаться от пути исходного PDF. Номера страниц в
результате сохранены как в оригинале.

### Проверочный фрагмент стрелкового раздела

```bash
python tools/weapon_book_small_guns_preview.py "Справочник оружия.pdf" --image-dir art --out docs/render/out/small-guns-preview.pdf
```

Страницы 1–13 копируются из оригинального PDF, включая таблицы модификаций
и обложку раздела. Страницы 14–16 генерируются из Companion без изображений
оружия, с местом для последующей вставки вручную. Это проверочный фрагмент,
не полный раздел и не перевёрстка справочных таблиц.

Для полного стрелкового раздела добавьте `--full`: порядок сохранён в
`data/weapons/small-guns-order.json`, после 43 страниц оригинала добавлен
10-мм пистолет-пулемёт. Страницы оружия создаются без картинок по умолчанию;
для прежнего варианта можно передать `--with-images`. Первые 13 страниц остаются из
оригинального PDF; таблицы модов ещё не перевёрстаны.

```bash
python tools/weapon_book_small_guns_preview.py "Справочник оружия.pdf" --image-dir art --full --out docs/render/out/small-guns-full.pdf
```

### Прототип таблицы модификаций

```bash
python tools/weapon_mods_table.py data/weapons/mods-receiver-sample.json --out docs/render/out/mods-receiver-preview.pdf
```

Это отдельная пробная страница с редактируемым текстом, не встроенная в
книгу. Данные — ручная расшифровка страницы 10 исходного PDF, они требуют
сверки с первоисточником и Companion; пустые поля в строке 10-мм оставлены
пустыми как в оригинале. В старом ReportLab-образце обозначение `DC` текстовое; Unicode-рендерер
заменяет `DC` в эффектах на иконку урона. При длинной таблице строки переносятся на следующие страницы
с повторением шапки. Файл данных не претендует на полный каталог модификаций.

### Ресиверы из Companion: пробное сопоставление

```bash
python tools/companion_mods_receiver.py --out-json data/weapons/mods-receiver-companion.json --report docs/weapon-mods-receiver-comparison.md
python tools/weapon_mods_table.py data/weapons/mods-receiver-companion.json --out docs/render/samples/mods-receiver-companion.pdf
```

Экспортирует только `Receiver`: операции урона, скорострельности, дистанции,
боеприпасов, эффектов и качеств превращаются в текст. Цена, вес и перки берутся
из Companion. `?` / «Не указано» — отсутствующее значение, а не ноль; неизвестные
операции и ID остаются видимыми. Префиксы задаются в отдельном рабочем JSON,
при отсутствии берутся из локализации. Отчёт сопоставляет
строки образца по имени как неподтверждённых кандидатов; одинаковые имена и
смысл эффектов необходимо проверять вручную. Это прототип, ещё не часть книги.

### Проверка совместимости кириллицы в PDF

Просмотрщик GitHub на Android показал искажённый текст и не показал фон в PDF
таблицы, созданном ReportLab. Для проверки подготовлена альтернативная сборка
с полностью встроенными шрифтами Type0 / Identity-H и текстом (не картинками):

```bash
python tools/weapon_mods_table_unicode.py data/weapons/mods-receiver-companion.json --out docs/render/out/mods-receiver-compatible.pdf
```

Работа в GitHub-приложении и редактирование в FlexiPDF требуют проверки на
устройстве пользователя. Предыдущие образцы и книга не пересобраны этим способом.

### Рабочие JSON книги — ручные изменения

Сборка страниц оружия и преобразователь ресиверов читают **рабочие копии** из
`data/weapon-book/companion/`, а не оригинал `data/companion/`. Это отдельные
файлы в репозитории: обновление оригинала скриптом синхронизации их не перезапишет.
Новые данные из Companion не попадают в рабочие копии автоматически — их надо
сверить и перенести вручную, сохраняя собственные правки.

* Характеристики оружия: `data/weapon-book/companion/equipment/weapons.json`.
* Названия и описания оружия: `data/weapon-book/companion/i18n/ru-RU/data/equipment/weapons/weapons.json`.
* Характеристики модов: `data/weapon-book/companion/equipment/weapon_mods.json`.
* Названия модов: `data/weapon-book/companion/i18n/ru-RU/data/equipment/weapon_mods.json`.
* Префиксы: `data/weapon-book/mod-prefixes.ru.json` — по ID, независимо от имени.
  Если запись отсутствует или пуста, используется `prefix` из локализации,
  а если его нет — `name`, как в Companion. Сгенерированный
  `data/weapons/mods-receiver-companion.json` — результат, а не исходник.

После правок (в PowerShell из папки проекта):

```powershell
python tools\weapon_book_small_guns_preview.py ".\Справочник оружия.pdf" --full --out docs\render\out\small-guns-full.pdf
python tools\companion_mods_receiver.py --out-json data\weapons\mods-receiver-companion.json --report docs\weapon-mods-receiver-comparison.md
python tools\weapon_mods_table_unicode.py data\weapons\mods-receiver-companion.json --out docs\render\out\mods-receiver.pdf
```

Первый PDF содержит текущие страницы оружия, но его страницы 1–13 всё ещё
копируются из исходной книги: таблица ресиверов не включена в него автоматически.
Второй PDF — отдельная пробная таблица ресиверов. Другие категории модов пока не
преобразуются этим скриптом. Редактирование текста в FlexiPDF и отображение
Unicode-PDF в GitHub на телефоне ещё нужно подтвердить на устройствах пользователя.

В `weapon_mods_table_unicode.py` отдельный маркер `DC` в ячейке эффектов
выводится как встроенная иконка `assets/pdf/damage-icon.png`; ширина иконки
учитывается при переносе строк. Остальные слова остаются текстом, а значок —
отдельным изображением. В рабочих JSON обозначение по-прежнему записывается `DC`.

### Сборка стрелкового раздела с таблицами модов

```powershell
python tools\build_small_guns_book.py ".\Справочник оружия.pdf" --out docs\render\out\small-guns-with-mods.pdf --report docs\render\out\small-guns-report.md
```

Страницы 1–9 копируются из исходной книги. Далее идут сгенерированные таблицы
модов только для оружия с навыком `SMALL_GUNS` из `data/weapons/small-guns-order.json`, затем страница 13
оригинального PDF (разделитель стрелкового оружия), затем страницы оружия без
изображений. Номера страниц на разделителе и оружии пересчитываются.

Таблицы используют рабочие JSON `data/weapon-book/`: берутся все моды из
списков слотов выбранного оружия, в том числе нестандартные категории. Отчёт
указывает пустые данные и непонятные значения; это не гарантия соответствия
правилам книги. Редактирование генерированного PDF вручную нужно выполнять
после последней пересборки, иначе изменения не сохранятся.

### Проверочный фрагмент тяжёлого оружия

```powershell
python tools\weapon_heavy_preview.py ".\Справочник оружия.pdf" --out docs\render\out\heavy-weapons-preview.pdf
```

После стрелкового раздела вставляется оригинальный разделитель. Модификации
20 видов тяжёлого оружия временно копируются векторными блоками из оригинального
PDF, без иллюстраций оружия: характеристики имеют приоритет над несовпадающими
рабочими данными Companion. Это промежуточное решение: блоки не генерируются из
редактируемых JSON. Для гатлинг-плазмы моды помечены как требующие проверки.
Отдельная таблица общих тяжёлых модов временно не формируется до сверки.

Для всего раздела добавьте `--full`; порядок хранится в
`data/weapons/heavy-guns-order.json`.

```powershell
python tools\weapon_heavy_preview.py ".\Справочник оружия.pdf" --full --out docs\render\out\heavy-guns-full.pdf --report docs\render\out\heavy-guns-report.md
python tools\compare_heavy_mods.py
```

Сопоставление оригинала и рабочих данных: `docs/weapon-heavy-mods-comparison.md`.

### Проверочный фрагмент энергетического оружия

```powershell
python tools\weapon_energy_preview.py ".\Справочник оружия.pdf" --out docs\render\out\energy-preview.pdf --report docs\render\out\energy-preview-report.md
```

После полного тяжёлого раздела вставлены две оригинальные страницы общих
таблиц и продолжение с уникальными конденсаторами мушкета из рабочих JSON,
затем оригинальный разделитель и три пробные страницы оружия. Блоки модов
пока взяты из исходного PDF; это не готовые редактируемые JSON. Особенность
лазерного мушкета записана в `data/weapons/energy-specials.ru.json`.
Неполнота таблиц и расхождения перечислены в отчёте.

Для оригинальных 14 видов энергетического оружия добавьте `--full`. Порядок
задаётся в `data/weapons/energy-guns-order.json`; исходные номера страниц
привязаны к ID, а не к текущему порядку. Известные расхождения характеристик
записаны в редактируемый `data/weapons/energy-stat-overrides.json`, дополнительные
особенности — в `data/weapons/energy-specials.ru.json`. Термоядерный магазин
бластера выводится в общей таблице из рабочих JSON; уникальные конденсаторы
головного лазера штурмотрона подробно показаны на странице самого оружия. Остальные расхождения и неопределённые
моды перечислены в отчёте; пистолет института пока не включён.

### Общее правило размещения модификаций

`weapon_mod_policy.py`: если у оружия до восьми модификаций и применимость
мода подтверждена только к нему без конфликтов списков, его характеристики
показываются на странице оружия, с пометкой «УНИКАЛЬНЫЙ», а не в общей таблице.
Условие применения — подробная таблица и описание помещаются без обрезания;
иначе характеристики остаются в общей таблице. При большом числе модификаций
приоритет за читаемостью: названия на странице, характеристики в общей таблице.
Это правило применяется сборщиком стрелкового раздела и для головного лазера
штурмотрона. Остальные блоки, временно скопированные из оригинального PDF,
ещё необходимо перенести в управляемую сборку и проверить на соответствие правилу.

Для абордажного пистолета параметры модификаций с сайта переопределяют
рабочую копию Companion только на его странице: редактируются в
`data/weapons/small-guns-mod-overrides.json`. Дополнительное описание и эффекты
оружия — в `data/weapons/small-guns-card-overrides.json`; сравнение источников —
в `docs/weapon-boarding-comparison.md`. Оригинальная копия Companion не меняется.

### Сверка с сайтом

Сайт fallout-2d20.ru используется как дополнительный источник наряду с PDF и
Companion. Ручная сверка и ссылки — в `docs/weapon-site-comparison.md`; она
пока охватывает только перечисленные страницы. Поправки по сайту для уникальных
конденсаторов мушкета и головного лазера хранятся в
`data/weapons/energy-mod-overrides.json` и не меняют исходные данные Companion.

### Список расхождений и проверка эрраты

Основной список на решение — `docs/weapon-discrepancies.md`. Он различает
оригинальный PDF, сайт, локальные данные Companion, внешние референсы и
проверенные / неподтверждённые сведения об эррате; на его основе данные не
изменяются автоматически. Поправки, уже выбранные для промежуточного PDF,
перечислены там как предварительные.

Рамки на страницах оружия: копируемые векторные таблицы пропорционально
вписываются в поля и получают рамки по границам исходных ячеек
(`weapon_table_borders.py`); генерируемые таблицы также обведены. Общие
справочные таблицы сохранены в прежнем виде по просьбе пользователя.

Оружие ближнего боя из рабочих данных Companion собирается командой
`python3 tools/weapon_melee_preview.py 'Справочник оружия.pdf' --out docs/render/samples/book-melee-original.pdf --report docs/weapon-melee-report.md`.
Порядок и поправки карточек находятся в `data/weapons/melee-original-order.json`
и `data/weapons/melee-card-overrides.json`; первые шесть соответствуют исходнику.

Полный рабочий каталог (143 из 146 ID Companion, три осознанных исключения):
`python3 tools/build_weapon_catalog.py 'Справочник оружия.pdf' --out docs/render/samples/book-weapon-catalog.pdf --report docs/weapon-catalog-report.md`.
Порядок добавленных разделов и поправки — `data/weapons/remaining-order.json` и
`data/weapons/remaining-card-overrides.json`. Приложение с пистолетом института
пока следует за ближним боем; категории и непроверенные правила перечислены в отчёте.

Для ближнего и рукопашного оружия параметры проверенных модов по сайту хранятся
по ID конкретного оружия в `data/weapons/melee-site-mod-overrides.json`,
а категории — в `data/weapons/melee-slot-labels.json`. Непроверенный слот
помечается «НЕ УТОЧНЁН»; полная сверка не завершена. Причины расхождений:
`docs/weapon-melee-site-review.md`.

Предварительный машинный аудит источников: `python3 tools/audit_weapon_sources.py`.
Числовые данные и голоса сохраняются в `data/weapon-audit/numeric-audit.json`,
список разногласий — `docs/weapon-source-numeric-audit.md`. Снимки референсов
зафиксированы по коммиту, веса Pip-Boy 3000 исключены до проверки единиц,
большинство предварительное и не изменяет данные карточек.
