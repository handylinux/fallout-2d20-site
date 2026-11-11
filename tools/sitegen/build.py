#!/usr/bin/env python3
"""
Генератор статической версии fallout-2d20.ru.

Источники (всё из дампов Joomla, лежащих в корне репозитория):
  jos_content.json        — статьи (jos_content)
  jos_sppagebuilder.zip   — страницы и модули SP Page Builder (jos_sppagebuilder)

Что происходит:
  1. Каждый layout SPP Page Builder рендерится своим рендерером (tools/sitegen/sppb.py),
     который повторяет разметку и CSS SPPB 5: секции/строки/колонки/аддоны, отступы,
     типографика, фоны, тени — из настроек, без «своих» значений.
  2. Страницы оборачиваются в каркас Helix Ultimate: body-wrapper → main#sp-main →
     section#sp-section-1 (лого + бургер) → section#sp-section-2 (#sp-topmenu из
     модуля «Fallout menu», строка 101) → section#sp-main-body.
  3. Оффканвас-меню: полное дерево навигации (src/nav/nav.json, 210+ пунктов).
  4. Ссылки Joomla (index.php?option=…) переписываются в человеческие URL.

Запуск: python3 tools/sitegen/build.py
"""
import html
import json
import os
import re
import shutil
import sys
import zipfile
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sppb  # noqa: E402
from sppb import Renderer, clean, esc  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
# На GitHub Pages сайт живёт в подкаталоге /fallout-2d20-site/: абсолютные пути
# (/assets/…) ломаются, поэтому префикс задаётся при сборке: BASE=/fallout-2d20-site
OUT = os.path.join(ROOT, 'public')
SRC = os.path.join(ROOT, 'src')
URLS = json.load(open(os.path.join(SRC, 'nav', 'urls.json'), encoding='utf-8'))
BASE = (os.environ.get('BASE') or '').rstrip('/')   # '' локально, '/repo' на GitHub Pages


def hp(url):
    """Внутренний абсолютный адрес → адрес с префиксом BASE."""
    if not BASE or not url.startswith('/'):
        return url
    if url.startswith('//'):
        return url
    return BASE + url


# --------------------------------------------------------------------------- данные дампа
def load_dumps():
    rows = json.load(open(os.path.join(ROOT, 'jos_content.json'), encoding='utf-8'))
    articles = [e for e in rows if e.get('type') == 'table'][0]['data']
    path = os.path.join(ROOT, 'jos_sppagebuilder', 'jos_sppagebuilder.json')
    if os.path.exists(path):
        sp = json.load(open(path, encoding='utf-8'))
    else:
        with zipfile.ZipFile(os.path.join(ROOT, 'jos_sppagebuilder.zip')) as z:
            sp = json.loads(z.read('jos_sppagebuilder.json').decode('utf-8'))
    layouts = [e for e in sp if e.get('type') == 'table'][0]['data']
    return articles, layouts


def layout_of(row):
    """SPPB 5 хранит JSON в `content`, SPPB 3 — в `text`."""
    if not row:
        return []
    for key in ('content', 'text'):
        v = row.get(key) or ''
        if len(v) > 2:
            try:
                data = json.loads(v)
            except ValueError:
                continue
            if isinstance(data, list) and data:
                return data
    return []


# --------------------------------------------------------------------------- картинки
# Соответствие путей Joomla → локальные файлы (что уже перенесено в public/assets/img).
IMG_MAP = {
    'images/main-background.jpg': 'assets/img/bg-main.jpg',
    'images/food-truck-pattern.jpg': 'assets/img/food-truck-pattern.jpg',
    'images/2025/03/30/logos.png': 'assets/img/logos.png',
    'images/2025/04/24/menu-item-bg-lblue-2.png': 'assets/img/plates/menu-item-bg-lblue2.png',
    'images/2025/04/24/menu-item-bg-lblue2.png': 'assets/img/plates/menu-item-bg-lblue2.png',
    'images/2025/04/24/menu-item-bg-lblue.png': 'assets/img/plates/menu-item-bg-lblue.png',
    'images/2025/04/24/menu-item-bg-green.png': 'assets/img/plates/menu-item-bg-green.png',
    'images/2025/04/24/menu-item-bg-green2.png': 'assets/img/plates/menu-item-bg-green2.png',
    'images/2025/04/24/menu-item-bg-pink.png': 'assets/img/plates/menu-item-bg-pink.png',
    'images/2025/04/24/menu-item-bg-orange2.png': 'assets/img/plates/menu-item-bg-orange2.png',
    'images/lxksyhm.png': 'assets/img/lxksyhm.png',
    'images/2025/03/30/lxksyhm.png': 'assets/img/lxksyhm.png',
}

# Категория без статьи: на живом сайте это JS-страница /perki26
CATEGORY_PAGES = {'15': '/perki26'}

MISSING_IMAGES = set()


def img_src(src):
    """Путь картинки из дампа → путь в статике (или заглушка, если файла ещё нет)."""
    if not src:
        return ''
    s = src.strip()
    if s.startswith(('http://', 'https://', 'data:')):
        return s
    key = s.lstrip('/')
    if key in IMG_MAP:
        return hp('/' + IMG_MAP[key].lstrip('/'))
    MISSING_IMAGES.add(key)
    return hp('/assets/img/' + key.split('/')[-1])


# --------------------------------------------------------------------------- ссылки
class Site:
    def __init__(self, articles, layouts, nav):
        self.by_alias = {}
        self.articles = {}
        for a in articles:
            self.articles[a['id']] = a
            self.by_alias.setdefault(a['alias'], a)
        self.sp = {r['id']: r for r in layouts}
        self.nav = nav
        self.url_by_alias = dict(URLS)
        self.article_url = {}
        self.itemid_url = {}
        self._collect_urls()

    def _walk(self, items, acc):
        for it in items:
            acc.append(it)
            self._walk(it.get('children') or [], acc)

    def _collect_urls(self):
        nodes = []
        self._walk(self.nav.get('items') or [], nodes)
        self._walk(self.nav.get('extra') or [], nodes)

        for it in nodes:
            u = it.get('url') or ''
            slug = u.rstrip('/').rsplit('/', 1)[-1]
            a = self.by_alias.get(slug)
            if a and u:
                self.article_url.setdefault(a['id'], u)
                self.url_by_alias.setdefault(a['alias'], u)

        # Itemid → адрес: берём из ссылок, которые уже разобраны в известные URL
        rx = re.compile(r'index\.php\?[^"\'\\\s<>]+')
        for r in self.sp.values():
            for key in ('content', 'text'):
                for m in rx.finditer(r.get(key) or ''):
                    q = self._query(html.unescape(m.group(0)))
                    itemid, ident = q.get('Itemid'), (q.get('id') or '').split(':')[0]
                    opt = q.get('option')
                    if not itemid or not ident:
                        continue
                    url = ''
                    if opt == 'com_sppagebuilder':
                        url = self.sppb_url(ident)
                    elif opt == 'com_content':
                        url = self.article_url.get(ident, '')
                    if url:
                        self.itemid_url.setdefault(itemid, url)

    @staticmethod
    def _query(url):
        if '?' not in url:
            return {}
        return {k: v[0] for k, v in parse_qs(url.split('?', 1)[1]).items()}

    def sppb_url(self, ident):
        r = self.sp.get(ident)
        if not r:
            return ''
        if r['extension'] == 'com_content':
            return self.article_url.get(r['view_id'], '')
        title = (r.get('title') or '').lower()
        if 'перки' in title:
            return '/perki'
        if 'форум' in title:
            return '/forum'
        return ''

    def resolve(self, url):
        """Joomla-ссылка → адрес статической страницы ('' если адрес ещё не известен)."""
        if not url:
            return ''
        u = html.unescape(str(url)).strip()
        if u.startswith(('mailto:', 'tel:', '#')):
            return u
        if u.startswith(('http://', 'https://')):
            if 'fallout-2d20.ru' not in u:
                return u
            u = urlparse(u).path + (('?' + urlparse(u).query) if urlparse(u).query else '')
        if 'index.php' in u or u.startswith('/component/') or u.startswith('component/'):
            q = self._query(u)
            ident = (q.get('id') or '').split(':')[0]
            opt = q.get('option')
            if ident:
                slug = ident if not ident.isdigit() else ''
                if slug and slug in self.url_by_alias:
                    return self.url_by_alias[slug]
            if opt == 'com_sppagebuilder':
                return self.sppb_url(ident) or self.itemid_url.get(q.get('Itemid'), '') or ''
            if opt == 'com_content':
                return (self.article_url.get(ident) or self.article_slug_url(ident)
                        or CATEGORY_PAGES.get(ident)
                        or self.itemid_url.get(q.get('Itemid'), '') or '')
            return self.itemid_url.get(q.get('Itemid'), '') or ''
        # относительный адрес из контента («bestiarij/raiders») → корневой
        if not u.startswith(('/', '#', 'mailto:', 'tel:', 'http://', 'https://', '//')):
            u = '/' + u
        return u

    # --- контекст для рендерера SPPB
    def ctx(self):
        return {
            'link': self.link,
            'raw_link': lambda u: hp(self.resolve(u) or '#'),
            'img': img_src,
            'text': lambda t: self.rewrite_html(t),
        }

    def link(self, link):
        if not isinstance(link, dict):
            return hp(self.resolve(link)) if link else ''
        if link.get('type') == 'menu' and link.get('menu'):
            return hp(self.resolve(link['menu']) or link.get('url') or '')
        return hp(self.resolve(link.get('url') or '') or '')

    def article_slug_url(self, ident):
        a = self.articles.get(str(ident))
        if not a:
            return ''
        return (self.url_by_alias.get(a['alias']) or self.article_url.get(str(ident)) or '')

    def rewrite_html(self, blob):
        if not blob:
            return ''
        # SPPB dynamic content: href="#" + data-link-value="index.php?..."
        blob = re.sub(
            r'<a([^>]*?)href="#"([^>]*?)data-link-value="([^"]+)"',
            lambda m: '<a%s href="%s"%s' % (
                m.group(1), esc(self.resolve(m.group(3)) or self.article_slug_url(
                    (re.search(r'id=(\d+)', m.group(3)) or [0, ''])[1]) or '#'), m.group(2)),
            blob)
        def absolute(u):
            u = self.resolve(u) or '#'
            return u

        out = re.sub(r'href="([^"]*)"',
                     lambda m: 'href="%s"' % esc(hp(absolute(m.group(1)))), blob)
        out = re.sub(r'src="([^"]*)"',
                     lambda m: 'src="%s"' % esc(hp(img_src(m.group(1)))), out)
        out = re.sub(r'(url\(["\']?)(/images/[^"\')]+)',
                     lambda m: m.group(1) + hp(img_src(m.group(2))), out)
        return out


# --------------------------------------------------------------------------- Helix-каркас
BODY_CLASSES = ('site helix-ultimate hu com-content view-article layout-default task-none '
                'itemid-172 ru-ru ltr layout-fluid offcanvas-init offcanvs-position-right')


def render_sppb_row(site, sp_id, extra_class='', scope=None):
    """Рендер строки SPPB. scope='#sp-topmenu' изолирует её CSS от стилей страницы:
    у шапки и у контента одинаковые id секций, и без scope правила «дерутся»."""
    row = site.sp.get(sp_id)
    rows = layout_of(row)
    r = Renderer(rows, getattr(site, 'ctx_d', None) or site.ctx())
    body = r.render()
    css = ''.join(r.css)
    if scope:
        css = scope_css(css, scope)
    if extra_class:
        body = body.replace('class="sppb-section', 'class="%s sppb-section' % extra_class, 1)
    return body, css


def scope_css(css, scope):
    """Префиксовать селекторы правил заданным контейнером (#sp-topmenu …)."""
    out = []
    i = 0
    n = len(css)
    while i < n:
        at = css.find('@media', i)
        brace = css.find('{', i)
        if brace < 0:
            out.append(css[i:])
            break
        if 0 <= at < brace:                      # медиа-блок: рекурсивно
            inner_start = css.find('{', at) + 1
            depth, j = 1, inner_start
            while j < n and depth:
                if css[j] == '{':
                    depth += 1
                elif css[j] == '}':
                    depth -= 1
                j += 1
            head_txt = css[at:inner_start]
            out.append(head_txt + scope_css(css[inner_start:j - 1], scope) + '}')
            i = j
            continue
        sel = css[i:brace].strip()
        depth, j = 1, brace + 1
        while j < n and depth:
            if css[j] == '{':
                depth += 1
            elif css[j] == '}':
                depth -= 1
            j += 1
        body = css[brace:j]
        if sel:
            sels = ', '.join(
                (x.strip() if x.strip().startswith(scope) else scope + ' ' + x.strip())
                for x in sel.split(',') if x.strip())
            out.append(sels + body)
        i = j
    return ''.join(out)


def head(title, css_blocks, page_css=''):
    return f"""<!DOCTYPE html>
<html lang="ru-ru" dir="ltr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no">
<meta name="generator" content="Helix Ultimate - The Most Popular Joomla! Template Framework.">
<title>{esc(title)}</title>
<link href="{BASE}/assets/vendor/bootstrap.min.css" rel="stylesheet">
<link href="{BASE}/assets/css/template.css" rel="stylesheet">
<link href="{BASE}/assets/css/presets-default.css" rel="stylesheet">
<link href="{BASE}/assets/css/animate.min.css" rel="stylesheet">
<link href="{BASE}/assets/css/sppagebuilder.css" rel="stylesheet">
<style>:root {{--sppb-topbar-bg-color: #333333; --sppb-topbar-text-color: #aaaaaa; --sppb-header-bg-color: #000000; --sppb-logo-text-color: #2b2b2b; --sppb-menu-text-color: #fee9a6; --sppb-menu-text-hover-color: #000000; --sppb-menu-text-active-color: #000000; --sppb-menu-dropdown-bg-color: #ffffff; --sppb-menu-dropdown-text-color: #252525; --sppb-menu-dropdown-text-hover-color: #fee9a6; --sppb-offcanvas-menu-icon-color: #ffc500; --sppb-offcanvas-menu-bg-color: #4f4b4b; --sppb-offcanvas-menu-items-and-items-color: #fee9a6; --sppb-offcanvas-menu-active-menu-item-color: #ffc500; --sppb-text-color: #000000; --sppb-bg-color: #ffffff; --sppb-link-color: #b15b23; --sppb-link-hover-color: #042615; --sppb-footer-bg-color: #171717; --sppb-footer-text-color: #ffffff; --sppb-footer-link-color: #a2a2a2; --sppb-footer-link-hover-color: #ffffff}}</style>
<style>.logo-image {{height:60px;}}.logo-image-phone {{height:60px;}}
@media(max-width: 992px) {{.logo-image {{height: 36px;}}.logo-image-phone {{height: 36px;}}}}
@media(max-width: 576px) {{.logo-image {{height: 36px;}}.logo-image-phone {{height: 36px;}}}}</style>
<style>#sp-section-1{{background-image:url("{BASE}/assets/img/bg-main.jpg");background-repeat:no-repeat;background-size:cover;background-attachment:fixed;background-position:50% 50%;padding:30px 0px 20px 0px;}}
#sp-section-2{{background-image:url("{BASE}/assets/img/bg-main.jpg");background-repeat:no-repeat;background-size:cover;background-attachment:fixed;background-position:50% 50%;padding:10px 0px;margin:0px 0px 0px 0px;}}
#sp-main-body{{background-image:url("{BASE}/assets/img/bg-main.jpg");background-repeat:no-repeat;background-size:cover;background-attachment:fixed;background-position:0 0;}}
@media(min-width: 1400px) {{.sppb-row-container {{max-width: 1400px;}}}}
.container,.sppb-row-container{{max-width:1400px;}}</style>
<style>body,.sp-preloader{{font-family:Helvetica,Arial,sans-serif;font-size:16px;font-weight:400;line-height:1.5;}}
h1,h2,h3,h4,h5,h6{{font-family:Arial,Helvetica,sans-serif;font-weight:700;}}
.sp-megamenu-parent>li>a,.sp-megamenu-parent>li>span,.offcanvas-menu .offcanvas-inner ul.menu a{{font-family:Arial,Helvetica,sans-serif;}}
#sp-header .logo a{{font-family:Arial,Helvetica,sans-serif;}}</style>
{''.join('<style>%s</style>' % c for c in css_blocks if c)}
{page_css}
</head>"""


def burger():
    return ('<a id="offcanvas-toggler" aria-label="Menu" '
            'class="offcanvas-toggler-right offcanvas-toggler-custom align-items-center" '
            'href="#" title="Menu"><div class="burger-icon" aria-hidden="true">'
            '<span></span><span></span><span></span></div></a>')


def offcanvas_tree(items, level=0):
    out = []
    for it in items:
        kids = it.get('children') or []
        url = esc(hp(it.get('url') or '#'))
        title = esc(it.get('title') or '')
        if kids:
            out.append('<li class="menu-parent">')
            out.append('<a class="nav-header" href="%s">%s</a>' % (url, title))
            out.append('<span class="menu-toggler" role="button" aria-expanded="false"></span>')
            out.append('<ul class="menu-child">%s</ul>' % offcanvas_tree(kids, level + 1))
            out.append('</li>')
        else:
            out.append('<li class="sp-menu-item"><a href="%s">%s</a></li>' % (url, title))
    return ''.join(out)


def footer(site):
    extra = ''.join('<li class="sp-menu-item"><a href="%s">%s</a></li>'
                    % (esc(i['url']), esc(i['title'])) for i in site.nav.get('extra') or [])
    return f"""
      <footer id="sp-footer">
        <div class="container"><div class="container-inner">
          <div class="row">
            <div id="sp-footer1" class="col-lg-12"><div class="sp-column">
              <div class="sp-module"><div class="sp-module-content">
                <ul class="menu footer-menu">{extra}</ul>
              </div></div>
              <span class="sp-copyright">Fallout 2D20 — настольная ролевая игра по мотивам Fallout от Modiphius Entertainment. Неофициальный русскоязычный сайт.</span>
            </div></div>
          </div>
        </div></div>
      </footer>"""


def offcanvas(site):
    return f"""
<div class="offcanvas-overlay"></div>
<div class="offcanvas-menu" tabindex="-1" inert>
  <div class="d-flex align-items-center justify-content-between p-3 pt-4">
    <a href="{BASE}/" class="offcanvas-logo"><img src="{BASE}/assets/img/logos.png" alt="Fallout 2D20"></a>
    <a href="#" class="close-offcanvas" role="button" aria-label="Закрыть меню">
      <div class="burger-icon" aria-hidden="true"><span></span><span></span><span></span></div>
    </a>
  </div>
  <div class="offcanvas-inner">
    <div class="sp-module">
      <ul class="menu">{offcanvas_tree(site.nav.get('items') or [])}</ul>
    </div>
    <div class="sp-module">
      <ul class="menu">{''.join('<li class="sp-menu-item"><a href="%s">%s</a></li>' % (esc(hp(i['url'])), esc(i['title'])) for i in site.nav.get('extra') or [])}</ul>
    </div>
  </div>
</div>
<a href="#" class="sp-scroll-up" aria-label="Scroll to top"><span class="fas fa-angle-up" aria-hidden="true">&#9650;</span></a>
<script src="{BASE}/assets/vendor/bootstrap.bundle.min.js"></script>
<script src="{BASE}/assets/js/main.js"></script>
</body>
</html>
"""




# ------------------------------------------------------------------ заглушки для меню
STUB = """<!DOCTYPE html>
<html lang="ru-ru" dir="ltr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no">
<title>{title}</title>
<link href="{base}/assets/vendor/bootstrap.min.css" rel="stylesheet">
<link href="{base}/assets/css/template.css" rel="stylesheet">
<link href="{base}/assets/css/presets-default.css" rel="stylesheet">
<style>body{{font-family:Helvetica,Arial,sans-serif;}}#sp-section-1{{background:url("{base}/assets/img/bg-main.jpg") fixed/cover;padding:30px 0 20px;}}</style>
</head>
<body class="site helix-ultimate ru-ru ltr layout-fluid">
<div class="body-wrapper"><div class="body-innerwrapper"><main id="sp-main">
<section id="sp-section-1"><div class="container"><div class="container-inner">
  <div class="d-flex align-items-center justify-content-between">
    <a href="{base}/" class="logo-image"><img src="{base}/assets/img/logos.png" alt="Fallout 2D20" class="logo-image"></a>
    <a href="{base}/" class="btn btn-sm btn-light">На главную</a>
  </div>
</div></div></section>
<section id="sp-main-body"><div class="container"><div class="container-inner">
  <div class="bg-white p-4 my-4">
    <h1 class="h3">{title}</h1>
    <p class="mb-2">Страница раздела «{title}» ещё не включена в статическую сборку.</p>
    <p class="mb-0 text-muted">Этот этап — скелет из шести разделов верхнего меню. Адрес сохранён из структуры сайта,
    поэтому все ссылки меню рабочие; страница появится на следующем этапе.</p>
    <p class="mt-3 mb-0"><a href="{base}/">← Правила игры</a></p>
  </div>
</div></div></section>
</main></div></div>
</body>
</html>
"""


def write_stubs(site):
    """Для каждого пункта меню без собранной страницы — заглушка по тому же адресу."""
    made = []

    def walk(items):
        for it in items:
            yield it
            yield from walk(it.get('children') or [])

    for it in walk(site.nav.get('items') or []):
        url = (it.get('url') or '').strip()
        if not url.startswith('/') or url in ('/', '/perki26'):
            continue
        target = os.path.join(OUT, url.strip('/'), 'index.html')
        if os.path.exists(target):
            continue
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, 'w', encoding='utf-8') as f:
            f.write(STUB.format(title=esc(it.get('title') or ''), base=BASE))
        made.append(url)
    return made


# --------------------------------------------------------------------------- сборка
PAGES = [
    # файл, id строки SPPB, заголовок
    ('.', '161', 'Правила игры'),
    ('proiskhozhdeniya', '72', 'Происхождения'),
    ('snaryazhenie', '269', 'Снаряжение'),
    ('perki', '115', 'Перки'),
    ('bestiarij', '293', 'Бестиарий'),
    ('forum', '388', 'Форум'),
]


def main():
    articles, layouts = load_dumps()
    nav = json.load(open(os.path.join(SRC, 'nav', 'nav.json'), encoding='utf-8'))
    site = Site(articles, layouts, nav)
    sppb.MAP_IMG = img_src

    def render_article(art_id):
        """Статья Joomla (introtext + fulltext) — как выводит com_content."""
        a = site.articles.get(art_id)
        if not a:
            return ''
        body = (a.get('introtext') or '') + (a.get('fulltext') or '')
        if not body.strip():
            return ''
        return ('<div class="com-content-article item-page"><div class="article-details">'
                '<div class="article-body">%s</div></div></div>' % site.rewrite_html(body))

    def render_module(mod_id):
        """Модуль по id: SPP Page Builder → его layout; статья → com_content."""
        for r in layouts:
            if r.get('view_id') != str(mod_id):
                continue
            if r['extension'] == 'com_content':
                return render_article(r['view_id'])
            if r['extension'] == 'mod_sppagebuilder':
                inner = Renderer(layout_of(r), ctx).render()
                return inner
        return ''

    ctx = site.ctx()
    ctx['module'] = render_module
    site.ctx_d = ctx

    for sub in ('assets/css', 'assets/js', 'assets/img'):
        os.makedirs(os.path.join(OUT, sub), exist_ok=True)

    # --- шапка: лого Helix + бургер; горизонтальное меню = модуль «Fallout menu» (строка 101)
    header_html, header_css = '', ''
    topmenu_html, topmenu_css = render_sppb_row(site, '101', scope='#sp-topmenu')
    topmenu_html = re.sub(r'<h([1-6])', '<span class="sp-menu-title"', topmenu_html)
    topmenu_html = re.sub(r'</h[1-6]>', '</span>', topmenu_html)
    topmenu_html = re.sub(r'class="sp-menu-title" class="([^"]*)"', r'class="\1 sp-menu-title"', topmenu_html)

    report = []
    for folder, sp_id, title in PAGES:
        body, css = render_sppb_row(site, sp_id)
        outdir = OUT if folder == '.' else os.path.join(OUT, folder)
        os.makedirs(outdir, exist_ok=True)

        page = head(title, [header_css, topmenu_css, css])
        page = page.replace('{BASE}', BASE)
        page += f"""
<body class="{BODY_CLASSES}">
<div class="body-wrapper">
  <div class="body-innerwrapper">
    <main id="sp-main">
      <section id="sp-section-1">
        <div class="container"><div class="container-inner">
          <div class="row align-items-center">
            <div id="sp-logo" class="col"><div class="sp-column">
              <div class="logo"><a href="{BASE}/" class="logo-image"><img src="{BASE}/assets/img/logos.png" alt="Fallout 2D20" class="logo-image"></a></div>
            </div></div>
            <div id="sp-menu" class="col-auto"><div class="sp-column d-flex justify-content-end">{burger()}</div></div>
          </div>
        </div></div>
      </section>
      <section id="sp-section-2" class="d-none d-xl-block">
        <div class="container"><div class="container-inner">
          <div class="row">
            <div id="sp-topmenu" class="col-lg-12"><div class="sp-column">
              <div class="sp-module"><div class="sp-module-content">{topmenu_html}</div></div>
            </div></div>
          </div>
        </div></div>
      </section>
      <section id="sp-main-body">
        <div class="container"><div class="container-inner">
          <div class="row">
            <div id="sp-component" class="col-lg-12"><div class="sp-column">
              <div id="sp-page-builder" class="sp-page-builder"><div class="page-content">
{body}
              </div></div>
            </div></div>
          </div>
        </div></div>
      </section>
    </main>
  </div>
</div>
{footer(site)}
{offcanvas(site)}"""
        with open(os.path.join(outdir, 'index.html'), 'w', encoding='utf-8') as f:
            f.write(page)
        report.append((folder, sp_id, len(body), len(css)))

    # --- CSS / JS
    for name in ('template.css', 'presets-default.css', 'sppagebuilder.css', 'animate.min.css'):
        src = os.path.join(SRC, 'css', name)
        if os.path.exists(src):
            shutil.copy(src, os.path.join(OUT, 'assets', 'css', name))
    idir = os.path.join(OUT, 'assets', 'img')
    srcdir = os.path.join(SRC, 'img')
    if os.path.isdir(srcdir):
        for root, _dirs, files in os.walk(srcdir):
            rel = os.path.relpath(root, srcdir)
            dst = idir if rel == '.' else os.path.join(idir, rel)
            os.makedirs(dst, exist_ok=True)
            for name in files:
                shutil.copy(os.path.join(root, name), os.path.join(dst, name))
    vdir = os.path.join(OUT, 'assets', 'vendor')
    os.makedirs(vdir, exist_ok=True)
    for name in ('bootstrap.min.css', 'bootstrap.bundle.min.js'):
        src = os.path.join(SRC, 'vendor', name)
        if os.path.exists(src):
            shutil.copy(src, os.path.join(vdir, name))
    for name in ('main.js',):
        src = os.path.join(SRC, 'js', name)
        if os.path.exists(src):
            shutil.copy(src, os.path.join(OUT, 'assets', 'js', name))

    stubs = write_stubs(site)
    # /perki26 — тот же контент, что /perki (живой сайт держит перки на /perki26)
    alt = os.path.join(OUT, 'perki26')
    os.makedirs(alt, exist_ok=True)
    with open(os.path.join(alt, 'index.html'), 'w', encoding='utf-8') as f:
        f.write('<!DOCTYPE html><html lang="ru-ru"><head><meta charset="utf-8">'
                '<meta http-equiv="refresh" content="0; url=%s/perki/">'
                '<link rel="canonical" href="%s/perki/"><title>Перки</title></head>'
                '<body><p><a href="%s/perki/">Перки</a></p></body></html>'
                % (BASE, BASE, BASE))
    for folder, sp_id, h, c in report:
        print('%-18s sppb#%-4s html=%-7s css=%s' % (folder, sp_id, h, c))
    print('заглушек для пунктов меню: %d' % len(stubs))
    if MISSING_IMAGES:
        print('\nКартинки, которых ещё нет в репозитории (%d):' % len(MISSING_IMAGES))
        for m in sorted(MISSING_IMAGES)[:40]:
            print('  ', m)


if __name__ == '__main__':
    main()
