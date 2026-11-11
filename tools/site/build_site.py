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
import html
import json
import os
import shutil
import urllib.parse

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
DATA = os.path.join(ROOT, 'data')
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


def card(item, media_pattern=None):
    style = ''
    if media_pattern:
        style = ' style="--f-plate-pattern:url(\'%s\')"' % esc(u(media_pattern))
    img = ''
    media = ''
    name = os.path.basename(item.get('image') or '')
    if name and os.path.exists(os.path.join(SRC, 'img', name)):
        img = ('<img src="%s" alt="%s" loading="lazy" width="300">'
               % (esc(u('/assets/img/' + name)), esc(item.get('alt') or item['title'])))
        media = '<div class="card__media">%s</div>' % img
    else:
        MISSING.add(name)
    body = ('<article class="card%s"%s>'
            '%s'
            '<h2 class="card__title">%s</h2>'
            '<div class="card__text"><p>%s</p></div>'
            '<div class="card__actions">%s</div>'
            '</article>')
    cls = '' if media else ' card--noimg'
    return body % (cls, style, media, esc(item['title']), esc(item.get('text')), cta(item.get('url')))


def cards(items, columns=4):
    cls = 'cards' if columns == 4 else 'cards cards--%d' % columns
    return '<div class="%s">%s</div>' % (cls, ''.join(card(i) for i in items))


# ------------------------------------------------------------------ меню/шапка
def load_nav():
    with open(os.path.join(SRC, 'nav', 'nav.json'), encoding='utf-8') as f:
        return json.load(f)['items']


TOP_MENU = [
    ('Главная', '/'),
    ('Происхождения', '/proiskhozhdeniya/'),
    ('Снаряжение', '/snaryazhenie/'),
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
def page(title, body, active='', nav_items=None):
    logo = u('/assets/img/logos.png')
    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} — Fallout 2D20</title>
<link rel="stylesheet" href="{u('/assets/css/site.css')}">
</head>
<body>
<header class="site-header">
  <div class="container site-header__inner">
    <a class="site-header__logo" href="{u('/')}"><img src="{logo}" alt="Fallout 2D20"></a>
    <nav class="site-header__menu" aria-label="Основное меню">{top_menu(active)}</nav>
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
  <ul>{drawer(nav_items or [])}</ul>
</aside>

<main class="page">
  <div class="container">
{body}
  </div>
</main>

<footer class="site-footer">
  <div class="container">
    <p class="site-footer__text">Fallout 2D20 — настольная ролевая игра по мотивам Fallout от
      Modiphius Entertainment. Неофициальный русскоязычный сайт.</p>
  </div>
</footer>

<script src="{u('/assets/js/site.js')}"></script>
</body>
</html>
"""


# ------------------------------------------------------------------- страницы
def page_origins(nav_items):
    with open(os.path.join(DATA, 'origins.json'), encoding='utf-8') as f:
        data = json.load(f)
    body = ('<h1 class="page__title">%s</h1>\n<p class="page__lead">%s</p>\n%s'
            % (esc(data['title']), esc(data['lead']), cards(data['cards'])))
    return page(data['title'], body, '/proiskhozhdeniya/', nav_items)


STUB_PAGE = """<h1 class="page__title">{title}</h1>
<p class="page__lead">Страница ещё не перенесена в новый каркас.</p>
<p class="page__lead"><a href="{home}">На главную</a></p>
"""


def stub(title, nav_items):
    return page(title, STUB_PAGE.format(title=esc(title), home=u('/')), '', nav_items)


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
    for sub in ('assets/css', 'assets/js', 'assets/img', 'assets/vendor'):
        os.makedirs(os.path.join(OUT, sub), exist_ok=True)

    # статика: свои css/js + картинки и bootstrap из src
    shutil.copy(os.path.join(SRC, 'site', 'css', 'site.css'), os.path.join(OUT, 'assets/css/site.css'))
    shutil.copy(os.path.join(SRC, 'site', 'js', 'site.js'), os.path.join(OUT, 'assets/js/site.js'))
    for root, _d, files in os.walk(os.path.join(SRC, 'img')):
        rel = os.path.relpath(root, os.path.join(SRC, 'img'))
        dst = os.path.join(OUT, 'assets/img') if rel == '.' else os.path.join(OUT, 'assets/img', rel)
        os.makedirs(dst, exist_ok=True)
        for name in files:
            shutil.copy(os.path.join(root, name), os.path.join(dst, name))

    write('index.html', page('Правила игры', '<h1 class="page__title">Правила игры</h1>',
                             '/', nav_items))
    write('proiskhozhdeniya/index.html', page_origins(nav_items))

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
