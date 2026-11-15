#!/usr/bin/env python3
"""List Latin words in extractable PDF text, separating known names from review items.

Does not inspect raster images or text converted to vector outlines. A clean
report does not prove the whole book has been translated or visually checked.
"""
import argparse
import re
from collections import defaultdict
from pathlib import Path
import pymupdf

# Proper names, calibre/weapon designations and Roman numeral model names.
KNOWN = {'special', 'apw', 'vault-tec', 'aer', 'wattz', 'iii', 'mirv'}
WORD = re.compile(r"[A-Za-z][A-Za-z\-']{2,}")

def scan(path):
    known, review = defaultdict(list), defaultdict(list)
    with pymupdf.open(path) as pdf:
        for page_num, page in enumerate(pdf, 1):
            for word in WORD.findall(page.get_text()):
                (known if word.lower() in KNOWN else review)[page_num].append(word)
    return dict(known), dict(review)

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('pdf', type=Path)
    args = ap.parse_args()
    known, review = scan(args.pdf)
    for name, group in [('ПРОВЕРИТЬ', review), ('ДОПУЩЕННЫЕ ОБОЗНАЧЕНИЯ', known)]:
        print(name + ':')
        for page, words in group.items():
            print(f"  {page}: {', '.join(dict.fromkeys(words))}")
        if not group:
            print('  нет')
    print('Только извлекаемый текст; изображения и кривые требуют отдельной проверки.')

if __name__ == '__main__':
    main()
