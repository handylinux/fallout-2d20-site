/* Тип страницы: существо/NPC. Набор строк задают данные:
   сколько в stats, special, attacks, abilities — столько и отрисуется. */
(function () {
  'use strict';
  var C = window.C;
  window.Views = window.Views || {};

  window.Views.creature_item = function (data) {
    var item = data.item;
    var frag = document.createDocumentFragment();
    frag.appendChild(C.back('/primery/', 'Назад к примерам'));
    frag.appendChild(C.el('h1', 'page__title', item.name));
    if (item.category) { frag.appendChild(C.el('p', 'page__lead', item.category)); }

    /* характеристики — любое число строк */
    if ((item.stats || []).length) {
      frag.appendChild(C.shadowBlock('Характеристики', C.table(item.stats)));
    }

    /* SPECIAL — свой набор, своя таблица */
    if ((item.special || []).length) {
      frag.appendChild(C.shadowBlock('S.P.E.C.I.A.L.', C.table(item.special)));
    }

    /* атаки — произвольные колонки */
    if ((item.attacks || []).length) {
      frag.appendChild(C.shadowBlock('Атаки',
        C.divTable(item.attacks[0].length === 4
          ? ['Атака', 'Урон', 'Тип', 'Дистанция']
          : ['Атака'], item.attacks)));
    }

    /* особенности — спойлеры */
    if ((item.abilities || []).length) {
      var box = C.el('div', '');
      item.abilities.forEach(function (ability) {
        box.appendChild(C.spoiler(ability[0], 0, C.el('p', 'cell__text', ability[1])));
      });
      frag.appendChild(C.shadowBlock('Особенности', box));
    }

    if (item.note) { frag.appendChild(C.el('p', 'wcard__note', item.note)); }
    return frag;
  };
}());
