/*!
 * shoe-wear.js — Tênis de corrida que envelhece conforme um progresso 0→1.
 * Sem dependências. Framework-agnostic.
 *
 * USO:
 *   const shoe = ShoeWear.mount(document.getElementById('shoe'));
 *   shoe.setProgress(0.0);   // 0 = zero km (limpo)   1 = veterano (rodado)
 *
 * Ligue setProgress() ao SEU progresso de scroll já existente (0→1).
 * Reversível: passar valores menores "rejuvenesce" o tênis.
 *
 * Dica de suavidade (opcional): se o seu progresso for "duro", interpole:
 *   let cur = 0;
 *   function tick(){ cur += (target - cur) * 0.12; shoe.setProgress(cur);
 *                    if (Math.abs(target-cur) > 0.001) requestAnimationFrame(tick); }
 */
(function (global) {
  'use strict';

  // ------- SVG do tênis (cobalt) + camadas de desgaste (começam invisíveis) -------
  var SVG_MARKUP = [
    '<svg viewBox="40 80 360 196" xmlns="http://www.w3.org/2000/svg" class="shoe-wear" aria-label="Tênis de corrida que envelhece">',
      '<defs>',
        '<linearGradient id="sw-grimeG" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#8a7c63" stop-opacity="0"/><stop offset="1" stop-color="#5f5238" stop-opacity="0.95"/></linearGradient>',
        '<radialGradient id="sw-dentG"><stop offset="0" stop-color="#a89876" stop-opacity="1"/><stop offset="1" stop-color="#a89876" stop-opacity="0"/></radialGradient>',
        '<radialGradient id="sw-updentG"><stop offset="0" stop-color="#16314a" stop-opacity="0.7"/><stop offset="1" stop-color="#16314a" stop-opacity="0"/></radialGradient>',
        '<radialGradient id="sw-abrG"><stop offset="0" stop-color="#7e93a6" stop-opacity="0.85"/><stop offset="1" stop-color="#7e93a6" stop-opacity="0"/></radialGradient>',
        '<linearGradient id="sw-patG" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#c79a55"/><stop offset="1" stop-color="#8f6a39"/></linearGradient>',
        // Crumple/deform: turbulence-driven displacement warps the whole shoe
        // SILHOUETTE; a second, stronger field crumples just the UPPER (cabedal).
        // Both start at scale 0 (clean) and ramp up with wear (set from JS).
        '<filter id="sw-crumple" x="-30%" y="-30%" width="160%" height="160%" color-interpolation-filters="sRGB"><feTurbulence type="fractalNoise" baseFrequency="0.009 0.022" numOctaves="2" seed="11" result="n"/><feDisplacementMap in="SourceGraphic" in2="n" scale="0" xChannelSelector="R" yChannelSelector="G"/></filter>',
        '<filter id="sw-crumple-up" x="-35%" y="-35%" width="170%" height="170%" color-interpolation-filters="sRGB"><feTurbulence type="fractalNoise" baseFrequency="0.015 0.04" numOctaves="2" seed="4" result="n"/><feDisplacementMap in="SourceGraphic" in2="n" scale="0" xChannelSelector="R" yChannelSelector="G"/></filter>',
      '</defs>',
      '<g class="w-dust" opacity="0"><ellipse cx="170" cy="262" rx="100" ry="12" fill="#a8946e" opacity="0.55"/><ellipse cx="320" cy="258" rx="76" ry="10" fill="#a8946e" opacity="0.5"/></g>',
      '<g class="shoe">',
        '<g class="sole-wrap">',
        // midsole / foam
        '<path class="midsole" d="M58 210 C54 224 54 244 66 252 C120 262 320 262 374 250 C388 244 392 226 384 212 C380 206 372 208 360 210 C300 220 130 220 80 210 C70 208 62 206 58 210 Z" fill="#eee8de"/>',
        '<path d="M56 232 C62 248 120 258 222 258 C320 258 372 250 384 236 C382 248 372 256 360 258 C300 264 130 264 80 258 C68 256 58 246 56 232 Z" fill="#d7cdbe"/>',
        '<path d="M62 214 C150 224 300 224 380 212 C384 216 382 222 376 224 C300 234 130 234 70 224 C64 222 60 218 62 214 Z" fill="#f5f0e8"/>',
        // foam wear
        '<path class="w-grime" d="M58 224 C150 238 300 236 384 218 C390 232 388 248 374 253 C320 263 120 263 66 253 C56 247 54 234 58 224 Z" fill="url(#sw-grimeG)" opacity="0" style="mix-blend-mode:multiply"/>',
        '<g class="w-dent" opacity="0"><ellipse cx="105" cy="232" rx="24" ry="13" fill="url(#sw-dentG)"/><ellipse cx="200" cy="240" rx="30" ry="11" fill="url(#sw-dentG)"/><ellipse cx="300" cy="233" rx="22" ry="12" fill="url(#sw-dentG)"/><ellipse cx="150" cy="236" rx="18" ry="9" fill="url(#sw-dentG)"/></g>',
        '<g class="w-crease" stroke="#8a795c" stroke-width="2.4" fill="none" stroke-linecap="round" opacity="0">',
          '<path d="M82 222 C98 230 116 230 132 224"/><path d="M80 236 C98 244 118 244 134 238"/>',
          '<path d="M262 222 C286 230 312 228 332 220"/><path d="M260 236 C286 244 312 242 332 234"/>',
          '<path d="M165 230 C190 237 218 236 242 229"/>',
        '</g>',
        '<path class="midline" d="M64 230 C150 240 300 238 382 222" fill="none" stroke="#b8552e" stroke-width="3.5" stroke-linecap="round" opacity="0.7"/>',
        '<path class="outsole" d="M70 252 C98 262 150 263 184 262 C150 256 108 254 84 248 C76 248 70 250 70 252 Z M256 262 C300 262 344 257 366 248 C346 260 308 263 270 263 C262 263 256 262 256 262 Z" fill="#2b2724"/>',
        '<g class="w-dirt" fill="#5f4a2c" opacity="0"><circle cx="120" cy="250" r="3.4"/><circle cx="150" cy="254" r="2.6"/><circle cx="186" cy="256" r="3.6"/><circle cx="225" cy="255" r="2.4"/><circle cx="262" cy="253" r="3"/><circle cx="300" cy="250" r="2.8"/><circle cx="335" cy="252" r="2.4"/><circle cx="100" cy="246" r="2.2"/></g>',
        '</g>',
        '<g class="upper-wrap">',
        // upper
        '<path class="upper" d="M78 210 C68 192 66 160 72 134 C78 112 92 106 100 116 C108 96 130 92 150 100 C156 116 158 128 160 138 C195 142 248 150 300 162 C342 172 366 188 376 210 C372 214 364 214 354 214 C250 218 130 218 92 214 C86 214 81 213 78 210 Z" fill="#3b6ea3"/>',
        '<path d="M160 138 C195 142 248 150 300 162 C300 178 296 196 286 210 C220 212 170 210 150 206 C150 184 154 158 160 138 Z" fill="#284f78" opacity="0.32"/>',
        '<path class="heel" d="M78 210 C68 192 66 160 72 134 C78 112 92 106 100 116 C94 138 92 172 98 200 C96 210 88 213 78 210 Z" fill="#284f78"/>',
        '<path d="M158 132 C176 136 198 140 218 146 C214 168 210 192 206 206 C190 204 174 200 162 196 C158 174 156 152 158 132 Z" fill="#284f78" opacity="0.55"/>',
        '<path class="toecap" d="M306 164 C338 174 360 190 376 210 C372 214 364 214 354 214 C318 216 300 216 292 214 C288 196 294 176 306 164 Z" fill="#284f78"/>',
        // upper wear
        '<g class="w-updent" opacity="0"><ellipse cx="220" cy="180" rx="34" ry="20" fill="url(#sw-updentG)"/><ellipse cx="130" cy="170" rx="22" ry="24" fill="url(#sw-updentG)"/><ellipse cx="300" cy="190" rx="20" ry="16" fill="url(#sw-updentG)"/></g>',
        '<g class="w-upcrease" stroke="#1d3f5e" stroke-width="2" fill="none" stroke-linecap="round" opacity="0">',
          '<path d="M150 150 C190 162 240 170 292 178"/><path d="M120 138 C100 158 96 182 104 202"/>',
          '<path d="M250 158 C246 176 244 194 248 208"/><path d="M180 200 C176 184 178 168 186 154"/><path d="M320 176 C330 188 334 200 332 210"/>',
        '</g>',
        '<path class="w-patina" d="M78 210 C68 192 66 160 72 134 C78 112 92 106 100 116 C108 96 130 92 150 100 C156 116 158 128 160 138 C195 142 248 150 300 162 C342 172 366 188 376 210 C372 214 364 214 354 214 C250 218 130 218 92 214 C86 214 81 213 78 210 Z" fill="url(#sw-patG)" opacity="0" style="mix-blend-mode:overlay"/>',
        '<g class="w-abrasion" opacity="0"><ellipse cx="84" cy="150" rx="14" ry="22" fill="url(#sw-abrG)"/><ellipse cx="350" cy="198" rx="18" ry="14" fill="url(#sw-abrG)"/><ellipse cx="100" cy="120" rx="10" ry="9" fill="url(#sw-abrG)"/></g>',
        '<g class="w-updirt" fill="#5a4126" opacity="0"><circle cx="110" cy="195" r="2.6"/><circle cx="140" cy="200" r="2"/><circle cx="175" cy="196" r="3"/><circle cx="215" cy="202" r="2.4"/><circle cx="250" cy="198" r="2.8"/><circle cx="285" cy="200" r="2.2"/><circle cx="320" cy="200" r="2.6"/><circle cx="95" cy="170" r="1.8"/><circle cx="200" cy="172" r="1.8"/><circle cx="270" cy="180" r="2"/></g>',
        '<g class="w-toecr" stroke="#16314a" stroke-width="1.8" fill="none" stroke-linecap="round" opacity="0"><path d="M300 168 C306 180 308 194 306 206"/><path d="M314 172 C320 184 322 196 320 207"/><path d="M328 180 C334 190 336 200 334 208"/></g>',
        '<path class="w-scuff" d="M338 194 C356 198 370 205 376 212 C362 217 344 215 334 209 C334 202 336 197 338 194 Z" fill="#6e5236" opacity="0"/>',
        // peito do pé (instep): compressão + vincos profundos onde o pé flexiona
        '<g class="w-instep" opacity="0">',
          '<ellipse cx="234" cy="178" rx="48" ry="23" fill="url(#sw-updentG)"/>',
          '<g stroke="#16314a" stroke-width="2.6" fill="none" stroke-linecap="round">',
            '<path d="M194 160 C220 176 252 183 288 185"/>',
            '<path d="M196 173 C222 189 254 194 288 194"/>',
            '<path d="M202 186 C226 198 256 202 286 202"/>',
            '<path d="M206 150 C214 168 218 188 216 206"/>',
            '<path d="M250 154 C245 174 245 194 250 208"/>',
          '</g>',
        '</g>',
        // rasgada no bico (dedão) — desgaste clássico de tênis rodado: abertura
        // escura com beirada desfiada e fios soltos. Aparece no fim da vida útil.
        '<g class="w-toetear" opacity="0">',
          '<path d="M328 181 L342 184 L351 191 L345 197 L333 196 L326 189 Z" fill="#0b1016"/>',
          '<g stroke="#13283c" stroke-width="1" opacity="0.85"><path d="M330 184 L347 191"/><path d="M329 188 L344 194"/></g>',
          '<path d="M327 180 C334 181 343 184 351 190" fill="none" stroke="#5f8ab6" stroke-width="2.1" stroke-linecap="round"/>',
          '<path d="M326 190 C332 193 339 195 346 196" fill="none" stroke="#274b72" stroke-width="2.1" stroke-linecap="round"/>',
          '<g stroke="#a8c0db" stroke-width="0.9" stroke-linecap="round" opacity="0.85"><path d="M338 184 l3 -4"/><path d="M345 189 l4 -3"/><path d="M333 187 l-3 -3"/><path d="M341 195 l2 4"/></g>',
        '</g>',
        // collar / tongue / laces / accents
        '<path class="collar" d="M100 116 C108 96 130 92 150 100 C170 110 168 132 150 142 C128 148 106 138 100 116 Z" fill="#1c2935"/>',
        '<path class="collar2" d="M100 116 C108 96 130 92 150 100 C170 110 168 132 150 142" fill="none" stroke="#284f78" stroke-width="7" stroke-linecap="round"/>',
        '<path class="tongue" d="M150 112 C152 92 170 88 180 96 C184 110 182 126 178 140 C166 134 154 124 150 112 Z" fill="#f5f0e8"/>',
        '<g class="laces" stroke="#f3efe9" stroke-width="5" stroke-linecap="round"><path d="M170 120 l30 6"/><path d="M172 134 l32 7"/><path d="M176 150 l32 7"/><path d="M180 166 l30 7"/></g>',
        // cadêrço encardindo (sutil) — suja menos que o resto, mas suja
        '<g class="w-lacedirt" stroke="#6b5b3f" stroke-width="4.2" stroke-linecap="round" opacity="0" style="mix-blend-mode:multiply"><path d="M170 120 l30 6"/><path d="M172 134 l32 7"/><path d="M176 150 l32 7"/><path d="M180 166 l30 7"/></g>',
        '<g class="eyelets" fill="#f3efe9"><circle cx="170" cy="120" r="2.8"/><circle cx="200" cy="126" r="2.8"/><circle cx="172" cy="134" r="2.8"/><circle cx="204" cy="141" r="2.8"/><circle cx="176" cy="150" r="2.8"/><circle cx="208" cy="157" r="2.8"/><circle cx="180" cy="166" r="2.8"/><circle cx="210" cy="173" r="2.8"/></g>',
        '<path class="accent" d="M306 182 C254 192 206 188 176 176 C206 200 262 202 312 192 C312 188 310 185 306 182 Z" fill="#cf7a3e"/>',
        '<path class="heeltab" d="M74 126 C68 116 76 108 86 112 C86 120 82 126 74 126 Z" fill="#cf7a3e"/>',
        '</g>',
      '</g>',
    '</svg>'
  ].join('');

  // ------- helpers -------
  function clamp(t, a, b) { a = (a == null ? 0 : a); b = (b == null ? 1 : b); return t < a ? a : t > b ? b : t; }
  function seg(p, a, b) { return clamp((p - a) / (b - a), 0, 1); }
  function lerp(a, b, t) { return a + (b - a) * t; }

  // ------- API -------
  function mount(container) {
    if (!container) throw new Error('ShoeWear.mount: container ausente');
    container.innerHTML = SVG_MARKUP;
    var svg = container.querySelector('svg.shoe-wear');
    var q = function (s) { return svg.querySelector(s); };

    var L = {
      grime:    q('.w-grime'),
      dentF:    q('.w-dent'),
      creaseF:  q('.w-crease'),
      dirt:     q('.w-dirt'),
      dust:     q('.w-dust'),
      updent:   q('.w-updent'),
      upcrease: q('.w-upcrease'),
      updirt:   q('.w-updirt'),
      abrasion: q('.w-abrasion'),
      patina:   q('.w-patina'),
      toecr:    q('.w-toecr'),
      scuff:    q('.w-scuff'),
      instep:   q('.w-instep'),
      toetear:  q('.w-toetear'),
      lacedirt: q('.w-lacedirt')
    };
    var shoeGroup = q('.shoe');
    var soleWrap  = q('.sole-wrap');
    var upperWrap = q('.upper-wrap');
    var dispSole  = svg.querySelector('#sw-crumple feDisplacementMap');
    var dispUp    = svg.querySelector('#sw-crumple-up feDisplacementMap');
    // The displacement filters are referenced from CSS so they compose with the
    // saturate/brightness grade; the SVG `scale` (set per-progress) does the work.
    if (soleWrap)  soleWrap.style.filter  = 'url(#sw-crumple)';
    if (upperWrap) upperWrap.style.filter = 'url(#sw-crumple-up)';
    if (L.toetear) { L.toetear.style.transformBox = 'fill-box'; L.toetear.style.transformOrigin = 'center'; }
    var setO = function (el, o) { if (el) el.style.opacity = o; };

    // p de 0 (limpo) a 1 (rodado). Mapeamento de cada marca de desgaste:
    function setProgress(p) {
      p = clamp(p, 0, 1);
      setO(L.grime,    seg(p, 0.12, 0.85));         // espuma encardindo
      setO(L.dentF,    seg(p, 0.16, 0.72));         // amassados na espuma (amortecimento)
      setO(L.creaseF,  seg(p, 0.12, 0.62));         // vincos de compressão (amortecimento)
      setO(L.dirt,     seg(p, 0.18, 0.85) * 0.95);  // sujeira na base
      setO(L.dust,     seg(p, 0.10, 0.70));         // poeira no chão
      setO(L.updent,   seg(p, 0.24, 0.85));         // amassados no cabedal
      setO(L.upcrease, seg(p, 0.18, 0.80));         // vincos cruzando o upper
      setO(L.updirt,   seg(p, 0.20, 0.95));         // respingos de lama no azul
      setO(L.abrasion, seg(p, 0.34, 0.90));         // abrasão (azul desbotado)
      setO(L.patina,   seg(p, 0.08, 0.85) * 0.4);   // patina quente (overlay)
      setO(L.toecr,    seg(p, 0.26, 0.80) * 0.75);  // vincos de flexão no bico
      setO(L.scuff,    seg(p, 0.30, 0.85));         // scuff no bico
      setO(L.instep,   seg(p, 0.16, 0.85));         // amassado/vincos no peito do pé
      setO(L.lacedirt, seg(p, 0.22, 0.95) * 0.6);   // cadêrço encardindo (menos intenso)
      // rasgada no bico: surge no fim da vida útil e "abre" crescendo
      var tear = seg(p, 0.5, 0.95);
      setO(L.toetear,  tear);
      if (L.toetear) L.toetear.style.transform = 'scale(' + lerp(0.45, 1, tear).toFixed(3) + ')';
      // Amassamento da silhueta: a sola deforma de leve e o cabedal bem mais
      // forte — a silhueta inteira "murcha"/enruga conforme o tênis roda. Escalas
      // altas porque na galeria o tênis aparece pequeno (~70px).
      var crumple = seg(p, 0.10, 1);
      crumple = crumple * crumple * (3 - 2 * crumple);   // smoothstep p/ início suave
      if (dispSole) dispSole.setAttribute('scale', (crumple * 15).toFixed(2));
      if (dispUp)   dispUp.setAttribute('scale',  (crumple * 20).toFixed(2));
      // encardido geral + leve dessaturação ("cara de rodado")
      var warm = seg(p, 0.05, 1);
      if (shoeGroup) shoeGroup.style.filter = 'saturate(' + lerp(1, 0.86, warm) + ') brightness(' + lerp(1, 0.95, warm) + ')';
    }

    setProgress(0);
    return { svg: svg, setProgress: setProgress };
  }

  global.ShoeWear = { SVG_MARKUP: SVG_MARKUP, mount: mount };
})(typeof window !== 'undefined' ? window : this);
