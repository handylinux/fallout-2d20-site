/* Тип страницы: броня. Вместо «Урона» — защита, вместо слотов оружия —
   зоны тела и материалы. Всё из данных. */
(function () {
  'use strict';
  var C = window.C;
  window.Views = window.Views || {};

  window.Views.armor_item = function (data) {
    var item = data.item;
    var frag = document.createDocumentFragment();
    frag.appendChild(C.back('/primery/', 'Назад к примерам'));
    frag.appendChild(C.el('h1', 'page__title', item.name));
    if (item.category) { frag.appendChild(C.el('p', 'page__lead', item.category)); }

    var card = C.el('div', 'wcard');
    var row = C.el('div', 'wcard__row');
    row.appendChild(item.image
      ? imageCell(item) : C.el('div', 'wcard__media wcard__media--empty'));
    var stats = C.el('div', 'wcard__stats');
    stats.appendChild(C.table(item.stats || []));
    row.appendChild(stats);
    card.appendChild(row);
    frag.appendChild(card);

    if ((item.locations || []).length) {
      frag.appendChild(C.shadowBlock('Зоны тела', C.table(item.locations)));
    }

    if ((item.mods || []).length) {
      var mods = C.el('section', 'wcard__mods');
      mods.appendChild(C.el('h2', 'wcard__sub', 'Модификации'));
      item.mods.forEach(function (group) {
        mods.appendChild(C.spoiler(group.slot, group.rows.length,
                                   C.divTable(group.head, group.rows)));
      });
      frag.appendChild(mods);
    }

    if (item.note) { frag.appendChild(C.el('p', 'wcard__note', item.note)); }
    return frag;
  };

  function imageCell(item) {
    var media = C.el('div', 'wcard__media');
    var img = document.createElement('img');
    img.className = 'wcard__img';
    img.src = C.href(item.image);
    img.alt = item.name;
    media.appendChild(img);
    return media;
  }
}());
