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


def mod_row(mod, labels):
    """Один мод: спойлер, внутри таблица «характеристика — значение»."""
    dmg = mod['damage']
    dmg_text = '—'
    if isinstance(dmg, dict):
        op = dmg.get('op')
        dmg_text = ('%s%s' % ('' if op == 'set' else (op or ''), dmg.get('value')))
    fr = mod['fireRate']
    fr_text = '—'
    if isinstance(fr, dict):
        fr_text = '%s%s' % (fr.get('op') or '', fr.get('value'))

    values = {
        'Урон': dmg_text,
        'Скорость': fr_text,
        'Патрон': mod['ammo'] or '—',
        'Сложность': mod['complexity'] if mod['complexity'] is not None else '—',
        'Перк': mod['perk'] or '—',
        'Цена': mod['cost'] if mod['cost'] is not None else '—',
        'Вес': mod['weight'] if mod['weight'] is not None else '—',
    }
    rows = ''.join('<tr><th scope="row">%s</th><td>%s</td></tr>' % (e(k), e(v))
                   for k, v in values.items())
    return ('<details class="wmod"><summary class="wmod__summary">%s</summary>'
            '<div class="wmod__body"><table class="wmod__table"><tbody>%s</tbody></table></div>'
            '</details>' % (e(mod['name']), rows))


def mods_block(group):
    """Слот модов: спойлер, внутри — спойлеры модов. Плюс таблица на div
    для широкого экрана (шапка = характеристики, строка = мод)."""
    mods = group['mods']
    return ('<details class="spoiler wmods-group"><summary class="spoiler__summary">%s '
            '<span class="wmods-group__count">(%d)</span></summary>'
            '<div class="spoiler__body">%s</div></details>'
            % (e(group['slotName']), len(mods),
               ''.join(mod_row(m, None) for m in mods)))


def mods_table_div(group):
    """Плоская таблица на div: на узком экране столбцы становятся колонками."""
    head = ('<div class="wmods__head">'
            '<div>Модификация</div><div>Урон</div><div>Скорость</div><div>Патрон</div>'
            '<div>Сложность</div><div>Перк</div><div>Цена</div><div>Вес</div></div>')
    rows = []
    for m in group['mods']:
        dmg = m['damage']
        dmg_text = '—'
        if isinstance(dmg, dict):
            op = dmg.get('op')
            dmg_text = '%s%s' % ('' if op == 'set' else (op or ''), dmg.get('value'))
        fr = m['fireRate']
        fr_text = '—'
        if isinstance(fr, dict):
            fr_text = '%s%s' % (fr.get('op') or '', fr.get('value'))
        cells = [
            ('Модификация', m['name']),
            ('Урон', dmg_text),
            ('Скорость', fr_text),
            ('Патрон', m['ammo'] or '—'),
            ('Сложность', m['complexity'] if m['complexity'] is not None else '—'),
            ('Перк', m['perk'] or '—'),
            ('Цена', m['cost'] if m['cost'] is not None else '—'),
            ('Вес', m['weight'] if m['weight'] is not None else '—'),
        ]
        rows.append('<div class="wmods__row">%s</div>' % ''.join(
            '<div class="wmods__cell"><span class="wmods__label">%s</span>%s</div>'
            % (e(label), e(value)) for label, value in cells))
    return '<div class="wmods">%s%s</div>' % (head, ''.join(rows))


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


def category_page(items, cat_title, cat_slug):
    """Список оружия категории плитками 3 в ряд."""
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
            '<div class="row g-3 tiles-row">%s</div>' % (e(cat_title), ''.join(tiles)))


ARROW = ('<svg viewBox="0 0 66 43" aria-hidden="true" class="tile__svg">'
         '<path d="M40.15 3.9 43.98.14a.66.66 0 0 1 .7 0l21.01 20.64a1 1 0 0 1 0 1.43'
         'L44.68 42.86a.66.66 0 0 1-.7 0l-3.83-3.75a.66.66 0 0 1 0-.71l16.84-16.54'
         'a.5.5 0 0 0 0-.71L40.15 4.61a.66.66 0 0 1 0-.71Z"/></svg>')
