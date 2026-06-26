/*!
 * loading.js — Tela de carregamento com o tênis da galeria.
 *
 * Sequência:
 *   1. abre com o tênis NOVO (limpo), grande e centralizado (cabendo na tela),
 *      parado por 0,8s;
 *   2. o tênis desce e encolhe até o início da pista e CRUZA a tela — chão,
 *      pegadas, poeira e desgaste progressivo (posição = progresso do load);
 *   3. quando os dados terminam, o tênis (agora DESGASTADO) volta ao centro,
 *      grande (cabendo na tela), e fica parado por 0,8s;
 *   4. o overlay some, revelando o site.
 *
 * Depende de ShoeWear (gallery/shoe-wear.js) e do overlay #loadingScreen.
 * app.js chama window.Loading.done() quando body.dataset.fullDataReady = '1'.
 */
(function () {
  'use strict';

  var overlay = document.getElementById('loadingScreen');
  if (!overlay) return;

  // Automated browsers (Playwright/Selenium) skip the loader entirely so its
  // overlay never intercepts test interactions — pure UX flourish, no behaviour
  // or data change.
  if (navigator.webdriver) {
    if (overlay.parentNode) overlay.parentNode.removeChild(overlay);
    return;
  }

  var stage  = overlay.querySelector('.load-shoe-stage');
  var prints = overlay.querySelector('.load-prints');
  if (!stage || !prints) { dismissNow(); return; }

  var reduce = false;
  try { reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches; } catch (e) {}

  var ctl = null;
  try { if (window.ShoeWear) ctl = window.ShoeWear.mount(stage); } catch (e) {}
  if (!ctl) { dismissNow(); return; }

  // ---- timing ----
  var HOLD_MS = 800;     // hero hold (new shoe at the start, worn shoe at the end)
  var INTRO_T = 600;     // hero → track-start transition
  var OUTRO_T = 720;     // track-end → hero transition
  var MIN_CROSS_MS = 1600;// minimum visible crossing (≈2 footfalls + dust), even on a cached load
  var GROUND_FRAC = 0.62;// ground line as a fraction of viewport height

  // Natural (untransformed) shoe-stage box — offset* ignores transforms.
  function W() { return stage.offsetWidth; }
  function H() { return stage.offsetHeight; }
  function vw() { return window.innerWidth; }
  function vh() { return window.innerHeight; }
  function groundY() { return vh() * GROUND_FRAC; }

  // transform-origin is 0 0 (see CSS), so a translate(px,px)+scale places the
  // box top-left exactly and scales from there — easy, predictable geometry.
  function setShoe(x, y, s) {
    stage.style.transform = 'translate(' + x + 'px,' + y + 'px) scale(' + s + ')';
  }

  // Track position at progress p (scale 1): shoe walks the ground line L→R,
  // staying fully inside the viewport at both ends.
  function applyTrack(p) {
    var x = p * (vw() - W());
    var y = groundY() - H() + 8;   // sole sits just into the dirt
    setShoe(x, y, 1);
  }

  // Hero: as large as fits the viewport with margin — never cropped.
  function heroScale() { return Math.min(0.78 * vw() / W(), 0.62 * vh() / H()); }
  function applyHero() {
    var s = heroScale();
    setShoe((vw() - W() * s) / 2, (vh() - H() * s) / 2, s);
  }

  // ---- footprint + dust (reused from the gallery) --------------------------
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
      var t = (N > 1) ? i / (N - 1) : 0.5;
      var edge = (t - 0.5) * 2;
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

  // A print + dust drop on every footfall (bottom of each step bounce), but only
  // while actually crossing the track.
  var inner = stage.querySelector('.shoe');
  if (inner) {
    inner.addEventListener('animationiteration', function () {
      if (!crossing) return;
      var m = metrics();
      spawnFootprint(m);
      spawnDust(m);
    });
  }

  // ---- state machine -------------------------------------------------------
  var done = false, crossing = false, finished = false;
  var prog = 0, raf = null, crossStart = 0;

  function now() { return (window.performance && performance.now) ? performance.now() : Date.now(); }

  // Reduced motion: no running gait/dust. Just hold the new shoe, age it in
  // place, hold the worn shoe, reveal — keeping the new→worn bookends.
  // The ground only belongs to the crossing — hide it under the hero framings.
  overlay.classList.add('intro');

  if (reduce) {
    ctl.setProgress(0);
    applyHero();
    setTimeout(function () {
      ctl.setProgress(1);
      overlay.classList.add('zooming');
      setTimeout(function () {
        overlay.classList.add('hidden');
        setTimeout(dismissNow, 600);
      }, HOLD_MS);
    }, HOLD_MS);
  } else {
    // PHASE 1 — new shoe, hero, held.
    ctl.setProgress(0);
    applyHero();
    setTimeout(introTransition, HOLD_MS);
  }

  // PHASE 2a — hero → track start (still clean).
  function introTransition() {
    stage.style.transition = 'transform ' + INTRO_T + 'ms cubic-bezier(.5,0,.4,1)';
    requestAnimationFrame(function () { applyTrack(0); });
    setTimeout(startCrossing, INTRO_T + 20);
  }

  // PHASE 2b — cross the track, aging, leaving prints + dust.
  function startCrossing() {
    stage.style.transition = '';      // rAF owns the transform now
    overlay.classList.remove('intro');// fade the ground in for the run
    stage.classList.add('walking');
    crossing = true;
    crossStart = now();
    raf = requestAnimationFrame(tick);
  }

  function tick() {
    var elapsed = (now() - crossStart) / 1000;
    // Asymptote toward 0.9 until the data is ready, then complete the crossing.
    var target = done ? 1 : Math.min(0.9, 1 - Math.exp(-elapsed / 2.4));
    prog += (target - prog) * 0.07;
    var p = Math.min(prog, 1);
    ctl.setProgress(p);
    applyTrack(p);
    if (done && prog > 0.992 && (now() - crossStart) >= MIN_CROSS_MS) {
      ctl.setProgress(1);
      applyTrack(1);
      outro();
      return;
    }
    raf = requestAnimationFrame(tick);
  }

  // PHASE 3 — worn shoe returns to centre (hero), held, then reveal.
  function outro() {
    if (finished) return;
    finished = true;
    crossing = false;
    if (raf) cancelAnimationFrame(raf);
    stage.classList.remove('walking');
    ctl.setProgress(1);                 // fully worn
    overlay.classList.add('zooming');   // fade the ground + footprints away
    stage.style.transition = 'transform ' + OUTRO_T + 'ms cubic-bezier(.4,0,.3,1)';
    requestAnimationFrame(applyHero);   // track-end → hero centre
    setTimeout(function () {
      setTimeout(function () {          // hold the worn shoe HOLD_MS
        overlay.classList.add('hidden');
        setTimeout(dismissNow, 600);
      }, HOLD_MS);
    }, OUTRO_T);
  }

  function dismissNow() {
    if (overlay && overlay.parentNode) overlay.parentNode.removeChild(overlay);
  }

  // Keep the hero framing correct if the viewport changes before the crossing.
  window.addEventListener('resize', function () {
    if (!crossing && !finished) applyHero();
  });

  // app.js signals the data is fully loaded.
  window.Loading = { done: function () { done = true; } };

  // Safety net: never trap the user if the load hangs (slow geo, failed fetch).
  setTimeout(function () { done = true; }, 14000);
})();
