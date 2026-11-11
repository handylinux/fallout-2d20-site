/* Тип страницы: броня. Образец —
   fallout-2d20.ru/bronya/silovaya-bronya/ekskavatornaya-silovaya-bronya

   Порядок блоков как в эталоне:
     назад в категорию → H1 → картинка → части брони таблицами
     (ШЛЕМ / ТЕЛО / РУКИ / НОГИ — сколько частей, столько таблиц)
     → описание → «Особенность» → свои секции (текст, таблица, спойлер)
     → «Поддерживаемые модификации»: слот-спойлер → div-таблица
       {Модификация, Эффект, Часть брони, Вес, Цена, Перки, Навык}.
   Ни одного зашитого числа: 4 части или 2, 7 колонок или 5 — из данных.
*/
(function () {
  'use strict';
  var C = window.C;
  window.Views = window.Views || {};

  /* {CD} → иконка боевого кубика, как на эталоне */
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

  function statsTable(rows) {
    var table = C.el('table', 'wstats');
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

  /* div-таблица с иконками кубиков внутри ячеек */
  function divTable(head, rows) {
    var wrap = C.el('div', 'wmods');
    var headNode = C.el('div', 'wmods__head');
    head.forEach(function (title) { headNode.appendChild(C.el('div', null, title)); });
    wrap.appendChild(headNode);
    rows.forEach(function (cells) {
      var row = C.el('div', 'wmods__row');
      cells.forEach(function (value, i) {
        var cell = C.el('div', 'wmods__c');
        cell.appendChild(C.el('span', 'wmods__label', head[i] || ''));
        cell.appendChild(withDice(value));
        row.appendChild(cell);
      });
      wrap.appendChild(row);
    });
    return wrap;
  }

  window.Views.armor_item = function (data) {
    var item = data.item || (data.detail && data.detail) || {};
    var frag = document.createDocumentFragment();

    frag.appendChild(C.back(item.back || '/bronya/', item.backText || 'Назад в категорию: Броня'));
    frag.appendChild(C.el('h1', 'page__title', item.name || ''));

    /* Две колонки, как на эталоне: слева картинка, справа все данные. */
    var row = C.el('div', 'wcard__row armor__row');
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
    row.appendChild(media);

    var side = C.el('div', 'armor__data');
    (item.pieces || []).forEach(function (piece) {
      side.appendChild(C.el('h2', 'armor__part', piece.area || piece.areaName || ''));
      side.appendChild(statsTable(piece.stats));
    });
    row.appendChild(side);
    frag.appendChild(row);

    if (item.description) {
      frag.appendChild(C.el('p', 'armor__text', item.description));
    }
    if (item.feature) {
      var feature = C.el('p', 'armor__text');
      feature.appendChild(C.el('strong', 'armor__label', 'Особенность: '));
      feature.appendChild(withDice(item.feature));
      frag.appendChild(feature);
    }

    /* свои блоки: текст, таблица, спойлер — в любом количестве */
    (item.sections || []).forEach(function (section) {
      if (section.title) {
        frag.appendChild(C.el('h2', 'wcard__sub', section.title));
      }
      if (section.text) {
        frag.appendChild(C.el('p', 'armor__text', section.text));
      }
      if (section.type === 'table' && section.rows) {
        frag.appendChild(divTable(section.head || [], section.rows));
      }
      if (section.type === 'spoiler' && section.rows) {
        frag.appendChild(C.spoiler(section.title, section.rows.length,
                                   divTable(section.head || [], section.rows)));
      }
    });

    /* модификации: слот — спойлер, внутри общая для всех таблица */
    if ((item.mods || []).length) {
      var mods = C.el('section', 'wcard__mods');
      mods.appendChild(C.el('h2', 'wcard__sub', 'Поддерживаемые модификации'));
      var head = item.modHead || ['Модификация', 'Эффект', 'Часть брони', 'Вес', 'Цена', 'Перки', 'Навык'];
      item.mods.forEach(function (group) {
        mods.appendChild(C.spoiler(group.slot, group.rows.length,
                                   divTable(head, group.rows)));
      });
      frag.appendChild(mods);
    }

    return frag;
  };
}());
