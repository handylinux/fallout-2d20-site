/* Роутер: адрес → данные → тип страницы из window.Views.
   Страницы на диске не генерируются: один каркас, много типов. */
(function () {
  'use strict';

  var BASE = document.body.getAttribute('data-base') || '';
  var app = document.getElementById('app');
  if (!app) { return; }

  var cache = {};

  function get(name) {
    if (cache[name]) { return Promise.resolve(cache[name]); }
    return fetch(BASE + '/assets/data/' + name + '.json', { credentials: 'same-origin' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (json) { cache[name] = json; return json; });
  }

  function path() {
    var p = window.location.pathname;
    if (BASE && p.indexOf(BASE) === 0) { p = p.slice(BASE.length); }
    return p.replace(/\/+$/, '') || '/';
  }

  function seg() { return path().split('/').filter(Boolean); }

  function paint(node, title) {
    app.innerHTML = '';
    app.appendChild(node);
    app.setAttribute('aria-busy', 'false');
    document.title = (title ? title + ' — ' : '') + 'Fallout 2D20';
    window.scrollTo(0, 0);
  }

  function notFound(title) {
    var frag = document.createDocumentFragment();
    frag.appendChild(window.C.el('h1', 'page__title', title || 'Страница не найдена'));
    frag.appendChild(window.C.el('p', 'page__lead',
      'Такого адреса в данных нет. Проверьте ссылку или меню.'));
    return frag;
  }

  function pick(sectionSlug, catSlug, itemSlug, catalog) {
    var section = null, cat = null, item = null;
    (catalog.sections || []).forEach(function (s) {
      if (s.slug === sectionSlug) { section = s; }
    });
    if (!section) { return null; }
    (section.categories || []).forEach(function (c) {
      if (c.slug === catSlug) { cat = c; }
    });
    if (!cat) { return { section: section, category: null, item: null }; }
    (cat.items || []).forEach(function (i) { if (i.slug === itemSlug) { item = i; } });
    return { section: section, category: cat, item: item };
  }

  function renderNav(catalog) {
    var holder = document.getElementById('drawer-nav');
    if (!holder || !catalog) { return; }
    holder.innerHTML = '';
    (catalog.sections || []).forEach(function (s) {
      var li = document.createElement('li');
      li.appendChild(window.C.link('/snaryazhenie/' + s.slug + '/', '', s.title));
      var btn = document.createElement('button');
      btn.className = 'drawer__toggle';
      btn.type = 'button';
      btn.setAttribute('aria-expanded', 'false');
      btn.innerHTML = '<span class="visually-hidden">Раскрыть «' + s.title + '»</span>';
      li.appendChild(btn);
      var sub = document.createElement('ul');
      sub.className = 'drawer__sub';
      (s.categories || []).forEach(function (c) {
        var cli = document.createElement('li');
        cli.appendChild(window.C.link('/snaryazhenie/' + s.slug + '/' + c.slug + '/', '', c.title));
        sub.appendChild(cli);
      });
      li.appendChild(sub);
      holder.appendChild(li);
      btn.addEventListener('click', function () {
        var open = !sub.classList.contains('is-open');
        sub.classList.toggle('is-open', open);
        btn.setAttribute('aria-expanded', String(open));
      });
    });
  }

  var routes = [
    /* /proiskhozhdeniya/ */
    { re: /^\/proiskhozhdeniya$/, data: 'origins', view: 'origins' },
    { re: /^\/proiskhozhdeniya\/([^/]+)$/, data: 'origins.pages', view: 'origin',
      bySlug: true },
    /* /blog/ и /blog/<slug>/ */
    { re: /^\/blog$/, data: 'blog', view: 'list' },
    { re: /^\/blog\/([^/]+)$/, data: 'blog', view: 'article', bySlug: true },
    /* каталог снаряжения */
    { re: /^\/snaryazhenie$/, view: 'snaryazhenie' },
    { re: /^\/snaryazhenie\/([^/]+)$/, view: 'section' },
    { re: /^\/snaryazhenie\/([^/]+)\/([^/]+)$/, view: 'category' },
    { re: /^\/snaryazhenie\/([^/]+)\/([^/]+)\/([^/]+)$/, view: 'weapon_item' },
  ];

  function route() {
    var p = path();
    var segs = seg();
    if (segs.length === 0) {
      var home = document.createDocumentFragment();
      home.appendChild(window.C.el('h1', 'page__title', 'Правила игры'));
      paint(home, 'Правила игры');
      return;
    }

    var matched = null;
    routes.some(function (r) {
      var m = p.match(r.re);
      if (m) { matched = { route: r, match: m }; return true; }
      return false;
    });

    if (!matched) {
      paint(notFound(), 'Не найдено');
      return;
    }

    var routeDef = matched.route;

    if (!routeDef.data && routeDef.view !== 'snaryazhenie') {
      /* раздел каталога */
      get('catalog').then(function (catalog) {
        renderNav(catalog);
        var data = { catalog: catalog, page: catalog && catalog.pages && catalog.pages[routeDef.view] };
        if (routeDef.view === 'section') {
          var s = null;
          (catalog.sections || []).forEach(function (x) {
            if (x.slug === matched.match[1]) { s = x; }
          });
          if (!s) { paint(notFound('Нет такого раздела'), 'Не найдено'); return; }
          data.section = s;
          paint(window.Views.section(data), s.title);
          return;
        }
        var found = pick(matched.match[1], matched.match[2], matched.match[3], catalog);
        if (!found || !found.category) { paint(notFound('Нет такой категории'), 'Не найдено'); return; }
        data.section = found.section;
        data.category = found.category;
        if (!matched.match[3]) {
          paint(window.Views.category(data), found.category.title);
          return;
        }
        if (!found.item) { paint(notFound('Нет такого предмета'), 'Не найдено'); return; }
        data.item = found.item;
        var view = window.Views[found.item.view || routeDef.view];
        paint(view(data), found.item.name);
      }).catch(function () {
        paint(notFound('Данные не загрузились'), 'Ошибка');
      });
      return;
    }

    if (routeDef.view === 'snaryazhenie') {
      get('catalog').then(function (catalog) {
        renderNav(catalog);
        paint(window.Views.snaryazhenie({ catalog: catalog }), 'Снаряжение');
      }).catch(function () { paint(notFound('Данные не загрузились'), 'Ошибка'); });
      return;
    }

    get(routeDef.data).then(function (data) {
      if (!data) { paint(notFound(), 'Не найдено'); return; }
      var page = data;
      if (routeDef.bySlug) {
        var slug = matched.match[1];
        page = null;
        var map = (data && data.pages) || (data && data.posts) || {};
        if (Array.isArray(map)) {
          map.forEach(function (row) { if (row.slug === slug) { page = row; } });
        } else if (map[slug]) {
          page = map[slug];
        }
        if (!page) { paint(notFound(), 'Не найдено'); return; }
      }
      paint(window.Views[routeDef.view]({ page: page }), page.title);
    }).catch(function () { paint(notFound('Данные не загрузились'), 'Ошибка'); });
  }

  /* первая отрисовка уже сделана предрендером; роутер включается при переходах */
  if (app.getAttribute('data-prerendered') !== '1') { route(); }
  window.addEventListener('popstate', route);

}());
