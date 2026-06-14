/* gallery-app.jsx — três direções de UX para a galeria de corridas.
   Cada direção é renderizada dentro de um artboard tamanho de celular. */

// ──────────────────────────────────────────────────────────────
// Dados — provas marcantes, da mais recente para a mais antiga.
// ──────────────────────────────────────────────────────────────
const RACES = [
  { name: 'Maratona do Rio',                 dist: '42,2', type: 'Maratona', city: 'Rio de Janeiro', uf: 'RJ', d: '07', m: 'JUN', y: '2026', device: 'Garmin' },
  { name: 'Circuito Rio Antigo',             dist: '10,0', type: '10K',      city: 'Rio de Janeiro', uf: 'RJ', d: '15', m: 'MAR', y: '2026', device: 'Garmin' },
  { name: 'Meia de São Paulo',               dist: '21,1', type: 'Meia',     city: 'São Paulo',      uf: 'SP', d: '09', m: 'ABR', y: '2023', device: 'Garmin' },
  { name: 'Maratona Monumental de Brasília', dist: '42,2', type: 'Maratona', city: 'Brasília',       uf: 'DF', d: '10', m: 'OUT', y: '2021', device: 'Polar'  },
  { name: 'Meia Internacional de Brasília',  dist: '21,1', type: 'Meia',     city: 'Brasília',       uf: 'DF', d: '18', m: 'AGO', y: '2019', device: 'Polar'  },
  { name: 'Track&Field Run Series',          dist: '10,0', type: '10K',      city: 'Brasília',       uf: 'DF', d: '06', m: 'MAI', y: '2018', device: 'Polar'  },
];

// Tom de imagem (placeholder de foto) por cidade — duotone discreto.
const PHOTO = {
  'Rio de Janeiro': ['#1f4d6b', '#3f8fae'],
  'São Paulo':      ['#3a3a44', '#6f6f7e'],
  'Brasília':       ['#7a4a2a', '#c98a52'],
};

// ──────────────────────────────────────────────────────────────
// Marcas (SVG / wordmarks reutilizáveis)
// ──────────────────────────────────────────────────────────────
function Strava({ size = 16, color = '#FC4C02' }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill={color} aria-label="Strava">
      <path d="M11.4 2 5.4 13.9h3.55L11.4 9l2.45 4.9h3.55z" />
      <path d="M13.85 13.9 11.4 18.8 8.95 13.9H6.05L11.4 24l5.35-10.1z" opacity=".55" />
    </svg>
  );
}
function GarminMark({ color = '#0B7BBF', size = 13 }) {
  return (
    <span style={{ fontFamily: 'Archivo, sans-serif', fontWeight: 700, letterSpacing: '.07em', fontSize: size, color, lineHeight: 1, whiteSpace: 'nowrap' }}>
      GARMIN
    </span>
  );
}
function PolarMark({ color = '#111', dot = '#E2001A', size = 13 }) {
  return (
    <span style={{ fontFamily: 'Archivo, sans-serif', fontWeight: 800, fontStyle: 'italic', letterSpacing: '.01em', fontSize: size, color, lineHeight: 1 }}>
      P<span style={{ color: dot }}>O</span>LAR
    </span>
  );
}
function DeviceMark({ name, mono }) {
  if (name === 'Garmin') return <GarminMark color={mono ? 'currentColor' : '#0B7BBF'} />;
  return <PolarMark color={mono ? 'currentColor' : '#111'} dot={mono ? 'currentColor' : '#E2001A'} />;
}

const ArrowUpRight = ({ s = 10 }) => (
  <svg width={s} height={s} viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" style={{ flex: '0 0 auto' }}>
    <path d="M3.5 8.5 8.5 3.5M4.5 3.5h4v4" />
  </svg>
);

// Distância → cor de acento (codifica o tipo de prova)
const distColor = (t) => (t === 'Maratona' ? '#E4572E' : t === 'Meia' ? '#3A7CA5' : '#2A9D5C');

// Tempo dentro do ano → fração [0,1] (jan = 0, dez = 1) e chave cronológica.
const MONTHS = { JAN: 0, FEV: 1, MAR: 2, ABR: 3, MAI: 4, JUN: 5, JUL: 6, AGO: 7, SET: 8, OUT: 9, NOV: 10, DEZ: 11 };
const fracOfYear = (r) => (MONTHS[r.m] + (parseInt(r.d, 10) - 1) / 31) / 12;
const dateKey = (r) => parseInt(r.y, 10) * 400 + MONTHS[r.m] * 31 + parseInt(r.d, 10);
const clampN = (v, a, b) => Math.max(a, Math.min(b, v));

// ══════════════════════════════════════════════════════════════
// DIREÇÃO A — DIÁRIO (editorial / minimal, sem fotos)
// Três tratamentos de linha do tempo.
// ══════════════════════════════════════════════════════════════
const RAIL = 34;        // largura da coluna da linha
const RAILX = 16;       // x do eixo da linha dentro da coluna
const diarioWrap = { height: '100%', background: '#faf8f4', fontFamily: 'Archivo, sans-serif', color: '#1c1a17', display: 'flex', flexDirection: 'column', overflow: 'hidden' };

function DiarioHeader({ small }) {
  return (
    <header style={{ padding: small ? '38px 28px 20px' : '40px 30px 24px', flex: '0 0 auto' }}>
      <div style={{ fontSize: 11, letterSpacing: '.22em', textTransform: 'uppercase', color: '#a59b8c', fontWeight: 600 }}>Mauricio Mendelson</div>
      <h1 style={{ fontFamily: 'Spectral, serif', fontWeight: 500, fontSize: small ? 29 : 33, lineHeight: 1.06, margin: '12px 0 0', letterSpacing: '-.01em' }}>Corridas que<br />marcaram o caminho</h1>
    </header>
  );
}

function EditorialLinks({ device }) {
  const a = { display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 12, fontWeight: 600, color: '#1c1a17', textDecoration: 'none', borderBottom: '1px solid #d8cfc1', paddingBottom: 2 };
  return (
    <div style={{ display: 'flex', gap: 16, marginTop: 13 }}>
      <a href="#" style={a}><Strava size={13} /> Strava <ArrowUpRight /></a>
      <a href="#" style={a}><span style={{ color: '#6b6357' }}><DeviceMark name={device} mono /></span> <ArrowUpRight /></a>
    </div>
  );
}

function RaceMeta({ r }) {
  return (
    <React.Fragment>
      <div style={{ fontSize: 10, letterSpacing: '.16em', color: '#a59b8c', fontWeight: 600, marginBottom: 6 }}>{r.d} {r.m} {r.y}</div>
      <h2 style={{ fontFamily: 'Spectral, serif', fontWeight: 500, fontSize: 18, lineHeight: 1.2, margin: 0, letterSpacing: '-.005em' }}>{r.name}</h2>
      <div style={{ fontSize: 12.5, color: '#857a6b', marginTop: 5 }}>{r.dist} km · {r.city}</div>
    </React.Fragment>
  );
}

// ── A1 · Linha contínua, nós em anel ──────────────────────────
function GalleryDiarioLine() {
  const rows = RACES.slice(0, 4);
  return (
    <div style={diarioWrap}>
      <DiarioHeader />
      <div style={{ flex: 1, position: 'relative', padding: '6px 30px 30px', borderTop: '1px solid #ece6dc' }}>
        <div style={{ position: 'absolute', left: 30 + RAILX, top: 30, bottom: 40, width: 1.5, background: '#cbbda4' }} />
        {rows.map((r, i) => (
          <div key={i} style={{ display: 'flex', gap: 14, padding: '20px 0', borderBottom: i < rows.length - 1 ? '1px solid #ece6dc' : 'none' }}>
            <div style={{ flex: `0 0 ${RAIL}px`, position: 'relative' }}>
              <span style={{ position: 'absolute', left: RAILX - 5, top: 2, width: 10, height: 10, borderRadius: 5, background: '#faf8f4', border: '1.5px solid #1c1a17', boxSizing: 'border-box' }} />
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <RaceMeta r={r} />
              <EditorialLinks device={r.device} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── A2 · Estações por ano (capítulos) ─────────────────────────
function GalleryDiarioStations() {
  const rows = RACES.slice(0, 4);
  // agrupa por ano preservando ordem
  const groups = [];
  rows.forEach((r) => {
    const g = groups.find((x) => x.y === r.y);
    if (g) g.items.push(r); else groups.push({ y: r.y, items: [r] });
  });
  return (
    <div style={diarioWrap}>
      <DiarioHeader />
      <div style={{ flex: 1, position: 'relative', padding: '2px 30px 30px', borderTop: '1px solid #ece6dc' }}>
        <div style={{ position: 'absolute', left: 30 + RAILX, top: 22, bottom: 30, width: 1.5, background: '#cbbda4' }} />
        {groups.map((g, gi) => (
          <div key={gi}>
            <div style={{ display: 'flex', gap: 14, alignItems: 'center', padding: '18px 0 6px' }}>
              <div style={{ flex: `0 0 ${RAIL}px`, position: 'relative', height: 22 }}>
                <span style={{ position: 'absolute', left: RAILX - 4, top: 6, width: 9, height: 9, borderRadius: 5, background: '#1c1a17' }} />
              </div>
              <div style={{ fontFamily: 'Spectral, serif', fontSize: 22, color: '#1c1a17', lineHeight: 1, fontWeight: 500 }}>{g.y}</div>
            </div>
            {g.items.map((r, i) => (
              <div key={i} style={{ display: 'flex', gap: 14, padding: '10px 0 18px' }}>
                <div style={{ flex: `0 0 ${RAIL}px`, position: 'relative' }}>
                  <span style={{ position: 'absolute', left: RAILX - 3, top: 4, width: 7, height: 7, borderRadius: 4, background: '#faf8f4', border: '1.5px solid #b3a896', boxSizing: 'border-box' }} />
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontFamily: 'Spectral, serif', fontWeight: 500, fontSize: 17.5, lineHeight: 1.2, letterSpacing: '-.005em' }}>{r.name}</div>
                  <div style={{ fontSize: 12, color: '#857a6b', marginTop: 4 }}>{r.dist} km · {r.city} · {r.d} {r.m}</div>
                  <EditorialLinks device={r.device} />
                </div>
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

// ── A3 · Linha-percurso, marco sólido por tipo de prova ───────
function GalleryDiarioSolid() {
  const rows = RACES.slice(0, 4);
  return (
    <div style={diarioWrap}>
      <DiarioHeader />
      <div style={{ flex: 1, position: 'relative', padding: '6px 30px 30px', borderTop: '1px solid #ece6dc' }}>
        <div style={{ position: 'absolute', left: 30 + RAILX, top: 28, bottom: 38, width: 2, background: 'linear-gradient(#cdbfa8, #e6ddcd)' }} />
        {rows.map((r, i) => {
          const c = distColor(r.type);
          return (
            <div key={i} style={{ display: 'flex', gap: 14, padding: '20px 0', borderBottom: i < rows.length - 1 ? '1px solid #ece6dc' : 'none' }}>
              <div style={{ flex: `0 0 ${RAIL}px`, position: 'relative' }}>
                <span style={{ position: 'absolute', left: RAILX - 6, top: 1, width: 12, height: 12, borderRadius: 6, background: c, boxShadow: '0 0 0 4px #faf8f4' }} />
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, flexWrap: 'wrap' }}>
                  <span style={{ fontSize: 10, letterSpacing: '.14em', color: c, fontWeight: 700, textTransform: 'uppercase' }}>{r.type}</span>
                  <span style={{ fontSize: 10, letterSpacing: '.16em', color: '#a59b8c', fontWeight: 600 }}>{r.d} {r.m} {r.y}</span>
                </div>
                <h2 style={{ fontFamily: 'Spectral, serif', fontWeight: 500, fontSize: 18, lineHeight: 1.2, margin: '5px 0 0', letterSpacing: '-.005em' }}>{r.name}</h2>
                <div style={{ fontSize: 12.5, color: '#857a6b', marginTop: 5 }}>{r.dist} km · {r.city}</div>
                <EditorialLinks device={r.device} />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════
// DIREÇÃO FINAL — A2 ESCURO, com posição proporcional ao mês
// Capítulos por ano (cronológico, antigo → recente). Dentro de cada
// ano, a prova fica a uma altura proporcional ao mês em que ocorreu.
// ══════════════════════════════════════════════════════════════
function EditorialLinksDark({ device }) {
  const a = { display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 12, fontWeight: 600, color: '#dad6cd', textDecoration: 'none', borderBottom: '1px solid #363c47', paddingBottom: 2 };
  return (
    <div style={{ display: 'flex', gap: 16, marginTop: 12 }}>
      <a href="#" style={a}><Strava size={13} /> Strava <ArrowUpRight /></a>
      <a href="#" style={a}><span style={{ color: '#aeb4c0' }}><DeviceMark name={device} mono /></span> <ArrowUpRight /></a>
    </div>
  );
}

function GalleryAnoDark() {
  const PPY = 350;            // altura de um ano inteiro (jan → dez)
  const CARD = 84;            // altura aproximada de um card de prova
  const RX = RAILX;           // eixo da linha dentro de cada banda
  const PADX = 28;            // padding horizontal do container
  const LETTERS = ['J', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S', 'O', 'N', 'D'];
  const QLABEL = { 0: 'JAN', 3: 'ABR', 6: 'JUL', 9: 'OUT' };

  const asc = [...RACES].sort((a, b) => dateKey(a) - dateKey(b));
  const all = [];
  asc.forEach((r) => { const g = all.find((x) => x.y === r.y); if (g) g.items.push(r); else all.push({ y: r.y, items: [r] }); });
  const groups = all.slice(-3); // três capítulos mais recentes

  let prevOverflow = 0;
  const blocks = groups.map((g, gi) => {
    const items = g.items.map((r) => ({ r, f: fracOfYear(r) }));
    const lastF = Math.max(...items.map((i) => i.f));
    const marginTop = gi === 0 ? 2 : Math.max(16, prevOverflow);
    prevOverflow = Math.max(0, lastF * PPY + CARD - PPY) + 16;
    return { y: g.y, items, marginTop };
  });

  return (
    <div style={{ height: '100%', background: '#0f1115', fontFamily: 'Archivo, sans-serif', color: '#fff', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      <header style={{ padding: '38px 28px 18px', flex: '0 0 auto' }}>
        <div style={{ fontSize: 10.5, letterSpacing: '.24em', textTransform: 'uppercase', color: '#6a7080', fontWeight: 700 }}>Mauricio Mendelson</div>
        <h1 style={{ fontFamily: 'Spectral, serif', fontWeight: 500, fontSize: 30, lineHeight: 1.05, margin: '10px 0 0', letterSpacing: '-.01em', color: '#f3efe7' }}>Corridas que<br />marcaram o caminho</h1>
      </header>
      <div style={{ flex: 1, position: 'relative', padding: `12px ${PADX}px 26px`, borderTop: '1px solid #20242c' }}>
        <div style={{ position: 'absolute', left: PADX + RX, top: 8, bottom: 16, width: 1.5, background: 'linear-gradient(#2c323d, #191c22)' }} />
        {blocks.map((b) => (
          <div key={b.y} style={{ position: 'relative', height: PPY, marginTop: b.marginTop }}>
            {/* régua de meses */}
            {LETTERS.map((L, mi) => {
              const top = (mi / 12) * PPY;
              const lab = QLABEL[mi];
              return (
                <div key={mi} style={{ position: 'absolute', top, left: 0, width: RAIL, height: 0 }}>
                  {mi !== 0 && <span style={{ position: 'absolute', left: RX - 3.5, top: -0.5, width: 7, height: 1, background: '#2b313b' }} />}
                  {lab
                    ? <span style={{ position: 'absolute', left: 0, top: -6, width: RX - 5, textAlign: 'right', fontSize: 8.5, letterSpacing: '.08em', color: '#565c68', fontWeight: 700 }}>{lab}</span>
                    : <span style={{ position: 'absolute', left: 0, top: -6, width: RX - 5, textAlign: 'right', fontSize: 8, color: '#363c46', fontWeight: 700 }}>{L}</span>}
                </div>
              );
            })}
            {/* marcador do ano (jan) */}
            <div style={{ position: 'absolute', top: -6, left: 0, right: 0, display: 'flex', gap: 14, alignItems: 'center' }}>
              <div style={{ flex: `0 0 ${RAIL}px`, position: 'relative', height: 20 }}>
                <span style={{ position: 'absolute', left: RX - 5, top: 4, width: 11, height: 11, borderRadius: 6, background: '#f3efe7', boxShadow: '0 0 0 4px #0f1115' }} />
              </div>
              <div style={{ fontFamily: 'Spectral, serif', fontSize: 23, color: '#f3efe7', lineHeight: 1, fontWeight: 500 }}>{b.y}</div>
            </div>
            {/* provas, posicionadas pelo mês */}
            {b.items.map(({ r, f }, i) => {
              const c = distColor(r.type);
              return (
                <div key={i} style={{ position: 'absolute', top: f * PPY - 6, left: 0, right: 0, display: 'flex', gap: 14 }}>
                  <div style={{ flex: `0 0 ${RAIL}px`, position: 'relative' }}>
                    <span style={{ position: 'absolute', left: RX - 4, top: 3, width: 9, height: 9, borderRadius: 5, background: c, boxShadow: '0 0 0 3.5px #0f1115' }} />
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
                      <span style={{ fontSize: 10, letterSpacing: '.16em', color: c, fontWeight: 700, textTransform: 'uppercase' }}>{r.d} {r.m}</span>
                      <span style={{ fontSize: 10, letterSpacing: '.14em', color: '#5e6472', fontWeight: 600, textTransform: 'uppercase' }}>{r.type} · {r.dist} km</span>
                    </div>
                    <h2 style={{ fontFamily: 'Spectral, serif', fontWeight: 500, fontSize: 18, lineHeight: 1.2, margin: '4px 0 0', letterSpacing: '-.005em', color: '#f3efe7' }}>{r.name}</h2>
                    <div style={{ fontSize: 12.5, color: '#8b91a0', marginTop: 3 }}>{r.city} · {r.uf}</div>
                    <EditorialLinksDark device={r.device} />
                  </div>
                </div>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════
// DIREÇÃO B — PÓDIO (esportivo / energético, escuro, sem fotos)
// ══════════════════════════════════════════════════════════════
function GalleryPodio() {
  const wrap = { height: '100%', background: '#0f1115', fontFamily: 'Archivo, sans-serif', color: '#fff', display: 'flex', flexDirection: 'column', overflow: 'hidden' };
  return (
    <div style={wrap}>
      <header style={{ padding: '38px 24px 22px' }}>
        <div style={{ fontSize: 10.5, letterSpacing: '.24em', textTransform: 'uppercase', color: '#6a7080', fontWeight: 700 }}>Mauricio Mendelson</div>
        <h1 style={{ fontFamily: 'Saira Condensed, sans-serif', fontWeight: 700, fontSize: 40, lineHeight: .92, margin: '8px 0 0', textTransform: 'uppercase', letterSpacing: '.01em' }}>Minhas<br />corridas</h1>
      </header>
      <div style={{ flex: 1, padding: '4px 24px 24px', display: 'flex', flexDirection: 'column', gap: 14 }}>
        {RACES.slice(0, 3).map((r, i) => {
          const c = distColor(r.type);
          return (
            <div key={i} style={{ background: '#181b21', borderRadius: 16, padding: '18px 18px 16px', border: '1px solid #23272f', position: 'relative', overflow: 'hidden' }}>
              <div style={{ position: 'absolute', top: 0, left: 0, width: 4, height: '100%', background: c }} />
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: 14 }}>
                <div style={{ flex: '0 0 auto' }}>
                  <div style={{ display: 'flex', alignItems: 'baseline', gap: 4 }}>
                    <span style={{ fontFamily: 'Saira Condensed, sans-serif', fontWeight: 700, fontSize: 46, lineHeight: .8, color: '#fff' }}>{r.dist}</span>
                    <span style={{ fontFamily: 'Saira Condensed, sans-serif', fontWeight: 600, fontSize: 16, color: c }}>KM</span>
                  </div>
                  <div style={{ fontSize: 9.5, letterSpacing: '.16em', color: c, fontWeight: 700, marginTop: 4, textTransform: 'uppercase' }}>{r.type}</div>
                </div>
                <div style={{ flex: 1, minWidth: 0, paddingTop: 2 }}>
                  <h2 style={{ fontWeight: 700, fontSize: 16, lineHeight: 1.15, margin: 0 }}>{r.name}</h2>
                  <div style={{ fontSize: 11.5, color: '#8b91a0', marginTop: 5, fontWeight: 500 }}>{r.city} · {r.uf}</div>
                  <div style={{ fontSize: 11.5, color: '#5e6472', marginTop: 1, fontWeight: 600, letterSpacing: '.03em' }}>{r.d} {r.m} {r.y}</div>
                </div>
              </div>
              <div style={{ display: 'flex', gap: 9, marginTop: 16 }}>
                <a href="#" style={{ flex: 1, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 7, background: '#FC4C02', color: '#fff', fontWeight: 700, fontSize: 12.5, textDecoration: 'none', borderRadius: 9, padding: '10px 0' }}>
                  <Strava size={15} color="#fff" /> Strava
                </a>
                <a href="#" style={{ flex: 1, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 7, background: 'transparent', border: '1.5px solid #2f3540', color: '#cfd4de', fontWeight: 700, fontSize: 12.5, textDecoration: 'none', borderRadius: 9, padding: '8.5px 0' }}>
                  <DeviceMark name={r.device} mono />
                </a>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════
// DIREÇÃO C — MEMÓRIA (imersivo, com fotos)
// ══════════════════════════════════════════════════════════════
function PhotoFill({ city }) {
  const [a, b] = PHOTO[city] || ['#444', '#777'];
  return (
    <div style={{ position: 'absolute', inset: 0, background: `linear-gradient(150deg, ${a}, ${b})` }}>
      <div style={{ position: 'absolute', inset: 0, opacity: .14, backgroundImage: 'repeating-linear-gradient(45deg, #fff 0 1px, transparent 1px 9px)' }} />
      <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: 7, color: 'rgba(255,255,255,.5)' }}>
        <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.4"><rect x="3" y="5" width="18" height="14" rx="2" /><circle cx="12" cy="12" r="3.2" /><path d="M8 5l1.5-2h5L16 5" /></svg>
        <span style={{ fontSize: 10, letterSpacing: '.12em', textTransform: 'uppercase', fontWeight: 600 }}>Foto da prova</span>
      </div>
    </div>
  );
}
function GalleryMemoria() {
  const wrap = { height: '100%', background: '#101010', fontFamily: 'Archivo, sans-serif', color: '#fff', display: 'flex', flexDirection: 'column', overflow: 'hidden' };
  const glass = { display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 6, background: 'rgba(255,255,255,.16)', backdropFilter: 'blur(8px)', WebkitBackdropFilter: 'blur(8px)', border: '1px solid rgba(255,255,255,.25)', color: '#fff', fontWeight: 700, fontSize: 12, textDecoration: 'none', borderRadius: 999, padding: '8px 0', flex: 1 };
  return (
    <div style={wrap}>
      <header style={{ padding: '36px 22px 18px', flex: '0 0 auto' }}>
        <div style={{ fontSize: 10.5, letterSpacing: '.24em', textTransform: 'uppercase', color: '#7c7c7c', fontWeight: 700 }}>Mauricio Mendelson</div>
        <h1 style={{ fontWeight: 800, fontSize: 28, lineHeight: 1, margin: '8px 0 0', letterSpacing: '-.02em' }}>Minhas corridas</h1>
      </header>
      <div style={{ flex: 1, padding: '4px 18px 18px', display: 'flex', flexDirection: 'column', gap: 16, overflow: 'hidden' }}>
        {RACES.slice(0, 2).map((r, i) => {
          const c = distColor(r.type);
          return (
            <div key={i} style={{ position: 'relative', borderRadius: 18, overflow: 'hidden', flex: 1, minHeight: 0, boxShadow: '0 8px 30px rgba(0,0,0,.4)' }}>
              <PhotoFill city={r.city} />
              <div style={{ position: 'absolute', inset: 0, background: 'linear-gradient(to top, rgba(0,0,0,.82) 14%, rgba(0,0,0,.15) 52%, rgba(0,0,0,.25))' }} />
              <div style={{ position: 'absolute', top: 14, left: 14, display: 'inline-flex', alignItems: 'center', gap: 7, background: 'rgba(0,0,0,.4)', backdropFilter: 'blur(6px)', WebkitBackdropFilter: 'blur(6px)', borderRadius: 999, padding: '5px 11px 5px 9px' }}>
                <span style={{ width: 6, height: 6, borderRadius: 3, background: c }} />
                <span style={{ fontSize: 10.5, fontWeight: 700, letterSpacing: '.04em' }}>{r.dist} KM · {r.type.toUpperCase()}</span>
              </div>
              <div style={{ position: 'absolute', left: 16, right: 16, bottom: 14 }}>
                <div style={{ fontSize: 10.5, letterSpacing: '.12em', color: 'rgba(255,255,255,.75)', fontWeight: 600, marginBottom: 4 }}>{r.d} {r.m} {r.y} · {r.city.toUpperCase()}</div>
                <h2 style={{ fontWeight: 800, fontSize: 21, lineHeight: 1.05, margin: '0 0 13px', letterSpacing: '-.01em' }}>{r.name}</h2>
                <div style={{ display: 'flex', gap: 9 }}>
                  <a href="#" style={glass}><Strava size={14} color="#fff" /> Strava</a>
                  <a href="#" style={glass}><DeviceMark name={r.device} mono /></a>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════
// Canvas
// ══════════════════════════════════════════════════════════════
const PW = 384, PH = 812;
function App() {
  return (
    <DesignCanvas>
      <DCSection id="final" title="Direção final · Diário escuro — linha do tempo proporcional" subtitle="Capítulos por ano (antigo → recente). A altura de cada prova reflete o mês em que ocorreu.">
        <DCArtboard id="anodark" label="A2 escuro — régua de meses + posição proporcional" width={PW} height={1240}>
          <GalleryAnoDark />
        </DCArtboard>
        <DCPostIt top={-4} left={PW + 48 + 24} rotate={2} width={224}>
          Cada ano é uma régua jan→dez. O ponto da prova fica exatamente no mês: o "Circuito" (mar) no alto de 2026, a "Maratona do Rio" (jun) mais abaixo, e a de 2021 (out) quase no fim do ano.
        </DCPostIt>
      </DCSection>
      <DCSection id="ref" title="Referência" subtitle="A2 claro (origem) e a direção B (paleta usada aqui).">
        <DCArtboard id="a2light" label="A2 claro — origem" width={PW} height={PH}>
          <GalleryDiarioStations />
        </DCArtboard>
        <DCArtboard id="podio" label="B · Pódio — paleta escura" width={PW} height={PH}>
          <GalleryPodio />
        </DCArtboard>
      </DCSection>
    </DesignCanvas>
  );
}
ReactDOM.createRoot(document.getElementById('root')).render(<App />);
