#!/usr/bin/env python3
"""Conservative, reproducible comparison of weapon stats across saved sources.

Only unambiguous exact names/IDs are joined; a missing or ambiguous record
never votes. Numeric fields only: category, effects, qualities, mods and
source-specific variants require separate review.
"""
import argparse
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import re
import pymupdf

ROOT = Path(__file__).resolve().parent.parent
SOURCES = ROOT / 'data/weapon-audit/sources'
COMP = ROOT / 'data/companion/equipment/weapons.json'
RU = ROOT / 'data/companion/i18n/ru-RU/data/equipment/weapons/weapons.json'
FIELDS = ('damage', 'fireRate', 'weight', 'cost', 'rarity')
APPROVED = {('weapon_boarding_pistol', 'fireRate'): '0',
            ('weapon_pistol_injector', 'damage'): '4'}
APPLIED = {('weapon_tesla_rifle', 'damage'): '5',
           ('weapon_alien_disintegrator', 'fireRate'): '2',
           ('weapon_pistol_injector', 'fireRate'): '0',
           ('weapon_pistol_injector', 'damage'): '4',
           ('weapon_gauss_rifle', 'rarity'): '4',
           ('weapon_crossbow', 'fireRate'): '0',
           ('weapon_pulse_mine', 'damage'): '6',
           ('weapon_pulse_mine', 'cost'): '100',
           ('weapon_gamma_gun', 'cost'): '156'}
FILES = {'pipboy': 'weapons.json', 'lonestar': 'lonestar_weapons.json',
         'focharactersheet': 'focharactersheet_weapons.json', 'pipboy3000': 'pipboy3000_weapons.json'}
KEYS = {'pipboy': {'damage': 'damageRating', 'fireRate': 'fireRate', 'weight': 'weight', 'cost': 'cost', 'rarity': 'rarity'},
        'lonestar': {'damage': 'damageRating', 'fireRate': 'fireRate', 'weight': 'weight', 'cost': 'cost', 'rarity': 'rarity'},
        'focharactersheet': {'damage': 'damage', 'fireRate': 'fire_rate', 'weight': 'weight', 'cost': 'cost', 'rarity': 'rarity'},
        'pipboy3000': {'damage': 'DAMAGE_RATING', 'fireRate': 'FIRE_RATE', 'weight': 'WEIGHT', 'cost': 'COST', 'rarity': 'RARITY'}}


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def namekey(value):
    return re.sub(r'\s+', ' ', str(value or '').strip().casefold().replace('ё', 'е'))


def idkey(value):
    return re.sub(r'[^a-z0-9]', '', str(value or '').lower())


def number(value, source='', field=''):
    if value is None or isinstance(value, bool):
        return None
    text = str(value).strip().replace(',', '.')
    if source == 'pipboy' and field == 'damage':
        text = re.sub(r'\s*БК$', '', text, flags=re.I)
    # No arithmetic, inequalities or dash-as-zero; preserve uncertainty.
    if not re.fullmatch(r'\d+(?:\.\d+)?', text):
        return None
    try:
        return format(Decimal(text).normalize(), 'f')
    except InvalidOperation:
        return None


def unique_index(rows, key):
    index = defaultdict(list)
    for row in rows:
        value = key(row)
        if value:
            index[value].append(row)
    return {key: rows[0] for key, rows in index.items() if len(rows) == 1}


def stat_cells(page):
    """Read integer cells only if exactly one geometric match is available."""
    words = page.get_text('words')
    result = {}
    for label, field in (('УРОН', 'damage'), ('СКОРОСТЬ', 'fireRate')):
        headings = [word for word in words if word[4] == label and 290 <= word[1] < 350]
        if len(headings) != 1:
            continue
        heading = headings[0]
        matches = [word[4] for word in words if re.fullmatch(r'\d+', word[4])
                   and 340 <= word[1] <= 390
                   and abs((word[0] + word[2] - heading[0] - heading[2]) / 2) < 30]
        if len(matches) == 1:
            result[field] = matches[0]
    return result


def original_pdf_values():
    """Extract explicit printed header values only; no inferred numeric cells."""
    paths = read(ROOT / 'data/weapon-audit/original-page-map.json')
    result = {}
    pattern = re.compile(r'Вес:\s*([^,\n]+),\s*Цена:\s*([^,\n]+),\s*Редкость:\s*([^\n]+)', re.I)
    with pymupdf.open(ROOT / 'Справочник оружия.pdf') as pdf:
        for wid, page in paths.items():
            matches = pattern.findall(pdf[page-1].get_text())
            if len(matches) != 1:
                continue
            weight, cost, rarity = matches[0]
            result[wid] = {'weight': number(weight), 'cost': number(cost),
                           'rarity': number(rarity), 'page': page, **stat_cells(pdf[page-1])}
    return result


def run():
    weapons = read(COMP)
    original = original_pdf_values()
    site = read(ROOT / 'data/weapon-audit/site-observations.json')
    names = {r['id']: r.get('name', '') for r in read(RU)}
    refs = {source: read(SOURCES / file) for source, file in FILES.items()}
    external = read(ROOT / 'data/weapon-audit/external-observations.json')
    indexes = {'pipboy': unique_index(refs['pipboy'], lambda x: namekey(x.get('name_ru'))),
               'lonestar': unique_index(refs['lonestar'], lambda x: namekey(x.get('name_en'))),
               'focharactersheet': unique_index(refs['focharactersheet'], lambda x: namekey(x.get('name_en'))),
               'pipboy3000': unique_index(refs['pipboy3000'], lambda x: idkey(x.get('ID')))}
    english = Counter(namekey(w.get('imageName')) for w in weapons if w.get('imageName'))
    russian = Counter(namekey(names.get(w['id'])) for w in weapons if names.get(w['id']))
    matched = Counter()
    output = []
    comparisons = []
    for weapon in weapons:
        wid = weapon['id']
        ru = namekey(names.get(wid))
        en = namekey(weapon.get('imageName'))
        matches = {'pipboy': indexes['pipboy'].get(ru) if russian[ru] == 1 else None,
                   'lonestar': indexes['lonestar'].get(en) if english[en] == 1 else None,
                   'focharactersheet': indexes['focharactersheet'].get(en) if english[en] == 1 else None,
                   'pipboy3000': indexes['pipboy3000'].get(idkey(wid))}
        for source, row in matches.items():
            if row is not None:
                matched[source] += 1
        for field in FIELDS:
            votes = {}
            base = number(weapon.get(field), 'companion', field)
            if base is not None:
                votes['companion'] = base
            site_value = number(site.get(wid, {}).get(field))
            if site_value is not None:
                votes['site'] = site_value
            for source_name, values in external.get(wid, {}).items():
                external_value = number(values.get(field))
                if external_value is not None:
                    votes[source_name] = external_value
            pdf_value = original.get(wid, {}).get(field)
            if pdf_value is not None:
                votes['original_pdf'] = pdf_value
            for source, row in matches.items():
                if row is not None:
                    # This dataset systematically reports half-weight values;
                    # do not assume a unit conversion without its specification.
                    if source == 'pipboy3000' and field == 'weight':
                        continue
                    val = number(row.get(KEYS[source][field]), source, field)
                    if val is not None:
                        votes[source] = val
            counts = Counter(votes.values())
            rank = counts.most_common()
            if not rank:
                comparisons.append({'weapon_id': wid, 'field': field, 'votes': votes, 'status': 'no_data'})
                continue
            tied = len(rank) > 1 and rank[0][1] == rank[1][1]
            # Require strict majority and at least three sources. This is only
            # a provisional vote, not a verified truth or an automatic edit.
            winner = rank[0][0] if not tied and len(votes) >= 3 and rank[0][1] > len(votes) / 2 else None
            record = {'weapon_id': wid, 'name_ru': names.get(wid, ''), 'field': field,
                           'votes': votes, 'counts': dict(counts), 'majority': winner,
                           'status': ('agreement' if len(counts) == 1 else 'provisional_majority' if winner is not None else 'review'),
                           'website': site.get(wid, {}).get('url'), 'original_pdf_page': original.get(wid, {}).get('page'), 'errata': 'not_checked'}
            if (wid, field) in APPLIED:
                record['book_value'] = APPLIED[(wid, field)]
            if (wid, field) in APPROVED:
                record['approved_by_user'] = APPROVED[(wid, field)]
                record['status'] = 'approved_by_user'
            comparisons.append(record)
            if len(counts) > 1:
                output.append(record)
    return {'version': 1, 'reference_commit': '2e66c7dc7c07d1fe1e62b1585e8764f453417193',
            'weapon_count': len(weapons), 'pdf_headers_extracted': len(original), 'site_records': len(site), 'fields': list(FIELDS), 'matched': dict(matched), 'comparisons': comparisons, 'differences': output}


def render(data):
    diffs = data['differences']
    labels = {'damage': 'Урон', 'fireRate': 'Скорострельность', 'weight': 'Вес', 'cost': 'Цена', 'rarity': 'Редкость'}
    lines = ['# Сверка оружия: предварительный машинный аудит', '',
             'Это не глобальная сверка всех источников: первичная эррата, моды, эффекты, качества, боеприпасы и категории здесь не проверены. Сайт сверён лишь для части предметов; остальные не голосуют. Из исходного PDF извлечены вес, цена, редкость и однозначно читаемые числовые ячейки урона и скорострельности. Сопоставление колонок по геометрии требует проверки по исходным страницам. Совпадение точных названий и ID не доказывает идентичность варианта; для публикации требуется проверка. Этот скрипт не меняет PDF или JSON оружия; отдельно отмечены известные применённые поправки, а для остальных применение ещё не проверено.', '',
             'Вес Pip-Boy 3000 не участвует: значения систематически вдвое меньше; единицы не подтверждены. Преобразование без проверки не выполняется.', '',
             'Голосование: уникальное большинство строго более половины доступных числовых голосов и минимум три источника; меньшее покрытие и ничьи — на ручную проверку. Отсутствующее, неопознанное и неоднозначное значение не голосует; прочерк, «<1» и выражения вроде «6+1» не подменяются числом. Зафиксированные решения пользователя имеют приоритет. Разные проекты могут использовать общий первоисточник; это голоса записей, не доказательство независимости.', '',
             f"Обработано записей Companion: {data['weapon_count']}; заголовков PDF извлечено: {data['pdf_headers_extracted']}; страниц сайта вручную сверено: {data['site_records']}. Точные однозначные сопоставления: "+', '.join(f'{k}: {v}' for k,v in sorted(data['matched'].items()))+'.',
             f"Расходящихся полей: {len(diffs)}; предварительное большинство: {sum(x['majority'] is not None for x in diffs)}; остальные — без решения.", '',
             'Источники сайта (включая локальный дамп) — в `data/weapon-audit/site-observations.json`, внешние транскрипции — в `data/weapon-audit/external-observations.json`. Подтверждённые решения пользователя, например скорострельность абордажного пистолета 0, не отменяются большинством.', '',
             'Полный машиночитаемый список с голосами: `data/weapon-audit/numeric-audit.json`. Источники и версии: `data/weapon-audit/sources/README.md`, фиксированный коммит '+data['reference_commit']+'.', '',
             '| ID | Поле | Голоса по источникам | Предварительный результат |', '|---|---|---|---|']
    for row in diffs:
        votes = '; '.join(f'{k}' + (f' стр.{row["original_pdf_page"]}' if k == 'original_pdf' else '') + f': {v}' for k, v in row['votes'].items())
        result = ('согласовано пользователем: '+row['approved_by_user']) if 'approved_by_user' in row else (('большинство '+row['majority'] + (' — в сборке' if row.get('book_value') == row['majority'] else ' — не проверено применение')) if row['majority'] is not None else '**проверить**')
        lines.append(f"| `{row['weapon_id']}` ({row['name_ru']}) | {labels[row['field']]} | {votes} | {result} |")
    return '\n'.join(lines)+'\n'


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path, default=ROOT / 'data/weapon-audit/numeric-audit.json')
    p.add_argument('--report', type=Path, default=ROOT / 'docs/weapon-source-numeric-audit.md')
    args = p.parse_args()
    data = run()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    args.report.write_text(render(data), encoding='utf-8')
    print(f"{len(data['differences'])} differences; matches {data['matched']}")

if __name__ == '__main__':
    main()
