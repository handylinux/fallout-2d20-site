/* Тип страницы: список примеров (витрина типов). */
(function () {
  'use strict';
  var C = window.C;
  window.Views = window.Views || {};

  window.Views.examples = function (data) {
    var page = data.page || {};
    var frag = document.createDocumentFragment();
    frag.appendChild(C.el('h1', 'page__title', page.title || 'Примеры'));
    if (page.lead) { frag.appendChild(C.el('p', 'page__lead', page.lead)); }
    frag.appendChild(C.tiles((page.examples || []).map(function (item) {
      return C.tile({
        title: item.name,
        href: '/primery/' + item.slug + '/',
        image: item.image,
      });
    })));
    return frag;
  };
}());
