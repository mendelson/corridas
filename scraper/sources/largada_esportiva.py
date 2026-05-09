"""Scraper for largadaesportiva.com.br — Brazilian sports-event registration platform.

The site is a JS SPA (requires JavaScript to render). Strategy:
1. HTTP GET with render_js=True (Scrapestack executes JS before responding).
2. Extract __NEXT_DATA__ JSON if the page is Next.js.
3. Extract other embedded JSON from <script> tags.
4. Playwright with response interception to capture the underlying API call.
5. Playwright HTML-card parsing as final fallback.

Keyword filtering keeps only road-running events, excluding other sports.
"""
from __future__ import annotations

import json
import re
from bs4 import BeautifulSoup

from ..http_client import get
from ..playwright_client import get_page_html
from ..models import Corrida, Distancia, FonteInfo
from ..utils import (
    normalize_titulo, normalize_date, normalize_time,
    slugify, infer_estado, now_iso, today_iso,
    validate_image_url,
)

BASE        = "https://largadaesportiva.com.br"
SOURCE_NAME = "Largada Esportiva"

# Try multiple common event-listing paths in order
_CANDIDATE_URLS = [
    f"{BASE}/eventos",
    f"{BASE}/corridas",
    f"{BASE}/calendario",
    BASE,
]

_RUNNING_KW = re.compile(
    r"corrida|maratona|meia[\s\-]?maratona|trail[\s\-]?run|run\b|race\b|\d+\s*km?\b",
    re.IGNORECASE,
)
_NON_RUNNING_KW = re.compile(
    r"\btriathlon\b|\btriathon\b|\bironman\b|\bduathlon\b"
    r"|\baquabike\b|\baquathlon\b|\bnatação\b|\bswimrun\b"
    r"|\bciclismo\b|\bpedalada\b|\bfutebol\b"
    r"|\bjiu.?jitsu\b|\bmma\b|\bboxe\b|\bkaratê\b|\bkarate\b"
    r"|\bcaminhada\b",
    re.IGNORECASE,
)

_PT_MONTHS = {
    "janeiro": "01", "fevereiro": "02", "março": "03", "marco": "03",
    "abril": "04", "maio": "05", "junho": "06", "julho": "07",
    "agosto": "08", "setembro": "09", "outubro": "10",
    "novembro": "11", "dezembro": "12",
}

_CANONICAL = [(42.195, 41.5, 43.0), (21.097, 20.5, 21.5)]
_DATE_ISO_RE = re.compile(r"(20\d{2}-\d{2}-\d{2})")
_DMYYYY_RE   = re.compile(r"\b(\d{1,2})[/\-](\d{1,2})[/\-](20\d{2})\b")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def scrape() -> list[Corrida]:
    today = today_iso()

    # Strategy 1: HTTP with JS rendering via Scrapestack
    html, used_url = _fetch_html_http()
    if html:
        soup = BeautifulSoup(html, "lxml")

        corridas = _try_next_data(soup, today, used_url)
        if corridas:
            print(f"[{SOURCE_NAME}] {len(corridas)} corridas via __NEXT_DATA__")
            return corridas

        corridas = _try_embedded_json(soup, today, used_url)
        if corridas:
            print(f"[{SOURCE_NAME}] {len(corridas)} corridas via JSON embutido")
            return corridas

        corridas = _parse_html_cards(soup, today, used_url)
        if corridas:
            print(f"[{SOURCE_NAME}] {len(corridas)} corridas via HTML")
            return corridas

    # Strategy 2: Playwright with API-response interception
    corridas = _fetch_via_playwright(today)
    if corridas is not None:
        print(f"[{SOURCE_NAME}] {len(corridas)} corridas via Playwright")
        return corridas

    print(f"[{SOURCE_NAME}] 0 corridas encontradas")
    return []


# ---------------------------------------------------------------------------
# HTTP fetch
# ---------------------------------------------------------------------------

def _fetch_html_http() -> tuple[str | None, str]:
    for url in _CANDIDATE_URLS:
        try:
            resp = get(url, render_js=True)
            resp.raise_for_status()
            html = resp.text
            if len(html) > 2000 and "<html" in html.lower():
                print(f"[{SOURCE_NAME}] HTTP OK ({len(html)} bytes) → {url}")
                return html, url
        except Exception as e:
            print(f"[{SOURCE_NAME}] HTTP {url}: {e}")
    return None, BASE


# ---------------------------------------------------------------------------
# Strategy 1a: __NEXT_DATA__ (Next.js SSR)
# ---------------------------------------------------------------------------

def _try_next_data(soup: BeautifulSoup, today: str, page_url: str) -> list[Corrida]:
    tag = soup.find("script", id="__NEXT_DATA__")
    if not tag:
        return []
    try:
        data = json.loads(tag.string or "")
    except Exception:
        return []
    return _extract_from_json(data, today, page_url)


# ---------------------------------------------------------------------------
# Strategy 1b: other embedded JSON blobs
# ---------------------------------------------------------------------------

def _try_embedded_json(soup: BeautifulSoup, today: str, page_url: str) -> list[Corrida]:
    for script in soup.find_all("script"):
        src = script.string or ""
        # Look for window.__STATE__, window.__DATA__, window.APP_DATA, etc.
        for pattern in [
            r"window\.__(?:STATE|DATA|APP_DATA|INITIAL_STATE|PRELOADED_STATE|initialState)\s*=\s*(\{.*?\});",
            r"self\.__next_f\.push\(\[1,\s*\"(.*?)\"\]\)",
        ]:
            m = re.search(pattern, src, re.DOTALL)
            if m:
                try:
                    raw = m.group(1)
                    if raw.startswith('"'):
                        raw = raw.encode().decode("unicode_escape")
                    obj = json.loads(raw)
                    result = _extract_from_json(obj, today, page_url)
                    if result:
                        return result
                except Exception:
                    pass
        # Also try any large JSON array directly in a script tag
        if "data_evento" in src or '"startDate"' in src or '"event_date"' in src:
            m = re.search(r"(\[[\s\S]{200,}\])", src)
            if m:
                try:
                    arr = json.loads(m.group(1))
                    if isinstance(arr, list):
                        result = _extract_from_json(arr, today, page_url)
                        if result:
                            return result
                except Exception:
                    pass
    return []


# ---------------------------------------------------------------------------
# JSON parsing helpers
# ---------------------------------------------------------------------------

def _extract_from_json(obj: object, today: str, page_url: str) -> list[Corrida]:
    """Recursively find event-like dicts inside any JSON structure."""
    events = _collect_event_dicts(obj)
    corridas: list[Corrida] = []
    for ev in events:
        try:
            c = _parse_event_dict(ev, today, page_url)
            if c:
                corridas.append(c)
        except Exception:
            pass
    return corridas


def _collect_event_dicts(obj: object, depth: int = 0) -> list[dict]:
    """Collect dicts that look like event objects from a nested JSON tree."""
    if depth > 8:
        return []
    results: list[dict] = []
    if isinstance(obj, dict):
        # A dict is event-like if it has a title/name AND a date field
        has_title = any(obj.get(k) for k in (
            "titulo", "title", "nome", "name", "eventTitle", "eventName",
            "event_name", "event_title", "descricao", "description",
        ))
        has_date = any(obj.get(k) for k in (
            "data_evento", "data", "date", "startDate", "start_date",
            "eventDate", "event_date", "dataEvento", "inicio", "start",
        ))
        if has_title and has_date:
            results.append(obj)
        else:
            for v in obj.values():
                results.extend(_collect_event_dicts(v, depth + 1))
    elif isinstance(obj, list):
        for item in obj[:200]:
            results.extend(_collect_event_dicts(item, depth + 1))
    return results


def _parse_event_dict(ev: dict, today: str, page_url: str) -> Corrida | None:
    # Title
    titulo_raw = (
        ev.get("titulo") or ev.get("title") or ev.get("nome") or
        ev.get("name") or ev.get("eventTitle") or ev.get("eventName") or
        ev.get("event_name") or ev.get("event_title") or ""
    )
    titulo = normalize_titulo(titulo_raw)
    if not titulo or len(titulo) < 3:
        return None
    if not _is_running(titulo):
        return None

    # Date
    data_raw = (
        ev.get("data_evento") or ev.get("data") or ev.get("date") or
        ev.get("startDate") or ev.get("start_date") or ev.get("eventDate") or
        ev.get("event_date") or ev.get("dataEvento") or ev.get("inicio") or
        ev.get("start") or ""
    )
    data_evento = _parse_date(str(data_raw))
    if data_evento and data_evento < today:
        return None

    # Time
    horario_raw = (
        ev.get("horario") or ev.get("hora") or ev.get("time") or
        ev.get("startTime") or ev.get("start_time") or ""
    )
    horario = normalize_time(str(horario_raw)) if horario_raw else None

    # Location
    estado = (ev.get("estado") or ev.get("uf") or ev.get("state") or "").upper()
    if len(estado) != 2:
        estado = ""
    cidade = normalize_titulo(
        ev.get("cidade") or ev.get("city") or ev.get("municipio") or ""
    )
    localizacao = (
        ev.get("localizacao") or ev.get("local") or ev.get("location") or
        ev.get("endereco") or ev.get("address") or ""
    )
    if not localizacao:
        localizacao = ", ".join(filter(None, [cidade, estado]))
    if not estado:
        estado = infer_estado(localizacao, titulo) or "??"
    if not cidade:
        cidade = localizacao.split(",")[0].strip()

    # Image
    imagem_url = validate_image_url(
        ev.get("imagem") or ev.get("image") or ev.get("foto") or
        ev.get("banner") or ev.get("thumbnail") or ev.get("imagem_url") or
        ev.get("imageUrl") or ev.get("image_url")
    )

    # Link / slug
    slug = ev.get("slug") or ev.get("id") or ev.get("eventId") or ""
    link = (
        ev.get("link") or ev.get("url") or ev.get("link_evento") or
        ev.get("linkEvento") or ""
    )
    if not link and slug:
        link = f"{BASE}/evento/{slug}"
    if not link:
        link = page_url

    # Distances
    dist_raw = (
        ev.get("distancias") or ev.get("distances") or
        ev.get("percursos") or ev.get("modalidades") or []
    )
    distancias = _parse_distances_from_value(dist_raw)
    if not distancias:
        # Try extracting from text fields
        desc = " ".join(str(v) for v in [
            ev.get("descricao") or "", ev.get("description") or "",
            ev.get("regulamento") or "", titulo_raw,
        ])
        distancias = _extract_distances_text(desc)

    ev_id = f"le_{slug}" if slug and str(slug).replace("-", "").isalnum() else \
            f"le_{slugify(titulo)}_{estado.lower()}"

    now = now_iso()
    return Corrida(
        id=ev_id,
        titulo=titulo,
        data_evento=data_evento or "",
        horario=horario,
        localizacao=localizacao,
        cidade=cidade,
        estado=estado,
        distancias=distancias,
        imagem_url=imagem_url,
        inscricoes_abertas=None,
        periodo_inscricao=None,
        fontes=[FonteInfo(nome=SOURCE_NAME, link_evento=link, links_inscricao=[link])],
        miss_count=0,
        first_seen_at=now,
        updated_at=now,
    )


# ---------------------------------------------------------------------------
# Strategy 1c: HTML card parsing
# ---------------------------------------------------------------------------

def _parse_html_cards(soup: BeautifulSoup, today: str, page_url: str) -> list[Corrida]:
    cards = _find_event_cards(soup)
    if not cards:
        return []
    corridas: list[Corrida] = []
    for el in cards:
        try:
            c = _parse_card(el, today, page_url)
            if c:
                corridas.append(c)
        except Exception:
            pass
    return corridas


def _find_event_cards(soup: BeautifulSoup):
    for sel in [
        "[class*='event-card']", "[class*='EventCard']", "[class*='corrida-card']",
        "[class*='card-evento']", "[class*='evento-card']",
        "article.card", "article[class*='event']", "div[class*='event-item']",
        "li[class*='event']", "div[class*='race-card']",
        ".card", "article", "li.event",
    ]:
        els = soup.select(sel)
        if len(els) >= 2:
            return els
    return []


def _parse_card(el, today: str, page_url: str) -> Corrida | None:
    text = el.get_text(" ", strip=True)
    if not text or len(text) < 10:
        return None

    heading = el.find(["h1", "h2", "h3", "h4", "h5", "strong"])
    titulo_raw = heading.get_text(strip=True) if heading else text[:100]
    titulo = normalize_titulo(titulo_raw)
    if not titulo or len(titulo) < 3:
        return None
    if not _is_running(titulo):
        return None

    data_evento = _extract_date_text(text)
    if data_evento and data_evento < today:
        return None

    horario = normalize_time(text)

    # Location: look for city-state pattern
    estado = ""
    cidade = ""
    localizacao = ""
    loc_el = el.find(class_=re.compile(r"local|location|cidade|place|city|address", re.I))
    if loc_el:
        localizacao = loc_el.get_text(strip=True)
    if not localizacao:
        m = re.search(
            r"([A-ZÁÉÍÓÚÀÂÃÊÔÕÇ][A-Za-záéíóúàâãêôõç\s]{2,})\s*[-–,]\s*([A-Z]{2})\b",
            text,
        )
        if m:
            localizacao = m.group(0)
            cidade = m.group(1).strip()
            estado = m.group(2)
    if not estado:
        estado = infer_estado(localizacao, titulo) or "??"
    if not cidade:
        cidade = localizacao.split(",")[0].split("-")[0].strip()

    img = el.find("img")
    imagem_url = None
    if img:
        imagem_url = validate_image_url(
            img.get("src") or img.get("data-src") or img.get("data-lazy-src")
        )
        if imagem_url and imagem_url.startswith("/"):
            imagem_url = BASE + imagem_url

    link_tag = el.find("a", href=True)
    link = link_tag["href"] if link_tag else page_url
    if link.startswith("/"):
        link = BASE + link

    slug = link.rstrip("/").split("/")[-1] if link != page_url else ""
    ev_id = f"le_{slug}" if slug and slug != "" else \
            f"le_{slugify(titulo)}_{estado.lower()}"

    distancias = _extract_distances_text(text)
    now = now_iso()
    return Corrida(
        id=ev_id,
        titulo=titulo,
        data_evento=data_evento or "",
        horario=horario,
        localizacao=localizacao,
        cidade=cidade,
        estado=estado,
        distancias=distancias,
        imagem_url=imagem_url,
        inscricoes_abertas=None,
        periodo_inscricao=None,
        fontes=[FonteInfo(nome=SOURCE_NAME, link_evento=link, links_inscricao=[link])],
        miss_count=0,
        first_seen_at=now,
        updated_at=now,
    )


# ---------------------------------------------------------------------------
# Strategy 2: Playwright with network interception
# ---------------------------------------------------------------------------

_INTERCEPT_JS = """
() => {
    const results = [];
    const _origFetch = window.fetch;
    window.fetch = async function(...args) {
        const resp = await _origFetch.apply(this, args);
        const clone = resp.clone();
        const ct = clone.headers.get('content-type') || '';
        if (ct.includes('json')) {
            clone.text().then(t => results.push({url: args[0], body: t}));
        }
        return resp;
    };
    window.__interceptedRequests = results;
}
"""


def _fetch_via_playwright(today: str) -> list[Corrida] | None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None

    for url in _CANDIDATE_URLS:
        try:
            corridas = _playwright_scrape_url(url, today)
            if corridas is not None:
                return corridas
        except Exception as e:
            print(f"[{SOURCE_NAME}] Playwright {url}: {e}")
    return None


def _playwright_scrape_url(url: str, today: str) -> list[Corrida] | None:
    from playwright.sync_api import sync_playwright

    _UA = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
    _STEALTH = (
        "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
        "window.chrome={runtime:{}};"
    )

    intercepted: list[dict] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        ctx = browser.new_context(
            user_agent=_UA,
            viewport={"width": 1280, "height": 800},
            locale="pt-BR",
        )
        page = ctx.new_page()
        page.add_init_script(_STEALTH)

        # Intercept JSON API responses
        def _on_response(response):
            ct = response.headers.get("content-type", "")
            if "json" in ct and response.status < 400:
                try:
                    intercepted.append({
                        "url": response.url,
                        "body": response.json(),
                    })
                except Exception:
                    pass

        page.on("response", _on_response)
        page.goto(url, timeout=30_000)
        try:
            page.wait_for_load_state("networkidle", timeout=20_000)
        except Exception:
            pass

        html = page.content()
        browser.close()

    # Try intercepted API responses first
    for item in intercepted:
        corridas = _extract_from_json(item["body"], today, url)
        if corridas:
            print(f"[{SOURCE_NAME}] API interceptada: {item['url']}")
            return corridas

    # Fall back to rendered HTML
    if html:
        soup = BeautifulSoup(html, "lxml")
        corridas = _try_next_data(soup, today, url)
        if corridas:
            return corridas
        corridas = _parse_html_cards(soup, today, url)
        if corridas is not None:
            return corridas

    return None


# ---------------------------------------------------------------------------
# Shared utilities
# ---------------------------------------------------------------------------

def _is_running(titulo: str) -> bool:
    if _NON_RUNNING_KW.search(titulo):
        return False
    return bool(_RUNNING_KW.search(titulo))


def _parse_date(raw: str) -> str | None:
    if not raw:
        return None
    raw = raw.strip()
    m = _DATE_ISO_RE.match(raw)
    if m:
        return m.group(1)
    m = _DMYYYY_RE.search(raw)
    if m:
        return f"{m.group(3)}-{m.group(2).zfill(2)}-{m.group(1).zfill(2)}"
    m = re.search(r"(\d{1,2})\s+de\s+([a-záéíóúâêôãõç]+)\s+de\s+(20\d{2})", raw, re.I)
    if m:
        mo = _PT_MONTHS.get(m.group(2).lower())
        if mo:
            return f"{m.group(3)}-{mo}-{m.group(1).zfill(2)}"
    return normalize_date(raw)


def _extract_date_text(text: str) -> str | None:
    m = _DATE_ISO_RE.search(text)
    if m:
        return m.group(1)
    m = _DMYYYY_RE.search(text)
    if m:
        return f"{m.group(3)}-{m.group(2).zfill(2)}-{m.group(1).zfill(2)}"
    m = re.search(
        r"(\d{1,2})\s+de\s+([a-záéíóúâêôãõç]+)\s+de\s+(20\d{2})", text, re.I
    )
    if m:
        mo = _PT_MONTHS.get(m.group(2).lower())
        if mo:
            return f"{m.group(3)}-{mo}-{m.group(1).zfill(2)}"
    return None


def _parse_distances_from_value(val: object) -> list[Distancia]:
    if isinstance(val, list):
        result: list[Distancia] = []
        for item in val:
            if isinstance(item, (int, float)) and 1 <= item <= 250:
                result.append(Distancia(km=float(item), data=None, horario=None))
            elif isinstance(item, str):
                result.extend(_extract_distances_text(item))
            elif isinstance(item, dict):
                raw = item.get("km") or item.get("distancia") or item.get("distance") or ""
                result.extend(_extract_distances_text(str(raw)))
        return result
    if isinstance(val, str):
        return _extract_distances_text(val)
    return []


def _extract_distances_text(text: str) -> list[Distancia]:
    _INTERVAL = re.compile(
        r"a cada \d+(?:[.,]\d+)?\s*km?\b|cada \d+(?:[.,]\d+)?\s*km?\b"
        r"|\d+(?:[.,]\d+)?\s*km?\s*(?:de hidrat|de água|de abastec)",
        re.IGNORECASE,
    )
    text = _INTERVAL.sub(" ", text)
    nums = re.findall(r"\b(\d+(?:[.,]\d+)?)\s*k(?:m)?\b", text, re.IGNORECASE)
    seen: set[float] = set()
    result: list[Distancia] = []
    for raw in nums:
        try:
            km = float(raw.replace(",", "."))
        except ValueError:
            continue
        if not (1 <= km <= 250):
            continue
        for canon, lo, hi in _CANONICAL:
            if lo <= km <= hi:
                km = canon
                break
        if km not in seen:
            seen.add(km)
            result.append(Distancia(km=km, data=None, horario=None))
    return result
