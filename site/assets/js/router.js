/* Роутер: адрес → данные каталога → шаблон. Страниц на диске нет. */
(function () {
  'use strict';

  var BASE = document.body.getAttribute('data-base') || '';
  var app = document.getElementById('app');
  if (!app) { return; }

  var catalog = null;

  function loadCatalog() {
    if (catalog) { return Promise.resolve(catalog); }
    return fetch(BASE + '/assets/data/catalog.json', { credentials: 'same-origin' })
      .then(function (r) { return r.json(); })
      .then(function (json) { catalog = json; return catalog; });
  }

  function find(sectionSlug, catSlug, itemSlug) {
    var section = null;
    var cat = null;
    (catalog.sections || []).forEach(function (s) {
      if (s.slug === sectionSlug) { section = s; }
    });
    if (!section) { return { section: null, cat: null, item: null }; }
    (section.categories || []).forEach(function (c) {
      if (c.slug === catSlug) { cat = c; }
    });
    if (!cat || !itemSlug) { return { section: section, cat: cat, item: null }; }
    var item = null;
    (cat.items || []).forEach(function (i) { if (i.slug === itemSlug) { item = i; } });
    return { section: section, cat: cat, item: item };
  }

  /* путь без BASE: /snaryazhenie/oruzhie/… */
  function path() {
    var p = window.location.pathname;
    if (BASE && p.indexOf(BASE) === 0) { p = p.slice(BASE.length); }
    return p.replace(/\/+$/, '') || '/';
  }

  function parts(p) {
    return p.split('/').filter(Boolean);
  }

  function paint(frag, title) {
    app.innerHTML = '';
    app.appendChild(frag);
    app.setAttribute('aria-busy', 'false');
    document.title = (title ? title + ' — ' : '') + 'Fallout 2D20';
    window.scrollTo(0, 0);
  }

  function renderNav() {
    var holder = document.getElementById('drawer-nav');
    if (!holder) { return; }
    holder.innerHTML = '';
    catalog.sections.forEach(function (s) {
      var li = document.createElement('li');
      var a = document.createElement('a');
      a.setAttribute('href', BASE + '/snaryazhenie/' + s.slug + '/');
      a.textContent = s.title;
      li.appendChild(a);

      var btn = document.createElement('button');
      btn.className = 'drawer__toggle';
      btn.type = 'button';
      btn.setAttribute('aria-expanded', 'false');
      btn.innerHTML = '<span class="visually-hidden">Раскрыть «' + s.title + '»</span>';
      li.appendChild(btn);

      var sub = document.createElement('ul');
      sub.className = 'drawer__sub';
      s.categories.forEach(function (c) {
        var cli = document.createElement('li');
        var ca = document.createElement('a');
        ca.setAttribute('href', BASE + '/snaryazhenie/' + s.slug + '/' + c.slug + '/');
        ca.textContent = c.title;
        cli.appendChild(ca);
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

  function route() {
    var p = path();
    var seg = parts(p);

    if (seg.length === 0) {
      paint(window.Render.home ? window.Render.home() : window.Render.notFound(), '');
      return;
    }

    if (seg[0] !== 'snaryazhenie') {
      page_placeholder(seg);
      return;
    }

    loadCatalog().then(function () {
      renderNav();

      /* /snaryazhenie/ — все разделы */
      if (seg.length === 1) {
        var frag = document.createDocumentFragment();
        var h = document.createElement('h1');
        h.className = 'page__title';
        h.textContent = 'Снаряжение';
        frag.appendChild(h);
        var row = document.createElement('div');
        row.className = 'row g-3 tiles-row';
        catalog.sections.forEach(function (s) {
          var col = document.createElement('div');
          col.className = 'col-12 col-md-6 col-lg-4';
          var a = document.createElement('a');
          a.className = 'tile';
          a.setAttribute('href', BASE + '/snaryazhenie/' + s.slug + '/');
          a.innerHTML = window.Render_tile ? '' : '';
          var t = document.createElement('h2');
          t.className = 'tile__title';
          t.textContent = s.title;
          a.appendChild(t);
          var media = document.createElement('div');
          media.className = 'tile__media tile__media--empty';
          a.appendChild(media);
          var arrow = document.createElement('div');
          arrow.className = 'tile__arrow';
          arrow.innerHTML = '<svg viewBox="0 0 66 43" aria-hidden="true" class="tile__svg">' +
            '<path d="M40.15 3.9 43.98.14a.66.66 0 0 1 .7 0l21.01 20.64a1 1 0 0 1 0 1.43' +
            'L44.68 42.86a.66.66 0 0 1-.7 0l-3.83-3.75a.66.66 0 0 1 0-.71l16.84-16.54' +
            'a.5.5 0 0 0 0-.71L40.15 4.61a.66.66 0 0 1 0-.71Z"/></svg>';
          a.appendChild(arrow);
          col.appendChild(a);
          row.appendChild(col);
        });
        frag.appendChild(row);
        paint(frag, 'Снаряжение');
        return;
      }

      var sectionSlug = seg[1];
      var catSlug = seg[2];
      var itemSlug = seg[3];
      if (!catSlug) {
        var s = null;
        catalog.sections.forEach(function (x) { if (x.slug === sectionSlug) { s = x; } });
        if (!s) { paint(window.Render.notFound(), 'Нет раздела'); return; }
        paint(window.Render.section(s), s.title);
        return;
      }
      var found = find(sectionSlug, catSlug, itemSlug);
      if (!found.cat) { paint(window.Render.notFound(), 'Нет категории'); return; }
      if (!itemSlug) {
        paint(window.Render.category(found.section, found.cat), found.cat.title);
        return;
      }
      if (!found.item) { paint(window.Render.notFound(), 'Нет предмета'); return; }
      paint(window.Render.item(found.section, found.cat, found.item), found.item.name);
    }).catch(function () {
      app.innerHTML = '<h1 class="page__title">Данные не загрузились</h1>' +
        '<p class="page__lead">Проверьте assets/data/catalog.json.</p>';
    });
  }

  function page_placeholder(seg) {
    /* прочие разделы пока живут отдельными страницами (заглушки) */
    window.location.replace(BASE + '/' + seg.join('/') + '/');
  }

  window.addEventListener('popstate', route);
  document.addEventListener('DOMContentLoaded', route);
  if (document.readyState !== 'loading') { route(); }
}());
