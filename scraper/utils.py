from __future__ import annotations
import html
import re
import unicodedata
from datetime import date, datetime
from dateutil import parser as dateutil_parser
from unidecode import unidecode

# ---------------------------------------------------------------------------
# Cancellation signal
# ---------------------------------------------------------------------------
# Structured cancellation markers, in the languages the sources actually emit.
# Matched only against STRUCTURED status fields (a platform `status` value, a
# schema.org eventStatus URL) — never against free-text descriptions, whose
# "política de cancelamento" boilerplate would false-positive.
_CANCEL_RE = re.compile(
    r"cancelad|cancell?ed|\bannul|abgesagt|annullat|geannuleerd|odwołan",
    re.IGNORECASE,
)


def is_cancelled(*signals: object) -> bool:
    """True if any structured signal marks the event as officially cancelled.

    Accepts a platform status string (e.g. "Cancelado") and/or a schema.org
    ``eventStatus`` value (``https://schema.org/EventCancelled``). Pass only
    structured fields here, not descriptions/titles.
    """
    for s in signals:
        if not s:
            continue
        text = str(s)
        if "EventCancelled" in text or _CANCEL_RE.search(text):
            return True
    return False


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


def horario_required(data_evento: str | None, today: date | None = None) -> bool:
    """Whether a published start time (horário) is mandatory for this event.

    Rule: horário is required for events within the next 3 months (and for past /
    imminent ones); events 3+ months in the future may still lack it, because
    organisers often haven't announced the start time that far ahead. The
    pipeline keeps those far-future events and re-checks every run, so a horário
    is filled in automatically as the event approaches the 3-month window.

    Returns False when there's no date (the missing-date check handles that).
    """
    if not data_evento:
        return False
    import calendar
    t = today or date.today()
    m = t.month - 1 + 3
    y = t.year + m // 12
    mo = m % 12 + 1
    cutoff = date(y, mo, min(t.day, calendar.monthrange(y, mo)[1]))
    return data_evento[:10] < cutoff.isoformat()


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
# Distance-list extraction from prose / titles (shared helper)
# ---------------------------------------------------------------------------
#
# Many scrapers read distances out of free text ("provas de 3, 5 e 10 km").
# A naive per-number regex like ``\b(\d+)\s*km\b`` only matches the number that
# directly carries the "km" token, so in a *shared-suffix* list ("3, 5 e 10 km")
# it silently drops the 3 and the 5. This helper — ported from the gold-standard
# ``correr_brasilia._extract_distances`` — handles every common enumeration form
# in pt / es / en, snaps 21/42 to their canonical half/full-marathon lengths and
# near-dedups. Use it instead of hand-rolling another per-number km regex.

_CANONICAL_KM = [(42.195, 41.5, 43.0), (21.097, 20.5, 21.5)]

_HALF_MARATHON_RE = re.compile(
    r"meia[\s-]?maratona|half[\s-]?marathon|medi[oa][\s-]?marat[oó]n", re.IGNORECASE
)
_FULL_MARATHON_RE = re.compile(
    r"\bmaratona\b|\bmarathon\b|\bmarat[oó]n\b", re.IGNORECASE
)

# A single distance "token": an explicit numeric km value OR a named distance.
_DIST_TOKEN = (
    r"(?:meia[\s-]?maratona|half[\s-]?marathon|medi[oa][\s-]?marat[oó]n"
    r"|maratona|marathon|marat[oó]n"
    r"|\d+(?:[.,]\d+)?\s*[kK][mM]?)"
)
# Connectors that join list members, across pt ("e"/"ou"), es ("y") and en ("and").
_DIST_CONNECTOR = r"(?:,|;|/|\||\be\b|\bou\b|\by\b|\band\b)"
_DIST_LIST_RE = re.compile(
    rf"{_DIST_TOKEN}(?:\s*{_DIST_CONNECTOR}\s*{_DIST_TOKEN})+", re.IGNORECASE
)
# Shared km suffix: "5 e 10 km", "3, 5 e 10km", "5, 10 y 21 km", "5 / 10 / 21 km".
# The leading-number lookbehind ``(?<![:.\d])`` stops a clock time ("07:00 e 10km")
# or a decimal fragment from seeding a bogus list — the "00" after ":" must not be
# read as the first distance.
_DIST_SHARED_SUFFIX_RE = re.compile(
    r"(?<![:.\d])(\d+(?:[.,]\d+)?)"
    r"(?:\s*(?:,|;|/|\||e|ou|y|and)\s*(\d+(?:[.,]\d+)?))+"
    r"\s*[kK][mM]?\b",
    re.IGNORECASE,
)
_DIST_LABEL = (
    r"dist[âa]ncias?|modalidades?|percursos?|provas?|categorias?"
    r"|trajetos?|recorridos?"
)
_DIST_LABELLED_RE = re.compile(
    rf"(?:{_DIST_LABEL})\s*:?\s*({_DIST_TOKEN})", re.IGNORECASE
)
_DIST_KM_RE = re.compile(r"\b(\d+(?:[.,]\d+)?)\s*[kK][mM]?\b")
# Currency-tagged amounts ("R$ 129,90", "US$ 25", "€ 30") — stripped before any
# distance extraction. Price tables like "7 KM: R$ 129,90 | 15 KM: R$ 139,90"
# otherwise feed the shared-suffix matcher via the "|" connector, turning lot
# prices into 129.9 km "distances".
_PRICE_RE = re.compile(r"(?:R\$|US?\$|\$|€|£)\s*\d+(?:[.,]\d{1,2})?")
# A number with exactly two decimals is money formatting, not a distance
# ("139,90"); real fractional distances use one ("7,5") or three ("21,097").
_TWO_DECIMALS_RE = re.compile(r"^\d+[.,]\d{2}$")


def _dist_token_to_km(tok: str, allow_named: bool) -> float | None:
    """Convert one distance token (numeric km or a named distance) to km."""
    t = tok.strip().lower()
    if allow_named and _HALF_MARATHON_RE.search(t):
        return 21.097
    if allow_named and _FULL_MARATHON_RE.search(t):
        return 42.195
    m = re.match(r"(\d+(?:[.,]\d+)?)", t)
    if m:
        try:
            return float(m.group(1).replace(",", "."))
        except ValueError:
            return None
    return None


def _filter_km_values(raw_values: list[float], min_km: float, max_km: float = 200.0) -> list[float]:
    """Snap 21/42 to canonical lengths, drop out-of-range, near-dedup (<0.5 km)."""
    seen: list[float] = []
    for raw in raw_values:
        if raw < min_km or raw > max_km:
            continue
        km = raw
        for canon, lo, hi in _CANONICAL_KM:
            if lo <= raw <= hi:
                km = canon
                break
        if any(abs(km - s) < 0.5 for s in seen):
            continue
        seen.append(km)
    return seen


def extract_distances_from_text(
    text: str | None,
    *,
    min_km: float = 3.0,
    max_km: float = 200.0,
    allow_named: bool = True,
    named_in_prose: bool = False,
    title: str = "",
    max_results: int = 8,
) -> list[float]:
    """Extract race distances (km) from prose or a title, robust to shared suffixes.

    Resolution order (first non-empty wins), mirroring correr_brasilia:
      1. Explicit distance lists of 2+ tokens ("5km, 10km e meia maratona").
      2. Shared km suffix ("3, 5 e 10 km" / "5, 10 y 21 km" / "5 / 10 / 21 km").
      3. A labelled single value ("Modalidade: Maratona", "Distância: 42km").
      4. Prose-safe numeric km scan (named terms are NOT inferred from loose prose).
      5. A parenthetical km list in the title ("(5km e 10km)").

    Named distances (maratona / meia maratona / marathon / medio maratón) count
    only as enumeration tokens by default — never inferred from free prose — which
    prevents phantom marathons from text like "a maior maratona de rua do DF". Pass
    ``named_in_prose=True`` for short, reliable strings (e.g. an event *title* such
    as "Meia Maratona de São Paulo") where a standalone named distance should count.
    Numeric 21/42 are canonical-snapped (21.097 / 42.195) and values within 0.5 km
    of an already-seen distance are deduped. Returns a sorted list of unique floats.
    """
    text = _PRICE_RE.sub(" ", text or "")
    raw: list[float] = []

    # 0. Standalone named distance, opt-in (titles only — avoids phantom marathons).
    if named_in_prose and allow_named:
        if _HALF_MARATHON_RE.search(text):
            raw.append(21.097)
        # "maratona" but not preceded by "meia"/"half" (handled above).
        for m in _FULL_MARATHON_RE.finditer(text):
            start = m.start()
            preceding = text[max(0, start - 6):start].lower()
            if "meia" not in preceding and "half" not in preceding and "medio" not in preceding and "média" not in preceding:
                raw.append(42.195)

    # 1. Distance lists (2+ tokens).
    for list_m in _DIST_LIST_RE.finditer(text):
        for tok_m in re.finditer(_DIST_TOKEN, list_m.group(0), re.IGNORECASE):
            km = _dist_token_to_km(tok_m.group(0), allow_named)
            if km is not None:
                raw.append(km)
    # 2. Shared km suffix.
    for m in _DIST_SHARED_SUFFIX_RE.finditer(text):
        for num_m in re.finditer(r"\d+(?:[.,]\d+)?", m.group(0)):
            if _TWO_DECIMALS_RE.match(num_m.group(0)):
                continue  # money formatting, not a distance
            try:
                raw.append(float(num_m.group(0).replace(",", ".")))
            except ValueError:
                pass
    # 3. Labelled single distance.
    if not raw:
        for lab_m in _DIST_LABELLED_RE.finditer(text):
            km = _dist_token_to_km(lab_m.group(1), allow_named)
            if km is not None:
                raw.append(km)
    # 4. Prose-safe numeric km scan (explicit numbers only).
    if not raw:
        for m in _DIST_KM_RE.finditer(text):
            try:
                raw.append(float(m.group(1).replace(",", ".")))
            except ValueError:
                continue
    # 5. Parenthetical km list in the title.
    if not raw and title:
        paren = re.search(r"\([^)]*\d+\s*[kK][mM]?[^)]*\)", title)
        if paren:
            for m in _DIST_KM_RE.finditer(paren.group(0)):
                try:
                    raw.append(float(m.group(1).replace(",", ".")))
                except ValueError:
                    continue

    return sorted(_filter_km_values(raw, min_km, max_km)[:max_results])


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
    "RO", "RR", "RS", "SC", "SE", "SP", "TO",
}


def normalize_titulo(raw: str | None) -> str:
    if not raw:
        return ""
    # Iteratively unescape: some sources (correrbrasilia.com.br JSON-LD) emit
    # double-encoded entities like "&amp;amp;". A single html.unescape leaves
    # "&amp;" intact and the .title() below would mangle it into "&Amp;".
    text = raw.strip()
    for _ in range(3):
        new = html.unescape(text)
        if new == text:
            break
        text = new
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
        # Edition numerals stay uppercase ("IX Corrida", "Etapa III"). Only
        # I/V/X forms (1–39) — allowing L/C/D/M would catch real words that
        # title-case into roman lookalikes ("Mix", "Liv", "Dom"...).
        elif re.fullmatch(r'x{0,3}(?:ix|iv|v?i{0,3})[ªº°.,]?', orig, re.IGNORECASE) \
                and re.search(r'[ivxIVX]', orig):
            words.append(orig.upper())
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
    raw = html.unescape(raw.strip())
    key = unidecode(raw).lower()
    if key in _CIDADE_NORMALIZED:
        return _CIDADE_NORMALIZED[key]
    # Fallback: title case then lowercase Portuguese articles/prepositions
    orig_words = raw.split()
    words = raw.title().split()
    result = [
        w if i == 0 else (w.lower() if w.lower() in _LOWER_WORDS else w)
        for i, w in enumerate(words)
    ]
    # Restore all-caps abbreviations that .title() wrongly lowercased (e.g. EUA, SP, RJ)
    for i, (orig, res) in enumerate(zip(orig_words, result)):
        bare = orig.strip('.,')
        if bare.isupper() and len(bare) >= 2:
            result[i] = orig
    return ' '.join(result)


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
    "piracicaba": "SP", "sao roque": "SP", "são roque": "SP",
    "bauru": "SP", "marilia": "SP", "presidente prudente": "SP",
    "jundiai": "SP", "indaiatuba": "SP", "limeira": "SP",
    "sao jose do rio preto": "SP", "sao carlos": "SP",
    "americana": "SP", "araras": "SP", "botucatu": "SP",
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
    "governador celso ramos": "SC", "balneario camboriu": "SC",
    "itajai": "SC", "blumenau": "SC", "chapeco": "SC",
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
    "paranoá", "paranoa", "lago paranoá", "lago paranoa",
    "ponte jk", "sces trecho", "setor de clubes",
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


def _collect_date_candidates(soup) -> list[str]:
    candidates: list[str] = []
    # schema.org Event JSON-LD: startDate is the authoritative race date and the
    # most reliable source on organizer sites (World Marathon Majors, EventOn,
    # etc.). The generic tag scan below skips <script> JSON (too long), so pull
    # startDate out explicitly first.
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = script.string or script.get_text() or ""
        for m in re.finditer(r'"startDate"\s*:\s*"(\d{4}-\d{2}-\d{2})', raw):
            iso = m.group(1)
            try:
                if 2025 <= int(iso[:4]) <= 2030:
                    candidates.append(iso)
            except ValueError:
                pass
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
    return candidates


def extract_date_from_soup(soup, year_hint: int | None = None) -> str | None:
    """Return the single best date from a page (earliest future, or latest past)."""
    candidates = _collect_date_candidates(soup)
    if not candidates:
        return None
    today = date.today().isoformat()
    if year_hint:
        year_str = str(year_hint)
        same_year = [d for d in candidates if d.startswith(year_str)]
        if same_year:
            return sorted(same_year)[0]
    future = [d for d in candidates if d >= today]
    return sorted(future)[0] if future else sorted(candidates)[-1]


def extract_all_future_dates(soup, today: str | None = None) -> list[str]:
    """Return all unique future dates found on a page, sorted ascending."""
    if today is None:
        today = date.today().isoformat()
    candidates = _collect_date_candidates(soup)
    return sorted(set(d for d in candidates if d >= today))


# ---------------------------------------------------------------------------
# Image URL validation
# ---------------------------------------------------------------------------
import re as _re
from urllib.parse import urlparse as _urlparse

_SUSPICIOUS_HOST = _re.compile(
    r"casino|silver|gold|crypto|bet|poker|loan|forex|pharma|"
    r"adult|xxx|porn|drug|pill|slot|wager|clickad|doubleclick|"
    r"adserv|tracker|analytics",
    _re.IGNORECASE,
)

# CDNs / hosting platforms that legitimately serve images for any event
_TRUSTED_CDN = frozenset({
    "cloudfront.net", "amazonaws.com", "bubble.io", "wixstatic.com",
    "imgix.net", "fastly.net", "akamaized.net", "cloudinary.com",
    "staticflickr.com", "cdn.jsdelivr.net",
    # Verified race organization domains that serve images for multiple sites
    "londonmarathonevents.co.uk",
})


def _reg_domain(host: str) -> str:
    """Registered domain, handling ccSLDs like .co.uk and .com.br."""
    parts = host.lstrip("www.").split(".")
    if len(parts) >= 3 and parts[-2] in ("co", "com", "org", "net", "gov", "edu"):
        return ".".join(parts[-3:])
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def validate_image_url(url: str | None, source_domain: str | None = None) -> str | None:
    """Return url if it passes safety checks, else None.

    Always rejects suspicious host keywords.
    With source_domain: also rejects images from unrelated domains,
    unless the image host is a known trusted CDN.
    """
    if not url or not url.startswith("http"):
        return None
    try:
        host = _urlparse(url).hostname or ""
    except Exception:
        return None
    if not host:
        return None
    if _SUSPICIOUS_HOST.search(host):
        return None
    if source_domain:
        img_base = _reg_domain(host)
        # Trusted CDNs are always allowed regardless of source
        if img_base in _TRUSTED_CDN or any(host.endswith("." + cdn) for cdn in _TRUSTED_CDN):
            return url
        src_host = _urlparse(source_domain).hostname or source_domain
        if _reg_domain(src_host) != img_base:
            return None
    return url


# ---------------------------------------------------------------------------
# Kids-only event detection
# ---------------------------------------------------------------------------
# Kids-only races (dashes, "corrida mirim/infantil") pollute a road-running
# calendar. The hard part is NOT removing *adult* races that merely offer a kids
# sub-event ("Eagle Run 5K & Kids Run", "Missoula Marathon … Kids Marathon").
# Rule: an event is kids-only when its title is a known kids brand, OR it carries
# explicit kids wording AND has no adult running distance (>= 3 km).
_KIDS_BRAND_RE = re.compile(r"\bmarotinga\b|pezinho\s+veloz", re.IGNORECASE)
_KIDS_WORD_RE = re.compile(
    r"\binfantil\b|\bmirim\b|\bkids?\s+run\b|\bkids?\s+dash\b"
    r"|corrida\s+(?:de\s+)?kids|baby\s+run|\bkids?\s+marathon\b",
    re.IGNORECASE,
)


def _has_adult_distance(distancias) -> bool:
    for d in distancias or []:
        km = getattr(d, "km", None)
        if km is None and isinstance(d, dict):
            km = d.get("km")
        if isinstance(km, (int, float)) and km >= 3.0:
            return True
        if isinstance(km, str):  # miles string like "1.8 mi"
            m = re.match(r"\s*([0-9]+(?:\.[0-9]+)?)", km)
            if m and float(m.group(1)) * 1.60934 >= 3.0:
                return True
    return False


def is_kids_event(titulo: str, distancias=None) -> bool:
    """True for kids-only races (filtered out of the calendar).

    Conservative: a known kids brand always counts; otherwise kids wording only
    counts when there is no adult distance, so adult races with a kids sub-event
    are kept.
    """
    t = titulo or ""
    if _KIDS_BRAND_RE.search(t):
        return True
    if _KIDS_WORD_RE.search(t) and not _has_adult_distance(distancias):
        return True
    return False
