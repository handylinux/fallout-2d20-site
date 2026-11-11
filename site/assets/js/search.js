/* Поиск по индексу, который сборка вкладывает в страницу (#site-search-data). */
(function () {
  'use strict';

  var openBtn = document.getElementById('search-open');
  var panel = document.getElementById('search-panel');
  var input = document.getElementById('search-input');
  var results = document.getElementById('search-results');
  if (!openBtn || !panel || !input || !results) { return; }

  var url = (document.body.getAttribute('data-base') || '') + '/assets/data/search.json';
  var data = null;
  var loading = null;

  function load() {
    if (data) { return Promise.resolve(data); }
    if (loading) { return loading; }
    loading = fetch(url, { credentials: 'same-origin' })
      .then(function (r) { return r.ok ? r.json() : { items: [] }; })
      .then(function (json) {
        data = (json || {}).items || [];
        index = data.map(build);
        return data;
      })
      .catch(function () { data = []; index = []; return data; });
    return loading;
  }

  function norm(text) {
    return String(text || '').toLowerCase().replace(/ё/g, 'е').replace(/\s+/g, ' ').trim();
  }

  var index = [];
  function build(row) {
    return { row: row, hay: norm((row.n || '') + ' ' + (row.c || '') + ' ' + (row.s || []).join(' ')) };
  }

  function show(on) {
    panel.hidden = !on;
    openBtn.setAttribute('aria-expanded', String(on));
    if (on) {
      input.focus();
      input.select();
      load().then(function () { if (input.value) { search(input.value); } else { render([], ''); } });
    }
  }

  function render(list, query) {
    if (!query) {
      results.innerHTML = '<div class="site-search__empty">Начните печатать: оружие, мод, навык, патрон.</div>';
      return;
    }
    if (!list.length) {
      results.innerHTML = '<div class="site-search__empty">Ничего не найдено.</div>';
      return;
    }
    results.innerHTML = list.slice(0, 20).map(function (row) {
      return '<a class="site-search__hit" href="' + row.u + '">' +
        '<span class="site-search__hit-title">' + row.n + '</span>' +
        '<span class="site-search__hit-meta">' + row.c +
        (row.d && row.d !== '—' ? ' · урон ' + row.d : '') + '</span></a>';
    }).join('');
  }

  function search(query) {
    var q = norm(query);
    if (!data) { return; }
    if (!q) { render([], ''); return; }
    var parts = q.split(' ').filter(Boolean);
    var found = [];
    index.forEach(function (entry) {
      var hay = entry.hay;
      var ok = parts.every(function (p) { return hay.indexOf(p) !== -1; });
      if (!ok) { return; }
      var score = norm(entry.row.n).indexOf(q) === 0 ? 0 : 1;
      found.push({ row: entry.row, score: score });
    });
    found.sort(function (a, b) { return a.score - b.score; });
    render(found.map(function (f) { return f.row; }), q);
  }

  openBtn.addEventListener('click', function (e) {
    e.preventDefault();
    show(panel.hidden);
  });

  input.addEventListener('input', function () { search(input.value); });

  input.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') { show(false); }
    if (e.key === 'Enter') {
      var first = results.querySelector('.site-search__hit');
      if (first) { window.location.href = first.getAttribute('href'); }
    }
  });

  document.addEventListener('click', function (e) {
    if (!panel.hidden && !panel.contains(e.target) && e.target !== openBtn && !openBtn.contains(e.target)) {
      show(false);
    }
  });

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && !panel.hidden) { show(false); }
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
      e.preventDefault();
      show(true);
    }
  });
}());
