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
 * A introdução SEMPRE roda pelo menos um ciclo inteiro. Se os dados ainda não
 * terminaram ao fim do ciclo, ela roda outro ciclo (o tênis permanece gasto) até
 * os dados chegarem; então, ao fim do ciclo, o overlay some e revela o site já
 * carregado.
 *
 * Depende de ShoeWear (gallery/shoe-wear.js) e do overlay #loadingScreen.
 * app.js chama window.Loading.done() quando os dados terminam de carregar.
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

  var scene = overlay.querySelector('.load-scene') || overlay;
  var stage = overlay.querySelector('.load-shoe-stage');
  if (!stage) { dismissNow(); return; }

  var reduce = false;
  try { reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches; } catch (e) {}

  var ctl = null;
  try { if (window.ShoeWear) ctl = window.ShoeWear.mount(stage); } catch (e) {}
  if (!ctl) { dismissNow(); return; }

  // ---- timing --------------------------------------------------------------
  var CYCLE_MS = 4000;     // one full year (4 seasons); the shoe ages over it
  var GROUND_FRAC = 0.62;  // ground line as a fraction of viewport height
  var SEASONS = ['spring', 'summer', 'autumn', 'winter'];

  function W() { return stage.offsetWidth; }
  function H() { return stage.offsetHeight; }
  function vw() { return window.innerWidth; }
  function vh() { return window.innerHeight; }
  function groundY() { return vh() * GROUND_FRAC; }

  function setShoe(x, y, s) {
    stage.style.transform = 'translate(' + x + 'px,' + y + 'px) scale(' + s + ')';
  }

  // Where the SOLE sits inside the stage box (the SVG leaves a sliver below the
  // outsole). Measured once at scale 1 so the shoe is grounded by its sole.
  var soleFrac = 0.93;
  (function () {
    try {
      var sole = stage.querySelector('.outsole') || stage.querySelector('.sole-wrap');
      var sb = stage.getBoundingClientRect();
      if (sole && sb.height) {
        soleFrac = (sole.getBoundingClientRect().bottom - sb.top) / sb.height;
      }
    } catch (e) {}
  })();

  function topForSole(s) { return groundY() - soleFrac * H() * s + 3; }

  // Hero: as large as fits — wide enough for side margins, short enough to stand
  // above the ground line — centred, sole on the ground. Held the whole time.
  function heroScale() {
    return Math.min(0.82 * vw() / W(), (groundY() - 24) / (soleFrac * H()));
  }
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
  // Behind the shoe (which is the focus) but above the sky tint, so seasons rise
  // and set behind the aging shoe.
  scene.insertBefore(arc, stage);

  function emblem(season, build) {
    var e = document.createElement('div');
    e.className = 'load-emblem e-' + season;
    if (build) build(e);
    arc.appendChild(e);
    return e;
  }
  // Order MUST match SEASONS: index 0 sits at the top at rotation 0, then each
  // rises from the right as the wheel turns.
  var emblems = [
    emblem('spring', function (e) {
      var c = document.createElement('div'); c.className = 'cloud'; e.appendChild(c);
      [22, 44, 66].forEach(function (x, i) {
        var r = document.createElement('span'); r.className = 'rd';
        r.style.left = x + 'px';
        r.style.animationDelay = (i * 0.28).toFixed(2) + 's';
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

  var curSeason = -1;
  function setSeason(i) {
    if (i === curSeason) return;
    curSeason = i;
    sky.className = 'load-sky ' + SEASONS[i];
  }

  // Place every emblem on the arc for a given rotation (φ in degrees). Each
  // emblem k starts 90° apart; θ measured from the top, +to the right. As φ
  // grows the emblems' θ shrinks → they rise on the right, peak at the top, set
  // on the left. Below the horizon (cos θ < 0) they fade out and are clipped.
  function placeWheel(phi) {
    var cx = vw() / 2, cy = groundY(), R = 0.46 * vh();
    for (var k = 0; k < 4; k++) {
      var th = (k * 90 - phi) * Math.PI / 180;
      var x = cx + R * Math.sin(th);
      var y = cy - R * Math.cos(th);
      var op = Math.max(0, Math.min(1, Math.cos(th) * 1.3));
      var e = emblems[k];
      e.style.left = x + 'px';
      e.style.top = y + 'px';
      e.style.opacity = op.toFixed(3);
    }
  }
  // Reduced motion: no spinning wheel — just hold the active season's emblem at
  // the top and hide the rest; the season still advances over the cycle.
  function placeStatic(seasonIdx) {
    var cx = vw() / 2, cy = groundY(), R = 0.46 * vh();
    for (var k = 0; k < 4; k++) {
      var e = emblems[k], on = (k === seasonIdx);
      e.style.left = cx + 'px';
      e.style.top = (cy - R) + 'px';
      e.style.opacity = on ? '1' : '0';
    }
  }

  function easeInOut(t) { return t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2; }

  // ---- state machine -------------------------------------------------------
  var done = false, finished = false, raf = null, anim = 0, last = 0, lastCyc = 0;

  function now() { return (window.performance && performance.now) ? performance.now() : Date.now(); }

  ctl.setProgress(0);
  applyHero();
  last = now();
  raf = requestAnimationFrame(tick);

  function tick() {
    var t = now(), dt = t - last; last = t;
    // Clamp large gaps so a main-thread stall (the one-off MBs corridas.json
    // parse in app.js freezes rAF) PAUSES the wheel instead of skipping seasons.
    if (dt > 80) dt = 80;
    anim += dt;

    // The shoe ages new -> worn across the FIRST cycle, then stays worn.
    ctl.setProgress(easeInOut(Math.min(1, anim / CYCLE_MS)));

    var frac = anim / CYCLE_MS;              // cycles elapsed (can exceed 1)
    // Tint the sky for whichever emblem is currently HIGHEST (round, not floor,
    // so the tint peaks with the emblem at the top — not when it starts rising).
    var s4 = Math.round(frac * 4) % 4;
    setSeason(s4);
    if (reduce) placeStatic(s4);
    else placeWheel((frac * 360) % 360);

    // A full cycle just completed?
    var cyc = Math.floor(frac);
    if (cyc > lastCyc) {
      lastCyc = cyc;
      if (done) { reveal(); return; }       // ran >= 1 full cycle AND data ready
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

  // Keep the hero framing correct if the viewport changes (the shoe never moves
  // otherwise, so re-applying only on resize is enough — no per-frame thrash).
  window.addEventListener('resize', function () { if (!finished) applyHero(); });

  // app.js signals the data is fully loaded.
  window.Loading = { done: function () { done = true; } };

  // Safety net: never trap the user if the load hangs (slow geo, failed fetch).
  setTimeout(function () { done = true; }, 14000);
})();
