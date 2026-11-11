/* Тип страницы: еда и препараты. Модов нет — есть эффекты. */
(function () {
  'use strict';
  var C = window.C;
  window.Views = window.Views || {};

  window.Views.food_item = function (data) {
    var item = data.item;
    var frag = document.createDocumentFragment();
    frag.appendChild(C.back('/primery/', 'Назад к примерам'));
    frag.appendChild(C.el('h1', 'page__title', item.name));
    if (item.category) { frag.appendChild(C.el('p', 'page__lead', item.category)); }
    if ((item.stats || []).length) {
      frag.appendChild(C.shadowBlock('Параметры', C.table(item.stats)));
    }
    if ((item.effects || []).length) {
      frag.appendChild(C.shadowBlock('Эффекты', C.table(item.effects)));
    }
    if (item.note) { frag.appendChild(C.el('p', 'wcard__note', item.note)); }
    return frag;
  };
}());
