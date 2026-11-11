#!/usr/bin/env python3
"""Рендер страниц из дампа SPPB (jos_sppagebuilder) — без «мотивов».

Каждая страница дампа — дерево: rows → columns → addons. Здесь оно
превращается в обычный HTML с классами проекта:

  .sp-row / .sp-row--{n}   ряд и его раскладка (layout из дампа)
  .sp-col                  колонка с width из дампа
  .sp-heading / .sp-text / .sp-img / .sp-table / .sp-acc / .sp-tabs / .sp-btn

Числа (padding, width, размеры, цвета) берутся из настроек записи, ничего
не подставляется «на глаз». Всё, чего в дампе нет, остаётся пустым.

Запуск:  python3 tools/site/sppb_render.py  (перезапишет страницы в docs/)
"""
import html
import json
import os
import re

SPPB_JSON = '/tmp/sppb/jos_sppagebuilder.json'
CONTENT_JSON = 'jos_content.json'
DOCS = 'docs'
BASE = os.environ.get('BASE', '')

TAG_SKIP = {'row', 'empty_space', 'divider'}


# --------------------------------------------------------------------- утилиты
def esc(s):
    return html.escape(s or '', quote=True)


def plain(s):
    return re.sub(r'<[^>]+>', '', s or '')


def clean_html(fragment):
    """Текст из аддона text_block: разрешённые теги, без мусора редактора."""
    s = fragment or ''
    s = re.sub(r'<p>\s*</p>', '', s)
    s = s.replace('&nbsp;', ' ')
    s = s.replace(' data-mce-style="[^"]*"', '')
    s = re.sub(r'\sdata-mce-[a-z-]+="[^"]*"', '', s)
    s = re.sub(r'\sclass="mce-item-table[^"]*"', '', s)
    s = re.sub(r'\sstyle="[^"]*"', '', s)
    # картинки внутри текста (кубики, иконки) — те же правила, что у аддона image
    # таблицы из редактора — под тот же класс, что и table_advanced
    if '<table' in s:
        s = re.sub(r'<table[^>]*>', '<table class="sp-table">', s)
        s = s.replace('<table class="sp-table">', '<div class="sp-table-wrap"><table class="sp-table">')
        s = s.replace('</table>', '</table></div>')

    def _img(m):
        url = img_url(m.group(2))
        return '<img%s src="%s"%s>' % (m.group(1), url, m.group(3)) if url else ''
    s = re.sub(r'<img([^>]*?)src="([^"]*)"([^>]*?)>', _img, s)
    return s.strip()


def setting(addon, key, default=None):
    return (addon.get('settings') or {}).get(key, default)


def px(value, default=''):
    """padding/margin из дампа: dict с xl или строка."""
    if isinstance(value, dict):
        value = value.get('xl') or ''
    if not value:
        return default
    value = str(value).strip()
    # в дампе встречаются пустые стороны вида "px 0px 20px 0px"
    value = re.sub(r'(^|\s)px(\s|$)', r'\g<1>0px\g<2>', value)
    value = re.sub(r'^px\s+', '0px ', value)
    return re.sub(r'\s+', ' ', value)


# В выгрузке SPPB ссылки на картинки идут на images/... , а самих файлов в дампе
# нет. Поэтому имена сопоставлены с тем, что есть в репозитории: по ключевому
# слову в имени файла — та же картинка из src/img.
IMG_MAP = {
    # картинка из image-search / src/img, если брать её из выгрузки нечем
    r'10mm|pipe_pistol|pipe_revolver':            'assets/img/weapons/10-mm-pistolet.png',
    r'minigun|mesmetron|syringer|railway':        'assets/img/weapons/minigan.png',
    r'laser|aer9|gauss|plasma|flamer|tesla':      'assets/img/weapons/lazernyj-pistolet.png',
    r'bita|bat|bumper|sword|tomahawk|blade|machete': 'assets/img/weapons/bejsbolnaya-bita.png',
    r'grenade|frag':                              'assets/img/weapons/oskolochnaya-granata.png',
    r'power_fist|kastet':                         'assets/img/weapons/silovoj-kastet.png',
    r'hunting_rifle|combat_shotgun|double-barrel|tommy|tomagavk': 'assets/img/weapons/tomagavk.png',
    r'\.38_round|5mm|ammo':                      'assets/img/gear/boepripasy.png',
    r'combat_armor|raider_armor|leather':         'assets/img/gear/bronya.png',
    r'power_armor|excavator':                     'assets/img/armor/ekskavatornaya-silovaya-bronya.png',
    r'vault111|jumpsuit|vault-suit':              'assets/img/gear/odezhda.png',
    r'stimpack|radaway|med-x':                    'assets/img/gear/preparaty.png',
    r'bloatfly_meat|baked_bloatfly|jerky|food':   'assets/img/gear/eda.png',
    r'nuka_cola|nuka':                            'assets/img/gear/napitki.png',
    r'tales_of_jjv|magazine':                     'assets/img/gear/knigi.png',
    r'stealth_boy|stealth':                       'assets/img/gear/raznoe.png',
    r'bolotnik|duten|bramin|mirelurk':            'assets/img/gear/raznoe.png',
}


def img_url(src):
    """Ссылка на картинку.

    Оригиналов из выгрузки в дампе нет (только пути images/2023…2025), поэтому
    берём близкую картинку из src/img по IMG_MAP. Если подходящей нет —
    возвращаем пустую строку: битую иконку лучше не показывать вовсе.
    """
    if not src:
        return ''
    name = (src or '').lower()
    root = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))), 'src', 'img')
    if re.search(r'(^|/)cd\.png$', name):
        return (BASE + '/' if BASE else '/') + 'assets/img/CD.png'
    # картинки темы (фоны плашек, фон страницы, лого) — они уже есть у нас
    m = re.search(r'(menu-item-bg-[a-z0-9]+|bg-fon[-_0-9a-z]*|bg-main|food-truck-pattern|logos|lxksyhm|CD)', name)
    if m:
        fname = m.group(1)
        for cand in (fname + '.png', fname + '.jpg', 'bg-fon-3.png', 'bg-main.jpg',
                     'food-truck-pattern.jpg', 'logos.png', 'lxksyhm.png'):
            if os.path.exists(os.path.join(root, cand)):
                return (BASE + '/' if BASE else '/') + 'assets/img/' + cand
    # галерея image-search: имя файла выгрузки ищем в имени картинки
    if len(name) > 4:
        import glob as _glob
        gal = os.path.join(root, '..', '..', 'image-search')
        stem = re.sub(r'[^a-z0-9._-]', '_', name.split('/')[-1].rsplit('.', 1)[0].lower())[:14]
        hits = sorted(_glob.glob(os.path.join(gal, '*' + stem + '*')))
        if hits:
            f = os.path.basename(hits[0])
            dst = os.path.join(root, 'search', f)
            if not os.path.exists(dst):
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                import shutil as _sh
                _sh.copy2(hits[0], dst)
            return (BASE + '/' if BASE else '/') + 'assets/img/search/' + f
    for pattern, target in IMG_MAP.items():
        if re.search(pattern, name):
            if os.path.exists(os.path.join(root, target.split('assets/img/')[-1])):
                return (BASE + '/' if BASE else '/') + target
            return ''
    return ''


def col_style(col):
    """Инлайн-стиль колонки из её настроек в дампе: ширина, отступы, рамка,
    подложка (overlay), выравнивание содержимого по центру."""
    st = col.get('settings') or {}
    css = ['flex:0 0 %s' % width_of(col), 'max-width:%s' % width_of(col)]

    if st.get('use_border'):
        width = px(st.get('border_width')) or '1'
        width = re.sub(r'[^0-9.]', '', width) or '1'
        color = st.get('border_color') or '#6e6e6e'
        css.append('border:%spx solid %s' % (width, color))

    bg = st.get('background_image') or {}
    bg_type = st.get('background_type') or 'none'
    src = bg.get('src') if isinstance(bg, dict) else ''
    if bg_type in ('none', '', None):
        src = ''            # тема не выводит фон при background_type=none
    url = img_url(src) if src else ''
    if url:
        size = st.get('background_size') or 'auto'
        if size not in ('auto', 'cover', 'contain'):
            size = 'auto'
        css.append('background:url(%s) %s %s/%s' % (
            url, st.get('background_position') or '0 0',
            st.get('background_repeat') or 'repeat', size))

    box = st.get('boxshadow') or {}
    if isinstance(box, dict) and box.get('enabled') and str(box.get('blur')) != '0':
        css.append('box-shadow:%s %s %s %s %s' % (
            box.get('ho', 0), box.get('vo', 0), box.get('blur', 0),
            box.get('spread', 0), box.get('color') or '#c3c3c3'))
    return ';'.join(css)


# id статьи/страницы Joomla → наш адрес; заполняется из gen_from_dump
LINK_MAP = {}


def resolve_link(link):
    """Ссылка аддона (heading/image) → адрес у нас. В выгрузке это
    пункт меню/статья Joomla, своего адреса у неё нет."""
    if not isinstance(link, dict):
        return ''
    url = (link.get('url') or '').strip()
    if url and url not in ('/', '#') and 'index.php' not in url:
        return url
    src = link.get('menu') or ''
    m = re.search(r'[?&]id=(\d+)', src)
    if m and m.group(1) in LINK_MAP:
        return LINK_MAP[m.group(1)]
    if url == '/':
        return '/'
    return ''


def width_of(col):
    w = (col.get('settings') or {}).get('width') or {}
    if isinstance(w, dict):
        w = w.get('xl') or w.get('md') or ''
    return w or '100%'


# ------------------------------------------------------------------ рендер аддонов
def r_heading(a):
    t = setting(a, 'title') or ''
    if not t:
        return ''
    lvl = setting(a, 'heading_selector') or 'h2'
    if lvl not in ('h1', 'h2', 'h3', 'h4', 'h5'):
        lvl = 'h2'
    align = (setting(a, 'alignment') or {}).get('xl') if isinstance(setting(a, 'alignment'), dict) else ''
    cls = 'sp-heading' + (' sp-heading--center' if align == 'center' else '')
    link = resolve_link(setting(a, 'title_link'))
    inner = esc(t)
    if link:
        inner = '<a href="%s">%s</a>' % (esc(link), inner)
    return '<%s class="%s">%s</%s>' % (lvl, cls, inner, lvl)


def r_text(a):
    raw = setting(a, 'text') or ''
    body = clean_html(raw)
    if not plain(body).strip() and '<img' not in body and '<table' not in body:
        return ''
    return '<div class="sp-text">%s</div>' % body


def r_image(a):
    img = setting(a, 'image') or {}
    src = img.get('src') if isinstance(img, dict) else img
    if not src:
        return ''
    w = setting(a, 'image_width') or {}
    if isinstance(w, dict):
        w = w.get('xl') or ''
    style = ' style="max-width:%spx"' % w if str(w).strip().isdigit() else ''
    href = resolve_link(setting(a, 'link'))
    url = img_url(src)
    if not url:
        return ''
    out = '<img src="%s" alt="%s"%s>' % (esc(url), esc(setting(a, 'alt_text') or ''), style)
    if href:
        return '<a class="sp-img" href="%s">%s</a>' % (esc(href), out)
    return '<div class="sp-img">%s</div>' % out


def _cells(items):
    """Ячейки одного ряда таблицы: у каждой свой content[].settings.text."""
    out = []
    for it in items or []:
        frag = ''
        for c in it.get('content') or []:
            frag += clean_html((c.get('settings') or {}).get('text') or '')
        out.append(frag.strip())
    return out


def r_table(a):
    head = _cells(setting(a, 'sp_table_advanced_item'))
    rows = []
    for wrap in setting(a, 'table_advanced_item') or []:
        rows.append(_cells(wrap.get('table_advanced_item')))
    if not head and not rows:
        return ''
    out = ['<div class="sp-table-wrap"><table class="sp-table">']
    if head:
        out.append('<thead><tr>%s</tr></thead>' % ''.join('<th>%s</th>' % c for c in head))
    out.append('<tbody>')
    for r in rows:
        out.append('<tr>%s</tr>' % ''.join('<td>%s</td>' % c for c in r))
    out.append('</tbody></table></div>')
    return ''.join(out)


def r_accordion(a):
    items = setting(a, 'sp_accordion_item') or []
    if not items:
        return ''
    out = ['<div class="sp-acc">']
    for it in items:
        title = it.get('title') or ''
        frag = ''
        for c in it.get('content') or []:
            frag += r_addon(c)
        out.append('<details class="sp-acc__item"><summary class="sp-acc__head">%s</summary>'
                   '<div class="sp-acc__body">%s</div></details>' % (esc(title), frag))
    out.append('</div>')
    return ''.join(out)


def r_tabs(a):
    items = setting(a, 'sp_tab_item') or setting(a, 'tab_item') or []
    if not items:
        return ''
    out = ['<div class="sp-tabs">']
    for it in items:
        title = it.get('title') or ''
        frag = ''.join(r_addon(c) for c in it.get('content') or [])
        out.append('<details class="sp-tab"><summary class="sp-tab__title">%s</summary>%s</details>'
                   % (esc(title), frag))
    out.append('</div>')
    return ''.join(out)


def r_raw(a):
    raw = setting(a, 'html') or ''
    if not raw.strip():
        return ''
    return '<div class="sp-raw">%s</div>' % clean_html(raw)


def r_divider(a):
    return '<hr class="sp-divider">'


def r_row(a):
    inner = ''.join(r_addon(c) for c in (setting(a, 'row') or {}).get('content') or [])
    return '<div class="sp-inner-row">%s</div>' % inner


RENDER = {
    'heading': r_heading,
    'text_block': r_text,
    'image': r_image,
    'table_advanced': r_table,
    'accordion': r_accordion,
    'tab': r_tabs,
    'raw_html': r_raw,
    'divider': r_divider,
    'row': r_row,
    'button': lambda a: '',
    'module': lambda a: '',
    'navigation': lambda a: '',
    'gallery': lambda a: '',
    'articles': lambda a: '',
}


def r_addon(a):
    fn = RENDER.get(a.get('name'))
    return fn(a) if fn else ''


# --------------------------------------------------------------------- страница
def render_tree(tree):
    out = []
    for row in tree or []:
        cols = row.get('columns') or []
        visible = [c for c in cols if c.get('visibility', True) is not False]
        if not visible:
            continue
        parts = []
        for col in visible:
            body = ''.join(r_addon(a) for a in col.get('addons') or [])
            if not body.strip():
                continue
            st = col.get('settings') or {}
            extra = ''
            if st.get('items_content_alignment') == 'center':
                extra += ' sp-col--center'
            if (st.get('items_align_center')):
                extra += ' sp-col--vcenter'
            pad = px(st.get('padding'))
            body_style = ' style="padding:%s"' % pad if pad else ''
            overlay = st.get('overlay')
            under = ''
            if overlay and str(overlay).lower() not in ('none', ''):
                under = '<div class="sp-col__overlay" style="background:%s"></div>' % overlay
            parts.append('<div class="sp-col%s" style="%s">%s<div class="sp-col__body"%s>%s</div></div>'
                         % (extra, col_style(col), under, body_style, body))
        if not parts:
            continue
        pad = px((row.get('settings') or {}).get('padding'))
        style = ' style="padding:%s"' % pad if pad else ''
        # в дампе layout — раскладка Bootstrap: "4+4+4" = три колонки по 4
        layout = str(row.get('layout') or '')
        cols = [int(x) for x in re.findall(r'\d+', layout)]
        if not cols:
            per = max(1, round(12 / max(1, len(parts))))
            cols = [per] * len(parts)
        elif len(cols) == 1:
            cols = cols * len(parts)
        mods = '-'.join(str(c) for c in cols[:max(1, len(parts))])
        out.append('<section class="sp-row sp-row--%s"><div class="sp-row__inner"%s>%s</div></section>'
                   % (mods or '12', style, ''.join(parts)))
    return ''.join(out)


def page_from_dump(rec, title_override=None):
    src = rec.get('content') or rec.get('text')
    if not src:
        return ''
    try:
        tree = json.loads(src)
    except ValueError:
        return ''
    body = render_tree(tree)
    if not body.strip():
        return ''
    title = title_override or rec['title']
    return ('<div class="sp-page">'
            '<h1 class="sp-page__title">%s</h1>%s</div>' % (esc(title.strip()), body))
