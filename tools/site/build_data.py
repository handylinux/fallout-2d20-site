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


def load_json(rel):
    path = os.path.join(ROOT, rel)
    if not os.path.exists(path):
        return None
    with open(path, encoding='utf-8') as f:
        return json.load(f)


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


def main():
    write_origins()
    write_blog()
    items = weapons.load()
    cats = weapons.by_category(items)

    write('catalog.json', {
        'sections': [{
            'slug': 'oruzhie',
            'title': 'Оружие',
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
