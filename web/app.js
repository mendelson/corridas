'use strict';

// Header logo: the SAME shoe artwork as the loader/gallery, taken straight from
// ShoeWear (single source of truth — no separate copy to drift out of sync).
// The wear layers stay invisible (opacity 0; the static logo never calls
// setProgress), so it renders the clean shoe. Re-cropped + tagged for the header.
const SHOE_LOGO = (function () {
  const m = (typeof window !== 'undefined' && window.ShoeWear && window.ShoeWear.SVG_MARKUP) || '';
  return m
    ? m.replace('class="shoe-wear"', 'class="shoe-logo shoe-wear" aria-hidden="true"')
        .replace('viewBox="40 80 360 196"', 'viewBox="54 98 330 166"')
    : '';
})();

// ---------------------------------------------------------------------------
// Language detection — runs before anything else
// ---------------------------------------------------------------------------
// The 28 UI languages — the same set as the Connect IQ Store listings (and as
// apps.mmendelson.com). The key is the URL prefix (/pt-pt/, /zh-cn/ …); the
// value is the BCP-47 tag Intl uses for dates, plurals, collation and names.
// Thai pins the Gregorian calendar: th-TH defaults to the Buddhist era, which
// would print 2569 next to the Gregorian <input type="date"> pickers.
const LOCALE_TAGS = {
  pt: 'pt-BR', en: 'en-US', es: 'es-ES', de: 'de-DE', fr: 'fr-FR',
  it: 'it-IT', nl: 'nl-NL', 'pt-pt': 'pt-PT', ru: 'ru-RU', pl: 'pl-PL',
  cs: 'cs-CZ', sk: 'sk-SK', sl: 'sl-SI', hr: 'hr-HR', hu: 'hu-HU',
  el: 'el-GR', da: 'da-DK', nb: 'nb-NO', sv: 'sv-SE', fi: 'fi-FI',
  ja: 'ja-JP', ko: 'ko-KR', 'zh-cn': 'zh-CN', 'zh-tw': 'zh-TW',
  th: 'th-TH-u-ca-gregory', he: 'he-IL', id: 'id-ID', ms: 'ms-MY',
};
const SUPPORTED_LANGS = Object.keys(LOCALE_TAGS);

// The five languages the site launched with keep their hand-written month,
// weekday and country tables; the rest format through Intl (CLDR), which
// already knows each language's word order ("2026年10月", "2026. október").
const _LEGACY_LANGS = ['pt', 'en', 'es', 'de', 'fr'];

// Map one BCP-47 tag (a navigator.languages entry) to a UI language, or null.
// Regional variants that are separate languages here are told apart by their
// subtags; the old Java codes (iw, in) and the Norwegian umbrella (no, nn)
// fold into the codes the site uses.
function _langFromTag(tag) {
  const parts = String(tag || '').toLowerCase().replace(/_/g, '-').split('-');
  const base = parts[0], sub = parts.slice(1);
  if (base === 'pt') {
    return sub.some(s => ['pt', 'ao', 'mz', 'cv', 'gw', 'st', 'tl'].includes(s)) ? 'pt-pt' : 'pt';
  }
  if (base === 'zh') {
    if (sub.includes('hans')) return 'zh-cn';
    return sub.some(s => ['hant', 'tw', 'hk', 'mo'].includes(s)) ? 'zh-tw' : 'zh-cn';
  }
  if (base === 'no' || base === 'nn') return 'nb';
  if (base === 'iw') return 'he';
  if (base === 'in') return 'id';
  return SUPPORTED_LANGS.includes(base) ? base : null;
}

const BROWSER_LANG = (() => {
  const prefs = (navigator.languages && navigator.languages.length)
    ? navigator.languages : [navigator.language];
  for (const tag of prefs) {
    const l = _langFromTag(tag);
    if (l) return l;
  }
  return 'en';
})();

const LANG = (() => {
  const seg = (window.location.pathname.split('/')[1] || '').toLowerCase();
  return SUPPORTED_LANGS.includes(seg) ? seg : BROWSER_LANG;
})();

const LANG_URLS = Object.fromEntries(SUPPORTED_LANGS.map(l => [l, '/' + l]));
const LOCALE_TAG = LOCALE_TAGS[LANG] || 'en-US';
const _IS_LEGACY_LANG = _LEGACY_LANGS.includes(LANG);

// Plural forms for the newer languages, picked by CLDR category (one, two,
// few, many, other) — Russian, Polish, Czech, Slovenian and Hebrew all need
// more than singular/plural. `{n}` in the chosen form is the count.
const _PLURAL_RULES = (typeof Intl !== 'undefined' && Intl.PluralRules)
  ? new Intl.PluralRules(LOCALE_TAG) : null;
function _pl(n, forms) {
  const cat = _PLURAL_RULES ? _PLURAL_RULES.select(n) : (n === 1 ? 'one' : 'other');
  return (forms[cat] || forms.other).replace('{n}', n);
}

// ---------------------------------------------------------------------------
// i18n strings
// ---------------------------------------------------------------------------
const STRINGS = {
  pt: {
    siteTitle: 'Calendário de Corridas de Rua — Brasil e Mundo',
    headerTitle: 'Calendário de Corridas de Rua',
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
    homeAriaLabel: 'Minha localização e idioma',
    langAriaLabel: 'Idioma',
    clearFiltersAriaLabel: 'Limpar filtros',
    allLocations: 'Todos',
    allBrazil: 'Todo o Brasil',
    allSources: 'Todas as fontes',
    nSources: n => n === 1 ? `${n} fonte` : `${n} fontes`,
    allSelos: 'Todos os selos',
    nSelos: n => n === 1 ? `${n} selo` : `${n} selos`,
    seloNames: { platinum: 'Platinum', gold: 'Gold', elite: 'Elite', label: 'Label', major: 'Major' },
    seloLegendTitle: 'Selos oficiais',
    seloLegendIntro: 'A World Athletics (entidade máxima do atletismo) premia as melhores corridas de rua do mundo. Do mais alto ao mais baixo:',
    seloLegendMajor: 'Major: uma das 7 Abbott World Marathon Majors — as maratonas mais prestigiadas do planeta.',
    seloLegendAria: 'O que significam os selos',
    badgeNovo: 'novo',
    badgeCancelado: 'cancelado',
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
    siteTitle: 'Road Running Race Calendar — Brazil & Worldwide',
    headerTitle: 'Road Running Race Calendar',
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
    homeAriaLabel: 'My location and language',
    langAriaLabel: 'Language',
    clearFiltersAriaLabel: 'Clear filters',
    allLocations: 'All',
    allBrazil: 'All Brazil',
    allSources: 'All sources',
    nSources: n => n === 1 ? `${n} source` : `${n} sources`,
    allSelos: 'All labels',
    nSelos: n => n === 1 ? `${n} label` : `${n} labels`,
    seloNames: { platinum: 'Platinum', gold: 'Gold', elite: 'Elite', label: 'Label', major: 'Major' },
    seloLegendTitle: 'Official labels',
    seloLegendIntro: 'World Athletics (the sport\'s governing body) awards the world\'s best road races. Highest to lowest:',
    seloLegendMajor: 'Major: one of the 7 Abbott World Marathon Majors — the most prestigious marathons on earth.',
    seloLegendAria: 'What the labels mean',
    badgeNovo: 'new',
    badgeCancelado: 'canceled',
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
    siteTitle: 'Calendario de Carreras de Calle — Brasil y el Mundo',
    headerTitle: 'Calendario de Carreras de Calle',
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
    homeAriaLabel: 'Mi ubicación e idioma',
    langAriaLabel: 'Idioma',
    clearFiltersAriaLabel: 'Limpiar filtros',
    allLocations: 'Todos',
    allBrazil: 'Todo Brasil',
    allSources: 'Todas las fuentes',
    nSources: n => n === 1 ? `${n} fuente` : `${n} fuentes`,
    allSelos: 'Todos los sellos',
    nSelos: n => n === 1 ? `${n} sello` : `${n} sellos`,
    seloNames: { platinum: 'Platinum', gold: 'Gold', elite: 'Elite', label: 'Label', major: 'Major' },
    seloLegendTitle: 'Sellos oficiales',
    seloLegendIntro: 'World Athletics (el organismo rector del atletismo) premia las mejores carreras de calle del mundo. De mayor a menor:',
    seloLegendMajor: 'Major: una de las 7 Abbott World Marathon Majors — las maratones más prestigiosas del planeta.',
    seloLegendAria: 'Qué significan los sellos',
    badgeNovo: 'nuevo',
    badgeCancelado: 'cancelado',
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
    siteTitle: 'Laufkalender Straßenläufe — Brasilien & weltweit',
    headerTitle: 'Laufkalender Straßenläufe',
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
    homeAriaLabel: 'Mein Standort und Sprache',
    langAriaLabel: 'Sprache',
    clearFiltersAriaLabel: 'Filter löschen',
    allLocations: 'Alle',
    allBrazil: 'Ganz Brasilien',
    allSources: 'Alle Quellen',
    nSources: n => n === 1 ? `${n} Quelle` : `${n} Quellen`,
    allSelos: 'Alle Labels',
    nSelos: n => n === 1 ? `${n} Label` : `${n} Labels`,
    seloNames: { platinum: 'Platinum', gold: 'Gold', elite: 'Elite', label: 'Label', major: 'Major' },
    seloLegendTitle: 'Offizielle Labels',
    seloLegendIntro: 'World Athletics (der Dachverband der Leichtathletik) zeichnet die besten Straßenläufe der Welt aus. Von hoch nach niedrig:',
    seloLegendMajor: 'Major: einer der 7 Abbott World Marathon Majors — die renommiertesten Marathons der Welt.',
    seloLegendAria: 'Was die Labels bedeuten',
    badgeNovo: 'neu',
    badgeCancelado: 'abgesagt',
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
    siteTitle: 'Calendrier des Courses sur Route — Brésil et Monde',
    headerTitle: 'Calendrier des Courses sur Route',
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
    homeAriaLabel: 'Ma position et langue',
    langAriaLabel: 'Langue',
    clearFiltersAriaLabel: 'Effacer les filtres',
    allLocations: 'Tous',
    allBrazil: 'Tout le Brésil',
    allSources: 'Toutes les sources',
    nSources: n => n === 1 ? `${n} source` : `${n} sources`,
    allSelos: 'Tous les labels',
    nSelos: n => n === 1 ? `${n} label` : `${n} labels`,
    seloNames: { platinum: 'Platinum', gold: 'Gold', elite: 'Elite', label: 'Label', major: 'Major' },
    seloLegendTitle: 'Labels officiels',
    seloLegendIntro: 'World Athletics (la fédération internationale d\'athlétisme) récompense les meilleures courses sur route du monde. Du plus haut au plus bas :',
    seloLegendMajor: 'Major : l\'une des 7 Abbott World Marathon Majors — les marathons les plus prestigieux de la planète.',
    seloLegendAria: 'Ce que signifient les labels',
    badgeNovo: 'nouveau',
    badgeCancelado: 'annulé',
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
  it: {
    siteTitle: 'Calendario delle corse su strada — Brasile e mondo',
    headerTitle: 'Calendario delle corse su strada',
    searchPlaceholder: 'Cerca gara...',
    searchAriaLabel: 'Cerca gara',
    modeSelect: 'Seleziona',
    modeInterval: 'Intervallo',
    distFrom: 'Da',
    distTo: 'A',
    distMinAriaLabel: 'Distanza minima in km',
    distMaxAriaLabel: 'Distanza massima in km',
    dateFromAriaLabel: 'Data iniziale',
    dateToAriaLabel: 'Data finale',
    periodoAriaLabel: 'Filtra per periodo',
    estadoAriaLabel: 'Filtra per località',
    fonteFilterAriaLabel: 'Filtra per fonte',
    homeAriaLabel: 'La mia posizione e lingua',
    langAriaLabel: 'Lingua',
    clearFiltersAriaLabel: 'Cancella filtri',
    allLocations: 'Tutte',
    allBrazil: 'Tutto il Brasile',
    allSources: 'Tutte le fonti',
    nSources: n => _pl(n, { one: '{n} fonte', other: '{n} fonti' }),
    allSelos: 'Tutti i label',
    nSelos: n => _pl(n, { one: '{n} label', other: '{n} label' }),
    seloNames: { platinum: 'Platinum', gold: 'Gold', elite: 'Elite', label: 'Label', major: 'Major' },
    seloLegendTitle: 'Label ufficiali',
    seloLegendIntro: 'World Athletics (la federazione internazionale di atletica) premia le migliori corse su strada del mondo. Dal più alto al più basso:',
    seloLegendMajor: 'Major: una delle 7 Abbott World Marathon Majors — le maratone più prestigiose del pianeta.',
    seloLegendAria: 'Cosa significano i label',
    badgeNovo: 'nuova',
    badgeCancelado: 'annullata',
    loading: 'Caricamento...',
    loadError: 'Errore nel caricamento dei dati.',
    clearFilters: 'Cancella filtri',
    noResults: 'Nessuna gara trovata con i filtri attuali.',
    raceCount: n => _pl(n, { one: '{n} gara', other: '{n} gare' }),
    pastSectionLabel: '🏁 Gare degli ultimi 15 giorni',
    past15: 'Da 15 giorni fa',
    today: 'Da oggi',
    next30: 'Prossimi 30 giorni',
    next90: 'Prossimi 3 mesi',
    next180: 'Prossimi 6 mesi',
    allTime: 'Tutto il periodo',
    custom: 'Intervallo personalizzato',
    distancesHeader: 'Distanze',
    dateColHeader: 'Data',
    timeColHeader: 'Orario',
    sourcesHeader: 'Fonti',
    registerBtn: 'Iscriviti →',
    labelDateFrom: 'Da',
    labelDateTo: 'A',
    labelDistFrom: 'Da',
    labelDistTo: 'A',
    monthNames: ['Gennaio','Febbraio','Marzo','Aprile','Maggio','Giugno','Luglio','Agosto','Settembre','Ottobre','Novembre','Dicembre'],
    dayNames: ['Dom','Lun','Mar','Mer','Gio','Ven','Sab'],
    today_label: 'Oggi',
    tomorrow_label: 'Domani',
    yesterday_label: 'Ieri',
    groupBrasil: 'Brasile',
    allCountry: country => `${country} (tutto il paese)`,
    pills: { '5': '5K', '10': '10K', '15': '15K', '21': '21K', '42': '42K', 'outros': 'Altre' },
    periodoSelect: 'Filtra per periodo',
  },
  nl: {
    siteTitle: 'Hardloopkalender voor wegwedstrijden — Brazilië en wereldwijd',
    headerTitle: 'Hardloopkalender voor wegwedstrijden',
    searchPlaceholder: 'Zoek wedstrijd...',
    searchAriaLabel: 'Zoek wedstrijd',
    modeSelect: 'Kiezen',
    modeInterval: 'Bereik',
    distFrom: 'Van',
    distTo: 'Tot',
    distMinAriaLabel: 'Minimale afstand in km',
    distMaxAriaLabel: 'Maximale afstand in km',
    dateFromAriaLabel: 'Begindatum',
    dateToAriaLabel: 'Einddatum',
    periodoAriaLabel: 'Filteren op periode',
    estadoAriaLabel: 'Filteren op locatie',
    fonteFilterAriaLabel: 'Filteren op bron',
    homeAriaLabel: 'Mijn locatie en taal',
    langAriaLabel: 'Taal',
    clearFiltersAriaLabel: 'Filters wissen',
    allLocations: 'Alle',
    allBrazil: 'Heel Brazilië',
    allSources: 'Alle bronnen',
    nSources: n => _pl(n, { one: '{n} bron', other: '{n} bronnen' }),
    allSelos: 'Alle labels',
    nSelos: n => _pl(n, { one: '{n} label', other: '{n} labels' }),
    seloNames: { platinum: 'Platinum', gold: 'Gold', elite: 'Elite', label: 'Label', major: 'Major' },
    seloLegendTitle: 'Officiële labels',
    seloLegendIntro: 'World Athletics (de wereldatletiekbond) bekroont de beste wegwedstrijden ter wereld. Van hoog naar laag:',
    seloLegendMajor: 'Major: een van de 7 Abbott World Marathon Majors — de meest prestigieuze marathons ter wereld.',
    seloLegendAria: 'Wat de labels betekenen',
    badgeNovo: 'nieuw',
    badgeCancelado: 'geannuleerd',
    loading: 'Laden...',
    loadError: 'Fout bij het laden van gegevens.',
    clearFilters: 'Filters wissen',
    noResults: 'Geen wedstrijden gevonden met de huidige filters.',
    raceCount: n => _pl(n, { one: '{n} wedstrijd', other: '{n} wedstrijden' }),
    pastSectionLabel: '🏁 Wedstrijden van de afgelopen 15 dagen',
    past15: 'Vanaf 15 dagen geleden',
    today: 'Vanaf vandaag',
    next30: 'Komende 30 dagen',
    next90: 'Komende 3 maanden',
    next180: 'Komende 6 maanden',
    allTime: 'Hele periode',
    custom: 'Aangepast bereik',
    distancesHeader: 'Afstanden',
    dateColHeader: 'Datum',
    timeColHeader: 'Tijd',
    sourcesHeader: 'Bronnen',
    registerBtn: 'Inschrijven →',
    labelDateFrom: 'Van',
    labelDateTo: 'Tot',
    labelDistFrom: 'Van',
    labelDistTo: 'Tot',
    monthNames: ['Januari','Februari','Maart','April','Mei','Juni','Juli','Augustus','September','Oktober','November','December'],
    dayNames: ['Zo','Ma','Di','Wo','Do','Vr','Za'],
    today_label: 'Vandaag',
    tomorrow_label: 'Morgen',
    yesterday_label: 'Gisteren',
    groupBrasil: 'Brazilië',
    allCountry: country => `Heel ${country}`,
    pills: { '5': '5K', '10': '10K', '15': '15K', '21': '21K', '42': '42K', 'outros': 'Overige' },
    periodoSelect: 'Filteren op periode',
  },
  'pt-pt': {
    siteTitle: 'Calendário de Corridas de Estrada — Brasil e Mundo',
    headerTitle: 'Calendário de Corridas de Estrada',
    searchPlaceholder: 'Pesquisar corrida...',
    searchAriaLabel: 'Pesquisar corrida',
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
    homeAriaLabel: 'A minha localização e idioma',
    langAriaLabel: 'Idioma',
    clearFiltersAriaLabel: 'Limpar filtros',
    allLocations: 'Todos',
    allBrazil: 'Todo o Brasil',
    allSources: 'Todas as fontes',
    nSources: n => _pl(n, { one: '{n} fonte', other: '{n} fontes' }),
    allSelos: 'Todos os selos',
    nSelos: n => _pl(n, { one: '{n} selo', other: '{n} selos' }),
    seloNames: { platinum: 'Platinum', gold: 'Gold', elite: 'Elite', label: 'Label', major: 'Major' },
    seloLegendTitle: 'Selos oficiais',
    seloLegendIntro: 'A World Athletics (entidade máxima do atletismo) distingue as melhores corridas de estrada do mundo. Do mais alto ao mais baixo:',
    seloLegendMajor: 'Major: uma das 7 Abbott World Marathon Majors — as maratonas mais prestigiadas do planeta.',
    seloLegendAria: 'O que significam os selos',
    badgeNovo: 'novo',
    badgeCancelado: 'cancelado',
    loading: 'A carregar...',
    loadError: 'Erro ao carregar os dados.',
    clearFilters: 'Limpar filtros',
    noResults: 'Nenhuma corrida encontrada com os filtros atuais.',
    raceCount: n => _pl(n, { one: '{n} corrida', other: '{n} corridas' }),
    pastSectionLabel: '🏁 Corridas nos últimos 15 dias',
    past15: 'Desde há 15 dias',
    today: 'A partir de hoje',
    next30: 'Próximos 30 dias',
    next90: 'Próximos 3 meses',
    next180: 'Próximos 6 meses',
    allTime: 'Todo o período',
    custom: 'Intervalo personalizado',
    distancesHeader: 'Distâncias',
    dateColHeader: 'Data',
    timeColHeader: 'Hora',
    sourcesHeader: 'Fontes',
    registerBtn: 'Inscrever-se →',
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
    allCountry: country => `${country} (todo o país)`,
    pills: { '5': '5K', '10': '10K', '15': '15K', '21': '21K', '42': '42K', 'outros': 'Outras' },
    periodoSelect: 'Filtrar por período',
  },
  ru: {
    siteTitle: 'Календарь шоссейных забегов — Бразилия и весь мир',
    headerTitle: 'Календарь шоссейных забегов',
    searchPlaceholder: 'Поиск забега...',
    searchAriaLabel: 'Поиск забега',
    modeSelect: 'Выбор',
    modeInterval: 'Диапазон',
    distFrom: 'От',
    distTo: 'До',
    distMinAriaLabel: 'Минимальная дистанция, км',
    distMaxAriaLabel: 'Максимальная дистанция, км',
    dateFromAriaLabel: 'Начальная дата',
    dateToAriaLabel: 'Конечная дата',
    periodoAriaLabel: 'Фильтр по периоду',
    estadoAriaLabel: 'Фильтр по местоположению',
    fonteFilterAriaLabel: 'Фильтр по источнику',
    homeAriaLabel: 'Моё местоположение и язык',
    langAriaLabel: 'Язык',
    clearFiltersAriaLabel: 'Сбросить фильтры',
    allLocations: 'Все',
    allBrazil: 'Вся Бразилия',
    allSources: 'Все источники',
    nSources: n => _pl(n, { one: '{n} источник', few: '{n} источника', many: '{n} источников', other: '{n} источника' }),
    allSelos: 'Все статусы',
    nSelos: n => _pl(n, { one: '{n} статус', few: '{n} статуса', many: '{n} статусов', other: '{n} статуса' }),
    seloNames: { platinum: 'Platinum', gold: 'Gold', elite: 'Elite', label: 'Label', major: 'Major' },
    seloLegendTitle: 'Официальные статусы',
    seloLegendIntro: 'World Athletics (международная федерация лёгкой атлетики) присваивает статусы лучшим шоссейным забегам мира. От высшего к низшему:',
    seloLegendMajor: 'Major: один из 7 марафонов серии Abbott World Marathon Majors — самых престижных марафонов планеты.',
    seloLegendAria: 'Что означают статусы',
    badgeNovo: 'новый',
    badgeCancelado: 'отменён',
    loading: 'Загрузка...',
    loadError: 'Ошибка загрузки данных.',
    clearFilters: 'Сбросить фильтры',
    noResults: 'По текущим фильтрам забегов не найдено.',
    raceCount: n => _pl(n, { one: '{n} забег', few: '{n} забега', many: '{n} забегов', other: '{n} забега' }),
    pastSectionLabel: '🏁 Забеги за последние 15 дней',
    past15: 'С 15 дней назад',
    today: 'С сегодняшнего дня',
    next30: 'Ближайшие 30 дней',
    next90: 'Ближайшие 3 месяца',
    next180: 'Ближайшие 6 месяцев',
    allTime: 'За всё время',
    custom: 'Свой диапазон',
    distancesHeader: 'Дистанции',
    dateColHeader: 'Дата',
    timeColHeader: 'Время',
    sourcesHeader: 'Источники',
    registerBtn: 'Регистрация →',
    labelDateFrom: 'С',
    labelDateTo: 'По',
    labelDistFrom: 'От',
    labelDistTo: 'До',
    monthNames: ['Январь','Февраль','Март','Апрель','Май','Июнь','Июль','Август','Сентябрь','Октябрь','Ноябрь','Декабрь'],
    dayNames: ['Вс','Пн','Вт','Ср','Чт','Пт','Сб'],
    today_label: 'Сегодня',
    tomorrow_label: 'Завтра',
    yesterday_label: 'Вчера',
    groupBrasil: 'Бразилия',
    allCountry: country => `${country} — вся страна`,
    pills: { '5': '5K', '10': '10K', '15': '15K', '21': '21K', '42': '42K', 'outros': 'Другие' },
    periodoSelect: 'Фильтр по периоду',
  },
  pl: {
    siteTitle: 'Kalendarz biegów ulicznych — Brazylia i świat',
    headerTitle: 'Kalendarz biegów ulicznych',
    searchPlaceholder: 'Szukaj biegu...',
    searchAriaLabel: 'Szukaj biegu',
    modeSelect: 'Wybierz',
    modeInterval: 'Zakres',
    distFrom: 'Od',
    distTo: 'Do',
    distMinAriaLabel: 'Minimalny dystans w km',
    distMaxAriaLabel: 'Maksymalny dystans w km',
    dateFromAriaLabel: 'Data początkowa',
    dateToAriaLabel: 'Data końcowa',
    periodoAriaLabel: 'Filtruj według okresu',
    estadoAriaLabel: 'Filtruj według lokalizacji',
    fonteFilterAriaLabel: 'Filtruj według źródła',
    homeAriaLabel: 'Moja lokalizacja i język',
    langAriaLabel: 'Język',
    clearFiltersAriaLabel: 'Wyczyść filtry',
    allLocations: 'Wszystkie',
    allBrazil: 'Cała Brazylia',
    allSources: 'Wszystkie źródła',
    nSources: n => _pl(n, { one: '{n} źródło', few: '{n} źródła', many: '{n} źródeł', other: '{n} źródła' }),
    allSelos: 'Wszystkie wyróżnienia',
    nSelos: n => _pl(n, { one: '{n} wyróżnienie', few: '{n} wyróżnienia', many: '{n} wyróżnień', other: '{n} wyróżnienia' }),
    seloNames: { platinum: 'Platinum', gold: 'Gold', elite: 'Elite', label: 'Label', major: 'Major' },
    seloLegendTitle: 'Oficjalne wyróżnienia',
    seloLegendIntro: 'World Athletics (światowa federacja lekkoatletyczna) wyróżnia najlepsze biegi uliczne na świecie. Od najwyższego do najniższego:',
    seloLegendMajor: 'Major: jeden z 7 maratonów Abbott World Marathon Majors — najbardziej prestiżowych maratonów na świecie.',
    seloLegendAria: 'Co oznaczają wyróżnienia',
    badgeNovo: 'nowy',
    badgeCancelado: 'odwołany',
    loading: 'Ładowanie...',
    loadError: 'Błąd podczas ładowania danych.',
    clearFilters: 'Wyczyść filtry',
    noResults: 'Nie znaleziono biegów dla bieżących filtrów.',
    raceCount: n => _pl(n, { one: '{n} bieg', few: '{n} biegi', many: '{n} biegów', other: '{n} biegu' }),
    pastSectionLabel: '🏁 Biegi z ostatnich 15 dni',
    past15: 'Od 15 dni temu',
    today: 'Od dziś',
    next30: 'Najbliższe 30 dni',
    next90: 'Najbliższe 3 miesiące',
    next180: 'Najbliższe 6 miesięcy',
    allTime: 'Cały okres',
    custom: 'Własny zakres',
    distancesHeader: 'Dystanse',
    dateColHeader: 'Data',
    timeColHeader: 'Godzina',
    sourcesHeader: 'Źródła',
    registerBtn: 'Zapisz się →',
    labelDateFrom: 'Od',
    labelDateTo: 'Do',
    labelDistFrom: 'Od',
    labelDistTo: 'Do',
    monthNames: ['Styczeń','Luty','Marzec','Kwiecień','Maj','Czerwiec','Lipiec','Sierpień','Wrzesień','Październik','Listopad','Grudzień'],
    dayNames: ['Nd','Pn','Wt','Śr','Cz','Pt','Sb'],
    today_label: 'Dziś',
    tomorrow_label: 'Jutro',
    yesterday_label: 'Wczoraj',
    groupBrasil: 'Brazylia',
    allCountry: country => `${country} — cały kraj`,
    pills: { '5': '5K', '10': '10K', '15': '15K', '21': '21K', '42': '42K', 'outros': 'Inne' },
    periodoSelect: 'Filtruj według okresu',
  },
  cs: {
    siteTitle: 'Kalendář silničních běhů — Brazílie a svět',
    headerTitle: 'Kalendář silničních běhů',
    searchPlaceholder: 'Hledat závod...',
    searchAriaLabel: 'Hledat závod',
    modeSelect: 'Výběr',
    modeInterval: 'Rozsah',
    distFrom: 'Od',
    distTo: 'Do',
    distMinAriaLabel: 'Minimální vzdálenost v km',
    distMaxAriaLabel: 'Maximální vzdálenost v km',
    dateFromAriaLabel: 'Počáteční datum',
    dateToAriaLabel: 'Koncové datum',
    periodoAriaLabel: 'Filtrovat podle období',
    estadoAriaLabel: 'Filtrovat podle místa',
    fonteFilterAriaLabel: 'Filtrovat podle zdroje',
    homeAriaLabel: 'Moje poloha a jazyk',
    langAriaLabel: 'Jazyk',
    clearFiltersAriaLabel: 'Zrušit filtry',
    allLocations: 'Vše',
    allBrazil: 'Celá Brazílie',
    allSources: 'Všechny zdroje',
    nSources: n => _pl(n, { one: '{n} zdroj', few: '{n} zdroje', many: '{n} zdroje', other: '{n} zdrojů' }),
    allSelos: 'Všechna ocenění',
    nSelos: n => _pl(n, { one: '{n} ocenění', few: '{n} ocenění', many: '{n} ocenění', other: '{n} ocenění' }),
    seloNames: { platinum: 'Platinum', gold: 'Gold', elite: 'Elite', label: 'Label', major: 'Major' },
    seloLegendTitle: 'Oficiální ocenění',
    seloLegendIntro: 'World Athletics (světová atletická federace) oceňuje nejlepší silniční běhy na světě. Od nejvyššího po nejnižší:',
    seloLegendMajor: 'Major: jeden ze 7 maratonů Abbott World Marathon Majors — nejprestižnějších maratonů na světě.',
    seloLegendAria: 'Co ocenění znamenají',
    badgeNovo: 'nový',
    badgeCancelado: 'zrušeno',
    loading: 'Načítání...',
    loadError: 'Chyba při načítání dat.',
    clearFilters: 'Zrušit filtry',
    noResults: 'Pro aktuální filtry nebyly nalezeny žádné závody.',
    raceCount: n => _pl(n, { one: '{n} závod', few: '{n} závody', many: '{n} závodu', other: '{n} závodů' }),
    pastSectionLabel: '🏁 Závody za posledních 15 dní',
    past15: 'Od doby před 15 dny',
    today: 'Od dneška',
    next30: 'Příštích 30 dní',
    next90: 'Příští 3 měsíce',
    next180: 'Příštích 6 měsíců',
    allTime: 'Celé období',
    custom: 'Vlastní rozsah',
    distancesHeader: 'Vzdálenosti',
    dateColHeader: 'Datum',
    timeColHeader: 'Čas',
    sourcesHeader: 'Zdroje',
    registerBtn: 'Registrovat →',
    labelDateFrom: 'Od',
    labelDateTo: 'Do',
    labelDistFrom: 'Od',
    labelDistTo: 'Do',
    monthNames: ['Leden','Únor','Březen','Duben','Květen','Červen','Červenec','Srpen','Září','Říjen','Listopad','Prosinec'],
    dayNames: ['Ne','Po','Út','St','Čt','Pá','So'],
    today_label: 'Dnes',
    tomorrow_label: 'Zítra',
    yesterday_label: 'Včera',
    groupBrasil: 'Brazílie',
    allCountry: country => `${country} — celá země`,
    pills: { '5': '5K', '10': '10K', '15': '15K', '21': '21K', '42': '42K', 'outros': 'Ostatní' },
    periodoSelect: 'Filtrovat podle období',
  },
  sk: {
    siteTitle: 'Kalendár cestných behov — Brazília a svet',
    headerTitle: 'Kalendár cestných behov',
    searchPlaceholder: 'Hľadať beh...',
    searchAriaLabel: 'Hľadať beh',
    modeSelect: 'Výber',
    modeInterval: 'Rozsah',
    distFrom: 'Od',
    distTo: 'Do',
    distMinAriaLabel: 'Minimálna vzdialenosť v km',
    distMaxAriaLabel: 'Maximálna vzdialenosť v km',
    dateFromAriaLabel: 'Počiatočný dátum',
    dateToAriaLabel: 'Koncový dátum',
    periodoAriaLabel: 'Filtrovať podľa obdobia',
    estadoAriaLabel: 'Filtrovať podľa miesta',
    fonteFilterAriaLabel: 'Filtrovať podľa zdroja',
    homeAriaLabel: 'Moja poloha a jazyk',
    langAriaLabel: 'Jazyk',
    clearFiltersAriaLabel: 'Zrušiť filtre',
    allLocations: 'Všetko',
    allBrazil: 'Celá Brazília',
    allSources: 'Všetky zdroje',
    nSources: n => _pl(n, { one: '{n} zdroj', few: '{n} zdroje', many: '{n} zdroja', other: '{n} zdrojov' }),
    allSelos: 'Všetky ocenenia',
    nSelos: n => _pl(n, { one: '{n} ocenenie', few: '{n} ocenenia', many: '{n} ocenenia', other: '{n} ocenení' }),
    seloNames: { platinum: 'Platinum', gold: 'Gold', elite: 'Elite', label: 'Label', major: 'Major' },
    seloLegendTitle: 'Oficiálne ocenenia',
    seloLegendIntro: 'World Athletics (svetová atletická federácia) oceňuje najlepšie cestné behy na svete. Od najvyššieho po najnižšie:',
    seloLegendMajor: 'Major: jeden zo 7 maratónov Abbott World Marathon Majors — najprestížnejších maratónov na svete.',
    seloLegendAria: 'Čo znamenajú ocenenia',
    badgeNovo: 'nový',
    badgeCancelado: 'zrušené',
    loading: 'Načítava sa...',
    loadError: 'Chyba pri načítaní údajov.',
    clearFilters: 'Zrušiť filtre',
    noResults: 'Pre aktuálne filtre sa nenašli žiadne behy.',
    raceCount: n => _pl(n, { one: '{n} beh', few: '{n} behy', many: '{n} behu', other: '{n} behov' }),
    pastSectionLabel: '🏁 Behy za posledných 15 dní',
    past15: 'Od 15 dní dozadu',
    today: 'Od dneška',
    next30: 'Najbližších 30 dní',
    next90: 'Najbližšie 3 mesiace',
    next180: 'Najbližších 6 mesiacov',
    allTime: 'Celé obdobie',
    custom: 'Vlastný rozsah',
    distancesHeader: 'Vzdialenosti',
    dateColHeader: 'Dátum',
    timeColHeader: 'Čas',
    sourcesHeader: 'Zdroje',
    registerBtn: 'Registrovať →',
    labelDateFrom: 'Od',
    labelDateTo: 'Do',
    labelDistFrom: 'Od',
    labelDistTo: 'Do',
    monthNames: ['Január','Február','Marec','Apríl','Máj','Jún','Júl','August','September','Október','November','December'],
    dayNames: ['Ne','Po','Ut','St','Št','Pi','So'],
    today_label: 'Dnes',
    tomorrow_label: 'Zajtra',
    yesterday_label: 'Včera',
    groupBrasil: 'Brazília',
    allCountry: country => `${country} — celá krajina`,
    pills: { '5': '5K', '10': '10K', '15': '15K', '21': '21K', '42': '42K', 'outros': 'Ostatné' },
    periodoSelect: 'Filtrovať podľa obdobia',
  },
  sl: {
    siteTitle: 'Koledar cestnih tekov — Brazilija in svet',
    headerTitle: 'Koledar cestnih tekov',
    searchPlaceholder: 'Išči tek...',
    searchAriaLabel: 'Išči tek',
    modeSelect: 'Izbira',
    modeInterval: 'Razpon',
    distFrom: 'Od',
    distTo: 'Do',
    distMinAriaLabel: 'Najmanjša razdalja v km',
    distMaxAriaLabel: 'Največja razdalja v km',
    dateFromAriaLabel: 'Začetni datum',
    dateToAriaLabel: 'Končni datum',
    periodoAriaLabel: 'Filtriraj po obdobju',
    estadoAriaLabel: 'Filtriraj po lokaciji',
    fonteFilterAriaLabel: 'Filtriraj po viru',
    homeAriaLabel: 'Moja lokacija in jezik',
    langAriaLabel: 'Jezik',
    clearFiltersAriaLabel: 'Počisti filtre',
    allLocations: 'Vse',
    allBrazil: 'Vsa Brazilija',
    allSources: 'Vsi viri',
    nSources: n => _pl(n, { one: '{n} vir', two: '{n} vira', few: '{n} viri', other: '{n} virov' }),
    allSelos: 'Vse oznake',
    nSelos: n => _pl(n, { one: '{n} oznaka', two: '{n} oznaki', few: '{n} oznake', other: '{n} oznak' }),
    seloNames: { platinum: 'Platinum', gold: 'Gold', elite: 'Elite', label: 'Label', major: 'Major' },
    seloLegendTitle: 'Uradne oznake',
    seloLegendIntro: 'World Athletics (svetovna atletska zveza) podeljuje oznake najboljšim cestnim tekom na svetu. Od najvišje do najnižje:',
    seloLegendMajor: 'Major: eden od 7 maratonov Abbott World Marathon Majors — najprestižnejših maratonov na svetu.',
    seloLegendAria: 'Kaj pomenijo oznake',
    badgeNovo: 'novo',
    badgeCancelado: 'odpovedano',
    loading: 'Nalaganje...',
    loadError: 'Napaka pri nalaganju podatkov.',
    clearFilters: 'Počisti filtre',
    noResults: 'Za trenutne filtre ni najdenih tekov.',
    raceCount: n => _pl(n, { one: '{n} tek', two: '{n} teka', few: '{n} teki', other: '{n} tekov' }),
    pastSectionLabel: '🏁 Teki v zadnjih 15 dneh',
    past15: 'Od pred 15 dnevi',
    today: 'Od danes',
    next30: 'Naslednjih 30 dni',
    next90: 'Naslednji 3 meseci',
    next180: 'Naslednjih 6 mesecev',
    allTime: 'Celotno obdobje',
    custom: 'Razpon po meri',
    distancesHeader: 'Razdalje',
    dateColHeader: 'Datum',
    timeColHeader: 'Ura',
    sourcesHeader: 'Viri',
    registerBtn: 'Prijava →',
    labelDateFrom: 'Od',
    labelDateTo: 'Do',
    labelDistFrom: 'Od',
    labelDistTo: 'Do',
    monthNames: ['Januar','Februar','Marec','April','Maj','Junij','Julij','Avgust','September','Oktober','November','December'],
    dayNames: ['Ned','Pon','Tor','Sre','Čet','Pet','Sob'],
    today_label: 'Danes',
    tomorrow_label: 'Jutri',
    yesterday_label: 'Včeraj',
    groupBrasil: 'Brazilija',
    allCountry: country => `${country} — vsa država`,
    pills: { '5': '5K', '10': '10K', '15': '15K', '21': '21K', '42': '42K', 'outros': 'Druge' },
    periodoSelect: 'Filtriraj po obdobju',
  },
  hr: {
    siteTitle: 'Kalendar cestovnih utrka — Brazil i svijet',
    headerTitle: 'Kalendar cestovnih utrka',
    searchPlaceholder: 'Traži utrku...',
    searchAriaLabel: 'Traži utrku',
    modeSelect: 'Odabir',
    modeInterval: 'Raspon',
    distFrom: 'Od',
    distTo: 'Do',
    distMinAriaLabel: 'Najmanja udaljenost u km',
    distMaxAriaLabel: 'Najveća udaljenost u km',
    dateFromAriaLabel: 'Početni datum',
    dateToAriaLabel: 'Završni datum',
    periodoAriaLabel: 'Filtriraj po razdoblju',
    estadoAriaLabel: 'Filtriraj po lokaciji',
    fonteFilterAriaLabel: 'Filtriraj po izvoru',
    homeAriaLabel: 'Moja lokacija i jezik',
    langAriaLabel: 'Jezik',
    clearFiltersAriaLabel: 'Očisti filtre',
    allLocations: 'Sve',
    allBrazil: 'Cijeli Brazil',
    allSources: 'Svi izvori',
    nSources: n => _pl(n, { one: '{n} izvor', few: '{n} izvora', other: '{n} izvora' }),
    allSelos: 'Sve oznake',
    nSelos: n => _pl(n, { one: '{n} oznaka', few: '{n} oznake', other: '{n} oznaka' }),
    seloNames: { platinum: 'Platinum', gold: 'Gold', elite: 'Elite', label: 'Label', major: 'Major' },
    seloLegendTitle: 'Službene oznake',
    seloLegendIntro: 'World Athletics (svjetski atletski savez) dodjeljuje oznake najboljim cestovnim utrkama na svijetu. Od najviše do najniže:',
    seloLegendMajor: 'Major: jedan od 7 maratona Abbott World Marathon Majors — najprestižnijih maratona na svijetu.',
    seloLegendAria: 'Što znače oznake',
    badgeNovo: 'novo',
    badgeCancelado: 'otkazano',
    loading: 'Učitavanje...',
    loadError: 'Pogreška pri učitavanju podataka.',
    clearFilters: 'Očisti filtre',
    noResults: 'Nema utrka za odabrane filtre.',
    raceCount: n => _pl(n, { one: '{n} utrka', few: '{n} utrke', other: '{n} utrka' }),
    pastSectionLabel: '🏁 Utrke u posljednjih 15 dana',
    past15: 'Od prije 15 dana',
    today: 'Od danas',
    next30: 'Sljedećih 30 dana',
    next90: 'Sljedeća 3 mjeseca',
    next180: 'Sljedećih 6 mjeseci',
    allTime: 'Cijelo razdoblje',
    custom: 'Prilagođeni raspon',
    distancesHeader: 'Udaljenosti',
    dateColHeader: 'Datum',
    timeColHeader: 'Vrijeme',
    sourcesHeader: 'Izvori',
    registerBtn: 'Prijava →',
    labelDateFrom: 'Od',
    labelDateTo: 'Do',
    labelDistFrom: 'Od',
    labelDistTo: 'Do',
    monthNames: ['Siječanj','Veljača','Ožujak','Travanj','Svibanj','Lipanj','Srpanj','Kolovoz','Rujan','Listopad','Studeni','Prosinac'],
    dayNames: ['Ned','Pon','Uto','Sri','Čet','Pet','Sub'],
    today_label: 'Danas',
    tomorrow_label: 'Sutra',
    yesterday_label: 'Jučer',
    groupBrasil: 'Brazil',
    allCountry: country => `${country} — cijela zemlja`,
    pills: { '5': '5K', '10': '10K', '15': '15K', '21': '21K', '42': '42K', 'outros': 'Ostale' },
    periodoSelect: 'Filtriraj po razdoblju',
  },
  hu: {
    siteTitle: 'Országúti futóversenyek naptára — Brazília és a világ',
    headerTitle: 'Országúti futóversenyek naptára',
    searchPlaceholder: 'Verseny keresése...',
    searchAriaLabel: 'Verseny keresése',
    modeSelect: 'Kiválasztás',
    modeInterval: 'Tartomány',
    distFrom: 'Ettől',
    distTo: 'Eddig',
    distMinAriaLabel: 'Minimális táv km-ben',
    distMaxAriaLabel: 'Maximális táv km-ben',
    dateFromAriaLabel: 'Kezdő dátum',
    dateToAriaLabel: 'Záró dátum',
    periodoAriaLabel: 'Szűrés időszak szerint',
    estadoAriaLabel: 'Szűrés helyszín szerint',
    fonteFilterAriaLabel: 'Szűrés forrás szerint',
    homeAriaLabel: 'Helyzetem és nyelvem',
    langAriaLabel: 'Nyelv',
    clearFiltersAriaLabel: 'Szűrők törlése',
    allLocations: 'Összes',
    allBrazil: 'Egész Brazília',
    allSources: 'Összes forrás',
    nSources: n => _pl(n, { one: '{n} forrás', other: '{n} forrás' }),
    allSelos: 'Összes minősítés',
    nSelos: n => _pl(n, { one: '{n} minősítés', other: '{n} minősítés' }),
    seloNames: { platinum: 'Platinum', gold: 'Gold', elite: 'Elite', label: 'Label', major: 'Major' },
    seloLegendTitle: 'Hivatalos minősítések',
    seloLegendIntro: 'A World Athletics (a nemzetközi atlétikai szövetség) minősíti a világ legjobb országúti futóversenyeit. A legmagasabbtól a legalacsonyabbig:',
    seloLegendMajor: 'Major: a 7 Abbott World Marathon Majors maraton egyike — a világ legrangosabb maratonjai.',
    seloLegendAria: 'Mit jelentenek a minősítések',
    badgeNovo: 'új',
    badgeCancelado: 'elmarad',
    loading: 'Betöltés...',
    loadError: 'Hiba az adatok betöltésekor.',
    clearFilters: 'Szűrők törlése',
    noResults: 'A jelenlegi szűrőkkel nincs találat.',
    raceCount: n => _pl(n, { one: '{n} verseny', other: '{n} verseny' }),
    pastSectionLabel: '🏁 Az elmúlt 15 nap versenyei',
    past15: '15 nappal ezelőttől',
    today: 'Mától',
    next30: 'Következő 30 nap',
    next90: 'Következő 3 hónap',
    next180: 'Következő 6 hónap',
    allTime: 'Teljes időszak',
    custom: 'Egyéni tartomány',
    distancesHeader: 'Távok',
    dateColHeader: 'Dátum',
    timeColHeader: 'Időpont',
    sourcesHeader: 'Források',
    registerBtn: 'Nevezés →',
    labelDateFrom: 'Ettől',
    labelDateTo: 'Eddig',
    labelDistFrom: 'Ettől',
    labelDistTo: 'Eddig',
    monthNames: ['Január','Február','Március','Április','Május','Június','Július','Augusztus','Szeptember','Október','November','December'],
    dayNames: ['V','H','K','Sze','Cs','P','Szo'],
    today_label: 'Ma',
    tomorrow_label: 'Holnap',
    yesterday_label: 'Tegnap',
    groupBrasil: 'Brazília',
    allCountry: country => `${country} (az egész ország)`,
    pills: { '5': '5K', '10': '10K', '15': '15K', '21': '21K', '42': '42K', 'outros': 'Egyéb' },
    periodoSelect: 'Szűrés időszak szerint',
  },
  el: {
    siteTitle: 'Ημερολόγιο αγώνων δρόμου — Βραζιλία και όλος ο κόσμος',
    headerTitle: 'Ημερολόγιο αγώνων δρόμου',
    searchPlaceholder: 'Αναζήτηση αγώνα...',
    searchAriaLabel: 'Αναζήτηση αγώνα',
    modeSelect: 'Επιλογή',
    modeInterval: 'Εύρος',
    distFrom: 'Από',
    distTo: 'Έως',
    distMinAriaLabel: 'Ελάχιστη απόσταση σε km',
    distMaxAriaLabel: 'Μέγιστη απόσταση σε km',
    dateFromAriaLabel: 'Ημερομηνία έναρξης',
    dateToAriaLabel: 'Ημερομηνία λήξης',
    periodoAriaLabel: 'Φιλτράρισμα ανά περίοδο',
    estadoAriaLabel: 'Φιλτράρισμα ανά τοποθεσία',
    fonteFilterAriaLabel: 'Φιλτράρισμα ανά πηγή',
    homeAriaLabel: 'Η τοποθεσία και η γλώσσα μου',
    langAriaLabel: 'Γλώσσα',
    clearFiltersAriaLabel: 'Καθαρισμός φίλτρων',
    allLocations: 'Όλα',
    allBrazil: 'Όλη η Βραζιλία',
    allSources: 'Όλες οι πηγές',
    nSources: n => _pl(n, { one: '{n} πηγή', other: '{n} πηγές' }),
    allSelos: 'Όλες οι διακρίσεις',
    nSelos: n => _pl(n, { one: '{n} διάκριση', other: '{n} διακρίσεις' }),
    seloNames: { platinum: 'Platinum', gold: 'Gold', elite: 'Elite', label: 'Label', major: 'Major' },
    seloLegendTitle: 'Επίσημες διακρίσεις',
    seloLegendIntro: 'Η World Athletics (η διεθνής ομοσπονδία στίβου) βραβεύει τους καλύτερους αγώνες δρόμου στον κόσμο. Από την υψηλότερη στη χαμηλότερη:',
    seloLegendMajor: 'Major: ένας από τους 7 μαραθωνίους Abbott World Marathon Majors — τους πιο φημισμένους μαραθωνίους του πλανήτη.',
    seloLegendAria: 'Τι σημαίνουν οι διακρίσεις',
    badgeNovo: 'νέο',
    badgeCancelado: 'ακυρώθηκε',
    loading: 'Φόρτωση...',
    loadError: 'Σφάλμα κατά τη φόρτωση δεδομένων.',
    clearFilters: 'Καθαρισμός φίλτρων',
    noResults: 'Δεν βρέθηκαν αγώνες με τα τρέχοντα φίλτρα.',
    raceCount: n => _pl(n, { one: '{n} αγώνας', other: '{n} αγώνες' }),
    pastSectionLabel: '🏁 Αγώνες των τελευταίων 15 ημερών',
    past15: 'Από πριν από 15 ημέρες',
    today: 'Από σήμερα',
    next30: 'Επόμενες 30 ημέρες',
    next90: 'Επόμενοι 3 μήνες',
    next180: 'Επόμενοι 6 μήνες',
    allTime: 'Όλη η περίοδος',
    custom: 'Προσαρμοσμένο εύρος',
    distancesHeader: 'Αποστάσεις',
    dateColHeader: 'Ημερομηνία',
    timeColHeader: 'Ώρα',
    sourcesHeader: 'Πηγές',
    registerBtn: 'Εγγραφή →',
    labelDateFrom: 'Από',
    labelDateTo: 'Έως',
    labelDistFrom: 'Από',
    labelDistTo: 'Έως',
    monthNames: ['Ιανουάριος','Φεβρουάριος','Μάρτιος','Απρίλιος','Μάιος','Ιούνιος','Ιούλιος','Αύγουστος','Σεπτέμβριος','Οκτώβριος','Νοέμβριος','Δεκέμβριος'],
    dayNames: ['Κυρ','Δευ','Τρί','Τετ','Πέμ','Παρ','Σάβ'],
    today_label: 'Σήμερα',
    tomorrow_label: 'Αύριο',
    yesterday_label: 'Χθες',
    groupBrasil: 'Βραζιλία',
    allCountry: country => `${country} — όλη η χώρα`,
    pills: { '5': '5K', '10': '10K', '15': '15K', '21': '21K', '42': '42K', 'outros': 'Άλλες' },
    periodoSelect: 'Φιλτράρισμα ανά περίοδο',
  },
  da: {
    siteTitle: 'Løbskalender for gadeløb — Brasilien og hele verden',
    headerTitle: 'Løbskalender for gadeløb',
    searchPlaceholder: 'Søg løb...',
    searchAriaLabel: 'Søg løb',
    modeSelect: 'Vælg',
    modeInterval: 'Interval',
    distFrom: 'Fra',
    distTo: 'Til',
    distMinAriaLabel: 'Mindste distance i km',
    distMaxAriaLabel: 'Største distance i km',
    dateFromAriaLabel: 'Startdato',
    dateToAriaLabel: 'Slutdato',
    periodoAriaLabel: 'Filtrér efter periode',
    estadoAriaLabel: 'Filtrér efter sted',
    fonteFilterAriaLabel: 'Filtrér efter kilde',
    homeAriaLabel: 'Min placering og mit sprog',
    langAriaLabel: 'Sprog',
    clearFiltersAriaLabel: 'Ryd filtre',
    allLocations: 'Alle',
    allBrazil: 'Hele Brasilien',
    allSources: 'Alle kilder',
    nSources: n => _pl(n, { one: '{n} kilde', other: '{n} kilder' }),
    allSelos: 'Alle mærker',
    nSelos: n => _pl(n, { one: '{n} mærke', other: '{n} mærker' }),
    seloNames: { platinum: 'Platinum', gold: 'Gold', elite: 'Elite', label: 'Label', major: 'Major' },
    seloLegendTitle: 'Officielle mærker',
    seloLegendIntro: 'World Athletics (det internationale atletikforbund) udnævner verdens bedste gadeløb. Fra højeste til laveste:',
    seloLegendMajor: 'Major: et af de 7 Abbott World Marathon Majors — de mest prestigefyldte maratonløb i verden.',
    seloLegendAria: 'Hvad mærkerne betyder',
    badgeNovo: 'ny',
    badgeCancelado: 'aflyst',
    loading: 'Indlæser...',
    loadError: 'Fejl ved indlæsning af data.',
    clearFilters: 'Ryd filtre',
    noResults: 'Ingen løb fundet med de aktuelle filtre.',
    raceCount: n => _pl(n, { one: '{n} løb', other: '{n} løb' }),
    pastSectionLabel: '🏁 Løb de seneste 15 dage',
    past15: 'Fra 15 dage siden',
    today: 'Fra i dag',
    next30: 'Næste 30 dage',
    next90: 'Næste 3 måneder',
    next180: 'Næste 6 måneder',
    allTime: 'Hele perioden',
    custom: 'Tilpasset interval',
    distancesHeader: 'Distancer',
    dateColHeader: 'Dato',
    timeColHeader: 'Tidspunkt',
    sourcesHeader: 'Kilder',
    registerBtn: 'Tilmeld dig →',
    labelDateFrom: 'Fra',
    labelDateTo: 'Til',
    labelDistFrom: 'Fra',
    labelDistTo: 'Til',
    monthNames: ['Januar','Februar','Marts','April','Maj','Juni','Juli','August','September','Oktober','November','December'],
    dayNames: ['Søn','Man','Tir','Ons','Tor','Fre','Lør'],
    today_label: 'I dag',
    tomorrow_label: 'I morgen',
    yesterday_label: 'I går',
    groupBrasil: 'Brasilien',
    allCountry: country => `Hele ${country}`,
    pills: { '5': '5K', '10': '10K', '15': '15K', '21': '21K', '42': '42K', 'outros': 'Andre' },
    periodoSelect: 'Filtrér efter periode',
  },
  nb: {
    siteTitle: 'Løpskalender for gateløp — Brasil og hele verden',
    headerTitle: 'Løpskalender for gateløp',
    searchPlaceholder: 'Søk etter løp...',
    searchAriaLabel: 'Søk etter løp',
    modeSelect: 'Velg',
    modeInterval: 'Intervall',
    distFrom: 'Fra',
    distTo: 'Til',
    distMinAriaLabel: 'Minste distanse i km',
    distMaxAriaLabel: 'Største distanse i km',
    dateFromAriaLabel: 'Startdato',
    dateToAriaLabel: 'Sluttdato',
    periodoAriaLabel: 'Filtrer etter periode',
    estadoAriaLabel: 'Filtrer etter sted',
    fonteFilterAriaLabel: 'Filtrer etter kilde',
    homeAriaLabel: 'Min posisjon og mitt språk',
    langAriaLabel: 'Språk',
    clearFiltersAriaLabel: 'Fjern filtre',
    allLocations: 'Alle',
    allBrazil: 'Hele Brasil',
    allSources: 'Alle kilder',
    nSources: n => _pl(n, { one: '{n} kilde', other: '{n} kilder' }),
    allSelos: 'Alle merker',
    nSelos: n => _pl(n, { one: '{n} merke', other: '{n} merker' }),
    seloNames: { platinum: 'Platinum', gold: 'Gold', elite: 'Elite', label: 'Label', major: 'Major' },
    seloLegendTitle: 'Offisielle merker',
    seloLegendIntro: 'World Athletics (det internasjonale friidrettsforbundet) utmerker verdens beste gateløp. Fra høyeste til laveste:',
    seloLegendMajor: 'Major: ett av de 7 Abbott World Marathon Majors — de mest prestisjefylte maratonløpene i verden.',
    seloLegendAria: 'Hva merkene betyr',
    badgeNovo: 'ny',
    badgeCancelado: 'avlyst',
    loading: 'Laster inn...',
    loadError: 'Feil ved innlasting av data.',
    clearFilters: 'Fjern filtre',
    noResults: 'Fant ingen løp med gjeldende filtre.',
    raceCount: n => _pl(n, { one: '{n} løp', other: '{n} løp' }),
    pastSectionLabel: '🏁 Løp de siste 15 dagene',
    past15: 'Fra 15 dager siden',
    today: 'Fra i dag',
    next30: 'Neste 30 dager',
    next90: 'Neste 3 måneder',
    next180: 'Neste 6 måneder',
    allTime: 'Hele perioden',
    custom: 'Egendefinert intervall',
    distancesHeader: 'Distanser',
    dateColHeader: 'Dato',
    timeColHeader: 'Tid',
    sourcesHeader: 'Kilder',
    registerBtn: 'Meld deg på →',
    labelDateFrom: 'Fra',
    labelDateTo: 'Til',
    labelDistFrom: 'Fra',
    labelDistTo: 'Til',
    monthNames: ['Januar','Februar','Mars','April','Mai','Juni','Juli','August','September','Oktober','November','Desember'],
    dayNames: ['Søn','Man','Tir','Ons','Tor','Fre','Lør'],
    today_label: 'I dag',
    tomorrow_label: 'I morgen',
    yesterday_label: 'I går',
    groupBrasil: 'Brasil',
    allCountry: country => `Hele ${country}`,
    pills: { '5': '5K', '10': '10K', '15': '15K', '21': '21K', '42': '42K', 'outros': 'Andre' },
    periodoSelect: 'Filtrer etter periode',
  },
  sv: {
    siteTitle: 'Loppkalender för gatulopp — Brasilien och hela världen',
    headerTitle: 'Loppkalender för gatulopp',
    searchPlaceholder: 'Sök lopp...',
    searchAriaLabel: 'Sök lopp',
    modeSelect: 'Välj',
    modeInterval: 'Intervall',
    distFrom: 'Från',
    distTo: 'Till',
    distMinAriaLabel: 'Minsta distans i km',
    distMaxAriaLabel: 'Största distans i km',
    dateFromAriaLabel: 'Startdatum',
    dateToAriaLabel: 'Slutdatum',
    periodoAriaLabel: 'Filtrera efter period',
    estadoAriaLabel: 'Filtrera efter plats',
    fonteFilterAriaLabel: 'Filtrera efter källa',
    homeAriaLabel: 'Min plats och mitt språk',
    langAriaLabel: 'Språk',
    clearFiltersAriaLabel: 'Rensa filter',
    allLocations: 'Alla',
    allBrazil: 'Hela Brasilien',
    allSources: 'Alla källor',
    nSources: n => _pl(n, { one: '{n} källa', other: '{n} källor' }),
    allSelos: 'Alla utmärkelser',
    nSelos: n => _pl(n, { one: '{n} utmärkelse', other: '{n} utmärkelser' }),
    seloNames: { platinum: 'Platinum', gold: 'Gold', elite: 'Elite', label: 'Label', major: 'Major' },
    seloLegendTitle: 'Officiella utmärkelser',
    seloLegendIntro: 'World Athletics (det internationella friidrottsförbundet) utmärker världens bästa gatulopp. Från högsta till lägsta:',
    seloLegendMajor: 'Major: ett av de 7 Abbott World Marathon Majors — världens mest prestigefyllda maratonlopp.',
    seloLegendAria: 'Vad utmärkelserna betyder',
    badgeNovo: 'ny',
    badgeCancelado: 'inställt',
    loading: 'Laddar...',
    loadError: 'Fel vid inläsning av data.',
    clearFilters: 'Rensa filter',
    noResults: 'Inga lopp hittades med nuvarande filter.',
    raceCount: n => _pl(n, { one: '{n} lopp', other: '{n} lopp' }),
    pastSectionLabel: '🏁 Lopp de senaste 15 dagarna',
    past15: 'Från 15 dagar sedan',
    today: 'Från i dag',
    next30: 'Kommande 30 dagar',
    next90: 'Kommande 3 månader',
    next180: 'Kommande 6 månader',
    allTime: 'Hela perioden',
    custom: 'Anpassat intervall',
    distancesHeader: 'Distanser',
    dateColHeader: 'Datum',
    timeColHeader: 'Tid',
    sourcesHeader: 'Källor',
    registerBtn: 'Anmäl dig →',
    labelDateFrom: 'Från',
    labelDateTo: 'Till',
    labelDistFrom: 'Från',
    labelDistTo: 'Till',
    monthNames: ['Januari','Februari','Mars','April','Maj','Juni','Juli','Augusti','September','Oktober','November','December'],
    dayNames: ['Sön','Mån','Tis','Ons','Tor','Fre','Lör'],
    today_label: 'I dag',
    tomorrow_label: 'I morgon',
    yesterday_label: 'I går',
    groupBrasil: 'Brasilien',
    allCountry: country => `Hela ${country}`,
    pills: { '5': '5K', '10': '10K', '15': '15K', '21': '21K', '42': '42K', 'outros': 'Övriga' },
    periodoSelect: 'Filtrera efter period',
  },
  fi: {
    siteTitle: 'Maantiejuoksujen kalenteri — Brasilia ja koko maailma',
    headerTitle: 'Maantiejuoksujen kalenteri',
    searchPlaceholder: 'Hae juoksua...',
    searchAriaLabel: 'Hae juoksua',
    modeSelect: 'Valitse',
    modeInterval: 'Väli',
    distFrom: 'Alkaen',
    distTo: 'Enintään',
    distMinAriaLabel: 'Vähimmäismatka km',
    distMaxAriaLabel: 'Enimmäismatka km',
    dateFromAriaLabel: 'Alkupäivä',
    dateToAriaLabel: 'Loppupäivä',
    periodoAriaLabel: 'Suodata ajanjakson mukaan',
    estadoAriaLabel: 'Suodata sijainnin mukaan',
    fonteFilterAriaLabel: 'Suodata lähteen mukaan',
    homeAriaLabel: 'Sijaintini ja kieleni',
    langAriaLabel: 'Kieli',
    clearFiltersAriaLabel: 'Tyhjennä suodattimet',
    allLocations: 'Kaikki',
    allBrazil: 'Koko Brasilia',
    allSources: 'Kaikki lähteet',
    nSources: n => _pl(n, { one: '{n} lähde', other: '{n} lähdettä' }),
    allSelos: 'Kaikki merkit',
    nSelos: n => _pl(n, { one: '{n} merkki', other: '{n} merkkiä' }),
    seloNames: { platinum: 'Platinum', gold: 'Gold', elite: 'Elite', label: 'Label', major: 'Major' },
    seloLegendTitle: 'Viralliset merkit',
    seloLegendIntro: 'World Athletics (kansainvälinen yleisurheiluliitto) palkitsee maailman parhaat maantiejuoksut. Korkeimmasta alimpaan:',
    seloLegendMajor: 'Major: yksi 7 Abbott World Marathon Majors -maratonista — maailman arvostetuimmat maratonit.',
    seloLegendAria: 'Mitä merkit tarkoittavat',
    badgeNovo: 'uusi',
    badgeCancelado: 'peruttu',
    loading: 'Ladataan...',
    loadError: 'Virhe tietojen latauksessa.',
    clearFilters: 'Tyhjennä suodattimet',
    noResults: 'Nykyisillä suodattimilla ei löytynyt juoksuja.',
    raceCount: n => _pl(n, { one: '{n} juoksu', other: '{n} juoksua' }),
    pastSectionLabel: '🏁 Viimeisten 15 päivän juoksut',
    past15: '15 päivän takaa',
    today: 'Tästä päivästä',
    next30: 'Seuraavat 30 päivää',
    next90: 'Seuraavat 3 kuukautta',
    next180: 'Seuraavat 6 kuukautta',
    allTime: 'Koko ajanjakso',
    custom: 'Mukautettu väli',
    distancesHeader: 'Matkat',
    dateColHeader: 'Päivämäärä',
    timeColHeader: 'Aika',
    sourcesHeader: 'Lähteet',
    registerBtn: 'Ilmoittaudu →',
    labelDateFrom: 'Alkaen',
    labelDateTo: 'Asti',
    labelDistFrom: 'Alkaen',
    labelDistTo: 'Enintään',
    monthNames: ['Tammikuu','Helmikuu','Maaliskuu','Huhtikuu','Toukokuu','Kesäkuu','Heinäkuu','Elokuu','Syyskuu','Lokakuu','Marraskuu','Joulukuu'],
    dayNames: ['Su','Ma','Ti','Ke','To','Pe','La'],
    today_label: 'Tänään',
    tomorrow_label: 'Huomenna',
    yesterday_label: 'Eilen',
    groupBrasil: 'Brasilia',
    allCountry: country => `Koko ${country}`,
    pills: { '5': '5K', '10': '10K', '15': '15K', '21': '21K', '42': '42K', 'outros': 'Muut' },
    periodoSelect: 'Suodata ajanjakson mukaan',
  },
  ja: {
    siteTitle: 'ロードレースカレンダー — ブラジルと世界のマラソン・ランニング大会',
    headerTitle: 'ロードレースカレンダー',
    searchPlaceholder: 'レースを検索...',
    searchAriaLabel: 'レースを検索',
    modeSelect: '選択',
    modeInterval: '範囲',
    distFrom: '最小',
    distTo: '最大',
    distMinAriaLabel: '最短距離（km）',
    distMaxAriaLabel: '最長距離（km）',
    dateFromAriaLabel: '開始日',
    dateToAriaLabel: '終了日',
    periodoAriaLabel: '期間で絞り込む',
    estadoAriaLabel: '場所で絞り込む',
    fonteFilterAriaLabel: '情報源で絞り込む',
    homeAriaLabel: '現在地と言語',
    langAriaLabel: '言語',
    clearFiltersAriaLabel: 'フィルターをクリア',
    allLocations: 'すべて',
    allBrazil: 'ブラジル全域',
    allSources: 'すべての情報源',
    nSources: n => _pl(n, { other: '情報源 {n} 件' }),
    allSelos: 'すべてのラベル',
    nSelos: n => _pl(n, { other: 'ラベル {n} 件' }),
    seloNames: { platinum: 'Platinum', gold: 'Gold', elite: 'Elite', label: 'Label', major: 'Major' },
    seloLegendTitle: '公式ラベル',
    seloLegendIntro: '世界陸連（World Athletics）は世界の優れたロードレースにラベルを付与しています。上位から順に：',
    seloLegendMajor: 'Major：アボット・ワールドマラソンメジャーズ（Abbott World Marathon Majors）の7大会の一つ。世界で最も権威あるマラソンです。',
    seloLegendAria: 'ラベルの意味',
    badgeNovo: '新着',
    badgeCancelado: '中止',
    loading: '読み込み中...',
    loadError: 'データの読み込みに失敗しました。',
    clearFilters: 'フィルターをクリア',
    noResults: '現在の条件に一致するレースはありません。',
    raceCount: n => _pl(n, { other: '{n} 件のレース' }),
    pastSectionLabel: '🏁 過去15日間のレース',
    past15: '15日前から',
    today: '今日から',
    next30: '今後30日間',
    next90: '今後3か月',
    next180: '今後6か月',
    allTime: '全期間',
    custom: '期間を指定',
    distancesHeader: '距離',
    dateColHeader: '日付',
    timeColHeader: '時刻',
    sourcesHeader: '情報源',
    registerBtn: 'エントリー →',
    labelDateFrom: '開始',
    labelDateTo: '終了',
    labelDistFrom: '最小',
    labelDistTo: '最大',
    monthNames: ['1月','2月','3月','4月','5月','6月','7月','8月','9月','10月','11月','12月'],
    dayNames: ['日','月','火','水','木','金','土'],
    today_label: '今日',
    tomorrow_label: '明日',
    yesterday_label: '昨日',
    groupBrasil: 'ブラジル',
    allCountry: country => `${country}全域`,
    pills: { '5': '5K', '10': '10K', '15': '15K', '21': '21K', '42': '42K', 'outros': 'その他' },
    periodoSelect: '期間で絞り込む',
  },
  ko: {
    siteTitle: '로드 레이스 캘린더 — 브라질과 전 세계 마라톤·러닝 대회',
    headerTitle: '로드 레이스 캘린더',
    searchPlaceholder: '대회 검색...',
    searchAriaLabel: '대회 검색',
    modeSelect: '선택',
    modeInterval: '범위',
    distFrom: '최소',
    distTo: '최대',
    distMinAriaLabel: '최소 거리(km)',
    distMaxAriaLabel: '최대 거리(km)',
    dateFromAriaLabel: '시작일',
    dateToAriaLabel: '종료일',
    periodoAriaLabel: '기간별 필터',
    estadoAriaLabel: '지역별 필터',
    fonteFilterAriaLabel: '출처별 필터',
    homeAriaLabel: '내 위치 및 언어',
    langAriaLabel: '언어',
    clearFiltersAriaLabel: '필터 초기화',
    allLocations: '전체',
    allBrazil: '브라질 전체',
    allSources: '모든 출처',
    nSources: n => _pl(n, { other: '출처 {n}개' }),
    allSelos: '모든 라벨',
    nSelos: n => _pl(n, { other: '라벨 {n}개' }),
    seloNames: { platinum: 'Platinum', gold: 'Gold', elite: 'Elite', label: 'Label', major: 'Major' },
    seloLegendTitle: '공식 라벨',
    seloLegendIntro: '세계육상연맹(World Athletics)은 세계 최고의 로드 레이스에 라벨을 부여합니다. 높은 등급부터:',
    seloLegendMajor: 'Major: 애보트 월드 마라톤 메이저스(Abbott World Marathon Majors) 7개 대회 중 하나 — 세계에서 가장 권위 있는 마라톤입니다.',
    seloLegendAria: '라벨의 의미',
    badgeNovo: '신규',
    badgeCancelado: '취소됨',
    loading: '불러오는 중...',
    loadError: '데이터를 불러오지 못했습니다.',
    clearFilters: '필터 초기화',
    noResults: '현재 필터에 맞는 대회가 없습니다.',
    raceCount: n => _pl(n, { other: '대회 {n}개' }),
    pastSectionLabel: '🏁 최근 15일간의 대회',
    past15: '15일 전부터',
    today: '오늘부터',
    next30: '향후 30일',
    next90: '향후 3개월',
    next180: '향후 6개월',
    allTime: '전체 기간',
    custom: '기간 직접 지정',
    distancesHeader: '거리',
    dateColHeader: '날짜',
    timeColHeader: '시간',
    sourcesHeader: '출처',
    registerBtn: '참가 신청 →',
    labelDateFrom: '시작',
    labelDateTo: '종료',
    labelDistFrom: '최소',
    labelDistTo: '최대',
    monthNames: ['1월','2월','3월','4월','5월','6월','7월','8월','9월','10월','11월','12월'],
    dayNames: ['일','월','화','수','목','금','토'],
    today_label: '오늘',
    tomorrow_label: '내일',
    yesterday_label: '어제',
    groupBrasil: '브라질',
    allCountry: country => `${country} 전체`,
    pills: { '5': '5K', '10': '10K', '15': '15K', '21': '21K', '42': '42K', 'outros': '기타' },
    periodoSelect: '기간별 필터',
  },
  'zh-cn': {
    siteTitle: '路跑赛事日历 — 巴西与全球马拉松、半程马拉松及路跑比赛',
    headerTitle: '路跑赛事日历',
    searchPlaceholder: '搜索赛事...',
    searchAriaLabel: '搜索赛事',
    modeSelect: '选择',
    modeInterval: '范围',
    distFrom: '从',
    distTo: '至',
    distMinAriaLabel: '最短距离（公里）',
    distMaxAriaLabel: '最长距离（公里）',
    dateFromAriaLabel: '开始日期',
    dateToAriaLabel: '结束日期',
    periodoAriaLabel: '按时间段筛选',
    estadoAriaLabel: '按地点筛选',
    fonteFilterAriaLabel: '按来源筛选',
    homeAriaLabel: '我的位置和语言',
    langAriaLabel: '语言',
    clearFiltersAriaLabel: '清除筛选',
    allLocations: '全部',
    allBrazil: '巴西全境',
    allSources: '全部来源',
    nSources: n => _pl(n, { other: '{n} 个来源' }),
    allSelos: '全部标牌',
    nSelos: n => _pl(n, { other: '{n} 个标牌' }),
    seloNames: { platinum: 'Platinum', gold: 'Gold', elite: 'Elite', label: 'Label', major: 'Major' },
    seloLegendTitle: '官方标牌',
    seloLegendIntro: '世界田联（World Athletics）为全球最优秀的路跑赛事授予标牌。由高到低：',
    seloLegendMajor: 'Major：雅培世界马拉松大满贯（Abbott World Marathon Majors）七项赛事之一——全球最负盛名的马拉松。',
    seloLegendAria: '标牌的含义',
    badgeNovo: '新',
    badgeCancelado: '已取消',
    loading: '加载中...',
    loadError: '数据加载失败。',
    clearFilters: '清除筛选',
    noResults: '没有符合当前筛选条件的赛事。',
    raceCount: n => _pl(n, { other: '{n} 场赛事' }),
    pastSectionLabel: '🏁 过去 15 天的赛事',
    past15: '自 15 天前起',
    today: '从今天起',
    next30: '未来 30 天',
    next90: '未来 3 个月',
    next180: '未来 6 个月',
    allTime: '全部时间',
    custom: '自定义范围',
    distancesHeader: '距离',
    dateColHeader: '日期',
    timeColHeader: '时间',
    sourcesHeader: '来源',
    registerBtn: '报名 →',
    labelDateFrom: '从',
    labelDateTo: '至',
    labelDistFrom: '从',
    labelDistTo: '至',
    monthNames: ['1月','2月','3月','4月','5月','6月','7月','8月','9月','10月','11月','12月'],
    dayNames: ['周日','周一','周二','周三','周四','周五','周六'],
    today_label: '今天',
    tomorrow_label: '明天',
    yesterday_label: '昨天',
    groupBrasil: '巴西',
    allCountry: country => `${country}（全部）`,
    pills: { '5': '5K', '10': '10K', '15': '15K', '21': '21K', '42': '42K', 'outros': '其他' },
    periodoSelect: '按时间段筛选',
  },
  'zh-tw': {
    siteTitle: '路跑賽事行事曆 — 巴西與全球馬拉松、半程馬拉松及路跑比賽',
    headerTitle: '路跑賽事行事曆',
    searchPlaceholder: '搜尋賽事...',
    searchAriaLabel: '搜尋賽事',
    modeSelect: '選擇',
    modeInterval: '範圍',
    distFrom: '從',
    distTo: '至',
    distMinAriaLabel: '最短距離（公里）',
    distMaxAriaLabel: '最長距離（公里）',
    dateFromAriaLabel: '開始日期',
    dateToAriaLabel: '結束日期',
    periodoAriaLabel: '依期間篩選',
    estadoAriaLabel: '依地點篩選',
    fonteFilterAriaLabel: '依來源篩選',
    homeAriaLabel: '我的位置與語言',
    langAriaLabel: '語言',
    clearFiltersAriaLabel: '清除篩選',
    allLocations: '全部',
    allBrazil: '巴西全境',
    allSources: '全部來源',
    nSources: n => _pl(n, { other: '{n} 個來源' }),
    allSelos: '全部標籤',
    nSelos: n => _pl(n, { other: '{n} 個標籤' }),
    seloNames: { platinum: 'Platinum', gold: 'Gold', elite: 'Elite', label: 'Label', major: 'Major' },
    seloLegendTitle: '官方標籤',
    seloLegendIntro: '世界田徑總會（World Athletics）為全球最優秀的路跑賽事授予標籤。由高至低：',
    seloLegendMajor: 'Major：亞培世界馬拉松大滿貫（Abbott World Marathon Majors）七項賽事之一——全球最負盛名的馬拉松。',
    seloLegendAria: '標籤的意義',
    badgeNovo: '新',
    badgeCancelado: '已取消',
    loading: '載入中...',
    loadError: '資料載入失敗。',
    clearFilters: '清除篩選',
    noResults: '沒有符合目前篩選條件的賽事。',
    raceCount: n => _pl(n, { other: '{n} 場賽事' }),
    pastSectionLabel: '🏁 過去 15 天的賽事',
    past15: '自 15 天前起',
    today: '從今天起',
    next30: '未來 30 天',
    next90: '未來 3 個月',
    next180: '未來 6 個月',
    allTime: '全部期間',
    custom: '自訂範圍',
    distancesHeader: '距離',
    dateColHeader: '日期',
    timeColHeader: '時間',
    sourcesHeader: '來源',
    registerBtn: '報名 →',
    labelDateFrom: '從',
    labelDateTo: '至',
    labelDistFrom: '從',
    labelDistTo: '至',
    monthNames: ['1月','2月','3月','4月','5月','6月','7月','8月','9月','10月','11月','12月'],
    dayNames: ['週日','週一','週二','週三','週四','週五','週六'],
    today_label: '今天',
    tomorrow_label: '明天',
    yesterday_label: '昨天',
    groupBrasil: '巴西',
    allCountry: country => `${country}（全部）`,
    pills: { '5': '5K', '10': '10K', '15': '15K', '21': '21K', '42': '42K', 'outros': '其他' },
    periodoSelect: '依期間篩選',
  },
  th: {
    siteTitle: 'ปฏิทินงานวิ่งถนน — บราซิลและทั่วโลก',
    headerTitle: 'ปฏิทินงานวิ่งถนน',
    searchPlaceholder: 'ค้นหางานวิ่ง...',
    searchAriaLabel: 'ค้นหางานวิ่ง',
    modeSelect: 'เลือก',
    modeInterval: 'ช่วง',
    distFrom: 'ตั้งแต่',
    distTo: 'ถึง',
    distMinAriaLabel: 'ระยะทางขั้นต่ำ (กม.)',
    distMaxAriaLabel: 'ระยะทางสูงสุด (กม.)',
    dateFromAriaLabel: 'วันที่เริ่มต้น',
    dateToAriaLabel: 'วันที่สิ้นสุด',
    periodoAriaLabel: 'กรองตามช่วงเวลา',
    estadoAriaLabel: 'กรองตามสถานที่',
    fonteFilterAriaLabel: 'กรองตามแหล่งที่มา',
    homeAriaLabel: 'ตำแหน่งและภาษาของฉัน',
    langAriaLabel: 'ภาษา',
    clearFiltersAriaLabel: 'ล้างตัวกรอง',
    allLocations: 'ทั้งหมด',
    allBrazil: 'บราซิลทั้งหมด',
    allSources: 'ทุกแหล่งที่มา',
    nSources: n => _pl(n, { other: '{n} แหล่งที่มา' }),
    allSelos: 'ตรารับรองทั้งหมด',
    nSelos: n => _pl(n, { other: '{n} ตรารับรอง' }),
    seloNames: { platinum: 'Platinum', gold: 'Gold', elite: 'Elite', label: 'Label', major: 'Major' },
    seloLegendTitle: 'ตรารับรองอย่างเป็นทางการ',
    seloLegendIntro: 'World Athletics (สหพันธ์กรีฑานานาชาติ) มอบตรารับรองให้งานวิ่งถนนที่ดีที่สุดในโลก จากสูงสุดไปต่ำสุด:',
    seloLegendMajor: 'Major: หนึ่งใน 7 รายการ Abbott World Marathon Majors — มาราธอนที่ทรงเกียรติที่สุดในโลก',
    seloLegendAria: 'ความหมายของตรารับรอง',
    badgeNovo: 'ใหม่',
    badgeCancelado: 'ยกเลิก',
    loading: 'กำลังโหลด...',
    loadError: 'โหลดข้อมูลไม่สำเร็จ',
    clearFilters: 'ล้างตัวกรอง',
    noResults: 'ไม่พบงานวิ่งที่ตรงกับตัวกรองปัจจุบัน',
    raceCount: n => _pl(n, { other: '{n} งานวิ่ง' }),
    pastSectionLabel: '🏁 งานวิ่งใน 15 วันที่ผ่านมา',
    past15: 'ตั้งแต่ 15 วันก่อน',
    today: 'ตั้งแต่วันนี้',
    next30: '30 วันข้างหน้า',
    next90: '3 เดือนข้างหน้า',
    next180: '6 เดือนข้างหน้า',
    allTime: 'ทุกช่วงเวลา',
    custom: 'กำหนดช่วงเอง',
    distancesHeader: 'ระยะทาง',
    dateColHeader: 'วันที่',
    timeColHeader: 'เวลา',
    sourcesHeader: 'แหล่งที่มา',
    registerBtn: 'สมัคร →',
    labelDateFrom: 'ตั้งแต่',
    labelDateTo: 'ถึง',
    labelDistFrom: 'ตั้งแต่',
    labelDistTo: 'ถึง',
    monthNames: ['มกราคม','กุมภาพันธ์','มีนาคม','เมษายน','พฤษภาคม','มิถุนายน','กรกฎาคม','สิงหาคม','กันยายน','ตุลาคม','พฤศจิกายน','ธันวาคม'],
    dayNames: ['อา.','จ.','อ.','พ.','พฤ.','ศ.','ส.'],
    today_label: 'วันนี้',
    tomorrow_label: 'พรุ่งนี้',
    yesterday_label: 'เมื่อวาน',
    groupBrasil: 'บราซิล',
    allCountry: country => `${country} ทั้งหมด`,
    pills: { '5': '5K', '10': '10K', '15': '15K', '21': '21K', '42': '42K', 'outros': 'อื่น ๆ' },
    periodoSelect: 'กรองตามช่วงเวลา',
  },
  he: {
    siteTitle: 'לוח מרוצי כביש — ברזיל וכל העולם',
    headerTitle: 'לוח מרוצי כביש',
    searchPlaceholder: 'חיפוש מרוץ...',
    searchAriaLabel: 'חיפוש מרוץ',
    modeSelect: 'בחירה',
    modeInterval: 'טווח',
    distFrom: 'מ־',
    distTo: 'עד',
    distMinAriaLabel: 'מרחק מינימלי בק״מ',
    distMaxAriaLabel: 'מרחק מקסימלי בק״מ',
    dateFromAriaLabel: 'תאריך התחלה',
    dateToAriaLabel: 'תאריך סיום',
    periodoAriaLabel: 'סינון לפי תקופה',
    estadoAriaLabel: 'סינון לפי מיקום',
    fonteFilterAriaLabel: 'סינון לפי מקור',
    homeAriaLabel: 'המיקום והשפה שלי',
    langAriaLabel: 'שפה',
    clearFiltersAriaLabel: 'ניקוי מסננים',
    allLocations: 'הכול',
    allBrazil: 'כל ברזיל',
    allSources: 'כל המקורות',
    nSources: n => _pl(n, { one: 'מקור אחד', two: '{n} מקורות', other: '{n} מקורות' }),
    allSelos: 'כל התווים',
    nSelos: n => _pl(n, { one: 'תו אחד', two: '{n} תווים', other: '{n} תווים' }),
    seloNames: { platinum: 'Platinum', gold: 'Gold', elite: 'Elite', label: 'Label', major: 'Major' },
    seloLegendTitle: 'תווים רשמיים',
    seloLegendIntro: 'World Athletics (ההתאחדות הבינלאומית לאתלטיקה) מעניקה תווים למרוצי הכביש הטובים בעולם. מהגבוה לנמוך:',
    seloLegendMajor: 'Major: אחד מ־7 מרתוני Abbott World Marathon Majors — המרתונים היוקרתיים ביותר בעולם.',
    seloLegendAria: 'מה פירוש התווים',
    badgeNovo: 'חדש',
    badgeCancelado: 'בוטל',
    loading: 'טוען...',
    loadError: 'שגיאה בטעינת הנתונים.',
    clearFilters: 'ניקוי מסננים',
    noResults: 'לא נמצאו מרוצים לפי המסננים הנוכחיים.',
    raceCount: n => _pl(n, { one: 'מרוץ אחד', two: '{n} מרוצים', other: '{n} מרוצים' }),
    pastSectionLabel: '🏁 מרוצים ב־15 הימים האחרונים',
    past15: 'מלפני 15 ימים',
    today: 'מהיום',
    next30: '30 הימים הקרובים',
    next90: '3 החודשים הקרובים',
    next180: '6 החודשים הקרובים',
    allTime: 'כל התקופה',
    custom: 'טווח מותאם אישית',
    distancesHeader: 'מרחקים',
    dateColHeader: 'תאריך',
    timeColHeader: 'שעה',
    sourcesHeader: 'מקורות',
    registerBtn: 'להרשמה ←',
    labelDateFrom: 'מ־',
    labelDateTo: 'עד',
    labelDistFrom: 'מ־',
    labelDistTo: 'עד',
    monthNames: ['ינואר','פברואר','מרץ','אפריל','מאי','יוני','יולי','אוגוסט','ספטמבר','אוקטובר','נובמבר','דצמבר'],
    dayNames: ['יום א׳','יום ב׳','יום ג׳','יום ד׳','יום ה׳','יום ו׳','שבת'],
    today_label: 'היום',
    tomorrow_label: 'מחר',
    yesterday_label: 'אתמול',
    groupBrasil: 'ברזיל',
    allCountry: country => `כל ${country}`,
    pills: { '5': '5K', '10': '10K', '15': '15K', '21': '21K', '42': '42K', 'outros': 'אחר' },
    periodoSelect: 'סינון לפי תקופה',
  },
  id: {
    siteTitle: 'Kalender Lomba Lari Jalan Raya — Brasil dan Dunia',
    headerTitle: 'Kalender Lomba Lari Jalan Raya',
    searchPlaceholder: 'Cari lomba...',
    searchAriaLabel: 'Cari lomba',
    modeSelect: 'Pilih',
    modeInterval: 'Rentang',
    distFrom: 'Dari',
    distTo: 'Sampai',
    distMinAriaLabel: 'Jarak minimum dalam km',
    distMaxAriaLabel: 'Jarak maksimum dalam km',
    dateFromAriaLabel: 'Tanggal mulai',
    dateToAriaLabel: 'Tanggal akhir',
    periodoAriaLabel: 'Filter menurut periode',
    estadoAriaLabel: 'Filter menurut lokasi',
    fonteFilterAriaLabel: 'Filter menurut sumber',
    homeAriaLabel: 'Lokasi dan bahasa saya',
    langAriaLabel: 'Bahasa',
    clearFiltersAriaLabel: 'Hapus filter',
    allLocations: 'Semua',
    allBrazil: 'Seluruh Brasil',
    allSources: 'Semua sumber',
    nSources: n => _pl(n, { other: '{n} sumber' }),
    allSelos: 'Semua label',
    nSelos: n => _pl(n, { other: '{n} label' }),
    seloNames: { platinum: 'Platinum', gold: 'Gold', elite: 'Elite', label: 'Label', major: 'Major' },
    seloLegendTitle: 'Label resmi',
    seloLegendIntro: 'World Athletics (badan atletik dunia) memberikan label kepada lomba lari jalan raya terbaik di dunia. Dari tertinggi ke terendah:',
    seloLegendMajor: 'Major: salah satu dari 7 Abbott World Marathon Majors — maraton paling bergengsi di dunia.',
    seloLegendAria: 'Arti label',
    badgeNovo: 'baru',
    badgeCancelado: 'dibatalkan',
    loading: 'Memuat...',
    loadError: 'Gagal memuat data.',
    clearFilters: 'Hapus filter',
    noResults: 'Tidak ada lomba yang cocok dengan filter saat ini.',
    raceCount: n => _pl(n, { other: '{n} lomba' }),
    pastSectionLabel: '🏁 Lomba dalam 15 hari terakhir',
    past15: 'Sejak 15 hari lalu',
    today: 'Mulai hari ini',
    next30: '30 hari ke depan',
    next90: '3 bulan ke depan',
    next180: '6 bulan ke depan',
    allTime: 'Semua waktu',
    custom: 'Rentang khusus',
    distancesHeader: 'Jarak',
    dateColHeader: 'Tanggal',
    timeColHeader: 'Waktu',
    sourcesHeader: 'Sumber',
    registerBtn: 'Daftar →',
    labelDateFrom: 'Dari',
    labelDateTo: 'Sampai',
    labelDistFrom: 'Dari',
    labelDistTo: 'Sampai',
    monthNames: ['Januari','Februari','Maret','April','Mei','Juni','Juli','Agustus','September','Oktober','November','Desember'],
    dayNames: ['Min','Sen','Sel','Rab','Kam','Jum','Sab'],
    today_label: 'Hari ini',
    tomorrow_label: 'Besok',
    yesterday_label: 'Kemarin',
    groupBrasil: 'Brasil',
    allCountry: country => `Seluruh ${country}`,
    pills: { '5': '5K', '10': '10K', '15': '15K', '21': '21K', '42': '42K', 'outros': 'Lainnya' },
    periodoSelect: 'Filter menurut periode',
  },
  ms: {
    siteTitle: 'Kalendar Larian Jalan Raya — Brazil dan Dunia',
    headerTitle: 'Kalendar Larian Jalan Raya',
    searchPlaceholder: 'Cari larian...',
    searchAriaLabel: 'Cari larian',
    modeSelect: 'Pilih',
    modeInterval: 'Julat',
    distFrom: 'Dari',
    distTo: 'Hingga',
    distMinAriaLabel: 'Jarak minimum dalam km',
    distMaxAriaLabel: 'Jarak maksimum dalam km',
    dateFromAriaLabel: 'Tarikh mula',
    dateToAriaLabel: 'Tarikh tamat',
    periodoAriaLabel: 'Tapis mengikut tempoh',
    estadoAriaLabel: 'Tapis mengikut lokasi',
    fonteFilterAriaLabel: 'Tapis mengikut sumber',
    homeAriaLabel: 'Lokasi dan bahasa saya',
    langAriaLabel: 'Bahasa',
    clearFiltersAriaLabel: 'Kosongkan penapis',
    allLocations: 'Semua',
    allBrazil: 'Seluruh Brazil',
    allSources: 'Semua sumber',
    nSources: n => _pl(n, { other: '{n} sumber' }),
    allSelos: 'Semua label',
    nSelos: n => _pl(n, { other: '{n} label' }),
    seloNames: { platinum: 'Platinum', gold: 'Gold', elite: 'Elite', label: 'Label', major: 'Major' },
    seloLegendTitle: 'Label rasmi',
    seloLegendIntro: 'World Athletics (badan olahraga sedunia) menganugerahkan label kepada larian jalan raya terbaik di dunia. Dari tertinggi ke terendah:',
    seloLegendMajor: 'Major: salah satu daripada 7 Abbott World Marathon Majors — maraton paling berprestij di dunia.',
    seloLegendAria: 'Maksud label',
    badgeNovo: 'baharu',
    badgeCancelado: 'dibatalkan',
    loading: 'Memuatkan...',
    loadError: 'Ralat semasa memuatkan data.',
    clearFilters: 'Kosongkan penapis',
    noResults: 'Tiada larian ditemui dengan penapis semasa.',
    raceCount: n => _pl(n, { other: '{n} larian' }),
    pastSectionLabel: '🏁 Larian dalam 15 hari lepas',
    past15: 'Sejak 15 hari lalu',
    today: 'Mulai hari ini',
    next30: '30 hari akan datang',
    next90: '3 bulan akan datang',
    next180: '6 bulan akan datang',
    allTime: 'Sepanjang masa',
    custom: 'Julat tersuai',
    distancesHeader: 'Jarak',
    dateColHeader: 'Tarikh',
    timeColHeader: 'Masa',
    sourcesHeader: 'Sumber',
    registerBtn: 'Daftar →',
    labelDateFrom: 'Dari',
    labelDateTo: 'Hingga',
    labelDistFrom: 'Dari',
    labelDistTo: 'Hingga',
    monthNames: ['Januari','Februari','Mac','April','Mei','Jun','Julai','Ogos','September','Oktober','November','Disember'],
    dayNames: ['Ahd','Isn','Sel','Rab','Kha','Jum','Sab'],
    today_label: 'Hari ini',
    tomorrow_label: 'Esok',
    yesterday_label: 'Semalam',
    groupBrasil: 'Brazil',
    allCountry: country => `Seluruh ${country}`,
    pills: { '5': '5K', '10': '10K', '15': '15K', '21': '21K', '42': '42K', 'outros': 'Lain-lain' },
    periodoSelect: 'Tapis mengikut tempoh',
  },
};

const T = STRINGS[LANG] || STRINGS.en;

// ---------------------------------------------------------------------------
// DOM references (populated after DOMContentLoaded)
// ---------------------------------------------------------------------------
let searchInput, cardsList, emptyState, btnClear, btnClearEmpty,
    periodoSelect, estadoFilterBtn, estadoFilterLabel, estadoFilterDropdown,
    fonteFilterBtn, fonteFilterLabel, fonteFilterDropdown,
    resultCount, btnLang, btnHome,
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
  selos:        new Set(),
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
  try {
    // Boot shard first (~1/3 of the full payload: default-filter window) so
    // the first paint doesn't wait for the whole dataset on mobile.
    let res = await fetch('/corridas-boot.json', { cache: 'no-cache' });
    if (!res.ok) res = await fetch('/corridas.json', { cache: 'no-cache' });
    if (!res.ok) throw new Error(res.status);
    const json = await res.json();
    allCorridas = json.corridas || json;
    // Start the full download in parallel with geo detection inside
    // initFilters; apply it only after the first paint.
    const fullPromise = json.parcial
      ? fetch('/corridas.json', { cache: 'no-cache' }).catch(() => null)
      : null;
    const paisSet = new Set(allCorridas.map(c => c.pais || 'BR').filter(Boolean));
    await loadLocationsData(paisSet);
    await initFilters();
    if (fullPromise) await _applyFullData(fullPromise);
    // Automation/test hook: the dataset is as complete as it will get and no
    // further background re-render will replace the card list.
    document.body.dataset.fullDataReady = '1';
  } catch (e) {
    resultCount.textContent = T.loadError;
    console.error('loadData error', e);
  } finally {
    // Data is fully loaded (or failed) — lift the loading screen. It runs its
    // zoom-in-on-the-worn-shoe transition and reveals the now-stable card list.
    if (window.Loading) window.Loading.done();
  }
}

async function _applyFullData(fullPromise) {
  try {
    const res = await fullPromise;
    if (!res || !res.ok) return;
    const json = await res.json();
    const full = json.corridas || json;
    if (!Array.isArray(full) || full.length < allCorridas.length) return;
    allCorridas = full;
    await loadLocationsData(new Set(full.map(c => c.pais || 'BR').filter(Boolean)));
    populateEstadoFilter({ skipGeo: true });
    populateFontesFilter();
    populateSelosFilter();
    applyFilters();
    renderCards();
    updateCount();
  } catch (e) {
    console.error('full data load error', e);
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
  _buildSeloWidget();
  populateEstadoFilter({ skipGeo: true });
  populateFontesFilter();
  populateSelosFilter();

  // First paint immediately — geolocation (IP lookup, up to 3 external
  // services) must never hold the card list hostage. The geo filter is
  // applied in a second render when (and if) it resolves.
  const estadoAtFirstPaint = state.estado;
  applyFilters();
  renderCards();
  updateCount();
  _anchorOpenMonth();

  // Geolocation must NOT hold the card list — nor the full-dataset load —
  // hostage. It runs fire-and-forget (the IP lookups can be slow or blocked by
  // ad/privacy blockers); the estado filter is applied in a later render when
  // (and if) it resolves. Crucially, NOT awaiting it here lets loadData proceed
  // to _applyFullData immediately, so far-future events (beyond the boot-shard
  // window) appear as soon as the full payload arrives instead of waiting on geo.
  detectGeoEstado().then(geo => {
    // Respect any location the user picked while geo was in flight.
    if (geo && _estadoAvailableValues.has(geo) && state.estado === estadoAtFirstPaint) {
      state.estado = geo;
      _geoApplied  = geo;
      _updateEstadoLabel();
      populateEstadoFilter({ skipGeo: true });
      populateFontesFilter();
      applyFilters();
      renderCards();
      updateCount();
      // The list above the current month changed — re-anchor (still load-time).
      _anchorOpenMonth();
    }
  });
}

// ---------------------------------------------------------------------------
// Persistence
// ---------------------------------------------------------------------------
function loadSavedFilters() { return null; }
function restoreFilters() {}
function saveFilters() {}

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
  BR: 'Brasil',     AR: 'Argentina',  PT: 'Portugal',   IT: 'Itália',     DE: 'Alemanha',
  FR: 'França',     GB: 'Reino Unido', US: 'EUA',       JP: 'Japão',      AU: 'Austrália',
  ES: 'Espanha',    CL: 'Chile',      CO: 'Colômbia',   MX: 'México',     PE: 'Peru',
  NL: 'Países Baixos', AT: 'Áustria', CH: 'Suíça',      SE: 'Suécia',     NO: 'Noruega',
  DK: 'Dinamarca',  FI: 'Finlândia',  PL: 'Polônia',    CZ: 'República Tcheca',
  ZA: 'África do Sul', KE: 'Quênia',  ET: 'Etiópia',    CN: 'China',      KR: 'Coreia do Sul',
  CA: 'Canadá',     NZ: 'Nova Zelândia', PY: 'Paraguai', UY: 'Uruguai',
  IE: 'Irlanda',    GR: 'Grécia',     AD: 'Andorra',    BM: 'Bermuda',
  BO: 'Bolívia',    PH: 'Filipinas',  CG: 'República do Congo', BA: 'Bósnia e Herzegovina',
  HK: 'Hong Kong',
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
  'Hong Kong':             { en: 'Hong Kong',                es: 'Hong Kong',            de: 'Hongkong',                  fr: 'Hong Kong' },
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
  IT: {
    VE:  { pt: 'Veneza',      en: 'Venice',      es: 'Venecia',    de: 'Venedig',     fr: 'Venise' },
    RM:  { pt: 'Roma',        en: 'Rome',         es: 'Roma',       de: 'Rom',         fr: 'Rome' },
    MI:  { pt: 'Milão',       en: 'Milan',        es: 'Milán',      de: 'Mailand',     fr: 'Milan' },
    NA:  { pt: 'Nápoles',     en: 'Naples',       es: 'Nápoles',    de: 'Neapel',      fr: 'Naples' },
    TO:  { pt: 'Turim',       en: 'Turin',        es: 'Turín',      de: 'Turin',       fr: 'Turin' },
    BZ:  { pt: 'Bolzano',     en: 'Bolzano',      es: 'Bolzano',    de: 'Bozen',       fr: 'Bolzano' },
    FI:  { pt: 'Florença',    en: 'Florence',     es: 'Florencia',  de: 'Florenz',     fr: 'Florence' },
    BO:  { pt: 'Bolonha',     en: 'Bologna',      es: 'Bolonia',    de: 'Bologna',     fr: 'Bologne' },
  },
  JP: {
    13:  { pt: 'Tóquio',      en: 'Tokyo',        es: 'Tokio',      de: 'Tokio',       fr: 'Tokyo' },
    27:  { pt: 'Osaka',       en: 'Osaka',        es: 'Osaka',      de: 'Osaka',       fr: 'Osaka' },
  },
  GR: {
    A:   { pt: 'Atenas',      en: 'Athens',       es: 'Atenas',     de: 'Athen',       fr: 'Athènes' },
    B:   { pt: 'Salônica',    en: 'Thessaloniki',  es: 'Salónica',  de: 'Thessaloniki', fr: 'Thessalonique' },
  },
  DK: {
    84:  { pt: 'Copenhague',  en: 'Copenhagen',   es: 'Copenhague', de: 'Kopenhagen',  fr: 'Copenhague' },
  },
  SE: {
    AB:  { pt: 'Estocolmo',   en: 'Stockholm',    es: 'Estocolmo',  de: 'Stockholm',   fr: 'Stockholm' },
  },
  IE: {
    D:   { pt: 'Dublin',      en: 'Dublin',       es: 'Dublín',     de: 'Dublin',      fr: 'Dublin' },
  },
  FR: {
    75:  { pt: 'Paris',       en: 'Paris',        es: 'París',      de: 'Paris',       fr: 'Paris' },
    69:  { pt: 'Lyon',        en: 'Lyon',         es: 'Lyon',       de: 'Lyon',        fr: 'Lyon' },
    13:  { pt: 'Marselha',    en: 'Marseille',    es: 'Marsella',   de: 'Marseille',   fr: 'Marseille' },
    33:  { pt: 'Bordeaux',    en: 'Bordeaux',     es: 'Burdeos',    de: 'Bordeaux',    fr: 'Bordeaux' },
    67:  { pt: 'Estrasburgo', en: 'Strasbourg',   es: 'Estrasburgo',de: 'Straßburg',   fr: 'Strasbourg' },
    '06':  { pt: 'Nice',        en: 'Nice',         es: 'Niza',       de: 'Nizza',       fr: 'Nice' },
  },
  PT: {
    11:  { pt: 'Lisboa',      en: 'Lisbon',       es: 'Lisboa',     de: 'Lissabon',    fr: 'Lisbonne' },
    13:  { pt: 'Porto',       en: 'Porto',        es: 'Oporto',     de: 'Porto',       fr: 'Porto' },
  },
  PL: {
    14:  { pt: 'Varsóvia',    en: 'Warsaw',       es: 'Varsovia',   de: 'Warschau',    fr: 'Varsovie' },
  },
  CZ: {
    PR:  { pt: 'Praga',       en: 'Prague',       es: 'Praga',      de: 'Prag',        fr: 'Prague' },
  },
  NO: {
    '03':  { pt: 'Oslo',        en: 'Oslo',         es: 'Oslo',       de: 'Oslo',        fr: 'Oslo' },
  },
  FI: {
    18:  { pt: 'Helsínquia',  en: 'Helsinki',     es: 'Helsinki',   de: 'Helsinki',    fr: 'Helsinki' },
  },
  CH: {
    GE:  { pt: 'Genebra',     en: 'Geneva',       es: 'Ginebra',    de: 'Genf',        fr: 'Genève' },
    ZH:  { pt: 'Zurique',     en: 'Zurich',       es: 'Zúrich',     de: 'Zürich',      fr: 'Zurich' },
  },
  BR: {
    // DF is the only state whose display name differs from the BR.json entry ("Distrito Federal")
    DF:  { pt: 'Brasília',    en: 'Brasília',     es: 'Brasília',   de: 'Brasília',    fr: 'Brasília' },
  },
  HK: {
    HKI: { pt: 'Ilha de Hong Kong', en: 'Hong Kong Island', es: 'Isla de Hong Kong', de: 'Hongkong-Insel', fr: 'Île de Hong Kong' },
    KLN: { pt: 'Kowloon',           en: 'Kowloon',          es: 'Kowloon',           de: 'Kowloon',        fr: 'Kowloon' },
    NTE: { pt: 'Novos Territórios', en: 'New Territories',  es: 'Nuevos Territorios',de: 'Neue Territorien',fr: 'Nouveaux Territoires' },
  },
};

// Subdivision names for the languages added after the first five, keyed
// '<ISO2>-<code>' (the same entries as _SUBDIV_LABELS above). A language or
// entry missing here falls back to that table's English name.
const _SUBDIV_LABELS_MORE = {
  it: {
    'MX-CMX': 'Città del Messico', 'MX-MEX': 'Stato del Messico', 'DE-BY': 'Baviera', 'DE-NW': 'Renania Settentrionale-Vestfalia',
    'DE-NI': 'Bassa Sassonia', 'DE-SN': 'Sassonia', 'DE-TH': 'Turingia', 'DE-RP': 'Renania-Palatinato',
    'DE-ST': 'Sassonia-Anhalt', 'DE-HE': 'Assia', 'DE-BW': 'Baden-Württemberg', 'DE-BB': 'Brandeburgo',
    'DE-MV': 'Meclemburgo-Pomerania Anteriore', 'GB-ENG': 'Inghilterra', 'GB-SCT': 'Scozia', 'GB-WLS': 'Galles',
    'GB-NIR': 'Irlanda del Nord', 'AT-9': 'Vienna', 'ES-CT': 'Catalogna', 'ES-AN': 'Andalusia',
    'ES-MD': 'Comunità di Madrid', 'ES-PV': 'Paesi Baschi', 'ES-GA': 'Galizia', 'ES-CL': 'Castiglia e León',
    'ES-CM': 'Castiglia-La Mancia', 'ES-AR': 'Aragona', 'ES-VC': 'Comunità Valenciana', 'ES-CN': 'Isole Canarie',
    'ES-NA': 'Navarra', 'CA-QC': 'Québec', 'CA-NB': 'Nuovo Brunswick', 'CA-NS': 'Nuova Scozia',
    'CA-NL': 'Terranova e Labrador', 'NL-NH': 'Olanda Settentrionale', 'NL-ZH': 'Olanda Meridionale', 'NL-NB': 'Brabante Settentrionale',
    'IT-VE': 'Venezia', 'IT-RM': 'Roma', 'IT-MI': 'Milano', 'IT-NA': 'Napoli',
    'IT-TO': 'Torino', 'IT-BZ': 'Bolzano', 'IT-FI': 'Firenze', 'IT-BO': 'Bologna',
    'JP-13': 'Tokyo', 'JP-27': 'Osaka', 'GR-A': 'Atene', 'GR-B': 'Salonicco',
    'DK-84': 'Copenaghen', 'SE-AB': 'Stoccolma', 'IE-D': 'Dublino', 'FR-75': 'Parigi',
    'FR-69': 'Lione', 'FR-13': 'Marsiglia', 'FR-33': 'Bordeaux', 'FR-67': 'Strasburgo',
    'FR-06': 'Nizza', 'PT-11': 'Lisbona', 'PT-13': 'Porto', 'PL-14': 'Varsavia',
    'CZ-PR': 'Praga', 'NO-03': 'Oslo', 'FI-18': 'Helsinki', 'CH-GE': 'Ginevra',
    'CH-ZH': 'Zurigo', 'BR-DF': 'Brasília', 'HK-HKI': 'Isola di Hong Kong', 'HK-KLN': 'Kowloon',
    'HK-NTE': 'Nuovi Territori',
  },
  nl: {
    'MX-CMX': 'Mexico-Stad', 'MX-MEX': 'Staat Mexico', 'DE-BY': 'Beieren', 'DE-NW': 'Noordrijn-Westfalen',
    'DE-NI': 'Nedersaksen', 'DE-SN': 'Saksen', 'DE-TH': 'Thüringen', 'DE-RP': 'Rijnland-Palts',
    'DE-ST': 'Saksen-Anhalt', 'DE-HE': 'Hessen', 'DE-BW': 'Baden-Württemberg', 'DE-BB': 'Brandenburg',
    'DE-MV': 'Mecklenburg-Voor-Pommeren', 'GB-ENG': 'Engeland', 'GB-SCT': 'Schotland', 'GB-WLS': 'Wales',
    'GB-NIR': 'Noord-Ierland', 'AT-9': 'Wenen', 'ES-CT': 'Catalonië', 'ES-AN': 'Andalusië',
    'ES-MD': 'Madrid', 'ES-PV': 'Baskenland', 'ES-GA': 'Galicië', 'ES-CL': 'Castilië en León',
    'ES-CM': 'Castilië-La Mancha', 'ES-AR': 'Aragón', 'ES-VC': 'Valencia', 'ES-CN': 'Canarische Eilanden',
    'ES-NA': 'Navarra', 'CA-QC': 'Quebec', 'CA-NB': 'New Brunswick', 'CA-NS': 'Nova Scotia',
    'CA-NL': 'Newfoundland en Labrador', 'NL-NH': 'Noord-Holland', 'NL-ZH': 'Zuid-Holland', 'NL-NB': 'Noord-Brabant',
    'IT-VE': 'Venetië', 'IT-RM': 'Rome', 'IT-MI': 'Milaan', 'IT-NA': 'Napels',
    'IT-TO': 'Turijn', 'IT-BZ': 'Bolzano', 'IT-FI': 'Florence', 'IT-BO': 'Bologna',
    'JP-13': 'Tokio', 'JP-27': 'Osaka', 'GR-A': 'Athene', 'GR-B': 'Thessaloniki',
    'DK-84': 'Kopenhagen', 'SE-AB': 'Stockholm', 'IE-D': 'Dublin', 'FR-75': 'Parijs',
    'FR-69': 'Lyon', 'FR-13': 'Marseille', 'FR-33': 'Bordeaux', 'FR-67': 'Straatsburg',
    'FR-06': 'Nice', 'PT-11': 'Lissabon', 'PT-13': 'Porto', 'PL-14': 'Warschau',
    'CZ-PR': 'Praag', 'NO-03': 'Oslo', 'FI-18': 'Helsinki', 'CH-GE': 'Genève',
    'CH-ZH': 'Zürich', 'BR-DF': 'Brasília', 'HK-HKI': 'Hongkong Island', 'HK-KLN': 'Kowloon',
    'HK-NTE': 'Nieuwe Gebieden',
  },
  'pt-pt': {
    'MX-CMX': 'Cidade do México', 'MX-MEX': 'Estado do México', 'DE-BY': 'Baviera', 'DE-NW': 'Renânia do Norte-Vestefália',
    'DE-NI': 'Baixa Saxónia', 'DE-SN': 'Saxónia', 'DE-TH': 'Turíngia', 'DE-RP': 'Renânia-Palatinado',
    'DE-ST': 'Saxónia-Anhalt', 'DE-HE': 'Hesse', 'DE-BW': 'Bade-Vurtemberga', 'DE-BB': 'Brandeburgo',
    'DE-MV': 'Meclemburgo-Pomerânia Ocidental', 'GB-ENG': 'Inglaterra', 'GB-SCT': 'Escócia', 'GB-WLS': 'País de Gales',
    'GB-NIR': 'Irlanda do Norte', 'AT-9': 'Viena', 'ES-CT': 'Catalunha', 'ES-AN': 'Andaluzia',
    'ES-MD': 'Comunidade de Madrid', 'ES-PV': 'País Basco', 'ES-GA': 'Galiza', 'ES-CL': 'Castela e Leão',
    'ES-CM': 'Castela-Mancha', 'ES-AR': 'Aragão', 'ES-VC': 'Comunidade Valenciana', 'ES-CN': 'Canárias',
    'ES-NA': 'Navarra', 'CA-QC': 'Quebeque', 'CA-NB': 'Novo Brunswick', 'CA-NS': 'Nova Escócia',
    'CA-NL': 'Terra Nova e Labrador', 'NL-NH': 'Holanda do Norte', 'NL-ZH': 'Holanda do Sul', 'NL-NB': 'Brabante do Norte',
    'IT-VE': 'Veneza', 'IT-RM': 'Roma', 'IT-MI': 'Milão', 'IT-NA': 'Nápoles',
    'IT-TO': 'Turim', 'IT-BZ': 'Bolzano', 'IT-FI': 'Florença', 'IT-BO': 'Bolonha',
    'JP-13': 'Tóquio', 'JP-27': 'Osaca', 'GR-A': 'Atenas', 'GR-B': 'Salónica',
    'DK-84': 'Copenhaga', 'SE-AB': 'Estocolmo', 'IE-D': 'Dublin', 'FR-75': 'Paris',
    'FR-69': 'Lyon', 'FR-13': 'Marselha', 'FR-33': 'Bordéus', 'FR-67': 'Estrasburgo',
    'FR-06': 'Nice', 'PT-11': 'Lisboa', 'PT-13': 'Porto', 'PL-14': 'Varsóvia',
    'CZ-PR': 'Praga', 'NO-03': 'Oslo', 'FI-18': 'Helsínquia', 'CH-GE': 'Genebra',
    'CH-ZH': 'Zurique', 'BR-DF': 'Brasília', 'HK-HKI': 'Ilha de Hong Kong', 'HK-KLN': 'Kowloon',
    'HK-NTE': 'Novos Territórios',
  },
  ru: {
    'MX-CMX': 'Мехико', 'MX-MEX': 'Штат Мехико', 'DE-BY': 'Бавария', 'DE-NW': 'Северный Рейн — Вестфалия',
    'DE-NI': 'Нижняя Саксония', 'DE-SN': 'Саксония', 'DE-TH': 'Тюрингия', 'DE-RP': 'Рейнланд-Пфальц',
    'DE-ST': 'Саксония-Анхальт', 'DE-HE': 'Гессен', 'DE-BW': 'Баден-Вюртемберг', 'DE-BB': 'Бранденбург',
    'DE-MV': 'Мекленбург — Передняя Померания', 'GB-ENG': 'Англия', 'GB-SCT': 'Шотландия', 'GB-WLS': 'Уэльс',
    'GB-NIR': 'Северная Ирландия', 'AT-9': 'Вена', 'ES-CT': 'Каталония', 'ES-AN': 'Андалусия',
    'ES-MD': 'Мадрид', 'ES-PV': 'Страна Басков', 'ES-GA': 'Галисия', 'ES-CL': 'Кастилия и Леон',
    'ES-CM': 'Кастилия — Ла-Манча', 'ES-AR': 'Арагон', 'ES-VC': 'Валенсия', 'ES-CN': 'Канарские острова',
    'ES-NA': 'Наварра', 'CA-QC': 'Квебек', 'CA-NB': 'Нью-Брансуик', 'CA-NS': 'Новая Шотландия',
    'CA-NL': 'Ньюфаундленд и Лабрадор', 'NL-NH': 'Северная Голландия', 'NL-ZH': 'Южная Голландия', 'NL-NB': 'Северный Брабант',
    'IT-VE': 'Венеция', 'IT-RM': 'Рим', 'IT-MI': 'Милан', 'IT-NA': 'Неаполь',
    'IT-TO': 'Турин', 'IT-BZ': 'Больцано', 'IT-FI': 'Флоренция', 'IT-BO': 'Болонья',
    'JP-13': 'Токио', 'JP-27': 'Осака', 'GR-A': 'Афины', 'GR-B': 'Салоники',
    'DK-84': 'Копенгаген', 'SE-AB': 'Стокгольм', 'IE-D': 'Дублин', 'FR-75': 'Париж',
    'FR-69': 'Лион', 'FR-13': 'Марсель', 'FR-33': 'Бордо', 'FR-67': 'Страсбург',
    'FR-06': 'Ницца', 'PT-11': 'Лиссабон', 'PT-13': 'Порту', 'PL-14': 'Варшава',
    'CZ-PR': 'Прага', 'NO-03': 'Осло', 'FI-18': 'Хельсинки', 'CH-GE': 'Женева',
    'CH-ZH': 'Цюрих', 'BR-DF': 'Бразилиа', 'HK-HKI': 'Остров Гонконг', 'HK-KLN': 'Коулун',
    'HK-NTE': 'Новые Территории',
  },
  pl: {
    'MX-CMX': 'Meksyk (miasto)', 'MX-MEX': 'Stan Meksyk', 'DE-BY': 'Bawaria', 'DE-NW': 'Nadrenia Północna-Westfalia',
    'DE-NI': 'Dolna Saksonia', 'DE-SN': 'Saksonia', 'DE-TH': 'Turyngia', 'DE-RP': 'Nadrenia-Palatynat',
    'DE-ST': 'Saksonia-Anhalt', 'DE-HE': 'Hesja', 'DE-BW': 'Badenia-Wirtembergia', 'DE-BB': 'Brandenburgia',
    'DE-MV': 'Meklemburgia-Pomorze Przednie', 'GB-ENG': 'Anglia', 'GB-SCT': 'Szkocja', 'GB-WLS': 'Walia',
    'GB-NIR': 'Irlandia Północna', 'AT-9': 'Wiedeń', 'ES-CT': 'Katalonia', 'ES-AN': 'Andaluzja',
    'ES-MD': 'Madryt', 'ES-PV': 'Kraj Basków', 'ES-GA': 'Galicja', 'ES-CL': 'Kastylia i León',
    'ES-CM': 'Kastylia-La Mancha', 'ES-AR': 'Aragonia', 'ES-VC': 'Walencja', 'ES-CN': 'Wyspy Kanaryjskie',
    'ES-NA': 'Nawarra', 'CA-QC': 'Quebec', 'CA-NB': 'Nowy Brunszwik', 'CA-NS': 'Nowa Szkocja',
    'CA-NL': 'Nowa Fundlandia i Labrador', 'NL-NH': 'Holandia Północna', 'NL-ZH': 'Holandia Południowa', 'NL-NB': 'Brabancja Północna',
    'IT-VE': 'Wenecja', 'IT-RM': 'Rzym', 'IT-MI': 'Mediolan', 'IT-NA': 'Neapol',
    'IT-TO': 'Turyn', 'IT-BZ': 'Bolzano', 'IT-FI': 'Florencja', 'IT-BO': 'Bolonia',
    'JP-13': 'Tokio', 'JP-27': 'Osaka', 'GR-A': 'Ateny', 'GR-B': 'Saloniki',
    'DK-84': 'Kopenhaga', 'SE-AB': 'Sztokholm', 'IE-D': 'Dublin', 'FR-75': 'Paryż',
    'FR-69': 'Lyon', 'FR-13': 'Marsylia', 'FR-33': 'Bordeaux', 'FR-67': 'Strasburg',
    'FR-06': 'Nicea', 'PT-11': 'Lizbona', 'PT-13': 'Porto', 'PL-14': 'Warszawa',
    'CZ-PR': 'Praga', 'NO-03': 'Oslo', 'FI-18': 'Helsinki', 'CH-GE': 'Genewa',
    'CH-ZH': 'Zurych', 'BR-DF': 'Brasília', 'HK-HKI': 'Wyspa Hongkong', 'HK-KLN': 'Kowloon',
    'HK-NTE': 'Nowe Terytoria',
  },
  cs: {
    'MX-CMX': 'Ciudad de México', 'MX-MEX': 'Stát México', 'DE-BY': 'Bavorsko', 'DE-NW': 'Severní Porýní-Vestfálsko',
    'DE-NI': 'Dolní Sasko', 'DE-SN': 'Sasko', 'DE-TH': 'Durynsko', 'DE-RP': 'Porýní-Falc',
    'DE-ST': 'Sasko-Anhaltsko', 'DE-HE': 'Hesensko', 'DE-BW': 'Bádensko-Württembersko', 'DE-BB': 'Braniborsko',
    'DE-MV': 'Meklenbursko-Přední Pomořansko', 'GB-ENG': 'Anglie', 'GB-SCT': 'Skotsko', 'GB-WLS': 'Wales',
    'GB-NIR': 'Severní Irsko', 'AT-9': 'Vídeň', 'ES-CT': 'Katalánsko', 'ES-AN': 'Andalusie',
    'ES-MD': 'Madridské autonomní společenství', 'ES-PV': 'Baskicko', 'ES-GA': 'Galicie', 'ES-CL': 'Kastilie a León',
    'ES-CM': 'Kastilie-La Mancha', 'ES-AR': 'Aragonie', 'ES-VC': 'Valencijské společenství', 'ES-CN': 'Kanárské ostrovy',
    'ES-NA': 'Navarra', 'CA-QC': 'Québec', 'CA-NB': 'Nový Brunšvik', 'CA-NS': 'Nové Skotsko',
    'CA-NL': 'Newfoundland a Labrador', 'NL-NH': 'Severní Holandsko', 'NL-ZH': 'Jižní Holandsko', 'NL-NB': 'Severní Brabantsko',
    'IT-VE': 'Benátky', 'IT-RM': 'Řím', 'IT-MI': 'Milán', 'IT-NA': 'Neapol',
    'IT-TO': 'Turín', 'IT-BZ': 'Bolzano', 'IT-FI': 'Florencie', 'IT-BO': 'Boloňa',
    'JP-13': 'Tokio', 'JP-27': 'Ósaka', 'GR-A': 'Atény', 'GR-B': 'Soluň',
    'DK-84': 'Kodaň', 'SE-AB': 'Stockholm', 'IE-D': 'Dublin', 'FR-75': 'Paříž',
    'FR-69': 'Lyon', 'FR-13': 'Marseille', 'FR-33': 'Bordeaux', 'FR-67': 'Štrasburk',
    'FR-06': 'Nice', 'PT-11': 'Lisabon', 'PT-13': 'Porto', 'PL-14': 'Varšava',
    'CZ-PR': 'Praha', 'NO-03': 'Oslo', 'FI-18': 'Helsinky', 'CH-GE': 'Ženeva',
    'CH-ZH': 'Curych', 'BR-DF': 'Brasília', 'HK-HKI': 'Hongkongský ostrov', 'HK-KLN': 'Kowloon',
    'HK-NTE': 'Nová teritoria',
  },
  sk: {
    'MX-CMX': 'Mexiko (mesto)', 'MX-MEX': 'Štát México', 'DE-BY': 'Bavorsko', 'DE-NW': 'Severné Porýnie-Vestfálsko',
    'DE-NI': 'Dolné Sasko', 'DE-SN': 'Sasko', 'DE-TH': 'Durínsko', 'DE-RP': 'Porýnie-Falcko',
    'DE-ST': 'Sasko-Anhaltsko', 'DE-HE': 'Hesensko', 'DE-BW': 'Bádensko-Württembersko', 'DE-BB': 'Brandenbursko',
    'DE-MV': 'Meklenbursko-Predné Pomoransko', 'GB-ENG': 'Anglicko', 'GB-SCT': 'Škótsko', 'GB-WLS': 'Wales',
    'GB-NIR': 'Severné Írsko', 'AT-9': 'Viedeň', 'ES-CT': 'Katalánsko', 'ES-AN': 'Andalúzia',
    'ES-MD': 'Madridské autonómne spoločenstvo', 'ES-PV': 'Baskicko', 'ES-GA': 'Galícia', 'ES-CL': 'Kastília a León',
    'ES-CM': 'Kastília-La Mancha', 'ES-AR': 'Aragónsko', 'ES-VC': 'Valencijské spoločenstvo', 'ES-CN': 'Kanárske ostrovy',
    'ES-NA': 'Navarra', 'CA-QC': 'Québec', 'CA-NB': 'Nový Brunšvik', 'CA-NS': 'Nové Škótsko',
    'CA-NL': 'Newfoundland a Labrador', 'NL-NH': 'Severné Holandsko', 'NL-ZH': 'Južné Holandsko', 'NL-NB': 'Severné Brabantsko',
    'IT-VE': 'Benátky', 'IT-RM': 'Rím', 'IT-MI': 'Miláno', 'IT-NA': 'Neapol',
    'IT-TO': 'Turín', 'IT-BZ': 'Bolzano', 'IT-FI': 'Florencia', 'IT-BO': 'Bologna',
    'JP-13': 'Tokio', 'JP-27': 'Osaka', 'GR-A': 'Atény', 'GR-B': 'Solún',
    'DK-84': 'Kodaň', 'SE-AB': 'Štokholm', 'IE-D': 'Dublin', 'FR-75': 'Paríž',
    'FR-69': 'Lyon', 'FR-13': 'Marseille', 'FR-33': 'Bordeaux', 'FR-67': 'Štrasburg',
    'FR-06': 'Nice', 'PT-11': 'Lisabon', 'PT-13': 'Porto', 'PL-14': 'Varšava',
    'CZ-PR': 'Praha', 'NO-03': 'Oslo', 'FI-18': 'Helsinki', 'CH-GE': 'Ženeva',
    'CH-ZH': 'Zürich', 'BR-DF': 'Brasília', 'HK-HKI': 'Hongkonský ostrov', 'HK-KLN': 'Kowloon',
    'HK-NTE': 'Nové teritóriá',
  },
  sl: {
    'MX-CMX': 'Ciudad de México', 'MX-MEX': 'Zvezna država México', 'DE-BY': 'Bavarska', 'DE-NW': 'Severno Porenje-Vestfalija',
    'DE-NI': 'Spodnja Saška', 'DE-SN': 'Saška', 'DE-TH': 'Turingija', 'DE-RP': 'Porenje-Pfalška',
    'DE-ST': 'Saška-Anhalt', 'DE-HE': 'Hessen', 'DE-BW': 'Baden-Württemberg', 'DE-BB': 'Brandenburg',
    'DE-MV': 'Mecklenburg-Predpomorjanska', 'GB-ENG': 'Anglija', 'GB-SCT': 'Škotska', 'GB-WLS': 'Wales',
    'GB-NIR': 'Severna Irska', 'AT-9': 'Dunaj', 'ES-CT': 'Katalonija', 'ES-AN': 'Andaluzija',
    'ES-MD': 'Madridska avtonomna skupnost', 'ES-PV': 'Baskija', 'ES-GA': 'Galicija', 'ES-CL': 'Kastilja in León',
    'ES-CM': 'Kastilja - La Mancha', 'ES-AR': 'Aragonija', 'ES-VC': 'Valencijska skupnost', 'ES-CN': 'Kanarski otoki',
    'ES-NA': 'Navara', 'CA-QC': 'Québec', 'CA-NB': 'Nova Brunswick', 'CA-NS': 'Nova Škotska',
    'CA-NL': 'Nova Fundlandija in Labrador', 'NL-NH': 'Severna Holandija', 'NL-ZH': 'Južna Holandija', 'NL-NB': 'Severni Brabant',
    'IT-VE': 'Benetke', 'IT-RM': 'Rim', 'IT-MI': 'Milano', 'IT-NA': 'Neapelj',
    'IT-TO': 'Torino', 'IT-BZ': 'Bocen', 'IT-FI': 'Firence', 'IT-BO': 'Bologna',
    'JP-13': 'Tokio', 'JP-27': 'Osaka', 'GR-A': 'Atene', 'GR-B': 'Solun',
    'DK-84': 'København', 'SE-AB': 'Stockholm', 'IE-D': 'Dublin', 'FR-75': 'Pariz',
    'FR-69': 'Lyon', 'FR-13': 'Marseille', 'FR-33': 'Bordeaux', 'FR-67': 'Strasbourg',
    'FR-06': 'Nica', 'PT-11': 'Lizbona', 'PT-13': 'Porto', 'PL-14': 'Varšava',
    'CZ-PR': 'Praga', 'NO-03': 'Oslo', 'FI-18': 'Helsinki', 'CH-GE': 'Ženeva',
    'CH-ZH': 'Zürich', 'BR-DF': 'Brasília', 'HK-HKI': 'Otok Hongkong', 'HK-KLN': 'Kowloon',
    'HK-NTE': 'Nova ozemlja',
  },
  hr: {
    'MX-CMX': 'Ciudad de México', 'MX-MEX': 'Savezna država México', 'DE-BY': 'Bavarska', 'DE-NW': 'Sjeverna Rajna-Vestfalija',
    'DE-NI': 'Donja Saska', 'DE-SN': 'Saska', 'DE-TH': 'Tiringija', 'DE-RP': 'Porajnje-Falačka',
    'DE-ST': 'Saska-Anhalt', 'DE-HE': 'Hessen', 'DE-BW': 'Baden-Württemberg', 'DE-BB': 'Brandenburg',
    'DE-MV': 'Mecklenburg-Zapadno Pomorje', 'GB-ENG': 'Engleska', 'GB-SCT': 'Škotska', 'GB-WLS': 'Wales',
    'GB-NIR': 'Sjeverna Irska', 'AT-9': 'Beč', 'ES-CT': 'Katalonija', 'ES-AN': 'Andaluzija',
    'ES-MD': 'Zajednica Madrid', 'ES-PV': 'Baskija', 'ES-GA': 'Galicija', 'ES-CL': 'Kastilja i León',
    'ES-CM': 'Kastilja-La Mancha', 'ES-AR': 'Aragonija', 'ES-VC': 'Valencijska Zajednica', 'ES-CN': 'Kanarski otoci',
    'ES-NA': 'Navara', 'CA-QC': 'Québec', 'CA-NB': 'New Brunswick', 'CA-NS': 'Nova Škotska',
    'CA-NL': 'Newfoundland i Labrador', 'NL-NH': 'Sjeverna Holandija', 'NL-ZH': 'Južna Holandija', 'NL-NB': 'Sjeverni Brabant',
    'IT-VE': 'Venecija', 'IT-RM': 'Rim', 'IT-MI': 'Milano', 'IT-NA': 'Napulj',
    'IT-TO': 'Torino', 'IT-BZ': 'Bolzano', 'IT-FI': 'Firenca', 'IT-BO': 'Bologna',
    'JP-13': 'Tokio', 'JP-27': 'Osaka', 'GR-A': 'Atena', 'GR-B': 'Solun',
    'DK-84': 'Kopenhagen', 'SE-AB': 'Stockholm', 'IE-D': 'Dublin', 'FR-75': 'Pariz',
    'FR-69': 'Lyon', 'FR-13': 'Marseille', 'FR-33': 'Bordeaux', 'FR-67': 'Strasbourg',
    'FR-06': 'Nica', 'PT-11': 'Lisabon', 'PT-13': 'Porto', 'PL-14': 'Varšava',
    'CZ-PR': 'Prag', 'NO-03': 'Oslo', 'FI-18': 'Helsinki', 'CH-GE': 'Ženeva',
    'CH-ZH': 'Zürich', 'BR-DF': 'Brasília', 'HK-HKI': 'Otok Hong Kong', 'HK-KLN': 'Kowloon',
    'HK-NTE': 'Novi teritoriji',
  },
  hu: {
    'MX-CMX': 'Mexikóváros', 'MX-MEX': 'México állam', 'DE-BY': 'Bajorország', 'DE-NW': 'Észak-Rajna-Vesztfália',
    'DE-NI': 'Alsó-Szászország', 'DE-SN': 'Szászország', 'DE-TH': 'Türingia', 'DE-RP': 'Rajna-vidék-Pfalz',
    'DE-ST': 'Szász-Anhalt', 'DE-HE': 'Hessen', 'DE-BW': 'Baden-Württemberg', 'DE-BB': 'Brandenburg',
    'DE-MV': 'Mecklenburg-Elő-Pomeránia', 'GB-ENG': 'Anglia', 'GB-SCT': 'Skócia', 'GB-WLS': 'Wales',
    'GB-NIR': 'Észak-Írország', 'AT-9': 'Bécs', 'ES-CT': 'Katalónia', 'ES-AN': 'Andalúzia',
    'ES-MD': 'Madridi autonóm közösség', 'ES-PV': 'Baszkföld', 'ES-GA': 'Galicia', 'ES-CL': 'Kasztília és León',
    'ES-CM': 'Kasztília-La Mancha', 'ES-AR': 'Aragónia', 'ES-VC': 'Valencia', 'ES-CN': 'Kanári-szigetek',
    'ES-NA': 'Navarra', 'CA-QC': 'Québec', 'CA-NB': 'Új-Brunswick', 'CA-NS': 'Új-Skócia',
    'CA-NL': 'Új-Fundland és Labrador', 'NL-NH': 'Észak-Holland', 'NL-ZH': 'Dél-Holland', 'NL-NB': 'Észak-Brabant',
    'IT-VE': 'Velence', 'IT-RM': 'Róma', 'IT-MI': 'Milánó', 'IT-NA': 'Nápoly',
    'IT-TO': 'Torino', 'IT-BZ': 'Bolzano', 'IT-FI': 'Firenze', 'IT-BO': 'Bologna',
    'JP-13': 'Tokió', 'JP-27': 'Oszaka', 'GR-A': 'Athén', 'GR-B': 'Szaloniki',
    'DK-84': 'Koppenhága', 'SE-AB': 'Stockholm', 'IE-D': 'Dublin', 'FR-75': 'Párizs',
    'FR-69': 'Lyon', 'FR-13': 'Marseille', 'FR-33': 'Bordeaux', 'FR-67': 'Strasbourg',
    'FR-06': 'Nizza', 'PT-11': 'Lisszabon', 'PT-13': 'Porto', 'PL-14': 'Varsó',
    'CZ-PR': 'Prága', 'NO-03': 'Oslo', 'FI-18': 'Helsinki', 'CH-GE': 'Genf',
    'CH-ZH': 'Zürich', 'BR-DF': 'Brasília', 'HK-HKI': 'Hongkong-sziget', 'HK-KLN': 'Kowloon',
    'HK-NTE': 'Új Területek',
  },
  el: {
    'MX-CMX': 'Πόλη του Μεξικού', 'MX-MEX': 'Πολιτεία του Μεξικού', 'DE-BY': 'Βαυαρία', 'DE-NW': 'Βόρεια Ρηνανία-Βεστφαλία',
    'DE-NI': 'Κάτω Σαξονία', 'DE-SN': 'Σαξονία', 'DE-TH': 'Θουριγγία', 'DE-RP': 'Ρηνανία-Παλατινάτο',
    'DE-ST': 'Σαξονία-Άνχαλτ', 'DE-HE': 'Έσση', 'DE-BW': 'Βάδη-Βυρτεμβέργη', 'DE-BB': 'Βρανδεμβούργο',
    'DE-MV': 'Μεκλεμβούργο-Πομερανία', 'GB-ENG': 'Αγγλία', 'GB-SCT': 'Σκωτία', 'GB-WLS': 'Ουαλία',
    'GB-NIR': 'Βόρεια Ιρλανδία', 'AT-9': 'Βιέννη', 'ES-CT': 'Καταλονία', 'ES-AN': 'Ανδαλουσία',
    'ES-MD': 'Κοινότητα της Μαδρίτης', 'ES-PV': 'Χώρα των Βάσκων', 'ES-GA': 'Γαλικία', 'ES-CL': 'Καστίλλη και Λεόν',
    'ES-CM': 'Καστίλλη-Λα Μάντσα', 'ES-AR': 'Αραγονία', 'ES-VC': 'Βαλενθιανή Κοινότητα', 'ES-CN': 'Κανάριοι Νήσοι',
    'ES-NA': 'Ναβάρρα', 'CA-QC': 'Κεμπέκ', 'CA-NB': 'Νιου Μπράνσγουικ', 'CA-NS': 'Νέα Σκωτία',
    'CA-NL': 'Νέα Γη και Λαμπραντόρ', 'NL-NH': 'Βόρεια Ολλανδία', 'NL-ZH': 'Νότια Ολλανδία', 'NL-NB': 'Βόρεια Βραβάντη',
    'IT-VE': 'Βενετία', 'IT-RM': 'Ρώμη', 'IT-MI': 'Μιλάνο', 'IT-NA': 'Νάπολη',
    'IT-TO': 'Τορίνο', 'IT-BZ': 'Μπολτσάνο', 'IT-FI': 'Φλωρεντία', 'IT-BO': 'Μπολόνια',
    'JP-13': 'Τόκιο', 'JP-27': 'Οσάκα', 'GR-A': 'Αθήνα', 'GR-B': 'Θεσσαλονίκη',
    'DK-84': 'Κοπεγχάγη', 'SE-AB': 'Στοκχόλμη', 'IE-D': 'Δουβλίνο', 'FR-75': 'Παρίσι',
    'FR-69': 'Λυών', 'FR-13': 'Μασσαλία', 'FR-33': 'Μπορντό', 'FR-67': 'Στρασβούργο',
    'FR-06': 'Νίκαια', 'PT-11': 'Λισαβόνα', 'PT-13': 'Πόρτο', 'PL-14': 'Βαρσοβία',
    'CZ-PR': 'Πράγα', 'NO-03': 'Όσλο', 'FI-18': 'Ελσίνκι', 'CH-GE': 'Γενεύη',
    'CH-ZH': 'Ζυρίχη', 'BR-DF': 'Μπραζίλια', 'HK-HKI': 'Νήσος Χονγκ Κονγκ', 'HK-KLN': 'Κόουλουν',
    'HK-NTE': 'Νέα Εδάφη',
  },
  da: {
    'MX-CMX': 'Mexico City', 'MX-MEX': 'Delstaten Mexico', 'DE-BY': 'Bayern', 'DE-NW': 'Nordrhein-Westfalen',
    'DE-NI': 'Niedersachsen', 'DE-SN': 'Sachsen', 'DE-TH': 'Thüringen', 'DE-RP': 'Rheinland-Pfalz',
    'DE-ST': 'Sachsen-Anhalt', 'DE-HE': 'Hessen', 'DE-BW': 'Baden-Württemberg', 'DE-BB': 'Brandenburg',
    'DE-MV': 'Mecklenburg-Vorpommern', 'GB-ENG': 'England', 'GB-SCT': 'Skotland', 'GB-WLS': 'Wales',
    'GB-NIR': 'Nordirland', 'AT-9': 'Wien', 'ES-CT': 'Catalonien', 'ES-AN': 'Andalusien',
    'ES-MD': 'Madrid', 'ES-PV': 'Baskerlandet', 'ES-GA': 'Galicien', 'ES-CL': 'Castilla og León',
    'ES-CM': 'Castilla-La Mancha', 'ES-AR': 'Aragonien', 'ES-VC': 'Valencia', 'ES-CN': 'De Kanariske Øer',
    'ES-NA': 'Navarra', 'CA-QC': 'Québec', 'CA-NB': 'New Brunswick', 'CA-NS': 'Nova Scotia',
    'CA-NL': 'Newfoundland og Labrador', 'NL-NH': 'Nordholland', 'NL-ZH': 'Sydholland', 'NL-NB': 'Nordbrabant',
    'IT-VE': 'Venedig', 'IT-RM': 'Rom', 'IT-MI': 'Milano', 'IT-NA': 'Napoli',
    'IT-TO': 'Torino', 'IT-BZ': 'Bolzano', 'IT-FI': 'Firenze', 'IT-BO': 'Bologna',
    'JP-13': 'Tokyo', 'JP-27': 'Osaka', 'GR-A': 'Athen', 'GR-B': 'Thessaloniki',
    'DK-84': 'København', 'SE-AB': 'Stockholm', 'IE-D': 'Dublin', 'FR-75': 'Paris',
    'FR-69': 'Lyon', 'FR-13': 'Marseille', 'FR-33': 'Bordeaux', 'FR-67': 'Strasbourg',
    'FR-06': 'Nice', 'PT-11': 'Lissabon', 'PT-13': 'Porto', 'PL-14': 'Warszawa',
    'CZ-PR': 'Prag', 'NO-03': 'Oslo', 'FI-18': 'Helsinki', 'CH-GE': 'Genève',
    'CH-ZH': 'Zürich', 'BR-DF': 'Brasília', 'HK-HKI': 'Hongkong Island', 'HK-KLN': 'Kowloon',
    'HK-NTE': 'De Nye Territorier',
  },
  nb: {
    'MX-CMX': 'Mexico by', 'MX-MEX': 'Delstaten Mexico', 'DE-BY': 'Bayern', 'DE-NW': 'Nordrhein-Westfalen',
    'DE-NI': 'Niedersachsen', 'DE-SN': 'Sachsen', 'DE-TH': 'Thüringen', 'DE-RP': 'Rheinland-Pfalz',
    'DE-ST': 'Sachsen-Anhalt', 'DE-HE': 'Hessen', 'DE-BW': 'Baden-Württemberg', 'DE-BB': 'Brandenburg',
    'DE-MV': 'Mecklenburg-Vorpommern', 'GB-ENG': 'England', 'GB-SCT': 'Skottland', 'GB-WLS': 'Wales',
    'GB-NIR': 'Nord-Irland', 'AT-9': 'Wien', 'ES-CT': 'Catalonia', 'ES-AN': 'Andalucía',
    'ES-MD': 'Madrid', 'ES-PV': 'Baskerland', 'ES-GA': 'Galicia', 'ES-CL': 'Castilla y León',
    'ES-CM': 'Castilla-La Mancha', 'ES-AR': 'Aragón', 'ES-VC': 'Valencia', 'ES-CN': 'Kanariøyene',
    'ES-NA': 'Navarra', 'CA-QC': 'Québec', 'CA-NB': 'New Brunswick', 'CA-NS': 'Nova Scotia',
    'CA-NL': 'Newfoundland og Labrador', 'NL-NH': 'Nord-Holland', 'NL-ZH': 'Sør-Holland', 'NL-NB': 'Nord-Brabant',
    'IT-VE': 'Venezia', 'IT-RM': 'Roma', 'IT-MI': 'Milano', 'IT-NA': 'Napoli',
    'IT-TO': 'Torino', 'IT-BZ': 'Bolzano', 'IT-FI': 'Firenze', 'IT-BO': 'Bologna',
    'JP-13': 'Tokyo', 'JP-27': 'Osaka', 'GR-A': 'Athen', 'GR-B': 'Thessaloniki',
    'DK-84': 'København', 'SE-AB': 'Stockholm', 'IE-D': 'Dublin', 'FR-75': 'Paris',
    'FR-69': 'Lyon', 'FR-13': 'Marseille', 'FR-33': 'Bordeaux', 'FR-67': 'Strasbourg',
    'FR-06': 'Nice', 'PT-11': 'Lisboa', 'PT-13': 'Porto', 'PL-14': 'Warszawa',
    'CZ-PR': 'Praha', 'NO-03': 'Oslo', 'FI-18': 'Helsingfors', 'CH-GE': 'Genève',
    'CH-ZH': 'Zürich', 'BR-DF': 'Brasília', 'HK-HKI': 'Hongkong Island', 'HK-KLN': 'Kowloon',
    'HK-NTE': 'De nye territoriene',
  },
  sv: {
    'MX-CMX': 'Mexico City', 'MX-MEX': 'Delstaten Mexiko', 'DE-BY': 'Bayern', 'DE-NW': 'Nordrhein-Westfalen',
    'DE-NI': 'Niedersachsen', 'DE-SN': 'Sachsen', 'DE-TH': 'Thüringen', 'DE-RP': 'Rheinland-Pfalz',
    'DE-ST': 'Sachsen-Anhalt', 'DE-HE': 'Hessen', 'DE-BW': 'Baden-Württemberg', 'DE-BB': 'Brandenburg',
    'DE-MV': 'Mecklenburg-Vorpommern', 'GB-ENG': 'England', 'GB-SCT': 'Skottland', 'GB-WLS': 'Wales',
    'GB-NIR': 'Nordirland', 'AT-9': 'Wien', 'ES-CT': 'Katalonien', 'ES-AN': 'Andalusien',
    'ES-MD': 'Madrid', 'ES-PV': 'Baskien', 'ES-GA': 'Galicien', 'ES-CL': 'Kastilien och León',
    'ES-CM': 'Kastilien-La Mancha', 'ES-AR': 'Aragonien', 'ES-VC': 'Valencia', 'ES-CN': 'Kanarieöarna',
    'ES-NA': 'Navarra', 'CA-QC': 'Québec', 'CA-NB': 'New Brunswick', 'CA-NS': 'Nova Scotia',
    'CA-NL': 'Newfoundland och Labrador', 'NL-NH': 'Nordholland', 'NL-ZH': 'Sydholland', 'NL-NB': 'Nordbrabant',
    'IT-VE': 'Venedig', 'IT-RM': 'Rom', 'IT-MI': 'Milano', 'IT-NA': 'Neapel',
    'IT-TO': 'Turin', 'IT-BZ': 'Bolzano', 'IT-FI': 'Florens', 'IT-BO': 'Bologna',
    'JP-13': 'Tokyo', 'JP-27': 'Osaka', 'GR-A': 'Aten', 'GR-B': 'Thessaloniki',
    'DK-84': 'Köpenhamn', 'SE-AB': 'Stockholm', 'IE-D': 'Dublin', 'FR-75': 'Paris',
    'FR-69': 'Lyon', 'FR-13': 'Marseille', 'FR-33': 'Bordeaux', 'FR-67': 'Strasbourg',
    'FR-06': 'Nice', 'PT-11': 'Lissabon', 'PT-13': 'Porto', 'PL-14': 'Warszawa',
    'CZ-PR': 'Prag', 'NO-03': 'Oslo', 'FI-18': 'Helsingfors', 'CH-GE': 'Genève',
    'CH-ZH': 'Zürich', 'BR-DF': 'Brasília', 'HK-HKI': 'Hongkong Island', 'HK-KLN': 'Kowloon',
    'HK-NTE': 'Nya territorierna',
  },
  fi: {
    'MX-CMX': 'México', 'MX-MEX': 'Méxicon osavaltio', 'DE-BY': 'Baijeri', 'DE-NW': 'Nordrhein-Westfalen',
    'DE-NI': 'Ala-Saksi', 'DE-SN': 'Saksi', 'DE-TH': 'Thüringen', 'DE-RP': 'Rheinland-Pfalz',
    'DE-ST': 'Saksi-Anhalt', 'DE-HE': 'Hessen', 'DE-BW': 'Baden-Württemberg', 'DE-BB': 'Brandenburg',
    'DE-MV': 'Mecklenburg-Vorpommern', 'GB-ENG': 'Englanti', 'GB-SCT': 'Skotlanti', 'GB-WLS': 'Wales',
    'GB-NIR': 'Pohjois-Irlanti', 'AT-9': 'Wien', 'ES-CT': 'Katalonia', 'ES-AN': 'Andalusia',
    'ES-MD': 'Madridin itsehallintoalue', 'ES-PV': 'Baskimaa', 'ES-GA': 'Galicia', 'ES-CL': 'Kastilia ja León',
    'ES-CM': 'Kastilia-La Mancha', 'ES-AR': 'Aragonia', 'ES-VC': 'Valencia', 'ES-CN': 'Kanariansaaret',
    'ES-NA': 'Navarra', 'CA-QC': 'Québec', 'CA-NB': 'New Brunswick', 'CA-NS': 'Nova Scotia',
    'CA-NL': 'Newfoundland ja Labrador', 'NL-NH': 'Pohjois-Hollanti', 'NL-ZH': 'Etelä-Hollanti', 'NL-NB': 'Pohjois-Brabant',
    'IT-VE': 'Venetsia', 'IT-RM': 'Rooma', 'IT-MI': 'Milano', 'IT-NA': 'Napoli',
    'IT-TO': 'Torino', 'IT-BZ': 'Bolzano', 'IT-FI': 'Firenze', 'IT-BO': 'Bologna',
    'JP-13': 'Tokio', 'JP-27': 'Osaka', 'GR-A': 'Ateena', 'GR-B': 'Thessaloniki',
    'DK-84': 'Kööpenhamina', 'SE-AB': 'Tukholma', 'IE-D': 'Dublin', 'FR-75': 'Pariisi',
    'FR-69': 'Lyon', 'FR-13': 'Marseille', 'FR-33': 'Bordeaux', 'FR-67': 'Strasbourg',
    'FR-06': 'Nizza', 'PT-11': 'Lissabon', 'PT-13': 'Porto', 'PL-14': 'Varsova',
    'CZ-PR': 'Praha', 'NO-03': 'Oslo', 'FI-18': 'Helsinki', 'CH-GE': 'Geneve',
    'CH-ZH': 'Zürich', 'BR-DF': 'Brasília', 'HK-HKI': 'Hongkongin saari', 'HK-KLN': 'Kowloon',
    'HK-NTE': 'Uudet territoriot',
  },
  ja: {
    'MX-CMX': 'メキシコシティ', 'MX-MEX': 'メキシコ州', 'DE-BY': 'バイエルン州', 'DE-NW': 'ノルトライン＝ヴェストファーレン州',
    'DE-NI': 'ニーダーザクセン州', 'DE-SN': 'ザクセン州', 'DE-TH': 'テューリンゲン州', 'DE-RP': 'ラインラント＝プファルツ州',
    'DE-ST': 'ザクセン＝アンハルト州', 'DE-HE': 'ヘッセン州', 'DE-BW': 'バーデン＝ヴュルテンベルク州', 'DE-BB': 'ブランデンブルク州',
    'DE-MV': 'メクレンブルク＝フォアポンメルン州', 'GB-ENG': 'イングランド', 'GB-SCT': 'スコットランド', 'GB-WLS': 'ウェールズ',
    'GB-NIR': '北アイルランド', 'AT-9': 'ウィーン', 'ES-CT': 'カタルーニャ', 'ES-AN': 'アンダルシア',
    'ES-MD': 'マドリード州', 'ES-PV': 'バスク', 'ES-GA': 'ガリシア', 'ES-CL': 'カスティーリャ・イ・レオン',
    'ES-CM': 'カスティーリャ＝ラ・マンチャ', 'ES-AR': 'アラゴン', 'ES-VC': 'バレンシア州', 'ES-CN': 'カナリア諸島',
    'ES-NA': 'ナバラ', 'CA-QC': 'ケベック州', 'CA-NB': 'ニューブランズウィック州', 'CA-NS': 'ノバスコシア州',
    'CA-NL': 'ニューファンドランド・ラブラドール州', 'NL-NH': '北ホラント州', 'NL-ZH': '南ホラント州', 'NL-NB': '北ブラバント州',
    'IT-VE': 'ヴェネツィア', 'IT-RM': 'ローマ', 'IT-MI': 'ミラノ', 'IT-NA': 'ナポリ',
    'IT-TO': 'トリノ', 'IT-BZ': 'ボルツァーノ', 'IT-FI': 'フィレンツェ', 'IT-BO': 'ボローニャ',
    'JP-13': '東京都', 'JP-27': '大阪府', 'GR-A': 'アテネ', 'GR-B': 'テッサロニキ',
    'DK-84': 'コペンハーゲン', 'SE-AB': 'ストックホルム', 'IE-D': 'ダブリン', 'FR-75': 'パリ',
    'FR-69': 'リヨン', 'FR-13': 'マルセイユ', 'FR-33': 'ボルドー', 'FR-67': 'ストラスブール',
    'FR-06': 'ニース', 'PT-11': 'リスボン', 'PT-13': 'ポルト', 'PL-14': 'ワルシャワ',
    'CZ-PR': 'プラハ', 'NO-03': 'オスロ', 'FI-18': 'ヘルシンキ', 'CH-GE': 'ジュネーヴ',
    'CH-ZH': 'チューリッヒ', 'BR-DF': 'ブラジリア', 'HK-HKI': '香港島', 'HK-KLN': '九龍',
    'HK-NTE': '新界',
  },
  ko: {
    'MX-CMX': '멕시코시티', 'MX-MEX': '멕시코주', 'DE-BY': '바이에른주', 'DE-NW': '노르트라인베스트팔렌주',
    'DE-NI': '니더작센주', 'DE-SN': '작센주', 'DE-TH': '튀링겐주', 'DE-RP': '라인란트팔츠주',
    'DE-ST': '작센안할트주', 'DE-HE': '헤센주', 'DE-BW': '바덴뷔르템베르크주', 'DE-BB': '브란덴부르크주',
    'DE-MV': '메클렌부르크포어포메른주', 'GB-ENG': '잉글랜드', 'GB-SCT': '스코틀랜드', 'GB-WLS': '웨일스',
    'GB-NIR': '북아일랜드', 'AT-9': '빈', 'ES-CT': '카탈루냐', 'ES-AN': '안달루시아',
    'ES-MD': '마드리드 지방', 'ES-PV': '바스크', 'ES-GA': '갈리시아', 'ES-CL': '카스티야이레온',
    'ES-CM': '카스티야라만차', 'ES-AR': '아라곤', 'ES-VC': '발렌시아 지방', 'ES-CN': '카나리아 제도',
    'ES-NA': '나바라', 'CA-QC': '퀘벡주', 'CA-NB': '뉴브런즈윅주', 'CA-NS': '노바스코샤주',
    'CA-NL': '뉴펀들랜드 래브라도주', 'NL-NH': '노르트홀란트주', 'NL-ZH': '자위트홀란트주', 'NL-NB': '노르트브라반트주',
    'IT-VE': '베네치아', 'IT-RM': '로마', 'IT-MI': '밀라노', 'IT-NA': '나폴리',
    'IT-TO': '토리노', 'IT-BZ': '볼차노', 'IT-FI': '피렌체', 'IT-BO': '볼로냐',
    'JP-13': '도쿄도', 'JP-27': '오사카부', 'GR-A': '아테네', 'GR-B': '테살로니키',
    'DK-84': '코펜하겐', 'SE-AB': '스톡홀름', 'IE-D': '더블린', 'FR-75': '파리',
    'FR-69': '리옹', 'FR-13': '마르세유', 'FR-33': '보르도', 'FR-67': '스트라스부르',
    'FR-06': '니스', 'PT-11': '리스본', 'PT-13': '포르투', 'PL-14': '바르샤바',
    'CZ-PR': '프라하', 'NO-03': '오슬로', 'FI-18': '헬싱키', 'CH-GE': '제네바',
    'CH-ZH': '취리히', 'BR-DF': '브라질리아', 'HK-HKI': '홍콩섬', 'HK-KLN': '주룽',
    'HK-NTE': '신제',
  },
  'zh-cn': {
    'MX-CMX': '墨西哥城', 'MX-MEX': '墨西哥州', 'DE-BY': '巴伐利亚州', 'DE-NW': '北莱茵-威斯特法伦州',
    'DE-NI': '下萨克森州', 'DE-SN': '萨克森州', 'DE-TH': '图林根州', 'DE-RP': '莱茵兰-普法尔茨州',
    'DE-ST': '萨克森-安哈尔特州', 'DE-HE': '黑森州', 'DE-BW': '巴登-符腾堡州', 'DE-BB': '勃兰登堡州',
    'DE-MV': '梅克伦堡-前波莫瑞州', 'GB-ENG': '英格兰', 'GB-SCT': '苏格兰', 'GB-WLS': '威尔士',
    'GB-NIR': '北爱尔兰', 'AT-9': '维也纳', 'ES-CT': '加泰罗尼亚', 'ES-AN': '安达卢西亚',
    'ES-MD': '马德里自治区', 'ES-PV': '巴斯克', 'ES-GA': '加利西亚', 'ES-CL': '卡斯蒂利亚-莱昂',
    'ES-CM': '卡斯蒂利亚-拉曼恰', 'ES-AR': '阿拉贡', 'ES-VC': '瓦伦西亚自治区', 'ES-CN': '加那利群岛',
    'ES-NA': '纳瓦拉', 'CA-QC': '魁北克省', 'CA-NB': '新不伦瑞克省', 'CA-NS': '新斯科舍省',
    'CA-NL': '纽芬兰与拉布拉多省', 'NL-NH': '北荷兰省', 'NL-ZH': '南荷兰省', 'NL-NB': '北布拉班特省',
    'IT-VE': '威尼斯', 'IT-RM': '罗马', 'IT-MI': '米兰', 'IT-NA': '那不勒斯',
    'IT-TO': '都灵', 'IT-BZ': '博尔扎诺', 'IT-FI': '佛罗伦萨', 'IT-BO': '博洛尼亚',
    'JP-13': '东京都', 'JP-27': '大阪府', 'GR-A': '雅典', 'GR-B': '塞萨洛尼基',
    'DK-84': '哥本哈根', 'SE-AB': '斯德哥尔摩', 'IE-D': '都柏林', 'FR-75': '巴黎',
    'FR-69': '里昂', 'FR-13': '马赛', 'FR-33': '波尔多', 'FR-67': '斯特拉斯堡',
    'FR-06': '尼斯', 'PT-11': '里斯本', 'PT-13': '波尔图', 'PL-14': '华沙',
    'CZ-PR': '布拉格', 'NO-03': '奥斯陆', 'FI-18': '赫尔辛基', 'CH-GE': '日内瓦',
    'CH-ZH': '苏黎世', 'BR-DF': '巴西利亚', 'HK-HKI': '香港岛', 'HK-KLN': '九龙',
    'HK-NTE': '新界',
  },
  'zh-tw': {
    'MX-CMX': '墨西哥市', 'MX-MEX': '墨西哥州', 'DE-BY': '巴伐利亞邦', 'DE-NW': '北萊茵-西發里亞邦',
    'DE-NI': '下薩克森邦', 'DE-SN': '薩克森邦', 'DE-TH': '圖林根邦', 'DE-RP': '萊茵蘭-普法茲邦',
    'DE-ST': '薩克森-安哈特邦', 'DE-HE': '黑森邦', 'DE-BW': '巴登-符騰堡邦', 'DE-BB': '布蘭登堡邦',
    'DE-MV': '梅克倫堡-前波美拉尼亞邦', 'GB-ENG': '英格蘭', 'GB-SCT': '蘇格蘭', 'GB-WLS': '威爾斯',
    'GB-NIR': '北愛爾蘭', 'AT-9': '維也納', 'ES-CT': '加泰隆尼亞', 'ES-AN': '安達魯西亞',
    'ES-MD': '馬德里自治區', 'ES-PV': '巴斯克', 'ES-GA': '加利西亞', 'ES-CL': '卡斯提亞-雷昂',
    'ES-CM': '卡斯提亞-拉曼查', 'ES-AR': '亞拉岡', 'ES-VC': '瓦倫西亞自治區', 'ES-CN': '加那利群島',
    'ES-NA': '納瓦拉', 'CA-QC': '魁北克省', 'CA-NB': '新布倫瑞克省', 'CA-NS': '新斯科細亞省',
    'CA-NL': '紐芬蘭與拉布拉多省', 'NL-NH': '北荷蘭省', 'NL-ZH': '南荷蘭省', 'NL-NB': '北布拉班特省',
    'IT-VE': '威尼斯', 'IT-RM': '羅馬', 'IT-MI': '米蘭', 'IT-NA': '拿坡里',
    'IT-TO': '杜林', 'IT-BZ': '波札諾', 'IT-FI': '佛羅倫斯', 'IT-BO': '波隆那',
    'JP-13': '東京都', 'JP-27': '大阪府', 'GR-A': '雅典', 'GR-B': '塞薩洛尼基',
    'DK-84': '哥本哈根', 'SE-AB': '斯德哥爾摩', 'IE-D': '都柏林', 'FR-75': '巴黎',
    'FR-69': '里昂', 'FR-13': '馬賽', 'FR-33': '波爾多', 'FR-67': '史特拉斯堡',
    'FR-06': '尼斯', 'PT-11': '里斯本', 'PT-13': '波多', 'PL-14': '華沙',
    'CZ-PR': '布拉格', 'NO-03': '奧斯陸', 'FI-18': '赫爾辛基', 'CH-GE': '日內瓦',
    'CH-ZH': '蘇黎世', 'BR-DF': '巴西利亞', 'HK-HKI': '香港島', 'HK-KLN': '九龍',
    'HK-NTE': '新界',
  },
  th: {
    'MX-CMX': 'เม็กซิโกซิตี', 'MX-MEX': 'รัฐเม็กซิโก', 'DE-BY': 'บาวาเรีย', 'DE-NW': 'นอร์ทไรน์-เวสต์ฟาเลีย',
    'DE-NI': 'โลเวอร์แซกโซนี', 'DE-SN': 'แซกโซนี', 'DE-TH': 'ทูรินเจีย', 'DE-RP': 'ไรน์ลันท์-พฟัลซ์',
    'DE-ST': 'แซกโซนี-อันฮัลท์', 'DE-HE': 'เฮสเซิน', 'DE-BW': 'บาเดิน-เวือร์ทเทมแบร์ค', 'DE-BB': 'บรันเดินบวร์ค',
    'DE-MV': 'เมคเลนบวร์ค-ฟอร์พอมเมิร์น', 'GB-ENG': 'อังกฤษ', 'GB-SCT': 'สกอตแลนด์', 'GB-WLS': 'เวลส์',
    'GB-NIR': 'ไอร์แลนด์เหนือ', 'AT-9': 'เวียนนา', 'ES-CT': 'กาตาลุญญา', 'ES-AN': 'อันดาลูซีอา',
    'ES-MD': 'แคว้นมาดริด', 'ES-PV': 'แคว้นบาสก์', 'ES-GA': 'กาลิเซีย', 'ES-CL': 'กัสติยาและเลออน',
    'ES-CM': 'กัสติยา-ลามันชา', 'ES-AR': 'อารากอน', 'ES-VC': 'แคว้นบาเลนเซีย', 'ES-CN': 'หมู่เกาะคานารี',
    'ES-NA': 'นาวาร์', 'CA-QC': 'ควิเบก', 'CA-NB': 'นิวบรันสวิก', 'CA-NS': 'โนวาสโกเชีย',
    'CA-NL': 'นิวฟันด์แลนด์และแลบราดอร์', 'NL-NH': 'นอร์ทฮอลแลนด์', 'NL-ZH': 'เซาท์ฮอลแลนด์', 'NL-NB': 'นอร์ทบราบันต์',
    'IT-VE': 'เวนิส', 'IT-RM': 'โรม', 'IT-MI': 'มิลาน', 'IT-NA': 'เนเปิลส์',
    'IT-TO': 'ตูริน', 'IT-BZ': 'โบลซาโน', 'IT-FI': 'ฟลอเรนซ์', 'IT-BO': 'โบโลญญา',
    'JP-13': 'โตเกียว', 'JP-27': 'โอซากา', 'GR-A': 'เอเธนส์', 'GR-B': 'เทสซาโลนีกี',
    'DK-84': 'โคเปนเฮเกน', 'SE-AB': 'สตอกโฮล์ม', 'IE-D': 'ดับลิน', 'FR-75': 'ปารีส',
    'FR-69': 'ลียง', 'FR-13': 'มาร์แซย์', 'FR-33': 'บอร์โด', 'FR-67': 'สตราสบูร์ก',
    'FR-06': 'นีซ', 'PT-11': 'ลิสบอน', 'PT-13': 'ปอร์โต', 'PL-14': 'วอร์ซอ',
    'CZ-PR': 'ปราก', 'NO-03': 'ออสโล', 'FI-18': 'เฮลซิงกิ', 'CH-GE': 'เจนีวา',
    'CH-ZH': 'ซูริก', 'BR-DF': 'บราซิเลีย', 'HK-HKI': 'เกาะฮ่องกง', 'HK-KLN': 'เกาลูน',
    'HK-NTE': 'นิวเทร์ริทอรีส์',
  },
  he: {
    'MX-CMX': 'מקסיקו סיטי', 'MX-MEX': 'מדינת מקסיקו', 'DE-BY': 'בוואריה', 'DE-NW': 'נורדריין-וסטפאליה',
    'DE-NI': 'סקסוניה התחתונה', 'DE-SN': 'סקסוניה', 'DE-TH': 'תורינגיה', 'DE-RP': 'ריינלנד-פפאלץ',
    'DE-ST': 'סקסוניה-אנהלט', 'DE-HE': 'הסן', 'DE-BW': 'באדן-וירטמברג', 'DE-BB': 'ברנדנבורג',
    'DE-MV': 'מקלנבורג-פורפומרן', 'GB-ENG': 'אנגליה', 'GB-SCT': 'סקוטלנד', 'GB-WLS': 'ויילס',
    'GB-NIR': 'צפון אירלנד', 'AT-9': 'וינה', 'ES-CT': 'קטלוניה', 'ES-AN': 'אנדלוסיה',
    'ES-MD': 'קהילת מדריד', 'ES-PV': 'חבל הבאסקים', 'ES-GA': 'גליסיה', 'ES-CL': 'קסטיליה ולאון',
    'ES-CM': 'קסטיליה-לה מנצ׳ה', 'ES-AR': 'אראגון', 'ES-VC': 'קהילת ולנסיה', 'ES-CN': 'האיים הקנריים',
    'ES-NA': 'נווארה', 'CA-QC': 'קוויבק', 'CA-NB': 'ניו ברנזוויק', 'CA-NS': 'נובה סקוטיה',
    'CA-NL': 'ניופאונדלנד ולברדור', 'NL-NH': 'צפון הולנד', 'NL-ZH': 'דרום הולנד', 'NL-NB': 'צפון בראבנט',
    'IT-VE': 'ונציה', 'IT-RM': 'רומא', 'IT-MI': 'מילאנו', 'IT-NA': 'נאפולי',
    'IT-TO': 'טורינו', 'IT-BZ': 'בולצאנו', 'IT-FI': 'פירנצה', 'IT-BO': 'בולוניה',
    'JP-13': 'טוקיו', 'JP-27': 'אוסקה', 'GR-A': 'אתונה', 'GR-B': 'סלוניקי',
    'DK-84': 'קופנהגן', 'SE-AB': 'שטוקהולם', 'IE-D': 'דבלין', 'FR-75': 'פריז',
    'FR-69': 'ליון', 'FR-13': 'מרסיי', 'FR-33': 'בורדו', 'FR-67': 'שטרסבורג',
    'FR-06': 'ניס', 'PT-11': 'ליסבון', 'PT-13': 'פורטו', 'PL-14': 'ורשה',
    'CZ-PR': 'פראג', 'NO-03': 'אוסלו', 'FI-18': 'הלסינקי', 'CH-GE': 'ז׳נבה',
    'CH-ZH': 'ציריך', 'BR-DF': 'ברזיליה', 'HK-HKI': 'האי הונג קונג', 'HK-KLN': 'קאולון',
    'HK-NTE': 'הטריטוריות החדשות',
  },
  id: {
    'MX-CMX': 'Kota Meksiko', 'MX-MEX': 'Negara Bagian Meksiko', 'DE-BY': 'Bayern', 'DE-NW': 'Nordrhein-Westfalen',
    'DE-NI': 'Niedersachsen', 'DE-SN': 'Sachsen', 'DE-TH': 'Thüringen', 'DE-RP': 'Rheinland-Pfalz',
    'DE-ST': 'Sachsen-Anhalt', 'DE-HE': 'Hessen', 'DE-BW': 'Baden-Württemberg', 'DE-BB': 'Brandenburg',
    'DE-MV': 'Mecklenburg-Vorpommern', 'GB-ENG': 'Inggris', 'GB-SCT': 'Skotlandia', 'GB-WLS': 'Wales',
    'GB-NIR': 'Irlandia Utara', 'AT-9': 'Wina', 'ES-CT': 'Katalonia', 'ES-AN': 'Andalusia',
    'ES-MD': 'Komunitas Madrid', 'ES-PV': 'Negara Basque', 'ES-GA': 'Galicia', 'ES-CL': 'Kastilia dan León',
    'ES-CM': 'Kastilia-La Mancha', 'ES-AR': 'Aragon', 'ES-VC': 'Komunitas Valencia', 'ES-CN': 'Kepulauan Canaria',
    'ES-NA': 'Navarra', 'CA-QC': 'Quebec', 'CA-NB': 'New Brunswick', 'CA-NS': 'Nova Scotia',
    'CA-NL': 'Newfoundland dan Labrador', 'NL-NH': 'Holland Utara', 'NL-ZH': 'Holland Selatan', 'NL-NB': 'Brabant Utara',
    'IT-VE': 'Venesia', 'IT-RM': 'Roma', 'IT-MI': 'Milan', 'IT-NA': 'Napoli',
    'IT-TO': 'Turin', 'IT-BZ': 'Bolzano', 'IT-FI': 'Firenze', 'IT-BO': 'Bologna',
    'JP-13': 'Tokyo', 'JP-27': 'Osaka', 'GR-A': 'Athena', 'GR-B': 'Thessaloniki',
    'DK-84': 'Kopenhagen', 'SE-AB': 'Stockholm', 'IE-D': 'Dublin', 'FR-75': 'Paris',
    'FR-69': 'Lyon', 'FR-13': 'Marseille', 'FR-33': 'Bordeaux', 'FR-67': 'Strasbourg',
    'FR-06': 'Nice', 'PT-11': 'Lisboa', 'PT-13': 'Porto', 'PL-14': 'Warsawa',
    'CZ-PR': 'Praha', 'NO-03': 'Oslo', 'FI-18': 'Helsinki', 'CH-GE': 'Jenewa',
    'CH-ZH': 'Zürich', 'BR-DF': 'Brasília', 'HK-HKI': 'Pulau Hong Kong', 'HK-KLN': 'Kowloon',
    'HK-NTE': 'Wilayah Baru',
  },
  ms: {
    'MX-CMX': 'Bandar Mexico', 'MX-MEX': 'Negeri Mexico', 'DE-BY': 'Bavaria', 'DE-NW': 'Rhine Utara-Westphalia',
    'DE-NI': 'Saxony Bawah', 'DE-SN': 'Saxony', 'DE-TH': 'Thuringia', 'DE-RP': 'Rhineland-Palatinate',
    'DE-ST': 'Saxony-Anhalt', 'DE-HE': 'Hesse', 'DE-BW': 'Baden-Württemberg', 'DE-BB': 'Brandenburg',
    'DE-MV': 'Mecklenburg-Pomerania Barat', 'GB-ENG': 'England', 'GB-SCT': 'Scotland', 'GB-WLS': 'Wales',
    'GB-NIR': 'Ireland Utara', 'AT-9': 'Vienna', 'ES-CT': 'Catalonia', 'ES-AN': 'Andalusia',
    'ES-MD': 'Komuniti Madrid', 'ES-PV': 'Negara Basque', 'ES-GA': 'Galicia', 'ES-CL': 'Castile dan León',
    'ES-CM': 'Castilla-La Mancha', 'ES-AR': 'Aragon', 'ES-VC': 'Komuniti Valencia', 'ES-CN': 'Kepulauan Canary',
    'ES-NA': 'Navarre', 'CA-QC': 'Quebec', 'CA-NB': 'New Brunswick', 'CA-NS': 'Nova Scotia',
    'CA-NL': 'Newfoundland dan Labrador', 'NL-NH': 'Holland Utara', 'NL-ZH': 'Holland Selatan', 'NL-NB': 'Brabant Utara',
    'IT-VE': 'Venice', 'IT-RM': 'Rom', 'IT-MI': 'Milan', 'IT-NA': 'Naples',
    'IT-TO': 'Turin', 'IT-BZ': 'Bolzano', 'IT-FI': 'Florence', 'IT-BO': 'Bologna',
    'JP-13': 'Tokyo', 'JP-27': 'Osaka', 'GR-A': 'Athens', 'GR-B': 'Thessaloniki',
    'DK-84': 'Copenhagen', 'SE-AB': 'Stockholm', 'IE-D': 'Dublin', 'FR-75': 'Paris',
    'FR-69': 'Lyon', 'FR-13': 'Marseille', 'FR-33': 'Bordeaux', 'FR-67': 'Strasbourg',
    'FR-06': 'Nice', 'PT-11': 'Lisbon', 'PT-13': 'Porto', 'PL-14': 'Warsaw',
    'CZ-PR': 'Prague', 'NO-03': 'Oslo', 'FI-18': 'Helsinki', 'CH-GE': 'Geneva',
    'CH-ZH': 'Zurich', 'BR-DF': 'Brasília', 'HK-HKI': 'Pulau Hong Kong', 'HK-KLN': 'Kowloon',
    'HK-NTE': 'Wilayah Baharu',
  },
};

function _localizeCountry(ptName) {
  if (LANG === 'pt') return ptName;
  const t = _COUNTRY_LABELS[ptName];
  if (!t) return ptName;
  return t[LANG] || t.en || ptName;
}

// Country names for the languages beyond the first five come from CLDR via
// Intl.DisplayNames — every country, every language, nothing to maintain.
const _REGION_NAMES = (() => {
  if (_IS_LEGACY_LANG || typeof Intl === 'undefined' || !Intl.DisplayNames) return null;
  try { return new Intl.DisplayNames([LOCALE_TAG], { type: 'region' }); } catch (e) { return null; }
})();

function _localizeCountryByIso2(iso2) {
  if (_REGION_NAMES && /^[A-Z]{2}$/.test(iso2 || '')) {
    try {
      const name = _REGION_NAMES.of(iso2);
      if (name && name !== iso2) return name;
    } catch (e) { /* fall through to the tables */ }
  }
  const ptName = _ISO2_TO_DATA_COUNTRY[iso2];
  if (ptName) return _localizeCountry(ptName);
  return _loadedLocations.get(iso2)?.name ?? iso2;
}

function _localizeSubdiv(pais, code, fallback) {
  const t = _SUBDIV_LABELS[pais]?.[code];
  if (!t) return fallback;
  if (LANG === 'pt') return t.pt || fallback;
  if (!_IS_LEGACY_LANG) return _SUBDIV_LABELS_MORE[LANG]?.[pais + '-' + code] || t.en || fallback;
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

  const base = allCorridas.filter(c =>
    matchesPeriodo(c) && matchesFonte(c) && matchesDistancia(c) && matchesSearch(c)
  );

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
// Master "All" row for the multi-select dropdowns (fontes / selos). It makes the
// default state self-explanatory: an explicit, pre-checked "Todas as fontes" /
// "Todos os selos" entry, instead of an empty list that merely *implies* "all".
// It mirrors the empty-set semantics (empty selection = no filter = all): the row
// is checked exactly when the selection set is empty. Clicking it resets to all;
// picking a specific option clears it (handled by _syncAllOption).
function _buildAllOption(text, isAll, onReset) {
  const label = document.createElement('label');
  label.className = 'fonte-filter-option fonte-filter-all' + (isAll ? ' checked' : '');
  label.setAttribute('role', 'option');
  label.setAttribute('aria-selected', String(isAll));

  const cb = document.createElement('input');
  cb.type = 'checkbox';
  cb.checked = isAll;

  label.appendChild(cb);
  label.appendChild(document.createTextNode(text));
  cb.addEventListener('change', onReset);
  return label;
}

// Keep the master "All" row in sync after an individual option toggles, without
// rebuilding the whole dropdown.
function _syncAllOption(dropdown, isAll) {
  const row = dropdown && dropdown.querySelector('.fonte-filter-all');
  if (!row) return;
  const cb = row.querySelector('input');
  if (cb) cb.checked = isAll;
  row.classList.toggle('checked', isAll);
  row.setAttribute('aria-selected', String(isAll));
}

function populateFontesFilter() {
  const base = allCorridas.filter(c =>
    matchesPeriodo(c) && matchesEstado(c) && matchesDistancia(c) && matchesSearch(c)
  );
  const availableNomes = new Set(base.flatMap(c => (c.fontes || []).map(f => f.nome)));

  let stateChanged = false;
  for (const nome of [...state.fontes]) {
    if (!availableNomes.has(nome)) { state.fontes.delete(nome); stateChanged = true; }
  }
  if (stateChanged) saveFilters();

  fonteFilterDropdown.innerHTML = '';

  // Pre-checked "Todas as fontes" master row — clicking it resets to all.
  fonteFilterDropdown.appendChild(_buildAllOption(T.allSources, state.fontes.size === 0, () => {
    state.fontes.clear();
    saveFilters();
    populateEstadoFilter({ skipGeo: true });
    populateFontesFilter();   // refresh master + individual checkboxes
    applyFilters();
    renderCards();
    updateCount();
    updateClearButton();
  }));

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
      _syncAllOption(fonteFilterDropdown, state.fontes.size === 0);
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

// Selos / Majors filter — ranked highest→lowest so the legend reads top-down.
const _SELO_ORDER = ['platinum', 'gold', 'elite', 'label', 'major'];

function populateSelosFilter() {
  const dd = document.getElementById('seloFilterDropdown');
  if (!dd) return;
  // Availability/visibility is intentionally decoupled from the location
  // (estado) filter: the selo facet is a global highlight (World Athletics
  // labels / Majors). Tying it to estado made the wrapper flash — visible at
  // first paint (estado "todos"), then hidden once geolocation narrowed to a
  // state with no labelled races. Scope it by período/distância/busca only so
  // it stays stable; the selected selo still ANDs with the location filter.
  const base = allCorridas.filter(c =>
    matchesPeriodo(c) && matchesDistancia(c) && matchesSearch(c)
  );
  const available = new Set(base.flatMap(_seloTokens));

  for (const s of [...state.selos]) {
    if (!available.has(s)) state.selos.delete(s);
  }

  dd.innerHTML = '';
  const present = _SELO_ORDER.filter(s => available.has(s));
  if (present.length === 0) {
    const wrap = document.getElementById('seloFilterWrapper');
    if (wrap) wrap.classList.add('hidden');
    _updateSeloLabel();
    return;
  }
  const wrap = document.getElementById('seloFilterWrapper');
  if (wrap) wrap.classList.remove('hidden');

  // Pre-checked "Todos os selos" master row — clicking it resets to all.
  dd.appendChild(_buildAllOption(T.allSelos, state.selos.size === 0, () => {
    state.selos.clear();
    populateSelosFilter();   // refresh master + individual checkboxes
    onFilterChange();
  }));

  for (const s of present) {
    const label = document.createElement('label');
    label.className = 'fonte-filter-option' + (state.selos.has(s) ? ' checked' : '');
    label.setAttribute('role', 'option');
    label.setAttribute('aria-selected', String(state.selos.has(s)));

    const cb = document.createElement('input');
    cb.type = 'checkbox';
    cb.value = s;
    cb.checked = state.selos.has(s);

    const dot = document.createElement('span');
    dot.className = `selo-dot badge-selo--${s}`;

    label.appendChild(cb);
    label.appendChild(dot);
    label.appendChild(document.createTextNode((T.seloNames && T.seloNames[s]) || s));

    cb.addEventListener('change', () => {
      if (cb.checked) { state.selos.add(s); label.classList.add('checked'); label.setAttribute('aria-selected', 'true'); }
      else { state.selos.delete(s); label.classList.remove('checked'); label.setAttribute('aria-selected', 'false'); }
      _syncAllOption(dd, state.selos.size === 0);
      _updateSeloLabel();
      onFilterChange();
    });
    dd.appendChild(label);
  }
  _updateSeloLabel();
}

function _updateSeloLabel() {
  const lbl = document.getElementById('seloFilterLabel');
  const btn = document.getElementById('seloFilterBtn');
  if (!lbl || !btn) return;
  const n = state.selos.size;
  if (n === 0) { lbl.textContent = T.allSelos; btn.classList.remove('active'); }
  else if (n === 1) { lbl.textContent = (T.seloNames && T.seloNames[[...state.selos][0]]) || T.nSelos(1); btn.classList.add('active'); }
  else { lbl.textContent = T.nSelos(n); btn.classList.add('active'); }
}

// Build the selo filter widget + legend once and append to the selects row.
function _buildSeloWidget() {
  const row = document.querySelector('.filter-row-selects');
  if (!row || document.getElementById('seloFilterWrapper')) return;

  const wrap = document.createElement('div');
  wrap.className = 'fonte-filter-wrapper selo-filter-wrapper hidden';
  wrap.id = 'seloFilterWrapper';
  wrap.innerHTML =
    `<button class="fonte-filter-btn" id="seloFilterBtn" aria-haspopup="listbox" aria-expanded="false">
       <span id="seloFilterLabel">${T.allSelos}</span>
       <span class="fonte-filter-chevron" aria-hidden="true">▾</span>
     </button>
     <button class="selo-legend-btn" id="seloLegendBtn" type="button" aria-label="${T.seloLegendAria}">?</button>
     <div class="fonte-filter-dropdown hidden" id="seloFilterDropdown" role="listbox" aria-multiselectable="true"></div>`;
  row.appendChild(wrap);

  const legend = document.createElement('div');
  legend.className = 'selo-legend hidden';
  legend.id = 'seloLegend';
  legend.innerHTML =
    `<strong>${T.seloLegendTitle}</strong><p>${T.seloLegendIntro}</p>
     <ul>
       <li><span class="selo-dot badge-selo--platinum"></span>${T.seloNames.platinum}</li>
       <li><span class="selo-dot badge-selo--gold"></span>${T.seloNames.gold}</li>
       <li><span class="selo-dot badge-selo--elite"></span>${T.seloNames.elite}</li>
       <li><span class="selo-dot badge-selo--label"></span>${T.seloNames.label}</li>
     </ul>
     <p class="selo-legend-major"><span class="selo-dot badge-selo--major"></span>${T.seloLegendMajor}</p>`;
  wrap.appendChild(legend);

  const btn = wrap.querySelector('#seloFilterBtn');
  const dd = wrap.querySelector('#seloFilterDropdown');
  btn.addEventListener('click', e => {
    e.stopPropagation();
    const willOpen = dd.classList.contains('hidden');
    // closeAllDropdowns lives in the DOMContentLoaded scope and isn't visible
    // from this module-level builder — referencing it bare threw a
    // ReferenceError on every click, which is why the selos menu wouldn't open.
    // Guard with typeof, then self-toggle.
    if (typeof closeAllDropdowns === 'function') closeAllDropdowns();
    dd.classList.toggle('hidden', !willOpen);
    btn.setAttribute('aria-expanded', String(willOpen));
  });
  dd.addEventListener('click', e => e.stopPropagation());

  const legendBtn = wrap.querySelector('#seloLegendBtn');
  legendBtn.addEventListener('click', e => {
    e.stopPropagation();
    legend.classList.toggle('hidden');
  });
  legend.addEventListener('click', e => e.stopPropagation());
  document.addEventListener('click', () => legend.classList.add('hidden'));
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
    matchesDistancia(c) && matchesSearch(c) && matchesSelo(c)
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

// A corrida's selo set: its World Athletics label plus a synthetic "major"
// token when it's an Abbott Major — so both filter through one widget.
function _seloTokens(c) {
  const out = [];
  if (c.selo) out.push(c.selo);
  if (c.major) out.push('major');
  return out;
}

function matchesSelo(c) {
  if (state.selos.size === 0) return true;
  return _seloTokens(c).some(s => state.selos.has(s));
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
// How long the "Novo" badge stays on an event after it is first seen (days).
const NEW_BADGE_DAYS = 15;

function renderCards() {
  cardsList.innerHTML = '';

  if (filteredCorridas.length === 0) {
    emptyState.classList.remove('hidden');
    return;
  }
  emptyState.classList.add('hidden');

  const today       = todayStr();
  const newSince    = addDays(today, -NEW_BADGE_DAYS);
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
    const hasNew = corridas.some(c => c.first_seen_at && c.first_seen_at >= newSince);
    const { section, cardsContainer } = buildMonthSection(monthKey, corridas.length, expand, hasNew);
    for (const corrida of corridas) {
      cardsContainer.appendChild(buildCard(corrida, today, newSince));
    }
    frag.appendChild(section);
  }

  if (recentPast.length > 0) {
    frag.prepend(buildPastSection(recentPast, today, newSince));
  }

  cardsList.appendChild(frag);
}


// Scroll a month section to the top of the viewport, leaving its first cards
// visible right below the sticky bars. Measures the (non-sticky) section, NOT
// the separator button: once a section is open its separator is
// position:sticky, so the button can report the *stuck* offset instead of its
// natural top (e.g. right after a tall month above collapsed). The section
// element is always in normal flow, so its top is reliable.
function _scrollSectionToTop(section, behavior = 'smooth') {
  const cs = getComputedStyle(document.documentElement);
  const headerH  = parseInt(cs.getPropertyValue('--header-h'))  || 0;
  const filtersH = parseInt(cs.getPropertyValue('--filters-h')) || 0;
  const top = section.getBoundingClientRect().top + window.scrollY - headerH - filtersH - 8;
  window.scrollTo({ top: Math.max(0, top), behavior });
}

// On load, anchor the initially-open month (the current one) at the top of
// the scroll so its most recent events are immediately visible — instead of
// landing on the collapsed past-events section at scroll 0.
function _anchorOpenMonth() {
  const section = cardsList.querySelector('.month-section--open');
  if (section) _scrollSectionToTop(section, 'instant');
}

function buildPastSection(corridas, today, newSince) {
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
    cardsContainer.appendChild(buildCard(corrida, today, newSince));
  }

  btn.addEventListener('click', () => {
    const anchorTop = btn.getBoundingClientRect().top;
    const isCollapsed = cardsContainer.classList.contains('month-cards--collapsed');
    if (isCollapsed) {
      closeAllOtherMonths(section);
    } else {
      _closeMonthSection(btn, cardsContainer);
      window.scrollBy({ top: btn.getBoundingClientRect().top - anchorTop, behavior: 'instant' });
      return;
    }
    cardsContainer.classList.remove('month-cards--collapsed');
    btn.setAttribute('aria-expanded', 'true');
    btn.querySelector('.month-chevron').textContent = '▾';
    section.classList.add('month-section--open');
    requestAnimationFrame(() => _scrollSectionToTop(section));
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
  section.className = expanded ? 'month-section month-section--open' : 'month-section';

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
    const anchorTop = btn.getBoundingClientRect().top;
    const isCollapsed = cardsContainer.classList.contains('month-cards--collapsed');
    if (isCollapsed) {
      closeAllOtherMonths(section);
    } else {
      _closeMonthSection(btn, cardsContainer);
      window.scrollBy({ top: btn.getBoundingClientRect().top - anchorTop, behavior: 'instant' });
      return;
    }
    cardsContainer.classList.remove('month-cards--collapsed');
    btn.setAttribute('aria-expanded', 'true');
    btn.querySelector('.month-chevron').textContent = '▾';
    section.classList.add('month-section--open');
    requestAnimationFrame(() => _scrollSectionToTop(section));
  });

  section.appendChild(btn);
  section.appendChild(cardsContainer);
  return { section, cardsContainer };
}

function _buildCardLocation(c) {
  const pais = c.pais || 'BR';

  const locData   = _loadedLocations.get(pais);
  const subdivMap = {};
  for (const s of (locData?.subdivisions || [])) subdivMap[s.code] = s.name;

  const parts = [];

  if (c.estado && subdivMap[c.estado]) {
    parts.push(_localizeSubdiv(pais, c.estado, subdivMap[c.estado]));
  } else {
    const city = (c.cidade || '').split(',')[0].trim();
    if (city) parts.push(city);
  }

  const country = _localizeCountryByIso2(pais);
  if (country) parts.push(country);

  return parts.join(', ') || c.localizacao || '';
}

function buildCard(c, today, newSince) {
  const tmpl = document.getElementById('cardTemplate');
  const node  = tmpl.content.cloneNode(true);
  const card  = node.querySelector('.card');

  // Collapsed section
  const collapsed = card.querySelector('.card-collapsed');

  card.querySelector('.card-title').textContent    = c.titulo;
  card.querySelector('.card-date').textContent     = formatDate(c.data_evento, c.horario, c.distancias);
  card.querySelector('.card-location').textContent = _buildCardLocation(c);

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
    const isNew = c.first_seen_at && c.first_seen_at >= newSince;
    badgeNovo.textContent = T.badgeNovo;
    badgeNovo.classList.toggle('hidden', !isNew);
  }

  // "Cancelado" tag — the edition was officially called off. The pipeline sets
  // c.cancelado from a live source signal; the card stays, just flagged.
  if (c.cancelado) {
    const footer = card.querySelector('.card-footer');
    if (footer) {
      const b = document.createElement('span');
      b.className = 'badge-cancelado';
      b.textContent = T.badgeCancelado;
      footer.insertBefore(b, footer.firstChild);
    }
  }

  // Fontes badge on collapsed card
  const badgeFontes = card.querySelector('.badge-fontes');
  if (badgeFontes && c.fontes && c.fontes.length > 1) {
    badgeFontes.textContent = T.nSources(c.fontes.length);
    badgeFontes.classList.remove('hidden');
  }

  // Official-label / Major badges on collapsed card (highest WA label + Major)
  const footer = card.querySelector('.card-footer');
  if (footer) {
    if (c.selo) {
      const b = document.createElement('span');
      b.className = `badge-selo badge-selo--${c.selo}`;
      b.textContent = (T.seloNames && T.seloNames[c.selo]) || c.selo;
      b.title = T.seloLegendTitle;
      footer.appendChild(b);
    }
    if (c.major) {
      const b = document.createElement('span');
      b.className = 'badge-selo badge-selo--major';
      b.textContent = (T.seloNames && T.seloNames.major) || 'Major';
      b.title = T.seloLegendMajor;
      footer.appendChild(b);
    }
  }

  // Expand / collapse
  collapsed.addEventListener('click',  e => toggleCard(card, c, e));
  collapsed.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggleCard(card, c, e); } });

  return card;
}

function _closeMonthSection(btn, container) {
  for (const openCard of container.querySelectorAll('.card.open')) {
    openCard.classList.remove('open');
    openCard.querySelector('.card-collapsed').setAttribute('aria-expanded', 'false');
    openCard.querySelector('.card-expanded').classList.add('hidden');
    openCard.querySelector('.card-expanded').setAttribute('aria-hidden', 'true');
  }
  container.classList.add('month-cards--collapsed');
  btn.setAttribute('aria-expanded', 'false');
  btn.querySelector('.month-chevron').textContent = '▸';
  btn.parentElement.classList.remove('month-section--open');
}

function closeAllOtherMonths(exceptSection) {
  for (const btn of cardsList.querySelectorAll('.month-separator')) {
    const section = btn.parentElement;
    if (section === exceptSection) continue;
    const container = btn.nextElementSibling;
    if (container && !container.classList.contains('month-cards--collapsed')) {
      _closeMonthSection(btn, container);
    }
  }
}

function toggleCard(card, c, e) {
  if (e.target.closest('a, button')) return;
  const isOpen = card.classList.contains('open');

  // Anchor: remember where the card sits in the viewport before any layout change
  const anchorTop = card.getBoundingClientRect().top;

  // Close all other open cards
  for (const other of cardsList.querySelectorAll('.card.open')) {
    if (other !== card) {
      other.classList.remove('open');
      other.querySelector('.card-collapsed').setAttribute('aria-expanded', 'false');
      other.querySelector('.card-expanded').classList.add('hidden');
      other.querySelector('.card-expanded').setAttribute('aria-hidden', 'true');
    }
  }

  // Close all other month sections (keep the one this card lives in)
  closeAllOtherMonths(card.closest('.month-section'));

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
  }

  // Restore viewport position so the card doesn't jump
  window.scrollBy({ top: card.getBoundingClientRect().top - anchorTop, behavior: 'instant' });
}

function buildExpanded(card, c) {
  const expTitle  = card.querySelector('.expanded-title');
  const expDist   = card.querySelector('.expanded-distances');
  const expFontes = card.querySelector('.expanded-fontes');

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

    const _TIPO_ORDER = { inscricao: 0, organizador: 1, calendario: 2 };
    for (const fonte of [...c.fontes].sort((a, b) => {
      const ta = _TIPO_ORDER[a.tipo] ?? 2, tb = _TIPO_ORDER[b.tipo] ?? 2;
      return ta !== tb ? ta - tb : (a.nome || '').localeCompare(b.nome || '');
    })) {
      const div = document.createElement('div');
      div.className = 'fonte-item';
      const link = (fonte.links_inscricao && fonte.links_inscricao.length > 0)
        ? fonte.links_inscricao[0] : (fonte.link_evento || null);
      const btnHtml = link
        ? `<a href="${link}" target="_blank" rel="noopener noreferrer" class="btn-inscricao">${T.registerBtn}</a>`
        : '';
      div.innerHTML = `<span class="fonte-nome-text">${fonte.nome || ''}</span>${btnHtml}`;
      expFontes.appendChild(div);
    }
  }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function formatMonth(yearMonth) {
  const [year, month] = yearMonth.split('-').map(Number);
  if (!_IS_LEGACY_LANG) {
    try {
      // Russian appends the year abbreviation ("октябрь 2026 г."), which the
      // upper-cased month header turns into a stray "Г." — drop it.
      const s = new Date(year, month - 1, 15)
        .toLocaleDateString(LOCALE_TAG, { month: 'long', year: 'numeric' })
        .replace(/\s*г\.$/, '');
      return s.charAt(0).toLocaleUpperCase(LOCALE_TAG) + s.slice(1);
    } catch (e) { /* fall through to the static table */ }
  }
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

  const today = todayStr();
  const iso   = isoDate;

  let label;
  if (iso === today)                label = T.today_label;
  else if (iso === addDays(today,1)) label = T.tomorrow_label;
  else if (iso === addDays(today,-1)) label = T.yesterday_label;
  else {
    const d = new Date(iso + 'T12:00:00');
    if (_IS_LEGACY_LANG) {
      const dateStr = d.toLocaleDateString(LOCALE_TAG, { day: 'numeric', month: 'long', year: 'numeric' });
      label = `${T.dayNames[d.getDay()]}, ${dateStr}`;
    } else {
      // Intl places the weekday where each language puts it
      // ("2026年10月3日(土)", "szo, 2026. október 3.").
      label = d.toLocaleDateString(LOCALE_TAG, { weekday: 'short', day: 'numeric', month: 'long', year: 'numeric' });
    }
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


function _ymd(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

function todayStr() {
  // LOCAL calendar date — never toISOString(), which returns the UTC date and,
  // at negative-UTC offsets (e.g. BRT, UTC-3), rolls over to the next day in the
  // evening — labelling tomorrow's events as "today" and shifting the period
  // filters by a day. Local Y-M-D components match the user's actual date.
  return _ymd(new Date());
}

function addDays(isoDate, days) {
  // Pure local-date arithmetic (no UTC round-trip): parse Y-M-D, add days.
  const [y, m, d] = isoDate.split('-').map(Number);
  return _ymd(new Date(y, m - 1, d + days));
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
    state.fontes.size > 0 ||
    state.selos.size > 0
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
  state.selos.clear();

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
  populateSelosFilter();
  onFilterChange();
}

function toggleCustomDateRow(show) {
  customDateRow.classList.toggle('hidden', !show);
}

// ---------------------------------------------------------------------------
// Event wiring
// ---------------------------------------------------------------------------
document.addEventListener('DOMContentLoaded', () => {
  // Clear any stale persisted filter state from previous sessions
  try { localStorage.removeItem('corridas_filters'); } catch (_) {}

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
  // Header brand: the shoe mark only. The site has no wordmark any more —
  // its name IS its localized descriptive name, which stays in the h1 as
  // visually-hidden text (screen readers + the SEO h1-site-name test).
  //
  // siteTitle must be the FULL title, not a short name: this assignment runs
  // on every load and replaces whatever the server sent. It used to set the
  // bare wordmark, so the keyword-rich served title never survived rendering.
  const headerTitle = document.querySelector('.app-title');
  if (headerTitle) {
    headerTitle.innerHTML = SHOE_LOGO + '<span class="visually-hidden"></span>';
    headerTitle.querySelector('.visually-hidden').textContent = T.headerTitle;
  }
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
  btnHome.setAttribute('aria-label',    T.homeAriaLabel);
  btnLang.setAttribute('aria-label',    T.langAriaLabel);
  btnClear.setAttribute('aria-label',       T.clearFiltersAriaLabel);
  btnClear.textContent      = T.clearFilters;
  btnClearEmpty.textContent = T.clearFilters;

  // Track filters bar height so sticky month headers stop below it
  const _filtersBar = document.querySelector('.filters-bar');
  if (_filtersBar) {
    const _updateFiltersH = () => {
      document.documentElement.style.setProperty('--filters-h', _filtersBar.offsetHeight + 'px');
    };
    new ResizeObserver(_updateFiltersH).observe(_filtersBar);
    _updateFiltersH();
  }
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

  const _LANG_LABELS = {
    pt: 'Português (Brasil)', en: 'English', es: 'Español', de: 'Deutsch', fr: 'Français',
    it: 'Italiano', nl: 'Nederlands', 'pt-pt': 'Português (Portugal)', ru: 'Русский',
    pl: 'Polski', cs: 'Čeština', sk: 'Slovenčina', sl: 'Slovenščina', hr: 'Hrvatski',
    hu: 'Magyar', el: 'Ελληνικά', da: 'Dansk', nb: 'Norsk bokmål', sv: 'Svenska',
    fi: 'Suomi', ja: '日本語', ko: '한국어', 'zh-cn': '简体中文', 'zh-tw': '繁體中文',
    th: 'ไทย', he: 'עברית', id: 'Bahasa Indonesia', ms: 'Bahasa Melayu',
  };
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
      btn.dataset.lang = code; // analytics.js reads this for language_change
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
    dd.style.maxHeight = Math.max(160, window.innerHeight - r.bottom - 16) + 'px';

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
    const sd = document.getElementById('seloFilterDropdown');
    const sb = document.getElementById('seloFilterBtn');
    if (sd) sd.classList.add('hidden');
    if (sb) sb.setAttribute('aria-expanded', 'false');
  }

  loadData();
});
