#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_joomla_full.py — полный пакет для массового создания страниц в Joomla.

В отличие от generate_joomla_pages.py (только раскладки SPPB), этот скрипт
делает ВСЁ, что нужно для появления страницы:

    1. запись в jos_content  (сама статья: заголовок, alias, категория, текст)
    2. запись в jos_sppagebuilder (раскладка SPPB, ссылается на статью
       через view_id = jos_content.id)
    3. пункт меню в jos_menu (чтобы адрес был ЧПУ и страница открывалась
       по ссылке, а не только по index.php?option=...&id=...)
    4. файл отчёта: что создано, какие id/alias получились

Почему так: в Joomla SPPB-раскладка не самодостаточна. Она привязана к статье
через view_id. Если создать только раскладку, страница не появится.

Использование:
    # 146 страниц оружия, отдельная категория, отдельный родитель меню
    python3 tools/joomla/generate_joomla_full.py \
        --source weapons --out /tmp/joomla.sql \
        --catid 18 --parent-menu 269 --start-id 10000

    # только посмотреть, что будет создано (без файлов)
    python3 tools/joomla/generate_joomla_full.py --source weapons --dry-run

Перед запуском SQL в живой базе:
    - сделайте дамп (mysqldump ... > backup.sql)
    - прогоните на копии (docker/локально)
    - проверьте один-два адреса

Скрипт НЕ подключается к базе и НЕ выполняет SQL. Он только генерирует файл.
"""
import argparse
import copy
import json
import os
import sys
import re
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from generate_joomla_pages import (  # noqa: E402
    ROOT, load_refs, merge_weapons, translit, html_escape, load_template,
    find_addons, find_headings, text_block, EMPTY, RANGE, DAMAGE_TYPE, SKILL,
)

CONTENT_DUMP = os.environ.get('CONTENT_DUMP', os.path.join(ROOT, 'jos_content.json'))


# --------------------------------------------------------------------------
def load_article_template(title='Боевой карабин'):
    """Берём реальную статью оружия как шаблон полей (attribs, images, urls)."""
    if not os.path.exists(CONTENT_DUMP):
        raise SystemExit('Нет дампа статей: %s (задайте CONTENT_DUMP)' % CONTENT_DUMP)
    with open(CONTENT_DUMP, encoding='utf-8') as f:
        rows = json.load(f)[2]['data']
    for r in rows:
        if (r.get('title') or '').strip() == title:
            return r
    # любая статья оружия: у неё заполнены images и attribs
    for r in rows:
        if str(r.get('catid')) == '18' and r.get('images'):
            return r
    raise SystemExit('Не нашёл статью-шаблон в %s' % CONTENT_DUMP)


# --------------------------------------------------------------------------
def sql_val(v):
    if v is None:
        return 'NULL'
    if isinstance(v, bool):
        return '1' if v else '0'
    if isinstance(v, (int, float)):
        return str(v)
    return "'" + str(v).replace('\\', '\\\\').replace("'", "\\'") + "'"


def is_english(text):
    """Грубая, но полезная проверка: описание на английском?
    В data/source/weapons.ru.json 127 из 146 flavour-текстов остались
    английскими — их нельзя молча выкладывать на русский сайт."""
    t = text or ''
    if len(t) < 20:
        return False
    lat = len(re.findall(r'[A-Za-z]', t))
    cyr = len(re.findall(r'[А-Яа-я]', t))
    return lat > cyr


def data_warnings(weapons):
    """Что в данных не готово к публикации. Печатается перед генерацией."""
    eng = [w['name'] for w in weapons if is_english(w['flavour'])]
    no_desc = [w['name'] for w in weapons if not (w['flavour'] or '').strip()]
    no_range = [w['name'] for w in weapons if not w['range']]
    no_img = [w['name'] for w in weapons if not w['image']]
    no_type = [w['name'] for w in weapons if not w['type']]
    lines = []
    if eng:
        lines.append('  английское описание: %d  (например: %s)'
                     % (len(eng), ', '.join(eng[:3])))
    if no_desc:
        lines.append('  без описания:        %d  (%s)' % (len(no_desc), ', '.join(no_desc[:3])))
    if no_range:
        lines.append('  без дистанции:       %d  (ближний бой/взрывчатка — это норма)' % len(no_range))
    if no_img:
        lines.append('  без картинки:        %d  (%s)' % (len(no_img), ', '.join(no_img[:3])))
    if no_type:
        lines.append('  без типа оружия:     %d  (%s)' % (len(no_type), ', '.join(no_type[:3])))
    return lines


def build_body_html(weapon):
    """Текст статьи (fulltext): боекомплект + описание. Таблица статов живёт
    в SPPB-раскладке, поэтому здесь только текст."""
    parts = []
    if weapon['ammo']:
        parts.append('<p><strong>Боеприпасы:</strong> %s</p>' % html_escape(weapon['ammo']))
    if weapon['flavour']:
        parts.append('<p>%s</p>' % html_escape(weapon['flavour']))
    if not parts:
        parts.append('<p></p>')
    return '\n'.join(parts)


def validate_layout(layout, weapon, headers_count=11):
    """Проверка перед выгрузкой: страница не должна уехать битой.
    Возвращает список проблем (пусто = всё хорошо)."""
    problems = []
    tabs = []
    find_addons(layout, 'table_advanced', tabs)
    if not tabs:
        return ['нет table_advanced']
    s = tabs[0]['settings']
    rows = s.get('table_advanced_item') or []
    if not rows:
        return ['таблица без строк']
    cells = rows[0].get('table_advanced_item') or []
    if len(cells) != headers_count:
        problems.append('колонок %d, ожидалось %d' % (len(cells), headers_count))

    def txt(c):
        return ' '.join((x.get('settings') or {}).get('text', '') for x in c.get('content') or [])

    vals = [txt(c) for c in cells]
    if not vals:
        problems.append('пустая строка таблицы')
    else:
        first = re.sub(r'<[^>]+>', '', vals[0]).strip()
        if weapon['name'] and first != weapon['name']:
            problems.append('в первой ячейке «%s», а ожидалось «%s»' % (first, weapon['name']))
    for i, v in enumerate(vals):
        if not re.sub(r'<[^>]+>', '', v).strip():
            problems.append('пустая ячейка №%d' % (i + 1))

    heads = []
    find_headings(layout, heads)
    if not heads:
        problems.append('нет заголовка страницы (heading)')
    elif heads[0].get('settings', {}).get('title') != weapon['name']:
        problems.append('заголовок не совпадает с названием')
    return problems


def fill_layout(template, weapon):
    """Копия эталонной SPPB-раскладки с подставленными данными оружия."""
    tree = copy.deepcopy(template)

    heads = []
    find_headings(tree, heads)
    if heads:
        st = heads[0].setdefault('settings', {})
        st['title'] = weapon['name']
        st.pop('title_link', None)

    tabs = []
    find_addons(tree, 'table_advanced', tabs)
    if not tabs:
        raise SystemExit('В шаблоне SPPB нет table_advanced')
    s = tabs[0]['settings']
    values = [weapon['name'], weapon['type'], weapon['damage'], weapon['effect'],
              weapon['damage_type'], weapon['fire_rate'], weapon['range'],
              weapon['qualities'], weapon['weight'], weapon['cost'], weapon['rarity']]
    hdr = s.get('sp_table_advanced_item') or []
    if len(hdr) != len(values):
        raise SystemExit('Колонок в шаблоне %d, а значений %d' % (len(hdr), len(values)))
    s['table_advanced_item'] = [{'table_advanced_item': [
        text_block(EMPTY if v in (None, '') else v) for v in values]}]

    texts = []
    find_addons(tree, 'text_block', texts)
    for t in texts:
        st = t.get('settings') or {}
        cur = st.get('text') or ''
        if 'Боеприпасы' in cur or len(cur) > 300:
            st['text'] = build_body_html(weapon)
            break
    return tree


# --------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description='Полный пакет страниц для Joomla')
    ap.add_argument('--source', default='weapons', choices=['weapons'])
    ap.add_argument('--out', default='joomla_pages.sql')
    ap.add_argument('--catid', type=int, default=18, help='id категории в jos_categories')
    ap.add_argument('--parent-menu', type=int, default=0,
                    help='id родительского пункта меню (0 = верхний уровень)')
    ap.add_argument('--parent-alias', default='',
                    help='alias родительского пункта (нужен, если --parent-menu задан)')
    ap.add_argument('--component-id', type=int, default=22,
                    help='jos_extensions.id для com_content (найдите: SELECT extension_id '
                         'FROM jos_extensions WHERE element="com_content")')
    ap.add_argument('--start-id', type=int, default=10000, help='с какого id начинать')
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--template', default='Боевой карабин')
    ap.add_argument('--skip-english-desc', action='store_true',
                    help='не выводить английские описания (оставить только статы)')
    args = ap.parse_args()

    refs = load_refs()
    weapons = merge_weapons(refs) if args.source == 'weapons' else []
    if args.limit:
        weapons = weapons[:args.limit]
    if not weapons:
        raise SystemExit('Нет данных для генерации')

    art_tpl = load_article_template(args.template)
    layout_tpl, layout_rec = load_template(args.template)

    print('Статья-шаблон:   id %s «%s» (catid %s)'
          % (art_tpl['id'], art_tpl['title'], art_tpl['catid']))
    print('Раскладка-шаблон: sppb id %s «%s»' % (layout_rec['id'], layout_rec['title'].strip()))
    print('Страниц: %d' % len(weapons))
    print('Категория: %s | родитель меню: %s | с id: %s'
          % (args.catid, args.parent_menu or 'верхний уровень', args.start_id))

    warns = data_warnings(weapons)
    if warns:
        print('\nВНИМАНИЕ по данным (страницы будут созданы как есть):')
        for line in warns:
            print(line)
        print('  → английский текст можно оставить пустым: --skip-english-desc')

    if args.dry_run:
        for i, w in enumerate(weapons[:8]):
            cid = args.start_id + i
            print('  %5d  %-30s %-28s урон %-4s' %
                  (cid, w['name'][:30], translit(w['name'])[:28], w['damage']))
        if len(weapons) > 8:
            print('  ... ещё %d' % (len(weapons) - 8))
        print('\nСухой прогон: файлы не создавались.')
        return

    now = '2026-01-01 00:00:00'
    content_sql, layout_sql, menu_sql, report = [], [], [], []
    content_sql.append('-- 1/3 Статьи (jos_content)')
    layout_sql.append('-- 2/3 Раскладки SPPB (jos_sppagebuilder), view_id → jos_content.id')
    menu_sql.append('-- 3/3 Пункты меню (jos_menu)')

    for i, w in enumerate(weapons):
        cid = args.start_id + i          # id статьи и раскладки совпадают, как в дампе
        alias = translit(w['name'])
        layout = fill_layout(layout_tpl, w)
        problems = validate_layout(layout, w)
        if problems:
            raise SystemExit(
                'Страница «%s» не прошла проверку: %s' % (w['name'], '; '.join(problems)))
        if args.skip_english_desc:
            w = dict(w, flavour='' if is_english(w['flavour']) else w['flavour'])
        body = build_body_html(w)

        # --- статья
        a = copy.deepcopy(art_tpl)
        a.update({
            'id': cid,
            'asset_id': 0,
            'title': w['name'],
            'alias': alias,
            'introtext': '',
            'fulltext': body,
            'state': 1,
            'catid': args.catid,
            'created': now,
            'modified': now,
            'publish_up': now,
            'publish_down': None,
            'version': 1,
            'ordering': i,
            'hits': 0,
            'featured': 0,
            'language': '*',
        })
        cols = ['id', 'asset_id', 'title', 'alias', 'introtext', 'fulltext', 'state',
                'catid', 'created', 'created_by', 'created_by_alias', 'modified',
                'modified_by', 'publish_up', 'publish_down', 'images', 'urls',
                'attribs', 'version', 'ordering', 'metakey', 'metadesc', 'access',
                'hits', 'metadata', 'featured', 'language', 'note']
        content_sql.append(
            'INSERT INTO `jos_content` (`%s`) VALUES (%s);'
            % ('`,`'.join(cols), ', '.join(sql_val(a.get(c)) for c in cols)))

        # --- раскладка
        content = json.dumps(layout, ensure_ascii=False, separators=(',', ':'))
        layout_sql.append(
            'INSERT INTO `jos_sppagebuilder` (`id`,`asset_id`,`title`,`text`,`content`,'
            '`extension`,`extension_view`,`view_id`,`active`,`published`,`catid`,'
            '`language`,`ordering`,`access`,`created_by`) VALUES '
            '(%d,0,%s,%s,%s,%s,%s,%d,1,1,%d,%s,0,1,1);'
            % (cid, sql_val(w['name']), sql_val(''), sql_val(content),
               sql_val('com_content'), sql_val('article'), cid, args.catid, sql_val('*')))

        # --- пункт меню
        # level/path зависят от родителя: у верхнего уровня level=1 и path=alias,
        # у вложенного level=2 и path=родитель/alias. Без этого Joomla
        # не построит дерево и пункт «повиснет».
        if args.parent_menu:
            if not args.parent_alias:
                raise SystemExit('С --parent-menu нужен --parent-alias '
                                 '(alias родительского пункта меню)')
            level = 2
            path = '%s/%s' % (args.parent_alias, alias)
        else:
            level = 1
            path = alias
        menu_sql.append(
            'INSERT INTO `jos_menu` (`id`,`menutype`,`title`,`alias`,`path`,`link`,'
            '`type`,`published`,`parent_id`,`level`,`component_id`,`checked_out`,'
            '`browserNav`,`access`,`img`,`template_style_id`,`params`,`home`,`language`,'
            '`client_id`) VALUES '
            '(%d,%s,%s,%s,%s,%s,%s,1,%d,%d,%d,0,0,1,%s,0,%s,0,%s,0);'
            % (cid, sql_val('mainmenu'), sql_val(w['name']), sql_val(alias),
               sql_val(path), sql_val('index.php?option=com_content&view=article&id=%d' % cid),
               sql_val('component'), args.parent_menu, level, args.component_id,
               sql_val(''), sql_val(json.dumps({'article_layout': 'sppb'})), sql_val('*')))

        report.append({'id': cid, 'title': w['name'], 'alias': alias})

    header = [
        '-- Сгенерировано tools/joomla/generate_joomla_full.py',
        '--',
        '-- ПЕРЕД ЗАПУСКОМ:',
        '--   1. cp базы:  mysqldump -u USER -p БАЗА > backup.sql',
        '--   2. прогон на копии базы (docker / локально)',
        '--   3. проверить 1-2 адреса глазами',
        '--',
        '-- id начинаются с %d и совпадают у статьи, раскладки и пункта меню.' % args.start_id,
        '-- Если у вас уже заняты эти id — поменяйте --start-id.',
        '--',
        '-- Категорию (%d) и родительский пункт меню (%d) скрипт НЕ создаёт:'
        % (args.catid, args.parent_menu),
        '-- они должны существовать. Проверьте их id в jos_categories / jos_menu.',
        '-- component_id в jos_menu = %d. Если у вас другой, поправьте:'
        % args.component_id,
        '--   SELECT extension_id FROM jos_extensions WHERE element = "com_content";',
        '',
    ]
    with open(args.out, 'w', encoding='utf-8') as f:
        f.write('\n'.join(header) + '\n')
        f.write('\n'.join(content_sql) + '\n\n')
        f.write('\n'.join(layout_sql) + '\n\n')
        f.write('\n'.join(menu_sql) + '\n')

    rpath = args.out + '.report.json'
    with open(rpath, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=1)

    print('\nГотово.')
    print('  SQL:    %s  (%.1f МБ)' % (args.out, os.path.getsize(args.out) / 1048576))
    print('  Отчёт:  %s' % rpath)
    print('  Записей jos_content:        %d' % len(weapons))
    print('  Записей jos_sppagebuilder:  %d' % len(weapons))
    print('  Пунктов меню jos_menu:      %d' % len(weapons))


if __name__ == '__main__':
    main()
