# Образцы PDF

| Файл | Что это |
|---|---|
| `book-weapon-catalog.pdf` | основной полный русский справочник оружия: 176 страниц (кратно 4 для печати), печатное оглавление на стр. 4–5 после разворота PLEASE STAND BY, 143 оружейные карточки. Artwork Publisher воспроизведён для 77 карточек по manifest с исходными matrix/crop/alpha; чужие иллюстрации не подставляются. |
| `book-weapon-catalog-mobile-raster.pdf` | дополнительная мобильная версия тех же 176 страниц. После корректной сборки основной книги каждая целая страница отрендерена в один RGB JPEG 200 DPI: нет текстовых блоков, шрифтов, векторных объектов, alpha-масок и отдельных слоёв оружия. Это **не** замена прозрачных PNG оружия: их прозрачность сначала правильно скомпонована с фоном страницы. Выбирайте этот файл только для viewer, который неправильно композитит слои; в нём нельзя искать/выделять текст, а качество печати ниже, чем у основной версии. |
| `book-weapon-catalog-artwork-coverage.json` | проверяемая карта artwork для основной книги: исходный SHA-256, source page, xref и placement 77 карточек с воспроизведённым artwork, а также явные причины отсутствия art у остальных карточек. |
| `book-weapon-catalog-en.pdf` | полный английский справочник: 146 оружейных карточек и иерархические PDF bookmarks по категориям. Для 77 карточек повторены те же exact Publisher artwork layers, что и в русской книге; неподтверждённые изображения не подставляются. |
| `book-weapon-catalog-en-mobile-raster.pdf` | дополнительная mobile-совместимая английская версия тех же 146 страниц: каждая страница — один непрозрачный RGB JPEG после полного рендеринга векторной страницы. |
| `book-weapon-catalog-en-artwork-coverage.json` | audit exact-ID artwork для английской книги: 77 replayed, 6 известных исходных страниц без recoverable exported artwork и 63 карточки без manifest page. |
| `sample-3.pdf` | три страницы подряд: 10-мм пистолет (лёгкое), Гатлинг (тяжёлое), Криолятор (энерго) |
| `sample-3.png` | те же три страницы одним листом для быстрого просмотра |
| `10mm-pistol.pdf`, `gatling-gun.pdf`, `cryolator.pdf` | те же страницы по отдельности |
| `effects.pdf`, `effects.png` | четыре страницы про эффекты: Револьвер .44 («Порочный»), Боевой дробовик («Разброс»), Карабин Теслы («Дуга»), Толстяк (три эффекта сразу) |
| `missile-launcher.pdf` | «Ракетная установка» — 7 строк описания целиком (раньше обрезалось) |
| `baseball-bat.pdf` | «Бейсбольная бита» — уникальные моды (слот «УНИКАЛЬНЫЙ», 5 штук) |
| `combat-rifle.pdf` | страница 18, собранная из Companion JSON — для сравнения с Publisher-оригиналом |
| `plasma-gun.pdf` | «Плазменный пистолет» — энергооружие со своей категорией «КОНДЕНСАТОР» |
| `revolver-44.pdf` | «Револьвер калибра .44» без картинки (карточка из `data/weapons/cards/`) |
| `combat-shotgun.pdf`, `tesla-rifle.pdf`, `fat-man.pdf` | те же страницы по отдельности |
| `weapons-manifest-ru-preview.pdf` | контрольный 10-страничный набор оружейных карточек: таблицы/заголовки на русском, а иллюстрации вставлены по `artwork-manifest.json` с исходными affine-матрицами, crop и alpha из Publisher. Не включает «Бейсбольную биту»: для неё нет корректного соответствия source-page → artwork. |

`plasma-gun.pdf` собран из Companion JSON (страница 21), остальные карточки —
из `data/weapons/cards/`. Во всех образцах картинка оружия — заглушка `assets/pdf/weapons/combat-rifle.png`
(кроме револьвера, где картинки нет). Описания — английские `flavour` из
компаньона. Шрифт — Carlito, метрический клон Calibri.

Пересобрать:

```bash
python3 tools/weapon2pdf.py data/weapons/cards/10mm-pistol.json \
    --out docs/render/samples/10mm-pistol.pdf
```

### Полная книга оружия

Полная книга использует отдельную рабочую копию данных Companion в
`data/weapon-book/`, порядок и проверенные поправки в `data/weapons/` и
исходный Publisher PDF. Сначала надо извлечь artwork из **того же** исходного
PDF: сборщик сверяет SHA-256, поэтому не сможет незаметно смешать другой
экспорт и старый manifest.

```bash
python3 tools/extract_pdf_images.py "Справочник оружия.pdf" \
  --out docs/render/pdf-extract/publisher-art --min-size 300

python3 tools/build_weapon_catalog.py "Справочник оружия.pdf" \
  --out docs/render/samples/book-weapon-catalog.pdf \
  --report docs/render/out/book-weapon-catalog-report.md \
  --artwork-manifest docs/render/pdf-extract/publisher-art/artwork-manifest.json \
  --artwork-root docs/render/pdf-extract/publisher-art \
  --artwork-coverage docs/render/samples/book-weapon-catalog-artwork-coverage.json
```

Вторая команда делает холст, таблицы и текст из JSON, но для карточки берёт
рисунок только при точном `weapon_id` в manifest. Позиция в готовой книге не
используется как fallback: это исключает заимствование art соседнего оружия
после вставки оглавления. При извлечении порог 300 px относится к большей
native-стороне изображения; для узких artwork дополнительно нужна площадь
placement не менее 5% страницы, поэтому крупные горизонтальные рисунки
сохраняются, а тонкие декоративные полосы не попадают в manifest. Описание
оружия печатается целиком: если у карточки нет таблицы модов, уведомление о её
отсутствии сдвигается ниже текста, а переполнение, которое нельзя решить
кеглем до 10 pt, завершает сборку с ошибкой вместо многоточия. В текущем
исходнике 77 карточек имеют экспортируемый Publisher artwork; у шести
исходных страниц artwork не является экспортируемым растровым placement, а у
60 добавленных/неидентифицированных карточек в исходнике соответствующего
слоя нет. Все 66 таких случаев явно записаны в coverage JSON, без подстановки
другого изображения.

Если конкретный мобильный PDF viewer ошибочно отображает отдельные
прозрачные слои, соберите **только дополнительную** растровую версию из уже
проверенной основной книги:

```bash
python3 tools/rasterize_pdf.py docs/render/samples/book-weapon-catalog.pdf \
  --out docs/render/samples/book-weapon-catalog-mobile-raster.pdf \
  --dpi 200 --jpeg-quality 85
```

Скрипт сначала рендерит страницу целиком, а затем кладёт в новый PDF ровно
один непрозрачный RGB JPEG на страницу. Поэтому все прозрачные PNG оружия и
их Publisher matrix/crop уже применены к фону до растеризации, но в резервном
файле отсутствуют выбор текста, шрифты, векторные объекты и самостоятельные
слои. Перед публикацией скрипт проверяет это свойство у каждой страницы.

### English weapon catalogue

Английский каталог строится из checked-in English Companion localisation и
тех же числовых правил `data/weapon-book/companion/`, но не использует
статические изображения из `art/`, другой ветки или соседних страниц. У
каждой из 146 карточек есть English title, subtitles, stat headers, mod
labels and description; PDF outline группирует их по восьми категориям.

Artwork допускается только по точному совпадению `weapon_id` с manifest,
извлечённым из данного `Справочник оружия.pdf` (SHA-256
`48c85e12c5eca695e0c4a4fc3a8bf9276d4fb1d1715b6a62f4b0f9c26ffdbd35`). Для
каждого из 77 доступных слоёв сохраняются matrix, crop/clip, rotation,
alpha и draw order. Нет fallback по конечному номеру страницы, source-page
или названию. Шесть source pages без recoverable exported artwork — `Sword`,
`Combat Knife`, `Machete`, `Ripper`, `Switchblade` и `Shishkebab` — остаются
без substitute illustration и явно записаны в English coverage. Ещё 63
добавленные/непредставленные в исходнике карточки имеют статус
`no-manifest-page`.

```bash
# Exact Publisher extraction; this ignored working directory is not published.
python3 tools/extract_pdf_images.py "Справочник оружия.pdf" \
  --out docs/render/pdf-extract/publisher-art --min-size 300

# Canonical English vector catalogue and its compact provenance audit.
python3 tools/build_weapon_catalog_en.py "Справочник оружия.pdf" \
  --out docs/render/samples/book-weapon-catalog-en.pdf \
  --artwork-manifest docs/render/pdf-extract/publisher-art/artwork-manifest.json \
  --artwork-root docs/render/pdf-extract/publisher-art \
  --artwork-coverage docs/render/samples/book-weapon-catalog-en-artwork-coverage.json

# Optional viewer-compatibility edition, made only from the verified vector PDF.
python3 tools/rasterize_pdf.py docs/render/samples/book-weapon-catalog-en.pdf \
  --out docs/render/samples/book-weapon-catalog-en-mobile-raster.pdf \
  --dpi 200 --jpeg-quality 85 --metadata-locale en
```

## Книга брони

| Файл | Что это |
|---|---|
| `armor-leather-book.pdf` | референс пользователя: кожаная броня, 2 страницы (снята геометрия) |
| `armor-book.pdf` | русская книга, собранная `tools/armorbook2pdf.py`: 62 страницы — общий каталог модов обычной брони (1 страница), броня (6 сетов), общий каталог модов силовой брони (2 страницы), силовая броня (6 наборов и 5 страниц уникальных модификаций), общий каталог модов одежды (1 страница), одежда (32 отдельных предмета) |
| `armor-book-en.pdf` | та же 62-страничная книга на английском: локализованы названия предметов, модов и эффектов, заголовки, характеристики, требования, каталоги и вводный текст кожаной брони |

У обычной брони первая страница сета содержит «Стандартный комплект» и
«Поддерживаемые модификации», а вторая — варианты
(укреплённая/тяжёлая) и уникальные модификации. В стандартном комплекте
строка делится пополам: левая половина зарезервирована для иллюстрации,
правая содержит вложенные таблицы четырёх деталей. Они разнесены пустым
пространством по обеим осям: 14 pt между столбцами и 45 pt между рядами.
Перед наборами расположен общий справочник стандартных модов: эффект,
деталь, вес, цена, перк и навык, поэтому назначение «Мягкой» и других
подкладок не теряется в коротком списке совместимости. Перед моделями
силовой брони расположен общий
справочник: он один раз объясняет эффект, деталь, вес, цену, перк и навык
систем и обшивок. На странице продолжения систем обшивка идёт сразу следом
в той же секции.
На первой странице конкретной модели остаётся короткий список её общих
модификаций. На второй показываются только уникальные улучшения шлема,
нагрудника, наруча и поножа с полными характеристиками; исключительные
система рейдеров и обшивка X-01 там же получают подробную таблицу эффекта.
Каркас не получает вторую страницу: в исходных данных для него нет модов.
Окраски не показаны, потому что источник данных подтверждает только
системы, обшивку и улучшения. Перед предметами одежды расположен общий
справочник тканевых основ и подкладок: в нём у каждого Mk баллистического
плетения явно показаны бонусы к ФИЗ. и ЭНРГ. СУ, вес, цена, перк и навык.
Одежда развёрстана по одному предмету на страницу; блок модов печатается
только для предметов, для которых совместимость известна.

```bash
# Русская версия (локаль по умолчанию)
python3 tools/armorbook2pdf.py --out docs/render/samples/armor-book.pdf

# Английская версия
python3 tools/armorbook2pdf.py --locale en-EN --out docs/render/samples/armor-book-en.pdf
```

Источником совместимости модов силовой брони и одежды служит
`handylinux/Fallout-2d20-helper`. После обновления его данных пересоберите
соответствующие JSON-файлы, затем книгу:

```bash
python3 tools/powerarmor_mods_from_helper.py /путь/к/Fallout-2d20-helper
python3 tools/clothes_mods_from_helper.py /путь/к/Fallout-2d20-helper
python3 tools/armorbook2pdf.py --out docs/render/samples/armor-book.pdf
```
