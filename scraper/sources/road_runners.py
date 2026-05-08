"""Scraper for roadrunners.run — Brazilian running events listed by state.

The site exposes events grouped by UF. The homepage doesn't list every
event, so we discover state-page URLs from the homepage (or fall back to
trying every Brazilian UF) and aggregate events across all of them.

Strategy:
  1. Fetch the homepage to discover state-page URLs (anchors like /sp, /df).
  2. If discovery fails, try every UF (/ac … /to) blindly.
  3. For each state page: prefer __NEXT_DATA__ JSON; fall back to HTML cards.
  4. Playwright is used as the last resort when both HTTP and the extractors
     come up empty for the homepage.
"""
from __future__ import annotations
import json
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..http_client import get
from ..models import Corrida, Distancia, FonteInfo
from ..utils import normalize_titulo, slugify, infer_estado, now_iso, today_iso

BASE        = "https://roadrunners.run"
SOURCE_NAME = "Road Runners"

_BR_STATES = [
    "AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS",
    "MT", "PA", "PB", "PE", "PI", "PR", "RJ", "RN", "RO", "RR", "RS", "SC",
    "SE", "SP", "TO",
]

_NON_RUNNING = re.compile(
    r"\btriathlon\b|\bduathlon\b|\baquathlon\b|\bcycling\b|\bciclismo\b"
    r"|\bswim\b|\bnatação\b|\bnatacao\b|\bpedalada\b",
    re.IGNORECASE,
)

_PT_MONTHS = {
    "jan": "01", "fev": "02", "mar": "03", "abr": "04", "mai": "05",
    "jun": "06", "jul": "07", "ago": "08", "set": "09", "out": "10",
    "nov": "11", "dez": "12",
    "janeiro": "01", "fevereiro": "02", "março": "03", "marco": "03",
    "abril": "04", "maio": "05", "junho": "06", "julho": "07",
    "agosto": "08", "setembro": "09", "outubro": "10",
    "novembro": "11", "dezembro": "12",
}

_ISO_RE  = re.compile(r"(\d{4})-(\d{1,2})-(\d{1,2})")
_DMY_RE  = re.compile(r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})")
_WORD_RE = re.compile(
    r"(\d{1,2})\s+(?:de\s+)?([a-záéíóúãõâêô]{3,})\s+(?:de\s+)?(\d{4})",
    re.IGNORECASE,
)
_DIST_RE = re.compile(r"\b(\d+(?:[.,]\d+)?)\s*[kK][mM]?\b")


# ---------------------------------------------------------------------------
def scrape() -> list[Corrida]:
    today = today_iso()

    # 1. Discover state URLs from homepage; fall back to all 27 UFs
    home_soup = _fetch_soup(f"{BASE}/")
    state_urls = _discover_state_urls(home_soup) if home_soup else []
    if not state_urls:
        print(f"[{SOURCE_NAME}] descoberta falhou — tentando todos os 27 UFs")
        state_urls = [(uf, f"{BASE}/{uf.lower()}") for uf in _BR_STATES]
    else:
        print(f"[{SOURCE_NAME}] {len(state_urls)} estados descobertos")

    # 2. Visit each state, accumulate events
    seen: set[str] = set()
    result: list[Corrida] = []
    for uf, url in state_urls:
        soup = _fetch_soup(url)
        if not soup:
            continue
        items = _extract_next_data(soup) or _extract_html_cards(soup)
        if not items:
            _log_diagnostics(soup, uf)
            continue
        print(f"[{SOURCE_NAME}] {uf}: {len(items)} candidatos em {url}")
        for it in items:
            try:
                c = _parse_event(it, uf, today)
                if c and c.id not in seen:
                    seen.add(c.id)
                    result.append(c)
            except Exception as e:
                name = it.get("name") or it.get("title") or "?"
                print(f"[{SOURCE_NAME}] erro ao parsear '{name}' ({uf}): {e}")

    print(f"[{SOURCE_NAME}] {len(result)} corridas no total")
    return result


# ---------------------------------------------------------------------------
# Fetch
# ---------------------------------------------------------------------------
def _fetch_soup(url: str) -> BeautifulSoup | None:
    try:
        resp = get(url, source=SOURCE_NAME, timeout=30)
    except Exception as e:
        print(f"[{SOURCE_NAME}] erro HTTP {url}: {e}")
        return None
    if resp.status_code != 200:
        print(f"[{SOURCE_NAME}] HTTP {resp.status_code} {url}")
        # If the homepage failed, try once via Playwright
        if url.rstrip("/") == BASE:
            return _playwright_soup(url)
        return None
    soup = BeautifulSoup(resp.text, "lxml")
    # If the response carries no event signals at all on the homepage,
    # try Playwright once to render JS.
    if url.rstrip("/") == BASE and not _has_signals(soup):
        pl = _playwright_soup(url)
        if pl:
            return pl
    return soup


def _playwright_soup(url: str) -> BeautifulSoup | None:
    try:
        from ..playwright_client import get_page_html
    except ImportError:
        return None
    print(f"[{SOURCE_NAME}] tentando Playwright para {url}")
    html = get_page_html(url)
    if not html:
        return None
    return BeautifulSoup(html, "lxml")


def _has_signals(soup) -> bool:
    if soup.find("script", id="__NEXT_DATA__"):
        return True
    return bool(soup.select_one(
        "a[href^='/'], [class*='event'], [class*='card'], [class*='race']"
    ))


# ---------------------------------------------------------------------------
# State discovery
# ---------------------------------------------------------------------------
def _discover_state_urls(soup) -> list[tuple[str, str]]:
    found: dict[str, str] = {}
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        # Only path-style links of the form /xx or /xx/
        m = re.match(r"^/([a-z]{2})/?$", href)
        if m and m.group(1).upper() in _BR_STATES:
            uf = m.group(1).upper()
            full = urljoin(BASE, href)
            found.setdefault(uf, full)
    return [(uf, found[uf]) for uf in sorted(found)]


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
    has_name = any(k in keys for k in (
        "name", "title", "nome", "eventname", "event_name",
    ))
    has_date = any(k in keys for k in (
        "date", "data", "startdate", "start_date", "eventdate",
        "event_date", "datestart", "datafim", "datainicio",
    ))
    return has_name and has_date


def _extract_html_cards(soup) -> list[dict]:
    selectors = [
        "a[href*='/evento/']", "a[href*='/event/']",
        "[class*='EventCard']", "[class*='event-card']",
        "[class*='RaceCard']", "[class*='race-card']",
        "article[class*='event']", "article[class*='race']",
        "[data-testid*='event']", "[class*='Card__']",
    ]
    for sel in selectors:
        cards = soup.select(sel)
        if len(cards) >= 2:
            print(f"[{SOURCE_NAME}] HTML selector '{sel}': {len(cards)} cards")
            return [_card_to_dict(c) for c in cards]
    return []


def _card_to_dict(el) -> dict:
    text = el.get_text(" ", strip=True)
    if el.name == "a" and el.get("href"):
        href = el["href"]
    else:
        a = el.find("a", href=True)
        href = a["href"] if a else ""
    if href and not href.startswith("http"):
        href = urljoin(BASE, href)

    heading = el.find(["h2", "h3", "h4", "strong", "p"])
    img = el.find("img", alt=True)
    if heading and len(heading.get_text(strip=True)) > 3:
        name = heading.get_text(strip=True)
    elif img and len(img.get("alt", "").strip()) > 3:
        name = img["alt"].strip()
    else:
        name = text[:120]

    img_src = ""
    if img and img.get("src"):
        img_src = img["src"]
        if img_src and not img_src.startswith("http"):
            img_src = urljoin(BASE, img_src)

    return {"name": name, "url": href, "image": img_src, "_text": text}


def _log_diagnostics(soup, uf: str) -> None:
    classes: set[str] = set()
    for el in soup.find_all(class_=True)[:300]:
        for c in el.get("class") or []:
            if any(kw in c.lower() for kw in (
                "event", "race", "card", "list", "item", "result"
            )):
                classes.add(c)
    if classes:
        print(f"[{SOURCE_NAME}] {uf} classes relevantes: {sorted(classes)[:15]}")
    else:
        # Show first heading text — often signals "no events" / 404
        first_h = soup.find(["h1", "h2"])
        if first_h:
            print(f"[{SOURCE_NAME}] {uf} primeiro título: '{first_h.get_text(strip=True)[:80]}'")


# ---------------------------------------------------------------------------
# Field extraction
# ---------------------------------------------------------------------------
_FIELDS = {
    "name":  ("name", "title", "nome", "eventName", "event_name"),
    "date":  ("date", "data", "startDate", "start_date", "eventDate",
              "event_date", "dataInicio", "data_inicio", "datestart"),
    "city":  ("city", "cidade", "location", "venue", "local",
              "city_name", "cityName"),
    "url":   ("url", "link", "slug", "permalink", "href",
              "event_url", "eventUrl"),
    "image": ("image", "imageUrl", "image_url", "cover", "coverImage",
              "thumbnail", "photo", "banner", "imagem"),
}


def _get(obj: dict, key: str):
    for alias in _FIELDS.get(key, (key,)):
        v = obj.get(alias)
        if v is None:
            continue
        if isinstance(v, (str, int, float)):
            s = str(v).strip()
            if s:
                return s
        if isinstance(v, dict):
            for sub in ("name", "nome", "label", "value", "city", "cidade", "url"):
                sv = v.get(sub)
                if isinstance(sv, str) and sv.strip():
                    return sv.strip()
    return None


def _parse_date(raw: str | None) -> str | None:
    if not raw:
        return None
    m = _ISO_RE.search(raw)
    if m:
        return f"{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}"
    m = _DMY_RE.search(raw)
    if m:
        return f"{m.group(3)}-{m.group(2).zfill(2)}-{m.group(1).zfill(2)}"
    m = _WORD_RE.search(raw)
    if m:
        mo = _PT_MONTHS.get(m.group(2).lower()[:3]) or _PT_MONTHS.get(m.group(2).lower())
        if mo:
            return f"{m.group(3)}-{mo}-{m.group(1).zfill(2)}"
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

    raw = item.get("distances") or item.get("distancias") or item.get("distance")
    if isinstance(raw, list):
        for d in raw:
            if isinstance(d, (int, float)):
                _add(float(d))
            elif isinstance(d, str):
                m = re.search(r"(\d+(?:[.,]\d+)?)", d)
                if m:
                    _add(float(m.group(1).replace(",", ".")))

    for field in ("name", "title", "description", "_text"):
        text = item.get(field) or ""
        if not text:
            continue
        if re.search(r"meia[\s-]maratona|half[\s-]marathon", text, re.IGNORECASE):
            _add(21.097)
        if re.search(r"(?<!meia\s)\bmaratona\b|(?<!half\s)\bmarathon\b", text, re.IGNORECASE):
            _add(42.195)
        for m in _DIST_RE.finditer(text):
            _add(float(m.group(1).replace(",", ".")))

    return sorted(result, key=lambda d: d.km if isinstance(d.km, (int, float)) else 999)


# ---------------------------------------------------------------------------
def _parse_event(item: dict, uf_default: str, today: str) -> Corrida | None:
    name_raw = _get(item, "name") or ""
    titulo   = normalize_titulo(name_raw)
    if not titulo or len(titulo) < 4:
        return None
    if _NON_RUNNING.search(titulo):
        return None

    data_evento = _parse_date(_get(item, "date"))
    if not data_evento or data_evento < today:
        return None

    city_raw = _get(item, "city") or ""
    estado   = (item.get("state") or item.get("uf") or uf_default or "??").upper()
    if estado == "??" or estado not in _BR_STATES + ["INT"]:
        inferred = infer_estado(city_raw + " " + titulo)
        estado   = inferred or uf_default or "??"

    localizacao = ", ".join(p for p in (city_raw, estado) if p) or estado

    url_raw = _get(item, "url") or ""
    if url_raw.startswith("http"):
        link = url_raw
    elif url_raw.startswith("/"):
        link = urljoin(BASE, url_raw)
    else:
        link = f"{BASE}/{uf_default.lower()}"

    image = _get(item, "image") or None

    distancias = _parse_distances(item)
    if not distancias:
        # Without distance info we still record the event — the merger may
        # complete it from another source. Use a sentinel single 5K so the
        # frontend's distance filter still works minimally.
        return None

    now  = now_iso()
    year = data_evento[:4]
    uid  = item.get("id") or item.get("slug") or slugify(titulo)
    return Corrida(
        id=f"roadrunners_{uid}_{year}",
        titulo=titulo,
        data_evento=data_evento,
        horario=None,
        localizacao=localizacao,
        cidade=city_raw or estado,
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
