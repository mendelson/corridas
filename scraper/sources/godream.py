"""Scraper for godream.com.br — Brazilian running events platform."""
from __future__ import annotations
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

from bs4 import BeautifulSoup

from ..http_client import get
from ..models import Corrida, Distancia, FonteInfo
from ..utils import (
    normalize_titulo, normalize_date, slugify,
    infer_estado, normalize_cidade, now_iso, today_iso,
)

BASE         = "https://www.godream.com.br"
CALENDAR_URL = f"{BASE}/corrida-de-rua"
SOURCE_NAME  = "GoDream"

_CANONICAL = [(42.195, 41.5, 43.0), (21.097, 20.5, 21.5)]
_INTERVAL_RE = re.compile(
    r"a cada \d+(?:[.,]\d+)?\s*k(?:m)?\b"
    r"|cada \d+(?:[.,]\d+)?\s*k(?:m)?\b"
    r"|\d+(?:[.,]\d+)?\s*k(?:m)?\s*(?:de hidrat|de água|de abastec)",
    re.IGNORECASE,
)

_NON_RUNNING_KW = [
    "triathlon", "triathon", "ironman", "duathlon",
    "natação", "natacao", "swimrun", "ciclismo", "bike", "pedalada",
    "caminhada", "trekking", "track and field", "atletismo",
]

_PT_MONTHS = {
    "janeiro": "01", "fevereiro": "02", "março": "03", "marco": "03",
    "abril": "04", "maio": "05", "junho": "06", "julho": "07",
    "agosto": "08", "setembro": "09", "outubro": "10",
    "novembro": "11", "dezembro": "12",
}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def scrape() -> list[Corrida]:
    today = today_iso()
    soup, via_playwright = _fetch_soup()
    if soup is None:
        return []

    # Strategy 1: __NEXT_DATA__ JSON (Next.js SSR — most complete data)
    corridas = _parse_next_data(soup, today)
    if corridas:
        print(f"[{SOURCE_NAME}] {len(corridas)} corridas (via __NEXT_DATA__)")
        return corridas

    if via_playwright:
        _debug_playwright_page(soup)

    # Strategy 2: Parse HTML event cards
    corridas = _parse_html_cards(soup, today)
    print(f"[{SOURCE_NAME}] {len(corridas)} corridas encontradas")
    return corridas


def _fetch_soup() -> "tuple[BeautifulSoup | None, bool]":
    """Fetch calendar via HTTP, falling back to Playwright. Returns (soup, via_playwright)."""
    try:
        resp = get(CALENDAR_URL, source=SOURCE_NAME)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "lxml"), False
    except Exception as e:
        print(f"[{SOURCE_NAME}] HTTP falhou ({e}), tentando Playwright...")

    html = _fetch_via_playwright()
    if html:
        print(f"[{SOURCE_NAME}] Playwright: {len(html)} bytes")
        return BeautifulSoup(html, "lxml"), True

    print(f"[{SOURCE_NAME}] todas as estratégias falharam")
    return None, False


def _fetch_via_playwright() -> "str | None":
    """Navigate GoDream via Playwright, intercepting API calls to capture event data."""
    try:
        from playwright.sync_api import sync_playwright
        from ..playwright_client import _STEALTH_JS, _USER_AGENT
    except ImportError:
        return None

    captured: list[tuple[str, str]] = []  # (url, body)

    def _handle_response(response):
        url = response.url
        ct = (response.headers.get("content-type") or "").lower()
        if "json" not in ct:
            return
        try:
            body = response.body()
            if body and body[0:1] in (b"{", b"[") and len(body) > 200:
                captured.append((url, body.decode("utf-8", errors="replace")))
                print(f"[{SOURCE_NAME}] JSON interceptado: {url} ({len(body)} bytes)")
        except Exception:
            pass

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled"],
            )
            ctx = browser.new_context(
                user_agent=_USER_AGENT,
                viewport={"width": 1280, "height": 720},
                locale="pt-BR",
                extra_http_headers={"Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8"},
            )
            page = ctx.new_page()
            page.add_init_script(_STEALTH_JS)
            page.on("response", _handle_response)

            # Navigate to homepage — API calls will be intercepted
            print(f"[{SOURCE_NAME}] Playwright navegando para homepage: {BASE}")
            page.goto(BASE, timeout=30000)
            try:
                page.wait_for_load_state("networkidle", timeout=20000)
            except Exception:
                pass

            # Scroll to trigger lazy-loaded content
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(2000)

            html = page.content()
            browser.close()

        # Process captured JSONs: parse event detail pages individually,
        # and try list pages for bulk event data
        if captured:
            print(f"[{SOURCE_NAME}] {len(captured)} respostas JSON capturadas")
            all_events: list[dict] = []
            for url, body in captured:
                try:
                    data = json.loads(body)
                except Exception:
                    continue
                if '/evento/' in url:
                    # GoDream event detail page: pageProps.event has title, eventAppointment, address
                    ev = _parse_godream_event_json(data)
                    if ev:
                        name = ev.get("title", "?")
                        print(f"[{SOURCE_NAME}] evento extraído: {name}")
                        all_events.append(ev)
                    else:
                        slug = url.split('/')[-1].split('?')[0]
                        print(f"[{SOURCE_NAME}] falhou ao parsear evento: {slug}")
                elif 'index.json' in url:
                    # index.json: pageProps.events.content = list of upcoming events
                    page_props = data.get("pageProps") or {}
                    content = (page_props.get("events") or {}).get("content") or []
                    if content:
                        parsed = [_parse_godream_index_item(c) for c in content]
                        found = [e for e in parsed if e]
                        print(f"[{SOURCE_NAME}] index.json: {len(content)} items → {len(found)} eventos")
                        all_events.extend(found)
                    else:
                        print(f"[{SOURCE_NAME}] index.json sem events.content — keys: {list((data.get('pageProps') or {}).keys())}")
                else:
                    # Possible list page
                    events = _find_events_in_json(data)
                    if events:
                        print(f"[{SOURCE_NAME}] {len(events)} eventos via lista: {url.split('/')[-1].split('?')[0]}")
                        all_events.extend(events)

            if all_events:
                print(f"[{SOURCE_NAME}] total: {len(all_events)} eventos nos JSONs capturados")
                synthetic = (
                    f'<html><body>'
                    f'<script id="__NEXT_DATA__" type="application/json">'
                    f'{{"props":{{"pageProps":{{"data":{json.dumps(all_events)}}}}}}}'
                    f'</script></body></html>'
                )
                return synthetic

        return html
    except Exception as e:
        print(f"[{SOURCE_NAME}] Playwright falhou: {e}")
        return None


def _parse_godream_event_json(data: dict) -> dict | None:
    """Extract a normalised event dict from a GoDream /_next/data/evento/*.json page.

    GoDream's event structure:
      props.pageProps.event  → { title, slug, eventAppointment, address, coverImage, ... }
    """
    try:
        # /_next/data/ API returns { "pageProps": {...} } directly (no "props" wrapper)
        # __NEXT_DATA__ in HTML returns { "props": { "pageProps": {...} } }
        props = (
            data.get("pageProps")
            or data.get("props", {}).get("pageProps")
            or {}
        )
        ev = props.get("event")
        if not ev or not isinstance(ev, dict):
            print(f"[{SOURCE_NAME}] event não encontrado — props keys: {list(props.keys())[:8]}")
            return None

        title = ev.get("title") or ev.get("name")
        if not title:
            return None

        # Date: inside eventAppointment (may be a dict or list of dicts)
        appt = ev.get("eventAppointment") or {}
        if isinstance(appt, list):
            appt = appt[0] if appt else {}
        date_raw = None
        for k in ("startDate", "start_date", "date", "data", "dtInicio", "startAt", "beginAt"):
            v = appt.get(k)
            if v:
                date_raw = str(v)
                break
        if not date_raw:
            # Fallback: look for date keys in the event itself
            for k in ("startDate", "start_date", "date", "data", "dtInicio"):
                v = ev.get(k)
                if v:
                    date_raw = str(v)
                    break

        if not date_raw:
            tickets = ev.get("tickets") or []
            if isinstance(tickets, list) and tickets:
                t0 = tickets[0] if isinstance(tickets[0], dict) else {}
                batch = t0.get("activeBatch") or {}
                print(f"[{SOURCE_NAME}] tickets[0].activeBatch: {str(batch)[:300]}")
                stocks = t0.get("stocks") or []
                if isinstance(stocks, list) and stocks:
                    print(f"[{SOURCE_NAME}] tickets[0].stocks[0]: {str(stocks[0])[:300]}")
            print(f"[{SOURCE_NAME}] sem data encontrada para evento '{ev.get('title')}'")
            return None

        date = normalize_date(date_raw)
        if not date:
            return None

        # Address — GoDream nests city as {name, state:{acronym}}
        addr = ev.get("address") or ev.get("eventAddress") or {}
        if isinstance(addr, list):
            addr = addr[0] if addr else {}
        city_raw = addr.get("city") or addr.get("cidade") or {}
        if isinstance(city_raw, dict):
            city  = (city_raw.get("name") or "").strip()
            state_raw = city_raw.get("state") or {}
            state = (state_raw.get("acronym") or state_raw.get("uf") or "").strip().upper()
        else:
            city  = str(city_raw).strip()
            state = (addr.get("state") or addr.get("uf") or "").strip().upper()

        # Image
        img = ev.get("coverImage") or ev.get("logoImage")
        if isinstance(img, dict):
            img = img.get("url") or img.get("src") or img.get("path")
        image_url = img if isinstance(img, str) else None

        slug = ev.get("slug") or ""
        link = f"{BASE}/evento/{slug}" if slug else BASE

        return {
            "title":  title,
            "date":   date,
            "city":   city,
            "state":  state,
            "url":    link,
            "image":  image_url,
            "slug":   slug,
        }
    except Exception as exc:
        print(f"[{SOURCE_NAME}] _parse_godream_event_json erro: {exc}")
        return None


def _parse_godream_index_item(item: dict) -> dict | None:
    """Extract a normalised event dict from a GoDream index.json events.content item."""
    try:
        title = item.get("title") or item.get("name") or item.get("titulo")
        if not title:
            return None

        # Try all common date field names (camelCase and snake_case)
        date_raw = None
        for k in ("startDate", "start_date", "date", "data", "eventDate",
                  "event_date", "dtInicio", "dt_inicio", "beginAt", "begin_at",
                  "startAt", "start_at", "dataEvento"):
            v = item.get(k)
            if v:
                date_raw = str(v)
                break

        # Nested appointment object
        if not date_raw:
            appt = item.get("eventAppointment") or item.get("appointment") or {}
            if isinstance(appt, list):
                appt = appt[0] if appt else {}
            if isinstance(appt, dict):
                for k in ("startDate", "start_date", "date", "data", "startAt"):
                    v = appt.get(k)
                    if v:
                        date_raw = str(v)
                        break

        date = normalize_date(date_raw) if date_raw else None
        if not date:
            print(f"[{SOURCE_NAME}] item sem data — slug={item.get('slug')}, keys={list(item.keys())}")
            return None

        # Address — GoDream nests city as {name, state:{acronym}}
        addr = item.get("address") or item.get("eventAddress") or {}
        if isinstance(addr, list):
            addr = addr[0] if addr else {}
        city_raw = (addr.get("city") or addr.get("cidade")) if isinstance(addr, dict) else None
        if isinstance(city_raw, dict):
            city = (city_raw.get("name") or "").strip()
            state_d = city_raw.get("state") or {}
            state = ((state_d.get("acronym") or state_d.get("uf") or "").strip().upper()
                     if isinstance(state_d, dict) else str(state_d).strip().upper())
        elif isinstance(city_raw, str):
            city = city_raw.strip()
            state_raw = (addr.get("state") or addr.get("uf")) if isinstance(addr, dict) else ""
            state = (state_raw.get("acronym") or "").strip().upper() if isinstance(state_raw, dict) else str(state_raw or "").strip().upper()
        else:
            city = str(item.get("city") or item.get("cidade") or "").strip()
            state = str(item.get("state") or item.get("estado") or item.get("uf") or "").strip().upper()

        img = item.get("coverImage") or item.get("image") or item.get("thumbnail")
        if isinstance(img, dict):
            img = img.get("url") or img.get("src") or img.get("path")
        image_url = img if isinstance(img, str) else None

        slug = str(item.get("slug") or "")
        link = f"{BASE}/evento/{slug}" if slug else BASE

        return {
            "title":  str(title),
            "date":   date,
            "city":   city,
            "state":  state,
            "url":    link,
            "image":  image_url,
            "slug":   slug,
        }
    except Exception as exc:
        print(f"[{SOURCE_NAME}] _parse_godream_index_item erro: {exc}")
        return None


def _debug_playwright_page(soup: BeautifulSoup) -> None:
    title = soup.find("title")
    print(f"[{SOURCE_NAME}] page title: {title.get_text(strip=True) if title else '(none)'}")
    text = soup.get_text(" ", strip=True)[:500]
    print(f"[{SOURCE_NAME}] texto inicial: {text}")


# ---------------------------------------------------------------------------
# Strategy 1: Next.js __NEXT_DATA__
# ---------------------------------------------------------------------------

def _parse_next_data(soup: BeautifulSoup, today: str) -> list[Corrida]:
    tag = soup.find("script", id="__NEXT_DATA__")
    if not tag or not tag.string:
        return []
    try:
        data = json.loads(tag.string)
    except json.JSONDecodeError:
        return []

    events = _find_events_in_json(data)
    if not events:
        return []

    corridas: list[Corrida] = []
    for ev in events:
        try:
            corrida = _parse_json_event(ev, today)
            if corrida:
                corridas.append(corrida)
        except Exception as e:
            print(f"[{SOURCE_NAME}] erro ao parsear evento JSON: {e}")

    return corridas


def _find_events_in_json(obj, _depth: int = 0) -> list[dict]:
    """Recursively search for an array of event-like dicts in the JSON tree."""
    if _depth > 8:
        return []

    if isinstance(obj, list) and obj and isinstance(obj[0], dict):
        # Heuristic: the list of events has dicts with at least title/date/city
        if any(_looks_like_event(item) for item in obj[:3]):
            return obj

    if isinstance(obj, dict):
        # Check well-known keys first
        for key in ("events", "eventos", "corridas", "items", "data", "results",
                    "races", "content", "list", "records"):
            val = obj.get(key)
            if isinstance(val, list) and val and isinstance(val[0], dict):
                if any(_looks_like_event(item) for item in val[:3]):
                    return val
        # Recurse into values
        for val in obj.values():
            result = _find_events_in_json(val, _depth + 1)
            if result:
                return result

    return []


def _looks_like_event(obj: dict) -> bool:
    """True if the dict has fields typical of a running event."""
    keys_lower = {k.lower() for k in obj}
    has_title = any(k in keys_lower for k in ("title", "titulo", "nome", "name", "event_name"))
    has_date  = any(k in keys_lower for k in ("date", "data", "data_evento", "dt_inicio", "start_date", "event_date"))
    return has_title and has_date


def _parse_json_event(ev: dict, today: str) -> Corrida | None:
    # Resolve field names flexibly
    titulo_raw = (
        ev.get("title") or ev.get("titulo") or ev.get("nome") or ev.get("name") or
        ev.get("event_name") or ev.get("eventName") or ""
    )
    titulo = normalize_titulo(titulo_raw)
    if not titulo or len(titulo) < 3:
        return None

    titulo_lower = titulo.lower()
    if any(kw in titulo_lower for kw in _NON_RUNNING_KW):
        return None

    # Date
    date_raw = (
        ev.get("date") or ev.get("data") or ev.get("data_evento") or
        ev.get("dtInicio") or ev.get("dt_inicio") or ev.get("startDate") or
        ev.get("start_date") or ev.get("eventDate") or ev.get("event_date") or ""
    )
    data_evento = normalize_date(str(date_raw)) if date_raw else None
    if not data_evento or data_evento < today:
        return None

    # Location
    estado_raw = (
        ev.get("state") or ev.get("estado") or ev.get("uf") or
        ev.get("estadoAbreviacao") or ev.get("state_abbr") or ""
    ).strip().upper()
    cidade_raw = (
        ev.get("city") or ev.get("cidade") or ev.get("localidade") or
        ev.get("cityName") or ev.get("city_name") or ""
    ).strip()
    localizacao_raw = (
        ev.get("location") or ev.get("localizacao") or ev.get("address") or
        ev.get("endereco") or ""
    ).strip()

    # Infer estado if not explicit
    if not estado_raw or len(estado_raw) != 2:
        estado_raw = infer_estado(localizacao_raw or cidade_raw, titulo) or "??"

    cidade = normalize_cidade(cidade_raw) if cidade_raw else ""
    localizacao = localizacao_raw or (f"{cidade}, {estado_raw}" if cidade else estado_raw)

    # Distances
    dist_raw = (
        ev.get("distances") or ev.get("distancias") or ev.get("percursos") or
        ev.get("modalities") or ev.get("modalidades") or []
    )
    distancias = _parse_json_distances(dist_raw)
    if not distancias:
        distancias = _distances_from_title(titulo_lower)

    # Inscription status
    status_raw = str(ev.get("status") or ev.get("inscricoesAbertas") or
                     ev.get("is_open") or ev.get("isOpen") or "").lower()
    if ev.get("isSoldOut") or ev.get("is_sold_out"):
        inscricoes_abertas: bool | None = False
    elif any(kw in status_raw for kw in ("encerrad", "esgotad", "fechad", "closed", "sold")):
        inscricoes_abertas = False
    elif any(kw in status_raw for kw in ("aberto", "aberta", "open", "true")):
        inscricoes_abertas = True
    else:
        inscricoes_abertas = None

    # Event URL / registration link
    event_id = str(ev.get("id") or ev.get("eventId") or ev.get("event_id") or "")
    slug_raw  = str(ev.get("slug") or ev.get("url") or ev.get("uri") or "")
    link = _build_event_link(event_id, slug_raw, titulo)

    # Image
    imagem_url = (
        ev.get("imageUrl") or ev.get("image") or ev.get("imagem") or
        ev.get("foto") or ev.get("thumbnail") or ev.get("image_url") or
        ev.get("logoImageSource") or ev.get("cover") or None
    )
    if isinstance(imagem_url, str) and imagem_url.startswith("/"):
        imagem_url = BASE + imagem_url

    now = now_iso()
    fonte = FonteInfo(
        nome=SOURCE_NAME,
        link_evento=link,
        links_inscricao=[link] if inscricoes_abertas is not False else [],
    )

    return Corrida(
        id=f"gd_{event_id}" if event_id else f"{slugify(titulo)}_{estado_raw.lower()}_{today}",
        titulo=titulo,
        data_evento=data_evento,
        horario=_parse_horario(ev),
        localizacao=localizacao,
        cidade=cidade,
        estado=estado_raw or "??",
        distancias=distancias,
        imagem_url=imagem_url or None,
        inscricoes_abertas=inscricoes_abertas,
        periodo_inscricao=None,
        fontes=[fonte],
        miss_count=0,
        first_seen_at=now,
        updated_at=now,
    )


def _parse_horario(ev: dict) -> str | None:
    raw = str(ev.get("horario") or ev.get("startTime") or ev.get("start_time") or
              ev.get("time") or ev.get("hora") or "")
    if not raw:
        return None
    m = re.search(r"(\d{1,2})[h:](\d{2})", raw)
    if m:
        return f"{int(m.group(1)):02d}:{m.group(2)}"
    return None


def _parse_json_distances(raw) -> list[Distancia]:
    if not raw:
        return []
    seen: set[float] = set()
    result: list[Distancia] = []

    items = raw if isinstance(raw, list) else [raw]
    for item in items:
        km: float | None = None
        if isinstance(item, (int, float)):
            km = float(item)
        elif isinstance(item, str):
            km = _parse_km(item)
        elif isinstance(item, dict):
            for key in ("km", "distance", "distancia", "name", "nome", "label"):
                val = item.get(key)
                if val is not None:
                    km = _parse_km(str(val))
                    if km:
                        break
        if km and km not in seen and 1 <= km <= 200:
            for canon, lo, hi in _CANONICAL:
                if lo <= km <= hi:
                    km = canon
                    break
            seen.add(km)
            result.append(Distancia(km=km, data=None, horario=None))

    return sorted(result, key=lambda d: d.km if isinstance(d.km, (int, float)) else 999)


def _parse_km(s: str) -> float | None:
    s = s.strip().lower()
    if "meia" in s or "half" in s:
        return 21.097
    if re.search(r"(?<!meia )\bmaratona\b|(?<!half )marathon", s):
        return 42.195
    m = re.match(r"(\d+(?:[.,]\d+)?)\s*k(?:m)?", s)
    if m:
        km = float(m.group(1).replace(",", "."))
        return km if 1 <= km <= 200 else None
    return None


def _build_event_link(event_id: str, slug_raw: str, titulo: str) -> str:
    # Absolute URL already
    if slug_raw.startswith("http"):
        return slug_raw
    # Relative path on godream
    if slug_raw.startswith("/"):
        return BASE + slug_raw
    # Slug without leading slash
    if slug_raw:
        return f"{BASE}/evento/{slug_raw}"
    # Build from ID + title slug
    if event_id:
        return f"{BASE}/evento/{slugify(titulo)}-{event_id}"
    return CALENDAR_URL


# ---------------------------------------------------------------------------
# Strategy 2: HTML card parsing
# ---------------------------------------------------------------------------

def _parse_html_cards(soup: BeautifulSoup, today: str) -> list[Corrida]:
    cards = _find_cards(soup)
    if not cards:
        return []

    corridas: list[Corrida] = []
    for card in cards:
        try:
            corrida = _parse_card(card, today)
            if corrida:
                corridas.append(corrida)
        except Exception as e:
            print(f"[{SOURCE_NAME}] erro ao parsear card: {e}")

    # Enrich with detail pages in parallel
    _enrich_details(corridas)

    return corridas


def _find_cards(soup: BeautifulSoup):
    """Try multiple CSS selector strategies to find event cards."""
    selectors = [
        "[class*='EventCard']",
        "[class*='event-card']",
        "[class*='card-event']",
        "[class*='race-card']",
        "[class*='corrida-card']",
        "article[class*='card']",
        "article",
        "li[class*='event']",
        "div[class*='event']",
        ".card",
    ]
    for sel in selectors:
        try:
            results = soup.select(sel)
            # Require the card to have an <a href> pointing to /evento/
            valid = [el for el in results if el.find("a", href=re.compile(r"/evento/"))]
            if valid:
                return valid
        except Exception:
            continue

    # Last resort: all <a> tags pointing to /evento/
    links = soup.find_all("a", href=re.compile(r"/evento/"))
    return links if links else []


def _parse_card(card, today: str) -> Corrida | None:
    # Find the event link
    a_tag = card.find("a", href=re.compile(r"/evento/")) if card.name != "a" else card
    if not a_tag:
        return None

    href = a_tag.get("href", "")
    if href.startswith("/"):
        href = BASE + href
    elif not href.startswith("http"):
        return None

    # Title
    titulo_raw = (
        _text_of(card, ["h1", "h2", "h3", "h4", "[class*='title']", "[class*='name']"]) or
        a_tag.get("title") or
        card.get_text(" ", strip=True)[:100]
    )
    titulo = normalize_titulo(titulo_raw)
    if not titulo or len(titulo) < 3:
        return None

    titulo_lower = titulo.lower()
    if any(kw in titulo_lower for kw in _NON_RUNNING_KW):
        return None

    text = card.get_text(" ", strip=True)

    # Date
    data_evento = _extract_date(card, text)
    if not data_evento or data_evento < today:
        return None

    # Location
    loc_text = (
        _text_of(card, ["[class*='location']", "[class*='city']", "[class*='local']",
                        "[class*='cidade']", "[class*='place']"]) or
        _extract_location_from_text(text)
    )
    cidade, estado = _parse_location(loc_text)
    if not estado:
        estado = infer_estado(loc_text, titulo) or "??"
    localizacao = f"{cidade}, {estado}" if cidade else estado

    # Distances
    distancias = _extract_distances(text)
    if not distancias:
        distancias = _distances_from_title(titulo_lower)

    # Inscription status
    inscricoes_abertas = _parse_status(card, text)

    # Image
    img = card.find("img")
    imagem_url: str | None = None
    if img:
        imagem_url = img.get("src") or img.get("data-src") or img.get("data-lazy-src")
        if imagem_url and imagem_url.startswith("/"):
            imagem_url = BASE + imagem_url

    # Event ID from URL
    id_match = re.search(r"-(\d+)$", href)
    event_id  = id_match.group(1) if id_match else ""

    now   = now_iso()
    today_str = today_iso()
    fonte = FonteInfo(
        nome=SOURCE_NAME,
        link_evento=href,
        links_inscricao=[href] if inscricoes_abertas is not False else [],
    )

    return Corrida(
        id=f"gd_{event_id}" if event_id else f"{slugify(titulo)}_{estado.lower()}_{today_str}",
        titulo=titulo,
        data_evento=data_evento,
        horario=None,
        localizacao=localizacao,
        cidade=normalize_cidade(cidade) if cidade else "",
        estado=estado,
        distancias=distancias,
        imagem_url=imagem_url,
        inscricoes_abertas=inscricoes_abertas,
        periodo_inscricao=None,
        fontes=[fonte],
        miss_count=0,
        first_seen_at=now,
        updated_at=now,
    )


# ---------------------------------------------------------------------------
# Detail page enrichment
# ---------------------------------------------------------------------------

def _enrich_details(corridas: list[Corrida]) -> None:
    with ThreadPoolExecutor(max_workers=6) as ex:
        futures = {ex.submit(_fetch_detail, c): c for c in corridas}
        for fut in as_completed(futures):
            pass  # errors logged inside


def _fetch_detail(corrida: Corrida) -> None:
    link = corrida.fontes[0].link_evento if corrida.fontes else None
    if not link or link == CALENDAR_URL:
        return
    try:
        resp = get(link)
        if resp.status_code != 200:
            return
    except Exception as e:
        print(f"[{SOURCE_NAME}] detalhe '{corrida.titulo}' falhou: {e}")
        return

    soup = BeautifulSoup(resp.text, "lxml")

    # Try __NEXT_DATA__ on detail page first
    tag = soup.find("script", id="__NEXT_DATA__")
    if tag and tag.string:
        try:
            data = json.loads(tag.string)
            _enrich_from_detail_json(corrida, data)
            return
        except Exception:
            pass

    # Fall back to HTML parsing of the detail page
    _enrich_from_detail_html(corrida, soup)


def _enrich_from_detail_json(corrida: Corrida, data: dict) -> None:
    ev = _find_single_event_in_json(data)
    if not ev:
        return

    dist_raw = (
        ev.get("distances") or ev.get("distancias") or ev.get("percursos") or
        ev.get("modalities") or ev.get("modalidades") or []
    )
    dists = _parse_json_distances(dist_raw)
    if dists:
        corrida.distancias = dists

    horario = _parse_horario(ev)
    if horario:
        corrida.horario = horario

    if not corrida.imagem_url:
        img = (ev.get("imageUrl") or ev.get("image") or ev.get("imagem") or
               ev.get("foto") or ev.get("cover"))
        if img:
            corrida.imagem_url = img


def _find_single_event_in_json(obj, _depth: int = 0) -> dict | None:
    """Find a single event dict in the detail page __NEXT_DATA__."""
    if _depth > 8:
        return None
    if isinstance(obj, dict):
        if _looks_like_event(obj) and len(obj) > 4:
            return obj
        for key in ("event", "evento", "corrida", "race", "data", "pageProps"):
            val = obj.get(key)
            if isinstance(val, dict) and _looks_like_event(val):
                return val
            if isinstance(val, (dict, list)):
                result = _find_single_event_in_json(val, _depth + 1)
                if result:
                    return result
    if isinstance(obj, list):
        for item in obj:
            result = _find_single_event_in_json(item, _depth + 1)
            if result:
                return result
    return None


def _enrich_from_detail_html(corrida: Corrida, soup: BeautifulSoup) -> None:
    text = soup.get_text(" ", strip=True)
    text_clean = _INTERVAL_RE.sub(" ", text)

    # Distances from detail page body
    dists = _extract_distances(text_clean)
    if dists:
        corrida.distancias = dists

    # Start time
    if not corrida.horario:
        m = re.search(r"\b(\d{1,2})[h:](\d{2})\b", text_clean)
        if m:
            h = int(m.group(1))
            if 4 <= h <= 22:
                corrida.horario = f"{h:02d}:{m.group(2)}"

    # OG image
    if not corrida.imagem_url:
        og = soup.find("meta", property="og:image")
        if og and og.get("content"):
            corrida.imagem_url = og["content"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _text_of(el, selectors: list[str]) -> str:
    for sel in selectors:
        try:
            found = el.select_one(sel)
            if found:
                t = found.get_text(strip=True)
                if t:
                    return t
        except Exception:
            continue
    return ""


def _extract_date(card, text: str) -> str | None:
    # Try datetime attributes first
    for tag in card.find_all(True):
        for attr in ("datetime", "data-date", "data-evento", "content"):
            val = tag.get(attr, "")
            if val:
                d = normalize_date(val)
                if d:
                    return d

    # DD/MM/YYYY
    m = re.search(r"\b(\d{1,2})[/\-\.](\d{1,2})[/\-\.](20\d{2})\b", text)
    if m:
        return f"{m.group(3)}-{m.group(2).zfill(2)}-{m.group(1).zfill(2)}"

    # "10 de agosto de 2026"
    m = re.search(r"(\d{1,2})\s+de\s+([a-záéíóúãõâêô]+)\s+de\s+(20\d{2})", text, re.IGNORECASE)
    if m:
        mo = _PT_MONTHS.get(m.group(2).lower())
        if mo:
            return f"{m.group(3)}-{mo}-{m.group(1).zfill(2)}"

    # "agosto 2026" (no day — skip)
    return None


def _extract_location_from_text(text: str) -> str:
    m = re.search(
        r"([A-ZÀ-Ú][a-zà-ú]+(?:\s+[A-ZÀ-Úa-zà-ú]+)*)\s*[,\-–]\s*([A-Z]{2})\b",
        text,
    )
    return m.group(0) if m else ""


def _parse_location(loc: str) -> tuple[str, str]:
    """'São Paulo, SP' or 'São Paulo - SP' → ('São Paulo', 'SP')"""
    if not loc:
        return "", ""
    m = re.search(r"(.+?)\s*[,\-–]\s*([A-Z]{2})\b", loc.strip())
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return loc.strip(), ""


def _extract_distances(text: str) -> list[Distancia]:
    clean = _INTERVAL_RE.sub(" ", text)
    nums = re.findall(r"(?<![.,])\b(\d+(?:[.,]\d+)?)\s*k(?:m)?\b", clean, re.IGNORECASE)
    seen: set[float] = set()
    result: list[Distancia] = []
    for n in nums:
        km = float(n.replace(",", "."))
        for canon, lo, hi in _CANONICAL:
            if lo <= km <= hi:
                km = canon
                break
        if km not in seen and 3 <= km <= 200:
            seen.add(km)
            result.append(Distancia(km=km, data=None, horario=None))
    return sorted(result, key=lambda d: d.km)


def _parse_status(card, text: str) -> bool | None:
    text_lower = text.lower()
    if any(kw in text_lower for kw in ("encerrad", "esgotad", "fechad", "sold out")):
        return False
    if any(kw in text_lower for kw in ("inscri", "comprar", "inscreva", "register")):
        # Check for an actual inscription button/link
        for a in card.find_all("a", href=True):
            btn_text = a.get_text(strip=True).lower()
            if any(kw in btn_text for kw in ("inscri", "comprar", "register")):
                return True
    return None


def _distances_from_title(titulo_lower: str) -> list[Distancia]:
    seen: set[float] = set()
    result: list[Distancia] = []

    if "meia maratona" in titulo_lower or "half marathon" in titulo_lower:
        seen.add(21.097)
        result.append(Distancia(km=21.097, data=None, horario=None))
    if re.search(r"(?<!meia )\bmaratona\b|(?<!half )\bmarathon\b", titulo_lower):
        if 42.195 not in seen:
            seen.add(42.195)
            result.append(Distancia(km=42.195, data=None, horario=None))
    for m in re.finditer(r"\b(\d+(?:[.,]\d+)?)\s*k(?:m)?\b", titulo_lower):
        km = float(m.group(1).replace(",", "."))
        for canon, lo, hi in _CANONICAL:
            if lo <= km <= hi:
                km = canon
                break
        if km not in seen and 3 <= km <= 200:
            seen.add(km)
            result.append(Distancia(km=km, data=None, horario=None))

    return sorted(result, key=lambda d: d.km if isinstance(d.km, (int, float)) else 999)
