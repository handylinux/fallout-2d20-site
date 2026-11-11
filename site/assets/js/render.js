/* Шаблоны страниц. Данные приходят из catalog.json, разметка — вот она.
   Ничего не генерируется: захочешь поменять вид — правишь этот файл. */
(function () {
  'use strict';

  var BASE = (document.body.getAttribute('data-base') || '');

  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) { node.className = cls; }
    if (text !== undefined && text !== null) { node.textContent = String(text); }
    return node;
  }

  function link(href, cls, text) {
    var a = el('a', cls, text);
    a.setAttribute('href', href);
    return a;
  }

  /* Шеврон «Подробнее» — тот же SVG, что и в остальных плитках сайта. */
  var ARROW = '<svg viewBox="0 0 66 43" aria-hidden="true" class="tile__svg">' +
    '<path d="M40.15 3.9 43.98.14a.66.66 0 0 1 .7 0l21.01 20.64a1 1 0 0 1 0 1.43' +
    'L44.68 42.86a.66.66 0 0 1-.7 0l-3.83-3.75a.66.66 0 0 1 0-.71l16.84-16.54' +
    'a.5.5 0 0 0 0-.71L40.15 4.61a.66.66 0 0 1 0-.71Z"/></svg>';

  var Render = {};

  /* ---------------------------------------------------------------- хаб раздела */
  Render.section = function (section) {
    var frag = document.createDocumentFragment();
    frag.appendChild(el('h1', 'page__title', section.title));
    var row = el('div', 'row g-3 tiles-row');
    section.categories.forEach(function (cat) {
      var col = el('div', 'col-12 col-md-6 col-lg-4');
      var a = link(BASE + '/snaryazhenie/' + section.slug + '/' + cat.slug + '/', 'tile');
      a.innerHTML = ARROW;
      var t = el('h2', 'tile__title', cat.title);
      var media = el('div', 'tile__media tile__media--empty');
      var arrow = el('div', 'tile__arrow');
      arrow.innerHTML = ARROW;
      a.insertBefore(t, a.firstChild);
      a.insertBefore(media, arrow);
      col.appendChild(a);
      row.appendChild(col);
    });
    frag.appendChild(row);
    return frag;
  };

  /* ------------------------------------------------------------ категория */
  Render.category = function (section, cat) {
    var frag = document.createDocumentFragment();
    var back = el('p', 'wcard__back');
    back.appendChild(link(BASE + '/snaryazhenie/' + section.slug + '/',
                          '', 'Назад в ' + section.title.toLowerCase()));
    frag.appendChild(back);
    frag.appendChild(el('h1', 'page__title', cat.title));
    frag.appendChild(el('p', 'page__lead', cat.items.length + ' единиц.'));

    var row = el('div', 'row g-3 tiles-row');
    cat.items.forEach(function (item) {
      var col = el('div', 'col-12 col-md-6 col-lg-4');
      var a = link(BASE + '/snaryazhenie/' + section.slug + '/' + cat.slug + '/' +
                   item.slug + '/', 'tile');
      a.appendChild(el('h2', 'tile__title', item.name));
      a.appendChild(el('div', 'tile__media tile__media--empty'));
      var arrow = el('div', 'tile__arrow');
      arrow.innerHTML = ARROW;
      a.appendChild(arrow);
      col.appendChild(a);
      row.appendChild(col);
    });
    frag.appendChild(row);
    return frag;
  };

  /* ---------------------------------------------------------------- карточка */
  function statsTable(item) {
    var table = el('table', 'wstats');
    var tbody = el('tbody');
    item.stats.forEach(function (row) {
      var tr = el('tr');
      var th = el('th', null, row[0]);
      th.setAttribute('scope', 'row');
      tr.appendChild(th);
      tr.appendChild(el('td', null, row[1]));
      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    return table;
  }

  /* Моды: слот — спойлер, внутри div-таблица.
     ПК: строка = 8 колонок, мобильный (CSS ≤760px): 2 колонки с подписями. */
  function modsBlock(group) {
    var details = el('details', 'spoiler wmods-group');
    var summary = el('summary', 'spoiler__summary', group.slot + ' ');
    summary.appendChild(el('span', 'wmods-group__count', '(' + group.rows.length + ')'));
    details.appendChild(summary);

    var body = el('div', 'spoiler__body wmods');
    var head = el('div', 'wmods__head');
    group.head.forEach(function (title) { head.appendChild(el('div', null, title)); });
    body.appendChild(head);

    group.rows.forEach(function (cells) {
      var row = el('div', 'wmods__row');
      cells.forEach(function (value, i) {
        var cell = el('div', 'wmods__c');
        cell.appendChild(el('span', 'wmods__label', group.head[i]));
        cell.appendChild(document.createTextNode(value));
        row.appendChild(cell);
      });
      body.appendChild(row);
    });

    details.appendChild(body);
    return details;
  }

  Render.item = function (section, cat, item) {
    var frag = document.createDocumentFragment();
    var back = el('p', 'wcard__back');
    back.appendChild(link(BASE + '/snaryazhenie/' + section.slug + '/' + cat.slug + '/',
                          '', 'Назад в категорию: ' + cat.title));
    frag.appendChild(back);
    frag.appendChild(el('h2', 'wcard__title', item.name));

    var card = el('div', 'wcard');
    var row = el('div', 'wcard__row');
    row.appendChild(el('div', 'wcard__media wcard__media--empty'));
    var stats = el('div', 'wcard__stats');
    stats.appendChild(statsTable(item));
    row.appendChild(stats);
    card.appendChild(row);

    if (item.flavour) { card.appendChild(el('p', 'wcard__text', item.flavour)); }
    (item.notes || []).forEach(function (note) {
      card.appendChild(el('h2', 'wcard__sub', 'Примечание'));
      card.appendChild(el('p', 'wcard__note', note));
    });

    if (item.mods && item.mods.length) {
      var sectionNode = el('section', 'wcard__mods');
      sectionNode.appendChild(el('h2', 'wcard__sub', 'Модификации'));
      item.mods.forEach(function (group) { sectionNode.appendChild(modsBlock(group)); });
      card.appendChild(sectionNode);
    }

    frag.appendChild(card);
    return frag;
  };

  Render.notFound = function () {
    var frag = document.createDocumentFragment();
    frag.appendChild(el('h1', 'page__title', 'Страница не найдена'));
    frag.appendChild(el('p', 'page__lead', 'Такого раздела в данных нет.'));
    return frag;
  };

  window.Render = Render;
}());
