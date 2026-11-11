/* Тип страницы: список элементов категории плитками. */
(function () {
  'use strict';
  var C = window.C;
  window.Views = window.Views || {};

  window.Views.category = function (data) {
    var section = data.section;
    var cat = data.category;
    var base = section.path || ('/snaryazhenie/' + section.slug);
    var frag = document.createDocumentFragment();

    frag.appendChild(C.back(base + '/', 'Назад в ' + section.title.toLowerCase()));
    frag.appendChild(C.el('h1', 'page__title', cat.title));
    frag.appendChild(C.el('p', 'page__lead', cat.items.length + ' единиц.'));
    frag.appendChild(C.tiles(cat.items.map(function (item) {
      return C.tile({
        title: item.name,
        href: base + '/' + cat.slug + '/' + item.slug + '/',
        image: item.image,
      });
    })));
    return frag;
  };
}());
