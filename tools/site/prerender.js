/* Предрендер: прогоняет те же views/*.js в Node и пишет готовый HTML.
   Ровно тот код, что исполняется в браузере, — второго шаблона нет.
   На выходе: у каждой страницы свой настоящий HTML (для поисковиков,
   sitemap и просмотра без JS), а клиентский роутер остаётся для навигации. */
'use strict';

const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..', '..');
const DOCS = path.join(ROOT, 'docs');
const VIEWS = path.join(ROOT, 'src', 'site', 'js', 'views');
const BASE = (process.env.BASE || '').replace(/\/$/, '');
const TEMPLATE = path.join(ROOT, 'src', 'site', 'template.html');

/* ---------------------------------------------------------------- мини-DOM */
function makeNode(tag) {
  const node = {
    tagName: tag,
    children: [],
    attrs: {},
    className: '',
    textContent: '',
    _html: '',
    appendChild(child) { this.children.push(child); return child; },
    insertBefore(child, ref) {
      const i = this.children.indexOf(ref);
      if (i < 0) { this.children.push(child); } else { this.children.splice(i, 0, child); }
      return child;
    },
    setAttribute(name, value) { this.attrs[name] = value; },
    getAttribute(name) { return this.attrs[name]; },
    get firstChild() { return this.children[0]; },
    get innerHTML() { return this._html; },
    set innerHTML(value) { this._html = value; this.children = []; },
  };
  return node;
}

const VOID = new Set(['img', 'br', 'hr', 'meta', 'link', 'input']);
const ESC = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };

function esc(text) {
  return String(text === undefined || text === null ? '' : text)
    .replace(/[&<>"']/g, (c) => ESC[c]);
}

function serialize(node) {
  if (node === null || node === undefined) { return ''; }
  if (typeof node === 'string') { return esc(node); }
  if (node.text !== undefined) { return esc(node.text); }   /* createTextNode */
  if (node === true) { return ''; }

  const tag = node.tagName;
  if (!tag || tag === '#frag') {
    return node.children.map(serialize).join('');
  }

  let out = '<' + tag;
  if (node.className) { out += ' class="' + esc(node.className) + '"'; }
  Object.keys(node.attrs).forEach((name) => {
    out += ' ' + name + '="' + esc(node.attrs[name]) + '"';
  });
  if (tag === 'details' && node.attrs.open === undefined) {
    /* открытые по умолчанию спойлеры задаются данными, не шаблоном */
  }
  out += '>';
  if (VOID.has(tag)) { return out; }
  if (node.textContent) { out += esc(node.textContent); }
  if (node._html) { out += node._html; }
  out += node.children.map(serialize).join('');
  return out + '</' + tag + '>';
}

/* ------------------------------------------------------------------ globals */
global.document = {
  body: { getAttribute: () => BASE },
  createElement: makeNode,
  createDocumentFragment: () => makeNode('#frag'),
  createTextNode: (text) => ({ text }),
};
global.window = global;

function loadViews() {
  const files = fs.readdirSync(VIEWS).filter((f) => f.endsWith('.js')).sort();
  /* common.js объявлен последним по алфавиту, а нужен первой: он создаёт window.C */
  files.sort((a, b) => (a === 'common.js' ? -1 : b === 'common.js' ? 1 : 0));
  files.forEach((file) => {
    // eslint-disable-next-line no-eval
    eval(fs.readFileSync(path.join(VIEWS, file), 'utf8'));
  });
  return global.Views;
}

function readJson(name) {
  const file = path.join(DOCS, 'assets', 'data', name + '.json');
  return fs.existsSync(file) ? JSON.parse(fs.readFileSync(file, 'utf8')) : null;
}

/* ------------------------------------------------------------------ каркас */
function shell() {
  let html = fs.readFileSync(TEMPLATE, 'utf8');
  if (BASE) {
    html = html.split("'/fallout-2d20-site").join("'" + BASE);
    html = html.split('"/fallout-2d20-site').join('"' + BASE);
  }
  return html;
}

const SHELL = shell();

const TOP_MENU = [
  ['/', 'Главная'],
  ['/proiskhozhdeniya/', 'Происхождения'],
  ['/snaryazhenie/', 'Снаряжение'],
  ['/snaryazhenie/oruzhie/', 'Оружие'],
  ['/bronya/', 'Броня'],
  ['/perki/', 'Перки'],
  ['/bestiarij/', 'Бестиарий'],
  ['/primery/', 'Примеры'],
];

function titleTag(title) {
  return (title ? esc(title) + ' — ' : '') + 'Fallout 2D20';
}

/* Собирает страницу: меню, дровер, предрендеренный контент, мета. */
function page(catalog, opts) {
  let html = SHELL;

  const content = serialize(opts.node);
  html = html.replace('<div class="wrap" id="app">', '<div class="wrap" id="app" data-prerendered="1">');
  html = html.replace(/<div class="wrap" id="app"[^>]*>[\s\S]*?<\/div>\s*<\/main>/,
    '<div class="wrap" id="app" data-prerendered="1">' + content + '</div>\n</main>');

  /* заголовок и описание — свои у каждой страницы */
  html = html.replace('<title>Fallout 2D20</title>',
    '<title>' + titleTag(opts.title) + '</title>');
  const desc = opts.description || (catalog && catalog.description) || '';
  if (desc) {
    html = html.replace('</head>',
      '<meta name="description" content="' + esc(desc) + '">\n</head>');
  }
  if (opts.canonical) {
    html = html.replace('</head>',
      '<link rel="canonical" href="' + esc(opts.canonical) + '">\n</head>');
  }

  /* хлебные крошки в разметке Schema.org — чтобы поисковик видел структуру */
  if (opts.breadcrumbs && opts.breadcrumbs.length) {
    const items = opts.breadcrumbs.map((crumb, i) => ({
      '@type': 'ListItem',
      position: i + 1,
      name: crumb[1],
      item: (opts.origin || '') + crumb[0],
    }));
    const ld = { '@context': 'https://schema.org', '@type': 'BreadcrumbList', itemListElement: items };
    html = html.replace('</head>',
      '<script type="application/ld+json">' + JSON.stringify(ld) + '</script>\n</head>');
  }

  /* активный пункт верхнего меню */
  return html;
}

/* -------------------------------------------------- ссылки: меню и дровер */
function menuHtml(active) {
  return '<ul class="top-menu">' + TOP_MENU.map(([url, title]) => {
    const cls = active && url === active ? ' class="is-active"' : '';
    return '<li><a href="' + (BASE + url) + '"' + cls + '>' + esc(title) + '</a></li>';
  }).join('') + '</ul>';
}

function drawerHtml(catalog) {
  const extras = [
    ['/proiskhozhdeniya/', 'Происхождения'],
    ['/blog/', 'Блог'],
    ['/primery/', 'Примеры типов страниц'],
  ];
  const pathOf = (s) => (s.path || ('/snaryazhenie/' + s.slug));
  const parts = [];
  extras.forEach(([url, title]) => {
    parts.push('<li><a href="' + (BASE + url) + '">' + esc(title) + '</a></li>');
  });
  (catalog.sections || []).forEach((section) => {
    const cats = (section.categories || []).map((cat) =>
      '<li><a href="' + (BASE + pathOf(section) + '/' + cat.slug + '/') + '">' +
      esc(cat.title) + '</a></li>').join('');
    parts.push('<li><a href="' + (BASE + pathOf(section) + '/') + '">' +
      esc(section.title) + '</a>' +
      '<button class="drawer__toggle" type="button" aria-expanded="false">' +
      '<span class="visually-hidden">Раскрыть «' + esc(section.title) + '»</span></button>' +
      '<ul class="drawer__sub">' + cats + '</ul></li>');
  });
  return parts.join('');
}

function fillChrome(html, catalog, active) {
  html = html.replace('<nav class="site-header__menu" aria-label="Основное меню">\n      <ul class="top-menu">[\s\S]*?</nav>',
    '<nav class="site-header__menu" aria-label="Основное меню">' + menuHtml(active) + '</nav>');
  html = html.replace('<ul id="drawer-nav"></ul>', '<ul id="drawer-nav">' + drawerHtml(catalog) + '</ul>');
  return html;
}

function writeSitemap(urls) {
  const origin = (process.env.SITE_URL || 'https://handylinux.github.io/fallout-2d20-site')
    .replace(/\/$/, '');
  const lines = ['<?xml version="1.0" encoding="UTF-8"?>',
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'];
  Array.from(new Set(urls)).sort().forEach((url) => {
    lines.push('  <url><loc>' + esc(origin + url) + '</loc></url>');
  });
  lines.push('</urlset>');
  fs.writeFileSync(path.join(DOCS, 'sitemap.xml'), lines.join('\n') + '\n');
  console.log('sitemap.xml: %d адресов', Array.from(new Set(urls)).length);
}

/* ---------------------------------------------------------------- маршруты */
function origin(slug) {
  return (BASE || '') + '/proiskhozhdeniya/' + slug + '/';
}

function build() {
  const Views = loadViews();
  const catalog = readJson('catalog');
  if (!catalog) { throw new Error('нет catalog.json — сначала build_data.py'); }

  const jobs = [];
  const push = (dir, node, title, extra) => {
    jobs.push(Object.assign({ dir, node, title }, extra || {}));
  };

  push('', Views.home ? Views.home({ catalog }) : makeNode('#frag'), 'Правила игры', {
    description: 'Правила Fallout 2D20: справочник оружия, происхождений, снаряжения.',
  });
  push('snaryazhenie', Views.snaryazhenie({ catalog }), 'Снаряжение');

  const pathOf = (section) => (section.path || ('/snaryazhenie/' + section.slug)).replace(/^\//, '');
  (catalog.sections || []).forEach((section) => {
    const base = pathOf(section);
    push(base, Views.section({ section, catalog }), section.title, {
      breadcrumbs: [['/snaryazhenie/', 'Снаряжение'], ['/' + base + '/', section.title]],
    });
    (section.categories || []).forEach((cat) => {
      push(base + '/' + cat.slug,
        Views.category({ section, category: cat, catalog }), cat.title, {
          description: cat.title + ' — ' + cat.items.length + ' единиц в справочнике Fallout 2D20.',
          breadcrumbs: [
            ['/snaryazhenie/', 'Снаряжение'],
            ['/' + base + '/', section.title],
            ['/' + base + '/' + cat.slug + '/', cat.title],
          ],
        });

      (cat.items || []).forEach((item) => {
        const viewName = item.view && Views[item.view] ? item.view : 'weapon_item';
        const extraData = { section, category: cat, item, catalog };
        const wanted = { 'УРОН': 1, 'ЦЕНА': 1, 'ВЕС': 1, 'ТИП УРОНА': 1 };
        const stats = (item.stats || [])
          .filter((row) => wanted[row[0]])
          .map((row) => row[0].toLowerCase() + ': ' + row[1])
          .join(', ');
        push(base + '/' + cat.slug + '/' + item.slug,
          Views[viewName](extraData), item.name, {
            description: [item.name, cat.title].filter(Boolean).join(' — ') +
              (stats ? '. ' + stats + '.' : ''),
            breadcrumbs: [
              ['/snaryazhenie/', 'Снаряжение'],
              ['/' + base + '/', section.title],
              ['/' + base + '/' + cat.slug + '/', cat.title],
              ['/' + base + '/' + cat.slug + '/' + item.slug + '/', item.name],
            ],
          });
      });
    });
  });

  /* происхождения: хаб и детали */
  const origins = readJson('origins');
  if (origins) {
    push('proiskhozhdeniya', Views.origins({ page: origins }), origins.title || 'Происхождения', {
      description: origins.lead || '',
      breadcrumbs: [['/proiskhozhdeniya/', origins.title || 'Происхождения']],
    });
  }
  const originPages = (readJson('origins.pages') || {}).pages || {};
  Object.keys(originPages).forEach((slug) => {
    const data = originPages[slug];
    push('proiskhozhdeniya/' + slug, Views.origin({ page: data }), data.title, {
      description: (data.blocks || []).map((b) => b.text).join(' ').slice(0, 180),
      breadcrumbs: [
        ['/proiskhozhdeniya/', 'Происхождения'],
        ['/proiskhozhdeniya/' + slug + '/', data.title],
      ],
    });
  });

  /* примеры типов страниц: NPC, броня, еда, препарат */
  const variants = readJson('variants');
  if (variants) {
    const views = { creature_item: 1, armor_item: 1, food_item: 1, weapon_item: 1 };
    push('primery', Views.examples({ page: variants }), variants.title || 'Примеры', {
      description: variants.lead || '',
      breadcrumbs: [['/primery/', variants.title || 'Примеры']],
    });
    (variants.examples || []).forEach((item) => {
      const view = views[item.view] ? item.view : 'weapon_item';
      push('primery/' + item.slug, Views[view]({ item, category: {}, section: {} }), item.name, {
        description: [item.name, item.category, item.note].filter(Boolean).join(' — '),
        breadcrumbs: [['/primery/', 'Примеры'], ['/primery/' + item.slug + '/', item.name]],
      });
    });
  }

  /* блог: список и статьи */
  const blog = readJson('blog');
  if (blog) {
    push('blog', Views.list({ page: blog }), blog.title || 'Блог', {
      breadcrumbs: [['/blog/', blog.title || 'Блог']],
    });
    const posts = blog.posts || {};
    Object.keys(posts).forEach((slug) => {
      const post = posts[slug];
      push('blog/' + slug, Views.article({ page: post }), post.title, {
        description: (post.blocks || []).map((b) => b.text || '').join(' ').slice(0, 180),
        breadcrumbs: [['/blog/', 'Блог'], ['/blog/' + slug + '/', post.title]],
      });
    });
  }

  /* пишем: адреса каталога — раньше заглушек, те же пути перезаписываем */
  const urls = [];
  jobs.forEach((job) => {
    const dir = path.join(DOCS, job.dir);
    fs.mkdirSync(dir, { recursive: true });
    const node = job.node;
    let html = page(catalog, {
      node,
      title: job.title,
      description: job.description,
      breadcrumbs: job.breadcrumbs,
    });
    html = fillChrome(html, catalog, '/' + job.dir + '/');
    fs.writeFileSync(path.join(dir, 'index.html'), html, 'utf8');
    urls.push('/' + job.dir + (job.dir ? '/' : ''));
  });

  writeSitemap(urls);
  console.log('предрендер: %d страниц', jobs.length);
  return urls;
}

if (require.main === module) {
  build();
}

module.exports = { build, serialize, makeNode };
