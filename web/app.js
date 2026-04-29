'use strict';

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------
let allCorridas = [];
let filteredCorridas = [];

const state = {
  distMode: 'select',  // 'select' | 'interval'
  activePills: new Set(),
  distMin: null,
  distMax: null,
  periodo: 'today',
  dateFrom: null,
  dateTo: null,
  estado: 'todos',
  searchQuery: '',
};

// ---------------------------------------------------------------------------
// DOM refs
// ---------------------------------------------------------------------------
const $ = id => document.getElementById(id);

const cardsList = $('cardsList');
const emptyState = $('emptyState');
const resultCount = $('resultCount');
const btnClear = $('btnClear');
const btnClearEmpty = $('btnClearEmpty');
const btnRefresh = $('btnRefresh');
const estadoSelect = $('estadoSelect');
const periodoSelect = $('periodoSelect');
const customDateRow = $('customDateRow');
const dateFrom = $('dateFrom');
const dateTo = $('dateTo');
const pillsContainer = $('pillsContainer');
const intervalContainer = $('intervalContainer');
const modeSelect = $('modeSelect');
const modeInterval = $('modeInterval');
const distMin = $('distMin');
const distMax = $('distMax');
const cardTemplate = $('cardTemplate');
const searchInput = $('searchInput');

// ---------------------------------------------------------------------------
// Persistence (localStorage)
// ---------------------------------------------------------------------------
const STORAGE_KEY = 'corridas_filters';

function saveFilters() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({
      activePills: [...state.activePills],
      distMode: state.distMode,
      distMin: state.distMin,
      distMax: state.distMax,
      estado: state.estado,
    }));
  } catch (e) { /* ignore */ }
}

function loadFilters() {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null');
    if (!saved) return;
    state.activePills = new Set(saved.activePills || []);
    state.distMode = saved.distMode || 'select';
    state.distMin = saved.distMin;
    state.distMax = saved.distMax;
    state.estado = saved.estado || 'todos';
  } catch (e) { /* ignore */ }
  // periodo always resets to 'today' (not persisted)
  state.periodo = 'today';
}

// ---------------------------------------------------------------------------
// Data fetch
// ---------------------------------------------------------------------------
async function fetchData() {
  btnRefresh.classList.add('spinning');
  try {
    const resp = await fetch('./corridas.json?t=' + Date.now());
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const json = await resp.json();
    allCorridas = json.corridas || [];
    populateEstadoFilter();
    applyFilters();
  } catch (e) {
    resultCount.textContent = 'Erro ao carregar dados.';
    console.error(e);
  } finally {
    btnRefresh.classList.remove('spinning');
  }
}

// ---------------------------------------------------------------------------
// Estado filter population
// ---------------------------------------------------------------------------
function populateEstadoFilter() {
  const estados = [...new Set(allCorridas.map(c => c.estado).filter(Boolean))].sort();
  // Remove existing dynamic options (keep Todos + INT)
  while (estadoSelect.options.length > 2) estadoSelect.remove(2);
  for (const uf of estados) {
    if (uf === 'INT') continue;
    const opt = document.createElement('option');
    opt.value = uf;
    opt.textContent = uf;
    estadoSelect.appendChild(opt);
  }
  estadoSelect.value = state.estado;
}

// ---------------------------------------------------------------------------
// Filtering
// ---------------------------------------------------------------------------
function applyFilters() {
  const today = todayStr();

  filteredCorridas = allCorridas.filter(c => {
    if (!matchesPeriodo(c, today)) return false;
    if (!matchesEstado(c)) return false;
    if (!matchesDistancia(c)) return false;
    if (!matchesSearch(c)) return false;
    return true;
  });

  updateClearButton();
  renderCards();
  updateCount();
}

function matchesPeriodo(c, today) {
  const d = c.data_evento;
  if (!d) return false;  // never show events without a date
  switch (state.periodo) {
    case 'today':   return d >= today;
    case '30':      return d >= today && d <= addDays(today, 30);
    case '90':      return d >= today && d <= addDays(today, 90);
    case '180':     return d >= today && d <= addDays(today, 180);
    case 'all':     return true;
    case 'custom': {
      const from = state.dateFrom;
      const to = state.dateTo;
      if (from && d < from) return false;
      if (to && d > to) return false;
      return true;
    }
    default: return true;
  }
}

function matchesEstado(c) {
  if (state.estado === 'todos') return true;
  if (state.estado === 'INT') return c.estado === 'INT';
  return c.estado === state.estado;
}

function matchesDistancia(c) {
  const kms = (c.distancias || []).map(d => typeof d.km === 'number' ? d.km : null).filter(k => k !== null);
  const hasOther = (c.distancias || []).some(d => typeof d.km === 'string');

  if (state.distMode === 'select') {
    if (state.activePills.size === 0) return true;
    for (const pill of state.activePills) {
      if (pill === 'outros') {
        if (hasOther) return true;
        if (kms.some(k => k !== 5 && k !== 10 && k !== 21 && k !== 21.097 && k !== 42 && k !== 42.195)) return true;
      } else {
        const target = parseFloat(pill);
        if (kms.some(k => Math.abs(k - target) < 0.5)) return true;
        // 42K pill also matches 42.195
        if (target === 42 && kms.some(k => Math.abs(k - 42.195) < 0.5)) return true;
        // 21K pill also matches 21.097
        if (target === 21 && kms.some(k => Math.abs(k - 21.097) < 0.5)) return true;
      }
    }
    return false;
  } else {
    const mn = state.distMin;
    const mx = state.distMax;
    if (mn === null && mx === null) return true;
    return kms.some(k => (mn === null || k >= mn) && (mx === null || k <= mx));
  }
}

function matchesSearch(c) {
  const q = state.searchQuery;
  if (!q) return true;
  const haystack = [c.titulo, c.cidade, c.localizacao, c.estado]
    .filter(Boolean).join(' ').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');
  const needle = q.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');
  return needle.split(/\s+/).every(word => haystack.includes(word));
}

// ---------------------------------------------------------------------------
// Render
// ---------------------------------------------------------------------------
function renderCards() {
  cardsList.innerHTML = '';

  if (filteredCorridas.length === 0) {
    emptyState.classList.remove('hidden');
    return;
  }
  emptyState.classList.add('hidden');

  const frag = document.createDocumentFragment();
  let lastMonthKey = null;
  for (const corrida of filteredCorridas) {
    const monthKey = corrida.data_evento ? corrida.data_evento.slice(0, 7) : null;
    if (monthKey && monthKey !== lastMonthKey) {
      frag.appendChild(buildMonthSeparator(monthKey));
      lastMonthKey = monthKey;
    }
    frag.appendChild(buildCard(corrida));
  }
  cardsList.appendChild(frag);
}

function buildMonthSeparator(monthKey) {
  const [year, month] = monthKey.split('-');
  const label = PT_MONTHS_FULL[parseInt(month, 10) - 1] + ' ' + year;
  const div = document.createElement('div');
  div.className = 'month-separator';
  div.setAttribute('role', 'separator');
  div.setAttribute('aria-label', label);
  div.innerHTML = `<span class="month-separator-label">${label}</span>`;
  return div;
}

function buildCard(c) {
  const clone = cardTemplate.content.cloneNode(true);
  const card = clone.querySelector('.card');
  const collapsed = card.querySelector('.card-collapsed');
  const expanded = card.querySelector('.card-expanded');

  // Image
  const img = card.querySelector('.card-img');
  const placeholder = card.querySelector('.card-img-placeholder');
  if (c.imagem_url) {
    img.src = c.imagem_url;
    img.alt = c.titulo;
    img.onload = () => placeholder.classList.add('hidden');
    img.onerror = () => { img.classList.add('hidden'); showPlaceholder(placeholder, c.estado); };
    showPlaceholder(placeholder, c.estado);
  } else {
    img.classList.add('hidden');
    showPlaceholder(placeholder, c.estado);
  }

  // Title
  card.querySelector('.card-title').textContent = c.titulo;

  // Date
  card.querySelector('.card-date').textContent = formatDate(c.data_evento, c.horario, c.distancias);

  // Location
  card.querySelector('.card-location').textContent = formatLocation(c.cidade, c.estado);

  // Distances pills (sorted ascending)
  const distContainer = card.querySelector('.card-distances');
  for (const km of formatDistancesPills(c.distancias)) {
    const span = document.createElement('span');
    span.className = 'dist-pill';
    span.textContent = km;
    distContainer.appendChild(span);
  }

  // Status badge
  const badge = card.querySelector('.badge-status');
  const { label, cls } = statusBadge(c);
  badge.textContent = label;
  badge.className = 'badge-status ' + cls;

  // Fontes badge
  const fontesBadge = card.querySelector('.badge-fontes');
  if (c.fontes && c.fontes.length > 1) {
    fontesBadge.textContent = c.fontes.length + ' fontes';
    fontesBadge.classList.remove('hidden');
  }

  // Expanded content
  buildExpanded(card, c);

  // Toggle expand
  collapsed.addEventListener('click', () => toggleExpand(collapsed, expanded));
  collapsed.addEventListener('keydown', e => {
    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggleExpand(collapsed, expanded); }
  });

  return card;
}

function showPlaceholder(el, estado) {
  el.style.background = stateColor(estado);
  el.textContent = '🏃';
}

function toggleExpand(collapsed, expanded) {
  const open = expanded.classList.toggle('hidden');
  collapsed.setAttribute('aria-expanded', String(!open));
  expanded.setAttribute('aria-hidden', String(open));
}

function buildExpanded(card, c) {
  const expDist = card.querySelector('.expanded-distances');
  const expPeriod = card.querySelector('.expanded-period');
  const expFontes = card.querySelector('.expanded-fontes');
  const expInscricoes = card.querySelector('.expanded-inscricoes');

  // Distances table (sorted ascending)
  if (c.distancias && c.distancias.length > 0) {
    const sorted = sortDistancias(c.distancias);
    const hasDate    = sorted.some(d => d.data);
    const hasHorario = sorted.some(d => d.horario);

    const table = document.createElement('table');
    table.className = 'dist-table';
    let thead = '<thead><tr><th>Distâncias</th>';
    if (hasDate)    thead += '<th>Data</th>';
    if (hasHorario) thead += '<th>Horário</th>';
    thead += '</tr></thead>';
    table.innerHTML = thead;

    const tbody = document.createElement('tbody');
    for (const d of sorted) {
      const tr = document.createElement('tr');
      let cells = `<td>${formatKm(d.km)}</td>`;
      if (hasDate)    cells += `<td>${d.data ? formatDateShort(d.data) : '—'}</td>`;
      if (hasHorario) cells += `<td>${d.horario || '—'}</td>`;
      tr.innerHTML = cells;
      tbody.appendChild(tr);
    }
    table.appendChild(tbody);
    expDist.appendChild(table);
  }

  // Period
  if (c.periodo_inscricao && (c.periodo_inscricao.abertura || c.periodo_inscricao.encerramento)) {
    const h = document.createElement('p');
    h.className = 'expanded-section-title';
    h.textContent = 'Período de inscrição';
    expPeriod.appendChild(h);
    const p = document.createElement('p');
    const ab = c.periodo_inscricao.abertura ? 'Abertura: ' + formatDateShort(c.periodo_inscricao.abertura) : '';
    const enc = c.periodo_inscricao.encerramento ? 'Encerramento: ' + formatDateShort(c.periodo_inscricao.encerramento) : '';
    p.textContent = [ab, enc].filter(Boolean).join(' · ');
    expPeriod.appendChild(p);
  }

  // Fontes: platform name + inscription button (only when link available)
  if (c.fontes && c.fontes.length > 0) {
    const h = document.createElement('p');
    h.className = 'expanded-section-title';
    h.textContent = 'Fontes';
    expFontes.appendChild(h);
    for (const fonte of c.fontes) {
      const div = document.createElement('div');
      div.className = 'fonte-item';
      const inscLink = (fonte.links_inscricao && fonte.links_inscricao.length > 0)
        ? fonte.links_inscricao[0] : (fonte.link_evento || null);
      const btnHtml = inscLink
        ? `<a href="${inscLink}" target="_blank" rel="noopener" class="btn-inscricao">Inscrever-se →</a>`
        : '';
      div.innerHTML = `<span class="fonte-nome-text">${fonte.nome}</span>${btnHtml}`;
      expFontes.appendChild(div);
    }
  }

  // Inscricoes table (all sources combined)
  const allInscricoes = (c.fontes || []).flatMap(f =>
    (f.inscricoes || []).map(i => ({ ...i, fonte: f.nome }))
  );
  if (allInscricoes.length > 0) {
    const h = document.createElement('p');
    h.className = 'expanded-section-title';
    h.textContent = 'Valores';
    expInscricoes.appendChild(h);
    const table = document.createElement('table');
    table.className = 'inscricao-table';
    table.innerHTML = '<thead><tr><th>Descrição</th><th>Valor</th><th>Status</th><th>Link</th></tr></thead>';
    const tbody = document.createElement('tbody');
    for (const i of allInscricoes) {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td>${i.descricao || '—'}</td>
        <td class="inscricao-valor">${i.valor != null ? 'R$ ' + i.valor.toFixed(2).replace('.', ',') : '—'}</td>
        <td>${i.disponivel ? '<span class="tag-open">Aberta</span>' : '<span class="tag-closed">Encerrada</span>'}</td>
        <td class="inscricao-link">${i.link ? `<a href="${i.link}" target="_blank" rel="noopener">Inscrever →</a>` : '—'}</td>
      `;
      tbody.appendChild(tr);
    }
    table.appendChild(tbody);
    expInscricoes.appendChild(table);
  }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
const PT_MONTHS = ['jan','fev','mar','abr','mai','jun','jul','ago','set','out','nov','dez'];
const PT_MONTHS_FULL = ['Janeiro','Fevereiro','Março','Abril','Maio','Junho','Julho','Agosto','Setembro','Outubro','Novembro','Dezembro'];
const PT_WEEKDAYS = ['Dom','Seg','Ter','Qua','Qui','Sex','Sáb'];

function formatDate(isoDate, horario, distancias) {
  if (!isoDate) return 'Data a confirmar';

  // Multi-day: at least 2 distinct dates across the distances themselves
  const distDates = [...new Set(
    (distancias || []).map(d => d.data).filter(Boolean)
  )].sort();

  if (distDates.length >= 2) {
    return formatDateRange(distDates[0], distDates[distDates.length - 1]);
  }

  // Single day
  return formatDateFull(isoDate) + (horario ? ` • ${horario.replace(':', 'h')}` : '');
}

function formatDateFull(iso) {
  const d = new Date(iso + 'T12:00:00');
  const wd = PT_WEEKDAYS[d.getDay()];
  return `${wd}, ${d.getDate()} de ${PT_MONTHS[d.getMonth()]} de ${d.getFullYear()}`;
}

function formatDateRange(fromIso, toIso) {
  const d1 = new Date(fromIso + 'T12:00:00');
  const d2 = new Date(toIso   + 'T12:00:00');
  const sameMonth = d1.getMonth() === d2.getMonth() && d1.getFullYear() === d2.getFullYear();
  if (sameMonth) {
    return `${d1.getDate()} a ${d2.getDate()} de ${PT_MONTHS[d1.getMonth()]} de ${d1.getFullYear()}`;
  }
  return `${d1.getDate()} de ${PT_MONTHS[d1.getMonth()]} a ${d2.getDate()} de ${PT_MONTHS[d2.getMonth()]} de ${d2.getFullYear()}`;
}

function formatDateShort(iso) {
  if (!iso) return '';
  const [y, m, d] = iso.split('-');
  return `${d}/${m}/${y}`;
}

function formatLocation(cidade, estado) {
  if (estado === 'INT') return cidade || '';
  return [cidade, estado].filter(Boolean).join(' · ');
}

function sortDistancias(distancias) {
  return [...distancias].sort((a, b) => {
    const ka = typeof a.km === 'number' ? a.km : Infinity;
    const kb = typeof b.km === 'number' ? b.km : Infinity;
    return ka - kb;
  });
}

function formatDistancesPills(distancias) {
  if (!distancias || distancias.length === 0) return [];
  return sortDistancias(distancias).map(d => formatKm(d.km));
}

function formatKm(km) {
  if (typeof km === 'string') return km;
  if (km === 42.195) return '42K';
  if (km === 21.097) return '21K';
  if (Number.isInteger(km)) return km + 'K';
  return km + 'K';
}

function statusBadge(c) {
  const today = todayStr();
  if (c.data_evento && c.data_evento < today) return { label: '🏁 Realizado', cls: 'badge-realized' };
  if (c.inscricoes_abertas === true) return { label: '🟢 Inscrições abertas', cls: 'badge-open' };
  if (c.inscricoes_abertas === false) return { label: '🔴 Inscrições encerradas', cls: 'badge-closed' };
  return { label: '⚪ Em breve', cls: 'badge-soon' };
}

function stateColor(estado) {
  const map = {
    DF: '#1a3a4a', SP: '#3a1a1a', RJ: '#1a3a1a', MG: '#2a1a3a',
    RS: '#1a2a3a', PR: '#2a3a1a', SC: '#3a2a1a', CE: '#3a3a1a',
    BA: '#3a1a2a', PE: '#1a3a3a', AM: '#1a3a2a', GO: '#2a2a3a',
    INT: '#2a2a2a',
  };
  return map[estado] || '#2a2a2a';
}

function todayStr() {
  return new Date().toISOString().slice(0, 10);
}

function addDays(isoDate, days) {
  const d = new Date(isoDate + 'T12:00:00');
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
}

function updateCount() {
  const n = filteredCorridas.length;
  resultCount.textContent = n === 1 ? '1 corrida encontrada' : `${n} corridas encontradas`;
}

function isFiltersActive() {
  return (
    state.searchQuery !== '' ||
    state.activePills.size > 0 ||
    state.distMin !== null ||
    state.distMax !== null ||
    state.periodo !== 'today' ||
    state.estado !== 'todos'
  );
}

function updateClearButton() {
  btnClear.classList.toggle('hidden', !isFiltersActive());
}

function clearFilters() {
  state.searchQuery = '';
  state.activePills.clear();
  state.distMin = null;
  state.distMax = null;
  state.distMode = 'select';
  state.periodo = 'today';
  state.dateFrom = null;
  state.dateTo = null;
  state.estado = 'todos';

  searchInput.value = '';

  // Sync UI
  document.querySelectorAll('.pill').forEach(p => {
    p.classList.remove('active');
    p.setAttribute('aria-pressed', 'false');
  });
  distMin.value = '';
  distMax.value = '';
  periodoSelect.value = 'today';
  estadoSelect.value = 'todos';
  customDateRow.classList.add('hidden');
  dateFrom.value = '';
  dateTo.value = '';
  setDistMode('select');

  saveFilters();
  applyFilters();
}

// ---------------------------------------------------------------------------
// Mode toggle
// ---------------------------------------------------------------------------
function setDistMode(mode) {
  state.distMode = mode;
  if (mode === 'select') {
    modeSelect.classList.add('active');
    modeSelect.setAttribute('aria-pressed', 'true');
    modeInterval.classList.remove('active');
    modeInterval.setAttribute('aria-pressed', 'false');
    pillsContainer.classList.remove('hidden');
    intervalContainer.classList.add('hidden');
  } else {
    modeInterval.classList.add('active');
    modeInterval.setAttribute('aria-pressed', 'true');
    modeSelect.classList.remove('active');
    modeSelect.setAttribute('aria-pressed', 'false');
    intervalContainer.classList.remove('hidden');
    pillsContainer.classList.add('hidden');
  }
}

// ---------------------------------------------------------------------------
// Event listeners
// ---------------------------------------------------------------------------
modeSelect.addEventListener('click', () => {
  if (state.distMode !== 'select') {
    state.distMin = null;
    state.distMax = null;
    distMin.value = '';
    distMax.value = '';
    setDistMode('select');
    saveFilters();
    applyFilters();
  }
});

modeInterval.addEventListener('click', () => {
  if (state.distMode !== 'interval') {
    state.activePills.clear();
    document.querySelectorAll('.pill').forEach(p => {
      p.classList.remove('active');
      p.setAttribute('aria-pressed', 'false');
    });
    setDistMode('interval');
    saveFilters();
    applyFilters();
  }
});

document.querySelectorAll('.pill').forEach(pill => {
  pill.addEventListener('click', () => {
    const km = pill.dataset.km;
    if (state.activePills.has(km)) {
      state.activePills.delete(km);
      pill.classList.remove('active');
      pill.setAttribute('aria-pressed', 'false');
    } else {
      state.activePills.add(km);
      pill.classList.add('active');
      pill.setAttribute('aria-pressed', 'true');
    }
    saveFilters();
    applyFilters();
  });
});

distMin.addEventListener('input', () => {
  state.distMin = distMin.value ? parseFloat(distMin.value) : null;
  saveFilters();
  applyFilters();
});
distMax.addEventListener('input', () => {
  state.distMax = distMax.value ? parseFloat(distMax.value) : null;
  saveFilters();
  applyFilters();
});

periodoSelect.addEventListener('change', () => {
  state.periodo = periodoSelect.value;
  customDateRow.classList.toggle('hidden', state.periodo !== 'custom');
  applyFilters();
});

dateFrom.addEventListener('change', () => {
  state.dateFrom = dateFrom.value || null;
  applyFilters();
});
dateTo.addEventListener('change', () => {
  state.dateTo = dateTo.value || null;
  applyFilters();
});

estadoSelect.addEventListener('change', () => {
  state.estado = estadoSelect.value;
  saveFilters();
  applyFilters();
});

let _searchTimer = null;
searchInput.addEventListener('input', () => {
  clearTimeout(_searchTimer);
  _searchTimer = setTimeout(() => {
    state.searchQuery = searchInput.value.trim();
    applyFilters();
  }, 200);
});

[btnClear, btnClearEmpty].forEach(btn => btn?.addEventListener('click', clearFilters));

btnRefresh.addEventListener('click', fetchData);

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------
function init() {
  loadFilters();

  // Restore UI from state
  if (state.distMode === 'interval') setDistMode('interval');
  state.activePills.forEach(km => {
    const pill = document.querySelector(`.pill[data-km="${km}"]`);
    if (pill) { pill.classList.add('active'); pill.setAttribute('aria-pressed', 'true'); }
  });
  if (state.distMin !== null) distMin.value = state.distMin;
  if (state.distMax !== null) distMax.value = state.distMax;
  estadoSelect.value = state.estado;
  periodoSelect.value = state.periodo;

  // Register service worker
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('./service-worker.js').catch(() => {});
  }

  fetchData();
}

init();
