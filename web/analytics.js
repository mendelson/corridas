'use strict';
/*
 * analytics.js — GA4 event tracking + consent bar for run.mmendelson.com.
 * Loaded on the 28 language shells and /gallery. GA4 itself is loaded (with
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
    fr: { t: 'Ce site utilise des cookies Google Analytics pour comprendre l\u2019usage de mmendelson.com et de ses sous-sites, y compris les estimations d\u2019âge, de genre et d\u2019intérêts fournies par Google. En cas de refus, seuls des comptages anonymes sont conservés.', a: 'Accepter', d: 'Refuser', p: 'Confidentialité' },
    it: { t: 'Questo sito usa i cookie di Google Analytics per capire come vengono usati mmendelson.com e i suoi sottositi, comprese le stime di età, genere e interessi fornite da Google. Se rifiuti, restano solo conteggi anonimi.', a: 'Accetta', d: 'Rifiuta', p: 'Privacy' },
    ru: { t: 'Этот сайт использует файлы cookie Google Analytics, чтобы понять, как используются mmendelson.com и его подсайты, включая оценки возраста, пола и интересов от Google. При отказе остаётся только анонимный подсчёт.', a: 'Принять', d: 'Отклонить', p: 'Конфиденциальность' },
    nl: { t: 'Deze site gebruikt cookies van Google Analytics om te begrijpen hoe mmendelson.com en de bijbehorende subsites worden gebruikt, inclusief schattingen van leeftijd, geslacht en interesses door Google. Weiger je, dan worden alleen anonieme tellingen bewaard.', a: 'Accepteren', d: 'Weigeren', p: 'Privacybeleid' },
    'pt-pt': { t: 'Este site utiliza cookies do Google Analytics para perceber como o mmendelson.com e os seus subsites são utilizados, incluindo estimativas de idade, género e interesses feitas pela Google. Se recusar, ficam apenas contagens anónimas.', a: 'Aceitar', d: 'Recusar', p: 'Política de privacidade' },
    pl: { t: 'Ta strona używa plików cookie Google Analytics, aby zrozumieć, jak korzysta się z mmendelson.com i jego podstron, w tym z szacunków wieku, płci i zainteresowań dostarczanych przez Google. Po odmowie zbierane są tylko anonimowe statystyki.', a: 'Akceptuję', d: 'Odrzucam', p: 'Polityka prywatności' },
    cs: { t: 'Tento web používá soubory cookie Google Analytics, aby pochopil, jak se mmendelson.com a jeho podweby používají, včetně odhadů věku, pohlaví a zájmů od Googlu. Pokud odmítnete, zůstanou jen anonymní počty.', a: 'Přijmout', d: 'Odmítnout', p: 'Zásady ochrany osobních údajů' },
    sk: { t: 'Tento web používa súbory cookie Google Analytics, aby pochopil, ako sa používa mmendelson.com a jeho podstránky, vrátane odhadov veku, pohlavia a záujmov od Googlu. Ak odmietnete, zostanú len anonymné počty.', a: 'Prijať', d: 'Odmietnuť', p: 'Zásady ochrany súkromia' },
    sl: { t: 'To spletno mesto uporablja piškotke Google Analytics, da razume, kako se uporabljajo mmendelson.com in njegova podspletišča, vključno z Googlovimi ocenami starosti, spola in interesov. Če zavrnete, se ohranijo le anonimna štetja.', a: 'Sprejmi', d: 'Zavrni', p: 'Pravilnik o zasebnosti' },
    hr: { t: 'Ova stranica koristi kolačiće Google Analyticsa kako bi razumjela kako se koriste mmendelson.com i njegove podstranice, uključujući Googleove procjene dobi, spola i interesa. Ako odbijete, zadržavaju se samo anonimni brojevi.', a: 'Prihvati', d: 'Odbij', p: 'Pravila privatnosti' },
    hu: { t: 'Ez a webhely Google Analytics-sütiket használ, hogy megértse, hogyan használják a mmendelson.com-ot és aloldalait, beleértve a Google életkorra, nemre és érdeklődésre vonatkozó becsléseit. Ha elutasítja, csak névtelen számlálás marad.', a: 'Elfogadom', d: 'Elutasítom', p: 'Adatvédelmi irányelvek' },
    el: { t: 'Αυτός ο ιστότοπος χρησιμοποιεί cookies του Google Analytics για να κατανοήσει πώς χρησιμοποιούνται το mmendelson.com και οι υποτομείς του, συμπεριλαμβανομένων εκτιμήσεων ηλικίας, φύλου και ενδιαφερόντων από την Google. Αν αρνηθείτε, διατηρούνται μόνο ανώνυμες μετρήσεις.', a: 'Αποδοχή', d: 'Απόρριψη', p: 'Πολιτική απορρήτου' },
    da: { t: 'Dette websted bruger cookies fra Google Analytics til at forstå, hvordan mmendelson.com og dets undersider bruges, herunder Googles skøn over alder, køn og interesser. Afviser du, gemmes kun anonyme optællinger.', a: 'Accepter', d: 'Afvis', p: 'Privatlivspolitik' },
    nb: { t: 'Dette nettstedet bruker informasjonskapsler fra Google Analytics for å forstå hvordan mmendelson.com og undersidene brukes, inkludert Googles anslag over alder, kjønn og interesser. Hvis du avslår, lagres bare anonyme tellinger.', a: 'Godta', d: 'Avslå', p: 'Personvernerklæring' },
    sv: { t: 'Den här webbplatsen använder cookies från Google Analytics för att förstå hur mmendelson.com och dess undersidor används, inklusive Googles uppskattningar av ålder, kön och intressen. Om du avböjer sparas bara anonyma räkningar.', a: 'Godkänn', d: 'Avböj', p: 'Integritetspolicy' },
    fi: { t: 'Tämä sivusto käyttää Google Analyticsin evästeitä ymmärtääkseen, miten mmendelson.comia ja sen alasivustoja käytetään, mukaan lukien Googlen arviot iästä, sukupuolesta ja kiinnostuksen kohteista. Jos kieltäydyt, tallennetaan vain nimettömiä laskentoja.', a: 'Hyväksy', d: 'Hylkää', p: 'Tietosuojakäytäntö' },
    ja: { t: 'このサイトでは、mmendelson.com とそのサブサイトの利用状況を把握するために Google アナリティクスの Cookie を使用しています。これには Google による年齢・性別・興味関心の推定が含まれます。拒否した場合は、匿名の集計のみが記録されます。', a: '同意する', d: '拒否する', p: 'プライバシーポリシー' },
    ko: { t: '이 사이트는 mmendelson.com 및 하위 사이트의 이용 방식을 파악하기 위해 Google 애널리틱스 쿠키를 사용하며, 여기에는 Google이 추정한 연령, 성별 및 관심사가 포함됩니다. 거부하면 익명 집계만 유지됩니다.', a: '동의', d: '거부', p: '개인정보처리방침' },
    'zh-cn': { t: '本网站使用 Google Analytics Cookie 来了解 mmendelson.com 及其子网站的使用情况，包括 Google 对年龄、性别和兴趣的估算。如果拒绝，将仅保留匿名统计。', a: '接受', d: '拒绝', p: '隐私政策' },
    'zh-tw': { t: '本網站使用 Google Analytics Cookie 來了解 mmendelson.com 及其子網站的使用情形，包括 Google 對年齡、性別與興趣的估計。若您拒絕，僅會保留匿名統計。', a: '接受', d: '拒絕', p: '隱私權政策' },
    th: { t: 'เว็บไซต์นี้ใช้คุกกี้ของ Google Analytics เพื่อทำความเข้าใจการใช้งาน mmendelson.com และเว็บไซต์ย่อย รวมถึงการประมาณอายุ เพศ และความสนใจโดย Google หากคุณปฏิเสธ จะเก็บไว้เพียงสถิติแบบไม่ระบุตัวตนเท่านั้น', a: 'ยอมรับ', d: 'ปฏิเสธ', p: 'นโยบายความเป็นส่วนตัว' },
    he: { t: 'אתר זה משתמש בקובצי Cookie של Google Analytics כדי להבין כיצד נעשה שימוש ב־mmendelson.com ובאתרי המשנה שלו, כולל הערכות של Google לגבי גיל, מגדר ותחומי עניין. אם תסרבו, יישמרו רק ספירות אנונימיות.', a: 'אישור', d: 'סירוב', p: 'מדיניות פרטיות' },
    id: { t: 'Situs ini menggunakan cookie Google Analytics untuk memahami cara mmendelson.com dan subsitusnya digunakan, termasuk perkiraan usia, jenis kelamin, dan minat dari Google. Jika Anda menolak, hanya hitungan anonim yang disimpan.', a: 'Terima', d: 'Tolak', p: 'Kebijakan privasi' },
    ms: { t: 'Laman ini menggunakan kuki Google Analytics untuk memahami cara mmendelson.com dan sublamannya digunakan, termasuk anggaran umur, jantina dan minat daripada Google. Jika anda menolak, hanya kiraan tanpa nama disimpan.', a: 'Terima', d: 'Tolak', p: 'Dasar privasi' }
  };
  function initConsent() {
    var bar = document.getElementById('consent-bar');
    // <html lang> is a full tag (pt-BR, pt-PT, zh-TW): regional variants with
    // their own entry are matched first, everything else by its language.
    var tag = (document.documentElement.lang || 'en').toLowerCase();
    var lang = I18N[tag] ? tag : tag.split('-')[0];
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
        var m = (a.getAttribute('href') || '').match(/^\/([a-z]{2}(?:-[a-z]{2})?)(\/|$)/);
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
