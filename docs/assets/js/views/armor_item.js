/* Тип страницы: броня. Образец —
   fallout-2d20.ru/bronya/silovaya-bronya/ekskavatornaya-silovaya-bronya

   Раскладка (как в образце):
     1) назад в категорию + H1
     2) строка из двух колонок: слева картинка, справа части брони сеткой 2×2 —
        подпись части по центру, под ней компактная таблица характеристик
     3) описание во всю ширину (абзацы из {text: [...]})
     4) «Особенность:» — абзац, без заголовка
     5) произвольные блоки из данных: split (текст | таблица), text, table, spoiler
        Блок «Добыча полезных ископаемых» — жёлтая плашка с золотой полосой слева
     6) «Поддерживаемые модификации» — заголовок по центру, золотая полоса
        «Модификации системы», ниже плоский список строк-спойлеров:
        название слева, стрелка справа, внутри таблица модификации
   Ни одного зашитого числа: сколько частей, сколько колонок — из данных.
*/
(function () {
  'use strict';
  var C = window.C;
  window.Views = window.Views || {};

  /* {CD} → иконка боевого кубика, как в образце */
  function withDice(text) {
    var span = C.el('span');
    var parts = String(text === undefined || text === null ? '' : text).split('{CD}');
    parts.forEach(function (part, i) {
      if (i) {
        var img = document.createElement('img');
        img.className = 'cd-icon';
        img.src = C.href('/assets/img/CD.png');
        img.alt = 'Боевой кубик';
        span.appendChild(img);
      }
      if (part) { span.appendChild(document.createTextNode(part)); }
    });
    return span;
  }

  /* компактная таблица характеристик: чёрная подпись, бежевое значение */
  function statsTable(rows) {
    var table = C.el('table', 'armor__stats');
    var tbody = C.el('tbody');
    (rows || []).forEach(function (row) {
      var tr = C.el('tr');
      var th = C.el('th', null, row[0]);
      th.setAttribute('scope', 'row');
      tr.appendChild(th);
      var td = C.el('td');
      td.appendChild(withDice(row[1]));
      tr.appendChild(td);
      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    return table;
  }

  /* table — настоящая таблица (так её видят поисковики и копирование) */
  function grid(head, rows) {
    var table = C.el('table', 'armor__grid');
    var thead = C.el('thead');
    var tr = C.el('tr');
    head.forEach(function (title) { tr.appendChild(C.el('th', null, title)); });
    thead.appendChild(tr);
    table.appendChild(thead);
    var tbody = C.el('tbody');
    rows.forEach(function (cells) {
      var row = C.el('tr');
      cells.forEach(function (value) {
        var cell = C.el('td');
        cell.appendChild(withDice(value));
        row.appendChild(cell);
      });
      tbody.appendChild(row);
    });
    table.appendChild(tbody);
    return table;
  }

  /* один блок «раскрывающаяся строка» */
  function modRow(title, body) {
    var details = C.el('details', 'armor__mod');
    var summary = C.el('summary', 'armor__mod-summary');
    summary.appendChild(C.el('span', 'armor__mod-name', title));
    summary.appendChild(C.el('span', 'armor__mod-arrow'));
    details.appendChild(summary);
    var wrap = C.el('div', 'armor__mod-body');
    wrap.appendChild(body);
    details.appendChild(wrap);
    return details;
  }

  window.Views.armor_item = function (data) {
    var item = data.item || (data.detail && data.detail) || {};
    var frag = document.createDocumentFragment();

    frag.appendChild(C.back(item.back || '/bronya/', item.backText || 'Назад в категорию: Броня'));
    frag.appendChild(C.el('h1', 'page__title', item.name || ''));

    /* 1. картинка | части сеткой 2×2 */
    var row1 = C.el('div', 'armor-row armor-row--2 armor-row--top');
    var media = C.el('div', 'wcard__media armor__media');
    if (item.image) {
      var img = document.createElement('img');
      img.className = 'wcard__img armor__img';
      img.src = C.href(item.image);
      img.alt = item.name || '';
      media.appendChild(img);
    } else {
      media.className += ' wcard__media--empty';
    }
    row1.appendChild(media);

    var parts = C.el('div', 'armor__parts');
    (item.pieces || []).forEach(function (piece) {
      var cell = C.el('div', 'armor__part');
      cell.appendChild(C.el('h2', 'armor__part-title', piece.area || piece.areaName || ''));
      cell.appendChild(statsTable(piece.stats));
      parts.appendChild(cell);
    });
    row1.appendChild(parts);
    frag.appendChild(row1);

    /* 2. описание во всю ширину */
    var texts = item.description;
    if (typeof texts === 'string') { texts = [texts]; }
    if (texts && texts.length) {
      var desc = C.el('div', 'armor-row armor-row--1 armor__desc');
      texts.forEach(function (t) { desc.appendChild(C.el('p', 'armor__text', t)); });
      frag.appendChild(desc);
    }

    /* 3. «Особенность» — абзац без заголовка */
    if (item.feature) {
      var feature = C.el('p', 'armor__text armor__feature');
      feature.appendChild(C.el('strong', 'armor__label', 'Особенность: '));
      feature.appendChild(withDice(item.feature));
      frag.appendChild(feature);
    }

    /* 4. свои блоки из данных */
    (item.sections || []).forEach(function (section) {
      var box = C.el('div', 'armor-row armor-row--1 armor-block');
      if (section.title) { box.appendChild(C.el('h2', 'armor-block__title', section.title)); }

      if (section.type === 'split') {
        var split = C.el('div', 'armor-block__split');
        var colText = C.el('div', 'armor-block__text');
        (section.texts || [section.text]).forEach(function (t) {
          if (t) { colText.appendChild(C.el('p', 'armor__text', t)); }
        });
        split.appendChild(colText);
        var colTable = C.el('div', 'armor-block__table');
        colTable.appendChild(grid(section.head || [], section.rows || []));
        split.appendChild(colTable);
        box.appendChild(split);
      } else {
        (section.texts || [section.text]).forEach(function (t) {
          if (t) { box.appendChild(C.el('p', 'armor__text', t)); }
        });
        if (section.rows) {
          box.appendChild(grid(section.head || [], section.rows));
        }
      }
      frag.appendChild(box);
    });

    /* 5. поддерживаемые модификации — плоский список строк */
    var rows = [];
    (item.mods || []).forEach(function (group) {
      (group.rows || []).forEach(function (r) { rows.push(r); });
    });
    if (rows.length) {
      var mods = C.el('section', 'armor-mods');
      mods.appendChild(C.el('h2', 'armor-mods__title', 'Поддерживаемые модификации'));
      mods.appendChild(C.el('div', 'armor-mods__bar', 'Модификации системы'));
      var head = item.modHead || ['Модификация', 'Эффект', 'Часть брони', 'Вес', 'Цена', 'Перки', 'Навык'];
      rows.forEach(function (r) {
        /* как в оружии: div-таблица, на узком экране — вертикальная */
        var body = C.divTable(head, [r]);
        body.className += ' wmods--armor';
        mods.appendChild(modRow(r[0], body));
      });
      frag.appendChild(mods);
    }

    return frag;
  };
}());
