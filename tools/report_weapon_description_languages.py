#!/usr/bin/env python3
"""Estimate language of effective card descriptions, not proofreading status."""
import json
import re
from collections import Counter
from pathlib import Path
from weapons2cards import Companion, build_card

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / 'data/weapons'
def load(name):
    return json.loads((DATA / name).read_text(encoding='utf-8'))

def report():
    comp = Companion()
    groups = [(name, load(name + '-order.json'), overrides) for name, overrides in (
        ('small-guns', load('small-guns-card-overrides.json')),
        ('heavy-guns', load('heavy-card-overrides.json')), ('energy-guns', load('energy-stat-overrides.json')),
        ('melee-original', load('melee-card-overrides.json')))]
    remaining = load('remaining-card-overrides.json')
    groups.extend((name, ids, remaining) for name, ids in load('remaining-order.json').items())
    totals = Counter()
    lines = []
    for name, ids, overrides in groups:
        counts = Counter()
        for wid in ids:
            card = build_card(comp, wid, page=1, image='')
            card.update(overrides.get(wid, {}))
            text = card.get('description') or ''
            ru = len(re.findall(r'[а-яА-ЯёЁ]', text))
            en = len(re.findall(r'[a-zA-Z]', text))
            status = 'нет текста' if not ru + en else 'английский/смешанный' if en > ru * .3 else 'преимущественно русский'
            counts[status] += 1
            if status != 'преимущественно русский':
                lines.append((name, wid, comp.weapon_name(wid), status))
        totals.update(counts)
        print(name, len(ids), dict(counts))
    print('ИТОГО:', dict(totals), 'карточек:', sum(totals.values()))
    for group, wid, title, status in lines:
        print(f'{group}: {wid} — {title}: {status}')

if __name__ == '__main__':
    report()
