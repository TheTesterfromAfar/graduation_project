// Progressive enhancement only: every page works without this file. No inline handlers are used
// anywhere, which is what lets the Content-Security-Policy forbid inline scripts.
(function () {
  'use strict';

  var reducedMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // ---- Mobile navigation ------------------------------------------------------------------
  var toggle = document.querySelector('[data-nav-toggle]');
  var menu = document.getElementById('site-menu');
  if (toggle && menu) {
    toggle.addEventListener('click', function () {
      var open = menu.classList.toggle('is-open');
      toggle.setAttribute('aria-expanded', String(open));
      toggle.setAttribute('aria-label', open ? 'Цэс хаах' : 'Цэс нээх');
    });
  }

  // ---- Dismissible flash messages ---------------------------------------------------------
  document.addEventListener('click', function (event) {
    var button = event.target.closest('[data-dismiss]');
    if (!button) return;
    var alert = button.closest('.alert');
    if (alert) alert.remove();
  });

  // ---- Confirm dialogs (<form data-confirm="...">) + loading state on submit ----------------
  function setLoading(button, loading) {
    button.classList.toggle('is-loading', loading);
    button.disabled = loading;
    if (loading) button.setAttribute('aria-busy', 'true');
    else button.removeAttribute('aria-busy');
  }

  document.addEventListener('submit', function (event) {
    var form = event.target;
    if (!(form instanceof HTMLFormElement)) return;

    var message = form.getAttribute('data-confirm');
    if (message && !window.confirm(message)) {
      event.preventDefault();
      return;
    }
    if (event.defaultPrevented || (form.method || '').toLowerCase() !== 'post') return;

    // Disable the button after the browser has collected the form data, so a double click can't
    // submit twice and the user sees something is happening.
    var button = event.submitter || form.querySelector('button[type="submit"]');
    if (button) window.setTimeout(function () { setLoading(button, true); }, 0);
  });

  // Back/forward cache can restore a page with a button stuck in the loading state.
  window.addEventListener('pageshow', function (event) {
    if (!event.persisted) return;
    document.querySelectorAll('.btn.is-loading').forEach(function (button) { setLoading(button, false); });
  });

  // ---- Survey progress ---------------------------------------------------------------------
  var surveyForm = document.querySelector('[data-survey-form]');
  if (surveyForm) {
    var items = Array.prototype.slice.call(surveyForm.querySelectorAll('[data-required-item]'));
    var bar = surveyForm.querySelector('[data-progress] progress');
    var label = surveyForm.querySelector('[data-progress-label]');
    var progress = surveyForm.querySelector('[data-progress]');

    var isAnswered = function (item) {
      var radios = item.querySelectorAll('input[type="radio"]');
      if (radios.length) return Array.prototype.some.call(radios, function (r) { return r.checked; });
      var control = item.querySelector('input, select, textarea');
      return !!control && control.value.trim() !== '';
    };

    var update = function () {
      var done = items.filter(isAnswered).length;
      bar.max = items.length;
      bar.value = done;
      label.textContent = done + ' / ' + items.length + ' хариулсан';
    };

    if (items.length && bar && label) {
      progress.classList.add('is-ready');
      surveyForm.addEventListener('input', update);
      surveyForm.addEventListener('change', update);
      update();
    }
  }

  // ---- Jump to the first validation error --------------------------------------------------
  var firstError = document.querySelector('.has-error');
  if (firstError) {
    firstError.scrollIntoView({ behavior: reducedMotion ? 'auto' : 'smooth', block: 'center' });
    var control = firstError.querySelector('input, select, textarea');
    if (control) control.focus({ preventScroll: true });
  }
})();
