/*!
 * shoe-wear.js — Tênis de corrida que envelhece conforme um progresso 0→1.
 * Sem dependências. Framework-agnostic.
 *
 * v2 — Redesign do modelo: geometria de tênis de corrida de verdade.
 *   • Solado "rocker": bisel no calcanhar + toe spring (bico levanta do chão)
 *   • Entressola de espuma alta, com drop calcanhar→bico visível
 *   • Borracha do solado com travas (lugs) seguindo a curvatura
 *   • Cabedal baixo tipo mesh, colarinho acolchoado, aba no calcanhar
 *
 * USO (inalterado):
 *   const shoe = ShoeWear.mount(document.getElementById('shoe'));
 *   shoe.setProgress(0.0);   // 0 = zero km (limpo)   1 = veterano (rodado)
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
        '<filter id="sw-crumple" x="-30%" y="-30%" width="160%" height="160%" color-interpolation-filters="sRGB"><feTurbulence type="fractalNoise" baseFrequency="0.009 0.022" numOctaves="2" seed="11" result="n"/><feDisplacementMap in="SourceGraphic" in2="n" scale="0" xChannelSelector="R" yChannelSelector="G"/></filter>',
        '<filter id="sw-crumple-up" x="-35%" y="-35%" width="170%" height="170%" color-interpolation-filters="sRGB"><feTurbulence type="fractalNoise" baseFrequency="0.015 0.04" numOctaves="2" seed="4" result="n"/><feDisplacementMap in="SourceGraphic" in2="n" scale="0" xChannelSelector="R" yChannelSelector="G"/></filter>',
      '</defs>',
      '<g class="w-dust" opacity="0"><ellipse cx="180" cy="261" rx="100" ry="8" fill="#a8946e" opacity="0.55"/><ellipse cx="320" cy="254" rx="70" ry="7" fill="#a8946e" opacity="0.5"/></g>',
      '<g class="shoe">',
        '<g class="sole-wrap">',
        // ---- ENTRESSOLA (espuma): rocker — bisel no calcanhar, toe spring no bico ----
        '<path class="midsole" d="M70 208 C62 218 62 232 72 242 C80 250 96 255 116 256 C170 259 240 258 282 255 C316 252 340 244 354 233 C363 227 365 218 355 215 C330 218 300 219 268 219 C224 219 176 214 140 209 C112 204 86 204 70 208 Z" fill="#eee8de"/>',
        // crista superior clara da espuma
        '<path d="M76 212 C150 219 260 223 352 217 C354 220 352 223 347 224 C280 229 160 226 90 219 C82 218 77 215 76 212 Z" fill="#f5f0e8"/>',
        // linha de segunda densidade
        '<path d="M74 236 C86 248 108 253 144 255 C196 258 246 257 284 251 C310 247 328 241 344 232 L346 236 C330 245 310 251 284 255 C246 261 194 262 142 259 C106 257 82 248 74 236 Z" fill="#d7cdbe"/>',
        // desgaste da espuma
        '<path class="w-grime" d="M74 230 C160 246 280 244 350 226 C354 234 350 242 340 246 C295 254 160 258 100 253 C82 249 68 240 74 230 Z" fill="url(#sw-grimeG)" opacity="0" style="mix-blend-mode:multiply"/>',
        '<g class="w-dent" opacity="0"><ellipse cx="110" cy="230" rx="24" ry="12" fill="url(#sw-dentG)"/><ellipse cx="200" cy="237" rx="30" ry="11" fill="url(#sw-dentG)"/><ellipse cx="296" cy="229" rx="22" ry="11" fill="url(#sw-dentG)"/><ellipse cx="152" cy="234" rx="18" ry="9" fill="url(#sw-dentG)"/></g>',
        '<g class="w-crease" stroke="#8a795c" stroke-width="2.4" fill="none" stroke-linecap="round" opacity="0">',
          '<path d="M84 220 C100 228 118 228 134 222"/><path d="M82 234 C100 242 120 242 136 236"/>',
          '<path d="M258 223 C282 230 308 227 328 218"/><path d="M256 237 C282 243 306 239 326 230"/>',
          '<path d="M164 229 C190 236 218 235 242 228"/>',
        '</g>',
        // costura da entressola
        '<path class="midline" d="M78 217 C170 226 290 226 352 219" fill="none" stroke="#b8552e" stroke-width="2.5" stroke-linecap="round" opacity="0.5"/>',
        // ---- BORRACHA do solado com travas, seguindo a curvatura (rocker) ----
        '<path class="outsole" d="M86 244 C98 251 122 254 158 255 C204 256 244 255 272 250 C300 246 322 240 340 230" fill="none" stroke="#2b2724" stroke-width="6" stroke-linecap="butt" stroke-dasharray="20 6"/>',
        '<g class="w-dirt" fill="#5f4a2c" opacity="0"><circle cx="120" cy="250" r="3.4"/><circle cx="152" cy="253" r="2.6"/><circle cx="188" cy="254" r="3.6"/><circle cx="226" cy="253" r="2.4"/><circle cx="262" cy="249" r="3"/><circle cx="298" cy="243" r="2.8"/><circle cx="330" cy="232" r="2.4"/><circle cx="98" cy="244" r="2.2"/></g>',
        '</g>',
        '<g class="upper-wrap" transform="translate(0,4)">',
        // ---- CABEDAL: perfil baixo, colarinho acolchoado, bico afilado ----
        '<path class="upper" d="M70 202 C62 178 63 146 78 128 C84 119 93 116 100 121 C108 104 128 99 145 107 C152 117 155 126 158 135 C210 142 264 154 306 169 C330 178 348 188 354 198 C358 206 354 213 344 214 C306 216 230 217 160 208 C120 202 88 200 70 202 Z" fill="#3b6ea3"/>',
        // sombra do vamp
        '<path d="M158 135 C210 142 264 154 306 169 C304 182 298 197 289 209 C226 211 178 207 158 203 C155 182 156 156 158 135 Z" fill="#284f78" opacity="0.22"/>',
        // contraforte do calcanhar
        '<path class="heel" d="M70 202 C62 178 63 146 78 128 C84 119 93 116 100 121 C95 142 93 172 99 197 C90 202 78 203 70 202 Z" fill="#284f78"/>',
        // painel do meio
        '<path d="M158 130 C176 134 198 139 218 145 C214 165 209 188 205 202 C190 200 175 196 164 192 C159 172 156 150 158 130 Z" fill="#284f78" opacity="0.4"/>',
        // bico reforçado
        '<path class="toecap" d="M310 172 C332 181 348 190 354 198 C358 206 354 213 344 214 C326 215 311 215 301 213 C298 199 302 184 310 172 Z" fill="#284f78"/>',
        // textura de mesh (sutil)
        '<g stroke="#284f78" stroke-width="1.2" fill="none" opacity="0.25"><path d="M202 140 C198 158 196 180 198 204"/><path d="M228 145 C224 162 223 182 225 205"/><path d="M254 150 C251 166 250 184 252 206"/><path d="M280 157 C278 171 278 187 280 208"/></g>',
        // desgaste do cabedal
        '<g class="w-updent" opacity="0"><ellipse cx="220" cy="176" rx="34" ry="20" fill="url(#sw-updentG)"/><ellipse cx="128" cy="164" rx="20" ry="22" fill="url(#sw-updentG)"/><ellipse cx="298" cy="188" rx="20" ry="15" fill="url(#sw-updentG)"/></g>',
        '<g class="w-upcrease" stroke="#1d3f5e" stroke-width="2" fill="none" stroke-linecap="round" opacity="0">',
          '<path d="M150 148 C190 158 240 166 292 176"/><path d="M116 136 C100 156 96 178 104 198"/>',
          '<path d="M250 156 C246 172 244 190 248 206"/><path d="M180 198 C176 182 178 168 186 154"/><path d="M320 176 C328 186 332 198 330 208"/>',
        '</g>',
        '<path class="w-patina" d="M70 202 C62 178 63 146 78 128 C84 119 93 116 100 121 C108 104 128 99 145 107 C152 117 155 126 158 135 C210 142 264 154 306 169 C330 178 348 188 354 198 C358 206 354 213 344 214 C306 216 230 217 160 208 C120 202 88 200 70 202 Z" fill="url(#sw-patG)" opacity="0" style="mix-blend-mode:overlay"/>',
        '<g class="w-abrasion" opacity="0"><ellipse cx="82" cy="155" rx="12" ry="20" fill="url(#sw-abrG)"/><ellipse cx="346" cy="198" rx="16" ry="12" fill="url(#sw-abrG)"/><ellipse cx="96" cy="127" rx="9" ry="8" fill="url(#sw-abrG)"/></g>',
        '<g class="w-updirt" fill="#5a4126" opacity="0"><circle cx="112" cy="192" r="2.6"/><circle cx="140" cy="198" r="2"/><circle cx="175" cy="194" r="3"/><circle cx="215" cy="200" r="2.4"/><circle cx="250" cy="196" r="2.8"/><circle cx="285" cy="196" r="2.2"/><circle cx="318" cy="198" r="2.6"/><circle cx="96" cy="168" r="1.8"/><circle cx="200" cy="172" r="1.8"/><circle cx="270" cy="180" r="2"/></g>',
        '<g class="w-toecr" stroke="#16314a" stroke-width="1.8" fill="none" stroke-linecap="round" opacity="0"><path d="M302 174 C308 186 310 196 308 206"/><path d="M316 178 C322 188 324 198 322 208"/><path d="M330 186 C336 194 338 202 336 209"/></g>',
        '<path class="w-scuff" d="M330 194 C344 198 352 203 355 208 C346 213 333 211 325 205 C325 199 327 196 330 194 Z" fill="#6e5236" opacity="0"/>',
        // peito do pé (instep): compressão + vincos profundos onde o pé flexiona
        '<g class="w-instep" opacity="0">',
          '<ellipse cx="234" cy="176" rx="48" ry="22" fill="url(#sw-updentG)"/>',
          '<g stroke="#16314a" stroke-width="2.6" fill="none" stroke-linecap="round">',
            '<path d="M194 158 C220 174 252 181 288 183"/>',
            '<path d="M196 171 C222 187 254 192 288 192"/>',
            '<path d="M202 184 C226 196 256 200 286 200"/>',
            '<path d="M206 148 C214 166 218 186 216 204"/>',
            '<path d="M250 152 C245 172 245 192 250 206"/>',
          '</g>',
        '</g>',
        // rasgada no bico (dedão) — abertura escura com beirada desfiada
        '<g class="w-toetear" opacity="0">',
          '<path d="M324 187 L338 190 L347 197 L341 203 L329 202 L322 195 Z" fill="#0b1016"/>',
          '<g stroke="#13283c" stroke-width="1" opacity="0.85"><path d="M326 190 L343 197"/><path d="M325 194 L340 200"/></g>',
          '<path d="M323 186 C330 187 339 190 347 196" fill="none" stroke="#5f8ab6" stroke-width="2.1" stroke-linecap="round"/>',
          '<path d="M322 196 C328 199 335 201 342 202" fill="none" stroke="#274b72" stroke-width="2.1" stroke-linecap="round"/>',
          '<g stroke="#a8c0db" stroke-width="0.9" stroke-linecap="round" opacity="0.85"><path d="M334 190 l3 -4"/><path d="M341 195 l4 -3"/><path d="M329 193 l-3 -3"/><path d="M337 201 l2 4"/></g>',
        '</g>',
        // colarinho / língua / cadarço / detalhes
        '<path class="collar" d="M100 121 C108 104 128 99 145 107 C158 116 156 132 142 141 C122 146 105 139 100 121 Z" fill="#1c2935"/>',
        '<path class="collar2" d="M100 121 C108 104 128 99 145 107 C158 116 156 132 142 141" fill="none" stroke="#284f78" stroke-width="7" stroke-linecap="round"/>',
        '<path class="tongue" d="M144 116 C146 100 161 96 170 103 C174 116 172 130 168 143 C157 137 148 128 144 116 Z" fill="#f5f0e8"/>',
        '<g class="laces" stroke="#f3efe9" stroke-width="5" stroke-linecap="round"><path d="M160 124 l28 6"/><path d="M164 138 l30 7"/><path d="M168 152 l30 7"/><path d="M173 166 l28 7"/></g>',
        '<g class="w-lacedirt" stroke="#6b5b3f" stroke-width="4.2" stroke-linecap="round" opacity="0" style="mix-blend-mode:multiply"><path d="M160 124 l28 6"/><path d="M164 138 l30 7"/><path d="M168 152 l30 7"/><path d="M173 166 l28 7"/></g>',
        '<g class="eyelets" fill="#f3efe9"><circle cx="160" cy="124" r="2.8"/><circle cx="188" cy="130" r="2.8"/><circle cx="164" cy="138" r="2.8"/><circle cx="194" cy="145" r="2.8"/><circle cx="168" cy="152" r="2.8"/><circle cx="198" cy="159" r="2.8"/><circle cx="173" cy="166" r="2.8"/><circle cx="201" cy="173" r="2.8"/></g>',
        // faixa de velocidade (acento laranja no meio do pé)
        '<path class="accent" d="M172 182 C220 194 274 198 324 192 L326 198 C276 206 218 202 170 189 Z" fill="#cf7a3e"/>',
        // aba do calcanhar
        '<path class="heeltab" d="M75 130 C68 122 73 113 82 116 C83 124 80 130 75 130 Z" fill="#cf7a3e"/>',
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
      setO(L.lacedirt, seg(p, 0.22, 0.95) * 0.6);   // cadarço encardindo (menos intenso)
      var tear = seg(p, 0.5, 0.95);
      setO(L.toetear,  tear);
      if (L.toetear) L.toetear.style.transform = 'scale(' + lerp(0.45, 1, tear).toFixed(3) + ')';
      var crumple = seg(p, 0.10, 1);
      crumple = crumple * crumple * (3 - 2 * crumple);   // smoothstep p/ início suave
      if (dispSole) dispSole.setAttribute('scale', (crumple * 15).toFixed(2));
      if (dispUp)   dispUp.setAttribute('scale',  (crumple * 20).toFixed(2));
      var warm = seg(p, 0.05, 1);
      if (shoeGroup) shoeGroup.style.filter = 'saturate(' + lerp(1, 0.86, warm) + ') brightness(' + lerp(1, 0.95, warm) + ')';
    }

    setProgress(0);
    return { svg: svg, setProgress: setProgress };
  }

  global.ShoeWear = { SVG_MARKUP: SVG_MARKUP, mount: mount };
})(typeof window !== 'undefined' ? window : this);
