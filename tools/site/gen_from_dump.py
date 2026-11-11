#!/usr/bin/env python3
"""Сборка страниц прямо из выгрузок Joomla: SPPB-дамп + jos_content.

Ничего не сочиняется: дерево SPPB рендерится как есть (см. sppb_render.py),
тексты статей берутся из jos_content, адреса — из сохранённых живых страниц
`public/` (там же лежит карта заголовок → URL).

Запуск: BASE=/fallout-2d20-site python3 tools/site/gen_from_dump.py
"""
import glob
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


TRANSLIT = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e', 'ж': 'zh',
    'з': 'z', 'и': 'i', 'й': 'j', 'к': 'k', 'л': 'l', 'м': 'm', 'н': 'n', 'о': 'o',
    'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u', 'ф': 'f', 'х': 'kh', 'ц': 'ts',
    'ч': 'ch', 'ш': 'sh', 'щ': 'shch', 'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e',
    'ю': 'yu', 'я': 'ya',
}


def slugify(text):
    out = ''.join(TRANSLIT.get(ch, ch) for ch in (text or '').lower())
    out = re.sub(r'[^a-z0-9]+', '-', out)
    return re.sub(r'-{2,}', '-', out).strip('-')


# заголовок в дампе → адрес живой страницы (там название короче)
URL_ALIASES = {
    'пистолет-пулемёт томпсона (томми-ган)': '/oruzhie/strelkovoe-oruzhie/tommi-gan/',
    'инъекционный пистолет': '/oruzhie/strelkovoe-oruzhie/karabin-gulya-2/',
}


PERK_URLS = {}  # отдельных страниц перков нет: все ведут в /perki/

# страницы SPPB (com_sppagebuilder), на которые ссылаются тексты
SP_PAGE_URLS = {
    '104': '/proiskhozhdeniya/',
    '107': '/proiskhozhdeniya/',
    '108': '/proiskhozhdeniya/',
    '109': '/proiskhozhdeniya/',
    '110': '/proiskhozhdeniya/',
    '111': '/proiskhozhdeniya/',
    '112': '/proiskhozhdeniya/',
}

# пункты меню Joomla, на которые ссылаются тексты (Itemid → адрес у нас)
MENU_ITEM_URLS = {
    '401': '/oruzhie/strelkovoe-oruzhie/',      # штурмовые винтовки
    '402': '/oruzhie/strelkovoe-oruzhie/',      # боевые винтовки
    '455': '/oruzhie/vzryvchatka/',             # осколочные гранаты
    '416': '/oruzhie/',                         # оружие
    '415': '/bronya/',
    '423': '/eda/',
    '425': '/oruzhie/',
    '428': '/snaryazhenie/',
    '430': '/bronya/',
    '434': '/perki/',
    '469': '/perki/',
    '470': '/proiskhozhdeniya/',
    '527': '/eda/',
    '548': '/eda/',
    '590': '/dopolneniya/',
    '399': '/',
    '535': '/oruzhie/energooruzhie/karabin-tesly/',
    '412': '/oruzhie/oruzhie-blizhnego-boya/',
    '424': '/oruzhie/oruzhie-blizhnego-boya/',
    '426': '/oruzhie/vzryvchatka/',
    '419': '/oruzhie/vzryvchatka/',
    '398': '/oruzhie/',
}


def fix_links(fragment, umap, articles, textmap=None):
    """Ссылки из выгрузки Joomla на нашем сайте.

    1) index.php?option=com_content&view=article&id=143:tablitsa-sluchajnoj-edy
       — берём id статьи и ищем адрес по её заголовку в jos_content;
    2) index.php?Itemid=455 — пункт меню: сопоставить нечем, оставляем как есть
       только если адреса нет, иначе ссылка ведёт в никуда → убираем href.
    3) абсолютные ссылки на fallout-2d20.ru → те же адреса у нас.
    """
    by_id = {}
    for aid, art in (articles or {}).items():
        by_id[str(aid)] = art.get('title')
    base = BASE

    textmap = textmap or {}

    def repl(m):
        # m.group(0) — вся ссылка целиком: меняем только href внутри неё
        href = html.unescape(m.group(1))
        whole = m.group(0)
        # файл, которого у нас нет (pdf/zip): ссылку снимаем, текст остаётся
        if re.search(r'\.(pdf|zip|docx?|xlsx?)$', href, re.I):
            # файла у нас нет, но он есть на исходном сайте — ведём туда
            if 'fallout-2d20.ru' not in href:
                href = 'https://www.fallout-2d20.ru/' + href.lstrip('/')
            return re.sub(r'href="[^"]*"', 'href="%s"' % href, whole, count=1)
        if 'index.php' in href or href == '#':
            label = re.sub(r'<[^>]+>', '', m.group(2) if m.lastindex and m.lastindex > 1 else '')
            label = re.sub(r'\s+', ' ', html.unescape(label)).strip().lower()
            if label in textmap:
                return re.sub(r'href="[^"]*"', 'href="%s%s"' % (base, textmap[label]), whole, count=1)
        # пункт меню Joomla → раздел по названию ссылки (текст подписи)
        if href.startswith('index.php?Itemid='):
            mid = re.search(r'Itemid=(\d+)', href).group(1)
            url = MENU_ITEM_URLS.get(mid)
            return re.sub(r'href="[^"]*"', 'href="%s%s"' % (base, url), whole, count=1) if url else whole
        if href.startswith('http'):
            if 'fallout-2d20.ru' not in href:
                return m.group(0)
            path = re.sub(r'^https?://(www\.)?fallout-2d20\.ru', '', href)
            if not path or path == '/':
                return re.sub(r'href="[^"]*"', 'href="%s/"' % base, whole, count=1)
            if not path.endswith('/') and '.' not in path.split('/')[-1]:
                path += '/'
            for url in umap.values():
                if url.rstrip('/') == path.rstrip('/'):
                    return re.sub(r'href="[^"]*"', 'href="%s%s"' % (base, url), whole, count=1)
            return re.sub(r'href="[^"]*"', 'href="%s%s"' % (base, path), whole, count=1)
        if 'catid=15' in href or re.search(r'option=com_content.*[?&]id=(95|22|30|143):', href):
            url = PERK_URLS.get(re.search(r'[?&]id=(\d+)', href).group(1), '/perki/')
            return re.sub(r'href="[^"]*"', 'href="%s%s"' % (base, url), whole, count=1)
        if 'com_sppagebuilder' in href:
            mid = re.search(r'[?&]id=(\d+)', href)
            if mid:
                url = SP_PAGE_URLS.get(mid.group(1))
                if url:
                    return re.sub(r'href="[^"]*"', 'href="%s%s"' % (base, url), whole, count=1)
        if 'option=com_content' in href:
            mid = re.search(r'[?&]id=(\d+)', href)
            if mid:
                title = by_id.get(mid.group(1))
                url = url_for(title, umap) if title else None
                if url:
                    return re.sub(r'href="[^"]*"', 'href="%s%s"' % (base, url), whole, count=1)
        return whole

    fragment = re.sub(r'<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', repl, fragment, flags=re.S)

    # относительные ссылки внутри текста («oruzhie/energooruzhie») → от корня сайта
    def rel(m):
        href = m.group(1)
        if (href.startswith(('http', '/', '#', 'mailto:', 'index.php', 'data:', 'tel:'))
                or re.search(r'\.(pdf|zip|png|jpe?g|webp|svg|css|js)$', href, re.I)):
            return m.group(0)
        return 'href="%s/%s"' % (base, href.lstrip('/'))
    return re.sub(r'href="([^"]+)"', rel, fragment)


def repair_internal_links(umap):
    """После сборки: ссылка на страницу, которой нет, ищется по последнему
    сегменту адреса; если и такой нет — href убираем (текст остаётся)."""
    pages = {}
    for f in glob.glob(os.path.join(DOCS, '**', 'index.html'), recursive=True):
        rel = os.path.relpath(f, DOCS).replace(os.sep, '/')
        url = '/' + rel[:-len('index.html')]
        pages.setdefault(url.strip('/').split('/')[-1], url)
    fixed = dropped = 0
    for f in glob.glob(os.path.join(DOCS, '**', '*.html'), recursive=True):
        src = open(f, encoding='utf-8').read()
        def repl(m):
            nonlocal fixed, dropped
            href = m.group(1)
            if 'index.php' in href:
                mid = re.search(r'[?&](?:amp;)?id=(\d+)', href)
                if 'com_sppagebuilder' in href and mid and mid.group(1) in SP_PAGE_URLS:
                    fixed += 1
                    return 'href="%s%s"' % (BASE, SP_PAGE_URLS[mid.group(1)])
                if 'Itemid=' in href:
                    mi = re.search(r'Itemid=(\d+)', href)
                    if mi and mi.group(1) in MENU_ITEM_URLS:
                        fixed += 1
                        return 'href="%s%s"' % (BASE, MENU_ITEM_URLS[mi.group(1)])
                dropped += 1
                return 'data-href="%s"' % href
            if not href.startswith(BASE + '/') or '?' in href:
                return m.group(0)
            rel = href[len(BASE):]
            if '.' in rel.split('/')[-1].strip('/'):
                # файл (css/js/img/pdf/zip): ссылку на отсутствующий файл снимаем
                if os.path.exists(os.path.join(DOCS, rel.lstrip('/'))):
                    return m.group(0)
                dropped += 1
                return 'data-href="%s"' % href
            if os.path.exists(os.path.join(DOCS, rel.strip('/'), 'index.html')):
                return m.group(0)
            tail = rel.strip('/').split('/')[-1]
            if tail in pages:
                fixed += 1
                return 'href="%s%s"' % (BASE, pages[tail])
            dropped += 1
            return 'data-href="%s"' % href
        out = re.sub(r'href="([^"]+)"', repl, src)
        if out != src:
            open(f, 'w', encoding='utf-8').write(out)
    print('ссылок перенаправлено: %d, снято: %d' % (fixed, dropped))


def text_link_map():
    """Текст ссылки → адрес: из сохранённых живых страниц public/.
    Нужна для ссылок дампа, у которых есть только index.php?Itemid=…"""
    pairs = {}
    for f in glob.glob(os.path.join('public', '**', '*.html'), recursive=True):
        src = open(f, encoding='utf-8', errors='ignore').read()
        for href, text in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', src, re.S):
            if 'index.php' in href or href.startswith('#'):
                continue
            label = re.sub(r'<[^>]+>', '', text)
            label = re.sub(r'\s+', ' ', html.unescape(label)).strip().lower()
            if not label or len(label) > 80:
                continue
            if href.startswith(BASE):
                href = href[len(BASE):]
            if href.startswith('/'):
                pairs.setdefault(label, href)
    return pairs


def url_for(title, umap, fallback=None):
    """Адрес живой страницы по заголовку: сначала точное совпадение,
    потом транслит заголовка против последнего сегмента адреса."""
    key = (title or '').strip().lower()
    if key in URL_ALIASES:
        return URL_ALIASES[key]
    if key in umap:
        return umap[key]
    want = slugify(title)
    if not want:
        return fallback
    words = [w for w in want.split('-') if len(w) > 2]
    for title_key, url in umap.items():
        tail = (url or '').strip('/').split('/')[-1]
        if not tail:
            continue
        if tail == want or tail.startswith(want) or want.startswith(tail):
            return url
        # заголовок в дампе с уточнением («… (GRA)», «(Томми-ган)»): сверяем слова
        kwords = [w for w in slugify(title_key).split('-') if len(w) > 2]
        if words and kwords:
            common = len(set(words) & set(kwords))
            if common >= max(2, min(len(words), len(kwords)) - 1) and common / len(words) >= 0.6:
                return url
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
HUB_URLS = {'/snaryazhenie/', '/bestiarij/', '/proiskhozhdeniya/'}

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


TEXTMAP = {}


def write(path, html_src, umap=None, articles=None):
    if umap is not None:
        html_src = fix_links(html_src, umap, articles, TEXTMAP)
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
    # ссылки заголовков/картинок в хабах: id статьи Joomla → наш адрес
    R.LINK_MAP.update({
        '191': '/oruzhie/', '192': '/oruzhie/', '190': '/oruzhie/',
        '449': '/bronya/', '300': '/eda/',
    })
    print('адресов из живых страниц:', len(umap))

    # ссылки статей Joomla (id=…) → наши адреса: чтобы ссылки из дампа
    # (index.php?option=com_content&view=article&id=469) вели куда надо
    for aid, art in articles.items():
        u = url_for(art.get('title'), umap)
        if u:
            R.LINK_MAP.setdefault(str(aid), u)
    TEXTMAP.update(text_link_map())
    print('пар «текст ссылки → адрес»:', len(TEXTMAP))

    # 1. Главная — страница SPPB id 161 «Правила игры», та же сетка, что на сайте
    home_rec = sp.get('161')
    home = R.page_from_dump(home_rec, 'Правила игры') if home_rec else ''
    if home:
        write('/', shell('Правила игры', home), umap, articles)
        print('главная: из дампа id 161')
    else:
        home = home_from_live()
        if home:
            write('/', shell('Правила игры', '<div class="sp-page">%s</div>' % home), umap, articles)
            print('главная: из public/index.html')

    # 2. Хабы из SPPB-дампа (269 снаряжение, 293 бестиарий, 72 происхождения)
    for pid, (url, title) in HUB_PAGES.items():
        rec = sp.get(pid)
        if not rec:
            continue
        body = R.page_from_dump(rec, title)
        if body:
            write(url, shell(title, body), umap, articles)
            print('хаб %-16s из дампа id %s' % (url, pid))

    # 3. Страницы-записи: всё, что нашлось в дампе и имеет адрес в живых страницах
    made = 0
    for rid, rec in sp.items():
        if str(rec.get('active')) != '1':
            continue
        if rid in HUB_PAGES or rid in ('161',):
            continue
        url = url_for(rec['title'], umap)
        if not url or url in ('/',):
            continue
        # хаб и адреса из HUB_PAGES не перезаписываем другой записью
        if url in HUB_URLS:
            continue
        body = R.page_from_dump(rec)
        if not body:
            continue
        write(url, shell(rec['title'], body), umap, articles)
        made += 1
    print('страниц из дампа SPPB:', made)

    # 4. Статьи из jos_content, у которых есть адрес в живых страницах.
    #    Приоритет ниже, чем у дампа SPPB: уже собранные страницы не трогаем.
    written = set(HUB_PAGES[rid][0] for rid in HUB_PAGES) | {'/'}
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
                         '<div class="sp-text">%s</div></div>' % (esc(art['title']), R.clean_html(body))),
              umap, articles)
        made_a += 1
    print('страниц из jos_content:', made_a)

    repair_internal_links(umap)


if __name__ == '__main__':
    main()
