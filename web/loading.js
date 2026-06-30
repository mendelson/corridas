/*!
 * loading.js — Tela de carregamento: o tênis da galeria fica centrado (no zoom,
 * pisando no chão) e envelhece de novo → desgastado enquanto o clima passa pelas
 * QUATRO ESTAÇÕES, na horizontal:
 *   primavera (céu verde, chuva leve + pétalas, respingos no tênis)
 *   → verão  (céu azul, sol forte)
 *   → outono (céu âmbar, folhas ao vento)
 *   → inverno(céu frio, neve caindo)
 * Quando os dados estão prontos e o ciclo terminou (≥~2,8s), revela o site.
 *
 * Depende de ShoeWear (gallery/shoe-wear.js) e do overlay #loadingScreen.
 * app.js chama window.Loading.done() quando body.dataset.fullDataReady = '1'.
 */
(function () {
  'use strict';

  var overlay = document.getElementById('loadingScreen');
  if (!overlay) return;

  if (navigator.webdriver) {                 // automated browsers skip the loader
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

  // ---- geometry: shoe centred, fit-to-screen, sole on the ground -----------
  var GROUND_FRAC = 0.62;
  function W() { return stage.offsetWidth; }
  function H() { return stage.offsetHeight; }
  function vw() { return window.innerWidth; }
  function vh() { return window.innerHeight; }
  function groundY() { return vh() * GROUND_FRAC; }
  function setShoe(x, y, s) { stage.style.transform = 'translate(' + x + 'px,' + y + 'px) scale(' + s + ')'; }

  // Ground on the VISIBLE white midsole, not the dark outsole tread: the tread
  // is nearly invisible on the dark dirt, so grounding it left the white sole
  // floating above the ground. With the midsole the sole plainly rests on the
  // dirt (the tread sinks slightly in).
  var soleFrac = 0.88;
  (function () {
    try {
      var sole = stage.querySelector('.midsole') || stage.querySelector('.sole-wrap');
      var sb = stage.getBoundingClientRect();
      if (sole && sb.height) soleFrac = (sole.getBoundingClientRect().bottom - sb.top) / sb.height;
    } catch (e) {}
  })();
  // Leave ~14vh of sky above the shoe so it reads as a shoe standing on a floor
  // (not jammed to the top edge), and keep it within the width.
  function heroScale() { return Math.min(0.82 * vw() / W(), (groundY() - vh() * 0.14) / (soleFrac * H())); }
  function applyHero() {
    var s = heroScale();
    // Sink the sole a few px into the ground so the shoe plainly rests on it.
    setShoe((vw() - W() * s) / 2, groundY() - soleFrac * H() * s + 6, s);
  }

  // ---- build the weather layers (no markup change in the shells) -----------
  function rnd(a, b) { return a + Math.random() * (b - a); }
  function layer(cls) { var d = document.createElement('div'); d.className = cls; scene.appendChild(d); return d; }
  function field(cls, n, gen) {
    var c = layer(cls);
    if (reduce) return c;
    var h = ''; for (var i = 0; i < n; i++) h += gen(i); c.innerHTML = h; return c;
  }

  // Four crossfading sky washes (sweep in from the right) — one per season.
  var sky = layer('load-sky');
  sky.innerHTML = '<div class="sky-spring"></div><div class="sky-summer"></div>'
                + '<div class="sky-autumn"></div><div class="sky-winter"></div>';

  // Spring: light slanted rain + drifting blossom petals.
  field('load-rain', Math.max(28, Math.min(70, Math.round(vw() / 22))), function () {
    return '<span class="load-drop" style="left:' + rnd(0, 100).toFixed(2) + '%;height:' + rnd(6, 13).toFixed(1)
      + 'vh;animation-duration:' + rnd(0.55, 1.0).toFixed(2) + 's;animation-delay:' + (-rnd(0, 1.2)).toFixed(2)
      + 's;opacity:' + rnd(0.3, 0.65).toFixed(2) + '"></span>';
  });
  var PETALS = ['#f3b6cf', '#f7c9d8', '#eaa6c6', '#f4a9c4'];
  field('load-petals', 28, function (i) {
    return '<span class="load-petal" style="left:' + rnd(-4, 100).toFixed(2) + '%;--c:' + PETALS[i % PETALS.length]
      + ';width:' + rnd(11, 19).toFixed(0) + 'px;animation-duration:' + rnd(3.0, 5.0).toFixed(2)
      + 's;animation-delay:' + (-rnd(0, 4)).toFixed(2) + 's"></span>';
  });
  var splashes = layer('load-splashes');   // rain hitting the ground + the shoe (spring)

  // Summer: the sun.
  layer('load-sun');

  // Autumn: leaves blown across by the wind.
  var LEAF = '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">'
    + '<path d="M12 1 C19 6 21 15 12 23 C3 15 5 6 12 1 Z" fill="currentColor"/>'
    + '<path d="M12 3 L12 21" stroke="rgba(0,0,0,.28)" stroke-width="1" fill="none"/>'
    + '<path d="M12 9 L8 7 M12 9 L16 7 M12 13 L8 11 M12 13 L16 11" stroke="rgba(0,0,0,.18)" stroke-width="0.8" fill="none"/></svg>';
  var LCOL = ['#c0612a', '#d98b3a', '#8a9a3b', '#b5482a', '#caa24a', '#9c5a25'];
  field('load-leaves', 14, function (i) {
    return '<span class="load-leaf" style="--y0:' + rnd(4, 50).toFixed(1) + 'vh;color:' + LCOL[i % LCOL.length]
      + ';width:' + rnd(13, 28).toFixed(0) + 'px;animation-duration:' + rnd(2.2, 4.0).toFixed(2)
      + 's;animation-delay:' + rnd(0, 2.4).toFixed(2) + 's">' + LEAF + '</span>';
  });

  // Winter: snow.
  field('load-snow', Math.max(34, Math.min(80, Math.round(vw() / 18))), function () {
    var sz = rnd(3, 7).toFixed(1);
    return '<span class="load-flake" style="left:' + rnd(0, 100).toFixed(2) + '%;width:' + sz + 'px;height:' + sz
      + 'px;animation-duration:' + rnd(2.6, 5.0).toFixed(2) + 's;animation-delay:' + (-rnd(0, 5)).toFixed(2)
      + 's;opacity:' + rnd(0.55, 1).toFixed(2) + '"></span>';
  });
  layer('load-frost');   // snow settled on the ground (winter only)

  // ---- run: age the shoe + march through the four seasons ------------------
  function now() { return (window.performance && performance.now) ? performance.now() : Date.now(); }
  function smooth(t) { t = t < 0 ? 0 : t > 1 ? 1 : t; return t * t * (3 - 2 * t); }

  var SEASONS = ['s-spring', 's-summer', 's-autumn', 's-winter'];
  var DURATION = 8000;            // 4 seasons × 2s each
  // Debug aid (e.g. ?loaderMs=16000) to slow the arc down for inspection/QA;
  // no effect in normal use.
  try { var _m = +(new URLSearchParams(location.search).get('loaderMs')); if (_m > 0) DURATION = _m; } catch (e) {}
  var SEG = DURATION / 4;         // 2s per season
  var MIN_MS = DURATION;          // loader stays for the whole cycle
  var startT = now(), done = false, finished = false, season = -1, raf = null, lastSplash = 0;

  function setSeason(i) {
    if (i === season) return;
    season = i;
    for (var j = 0; j < SEASONS.length; j++) overlay.classList.toggle(SEASONS[j], j === i);
  }

  function spawnSplash() {
    var shoe = stage.getBoundingClientRect(), onShoe = Math.random() < 0.5, s = document.createElement('span');
    if (onShoe) {
      s.className = 'load-spat';
      s.style.left = (shoe.left + shoe.width * rnd(0.22, 0.78)) + 'px';
      s.style.top = (shoe.top + shoe.height * rnd(0.12, 0.52)) + 'px';
    } else {
      s.className = 'load-ripple';
      var w = rnd(10, 32);
      s.style.left = (Math.random() * vw()) + 'px';
      s.style.top = (groundY() + rnd(0, 8)) + 'px';
      s.style.width = w + 'px'; s.style.height = (w * 0.4) + 'px';
    }
    splashes.appendChild(s);
    s.addEventListener('animationend', function () { if (s.parentNode) s.parentNode.removeChild(s); });
  }

  ctl.setProgress(0);
  applyHero();
  setSeason(0);

  function tick() {
    var t = now() - startT;
    ctl.setProgress(smooth(t / DURATION));                 // progressive wear → final
    setSeason(Math.min(SEASONS.length - 1, Math.floor(t / SEG)));
    if (!reduce && season === 0 && t - lastSplash >= 90) { lastSplash = t; spawnSplash(); spawnSplash(); }
    if (t >= MIN_MS && done) { finish(); return; }
    raf = requestAnimationFrame(tick);
  }
  raf = requestAnimationFrame(tick);

  function finish() {
    if (finished) return;
    finished = true;
    if (raf) cancelAnimationFrame(raf);
    ctl.setProgress(1);
    setSeason(SEASONS.length - 1);
    overlay.classList.add('hidden');
    setTimeout(dismissNow, 600);
  }

  function dismissNow() {
    if (overlay && overlay.parentNode) overlay.parentNode.removeChild(overlay);
  }

  window.addEventListener('resize', function () { if (!finished) applyHero(); });
  window.Loading = { done: function () { done = true; } };
  setTimeout(function () { done = true; }, 14000);   // safety net
})();
