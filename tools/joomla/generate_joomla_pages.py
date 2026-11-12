#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_joomla_pages.py — массовая генерация SPPB-страниц для Joomla из JSON.

Зачем: страницы оружия/модов/патронов/качеств в Joomla — это по сути
одна и та же вёрстка (заголовок-категория → картинка + текст → таблица
статов), различающаяся только данными. Руками это сотни страниц.

Что делает скрипт:
  1. Берёт "эталонную" страницу из выгрузки jos_sppagebuilder (SPPB-раскладка
     реальной страницы оружия) — она служит шаблоном.
  2. Подставляет в её JSON данные из data/source/*.json (статы, названия,
     картинку, качества, эффекты, боекомплект).
  3. Складывает результат двумя способами:
       --mode sql    → готовый .sql (INSERT для jos_sppagebuilder) + отчёт
       --mode json   → файлы SPPB-JSON для импорта через CLI/API по одному
       --mode html   → превью HTML (проверить глазами без Joomla)

Использование:
    python3 tools/joomla/generate_joomla_pages.py --mode json --out /tmp/gen
    python3 tools/joomla/generate_joomla_pages.py --mode sql  --out gen.sql
    python3 tools/joomla/generate_joomla_pages.py --mode html --out /tmp/preview
    python3 tools/joomla/generate_joomla_pages.py --list        # что умеет

Важно: скрипт НИЧЕГО не пишет в живую базу. Он только готовит файлы.
Импорт — ваше решение и ваша копия базы.

Требуемые данные (уже есть в репозитории):
    data/source/weapons.json       — статы (id, damage, fireRate, weight, ...)
    data/source/weapons.ru.json    — названия, диапазон, flavour-текст
    data/source/qualities.ru.json  — качества (id → русское название)
    data/source/ammo.ru.json       — патроны
    data/source/damage_effects.ru.json — эффекты
    data/source/origins.ru.json    — происхождения (если понадобятся)
"""
import argparse
import copy
import json
import os
import re
import sys
import unicodedata
import uuid

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(ROOT, 'data', 'source')
SPPB_DUMP = os.environ.get('SPPB_DUMP', '/tmp/sppb/jos_sppagebuilder.json')

# --------------------------------------------------------------------------
# Справочники: код из JSON → текст на странице.
# Значения сняты с реальных страниц (например «Боевой карабин», sppb id 8),
# поэтому совпадают с тем, что сейчас на сайте, а не выдуманы.
# --------------------------------------------------------------------------
RANGE = {
    'C': 'Близкая',
    'M': 'Средняя',
    'L': 'Дальняя',
    '': '',
}
DAMAGE_TYPE = {
    'physical': 'Физический',
    'energy': 'Энергетический',
    'radiation': 'Радиация',
    'poison': 'Отравление',
    'special': 'Особый',
}
SKILL = {
    'SMALL_GUNS': 'Стрелковое оружие',
    'MELEE_WEAPONS': 'Оружие ближнего боя',
    'BIG_GUNS': 'Тяжёлое оружие',
    'ENERGY_WEAPONS': 'Энергетическое оружие',
    'EXPLOSIVES': 'Взрывчатка',
    'UNARMED': 'Без оружия',
    'THROWING': 'Метательное',
}
# Заголовки таблицы эталонной страницы оружия (порядок важен — по нему
# раскладываются значения).
WEAPON_HEADERS = ['НАЗВАНИЕ', 'ТИП ОРУЖИЯ', 'УРОН', 'Эффект', 'ТИП УРОНА',
                  'СКОРОСТРЕЛЬНОСТЬ', 'ДИСТАНЦИЯ', 'КАЧЕСТВА', 'ВЕС', 'ЦЕНА', 'РЕДКОСТЬ']

EMPTY = '-'


# --------------------------------------------------------------------------
# загрузка исходников
# --------------------------------------------------------------------------
def load_json(name):
    path = os.path.join(SRC, name)
    if not os.path.exists(path):
        return []
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def load_refs():
    """Справочники id → русское название."""
    def index(rows):
        return {r['id']: r.get('name', '') for r in rows if isinstance(r, dict) and 'id' in r}
    return {
        'quality': index(load_json('qualities.ru.json')),
        'ammo': index(load_json('ammo.ru.json')),
        'effect': index(load_json('damage_effects.ru.json')),
    }


def merge_weapons(refs):
    """weapons.json (статы) + weapons.ru.json (русские названия) → список записей."""
    stats = {w['id']: w for w in load_json('weapons.json') if isinstance(w, dict) and 'id' in w}
    names = {w['id']: w for w in load_json('weapons.ru.json') if isinstance(w, dict) and 'id' in w}
    out = []
    for wid, st in stats.items():
        ru = names.get(wid, {})
        name = (ru.get('name') or st.get('imageName') or wid).strip()
        if not name:
            continue
        qualities = []
        for q in st.get('qualities') or []:
            qid = q.get('qualityId') if isinstance(q, dict) else q
            qn = refs['quality'].get(qid)
            if qn:
                qualities.append(qn)
        effects = []
        for e in st.get('effects') or []:
            eid = e.get('effectId') if isinstance(e, dict) else e
            en = refs['effect'].get(eid)
            if en:
                effects.append(en)
        dtype = st.get('damageType')
        if isinstance(dtype, list):
            dtype = ' / '.join(DAMAGE_TYPE.get(x, x) for x in dtype)
        else:
            dtype = DAMAGE_TYPE.get(dtype, dtype or '')
        out.append({
            'id': wid,
            'name': name,
            'type': SKILL.get(st.get('mainSkill'), '') or '',
            'damage': st.get('damage'),
            'effect': ', '.join(effects) if effects else EMPTY,
            'damage_type': dtype or EMPTY,
            'fire_rate': st.get('fireRate'),
            'range': RANGE.get(str(st.get('range') or ''), str(st.get('range') or '')),
            'qualities': ', '.join(qualities) if qualities else EMPTY,
            'weight': st.get('weight') if st.get('weight') not in (None, '') else EMPTY,
            'cost': st.get('cost') if st.get('cost') not in (None, '') else EMPTY,
            'rarity': st.get('rarity') if st.get('rarity') not in (None, '') else EMPTY,
            'ammo': refs['ammo'].get(st.get('ammoId'), ''),
            'image': st.get('imageName') or '',
            'flavour': (ru.get('flavour') or '').strip(),
        })
    out.sort(key=lambda w: w['name'].lower())
    return out


# --------------------------------------------------------------------------
# утилиты
# --------------------------------------------------------------------------
def translit(text):
    """Русское название → alias для Joomla (латиница, дефисы)."""
    table = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
        'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'j', 'к': 'k', 'л': 'l', 'м': 'm',
        'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
        'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'shch',
        'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
    }
    out = []
    for ch in text.lower():
        if ch in table:
            out.append(table[ch])
        elif ch.isalnum() and ch.isascii():
            out.append(ch)
        else:
            out.append('-')
    alias = re.sub(r'-+', '-', ''.join(out)).strip('-')
    return alias or 'page'


def html_escape(s):
    return (str(s).replace('&', '&amp;').replace('<', '&lt;')
            .replace('>', '&gt;').replace('"', '&quot;'))


def text_block(text, color='#FFF', align='sppb-text-center'):
    """Стандартная ячейка SPPB table_advanced — ровно как в дампе."""
    return {
        'content': [{
            'id': int(uuid.uuid4().int % 10 ** 13),
            'name': 'text_block',
            'settings': {
                'text': '<p>%s</p>' % html_escape(text),
                'dropcap': 0,
                'global_user_border': 0,
                'global_margin': {'md': '   ', 'sm': '   ', 'xs': '   '},
                'global_padding': {'md': '   ', 'sm': '   ', 'xs': '   '},
                'global_use_animation': 0,
                'global_text_color': color,
                'alignment': align,
            },
            'reference_id': 1703611037261,
        }],
        'title': str(text),
    }


def find_addons(node, name, out):
    if isinstance(node, dict):
        if node.get('name') == name:
            out.append(node)
        for k in ('content', 'columns', 'addons'):
            if isinstance(node.get(k), list):
                for c in node[k]:
                    find_addons(c, name, out)
    elif isinstance(node, list):
        for c in node:
            find_addons(c, name, out)


def find_headings(node, out):
    """Все content-аддоны с name=heading (заголовок-категория)."""
    if isinstance(node, dict):
        if node.get('name') == 'heading' and node.get('type') == 'content':
            out.append(node)
        for k in ('content', 'columns', 'addons'):
            if isinstance(node.get(k), list):
                for c in node[k]:
                    find_headings(c, out)
    elif isinstance(node, list):
        for c in node:
            find_headings(c, out)


# --------------------------------------------------------------------------
# генерация одной страницы из шаблона
# --------------------------------------------------------------------------
def load_template(weapon_name='Боевой карабин'):
    """Достаём из выгрузки SPPB реальную страницу оружия как шаблон."""
    if not os.path.exists(SPPB_DUMP):
        raise SystemExit(
            'Нет выгрузки SPPB: %s\n'
            'Положите jos_sppagebuilder.json туда или задайте SPPB_DUMP.\n'
            'Скрипт не может работать без эталонной страницы: он копирует её\n'
            'вёрстку, а не рисует HTML заново.' % SPPB_DUMP)
    with open(SPPB_DUMP, encoding='utf-8') as f:
        dump = json.load(f)
    rows = dump[2]['data']
    for rec in rows:
        if rec.get('title', '').strip() == weapon_name and rec.get('content'):
            return json.loads(rec['content']), rec
    # если точного совпадения нет — берём любую страницу с таблицей оружия
    for rec in rows:
        if not rec.get('content'):
            continue
        try:
            tree = json.loads(rec['content'])
        except Exception:
            continue
        tabs = []
        find_addons(tree, 'table_advanced', tabs)
        if tabs:
            return tree, rec
    raise SystemExit('В выгрузке не нашлось ни одной страницы с таблицей.')


def fill_page(template, weapon):
    """Подставляет данные оружия в копию шаблона и возвращает дерево."""
    tree = copy.deepcopy(template)

    # 1. заголовок страницы (аддон heading) — название оружия
    heads = []
    find_headings(tree, heads)
    if heads:
        st = heads[0].setdefault('settings', {})
        st['title'] = weapon['name']
        # в дампе заголовок часто «КАТЕГОРИЯ: СТРЕЛКОВОЕ ОРУЖИЕ» — заменяем целиком
        st.pop('title_link', None)

    # 2. таблица статов
    tabs = []
    find_addons(tree, 'table_advanced', tabs)
    if not tabs:
        raise SystemExit('В шаблоне нет table_advanced — некуда писать статы.')
    s = tabs[0]['settings']
    values = [
        weapon['name'], weapon['type'], weapon['damage'], weapon['effect'],
        weapon['damage_type'], weapon['fire_rate'], weapon['range'],
        weapon['qualities'], weapon['weight'], weapon['cost'], weapon['rarity'],
    ]
    # заголовки: сохраняем эталонные, но проверяем количество
    hdr = s.get('sp_table_advanced_item') or []
    if len(hdr) != len(values):
        raise SystemExit(
            'Шаблон не совпадает по числу колонок: ожидалось %d, в шаблоне %d\n'
            'Заголовки шаблона: %s' % (len(values), len(hdr), [h.get('title') for h in hdr]))
    row = []
    for v in values:
        row.append(text_block(EMPTY if v in (None, '') else v))
    s['table_advanced_item'] = [{'table_advanced_item': row}]

    # 3. текст под картинкой: боекомплект + flavour
    texts = []
    find_addons(tree, 'text_block', texts)
    for t in texts:
        st = t.get('settings') or {}
        cur = st.get('text') or ''
        if 'Боеприпасы' in cur or len(cur) > 300:
            parts = []
            if weapon['ammo']:
                parts.append('<p><strong>Боеприпасы:</strong> %s</p>' % html_escape(weapon['ammo']))
            if weapon['flavour']:
                parts.append('<p>%s</p>' % html_escape(weapon['flavour']))
            st['text'] = '\n'.join(parts)
            break
    return tree


def page_title(weapon):
    return weapon['name']


# --------------------------------------------------------------------------
# режимы вывода
# --------------------------------------------------------------------------
def mode_json(rows, outdir, template):
    os.makedirs(outdir, exist_ok=True)
    index = []
    for w in rows:
        tree = fill_page(template, w)
        alias = translit(w['name'])
        payload = {
            'title': page_title(w),
            'alias': alias,
            'catid': None,          # заполняется вами: id категории в вашей Joomla
            'language': '*',
            'access': 1,
            'published': 1,
            'sppb': {
                'extension': 'com_content',
                'extension_view': 'article',
                'title': page_title(w),
                'content': tree,
            },
        }
        path = os.path.join(outdir, alias + '.json')
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(payload, f, ensure_ascii=False, indent=1)
        index.append({'title': w['name'], 'alias': alias, 'file': alias + '.json'})
    with open(os.path.join(outdir, '_index.json'), 'w', encoding='utf-8') as f:
        json.dump(index, f, ensure_ascii=False, indent=1)
    print('JSON-страниц: %d → %s' % (len(index), outdir))
    print('Список: %s' % os.path.join(outdir, '_index.json'))


def sql_quote(v):
    if v is None:
        return 'NULL'
    if isinstance(v, (int, float)):
        return str(v)
    return "'" + str(v).replace('\\', '\\\\').replace("'", "\\'") + "'"


def mode_sql(rows, outfile, template, start_id=10000):
    lines = [
        '-- Сгенерировано tools/joomla/generate_joomla_pages.py',
        '-- ВАЖНО: сначала проверьте на копии базы. id начинаются с %d,' % start_id,
        '-- чтобы не задеть существующие записи. Перед запуском сделайте бэкап.',
        '--',
        '-- Каждая страница = 1 запись в jos_sppagebuilder (раскладка SPPB).',
        '-- Сами статьи (jos_content) скрипт НЕ создаёт: их проще завести',
        '-- штатным импортом или по списку из _index.json.',
        '',
    ]
    for i, w in enumerate(rows):
        rid = start_id + i
        tree = fill_page(template, w)
        content = json.dumps(tree, ensure_ascii=False, separators=(',', ':'))
        alias = translit(w['name'])
        lines.append(
            'INSERT INTO `jos_sppagebuilder` '
            '(`id`,`asset_id`,`title`,`text`,`content`,`extension`,`extension_view`,'
            '`view_id`,`active`,`published`,`catid`,`language`,`ordering`,`access`,`created_by`) VALUES\n'
            '(%d,0,%s,%s,%s,%s,%s,0,1,1,2,%s,0,1,1);\n'
            % (rid, sql_quote(w['name']), sql_quote(''), sql_quote(content),
               sql_quote('com_content'), sql_quote('article'), sql_quote('*')))
    with open(outfile, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    # отчёт: alias → что создаётся
    report = outfile + '.map.tsv'
    with open(report, 'w', encoding='utf-8') as f:
        f.write('id\ttitle\talias\n')
        for i, w in enumerate(rows):
            f.write('%d\t%s\t%s\n' % (start_id + i, w['name'], translit(w['name'])))
    print('SQL: %s (%d страниц)' % (outfile, len(rows)))
    print('Карта id → страница: %s' % report)


def mode_html(rows, outdir, template):
    """Превью без Joomla: показываем таблицу статов так, как её увидит читатель."""
    os.makedirs(outdir, exist_ok=True)
    css = '''<style>
body{font:16px/1.5 Helvetica,Arial,sans-serif;background:#f4f2ef;color:#000;margin:0;padding:24px}
h1{font:700 32px/1.2 Arial,sans-serif;color:#b15b23;margin:0 0 4px}
h2{font:700 28px/1.2 Arial,sans-serif;margin:32px 0 8px}
table{border-collapse:collapse;background:#fff;box-shadow:0 0 0 1px #ccc}
th,td{border:1px solid #b9b9b9;padding:8px 12px;font-size:14px}
th{background:#2b2b2b;color:#fff;font-weight:700;white-space:nowrap}
td{text-align:center}
.meta{color:#555;font-size:14px;margin:0 0 20px}
a{color:#b15b23}
</style>'''
    idx = []
    for w in rows:
        alias = translit(w['name'])
        vals = [w['name'], w['type'], w['damage'], w['effect'], w['damage_type'],
                w['fire_rate'], w['range'], w['qualities'], w['weight'], w['cost'], w['rarity']]
        cells = ''.join('<th>%s</th>' % html_escape(h) for h in WEAPON_HEADERS)
        vals_html = ''.join('<td>%s</td>' % html_escape(v) for v in vals)
        html = ('<!DOCTYPE html><html lang="ru"><head><meta charset="utf-8">'
                '<title>%s</title>%s</head><body>'
                '<h1>%s</h1><p class="meta">%s · боекомплект: %s</p>'
                '<p>%s</p>'
                '<table><tr>%s</tr><tr>%s</tr></table>'
                '<p class="meta">Файл данных: %s.json</p>'
                '</body></html>'
                % (html_escape(w['name']), css, html_escape(w['name']),
                   html_escape(w['type']), html_escape(w['ammo'] or EMPTY),
                   html_escape(w['flavour'][:600]),
                   cells, vals_html, alias))
        with open(os.path.join(outdir, alias + '.html'), 'w', encoding='utf-8') as f:
            f.write(html)
        idx.append((w['name'], alias + '.html'))
    # общий индекс
    links = ''.join('<li><a href="%s">%s</a></li>' % (f, html_escape(n)) for n, f in idx)
    with open(os.path.join(outdir, 'index.html'), 'w', encoding='utf-8') as f:
        f.write('<!DOCTYPE html><html lang="ru"><head><meta charset="utf-8">'
                '<title>Превью сгенерированных страниц</title>%s</head><body>'
                '<h1>Превью: %d страниц</h1><ul>%s</ul></body></html>'
                % (css, len(idx), links))
    print('Превью: %d страниц → %s/index.html' % (len(idx), outdir))


# --------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description='Генерация SPPB-страниц Joomla из JSON')
    ap.add_argument('--mode', choices=['json', 'sql', 'html', 'list'], default='list')
    ap.add_argument('--out', default='gen')
    ap.add_argument('--limit', type=int, default=0, help='только первые N страниц')
    ap.add_argument('--template', default='Боевой карабин',
                    help='название страницы-шаблона в выгрузке SPPB')
    args = ap.parse_args()

    refs = load_refs()
    weapons = merge_weapons(refs)

    if args.mode == 'list':
        print('Оружий в JSON: %d' % len(weapons))
        print('Готовые режимы:')
        print('  --mode html  превью (без Joomla, посмотреть глазами)')
        print('  --mode json  SPPB-JSON по файлу на страницу + _index.json')
        print('  --mode sql   INSERT-ы для jos_sppagebuilder + карта id/alias')
        print('\nПримеры:')
        for w in weapons[:5]:
            print('  %-28s %-24s урон %-4s вес %-4s цена %-4s' %
                  (w['name'][:28], w['type'][:24], w['damage'], w['weight'], w['cost']))
        return

    template, tpl_rec = load_template(args.template)
    print('Шаблон: «%s» (sppb id %s)' % (tpl_rec['title'].strip(), tpl_rec['id']))
    if args.limit:
        weapons = weapons[:args.limit]
    print('Страниц к генерации: %d' % len(weapons))

    if args.mode == 'json':
        mode_json(weapons, args.out, template)
    elif args.mode == 'sql':
        mode_sql(weapons, args.out, template)
    else:
        mode_html(weapons, args.out, template)


if __name__ == '__main__':
    main()
