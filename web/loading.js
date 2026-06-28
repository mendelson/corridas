/*!
 * loading.js — Tela de carregamento com o tênis da galeria.
 *
 * O tênis fica SEMPRE grande e centralizado (o mesmo enquadramento "zoom" do
 * início/fim da galeria — ele nunca cruza a tela). Enquanto isso, passa UM ANO:
 * as estações giram numa roda celeste — cada estação NASCE pela direita, cruza o
 * topo e SE PÕE pela esquerda enquanto a próxima sobe — e o tênis envelhece de
 * NOVO a GASTO. A intenção é de tempo passando e desgastando o tênis.
 *
 * Suavidade: a roda é uma animação de `transform: rotate` e cada emblema
 * contra-gira para ficar em pé — TUDO com `transform`, ou seja, roda no
 * COMPOSITOR e não trava quando a main thread fica ocupada lendo o JSON. O
 * filtro de deformação (caro) do tênis é desligado nesta tela (ele aparece
 * enorme aqui), restando o envelhecimento por opacidade, atualizado com
 * parcimônia (~12 fps) para não disputar a main thread.
 *
 * A introdução SEMPRE roda pelo menos um ciclo inteiro: revela só na virada de
 * um ciclo, e somente quando os dados já chegaram.
 *
 * Depende de ShoeWear (gallery/shoe-wear.js) e do overlay #loadingScreen.
 * app.js chama window.Loading.done() quando os dados terminam de carregar.
 */
(function () {
  'use strict';

  var overlay = document.getElementById('loadingScreen');
  if (!overlay) return;

  if (navigator.webdriver) {
    if (overlay.parentNode) overlay.parentNode.removeChild(overlay);
    return;
  }

  var scene = overlay.querySelector('.load-scene') || overlay;
  var stage = overlay.querySelector('.load-shoe-stage');
  if (!stage) { dismissNow(); return; }

  var reduce = false;
  try { reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches; } catch (e) {}

  var ctl = null;
  try { if (window.ShoeWear) ctl = window.ShoeWear.mount(stage); } catch (e) {}
  if (!ctl) { dismissNow(); return; }

  // The SVG crumple (feDisplacementMap) is gorgeous but re-rasters the WHOLE
  // shoe every time progress changes — and here the shoe is huge (hero), so it
  // hammers the main thread and causes the hitching. Drop it for the loader; the
  // shoe still ages via the (cheap) opacity wear layers.
  try {
    var sole = stage.querySelector('.sole-wrap'); if (sole) sole.style.filter = 'none';
    var upper = stage.querySelector('.upper-wrap'); if (upper) upper.style.filter = 'none';
  } catch (e) {}

  // ---- timing --------------------------------------------------------------
  var CYCLE_MS = 6000;     // one full year (4 seasons); the shoe ages over it
  var WEAR_MS = 80;        // throttle the shoe-aging repaint to ~12 fps
  var GROUND_FRAC = 0.62;
  overlay.style.setProperty('--cyc', CYCLE_MS + 'ms');

  function W() { return stage.offsetWidth; }
  function H() { return stage.offsetHeight; }
  function vw() { return window.innerWidth; }
  function vh() { return window.innerHeight; }
  function groundY() { return vh() * GROUND_FRAC; }

  function setShoe(x, y, s) {
    stage.style.transform = 'translate(' + x + 'px,' + y + 'px) scale(' + s + ')';
  }

  var soleFrac = 0.93;
  (function () {
    try {
      var sw = stage.querySelector('.outsole') || stage.querySelector('.sole-wrap');
      var sb = stage.getBoundingClientRect();
      if (sw && sb.height) soleFrac = (sw.getBoundingClientRect().bottom - sb.top) / sb.height;
    } catch (e) {}
  })();

  function topForSole(s) { return groundY() - soleFrac * H() * s + 3; }
  function heroScale() { return Math.min(0.82 * vw() / W(), (groundY() - 24) / (soleFrac * H())); }
  function applyHero() {
    var s = heroScale();
    setShoe((vw() - W() * s) / 2, topForSole(s), s);
  }
  applyHero();

  // ---- scene: sky tint + celestial wheel (built here so the shells stay clean) -
  var sky = document.createElement('div');
  sky.className = 'load-sky';
  scene.insertBefore(sky, scene.firstChild);

  var arc = document.createElement('div');
  arc.className = 'load-arc';
  scene.insertBefore(arc, stage); // behind the shoe (the focus), above the sky

  var wheel = document.createElement('div');
  wheel.className = 'load-wheel';
  arc.appendChild(wheel);

  function emblem(season, build) {
    var e = document.createElement('div');
    e.className = 'load-emblem e-' + season;
    if (build) build(e);
    wheel.appendChild(e);            // a child of the wheel → orbits as it spins
    return e;
  }
  emblem('spring', function (e) {
    var c = document.createElement('div'); c.className = 'cloud'; e.appendChild(c);
    [22, 44, 66].forEach(function (x, i) {
      var r = document.createElement('span'); r.className = 'rd';
      r.style.left = x + 'px';
      r.style.animationDelay = (i * 0.32).toFixed(2) + 's';
      e.appendChild(r);
    });
  });
  emblem('summer', null);
  emblem('autumn', function (e) {
    var l = document.createElement('div'); l.className = 'leaf'; e.appendChild(l);
  });
  emblem('winter', function (e) {
    [0, 60, 120].forEach(function (deg) {
      var s = document.createElement('span'); s.className = 'spoke';
      s.style.transform = 'rotate(' + deg + 'deg)';
      e.appendChild(s);
    });
  });

  function easeInOut(t) { return t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2; }

  // ---- state machine -------------------------------------------------------
  var done = false, finished = false, raf = null, start = 0, cur = 0, lastWear = 0, lastCyc = 0;

  function now() { return (window.performance && performance.now) ? performance.now() : Date.now(); }

  ctl.setProgress(0);
  start = now();
  lastWear = start;

  // Non-reduced: the wheel + sky run on the compositor (CSS). Reveal at a full
  // cycle boundary via the wheel animation's iteration event — always at least
  // one complete year, and only once the data is ready.
  if (!reduce) {
    wheel.addEventListener('animationiteration', function () { if (done) reveal(); });
  }

  raf = requestAnimationFrame(tick);
  function tick() {
    var t = now(), el = t - start;
    // Age the shoe new -> worn over the first cycle, throttled + eased so it
    // never jumps after a one-off main-thread stall and never spams repaints.
    if (t - lastWear >= WEAR_MS) {
      lastWear = t;
      var target = easeInOut(Math.min(1, el / CYCLE_MS));
      cur += (target - cur) * 0.3;
      ctl.setProgress(cur);
    }
    if (reduce) {
      var cyc = Math.floor(el / CYCLE_MS);
      if (cyc > lastCyc) { lastCyc = cyc; if (done) { reveal(); return; } }
    }
    raf = requestAnimationFrame(tick);
  }

  function reveal() {
    if (finished) return;
    finished = true;
    if (raf) cancelAnimationFrame(raf);
    ctl.setProgress(1);
    overlay.classList.add('hidden');
    setTimeout(dismissNow, 650);
  }

  function dismissNow() {
    if (overlay && overlay.parentNode) overlay.parentNode.removeChild(overlay);
  }

  window.addEventListener('resize', function () { if (!finished) applyHero(); });

  // app.js signals the data is fully loaded.
  window.Loading = { done: function () { done = true; } };

  // Safety net: never trap the user if the load hangs (slow geo, failed fetch).
  setTimeout(function () { done = true; }, 14000);
})();
