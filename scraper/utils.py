from __future__ import annotations
import html
import re
import unicodedata
from datetime import date, datetime
from dateutil import parser as dateutil_parser
from unidecode import unidecode

# ---------------------------------------------------------------------------
# Date normalization
# ---------------------------------------------------------------------------

_MONTH_PT = {
    "janeiro": "01", "fevereiro": "02", "março": "03", "marco": "03",
    "abril": "04", "maio": "05", "junho": "06", "julho": "07",
    "agosto": "08", "setembro": "09", "outubro": "10",
    "novembro": "11", "dezembro": "12",
}

_DATE_DMY = re.compile(r"(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{4})")
_DATE_PTBR = re.compile(
    r"(\d{1,2})\s+de\s+([a-záéíóúãõâêô]+)\s+de\s+(\d{4})", re.IGNORECASE
)


def normalize_date(raw: str | None) -> str | None:
    """Return ISO 8601 date string (YYYY-MM-DD) or None."""
    if not raw:
        return None
    raw = raw.strip()

    # Already ISO
    if re.match(r"^\d{4}-\d{2}-\d{2}$", raw):
        return raw

    # DD/MM/YYYY or DD-MM-YYYY or DD.MM.YYYY
    m = _DATE_DMY.search(raw)
    if m:
        d, mo, y = m.group(1), m.group(2), m.group(3)
        return f"{y}-{mo.zfill(2)}-{d.zfill(2)}"

    # "10 de agosto de 2025"
    m = _DATE_PTBR.search(raw)
    if m:
        d, month_str, y = m.group(1), m.group(2).lower(), m.group(3)
        mo = _MONTH_PT.get(unidecode(month_str))
        if mo:
            return f"{y}-{mo}-{d.zfill(2)}"

    # Fallback to dateutil
    try:
        return dateutil_parser.parse(raw, dayfirst=True).strftime("%Y-%m-%d")
    except Exception:
        return None


def normalize_time(raw: str | None) -> str | None:
    """Return HH:MM string or None."""
    if not raw:
        return None
    m = re.search(r"(\d{1,2})[h:](\d{2})", raw.strip())
    if m:
        return f"{m.group(1).zfill(2)}:{m.group(2)}"
    m = re.search(r"(\d{1,2})h", raw.strip(), re.IGNORECASE)
    if m:
        return f"{m.group(1).zfill(2)}:00"
    return None


# ---------------------------------------------------------------------------
# Distance normalization
# ---------------------------------------------------------------------------

_DIST_NUM = re.compile(r"(\d+(?:[.,]\d+)?)\s*k", re.IGNORECASE)
_DIST_WORDS = {
    "cinco": 5, "dez": 10, "quinze": 15, "vinte": 20,
    "meia": 21.097, "half": 21.097,
    "maratona": 42.195, "marathon": 42.195, "full": 42.195,
}


def normalize_distance(raw: str | None) -> float | str | None:
    if not raw:
        return None
    raw_l = raw.strip().lower()
    for word, val in _DIST_WORDS.items():
        if word in raw_l:
            return val
    m = _DIST_NUM.search(raw_l)
    if m:
        return float(m.group(1).replace(",", "."))
    if "infantil" in raw_l or "kids" in raw_l:
        return "Infantil"
    return None


# ---------------------------------------------------------------------------
# Money normalization
# ---------------------------------------------------------------------------

def normalize_valor(raw: str | None) -> float | None:
    if not raw:
        return None
    cleaned = re.sub(r"[R$\s]", "", raw.strip())
    cleaned = cleaned.replace(".", "").replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Title normalization
# ---------------------------------------------------------------------------

_BR_STATES = {
    "AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA",
    "MG", "MS", "MT", "PA", "PB", "PE", "PI", "PR", "RJ", "RN",
    "RO", "RR", "RS", "SC", "SE", "SP", "TO", "INT",
}


def normalize_titulo(raw: str | None) -> str:
    if not raw:
        return ""
    text = html.unescape(raw.strip())
    # Remove Symbol-Other (emojis) but keep letters, digits, punctuation
    text = "".join(c for c in text if not unicodedata.category(c).startswith("So"))
    text = re.sub(r"\s+", " ", text).strip()
    # Apply title-case, then restore known abbreviations (state codes, distance tokens)
    titled = text.title()
    words = []
    for orig, titled_word in zip(text.split(), titled.split()):
        upper = orig.upper()
        # Restore state abbreviations (DF, SP, etc.)
        if upper in _BR_STATES and orig.isupper():
            words.append(upper)
        # Restore distance tokens: 5K, 10K, 21K, 42K
        elif re.match(r'^\d+[kKmM],?$', orig):
            words.append(re.sub(r'[kKmM]', lambda m: m.group().upper(), orig))
        else:
            words.append(titled_word)
    return " ".join(words)


# ---------------------------------------------------------------------------
# Slugify
# ---------------------------------------------------------------------------

def slugify(text: str) -> str:
    text = unidecode(text).lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


# ---------------------------------------------------------------------------
# Title similarity key (for merger)
# ---------------------------------------------------------------------------

_STOP_WORDS = {
    "corrida", "run", "race", "maratona", "meia", "de", "da", "do",
    "das", "dos", "em", "a", "o", "e", "na", "no", "para",
}


def normalize_titulo_merge(titulo: str) -> str:
    t = unidecode(titulo).lower()
    t = re.sub(r"[^a-z0-9 ]", " ", t)
    # Strip standalone 4-digit years so "Corrida 2025" ≈ "Corrida"
    t = re.sub(r"\b20\d{2}\b", "", t)
    tokens = [w for w in t.split() if w not in _STOP_WORDS]
    return " ".join(tokens)


# ---------------------------------------------------------------------------
# City name normalization
# ---------------------------------------------------------------------------

# Canonical forms for cities whose title-case would drop accents (e.g. BRASILIA → Brasília).
# Keys are unidecode(name).lower() so they match any casing/accent variant.
_CIDADE_NORMALIZED: dict[str, str] = {
    # DF
    "brasilia": "Brasília",
    "aguas claras": "Águas Claras",
    "guara": "Guará",
    "paranoa": "Paranoá",
    "candangolandia": "Candangolândia",
    "nucleo bandeirante": "Núcleo Bandeirante",
    "sao sebastiao": "São Sebastião",
    "ceilandia": "Ceilândia",
    # SP
    "sao paulo": "São Paulo",
    "sao bernardo do campo": "São Bernardo do Campo",
    "sao bernardo": "São Bernardo",
    "sao jose dos campos": "São José dos Campos",
    "sao jose": "São José",
    "ribeirao preto": "Ribeirão Preto",
    "sao caetano do sul": "São Caetano do Sul",
    "santo andre": "Santo André",
    "mogi das cruzes": "Mogi das Cruzes",
    "mogi mirim": "Mogi Mirim",
    "sao carlos": "São Carlos",
    "sao jose do rio preto": "São José do Rio Preto",
    "sao joao da boa vista": "São João da Boa Vista",
    "praia grande": "Praia Grande",
    "sao vicente": "São Vicente",
    "itanhaem": "Itanhaém",
    "guaruja": "Guarujá",
    # RJ
    "rio de janeiro": "Rio de Janeiro",
    "petropolis": "Petrópolis",
    "niteroi": "Niterói",
    "sao goncalo": "São Gonçalo",
    "duque de caxias": "Duque de Caxias",
    "nova iguacu": "Nova Iguaçu",
    "campos dos goytacazes": "Campos dos Goytacazes",
    "angra dos reis": "Angra dos Reis",
    "buzios": "Búzios",
    "arraial do cabo": "Arraial do Cabo",
    # MG
    "belo horizonte": "Belo Horizonte",
    "uberlandia": "Uberlândia",
    "contagem": "Contagem",
    "juiz de fora": "Juiz de Fora",
    "betim": "Betim",
    "montes claros": "Montes Claros",
    "ribeirao das neves": "Ribeirão das Neves",
    "sete lagoas": "Sete Lagoas",
    "ipatinga": "Ipatinga",
    "divinopolis": "Divinópolis",
    "governador valadares": "Governador Valadares",
    # RS
    "porto alegre": "Porto Alegre",
    "caxias do sul": "Caxias do Sul",
    "pelotas": "Pelotas",
    "canoas": "Canoas",
    "sao leopoldo": "São Leopoldo",
    "novo hamburgo": "Novo Hamburgo",
    "santa maria": "Santa Maria",
    "gravatai": "Gravataí",
    "viamao": "Viamão",
    # PR
    "curitiba": "Curitiba",
    "londrina": "Londrina",
    "maringa": "Maringá",
    "ponta grossa": "Ponta Grossa",
    "cascavel": "Cascavel",
    "sao jose dos pinhais": "São José dos Pinhais",
    "foz do iguacu": "Foz do Iguaçu",
    # SC
    "florianopolis": "Florianópolis",
    "joinville": "Joinville",
    "blumenau": "Blumenau",
    "sao jose": "São José",
    "chapeco": "Chapecó",
    "itajai": "Itajaí",
    "criciuma": "Criciúma",
    "jaragua do sul": "Jaraguá do Sul",
    # GO
    "goiania": "Goiânia",
    "anapolis": "Anápolis",
    # CE
    "fortaleza": "Fortaleza",
    "caucaia": "Caucaia",
    # BA
    "salvador": "Salvador",
    "feira de santana": "Feira de Santana",
    "vitoria da conquista": "Vitória da Conquista",
    "camacari": "Camaçari",
    "lauro de freitas": "Lauro de Freitas",
    # PE
    "recife": "Recife",
    "caruaru": "Caruaru",
    "olinda": "Olinda",
    "paulista": "Paulista",
    # AM
    "manaus": "Manaus",
    # PA
    "belem": "Belém",
    "ananindeua": "Ananindeua",
    # MA
    "sao luis": "São Luís",
    # PI
    "teresina": "Teresina",
    # AL
    "maceio": "Maceió",
    # SE
    "aracaju": "Aracaju",
    # RN
    "natal": "Natal",
    "mossoro": "Mossoró",
    # PB
    "joao pessoa": "João Pessoa",
    "campina grande": "Campina Grande",
    # ES
    "vitoria": "Vitória",
    "vila velha": "Vila Velha",
    "cariacica": "Cariacica",
    "serra": "Serra",
    # MT
    "cuiaba": "Cuiabá",
    # MS
    "campo grande": "Campo Grande",
    # RO
    "porto velho": "Porto Velho",
    # TO
    "palmas": "Palmas",
    # AC
    "rio branco": "Rio Branco",
    # AP
    "macapa": "Macapá",
    # RR
    "boa vista": "Boa Vista",
}


_LOWER_WORDS = {'de', 'da', 'do', 'das', 'dos', 'e', 'em', 'a', 'o', 'na', 'no', 'para'}


def normalize_cidade(raw: str | None) -> str:
    """Return properly accented, title-cased city name."""
    if not raw:
        return raw or ""
    raw = raw.strip()
    key = unidecode(raw).lower()
    if key in _CIDADE_NORMALIZED:
        return _CIDADE_NORMALIZED[key]
    # Fallback: title case then lowercase Portuguese articles/prepositions
    words = raw.title().split()
    return ' '.join(
        w if i == 0 else (w.lower() if w.lower() in _LOWER_WORDS else w)
        for i, w in enumerate(words)
    )


# ---------------------------------------------------------------------------
# City → State lookup
# ---------------------------------------------------------------------------

_CIDADE_UF: dict[str, str] = {
    # DF
    "brasilia": "DF", "brasília": "DF", "plano piloto": "DF",
    "taguatinga": "DF", "ceilândia": "DF", "ceilandia": "DF",
    "sobradinho": "DF", "gama": "DF", "samambaia": "DF",
    "aguas claras": "DF", "águas claras": "DF", "guara": "DF", "guará": "DF",
    "nucleo bandeirante": "DF", "cruzeiro": "DF", "lago sul": "DF",
    "lago norte": "DF", "paranoa": "DF", "paranoá": "DF",
    "riacho fundo": "DF", "planaltina": "DF", "sao sebastiao": "DF",
    "recanto das emas": "DF", "candangolandia": "DF",
    # SP
    "sao paulo": "SP", "são paulo": "SP", "campinas": "SP",
    "santos": "SP", "sao bernardo": "SP", "guarulhos": "SP",
    "osasco": "SP", "ribeirao preto": "SP", "sorocaba": "SP",
    # RJ
    "rio de janeiro": "RJ", "niteroi": "RJ", "petrópolis": "RJ",
    "petropolis": "RJ",
    # MG
    "belo horizonte": "MG", "uberlandia": "MG", "contagem": "MG",
    # RS
    "porto alegre": "RS", "caxias do sul": "RS",
    # PR
    "curitiba": "PR", "londrina": "PR",
    # SC
    "florianopolis": "SC", "florianópolis": "SC", "joinville": "SC",
    # CE
    "fortaleza": "CE",
    # BA
    "salvador": "BA",
    # PE
    "recife": "PE",
    # AM
    "manaus": "AM",
    # GO
    "goiania": "GO", "goiânia": "GO",
}

_BSB_KEYWORDS = {
    "brasília", "brasilia", "df", "distrito federal", "plano piloto",
    "taguatinga", "ceilândia", "ceilandia", "sobradinho", "gama",
    "samambaia", "águas claras", "aguas claras", "guará", "guara",
}


def infer_estado(localizacao: str, titulo: str = "") -> str | None:
    text = (localizacao + " " + titulo).lower()
    text_ascii = unidecode(text)

    for keyword in _BSB_KEYWORDS:
        if keyword in text or unidecode(keyword) in text_ascii:
            return "DF"

    for cidade, uf in _CIDADE_UF.items():
        if unidecode(cidade) in text_ascii:
            return uf

    return None


def is_bsb_event(localizacao: str, titulo: str = "") -> bool:
    text = (localizacao + " " + titulo).lower()
    text_ascii = unidecode(text)
    for keyword in _BSB_KEYWORDS:
        if keyword in text or unidecode(keyword) in text_ascii:
            return True
    return False


# ---------------------------------------------------------------------------
# Timestamp helpers
# ---------------------------------------------------------------------------

def now_iso() -> str:
    from datetime import timezone
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def today_iso() -> str:
    return date.today().isoformat()


# ---------------------------------------------------------------------------
# Robust date extraction from BeautifulSoup soup (for major scrapers)
# ---------------------------------------------------------------------------

_YEAR_RE = re.compile(r'\b(202[5-9]|203\d)\b')
_MONTH_EN = r'(?:January|February|March|April|May|June|July|August|September|October|November|December)'
_MONTH_DE = r'(?:Januar|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember)'
_MONTH_ANY = f'(?:{_MONTH_EN}|{_MONTH_DE})'

_DATE_PATTERNS = [
    re.compile(rf'\b{_MONTH_ANY}\s+\d{{1,2}}(?:st|nd|rd|th)?,?\s+20\d{{2}}\b', re.IGNORECASE),
    re.compile(rf'\b\d{{1,2}}(?:st|nd|rd|th)?\s+{_MONTH_ANY},?\s+20\d{{2}}\b', re.IGNORECASE),
    re.compile(rf'\b\d{{1,2}}\.\s*{_MONTH_ANY}\s+20\d{{2}}\b', re.IGNORECASE),
    re.compile(r'\b20\d{2}[-/]\d{2}[-/]\d{2}\b'),
    re.compile(r'\b\d{2}[-/]\d{2}[-/]20\d{2}\b'),
]


def extract_date_from_soup(soup, year_hint: int | None = None) -> str | None:
    """Scan BeautifulSoup tree for any recognisable date, return ISO 8601 or None."""
    candidates: list[str] = []
    for tag in soup.find_all(True, limit=300):
        for text in [tag.get_text(' ', strip=True), tag.get('content', ''), tag.get('datetime', '')]:
            if not text or len(text) > 200:
                continue
            for pat in _DATE_PATTERNS:
                m = pat.search(text)
                if m:
                    try:
                        parsed = dateutil_parser.parse(m.group(0), dayfirst=False)
                        if 2025 <= parsed.year <= 2030:
                            candidates.append(parsed.strftime('%Y-%m-%d'))
                    except Exception:
                        pass

    if not candidates:
        return None

    # Prefer dates matching year_hint, otherwise pick the earliest future date
    today = date.today().isoformat()
    if year_hint:
        year_str = str(year_hint)
        same_year = [d for d in candidates if d.startswith(year_str)]
        if same_year:
            return sorted(same_year)[0]

    future = [d for d in candidates if d >= today]
    return sorted(future)[0] if future else sorted(candidates)[-1]
