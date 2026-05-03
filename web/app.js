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
    clearFiltersAriaLabel: 'Limpar filtros',
    allLocations: 'Todos',
    allBrazil: 'Todo o Brasil',
    allSources: 'Todas as fontes',
    nSources: n => n === 1 ? `${n} fonte` : `${n} fontes`,
    badgeNovo: 'novo',
    loading: 'Carregando...',
    loadError: 'Erro ao carregar dados.',
    clearFilters: 'Limpar filtros',
    noRacesMsg: 'Nenhuma corrida encontrada com os filtros atuais.',
    raceCount: n => n === 1 ? '1 corrida encontrada' : `${n} corridas encontradas`,
    raceCountLabel: n => n === 1 ? '1 corrida' : `${n} corridas`,
    dateTBD: 'Data a confirmar',
    months: ['jan','fev','mar','abr','mai','jun','jul','ago','set','out','nov','dez'],
    monthsFull: ['Janeiro','Fevereiro','Março','Abril','Maio','Junho','Julho','Agosto','Setembro','Outubro','Novembro','Dezembro'],
    weekdays: ['Dom','Seg','Ter','Qua','Qui','Sex','Sáb'],
    dateFullFormat: (wd, d, m, y) => `${wd}, ${d} de ${m} de ${y}`,
    dateRangeSameMonth: (d1, d2, m, y) => `${d1} a ${d2} de ${m} de ${y}`,
    dateRangeDiff: (d1, m1, d2, m2, y) => `${d1} de ${m1} a ${d2} de ${m2} de ${y}`,
    pastSectionLabel: '🏁 Corridas nos últimos 15 dias',
    distancesHeader: 'Distâncias',
    dateColHeader: 'Data',
    timeColHeader: 'Horário',
    registrationPeriod: 'Período de inscrição',
    regOpening: 'Abertura',
    regClosing: 'Encerramento',
    sourcesSection: 'Fontes',
    photosSection: 'Fotos',
    registerBtn: 'Inscrever-se →',
    groupBrasil: 'Brasil',
    allCountry: country => `Todo ${country}`,
    periodOptions: [
      { value: 'past15', label: 'Desde 15 dias atrás' },
      { value: 'today',  label: 'A partir de hoje' },
      { value: '30',     label: 'Próximos 30 dias' },
      { value: '90',     label: 'Próximos 3 meses' },
      { value: '180',    label: 'Próximos 6 meses' },
      { value: 'all',    label: 'Todo o período' },
      { value: 'custom', label: 'Intervalo personalizado' },
    ],
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
    clearFiltersAriaLabel: 'Clear filters',
    allLocations: 'All',
    allBrazil: 'All Brazil',
    allSources: 'All sources',
    nSources: n => n === 1 ? `${n} source` : `${n} sources`,
    badgeNovo: 'new',
    loading: 'Loading...',
    loadError: 'Error loading data.',
    clearFilters: 'Clear filters',
    noRacesMsg: 'No races found with current filters.',
    raceCount: n => n === 1 ? '1 race found' : `${n} races found`,
    raceCountLabel: n => n === 1 ? '1 race' : `${n} races`,
    dateTBD: 'Date TBD',
    months: ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'],
    monthsFull: ['January','February','March','April','May','June','July','August','September','October','November','December'],
    weekdays: ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'],
    dateFullFormat: (wd, d, m, y) => `${wd}, ${m} ${d}, ${y}`,
    dateRangeSameMonth: (d1, d2, m, y) => `${m} ${d1}–${d2}, ${y}`,
    dateRangeDiff: (d1, m1, d2, m2, y) => `${m1} ${d1} – ${m2} ${d2}, ${y}`,
    pastSectionLabel: '🏁 Races in the last 15 days',
    distancesHeader: 'Distances',
    dateColHeader: 'Date',
    timeColHeader: 'Time',
    registrationPeriod: 'Registration period',
    regOpening: 'Opening',
    regClosing: 'Closing',
    sourcesSection: 'Sources',
    photosSection: 'Photos',
    registerBtn: 'Register →',
    groupBrasil: 'Brazil',
    allCountry: country => `All ${country}`,
    periodOptions: [
      { value: 'past15', label: 'Since 15 days ago' },
      { value: 'today',  label: 'From today' },
      { value: '30',     label: 'Next 30 days' },
      { value: '90',     label: 'Next 3 months' },
      { value: '180',    label: 'Next 6 months' },
      { value: 'all',    label: 'All time' },
      { value: 'custom', label: 'Custom range' },
    ],
    places: {
      'Reino Unido': 'United Kingdom', 'EUA': 'USA', 'Estados Unidos': 'USA',
      'Japão': 'Japan', 'Alemanha': 'Germany', 'França': 'France',
      'Austrália': 'Australia', 'Países Baixos': 'Netherlands', 'Itália': 'Italy',
      'Espanha': 'Spain', 'Paraguai': 'Paraguay', 'Uruguai': 'Uruguay',
      'Dinamarca': 'Denmark', 'Suécia': 'Sweden', 'Noruega': 'Norway',
      'Irlanda': 'Ireland', 'República Tcheca': 'Czech Republic',
      'Grécia': 'Greece', 'Colômbia': 'Colombia', 'México': 'Mexico',
      'África do Sul': 'South Africa', 'Quênia': 'Kenya', 'Etiópia': 'Ethiopia',
      'Coreia do Sul': 'South Korea', 'Canadá': 'Canada', 'Nova Zelândia': 'New Zealand',
      'Áustria': 'Austria', 'Suíça': 'Switzerland', 'Polônia': 'Poland',
      'Edimburgo': 'Edinburgh', 'Tóquio': 'Tokyo', 'Londres': 'London',
      'Berlim': 'Berlin', 'Valência': 'Valencia',
      'Nova York': 'New York', 'Amsterdã': 'Amsterdam', 'Copenhague': 'Copenhagen',
      'Estocolmo': 'Stockholm', 'Praga': 'Prague', 'Atenas': 'Athens',
      'Milão': 'Milan', 'Veneza': 'Venice', 'Assunção': 'Asunción',
      'Lisboa': 'Lisbon', 'Moscou': 'Moscow',
    },
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
    clearFiltersAriaLabel: 'Limpiar filtros',
    allLocations: 'Todos',
    allBrazil: 'Todo Brasil',
    allSources: 'Todas las fuentes',
    nSources: n => n === 1 ? `${n} fuente` : `${n} fuentes`,
    badgeNovo: 'nuevo',
    loading: 'Cargando...',
    loadError: 'Error al cargar datos.',
    clearFilters: 'Limpiar filtros',
    noRacesMsg: 'No se encontraron carreras con los filtros actuales.',
    raceCount: n => n === 1 ? '1 carrera encontrada' : `${n} carreras encontradas`,
    raceCountLabel: n => n === 1 ? '1 carrera' : `${n} carreras`,
    dateTBD: 'Fecha por confirmar',
    months: ['ene','feb','mar','abr','may','jun','jul','ago','sep','oct','nov','dic'],
    monthsFull: ['Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre'],
    weekdays: ['Dom','Lun','Mar','Mié','Jue','Vie','Sáb'],
    dateFullFormat: (wd, d, m, y) => `${wd}, ${d} de ${m} de ${y}`,
    dateRangeSameMonth: (d1, d2, m, y) => `${d1} al ${d2} de ${m} de ${y}`,
    dateRangeDiff: (d1, m1, d2, m2, y) => `${d1} de ${m1} al ${d2} de ${m2} de ${y}`,
    pastSectionLabel: '🏁 Carreras en los últimos 15 días',
    distancesHeader: 'Distancias',
    dateColHeader: 'Fecha',
    timeColHeader: 'Hora',
    registrationPeriod: 'Período de inscripción',
    regOpening: 'Apertura',
    regClosing: 'Cierre',
    sourcesSection: 'Fuentes',
    photosSection: 'Fotos',
    registerBtn: 'Inscribirse →',
    groupBrasil: 'Brasil',
    allCountry: country => `Todo ${country}`,
    periodOptions: [
      { value: 'past15', label: 'Desde hace 15 días' },
      { value: 'today',  label: 'Desde hoy' },
      { value: '30',     label: 'Próximos 30 días' },
      { value: '90',     label: 'Próximos 3 meses' },
      { value: '180',    label: 'Próximos 6 meses' },
      { value: 'all',    label: 'Todo el período' },
      { value: 'custom', label: 'Intervalo personalizado' },
    ],
    places: {
      'Reino Unido': 'Reino Unido', 'EUA': 'EE.UU.', 'Estados Unidos': 'EE.UU.',
      'Japão': 'Japón', 'Alemanha': 'Alemania', 'França': 'Francia',
      'Austrália': 'Australia', 'Países Baixos': 'Países Bajos', 'Itália': 'Italia',
      'Espanha': 'España', 'Paraguai': 'Paraguay', 'Uruguai': 'Uruguay',
      'Dinamarca': 'Dinamarca', 'Suécia': 'Suecia', 'Noruega': 'Noruega',
      'Irlanda': 'Irlanda', 'República Tcheca': 'República Checa',
      'Grécia': 'Grecia', 'Colômbia': 'Colombia', 'México': 'México',
      'África do Sul': 'Sudáfrica', 'Quênia': 'Kenia', 'Etiópia': 'Etiopía',
      'Coreia do Sul': 'Corea del Sur', 'Canadá': 'Canadá', 'Nova Zelândia': 'Nueva Zelanda',
      'Áustria': 'Austria', 'Suíça': 'Suiza', 'Polônia': 'Polonia',
      'Edimburgo': 'Edimburgo', 'Tóquio': 'Tokio', 'Londres': 'Londres',
      'Berlim': 'Berlín', 'Valência': 'Valencia', 'Dublin': 'Dublín',
      'Nova York': 'Nueva York', 'Amsterdã': 'Ámsterdam', 'Copenhague': 'Copenhague',
      'Estocolmo': 'Estocolmo', 'Praga': 'Praga', 'Atenas': 'Atenas',
      'Milão': 'Milán', 'Veneza': 'Venecia', 'Assunção': 'Asunción',
      'Lisboa': 'Lisboa', 'Moscou': 'Moscú',
    },
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
    clearFiltersAriaLabel: 'Filter löschen',
    allLocations: 'Alle',
    allBrazil: 'Ganz Brasilien',
    allSources: 'Alle Quellen',
    nSources: n => n === 1 ? `${n} Quelle` : `${n} Quellen`,
    badgeNovo: 'neu',
    loading: 'Laden...',
    loadError: 'Fehler beim Laden der Daten.',
    clearFilters: 'Filter löschen',
    noRacesMsg: 'Keine Rennen mit den aktuellen Filtern gefunden.',
    raceCount: n => n === 1 ? '1 Rennen gefunden' : `${n} Rennen gefunden`,
    raceCountLabel: n => n === 1 ? '1 Rennen' : `${n} Rennen`,
    dateTBD: 'Datum noch offen',
    months: ['Jan','Feb','Mär','Apr','Mai','Jun','Jul','Aug','Sep','Okt','Nov','Dez'],
    monthsFull: ['Januar','Februar','März','April','Mai','Juni','Juli','August','September','Oktober','November','Dezember'],
    weekdays: ['So','Mo','Di','Mi','Do','Fr','Sa'],
    dateFullFormat: (wd, d, m, y) => `${wd}, ${d}. ${m} ${y}`,
    dateRangeSameMonth: (d1, d2, m, y) => `${d1}.–${d2}. ${m} ${y}`,
    dateRangeDiff: (d1, m1, d2, m2, y) => `${d1}. ${m1} – ${d2}. ${m2} ${y}`,
    pastSectionLabel: '🏁 Rennen der letzten 15 Tage',
    distancesHeader: 'Distanzen',
    dateColHeader: 'Datum',
    timeColHeader: 'Uhrzeit',
    registrationPeriod: 'Anmeldezeitraum',
    regOpening: 'Öffnung',
    regClosing: 'Schließung',
    sourcesSection: 'Quellen',
    photosSection: 'Fotos',
    registerBtn: 'Anmelden →',
    groupBrasil: 'Brasilien',
    allCountry: country => `Ganz ${country}`,
    periodOptions: [
      { value: 'past15', label: 'Seit 15 Tagen' },
      { value: 'today',  label: 'Ab heute' },
      { value: '30',     label: 'Nächste 30 Tage' },
      { value: '90',     label: 'Nächste 3 Monate' },
      { value: '180',    label: 'Nächste 6 Monate' },
      { value: 'all',    label: 'Gesamter Zeitraum' },
      { value: 'custom', label: 'Benutzerdefinierter Zeitraum' },
    ],
    places: {
      'Reino Unido': 'Vereinigtes Königreich', 'EUA': 'USA', 'Estados Unidos': 'USA',
      'Japão': 'Japan', 'Alemanha': 'Deutschland', 'França': 'Frankreich',
      'Austrália': 'Australien', 'Países Baixos': 'Niederlande', 'Itália': 'Italien',
      'Espanha': 'Spanien', 'Paraguai': 'Paraguay', 'Uruguai': 'Uruguay',
      'Dinamarca': 'Dänemark', 'Suécia': 'Schweden', 'Noruega': 'Norwegen',
      'Irlanda': 'Irland', 'República Tcheca': 'Tschechien',
      'Grécia': 'Griechenland', 'Colômbia': 'Kolumbien', 'México': 'Mexiko',
      'África do Sul': 'Südafrika', 'Quênia': 'Kenia', 'Etiópia': 'Äthiopien',
      'Coreia do Sul': 'Südkorea', 'Canadá': 'Kanada', 'Nova Zelândia': 'Neuseeland',
      'Áustria': 'Österreich', 'Suíça': 'Schweiz', 'Polônia': 'Polen',
      'Edimburgo': 'Edinburgh', 'Tóquio': 'Tokio', 'Londres': 'London',
      'Berlim': 'Berlin', 'Valência': 'Valencia',
      'Nova York': 'New York', 'Amsterdã': 'Amsterdam', 'Copenhague': 'Kopenhagen',
      'Estocolmo': 'Stockholm', 'Praga': 'Prag', 'Atenas': 'Athen',
      'Milão': 'Mailand', 'Veneza': 'Venedig', 'Assunção': 'Asunción',
      'Lisboa': 'Lissabon', 'Moscou': 'Moskau',
    },
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
    clearFiltersAriaLabel: 'Effacer les filtres',
    allLocations: 'Tous',
    allBrazil: 'Tout le Brésil',
    allSources: 'Toutes les sources',
    nSources: n => n === 1 ? `${n} source` : `${n} sources`,
    badgeNovo: 'nouveau',
    loading: 'Chargement...',
    loadError: 'Erreur lors du chargement des données.',
    clearFilters: 'Effacer les filtres',
    noRacesMsg: 'Aucune course trouvée avec les filtres actuels.',
    raceCount: n => n === 1 ? '1 course trouvée' : `${n} courses trouvées`,
    raceCountLabel: n => n === 1 ? '1 course' : `${n} courses`,
    dateTBD: 'Date à confirmer',
    months: ['jan','fév','mar','avr','mai','jun','jul','aoû','sep','oct','nov','déc'],
    monthsFull: ['Janvier','Février','Mars','Avril','Mai','Juin','Juillet','Août','Septembre','Octobre','Novembre','Décembre'],
    weekdays: ['Dim','Lun','Mar','Mer','Jeu','Ven','Sam'],
    dateFullFormat: (wd, d, m, y) => `${wd} ${d} ${m} ${y}`,
    dateRangeSameMonth: (d1, d2, m, y) => `${d1}–${d2} ${m} ${y}`,
    dateRangeDiff: (d1, m1, d2, m2, y) => `${d1} ${m1} – ${d2} ${m2} ${y}`,
    pastSectionLabel: '🏁 Courses des 15 derniers jours',
    distancesHeader: 'Distances',
    dateColHeader: 'Date',
    timeColHeader: 'Heure',
    registrationPeriod: "Période d'inscription",
    regOpening: 'Ouverture',
    regClosing: 'Clôture',
    sourcesSection: 'Sources',
    photosSection: 'Photos',
    registerBtn: "S'inscrire →",
    groupBrasil: 'Brésil',
    allCountry: country => `Tout ${country}`,
    periodOptions: [
      { value: 'past15', label: 'Depuis 15 jours' },
      { value: 'today',  label: "À partir d'aujourd'hui" },
      { value: '30',     label: '30 prochains jours' },
      { value: '90',     label: '3 prochains mois' },
      { value: '180',    label: '6 prochains mois' },
      { value: 'all',    label: 'Toute la période' },
      { value: 'custom', label: 'Période personnalisée' },
    ],
    places: {
      'Reino Unido': 'Royaume-Uni', 'EUA': 'États-Unis', 'Estados Unidos': 'États-Unis',
      'Japão': 'Japon', 'Alemanha': 'Allemagne', 'França': 'France',
      'Austrália': 'Australie', 'Países Baixos': 'Pays-Bas', 'Itália': 'Italie',
      'Espanha': 'Espagne', 'Paraguai': 'Paraguay', 'Uruguai': 'Uruguay',
      'Dinamarca': 'Danemark', 'Suécia': 'Suède', 'Noruega': 'Norvège',
      'Irlanda': 'Irlande', 'República Tcheca': 'République Tchèque',
      'Grécia': 'Grèce', 'Colômbia': 'Colombie', 'México': 'Mexique',
      'África do Sul': 'Afrique du Sud', 'Quênia': 'Kenya', 'Etiópia': 'Éthiopie',
      'Coreia do Sul': 'Corée du Sud', 'Canadá': 'Canada', 'Nova Zelândia': 'Nouvelle-Zélande',
      'Áustria': 'Autriche', 'Suíça': 'Suisse', 'Polônia': 'Pologne',
      'Edimburgo': 'Édimbourg', 'Tóquio': 'Tokyo', 'Londres': 'Londres',
      'Berlim': 'Berlin', 'Valência': 'Valence',
      'Nova York': 'New York', 'Amsterdã': 'Amsterdam', 'Copenhague': 'Copenhague',
      'Estocolmo': 'Stockholm', 'Praga': 'Prague', 'Atenas': 'Athènes',
      'Milão': 'Milan', 'Veneza': 'Venise', 'Assunção': 'Asunción',
      'Lisboa': 'Lisbonne', 'Moscou': 'Moscou',
    },
  },
};

const T = STRINGS[LANG];

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------
let allCorridas = [];
let filteredCorridas = [];

// Raw geo-detected filter value (e.g. 'DF', 'INT:Japão')
let _geoDetected = null;
// Filter value actually applied after fallback chain (may differ from _geoDetected)
let _geoApplied = null;
// True when user manually picked a location (suppresses geo re-apply on refresh)
let _userChoseLocation = false;

const state = {
  distMode: 'select',
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

const cardsList         = $('cardsList');
const emptyState        = $('emptyState');
const resultCount       = $('resultCount');
const btnClear          = $('btnClear');
const btnClearEmpty     = $('btnClearEmpty');
const btnRefresh        = $('btnRefresh');
const langSelect        = $('langSelect');
const estadoFilterWrapper  = $('estadoFilterWrapper');
const estadoFilterBtn      = $('estadoFilterBtn');
const estadoFilterDropdown = $('estadoFilterDropdown');
const estadoFilterLabel    = $('estadoFilterLabel');
let _estadoAvailableValues = new Set(['todos']);
const periodoSelect     = $('periodoSelect');
const customDateRow     = $('customDateRow');
const dateFrom          = $('dateFrom');
const dateTo            = $('dateTo');
const pillsContainer    = $('pillsContainer');
const intervalContainer = $('intervalContainer');
const modeSelect        = $('modeSelect');
const modeInterval      = $('modeInterval');
const distMin           = $('distMin');
const distMax           = $('distMax');
const cardTemplate      = $('cardTemplate');
const searchInput       = $('searchInput');
const fonteFilterWrapper  = $('fonteFilterWrapper');
const fonteFilterBtn      = $('fonteFilterBtn');
const fonteFilterDropdown = $('fonteFilterDropdown');
const fonteFilterLabel    = $('fonteFilterLabel');

// ---------------------------------------------------------------------------
// i18n initialisation
// ---------------------------------------------------------------------------
function initI18n() {
  document.title = T.siteTitle;
  document.querySelector('.app-title').textContent = T.headerTitle;

  if (langSelect) langSelect.value = LANG;
  if (btnRefresh)  btnRefresh.setAttribute('aria-label', T.refreshAriaLabel);
  if (searchInput) {
    searchInput.placeholder = T.searchPlaceholder;
    searchInput.setAttribute('aria-label', T.searchAriaLabel);
  }
  if (modeSelect)   modeSelect.textContent   = T.modeSelect;
  if (modeInterval) modeInterval.textContent = T.modeInterval;

  const ldf  = $('labelDistFrom');
  const ldt  = $('labelDistTo');
  const ldaf = $('labelDateFrom');
  const ldat = $('labelDateTo');
  if (ldf)  ldf.textContent  = T.distFrom;
  if (ldt)  ldt.textContent  = T.distTo;
  if (ldaf) ldaf.textContent = T.distFrom;
  if (ldat) ldat.textContent = T.distTo;
  if (distMin) distMin.setAttribute('aria-label', T.distMinAriaLabel);
  if (distMax) distMax.setAttribute('aria-label', T.distMaxAriaLabel);
  if (dateFrom) dateFrom.setAttribute('aria-label', T.dateFromAriaLabel);
  if (dateTo)   dateTo.setAttribute('aria-label',   T.dateToAriaLabel);

  if (periodoSelect) {
    periodoSelect.innerHTML = '';
    periodoSelect.setAttribute('aria-label', T.periodoAriaLabel);
    for (const opt of T.periodOptions) {
      const o = document.createElement('option');
      o.value = opt.value;
      o.textContent = opt.label;
      periodoSelect.appendChild(o);
    }
  }

  if (estadoFilterBtn) estadoFilterBtn.setAttribute('aria-label', T.estadoAriaLabel);

  if (fonteFilterBtn)   fonteFilterBtn.setAttribute('aria-label', T.fonteFilterAriaLabel);
  if (fonteFilterLabel) fonteFilterLabel.textContent = T.allSources;
  if (resultCount)   resultCount.textContent  = T.loading;
  if (btnClear)      btnClear.textContent     = T.clearFilters;
  if (btnClearEmpty) btnClearEmpty.textContent = T.clearFilters;

  const emptyMsg = emptyState && emptyState.querySelector('p');
  if (emptyMsg) emptyMsg.textContent = T.noRacesMsg;
  const emptyBtn = emptyState && emptyState.querySelector('.btn-clear');
  if (emptyBtn) emptyBtn.textContent = T.clearFilters;
}

// ---------------------------------------------------------------------------
// Language switch
// ---------------------------------------------------------------------------
if (langSelect) {
  langSelect.addEventListener('change', () => {
    window.location.href = LANG_URLS[langSelect.value] || '/pt';
  });
}

// ---------------------------------------------------------------------------
// Persistence (localStorage)
// ---------------------------------------------------------------------------
const STORAGE_KEY = 'corridas_filters';

function saveFilters() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({
      activePills: [...state.activePills],
      distMode: state.distMode,
      distMin:  state.distMin,
      distMax:  state.distMax,
      estado:   state.estado,
      fontes:   [...state.fontes],
    }));
  } catch (e) { /* ignore */ }
}

function loadFilters() {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null');
    if (!saved) return;
    state.activePills = new Set(saved.activePills || []);
    state.distMode    = saved.distMode || 'select';
    state.distMin     = saved.distMin;
    state.distMax     = saved.distMax;
    state.estado      = saved.estado || 'todos';
    state.fontes      = new Set(saved.fontes || []);
  } catch (e) { /* ignore */ }
  state.periodo = 'past15';
}

// ---------------------------------------------------------------------------
// Data fetch
// ---------------------------------------------------------------------------
async function fetchData(triggeredByUser = false) {
  btnRefresh.classList.add('spinning');
  try {
    const resp = await fetch('/corridas.json?t=' + Date.now());
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const json = await resp.json();
    allCorridas = json.corridas || [];
    populateEstadoFilter({ skipGeo: true });
    populateFontesFilter();
    if (triggeredByUser && !_userChoseLocation) {
      state.estado = 'todos';
      _geoApplied  = null;
      await detectUserLocation();
      if (state.estado === 'todos') applyFilters();
    } else {
      applyFilters();
    }
  } catch (e) {
    resultCount.textContent = T.loadError;
    console.error(e);
  } finally {
    btnRefresh.classList.remove('spinning');
  }
}

// ---------------------------------------------------------------------------
// Location / geo helpers
// ---------------------------------------------------------------------------

// Translate a Portuguese place string (city, country, or "City, Country")
// to the current language. PT is already the base, other langs use T.places.
function translatePlace(str) {
  if (!str || LANG === 'pt' || !T.places) return str || '';
  // Sort entries longest-first so "Estados Unidos" matches before "Estados"
  const entries = Object.entries(T.places).sort((a, b) => b[0].length - a[0].length);
  let out = str;
  for (const [pt, local] of entries) {
    if (out.includes(pt)) out = out.split(pt).join(local);
  }
  return out;
}

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

// Fallback country for cities that omit the ", Country" suffix
const _CITY_COUNTRY = {
  'Buenos Aires': 'Argentina',
  'Assunção':     'Paraguai',
  'Punta Del Este': 'Uruguai',
  'Porto':        'Portugal',
  'Paris':        'França',
  'Veneza':       'Itália',
  'Colonia Agip': 'Itália',
  'Roma':         'Itália',
  'Milão':        'Itália',
  'Madrid':       'Espanha',
  'Barcelona':    'Espanha',
  'Amsterdam':    'Países Baixos',
  'Amsterdã':     'Países Baixos',
  'Montevidéu':   'Uruguai',
  'Santiago':     'Chile',
  'Lima':         'Peru',
  'Bogotá':       'Colômbia',
  'Cidade do México': 'México',
};

// ISO 3166-1 alpha-2 → country name as used in the data (Portuguese)
const _ISO2_TO_DATA_COUNTRY = {
  AR: 'Argentina',
  PY: 'Paraguai',
  UY: 'Uruguai',
  PT: 'Portugal',
  IT: 'Itália',
  DE: 'Alemanha',
  FR: 'França',
  GB: 'Reino Unido',
  US: 'EUA',
  JP: 'Japão',
  AU: 'Austrália',
  ES: 'Espanha',
  CL: 'Chile',
  CO: 'Colômbia',
  MX: 'México',
  PE: 'Peru',
  NL: 'Países Baixos',
  AT: 'Áustria',
  CH: 'Suíça',
  SE: 'Suécia',
  NO: 'Noruega',
  DK: 'Dinamarca',
  FI: 'Finlândia',
  PL: 'Polônia',
  CZ: 'República Tcheca',
  ZA: 'África do Sul',
  KE: 'Quênia',
  ET: 'Etiópia',
  CN: 'China',
  KR: 'Coreia do Sul',
  CA: 'Canadá',
  NZ: 'Nova Zelândia',
};

// Cities that host World Marathon Majors (lowercase for matching)
const _MAJOR_CITIES = new Set([
  'tóquio', 'tokyo',
  'boston',
  'londres', 'london',
  'berlim', 'berlin',
  'chicago',
  'nova york', 'new york',
  'sydney',
]);

function isMajor(c) {
  if (c.estado !== 'INT') return false;
  const city = (c.cidade || '').toLowerCase().split(',')[0].trim();
  return _MAJOR_CITIES.has(city);
}

function _extractCountry(cidade) {
  if (!cidade) return null;
  const parts = cidade.split(',');
  if (parts.length > 1) return parts[parts.length - 1].trim();
  return _CITY_COUNTRY[cidade.trim()] || null;
}

function _extractCity(cidade) {
  if (!cidade) return null;
  return cidade.split(',')[0].trim() || null;
}

// ---------------------------------------------------------------------------
// Geo-detection fallback chain
// ---------------------------------------------------------------------------

// Returns true if there is at least one future event matching filterValue
function _hasFutureEvents(filterValue) {
  const today = todayStr();
  return allCorridas.some(c => c.data_evento >= today && _matchEstadoValue(c, filterValue));
}

// Fallback candidates, in priority order
function _getFallbackChain(geoValue) {
  if (!geoValue) return [];
  // INT:Country:City → INT:Country; INT:Country → todos
  if (geoValue.startsWith('INT:')) {
    const rest = geoValue.slice(4);
    if (rest.includes(':')) return [geoValue, 'INT:' + rest.slice(0, rest.indexOf(':'))];
    return [geoValue];
  }
  // BR state → all Brazil
  return [geoValue, 'BR'];
}

function _applyGeoLocation() {
  // Don't override a saved/explicit user filter
  if (state.estado !== 'todos') return;
  if (!_geoDetected && !allCorridas.length) return;

  for (const candidate of _getFallbackChain(_geoDetected)) {
    if (!_estadoAvailableValues.has(candidate)) continue;
    if (!_hasFutureEvents(candidate)) continue;
    _geoApplied = candidate;
    state.estado = candidate;
    saveFilters();
    _updateEstadoLabel();
    applyFilters();
    return;
  }
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
  const fetchers = [
    () => _tryGeoFetch('https://ipwho.is/').then(d => {
      if (!d?.success || !d.country_code) return null;
      if (d.country_code === 'BR' && _ESTADO_LABELS[d.region_code])
        return { iso2: 'BR', region: d.region_code };
      return { iso2: d.country_code, region: null };
    }),
    () => _tryGeoFetch('https://freeipapi.com/api/json').then(d => {
      if (!d?.countryCode) return null;
      if (d.countryCode === 'BR' && _ESTADO_LABELS[d.regionCode])
        return { iso2: 'BR', region: d.regionCode };
      return { iso2: d.countryCode, region: null };
    }),
    () => _tryGeoFetch('https://api.ip.sb/geoip').then(d => {
      if (!d?.country_code) return null;
      if (d.country_code === 'BR' && _ESTADO_LABELS[d.region_code])
        return { iso2: 'BR', region: d.region_code };
      return { iso2: d.country_code, region: null };
    }),
  ];

  const result = await new Promise(resolve => {
    let remaining = fetchers.length;
    for (const fn of fetchers) {
      fn().then(r => {
        if (r) resolve(r);
        else if (--remaining === 0) resolve(null);
      }).catch(() => { if (--remaining === 0) resolve(null); });
    }
  });

  if (!result) return;

  if (result.iso2 === 'BR') {
    if (result.region) _geoDetected = result.region;  // e.g. 'DF'
    else _geoDetected = 'BR';
  } else {
    const dataCountry = _ISO2_TO_DATA_COUNTRY[result.iso2];
    if (dataCountry) _geoDetected = 'INT:' + dataCountry;
  }

  _applyGeoLocation();
}

// ---------------------------------------------------------------------------
// Estado filter — custom accordion dropdown
// ---------------------------------------------------------------------------
function _updateEstadoLabel() {
  const v = state.estado;
  if (v === 'todos') {
    estadoFilterLabel.textContent = T.allLocations;
    estadoFilterBtn.classList.remove('active');
    return;
  }
  const opt = estadoFilterDropdown.querySelector(`.estado-option[data-value="${CSS.escape(v)}"]`);
  estadoFilterLabel.textContent = opt ? opt.textContent : translatePlace(v.replace(/^INT:/, '').replace(/:/g, ', '));
  estadoFilterBtn.classList.add('active');
}

function _closeEstadoDropdown() {
  estadoFilterDropdown.classList.add('hidden');
  estadoFilterBtn.setAttribute('aria-expanded', 'false');
}

function _closeFonteDropdown() {
  fonteFilterDropdown.classList.add('hidden');
  fonteFilterBtn.setAttribute('aria-expanded', 'false');
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
      // Accordion: close every other open group
      estadoFilterDropdown.querySelectorAll('.estado-group-body').forEach(b => {
        if (b !== body && !b.classList.contains('collapsed')) {
          b.classList.add('collapsed');
          b.previousElementSibling.querySelector('.estado-group-chevron').textContent = '▸';
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
      saveFilters();
      _closeEstadoDropdown();
      _updateEstadoLabel();
      populateFontesFilter();
      applyFilters();
    });
    return el;
  }

  // "Todos" at top level
  estadoFilterDropdown.appendChild(makeOption('todos', T.allLocations));

  // Build Brasil group entry
  const brEstados = [...new Set(
    base
      .filter(c => c.estado && c.estado !== 'INT' && c.estado !== '??' && c.data_evento >= today)
      .map(c => c.estado)
  )].sort();

  // Build per-country entries
  const countryCity = new Map();
  for (const c of base) {
    if (c.estado !== 'INT' || c.data_evento < today) continue;
    const country = _extractCountry(c.cidade);
    if (!country) continue;
    const city = _extractCity(c.cidade);
    if (!countryCity.has(country)) countryCity.set(country, new Set());
    if (city && city !== country) countryCity.get(country).add(city);
  }

  // Merge into a single sorted list and append in alphabetical order
  const allGroups = [];

  if (brEstados.length > 0) {
    allGroups.push({ label: T.groupBrasil, build: () => {
      const brActive = state.estado === 'BR' || brEstados.includes(state.estado);
      const { wrapper, body } = _makeAccordionGroup(T.groupBrasil, brActive);
      body.appendChild(makeOption('BR', T.allBrazil));
      for (const uf of brEstados) body.appendChild(makeOption(uf, _ESTADO_LABELS[uf] || uf));
      return wrapper;
    }});
  }

  for (const country of countryCity.keys()) {
    const countryLabel = translatePlace(country);
    allGroups.push({ label: countryLabel, build: () => {
      const cities = [...countryCity.get(country)].sort();
      const isActive = state.estado === 'INT:' + country ||
                       cities.some(city => state.estado === 'INT:' + country + ':' + city);
      const { wrapper, body } = _makeAccordionGroup(countryLabel, isActive);
      if (cities.length > 1) body.appendChild(makeOption('INT:' + country, T.allCountry(countryLabel)));
      for (const city of cities) {
        const value = cities.length === 1 ? 'INT:' + country : 'INT:' + country + ':' + city;
        body.appendChild(makeOption(value, translatePlace(city)));
      }
      return wrapper;
    }});
  }

  allGroups.sort((a, b) => a.label.localeCompare(b.label, 'pt'));
  for (const grp of allGroups) estadoFilterDropdown.appendChild(grp.build());

  // Reset to 'todos' if saved value no longer valid
  if (state.estado !== 'todos' && !_estadoAvailableValues.has(state.estado)) {
    state.estado = 'todos';
    saveFilters();
  }

  if (!skipGeo) _applyGeoLocation();
  _updateEstadoLabel();
}

// ---------------------------------------------------------------------------
// Fonte filter
// ---------------------------------------------------------------------------
function populateFontesFilter() {
  const today = todayStr();
  // When a location is selected, only show fontes that have events there
  const base = allCorridas.filter(c =>
    c.data_evento >= today && _matchEstadoValue(c, state.estado)
  );
  const availableNomes = new Set(base.flatMap(c => (c.fontes || []).map(f => f.nome)));

  // Auto-uncheck fontes no longer available in the selected location
  let stateChanged = false;
  for (const nome of [...state.fontes]) {
    if (!availableNomes.has(nome)) {
      state.fontes.delete(nome);
      stateChanged = true;
    }
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
      // Update available locations based on new fonte selection
      const prevEstado = state.estado;
      populateEstadoFilter({ skipGeo: true });
      // If estado was reset (no longer valid), refresh fontes for new 'todos' scope
      if (state.estado !== prevEstado) populateFontesFilter();
      applyFilters();
    });

    fonteFilterDropdown.appendChild(label);
  }
  _updateFonteLabel();
}

function _updateFonteLabel() {
  if (state.fontes.size === 0) {
    fonteFilterLabel.textContent = T.allSources;
    fonteFilterBtn.classList.remove('active');
  } else if (state.fontes.size === 1) {
    fonteFilterLabel.textContent = [...state.fontes][0];
    fonteFilterBtn.classList.add('active');
  } else {
    fonteFilterLabel.textContent = T.nSources(state.fontes.size);
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
  if (!d) return false;
  switch (state.periodo) {
    case 'past15':  return d >= addDays(today, -15);
    case 'today':   return d >= today;
    case '30':      return d >= today && d <= addDays(today, 30);
    case '90':      return d >= today && d <= addDays(today, 90);
    case '180':     return d >= today && d <= addDays(today, 180);
    case 'all':     return true;
    case 'custom': {
      const from = state.dateFrom;
      const to   = state.dateTo;
      if (from && d < from) return false;
      if (to   && d > to)   return false;
      return true;
    }
    default: return true;
  }
}

// Pure helper: test an event against an arbitrary filter value
function _matchEstadoValue(c, value) {
  if (value === 'todos') return true;
  if (value === 'BR')    return c.estado !== 'INT';
  if (value === 'INT')   return c.estado === 'INT';
  if (value === 'MAJORS') return isMajor(c);
  if (value.startsWith('INT:')) {
    const rest = value.slice(4);
    const sep = rest.indexOf(':');
    if (sep === -1) {
      return c.estado === 'INT' && _extractCountry(c.cidade) === rest;
    }
    const country = rest.slice(0, sep);
    const city    = rest.slice(sep + 1);
    return c.estado === 'INT' && _extractCountry(c.cidade) === country && _extractCity(c.cidade) === city;
  }
  return c.estado === value;
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

  const today = todayStr();
  const frag  = document.createDocumentFragment();

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
    const { section, cardsContainer } = buildMonthSection(monthKey, corridas.length, expand);
    for (const corrida of corridas) {
      cardsContainer.appendChild(buildCard(corrida));
    }
    frag.appendChild(section);
  }

  if (recentPast.length > 0) {
    frag.prepend(buildPastSection(recentPast));
  }

  cardsList.appendChild(frag);
}

function buildPastSection(corridas) {
  const sorted = [...corridas].sort((a, b) =>
    (b.data_evento || '').localeCompare(a.data_evento || ''));

  const countLabel = T.raceCountLabel(sorted.length);
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
    cardsContainer.appendChild(buildCard(corrida));
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

function buildMonthSection(monthKey, count, expanded = false) {
  const [year, month] = monthKey.split('-');
  const label      = T.monthsFull[parseInt(month, 10) - 1] + ' ' + year;
  const countLabel = T.raceCountLabel(count);

  const section = document.createElement('div');
  section.className = 'month-section';

  const btn = document.createElement('button');
  btn.className = 'month-separator';
  btn.setAttribute('aria-expanded', String(expanded));
  btn.setAttribute('aria-label', `${label}, ${countLabel}`);
  btn.innerHTML = `
    <span class="month-separator-label">${label}</span>
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

function buildCard(c) {
  const clone     = cardTemplate.content.cloneNode(true);
  const card      = clone.querySelector('.card');
  const collapsed = card.querySelector('.card-collapsed');
  const expanded  = card.querySelector('.card-expanded');

  const img         = card.querySelector('.card-img');
  const placeholder = card.querySelector('.card-img-placeholder');
  if (c.imagem_url) {
    img.src    = c.imagem_url;
    img.alt    = c.titulo;
    img.onload  = () => placeholder.classList.add('hidden');
    img.onerror = () => { img.classList.add('hidden'); showPlaceholder(placeholder, c.estado); };
    showPlaceholder(placeholder, c.estado);
  } else {
    img.classList.add('hidden');
    showPlaceholder(placeholder, c.estado);
  }

  card.querySelector('.card-title').textContent    = c.titulo;
  card.querySelector('.card-date').textContent     = formatDate(c.data_evento, c.horario, c.distancias);
  card.querySelector('.card-location').textContent = formatLocation(c.cidade, c.estado);

  const distContainer = card.querySelector('.card-distances');
  for (const km of formatDistancesPills(c.distancias)) {
    const span = document.createElement('span');
    span.className   = 'dist-pill';
    span.textContent = km;
    distContainer.appendChild(span);
  }


  const novoBadge = card.querySelector('.badge-novo');
  if (c.first_seen_at) {
    const age = Date.now() - new Date(c.first_seen_at).getTime();
    if (age < 24 * 60 * 60 * 1000) {
      novoBadge.textContent = T.badgeNovo;
      novoBadge.classList.remove('hidden');
    }
  }

  const fontesBadge = card.querySelector('.badge-fontes');
  if (c.fontes && c.fontes.length > 1) {
    fontesBadge.textContent = T.nSources(c.fontes.length);
    fontesBadge.classList.remove('hidden');
  }

  buildExpanded(card, c);

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

function _collapseAllCards(anchor) {
  const others = document.querySelectorAll('.card-expanded:not(.hidden)');
  if (!others.length) return;
  const anchorTop = anchor.getBoundingClientRect().top;
  others.forEach(exp => {
    exp.classList.add('hidden');
    exp.setAttribute('aria-hidden', 'true');
    exp.closest('.card').querySelector('.card-collapsed').setAttribute('aria-expanded', 'false');
  });
  const shift = anchor.getBoundingClientRect().top - anchorTop;
  if (shift !== 0) window.scrollBy({ top: shift, behavior: 'instant' });
}

function toggleExpand(collapsed, expanded) {
  const opening = expanded.classList.contains('hidden');
  if (opening) {
    _closeEstadoDropdown();
    _closeFonteDropdown();
    _collapseAllCards(collapsed.closest('.card'));
  }
  const open = expanded.classList.toggle('hidden');
  collapsed.setAttribute('aria-expanded', String(!open));
  expanded.setAttribute('aria-hidden', String(open));
}

function buildExpanded(card, c) {
  const expTitle  = card.querySelector('.expanded-title');
  const expDist   = card.querySelector('.expanded-distances');
  const expPeriod = card.querySelector('.expanded-period');
  const expFontes = card.querySelector('.expanded-fontes');
  const expFotos  = card.querySelector('.expanded-fotos');

  expTitle.textContent = c.titulo;
  expTitle.classList.remove('hidden');

  if (c.distancias && c.distancias.length > 0) {
    const sorted      = sortDistancias(c.distancias);
    const hasDate     = sorted.some(d => d.data);
    const uniqueTimes = new Set(sorted.map(d => d.horario || null).filter(Boolean));
    const hasHorario  = uniqueTimes.size > 1;

    const table = document.createElement('table');
    table.className = 'dist-table';
    let thead = `<thead><tr><th>${T.distancesHeader}</th>`;
    if (hasDate)    thead += `<th>${T.dateColHeader}</th>`;
    if (hasHorario) thead += `<th>${T.timeColHeader}</th>`;
    thead += '</tr></thead>';
    table.innerHTML = thead;

    const tbody = document.createElement('tbody');
    for (const d of sorted) {
      const tr  = document.createElement('tr');
      let cells = `<td>${formatKm(d.km)}</td>`;
      if (hasDate)    cells += `<td>${d.data ? formatDateShort(d.data) : '—'}</td>`;
      if (hasHorario) cells += `<td>${d.horario || '—'}</td>`;
      tr.innerHTML = cells;
      tbody.appendChild(tr);
    }
    table.appendChild(tbody);
    expDist.appendChild(table);
  }

  if (c.periodo_inscricao && (c.periodo_inscricao.abertura || c.periodo_inscricao.encerramento)) {
    const h = document.createElement('p');
    h.className   = 'expanded-section-title';
    h.textContent = T.registrationPeriod;
    expPeriod.appendChild(h);
    const p   = document.createElement('p');
    const ab  = c.periodo_inscricao.abertura     ? `${T.regOpening}: ${formatDateShort(c.periodo_inscricao.abertura)}`     : '';
    const enc = c.periodo_inscricao.encerramento ? `${T.regClosing}: ${formatDateShort(c.periodo_inscricao.encerramento)}` : '';
    p.textContent = [ab, enc].filter(Boolean).join(' · ');
    expPeriod.appendChild(p);
  }

  if (c.fontes && c.fontes.length > 0) {
    const h = document.createElement('p');
    h.className   = 'expanded-section-title';
    h.textContent = T.sourcesSection;
    expFontes.appendChild(h);
    for (const fonte of c.fontes) {
      const div    = document.createElement('div');
      div.className = 'fonte-item';
      const inscLink = (fonte.links_inscricao && fonte.links_inscricao.length > 0)
        ? fonte.links_inscricao[0] : (fonte.link_evento || null);
      const btnHtml = inscLink
        ? `<a href="${inscLink}" target="_blank" rel="noopener" class="btn-inscricao">${T.registerBtn}</a>`
        : '';
      div.innerHTML = `<span class="fonte-nome-text">${fonte.nome}</span>${btnHtml}`;
      expFontes.appendChild(div);
    }
  }

  if (expFotos && c.fotos && c.fotos.length > 0) {
    const h = document.createElement('p');
    h.className   = 'expanded-section-title';
    h.textContent = T.photosSection;
    expFotos.appendChild(h);
    const btns = document.createElement('div');
    btns.className = 'fotos-btns';
    for (const foto of c.fotos) {
      const a = document.createElement('a');
      a.href      = foto.url;
      a.target    = '_blank';
      a.rel       = 'noopener';
      a.className = 'btn-fotos';
      a.textContent = foto.plataforma + ' →';
      btns.appendChild(a);
    }
    expFotos.appendChild(btns);
  }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function formatDate(isoDate, horario, distancias) {
  if (!isoDate) return T.dateTBD;
  const distDates = [...new Set(
    (distancias || []).map(d => d.data).filter(Boolean)
  )].sort();
  if (distDates.length >= 2) return formatDateRange(distDates[0], distDates[distDates.length - 1]);
  return formatDateFull(isoDate) + (horario ? ` • ${horario.replace(':', 'h')}` : '');
}

function formatDateFull(iso) {
  const d = new Date(iso + 'T12:00:00');
  return T.dateFullFormat(T.weekdays[d.getDay()], d.getDate(), T.months[d.getMonth()], d.getFullYear());
}

function formatDateRange(fromIso, toIso) {
  const d1 = new Date(fromIso + 'T12:00:00');
  const d2 = new Date(toIso   + 'T12:00:00');
  if (d1.getMonth() === d2.getMonth() && d1.getFullYear() === d2.getFullYear()) {
    return T.dateRangeSameMonth(d1.getDate(), d2.getDate(), T.months[d1.getMonth()], d1.getFullYear());
  }
  return T.dateRangeDiff(d1.getDate(), T.months[d1.getMonth()], d2.getDate(), T.months[d2.getMonth()], d2.getFullYear());
}

function formatDateShort(iso) {
  if (!iso) return '';
  const [y, m, d] = iso.split('-');
  return `${d}/${m}/${y}`;
}

function formatLocation(cidade, estado) {
  if (estado === 'INT' || estado === '??' || !estado) return translatePlace(cidade || '');
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
  _userChoseLocation = false;
  state.searchQuery = '';
  state.activePills.clear();
  state.distMin  = null;
  state.distMax  = null;
  state.distMode = 'select';
  state.periodo  = 'past15';
  state.dateFrom = null;
  state.dateTo   = null;
  state.estado   = _geoApplied || 'todos';
  state.fontes.clear();

  searchInput.value = '';

  document.querySelectorAll('.pill').forEach(p => {
    p.classList.remove('active');
    p.setAttribute('aria-pressed', 'false');
  });
  distMin.value       = '';
  distMax.value       = '';
  periodoSelect.value = 'past15';
  state.estado = _geoApplied || 'todos';
  _updateEstadoLabel();
  customDateRow.classList.add('hidden');
  dateFrom.value = '';
  dateTo.value   = '';
  setDistMode('select');

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

estadoFilterBtn.addEventListener('click', e => {
  e.stopPropagation();
  const isOpen = !estadoFilterDropdown.classList.contains('hidden');
  if (!isOpen) {
    _closeFonteDropdown();
    _collapseAllCards(estadoFilterBtn);
  }
  estadoFilterDropdown.classList.toggle('hidden', isOpen);
  estadoFilterBtn.setAttribute('aria-expanded', String(!isOpen));
});

document.addEventListener('click', e => {
  if (estadoFilterWrapper && !estadoFilterWrapper.contains(e.target)) {
    _closeEstadoDropdown();
  }
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
btnRefresh.addEventListener('click', () => {
  window.location.replace(LANG_URLS[BROWSER_LANG] || '/pt');
});

fonteFilterBtn.addEventListener('click', e => {
  e.stopPropagation();
  const isOpen = !fonteFilterDropdown.classList.contains('hidden');
  if (!isOpen) _closeEstadoDropdown();
  fonteFilterDropdown.classList.toggle('hidden', isOpen);
  fonteFilterBtn.setAttribute('aria-expanded', String(!isOpen));
});

document.addEventListener('click', e => {
  if (!fonteFilterWrapper.contains(e.target)) _closeFonteDropdown();
});

document.addEventListener('keydown', e => {
  if (e.key === 'Escape') {
    if (!fonteFilterDropdown.classList.contains('hidden')) {
      _closeFonteDropdown();
      fonteFilterBtn.focus();
    }
    if (!estadoFilterDropdown.classList.contains('hidden')) {
      _closeEstadoDropdown();
      estadoFilterBtn.focus();
    }
  }
});

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------
function init() {
  initI18n();
  loadFilters();

  if (state.distMode === 'interval') setDistMode('interval');
  state.activePills.forEach(km => {
    const pill = document.querySelector(`.pill[data-km="${km}"]`);
    if (pill) { pill.classList.add('active'); pill.setAttribute('aria-pressed', 'true'); }
  });
  if (state.distMin !== null) distMin.value = state.distMin;
  if (state.distMax !== null) distMax.value = state.distMax;
  _updateEstadoLabel();
  periodoSelect.value = state.periodo;

  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/service-worker.js').catch(() => {});
  }

  detectUserLocation();
  fetchData();
}

init();
