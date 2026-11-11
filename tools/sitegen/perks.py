#!/usr/bin/env python3
"""
Перки: страница /perki.

Живой сайт отдаёт здесь JS-карточки, которые подгружаются из /images/perks/perks.json
(см. inline-скрипт «cards-container» в выдаче Joomla). JSON в дампе отсутствует, поэтому
данные собираются из статьи «ПЕРКИ» (jos_content id 15): блоки «НАЗВАНИЕ / Ранги: N /
Требования: … / описание». Структура карточек, разметка и CSS — ровно как на живом сайте
(perk-card, filter-attributes, сетка в 2 колонки, паттерн food-truck + тень 7px 5px).

Результат: public/perki/index.html + public/images/perks/perks.json (та же схема, что
ожидает оригинальный скрипт: id, title, rank, requirements, description).
"""
import html
import json
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
OUT = os.path.join(ROOT, 'public')
# на GitHub Pages сайт в подкаталоге /fallout-2d20-site/ — префикс задаётся при сборке
BASE = (os.environ.get('BASE') or '').rstrip('/')


# --------------------------------------------------------------------------- данные
def article(art_id):
    rows = json.load(open(os.path.join(ROOT, 'jos_content.json'), encoding='utf-8'))
    arts = [e for e in rows if e.get('type') == 'table'][0]['data']
    return [x for x in arts if x['id'] == str(art_id)][0]


def translit_slug(s):
    tr = {'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e', 'ж': 'zh',
          'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm', 'н': 'n', 'о': 'o',
          'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u', 'ф': 'f', 'х': 'kh', 'ц': 'ts',
          'ч': 'ch', 'ш': 'sh', 'щ': 'shch', 'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu',
          'я': 'ya', ' ': '_'}
    return ''.join(tr.get(ch, ch) for ch in s.lower() if ch.isalnum() or ch in ' _-').strip('_')


def parse_perks():
    a = article(15)
    raw = (a.get('introtext') or '') + (a.get('fulltext') or '')
    raw = raw.replace('\r', '')
    blocks = re.findall(r'<p>(.*?)</p>', raw, re.S)
    texts = []
    for b in blocks:
        b = re.sub(r'<br\s*/?>', '\n', b)
        t = html.unescape(re.sub(r'<[^>]+>', '', b)).replace('\xa0', ' ').strip()
        if t:
            texts.append(t)

    perks = []
    i = 0
    n = len(texts)
    while i < n:
        t = texts[i]
        nxt = texts[i + 1] if i + 1 < n else ''
        if nxt.startswith('Ранги'):
            title = t
            rank = nxt.split(':', 1)[-1].strip()
            req = ''
            j = i + 2
            if j < n and texts[j].startswith('Требования'):
                req = texts[j].split(':', 1)[-1].strip()
                j += 1
            desc = []
            while j < n and not (j + 1 < n and texts[j + 1].startswith('Ранги')):
                # следующее название перка = строка, за которой идёт «Ранги:»
                if j + 1 < n and texts[j + 1].startswith('Ранги'):
                    break
                desc.append(texts[j])
                j += 1
            perks.append({
                'id': translit_slug(title),
                'title': title,
                'rank': rank,
                'requirements': req,
                'description': '\n'.join(desc).strip(),
            })
            i = j
        else:
            i += 1
    return perks


# --------------------------------------------------------------------------- разметка
CSS = """
/* === КАРТОЧКИ ПЕРКОВ === */
#cards-container .card-title { font-size: 1.2rem; text-transform: uppercase; font-weight: 700; margin-bottom: 10px; }
.article-list .article { border: 1px solid #9b9999; }
a:hover { text-decoration: underline; }

#cards-container.cards-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 25px;
    padding: 20px 0;
    align-items: start;
}
#cards-container .perk-card {
    width: 100%;
    box-sizing: border-box;
    display: flex;
    flex-direction: column;
    background-image: linear-gradient(rgba(150, 150, 150, 0.2), rgba(150, 150, 150, 0.2)), url('{BASE}/assets/img/food-truck-pattern.jpg');
    background-repeat: repeat;
    background-position: center;
    box-shadow: 7px 5px 0px 0px #C3C3C3 !important;
}
#cards-container .perk-card-header {
    font-size: 1.2rem;
    text-transform: uppercase;
    font-weight: 700;
    padding: 10px 15px;
    border-bottom: 1px solid rgba(110, 110, 110, 0.3) !important;
    background: transparent;
}
#cards-container .perk-card-body { display: flex; flex-direction: row; background: transparent; }
#cards-container .perk-card-image-col {
    width: 30%; padding: 12px; display: flex; align-items: center; justify-content: center;
    box-sizing: border-box; background: transparent;
}
#cards-container .perk-card-image-col img { max-width: 100%; height: auto; display: block; }
#cards-container .perk-card-text-col { width: 70%; padding: 12px 15px; box-sizing: border-box; background: transparent; }
#cards-container .perk-card-text-col p { margin: 0 0 5px 0; font-size: 0.95rem; line-height: 1.4; }
#cards-container .perk-card-desc { margin-top: 8px; line-height: 1.5; font-size: 0.92rem; white-space: pre-line; }

#filter-attributes {
    display: flex; flex-wrap: wrap; gap: 12px; align-items: center;
    padding: 12px 0; margin-bottom: 20px; border-bottom: 2px solid rgba(110, 110, 110, 0.2);
}
#filter-attributes span { font-weight: 600; }
#filter-attributes label {
    display: inline-flex; align-items: center; gap: 5px; cursor: pointer; font-size: 0.95rem;
    user-select: none; background: rgba(0, 0, 0, 0.05); padding: 4px 10px; transition: background 0.2s;
}
#filter-attributes label:hover { background: rgba(0, 0, 0, 0.1); }
#filter-attributes input[type="checkbox"] { width: 15px; height: 15px; cursor: pointer; }
#filter-attributes button {
    padding: 5px 16px; background: #dc3545; color: #fff; border: none; cursor: pointer;
    font-size: 0.9rem; transition: background 0.2s;
}
#filter-attributes button:hover { background: #c82333; }
@media (max-width: 768px) { #cards-container.cards-grid { grid-template-columns: 1fr; gap: 20px; } }
@media (max-width: 480px) {
    #cards-container .perk-card-body { flex-direction: column; }
    #cards-container .perk-card-image-col { width: 100%; padding: 15px 15px 5px 15px; }
    #cards-container .perk-card-image-col img { max-width: 120px; margin: 0 auto; }
    #cards-container .perk-card-text-col { width: 100%; padding: 5px 15px 15px 15px; }
}
"""

JS = """
<script>
document.addEventListener("DOMContentLoaded", function() {
    const container = document.getElementById('cards-container');
    if (!container) { return; }
    const jsonUrl = '__BASE__/images/perks/perks.json';
    const imagesFolder = '__BASE__/images/perks/images/';
    const attributes = ['СИЛ', 'ВОС', 'ВЫН', 'ХАР', 'ИНТ', 'ЛОВ', 'УДЧ'];

    let filterDiv = document.getElementById('filter-attributes');
    if (!filterDiv) { return; }

    fetch(jsonUrl)
        .then(response => { if (!response.ok) throw new Error('Ошибка загрузки JSON'); return response.json(); })
        .then(data => {
            container.innerHTML = '';
            data.forEach(card => {
                const cardElement = document.createElement('div');
                cardElement.classList.add('perk-card');
                cardElement.dataset.requirements = card.requirements || '';
                const diceIcon = '<img src="__BASE__/assets/img/CD.png" alt="Боевой Кубик" style="height:1.2em; vertical-align:middle; display:inline-block; margin:0 2px;">';
                const formattedDescription = (card.description || '').replace(/\\bDC\\b/g, diceIcon);
                const imageSrc = `${imagesFolder}${card.id}.png`;
                cardElement.innerHTML = `
                    <div class="perk-card-header">${card.title}</div>
                    <div class="perk-card-body">
                        <div class="perk-card-image-col">
                            <img src="${imageSrc}" alt="${card.title}"
                                 onerror="this.onerror=null; this.src='${imagesFolder}default.png';">
                        </div>
                        <div class="perk-card-text-col">
                            <p><strong>Ранги:</strong> ${card.rank}</p>
                            <p><strong>Требования:</strong> ${card.requirements || 'Нет'}</p>
                            <div class="perk-card-desc">${formattedDescription}</div>
                        </div>
                    </div>`;
                container.appendChild(cardElement);
            });
            buildFilterUI(filterDiv, attributes);
        })
        .catch(error => {
            console.error('Не удалось загрузить данные:', error);
            container.innerHTML = '<p>Не удалось загрузить карточки.</p>';
        });

    function buildFilterUI(targetEl, attrs) {
        targetEl.innerHTML = '<span>Фильтр по атрибутам:</span>';
        attrs.forEach(attr => {
            const label = document.createElement('label');
            label.innerHTML = `<input type="checkbox" value="${attr}"> ${attr}`;
            label.querySelector('input').addEventListener('change', applyFilter);
            targetEl.appendChild(label);
        });
        const resetBtn = document.createElement('button');
        resetBtn.textContent = 'Сбросить';
        resetBtn.addEventListener('click', () => {
            targetEl.querySelectorAll('input[type="checkbox"]').forEach(cb => cb.checked = false);
            applyFilter();
        });
        targetEl.appendChild(resetBtn);
    }

    function applyFilter() {
        const filterDiv = document.getElementById('filter-attributes');
        const checkedCbs = filterDiv.querySelectorAll('input[type="checkbox"]:checked');
        const activeFilters = Array.from(checkedCbs).map(cb => cb.value);
        const cards = container.querySelectorAll('.perk-card');
        cards.forEach(card => {
            const reqText = (card.dataset.requirements || '').trim().toUpperCase();
            const hasNoRequirements = !reqText || reqText === '—' || reqText === '-' || reqText === 'НЕТ' || reqText.includes('НЕТ ТРЕБОВАНИЙ');
            if (activeFilters.length === 0) { card.style.display = ''; }
            else {
                const matches = activeFilters.some(attr => reqText.includes(attr));
                card.style.display = (hasNoRequirements || matches) ? '' : 'none';
            }
        });
    }
});
</script>
"""


def render_page(perks):
    tpl = os.path.join(ROOT, 'public', 'perki', 'template.html')
    if not os.path.exists(tpl):
        sys.exit('нет %s — сначала запустите tools/sitegen/build.py' % tpl)
    with open(tpl, encoding='utf-8') as f:
        shell = f.read()
    content = ('<div class="com-content-article item-page"><div class="article-details">'
               '<div class="article-header"><h1>Перки 2026</h1></div>'
               '<div class="article-body">'
               '<div id="filter-attributes"></div>'
               '<div id="cards-container" class="cards-grid"></div>'
               '</div></div></div>')
    if '<!--PERKS_CONTENT-->' in shell:
        out = shell.replace('<!--PERKS_CONTENT-->', content)
    else:
        # build.py кладёт в /perki содержимое модуля — заменяем его на каркас перков
        out, n = re.subn(r'<div class="com-content-article item-page">.*?</div></div></div>',
                         content, shell, count=1, flags=re.S)
        if not n:
            sys.exit('в шаблоне /perki нет ни маркера, ни article-body')
    out = out.replace('</head>', '<style>%s</style>\n</head>' % CSS.replace('{BASE}', BASE))
    out = out.replace('</body>', JS.replace('__BASE__', BASE) + '\n</body>')
    return out


def main():
    perks = parse_perks()
    os.makedirs(os.path.join(OUT, 'perki'), exist_ok=True)
    os.makedirs(os.path.join(OUT, 'images', 'perks', 'images'), exist_ok=True)
    with open(os.path.join(OUT, 'images', 'perks', 'perks.json'), 'w', encoding='utf-8') as f:
        json.dump(perks, f, ensure_ascii=False, indent=1)
    with open(os.path.join(OUT, 'perki', 'index.html'), 'w', encoding='utf-8') as f:
        f.write(render_page(perks))
    print('перков:', len(perks))
    for p in perks[:3]:
        print('  ', p['title'], '| ранги', p['rank'], '|', p['requirements'])


if __name__ == '__main__':
    main()
