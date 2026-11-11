"""Кладёт шаблон на каждый адрес каталога + поддержка прямых ссылок.

Страниц как таковых нет: docs/…/index.html — это одна и та же оболочка,
которая читает assets/data/catalog.json. Нужны они только для GitHub Pages
(он не умеет отдавать index.html на произвольный путь).
"""

import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TEMPLATE = os.path.join(ROOT, 'src', 'site', 'template.html')
DATA = os.path.join(ROOT, 'docs', 'assets', 'data', 'catalog.json')
OUT = os.path.join(ROOT, 'docs')

BASE = (os.environ.get('BASE') or '').rstrip('/')


def shell():
    with open(TEMPLATE, encoding='utf-8') as f:
        html = f.read()
    if BASE:
        html = html.replace("'/fallout-2d20-site", "'%s" % BASE)
        html = html.replace('"/fallout-2d20-site', '"%s' % BASE)
    return html


def main():
    html = shell()
    with open(DATA, encoding='utf-8') as f:
        catalog = json.load(f)

    written = 0
    for section in catalog['sections']:
        for cat in section['categories']:
            paths = ['snaryazhenie/%s/%s' % (section['slug'], cat['slug'])]
            paths += ['snaryazhenie/%s/%s/%s' % (section['slug'], cat['slug'], item['slug'])
                      for item in cat['items']]
            for path in paths:
                full = os.path.join(OUT, path)
                os.makedirs(full, exist_ok=True)
                with open(os.path.join(full, 'index.html'), 'w', encoding='utf-8') as f:
                    f.write(html)
                written += 1

    # /snaryazhenie/ и /snaryazhenie/oruzhie/ — хабы
    for path in ['snaryazhenie'] + ['snaryazhenie/%s' % s['slug'] for s in catalog['sections']]:
        full = os.path.join(OUT, path)
        os.makedirs(full, exist_ok=True)
        with open(os.path.join(full, 'index.html'), 'w', encoding='utf-8') as f:
            f.write(html)
        written += 1

    # прочие типы страниц: происхождения, блог
    extra = []
    origins = os.path.join(ROOT, 'docs', 'assets', 'data', 'origins.pages.json')
    if os.path.exists(origins):
        with open(origins, encoding='utf-8') as f:
            extra.append('proiskhozhdeniya')
            extra += ['proiskhozhdeniya/%s' % slug
                      for slug in json.load(f).get('pages', {})]
    blog = os.path.join(ROOT, 'docs', 'assets', 'data', 'blog.json')
    if os.path.exists(blog):
        with open(blog, encoding='utf-8') as f:
            data = json.load(f)
            extra.append('blog')
            extra += ['blog/%s' % slug for slug in (data.get('posts') or {})]
    for path in extra:
        full = os.path.join(OUT, path)
        os.makedirs(full, exist_ok=True)
        with open(os.path.join(full, 'index.html'), 'w', encoding='utf-8') as f:
            f.write(html)
        written += 1

    print('shell-страниц: %d' % written)


if __name__ == '__main__':
    main()
