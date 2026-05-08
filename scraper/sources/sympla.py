"""Scraper for Sympla (sympla.com.br) — Brazilian event platform.

Sympla hosts thousands of events of all types. This scraper searches
specifically for running events using targeted search terms and applies
strict post-hoc filters so only road/trail running events are returned.

Strategy:
  1. Fetch search pages for running-specific queries via __NEXT_DATA__
  2. Fall back to Playwright if page is client-side rendered
  3. Filter aggressively: title must match running keywords and must not
     match non-running keywords
"""
from __future__ import annotations
import json
import re

from bs4 import BeautifulSoup

from ..http_client import get
from ..models import Corrida, Distancia, FonteInfo
from ..utils import normalize_titulo, slugify, infer_estado, now_iso, today_iso

BASE        = "https://www.sympla.com.br"
SOURCE_NAME = "Sympla"

# Search terms — ordered from most to least specific
_SEARCH_TERMS = [
    "corrida de rua",
    "corrida de rua brasilia",
    "maratona",
    "trail run",
    "corrida noturna",
]
_MAX_PAGES = 10

# ── Inclusion filter — title must contain at least one of these ──────────────
_RUNNING_KW = re.compile(
    r"\bcorrida\b|\bmaratona\b|\bmaratoninha\b|\bmeia[\s-]maratona\b"
    r"|\btrail\b|\bcross[\s-]country\b"
    r"|\b\d+\s*k\b|\b\d+\s*km\b"
    r"|\bvolta\s+do\s+lago\b|\bvolta\s+da\s+lagoa\b"
    r"|\brun\b|\brace\b|\bmarcha\b",
    re.IGNORECASE,
)

# ── Exclusion filter — title must NOT contain any of these ──────────────────
_NON_RUNNING_KW = re.compile(
    r"\bshow\b|\bfestival\b|\bconcerto\b|\bforró\b|\bsamba\b|\bbaile\b"
    r"|\byoga\b|\byoga\b|\bpilates\b|\bzumba\b|\bdança\b|\bdance\b"
    r"|\bworkshop\b|\bpalestra\b|\bwebinar\b|\bcurso\b|\baula\b"
    r"|\bteatro\b|\bespetáculo\b|\bpeça\b"
    r"|\bfeira\b|\bexposição\b|\bexpo\b|\bcongresso\b|\bseminário\b"
    r"|\bnatação\b|\bciclismo\b|\bpedalada\b|\btriathlon\b|\bduathlon\b"
    r"|\bfutebol\b|\bvolei\b|\btênis\b|\bbasquete\b"
    r"|\bparty\b|\bfesta\b|\bcarnaval\b|\bréveillon\b"
    r"|\bwrestling\b|\bmma\b|\bjiu.jitsu\b|\bboxe\b|\bkaratê\b"
    r"|\bcaminhada\b(?!.*\bcorrida\b)",  # caminhada alone (not paired with corrida)
    re.IGNORECASE,
)

_EN_MONTHS = {
    "jan": "01", "fev": "02", "mar": "03", "abr": "04", "mai": "05",
    "jun": "06", "jul": "07", "ago": "08", "set": "09", "out": "10",
    "nov": "11", "dez": "12",
    "janeiro": "01", "fevereiro": "02", "março": "03", "marco": "03",
    "abril": "04", "maio": "05", "junho": "06", "julho": "07",
    "agosto": "08", "setembro": "09", "outubro": "10",
    "novembro": "11", "dezembro": "12",
}

_ISO_RE  = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
_DMY_RE  = re.compile(r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})")
_WORD_RE = re.compile(
    r"(\d{1,2})\s+de\s+([a-záéíóúãõâêô]+)\s+de\s+(\d{4})"
    r"|(\d{1,2})\s+([a-záéíóúãõâêô]+)\s+(\d{4})",
    re.IGNORECASE,
)
_DIST_RE = re.compile(r"\b(\d+(?:[.,]\d+)?)\s*k(?:m\b|\b)", re.IGNORECASE)


# ---------------------------------------------------------------------------
def scrape() -> list[Corrida]:
    today  = today_iso()
    seen   : set[str] = set()
    result : list[Corrida] = []

    for term in _SEARCH_TERMS:
        raw = _fetch_search(term)
        if not raw:
            continue
        print(f"[{SOURCE_NAME}] '{term}': {len(raw)} candidatos")
        for item in raw:
            try:
                c = _parse_item(item, today)
                if c and c.id not in seen:
                    seen.add(c.id)
                    result.append(c)
            except Exception as e:
                name = item.get("name") or item.get("title") or "?"
                print(f"[{SOURCE_NAME}] erro ao parsear '{name}': {e}")

    print(f"[{SOURCE_NAME}] {len(result)} corridas encontradas no total")
    return result


# ---------------------------------------------------------------------------
# Fetch & extract
# ---------------------------------------------------------------------------
def _fetch_search(term: str) -> list[dict]:
    raw: list[dict] = []
    for page in range(1, _MAX_PAGES + 1):
        # Sympla search URL — no trailing slash before query string
        url = f"{BASE}/busca?q={term.replace(' ', '+')}&page={page}"
        soup = None

        try:
            resp = get(url, source=SOURCE_NAME, timeout=30)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "lxml")
            else:
                print(f"[{SOURCE_NAME}] HTTP {resp.status_code} '{term}' pág {page}")
        except Exception as e:
            print(f"[{SOURCE_NAME}] erro HTTP '{term}' pág {page}: {e}")

        # Playwright fallback on first page if HTTP failed or returned nothing useful
        if soup is None or (page == 1 and not _has_event_signals(soup)):
            pl_soup = _playwright_soup(url)
            if pl_soup:
                soup = pl_soup

        if soup is None:
            break

        page_raw = _extract_next_data(soup)
        if not page_raw:
            page_raw = _extract_html_cards(soup)
        if not page_raw:
            if page == 1:
                tag = soup.find("script", id="__NEXT_DATA__")
                if tag:
                    try:
                        data = json.loads(tag.string or "")
                        pprops = data.get("pageProps", {}) if isinstance(data, dict) else {}
                        print(f"[{SOURCE_NAME}] pageProps keys: {list(pprops.keys())[:15]}")
                    except Exception:
                        pass
                else:
                    print(f"[{SOURCE_NAME}] sem __NEXT_DATA__ nem cards em '{term}' pág {page}")
            break

        raw.extend(page_raw)
        if len(page_raw) < 10:   # last page has fewer items
            break

    return raw


def _has_event_signals(soup) -> bool:
    """True if the page has any markers suggesting events were rendered."""
    if soup.find("script", id="__NEXT_DATA__"):
        return True
    return bool(soup.select_one(
        ".btn-event, [class*='EventCard'], [class*='event-card'], "
        "a[href*='/evento/'], [data-testid*='event']"
    ))


def _playwright_soup(url: str):
    try:
        from ..playwright_client import get_page_html
    except ImportError:
        return None
    print(f"[{SOURCE_NAME}] tentando Playwright para {url}")
    html = get_page_html(url)
    if not html:
        return None
    return BeautifulSoup(html, "lxml")


# ---------------------------------------------------------------------------
# Extraction strategies
# ---------------------------------------------------------------------------
def _extract_next_data(soup) -> list[dict]:
    tag = soup.find("script", id="__NEXT_DATA__")
    if not tag:
        return []
    try:
        data = json.loads(tag.string or "")
    except Exception:
        return []
    return _find_event_list(data)


def _find_event_list(obj, depth: int = 0) -> list[dict]:
    if depth > 12:
        return []
    if isinstance(obj, list):
        candidates = [x for x in obj if isinstance(x, dict) and _looks_like_event(x)]
        if len(candidates) >= 1:
            return candidates
    if isinstance(obj, dict):
        for v in obj.values():
            found = _find_event_list(v, depth + 1)
            if found:
                return found
    return []


def _looks_like_event(obj: dict) -> bool:
    keys = {k.lower() for k in obj}
    has_name  = any(k in keys for k in ("name", "title", "nome"))
    has_date  = any(k in keys for k in (
        "date", "start_date", "startdate", "data", "data_inicio",
        "start", "start_time", "starttime",
    ))
    return has_name and has_date


def _extract_html_cards(soup) -> list[dict]:
    selectors = [
        # Sympla uses "btn-event" class on event anchor/button elements
        ".btn-event",
        "a[href*='/evento/']",
        "[data-testid*='event']",
        "[class*='EventCard']", "[class*='event-card']", "[class*='Card__']",
        "article[class*='event']", ".sympla-card",
    ]
    for sel in selectors:
        cards = soup.select(sel)
        if len(cards) >= 2:
            print(f"[{SOURCE_NAME}] HTML selector '{sel}': {len(cards)} itens")
            return [_card_to_dict(c) for c in cards]
    # Diagnostic: log classes with event-related names
    classes = set()
    for el in soup.find_all(class_=True)[:300]:
        for c in (el.get("class") or []):
            if any(kw in c.lower() for kw in ("event", "card", "result", "item", "listing", "btn")):
                classes.add(c)
    if classes:
        print(f"[{SOURCE_NAME}] classes relevantes: {sorted(classes)[:20]}")
    return []


def _card_to_dict(el) -> dict:
    text = el.get_text(" ", strip=True)
    # Sympla btn-event elements are <a> tags themselves
    if el.name == "a" and el.get("href"):
        href = el["href"]
    else:
        link = el.find("a", href=True)
        href = link["href"] if link else ""
    if href and not href.startswith("http"):
        href = BASE + href

    # Title: heading tag or img alt or first meaningful text chunk
    heading = el.find(["h2", "h3", "h4", "strong", "p"])
    img = el.find("img", alt=True)
    if heading and len(heading.get_text(strip=True)) > 3:
        name = heading.get_text(strip=True)
    elif img and len(img.get("alt", "").strip()) > 3:
        name = img["alt"].strip()
    else:
        name = text[:100]

    # Sympla event slug sometimes contains the event name
    if not name or len(name) < 4:
        slug_m = re.search(r"/evento/([^/]+)/", href)
        if slug_m:
            name = slug_m.group(1).replace("-", " ").title()

    return {"name": name, "url": href, "_text": text}


# ---------------------------------------------------------------------------
# Field extraction helpers
# ---------------------------------------------------------------------------
_FIELD_MAP = {
    "name":  ["name", "title", "nome", "event_name", "eventName"],
    "date":  ["start_date", "startDate", "start", "date", "data", "data_inicio",
               "start_time", "startTime", "start_datetime"],
    "city":  ["city", "cidade", "address", "location", "venue", "local",
               "city_name", "cityName"],
    "state": ["state", "estado", "uf", "province"],
    "url":   ["url", "link", "slug", "permalink", "event_url", "eventUrl"],
    "image": ["image", "image_url", "imageUrl", "cover", "cover_image",
               "coverImage", "thumbnail", "photo", "banner"],
    "id":    ["id", "event_id", "eventId", "event_id_sympla", "sympla_id"],
}


def _get(obj: dict, key: str):
    for alias in _FIELD_MAP.get(key, [key]):
        v = obj.get(alias)
        if v is None:
            continue
        if isinstance(v, (str, int, float)):
            return str(v).strip()
        if isinstance(v, dict):
            for sub in ("name", "nome", "label", "value", "city", "cidade"):
                sv = v.get(sub)
                if isinstance(sv, str) and sv.strip():
                    return sv.strip()
    return None


def _parse_date(raw: str | None) -> str | None:
    if not raw:
        return None
    m = _ISO_RE.search(raw)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    m = _DMY_RE.search(raw)
    if m:
        return f"{m.group(3)}-{m.group(2).zfill(2)}-{m.group(1).zfill(2)}"
    m = _WORD_RE.search(raw)
    if m:
        if m.group(1):   # "dia de mês de ano"
            mo = _EN_MONTHS.get(m.group(2).lower()[:3])
            if mo:
                return f"{m.group(3)}-{mo}-{m.group(1).zfill(2)}"
        elif m.group(4):  # "dia mês ano"
            mo = _EN_MONTHS.get(m.group(5).lower()[:3])
            if mo:
                return f"{m.group(6)}-{mo}-{m.group(4).zfill(2)}"
    return None


def _parse_distances(item: dict) -> list[Distancia]:
    seen: set[float] = set()
    result: list[Distancia] = []

    def _add(km: float) -> None:
        for canon, lo, hi in ((42.195, 41.5, 43.0), (21.097, 20.5, 21.5)):
            if lo <= km <= hi:
                km = canon; break
        if km not in seen and 1.0 <= km <= 200.0:
            seen.add(km); result.append(Distancia(km=km, data=None, horario=None))

    # Try structured distances field
    dists = item.get("distances") or item.get("distance") or item.get("categorias")
    if isinstance(dists, list):
        for d in dists:
            if isinstance(d, (int, float)):
                _add(float(d))
            elif isinstance(d, str):
                m = re.search(r"(\d+(?:[.,]\d+)?)", d)
                if m:
                    _add(float(m.group(1).replace(",", ".")))

    # Extract from title / description
    for field in ("name", "title", "description", "details", "_text"):
        text = item.get(field) or ""
        if not text:
            continue
        if re.search(r"\bmeia[\s-]maratona\b|half[\s-]marathon", text, re.IGNORECASE):
            _add(21.097)
        if re.search(r"(?<!meia\s)\bmaratona\b|(?<!half\s)\bmarathon\b", text, re.IGNORECASE):
            _add(42.195)
        for m in _DIST_RE.finditer(text):
            _add(float(m.group(1).replace(",", ".")))

    return sorted(result, key=lambda d: float(d.km) if isinstance(d.km, (int, float)) else 999)


# ---------------------------------------------------------------------------
# Parse item → Corrida
# ---------------------------------------------------------------------------
def _parse_item(item: dict, today: str) -> Corrida | None:
    name_raw = _get(item, "name") or ""
    titulo   = normalize_titulo(name_raw)
    if not titulo or len(titulo) < 4:
        return None

    # ── Scope filter ────────────────────────────────────────────────────────
    if not _RUNNING_KW.search(titulo):
        return None
    if _NON_RUNNING_KW.search(titulo):
        return None

    data_evento = _parse_date(_get(item, "date"))
    if not data_evento or data_evento < today:
        return None

    distancias = _parse_distances(item)
    # Distances optional — Sympla event pages rarely carry structured distances;
    # scraper still records the event so it can be merged with other sources.

    # Location
    city_raw  = _get(item, "city") or ""
    state_raw = _get(item, "state") or ""
    if not state_raw and city_raw:
        state_raw = infer_estado(city_raw) or ""
    estado    = state_raw.upper() if state_raw else "??"
    loc_parts = [p for p in (city_raw, state_raw.upper()) if p]
    localizacao = ", ".join(loc_parts) if loc_parts else "Brasil"

    # URL
    url_raw = _get(item, "url") or ""
    event_id = _get(item, "id") or ""
    if url_raw.startswith("http"):
        link = url_raw
    elif url_raw.startswith("/"):
        link = BASE + url_raw
    elif event_id:
        link = f"{BASE}/evento/{slugify(titulo)}/{event_id}"
    else:
        link = BASE

    image = _get(item, "image") or None

    now  = now_iso()
    year = data_evento[:4]
    uid  = event_id or slugify(titulo)
    return Corrida(
        id=f"sympla_{uid}_{year}",
        titulo=titulo,
        data_evento=data_evento,
        horario=None,
        localizacao=localizacao,
        cidade=city_raw or localizacao,
        estado=estado,
        distancias=distancias,
        imagem_url=image,
        inscricoes_abertas=None,
        periodo_inscricao=None,
        fontes=[FonteInfo(
            nome=SOURCE_NAME,
            link_evento=link,
            links_inscricao=[link],
        )],
        miss_count=0,
        first_seen_at=now,
        updated_at=now,
    )
