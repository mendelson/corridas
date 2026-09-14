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
  // Banner v2 — it must name the demographic signals, because accepting now
  // also grants ad_user_data / ad_personalization (Google Signals).
  var I18N = {
    en: { t: 'This site uses Google Analytics cookies to understand how mmendelson.com and its sub-sites are used, including age, gender and interest estimates from Google. Decline and only anonymous counts are kept.', a: 'Accept', d: 'Decline', p: 'Privacy policy' },
    pt: { t: 'Este site usa cookies do Google Analytics para entender como o mmendelson.com e seus subsites são usados, incluindo estimativas de idade, gênero e interesses feitas pelo Google. Ao recusar, ficam apenas contagens anônimas.', a: 'Aceitar', d: 'Recusar', p: 'Política de privacidade' },
    es: { t: 'Este sitio usa cookies de Google Analytics para entender cómo se usan mmendelson.com y sus subsitios, incluidas las estimaciones de edad, género e intereses de Google. Al rechazar, solo se conservan recuentos anónimos.', a: 'Aceptar', d: 'Rechazar', p: 'Política de privacidad' },
    de: { t: 'Diese Website nutzt Google-Analytics-Cookies, um die Nutzung von mmendelson.com und seinen Unterseiten zu verstehen — einschließlich der von Google geschätzten Angaben zu Alter, Geschlecht und Interessen. Bei Ablehnung bleiben nur anonyme Zählungen.', a: 'Akzeptieren', d: 'Ablehnen', p: 'Datenschutz' },
    fr: { t: 'Ce site utilise des cookies Google Analytics pour comprendre l\u2019usage de mmendelson.com et de ses sous-sites, y compris les estimations d\u2019âge, de genre et d\u2019intérêts fournies par Google. En cas de refus, seuls des comptages anonymes sont conservés.', a: 'Accepter', d: 'Refuser', p: 'Confidentialité' }
  };
  function initConsent() {
    var bar = document.getElementById('consent-bar');
    var lang = (document.documentElement.lang || 'en').split('-')[0];
    var t = I18N[lang] || I18N.en;
    if (bar) {
      var tx = bar.querySelector('.consent-text'),
          ac = bar.querySelector('[data-consent="accept"]'),
          dc = bar.querySelector('[data-consent="decline"]');
      if (tx) {
        tx.textContent = t.t + ' ';
        var a = document.createElement('a');
        // The family policy lives on the apps site; this site has no page of
        // its own to point at.
        a.href = 'https://apps.mmendelson.com/privacy_policy/' + (I18N[lang] ? lang : 'en') + '/';
        a.rel = 'noopener';
        a.textContent = t.p;
        tx.appendChild(a);
      }
      if (ac) ac.textContent = t.a;
      if (dc) dc.textContent = t.d;
      // mm_consent_v is the banner version answered. A visitor who accepted
      // the v1 banner consented to analytics only, so they are asked again
      // rather than having the ad signals switched on behind them.
      var answered = (window.mmConsentGet || function () { return null; })('mm_consent_v');
      if (answered !== '2') bar.hidden = false;
      function set(v) {
        var put = window.mmConsentSet || function (k, x) { try { localStorage.setItem(k, x); } catch (e) {} };
        put('mm_consent', v);
        put('mm_consent_v', '2');
        if (v === 'granted') {
          try {
            gtag('consent', 'update', {
              analytics_storage: 'granted', ad_storage: 'granted',
              ad_user_data: 'granted', ad_personalization: 'granted'
            });
          } catch (e) {}
        }
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
