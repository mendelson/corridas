"""TF Sports App scraper — captures /aulas-e-eventos events via Next.js ISR.

The TF Sports website uses Next.js SSG with fallback:true for event pages at
/aulas-e-eventos/{slug}. When a page is first requested, the server calls
api.prod.tfsports.com.br (mobile API) via getStaticProps using server-stored
credentials, then returns the full event pageProps. This scraper triggers that
server-side rendering by requesting the /_next/data/ endpoint and intercepting
the JSON response — no mobile API credentials needed.

Phase 1: Get event slugs from sitemap + listing page (Playwright for dynamic slugs)
Phase 2: For each slug, fetch /_next/data/{buildId}/aulas-e-eventos/{slug}.json
         (direct HTTP first, Playwright fallback)
Phase 3: Parse event data, filter running events, build Corrida objects
"""
from __future__ import annotations
import json
import re

import httpx
from bs4 import BeautifulSoup

from ..models import Corrida, Distancia, FonteInfo
from ..utils import normalize_titulo, slugify, now_iso, today_iso
from ..http_client import get as _http_get, HEADERS
from .. import geo as _geo

SOURCE_NAME = "TF Sports App"
BASE = "https://www.tfsports.com.br"
LISTING_URL = f"{BASE}/aulas-e-eventos"

_UA = HEADERS["User-Agent"]
_TIMEOUT = 30

_RUNNING_AREAS = {"running", "corrida", "trail", "trilha"}
_RUNNING_TITLE_RE = re.compile(
    r"\b(runn?(?:ing|er)?|corrida|trail|trilha|maratona|meia.maratona|5k|10k)\b",
    re.IGNORECASE,
)
_NON_RUNNING_RE = re.compile(
    r"\b(yoga|pilates|beach.tennis|along(?:amento)?|medita[cç]|funcional"
    r"|dan[cç]a|natac|swim|ciclismo|surf)\b",
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


def _parse_location(location: str | None) -> tuple[str, str]:
    """Return (city, state) from a location string."""
    if not location:
        return "", ""
    parts = [p.strip() for p in location.split(",")]
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
    if not city and parts:
        city = parts[0].strip()
    return city, state


# ---------------------------------------------------------------------------
# Event filtering
# ---------------------------------------------------------------------------

def _is_running_event(attrs: dict, ev: dict) -> bool:
    """Return True when the event appears to be a running event."""
    # Check area slug if present
    area = attrs.get("area") or ev.get("area") or {}
    if isinstance(area, dict):
        area_inner = area.get("data") or area
        area_attrs = area_inner.get("attributes") or area_inner
        area_slug = (area_attrs.get("slug") or area_attrs.get("name") or "").lower()
        if area_slug:
            if any(kw in area_slug for kw in _RUNNING_AREAS):
                return True
            # Has a different area — not a running event
            return False

    title = attrs.get("title") or ev.get("eventName") or attrs.get("name") or ""
    if _NON_RUNNING_RE.search(title):
        return False
    return bool(_RUNNING_TITLE_RE.search(title))


# ---------------------------------------------------------------------------
# Distance extraction
# ---------------------------------------------------------------------------

def _distances_from_modalities(modalities_raw) -> list[Distancia]:
    """Extract distances from the modalities data structure."""
    items: list[dict] = []
    if isinstance(modalities_raw, dict):
        items = modalities_raw.get("modalitiesItems") or []
    elif isinstance(modalities_raw, list):
        items = modalities_raw

    seen: set[float] = set()
    result: list[Distancia] = []
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
                result.append(Distancia(km=km, data=None, horario=None))
        except ValueError:
            pass

    return sorted(result, key=lambda d: float(d.km) if isinstance(d.km, (int, float)) else 999)


# ---------------------------------------------------------------------------
# Build ID
# ---------------------------------------------------------------------------

def _get_build_id() -> str | None:
    """Extract current Next.js buildId from the main page."""
    try:
        resp = _http_get(BASE + "/", source=SOURCE_NAME, timeout=_TIMEOUT)
        if resp.status_code != 200:
            return None
        m = re.search(r'"buildId"\s*:\s*"([^"]+)"', resp.text)
        return m.group(1) if m else None
    except Exception as e:
        print(f"[{SOURCE_NAME}] erro ao obter buildId: {e}")
        return None


# ---------------------------------------------------------------------------
# Slug discovery
# ---------------------------------------------------------------------------

def _get_sitemap_slugs() -> list[str]:
    """Return /aulas-e-eventos/ slugs from sitemap.xml."""
    try:
        resp = _http_get(f"{BASE}/sitemap.xml", source=SOURCE_NAME, timeout=_TIMEOUT)
        if resp.status_code != 200:
            return []
        slugs = re.findall(
            r"<loc>https://www\.tfsports\.com\.br/aulas-e-eventos/([^<]+)</loc>",
            resp.text,
        )
        return [s.strip() for s in slugs if s.strip()]
    except Exception as e:
        print(f"[{SOURCE_NAME}] erro ao ler sitemap: {e}")
        return []


def _get_listing_slugs_playwright() -> list[str]:
    """Use Playwright on the listing page to discover event slugs.

    The blocks.archive-events component loads events client-side. We intercept
    all JSON responses and look for slugs, and also parse anchor links in the
    rendered HTML that point to /aulas-e-eventos/ paths.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(f"[{SOURCE_NAME}] Playwright não disponível")
        return []

    slugs: list[str] = []
    api_calls: list[str] = []

    def on_response(response):
        url = response.url
        status = response.status
        ct = response.headers.get("content-type", "")

        # Log all non-static calls for debugging
        if not any(ext in url for ext in (".js", ".css", ".png", ".jpg", ".svg", ".ico", ".woff")):
            api_calls.append(f"  {status} {url}")

        # Try to extract slugs from any JSON response
        if "json" in ct and status == 200:
            try:
                data = response.json()
                _extract_slugs_recursive(data, slugs)
            except Exception:
                pass

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

            # Scroll to trigger lazy loading
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(2_000)

            # Click "carregar mais" button up to 5 times
            for _ in range(5):
                try:
                    btn = page.locator(
                        "button:has-text('carregar mais'), "
                        "button:has-text('Carregar mais'), "
                        "button:has-text('Ver mais')"
                    )
                    if btn.count() == 0:
                        break
                    btn.first.click()
                    page.wait_for_timeout(2_000)
                except Exception:
                    break

            html = page.content()
            browser.close()

    except Exception as e:
        print(f"[{SOURCE_NAME}] Playwright listing error: {e}")
        html = ""

    print(f"[{SOURCE_NAME}] API calls from listing page:")
    for r in api_calls[:30]:
        print(r)

    # Also parse anchor links from rendered HTML
    if html:
        for m in re.finditer(
            r'href=["\'](?:/aulas-e-eventos/)([^"\'?#/]+)["\']',
            html,
        ):
            s = m.group(1).strip()
            if s and s not in slugs:
                slugs.append(s)

    print(f"[{SOURCE_NAME}] slugs descobertos via listing: {slugs}")
    return slugs


def _extract_slugs_recursive(data, slugs: list[str]) -> None:
    """Recursively search JSON for event slugs."""
    if isinstance(data, dict):
        slug = data.get("slug")
        if (
            isinstance(slug, str)
            and slug
            and slug not in slugs
            and re.match(r"^[a-z0-9][a-z0-9-]*$", slug)
            and len(slug) > 4
        ):
            slugs.append(slug)
        for v in data.values():
            _extract_slugs_recursive(v, slugs)
    elif isinstance(data, list):
        for item in data:
            _extract_slugs_recursive(item, slugs)


# ---------------------------------------------------------------------------
# Event page data fetching
# ---------------------------------------------------------------------------

def _fetch_next_data_direct(slug: str, build_id: str) -> dict | None:
    """Fetch /_next/data/{buildId}/aulas-e-eventos/{slug}.json directly.

    The Next.js server's getStaticProps calls api.prod.tfsports.com.br using
    server-stored credentials and returns full event pageProps as JSON.
    Adding x-nextjs-data header marks it as an ISR data request.
    """
    url = f"{BASE}/_next/data/{build_id}/aulas-e-eventos/{slug}.json"
    headers = {**HEADERS, "x-nextjs-data": "1", "Accept": "application/json"}
    try:
        resp = httpx.get(url, headers=headers, timeout=_TIMEOUT, follow_redirects=True)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, dict) and "pageProps" in data:
                return data["pageProps"]
        print(f"[{SOURCE_NAME}] _next/data direto: HTTP {resp.status_code} para {slug}")
    except Exception as e:
        print(f"[{SOURCE_NAME}] _next/data erro para {slug}: {e}")
    return None


def _fetch_next_data_playwright(slug: str) -> dict | None:
    """Visit event page with Playwright and capture the /_next/data/ response.

    Playwright triggers the ISR data fetch (the page JS requests _next/data when
    isFallback=true) and we intercept the resulting JSON response.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None

    captured: dict | None = None

    def on_response(response):
        nonlocal captured
        url = response.url
        if "/_next/data/" in url and "aulas-e-eventos" in url:
            try:
                data = response.json()
                if isinstance(data, dict) and "pageProps" in data:
                    captured = data["pageProps"]
                    print(f"[{SOURCE_NAME}] _next/data capturado para {slug}")
            except Exception:
                pass
        # Log other relevant calls
        if not any(ext in url for ext in (".js", ".css", ".png", ".jpg", ".svg")):
            if "tfsports" in url or "/_next/" in url:
                print(f"[{SOURCE_NAME}]   {response.status} {url}")

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
            )
            page = ctx.new_page()
            page.add_init_script(
                "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
                "window.chrome={runtime:{}};"
            )
            page.on("response", on_response)

            page.goto(f"{LISTING_URL}/{slug}", timeout=_TIMEOUT * 1000)
            try:
                page.wait_for_load_state("networkidle", timeout=20_000)
            except Exception:
                pass
            # Extra time for ISR to complete
            page.wait_for_timeout(5_000)

            browser.close()
    except Exception as e:
        print(f"[{SOURCE_NAME}] Playwright event error for {slug}: {e}")

    return captured


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def _parse_page_props(props: dict, slug: str, now: str) -> Corrida | None:
    """Parse event data from Next.js pageProps into a Corrida."""
    page_data = props.get("pageData") or {}
    attrs = page_data.get("attributes") or page_data

    title = normalize_titulo(
        attrs.get("title") or attrs.get("name") or ""
    )
    if not title:
        return None

    # eventData sub-object (contains location, date, modalities, etc.)
    ev = attrs.get("eventData") or {}

    if not _is_running_event(attrs, ev):
        print(f"[{SOURCE_NAME}] filtrado(tipo): {title!r}")
        return None

    if ev.get("isOnlineEvent"):
        print(f"[{SOURCE_NAME}] filtrado(online): {title!r}")
        return None

    date_str = (
        ev.get("startDate") or ev.get("date") or
        attrs.get("startDate") or attrs.get("date") or ""
    )

    location_raw = ev.get("location") or attrs.get("location") or ""
    city, state = _parse_location(location_raw)
    if not state:
        _, state = _geo.resolve(location_raw, city, "BR")
    localizacao = ", ".join(p for p in [city, state] if p)

    distancias = _distances_from_modalities(ev.get("modalities") or ev.get("modalitiesItems") or [])
    if not distancias:
        # Fall back to title keyword extraction
        for m in re.finditer(r"\b(\d+(?:[.,]\d+)?)\s*[kK][mM]?\b", title):
            try:
                km = float(m.group(1).replace(",", "."))
                if 3 <= km <= 100:
                    distancias.append(Distancia(km=km, data=None, horario=None))
            except ValueError:
                pass
    if not distancias:
        distancias = list(_TF_DEFAULT_DISTANCES)

    # Cover image
    cover = ev.get("coverImage") or {}
    imagem_url = None
    if isinstance(cover, dict):
        img_data = cover.get("data") or {}
        img_attrs = img_data.get("attributes") or img_data
        if isinstance(img_attrs, dict):
            imagem_url = img_attrs.get("url")

    # Registration link
    sub_cta = ev.get("subscriptionCta") or {}
    reg_url = sub_cta.get("url") if isinstance(sub_cta, dict) else None
    link_evento = f"{LISTING_URL}/{slug}"

    ev_id = page_data.get("id") or attrs.get("id") or slug or slugify(title)

    return Corrida(
        id=f"tfsapp_{ev_id}",
        titulo=title,
        data_evento=date_str,
        horario=None,
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
        )],
        miss_count=0,
        first_seen_at=now,
        updated_at=now,
    )


# ---------------------------------------------------------------------------
# Main scraper
# ---------------------------------------------------------------------------

def scrape() -> list[Corrida]:
    now = now_iso()
    today = today_iso()

    # --- Phase 1: discover event slugs ---
    sitemap_slugs = _get_sitemap_slugs()
    print(f"[{SOURCE_NAME}] sitemap: {len(sitemap_slugs)} slugs: {sitemap_slugs}")

    listing_slugs = _get_listing_slugs_playwright()

    all_slugs: list[str] = list(dict.fromkeys(sitemap_slugs + listing_slugs))
    print(f"[{SOURCE_NAME}] total: {len(all_slugs)} slugs únicos")

    # --- Phase 2: fetch event details ---
    build_id = _get_build_id()
    print(f"[{SOURCE_NAME}] buildId: {build_id!r}")

    corridas: list[Corrida] = []
    seen_ids: set[str] = set()

    for slug in all_slugs:
        props: dict | None = None

        # Try direct HTTP first (fast, no browser overhead)
        if build_id:
            props = _fetch_next_data_direct(slug, build_id)

        # Fall back to Playwright (triggers ISR via browser JS)
        if not props:
            print(f"[{SOURCE_NAME}] usando Playwright para {slug}")
            props = _fetch_next_data_playwright(slug)

        if not props:
            print(f"[{SOURCE_NAME}] sem dados para {slug}")
            continue

        c = _parse_page_props(props, slug, now)
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
