/* Тип страницы: хаб раздела (список категорий) и хаб «Снаряжение». */
(function () {
  'use strict';
  var C = window.C;
  window.Views = window.Views || {};

  window.Views.section = function (data) {
    var section = data.section;
    var frag = document.createDocumentFragment();
    frag.appendChild(C.el('h1', 'page__title', section.title));
    if (section.lead) { frag.appendChild(C.el('p', 'page__lead', section.lead)); }
    frag.appendChild(C.tiles(section.categories.map(function (cat) {
      return C.tile({
        title: cat.title,
        href: '/snaryazhenie/' + section.slug + '/' + cat.slug + '/',
        image: cat.image,
      });
    })));
    return frag;
  };

  window.Views.snaryazhenie = function (data) {
    var frag = document.createDocumentFragment();
    frag.appendChild(C.el('h1', 'page__title', 'Снаряжение'));
    frag.appendChild(C.tiles((data.catalog.sections || []).map(function (s) {
      return C.tile({
        title: s.title,
        href: '/snaryazhenie/' + s.slug + '/',
        image: s.image,
      });
    })));
    return frag;
  };
}());
