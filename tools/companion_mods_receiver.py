#!/usr/bin/env python3
"""Convert Companion receiver mods to preview JSON and a cautious comparison.

Match book rows by normalized exact name only. A match is a candidate, not a
verified identity. Unsupported/missing values are kept visible in the report.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COMP = ROOT / 'data/weapon-book/companion'
PREFIXES = ROOT / 'data/weapon-book/mod-prefixes.ru.json'
EQUIP = COMP / 'i18n/ru-RU/data/equipment'
SYSTEM = COMP / 'i18n/ru-RU/data/system'
BOOK = ROOT / 'data/weapons/mods-receiver-sample.json'
FIELDS = ('damageModifier', 'fireRateModifier', 'rangeModifier', 'ammoOverride',
          'effectChanges', 'qualityChanges', 'damageTypeOverride')


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def index(path):
    return {x['id']: x['name'] for x in load(path)}


def norm(text):
    return re.sub(r'[^\w]+', '', text.casefold().replace('ё', 'е'))


def label(identifier, labels):
    return labels.get(identifier) or f'[{identifier}]'


def effect_text(mod, effects, qualities, ammo, damage_types=None):
    parts = []
    for key, name, unit in [('damageModifier', 'урон', ' DC'),
                            ('fireRateModifier', 'скорость стрельбы', ''),
                            ('rangeModifier', 'дистанция', ' зон')]:
        value = mod.get(key)
        if value is None:
            continue
        if not isinstance(value, dict) or 'value' not in value:
            parts.append(f'[{key}: {json.dumps(value, ensure_ascii=False)}]')
            continue
        op, n = value.get('op'), value['value']
        if key == 'rangeModifier' and op in ('+', '-') and n == 1:
            parts.append('Дистанция: ' + ('увеличить' if op == '+' else 'уменьшить') + ' на 1 зону')
        elif op == 'set':
            parts.append(f'{name.capitalize()}: установить {n}{unit}')
        elif op in ('+', '-'):
            parts.append(f'{name.capitalize()}: {op}{n}{unit}')
        else:
            parts.append(f'[{key}: {json.dumps(value, ensure_ascii=False)}]')
    if mod.get('ammoOverride'):
        parts.append('Патроны: ' + label(mod['ammoOverride'], ammo))
    if mod.get('damageTypeOverride'):
        override = mod['damageTypeOverride']
        if isinstance(override, dict) and override.get('op') in ('set', 'add') and isinstance(override.get('value'), (str, list)):
            raw_values = override['value'] if isinstance(override['value'], list) else [override['value']]
            types = ' и '.join(label(x, damage_types or {}) for x in raw_values)
            action = 'Установить' if override['op'] == 'set' else 'Добавить'
            parts.append(f'{action} тип урона: {types}')
        else:
            parts.append('[damageTypeOverride: ' + json.dumps(override, ensure_ascii=False) + ']')
    for key, labels, kind in [('effectChanges', effects, 'эффект'),
                              ('qualityChanges', qualities, 'качество')]:
        for change in mod.get(key) or []:
            op = {'gain': 'Добавить', 'remove': 'Убрать', 'lose': 'Убрать'}.get(change.get('op'))
            if op is None:
                parts.append(f'[{key}: {json.dumps(change, ensure_ascii=False)}]')
                continue
            name = label(change.get('id', '?'), labels)
            if change.get('value') is not None:
                name += ' ' + str(change['value'])
            parts.append(f'{op} {kind} «{name}»')
    return '; '.join(parts) if parts else 'Не указано'


def number(value):
    if value is None:
        return '?'
    if isinstance(value, (int, float)):
        return f'{value:+g}' if value else '0'
    return str(value)


def perks(mod):
    out = []
    for key in ('perk1', 'perk2'):
        value = mod.get(key)
        if value:
            value = re.sub(r'^Gun Nut\b', 'Фанатик оружия', value)
            out.append(value)
    if out:
        return ', '.join(out)
    return 'Не указано' if 'perk1' not in mod or 'perk2' not in mod else '—'


def generate(mods, names, effects, qualities, ammo, book, prefixes=None, damage_types=None):
    prefixes = prefixes or {}
    receivers = [x for x in mods if x.get('slot') == 'Receiver']
    by_name = {}
    for mod in receivers:
        by_name.setdefault(norm(names.get(mod['id'], mod['id'])), []).append(mod)
    converted = []
    entries = []
    for mod in receivers:
        name = names.get(mod['id'], f'[{mod["id"]}]')
        cells = [name, prefixes.get(mod['id']) or names.get(mod['id']) or 'Не указано', effect_text(mod, effects, qualities, ammo, damage_types),
                 number(mod.get('weight')), number(mod.get('cost')), perks(mod)]
        converted.append(cells)
        missing = [key for key in FIELDS if key not in mod]
        if 'weight' not in mod or mod['weight'] is None:
            missing.append('weight')
        if 'cost' not in mod or mod['cost'] is None:
            missing.append('cost')
        if 'perk1' not in mod or 'perk2' not in mod:
            missing.append('perk1/perk2')
        entries.append((mod, cells, missing))

    report = ['# Ресиверы: сравнение образца книги с Companion', '',
              'Это предварительное сопоставление только по точному нормализованному названию. '
              'Одинаковые названия не доказывают одинаковую модификацию. Различия приведены '
              'для ручной проверки; эталон автоматически не выбирается.', '',
              '«Не указано» и знак «?» означают, что значения нет в записи, а не что оно равно нулю '
              'или отсутствует в правилах. Пустые массивы изменений отличаются от отсутствующих полей. '
              'Префиксы взяты из отдельного рабочего файла; если записи нет — используется локализованное имя, как в Companion. '
              'В JSON используется обозначение DC; Unicode-рендерер заменяет его значком урона.', '',
              '## Строки образца книги', '']
    matched = set()
    for row in book['rows']:
        choices = by_name.get(norm(row[0]), [])
        report.append(f'### {row[0]}')
        report.append('')
        if len(choices) != 1:
            report.append('Совпадение не определено.' if not choices else
                          'Неоднозначное название: ' + ', '.join('`'+x['id']+'`' for x in choices) + '. Требуется ручная проверка.')
            report.append('')
            continue
        mod = choices[0]
        matched.add(mod['id'])
        item = next(x for x in entries if x[0]['id'] == mod['id'])
        report += [f'Кандидат по названию: `{mod["id"]}` (не подтверждён).', '',
                   '| Поле | Образец книги | Companion (интерпретация) |', '|---|---|---|']
        for field, left, right in zip(('Название', 'Префикс', 'Эффекты', 'Вес', 'Цена', 'Перки'), row, item[1]):
            def safe(x): return str(x or 'пусто').replace('|', '\\|').replace('\n', ' ')
            report.append(f'| {field} | {safe(left)} | {safe(right)} |')
        # Compare only unambiguous numeric/perk cells; semantic effect text is
        # deliberately left for review instead of pretending string equality.
        differences = []
        for column, name in ((1, 'префикс'), (3, 'вес'), (4, 'цена'), (5, 'перки')):
            original, comp_value = row[column].strip(), item[1][column].strip()
            if not original or comp_value in ('?', 'Не указано'):
                continue
            original = original.replace('–', '—').replace('-', '—') if original in ('–', '-', '—') else original
            if original != comp_value:
                differences.append(name)
        report += ['', 'Различия в сравнимых полях: ' + (', '.join(differences) if differences else 'не обнаружены')
                   + '. Эффекты требуют смысловой сверки вручную.',
                   'Не содержащиеся в записи поля: ' + (', '.join('`'+x+'`' for x in item[2]) or 'нет') + '.', '']
    report += ['## Остальные записи Companion без однозначного совпадения', '']
    for mod, cells, missing in entries:
        if mod['id'] not in matched:
            report.append(f'- {cells[0]} — `{mod["id"]}`; эффекты: {cells[2]}; '
                          f'вес: {cells[3]}; цена: {cells[4]}; перки: {cells[5]}. '
                          f'Не содержатся: {", ".join(missing) or "нет"}.')
    result = {'title': 'МОДИФИКАЦИИ СТРЕЛКОВОГО ОРУЖИЯ',
              'category': 'МОДИФИКАЦИИ РЕСИВЕРА',
              'source': 'Рабочая копия Companion и пользовательские префиксы; предварительная интерпретация',
              'rows': converted}
    return result, '\n'.join(report) + '\n'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out-json', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args(argv)
    localized = load(EQUIP / 'weapon_mods.json')
    prefix_candidates = {item['id']: item.get('prefix') or item.get('name', '')
                         for item in localized}
    prefix_candidates.update(load(PREFIXES))
    converted, report = generate(load(COMP / 'equipment/weapon_mods.json'),
        {item['id']: item['name'] for item in localized}, index(SYSTEM / 'damageEffects.json'),
        index(SYSTEM / 'qualities.json'), index(EQUIP / 'ammo/ammo_types.json'), load(BOOK), prefix_candidates,
        load(COMP / 'i18n/ru-RU/screens/addItemModal.json')['filter']['damageTypes'])
    for path in (args.out_json, args.report):
        path.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(converted, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    args.report.write_text(report, encoding='utf-8')
    print(f'{len(converted["rows"])} ресиверов; {args.out_json}; {args.report}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
