/*!
 * loading.js — Tela de carregamento: o tênis da galeria cruza a tela deixando
 * chão, pegadas, desgaste e poeira; a posição = progresso do carregamento.
 * Quando os dados terminam de carregar (sem mais re-render que troque a lista),
 * dá um zoom-in no tênis já desgastado e revela o site.
 *
 * Depende de ShoeWear (gallery/shoe-wear.js) e do overlay #loadingScreen no HTML.
 * app.js chama window.Loading.done() quando body.dataset.fullDataReady = '1'.
 */
(function () {
  'use strict';

  var overlay = document.getElementById('loadingScreen');
  if (!overlay) return;

  // Automated browsers (Playwright/Selenium) skip the loader entirely so its
  // overlay never intercepts test interactions — it is a pure UX flourish and
  // changes nothing about the app's behaviour or data.
  if (navigator.webdriver) {
    if (overlay.parentNode) overlay.parentNode.removeChild(overlay);
    return;
  }

  var stage  = overlay.querySelector('.load-shoe-stage');
  var prints = overlay.querySelector('.load-prints');
  if (!stage || !prints) { dismissNow(); return; }

  var reduce = false;
  try { reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches; } catch (e) {}

  // Mount the aging shoe SVG. Without it there is nothing to show — bail to the site.
  var ctl = null;
  try { if (window.ShoeWear) ctl = window.ShoeWear.mount(stage); } catch (e) {}
  if (!ctl) { dismissNow(); return; }

  // ---- footprint (sole silhouette, same as the gallery) --------------------
  var SOLE = '<svg viewBox="0 0 120 42" xmlns="http://www.w3.org/2000/svg">'
    + '<path d="M18 21 C18 12 26 9 36 9 C46 9 52 12 56 15 C60 12 70 9 82 9 C100 9 112 13 114 21 C112 29 100 33 82 33 C70 33 60 30 56 27 C52 30 46 33 36 33 C26 33 18 30 18 21 Z" fill="#241a0d"/>'
    + '<path d="M18 21 C18 12 26 9 36 9 C46 9 52 12 56 15 C60 12 70 9 82 9 C100 9 112 13 114 21 C112 29 100 33 82 33 C70 33 60 30 56 27 C52 30 46 33 36 33 C26 33 18 30 18 21 Z" fill="none" stroke="#6e5536" stroke-width="1.6" opacity="0.4"/>'
    + '<g stroke="#120c04" stroke-width="2.4" stroke-linecap="round" opacity="0.42"><path d="M70 14 L70 28"/><path d="M82 13 L82 29"/><path d="M94 15 L94 27"/><path d="M30 15 L30 27"/></g>'
    + '</svg>';

  function metrics() {
    var sr = stage.getBoundingClientRect(), pr = prints.getBoundingClientRect();
    return { x: sr.left - pr.left + sr.width / 2, w: sr.width };
  }

  function spawnFootprint(m) {
    var w = m.w * 0.96, h = w * 0.26;
    var fp = document.createElement('div');
    fp.className = 'load-footprint';
    fp.style.left = (m.x - w / 2) + 'px';
    fp.style.width = w + 'px';
    fp.style.height = h + 'px';
    fp.style.top = (2 + Math.random() * 2) + 'px';
    fp.style.transform = 'rotate(' + (Math.random() * 4 - 2).toFixed(1) + 'deg)';
    fp.innerHTML = SOLE;
    prints.appendChild(fp);
    fp.addEventListener('animationend', function () { if (fp.parentNode) fp.parentNode.removeChild(fp); });
  }

  function spawnDust(m) {
    var w = m.w;
    var cloud = document.createElement('div');
    cloud.className = 'load-dust';
    cloud.style.left = (m.x - w / 2) + 'px';
    cloud.style.width = w + 'px';
    var N = Math.max(14, Math.round(w / 3.4));
    for (var i = 0; i < N; i++) {
      var t = (N > 1) ? i / (N - 1) : 0.5;     // 0..1 across the shoe width
      var edge = (t - 0.5) * 2;                // -1 (heel) .. 1 (toe)
      var size = 10 + Math.random() * 16;
      var p = document.createElement('span');
      p.className = 'load-puff';
      p.style.width = size + 'px';
      p.style.height = size + 'px';
      p.style.left = (t * w - size / 2 + (Math.random() * 8 - 4)) + 'px';
      p.style.top = (2 + Math.random() * 4) + 'px';
      p.style.setProperty('--dx', (edge * w * 0.42 + (Math.random() * 12 - 6)).toFixed(1) + 'px');
      p.style.setProperty('--dy', (-(26 + Math.random() * 22) - (1 - Math.abs(edge)) * 12).toFixed(1) + 'px');
      p.style.setProperty('--s', (2.2 + Math.random() * 1.4).toFixed(2));
      p.style.setProperty('--o', (0.45 + Math.random() * 0.3).toFixed(2));
      p.style.setProperty('--d', (0.8 + Math.random() * 0.5).toFixed(2) + 's');
      p.style.animationDelay = (Math.random() * 110).toFixed(0) + 'ms';
      cloud.appendChild(p);
    }
    prints.appendChild(cloud);
    setTimeout(function () { if (cloud.parentNode) cloud.parentNode.removeChild(cloud); }, 1700);
  }

  // A print + dust drop on every footfall (the bottom of each step bounce).
  if (!reduce) {
    var inner = stage.querySelector('.shoe');
    if (inner) {
      inner.addEventListener('animationiteration', function () {
        if (finished) return;
        var m = metrics();
        spawnFootprint(m);
        spawnDust(m);
      });
    }
    stage.classList.add('walking');
  }

  // ---- progress: shoe position + wear both driven by one value -------------
  function apply(p) {
    ctl.setProgress(p);
    stage.style.left = (p * 100) + '%';
    stage.style.transform = 'translateX(' + (-p * 100) + '%)';
  }
  apply(0);

  var prog = 0, target = 0, done = false, finished = false;
  var raf = null, startT = (window.performance && performance.now) ? performance.now() : Date.now();
  var MIN_MS = 1600;   // always show enough of the crossing, even on a cached load

  function now() { return (window.performance && performance.now) ? performance.now() : Date.now(); }

  function tick() {
    var elapsed = (now() - startT) / 1000;
    // Until the data is ready, ease toward 0.9 (asymptotic — the shoe keeps
    // advancing but never "arrives" before the site actually does). Once ready,
    // let it complete the crossing.
    target = done ? 1 : Math.min(0.9, 1 - Math.exp(-elapsed / 2.6));
    prog += (target - prog) * 0.07;
    apply(Math.min(prog, 1));
    if (done && prog > 0.992 && (now() - startT) >= MIN_MS) {
      apply(1);
      finish();
      return;
    }
    raf = requestAnimationFrame(tick);
  }
  raf = requestAnimationFrame(tick);

  // ---- finish: zoom into the worn shoe, then reveal the site ---------------
  function finish() {
    if (finished) return;
    finished = true;
    if (raf) cancelAnimationFrame(raf);
    apply(1);                          // fully worn, parked at the end of the track
    stage.classList.remove('walking');
    overlay.classList.add('zooming');  // fades the ground + footprints away

    if (reduce) {                      // no motion: just reveal the site
      overlay.classList.add('hidden');
      setTimeout(dismissNow, 600);
      return;
    }

    // Zoom into the worn shoe: transition from its current (inline) end-of-track
    // position to centre + scaled-up. Setting the target on the next frame makes
    // the transition interpolate from the current position (no jump).
    stage.style.transition = 'left .82s ease, transform .82s cubic-bezier(.45,0,.6,1)';
    requestAnimationFrame(function () {
      stage.style.left = '50%';
      stage.style.transform = 'translate(-50%, -22%) scale(8)';
    });
    setTimeout(function () {
      overlay.classList.add('hidden');   // fade the overlay → reveal the site
      setTimeout(dismissNow, 650);
    }, 820);
  }

  function dismissNow() {
    document.documentElement.classList.remove('loading');
    if (overlay && overlay.parentNode) overlay.parentNode.removeChild(overlay);
  }

  // Public API for app.js to signal the data is fully loaded.
  window.Loading = { done: function () { done = true; } };

  // Safety net: never trap the user behind the loader if the data load hangs
  // or stalls (slow geo lookup, failed fetch). Force completion after 14s.
  setTimeout(function () { done = true; }, 14000);
})();
