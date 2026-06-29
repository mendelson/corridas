/*!
 * loading.js — Tela de carregamento com o tênis da galeria.
 *
 * O tênis fica SEMPRE na tela, no mesmo enquadramento de zoom (grande, pisando
 * no chão). Ao longo de ≥2s ele envelhece progressivamente (0 → estado final).
 * Enquanto isso, primeiro CAI CHUVA e depois SURGE UM SOL. Quando os dados estão
 * prontos e já se passaram ≥2s, o overlay some e revela o site.
 *
 * Depende de ShoeWear (gallery/shoe-wear.js) e do overlay #loadingScreen.
 * app.js chama window.Loading.done() quando body.dataset.fullDataReady = '1'.
 */
(function () {
  'use strict';

  var overlay = document.getElementById('loadingScreen');
  if (!overlay) return;

  // Automated browsers (Playwright/Selenium) skip the loader entirely so its
  // overlay never intercepts test interactions — pure UX flourish.
  if (navigator.webdriver) {
    if (overlay.parentNode) overlay.parentNode.removeChild(overlay);
    return;
  }

  var scene = overlay.querySelector('.load-scene');
  var stage = overlay.querySelector('.load-shoe-stage');
  if (!scene || !stage) { dismissNow(); return; }

  var reduce = false;
  try { reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches; } catch (e) {}

  var ctl = null;
  try { if (window.ShoeWear) ctl = window.ShoeWear.mount(stage); } catch (e) {}
  if (!ctl) { dismissNow(); return; }

  // ---- geometry: keep the shoe centred, fit-to-screen, sole on the ground ----
  var GROUND_FRAC = 0.62;
  function W() { return stage.offsetWidth; }
  function H() { return stage.offsetHeight; }
  function vw() { return window.innerWidth; }
  function vh() { return window.innerHeight; }
  function groundY() { return vh() * GROUND_FRAC; }
  function setShoe(x, y, s) { stage.style.transform = 'translate(' + x + 'px,' + y + 'px) scale(' + s + ')'; }

  // Sole position inside the box (measured), so the shoe is grounded by its sole
  // at any scale (the SVG leaves empty space below the outsole).
  var soleFrac = 0.93;
  (function () {
    try {
      var sole = stage.querySelector('.outsole') || stage.querySelector('.sole-wrap');
      var sb = stage.getBoundingClientRect();
      if (sole && sb.height) soleFrac = (sole.getBoundingClientRect().bottom - sb.top) / sb.height;
    } catch (e) {}
  })();

  function heroScale() { return Math.min(0.82 * vw() / W(), (groundY() - 24) / (soleFrac * H())); }
  function applyHero() {
    var s = heroScale();
    setShoe((vw() - W() * s) / 2, groundY() - soleFrac * H() * s + 3, s);
  }

  // ---- weather: rain first, then the sun ----
  var sun = document.createElement('div');
  sun.className = 'load-sun';
  sun.setAttribute('aria-hidden', 'true');
  scene.insertBefore(sun, scene.firstChild); // behind the shoe (sky)

  var rain = document.createElement('div');
  rain.className = 'load-rain';
  rain.setAttribute('aria-hidden', 'true');
  if (!reduce) {
    var drops = Math.max(40, Math.min(90, Math.round(vw() / 14)));
    var html = '';
    for (var i = 0; i < drops; i++) {
      var left = (Math.random() * 100).toFixed(2);
      var dur = (0.55 + Math.random() * 0.5).toFixed(2);
      var delay = (-Math.random() * 1.2).toFixed(2);
      var len = (8 + Math.random() * 8).toFixed(1);
      var op = (0.35 + Math.random() * 0.4).toFixed(2);
      html += '<span class="load-drop" style="left:' + left + '%;height:' + len + 'vh;'
            + 'animation-duration:' + dur + 's;animation-delay:' + delay + 's;opacity:' + op + '"></span>';
    }
    rain.innerHTML = html;
  }
  scene.appendChild(rain); // in front (falls over the shoe)

  // ---- run ----
  function now() { return (window.performance && performance.now) ? performance.now() : Date.now(); }
  function smooth(t) { t = t < 0 ? 0 : t > 1 ? 1 : t; return t * t * (3 - 2 * t); }

  var DURATION = 2000;   // shoe ages clean → worn over this long
  var SUN_START = 1100;  // rain falls first, then the sun comes out
  var MIN_MS = 2000;     // the loader is on screen for at least 2s total
  var startT = now(), done = false, finished = false, sunOn = false, raf = null;

  ctl.setProgress(0);
  applyHero();
  overlay.classList.add('raining');

  function tick() {
    var el = now() - startT;
    ctl.setProgress(smooth(el / DURATION));        // progressive wear → final state
    if (!sunOn && el >= SUN_START) {               // rain clears, sun rises
      sunOn = true;
      overlay.classList.add('sunny');
    }
    if (el >= MIN_MS && done) { finish(); return; }
    raf = requestAnimationFrame(tick);
  }
  raf = requestAnimationFrame(tick);

  function finish() {
    if (finished) return;
    finished = true;
    if (raf) cancelAnimationFrame(raf);
    ctl.setProgress(1);                            // fully worn, final state
    if (!sunOn) overlay.classList.add('sunny');
    overlay.classList.add('hidden');               // fade overlay → reveal site
    setTimeout(dismissNow, 600);
  }

  function dismissNow() {
    if (overlay && overlay.parentNode) overlay.parentNode.removeChild(overlay);
  }

  // The shoe is static; just keep it framed correctly on resize.
  window.addEventListener('resize', function () { if (!finished) applyHero(); });

  // app.js signals the data is fully loaded.
  window.Loading = { done: function () { done = true; } };

  // Safety net: never trap the user if the load hangs (slow geo, failed fetch).
  setTimeout(function () { done = true; }, 14000);
})();
