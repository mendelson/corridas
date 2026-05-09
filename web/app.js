'use strict';

// ---------------------------------------------------------------------------
// Language detection — runs before anything else
// ---------------------------------------------------------------------------
const BROWSER_LANG = (() => {
  const bl = (navigator.language || (navigator.languages && navigator.languages[0]) || '').toLowerCase();
  if (bl.startsWith('pt')) return 'pt';
  if (bl.startsWith('es')) return 'es';
  if (bl.startsWith('de')) return 'de';
  if (bl.startsWith('fr')) return 'fr';
  return 'en';
})();

const LANG = (() => {
  const path = window.location.pathname;
  return ['pt','en','es','de','fr'].find(l => path.startsWith('/' + l)) || BROWSER_LANG;
})();

const LANG_URLS = { pt: '/pt', en: '/en', es: '/es', de: '/de', fr: '/fr' };

// ---------------------------------------------------------------------------
// i18n strings
// ---------------------------------------------------------------------------
const STRINGS = {
  pt: {
    siteTitle: 'Próxima Corrida',
    headerTitle: '🏃 Próxima Corrida',
    searchPlaceholder: 'Buscar corrida...',
    searchAriaLabel: 'Buscar corrida',
    modeSelect: 'Selecionar',
    modeInterval: 'Intervalo',
    distFrom: 'De',
    distTo: 'Até',
    distMinAriaLabel: 'Distância mínima em km',
    distMaxAriaLabel: 'Distância máxima em km',
    dateFromAriaLabel: 'Data inicial',
    dateToAriaLabel: 'Data final',
    periodoAriaLabel: 'Filtrar por período',
    estadoAriaLabel: 'Filtrar por localização',
    fonteFilterAriaLabel: 'Filtrar por fonte',
    refreshAriaLabel: 'Atualizar',
    homeAriaLabel: 'Minha localização e idioma',
    langAriaLabel: 'Idioma',
    clearFiltersAriaLabel: 'Limpar filtros',
    allLocations: 'Todos',
    allBrazil: 'Todo o Brasil',
    allSources: 'Todas as fontes',
    nSources: n => n === 1 ? `${n} fonte` : `${n} fontes`,
    badgeNovo: 'novo',
    loading: 'Carregando...',
    loadError: 'Erro ao carregar dados.',
    clearFilters: 'Limpar filtros',
    noResults: 'Nenhuma corrida encontrada com os filtros atuais.',
    raceCount: n => n === 1 ? `${n} corrida` : `${n} corridas`,
    past15: 'Desde 15 dias atrás',
    today: 'A partir de hoje',
    next30: 'Próximos 30 dias',
    next90: 'Próximos 3 meses',
    next180: 'Próximos 6 meses',
    allTime: 'Todo o período',
    custom: 'Intervalo personalizado',
    distancesHeader: 'Distâncias',
    dateColHeader: 'Data',
    timeColHeader: 'Horário',
    sourcesHeader: 'Fontes',
    registerBtn: 'Inscreva-se',
    noImage: 'Sem imagem',
    labelDateFrom: 'De',
    labelDateTo: 'Até',
    labelDistFrom: 'De',
    labelDistTo: 'Até',
    monthNames: ['Janeiro','Fevereiro','Março','Abril','Maio','Junho','Julho','Agosto','Setembro','Outubro','Novembro','Dezembro'],
    dayNames: ['Dom','Seg','Ter','Qua','Qui','Sex','Sáb'],
    today_label: 'Hoje',
    tomorrow_label: 'Amanhã',
    yesterday_label: 'Ontem',
    pills: { '5': '5K', '10': '10K', '15': '15K', '21': '21K', '42': '42K', 'outros': 'Outras' },
    periodoSelect: 'Filtrar por período',
  },
  en: {
    siteTitle: 'Next Race',
    headerTitle: '🏃 Next Race',
    searchPlaceholder: 'Search race...',
    searchAriaLabel: 'Search race',
    modeSelect: 'Select',
    modeInterval: 'Range',
    distFrom: 'From',
    distTo: 'To',
    distMinAriaLabel: 'Minimum distance in km',
    distMaxAriaLabel: 'Maximum distance in km',
    dateFromAriaLabel: 'Start date',
    dateToAriaLabel: 'End date',
    periodoAriaLabel: 'Filter by period',
    estadoAriaLabel: 'Filter by location',
    fonteFilterAriaLabel: 'Filter by source',
    refreshAriaLabel: 'Refresh',
    homeAriaLabel: 'My location and language',
    langAriaLabel: 'Language',
    clearFiltersAriaLabel: 'Clear filters',
    allLocations: 'All',
    allBrazil: 'All Brazil',
    allSources: 'All sources',
    nSources: n => n === 1 ? `${n} source` : `${n} sources`,
    badgeNovo: 'new',
    loading: 'Loading...',
    loadError: 'Error loading data.',
    clearFilters: 'Clear filters',
    noResults: 'No races found with current filters.',
    raceCount: n => n === 1 ? `${n} race` : `${n} races`,
    past15: 'Since 15 days ago',
    today: 'From today',
    next30: 'Next 30 days',
    next90: 'Next 3 months',
    next180: 'Next 6 months',
    allTime: 'All time',
    custom: 'Custom range',
    distancesHeader: 'Distances',
    dateColHeader: 'Date',
    timeColHeader: 'Time',
    sourcesHeader: 'Sources',
    registerBtn: 'Register',
    noImage: 'No image',
    labelDateFrom: 'From',
    labelDateTo: 'To',
    labelDistFrom: 'From',
    labelDistTo: 'To',
    monthNames: ['January','February','March','April','May','June','July','August','September','October','November','December'],
    dayNames: ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'],
    today_label: 'Today',
    tomorrow_label: 'Tomorrow',
    yesterday_label: 'Yesterday',
    pills: { '5': '5K', '10': '10K', '15': '15K', '21': '21K', '42': '42K', 'outros': 'Other' },
    periodoSelect: 'Filter by period',
  },
  es: {
    siteTitle: 'Próxima Carrera',
    headerTitle: '🏃 Próxima Carrera',
    searchPlaceholder: 'Buscar carrera...',
    searchAriaLabel: 'Buscar carrera',
    modeSelect: 'Seleccionar',
    modeInterval: 'Intervalo',
    distFrom: 'Desde',
    distTo: 'Hasta',
    distMinAriaLabel: 'Distancia mínima en km',
    distMaxAriaLabel: 'Distancia máxima en km',
    dateFromAriaLabel: 'Fecha inicial',
    dateToAriaLabel: 'Fecha final',
    periodoAriaLabel: 'Filtrar por período',
    estadoAriaLabel: 'Filtrar por ubicación',
    fonteFilterAriaLabel: 'Filtrar por fuente',
    refreshAriaLabel: 'Actualizar',
    homeAriaLabel: 'Mi ubicación e idioma',
    langAriaLabel: 'Idioma',
    clearFiltersAriaLabel: 'Limpiar filtros',
    allLocations: 'Todos',
    allBrazil: 'Todo Brasil',
    allSources: 'Todas las fuentes',
    nSources: n => n === 1 ? `${n} fuente` : `${n} fuentes`,
    badgeNovo: 'nuevo',
    loading: 'Cargando...',
    loadError: 'Error al cargar datos.',
    clearFilters: 'Limpiar filtros',
    noResults: 'No se encontraron carreras con los filtros actuales.',
    raceCount: n => n === 1 ? `${n} carrera` : `${n} carreras`,
    past15: 'Desde hace 15 días',
    today: 'Desde hoy',
    next30: 'Próximos 30 días',
    next90: 'Próximos 3 meses',
    next180: 'Próximos 6 meses',
    allTime: 'Todo el período',
    custom: 'Intervalo personalizado',
    distancesHeader: 'Distancias',
    dateColHeader: 'Fecha',
    timeColHeader: 'Hora',
    sourcesHeader: 'Fuentes',
    registerBtn: 'Inscribirse',
    noImage: 'Sin imagen',
    labelDateFrom: 'Desde',
    labelDateTo: 'Hasta',
    labelDistFrom: 'Desde',
    labelDistTo: 'Hasta',
    monthNames: ['Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre'],
    dayNames: ['Dom','Lun','Mar','Mié','Jue','Vie','Sáb'],
    today_label: 'Hoy',
    tomorrow_label: 'Mañana',
    yesterday_label: 'Ayer',
    pills: { '5': '5K', '10': '10K', '15': '15K', '21': '21K', '42': '42K', 'outros': 'Otras' },
    periodoSelect: 'Filtrar por período',
  },
  de: {
    siteTitle: 'Nächstes Rennen',
    headerTitle: '🏃 Nächstes Rennen',
    searchPlaceholder: 'Rennen suchen...',
    searchAriaLabel: 'Rennen suchen',
    modeSelect: 'Auswählen',
    modeInterval: 'Bereich',
    distFrom: 'Von',
    distTo: 'Bis',
    distMinAriaLabel: 'Mindestdistanz in km',
    distMaxAriaLabel: 'Maximaldistanz in km',
    dateFromAriaLabel: 'Startdatum',
    dateToAriaLabel: 'Enddatum',
    periodoAriaLabel: 'Nach Zeitraum filtern',
    estadoAriaLabel: 'Nach Ort filtern',
    fonteFilterAriaLabel: 'Nach Quelle filtern',
    refreshAriaLabel: 'Aktualisieren',
    homeAriaLabel: 'Mein Standort und Sprache',
    langAriaLabel: 'Sprache',
    clearFiltersAriaLabel: 'Filter löschen',
    allLocations: 'Alle',
    allBrazil: 'Ganz Brasilien',
    allSources: 'Alle Quellen',
    nSources: n => n === 1 ? `${n} Quelle` : `${n} Quellen`,
    badgeNovo: 'neu',
    loading: 'Laden...',
    loadError: 'Fehler beim Laden der Daten.',
    clearFilters: 'Filter löschen',
    noResults: 'Keine Rennen mit den aktuellen Filtern gefunden.',
    raceCount: n => n === 1 ? `${n} Rennen` : `${n} Rennen`,
    past15: 'Seit 15 Tagen',
    today: 'Ab heute',
    next30: 'Nächste 30 Tage',
    next90: 'Nächste 3 Monate',
    next180: 'Nächste 6 Monate',
    allTime: 'Gesamter Zeitraum',
    custom: 'Benutzerdefinierter Zeitraum',
    distancesHeader: 'Distanzen',
    dateColHeader: 'Datum',
    timeColHeader: 'Zeit',
    sourcesHeader: 'Quellen',
    registerBtn: 'Anmelden',
    noImage: 'Kein Bild',
    labelDateFrom: 'Von',
    labelDateTo: 'Bis',
    labelDistFrom: 'Von',
    labelDistTo: 'Bis',
    monthNames: ['Januar','Februar','März','April','Mai','Juni','Juli','August','September','Oktober','November','Dezember'],
    dayNames: ['So','Mo','Di','Mi','Do','Fr','Sa'],
    today_label: 'Heute',
    tomorrow_label: 'Morgen',
    yesterday_label: 'Gestern',
    pills: { '5': '5K', '10': '10K', '15': '15K', '21': '21K', '42': '42K', 'outros': 'Andere' },
    periodoSelect: 'Nach Zeitraum filtern',
  },
  fr: {
    siteTitle: 'Prochaine Course',
    headerTitle: '🏃 Prochaine Course',
    searchPlaceholder: 'Rechercher une course...',
    searchAriaLabel: 'Rechercher une course',
    modeSelect: 'Sélectionner',
    modeInterval: 'Intervalle',
    distFrom: 'De',
    distTo: 'À',
    distMinAriaLabel: 'Distance minimale en km',
    distMaxAriaLabel: 'Distance maximale en km',
    dateFromAriaLabel: 'Date de début',
    dateToAriaLabel: 'Date de fin',
    periodoAriaLabel: 'Filtrer par période',
    estadoAriaLabel: 'Filtrer par lieu',
    fonteFilterAriaLabel: 'Filtrer par source',
    refreshAriaLabel: 'Actualiser',
    homeAriaLabel: 'Ma position et langue',
    langAriaLabel: 'Langue',
    clearFiltersAriaLabel: 'Effacer les filtres',
    allLocations: 'Tous',
    allBrazil: 'Tout le Brésil',
    allSources: 'Toutes les sources',
    nSources: n => n === 1 ? `${n} source` : `${n} sources`,
    badgeNovo: 'nouveau',
    loading: 'Chargement...',
    loadError: 'Erreur lors du chargement des données.',
    clearFilters: 'Effacer les filtres',
    noResults: 'Aucune course trouvée avec les filtres actuels.',
    raceCount: n => n === 1 ? `${n} course` : `${n} courses`,
    past15: 'Depuis 15 jours',
    today: "À partir d'aujourd'hui",
    next30: '30 prochains jours',
    next90: '3 prochains mois',
    next180: '6 prochains mois',
    allTime: 'Toute la période',
    custom: 'Période personnalisée',
    distancesHeader: 'Distances',
    dateColHeader: 'Date',
    timeColHeader: 'Heure',
    sourcesHeader: 'Sources',
    registerBtn: "S'inscrire",
    noImage: 'Sans image',
    labelDateFrom: 'De',
    labelDateTo: 'À',
    labelDistFrom: 'De',
    labelDistTo: 'À',
    monthNames: ['Janvier','Février','Mars','Avril','Mai','Juin','Juillet','Août','Septembre','Octobre','Novembre','Décembre'],
    dayNames: ['Dim','Lun','Mar','Mer','Jeu','Ven','Sam'],
    today_label: "Aujourd'hui",
    tomorrow_label: 'Demain',
    yesterday_label: 'Hier',
    pills: { '5': '5K', '10': '10K', '15': '15K', '21': '21K', '42': '42K', 'outros': 'Autres' },
    periodoSelect: 'Filtrer par période',
  },
};

const T = STRINGS[LANG] || STRINGS.en;

// ---------------------------------------------------------------------------
// DOM references (populated after DOMContentLoaded)
// ---------------------------------------------------------------------------
let searchInput, cardsList, emptyState, btnClear, btnClearEmpty,
    periodoSelect, estadoFilterBtn, estadoFilterLabel, estadoFilterDropdown,
    fonteFilterBtn, fonteFilterLabel, fonteFilterDropdown,
    resultCount, filtersBar, btnRefresh, btnLang, btnHome,
    modeSelect, modeInterval, pillsContainer, intervalContainer,
    distMin, distMax, customDateRow, dateFrom, dateTo;

// ---------------------------------------------------------------------------
// App state
// ---------------------------------------------------------------------------
const state = {
  searchQuery: '',
  activePills:  new Set(),
  distMode:     'select',
  distMin:      null,
  distMax:      null,
  periodo:      'past15',
  dateFrom:     null,
  dateTo:       null,
  estado:       'todos',
  fontes:       new Set(),
};

let allCorridas      = [];
let filteredCorridas = [];
let _geoApplied      = null;  // estado code applied from geolocation

// ---------------------------------------------------------------------------
// Geolocation pipeline
// ---------------------------------------------------------------------------
async function detectGeoEstado() {
  const cached = sessionStorage.getItem('_geoCache');
  if (cached) return cached === 'null' ? null : cached;

  const apis = [
    () => fetch('https://ipwho.is/').then(r => r.json()).then(d => d.country_code === 'BR' ? d.region_code : null),
    () => fetch('https://freeipapi.com/api/json').then(r => r.json()).then(d => d.countryCode === 'BR' ? d.regionCode : null),
    () => fetch('https://api.ip.sb/geoip').then(r => r.json()).then(d => d.country_code === 'BR' ? d.region_code : null),
  ];
  for (const fn of apis) {
    try {
      const code = await fn();
      if (code) {
        sessionStorage.setItem('_geoCache', code);
        return code;
      }
    } catch (_) {}
  }
  sessionStorage.setItem('_geoCache', 'null');
  return null;
}

// ---------------------------------------------------------------------------
// Data loading
// ---------------------------------------------------------------------------
async function loadData() {
  resultCount.textContent = T.loading;
  try {
    const res = await fetch('/corridas.json');
    if (!res.ok) throw new Error(res.status);
    const json = await res.json();
    allCorridas = json.corridas || json;
    await initFilters();
  } catch (e) {
    resultCount.textContent = T.loadError;
    console.error('loadData error', e);
  }
}

// ---------------------------------------------------------------------------
// Filter initialisation
// ---------------------------------------------------------------------------
async function initFilters() {
  restoreFilters();

  // Build estado dropdown
  const estadoSet = new Set();
  for (const c of allCorridas) {
    if (c.estado) estadoSet.add(c.estado);
  }
  const estados = [...estadoSet].sort();
  buildEstadoDropdown(estados);

  // Build fonte dropdown
  const fonteSet = new Set();
  for (const c of allCorridas) {
    for (const f of (c.fontes || [])) {
      if (f.nome) fonteSet.add(f.nome);
    }
  }
  const fontes = [...fonteSet].sort();
  buildFonteDropdown(fontes);

  // Geolocation (only if no persisted state preference)
  const saved = loadSavedFilters();
  if (!saved || !saved.estado) {
    const geo = await detectGeoEstado();
    if (geo && estadoSet.has(geo)) {
      state.estado  = geo;
      _geoApplied   = geo;
      updateEstadoUI();
    }
  }

  applyFilters();
  renderCards();
  updateCount();
}

// ---------------------------------------------------------------------------
// Persistence
// ---------------------------------------------------------------------------
function loadSavedFilters() {
  try { return JSON.parse(localStorage.getItem('corridas_filters') || 'null'); }
  catch (_) { return null; }
}

function restoreFilters() {
  const saved = loadSavedFilters();
  if (!saved) return;

  if (saved.searchQuery) {
    state.searchQuery = saved.searchQuery;
    searchInput.value = saved.searchQuery;
  }
  if (saved.periodo) {
    state.periodo = saved.periodo;
    periodoSelect.value = saved.periodo;
    toggleCustomDateRow(saved.periodo === 'custom');
  }
  if (saved.dateFrom) { state.dateFrom = saved.dateFrom; dateFrom.value = saved.dateFrom; }
  if (saved.dateTo)   { state.dateTo   = saved.dateTo;   dateTo.value   = saved.dateTo; }
  if (saved.estado) {
    state.estado = saved.estado;
    updateEstadoUI();
  }
  if (saved.fontes && Array.isArray(saved.fontes)) {
    state.fontes = new Set(saved.fontes);
  }
  if (saved.activePills && Array.isArray(saved.activePills)) {
    state.activePills = new Set(saved.activePills);
    for (const pill of pillsContainer.querySelectorAll('.pill')) {
      pill.setAttribute('aria-pressed', state.activePills.has(pill.dataset.km) ? 'true' : 'false');
      pill.classList.toggle('active', state.activePills.has(pill.dataset.km));
    }
  }
  if (saved.distMode === 'interval') {
    state.distMode = 'interval';
    modeSelect.classList.remove('active'); modeSelect.setAttribute('aria-pressed', 'false');
    modeInterval.classList.add('active');  modeInterval.setAttribute('aria-pressed', 'true');
    pillsContainer.classList.add('hidden');
    intervalContainer.classList.remove('hidden');
  }
  if (saved.distMin !== undefined && saved.distMin !== null) { state.distMin = saved.distMin; distMin.value = saved.distMin; }
  if (saved.distMax !== undefined && saved.distMax !== null) { state.distMax = saved.distMax; distMax.value = saved.distMax; }
}

function saveFilters() {
  const obj = {
    searchQuery: state.searchQuery,
    periodo:     state.periodo,
    dateFrom:    state.dateFrom,
    dateTo:      state.dateTo,
    estado:      state.estado,
    fontes:      [...state.fontes],
    activePills: [...state.activePills],
    distMode:    state.distMode,
    distMin:     state.distMin,
    distMax:     state.distMax,
  };
  localStorage.setItem('corridas_filters', JSON.stringify(obj));
}

// ---------------------------------------------------------------------------
// Estado dropdown (custom multi-region selector)
// ---------------------------------------------------------------------------
const STATE_LABELS = {
  AC:'Acre',AM:'Amazonas',AP:'Amapá',PA:'Pará',RO:'Rondônia',RR:'Roraima',TO:'Tocantins',
  AL:'Alagoas',BA:'Bahia',CE:'Ceará',MA:'Maranhão',PB:'Paraíba',PE:'Pernambuco',
  PI:'Piauí',RN:'Rio Grande do Norte',SE:'Sergipe',
  DF:'Distrito Federal',GO:'Goiás',MS:'Mato Grosso do Sul',MT:'Mato Grosso',
  ES:'Espírito Santo',MG:'Minas Gerais',RJ:'Rio de Janeiro',SP:'São Paulo',
  PR:'Paraná',RS:'Rio Grande do Sul',SC:'Santa Catarina',
  INT:'Internacional',
};

function buildEstadoDropdown(estados) {
  estadoFilterDropdown.innerHTML = '';

  const allOpt = document.createElement('div');
  allOpt.className = 'estado-option';
  allOpt.setAttribute('role', 'option');
  allOpt.dataset.value = 'todos';
  allOpt.textContent = T.allLocations;
  allOpt.setAttribute('aria-selected', state.estado === 'todos' ? 'true' : 'false');
  allOpt.addEventListener('click', () => setEstado('todos'));
  estadoFilterDropdown.appendChild(allOpt);

  const brOpt = document.createElement('div');
  brOpt.className = 'estado-option';
  brOpt.setAttribute('role', 'option');
  brOpt.dataset.value = 'brasil';
  brOpt.textContent = T.allBrazil;
  brOpt.setAttribute('aria-selected', state.estado === 'brasil' ? 'true' : 'false');
  brOpt.addEventListener('click', () => setEstado('brasil'));
  estadoFilterDropdown.appendChild(brOpt);

  for (const est of estados) {
    const opt = document.createElement('div');
    opt.className = 'estado-option';
    opt.setAttribute('role', 'option');
    opt.dataset.value = est;
    opt.textContent = STATE_LABELS[est] ? `${STATE_LABELS[est]} (${est})` : est;
    opt.setAttribute('aria-selected', state.estado === est ? 'true' : 'false');
    opt.addEventListener('click', () => setEstado(est));
    estadoFilterDropdown.appendChild(opt);
  }
}

function setEstado(val) {
  state.estado = val;
  updateEstadoUI();
  estadoFilterDropdown.classList.add('hidden');
  estadoFilterBtn.setAttribute('aria-expanded', 'false');
  onFilterChange();
}

function updateEstadoUI() {
  const val = state.estado;
  if (val === 'todos')  estadoFilterLabel.textContent = T.allLocations;
  else if (val === 'brasil') estadoFilterLabel.textContent = T.allBrazil;
  else estadoFilterLabel.textContent = STATE_LABELS[val] ? `${STATE_LABELS[val]} (${val})` : val;

  for (const opt of estadoFilterDropdown.querySelectorAll('.estado-option')) {
    opt.setAttribute('aria-selected', opt.dataset.value === val ? 'true' : 'false');
  }
}

// ---------------------------------------------------------------------------
// Fonte dropdown
// ---------------------------------------------------------------------------
function buildFonteDropdown(fontes) {
  fonteFilterDropdown.innerHTML = '';

  const allOpt = document.createElement('div');
  allOpt.className = 'fonte-option';
  allOpt.setAttribute('role', 'option');
  allOpt.setAttribute('aria-selected', state.fontes.size === 0 ? 'true' : 'false');
  allOpt.dataset.value = '__all__';
  allOpt.textContent = T.allSources;
  allOpt.addEventListener('click', () => {
    state.fontes.clear();
    updateFonteUI();
    fonteFilterDropdown.classList.add('hidden');
    fonteFilterBtn.setAttribute('aria-expanded', 'false');
    onFilterChange();
  });
  fonteFilterDropdown.appendChild(allOpt);

  for (const f of fontes) {
    const opt = document.createElement('div');
    opt.className = 'fonte-option';
    opt.setAttribute('role', 'option');
    opt.setAttribute('aria-selected', state.fontes.has(f) ? 'true' : 'false');
    opt.dataset.value = f;
    opt.textContent = f;
    opt.addEventListener('click', () => {
      if (state.fontes.has(f)) state.fontes.delete(f);
      else state.fontes.add(f);
      updateFonteUI();
      onFilterChange();
    });
    fonteFilterDropdown.appendChild(opt);
  }

  updateFonteUI();
}

function updateFonteUI() {
  const n = state.fontes.size;
  fonteFilterLabel.textContent = n === 0 ? T.allSources : T.nSources(n);
  for (const opt of fonteFilterDropdown.querySelectorAll('.fonte-option')) {
    const v = opt.dataset.value;
    opt.setAttribute('aria-selected',
      v === '__all__' ? (n === 0 ? 'true' : 'false') : state.fontes.has(v) ? 'true' : 'false'
    );
  }
}

// ---------------------------------------------------------------------------
// Filter logic
// ---------------------------------------------------------------------------
function onFilterChange() {
  applyFilters();
  renderCards();
  updateCount();
  updateClearButton();
  saveFilters();
}

function applyFilters() {
  filteredCorridas = allCorridas.filter(c =>
    matchesPeriodo(c) && matchesEstado(c) && matchesFonte(c) &&
    matchesDistancia(c) && matchesSearch(c)
  );
}

function matchesPeriodo(c) {
  const today = todayStr();
  switch (state.periodo) {
    case 'past15': return !c.data_evento || c.data_evento >= addDays(today, -15);
    case 'today':  return !c.data_evento || c.data_evento >= today;
    case '30':     return !c.data_evento || (c.data_evento >= today && c.data_evento <= addDays(today, 30));
    case '90':     return !c.data_evento || (c.data_evento >= today && c.data_evento <= addDays(today, 90));
    case '180':    return !c.data_evento || (c.data_evento >= today && c.data_evento <= addDays(today, 180));
    case 'all':    return true;
    case 'custom': {
      const from = state.dateFrom, to = state.dateTo;
      if (!from && !to) return true;
      if (from && c.data_evento < from) return false;
      if (to   && c.data_evento > to)   return false;
      return true;
    }
    default: return true;
  }
}

function matchesEstado(c) {
  if (state.estado === 'todos')  return true;
  if (state.estado === 'brasil') return c.estado !== 'INT';
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
        if (target === 42 && kms.some(k => Math.abs(k - 42.195) < 0.5)) return true;
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

  const today = todayStr();
  const frag  = document.createDocumentFragment();

  // Group by month
  const groups = [];
  let curMonth = null;
  for (const c of filteredCorridas) {
    const month = (c.data_evento || '').slice(0, 7);
    if (month !== curMonth) {
      groups.push({ month, items: [] });
      curMonth = month;
    }
    groups[groups.length - 1].items.push(c);
  }

  const sevenDaysAgo = addDays(today, -7);

  for (const { month, items } of groups) {
    // Month header
    const header = document.createElement('div');
    header.className = 'month-header';
    const monthLabel = month ? formatMonth(month) : '—';
    const hasNew = items.some(c => c.first_seen_at && c.first_seen_at >= sevenDaysAgo);
    header.innerHTML = `<span class="month-label">${monthLabel}</span>${hasNew ? `<span class="badge-novo">${T.badgeNovo}</span>` : ''}`;
    frag.appendChild(header);

    for (const c of items) {
      const card = buildCard(c, today, sevenDaysAgo);
      frag.appendChild(card);
    }
  }

  cardsList.appendChild(frag);
}

function buildCard(c, today, sevenDaysAgo) {
  const tmpl = document.getElementById('cardTemplate');
  const node  = tmpl.content.cloneNode(true);
  const card  = node.querySelector('.card');

  // Collapsed section
  const collapsed = card.querySelector('.card-collapsed');

  const img = card.querySelector('.card-img');
  const placeholder = card.querySelector('.card-img-placeholder');
  if (c.imagem_url) {
    img.src = c.imagem_url;
    img.alt = c.titulo;
    img.style.display = '';
    placeholder.style.display = 'none';
    img.addEventListener('error', () => {
      img.style.display = 'none';
      placeholder.style.display = '';
      placeholder.style.background = stateColor(c.estado);
    });
  } else {
    img.style.display = 'none';
    placeholder.style.display = '';
    placeholder.style.background = stateColor(c.estado);
  }

  card.querySelector('.card-title').textContent    = c.titulo;
  card.querySelector('.card-date').textContent     = formatDate(c.data_evento, c.horario, c.distancias);
  card.querySelector('.card-location').textContent = c.localizacao || '';

  const distContainer = card.querySelector('.card-distances');
  for (const km of formatDistancesPills(c.distancias)) {
    const span = document.createElement('span');
    span.className   = 'dist-pill';
    span.textContent = km;
    distContainer.appendChild(span);
  }

  // "Novo" badge
  const badgeNovo = card.querySelector('.badge-novo');
  if (badgeNovo) {
    const isNew = c.first_seen_at && c.first_seen_at >= sevenDaysAgo;
    badgeNovo.textContent = T.badgeNovo;
    badgeNovo.classList.toggle('hidden', !isNew);
  }

  // Fontes badge on collapsed card
  const badgeFontes = card.querySelector('.badge-fontes');
  if (badgeFontes && c.fontes && c.fontes.length > 1) {
    badgeFontes.textContent = T.nSources(c.fontes.length);
    badgeFontes.classList.remove('hidden');
  }

  // Expand / collapse
  collapsed.addEventListener('click',  e => toggleCard(card, c, e));
  collapsed.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggleCard(card, c, e); } });

  return card;
}

function toggleCard(card, c, e) {
  if (e.target.closest('a, button')) return;
  const isOpen = card.classList.contains('open');
  // Close all other open cards
  for (const other of cardsList.querySelectorAll('.card.open')) {
    if (other !== card) {
      other.classList.remove('open');
      other.querySelector('.card-collapsed').setAttribute('aria-expanded', 'false');
      other.querySelector('.card-expanded').classList.add('hidden');
      other.querySelector('.card-expanded').setAttribute('aria-hidden', 'true');
    }
  }
  if (isOpen) {
    card.classList.remove('open');
    card.querySelector('.card-collapsed').setAttribute('aria-expanded', 'false');
    card.querySelector('.card-expanded').classList.add('hidden');
    card.querySelector('.card-expanded').setAttribute('aria-hidden', 'true');
  } else {
    card.classList.add('open');
    card.querySelector('.card-collapsed').setAttribute('aria-expanded', 'true');
    const expPanel = card.querySelector('.card-expanded');
    expPanel.classList.remove('hidden');
    expPanel.setAttribute('aria-hidden', 'false');
    if (!expPanel.dataset.built) {
      buildExpanded(card, c);
      expPanel.dataset.built = '1';
    }
    card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }
}

function buildExpanded(card, c) {
  const expTitle  = card.querySelector('.expanded-title');
  const expDist   = card.querySelector('.expanded-distances');
  const expFontes = card.querySelector('.expanded-fontes');
  const expFotos  = card.querySelector('.expanded-fotos');

  expTitle.textContent = c.titulo;
  expTitle.classList.remove('hidden');

  if (c.distancias && c.distancias.length > 0) {
    const sorted      = sortDistancias(c.distancias);
    const uniqueDates = new Set(sorted.map(d => d.data || null).filter(Boolean));
    const uniqueTimes = new Set(sorted.map(d => d.horario || null).filter(Boolean));
    // Only show per-distance columns when values differ across distances —
    // otherwise the date/time is redundant with what's already on the card.
    const hasDate     = uniqueDates.size > 1;
    const hasHorario  = uniqueTimes.size > 1;

    const table = document.createElement('table');
    table.className = 'dist-table';
    let thead = `<thead><tr><th>${T.distancesHeader}</th>`;
    if (hasDate)    thead += `<th>${T.dateColHeader}</th>`;
    if (hasHorario) thead += `<th>${T.timeColHeader}</th>`;
    thead += '</tr></thead>';
    table.innerHTML = thead;

    const tbody = document.createElement('tbody');
    const seenKm = new Set();
    for (const d of sorted) {
      const label = formatKm(d.km);
      if (seenKm.has(label)) continue;
      seenKm.add(label);
      const tr  = document.createElement('tr');
      let cells = `<td>${label}</td>`;
      if (hasDate)    cells += `<td>${d.data ? formatDateShort(d.data) : '—'}</td>`;
      if (hasHorario) cells += `<td>${d.horario || '—'}</td>`;
      tr.innerHTML = cells;
      tbody.appendChild(tr);
    }
    table.appendChild(tbody);
    expDist.appendChild(table);
  }

  if (c.fontes && c.fontes.length > 0) {
    const h = document.createElement('p');
    h.className   = 'expanded-section-title';
    h.textContent = T.sourcesHeader;
    expFontes.appendChild(h);

    for (const fonte of c.fontes) {
      const row = document.createElement('div');
      row.className = 'fonte-row';

      const name = document.createElement('span');
      name.className   = 'fonte-name';
      name.textContent = fonte.nome || '';
      row.appendChild(name);

      if (fonte.links_inscricao && fonte.links_inscricao.length > 0) {
        for (const link of fonte.links_inscricao) {
          const a = document.createElement('a');
          a.href      = link;
          a.target    = '_blank';
          a.rel       = 'noopener noreferrer';
          a.className = 'btn-register';
          a.textContent = T.registerBtn;
          row.appendChild(a);
        }
      }
      expFontes.appendChild(row);
    }
  }

  if (c.fotos && c.fotos.length > 0) {
    for (const url of c.fotos) {
      const img = document.createElement('img');
      img.src     = url;
      img.alt     = '';
      img.loading = 'lazy';
      img.className = 'expanded-photo';
      expFotos.appendChild(img);
    }
  }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function formatMonth(yearMonth) {
  const [year, month] = yearMonth.split('-').map(Number);
  return `${T.monthNames[month - 1]} ${year}`;
}

function formatDateShort(iso) {
  if (!iso) return '—';
  const [y, m, d] = iso.split('-').map(Number);
  return `${String(d).padStart(2,'0')}/${String(m).padStart(2,'0')}/${y}`;
}

function formatDate(isoDate, horario, distancias) {
  if (!isoDate) return '';
  const dates = new Set(
    (distancias || []).map(d => d.data).filter(Boolean)
  );
  const hasPerDistDate = dates.size > 1;

  const [y, m, d] = isoDate.split('-').map(Number);
  const today = todayStr();
  const iso   = isoDate;

  let label;
  if (iso === today)                label = T.today_label;
  else if (iso === addDays(today,1)) label = T.tomorrow_label;
  else if (iso === addDays(today,-1)) label = T.yesterday_label;
  else {
    const dow = new Date(iso + 'T12:00:00').getDay();
    label = `${T.dayNames[dow]}, ${String(d).padStart(2,'0')}/${String(m).padStart(2,'0')}/${y}`;
  }

  if (!hasPerDistDate && horario) label += ` · ${horario}`;
  return label;
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
  const seen = new Set();
  return sortDistancias(distancias)
    .map(d => formatKm(d.km))
    .filter(label => { if (seen.has(label)) return false; seen.add(label); return true; });
}

function formatKm(km) {
  if (typeof km === 'string') return km;
  if (km === 42.195) return '42K';
  if (km === 21.097) return '21K';
  if (Number.isInteger(km)) return km + 'K';
  return km + 'K';
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
  resultCount.textContent = T.raceCount(filteredCorridas.length);
}

function isFiltersActive() {
  return (
    state.searchQuery !== '' ||
    state.activePills.size > 0 ||
    state.distMin !== null ||
    state.distMax !== null ||
    state.periodo !== 'past15' ||
    state.estado !== (_geoApplied || 'todos') ||
    state.fontes.size > 0
  );
}

function updateClearButton() {
  btnClear.classList.toggle('hidden', !isFiltersActive());
}

function clearFilters() {
  state.searchQuery = '';
  state.activePills.clear();
  state.distMode   = 'select';
  state.distMin    = null;
  state.distMax    = null;
  state.periodo    = 'past15';
  state.dateFrom   = null;
  state.dateTo     = null;
  state.estado     = _geoApplied || 'todos';
  state.fontes.clear();

  searchInput.value   = '';
  periodoSelect.value = 'past15';
  dateFrom.value = '';
  dateTo.value   = '';
  toggleCustomDateRow(false);

  modeSelect.classList.add('active');    modeSelect.setAttribute('aria-pressed', 'true');
  modeInterval.classList.remove('active'); modeInterval.setAttribute('aria-pressed', 'false');
  pillsContainer.classList.remove('hidden');
  intervalContainer.classList.add('hidden');
  distMin.value = '';
  distMax.value = '';

  for (const pill of pillsContainer.querySelectorAll('.pill')) {
    pill.setAttribute('aria-pressed', 'false');
    pill.classList.remove('active');
  }

  updateEstadoUI();
  updateFonteUI();
  onFilterChange();
}

function toggleCustomDateRow(show) {
  customDateRow.classList.toggle('hidden', !show);
}

// ---------------------------------------------------------------------------
// Event wiring
// ---------------------------------------------------------------------------
document.addEventListener('DOMContentLoaded', () => {
  // DOM refs
  searchInput         = document.getElementById('searchInput');
  cardsList           = document.getElementById('cardsList');
  emptyState          = document.getElementById('emptyState');
  btnClear            = document.getElementById('btnClear');
  btnClearEmpty       = document.getElementById('btnClearEmpty');
  periodoSelect       = document.getElementById('periodoSelect');
  estadoFilterBtn     = document.getElementById('estadoFilterBtn');
  estadoFilterLabel   = document.getElementById('estadoFilterLabel');
  estadoFilterDropdown = document.getElementById('estadoFilterDropdown');
  fonteFilterBtn      = document.getElementById('fonteFilterBtn');
  fonteFilterLabel    = document.getElementById('fonteFilterLabel');
  fonteFilterDropdown = document.getElementById('fonteFilterDropdown');
  resultCount         = document.getElementById('resultCount');
  filtersBar          = document.getElementById('filtersBar');
  btnRefresh          = document.getElementById('btnRefresh');
  btnLang             = document.getElementById('btnLang');
  btnHome             = document.getElementById('btnHome');
  modeSelect          = document.getElementById('modeSelect');
  modeInterval        = document.getElementById('modeInterval');
  pillsContainer      = document.getElementById('pillsContainer');
  intervalContainer   = document.getElementById('intervalContainer');
  distMin             = document.getElementById('distMin');
  distMax             = document.getElementById('distMax');
  customDateRow       = document.getElementById('customDateRow');
  dateFrom            = document.getElementById('dateFrom');
  dateTo              = document.getElementById('dateTo');

  // i18n static labels
  document.title = T.siteTitle;
  const headerTitle = document.querySelector('.app-title');
  if (headerTitle) headerTitle.textContent = T.headerTitle;
  searchInput.placeholder = T.searchPlaceholder;
  searchInput.setAttribute('aria-label', T.searchAriaLabel);
  modeSelect.textContent   = T.modeSelect;
  modeInterval.textContent = T.modeInterval;
  document.getElementById('labelDistFrom').textContent = T.labelDistFrom;
  document.getElementById('labelDistTo').textContent   = T.labelDistTo;
  document.getElementById('labelDateFrom').textContent = T.labelDateFrom;
  document.getElementById('labelDateTo').textContent   = T.labelDateTo;
  distMin.setAttribute('aria-label', T.distMinAriaLabel);
  distMax.setAttribute('aria-label', T.distMaxAriaLabel);
  dateFrom.setAttribute('aria-label', T.dateFromAriaLabel);
  dateTo.setAttribute('aria-label',   T.dateToAriaLabel);
  periodoSelect.setAttribute('aria-label', T.periodoAriaLabel);
  estadoFilterBtn.setAttribute('aria-label', T.estadoAriaLabel);
  fonteFilterBtn.setAttribute('aria-label',  T.fonteFilterAriaLabel);
  btnRefresh.setAttribute('aria-label', T.refreshAriaLabel);
  btnHome.setAttribute('aria-label',    T.homeAriaLabel);
  btnLang.setAttribute('aria-label',    T.langAriaLabel);
  btnClear.setAttribute('aria-label',       T.clearFiltersAriaLabel);
  btnClear.textContent      = T.clearFilters;
  btnClearEmpty.textContent = T.clearFilters;
  document.querySelector('#emptyState p').textContent = T.noResults;

  // Periodo options
  const periodoOpts = [
    ['past15', T.past15], ['today', T.today], ['30', T.next30],
    ['90', T.next90], ['180', T.next180], ['all', T.allTime], ['custom', T.custom],
  ];
  periodoSelect.innerHTML = periodoOpts.map(([v, l]) => `<option value="${v}">${l}</option>`).join('');

  // Distance pills
  for (const pill of pillsContainer.querySelectorAll('.pill')) {
    const key = pill.dataset.km;
    if (T.pills[key]) pill.textContent = T.pills[key];
  }

  // Event listeners
  searchInput.addEventListener('input', () => {
    state.searchQuery = searchInput.value.trim();
    onFilterChange();
  });

  periodoSelect.addEventListener('change', () => {
    state.periodo = periodoSelect.value;
    toggleCustomDateRow(state.periodo === 'custom');
    onFilterChange();
  });

  dateFrom.addEventListener('change', () => { state.dateFrom = dateFrom.value || null; onFilterChange(); });
  dateTo.addEventListener('change',   () => { state.dateTo   = dateTo.value   || null; onFilterChange(); });

  for (const pill of pillsContainer.querySelectorAll('.pill')) {
    pill.addEventListener('click', () => {
      const km = pill.dataset.km;
      if (state.activePills.has(km)) {
        state.activePills.delete(km);
        pill.setAttribute('aria-pressed', 'false');
        pill.classList.remove('active');
      } else {
        state.activePills.add(km);
        pill.setAttribute('aria-pressed', 'true');
        pill.classList.add('active');
      }
      onFilterChange();
    });
  }

  modeSelect.addEventListener('click', () => {
    if (state.distMode === 'select') return;
    state.distMode = 'select';
    state.distMin  = null;
    state.distMax  = null;
    distMin.value  = '';
    distMax.value  = '';
    modeSelect.classList.add('active');    modeSelect.setAttribute('aria-pressed', 'true');
    modeInterval.classList.remove('active'); modeInterval.setAttribute('aria-pressed', 'false');
    pillsContainer.classList.remove('hidden');
    intervalContainer.classList.add('hidden');
    onFilterChange();
  });

  modeInterval.addEventListener('click', () => {
    if (state.distMode === 'interval') return;
    state.distMode = 'interval';
    state.activePills.clear();
    for (const pill of pillsContainer.querySelectorAll('.pill')) {
      pill.setAttribute('aria-pressed', 'false');
      pill.classList.remove('active');
    }
    modeInterval.classList.add('active');  modeInterval.setAttribute('aria-pressed', 'true');
    modeSelect.classList.remove('active'); modeSelect.setAttribute('aria-pressed', 'false');
    intervalContainer.classList.remove('hidden');
    pillsContainer.classList.add('hidden');
    onFilterChange();
  });

  distMin.addEventListener('input', () => { state.distMin = distMin.value ? parseFloat(distMin.value) : null; onFilterChange(); });
  distMax.addEventListener('input', () => { state.distMax = distMax.value ? parseFloat(distMax.value) : null; onFilterChange(); });

  btnClear.addEventListener('click',      clearFilters);
  btnClearEmpty.addEventListener('click', clearFilters);

  btnRefresh.addEventListener('click', () => {
    allCorridas = [];
    filteredCorridas = [];
    cardsList.innerHTML = '';
    loadData();
  });

  btnLang.addEventListener('click', () => {
    const langs = Object.keys(LANG_URLS);
    const next  = langs[(langs.indexOf(LANG) + 1) % langs.length];
    sessionStorage.setItem('_geoCache', sessionStorage.getItem('_geoCache') || 'null');
    window.location.href = LANG_URLS[next];
  });

  btnHome.addEventListener('click', async () => {
    const geo = await detectGeoEstado();
    if (geo) {
      setEstado(geo);
      _geoApplied = geo;
    } else {
      setEstado('todos');
      _geoApplied = null;
    }
  });

  // Estado dropdown toggle
  estadoFilterBtn.addEventListener('click', e => {
    e.stopPropagation();
    const open = !estadoFilterDropdown.classList.contains('hidden');
    closeAllDropdowns();
    if (!open) {
      estadoFilterDropdown.classList.remove('hidden');
      estadoFilterBtn.setAttribute('aria-expanded', 'true');
    }
  });

  // Fonte dropdown toggle
  fonteFilterBtn.addEventListener('click', e => {
    e.stopPropagation();
    const open = !fonteFilterDropdown.classList.contains('hidden');
    closeAllDropdowns();
    if (!open) {
      fonteFilterDropdown.classList.remove('hidden');
      fonteFilterBtn.setAttribute('aria-expanded', 'true');
    }
  });

  document.addEventListener('click', closeAllDropdowns);

  function closeAllDropdowns() {
    estadoFilterDropdown.classList.add('hidden');
    estadoFilterBtn.setAttribute('aria-expanded', 'false');
    fonteFilterDropdown.classList.add('hidden');
    fonteFilterBtn.setAttribute('aria-expanded', 'false');
  }

  loadData();
});
