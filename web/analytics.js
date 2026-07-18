'use strict';
/*
 * analytics.js — GA4 event tracking + consent bar for run.mmendelson.com.
 * Loaded on the five language shells and /gallery. GA4 itself is loaded (with
 * Consent Mode v2, denied by default) by the <head> block in each page; this
 * file provides mmTrack(), the localized consent bar, and event wiring.
 * All params are bucketed / non-PII (query_length, host, country, percent) —
 * never the search text, a registration URL's query, or any id/user value.
 * See website/ANALYTICS_TRACKING.md.
 */
(function () {
  function track(name, params) {
    try { if (typeof gtag === 'function') gtag('event', name, params || {}); } catch (e) {}
  }
  window.mmTrack = track;

  var FAMILY = /(^|\.)mmendelson\.com$/i;
  function hostOf(href) { try { return new URL(href, location.href).hostname; } catch (e) { return ''; } }
  function siteOf(href) {
    if (/apps\.mmendelson\.com/.test(href)) return 'apps';
    if (/run\.mmendelson\.com/.test(href)) return 'run';
    if (/mmendelson\.com/.test(href)) return 'home';
    return href.charAt(0) === '/' ? 'run' : 'home';
  }

  // Consent bar — text localized from <html lang> (shells: fixed; gallery: runtime)
  var I18N = {
    en: { t: 'This site uses Google Analytics to understand usage. No personal data is collected.', a: 'Accept', d: 'Decline' },
    pt: { t: 'Este site usa o Google Analytics para entender o uso. Nenhum dado pessoal é coletado.', a: 'Aceitar', d: 'Recusar' },
    es: { t: 'Este sitio usa Google Analytics para entender el uso. No se recopilan datos personales.', a: 'Aceptar', d: 'Rechazar' },
    de: { t: 'Diese Seite nutzt Google Analytics zur Nutzungsanalyse. Es werden keine personenbezogenen Daten erhoben.', a: 'Akzeptieren', d: 'Ablehnen' },
    fr: { t: "Ce site utilise Google Analytics pour comprendre son usage. Aucune donnée personnelle n'est collectée.", a: 'Accepter', d: 'Refuser' }
  };
  function initConsent() {
    var bar = document.getElementById('consent-bar');
    var lang = (document.documentElement.lang || 'en').split('-')[0];
    var t = I18N[lang] || I18N.en;
    if (bar) {
      var tx = bar.querySelector('.consent-text'),
          ac = bar.querySelector('[data-consent="accept"]'),
          dc = bar.querySelector('[data-consent="decline"]');
      if (tx) tx.textContent = t.t;
      if (ac) ac.textContent = t.a;
      if (dc) dc.textContent = t.d;
      var stored;
      try { stored = localStorage.getItem('mm_consent'); } catch (e) {}
      if (!stored) bar.hidden = false;
      function set(v) {
        try { localStorage.setItem('mm_consent', v); } catch (e) {}
        if (v === 'granted') { try { gtag('consent', 'update', { analytics_storage: 'granted' }); } catch (e) {} }
        bar.hidden = true;
      }
      if (ac) ac.addEventListener('click', function () { set('granted'); });
      if (dc) dc.addEventListener('click', function () { set('denied'); });
    }
    document.querySelectorAll('[data-consent="reset"]').forEach(function (el) {
      el.addEventListener('click', function (e) { e.preventDefault(); if (bar) bar.hidden = false; });
    });
  }

  function initEvents() {
    // Static chrome links (present at load) ---------------------------------
    document.querySelectorAll('.site-switch a, .foot-switch a').forEach(function (a) {
      if (a.classList.contains('active')) return;
      var where = (a.closest('.foot-switch') || a.closest('.footer-family')) ? 'footer' : 'header';
      a.addEventListener('click', function () {
        track('site_switch_click', { to_site: siteOf(a.getAttribute('href') || ''), location: where });
      });
    });
    document.querySelectorAll('.footer-langs a').forEach(function (a) {
      a.addEventListener('click', function () {
        var m = (a.getAttribute('href') || '').match(/\/(pt|en|es|de|fr)(\/|$)/);
        track('language_change', { to_lang: m ? m[1] : '', method: 'footer' });
      });
    });

    // Delegated clicks (covers dynamically-rendered cards/links) ------------
    document.addEventListener('click', function (e) {
      var t = e.target; if (!t || !t.closest) return;
      var pill = t.closest('.pill[data-km]');
      if (pill) { track('filter_change', { filter_type: 'distance', value: pill.getAttribute('data-km') }); return; }
      var opt = t.closest('.estado-option[data-value]');
      if (opt) { track('filter_change', { filter_type: 'state', value: opt.getAttribute('data-value') }); return; }
      var lopt = t.closest('.lang-option[data-lang]');
      if (lopt) { track('language_change', { to_lang: lopt.getAttribute('data-lang'), method: 'globe' }); return; }
      var reg = t.closest('.btn-inscricao');
      if (reg) {
        var item = reg.closest('.fonte-item'), nameEl = item && item.querySelector('.fonte-nome-text');
        track('registration_click', { host: hostOf(reg.getAttribute('href') || ''), source: nameEl ? (nameEl.textContent || '').trim() : '' });
        return;
      }
      var link = t.closest('a[href^="http"]');
      if (link) {
        var host = hostOf(link.href);
        if (host && !FAMILY.test(host)) { track('outbound_click', { host: host }); return; }
      }
      var card = t.closest('.card');
      if (card && !t.closest('a') && !t.closest('button')) {
        setTimeout(function () { if (card.classList.contains('open')) track('card_expand', {}); }, 0);
      }
    }, true);

    // Source filter (multi-select checkboxes) -------------------------------
    var fonteDd = document.getElementById('fonteFilterDropdown');
    if (fonteDd) fonteDd.addEventListener('change', function () { track('filter_change', { filter_type: 'source' }); });

    // Search — debounced, length only (never the query text) ----------------
    var search = document.getElementById('searchInput');
    if (search) {
      var tmr;
      search.addEventListener('input', function () {
        clearTimeout(tmr);
        tmr = setTimeout(function () { var v = (search.value || '').trim(); if (v) track('search', { query_length: v.length }); }, 1200);
      });
    }

    if (/\/gallery(\/|$)/.test(location.pathname)) track('gallery_view', {});

    var marks = [25, 50, 75, 100], hit = {};
    window.addEventListener('scroll', function () {
      var h = document.documentElement, sc = h.scrollHeight - h.clientHeight; if (sc <= 0) return;
      var pct = Math.round((h.scrollTop || window.scrollY) / sc * 100);
      marks.forEach(function (m) { if (pct >= m && !hit[m]) { hit[m] = 1; track('scroll_depth', { percent: m }); } });
    }, { passive: true });
  }

  function boot() { initConsent(); initEvents(); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
