/* Общие кирпичики для всех типов страниц.
   Никаких фреймворков: обычные функции, создающие DOM. */
(function () {
  'use strict';

  var BASE = document.body.getAttribute('data-base') || '';

  var ARROW = '<svg viewBox="0 0 66 43" aria-hidden="true" class="tile__svg">' +
    '<path d="M40.15 3.9 43.98.14a.66.66 0 0 1 .7 0l21.01 20.64a1 1 0 0 1 0 1.43' +
    'L44.68 42.86a.66.66 0 0 1-.7 0l-3.83-3.75a.66.66 0 0 1 0-.71l16.84-16.54' +
    'a.5.5 0 0 0 0-.71L40.15 4.61a.66.66 0 0 1 0-.71Z"/></svg>';

  var C = {};

  C.BASE = BASE;
  C.ARROW = ARROW;

  C.href = function (path) {
    if (!path) { return '#'; }
    if (/^https?:/.test(path)) { return path; }
    return BASE + path;
  };

  C.el = function (tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) { node.className = cls; }
    if (text !== undefined && text !== null) { node.textContent = String(text); }
    return node;
  };

  C.link = function (href, cls, text) {
    var a = C.el('a', cls, text);
    a.setAttribute('href', C.href(href));
    return a;
  };


  /* Шеврон-кнопка «Подробнее». Один кирпичик на все страницы: тот же HTML
     пишется и предрендером, и браузером, иначе анимация стрелки ломается.
     Текст обёрнут в <span> — на него возвращается обратный скос, который
     кнопка получает через transform: skewX(-15deg). */
  C.CTA_ARROW = '<svg class="cta__arrow" width="36" height="23" viewBox="0 0 66 43"' +
    ' aria-hidden="true" focusable="false"><g fill="#FFFFFF">' +
    '<path class="a1" d="M40.15 3.9 43.98.14a.66.66 0 0 1 .7 0l21.01 20.64a1 1 0 0 1 0 1.43' +
    'L44.68 42.86a.66.66 0 0 1-.7 0l-3.83-3.75a.66.66 0 0 1 0-.71l16.84-16.54a.5.5 0 0 0 0-.71' +
    'L40.15 4.61a.66.66 0 0 1 0-.71Z"/>' +
    '<path class="a2" d="M20.15 3.9 23.98.14a.66.66 0 0 1 .7 0l21.01 20.64a1 1 0 0 1 0 1.43' +
    'L24.68 42.86a.66.66 0 0 1-.7 0l-3.83-3.75a.66.66 0 0 1 0-.71l16.84-16.54a.5.5 0 0 0 0-.71' +
    'L20.15 4.61a.66.66 0 0 1 0-.71Z"/>' +
    '<path class="a3" d="M.15 3.9 3.98.14a.66.66 0 0 1 .7 0l21.01 20.64a1 1 0 0 1 0 1.43L4.68 42.86' +
    'a.66.66 0 0 1-.7 0L.15 39.11a.66.66 0 0 1 0-.71l16.84-16.54a.5.5 0 0 0 0-.71L.15 4.61' +
    'a.66.66 0 0 1 0-.71Z"/></g></svg>';

  C.cta = function (href, label) {
    var a = C.link(href, 'cta');
    a.appendChild(C.el('span', null, label || 'Подробнее'));
    a.innerHTML += C.CTA_ARROW;
    return a;
  };

  /* Плитка: заголовок — картинка — шеврон. Та же, что на хабах. */
  C.tile = function (opts) {
    var a = C.link(opts.href, 'tile');
    a.appendChild(C.el('h2', 'tile__title', opts.title));
    var media = C.el('div', 'tile__media' + (opts.image ? '' : ' tile__media--empty'));
    if (opts.image) {
      var img = document.createElement('img');
      img.src = C.href(opts.image);
      img.alt = opts.title;
      img.loading = 'lazy';
      media.appendChild(img);
    }
    a.appendChild(media);
    var arrow = C.el('div', 'tile__arrow');
    arrow.innerHTML = ARROW;
    a.appendChild(arrow);
    return a;
  };

  C.tiles = function (items, cols) {
    var row = C.el('div', 'row g-3 tiles-row');
    items.forEach(function (item) {
      var col = C.el('div', cols || 'col-12 col-md-6 col-lg-4');
      col.appendChild(item);
      row.appendChild(col);
    });
    return row;
  };

  C.back = function (href, text) {
    var p = C.el('p', 'wcard__back');
    p.appendChild(C.link(href, '', text));
    return p;
  };

  C.table = function (rows, cls) {
    var table = C.el('table', cls || 'wstats');
    var tbody = C.el('tbody');
    rows.forEach(function (row) {
      var tr = C.el('tr');
      var th = C.el('th', null, row[0]);
      th.setAttribute('scope', 'row');
      tr.appendChild(th);
      tr.appendChild(C.el('td', null, row[1]));
      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    return table;
  };

  /* Div-таблица: шапка + строки. На ПК — колонки, на мобильном — 2 колонки
     с подписями из .wmods__label (см. CSS). */
  /* Текст с {CD} → текст с иконкой боевого кубика. Общая замена для
     таблиц, где иконка стоит внутри значения. */
  C.diceText = function (value) {
    var parts = String(value === undefined || value === null ? '' : value).split('{CD}');
    if (parts.length === 1) { return document.createTextNode(parts[0]); }
    var frag = document.createDocumentFragment();
    parts.forEach(function (part, i) {
      if (i) {
        var img = document.createElement('img');
        img.className = 'cd-icon';
        img.src = C.href('/assets/img/CD.png');
        img.alt = 'Боевой кубик';
        frag.appendChild(img);
      }
      if (part) { frag.appendChild(document.createTextNode(part)); }
    });
    return frag;
  };

  C.divTable = function (head, rows) {
    var wrap = C.el('div', 'wmods');
    var headNode = C.el('div', 'wmods__head');
    head.forEach(function (title) { headNode.appendChild(C.el('div', null, title)); });
    wrap.appendChild(headNode);
    rows.forEach(function (cells) {
      var row = C.el('div', 'wmods__row');
      cells.forEach(function (value, i) {
        var cell = C.el('div', 'wmods__c');
        cell.appendChild(C.el('span', 'wmods__label', head[i] || ''));
        var val = C.el('div', 'wmods__v');
        val.appendChild(C.diceText(value));
        cell.appendChild(val);
        row.appendChild(cell);
      });
      wrap.appendChild(row);
    });
    return wrap;
  };

  /* Спойлер: заголовок + содержимое (узел или массив узлов). */
  C.spoiler = function (title, count, content) {
    var details = C.el('details', 'spoiler');
    var summary = C.el('summary', 'spoiler__summary', title + ' ');
    if (count) {
      summary.appendChild(C.el('span', 'wmods-group__count', '(' + count + ')'));
    }
    details.appendChild(summary);
    var body = C.el('div', 'spoiler__body');
    (Array.isArray(content) ? content : [content]).forEach(function (node) {
      if (node) { body.appendChild(node); }
    });
    details.appendChild(body);
    return details;
  };

  /* Блок с тенью — «плашка» сайта. */
  C.shadowBlock = function (title, content) {
    var box = C.el('div', 'cell cell--shadow rich-block');
    if (title) { box.appendChild(C.el('h2', 'cell__title', title)); }
    (Array.isArray(content) ? content : [content]).forEach(function (node) {
      if (node) { box.appendChild(node); }
    });
    return box;
  };

  C.paragraphs = function (text) {
    return String(text || '').split(/\n{2,}/).filter(Boolean).map(function (part) {
      return C.el('p', 'cell__text', part.trim());
    });
  };

  window.C = C;
}());
