"""Броня: данные компаньона → структуры для шаблона.

Страница брони повторяет образец
https://www.fallout-2d20.ru/bronya/silovaya-bronya/ekskavatornaya-silovaya-bronya:
  назад в категорию → картинка → «ШЛЕМ / ТЕЛО / РУКИ / НОГИ» таблицами
  → описание → «Особенность» → свои блоки (таблицы, спойлеры)
  → «Поддерживаемые модификации»: слот → div-таблица
     {Модификация, Эффект, Часть брони, Вес, Цена, Перки, Навык}.

Ключевое: количество частей и колонок — из данных, не из шаблона.
"""

import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
SRC_JSON = os.path.join(ROOT, 'data', 'source')

AREAS = {
    'Head': 'ШЛЕМ',
    'Body': 'ТЕЛО',
    'Hand': 'РУКИ',
    'Leg': 'НОГИ',
    'FullBody': 'ВСЁ ТЕЛО',
}
TIERS = {'standard': '', 'sturdy': 'Прочная ', 'heavy': 'Тяжёлая '}
RARITY = {0: 'Обычное', 1: 'Необычное', 2: 'Редкое', 3: 'Очень редкое',
          4: 'Легендарное', 5: 'Уникальное'}
SKILLS = {
    'REPAIR': 'Ремонт', 'SCIENCE': 'Наука', 'SNEAK': 'Скрытность',
    'SMALL_GUNS': 'Стрелковое оружие',
}

MOD_COLS = ['Модификация', 'Эффект', 'Часть брони', 'Вес', 'Цена', 'Перки', 'Навык']


def _load(name):
    path = os.path.join(SRC_JSON, name)
    if not os.path.exists(path):
        return None
    with open(path, encoding='utf-8') as f:
        return json.load(f)


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


def _stat_rows(piece):
    """Строки характеристик одной части брони — ровно те, что есть в данных."""
    rows = [['ФИЗ. СУ', piece.get('physicalDamageRating')],
            ['ЭНРГ. СУ', piece.get('energyDamageRating')],
            ['РАД. СУ', piece.get('radiationDamageRating')]]
    if piece.get('durability') is not None:
        rows.append(['ПРОЧНОСТЬ', piece['durability']])
    rows += [['ВЕС', piece.get('weight')], ['ЦЕНА', piece.get('cost')],
             ['РЕДКОСТЬ', RARITY.get(piece.get('rarity'), piece.get('rarity'))]]
    return [[k, '—' if v is None else v] for k, v in rows]


def load_sets():
    """Обычная броня: 6 наборов × 3 класса прочности → «элемент» = набор."""
    armor = _load('armor.json') or {}
    ru = (_load('armor.ru.json') or {}).get('armor') or []
    names = {}
    for group in ru:
        for item in group.get('items') or []:
            names[item['id']] = item.get('name')
    items = []
    for key, setdata in armor.items():
        ru_group = next((g for g in ru if g.get('categoryKey') == key), None)
        title = (ru_group or {}).get('type') or key
        pieces = []
        for tier, tierdata in (setdata.get('tiers') or {}).items():
            for piece in tierdata.get('pieces') or []:
                piece = dict(piece)
                piece['name'] = names.get(piece['id']) or piece.get('imageName') or piece['id']
                piece['tier'] = tier
                piece['tierName'] = TIERS.get(tier, '')
                piece['areaName'] = ', '.join(AREAS.get(a, a) for a in piece.get('protectedAreas') or [])
                piece['stats'] = _stat_rows(piece)
                piece['slug'] = slug(piece['name'])
                pieces.append(piece)
        items.append({
            'kind': 'armor',
            'slug': slug(title),
            'name': title,
            'category': ('bronya', 'Броня'),
            'pieces': pieces,
            'modCategories': setdata.get('allowedModCategories') or [],
        })
    return items


def load_power_armor():
    """Силовая броня: у набора части с одним id-префиксом на костюм."""
    data = _load('power_armor.json') or {}
    items = []
    for key, setdata in data.items():
        pieces = []
        for piece in setdata.get('pieces') or []:
            piece = dict(piece)
            piece['areaName'] = ', '.join(AREAS.get(a, a) for a in piece.get('protectedAreas') or [])
            piece['stats'] = _stat_rows(piece)
            pieces.append(piece)
        title = 'Силовая броня: ' + key
        if key == 'frame':
            title = 'Каркас силовой брони'
        if key in ('raiderPower', 't45', 't51', 't60', 'x01'):
            titles = {'raiderPower': 'Рейдерская силовая броня', 't45': 'Силовая броня T-45',
                      't51': 'Силовая броня T-51', 't60': 'Силовая броня T-60',
                      'x01': 'Силовая броня X-01'}
            title = titles[key]
        items.append({
            'kind': 'armor',
            'slug': slug(title),
            'name': title,
            'category': ('bronya', 'Броня'),
            'pieces': pieces,
            'modCategories': ['powerArmorMods'],
        })
    return items


def load_detail_example():
    """Разобранный по образцу пример: экскаваторная силовая броня.

    Данных этого костюма в компаньоне нет — он живёт в data/armor_detail.json,
    полностью по структуре эталона (4 части, особенность, свой блок про добычу
    с таблицей, 18 модификаций). Правь json — страница обновится.
    """
    return _load('armor_detail.json')


def build():
    sets = load_sets() + load_power_armor()
    return {'items': sets, 'detail': load_detail_example()}
