# Образцы PDF

| Файл | Что это |
|---|---|
| `book-weapon-catalog.pdf` | полный русский справочник оружия: 176 страниц (кратно 4 для печати), с печатным оглавлением на страницах 4–5 после разворота PLEASE STAND BY |
| `book-weapon-catalog-en.pdf` | английская версия справочника: 172 страницы (кратно 4), оглавление на страницах 2–3 |
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
| `armor-leather-book.pdf` | тестовая страница «Кожанная броня» в стиле книги оружия: страница 1 — заголовок, картинка, таблицы характеристик по элементам и уровням; страница 2 — таблица модификаций |

`plasma-gun.pdf` собран из Companion JSON (страница 21), остальные карточки —
из `data/weapons/cards/`. Во всех образцах картинка оружия — заглушка `assets/pdf/weapons/combat-rifle.png`
(кроме револьвера, где картинки нет). Описания — английские `flavour` из
компаньона. Шрифт — Carlito, метрический клон Calibri.

Пересобрать:

```bash
python3 tools/weapon2pdf.py data/weapons/cards/10mm-pistol.json \
    --out docs/render/samples/10mm-pistol.pdf
```

Броню:

```bash
python3 tools/armor_book_pdf.py --out docs/render/samples/armor-leather-book.pdf --only leather-armor-book
```
