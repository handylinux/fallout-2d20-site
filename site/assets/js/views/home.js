/* Тип страницы: главная / правила игры. */
(function () {
  'use strict';
  var C = window.C;
  window.Views = window.Views || {};

  window.Views.home = function (data) {
    var frag = document.createDocumentFragment();
    frag.appendChild(C.el('h1', 'page__title', 'Правила игры'));
    frag.appendChild(C.el('p', 'page__lead',
      'Справочник по Fallout 2D20: снаряжение, оружие и модификации, происхождения.'));
    var sections = (data && data.catalog && data.catalog.sections) || [];
    if (sections.length) {
      frag.appendChild(C.tiles(sections.map(function (s) {
        return C.tile({
          title: s.title,
          href: '/snaryazhenie/' + s.slug + '/',
          image: s.image,
        });
      })));
    }
    return frag;
  };
}());
