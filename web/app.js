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
    pastSectionLabel: '🏁 Corridas nos últimos 15 dias',
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
    registerBtn: 'Inscreva-se →',
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
    groupBrasil: 'Brasil',
    allCountry: country => `Todo ${country}`,
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
    pastSectionLabel: '🏁 Races in the last 15 days',
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
    registerBtn: 'Register →',
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
    groupBrasil: 'Brazil',
    allCountry: country => `All ${country}`,
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
    pastSectionLabel: '🏁 Carreras en los últimos 15 días',
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
    registerBtn: 'Inscribirse →',
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
    groupBrasil: 'Brasil',
    allCountry: country => `Todo ${country}`,
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
    pastSectionLabel: '🏁 Rennen der letzten 15 Tage',
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
    registerBtn: 'Anmelden →',
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
    groupBrasil: 'Brasilien',
    allCountry: country => `Ganz ${country}`,
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
    pastSectionLabel: '🏁 Courses des 15 derniers jours',
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
    registerBtn: "S'inscrire →",
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
    groupBrasil: 'Brésil',
    allCountry: country => `Tout le ${country}`,
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
    resultCount, btnRefresh, btnLang, btnHome,
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
let _userChoseLocation = false;
let _estadoAvailableValues = new Set(['todos']);
const _loadedLocations = new Map(); // iso2 → { name, subdivisions }

// ---------------------------------------------------------------------------
// Geolocation pipeline
// ---------------------------------------------------------------------------
async function detectGeoEstado({ force = false } = {}) {
  if (!force) {
    const cached = sessionStorage.getItem('_geoCache');
    // Evict stale values: must match new format 'XX:...' or be the sentinel 'null'
    if (cached && cached !== 'null' && !cached.match(/^[A-Z]{2}:/)) {
      sessionStorage.removeItem('_geoCache');
    } else if (cached) {
      return cached === 'null' ? null : cached;
    }
  } else {
    sessionStorage.removeItem('_geoCache');
  }

  const apis = [
    () => fetch('https://ipwho.is/').then(r => r.json()).then(d => [d.country_code, d.region_code]),
    () => fetch('https://freeipapi.com/api/json').then(r => r.json()).then(d => [d.countryCode, d.regionCode]),
    () => fetch('https://api.ip.sb/geoip').then(r => r.json()).then(d => [d.country_code, d.region_code]),
  ];
  for (const fn of apis) {
    try {
      const [countryCode, regionCode] = await fn();
      if (countryCode === 'BR') {
        // Brazilian user: return 'BR:<UF>' when region is known
        const region = (regionCode || '').replace(/^BR-/, '').trim();
        if (region && _ESTADO_LABELS[region]) {
          const val = 'BR:' + region;
          sessionStorage.setItem('_geoCache', val);
          return val;
        }
      } else if (countryCode) {
        // International user: return '<ISO2>:'
        const val = countryCode.toUpperCase() + ':';
        sessionStorage.setItem('_geoCache', val);
        return val;
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
  if (btnRefresh) btnRefresh.classList.add('spinning');
  try {
    const res = await fetch('/corridas.json');
    if (!res.ok) throw new Error(res.status);
    const json = await res.json();
    allCorridas = json.corridas || json;
    const paisSet = new Set(allCorridas.map(c => c.pais || 'BR').filter(Boolean));
    await loadLocationsData(paisSet);
    await initFilters();
  } catch (e) {
    resultCount.textContent = T.loadError;
    console.error('loadData error', e);
  } finally {
    if (btnRefresh) btnRefresh.classList.remove('spinning');
  }
}

async function loadLocationsData(paisSet) {
  await Promise.all([...paisSet].map(async iso2 => {
    if (_loadedLocations.has(iso2)) return;
    try {
      const r = await fetch(`../locations/${iso2}.json`);
      if (r.ok) _loadedLocations.set(iso2, await r.json());
    } catch (_) {}
  }));
}

// ---------------------------------------------------------------------------
// Filter initialisation
// ---------------------------------------------------------------------------
async function initFilters() {
  restoreFilters();
  populateEstadoFilter({ skipGeo: true });
  populateFontesFilter();

  // Geolocation (only if no persisted location preference)
  const saved = loadSavedFilters();
  if (!saved || !saved.estado) {
    const geo = await detectGeoEstado();
    if (geo && _estadoAvailableValues.has(geo)) {
      state.estado = geo;
      _geoApplied  = geo;
      _updateEstadoLabel();
      // Refresh selected state in accordion
      populateEstadoFilter({ skipGeo: true });
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
    let est = saved.estado;
    if (est !== 'todos') {
      if (est.startsWith('INT:')) {
        est = 'todos';
      } else if (!est.includes(':')) {
        est = est === 'BR' ? 'BR:' : 'BR:' + est;
      }
    }
    state.estado = est;
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
const _ESTADO_LABELS = {
  AC: 'Acre',              AL: 'Alagoas',            AM: 'Amazonas',
  AP: 'Amapá',             BA: 'Bahia',              CE: 'Ceará',
  DF: 'Brasília',          ES: 'Espírito Santo',     GO: 'Goiás',
  MA: 'Maranhão',          MG: 'Minas Gerais',       MS: 'Mato Grosso do Sul',
  MT: 'Mato Grosso',       PA: 'Pará',               PB: 'Paraíba',
  PE: 'Pernambuco',        PI: 'Piauí',              PR: 'Paraná',
  RJ: 'Rio de Janeiro',    RN: 'Rio Grande do Norte', RO: 'Rondônia',
  RR: 'Roraima',           RS: 'Rio Grande do Sul',  SC: 'Santa Catarina',
  SE: 'Sergipe',           SP: 'São Paulo',           TO: 'Tocantins',
};

const _CITY_COUNTRY = {
  // Well-known cities (no country suffix in cidade)
  'Buenos Aires': 'Argentina',   'Paris': 'França',          'Veneza': 'Itália',
  'Roma': 'Itália',              'Milão': 'Itália',          'Amsterdam': 'Países Baixos',
  'Madrid': 'Espanha',           'Barcelona': 'Espanha',     'Porto': 'Portugal',
  'Assunção': 'Paraguai',        'Montevidéu': 'Uruguai',    'Santiago': 'Chile',
  'Lima': 'Peru',                'Bogotá': 'Colômbia',       'Cidade do México': 'México',
  'Punta Del Este': 'Uruguai',   'Punta del Este': 'Uruguai',
  // Country-name fallback: when cidade has no comma (no city info available)
  'EUA': 'EUA',                  'México': 'México',         'Canadá': 'Canadá',
  'Alemanha': 'Alemanha',        'França': 'França',         'Itália': 'Itália',
  'Espanha': 'Espanha',          'Irlanda': 'Irlanda',       'Países Baixos': 'Países Baixos',
  'Austrália': 'Austrália',      'Reino Unido': 'Reino Unido', 'Portugal': 'Portugal',
  'Argentina': 'Argentina',      'Chile': 'Chile',           'Colômbia': 'Colômbia',
  'Uruguai': 'Uruguai',          'Peru': 'Peru',             'Paraguai': 'Paraguai',
};

const _ISO2_TO_DATA_COUNTRY = {
  AR: 'Argentina',  PT: 'Portugal',   IT: 'Itália',     DE: 'Alemanha',  FR: 'França',
  GB: 'Reino Unido', US: 'EUA',       JP: 'Japão',      AU: 'Austrália', ES: 'Espanha',
  CL: 'Chile',      CO: 'Colômbia',   MX: 'México',     PE: 'Peru',      NL: 'Países Baixos',
  AT: 'Áustria',    CH: 'Suíça',      SE: 'Suécia',     NO: 'Noruega',   DK: 'Dinamarca',
  FI: 'Finlândia',  PL: 'Polônia',    CZ: 'República Tcheca', ZA: 'África do Sul',
  KE: 'Quênia',     ET: 'Etiópia',    CN: 'China',      KR: 'Coreia do Sul', CA: 'Canadá',
  NZ: 'Nova Zelândia', PY: 'Paraguai', UY: 'Uruguai',
  IE: 'Irlanda',    GR: 'Grécia',     AD: 'Andorra',    BM: 'Bermuda',
  BO: 'Bolívia',    PH: 'Filipinas',  CG: 'República do Congo', BA: 'Bósnia e Herzegovina',
};

const _COUNTRY_NORMALIZE = {
  'Eua': 'EUA', 'eua': 'EUA', 'EuA': 'EUA',
  // ISO-2 codes that may appear in stale data before scraper fix
  'AD': 'Andorra',               'BM': 'Bermuda',
  'BO': 'Bolívia',               'PH': 'Filipinas',
  'CG': 'República do Congo',    'BA': 'Bósnia e Herzegovina',
  'GR': 'Grécia',                'AT': 'Áustria',
  'CH': 'Suíça',                 'SE': 'Suécia',
};

// Portuguese country name → per-language display name
const _COUNTRY_LABELS = {
  'EUA':                   { en: 'USA',                      es: 'EE.UU.',               de: 'USA',                       fr: 'États-Unis' },
  'México':                { en: 'Mexico',                   es: 'México',               de: 'Mexiko',                    fr: 'Mexique' },
  'Reino Unido':           { en: 'United Kingdom',           es: 'Reino Unido',          de: 'Vereinigtes Königreich',    fr: 'Royaume-Uni' },
  'Canadá':                { en: 'Canada',                   es: 'Canadá',               de: 'Kanada',                    fr: 'Canada' },
  'Alemanha':              { en: 'Germany',                  es: 'Alemania',             de: 'Deutschland',               fr: 'Allemagne' },
  'Japão':                 { en: 'Japan',                    es: 'Japón',                de: 'Japan',                     fr: 'Japon' },
  'África do Sul':         { en: 'South Africa',             es: 'Sudáfrica',            de: 'Südafrika',                 fr: 'Afrique du Sud' },
  'Suécia':                { en: 'Sweden',                   es: 'Suecia',               de: 'Schweden',                  fr: 'Suède' },
  'Austrália':             { en: 'Australia',                es: 'Australia',            de: 'Australien',                fr: 'Australie' },
  'Países Baixos':         { en: 'Netherlands',              es: 'Países Bajos',         de: 'Niederlande',               fr: 'Pays-Bas' },
  'Irlanda':               { en: 'Ireland',                  es: 'Irlanda',              de: 'Irland',                    fr: 'Irlande' },
  'Grécia':                { en: 'Greece',                   es: 'Grecia',               de: 'Griechenland',              fr: 'Grèce' },
  'Espanha':               { en: 'Spain',                    es: 'España',               de: 'Spanien',                   fr: 'Espagne' },
  'França':                { en: 'France',                   es: 'Francia',              de: 'Frankreich',                fr: 'France' },
  'Dinamarca':             { en: 'Denmark',                  es: 'Dinamarca',            de: 'Dänemark',                  fr: 'Danemark' },
  'Argentina':             { en: 'Argentina',                es: 'Argentina',            de: 'Argentinien',               fr: 'Argentine' },
  'Portugal':              { en: 'Portugal',                 es: 'Portugal',             de: 'Portugal',                  fr: 'Portugal' },
  'Itália':                { en: 'Italy',                    es: 'Italia',               de: 'Italien',                   fr: 'Italie' },
  'Áustria':               { en: 'Austria',                  es: 'Austria',              de: 'Österreich',                fr: 'Autriche' },
  'Suíça':                 { en: 'Switzerland',              es: 'Suiza',                de: 'Schweiz',                   fr: 'Suisse' },
  'Noruega':               { en: 'Norway',                   es: 'Noruega',              de: 'Norwegen',                  fr: 'Norvège' },
  'Polônia':               { en: 'Poland',                   es: 'Polonia',              de: 'Polen',                     fr: 'Pologne' },
  'República Tcheca':      { en: 'Czech Republic',           es: 'República Checa',      de: 'Tschechien',                fr: 'République tchèque' },
  'Finlândia':             { en: 'Finland',                  es: 'Finlandia',            de: 'Finnland',                  fr: 'Finlande' },
  'Quênia':                { en: 'Kenya',                    es: 'Kenia',                de: 'Kenia',                     fr: 'Kenya' },
  'Etiópia':               { en: 'Ethiopia',                 es: 'Etiopía',              de: 'Äthiopien',                 fr: 'Éthiopie' },
  'China':                 { en: 'China',                    es: 'China',                de: 'China',                     fr: 'Chine' },
  'Coreia do Sul':         { en: 'South Korea',              es: 'Corea del Sur',        de: 'Südkorea',                  fr: 'Corée du Sud' },
  'Colômbia':              { en: 'Colombia',                 es: 'Colombia',             de: 'Kolumbien',                 fr: 'Colombie' },
  'Peru':                  { en: 'Peru',                     es: 'Perú',                 de: 'Peru',                      fr: 'Pérou' },
  'Chile':                 { en: 'Chile',                    es: 'Chile',                de: 'Chile',                     fr: 'Chili' },
  'Uruguai':               { en: 'Uruguay',                  es: 'Uruguay',              de: 'Uruguay',                   fr: 'Uruguay' },
  'Paraguai':              { en: 'Paraguay',                 es: 'Paraguay',             de: 'Paraguay',                  fr: 'Paraguay' },
  'Nova Zelândia':         { en: 'New Zealand',              es: 'Nueva Zelanda',        de: 'Neuseeland',                fr: 'Nouvelle-Zélande' },
  'Brasil':                { en: 'Brazil',                   es: 'Brasil',               de: 'Brasilien',                 fr: 'Brésil' },
  'Andorra':               { en: 'Andorra',                  es: 'Andorra',              de: 'Andorra',                   fr: 'Andorre' },
  'Bermuda':               { en: 'Bermuda',                  es: 'Bermuda',              de: 'Bermuda',                   fr: 'Bermudes' },
  'Bolívia':               { en: 'Bolivia',                  es: 'Bolivia',              de: 'Bolivien',                  fr: 'Bolivie' },
  'Filipinas':             { en: 'Philippines',              es: 'Filipinas',            de: 'Philippinen',               fr: 'Philippines' },
  'República do Congo':    { en: 'Republic of the Congo',    es: 'República del Congo',  de: 'Republik Kongo',            fr: 'République du Congo' },
  'Bósnia e Herzegovina':  { en: 'Bosnia and Herzegovina',   es: 'Bosnia y Herzegovina', de: 'Bosnien und Herzegowina',   fr: 'Bosnie-Herzégovine' },
  'Índia':                 { en: 'India',                    es: 'India',                de: 'Indien',                    fr: 'Inde' },
  'Rússia':                { en: 'Russia',                   es: 'Rusia',                de: 'Russland',                  fr: 'Russie' },
};

// Subdivision translations: ISO2 country → subdivision code → per-language name.
// Only entries where the name differs meaningfully across languages are listed.
// Fallback: locations/{iso2}.json English name, then code.
const _SUBDIV_LABELS = {
  MX: {
    CMX: { pt: 'Cidade do México',              en: 'Mexico City',               es: 'Ciudad de México',                de: 'Mexiko-Stadt',                      fr: 'Mexico' },
    MEX: { pt: 'Estado do México',              en: 'State of Mexico',           es: 'Estado de México',                de: 'Bundesstaat Mexiko',                fr: 'État de Mexico' },
  },
  DE: {
    BY:  { pt: 'Baviera',                       en: 'Bavaria',                   es: 'Baviera',                         de: 'Bayern',                            fr: 'Bavière' },
    NW:  { pt: 'Renânia do Norte-Vestfália',    en: 'North Rhine-Westphalia',    es: 'Renania del Norte-Westfalia',     de: 'Nordrhein-Westfalen',               fr: 'Rhénanie-du-Nord-Westphalie' },
    NI:  { pt: 'Baixa Saxônia',                 en: 'Lower Saxony',              es: 'Baja Sajonia',                    de: 'Niedersachsen',                     fr: 'Basse-Saxe' },
    SN:  { pt: 'Saxônia',                       en: 'Saxony',                    es: 'Sajonia',                         de: 'Sachsen',                           fr: 'Saxe' },
    TH:  { pt: 'Turíngia',                      en: 'Thuringia',                 es: 'Turingia',                        de: 'Thüringen',                         fr: 'Thuringe' },
    RP:  { pt: 'Renânia-Palatinado',            en: 'Rhineland-Palatinate',      es: 'Renania-Palatinado',              de: 'Rheinland-Pfalz',                   fr: 'Rhénanie-Palatinat' },
    ST:  { pt: 'Saxônia-Anhalt',                en: 'Saxony-Anhalt',             es: 'Sajonia-Anhalt',                  de: 'Sachsen-Anhalt',                    fr: 'Saxe-Anhalt' },
    HE:  { pt: 'Hesse',                         en: 'Hesse',                     es: 'Hesse',                           de: 'Hessen',                            fr: 'Hesse' },
    BW:  { pt: 'Baden-Württemberg',             en: 'Baden-Württemberg',         es: 'Baden-Wurtemberg',                de: 'Baden-Württemberg',                 fr: 'Bade-Wurtemberg' },
    BB:  { pt: 'Brandemburgo',                  en: 'Brandenburg',               es: 'Brandeburgo',                     de: 'Brandenburg',                       fr: 'Brandebourg' },
    MV:  { pt: 'Mecklemburgo-Pomerânia Ocidental', en: 'Mecklenburg-Vorpommern', es: 'Mecklemburgo-Pomerania Occidental', de: 'Mecklenburg-Vorpommern',          fr: 'Mecklembourg-Poméranie-Occidentale' },
  },
  GB: {
    ENG: { pt: 'Inglaterra',                    en: 'England',                   es: 'Inglaterra',                      de: 'England',                           fr: 'Angleterre' },
    SCT: { pt: 'Escócia',                       en: 'Scotland',                  es: 'Escocia',                         de: 'Schottland',                        fr: 'Écosse' },
    WLS: { pt: 'País de Gales',                 en: 'Wales',                     es: 'Gales',                           de: 'Wales',                             fr: 'Pays de Galles' },
    NIR: { pt: 'Irlanda do Norte',              en: 'Northern Ireland',          es: 'Irlanda del Norte',               de: 'Nordirland',                        fr: 'Irlande du Nord' },
  },
  AT: {
    '9': { pt: 'Viena',                         en: 'Vienna',                    es: 'Viena',                           de: 'Wien',                              fr: 'Vienne' },
  },
  ES: {
    CT:  { pt: 'Catalunha',                     en: 'Catalonia',                 es: 'Cataluña',                        de: 'Katalonien',                        fr: 'Catalogne' },
    AN:  { pt: 'Andaluzia',                     en: 'Andalusia',                 es: 'Andalucía',                       de: 'Andalusien',                        fr: 'Andalousie' },
    MD:  { pt: 'Comunidade de Madri',           en: 'Community of Madrid',       es: 'Comunidad de Madrid',             de: 'Gemeinde Madrid',                   fr: 'Communauté de Madrid' },
    PV:  { pt: 'País Basco',                    en: 'Basque Country',            es: 'País Vasco',                      de: 'Baskenland',                        fr: 'Pays basque' },
    GA:  { pt: 'Galiza',                        en: 'Galicia',                   es: 'Galicia',                         de: 'Galicien',                          fr: 'Galice' },
    CL:  { pt: 'Castela e Leão',                en: 'Castile and León',          es: 'Castilla y León',                 de: 'Kastilien-León',                    fr: 'Castille-et-León' },
    CM:  { pt: 'Castela-La Mancha',             en: 'Castilla-La Mancha',        es: 'Castilla-La Mancha',              de: 'Kastilien-La Mancha',               fr: 'Castille-La Manche' },
    AR:  { pt: 'Aragão',                        en: 'Aragon',                    es: 'Aragón',                          de: 'Aragonien',                         fr: 'Aragon' },
    VC:  { pt: 'Comunidade Valenciana',         en: 'Valencian Community',       es: 'Comunidad Valenciana',            de: 'Valencianische Gemeinschaft',       fr: 'Communauté valencienne' },
    CN:  { pt: 'Ilhas Canárias',                en: 'Canary Islands',            es: 'Islas Canarias',                  de: 'Kanarische Inseln',                 fr: 'Îles Canaries' },
    NA:  { pt: 'Navarra',                       en: 'Navarre',                   es: 'Navarra',                         de: 'Navarra',                           fr: 'Navarre' },
  },
  CA: {
    QC:  { pt: 'Quebec',                        en: 'Quebec',                    es: 'Quebec',                          de: 'Québec',                            fr: 'Québec' },
    NB:  { pt: 'Novo Brunswick',                en: 'New Brunswick',             es: 'Nuevo Brunswick',                 de: 'Neubraunschweig',                   fr: 'Nouveau-Brunswick' },
    NS:  { pt: 'Nova Escócia',                  en: 'Nova Scotia',               es: 'Nueva Escocia',                   de: 'Neuschottland',                     fr: 'Nouvelle-Écosse' },
    NL:  { pt: 'Terra Nova e Labrador',         en: 'Newfoundland and Labrador', es: 'Terranova y Labrador',            de: 'Neufundland und Labrador',          fr: 'Terre-Neuve-et-Labrador' },
  },
  NL: {
    NH:  { pt: 'Holanda do Norte',              en: 'North Holland',             es: 'Holanda del Norte',               de: 'Nordholland',                       fr: 'Hollande-Septentrionale' },
    ZH:  { pt: 'Holanda do Sul',                en: 'South Holland',             es: 'Holanda del Sur',                 de: 'Südholland',                        fr: 'Hollande-Méridionale' },
    NB:  { pt: 'Brabante do Norte',             en: 'North Brabant',             es: 'Brabante del Norte',              de: 'Nordbrabant',                       fr: 'Brabant-Septentrional' },
  },
};

function _localizeCountry(ptName) {
  if (LANG === 'pt') return ptName;
  const t = _COUNTRY_LABELS[ptName];
  if (!t) return ptName;
  return t[LANG] || t.en || ptName;
}

function _localizeCountryByIso2(iso2) {
  const ptName = _ISO2_TO_DATA_COUNTRY[iso2];
  if (ptName) return _localizeCountry(ptName);
  return _loadedLocations.get(iso2)?.name ?? iso2;
}

function _localizeSubdiv(pais, code, fallback) {
  const t = _SUBDIV_LABELS[pais]?.[code];
  if (!t) return fallback;
  if (LANG === 'pt') return t.pt || fallback;
  return t[LANG] || t.en || fallback;
}

function _extractCountry(cidade) {
  if (!cidade) return null;
  const parts = cidade.split(',');
  if (parts.length > 1) {
    const raw = parts[parts.length - 1].trim();
    return _COUNTRY_NORMALIZE[raw] || raw;
  }
  return _CITY_COUNTRY[cidade.trim()] || null;
}

function _extractCity(cidade) {
  if (!cidade) return null;
  return cidade.split(',')[0].trim() || null;
}

function _closeEstadoDropdown() {
  estadoFilterDropdown.classList.add('hidden');
  estadoFilterBtn.setAttribute('aria-expanded', 'false');
}

function _closeFonteDropdown() {
  fonteFilterDropdown.classList.add('hidden');
  fonteFilterBtn.setAttribute('aria-expanded', 'false');
}

function _updateEstadoLabel() {
  const v = state.estado;
  if (v === 'todos') {
    estadoFilterLabel.textContent = T.allLocations;
    estadoFilterBtn.classList.remove('active');
    return;
  }
  const opt = estadoFilterDropdown.querySelector(`.estado-option[data-value="${CSS.escape(v)}"]`);
  if (opt) {
    estadoFilterLabel.textContent = opt.textContent;
  } else {
    const colon = v.indexOf(':');
    if (colon !== -1) {
      const pais   = v.slice(0, colon);
      const estado = v.slice(colon + 1);
      const localCountry = _localizeCountryByIso2(pais);
      if (!estado) {
        estadoFilterLabel.textContent = pais === 'BR' ? T.allBrazil : T.allCountry(localCountry);
      } else {
        const locData = _loadedLocations.get(pais);
        const sub = locData?.subdivisions?.find(s => s.code === estado);
        const brLabel = pais === 'BR' ? _ESTADO_LABELS[estado] : null;
        estadoFilterLabel.textContent = _localizeSubdiv(pais, estado, brLabel || (sub ? sub.name : estado));
      }
    } else {
      estadoFilterLabel.textContent = v;
    }
  }
  estadoFilterBtn.classList.remove('active');
}

function _makeAccordionGroup(label, initiallyOpen) {
  const wrapper = document.createElement('div');
  wrapper.className = 'estado-group';

  const header = document.createElement('div');
  header.className = 'estado-group-header';
  const labelSpan = document.createElement('span');
  labelSpan.textContent = label;
  const chevron = document.createElement('span');
  chevron.className = 'estado-group-chevron';
  chevron.setAttribute('aria-hidden', 'true');
  chevron.textContent = initiallyOpen ? '▾' : '▸';
  header.appendChild(labelSpan);
  header.appendChild(chevron);

  const body = document.createElement('div');
  body.className = 'estado-group-body';
  if (!initiallyOpen) body.classList.add('collapsed');

  header.addEventListener('click', () => {
    const isOpen = !body.classList.contains('collapsed');
    if (!isOpen) {
      estadoFilterDropdown.querySelectorAll('.estado-group-body').forEach(b => {
        if (b !== body && !b.classList.contains('collapsed')) {
          b.classList.add('collapsed');
          const otherChevron = b.previousElementSibling?.querySelector('.estado-group-chevron');
          if (otherChevron) otherChevron.textContent = '▸';
        }
      });
    }
    body.classList.toggle('collapsed', isOpen);
    chevron.textContent = isOpen ? '▸' : '▾';
  });

  wrapper.appendChild(header);
  wrapper.appendChild(body);
  return { wrapper, body };
}

function populateEstadoFilter({ skipGeo = false } = {}) {
  estadoFilterDropdown.innerHTML = '';
  _estadoAvailableValues = new Set(['todos']);
  const today = todayStr();

  const base = state.fontes.size === 0
    ? allCorridas
    : allCorridas.filter(c => matchesFonte(c));

  function makeOption(value, text) {
    _estadoAvailableValues.add(value);
    const el = document.createElement('div');
    el.className = 'estado-option' + (state.estado === value ? ' selected' : '');
    el.setAttribute('role', 'option');
    el.setAttribute('aria-selected', String(state.estado === value));
    el.dataset.value = value;
    el.textContent = text;
    el.addEventListener('click', () => {
      _userChoseLocation = (value !== 'todos');
      state.estado = value;
      estadoFilterDropdown.querySelectorAll('.estado-option').forEach(opt => {
        const sel = opt.dataset.value === value;
        opt.classList.toggle('selected', sel);
        opt.setAttribute('aria-selected', String(sel));
      });
      saveFilters();
      _closeEstadoDropdown();
      _updateEstadoLabel();
      populateFontesFilter();
      applyFilters();
      renderCards();
      updateCount();
      updateClearButton();
    });
    return el;
  }

  estadoFilterDropdown.appendChild(makeOption('todos', T.allLocations));

  // Collect (pais → Set of estado codes) from upcoming events
  const paisEstados = new Map();
  for (const c of base) {
    if (!c.data_evento || c.data_evento < today) continue;
    const pais = c.pais || 'BR';
    if (!paisEstados.has(pais)) paisEstados.set(pais, new Set());
    paisEstados.get(pais).add(c.estado || '');
  }

  const allGroups = [];

  for (const [pais, estadoSet] of paisEstados) {
    const locData = _loadedLocations.get(pais);
    const subdivByCode = {};
    for (const sub of (locData?.subdivisions || [])) subdivByCode[sub.code] = sub.name;

    const countryValue = pais + ':';
    const localCountryLabel = pais === 'BR' ? T.groupBrasil : _localizeCountryByIso2(pais);

    // Known subdivisions present in data, sorted by display name
    const _brLabel = s => pais === 'BR' ? _ESTADO_LABELS[s] : null;
    const subdivisions = [...estadoSet]
      .filter(s => s && (_brLabel(s) || subdivByCode[s]))
      .sort((a, b) => {
        const la = _localizeSubdiv(pais, a, _brLabel(a) || subdivByCode[a] || a);
        const lb = _localizeSubdiv(pais, b, _brLabel(b) || subdivByCode[b] || b);
        return la.localeCompare(lb, LANG);
      });
    const hasCountryLevel = estadoSet.has('') || [...estadoSet].some(s => !s || (!_brLabel(s) && !subdivByCode[s]));

    allGroups.push({ label: localCountryLabel, pais, build: () => {
      const isActive = state.estado === countryValue || state.estado.startsWith(pais + ':');
      const { wrapper, body } = _makeAccordionGroup(localCountryLabel, isActive);
      const allLabel = pais === 'BR' ? T.allBrazil : T.allCountry(_localizeCountryByIso2(pais));
      body.appendChild(makeOption(countryValue, allLabel));
      for (const code of subdivisions) {
        const label = _localizeSubdiv(pais, code, _brLabel(code) || subdivByCode[code] || code);
        body.appendChild(makeOption(pais + ':' + code, label));
      }
      return wrapper;
    }});
  }

  allGroups.sort((a, b) => a.label.localeCompare(b.label, LANG));
  for (const grp of allGroups) estadoFilterDropdown.appendChild(grp.build());

  if (state.estado !== 'todos' && !_estadoAvailableValues.has(state.estado)) {
    state.estado = 'todos';
    saveFilters();
  }

  _updateEstadoLabel();
}

// ---------------------------------------------------------------------------
// Fonte filter (multi-select checkboxes, shows only available sources)
// ---------------------------------------------------------------------------
function populateFontesFilter() {
  const today = todayStr();
  const base = allCorridas.filter(c =>
    c.data_evento >= today && _matchEstadoValue(c, state.estado)
  );
  const availableNomes = new Set(base.flatMap(c => (c.fontes || []).map(f => f.nome)));

  let stateChanged = false;
  for (const nome of [...state.fontes]) {
    if (!availableNomes.has(nome)) { state.fontes.delete(nome); stateChanged = true; }
  }
  if (stateChanged) saveFilters();

  fonteFilterDropdown.innerHTML = '';
  for (const nome of [...availableNomes].sort()) {
    const label = document.createElement('label');
    label.className = 'fonte-filter-option' + (state.fontes.has(nome) ? ' checked' : '');
    label.setAttribute('role', 'option');
    label.setAttribute('aria-selected', String(state.fontes.has(nome)));

    const cb = document.createElement('input');
    cb.type = 'checkbox';
    cb.value = nome;
    cb.checked = state.fontes.has(nome);

    label.appendChild(cb);
    label.appendChild(document.createTextNode(nome));

    cb.addEventListener('change', () => {
      if (cb.checked) { state.fontes.add(nome); label.classList.add('checked'); label.setAttribute('aria-selected', 'true'); }
      else { state.fontes.delete(nome); label.classList.remove('checked'); label.setAttribute('aria-selected', 'false'); }
      _updateFonteLabel();
      saveFilters();
      const prevEstado = state.estado;
      populateEstadoFilter({ skipGeo: true });
      if (state.estado !== prevEstado) populateFontesFilter();
      applyFilters();
      renderCards();
      updateCount();
      updateClearButton();
    });

    fonteFilterDropdown.appendChild(label);
  }
  _updateFonteLabel();
}

function _updateFonteLabel() {
  const n = state.fontes.size;
  if (n === 0) {
    fonteFilterLabel.textContent = T.allSources;
    fonteFilterBtn.classList.remove('active');
  } else if (n === 1) {
    fonteFilterLabel.textContent = [...state.fontes][0];
    fonteFilterBtn.classList.add('active');
  } else {
    fonteFilterLabel.textContent = T.nSources(n);
    fonteFilterBtn.classList.add('active');
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

function _matchEstadoValue(c, value) {
  if (value === 'todos') return true;
  const colonIdx = value.indexOf(':');
  if (colonIdx === -1) return false;
  const pais   = value.slice(0, colonIdx);
  const estado = value.slice(colonIdx + 1);
  if ((c.pais || 'BR') !== pais) return false;
  if (estado === '') return true;
  return c.estado === estado;
}

function matchesEstado(c) {
  return _matchEstadoValue(c, state.estado);
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

  const today       = todayStr();
  const sevenDaysAgo = addDays(today, -3);
  const frag        = document.createDocumentFragment();

  let toRender   = filteredCorridas;
  let recentPast = [];

  if (state.periodo === 'past15') {
    recentPast = filteredCorridas.filter(c => c.data_evento && c.data_evento < today);
    toRender   = filteredCorridas.filter(c => !c.data_evento || c.data_evento >= today);
  }

  const byMonth = new Map();
  for (const corrida of toRender) {
    const key = corrida.data_evento ? corrida.data_evento.slice(0, 7) : '__sem_data';
    if (!byMonth.has(key)) byMonth.set(key, []);
    byMonth.get(key).push(corrida);
  }

  let firstFutureMonthFound = false;
  for (const [monthKey, corridas] of byMonth) {
    const hasFuture = corridas.some(c => !c.data_evento || c.data_evento >= today);
    const expand = hasFuture && !firstFutureMonthFound;
    if (expand) firstFutureMonthFound = true;
    const hasNew = corridas.some(c => c.first_seen_at && c.first_seen_at >= sevenDaysAgo);
    const { section, cardsContainer } = buildMonthSection(monthKey, corridas.length, expand, hasNew);
    for (const corrida of corridas) {
      cardsContainer.appendChild(buildCard(corrida, today, sevenDaysAgo));
    }
    frag.appendChild(section);
  }

  if (recentPast.length > 0) {
    frag.prepend(buildPastSection(recentPast, today, sevenDaysAgo));
  }

  cardsList.appendChild(frag);
}

function buildPastSection(corridas, today, sevenDaysAgo) {
  const sorted = [...corridas].sort((a, b) =>
    (b.data_evento || '').localeCompare(a.data_evento || ''));

  const countLabel = T.raceCount(sorted.length);
  const section    = document.createElement('div');
  section.className = 'month-section';

  const btn = document.createElement('button');
  btn.className = 'month-separator month-separator--past';
  btn.setAttribute('aria-expanded', 'false');
  btn.setAttribute('aria-label', `${T.pastSectionLabel}, ${countLabel}`);
  btn.innerHTML = `
    <span class="month-separator-label">${T.pastSectionLabel}</span>
    <span class="month-count">${countLabel}</span>
    <span class="month-chevron" aria-hidden="true">▸</span>`;

  const cardsContainer = document.createElement('div');
  cardsContainer.className = 'month-cards month-cards--collapsed';

  for (const corrida of sorted) {
    cardsContainer.appendChild(buildCard(corrida, today, sevenDaysAgo));
  }

  btn.addEventListener('click', () => {
    const collapsed = cardsContainer.classList.toggle('month-cards--collapsed');
    btn.setAttribute('aria-expanded', String(!collapsed));
    btn.querySelector('.month-chevron').textContent = collapsed ? '▸' : '▾';
  });

  section.appendChild(btn);
  section.appendChild(cardsContainer);
  return section;
}

function buildMonthSection(monthKey, count, expanded = false, hasNew = false) {
  const label      = monthKey === '__sem_data' ? '—' : formatMonth(monthKey);
  const countLabel = T.raceCount(count);
  const novoBadge  = hasNew ? `<span class="badge-novo">${T.badgeNovo}</span>` : '';

  const section = document.createElement('div');
  section.className = 'month-section';

  const btn = document.createElement('button');
  btn.className = 'month-separator';
  btn.setAttribute('aria-expanded', String(expanded));
  btn.setAttribute('aria-label', `${label}, ${countLabel}`);
  btn.innerHTML = `
    <span class="month-separator-label">${label}</span>
    ${novoBadge}
    <span class="month-count">${countLabel}</span>
    <span class="month-chevron" aria-hidden="true">${expanded ? '▾' : '▸'}</span>`;

  const cardsContainer = document.createElement('div');
  cardsContainer.className = expanded ? 'month-cards' : 'month-cards month-cards--collapsed';

  btn.addEventListener('click', () => {
    const collapsed = cardsContainer.classList.toggle('month-cards--collapsed');
    btn.setAttribute('aria-expanded', String(!collapsed));
    btn.querySelector('.month-chevron').textContent = collapsed ? '▸' : '▾';
  });

  section.appendChild(btn);
  section.appendChild(cardsContainer);
  return { section, cardsContainer };
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
      const div = document.createElement('div');
      div.className = 'fonte-item';
      const link = (fonte.links_inscricao && fonte.links_inscricao.length > 0)
        ? fonte.links_inscricao[0] : null;
      const btnHtml = link
        ? `<a href="${link}" target="_blank" rel="noopener noreferrer" class="btn-inscricao">${T.registerBtn}</a>`
        : '';
      div.innerHTML = `<span class="fonte-nome-text">${fonte.nome || ''}</span>${btnHtml}`;
      expFontes.appendChild(div);
    }
  }

  // fotos rendering out of scope for now
  // if (c.fotos && c.fotos.length > 0) {
  //   for (const foto of c.fotos) {
  //     const img = document.createElement('img');
  //     img.src       = foto.url;
  //     img.alt       = foto.plataforma || '';
  //     img.loading   = 'lazy';
  //     img.className = 'expanded-photo';
  //     expFotos.appendChild(img);
  //   }
  // }
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

const _LOCALE_MAP = { pt: 'pt-BR', en: 'en-US', es: 'es-ES', de: 'de-DE', fr: 'fr-FR' };

function formatDate(isoDate, horario, distancias) {
  if (!isoDate) return '';
  const dates = new Set(
    (distancias || []).map(d => d.data).filter(Boolean)
  );
  const hasPerDistDate = dates.size > 1;

  const today = todayStr();
  const iso   = isoDate;

  let label;
  if (iso === today)                label = T.today_label;
  else if (iso === addDays(today,1)) label = T.tomorrow_label;
  else if (iso === addDays(today,-1)) label = T.yesterday_label;
  else {
    const dow = new Date(iso + 'T12:00:00').getDay();
    const dateStr = new Date(iso + 'T12:00:00').toLocaleDateString(_LOCALE_MAP[LANG] || 'en-US', { day: 'numeric', month: 'long', year: 'numeric' });
    label = `${T.dayNames[dow]}, ${dateStr}`;
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

  _userChoseLocation = false;
  populateEstadoFilter({ skipGeo: true });
  populateFontesFilter();
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

  const _LANG_LABELS = { pt: 'Português', en: 'English', es: 'Español', de: 'Deutsch', fr: 'Français' };
  let _langDropdown = null;

  function _closeLangDropdown() {
    if (_langDropdown) { _langDropdown.remove(); _langDropdown = null; }
  }

  btnLang.addEventListener('click', e => {
    e.stopPropagation();
    if (_langDropdown) { _closeLangDropdown(); return; }

    const dd = document.createElement('div');
    dd.className = 'lang-dropdown';

    const sorted = [
      [LANG, _LANG_LABELS[LANG]],
      ...Object.entries(_LANG_LABELS).filter(([c]) => c !== LANG).sort((a, b) => a[1].localeCompare(b[1])),
    ];
    for (const [code, label] of sorted) {
      const btn = document.createElement('button');
      btn.className = 'lang-option' + (code === LANG ? ' lang-option-active' : '');
      btn.textContent = label;
      btn.addEventListener('click', () => {
        _closeLangDropdown();
        if (code !== LANG) {
          sessionStorage.setItem('_geoCache', sessionStorage.getItem('_geoCache') || 'null');
          window.location.href = LANG_URLS[code];
        }
      });
      dd.appendChild(btn);
    }

    _langDropdown = dd;
    document.body.appendChild(dd);
    const r = btnLang.getBoundingClientRect();
    dd.style.top   = (r.bottom + 4) + 'px';
    dd.style.right = (window.innerWidth - r.right) + 'px';

    setTimeout(() => document.addEventListener('click', _closeLangDropdown, { once: true }), 0);
  });

  btnHome.addEventListener('click', async () => {
    // Always do a fresh geo lookup — bypass stale cache
    const geo = await detectGeoEstado({ force: true });

    // Apply location to current page
    _userChoseLocation = false;
    state.estado = geo || 'todos';
    _geoApplied  = geo || null;
    _closeEstadoDropdown();
    populateEstadoFilter({ skipGeo: true });
    populateFontesFilter();
    applyFilters();
    renderCards();
    updateCount();
    updateClearButton();
    saveFilters();

    // Switch to browser language if different
    const targetLang = BROWSER_LANG;
    if (targetLang !== LANG) {
      try {
        const saved = JSON.parse(localStorage.getItem('corridas_filters') || 'null');
        if (saved) { delete saved.estado; localStorage.setItem('corridas_filters', JSON.stringify(saved)); }
      } catch (_) {}
      window.location.href = LANG_URLS[targetLang];
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

  // Fonte dropdown toggle — stopPropagation on the dropdown itself keeps it open on checkbox clicks
  fonteFilterBtn.addEventListener('click', e => {
    e.stopPropagation();
    const open = !fonteFilterDropdown.classList.contains('hidden');
    closeAllDropdowns();
    if (!open) {
      fonteFilterDropdown.classList.remove('hidden');
      fonteFilterBtn.setAttribute('aria-expanded', 'true');
    }
  });
  estadoFilterDropdown.addEventListener('click', e => e.stopPropagation());
  fonteFilterDropdown.addEventListener('click', e => e.stopPropagation());

  document.addEventListener('click', closeAllDropdowns);

  function closeAllDropdowns() {
    _closeEstadoDropdown();
    _closeFonteDropdown();
  }

  loadData();
});
