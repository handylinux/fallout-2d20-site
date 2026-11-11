# Статическая версия fallout-2d20.ru

Сайт пересобирается из дампов Joomla и SP Page Builder, которые лежат в корне репозитория:

- `jos_content.json` — таблица `jos_content` (441 статья);
- `jos_sppagebuilder.zip` → `jos_sppagebuilder.json` — таблица `jos_sppagebuilder` (366 записей).

Ничего не придумывается вручную: разметка, отступы, типографика, фоны, тени и сетки берутся
из настроек SP Page Builder, каркас — из шаблона Helix Ultimate (Bootstrap 5.3.8).

## Сборка и просмотр

```bash
python3 tools/sitegen/build.py    # страницы из дампов → public/
python3 tools/sitegen/perks.py    # /perki (карточки из статьи «ПЕРКИ») → public/perki/
python3 tools/serve.py            # локальный просмотр public/ на http://localhost:8000
```

## Что где

| путь | назначение |
| --- | --- |
| `tools/sitegen/sppb.py` | рендерер layout'ов SP Page Builder 5: HTML + per-id CSS (секции, колонки, аддоны) |
| `tools/sitegen/build.py` | собирает 6 страниц навигации, шапку с бургером, оффканвас-меню, ссылки |
| `tools/sitegen/perks.py` | карточки перков (живой сайт грузит их из `perks.json`) |
| `src/nav/nav.json` | дерево оффканвас-меню (бургер), 255 пунктов, порядок и вложенность как на сайте |
| `src/nav/urls.json` | 214 адресов сайта: алиас статьи → путь (для переписывания ссылок Joomla) |
| `src/css/` | `template.css` (Helix), `presets-default.css` (пресет шаблона), `sppagebuilder.css` (SPPB 5), `animate.min.css` |
| `src/js/main.js` | оффканвас, аккордеон SPPB, табы SPPB, кнопка «наверх» |
| `src/img/`, `src/vendor/` | исходники картинок и Bootstrap, копируются в `public/assets/` при сборке |
| `public/` | результат сборки (готов к раздаче любым статическим сервером) |

## Страницы этого этапа

`/` (Правила игры), `/proiskhozhdeniya`, `/snaryazhenie`, `/perki`, `/bestiarij`, `/forum` —
шесть разделов верхнего меню. Остальные пункты меню уже присутствуют в бургере и ведут на
свои адреса; их страницы собираются тем же генератором на следующем этапе
(нужны только соответствующие записи дампа — они есть, но контент-страницы пока не включены в сборку).
