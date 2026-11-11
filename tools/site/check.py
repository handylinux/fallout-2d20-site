#!/usr/bin/env python3
"""Проверка собранного docs/ по замерам из SPEC.md.

Ловит регрессии, которые глазами видно позже, чем хотелось бы:
ширину оболочки, сетку карточек, шапку (6 пунктов, без лого/лупы),
фон карточек, ссылки на заголовках и картинках, битые внутренние ссылки.
"""
import glob
import os
import re
import sys

DOCS = 'docs'
BASE = '/fallout-2d20-site'
errors, warnings = [], []


def read(path):
    with open(path, encoding='utf-8') as f:
        return f.read()


css = read(os.path.join(DOCS, 'assets/css/site.css'))

# --- ширина и оболочка
if 'max-width: 1425px' not in css:
    errors.append('CSS: у .site нет max-width: 1425px')


# --- текстуры плашек в CSS: ровно 6 правил nth-child с menu-item-bg
plates = re.findall(r'\.top-menu li:nth-child\((\d)\) a \{ background-image', css)
if len(plates) != 6:
    errors.append('CSS: правил текстур плашек %d, ожидалось 6' % len(plates))
if '.top-menu a:hover .top-menu__title' not in css:
    errors.append('CSS: пропал hover-underline у плашек')
if 'scale(1.05)' not in css:
    errors.append('CSS: пропало увеличение текста при hover')

# --- карточки хаба
for need in ('.tiles-row', '33.3333%', '13.336px', '.tile__media img'):
    if need not in css:
        errors.append('CSS: пропало `%s`' % need)
if 'background-image: var(--f-plate-pattern' in css:
    errors.append('CSS: у .tile вернулся фон-паттерн (у эталона фон отсутствует)')

pages = glob.glob(os.path.join(DOCS, '**/*.html'), recursive=True)

# --- шапка на каждой странице
for path in pages:
    html = read(path)
    head = html[html.find('<header'):html.find('</header>')] if '<header' in html else ''
    items = re.findall(r'<li><a href="[^"]*"><span class="top-menu__title">', head)
    if len(items) != 6:
        errors.append('%s: в шапке %d пунктов вместо 6' % (path, len(items)))
    if 'site-header__logo' in head:
        errors.append('%s: в шапке вернулся логотип' % path)
    if '<button class="site-search__btn"' in head:
        errors.append('%s: в шапке вернулась кнопка поиска' % path)

# --- хаб «Снаряжение»
hub = os.path.join(DOCS, 'snaryazhenie/index.html')
if os.path.exists(hub):
    html = read(hub)
    tiles = re.findall(r'class="tile__title">([^<]+)<', html)
    expect = ['Оружие', 'Боеприпасы', 'Броня', 'Одежда', 'Препараты', 'Еда',
              'Напитки', 'Книги и журналы', 'Разное']
    if tiles[:9] != expect:
        errors.append('хаб: порядок плиток %r, ожидался %r' % (tiles[:9], expect))
    if 'tile--soon' in html and 'скоро' not in html:
        errors.append('хаб: плитка «скоро» без подписи')

# --- битые внутренние ссылки
for path in pages:
    html = read(path)
    for href in re.findall(r'href="(%s/[^"#?]*)"' % re.escape(BASE), html):
        target = DOCS + (href[len(BASE):] or '/')
        if not (os.path.exists(target) or os.path.exists(target.rstrip('/') + '/index.html')):
            errors.append('%s: битая ссылка %s' % (path, href))

print('страниц проверено: %d' % len(pages))
for w in warnings:
    print('  предупреждение:', w)
if errors:
    for e in errors[:40]:
        print('  ОШИБКА:', e)
    print('итого ошибок:', len(errors))
    sys.exit(1)
print('всё по SPEC.md — ошибок нет')
