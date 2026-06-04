"""TF Sports App scraper — /aulas-e-eventos events via Strapi locale=pt-BR.

tf_sports.py queries Strapi without a locale, returning default-locale events.
This scraper adds locale=pt-BR to the same endpoints, catching events that are
only published in the pt-BR locale (e.g. Flying Run Sunset Brasília 2026).

Both scrapers run in parallel; the merger deduplicates by title/date.

Phase 1: Direct Strapi /api/events with locale=pt-BR (bearer token + public fallback)
Phase 2: Playwright on /aulas-e-eventos listing page, intercepting API responses
          — catches any events served by the listing but not in the direct API
"""
from __future__ import annotations
import re

import httpx
from bs4 import BeautifulSoup

from ..models import Corrida, Distancia, FonteInfo
from ..utils import normalize_titulo, slugify, now_iso, today_iso
from ..http_client import get as _http_get, HEADERS
from .. import geo as _geo

SOURCE_NAME = "TF Sports App"
BASE = "https://www.tfsports.com.br"
API_BASE = "https://painel-website.tfsports.com.br/api"
LISTING_URL = f"{BASE}/aulas-e-eventos"

_UA = HEADERS["User-Agent"]
_TIMEOUT = 30

_RUNNING_AREAS = {"running", "corrida", "trail", "trilha"}
_RUNNING_TITLE_RE = re.compile(
    r"\b(runn?(?:ing|er)?|corrida|trail|trilha|maratona|meia.maratona|5k|10k|\d+\s*km)\b",
    re.IGNORECASE,
)
_NON_RUNNING_RE = re.compile(
    r"\b(yoga|pilates|beach.tennis|along(?:amento)?|medita[cç]|funcional"
    r"|dan[cç]a|natac|swim|ciclismo|surf|zumba|cross[- ]?fit)\b",
    re.IGNORECASE,
)
_TF_DEFAULT_DISTANCES = [
    Distancia(km=5.0, data=None, horario=None),
    Distancia(km=10.0, data=None, horario=None),
]

# ---------------------------------------------------------------------------
# Location helpers (mirrors tf_sports.py logic)
# ---------------------------------------------------------------------------

_BR_STATES = {
    "AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA",
    "MG", "MS", "MT", "PA", "PB", "PE", "PI", "PR", "RJ", "RN",
    "RO", "RR", "RS", "SC", "SE", "SP", "TO",
}
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


_COUNTRY_WORDS = {"brasil", "brazil"}


def _parse_location(location: str | None, titulo: str = "") -> tuple[str, str]:
    """Return (city, state) from a location string.

    Handles both comma-separated and pipe-separated formats used by TF Sports,
    e.g. "Rua X - SP" or "Street | Neighborhood, City | Brasil".
    """
    if not location:
        return "", ""
    # Normalise pipe separators to commas for uniform splitting
    normalised = location.replace("|", ",")
    parts = [p.strip() for p in normalised.split(",") if p.strip()]
    city, state = "", ""
    for part in parts:
        m = re.match(r"^(.*?[A-Za-zÀ-ÿ])\s*[-–]\s*([A-Z]{2})$", part.strip())
        if m and m.group(2) in _BR_STATES:
            city, state = m.group(1).strip(), m.group(2)
            break
        for full, uf in _STATE_FULL_TO_UF.items():
            pat = re.compile(
                rf"([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ .]+?)\s*[-–]\s*{re.escape(full)}\b",
                re.IGNORECASE,
            )
            mm = pat.search(part)
            if mm:
                city, state = mm.group(1).strip(), uf
                break
        if state:
            break
    if not city:
        # When pipes were present, use the last non-country, non-address-like segment
        # e.g. "Estrada | Bairro, Cidade | Brasil" → "Cidade"
        non_country = [p for p in parts if p.lower() not in _COUNTRY_WORDS]
        if non_country:
            city = non_country[-1]
    return city, state


# ---------------------------------------------------------------------------
# Event filtering
# ---------------------------------------------------------------------------

def _is_running_event(attrs: dict, ev: dict) -> bool:
    """Return True when the event appears to be a running event."""
    area = attrs.get("area") or ev.get("area") or {}
    if isinstance(area, dict):
        area_inner = area.get("data") or area
        area_attrs = area_inner.get("attributes") or area_inner
        area_slug = (area_attrs.get("slug") or area_attrs.get("name") or "").lower()
        if area_slug:
            if any(kw in area_slug for kw in _RUNNING_AREAS):
                return True
            return False

    # Use eventData.eventName preferentially over section-level title
    title = ev.get("eventName") or attrs.get("title") or ev.get("name") or attrs.get("name") or ""
    if _NON_RUNNING_RE.search(title):
        return False
    return bool(_RUNNING_TITLE_RE.search(title))


# ---------------------------------------------------------------------------
# Distance extraction
# ---------------------------------------------------------------------------

def _time_from_val(val) -> str | None:
    if not isinstance(val, str) or not val:
        return None
    m = re.search(r"[T ](\d{2}):(\d{2})", val)
    if m:
        h, mi = int(m.group(1)), int(m.group(2))
        if 0 <= h <= 23 and 0 <= mi <= 59:
            return f"{h:02d}:{mi:02d}"
    m = re.search(r"\b(\d{1,2})[h:](\d{2})\b", val, re.IGNORECASE)
    if m:
        h, mi = int(m.group(1)), int(m.group(2))
        if 0 <= h <= 23 and 0 <= mi <= 59:
            return f"{h:02d}:{mi:02d}"
    return None


_HORARIO_TEXT_RE = re.compile(
    r"(?:hor[áa]rio|largada|sa[íi]da|in[íi]cio|partida|às?)\s*:?\s*(\d{1,2})[h:](\d{2})"
    r"|\b(\d{1,2})[h:](\d{2})\s*(?:h(?:oras?)?)?\b",
    re.IGNORECASE,
)


def _horario_from_text(text: str) -> str | None:
    m = _HORARIO_TEXT_RE.search(text)
    if not m:
        return None
    h_str = m.group(1) or m.group(3)
    mi_str = m.group(2) or m.group(4)
    if not h_str or not mi_str:
        return None
    h, mi = int(h_str), int(mi_str)
    if 4 <= h <= 23 and 0 <= mi <= 59:
        return f"{h:02d}:{mi:02d}"
    return None


def _horario_from_json(obj, visited: set) -> str | None:
    """Recursively search JSON for a non-midnight event start time (4-23h)."""
    obj_id = id(obj)
    if obj_id in visited:
        return None
    visited.add(obj_id)
    if isinstance(obj, str):
        # ISO timestamp: "2026-07-15T07:00:00.000Z"
        m = re.search(r"T(\d{2}):(\d{2})", obj)
        if m:
            h, mi = int(m.group(1)), int(m.group(2))
            if 4 <= h <= 23:
                return f"{h:02d}:{mi:02d}"
        # Plain time string: "07:00", "7h00", "07h30"
        m = re.search(r"^\s*(\d{1,2})[h:](\d{2})\s*$", obj)
        if m:
            h, mi = int(m.group(1)), int(m.group(2))
            if 4 <= h <= 23 and 0 <= mi <= 59:
                return f"{h:02d}:{mi:02d}"
        return None
    if isinstance(obj, list):
        for item in obj:
            r = _horario_from_json(item, visited)
            if r:
                return r
        return None
    if isinstance(obj, dict):
        for key in ("startDate", "startTime", "start_date", "start_time", "horario", "hora"):
            val = obj.get(key)
            if val:
                r = _horario_from_json(val, visited)
                if r:
                    return r
        for v in obj.values():
            r = _horario_from_json(v, visited)
            if r:
                return r
    return None


def _horario_from_event_page(slug: str) -> str | None:
    """Fetch the event detail page and extract horario from JSON or visible text.

    Tries multiple URL patterns (events and run-series), proxy chain first,
    then Playwright (full JS rendering) as a fallback — the site is Next.js
    and start times may only be populated by client-side JS.
    """
    if not slug:
        return None

    import json as _json

    def _parse(html_text: str) -> str | None:
        soup = BeautifulSoup(html_text, "lxml")
        tag = soup.find("script", id="__NEXT_DATA__")
        if tag and tag.string:
            try:
                data = _json.loads(tag.string)
                h = _horario_from_json(data, set())
                if h:
                    return h
            except Exception:
                pass
        return _horario_from_text(soup.get_text(" ", strip=True))

    def _try_url(url: str) -> str | None:
        html_proxy: str | None = None
        try:
            resp = _http_get(url, source=SOURCE_NAME, timeout=_TIMEOUT)
            if resp.status_code == 200:
                html_proxy = resp.text
        except Exception:
            pass

        if html_proxy:
            h = _parse(html_proxy)
            if h:
                return h

        # Playwright — renders client-side JS that populates start times
        try:
            from ..playwright_client import get_page_html as _pw_html
            pw_html = _pw_html(url, timeout=30_000)
            if pw_html:
                return _parse(pw_html)
        except Exception:
            pass
        return None

    # Try the events listing URL first, then run-series URL as fallback
    # (some events appear in both collections and /run-series/ pages have SSR time data)
    for url in (f"{LISTING_URL}/{slug}", f"{BASE}/run-series/{slug}"):
        h = _try_url(url)
        if h:
            return h

    return None


def _distances_from_modalities(modalities_raw) -> tuple[list[Distancia], str | None]:
    """Returns (distancias, earliest_horario)."""
    items: list[dict] = []
    if isinstance(modalities_raw, dict):
        items = modalities_raw.get("modalitiesItems") or []
    elif isinstance(modalities_raw, list):
        items = modalities_raw

    seen: set[float] = set()
    result: list[Distancia] = []
    horarios: list[str] = []
    for item in items:
        val = item.get("value") or item.get("km") or item.get("distance") or ""
        if not val:
            continue
        km_str = re.sub(r"[^\d,.]", "", str(val)).replace(",", ".")
        if not km_str:
            continue
        try:
            km = float(km_str)
            if 0.5 <= km <= 250 and km not in seen:
                seen.add(km)
                time_raw = (item.get("startTime") or item.get("start_time")
                            or item.get("horario") or item.get("hora"))
                h = _time_from_val(time_raw)
                if h:
                    horarios.append(h)
                result.append(Distancia(km=km, data=None, horario=h))
        except ValueError:
            pass

    dists = sorted(result, key=lambda d: float(d.km) if isinstance(d.km, (int, float)) else 999)
    return dists, (min(horarios) if horarios else None)


def _distances_from_attrs(attrs: dict, titulo: str) -> tuple[list[Distancia], str | None]:
    """Extract distances and start time from eventData.modalities, then title keywords."""
    ev = attrs.get("eventData") or {}
    modalities = ev.get("modalities") or ev.get("modalitiesItems") or []
    dists, horario = _distances_from_modalities(modalities)
    if dists:
        return dists, horario
    result: list[Distancia] = []
    for m in re.finditer(r"\b(\d+(?:[.,]\d+)?)\s*[kK][mM]?\b", titulo):
        try:
            km = float(m.group(1).replace(",", "."))
            if 3 <= km <= 100:
                result.append(Distancia(km=km, data=None, horario=None))
        except ValueError:
            pass
    return (result if result else list(_TF_DEFAULT_DISTANCES)), None


# ---------------------------------------------------------------------------
# Bearer token (same extraction as tf_sports.py)
# ---------------------------------------------------------------------------

_HEADERS_HTML = {
    "User-Agent": _UA,
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.7",
}


def _get_bearer_token() -> str | None:
    try:
        resp = _http_get(f"{BASE}/aulas-e-eventos/", source=SOURCE_NAME, timeout=_TIMEOUT)
        if resp.status_code != 200:
            return None
        soup = BeautifulSoup(resp.text, "lxml")
        for script in soup.find_all("script", src=True):
            src = script.get("src", "")
            if not src.endswith(".js"):
                continue
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
                r'"Bearer\s+"\s*\.\s*concat\s*\(\s*"([^"]{20,})"',
                r'concat\s*\(\s*"([a-f0-9]{40,})"',
                r'"Bearer\s+([\w\-_]{20,})"',
                r'"(ey[\w\-_.]{20,})"',
            ]:
                m = re.search(pat, text)
                if m:
                    return m.group(1)
    except Exception as e:
        print(f"[{SOURCE_NAME}] erro ao extrair token: {e}")
    return None


# ---------------------------------------------------------------------------
# Strapi pagination
# ---------------------------------------------------------------------------

def _fetch_all_pages(base_url: str, api_headers: dict, label: str) -> list[dict]:
    all_items: list[dict] = []
    page = 0
    while True:
        page += 1
        page_url = f"{base_url}&pagination[page]={page}"
        try:
            resp = httpx.get(
                page_url, headers=api_headers, timeout=_TIMEOUT, follow_redirects=True
            )
            if resp.status_code in (401, 403):
                resp = _http_get(page_url, source=SOURCE_NAME, timeout=_TIMEOUT)
            if resp.status_code in (401, 403):
                print(f"[{SOURCE_NAME}] {label}: acesso negado ({resp.status_code})")
                return all_items
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"[{SOURCE_NAME}] {label}: erro página {page}: {e}")
            break

        batch = data.get("data", [])
        if not batch:
            break
        all_items.extend(batch)

        meta_pag = data.get("meta", {}).get("pagination", {})
        if page >= meta_pag.get("pageCount", 1):
            break

    return all_items


def _events_url_dated_locale(today: str) -> str:
    return (
        f"{API_BASE}/events"
        "?publicationState=preview"
        "&populate=deep,6"
        "&sort=eventData.startDate:asc"
        f"&filters[eventData][startDate][$gte]={today}"
        "&locale=pt-BR"
        "&pagination[pageSize]=100"
    )


_EVENTS_URL_NO_DATE_LOCALE = (
    f"{API_BASE}/events"
    "?publicationState=preview"
    "&populate=deep,6"
    "&sort=id:desc"
    "&filters[eventData][startDate][$null]=true"
    "&locale=pt-BR"
    "&pagination[pageSize]=100"
)

_EVENTS_URL_RECENT_LOCALE = (
    f"{API_BASE}/events"
    "?publicationState=preview"
    "&populate=deep,6"
    "&sort=id:desc"
    "&locale=pt-BR"
    "&pagination[pageSize]=100"
)


# ---------------------------------------------------------------------------
# Parse a single Strapi event record
# ---------------------------------------------------------------------------

def _parse_strapi_event(event: dict, now: str) -> Corrida | None:
    attrs = event.get("attributes", {})
    ev = attrs.get("eventData") or {}

    # Title: prefer the Strapi page title, fall back to eventData.eventName
    titulo = normalize_titulo(
        attrs.get("title") or ev.get("eventName") or attrs.get("name") or ""
    )
    if not titulo or len(titulo) < 3:
        return None

    if not _is_running_event(attrs, ev):
        print(f"[{SOURCE_NAME}] filtrado(tipo): {titulo!r}")
        return None

    if ev.get("isOnlineEvent"):
        return None

    slug = attrs.get("slug") or ""
    ev_id = event.get("id") or slug or slugify(titulo)

    start_raw = ev.get("startDate") or attrs.get("startDate") or ""
    date_str = start_raw[:10] if start_raw else ""

    # Try to extract time from startDate ISO string, e.g. "2026-07-15T07:00:00.000Z".
    # Reject midnight (00:00) — used as placeholder when no actual start time is set.
    horario_from_date: str | None = None
    if len(start_raw) > 10:
        mt = re.search(r"T(\d{2}):(\d{2})", start_raw)
        if mt:
            h, mi = int(mt.group(1)), int(mt.group(2))
            if 4 <= h <= 23:
                horario_from_date = f"{h:02d}:{mi:02d}"

    location_raw = ev.get("location") or attrs.get("location") or ""
    city, state = _parse_location(location_raw, titulo)
    if not state or state == "??":
        # When _parse_location found no UF pattern, city came from the raw string fallback.
        # Pass empty city to geo.resolve to avoid doubling the venue name in the cache key.
        geo_city = city if state else ""
        _, geo_state = _geo.resolve(location_raw or titulo, geo_city, "BR")
        state = geo_state or ""
    if not state:
        print(f"[{SOURCE_NAME}] filtrado(sem UF): {titulo!r} location={location_raw!r}")
        return None
    localizacao = ", ".join(p for p in [city, state] if p)

    distancias, horario = _distances_from_attrs(attrs, titulo)
    horario = horario or horario_from_date
    if horario is None:
        horario = _horario_from_event_page(slug)
    if horario is None:
        print(f"[{SOURCE_NAME}] pulando '{titulo}' (sem horário publicado)")
        return None

    imagem_url = None
    cover = ev.get("coverImage") or {}
    if isinstance(cover, dict):
        img_data = cover.get("data") or {}
        img_attrs = img_data.get("attributes") or img_data
        if isinstance(img_attrs, dict):
            imagem_url = img_attrs.get("url")
    if not imagem_url:
        seo = attrs.get("pageSeo") or {}
        meta_img = seo.get("metaImage") or {}
        if isinstance(meta_img, dict):
            inner = meta_img.get("data") or {}
            img_a = inner.get("attributes") or {}
            imagem_url = img_a.get("url")

    sub_cta = ev.get("subscriptionCta") or {}
    _raw_reg = sub_cta.get("url") if isinstance(sub_cta, dict) else None
    reg_url = _raw_reg if (_raw_reg and _raw_reg.startswith("http")) else None
    # Priority: explicit registration URL > slug page > generic listing.
    # Slug pages may not always resolve, but they're event-unique — using the
    # generic listing for every event would trip the shared-inscription-link test.
    link_evento = reg_url or (f"{LISTING_URL}/{slug}" if slug else LISTING_URL)

    return Corrida(
        id=f"tfsapp_{ev_id}",
        titulo=titulo,
        data_evento=date_str,
        horario=horario,  # always non-None: skip guard above ensures this
        localizacao=localizacao,
        cidade=city,
        estado=state if state != "??" else "",
        pais="BR",
        distancias=distancias,
        imagem_url=imagem_url,
        inscricoes_abertas=None,
        periodo_inscricao=None,
        fontes=[FonteInfo(
            nome=SOURCE_NAME,
            link_evento=link_evento,
            links_inscricao=[reg_url or link_evento],
            tipo="organizador",
        )],
        miss_count=0,
        first_seen_at=now,
        updated_at=now,
    )


# ---------------------------------------------------------------------------
# Playwright fallback: intercept listing page API responses
# ---------------------------------------------------------------------------

def _get_listing_events_playwright() -> list[dict]:
    """Use Playwright on /aulas-e-eventos to capture Strapi event records.

    Intercepts /api/events responses and collects all event items, clicking
    'carregar mais' up to 10 times to paginate through the listing.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(f"[{SOURCE_NAME}] Playwright não disponível")
        return []

    captured_items: list[dict] = []
    seen_ids: set = set()

    def on_response(response):
        url = response.url
        status = response.status
        ct = response.headers.get("content-type", "")
        if "json" not in ct:
            return
        if "painel-website.tfsports.com.br/api/events" not in url:
            return
        if status != 200:
            print(f"[{SOURCE_NAME}] listing API: HTTP {status} {url}")
            return
        try:
            data = response.json()
            items = data.get("data", [])
            print(f"[{SOURCE_NAME}] listing interceptado: {len(items)} itens ({url})")
            for item in items:
                item_id = item.get("id")
                if item_id not in seen_ids:
                    seen_ids.add(item_id)
                    captured_items.append(item)
        except Exception as e:
            print(f"[{SOURCE_NAME}] listing parse error: {e}")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled"],
            )
            ctx = browser.new_context(
                user_agent=_UA,
                viewport={"width": 1280, "height": 720},
                locale="pt-BR",
                extra_http_headers={"Accept-Language": "pt-BR,pt;q=0.9"},
            )
            page = ctx.new_page()
            page.add_init_script(
                "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
                "window.chrome={runtime:{}};"
            )
            page.on("response", on_response)

            page.goto(LISTING_URL, timeout=_TIMEOUT * 1000)
            try:
                page.wait_for_load_state("networkidle", timeout=20_000)
            except Exception:
                pass

            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(2_000)

            for _ in range(10):
                try:
                    btn = page.locator(
                        "button:has-text('carregar mais'), "
                        "button:has-text('Carregar mais'), "
                        "button:has-text('Ver mais'), "
                        "button:has-text('Load more')"
                    )
                    if btn.count() == 0:
                        break
                    btn.first.click()
                    page.wait_for_timeout(2_500)
                except Exception:
                    break

            browser.close()

    except Exception as e:
        print(f"[{SOURCE_NAME}] Playwright listing error: {e}")

    print(f"[{SOURCE_NAME}] Playwright listing: {len(captured_items)} eventos capturados")
    return captured_items


# ---------------------------------------------------------------------------
# Main scraper
# ---------------------------------------------------------------------------

def scrape() -> list[Corrida]:
    now = now_iso()
    today = today_iso()

    token = _get_bearer_token()
    if not token:
        print(f"[{SOURCE_NAME}] token não encontrado, tentando sem autenticação")

    api_headers: dict = {
        "User-Agent": _UA,
        "Accept": "application/json",
    }
    if token:
        api_headers["Authorization"] = f"Bearer {token}"

    # Phase 1: Direct Strapi with locale=pt-BR
    dated = _fetch_all_pages(_events_url_dated_locale(today), api_headers, "events(data,pt-BR)")
    print(f"[{SOURCE_NAME}] events(data,pt-BR): {len(dated)} brutos")

    no_date = _fetch_all_pages(_EVENTS_URL_NO_DATE_LOCALE, api_headers, "events(sem-data,pt-BR)")
    print(f"[{SOURCE_NAME}] events(sem-data,pt-BR): {len(no_date)} brutos")

    recent = _fetch_all_pages(_EVENTS_URL_RECENT_LOCALE, api_headers, "events(recentes,pt-BR)")
    print(f"[{SOURCE_NAME}] events(recentes,pt-BR): {len(recent)} brutos")

    seen_strapi_ids: set = set()
    all_strapi: list[dict] = []
    for item in dated + no_date + recent:
        item_id = item.get("id")
        if item_id not in seen_strapi_ids:
            seen_strapi_ids.add(item_id)
            all_strapi.append(item)

    print(f"[{SOURCE_NAME}] total Strapi locale=pt-BR: {len(all_strapi)} únicos")

    # Phase 2: Playwright listing page — catches events not in direct API
    listing_items = _get_listing_events_playwright()
    for item in listing_items:
        item_id = item.get("id")
        if item_id not in seen_strapi_ids:
            seen_strapi_ids.add(item_id)
            all_strapi.append(item)

    print(f"[{SOURCE_NAME}] total após merge: {len(all_strapi)}")

    # Phase 3: Parse and filter
    corridas: list[Corrida] = []
    seen_ids: set[str] = set()

    for item in all_strapi:
        c = _parse_strapi_event(item, now)
        if not c:
            continue
        if c.data_evento and c.data_evento < today:
            print(f"[{SOURCE_NAME}] filtrado(passado): {c.titulo!r} ({c.data_evento})")
            continue
        if c.id not in seen_ids:
            seen_ids.add(c.id)
            corridas.append(c)
            print(f"[{SOURCE_NAME}] adicionado: {c.titulo!r} em {c.data_evento}")

    print(f"[{SOURCE_NAME}] {len(corridas)} corridas encontradas")
    return corridas
