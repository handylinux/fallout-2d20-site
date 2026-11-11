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

  /* Карточка хаба: заголовок → картинка → то, что передали снизу
     (кнопка «Подробнее» у готового раздела или плашка «скоро» у будущего). */
  function card(tile, bottom) {
    var node = C.el('div', 'tile' + (tile.href ? '' : ' tile--soon'));
    var title = C.el('h2', 'tile__title', tile.title);
    /* на эталоне заголовок — ссылка: <a href><h2> */
    if (tile.href) {
      var titleLink = C.el('a');
      titleLink.setAttribute('href', C.href(tile.href));
      titleLink.appendChild(title);
      node.appendChild(titleLink);
    } else {
      node.appendChild(title);
    }
    var media = C.el('div', 'tile__media');
    if (tile.image) {
      var img = document.createElement('img');
      img.src = C.href(tile.image);
      img.alt = tile.title;
      img.loading = 'lazy';
      media.appendChild(img);
    }
    node.appendChild(media);
    node.appendChild(bottom);
    return node;
  }

  /* Хаб «Снаряжение»: 9 плиток в порядке эталона.
     Готовые разделы — ссылки, будущие — та же плитка с плашкой «скоро». */
  function soon() {
    var plate = C.el('span', 'tile__soon');
    plate.appendChild(C.el('span', null, 'скоро'));
    return plate;
  }

  window.Views.snaryazhenie = function (data) {
    var hub = data.hub || {};
    var frag = document.createDocumentFragment();
    frag.appendChild(C.el('h1', 'page__title', hub.title || 'Снаряжение'));
    frag.appendChild(C.tiles((hub.tiles || []).map(function (tile) {
      if (tile.href) {
        return card(tile, C.cta(tile.href, 'Подробнее'));
      }
      /* будущий раздел: не ссылка, чтобы не попадал в индекс битым адресом */
      return card(tile, soon());
    })));
    return frag;
  };
}());
