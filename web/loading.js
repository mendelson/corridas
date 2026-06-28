/*!
 * loading.js — Tela de carregamento com o tênis da galeria.
 *
 * O tênis fica SEMPRE grande e centralizado (o mesmo enquadramento "zoom" do
 * início/fim da galeria — ele nunca cruza a tela). Enquanto isso, passa UM ANO:
 * as estações giram numa roda celeste — cada estação NASCE pela direita, cruza o
 * topo e SE PÕE pela esquerda enquanto a próxima sobe (acaba a chuva, tudo gira
 * para a esquerda, o sol sobe pela direita...) — e o tênis envelhece de NOVO a
 * GASTO. A intenção é de tempo passando e desgastando o tênis.
 *
 * A roda e o céu são animados por CSS (Motion Path + keyframes), ou seja, rodam
 * no COMPOSITOR — não travam quando a main thread fica ocupada lendo o JSON dos
 * dados. Só o envelhecimento do tênis (SVG) é via JS, e é suave/sutil.
 *
 * A introdução SEMPRE roda pelo menos um ciclo inteiro. Se os dados ainda não
 * terminaram ao fim do ciclo, ela gira outro (o tênis permanece gasto) até os
 * dados chegarem; então, ao fim do ciclo, o overlay some e revela o site.
 *
 * Depende de ShoeWear (gallery/shoe-wear.js) e do overlay #loadingScreen.
 * app.js chama window.Loading.done() quando os dados terminam de carregar.
 */
(function () {
  'use strict';

  var overlay = document.getElementById('loadingScreen');
  if (!overlay) return;

  // Automated browsers skip the loader entirely so its overlay never intercepts
  // test interactions — pure UX flourish, no behaviour or data change.
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

  // ---- timing --------------------------------------------------------------
  var CYCLE_MS = 6000;     // one full year (4 seasons); the shoe ages over it
  var GROUND_FRAC = 0.62;  // ground line as a fraction of viewport height
  overlay.style.setProperty('--cyc', CYCLE_MS + 'ms');

  function W() { return stage.offsetWidth; }
  function H() { return stage.offsetHeight; }
  function vw() { return window.innerWidth; }
  function vh() { return window.innerHeight; }
  function groundY() { return vh() * GROUND_FRAC; }

  function setShoe(x, y, s) {
    stage.style.transform = 'translate(' + x + 'px,' + y + 'px) scale(' + s + ')';
  }

  // Where the SOLE sits inside the stage box. Measured once at scale 1 so the
  // shoe is grounded by its sole, not the box bottom.
  var soleFrac = 0.93;
  (function () {
    try {
      var sole = stage.querySelector('.outsole') || stage.querySelector('.sole-wrap');
      var sb = stage.getBoundingClientRect();
      if (sole && sb.height) soleFrac = (sole.getBoundingClientRect().bottom - sb.top) / sb.height;
    } catch (e) {}
  })();

  function topForSole(s) { return groundY() - soleFrac * H() * s + 3; }
  function heroScale() { return Math.min(0.82 * vw() / W(), (groundY() - 24) / (soleFrac * H())); }
  function applyHero() {
    var s = heroScale();
    setShoe((vw() - W() * s) / 2, topForSole(s), s);
  }

  // ---- scene: sky tint + celestial wheel (built here so the shells stay clean) -
  var sky = document.createElement('div');
  sky.className = 'load-sky';
  scene.insertBefore(sky, scene.firstChild);

  var arc = document.createElement('div');
  arc.className = 'load-arc';
  scene.insertBefore(arc, stage); // behind the shoe (the focus), above the sky

  function emblem(season, build) {
    var e = document.createElement('div');
    e.className = 'load-emblem e-' + season;
    if (build) build(e);
    arc.appendChild(e);
    return e;
  }
  // Order MUST match the seasons (spring, summer, autumn, winter): index 0 is at
  // the top at t=0, then each rises from the right a quarter-cycle apart.
  var emblems = [
    emblem('spring', function (e) {
      var c = document.createElement('div'); c.className = 'cloud'; e.appendChild(c);
      [22, 44, 66].forEach(function (x, i) {
        var r = document.createElement('span'); r.className = 'rd';
        r.style.left = x + 'px';
        r.style.animationDelay = (i * 0.32).toFixed(2) + 's';
        e.appendChild(r);
      });
    }),
    emblem('summer', null),
    emblem('autumn', function (e) {
      var l = document.createElement('div'); l.className = 'leaf'; e.appendChild(l);
    }),
    emblem('winter', function (e) {
      [0, 60, 120].forEach(function (deg) {
        var s = document.createElement('span'); s.className = 'spoke';
        s.style.transform = 'rotate(' + deg + 'deg)';
        e.appendChild(s);
      });
    })
  ];

  // The orbit is a circle through the top/horizon, centred on the horizon. The
  // CSS animation drives offset-distance; each emblem is phased a quarter apart
  // so they rise on the right and set on the left. Recomputed on resize.
  function layout() {
    var cx = vw() / 2, cy = groundY(), R = 0.46 * vh();
    // CCW circle from the top: top -> left -> bottom -> right -> top.
    var p = "path('M " + cx + "," + (cy - R) +
            " A " + R + "," + R + " 0 1,0 " + cx + "," + (cy + R) +
            " A " + R + "," + R + " 0 1,0 " + cx + "," + (cy - R) + "')";
    for (var k = 0; k < 4; k++) {
      var e = emblems[k];
      e.style.offsetPath = p;
      if (!reduce) e.style.animationDelay = (-(((4 - k) % 4) / 4) * CYCLE_MS) + 'ms';
    }
    applyHero();
  }
  layout();

  function easeInOut(t) { return t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2; }

  // ---- state machine -------------------------------------------------------
  var done = false, finished = false, raf = null, start = 0, cur = 0, lastCyc = 0;

  function now() { return (window.performance && performance.now) ? performance.now() : Date.now(); }

  ctl.setProgress(0);
  start = now();

  // Non-reduced: the wheel + sky run on the compositor (CSS). Reveal at a full
  // cycle boundary via the sky animation's iteration event, so we always show at
  // least one complete year and only then hand off to the loaded site.
  if (!reduce) {
    sky.addEventListener('animationiteration', function () { if (done) reveal(); });
  }

  raf = requestAnimationFrame(tick);
  function tick() {
    var el = now() - start;
    // Age the shoe new -> worn across the first cycle, eased so a one-off
    // main-thread stall (the data parse) catches up smoothly instead of jumping.
    var target = easeInOut(Math.min(1, el / CYCLE_MS));
    cur += (target - cur) * 0.12;
    ctl.setProgress(cur);

    if (reduce) {
      // No spinning wheel: hold the active season's emblem at the top, hide the
      // rest, and reveal at a full-cycle boundary once data is ready.
      var s = Math.floor((el / CYCLE_MS) * 4) % 4;
      for (var k = 0; k < 4; k++) emblems[k].style.offsetDistance = (k === s) ? '0%' : '50%';
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

  window.addEventListener('resize', function () { if (!finished) layout(); });

  // app.js signals the data is fully loaded.
  window.Loading = { done: function () { done = true; } };

  // Safety net: never trap the user if the load hangs (slow geo, failed fetch).
  setTimeout(function () { done = true; }, 14000);
})();
