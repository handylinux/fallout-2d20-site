/* Свои типы страниц вне каталога: происхождения, блог, списки.
   Данные — из данных сайта (data/*.json → assets/data/*.json). */
(function () {
  'use strict';
  var C = window.C;
  window.Views = window.Views || {};

  /* хаб происхождений: аватар + плашка с текстом и шевроном */
  window.Views.origins = function (data) {
    var frag = document.createDocumentFragment();
    var page = data.page || {};
    frag.appendChild(C.el('h1', 'page__title', page.title || 'Происхождения'));
    if (page.lead) { frag.appendChild(C.el('p', 'page__lead', page.lead)); }

    var cards = page.cards || [];
    for (var i = 0; i < cards.length; i += 2) {
      var row = C.el('div', 'row g-0 origins-row');
      cards.slice(i, i + 2).forEach(function (card) {
        var mediaCol = C.el('div', 'col-12 col-sm-6 col-lg-3');
        var cell = C.el('div', 'media-cell');
        if (card.image) {
          var img = document.createElement('img');
          img.src = C.href(card.image);
          img.alt = card.alt || card.title;
          img.loading = 'lazy';
          cell.appendChild(img);
        } else {
          cell.className += ' media-cell--empty';
        }
        mediaCol.appendChild(cell);
        row.appendChild(mediaCol);

        var plateCol = C.el('div', 'col-12 col-sm-6 col-lg-3');
        var plate = C.el('div', 'cell cell--shadow');
        var h = C.el('h2', 'cell__title');
        h.appendChild(C.link(card.url, '', card.title));
        plate.appendChild(h);
        (card.texts || (card.text ? [card.text] : [])).forEach(function (text) {
          plate.appendChild(C.el('p', 'cell__text', text));
        });
        var chev = C.el('div', 'cell__chevron');
        var a = C.link(card.url, 'cta', 'Подробнее');
        a.innerHTML += C.ARROW;
        chev.appendChild(a);
        plate.appendChild(chev);
        plateCol.appendChild(plate);
        row.appendChild(plateCol);
      });
      frag.appendChild(row);
    }
    return frag;
  };

  /* деталь происхождения */
  window.Views.origin = function (data) {
    var page = data.page;
    var frag = document.createDocumentFragment();
    frag.appendChild(C.back('/proiskhozhdeniya/', 'Назад к происхождениям'));
    frag.appendChild(C.el('h1', 'page__title', page.title));
    if (page.image) {
      var media = C.el('div', 'wcard__media');
      var img = document.createElement('img');
      img.className = 'wcard__img';
      img.src = C.href(page.image);
      img.alt = page.title;
      media.appendChild(img);
      frag.appendChild(media);
    }
    (page.blocks || []).forEach(function (block) {
      frag.appendChild(C.shadowBlock(block.title, C.paragraphs(block.text)));
    });
    return frag;
  };

  /* произвольная статья: блог, правила, дополнения */
  window.Views.article = function (data) {
    var page = data.page || {};
    var frag = document.createDocumentFragment();
    if (page.back) { frag.appendChild(C.back(page.back.url, page.back.text)); }
    frag.appendChild(C.el('h1', 'page__title', page.title || ''));
    if (page.date) { frag.appendChild(C.el('p', 'page__date', page.date)); }
    (page.blocks || []).forEach(function (block) {
      if (block.type === 'text') {
        frag.appendChild(C.shadowBlock(block.title, C.paragraphs(block.text)));
      } else if (block.type === 'spoiler') {
        frag.appendChild(C.spoiler(block.title, block.count, C.paragraphs(block.text)));
      } else if (block.type === 'html') {
        var box = C.el('div', 'rich-block');
        box.innerHTML = block.html || '';
        frag.appendChild(box);
      }
    });
    return frag;
  };

  /* список: блог, новости, любые перечни */
  window.Views.list = function (data) {
    var page = data.page || {};
    var frag = document.createDocumentFragment();
    frag.appendChild(C.el('h1', 'page__title', page.title || ''));
    if (page.lead) { frag.appendChild(C.el('p', 'page__lead', page.lead)); }
    frag.appendChild(C.tiles((page.items || []).map(function (item) {
      return C.tile({ title: item.title, href: item.url, image: item.image });
    })));
    return frag;
  };
}());
