"""Страницы оружия из данных приложения-компаньона.

Источник данных — data/source/*.json (копии из
github.com/rpg-companios/Fallout-2d20-companion):
  weapons.json, weapons.ru.json          — оружие (EN-механика + RU-текст)
  weapon_mods.json, weapon_mods.ru.json  — модификации
  weapon_mod_slots.json                  — какие моды к какому оружию
  qualities.ru.json, damage_effects.ru.json, ammo.ru.json — справочники RU

Страница оружия повторяет образец:
  «Назад в категорию» → H2 название → две колонки:
    слева картинка, справа таблица характеристик (чёрные th, бежевые td);
  описание (flavour), примечание, затем модификации по слотам (спойлеры).
"""

import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
SRC_JSON = os.path.join(ROOT, 'data', 'source')

# ------------------------------------------------------------------ справочники
SKILLS = {
    'SMALL_GUNS': 'Стрелковое оружие',
    'BIG_GUNS': 'Тяжёлое оружие',
    'ENERGY_WEAPONS': 'Энергетическое оружие',
    'MELEE_WEAPONS': 'Холодное оружие',
    'UNARMED': 'Без оружия',
    'EXPLOSIVES': 'Взрывчатка',
    'THROWING': 'Метательное',
}
WEAPON_TYPES = {
    'Light': 'Лёгкое',
    'Heavy': 'Тяжёлое',
    'Energy': 'Энергетическое',
    'Melee': 'Ближнего боя',
    'Unarmed': 'Без оружия',
    'Explosive': 'Взрывное',
    'Thrown': 'Метательное',
}
DAMAGE_TYPES = {
    'physical': 'Физический',
    'energy': 'Энергетический',
    'radiation': 'Радиация',
    'poison': 'Яд',
    'special': 'Особый',
}
SLOTS = {
    'Receiver': 'Ресивер',
    'Barrel': 'Ствол',
    'Muzzle': 'Дуло',
    'Stock': 'Ложе',
    'Magazine': 'Магазин',
    'Sight': 'Прицел',
    'Grip': 'Рукоять',
    'Capacitor': 'Конденсатор',
    'Nozzle': 'Сопло',
    'Tank': 'Бак',
    'Frame': 'Каркас',
    'Container': 'Контейнер',
    'Winch': 'Лебёдка',
    'Launcher': 'Пусковая установка',
    'Canister': 'Канистра',
    'Fuel': 'Топливо',
    'Camera': 'Камера',
    'Concentrate': 'Концентрат',
    'Dish': 'Антенна',
    'Unique': 'Уникальное',
}
RARITY_WORDS = {0: 'Обычное', 1: 'Необычное', 2: 'Редкое', 3: 'Очень редкое',
                4: 'Легендарное', 5: 'Уникальное', 6: 'Уникальное'}

# категория = навык + тип ствола, порядок важен
CATEGORIES = [
    ('strelkovoe-oruzhie', 'Стрелковое оружие', ('SMALL_GUNS',)),
    ('tyazhjoloe-oruzhie', 'Тяжёлое оружие', ('BIG_GUNS',)),
    ('energeticheskoe-oruzhie', 'Энергетическое оружие', ('ENERGY_WEAPONS',)),
    ('kholodnoe-oruzhie', 'Холодное оружие', ('MELEE_WEAPONS',)),
    ('bez-oruzhiya', 'Без оружия', ('UNARMED',)),
    ('vzryvchatka', 'Взрывчатка', ('EXPLOSIVES',)),
    ('metatelnoe', 'Метательное', ('THROWING',)),
]

TRANSLIT = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e', 'ж': 'zh',
    'з': 'z', 'и': 'i', 'й': 'j', 'к': 'k', 'л': 'l', 'м': 'm', 'н': 'n', 'о': 'o',
    'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u', 'ф': 'f', 'х': 'kh', 'ц': 'ts',
    'ч': 'ch', 'ш': 'sh', 'щ': 'shch', 'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e',
    'ю': 'yu', 'я': 'ya',
}


def slug(text):
    text = (text or '').lower()
    out = ''.join(TRANSLIT.get(ch, ch) for ch in text)
    out = re.sub(r'[^a-z0-9]+', '-', out)
    return re.sub(r'-{2,}', '-', out).strip('-')


def _load(name):
    path = os.path.join(SRC_JSON, name)
    if not os.path.exists(path):
        return []
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def _dict_by_id(rows):
    return {row['id']: row for row in rows}


# ----------------------------------------------------------------------- данные
def load():
    """Собирает оружие, моды и справочники в готовые структуры."""
    weapons = _load('weapons.json')
    weapons_ru = _dict_by_id(_load('weapons.ru.json'))
    mods = _load('weapon_mods.json')
    mods_ru = _dict_by_id(_load('weapon_mods.ru.json'))
    slots_map = _load('weapon_mod_slots.json') or {}
    qualities = {r['id']: r.get('name') for r in _load('qualities.ru.json')}
    effects = {r['id']: r.get('name') for r in _load('damage_effects.ru.json')}
    ammo = {r['id']: r.get('name') for r in _load('ammo.ru.json')}

    mods_by_weapon = {}
    for mod in mods:
        for wid in mod.get('applies_to_ids') or []:
            mods_by_weapon.setdefault(wid, []).append(mod)

    items = []
    for w in weapons:
        ru = weapons_ru.get(w['id']) or {}
        name = (ru.get('name') or w.get('imageName') or w['id']).strip()
        item = dict(w)
        item['name'] = name
        item['slug'] = slug(name)
        item['rangeName'] = ru.get('rangeName') or ''
        item['flavour'] = clean_flavour(ru.get('flavour') or '')
        item['category'] = category_of(w)
        # характеристики
        dmg = w.get('damage')
        dtypes = w.get('damageType')
        if isinstance(dtypes, str):
            dtypes = [dtypes]
        item['damageTypeName'] = ', '.join(DAMAGE_TYPES.get(d, d) for d in (dtypes or []))
        item['damageType'] = DAMAGE_TYPES.get(dtypes[0], '') if dtypes else ''
        item['damageText'] = ('%s {/CD}' % dmg) if dmg not in (None, '') else '—'
        item['ammoName'] = ammo.get(w.get('ammoId') or '', '') or '—'
        item['effectName'] = ', '.join(
            effects.get(e.get('effectId'), e.get('effectId')) for e in (w.get('effects') or [])) or '—'
        item['qualityName'] = ', '.join(
            qualities.get(q.get('qualityId'), q.get('qualityId')) for q in (w.get('qualities') or [])) or '—'
        item['rarityName'] = RARITY_WORDS.get(w.get('rarity'), '—')
        item['skillName'] = SKILLS.get(w.get('mainSkill'), '')
        item['typeName'] = WEAPON_TYPES.get(w.get('weaponType'), '')
        # моды по слотам (порядок как в weapon_mod_slots.json, если есть)
        ordered = slots_map.get(w['id']) or {}
        grouped = {}
        for mod in mods_by_weapon.get(w['id'], []):
            slot = mod.get('slot') or 'Unique'
            grouped.setdefault(slot, []).append(mod)
        item['mod_groups'] = []
        for slot in list(ordered) + [s for s in grouped if s not in ordered]:
            group = grouped.get(slot)
            if not group:
                continue
            item['mod_groups'].append({
                'slot': slot,
                'slotName': SLOTS.get(slot, slot),
                'mods': [{
                    'name': (mods_ru.get(m['id']) or {}).get('name') or m['id'],
                    'damage': m.get('damageModifier'),
                    'fireRate': m.get('fireRateModifier'),
                    'ammo': ammo.get(m.get('ammoOverride') or '', ''),
                    'complexity': m.get('complexity'),
                    'perk': ', '.join(p for p in (m.get('perk1'), m.get('perk2')) if p),
                    'cost': m.get('cost'),
                    'weight': m.get('weight'),
                    'rarity': RARITY_WORDS.get(m.get('rarity'), m.get('rarity') or ''),
                    'materials': m.get('materials') or '',
                } for m in group],
            })
        items.append(item)
    items.sort(key=lambda i: i['name'].lower())
    return items


def clean_flavour(text):
    """В русском файле flavour — английский текст с вклейками перевода."""
    text = re.sub(r'<[^>]+>', ' ', text or '')
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def category_of(w):
    skill = w.get('mainSkill')
    for cat_slug, title, skills in CATEGORIES:
        if skill in skills:
            return (cat_slug, title)
    return ('oruzhie', 'Оружие')


def by_category(items):
    """{слаг категории: (название, [оружие])} в заданном порядке."""
    out = []
    for cat_slug, title, skills in CATEGORIES:
        group = [i for i in items if i['category'][0] == cat_slug]
        if group:
            out.append((cat_slug, title, group))
    rest = [i for i in items if i['category'][0] == 'oruzhie']
    if rest:
        out.append(('oruzhie', 'Оружие', rest))
    return out


def note_for(item):
    """Примечание под описанием — из данных, если есть что сказать."""
    notes = []
    if item.get('hasStockVariant'):
        notes.append('Вы не можете взять одновременно рукоять и ложе: любая '
                     'модификация ложа меняет тип оружия с «Пистолет» на «Карабин».')
    if not item.get('mod_groups'):
        notes.append('Модификаций для этого оружия в справочнике нет.')
    return notes
