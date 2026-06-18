"""Scraper for largadaesportiva.com.br — Brazilian sports-event registration platform.

The site is a JS SPA (Hostinger VPS, no WAF). A plain httpx request returns only
the HTML shell. Strategy:

1. HTTP GET (direct httpx). Tries /eventos, /corridas, /calendario, and / in order.
2. Within the rendered HTML: extract __NEXT_DATA__ (Next.js), then other embedded
   JSON blobs (window.__STATE__ etc.), then HTML card parsing.
3. Playwright fallback with fetch/XHR response interception → JSON API capture.
   Falls back to HTML card parsing on the rendered page.

No running-keyword filter: the platform is running-focused so all events are kept.
Non-running sports (triathlon, cycling, etc.) are excluded.
"""
from __future__ import annotations

import json
import re
from bs4 import BeautifulSoup

from ..http_client import get
from ..models import Corrida, Distancia, FonteInfo
from ..utils import (
    normalize_titulo, normalize_date, normalize_time,
    slugify, infer_estado, now_iso, today_iso,
    validate_image_url, extract_distances_from_text,
)
from .. import geo as _geo

BASE        = "https://largadaesportiva.com.br"
SOURCE_NAME = "Largada Esportiva"

# Ordered by likelihood of containing the events listing
_CANDIDATE_URLS = [
    f"{BASE}/eventos",
    f"{BASE}/corridas",
    f"{BASE}/calendario",
    f"{BASE}/corridas-de-rua",
    BASE,
]

# Excluded: non-running sports that may appear on a general sports platform
_NON_RUNNING_KW = re.compile(
    r"\btriathlon\b|\btriathon\b|\bironman\b|\bduathlon\b"
    r"|\baquabike\b|\baquathlon\b|\bnatação\b|\bswimrun\b"
    r"|\bciclismo\b|\bpedalada\b|\bfutebol\b"
    r"|\bjiu.?jitsu\b|\bmma\b|\bboxe\b|\bkaratê\b|\bkarate\b",
    re.IGNORECASE,
)

_PT_MONTHS = {
    "janeiro": "01", "fevereiro": "02", "março": "03", "marco": "03",
    "abril": "04", "maio": "05", "junho": "06", "julho": "07",
    "agosto": "08", "setembro": "09", "outubro": "10",
    "novembro": "11", "dezembro": "12",
}

_UF_TO_CAPITAL: dict[str, str] = {
    "AC": "Rio Branco", "AL": "Maceió", "AM": "Manaus", "AP": "Macapá",
    "BA": "Salvador", "CE": "Fortaleza", "DF": "Brasília", "ES": "Vitória",
    "GO": "Goiânia", "MA": "São Luís", "MG": "Belo Horizonte", "MS": "Campo Grande",
    "MT": "Cuiabá", "PA": "Belém", "PB": "João Pessoa", "PE": "Recife",
    "PI": "Teresina", "PR": "Curitiba", "RJ": "Rio de Janeiro", "RN": "Natal",
    "RO": "Porto Velho", "RR": "Boa Vista", "RS": "Porto Alegre",
    "SC": "Florianópolis", "SE": "Aracaju", "SP": "São Paulo", "TO": "Palmas",
}

_CANONICAL  = [(42.195, 41.5, 43.0), (21.097, 20.5, 21.5)]
_DATE_ISO   = re.compile(r"(20\d{2}-\d{2}-\d{2})")
_DATE_DMY   = re.compile(r"\b(\d{1,2})[/\-](\d{1,2})[/\-](20\d{2})\b")

# All field names seen across Brazilian event-platform APIs
_TITLE_KEYS = (
    "titulo", "title", "nome", "name", "nome_evento", "event_name",
    "eventTitle", "eventName", "event_title", "titulo_evento",
    "descricao", "description",
)
_DATE_KEYS = (
    "data_evento", "data", "date", "startDate", "start_date",
    "eventDate", "event_date", "dataEvento", "inicio", "start",
    "data_realizacao", "data_corrida", "data_inicio", "dt_evento",
    "dt_inicio", "scheduled_date",
)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


# Venue phrases ("Largada na Orla da Ponte JK – SCES Trecho 2 …") sometimes end
# up in the free-text location field that we fall back to for the city. A venue
# is not a city: emitting it as `cidade` breaks the merger's city check and
# leaves duplicates (e.g. two "20ª Volta do Lago" records). Reject implausible
# city names so the empty-cidade fallbacks (UF capital) apply instead.
_VENUE_WORDS_RE = re.compile(
    r"\b(largada|chegada|orla|trecho|estacionamento|est[áa]dio|gin[áa]sio|"
    r"arena|setor|quadra|lote|rodovia|avenida|av\.|rua|r\.|p[óo]rtico|"
    r"p[íi]er|deck|complexo)\b",
    re.IGNORECASE,
)


def _plausible_city(name: str) -> bool:
    if not name or len(name) > 35 or any(ch.isdigit() for ch in name):
        return False
    if len(name.split()) > 4:
        return False
    return not _VENUE_WORDS_RE.search(name)

def scrape() -> list[Corrida]:
    today = today_iso()

    # Strategy 1: HTTP with JS rendering
    html, used_url = _fetch_html_http()
    if html:
        soup = BeautifulSoup(html, "lxml")
        for fn in (_try_next_data, _try_embedded_json, _parse_html_cards):
            result = fn(soup, today, used_url)
            if result:
                print(f"[{SOURCE_NAME}] {len(result)} corridas via {fn.__name__}")
                return result
        print(f"[{SOURCE_NAME}] HTTP: página obtida ({len(html)}B) mas sem eventos reconhecíveis")

    # Strategy 2: Playwright with API interception
    result = _fetch_via_playwright(today)
    if result:
        print(f"[{SOURCE_NAME}] {len(result)} corridas via Playwright")
        return result

    print(f"[{SOURCE_NAME}] 0 corridas encontradas")
    return []


# ---------------------------------------------------------------------------
# HTTP fetch — tries each candidate URL, stops at first usable HTML
# ---------------------------------------------------------------------------

def _fetch_html_http() -> tuple[str | None, str]:
    for url in _CANDIDATE_URLS:
        try:
            resp = get(url)
            resp.raise_for_status()
            html = resp.text
            if len(html) > 1000 and "<html" in html.lower():
                print(f"[{SOURCE_NAME}] HTTP OK {len(html)}B → {url}")
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
    result = _extract_from_json(data, today, page_url)
    if not result:
        print(f"[{SOURCE_NAME}] __NEXT_DATA__ encontrado mas sem eventos")
    return result


# ---------------------------------------------------------------------------
# Strategy 1b: other embedded JSON blobs
# ---------------------------------------------------------------------------

def _try_embedded_json(soup: BeautifulSoup, today: str, page_url: str) -> list[Corrida]:
    for script in soup.find_all("script"):
        src = script.string or ""
        if len(src) < 50:
            continue
        # window.__STATE__, __DATA__, __APP__, __PRELOADED_STATE__, etc.
        for pat in [
            r"window\.__(?:STATE|DATA|APP(?:_DATA)?|INITIAL_STATE|PRELOADED_STATE|initialState)\s*=\s*(\{[\s\S]+?\});",
            r"var\s+__(?:APP|DATA|STORE|STATE)__\s*=\s*(\{[\s\S]+?\});",
        ]:
            m = re.search(pat, src, re.DOTALL)
            if m:
                try:
                    obj = json.loads(m.group(1))
                    result = _extract_from_json(obj, today, page_url)
                    if result:
                        return result
                except Exception:
                    pass
        # Large JSON array sitting directly in a script
        if any(k in src for k in _DATE_KEYS):
            for m in re.finditer(r"(\[[\s\S]{100,}\])", src):
                try:
                    arr = json.loads(m.group(1))
                    if isinstance(arr, list) and arr:
                        result = _extract_from_json(arr, today, page_url)
                        if result:
                            return result
                except Exception:
                    pass
    return []


# ---------------------------------------------------------------------------
# Strategy 1c: HTML card parsing
# ---------------------------------------------------------------------------

def _parse_html_cards(soup: BeautifulSoup, today: str, page_url: str) -> list[Corrida]:
    cards = _find_event_cards(soup)
    if not cards:
        # Debug: show top-level tag structure
        tags = [t.name for t in soup.body.children if hasattr(t, "name")] if soup.body else []
        print(f"[{SOURCE_NAME}] HTML: nenhum card encontrado. Tags raiz: {tags[:10]}")
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
        "[class*='event-card']", "[class*='EventCard']", "[class*='corrida']",
        "[class*='evento']", "[class*='race-card']", "[class*='card-race']",
        "article.card", "article[class*='event']", "li[class*='event']",
        "div[class*='event-item']", "div[class*='race-item']",
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
    if _NON_RUNNING_KW.search(titulo):
        return None

    data_evento = _extract_date_text(text)
    if data_evento and data_evento < today:
        return None

    estado, cidade, localizacao = _extract_location(el, text)
    _pais_geo, _ = _geo.resolve(localizacao, cidade, "BR")
    pais_card = _pais_geo or "BR"
    horario = normalize_time(text)

    img = el.find("img")
    imagem_url = None
    if img:
        src = img.get("src") or img.get("data-src") or img.get("data-lazy-src") or ""
        if src.startswith("/"):
            src = BASE + src
        imagem_url = validate_image_url(src)

    link_tag = el.find("a", href=True)
    link = link_tag["href"] if link_tag else page_url
    if link.startswith("/"):
        link = BASE + link

    distancias = _extract_distances_text(text)
    if not distancias:
        return None

    slug = link.rstrip("/").split("/")[-1] if link != page_url else ""
    ev_id = f"le_{slug}" if slug else f"le_{slugify(titulo)}_{estado.lower()}"

    now = now_iso()
    return Corrida(
        id=ev_id,
        titulo=titulo,
        data_evento=data_evento or "",
        horario=horario,
        localizacao=localizacao,
        cidade=cidade,
        estado=estado,
        pais=pais_card,
        distancias=distancias,
        imagem_url=imagem_url,
        inscricoes_abertas=None,
        periodo_inscricao=None,
        fontes=[FonteInfo(nome=SOURCE_NAME, link_evento=link, links_inscricao=[link], tipo="calendario")],
        miss_count=0,
        first_seen_at=now,
        updated_at=now,
    )


# ---------------------------------------------------------------------------
# Strategy 2: Playwright with API interception
# ---------------------------------------------------------------------------

def _fetch_via_playwright(today: str) -> list[Corrida]:
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
    except ImportError:
        return []

    for url in _CANDIDATE_URLS:
        try:
            result = _playwright_one_url(url, today)
            if result:          # only stop if events actually found
                return result
        except Exception as e:
            print(f"[{SOURCE_NAME}] Playwright {url}: {e}")
    return []


def _playwright_one_url(url: str, today: str) -> list[Corrida]:
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

        def _on_response(response):
            ct = response.headers.get("content-type", "")
            if "json" in ct and response.status < 400:
                try:
                    body = response.json()
                    intercepted.append({"url": response.url, "body": body})
                except Exception:
                    pass

        page.on("response", _on_response)
        # domcontentloaded, not the default "load": this SPA hangs the load event
        # on never-completing subresources, so goto() would time out at 30s even
        # though the document (and the XHR JSON we intercept) is already available.
        page.goto(url, timeout=30_000, wait_until="domcontentloaded")
        try:
            page.wait_for_load_state("networkidle", timeout=20_000)
        except Exception:
            pass

        # Scroll to trigger lazy-loaded content
        try:
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(2000)
        except Exception:
            pass

        html = page.content()
        browser.close()

    print(f"[{SOURCE_NAME}] Playwright {url}: {len(intercepted)} respostas JSON interceptadas")

    # Try intercepted API responses
    for item in intercepted:
        result = _extract_from_json(item["body"], today, url)
        if result:
            print(f"[{SOURCE_NAME}] API: {item['url']}")
            return result

    # Fall back to rendered HTML
    if html:
        soup = BeautifulSoup(html, "lxml")
        for fn in (_try_next_data, _try_embedded_json, _parse_html_cards):
            result = fn(soup, today, url)
            if result:
                return result

    return []   # no events at this URL — caller will try next


# ---------------------------------------------------------------------------
# JSON extraction helpers
# ---------------------------------------------------------------------------

def _extract_from_json(obj: object, today: str, page_url: str) -> list[Corrida]:
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
    if depth > 10:
        return []
    results: list[dict] = []
    if isinstance(obj, dict):
        has_title = any(obj.get(k) for k in _TITLE_KEYS)
        has_date  = any(obj.get(k) for k in _DATE_KEYS)
        if has_title and has_date:
            results.append(obj)
        else:
            for v in obj.values():
                results.extend(_collect_event_dicts(v, depth + 1))
    elif isinstance(obj, list):
        for item in obj:
            results.extend(_collect_event_dicts(item, depth + 1))
    return results


def _parse_event_dict(ev: dict, today: str, page_url: str) -> Corrida | None:
    titulo_raw = next((ev[k] for k in _TITLE_KEYS if ev.get(k)), "")
    titulo = normalize_titulo(str(titulo_raw))
    if not titulo or len(titulo) < 3:
        return None
    if _NON_RUNNING_KW.search(titulo):
        return None

    data_raw = next((ev[k] for k in _DATE_KEYS if ev.get(k)), "")
    data_evento = _parse_date(str(data_raw))
    if data_evento and data_evento < today:
        return None

    horario_raw = ev.get("horario") or ev.get("hora") or ev.get("time") or \
                  ev.get("startTime") or ev.get("start_time") or ev.get("hora_inicio") or ""
    horario = normalize_time(str(horario_raw)) if horario_raw else None

    # Fallback: extract HH:MM from the ISO datetime used for the date.
    # Largada Esportiva stores the manually-entered local start time with a
    # cosmetic "Z" suffix — the raw hour IS the BRT start, not UTC. Confirmed
    # for Volta do Lago: start="2026-07-05T04:00:00.000Z" and the regulation
    # text reads "7 – LARGADAS … Largada 04h00". Price-tier cutoff dates, by
    # contrast, are stored at T03:00Z (= local midnight) as a date-only
    # placeholder; the 4 AM lower bound below skips that hour-3 placeholder.
    if horario is None and data_raw:
        _tm = re.match(r"\d{4}-\d{2}-\d{2}T(\d{2}):(\d{2})", str(data_raw))
        if _tm:
            _h, _mn = int(_tm.group(1)), int(_tm.group(2))
            if 4 <= _h <= 22:  # plausible race-start window; excludes midnight placeholder
                horario = f"{_h:02d}:{_mn:02d}"

    estado = str(ev.get("estado") or ev.get("uf") or ev.get("state") or "").upper()
    if len(estado) != 2:
        estado = ""
    cidade = normalize_titulo(str(
        ev.get("cidade") or ev.get("city") or ev.get("municipio") or ""
    ))
    localizacao = str(
        ev.get("localizacao") or ev.get("local") or ev.get("location") or
        ev.get("endereco") or ev.get("address") or ""
    )
    if not localizacao:
        localizacao = ", ".join(filter(None, [cidade, estado]))
    if not estado:
        _pais_geo, _estado_geo = _geo.resolve(localizacao, cidade, "BR")
        pais_dict = _pais_geo or "BR"
        # estado from the structured address only (+ geo fallback) — never the title.
        estado = infer_estado(localizacao) or _estado_geo or ""
    else:
        pais_dict = "BR"
    if not cidade:
        derived = localizacao.split(",")[0].split("-")[0].strip()
        # also split on en/em dashes the venue lines use
        derived = re.split(r"[–—]", derived)[0].strip()
        cidade = derived if _plausible_city(derived) else ""
    if not cidade and estado in _UF_TO_CAPITAL:
        cidade = _UF_TO_CAPITAL[estado]
    if cidade and estado and len(estado) == 2:
        localizacao = f"{cidade}, {estado}"

    img_raw = (
        ev.get("imagem") or ev.get("image") or ev.get("foto") or
        ev.get("banner") or ev.get("thumbnail") or ev.get("imagem_url") or
        ev.get("imageUrl") or ev.get("image_url") or ev.get("capa") or ""
    )
    imagem_url = validate_image_url(str(img_raw) if img_raw else None)

    slug = str(ev.get("slug") or ev.get("id") or ev.get("eventId") or ev.get("evento_id") or "")
    link = str(
        ev.get("link") or ev.get("url") or ev.get("link_evento") or
        ev.get("linkEvento") or ev.get("link_inscricao") or ""
    )
    if not link and slug:
        link = f"{BASE}/evento/{slug}"
    if not link:
        link = page_url

    dist_raw = (
        ev.get("distancias") or ev.get("distances") or
        ev.get("percursos") or ev.get("modalidades") or
        ev.get("categorias") or ev.get("provas") or
        ev.get("percurso") or ev.get("itens") or []
    )
    distancias = _parse_distances_value(dist_raw)
    if not distancias:
        # Collect all text-like values from the event dict for pattern matching
        text_parts: list[str] = [
            str(ev.get("descricao") or ""),
            str(ev.get("description") or ""),
            str(ev.get("regulamento") or ""),
            str(titulo_raw),
        ]
        for v in ev.values():
            if isinstance(v, str) and len(v) >= 2:
                text_parts.append(v)
            elif isinstance(v, list):
                for item in v:
                    if isinstance(item, str):
                        text_parts.append(item)
                    elif isinstance(item, dict):
                        text_parts.extend(
                            str(vv) for vv in item.values()
                            if isinstance(vv, (str, int, float))
                        )
        distancias = _extract_distances_text(" ".join(text_parts))
    if not distancias:
        return None

    ev_id = f"le_{slug}" if slug and re.match(r"^[\w\-]+$", slug) else \
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
        pais=pais_dict,
        distancias=distancias,
        imagem_url=imagem_url,
        inscricoes_abertas=None,
        periodo_inscricao=None,
        fontes=[FonteInfo(nome=SOURCE_NAME, link_evento=link, links_inscricao=[link], tipo="calendario")],
        miss_count=0,
        first_seen_at=now,
        updated_at=now,
    )


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _extract_location(el, text: str) -> tuple[str, str, str]:
    loc_el = el.find(class_=re.compile(r"local|location|cidade|place|city|address|endereco", re.I))
    localizacao = loc_el.get_text(strip=True) if loc_el else ""
    if not localizacao:
        m = re.search(
            r"([A-ZÁÉÍÓÚÀÂÃÊÔÕÇ][A-Za-záéíóúàâãêôõç\s]{2,30?})\s*[-–,]\s*([A-Z]{2})\b",
            text,
        )
        if m:
            localizacao = m.group(0)
    estado = ""
    cidade = ""
    m = re.search(r"\b([A-Z]{2})\b", localizacao)
    if m:
        estado = m.group(1)
    if not estado:
        _, _loc_geo = _geo.resolve(localizacao, "", "BR")
        estado = infer_estado(localizacao, "") or _loc_geo or ""
    cidade = localizacao.split(",")[0].split("-")[0].strip()
    if not cidade and estado in _UF_TO_CAPITAL:
        cidade = _UF_TO_CAPITAL[estado]
    if cidade and estado and len(estado) == 2:
        localizacao = f"{cidade}, {estado}"
    return estado, cidade, localizacao


def _parse_date(raw: str) -> str | None:
    if not raw:
        return None
    raw = raw.strip()
    m = _DATE_ISO.match(raw)
    if m:
        return m.group(1)
    m = _DATE_DMY.search(raw)
    if m:
        return f"{m.group(3)}-{m.group(2).zfill(2)}-{m.group(1).zfill(2)}"
    m = re.search(r"(\d{1,2})\s+de\s+([a-záéíóúâêôãõç]+)\s+de\s+(20\d{2})", raw, re.I)
    if m:
        mo = _PT_MONTHS.get(m.group(2).lower())
        if mo:
            return f"{m.group(3)}-{mo}-{m.group(1).zfill(2)}"
    return normalize_date(raw)


def _extract_date_text(text: str) -> str | None:
    m = _DATE_ISO.search(text)
    if m:
        return m.group(1)
    m = _DATE_DMY.search(text)
    if m:
        return f"{m.group(3)}-{m.group(2).zfill(2)}-{m.group(1).zfill(2)}"
    m = re.search(r"(\d{1,2})\s+de\s+([a-záéíóúâêôãõç]+)\s+de\s+(20\d{2})", text, re.I)
    if m:
        mo = _PT_MONTHS.get(m.group(2).lower())
        if mo:
            return f"{m.group(3)}-{mo}-{m.group(1).zfill(2)}"
    return None


_KM_SUBKEYS = ("km", "distancia", "distance", "quilometros", "kilometers", "percurso_km")


def _parse_distances_value(val: object) -> list[Distancia]:
    if isinstance(val, list):
        result: list[Distancia] = []
        seen_km: set[float] = set()
        for item in val:
            if isinstance(item, (int, float)) and 1 <= item <= 250:
                km = float(item)
                if km not in seen_km:
                    seen_km.add(km)
                    result.append(Distancia(km=km, data=None, horario=None))
            elif isinstance(item, dict):
                # Check common sub-keys that store the distance numerically
                for k in _KM_SUBKEYS:
                    raw_km = item.get(k)
                    if raw_km is not None:
                        try:
                            km = float(raw_km)
                            if 1 <= km <= 250 and km not in seen_km:
                                seen_km.add(km)
                                result.append(Distancia(km=km, data=None, horario=None))
                        except (ValueError, TypeError):
                            pass
                        break
                else:
                    # Fall back to text extraction from all string/numeric values
                    text = " ".join(str(v) for v in item.values() if isinstance(v, (str, int, float)))
                    for d in _extract_distances_text(text):
                        if d.km not in seen_km:
                            seen_km.add(d.km)
                            result.append(d)
            elif isinstance(item, str):
                for d in _extract_distances_text(item):
                    if d.km not in seen_km:
                        seen_km.add(d.km)
                        result.append(d)
        return result
    return _extract_distances_text(str(val)) if val else []


def _extract_distances_text(text: str) -> list[Distancia]:
    _INTERVAL = re.compile(
        r"a cada \d+(?:[.,]\d+)?\s*km?\b|cada \d+(?:[.,]\d+)?\s*km?\b"
        r"|\d+(?:[.,]\d+)?\s*km?\s*(?:de hidrat|de água|de abastec)",
        re.IGNORECASE,
    )
    text_clean = _INTERVAL.sub(" ", text)
    # Shared-suffix-aware numeric extraction; named distances handled by the
    # keyword fallback below (allow_named=False).
    result: list[Distancia] = [
        Distancia(km=km, data=None, horario=None)
        for km in extract_distances_from_text(text_clean, min_km=1.0, max_km=250.0, allow_named=False)
    ]
    if not result:
        ltext = text.lower()
        is_half = bool(re.search(r"\b(meia\s+maratona|half\s+marathon|21k)\b", ltext))
        is_full = bool(re.search(r"\b(maratona|marathon|42k)\b", ltext))
        if is_half:
            result.append(Distancia(km=21.097, data=None, horario=None))
        elif is_full:
            result.append(Distancia(km=42.195, data=None, horario=None))
    return result
