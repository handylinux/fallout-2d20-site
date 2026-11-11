/* Тип страницы: карточка предмета с модами (оружие, броня, еда…).
   Отличия от других типов: таблица характеристик, моды по слотам,
   примечания. Моды — слот-спойлер → div-таблица (ПК 8 колонок / мобильный 2). */
(function () {
  'use strict';
  var C = window.C;

  window.Views = window.Views || {};

  window.Views.weapon_item = function (data) {
    var item = data.item;
    var cat = data.category;
    var section = data.section;
    var frag = document.createDocumentFragment();

    frag.appendChild(C.back('/snaryazhenie/' + section.slug + '/' + cat.slug + '/',
                           'Назад в категорию: ' + cat.title));
    frag.appendChild(C.el('h1', 'page__title', item.name));

    var card = C.el('div', 'wcard');
    var row = C.el('div', 'wcard__row');
    if (item.image) {
      var media = C.el('div', 'wcard__media');
      var img = document.createElement('img');
      img.className = 'wcard__img';
      img.src = item.image;
      img.alt = item.name;
      media.appendChild(img);
      row.appendChild(media);
    } else {
      row.appendChild(C.el('div', 'wcard__media wcard__media--empty'));
    }
    var stats = C.el('div', 'wcard__stats');
    stats.appendChild(C.table(item.stats));
    row.appendChild(stats);
    card.appendChild(row);

    if (item.flavour) { card.appendChild(C.el('p', 'wcard__text', item.flavour)); }

    (item.notes || []).forEach(function (note) {
      card.appendChild(C.el('h2', 'wcard__sub', 'Примечание'));
      card.appendChild(C.el('p', 'wcard__note', note));
    });

    if (item.mods && item.mods.length) {
      var mods = C.el('section', 'wcard__mods');
      mods.appendChild(C.el('h2', 'wcard__sub', 'Модификации'));
      item.mods.forEach(function (group) {
        mods.appendChild(C.spoiler(group.slot, group.rows.length,
                                   C.divTable(group.head, group.rows)));
      });
      card.appendChild(mods);
    }

    frag.appendChild(card);

    /* перелинковка: соседи по категории */
    var others = (cat.items || []).filter(function (i) { return i.slug !== item.slug; }).slice(0, 4);
    if (others.length) {
      frag.appendChild(C.el('h2', 'wcard__sub', 'Смотрите также'));
      frag.appendChild(C.tiles(others.map(function (other) {
        return C.tile({
          title: other.name,
          href: '/snaryazhenie/' + section.slug + '/' + cat.slug + '/' + other.slug + '/',
          image: other.image,
        });
      })));
    }

    return frag;
  };
}());
