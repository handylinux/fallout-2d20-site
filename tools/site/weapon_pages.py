"""Разметка страниц оружия: карточка оружия, категория, хаб «Снаряжение».

Отдельно от build_site.py, потому что это уже контент, а не каркас:
каркас (page(), секции, строки) берётся из build_site.
"""

import html

import weapons

TAB_LABELS = [
    ('ammoName', 'ТИП ПАТРОНА'),
    ('damageTypeName', 'ТИП УРОНА'),
    ('damageText', 'УРОН'),
    ('effectName', 'ЭФФЕКТ'),
    ('fireRate', 'СКОРОСТЬ СТРЕЛЬБЫ'),
    ('rangeName', 'ДИСТАНЦИЯ'),
    ('qualityName', 'КАЧЕСТВА'),
    ('weight', 'ВЕС'),
    ('cost', 'ЦЕНА'),
    ('rarityName', 'РЕДКОСТЬ'),
]


def e(value):
    return html.escape(str(value if value is not None else ''), quote=True)


def stats_table(item):
    """Таблица характеристик: чёрные заголовки, бежевые значения."""
    rows = []
    for key, label in TAB_LABELS:
        value = item.get(key)
        if value in (None, ''):
            value = '—'
        rows.append((label, value))
    body = ''.join(
        '<tr><th scope="row">%s</th><td>%s</td></tr>' % (e(label), e(value))
        for label, value in rows)
    return ('<table class="wstats"><tbody>%s</tbody></table>' % body)


MOD_COLS = ['Модификация', 'Урон', 'Скорость', 'Патрон', 'Сложность', 'Перк', 'Цена', 'Вес']


def _op_text(mod, key):
    value = mod.get(key)
    if isinstance(value, dict):
        op = value.get('op')
        return '%s%s' % ('' if op == 'set' else (op or ''), value.get('value'))
    return '—'


def mod_values(mod):
    return [
        mod['name'],
        _op_text(mod, 'damage'),
        _op_text(mod, 'fireRate'),
        mod['ammo'] or '—',
        mod['complexity'] if mod['complexity'] is not None else '—',
        mod['perk'] or '—',
        mod['cost'] if mod['cost'] is not None else '—',
        mod['weight'] if mod['weight'] is not None else '—',
    ]


def mod_row(mod):
    """Одна строка мода. На ПК — 8 колонок таблицы, на мобильном — 2 колонки
    (название характеристики | значение), для чего у каждой ячейки есть подпись."""
    cells = ''.join(
        '<div class="wmods__c"><span class="wmods__label">%s</span>%s</div>'
        % (e(col), e(value)) for col, value in zip(MOD_COLS, mod_values(mod)))
    return '<div class="wmods__row">%s</div>' % cells


def mods_block(group):
    """Слот модов — спойлер; внутри div-таблица: шапка + строки модов."""
    head = ''.join('<div>%s</div>' % e(c) for c in MOD_COLS)
    rows = ''.join(mod_row(m) for m in group['mods'])
    return ('<details class="spoiler wmods-group"><summary class="spoiler__summary">%s '
            '<span class="wmods-group__count">(%d)</span></summary>'
            '<div class="spoiler__body wmods">'
            '<div class="wmods__head">%s</div>%s'
            '</div></details>'
            % (e(group['slotName']), len(group['mods']), head, rows))


def card(item, back_url=None, back_title=None, img_url=None):
    """Страница оружия по образцу."""
    cat_slug, cat_title = item['category']
    back_href = back_url or '/snaryazhenie/oruzhie/%s/' % cat_slug
    back_text = back_title or (u'Назад в категорию: ' + cat_title)

    picture = ('<img class="wcard__img" src="%s" alt="%s">' % (e(img_url), e(item['name']))
               if img_url else '')
    left = ('<div class="wcard__media%s">%s</div>'
            % ('' if picture else ' wcard__media--empty', picture))

    notes = weapons.note_for(item)
    note_html = ''.join(
        '<h2 class="wcard__sub">Примечание</h2><p class="wcard__note">%s</p>' % e(n)
        for n in notes)

    mods_html = ''
    if item['mod_groups']:
        blocks = [mods_block(g) for g in item['mod_groups']]
        mods_html = ('<section class="wcard__mods"><h2 class="wcard__sub">Модификации</h2>%s</section>'
                     % ''.join(blocks))

    flavour = ('<p class="wcard__text">%s</p>' % e(item['flavour'])) if item['flavour'] else ''

    return ('<p class="wcard__back"><a href="%s">%s</a></p>'
            '<h2 class="wcard__title">%s</h2>'
            '<div class="wcard">'
            '<div class="wcard__row">%s<div class="wcard__stats">%s</div></div>'
            '%s%s%s'
            '</div>' % (e(back_href), e(back_text), e(item['name']),
                        left, stats_table(item), flavour, note_html, mods_html))


def _mods_words(item):
    """Все моды оружия одной строкой — для поиска."""
    words = []
    for group in item.get('mod_groups') or []:
        words.append(group['slotName'])
        for mod in group['mods']:
            words.append(mod['name'])
    return ' '.join(words)


SEARCH_FIELDS = (
    'name', 'skillName', 'typeName', 'damageTypeName', 'ammoName',
    'effectName', 'qualityName', 'rangeName', 'rarityName',
)


def search_index(items):
    """Индекс поиска: те же json, что и страницы. Отдаётся одним файлом."""
    import json
    rows = []
    for item in items:
        catslug = item['category'][0]
        rows.append({
            'n': item['name'],
            'u': '/snaryazhenie/oruzhie/%s/%s/' % (catslug, item['slug']),
            'c': item['category'][1],
            'd': item['damageText'].replace(' {/CD}', ''),
            's': [item.get(f) or '' for f in SEARCH_FIELDS] + [_mods_words(item)],
        })
    rows.sort(key=lambda r: r['n'].lower())
    return json.dumps({'items': rows}, ensure_ascii=False, separators=(',', ':'))


def search_box():
    return ('<div class="site-search">'
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


def category_page(items, cat_title, cat_slug):
    """Список оружия категории плитками 3 в ряд — целиком из json."""
    tiles = []
    for item in items:
        tiles.append(
            '<div class="col-12 col-md-6 col-lg-4">'
            '<a class="tile" href="/snaryazhenie/oruzhie/%s/%s/">'
            '<h2 class="tile__title">%s</h2>'
            '<div class="tile__media tile__media--empty"></div>'
            '<div class="tile__arrow">%s</div></a></div>'
            % (cat_slug, item['slug'], e(item['name']), ARROW))
    return ('<p class="wcard__back"><a href="/snaryazhenie/">Назад в снаряжение</a></p>'
            '<h1 class="page__title">%s</h1>'
            '<p class="page__lead">%d единиц оружия в категории.</p>'
            '<div class="row g-3 tiles-row">%s</div>'
            % (e(cat_title), len(items), ''.join(tiles)))


ARROW = ('<svg viewBox="0 0 66 43" aria-hidden="true" class="tile__svg">'
         '<path d="M40.15 3.9 43.98.14a.66.66 0 0 1 .7 0l21.01 20.64a1 1 0 0 1 0 1.43'
         'L44.68 42.86a.66.66 0 0 1-.7 0l-3.83-3.75a.66.66 0 0 1 0-.71l16.84-16.54'
         'a.5.5 0 0 0 0-.71L40.15 4.61a.66.66 0 0 1 0-.71Z"/></svg>')
