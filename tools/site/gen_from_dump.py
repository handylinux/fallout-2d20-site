#!/usr/bin/env python3
"""Сборка страниц прямо из выгрузок Joomla: SPPB-дамп + jos_content.

Ничего не сочиняется: дерево SPPB рендерится как есть (см. sppb_render.py),
тексты статей берутся из jos_content, адреса — из сохранённых живых страниц
`public/` (там же лежит карта заголовок → URL).

Запуск: BASE=/fallout-2d20-site python3 tools/site/gen_from_dump.py
"""
import html
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sppb_render as R  # noqa: E402

DOCS = 'docs'
BASE = os.environ.get('BASE', '')
SPPB = '/tmp/sppb/jos_sppagebuilder.json'
CONTENT = 'jos_content.json'


def esc(s):
    return html.escape(s or '', quote=True)


def load():
    dump = json.load(open(SPPB, encoding='utf-8'))
    sp = {r['id']: r for r in dump[2]['data']}
    cnt = json.load(open(CONTENT, encoding='utf-8'))
    articles = {r['id']: r for r in cnt[2]['data']}
    return sp, articles


# ------------------------------------------------------------------ URL из живых
def url_map():
    """Заголовок (lower) → путь на сайте, по сохранённым страницам public/."""
    out = {}
    for root, _dirs, files in os.walk('public'):
        if 'index.html' not in files:
            continue
        path = os.path.relpath(root, 'public')
        url = '/' if path == '.' else '/' + path.replace(os.sep, '/') + '/'
        html_src = open(os.path.join(root, 'index.html'), encoding='utf-8', errors='ignore').read()
        m = re.search(r'<title>([^<]*)</title>', html_src)
        if m:
            out.setdefault(m.group(1).split(' - ')[0].strip().lower(), url)
        m = re.search(r'<h1[^>]*>(.*?)</h1>', html_src, re.S)
        if m:
            out.setdefault(re.sub(r'<[^>]+>', '', m.group(1)).strip().lower(), url)
    return out


def url_for(title, umap, fallback=None):
    key = (title or '').strip().lower()
    if key in umap:
        return umap[key]
    return fallback


# ------------------------------------------------------------------ главная
HOME_SECTIONS = []  # заполняется из живой страницы: h2 + ссылки внутри


def build_home(articles, umap):
    """Главная = статья «Правила игры»: 9 блоков со ссылками, как на живом сайте."""
    art = None
    for r in articles.values():
        if r.get('alias') == 'pravila-igry' and r.get('state') == '1':
            art = r
            break
    if not art:
        return ''
    body = art.get('fulltext') or art.get('introtext') or ''
    # на живом сайте текст статьи разложен по 3-колоночной сетке;
    # берём ссылки в порядке дампа и собираем те же блоки
    secs = re.findall(r'<h2[^>]*>(.*?)</h2>\s*<div[^>]*>(.*?)</div>', body, re.S)
    if not secs:
        # текст без разметки: режем по заголовкам из живого рендера
        return R.clean_html(body)
    out = []
    for title, chunk in secs:
        out.append('<div class="home-cell"><h2 class="home-cell__title">%s</h2>'
                   '<div class="home-cell__body">%s</div></div>'
                   % (re.sub(r'<[^>]+>', '', title).strip(), R.clean_html(chunk)))
    return '<div class="home-grid">%s</div>' % ''.join(out)


def home_from_live():
    """Блоки главной — прямо из разметки живой страницы public/index.html.

    На главной несколько SPPB-секций подряд (по 3 колонки в каждой), поэтому
    идём по всем section-id и собираем колонки с заголовком + списком ссылок.
    """
    src = open('public/index.html', encoding='utf-8', errors='ignore').read()
    marks = [m.start() for m in re.finditer(r'<section id="section-id-', src)]
    if not marks:
        return ''
    marks.append(src.find('<section id="sp-footer"') if '<section id="sp-footer"' in src else len(src))
    seg = ''.join(src[marks[i]:marks[i + 1]] for i in range(len(marks) - 1))
    # граница контента главной: от первой секции до конца последней
    if '<section id="sp-footer"' in src:
        seg = src[marks[0]:src.find('<section id="sp-footer"')]
    parts = []
    # Разбиваем по колонкам SPPB и берём заголовок + список внутри колонки.
    chunks = re.split(r'<div id="column-wrap-id-', seg)[1:]
    for col in chunks:
        h = re.search(r'<h2 class="sppb-addon-title">(.*?)</h2>', col, re.S)
        if not h:
            continue
        title = re.sub(r'<[^>]+>', '', h.group(1)).strip()
        body = col[h.end():]
        # ссылки/пункты только до следующей колонки
        ul = re.search(r'<ul[^>]*>(.*?)</ul>', body, re.S)
        items = []
        for href, text in re.findall(r'<a href="([^"]+)"[^>]*>(.*?)</a>', ul.group(1) if ul else '', re.S):
            label = re.sub(r'<[^>]+>', '', text).strip()
            if label and href != '#':
                items.append('<li><a href="%s">%s</a></li>' % (esc(href), esc(label)))
        if not items and ul:
            for text in re.findall(r'<li[^>]*>(.*?)</li>', ul.group(1), re.S):
                label = re.sub(r'<[^>]+>', '', text).strip()
                if label:
                    items.append('<li>%s</li>' % esc(label))
        if not items:
            continue
        parts.append('<div class="home-cell"><h2 class="home-cell__title">%s</h2>'
                     '<ul class="home-cell__list">%s</ul></div>' % (esc(title), ''.join(items)))
    if not parts:
        return ''
    return '<div class="home-grid">%s</div>' % ''.join(parts)


# ------------------------------------------------------------------ хабы и страницы
HUB_PAGES = {
    '269': ('/snaryazhenie/', 'Снаряжение'),
    '293': ('/bestiarij/', 'Бестиарий'),
    '72': ('/proiskhozhdeniya/', 'Происхождения'),
}

# список персонажей/существ: из живого рендера хаба
def hub_cards_from_live(path, base_url):
    src = open(os.path.join('public', path.strip('/'), 'index.html'), encoding='utf-8', errors='ignore').read()
    cards = re.findall(r'<a href="([^"]+)"[^>]*>\s*<img[^>]*src="([^"]+)"[^>]*alt="([^"]*)"', src)
    return cards


def write(path, html_src):
    target = os.path.join(DOCS, path.strip('/'), 'index.html')
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, 'w', encoding='utf-8') as f:
        f.write(html_src)
    return target


def shell(title, body, active=''):
    """Каркас страницы — тот же, что у сайта (шапка плашками, подвал)."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import build_site as B
    return B.page(title, body, active=active)


def main():
    sp, articles = load()
    umap = url_map()
    print('адресов из живых страниц:', len(umap))

    # 1. Главная
    home = home_from_live()
    if home:
        write('/', shell('Правила игры', '<div class="sp-page">%s</div>' % home))
        print('главная: из public/index.html')

    # 2. Хабы из SPPB-дампа (269 снаряжение, 293 бестиарий, 72 происхождения)
    for pid, (url, title) in HUB_PAGES.items():
        rec = sp.get(pid)
        if not rec:
            continue
        body = R.page_from_dump(rec, title)
        if body:
            write(url, shell(title, body))
            print('хаб %-16s из дампа id %s' % (url, pid))

    # 3. Страницы-записи: всё, что нашлось в дампе и имеет адрес в живых страницах
    made = 0
    for rid, rec in sp.items():
        if str(rec.get('active')) != '1':
            continue
        if rid in HUB_PAGES:
            continue
        url = url_for(rec['title'], umap)
        if not url or url in ('/',):
            continue
        body = R.page_from_dump(rec)
        if not body:
            continue
        write(url, shell(rec['title'], body))
        made += 1
    print('страниц из дампа SPPB:', made)

    # 4. Статьи из jos_content, у которых есть адрес в живых страницах.
    #    Приоритет ниже, чем у дампа SPPB: уже собранные страницы не трогаем.
    written = set()
    for rid, rec in sp.items():
        u = url_for(rec['title'], umap)
        if u:
            written.add(u)
    made_a = 0
    for aid, art in articles.items():
        if art.get('state') != '1':
            continue
        url = url_for(art['title'], umap)
        if not url or url in written:
            continue
        body = (art.get('fulltext') or '') + (art.get('introtext') or '')
        if not R.plain(body).strip():
            continue
        write(url, shell(art['title'], '<div class="sp-page"><h1 class="sp-page__title">%s</h1>'
                         '<div class="sp-text">%s</div></div>' % (esc(art['title']), R.clean_html(body))))
        made_a += 1
    print('страниц из jos_content:', made_a)


if __name__ == '__main__':
    main()
