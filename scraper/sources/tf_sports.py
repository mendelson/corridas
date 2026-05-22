"""Scraper for tfsports.com.br — uses Strapi CMS API (painel-website.tfsports.com.br)."""
from __future__ import annotations
import json
import re
import unicodedata
import httpx
from bs4 import BeautifulSoup

from ..models import Corrida, Distancia, FonteInfo
from ..utils import normalize_titulo, slugify, infer_estado, now_iso, today_iso
from ..http_client import get as _http_get
from .. import geo as _geo

BASE = "https://www.tfsports.com.br"
API_BASE = "https://painel-website.tfsports.com.br/api"
def _run_series_url() -> str:
    """Upcoming run-series events (published + drafts) with startDate >= today."""
    today = today_iso()
    return (
        f"{API_BASE}/run-series"
        "?publicationState=preview"
        "&populate[eventData][populate]=*"
        "&populate[pageSeo][populate]=*"
        "&sort=eventData.startDate:asc"
        f"&filters[eventData][startDate][$gte]={today}"
        "&pagination[pageSize]=100"
    )


# run-series drafts without a startDate yet — sort newest first so Flying Run-style
# events that are still being set up don't get buried behind historical records.
_RUN_SERIES_NO_DATE = (
    f"{API_BASE}/run-series"
    "?publicationState=preview"
    "&populate[eventData][populate]=*"
    "&populate[pageSeo][populate]=*"
    "&sort=id:desc"
    "&filters[eventData][startDate][$null]=true"
    "&pagination[pageSize]=100"
)
# 100 most recently created run-series entries — catches drafts with eventData=null
# (where even the null-date filter above wouldn't match).
_RUN_SERIES_RECENT = (
    f"{API_BASE}/run-series"
    "?publicationState=preview"
    "&populate[eventData][populate]=*"
    "&populate[pageSeo][populate]=*"
    "&sort=id:desc"
    "&pagination[pageSize]=100"
)


def _events_list_url() -> str:
    """Upcoming events (startDate >= today) in preview mode."""
    today = today_iso()
    return (
        f"{API_BASE}/events"
        "?publicationState=preview"
        "&populate[eventData][populate]=*"
        "&populate[pageSeo][populate]=*"
        "&sort=eventData.startDate:asc"
        f"&filters[eventData][startDate][$gte]={today}"
        "&pagination[pageSize]=100"
    )


# Events with no startDate set (draft events pending date fill-in).
_EVENTS_URL_NO_DATE = (
    f"{API_BASE}/events"
    "?publicationState=preview"
    "&populate[eventData][populate]=*"
    "&populate[pageSeo][populate]=*"
    "&sort=id:desc"
    "&filters[eventData][startDate][$null]=true"
    "&pagination[pageSize]=100"
)
# 100 most recently created events regardless of date — captures events that use
# a non-standard date field or have startDate stored in an unexpected format.
_EVENTS_URL_RECENT = (
    f"{API_BASE}/events"
    "?publicationState=preview"
    "&populate[eventData][populate]=*"
    "&populate[pageSeo][populate]=*"
    "&sort=id:desc"
    "&pagination[pageSize]=100"
)


def _experiences_url() -> str:
    """Upcoming TF Experience events (startDate >= today) in preview mode."""
    today = today_iso()
    return (
        f"{API_BASE}/experiences"
        "?publicationState=preview"
        "&populate=deep,5"
        "&sort=eventData.startDate:asc"
        f"&filters[eventData][startDate][$gte]={today}"
        "&pagination[pageSize]=100"
    )


# Experiences with no startDate yet (drafts still being set up).
_EXPERIENCES_NO_DATE = (
    f"{API_BASE}/experiences"
    "?publicationState=preview"
    "&populate=deep,5"
    "&sort=id:desc"
    "&filters[eventData][startDate][$null]=true"
    "&pagination[pageSize]=100"
)

_RUNNING_AREAS = {"running", "corrida", "trail", "trilha"}
_NON_RUNNING_EXP_RE = re.compile(
    r"\b(yoga|pilates|zumba|dança|danca|tenis|tennis|vôlei|volei|ciclismo|natação|natacao|crossfit)\b",
    re.IGNORECASE,
)
_RUNNING_TITLE_RE = re.compile(
    r"\b(run|corrida|trail|maratona|meia|5k|10k|21k|42k|\d+\s*km|marathon|race|atletismo|trilha)\b",
    re.IGNORECASE,
)


def _exp_is_running(attrs: dict) -> bool:
    """Return True when an experience is a running-type event.

    Logic:
      1. Title contains obvious non-running sport → exclude.
      2. area.data is null/empty → include (untagged, assume running).
      3. area name contains a running keyword → include.
      4. area name is non-running → rescue if title contains a running keyword.
    """
    titulo = attrs.get("title") or ""
    if _NON_RUNNING_EXP_RE.search(titulo):
        return False
    area = attrs.get("area") or {}
    if isinstance(area, dict):
        area_data = area.get("data") or {}
        if not area_data:
            return True  # no area → include (may not be tagged yet)
        area_attrs = area_data.get("attributes") or {}
        area_name = (area_attrs.get("name") or area_attrs.get("slug") or "").lower()
        if not area_name or any(kw in area_name for kw in _RUNNING_AREAS):
            return True
        # Non-running area tag: rescue if title strongly suggests a running event
        return bool(_RUNNING_TITLE_RE.search(titulo))
    return True


SOURCE_NAME = "TF Sports"

_TIMEOUT = 30
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
_HEADERS_HTML = {
    "User-Agent": _UA,
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.7",
}

_BR_STATES = {
    "AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA",
    "MG", "MS", "MT", "PA", "PB", "PE", "PI", "PR", "RJ", "RN",
    "RO", "RR", "RS", "SC", "SE", "SP", "TO",
}

# CEP first-5-digits → UF (Correios postal-code ranges).
_CEP_RANGES: list[tuple[int, int, str]] = [
    (1000,  19999, "SP"), (20000, 28999, "RJ"), (29000, 29999, "ES"),
    (30000, 39999, "MG"), (40000, 48999, "BA"), (49000, 49999, "SE"),
    (50000, 56999, "PE"), (57000, 57999, "AL"), (58000, 58999, "PB"),
    (59000, 59999, "RN"), (60000, 63999, "CE"), (64000, 64999, "PI"),
    (65000, 65999, "MA"), (66000, 68899, "PA"), (68900, 68999, "AP"),
    (69000, 69299, "AM"), (69300, 69399, "RR"), (69400, 69899, "AM"),
    (69900, 69999, "AC"), (70000, 72799, "DF"), (72800, 72999, "GO"),
    (73000, 73699, "DF"), (73700, 76799, "GO"), (76800, 76999, "RO"),
    (77000, 77999, "TO"), (78000, 78899, "MT"), (78900, 78999, "RO"),
    (79000, 79999, "MS"), (80000, 87999, "PR"), (88000, 89999, "SC"),
    (90000, 99999, "RS"),
]


def _state_from_cep(text: str) -> str | None:
    """Find a CEP in the text and return its UF (state)."""
    if not text:
        return None
    m = re.search(r"\b(\d{5})-?\d{3}\b", text)
    if not m:
        return None
    cep = int(m.group(1))
    for low, high, uf in _CEP_RANGES:
        if low <= cep <= high:
            return uf
    return None


# ---------------------------------------------------------------------------
# Token extraction
# ---------------------------------------------------------------------------

def _get_bearer_token() -> str | None:
    """Extract Bearer token from the compiled Next.js app bundle.

    Uses the proxy chain for the HTML page (handles Cloudflare).
    Searches _app and chunked bundles — Next.js may split the token across
    any static chunk, not only the _app entry point.
    """
    try:
        resp = _http_get(f"{BASE}/run-series/", source=SOURCE_NAME, timeout=_TIMEOUT)
        if resp.status_code != 200:
            return None
        soup = BeautifulSoup(resp.text, "lxml")
        for script in soup.find_all("script", src=True):
            src = script.get("src", "")
            if not src.endswith(".js"):
                continue
            # "_app" is primary; also check other chunked bundles
            if not any(kw in src for kw in ("_app", "pages/_", "chunks/")):
                continue
            bundle_url = src if src.startswith("http") else f"{BASE}{src}"
            try:
                bundle = httpx.get(
                    bundle_url, headers=_HEADERS_HTML, timeout=_TIMEOUT, follow_redirects=True
                )
                if bundle.status_code != 200:
                    continue
            except Exception:
                continue
            text = bundle.text
            for pat in [
                # "Bearer ".concat("TOKEN") — typical Next.js minified bundle pattern
                r'"Bearer\s+"\s*\.\s*concat\s*\(\s*"([^"]{20,})"',
                # Simpler concat form without spaces
                r'concat\s*\(\s*"([a-f0-9]{40,})"',
                # Plain "Bearer TOKEN" in a single string
                r'"Bearer\s+([\w\-_]{20,})"',
                # JWT (ey... prefix)
                r'"(ey[\w\-_.]{20,})"',
            ]:
                m = re.search(pat, text)
                if m:
                    return m.group(1)
    except Exception as e:
        print(f"[{SOURCE_NAME}] erro ao extrair token: {e}")
    return None


# ---------------------------------------------------------------------------
# Location parsing
# ---------------------------------------------------------------------------

def _strip_symbols(text: str) -> str:
    """Remove emoji and Symbol-Other characters."""
    return "".join(c for c in text if not unicodedata.category(c).startswith("So")).strip()


_STATE_FULL_TO_UF = {
    "acre": "AC", "alagoas": "AL", "amazonas": "AM", "amapá": "AP", "amapa": "AP",
    "bahia": "BA", "ceará": "CE", "ceara": "CE", "distrito federal": "DF",
    "espírito santo": "ES", "espirito santo": "ES", "goiás": "GO", "goias": "GO",
    "maranhão": "MA", "maranhao": "MA", "minas gerais": "MG",
    "mato grosso do sul": "MS", "mato grosso": "MT",
    "pará": "PA", "para": "PA", "paraíba": "PB", "paraiba": "PB",
    "pernambuco": "PE", "piauí": "PI", "piaui": "PI",
    "paraná": "PR", "parana": "PR", "rio de janeiro": "RJ",
    "rio grande do norte": "RN", "rondônia": "RO", "rondonia": "RO",
    "roraima": "RR", "rio grande do sul": "RS",
    "santa catarina": "SC", "sergipe": "SE", "são paulo": "SP", "sao paulo": "SP",
    "tocantins": "TO",
}


def _parse_location(location: str | None, titulo: str = "") -> tuple[str, str]:
    """
    Parse (city, state) from address strings.

    Priority:
      1. CEP → UF mapping (most reliable; addresses are often malformed).
      2. "City - UF" pattern in any comma-separated part.
      3. "City - FullStateName" pattern.
      4. Title fallback for city (e.g. "Aracaju I" → city "Aracaju").
    """
    if not location:
        return "", "??"
    clean = _strip_symbols(location)
    parts = [p.strip() for p in clean.split(",")]

    cep_state = _state_from_cep(clean)

    # Find a "City - UF" or "City - StateName" anywhere in the address
    addr_city, addr_state = "", ""
    for part in parts:
        # City - UF
        m = re.match(r"^(.*?[A-Za-zÀ-ÿ])\s*[-–]\s*([A-Z]{2})$", part.strip())
        if m and m.group(2) in _BR_STATES:
            addr_city, addr_state = m.group(1).strip(), m.group(2).strip()
            break
        # City - FullStateName (or "-City - FullStateName")
        for full, uf in _STATE_FULL_TO_UF.items():
            pat = re.compile(rf"([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ .]+?)\s*[-–]\s*{re.escape(full)}\b",
                             re.IGNORECASE)
            mm = pat.search(part)
            if mm:
                addr_city, addr_state = mm.group(1).strip(), uf
                break
        if addr_state:
            break

    # CEP wins if it disagrees with the address-extracted UF
    if cep_state and addr_state and cep_state != addr_state:
        return (addr_city or _city_from_titulo(titulo)), cep_state
    if addr_state:
        return addr_city, addr_state
    if cep_state:
        return _city_from_titulo(titulo), cep_state

    return "", "??"


_TITULO_CITY_STRIP = re.compile(
    r"\s*\b(i{1,3}|iv|v|vi{0,3}|ix|x|\d+|run|race|series)\b\s*$",
    re.IGNORECASE,
)

# Matches edition markers like "2ª Edição", "3 Ed.", "Round 2"
_EDITION_RE = re.compile(r'^(\d+[aª°.]?\s*)?(edi[çc]|ed\.|round)\b', re.IGNORECASE)


def _venue_candidates(titulo: str) -> list[str]:
    """Return candidate location strings to try geocoding for experience events.

    Titles follow patterns like 'EventName | VenueName | Edition'.
    The venue part (after the first |) or single-word titles are the best hints.
    """
    candidates: list[str] = []
    parts = [p.strip() for p in titulo.split("|")]

    if len(parts) > 1:
        # Non-edition parts after the first segment are venue/location hints
        for part in parts[1:]:
            if not _EDITION_RE.match(part):
                candidates.append(part)
    # Sliding window of 1–2 words (right to left) across all parts
    for part in parts:
        words = [w for w in part.split() if len(w) > 2]
        for i in range(len(words) - 1, -1, -1):
            candidates.append(words[i])
            if i > 0:
                candidates.append(f"{words[i - 1]} {words[i]}")

    seen: set[str] = set()
    result: list[str] = []
    for c in candidates:
        c = c.strip()
        if c and c not in seen:
            seen.add(c)
            result.append(c)
    return result


def _city_from_titulo(titulo: str) -> str:
    """Best-effort city extraction from event title, e.g. 'Aracaju I' → 'Aracaju'.

    Run Series titles use the city name plus a roman numeral or edition number.
    """
    if not titulo:
        return ""
    t = titulo.strip()
    # Strip trailing edition tokens
    while True:
        new = _TITULO_CITY_STRIP.sub("", t).strip(" -")
        if new == t:
            break
        t = new
    return t


# ---------------------------------------------------------------------------
# Distance extraction
# ---------------------------------------------------------------------------

def _km_from_val(val) -> float | None:
    if isinstance(val, (int, float)):
        km = float(val)
    elif isinstance(val, str):
        s = val.replace(",", ".").strip().lower()
        # Strip trailing "km", "k", " m" while keeping numeric core
        s = re.sub(r"\s*(km|k|m)\s*$", "", s)
        try:
            km = float(s)
        except ValueError:
            return None
    else:
        return None
    return km if 0.5 <= km <= 200 else None


_TIME_RE = re.compile(r"^(\d{1,2}):(\d{2})(?::\d{2})?")


def _time_from_val(val) -> str | None:
    """Extract HH:MM from a time/datetime value."""
    if val is None:
        return None
    if isinstance(val, str):
        m = _TIME_RE.search(val)
        if m:
            h, mi = int(m.group(1)), int(m.group(2))
            if 0 <= h <= 23 and 0 <= mi <= 59:
                return f"{h:02d}:{mi:02d}"
        # ISO datetime "2026-05-10T07:00:00.000Z"
        m = re.search(r"T(\d{2}):(\d{2})", val)
        if m:
            return f"{m.group(1)}:{m.group(2)}"
    return None


def _walk_modalities(obj, results: list[Distancia], seen: set[float]) -> None:
    """Recursively walk a JSON tree, capturing objects that look like a
    modality entry — i.e. having a km/distance field. Capture associated
    start time when present.
    """
    if isinstance(obj, list):
        for item in obj:
            _walk_modalities(item, results, seen)
        return
    if not isinstance(obj, dict):
        return

    # Detect a modality-like dict — require explicit distance key
    km_raw = obj.get("km") or obj.get("distance") or obj.get("distancia")
    name = obj.get("name") or obj.get("title") or obj.get("modality") or ""
    # Only fall back to name-extraction when the dict already looks like a
    # modality (has time field) — avoids matching unrelated objects.
    has_time_field = any(
        obj.get(k) for k in ("startTime", "start_time", "horario", "hora")
    )
    if km_raw is None and has_time_field and isinstance(name, str):
        m = re.search(r"(\d+(?:[.,]\d+)?)\s*[kK][mM]?\b", name)
        if m:
            km_raw = m.group(1).replace(",", ".")

    km = _km_from_val(km_raw) if km_raw is not None else None
    if km is not None and km not in seen:
        seen.add(km)
        time_raw = (obj.get("startTime") or obj.get("start_time")
                    or obj.get("horario") or obj.get("hora")
                    or obj.get("time") or obj.get("schedule"))
        horario = _time_from_val(time_raw)
        results.append(Distancia(km=km, data=None, horario=horario))

    for v in obj.values():
        _walk_modalities(v, results, seen)


def _distances_from_api(attrs: dict) -> list[Distancia]:
    """Walk the entire API response looking for modality-like objects."""
    seen: set[float] = set()
    result: list[Distancia] = []
    _walk_modalities(attrs, result, seen)
    return sorted(result, key=lambda d: d.km if isinstance(d.km, (int, float)) else 999)


def _distances_from_next_data(slug: str) -> list[Distancia]:
    """Fall back to the event detail page's __NEXT_DATA__ for modalities."""
    try:
        resp = httpx.get(
            f"{BASE}/run-series/{slug}",
            headers=_HEADERS_HTML,
            timeout=_TIMEOUT,
            follow_redirects=True,
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        tag = soup.find("script", id="__NEXT_DATA__")
        if not tag or not tag.string:
            return []
        data = json.loads(tag.string)
        seen: set[float] = set()
        result: list[Distancia] = []
        _walk_modalities(data, result, seen)
        return sorted(result, key=lambda d: d.km if isinstance(d.km, (int, float)) else 999)
    except Exception:
        return []


def _distances_from_title(titulo: str) -> list[Distancia]:
    nums = re.findall(r"\b(\d+(?:[.,]\d+)?)\s*[kK][mM]?\b", titulo)
    seen: set[float] = set()
    result: list[Distancia] = []
    for n in nums:
        km = float(n.replace(",", "."))
        if km not in seen and 3 <= km <= 100:
            seen.add(km)
            result.append(Distancia(km=km, data=None, horario=None))
    return result


_TF_DEFAULT_DISTANCES = [
    Distancia(km=5.0, data=None, horario=None),
    Distancia(km=10.0, data=None, horario=None),
]


def _get_distances(attrs: dict, slug: str) -> list[Distancia]:
    d = _distances_from_api(attrs)
    if d:
        return d
    d = _distances_from_next_data(slug)
    if d:
        return d
    d = _distances_from_title(attrs.get("title", ""))
    if d:
        return d
    # Track&Field Run Series is a standardized circuit — always 5km and 10km
    return _TF_DEFAULT_DISTANCES


# ---------------------------------------------------------------------------
# Image extraction
# ---------------------------------------------------------------------------

def _extract_image(attrs: dict) -> str | None:
    """Extract image URL from pageSeo.metaImage (Strapi media format)."""
    seo = attrs.get("pageSeo") or {}
    img_data = seo.get("metaImage", {})
    if isinstance(img_data, dict):
        inner = img_data.get("data", {})
        if inner:
            img_attrs = inner.get("attributes", {})
            # Prefer small format (700px), fallback to original
            small = img_attrs.get("formats", {}).get("small", {}).get("url")
            return small or img_attrs.get("url")
    return None


# ---------------------------------------------------------------------------
# Main scraper
# ---------------------------------------------------------------------------

def _fetch_all_pages(
    base_url: str, api_headers: dict, token: str | None, label: str, max_pages: int = 0
) -> list[dict]:
    """Paginate a Strapi v4 list endpoint, returning all raw items.

    max_pages=0 means unlimited (follow pageCount from API metadata).
    max_pages=1 is used for "recent" catch-all endpoints that are intentionally
    designed as a top-N sample, not a full scan.
    """
    all_items: list[dict] = []
    page = 0
    while True:
        page += 1
        page_url = f"{base_url}&pagination[page]={page}"
        try:
            if token:
                resp = httpx.get(
                    page_url, headers=api_headers, timeout=_TIMEOUT, follow_redirects=True
                )
                if resp.status_code in (401, 403):
                    print(f"[{SOURCE_NAME}] {label}: token rejeitado ({resp.status_code}), tentando sem auth")
                    resp = _http_get(page_url, source=SOURCE_NAME, timeout=_TIMEOUT)
            else:
                resp = _http_get(page_url, source=SOURCE_NAME, timeout=_TIMEOUT)
            if resp.status_code in (401, 403):
                print(f"[{SOURCE_NAME}] {label}: acesso negado ({resp.status_code}), pulando endpoint")
                return all_items
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"[{SOURCE_NAME}] {label}: erro ao buscar página {page}: {e}")
            break

        batch = data.get("data", [])
        if not batch:
            break
        all_items.extend(batch)

        meta_pag = data.get("meta", {}).get("pagination", {})
        if page >= meta_pag.get("pageCount", 1):
            break
        if max_pages and page >= max_pages:
            break

    return all_items


def _events_to_corridas(
    events: list[dict], now: str, id_prefix: str, link_prefix: str,
    city_from_title: bool = True,
) -> list[Corrida]:
    corridas: list[Corrida] = []
    for event in events:
        try:
            attrs = event.get("attributes", {})
            titulo = normalize_titulo(attrs.get("title", ""))
            if not titulo or len(titulo) < 3:
                continue
            slug = attrs.get("slug", "")
            ed = attrs.get("eventData") or {}

            data_evento = ed.get("startDate") or ""
            location_raw = ed.get("location") or ""
            is_closed = ed.get("isSubscriptionClosed")

            city, state = _parse_location(location_raw, titulo)
            pais = "BR"
            if state == "??":
                if city_from_title:
                    # Run-series: location_raw is a proper address
                    inferred = infer_estado(location_raw + " " + titulo)
                    _pais_geo, _estado_geo = _geo.resolve(location_raw, city, "BR")
                    pais = _pais_geo or "BR"
                    state = inferred or _estado_geo or ""
                else:
                    # Experience/events: location_raw is the event name, not an address.
                    # Try candidate venue strings extracted from the title.
                    inferred = infer_estado(titulo)
                    pais = "BR"
                    state = ""
                    for candidate in _venue_candidates(titulo):
                        _pais_geo, _estado_geo = _geo.resolve(candidate, "", "BR")
                        if _estado_geo and _pais_geo == "BR":
                            city = candidate
                            state = _estado_geo
                            break
                    if not state:
                        state = inferred or ""
            if not city and city_from_title:
                city = _city_from_titulo(titulo)

            parts = [p for p in [city, state] if p and p != "??"]
            localizacao = ", ".join(parts)

            distancias = _get_distances(attrs, slug)
            imagem_url = _extract_image(attrs)

            horarios_dist = [d.horario for d in distancias if d.horario]
            horario_evento = min(horarios_dist) if horarios_dist else None

            link_evento = f"{link_prefix}/{slug}"
            inscricoes_abertas = None if is_closed is None else (not is_closed)

            fonte = FonteInfo(
                nome=SOURCE_NAME,
                link_evento=link_evento,
                links_inscricao=[link_evento],
            )
            corridas.append(Corrida(
                id=f"{id_prefix}{event.get('id') or slug or slugify(titulo)}",
                titulo=titulo,
                data_evento=data_evento,
                horario=horario_evento,
                localizacao=localizacao,
                cidade=city,
                estado=state,
                pais=pais,
                distancias=distancias,
                imagem_url=imagem_url,
                inscricoes_abertas=inscricoes_abertas,
                periodo_inscricao=None,
                fontes=[fonte],
                miss_count=0,
                first_seen_at=now,
                updated_at=now,
            ))
        except Exception as e:
            attrs = event.get("attributes", {}) if isinstance(event, dict) else {}
            print(f"[{SOURCE_NAME}] erro ao processar '{attrs.get('title', '?')}': {e}")
    return corridas


def scrape() -> list[Corrida]:
    token = _get_bearer_token()
    if not token:
        print(f"[{SOURCE_NAME}] token não encontrado, tentando sem autenticação")

    api_headers: dict = {
        "User-Agent": _UA,
        "Accept": "application/json",
    }
    if token:
        api_headers["Authorization"] = f"Bearer {token}"

    now = now_iso()

    run_series = _fetch_all_pages(_run_series_url(), api_headers, token, "run-series")
    print(f"[{SOURCE_NAME}] run-series: {len(run_series)} eventos brutos")
    corridas = _events_to_corridas(run_series, now, "tfs_", f"{BASE}/run-series")

    run_series_nd = _fetch_all_pages(_RUN_SERIES_NO_DATE, api_headers, token, "run-series(sem data)")
    print(f"[{SOURCE_NAME}] run-series(sem data): {len(run_series_nd)} eventos brutos")
    corridas += _events_to_corridas(run_series_nd, now, "tfs_", f"{BASE}/run-series")

    run_series_recent = _fetch_all_pages(_RUN_SERIES_RECENT, api_headers, token, "run-series(recentes)", max_pages=1)
    print(f"[{SOURCE_NAME}] run-series(recentes): {len(run_series_recent)} eventos brutos")
    corridas += _events_to_corridas(run_series_recent, now, "tfs_", f"{BASE}/run-series")

    events_raw = _fetch_all_pages(_events_list_url(), api_headers, token, "events(data)")
    print(f"[{SOURCE_NAME}] events(data): {len(events_raw)} eventos brutos")
    ev_running = [e for e in events_raw if _exp_is_running(e.get("attributes", {}))]
    corridas += _events_to_corridas(ev_running, now, "tfse_", f"{BASE}/aulas-e-eventos", city_from_title=False)

    events_no_date = _fetch_all_pages(_EVENTS_URL_NO_DATE, api_headers, token, "events(sem data)")
    print(f"[{SOURCE_NAME}] events(sem data): {len(events_no_date)} eventos brutos")
    ev_nd_running = [e for e in events_no_date if _exp_is_running(e.get("attributes", {}))]
    corridas += _events_to_corridas(ev_nd_running, now, "tfse_", f"{BASE}/aulas-e-eventos", city_from_title=False)

    events_recent = _fetch_all_pages(_EVENTS_URL_RECENT, api_headers, token, "events(recentes)", max_pages=1)
    print(f"[{SOURCE_NAME}] events(recentes): {len(events_recent)} eventos brutos")
    ev_rec_running = [e for e in events_recent if _exp_is_running(e.get("attributes", {}))]
    corridas += _events_to_corridas(ev_rec_running, now, "tfse_", f"{BASE}/aulas-e-eventos", city_from_title=False)

    experiences_raw = _fetch_all_pages(_experiences_url(), api_headers, token, "experiences")
    print(f"[{SOURCE_NAME}] experiences: {len(experiences_raw)} eventos brutos")
    exp_running = []
    for e in experiences_raw:
        attrs = e.get("attributes", {})
        if _exp_is_running(attrs):
            exp_running.append(e)
        else:
            area = attrs.get("area") or {}
            area_data = area.get("data") or {} if isinstance(area, dict) else {}
            area_attrs = area_data.get("attributes") or {} if area_data else {}
            area_name = area_attrs.get("name") or area_attrs.get("slug") or "?"
            print(f"[{SOURCE_NAME}] filtrado(exp): '{attrs.get('title', '?')}' area={area_name!r}")
    corridas += _events_to_corridas(exp_running, now, "tfexp_", f"{BASE}/tf-experience", city_from_title=False)

    experiences_nd = _fetch_all_pages(_EXPERIENCES_NO_DATE, api_headers, token, "experiences(sem data)")
    print(f"[{SOURCE_NAME}] experiences(sem data): {len(experiences_nd)} eventos brutos")
    exp_nd_running = [e for e in experiences_nd if _exp_is_running(e.get("attributes", {}))]
    corridas += _events_to_corridas(exp_nd_running, now, "tfexp_", f"{BASE}/tf-experience", city_from_title=False)

    print(f"[{SOURCE_NAME}] {len(corridas)} corridas encontradas")
    # Deduplicate by id — RECENT catch-all endpoints overlap with dated ones
    seen: set[str] = set()
    unique: list[Corrida] = []
    for c in corridas:
        if c.id not in seen:
            seen.add(c.id)
            unique.append(c)
    if len(unique) < len(corridas):
        print(f"[{SOURCE_NAME}] {len(corridas) - len(unique)} duplicata(s) removida(s)")
    return unique
