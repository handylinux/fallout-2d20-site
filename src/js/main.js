/*
 * Поведение Helix Ultimate / SP Page Builder, нужное для статической версии:
 *  - бургер и оффканвас-меню (offcanvas-init, offcanvas-active, offcanvas-overlay)
 *  - аккордеон SPPB (.sppb-panel-heading / .sppb-panel-collapse)
 *  - табы SPPB (data-toggle="sppb-tab")
 *  - кнопка «наверх» (a.sp-scroll-up)
 *  - ленивая подгрузка фонов (.sppb-element-loaded)
 */
(function () {
  'use strict';

  var doc = document;
  var body = doc.body;

  /* ---------------------------------------------------------------- offcanvas */
  function openOffcanvas() {
    body.classList.add('offcanvas-active', 'full-offcanvas');
    body.style.overflow = 'hidden';
    var menu = doc.querySelector('.offcanvas-menu');
    if (menu) {
      menu.removeAttribute('inert');
      menu.setAttribute('tabindex', '0');
    }
  }

  function closeOffcanvas() {
    body.classList.remove('offcanvas-active', 'full-offcanvas');
    body.style.overflow = '';
    var menu = doc.querySelector('.offcanvas-menu');
    if (menu) {
      menu.setAttribute('inert', '');
      menu.setAttribute('tabindex', '-1');
    }
  }

  doc.addEventListener('click', function (e) {
    var t = e.target;
    if (t.closest('#offcanvas-toggler')) { e.preventDefault(); openOffcanvas(); return; }
    if (t.closest('.close-offcanvas') || t.closest('.offcanvas-overlay')) { e.preventDefault(); closeOffcanvas(); return; }
    if (t.closest('a.sp-scroll-up')) {
      e.preventDefault();
      window.scrollTo({ top: 0, behavior: 'smooth' });
      return;
    }
    var toggler = t.closest('.menu-toggler');
    if (toggler) {
      e.preventDefault();
      var li = toggler.closest('li.menu-parent');
      if (!li) return;
      var child = li.querySelector(':scope > ul.menu-child');
      if (!child) return;
      var open = li.classList.toggle('menu-parent-open');
      toggler.setAttribute('aria-expanded', open ? 'true' : 'false');
      child.style.display = open ? 'block' : 'none';
    }
  });

  doc.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') closeOffcanvas();
  });

  /* ---------------------------------------------------------------- scroll up */
  function onScroll() {
    var btn = doc.querySelector('a.sp-scroll-up');
    if (!btn) return;
    if (window.pageYOffset > 100) btn.classList.add('active');
    else btn.classList.remove('active');
  }
  window.addEventListener('scroll', onScroll, { passive: true });
  onScroll();

  /* ---------------------------------------------------------------- SPPB accordion */
  doc.addEventListener('click', function (e) {
    var head = e.target.closest('.sppb-panel-heading');
    if (!head) return;
    var panel = head.parentNode;
    var collapse = panel.querySelector('.sppb-panel-collapse');
    if (!collapse) return;
    var open = head.getAttribute('aria-expanded') === 'true';
    head.setAttribute('aria-expanded', open ? 'false' : 'true');
    panel.classList.toggle('sppb-panel-open', !open);
    collapse.style.display = open ? 'none' : 'block';
  });

  /* ---------------------------------------------------------------- SPPB tabs */
  doc.addEventListener('click', function (e) {
    var a = e.target.closest('a[data-toggle="sppb-tab"]');
    if (!a) return;
    e.preventDefault();
    var ul = a.closest('.sppb-nav');
    var wrap = ul ? ul.parentNode : doc;
    var items = ul ? ul.querySelectorAll('li') : [];
    Array.prototype.forEach.call(items, function (li) { li.classList.remove('active'); });
    var li = a.closest('li');
    if (li) li.classList.add('active');
    var panes = wrap.querySelectorAll('.sppb-tab-pane');
    Array.prototype.forEach.call(panes, function (p) { p.classList.remove('active', 'in'); });
    var target = doc.querySelector(a.getAttribute('href'));
    if (target) target.classList.add('active', 'in');
  });

  /* ---------------------------------------------------------------- lazy backgrounds */
  function loadBackgrounds() {
    Array.prototype.forEach.call(doc.querySelectorAll('[data-sppb-bg]'), function (el) {
      el.style.backgroundImage = 'url(' + el.getAttribute('data-sppb-bg') + ')';
      el.classList.add('sppb-element-loaded');
    });
  }
  if ('requestIdleCallback' in window) window.requestIdleCallback(loadBackgrounds);
  else window.setTimeout(loadBackgrounds, 1);
})();
