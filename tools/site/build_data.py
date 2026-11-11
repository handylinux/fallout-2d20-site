"""Сборка данных для сайта: JSON справочника → docs/assets/data/*.json.

Страницы НЕ генерируются. Шаблон один (site/template.html), данные грузятся
в браузере, страницы подставляются по адресу (см. src/site/js/router.js).
Поэтому правка JSON + пересборка данных = обновление сайта, а карточки,
категории и хабы берутся из одних и тех же данных.
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import armor  # noqa: E402
import weapons  # noqa: E402

OUT = os.path.join(ROOT, 'docs', 'assets', 'data')


def write(name, payload):
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, name)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, separators=(',', ':'))
    print('%-22s %6.1f КБ' % (name, os.path.getsize(path) / 1024))


def dump(name, value):
    return '<script type="application/json" id="%s">%s</script>' % (
        name, json.dumps(value, ensure_ascii=False, separators=(',', ':')))


MOD_COLS = ['Модификация', 'Урон', 'Скорость', 'Патрон', 'Сложность', 'Перк', 'Цена', 'Вес']


def _op_text(mod, key):
    value = mod.get(key)
    if isinstance(value, dict):
        op = value.get('op')
        return '%s%s' % ('' if op == 'set' else (op or ''), value.get('value'))
    return '—'


def _mod_row(mod):
    """Строка мода: те же 8 колонок, что и в шапке (см. MOD_COLS)."""
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


def weapon_entry(item):
    """Одно оружие в виде, который ждёт шаблон карточки."""
    return {
        'kind': 'weapon',
        'view': 'weapon_item',
        'id': item['id'],
        'slug': item['slug'],
        'name': item['name'],
        'cat': item['category'][0],
        'catName': item['category'][1],
        'stats': [[label, value] for label, value in item['stats']],
        'image': item.get('image'),
        'search': ' '.join([item['name'], item['category'][1]] +
                           [str(v) for _k, v in item['stats']]),
        'flavour': item.get('flavour') or '',
        'notes': item.get('notes') or [],
        'mods': [{
            'slot': group['slotName'],
            'head': MOD_COLS,
            'rows': [_mod_row(mod) for mod in group['mods']],
        } for group in item.get('mod_groups') or []],
    }


def armor_section():
    """Раздел «Броня»: категории — наборы брони (Кожаная, Металлическая…)."""
    data = armor.build()
    detail = data.get('detail')
    categories = []
    # категории эталона: обычная / силовая
    plain = [i for i in data['items'] if i['slug'] not in ('karkas-silovoj-brony',)
             and 'silovaya-bronya' not in i['slug']]
    power = [i for i in data['items'] if i not in plain and i['slug'] != 'karkas-silovoj-brony']
    for slug, title, group in (
            ('obychnaya-bronya', 'Обычная броня', plain),
            ('silovaya-bronya', 'Силовая Броня', power)):
        items = []
        if slug == 'silovaya-bronya' and detail:
            items.append(armor_entry(detail, slug, title, '/bronya/' + slug + '/'))
        for item in group:
            items.append(armor_entry(item, slug, title))
        categories.append({'slug': slug, 'title': title, 'items': items})
    return {'slug': 'bronya', 'title': 'Броня', 'path': '/bronya',
            'categories': categories}


def armor_entry(item, cat_slug='obychnaya-bronya', cat_title='Броня', back=None):
    return {
        'kind': 'armor',
        'view': 'armor_item',
        'slug': item['slug'],
        'name': item['name'],
        'cat': 'bronya',
        'catName': 'Броня',
        'image': item.get('image'),
        'description': item.get('description'),
        'feature': item.get('feature'),
        'pieces': item.get('pieces') or [],
        'sections': item.get('sections') or [],
        'mods': item.get('mods') or [],
        'modHead': item.get('modHead'),
        'back': back or ('/bronya/' + cat_slug + '/'),
        'backText': 'Назад в категорию: ' + cat_title,
        'search': ' '.join([item['name'], 'Броня'] +
                           [p.get('area', '') for p in (item.get('pieces') or [])]),
    }


def load_json(rel):
    path = os.path.join(ROOT, rel)
    if not os.path.exists(path):
        return None
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def write_examples():
    """По одному примеру каждого вида: разные наборы характеристик и блоков.

    Это не «спецстраницы»: тот же шаблон, просто данные другой формы.
    """
    variants = load_json('data/variants.json')
    if variants:
        write('variants.json', variants)


def write_origins():
    """Происхождения: хаб (origins.json) и детали (origins.pages.json)."""
    hub = load_json('data/origins.json')
    if hub:
        write('origins.json', hub)
    pages = load_json('data/origins.pages.json')
    if pages:
        write('origins.pages.json', pages)


def write_blog():
    blog = load_json('data/blog.json')
    if blog:
        write('blog.json', blog)


def write_snaryazhenie():
    """Хаб «Снаряжение»: 9 плиток в порядке эталона (SPPB id 269, 3 ряда 4+4+4).
    У готовых разделов — путь, у будущих — ready:false (таблица показывает «скоро»)."""
    data = load_json('data/snaryazhenie.json') or {'title': 'Снаряжение', 'tiles': []}
    write('hub.json', data)


def main():
    write_snaryazhenie()
    write_origins()
    write_blog()
    write_examples()
    items = weapons.load()
    cats = weapons.by_category(items)

    write('catalog.json', {
        'sections': [armor_section(), {
            'slug': 'oruzhie',
            'title': 'Оружие',
            'path': '/snaryazhenie/oruzhie',
            'categories': [{
                'slug': cat_slug,
                'title': title,
                'items': [weapon_entry(i) for i in group],
            } for cat_slug, title, group in cats],
        }],
        'stats': {
            'weapons': len(items),
            'categories': len(cats),
        },
    })

    # поисковый индекс: одно плоское поле на элемент
    rows = []
    for item in items:
        words = [item['name'], item['category'][1]]
        words += [str(v) for _k, v in item['stats']]
        for group in item.get('mod_groups') or []:
            words.append(group['slotName'])
            words += [m['name'] for m in group['mods']]
        rows.append({
            'n': item['name'],
            'u': '/snaryazhenie/oruzhie/%s/%s/' % (item['category'][0], item['slug']),
            'c': item['category'][1],
            'd': item['damageText'].replace(' {/CD}', ''),
            's': ' '.join(words),
        })
    write('search.json', {'items': rows})

if __name__ == '__main__':
    main()
