/* Тип страницы: хаб раздела (список категорий) и хаб «Снаряжение». */
(function () {
  'use strict';
  var C = window.C;
  window.Views = window.Views || {};

  window.Views.section = function (data) {
    var section = data.section;
    var base = section.path || ('/snaryazhenie/' + section.slug);
    var frag = document.createDocumentFragment();
    frag.appendChild(C.el('h1', 'page__title', section.title));
    if (section.lead) { frag.appendChild(C.el('p', 'page__lead', section.lead)); }
    frag.appendChild(C.tiles(section.categories.map(function (cat) {
      return C.tile({
        title: cat.title,
        href: base + '/' + cat.slug + '/',
        image: cat.image,
      });
    })));
    return frag;
  };

  /* Хаб «Снаряжение»: 9 плиток в порядке эталона.
     Готовые разделы — ссылки, будущие — та же плитка с плашкой «скоро». */
  window.Views.snaryazhenie = function (data) {
    var hub = data.hub || {};
    var frag = document.createDocumentFragment();
    frag.appendChild(C.el('h1', 'page__title', hub.title || 'Снаряжение'));
    frag.appendChild(C.tiles((hub.tiles || []).map(function (tile) {
      if (tile.href) {
        return C.tile({ title: tile.title, href: tile.href, image: tile.image });
      }
      /* не ссылка: будущий раздел не должен попадать в индекс как битый адрес */
      var card = C.el('div', 'tile tile--soon');
      card.setAttribute('aria-disabled', 'true');
      card.appendChild(C.el('h2', 'tile__title', tile.title));
      var media = C.el('div', 'tile__media');
      if (tile.image) {
        var img = document.createElement('img');
        img.src = C.href(tile.image);
        img.alt = tile.title;
        img.loading = 'lazy';
        media.appendChild(img);
      }
      card.appendChild(media);
      card.appendChild(C.el('span', 'tile__soon', 'скоро'));
      return card;
    })));
    return frag;
  };
}());
