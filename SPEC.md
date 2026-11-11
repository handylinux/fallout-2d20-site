# Замеры эталона — единственный источник истины

Любая правка вёрстки сверяется с этим файлом, а не с памятью. Все числа сняты
с материалов, которые лежат в репозитории:

- `jos_sppagebuilder.zip` → `jos_sppagebuilder.json` (дамп SPPB: `data[2]['data']`,
  поле `content` — дерево секции, искать по `title`)
- `public/*.html` (сохранённые страницы живого сайта, уже отрендеренные)
- `public/assets/css/*.css` (CSS темы: template, sppagebuilder)

## Оболочка и ширина

| Элемент | Значение | Источник |
|---|---|---|
| `body` | fluid + boxed-обёртка | `public/snaryazhenie/index.html` |
| `.body-innerwrapper` | `max-width: 1240px; margin: 0 auto` (boxed) | `template.css` |
| `#sp-main-body` | 1425, `padding: 0 30px` (контент 1370) | живой сайт |
| контейнер с контентом | 1370, `padding: 0` | живой сайт |
| строка с содержимым | 1370, `padding: 0 25px` (контент 1320) | живой сайт |
| карточка категории | **426.664** = 1320/3 − 13.336 | живой сайт |
| карточка, `padding` | `15px 0` | живой сайт |

Наша реализация: `.site{max-width:1425px;margin:0 auto;padding:0 27.5px}`,
`.tiles-row{padding:0 25px;--bs-gutter-x:13.336px}`, колонка `33.3333%`.

## Хаб «Снаряжение» — SPPB id 269

9 плиток (3×3, `layout: 4+4+4`), порядок: Оружие, Боеприпасы, Броня, Одежда,
Препараты, Еда, Напитки, Книги и журналы, Разное.

| Элемент | Значение |
|---|---|
| колонка | `width: 33.333333%`, `padding: 30px 0 20px`, `border: 1px solid rgb(110,110,110)` |
| фон колонки | `background_type: none`, оверлей `RGBA(203,203,203,0.4)` — без фона не виден |
| ряд | `padding: 25px 0`, `columns_content_alignment: center` |
| заголовок | `<a href><h2 class="sppb-addon-title">`, 36px/36px, 600, `#b15b23` |
| картинка | `<a href><img>`, `padding: 20px 0`, `img{width:200px}` |
| кнопка | `raw_html`, `padding-top: 60px` |
| кнопка `.cta` | `padding:10px 45px`, 20px Poppins, `#000`, `box-shadow:6px 6px 0 gray`, `skewX(-15deg)` |
| hover кнопки | `box-shadow:10px 10px 0 #FBC638` |

Ссылки эталона: Оружие → `/oruzhie`, Броня → `/bronya`, Еда → `/eda`.
У остальных плиток ссылок нет (заголовок/картинка без `<a>`).

## Шапка — SPPB id 101 «Fallout menu»

| Элемент | Значение |
|---|---|
| пункты | 6: Главная, Происхождения, Снаряжение, Перки, Бестиарий, Форум |
| логотип внутри секции | **нет** |
| фон секции | `background_type: none` |
| `section_height` | 100px |
| ряд | `padding: 5px 0`, `columns_content_alignment: center` |
| колонка | `16.666667%` ×6 |
| фон пункта | `contain`, `50% 50%`, `no-repeat`, `images/2025/04/24/menu-item-bg-*.png` |
| порядок текстур | lblue2, orange2, green2, pink, lblue, green |
| padding пункта | `10px 0`; у orange2 снизу 15px; у lblue и green — `15px 0` |
| текст | 16px, 600, uppercase, `#fff`, `text-shadow: 1px 3px 5px #484848` |
| hover | `underline`, `text-decoration-color: currentColor`, `transform: scale(1.05)`, `display: inline-block` |
| `:visited` | цвет остаётся `#fff` |
| лупы/поиска в шапке | **нет** |

## Привычки, которые ломали работу

- Не «додумывать»: числа только из дампа/`public`, иначе спросить.
- Перед правкой CSS открывать нужную секцию дампа целиком, а не по диагонали.
- После правки проверять, что ранее сделанное (плашки, кнопки, сетка) на месте.
