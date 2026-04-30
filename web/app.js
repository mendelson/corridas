'use strict';

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------
let allCorridas = [];
let filteredCorridas = [];

// Geo-detected state abbreviation (in-session only — always refreshed on page load)
let _geoEstado = null;

const state = {
  distMode: 'select',  // 'select' | 'interval'
  activePills: new Set(),
  distMin: null,
  distMax: null,
  periodo: 'past15',
  dateFrom: null,
  dateTo: null,
  estado: 'todos',
  fontes: new Set(),
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
const fonteFilterWrapper = $('fonteFilterWrapper');
const fonteFilterBtn = $('fonteFilterBtn');
const fonteFilterDropdown = $('fonteFilterDropdown');
const fonteFilterLabel = $('fonteFilterLabel');

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
      fontes: [...state.fontes],
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
    state.fontes = new Set(saved.fontes || []);
  } catch (e) { /* ignore */ }
  // periodo always resets to default (not persisted)
  state.periodo = 'past15';
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
    populateFontesFilter();
    applyFilters();
  } catch (e) {
    resultCount.textContent = 'Erro ao carregar dados.';
    console.error(e);
  } finally {
    btnRefresh.classList.remove('spinning');
  }
}

// ---------------------------------------------------------------------------
// Location filter helpers
// ---------------------------------------------------------------------------
const _ESTADO_LABELS = {
  AC: 'Acre · AC',           AL: 'Alagoas · AL',        AM: 'Amazonas · AM',
  AP: 'Amapá · AP',          BA: 'Bahia · BA',           CE: 'Ceará · CE',
  DF: 'Brasília · DF',       ES: 'Espírito Santo · ES',  GO: 'Goiás · GO',
  MA: 'Maranhão · MA',       MG: 'Minas Gerais · MG',    MS: 'Mato Grosso do Sul · MS',
  MT: 'Mato Grosso · MT',    PA: 'Pará · PA',             PB: 'Paraíba · PB',
  PE: 'Pernambuco · PE',     PI: 'Piauí · PI',            PR: 'Paraná · PR',
  RJ: 'Rio de Janeiro · RJ', RN: 'Rio Grande do Norte · RN', RO: 'Rondônia · RO',
  RR: 'Roraima · RR',        RS: 'Rio Grande do Sul · RS',   SC: 'Santa Catarina · SC',
  SE: 'Sergipe · SE',        SP: 'São Paulo · SP',           TO: 'Tocantins · TO',
};

// Apply _geoEstado to the select if the option already exists; called from both
// detectUserLocation (late resolution) and populateEstadoFilter (early resolution).
function _applyGeoEstado() {
  if (!_geoEstado || state.estado !== 'todos') return;
  // Only apply if the option exists — options may not be populated yet
  if (![...estadoSelect.options].some(o => o.value === _geoEstado)) return;
  // Don't apply if it would produce an empty list in the current period
  const today = todayStr();
  const wouldMatch = allCorridas.some(c => c.estado === _geoEstado && matchesPeriodo(c, today));
  if (!wouldMatch) return;
  state.estado = _geoEstado;
  estadoSelect.value = _geoEstado;
  saveFilters();
  applyFilters();
}

async function _tryGeoFetch(url) {
  const ctrl = new AbortController();
  const tid = setTimeout(() => ctrl.abort(), 5000);
  try {
    const r = await fetch(url, { signal: ctrl.signal });
    clearTimeout(tid);
    return r.ok ? r.json() : null;
  } catch {
    clearTimeout(tid);
    return null;
  }
}

async function detectUserLocation() {
  // Try three independent APIs concurrently; use the first valid BR state that responds.
  const fetchers = [
    () => _tryGeoFetch('https://ipwho.is/').then(d =>
      (d?.success && d.country_code === 'BR' && _ESTADO_LABELS[d.region_code]) ? d.region_code : null),
    () => _tryGeoFetch('https://freeipapi.com/api/json').then(d =>
      (d?.countryCode === 'BR' && _ESTADO_LABELS[d.regionCode]) ? d.regionCode : null),
    () => _tryGeoFetch('https://api.ip.sb/geoip').then(d =>
      (d?.country_code === 'BR' && _ESTADO_LABELS[d.region_code]) ? d.region_code : null),
  ];

  const uf = await new Promise(resolve => {
    let remaining = fetchers.length;
    for (const fn of fetchers) {
      fn().then(r => {
        if (r) resolve(r);
        else if (--remaining === 0) resolve(null);
      }).catch(() => { if (--remaining === 0) resolve(null); });
    }
  });

  if (uf) {
    _geoEstado = uf;
    _applyGeoEstado();
  }
}

function _extractCountry(cidade) {
  if (!cidade) return null;
  const parts = cidade.split(',');
  return parts.length > 1 ? parts[parts.length - 1].trim() : null;
}

// ---------------------------------------------------------------------------
// Estado filter population
// ---------------------------------------------------------------------------
function populateEstadoFilter() {
  // Keep only the first "Todos" option
  while (estadoSelect.options.length > 1) estadoSelect.remove(1);

  const brEstados = [...new Set(
    allCorridas.filter(c => c.estado && c.estado !== 'INT' && c.estado !== '??').map(c => c.estado)
  )].sort();

  const intCountries = [...new Set(
    allCorridas.filter(c => c.estado === 'INT').map(c => _extractCountry(c.cidade))
  )].filter(Boolean).sort();

  if (brEstados.length > 0) {
    const grp = document.createElement('optgroup');
    grp.label = 'Brasil';
    for (const uf of brEstados) {
      const opt = document.createElement('option');
      opt.value = uf;
      opt.textContent = _ESTADO_LABELS[uf] || uf;
      grp.appendChild(opt);
    }
    estadoSelect.appendChild(grp);
  }

  if (intCountries.length > 0) {
    const grp = document.createElement('optgroup');
    grp.label = 'Internacional';
    const allOpt = document.createElement('option');
    allOpt.value = 'INT';
    allOpt.textContent = 'Todos internacionais';
    grp.appendChild(allOpt);
    for (const country of intCountries) {
      const opt = document.createElement('option');
      opt.value = 'INT:' + country;
      opt.textContent = country;
      grp.appendChild(opt);
    }
    estadoSelect.appendChild(grp);
  }

  // If the saved state has no option in current data, reset to 'todos'
  const availableValues = new Set([...estadoSelect.options].map(o => o.value));
  if (state.estado !== 'todos' && !availableValues.has(state.estado)) {
    state.estado = 'todos';
  }

  // Apply geo default if state is still 'todos'
  _applyGeoEstado();
  // Ensure select reflects current state
  if (estadoSelect.value !== state.estado) estadoSelect.value = state.estado;
}

// ---------------------------------------------------------------------------
// Fonte filter
// ---------------------------------------------------------------------------
function populateFontesFilter() {
  const allNomes = [...new Set(
    allCorridas.flatMap(c => (c.fontes || []).map(f => f.nome))
  )].sort();

  fonteFilterDropdown.innerHTML = '';
  for (const nome of allNomes) {
    const label = document.createElement('label');
    label.className = 'fonte-filter-option' + (state.fontes.has(nome) ? ' checked' : '');
    label.setAttribute('role', 'option');
    label.setAttribute('aria-selected', String(state.fontes.has(nome)));

    const cb = document.createElement('input');
    cb.type = 'checkbox';
    cb.value = nome;
    cb.checked = state.fontes.has(nome);

    const text = document.createTextNode(nome);
    label.appendChild(cb);
    label.appendChild(text);

    cb.addEventListener('change', () => {
      if (cb.checked) {
        state.fontes.add(nome);
        label.classList.add('checked');
        label.setAttribute('aria-selected', 'true');
      } else {
        state.fontes.delete(nome);
        label.classList.remove('checked');
        label.setAttribute('aria-selected', 'false');
      }
      _updateFonteLabel();
      saveFilters();
      applyFilters();
    });

    fonteFilterDropdown.appendChild(label);
  }
  _updateFonteLabel();
}

function _updateFonteLabel() {
  if (state.fontes.size === 0) {
    fonteFilterLabel.textContent = 'Todas as fontes';
    fonteFilterBtn.classList.remove('active');
  } else if (state.fontes.size === 1) {
    fonteFilterLabel.textContent = [...state.fontes][0];
    fonteFilterBtn.classList.add('active');
  } else {
    fonteFilterLabel.textContent = `${state.fontes.size} fontes`;
    fonteFilterBtn.classList.add('active');
  }
}

// ---------------------------------------------------------------------------
// Filtering
// ---------------------------------------------------------------------------
function applyFilters() {
  const today = todayStr();
  const searching = state.searchQuery !== '';

  filteredCorridas = allCorridas.filter(c => {
    if (!searching && !matchesPeriodo(c, today)) return false;
    if (!matchesEstado(c)) return false;
    if (!matchesFonte(c)) return false;
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
    case 'past15':  return d >= addDays(today, -15);
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
  if (state.estado.startsWith('INT:')) {
    const country = state.estado.slice(4);
    return c.estado === 'INT' && _extractCountry(c.cidade) === country;
  }
  return c.estado === state.estado;
}

function matchesFonte(c) {
  if (state.fontes.size === 0) return true;
  return (c.fontes || []).some(f => state.fontes.has(f.nome));
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
  const norm = s => s.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');
  const haystack = [c.titulo, c.cidade, c.localizacao, c.estado].filter(Boolean).map(norm).join(' ');
  const needle = norm(q);
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

  // Group by month key (YYYY-MM) preserving sort order
  const byMonth = new Map();
  for (const corrida of filteredCorridas) {
    const key = corrida.data_evento ? corrida.data_evento.slice(0, 7) : '__sem_data';
    if (!byMonth.has(key)) byMonth.set(key, []);
    byMonth.get(key).push(corrida);
  }

  const frag = document.createDocumentFragment();
  for (const [monthKey, corridas] of byMonth) {
    const { section, cardsContainer } = buildMonthSection(monthKey, corridas.length);
    for (const corrida of corridas) {
      cardsContainer.appendChild(buildCard(corrida));
    }
    frag.appendChild(section);
  }
  cardsList.appendChild(frag);
}

function buildMonthSection(monthKey, count) {
  const [year, month] = monthKey.split('-');
  const label = PT_MONTHS_FULL[parseInt(month, 10) - 1] + ' ' + year;
  const countLabel = count === 1 ? '1 corrida' : `${count} corridas`;

  const section = document.createElement('div');
  section.className = 'month-section';

  const btn = document.createElement('button');
  btn.className = 'month-separator';
  btn.setAttribute('aria-expanded', 'true');
  btn.setAttribute('aria-label', `${label}, ${countLabel}`);
  btn.innerHTML = `
    <span class="month-separator-label">${label}</span>
    <span class="month-count">${countLabel}</span>
    <span class="month-chevron" aria-hidden="true">▾</span>`;

  const cardsContainer = document.createElement('div');
  cardsContainer.className = 'month-cards';

  btn.addEventListener('click', () => {
    const collapsed = cardsContainer.classList.toggle('month-cards--collapsed');
    btn.setAttribute('aria-expanded', String(!collapsed));
    btn.querySelector('.month-chevron').textContent = collapsed ? '▸' : '▾';
  });

  section.appendChild(btn);
  section.appendChild(cardsContainer);
  return { section, cardsContainer };
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
  const expTitle = card.querySelector('.expanded-title');
  const expDist = card.querySelector('.expanded-distances');
  const expPeriod = card.querySelector('.expanded-period');
  const expFontes = card.querySelector('.expanded-fontes');

  expTitle.textContent = c.titulo;
  expTitle.classList.remove('hidden');

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
  if (estado === 'INT' || estado === '??' || !estado) return cidade || '';
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
  // Fallback: presence of inscription links implies open inscriptions
  const hasInscLink = (c.fontes || []).some(f => (f.links_inscricao || []).length > 0);
  if (hasInscLink) return { label: '🟢 Inscrições abertas', cls: 'badge-open' };
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
    state.periodo !== 'past15' ||
    state.estado !== (_geoEstado || 'todos') ||
    state.fontes.size > 0
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
  state.periodo = 'past15';
  state.dateFrom = null;
  state.dateTo = null;
  state.estado = _geoEstado || 'todos';
  state.fontes.clear();

  searchInput.value = '';

  // Sync UI
  document.querySelectorAll('.pill').forEach(p => {
    p.classList.remove('active');
    p.setAttribute('aria-pressed', 'false');
  });
  distMin.value = '';
  distMax.value = '';
  periodoSelect.value = 'past15';
  estadoSelect.value = _geoEstado || 'todos';
  customDateRow.classList.add('hidden');
  dateFrom.value = '';
  dateTo.value = '';
  setDistMode('select');

  // Reset fonte checkboxes
  fonteFilterDropdown.querySelectorAll('input[type="checkbox"]').forEach(cb => {
    cb.checked = false;
    cb.closest('.fonte-filter-option')?.classList.remove('checked');
  });
  _updateFonteLabel();

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

fonteFilterBtn.addEventListener('click', e => {
  e.stopPropagation();
  const isOpen = !fonteFilterDropdown.classList.contains('hidden');
  fonteFilterDropdown.classList.toggle('hidden', isOpen);
  fonteFilterBtn.setAttribute('aria-expanded', String(!isOpen));
});

document.addEventListener('click', e => {
  if (!fonteFilterWrapper.contains(e.target)) {
    fonteFilterDropdown.classList.add('hidden');
    fonteFilterBtn.setAttribute('aria-expanded', 'false');
  }
});

document.addEventListener('keydown', e => {
  if (e.key === 'Escape' && !fonteFilterDropdown.classList.contains('hidden')) {
    fonteFilterDropdown.classList.add('hidden');
    fonteFilterBtn.setAttribute('aria-expanded', 'false');
    fonteFilterBtn.focus();
  }
});

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

  detectUserLocation();
  fetchData();
}

init();
