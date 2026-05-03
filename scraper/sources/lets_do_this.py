"""Scraper for Let's Do This (letsdothis.com) — UK running event calendar.

Let's Do This is the largest UK running event discovery and registration
platform, covering road races, trail runs and mass-participation events.

Strategies:
  1. __NEXT_DATA__ / embedded JSON in the page
  2. GraphQL API endpoint
  3. HTML card parsing fallback
"""
from __future__ import annotations
import json
import re
from datetime import date

from bs4 import BeautifulSoup

from ..http_client import get, get_with_fallback
from ..models import Corrida, Distancia, FonteInfo
from ..utils import normalize_titulo, slugify, now_iso, today_iso

BASE        = "https://www.letsdothis.com"
SOURCE_NAME = "Let's Do This"
_MIN_KM     = 5.0

# Pages to fetch (ordered by specificity)
_CALENDAR_URLS = [
    f"{BASE}/gb/e/running?distanceMin=10",
    f"{BASE}/gb/e/running",
    f"{BASE}/gb/e/marathon",
    f"{BASE}/gb/e/half-marathon",
]

# GraphQL endpoint (Let's Do This uses GraphQL internally)
_GRAPHQL_URL = f"{BASE}/api/graphql"
_GRAPHQL_QUERY = """
{
  events(country: "GB", sport: "running", limit: 100) {
    id name date city distance registrationUrl imageUrl status
  }
}
"""

_UK_CITIES = set()  # populated lazily — used to filter non-UK events if needed

_CANONICAL = [(42.195, 41.5, 43.0), (21.097, 20.5, 21.5)]

_EN_MONTHS = {
    "jan": "01", "feb": "02", "mar": "03", "apr": "04",
    "may": "05", "jun": "06", "jul": "07", "aug": "08",
    "sep": "09", "oct": "10", "nov": "11", "dec": "12",
    "january": "01", "february": "02", "march": "03", "april": "04",
    "june": "06", "july": "07", "august": "08", "september": "09",
    "october": "10", "november": "11", "december": "12",
}


def scrape() -> list[Corrida]:
    today = today_iso()
    raw: list[dict] = []

    # ── Strategy 1: __NEXT_DATA__ / embedded JSON ──────────────────────────
    for url in _CALENDAR_URLS:
        try:
            resp = get_with_fallback(url, source=SOURCE_NAME)
        except Exception as e:
            print(f"[{SOURCE_NAME}] erro ao buscar {url}: {e}")
            continue

        if resp.status_code != 200:
            print(f"[{SOURCE_NAME}] HTTP {resp.status_code} para {url}")
            continue

        print(f"[{SOURCE_NAME}] HTTP 200 para {url} ({len(resp.text)} bytes)")
        soup = BeautifulSoup(resp.text, "lxml")

        raw = _extract_next_data(soup)
        if raw:
            print(f"[{SOURCE_NAME}] {len(raw)} candidatos via __NEXT_DATA__")
            break

        raw = _extract_from_scripts(soup)
        if raw:
            print(f"[{SOURCE_NAME}] {len(raw)} candidatos via script JSON")
            break

        raw = _extract_html_cards(soup)
        if raw:
            print(f"[{SOURCE_NAME}] {len(raw)} candidatos via HTML cards")
            break

        print(f"[{SOURCE_NAME}] sem dados reconhecíveis em {url}")

    # ── Strategy 2: GraphQL ────────────────────────────────────────────────
    if not raw:
        raw = _try_graphql()

    if not raw:
        print(f"[{SOURCE_NAME}] sem dados — nenhuma estratégia funcionou")
        return []

    corridas: list[Corrida] = []
    skipped = 0
    for item in raw:
        try:
            c = _parse_item(item, today)
            if c:
                corridas.append(c)
            else:
                skipped += 1
        except Exception as e:
            name = item.get("name") or item.get("title") or "?"
            print(f"[{SOURCE_NAME}] erro ao parsear '{name}': {e}")

    print(f"[{SOURCE_NAME}] {len(corridas)} corridas UK encontradas ({skipped} ignoradas)")
    return corridas


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

    if isinstance(data, dict):
        pprops = data.get("pageProps", {})
        if isinstance(pprops, dict):
            keys = list(pprops.keys())[:10]
            print(f"[{SOURCE_NAME}] __NEXT_DATA__ pageProps keys: {keys}")

    return _find_event_list(data)


def _extract_from_scripts(soup) -> list[dict]:
    for script in soup.find_all("script"):
        content = script.string or ""
        if len(content) < 200:
            continue
        # Look for JSON arrays containing event-like objects
        for m in re.finditer(r'\[(\s*\{[^[\]]{50,})\]', content):
            try:
                arr = json.loads('[' + m.group(1) + ']')
                candidates = [x for x in arr if isinstance(x, dict) and _looks_like_event(x)]
                if len(candidates) >= 2:
                    return candidates
            except Exception:
                pass
    return []


def _extract_html_cards(soup) -> list[dict]:
    selectors = [
        "[data-testid='event-card']", ".event-card", ".race-card",
        "article[class*='event']", "article[class*='race']",
        "[class*='EventCard']", "[class*='RaceCard']",
        "li[class*='event']", "li[class*='race']",
        ".search-result", "[class*='SearchResult']",
    ]
    for sel in selectors:
        cards = soup.select(sel)
        if len(cards) >= 2:
            print(f"[{SOURCE_NAME}] HTML selector '{sel}' encontrou {len(cards)} cards")
            return [_card_to_dict(c) for c in cards]
    # Log classes present on the page for diagnosis
    classes = set()
    for el in soup.find_all(class_=True)[:200]:
        for c in el.get("class", []):
            if any(kw in c.lower() for kw in ("event", "race", "card", "result", "listing")):
                classes.add(c)
    if classes:
        print(f"[{SOURCE_NAME}] classes relevantes na página: {sorted(classes)[:20]}")
    return []


def _try_graphql() -> list[dict]:
    try:
        resp = get_with_fallback(_GRAPHQL_URL, source=SOURCE_NAME)
        if resp.status_code == 200:
            data = resp.json()
            print(f"[{SOURCE_NAME}] GraphQL OK: {list(data.keys())[:5]}")
            return _find_event_list(data)
        print(f"[{SOURCE_NAME}] GraphQL HTTP {resp.status_code}")
    except Exception as e:
        print(f"[{SOURCE_NAME}] GraphQL erro: {e}")
    return []


# ---------------------------------------------------------------------------
# Recursive JSON search
# ---------------------------------------------------------------------------
def _find_event_list(obj, depth: int = 0) -> list[dict]:
    if depth > 12:
        return []
    if isinstance(obj, list):
        candidates = [x for x in obj if isinstance(x, dict) and _looks_like_event(x)]
        if len(candidates) >= 2:
            return candidates
    if isinstance(obj, dict):
        for v in obj.values():
            result = _find_event_list(v, depth + 1)
            if result:
                return result
    return []


def _looks_like_event(obj: dict) -> bool:
    keys = {k.lower() for k in obj}
    return any(k in keys for k in ("name", "title", "event_name", "eventname"))


def _card_to_dict(el) -> dict:
    text = el.get_text(" ", strip=True)
    heading = el.find(["h2", "h3", "h4", "strong", "[class*='title']"])
    name = heading.get_text(strip=True) if heading else text[:80]
    link = el.find("a", href=True)
    href = link["href"] if link else ""
    if href and not href.startswith("http"):
        href = BASE + href
    m = re.search(
        r"(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})"
        r"|(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})"
        r"|(\d{1,2})\s+(\w+)\s+(\d{4})",
        text, re.IGNORECASE,
    )
    date_str = None
    if m:
        if m.group(1):
            date_str = f"{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}"
        elif m.group(6):
            date_str = f"{m.group(6)}-{m.group(5).zfill(2)}-{m.group(4).zfill(2)}"
        elif m.group(9):
            mo = _EN_MONTHS.get(m.group(8).lower()[:3])
            if mo:
                date_str = f"{m.group(9)}-{mo}-{m.group(7).zfill(2)}"
    dists = re.findall(r"\b(\d+(?:[.,]\d+)?)\s*km?\b", text, re.IGNORECASE)
    return {"name": name, "date": date_str, "url": href,
            "distances_raw": dists, "text": text}


# ---------------------------------------------------------------------------
# Parse raw item → Corrida
# ---------------------------------------------------------------------------
_FIELD_ALIASES = {
    "name":      ["name", "title", "eventName", "event_name"],
    "date":      ["date", "startDate", "start_date", "eventDate", "event_date",
                  "dateTime", "datetime", "occurrenceDate"],
    "city":      ["city", "location", "town", "venue", "place", "address",
                  "locationName", "location_name"],
    "url":       ["url", "slug", "href", "link", "registrationUrl",
                  "registration_url", "eventUrl", "permalink"],
    "image":     ["image", "imageUrl", "image_url", "heroImage", "thumbnail",
                  "coverImage", "photo"],
    "status":    ["status", "registrationStatus", "registration_status",
                  "entryStatus"],
    "distances": ["distances", "distance", "categories", "distanceCategories"],
}


def _get(obj: dict, key: str):
    for alias in _FIELD_ALIASES.get(key, [key]):
        v = obj.get(alias)
        if v is None:
            continue
        if isinstance(v, str) and v.strip():
            return v.strip()
        if isinstance(v, (int, float)):
            return str(v)
        if isinstance(v, dict):
            for sub in ("name", "label", "value", "title"):
                sv = v.get(sub)
                if isinstance(sv, str) and sv.strip():
                    return sv.strip()
    return None


_ISO_RE   = re.compile(r"(\d{4})[/\-](\d{1,2})[/\-](\d{1,2})")
_DMY_RE   = re.compile(r"(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})")
_WORD_RE  = re.compile(r"(\d{1,2})\s+(\w+)\s+(\d{4})", re.IGNORECASE)


def _parse_date(raw: str) -> str | None:
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
        mo = _EN_MONTHS.get(m.group(2).lower()[:3])
        if mo:
            return f"{m.group(3)}-{mo}-{m.group(1).zfill(2)}"
    if raw.isdigit():
        import datetime
        ts = int(raw)
        if ts > 1e10:
            ts //= 1000
        try:
            return datetime.datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d")
        except Exception:
            pass
    return None


_MARATHON_KW = re.compile(r"\bmarathon\b", re.IGNORECASE)
_HALF_KW     = re.compile(r"\bhalf\b|\bhalf.marathon\b", re.IGNORECASE)
_NON_RUNNING = re.compile(
    r"\bcycl|\bbike\b|\bcycling\b|\btriathlon\b|\bswim\b|\baquath",
    re.IGNORECASE,
)


def _parse_distances(item: dict) -> list[Distancia]:
    seen: set[float] = set()
    result: list[Distancia] = []

    def _add(km: float) -> None:
        for canon, lo, hi in _CANONICAL:
            if lo <= km <= hi:
                km = canon; break
        if km not in seen and 0.5 <= km <= 200:
            seen.add(km); result.append(Distancia(km=km, data=None, horario=None))

    raw = _get(item, "distances")
    if isinstance(raw, list):
        for d in raw:
            if isinstance(d, (int, float)):
                _add(float(d))
            elif isinstance(d, str):
                m = re.search(r"(\d+(?:[.,]\d+)?)", d)
                if m:
                    _add(float(m.group(1).replace(",", ".")))
            elif isinstance(d, dict):
                for k in ("km", "distance", "meters", "length"):
                    v = d.get(k)
                    if isinstance(v, (int, float)):
                        _add(float(v) / (1000 if k == "meters" else 1)); break

    for s in item.get("distances_raw") or []:
        try:
            _add(float(str(s).replace(",", ".")))
        except ValueError:
            pass

    if not result:
        text = (item.get("text") or _get(item, "name") or "")
        has_half     = bool(_HALF_KW.search(text))
        has_marathon = bool(_MARATHON_KW.search(text))
        if has_half and has_marathon:
            _add(21.097); _add(42.195)
        elif has_half:
            _add(21.097)
        elif has_marathon:
            _add(42.195)
        for m in re.finditer(r"\b(\d+(?:[.,]\d+)?)\s*km?\b", text, re.IGNORECASE):
            _add(float(m.group(1).replace(",", ".")))

    return sorted(result, key=lambda d: float(d.km) if isinstance(d.km, (int, float)) else 999)


def _parse_item(item: dict, today: str) -> Corrida | None:
    name_raw = _get(item, "name") or ""
    titulo   = normalize_titulo(name_raw)
    if not titulo or len(titulo) < 4:
        return None

    # Skip non-running events
    if _NON_RUNNING.search(titulo):
        return None

    raw_date    = _get(item, "date") or ""
    data_evento = _parse_date(raw_date)
    if not data_evento or data_evento < today:
        return None

    city_raw    = _get(item, "city") or "Reino Unido"
    localizacao = f"{city_raw}, Reino Unido" if "reino unido" not in city_raw.lower() else city_raw

    url_raw = _get(item, "url") or ""
    if url_raw.startswith("http"):
        link = url_raw
    elif url_raw.startswith("/"):
        link = BASE + url_raw
    else:
        link = f"{BASE}/gb/e/{url_raw}" if url_raw else BASE

    imagem_url = _get(item, "image") or None

    distancias = _parse_distances(item)
    if not distancias:
        return None
    if all(d.km < _MIN_KM for d in distancias if isinstance(d.km, (int, float))):
        return None

    status_raw = (_get(item, "status") or "").lower()
    if any(k in status_raw for k in ("closed", "sold out", "full")):
        inscricoes_abertas: bool | None = False
    elif any(k in status_raw for k in ("open", "available", "register")):
        inscricoes_abertas = True
    else:
        inscricoes_abertas = None

    now  = now_iso()
    year = data_evento[:4]
    return Corrida(
        id=f"ldt_{slugify(titulo)}_{year}",
        titulo=titulo,
        data_evento=data_evento,
        horario=None,
        localizacao=localizacao,
        cidade=localizacao,
        estado="INT",
        distancias=distancias,
        imagem_url=imagem_url,
        inscricoes_abertas=inscricoes_abertas,
        periodo_inscricao=None,
        fontes=[FonteInfo(
            nome=SOURCE_NAME,
            link_evento=link,
            links_inscricao=[link] if inscricoes_abertas else [],
        )],
        miss_count=0,
        first_seen_at=now,
        updated_at=now,
    )
