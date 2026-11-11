#!/usr/bin/env python3
"""
Генератор статики на своём каркасе (без классов SPPB/Helix).

Входные данные — JSON из каталога data/ плюс дерево меню src/nav/nav.json.
Выход — каталог site/ (то, что публикуется на GitHub Pages).

    python3 tools/site/build_site.py            # локально, корень сайта
    BASE=/repo python3 tools/site/build_site.py # с префиксом пути

Страница описывается данными: title, lead, и список блоков. Новые страницы
добавляются записью в PAGES — код рендера трогать не нужно.
"""
import hashlib
import html
import json
import base64
import os
import re
import sys
import shutil
import urllib.parse

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
DATA = os.path.join(ROOT, 'data')
sys.path.insert(0, os.path.join(ROOT, 'tools', 'site'))
import weapons            # noqa: E402
import weapon_pages       # noqa: E402

SRC = os.path.join(ROOT, 'src')
OUT = os.path.join(ROOT, 'site')
BASE = (os.environ.get('BASE') or '').rstrip('/')


def u(url):
    """Внутренний абсолютный адрес → адрес с префиксом BASE."""
    if not BASE or not url.startswith('/') or url.startswith('//'):
        return url
    return BASE + url


def esc(value):
    return html.escape('' if value is None else str(value), quote=True)


# --------------------------------------------------------------------- иконка
ARROW = (
    '<svg class="cta__arrow" width="36" height="23" viewBox="0 0 66 43" aria-hidden="true" '
    'focusable="false"><g fill="#FFFFFF">'
    '<path class="a1" d="M40.15 3.9 43.98.14a.66.66 0 0 1 .7 0l21.01 20.64a1 1 0 0 1 0 1.43L44.68 42.86a.66.66 0 0 1-.7 0l-3.83-3.75a.66.66 0 0 1 0-.71l16.84-16.54a.5.5 0 0 0 0-.71L40.15 4.61a.66.66 0 0 1 0-.71Z"/>'
    '<path class="a2" d="M20.15 3.9 23.98.14a.66.66 0 0 1 .7 0l21.01 20.64a1 1 0 0 1 0 1.43L24.68 42.86a.66.66 0 0 1-.7 0l-3.83-3.75a.66.66 0 0 1 0-.71l16.84-16.54a.5.5 0 0 0 0-.71L20.15 4.61a.66.66 0 0 1 0-.71Z"/>'
    '<path class="a3" d="M.15 3.9 3.98.14a.66.66 0 0 1 .7 0l21.01 20.64a1 1 0 0 1 0 1.43L4.68 42.86a.66.66 0 0 1-.7 0L.15 39.11a.66.66 0 0 1 0-.71l16.84-16.54a.5.5 0 0 0 0-.71L.15 4.61a.66.66 0 0 1 0-.71Z"/>'
    '</g></svg>'
)


def cta(href, label='Подробнее'):
    return ('<a class="cta" href="%s"><span>%s</span>%s</a>'
            % (esc(u(href) if href else '#'), esc(label), ARROW))


# ------------------------------------------------------------------- карточка
MISSING = set()

# фон под аватаром происхождения (из дампа SPPB: images/2025/03/30/bg-fon-3.png)
ORIGIN_BG = '/assets/img/bg-fon-3.png'


def origin_art(url):
    """Файл аватара для происхождения: src/img/origins/<slug>.png.
    Имя берётся из адреса страницы, поэтому достаточно положить файл в папку."""
    slug = (url or '').rstrip('/').rsplit('/', 1)[-1]
    if not slug:
        return None
    for ext in ('.png', '.webp', '.jpg'):
        name = 'origins/' + slug + ext
        if os.path.exists(os.path.join(SRC, 'img', name)):
            return name
    return None


def has_img(path):
    """Файл картинки реально есть в src/img? (иначе не выводим битую иконку)"""
    name = os.path.basename(path or '')
    return bool(name) and (os.path.exists(os.path.join(SRC, 'img', name))
                           or os.path.exists(os.path.join(SRC, 'img', 'origins', name)))


def img_tag(path, alt, cls='', max_width=300):
    if not has_img(path):
        MISSING.add(os.path.basename(path))
        return ''
    rel = path if path.startswith('origins/') else 'origins/' + os.path.basename(path)
    src = rel if os.path.exists(os.path.join(SRC, 'img', rel)) else 'origins/' + os.path.basename(path)
    if not os.path.exists(os.path.join(SRC, 'img', src)):
        src = os.path.basename(path)
    return ('<img%s src="%s" alt="%s" loading="lazy" width="%d">'
            % (' class="%s"' % cls if cls else '', esc(u('/assets/img/' + src)),
               esc(alt), max_width))


def origin_media(item):
    """Левая часть пары: аватар происхождения (по слагу адреса)."""
    art = origin_art(item.get('url')) or item.get('image')
    media = img_tag(art, item.get('alt') or item['title'])
    cls = 'media-cell' + ('' if media else ' media-cell--empty')
    style = (' style="--f-media-bg:url(\'%s\')"' % esc(u(ORIGIN_BG))).replace("'", '&#39;')
    return '<div class="%s"%s>%s</div>' % (cls, style, media)


def origin_plate(item):
    """Правая часть пары: заголовок, описание, шеврон."""
    url = item.get('url') or '#'
    return ('<div class="cell cell--shadow">'
            '<h2 class="cell__title"><a href="%s">%s</a></h2>'
            # ссылки происхождений берутся из данных — BASE добавляем сразу
            '<p class="cell__text">%s</p>'
            '<div class="cell__chevron">%s</div>'
            '</div>' % (esc(u(url)), esc(item['title']), esc(item.get('text')), cta(url)))


def origins_block(items):
    """Строка Bootstrap: 4 колонки по col-3 — аватар, плашка, аватар, плашка."""
    out = []
    for i in range(0, len(items), 2):
        pair = items[i:i + 2]
        cols = ''.join(
            '<div class="col-12 col-sm-6 col-lg-3">%s</div>' % origin_media(it) +
            '<div class="col-12 col-sm-6 col-lg-3">%s</div>' % origin_plate(it)
            for it in pair)
        out.append('<div class="row g-0 origins-row">%s</div>' % cols)
    return ''.join(out)


def tile(title, href, image=None, alt=None):
    """Плитка хаба: 3 строки — заголовок, картинка, шеврон."""
    media = img_tag(image or '', alt or title, max_width=200)
    return (
        '<a class="tile" href="%s">'
        '<h2 class="tile__title">%s</h2>'
        '<div class="tile__media">%s</div>'
        '<div class="tile__arrow">%s</div>'
        '</a>' % (esc(u(href)), esc(title), media, ARROW_SMALL)
    )


def tiles(items):
    """Хаб: 3 колонки (col-lg-4), на планшете 2, на телефоне 1."""
    cols = ''.join(
        '<div class="col-12 col-md-6 col-lg-4">%s</div>' %
        tile(i['title'], i.get('url') or '#', i.get('image'), i.get('alt'))
        for i in items)
    return '<div class="row g-3 tiles-row">%s</div>' % cols


def cell(content, shadow=False):
    return '<div class="cell%s">%s</div>' % (' cell--shadow' if shadow else '', content)


def columns(cells_list, sizes=None):
    """Ряд ячеек на сетке Bootstrap. sizes — список классов ширины на колонку."""
    sizes = sizes or ['col-12 col-md-6 col-lg-4'] * len(cells_list)
    return '<div class="row g-3">%s</div>' % ''.join(
        '<div class="%s">%s</div>' % (sizes[i], c) for i, c in enumerate(cells_list))


ARROW_SMALL = (
    '<svg class="cta__arrow" viewBox="0 0 66 43" aria-hidden="true" focusable="false">'
    '<path class="a1" d="M40.15 3.9 43.98.14a.66.66 0 0 1 .7 0l21.01 20.64a1 1 0 0 1 0 1.43'
    'L44.68 42.86a.66.66 0 0 1-.7 0l-3.83-3.75a.66.66 0 0 1 0-.71l16.84-16.54a.5.5 0 0 0 0-.71'
    'L40.15 4.61a.66.66 0 0 1 0-.71Z"/>'
    '<path class="a2" d="M20.15 3.9 23.98.14a.66.66 0 0 1 .7 0l21.01 20.64a1 1 0 0 1 0 1.43'
    'L24.68 42.86a.66.66 0 0 1-.7 0l-3.83-3.75a.66.66 0 0 1 0-.71l16.84-16.54a.5.5 0 0 0 0-.71'
    'L20.15 4.61a.66.66 0 0 1 0-.71Z"/>'
    '</svg>'
)



# ------------------------------------------------------- таблица на div (data)
def dtable(headers, rows, wide=None):
    """Таблица на div. wide=None — считается по числу столбцов (>3 → вертикальная
    сетка 2×N на мобильном). Подписи ячеек выводятся из заголовков (data-label)."""
    cols = max(len(headers), max((len(r) for r in rows), default=0))
    wide = (cols > 3) if wide is None else wide
    cls = 'dtable' + (' dtable--wide' if wide else '')
    out = ['<div class="%s" style="--cols:%d">' % (cls, cols)]
    if headers:
        out.append('<div class="dtable__row dtable__row--head">%s</div>' % ''.join(
            '<div class="dtable__cell">%s</div>' % esc(h) for h in headers))
    for row in rows:
        cells = []
        for i, cell in enumerate(row):
            label = headers[i] if i < len(headers) else ''
            cells.append('<div class="dtable__cell">%s%s</div>' % (
                '<span class="dtable__label">%s</span>' % esc(label) if label else '',
                cell if isinstance(cell, str) and cell.startswith('<') else esc(cell)))
        out.append('<div class="dtable__row">%s</div>' % ''.join(cells))
    out.append('</div>')
    return ''.join(out)


def spoiler(title, body, open_=False):
    return ('<details class="spoiler"%s><summary class="spoiler__summary">%s</summary>'
            '<div class="spoiler__body">%s</div></details>'
            % (' open' if open_ else '', esc(title), body))


# ------------------------------------------------------------------ меню/шапка
def load_nav():
    with open(os.path.join(SRC, 'nav', 'nav.json'), encoding='utf-8') as f:
        return json.load(f)['items']


TOP_MENU = [
    ('Главная', '/'),
    ('Происхождения', '/proiskhozhdeniya/'),
    ('Снаряжение', '/snaryazhenie/'),
    ('Оружие', '/snaryazhenie/oruzhie/'),
    ('Перки', '/perki/'),
    ('Бестиарий', '/bestiarij/'),
    ('Форум', '/forum/'),
]


def top_menu(active=''):
    out = []
    for title, href in TOP_MENU:
        cls = ' class="is-active"' if href == active else ''
        out.append('<li%s><a href="%s">%s</a></li>' % (cls, esc(u(href)), esc(title)))
    return '<ul class="top-menu">%s</ul>' % ''.join(out)


def drawer_node(item):
    children = item.get('children') or []
    title = esc(item.get('title'))
    href = esc(u(item.get('url') or '#'))
    if not children:
        return '<li><a href="%s">%s</a></li>' % (href, title)
    return ('<li><a href="%s">%s</a>'
            '<button class="drawer__toggle" type="button" aria-expanded="false">'
            '<span class="visually-hidden">Раскрыть «%s»</span></button>'
            '<ul class="drawer__sub">%s</ul></li>'
            % (href, title, title, ''.join(drawer_node(c) for c in children)))


def drawer(items):
    return ''.join(drawer_node(i) for i in items)


# --------------------------------------------------------------------- каркас
BG_URI = None


def bg_data_uri():
    """Фон сайта как data URI: файл bg-main.jpg на самом деле WebP,
    и как обычный url() браузер его не рисует (неверный MIME)."""
    global BG_URI
    if BG_URI is None:
        path = os.path.join(SRC, 'img', 'bg-main.jpg')
        data = open(path, 'rb').read()
        BG_URI = 'data:image/webp;base64,' + base64.b64encode(data).decode()
    return BG_URI


def read_css():
    with open(os.path.join(SRC, 'site', 'css', 'site.css'), encoding='utf-8') as f:
        css = f.read()
    # в инлайновом CSS абсолютные пути к картинкам тоже получают префикс
    return css.replace('__BG_DATA_URI__', bg_data_uri()).replace('url("/assets/', 'url("%s/assets/' % BASE)


SEARCH_BOX = ('<div class="site-search">'
             '<button class="site-search__btn" type="button" id="search-open" '
             'aria-label="Поиск по сайту" aria-expanded="false">'
             '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5" '
             'fill="none" stroke="currentColor" stroke-width="2.2"/>'
             '<path d="M15.4 15.4 21 21" fill="none" stroke="currentColor" stroke-width="2.2" '
             'stroke-linecap="round"/></svg></button>'
             '<div class="site-search__panel" id="search-panel" hidden>'
             '<input class="site-search__input" type="search" id="search-input" '
             'placeholder="Оружие, моды, навык…" autocomplete="off" '
             'aria-label="Поиск по оружию и модам">'
             '<div class="site-search__results" id="search-results" role="listbox"></div>'
             '</div></div>')


def search_box():
    return SEARCH_BOX


def read_css_raw():
    with open(os.path.join(SRC, 'site', 'css', 'site.css'), encoding='utf-8') as f:
        return f.read()


ASSET_VER = hashlib.sha1(read_css_raw().encode('utf-8')).hexdigest()[:8]


def page(title, body, active='', nav_items=None, search_data=None):
    logo = u('/assets/img/logos.png')
    if BASE:
        # все внутренние абсолютные ссылки получают префикс BASE (GitHub Pages)
        body = re.sub(r'href="/(?!%s)(?!/)' % re.escape(BASE.lstrip('/')),
                      'href="%s/' % BASE, body)
    styles = read_css()
    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} — Fallout 2D20</title>
<link rel="stylesheet" href="{u('/assets/vendor/bootstrap.min.css')}">
<style>{styles}</style>
</head>
<body data-base="{BASE}">
<div class="site">
<header class="site-header">
  <div class="wrap site-header__inner">
    <a class="site-header__logo" href="{u('/')}"><img src="{logo}" alt="Fallout 2D20"></a>
    <nav class="site-header__menu" aria-label="Основное меню">{top_menu(active)}</nav>
    {search_box()}
    <button class="burger" type="button" aria-label="Открыть меню" aria-controls="drawer">
      <span></span><span></span><span></span>
    </button>
  </div>
</header>

<div class="drawer-backdrop" data-drawer-close></div>
<aside class="drawer" id="drawer" aria-hidden="true">
  <div class="drawer__head">
    <a class="drawer__logo" href="{u('/')}"><img src="{logo}" alt="Fallout 2D20"></a>
    <button class="drawer__close" type="button" aria-label="Закрыть меню" data-drawer-close>
      <span></span><span></span>
    </button>
  </div>
  <ul>{drawer(globals().get('NAV_ITEMS') or nav_items or [])}</ul>
</aside>

<main class="page">
  <div class="wrap">
{body}
  </div>
</main>

<footer class="site-footer">
  <div class="wrap">
    <p class="site-footer__text">Fallout 2D20 — настольная ролевая игра по мотивам Fallout от
      Modiphius Entertainment. Неофициальный русскоязычный сайт.</p>
  </div>
</footer>
</div><!-- /.site -->

<script src="{u('/assets/vendor/bootstrap.bundle.min.js')}"></script>
<script src="{u('/assets/js/search.js')}"></script>
<script src="{u('/assets/js/site.js')}?v={ASSET_VER}"></script>
</body>
</html>
"""


# ------------------------------------------------------------------- страницы
def page_origins(nav_items):
    with open(os.path.join(DATA, 'origins.json'), encoding='utf-8') as f:
        data = json.load(f)
    body = ('<h1 class="page__title">%s</h1>\n<p class="page__lead">%s</p>\n%s'
            % (esc(data['title']), esc(data['lead']), origins_block(data['cards'])))
    return page(data['title'], body, '/proiskhozhdeniya/', nav_items)


STUB_PAGE = """<h1 class="page__title">{title}</h1>
<p class="page__lead">Страница ещё не перенесена в новый каркас.</p>
<p class="page__lead"><a href="{home}">На главную</a></p>
"""


def stub(title, nav_items):
    return page(title, STUB_PAGE.format(title=esc(title), home=u('/')), '', nav_items)


PERKS_HUB = [
    {'title': 'Все перки', 'url': '/perki26/'},
    {'title': 'Перки по атрибутам', 'url': '/perki26/'},
    {'title': 'Требования и ранги', 'url': '/perki26/'},
]


ORIGINS_STUB = """<p class="wcard__back"><a href="/proiskhozhdeniya/">Назад к происхождениям</a></p>
<h1 class="page__title">{title}</h1>
<div class="wcard"><div class="wcard__row">
  <div class="wcard__media">{art}</div>
  <div class="wcard__stats"><p class="page__lead">{text}</p></div>
</div></div>
"""


def with_weapon_nav(nav_items, cats):
    """Подменяет ветку меню «Оружие» списком из json: категория → оружие."""
    children = [{
        'title': title,
        'url': '/snaryazhenie/oruzhie/%s/' % cat_slug,
        'children': [{'title': it['name'],
                      'url': '/snaryazhenie/oruzhie/%s/%s/' % (cat_slug, it['slug'])}
                     for it in group],
    } for cat_slug, title, group in cats]
    branch = {'title': 'Оружие', 'url': '/snaryazhenie/oruzhie/', 'children': children}

    def walk(items):
        out = []
        for item in items:
            if (item.get('title') or '').lower() == 'оружие':
                out.append(branch)
            else:
                out.append(dict(item, children=walk(item.get('children') or [])))
        return out

    return walk(nav_items)


def write_origin_pages(nav_items):
    """Страница на каждое происхождение из data/origins.json + пункты меню.

    Иначе карточка происхождения ведёт в 404. Текст черновой — из данных.
    """
    with open(os.path.join(DATA, 'origins.json'), encoding='utf-8') as f:
        cards = json.load(f)['cards']
    seen = set()
    for card in cards:
        url = (card.get('url') or '').rstrip('/')
        if not url or url in seen:
            continue
        seen.add(url)
        slug = url.rsplit('/', 1)[-1]
        art = origin_art(url) or card.get('image') or ''
        media = img_tag(art, card.get('alt') or card['title']) if art else ''
        body = ORIGINS_STUB.format(
            title=esc(card['title']),
            art=media or '<div class="media-cell media-cell--empty"></div>',
            text=esc(card.get('text') or ''))
        write('proiskhozhdeniya/%s/index.html' % slug,
              page(card['title'], body, '/proiskhozhdeniya/', nav_items))


def page_perks(nav_items):
    body = ('<h1 class="page__title">Перки</h1>'
            '<p class="page__lead">Карточки перков с фильтром по атрибутам — '
            'на странице <a href="%s">Перки 2026</a>.</p>%s'
            % (u('/perki26/'), tiles(PERKS_HUB)))
    return page('Перки', body, '/perki/', nav_items)



def page_layout(nav_items):
    """Страница-эталон: все типы блоков каркаса рядом, для сверки глазами."""
    sample = {'title': 'Пример', 'text': 'Короткое описание в одну-две строки.',
              'image': '', 'url': '#'}
    parts = ['<h1 class="page__title">Эталон раскладки</h1>']

    parts.append('<h2>1. Одна строка происхождений: 4 элемента (col-3 × 4)</h2>')
    parts.append(origins_block([sample, sample]))

    parts.append('<h2>2. Два столбца: слева картинка, справа текст</h2>')
    parts.append(columns([origin_media(sample), cell('<p>Текст справа от картинки.</p>')],
                         ['col-12 col-md-5', 'col-12 col-md-7']))

    parts.append('<h2>3. Три столбца (ячейки, col-lg-4)</h2>')
    parts.append(columns([cell('<p>Ячейка %d</p>' % i) for i in (1, 2, 3)]))

    parts.append('<h2>4. Четыре столбца (col-lg-3)</h2>')
    parts.append(columns([cell('<p>Колонка %d</p>' % i) for i in (1, 2, 3, 4)],
                         ['col-12 col-sm-6 col-lg-3'] * 4))

    parts.append('<h2>5. Хаб из плиток: 3 столбца</h2>')
    parts.append(tiles([{'title': 'Оружие', 'url': '#'},
                        {'title': 'Броня', 'url': '#'},
                        {'title': 'Еда', 'url': '#'}]))

    parts.append('<h2>6. Таблица на div: 4 столбца → 2×N на мобильном</h2>')
    parts.append(dtable(['Оружие', 'Урон', 'Вес', 'Цена'],
                        [['10-мм пистолет', '1DC', '1', '100'],
                         ['Лазерный пистолет', '2DC', '2', '120']]))

    parts.append('<h2>7. Вложенный спойлер</h2>')
    parts.append(spoiler('Внешний спойлер',
                         spoiler('Внутренний спойлер', '<p>Текст внутри.</p>') +
                         '<p>Текст на уровне внешнего.</p>', open_=True))

    return page('Эталон раскладки', '\n'.join(parts), '', nav_items)


def write(path, content):
    full = os.path.join(OUT, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, 'w', encoding='utf-8') as f:
        f.write(content)
    return full


def main():
    nav_items = load_nav()
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    for sub in ('assets/css', 'assets/js', 'assets/img', 'assets/img/origins', 'assets/vendor'):
        os.makedirs(os.path.join(OUT, sub), exist_ok=True)

    # статика: свои css/js + картинки и bootstrap из src
    # css отдаём уже обработанным: фон вшит data URI, пути к картинкам с BASE
    with open(os.path.join(OUT, 'assets/css/site.css'), 'w', encoding='utf-8') as f:
        f.write(read_css())
    shutil.copy(os.path.join(SRC, 'site', 'js', 'site.js'), os.path.join(OUT, 'assets/js/site.js'))
    for name in ('search.js', 'router.js'):
        shutil.copy(os.path.join(SRC, 'site', 'js', name), os.path.join(OUT, 'assets/js', name))
    # типы страниц: views/*.js — каждый тип в своём файле
    views_out = os.path.join(OUT, 'assets/js/views')
    os.makedirs(views_out, exist_ok=True)
    views_src = os.path.join(SRC, 'site', 'js', 'views')
    for name in sorted(os.listdir(views_src)):
        if name.endswith('.js'):
            shutil.copy(os.path.join(views_src, name), os.path.join(views_out, name))
    for name in ('bootstrap.min.css', 'bootstrap.bundle.min.js'):
        src = os.path.join(SRC, 'vendor', name)
        if os.path.exists(src):
            shutil.copy(src, os.path.join(OUT, 'assets/vendor', name))
    for root, _d, files in os.walk(os.path.join(SRC, 'img')):
        rel = os.path.relpath(root, os.path.join(SRC, 'img'))
        dst = os.path.join(OUT, 'assets/img') if rel == '.' else os.path.join(OUT, 'assets/img', rel)
        os.makedirs(dst, exist_ok=True)
        for name in files:
            shutil.copy(os.path.join(root, name), os.path.join(dst, name))


    # заглушки для всех пунктов меню, чтобы ссылки не давали 404
    titles = {}
    def walk(items):
        for it in items:
            url = (it.get('url') or '').strip()
            if url.startswith('/') and url != '/':
                titles.setdefault(url.rstrip('/'), it.get('title') or url)
            walk(it.get('children') or [])
    walk(nav_items)
    for _title, href in TOP_MENU:
        if href != '/':
            titles.setdefault(href.rstrip('/'), _title)
    stubs = 0
    for url, title in titles.items():
        rel = url.strip('/')
        target = os.path.join(OUT, rel, 'index.html')
        if os.path.exists(target):
            continue
        write(os.path.join(rel, 'index.html'), stub(title, nav_items))
        stubs += 1

    open(os.path.join(OUT, '.nojekyll'), 'w').close()
    print('заглушек:', stubs)
    if MISSING:
        print('без картинки (файла нет):', len(MISSING))
    print('готово: site/ — страниц:', len([1 for _r, _d, fs in os.walk(OUT) for f in fs if f == 'index.html']))


if __name__ == '__main__':
    main()
