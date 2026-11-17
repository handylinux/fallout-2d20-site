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

* Страницы HTML используют свой набор входных данных. Совместимость модов
  силовой брони для PDF-справочника хранится отдельно в
  `powerArmor_mods.json` и `powerArmor_modCompatibility.json`; если обновить
  эти файлы, PDF покажет подтверждённые моды.
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

# вытащить все картинки оружия из книги Publisher
python3 tools/extract_pdf_images.py "Справочник оружия.pdf" --out art/ \
    --min-size 300
# имена берутся с самой страницы: заголовок «БОЕВОЙ КАРАБИН» → weapon_combat_rifle
# → art/combat-rifle.png (тот же слаг, что у карточки); если заголовок не
# совпал с weapons.json — art/p018.png, а в report.csv пустой weapon_id
# art/index.html — контактный лист; art/report.csv — прежняя короткая таблица
# извлечённых PNG; art/artwork-manifest.json — полный слой размещений.

# сохранить manifest отдельно или выключить его для прежнего короткого flow
python3 tools/extract_pdf_images.py "Справочник оружия.pdf" --out art/ \
    --manifest docs/render/artwork-manifest.json
python3 tools/extract_pdf_images.py "Справочник оружия.pdf" --out art/ --no-manifest
```

`artwork-manifest.json` — воспроизводимый снимок **каждого** вызова изображения
на выбранных страницах, а не только PNG, прошедших фильтр размера. Координаты
даны в исходной PDF-системе (pt, начало внизу слева). Для каждой отрисовки он
хранит `draw_order`, точную affine-матрицу `matrix_pdf`, bbox, весь активный
`clip_paths` и выделенные `crop_paths`, ExtGState (opacity, blend mode и
SMask), а также сведения об image SMask. Поэтому один и тот же embedded asset,
использованный несколько раз, остаётся несколькими placement-записями с
собственными поворотом, skew, масштабом и обрезкой. PNG с SMask сохраняется
RGBA; в `report.csv` его контракт не менялся.

Путь к манифесту можно задать через `--manifest PATH`; без параметра это
`<out>/artwork-manifest.json`. Рядом с исходником записаны SHA-256 и PDF
metadata, чтобы повторная отрисовка могла убедиться, что работает с тем же
экспортом Publisher.

Повторная сборка карточки читает этот слой напрямую: `weapon2pdf.py` выбирает
страницу сначала по `card.id` (`weapon_id` в manifest), затем по `card.page`.
Он рисует все exported placements строго в `draw_order`, применяя исходные
`matrix_pdf`, clipping path, opacity и blend mode; PNG с `/SMask` остаётся
RGBA. Поэтому картинка не вписывается заново в общий `IMAGE_BOX` и не теряет
поворот, skew или частичное появление с соседней страницы.

```bash
# контрольная пересборка страницы 18 с исходным художественным слоем Publisher
python3 tools/weapon2pdf.py data/weapons/cards/combat-rifle.json \
    --out docs/render/out/combat-rifle-manifest.pdf \
    --artwork-manifest art/artwork-manifest.json

# если PNG перенесли в другой каталог или нужно выбрать страницу вручную
python3 tools/weapon2pdf.py data/weapons/cards/combat-rifle.json \
    --out docs/render/out/combat-rifle-manifest.pdf \
    --artwork-manifest art/artwork-manifest.json \
    --artwork-root assets/pdf/weapons --artwork-page 18

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

### Полная русская книга оружия

`tools/build_weapon_catalog.py` соединяет все оружейные разделы в
176-страничную книгу (кратно 4 для печати) с печатным оглавлением на
страницах 4–5. Данные полного каталога находятся в
`data/weapon-book/companion/`, порядок, текстовые и модификационные поправки
— в `data/weapons/`. В отличие от единичной карточки, сборщик принимает
artwork только при точном `weapon_id` в manifest: итоговый номер страницы
никогда не используется как fallback. Поэтому иллюстрация соседа не может
попасть на карточку после вставки оглавления.

```bash
# Создать assets и manifest из ровно того Publisher PDF, который будет source.
python3 tools/extract_pdf_images.py "Справочник оружия.pdf" \
  --out docs/render/pdf-extract/publisher-art --min-size 300

# Полный PDF и небольшой audit-файл, оба предназначены для GitHub.
python3 tools/build_weapon_catalog.py "Справочник оружия.pdf" \
  --out docs/render/samples/book-weapon-catalog.pdf \
  --report docs/render/out/book-weapon-catalog-report.md \
  --artwork-manifest docs/render/pdf-extract/publisher-art/artwork-manifest.json \
  --artwork-root docs/render/pdf-extract/publisher-art \
  --artwork-coverage docs/render/samples/book-weapon-catalog-artwork-coverage.json
```

Сборщик сравнивает SHA-256 source PDF, записанный в manifest, и прекращает
работу при несовпадении, отсутствующем asset или неподдерживаемом graphics
state. Coverage JSON фиксирует точные source page/xref/asset воспроизведённых
layers и явные статусы остальных карточек. Описание правила никогда не
заменяется многоточием: у карточки без таблицы модов уведомление сдвигается
ниже полного текста, а невозможное даже при 10 pt переполнение останавливает
сборку. В актуальном исходнике воспроизводятся artwork layers для 77 карточек;
шесть исходных страниц без экспортируемого raster placement и 60 карточек без
manifest page остаются без заменяющей иллюстрации.

Для viewer, который неправильно отображает отдельные прозрачные PDF-слои,
есть дополнительный полностью растровый файл. Он строится **после** основной
книги: `tools/rasterize_pdf.py` рендерит целую страницу при 200 DPI и кладёт
в результирующий PDF только один непрозрачный RGB JPEG на страницу. Так
сохраняется уже скомпонованная прозрачность artwork, но исчезают текстовые
блоки, шрифты, векторные объекты и отдельные artwork-слои:

```bash
python3 tools/rasterize_pdf.py docs/render/samples/book-weapon-catalog.pdf \
  --out docs/render/samples/book-weapon-catalog-mobile-raster.pdf \
  --dpi 200 --jpeg-quality 85
```

Проверка внутри скрипта требует для каждой страницы ровно один JPEG без
`/SMask` и запрещает шрифты, текст, vector/form XObject и аннотации. Это
резерв для проблемных viewer, не замена основной печатной версии.

Тесты (`tools/test_weapon2pdf.py`) проверяют перенос строк, разбиение
категории на строки по 6 модов, растяжение таблицы до нижнего поля, номер
страницы на внешнем поле и рендер PDF (если установлен PyMuPDF).
`tools/test_rasterize_pdf.py` отдельно фиксирует контракт мобильного PDF: один
непрозрачный JPEG, без текста, векторов и alpha-маски на каждой странице.

---

# Книга брони: PDF по референсу (`tools/armorbook2pdf.py`)

Собирает **одну книгу** по вёрстке пользователя
`docs/render/samples/armor-leather-book.pdf` (2 страницы A4 на сет):

```
Companion JSON  →  tools/armorbook2pdf.py  →  PDF (reportlab, векторный текст)
```

Вёрстка не «на глаз»: геометрия снята из референса через PyMuPDF
(`get_drawings()` для линий и заливок, `get_text("dict")` для кеглей), все
числа вынесены в константы в начале скрипта и проверяются тестами.

## Что на страницах

**Страница 1 — `<НАЗВАНИЕ СЕТА>`**

* заголовок 22 pt Bold + линейка 385.94×2.2 pt (x 128.90…514.84, верх 90.43);
* строка в логике Bootstrap разделена на две равные `col-6`: слева —
  область иллюстрации шириной 50% контента, справа — блок
  «СТАНДАРТНЫЙ КОМПЛЕКТ»;
* правая `col-6` содержит вложенную сетку 2×2: ШЛЕМ / НАГРУДНИК сверху,
  НАРУЧ / ПОНОЖ снизу. Каждая таблица — отдельный прямоугольник: между
  вложенными столбцами 14 pt пустоты, между рядами — 45 pt белого поля.
  Все названия деталей набраны одним Carlito Bold 12 pt; метка — белым на
  чёрном 11 pt, значение — Carlito 11 pt на `#FFEBCD`;
* описание — 12 pt / 17.4 pt, по ширине; длина ограничивается заголовком
  модов, лишнее аккуратно обрезается многоточием (не наезжает на сетку);
* «ПОДДЕРЖИВАЕМЫЕ МОДИФИКАЦИИ» 18 pt Bold + сетка: строки — зоны,
  5 колонок, фон чередуется `#FFEBCD` / `#FFC674`, последняя строка
  «УНИКАЛЬНАЯ». Сетка **прижата к низу листа** (низ 794.20), заголовок идёт
  над ней; если строк много, сетка поднимается, а описание ужимается.

**Страница 2 — `ВАРИАНТЫ`**

* две матрицы тиров рядом (УКРЕПЛЁННАЯ, ТЯЖЁЛАЯ): шапка 20.5 pt — названия
  деталей белым на чёрном, строки по 18.7 pt;
* «УНИКАЛЬНЫЕ МОДИФИКАЦИИ / `<СЕТ>`» 22 pt Bold в две строки;
* таблица уникальных модов: название, ФИЗ./ЭНРГ./РАД. СУ, ВЕС, ЦЕНА, ПЕРКИ,
  ЭФФЕКТЫ. Значения считаются из данных (`statModifiers`, `weightModifier`,
  `costModifier`, `requiredPerk`), эффект — русское описание из i18n.

## Правила, которых нет в референсе (но нужны для всех сетов)

* **Нет детали — нет ничего про неё.** У кожаной брони нет шлема: нет ни
  подписи «ШЛЕМ», ни таблицы, ни строки в сетке модов, ни колонки
  в матрицах тиров.
* Строка «ШЛЕМ» в сетке модов появляется только если у шлема есть моды
  в `armor_mods.json` (сейчас моды есть лишь для тела, рук и ног — значит
  строки «ШЛЕМ» нет даже у металлической брони, где шлем в комплекте есть).
* Перед наборами обычной брони в полной книге печатается «МОДИФИКАЦИИ
  БРОНИ» — общий справочник всех подтверждённых стандартных модов. В нём
  показаны эффект, защищаемая деталь, вес, цена, перк и реальный навык из
  `armor_mods.json`; числовые СУ и правило из i18n объединены в эффекте.
  Поэтому, например, у «Мягкой» явно указано сопротивление взрывному оружию.
* Деталь, закрывающая несколько зон сразу (каркас силовой брони — все
  четыре, «Броня охранника Волт-Тек» — тело/руки/ноги), печатается **один
  раз**.
* Силовая броня: у деталей есть `hp`, поэтому строк 7 — сетка ниже,
  подпись нижнего ряда от этого не налезает на верхнюю таблицу. Между верхним
  и нижним рядами оставлен заметный пустой промежуток, чтобы таблицы не
  сливались визуально.
* У силовой брони краткий список совместимых **общих** систем и обшивок
  остаётся внизу первой страницы модели. Перед моделями печатается единый
  каталог «МОДИФИКАЦИИ СИЛОВОЙ БРОНИ»: он один раз подробно объясняет эффект,
  защищаемую деталь, вес, цену, перк и навык каждого общего мода. Если
  системы переходят на второй лист, таблица обшивки продолжается сразу под
  «СИСТЕМА · ПРОДОЛЖЕНИЕ», а не начинает отдельную пустую страницу.
* Вторая страница модели — «УНИКАЛЬНЫЕ МОДИФИКАЦИИ»: построчно показаны
  реальные улучшения для шлема, нагрудника, наруча и поножа со всеми
  сопротивлениями, ОЗ, весом, ценой и перками. Исключительные система
  рейдеров и обшивка X-01 получают там же отдельную таблицу с эффектом.
  Каркас не получает эту страницу, так как в данных для него нет модов.
  Окраски не печатаются: исходные данные подтверждают только `systeme`,
  `blindage` и `amelioration`.
* В таблицах модификаций перенос возможен только между словами. Слово, не
  помещающееся в ячейку, остаётся целым, а кегль уменьшается лишь для него.
* Один тир (например, «Броня охранника Волт-Тек») — матриц тиров нет,
  страница «ВАРИАНТЫ» печатается только ради уникальных модов.
* Нечего печатать на второй странице — её нет вовсе.
* Одежда печатается по одному предмету: справа — его характеристики,
  снизу — только подтверждённые helper-совместимостью модификации.
  Перед предметами одежды в полной книге добавляется «МОДИФИКАЦИИ ОДЕЖДЫ»:
  общий справочник тканевых основ и подкладок. Он выводит реальные числовые
  эффекты из `uniq_armor_mods.json`, поэтому у каждого Mk баллистического
  плетения явно видны бонусы к ФИЗ. и ЭНРГ. СУ, а также вес, цена, перк и
  навык. При `--no-sections` этот каталог не добавляется к одиночной странице
  вещи.
* Заглушки `lorem ipsum` в описаниях не печатаются: место остаётся пустым,
  чтобы вписать текст в PDF-редакторе.
* Титул книги и подзаголовок — `data/armor-pages/book.json` (это конфиг
  книги, а не сет: `armor2page.py` его пропускает).

## Запуск

```bash
# вся книга: обычная броня + три общих каталога + силовая броня + одежда (62 страницы)
python3 tools/armorbook2pdf.py --out docs/render/samples/armor-book.pdf

# только один сет (2 страницы, без титула и разделов)
python3 tools/armorbook2pdf.py --set leatherArmor --no-cover --no-sections \
    --out /tmp/leather.pdf

# только коллекция
python3 tools/armorbook2pdf.py --collection powerArmor --out /tmp/pa.pdf
```

Состав берётся из данных: `armor.json` (6 сетов), `powerArmor.json`
(6 наборов), `clothes.json` (3 группы: костюмы, обмундирование, головные
уборы). Описания и заголовки — из `data/armor-pages/*.json` (те же файлы,
что у `armor2page.py`), недостающие наборы подписываются из i18n.

## Проверка

```bash
python3 -m unittest tools.test_armorbook2pdf -v
```

Тесты сверяют геометрию с референсом, правила данных (нет шлема — нет
блока), число страниц и тексты готового PDF, отсутствие наложений подписей
на таблицы и обрезанных описаний, налезающих на заголовок.

## Данные

`data/companion/equipment/clothes.json` и
`data/companion/i18n/ru-RU/data/equipment/armor/clothes.json` — копия из
`rpg-companios/Fallout-2d20-companion` (тот же источник, что и остальные
файлы). Обновление: `tools/sync_companion_data.sh /tmp/companion` (теперь
копирует и `clothes.json`).
