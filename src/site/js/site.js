/* Каркас: бургер-меню. Ничего лишнего. */
(function () {
  'use strict';

  var drawer = document.getElementById('drawer');
  var backdrop = document.querySelector('.drawer-backdrop');
  if (!drawer || !backdrop) { return; }

  function open() {
    drawer.classList.add('is-open');
    backdrop.classList.add('is-open');
    drawer.setAttribute('aria-hidden', 'false');
    document.body.style.overflow = 'hidden';
  }

  function close() {
    drawer.classList.remove('is-open');
    backdrop.classList.remove('is-open');
    drawer.setAttribute('aria-hidden', 'true');
    document.body.style.overflow = '';
  }

  document.querySelectorAll('.burger').forEach(function (btn) {
    btn.addEventListener('click', function (e) {
      e.preventDefault();
      if (drawer.classList.contains('is-open')) { close(); } else { open(); }
    });
  });

  document.querySelectorAll('[data-drawer-close]').forEach(function (el) {
    el.addEventListener('click', close);
  });

  drawer.querySelectorAll('.drawer__toggle').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var sub = btn.nextElementSibling;
      if (!sub) { return; }
      var willOpen = !sub.classList.contains('is-open');
      sub.classList.toggle('is-open', willOpen);
      btn.setAttribute('aria-expanded', String(willOpen));
    });
  });

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') { close(); }
  });
}());
