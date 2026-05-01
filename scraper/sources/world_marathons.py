"""Scraper for worldsmarathons.com — calendário global de maratonas.

Estratégia:
  1. Fetch da página de corridas europeias (continent=europe)
  2. Extração via __NEXT_DATA__ (site Next.js)
  3. Fallback: parsing de cards HTML

Filtra por distâncias ≥ 10 km e exclui países fora da Europa.
"""
from __future__ import annotations
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

from bs4 import BeautifulSoup

from ..http_client import get
from ..models import Corrida, Distancia, FonteInfo
from ..utils import normalize_titulo, slugify, now_iso, today_iso

BASE        = "https://worldsmarathons.com"
SOURCE_NAME = "World Marathons"

# Pages to fetch — broader first, narrower as fallback
_CALENDAR_URLS = [
    f"{BASE}/marathons?continent=europe&future=1",
    f"{BASE}/marathons?continent=europe",
    f"{BASE}/races?continent=europe",
    f"{BASE}/marathons",   # all, then filter locally
]

# Minimum distance to include (avoid 5K fun runs)
_MIN_KM = 10.0

# English country name → Portuguese (for localizacao)
_EN_TO_PT: dict[str, str] = {
    "portugal":          "Portugal",
    "spain":             "Espanha",
    "france":            "França",
    "italy":             "Itália",
    "germany":           "Alemanha",
    "united kingdom":    "Reino Unido",
    "uk":                "Reino Unido",
    "england":           "Reino Unido",
    "netherlands":       "Países Baixos",
    "holland":           "Países Baixos",
    "belgium":           "Bélgica",
    "switzerland":       "Suíça",
    "austria":           "Áustria",
    "sweden":            "Suécia",
    "norway":            "Noruega",
    "denmark":           "Dinamarca",
    "finland":           "Finlândia",
    "ireland":           "Irlanda",
    "greece":            "Grécia",
    "czech republic":    "República Tcheca",
    "czechia":           "República Tcheca",
    "poland":            "Polônia",
    "hungary":           "Hungria",
    "croatia":           "Croácia",
    "romania":           "Romênia",
    "bulgaria":          "Bulgária",
    "slovakia":          "Eslováquia",
    "slovenia":          "Eslovênia",
    "luxembourg":        "Luxemburgo",
    "malta":             "Malta",
    "cyprus":            "Chipre",
    "estonia":           "Estônia",
    "latvia":            "Letônia",
    "lithuania":         "Lituânia",
    "iceland":           "Islândia",
    "monaco":            "Mônaco",
    "serbia":            "Sérvia",
    "montenegro":        "Montenegro",
    "north macedonia":   "Macedônia do Norte",
    "albania":           "Albânia",
    "bosnia":            "Bósnia",
    "turkey":            "Turquia",
    "russia":            "Rússia",
    "ukraine":           "Ucrânia",
    "moldova":           "Moldávia",
    "belarus":           "Bielorrússia",
}

# European country set (lowercase) for filtering
_EU_COUNTRIES = set(_EN_TO_PT.keys())

_CANONICAL = [(42.195, 41.5, 43.0), (21.097, 20.5, 21.5)]


def scrape() -> list[Corrida]:
    today = today_iso()
    raw: list[dict] = []

    for url in _CALENDAR_URLS:
        try:
            resp = get(url, timeout=12)
        except Exception as e:
            print(f"[{SOURCE_NAME}] erro ao buscar {url}: {e}")
            continue

        if resp.status_code != 200:
            continue

        soup = BeautifulSoup(resp.text, "lxml")

        # Strategy 1: __NEXT_DATA__
        raw = _extract_next_data(soup)
        if raw:
            break

        # Strategy 2: HTML cards
        raw = _extract_html_cards(soup)
        if raw:
            break

    if not raw:
        print(f"[{SOURCE_NAME}] sem dados — site inacessível ou estrutura mudou")
        return []

    corridas: list[Corrida] = []
    for item in raw:
        try:
            c = _parse_item(item, today)
            if c:
                corridas.append(c)
        except Exception as e:
            print(f"[{SOURCE_NAME}] erro ao parsear '{item.get('name', item.get('title', '?'))}': {e}")

    # Enrich with detail pages (up to 6 in parallel)
    _enrich_details(corridas)

    print(f"[{SOURCE_NAME}] {len(corridas)} corridas europeias encontradas")
    return corridas


# ---------------------------------------------------------------------------
# __NEXT_DATA__ extraction
# ---------------------------------------------------------------------------
def _extract_next_data(soup) -> list[dict]:
    tag = soup.find("script", id="__NEXT_DATA__")
    if not tag:
        return []
    try:
        data = json.loads(tag.string or "")
    except Exception:
        return []

    # Recursively find the first list of race-like objects
    return _find_race_list(data)


def _find_race_list(obj, depth: int = 0) -> list[dict]:
    if depth > 8:
        return []
    if isinstance(obj, list):
        candidates = [x for x in obj if isinstance(x, dict) and _looks_like_race(x)]
        if len(candidates) >= 2:
            return candidates
    if isinstance(obj, dict):
        for v in obj.values():
            result = _find_race_list(v, depth + 1)
            if result:
                return result
    return []


def _looks_like_race(obj: dict) -> bool:
    keys = {k.lower() for k in obj}
    has_name = any(k in keys for k in ("name", "title", "race_name", "marathon_name", "event_name"))
    has_date = any(k in keys for k in ("date", "start_date", "event_date", "race_date", "datetime"))
    return has_name and has_date


# ---------------------------------------------------------------------------
# HTML card extraction (fallback)
# ---------------------------------------------------------------------------
_CARD_SELECTORS = [
    ".race-card", ".marathon-card", ".event-card",
    "article.race", "article.marathon", "article.event",
    ".races-list .item", ".marathons-list .item",
    "[class*='race-item']", "[class*='marathon-item']",
    "li.race", "li.event",
]

_DATE_RE = re.compile(
    r"(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})"          # YYYY-MM-DD
    r"|(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})"          # DD/MM/YYYY
    r"|(\d{1,2})\s+(\w+)\s+(\d{4})",                   # DD Month YYYY
    re.IGNORECASE,
)
_EN_MONTHS = {
    "jan": "01", "feb": "02", "mar": "03", "apr": "04",
    "may": "05", "jun": "06", "jul": "07", "aug": "08",
    "sep": "09", "oct": "10", "nov": "11", "dec": "12",
    "january": "01", "february": "02", "march": "03", "april": "04",
    "june": "06", "july": "07", "august": "08", "september": "09",
    "october": "10", "november": "11", "december": "12",
}


def _extract_html_cards(soup) -> list[dict]:
    for sel in _CARD_SELECTORS:
        cards = soup.select(sel)
        if len(cards) >= 3:
            return [_html_card_to_dict(c) for c in cards]
    return []


def _html_card_to_dict(el) -> dict:
    text = el.get_text(" ", strip=True)
    heading = el.find(["h2", "h3", "h4", "strong"])
    name = heading.get_text(strip=True) if heading else text[:80]
    link = el.find("a", href=True)
    href = link["href"] if link else ""
    if href and not href.startswith("http"):
        href = BASE + href

    # Date
    date_str = None
    m = _DATE_RE.search(text)
    if m:
        if m.group(1):  # YYYY-MM-DD
            date_str = f"{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}"
        elif m.group(6):  # DD/MM/YYYY
            date_str = f"{m.group(6)}-{m.group(5).zfill(2)}-{m.group(4).zfill(2)}"
        elif m.group(9):  # DD Month YYYY
            mo = _EN_MONTHS.get(m.group(8).lower()[:3])
            if mo:
                date_str = f"{m.group(9)}-{mo}-{m.group(7).zfill(2)}"

    # Distances
    dists = re.findall(r"\b(\d+(?:[.,]\d+)?)\s*km?\b", text, re.IGNORECASE)

    return {"name": name, "date": date_str, "url": href,
            "distances_raw": dists, "text": text}


# ---------------------------------------------------------------------------
# Parse a raw race dict → Corrida
# ---------------------------------------------------------------------------
_FIELD_ALIASES: dict[str, list[str]] = {
    "name":     ["name", "title", "race_name", "marathon_name", "event_name", "Nome"],
    "date":     ["date", "start_date", "event_date", "race_date", "startDate", "datetime", "data"],
    "city":     ["city", "cidade", "location", "town", "venue", "place"],
    "country":  ["country", "country_name", "pais", "nation"],
    "url":      ["url", "website", "link", "href", "registration_url", "entry_url", "slug"],
    "image":    ["image", "logo", "photo", "img", "banner", "cover", "imageUrl", "logoUrl"],
    "status":   ["status", "registration_status", "entry_status", "state"],
    "distances": ["distances", "distancias", "categories", "events"],
}


def _get(obj: dict, key: str) -> str | None:
    for alias in _FIELD_ALIASES.get(key, [key]):
        v = obj.get(alias)
        if v is not None:
            if isinstance(v, str) and v.strip():
                return v.strip()
            if isinstance(v, (int, float)):
                return str(v)
    return None


def _parse_item(item: dict, today: str) -> Corrida | None:
    name_raw = _get(item, "name") or ""
    titulo = normalize_titulo(name_raw)
    if not titulo or len(titulo) < 4:
        return None

    # Date
    raw_date = _get(item, "date") or ""
    data_evento = _parse_date(raw_date)
    if not data_evento or data_evento < today:
        return None

    # Country / location
    country_raw = (_get(item, "country") or "").lower().strip()
    if country_raw and country_raw not in _EU_COUNTRIES:
        return None   # skip non-European

    country_pt = _EN_TO_PT.get(country_raw, country_raw.title() if country_raw else "Europa")
    city_raw   = _get(item, "city") or ""
    localizacao = f"{city_raw}, {country_pt}".strip(", ") if city_raw else country_pt

    # Link
    url_raw = _get(item, "url") or ""
    link = url_raw if url_raw.startswith("http") else (BASE + "/" + url_raw.lstrip("/") if url_raw else BASE)

    # Image
    imagem_url = _get(item, "image") or None

    # Distances
    distancias = _parse_distances(item)
    if not distancias:
        return None   # no usable distance info
    if all(d.km < _MIN_KM for d in distancias if isinstance(d.km, (int, float))):
        return None   # only very short distances

    # Registration status
    status_raw = (_get(item, "status") or "").lower()
    if any(k in status_raw for k in ("closed", "sold out", "encerrad", "esgotad")):
        inscricoes_abertas: bool | None = False
    elif any(k in status_raw for k in ("open", "aberto", "aberta", "available")):
        inscricoes_abertas = True
    else:
        inscricoes_abertas = None

    now  = now_iso()
    year = data_evento[:4]
    fonte = FonteInfo(
        nome=SOURCE_NAME,
        link_evento=link,
        links_inscricao=[link] if inscricoes_abertas else [],
    )

    return Corrida(
        id=f"wm_{slugify(titulo)}_{year}",
        titulo=titulo,
        data_evento=data_evento,
        horario=None,
        localizacao=localizacao,
        cidade=city_raw or localizacao,
        estado="INT",
        distancias=distancias,
        imagem_url=imagem_url,
        inscricoes_abertas=inscricoes_abertas,
        periodo_inscricao=None,
        fontes=[fonte],
        miss_count=0,
        first_seen_at=now,
        updated_at=now,
    )


_ISO_DATE_RE   = re.compile(r"(\d{4})[/\-](\d{1,2})[/\-](\d{1,2})")
_BR_DATE_RE    = re.compile(r"(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})")
_WORDS_DATE_RE = re.compile(r"(\d{1,2})\s+(\w+)\s+(\d{4})", re.IGNORECASE)


def _parse_date(raw: str) -> str | None:
    if not raw:
        return None
    m = _ISO_DATE_RE.search(raw)
    if m:
        return f"{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}"
    m = _BR_DATE_RE.search(raw)
    if m:
        return f"{m.group(3)}-{m.group(2).zfill(2)}-{m.group(1).zfill(2)}"
    m = _WORDS_DATE_RE.search(raw)
    if m:
        mo = _EN_MONTHS.get(m.group(2).lower()[:3])
        if mo:
            return f"{m.group(3)}-{mo}-{m.group(1).zfill(2)}"
    # Epoch ms / seconds
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


def _canonicalize(km: float) -> float:
    for canon, lo, hi in _CANONICAL:
        if lo <= km <= hi:
            return canon
    return km


def _parse_distances(item: dict) -> list[Distancia]:
    seen: set[float] = set()
    result: list[Distancia] = []

    def _add(km: float) -> None:
        km = _canonicalize(km)
        if km not in seen and 1 <= km <= 200:
            seen.add(km)
            result.append(Distancia(km=km, data=None, horario=None))

    # From structured distances list
    raw_dists = item.get("distances") or item.get("categories") or item.get("events") or []
    if isinstance(raw_dists, list):
        for d in raw_dists:
            if isinstance(d, (int, float)):
                _add(float(d))
            elif isinstance(d, str):
                m = re.search(r"(\d+(?:[.,]\d+)?)", d)
                if m:
                    _add(float(m.group(1).replace(",", ".")))
            elif isinstance(d, dict):
                for k in ("km", "distance", "length", "distancia"):
                    v = d.get(k)
                    if isinstance(v, (int, float)):
                        _add(float(v)); break
                    if isinstance(v, str):
                        m = re.search(r"(\d+(?:[.,]\d+)?)", v)
                        if m:
                            _add(float(m.group(1).replace(",", "."))); break

    # From raw_distances_raw (HTML card fallback)
    for s in item.get("distances_raw") or []:
        try:
            _add(float(str(s).replace(",", ".")))
        except ValueError:
            pass

    # From text fallback
    if not result:
        text = item.get("text") or item.get("name") or ""
        text_lower = text.lower()
        if "meia maratona" in text_lower or "half marathon" in text_lower:
            _add(21.097)
        if re.search(r"(?<!half )(?<!meia )\bmarathon\b|\bmaratona\b", text_lower):
            _add(42.195)
        for m in re.finditer(r"\b(\d+(?:[.,]\d+)?)\s*km?\b", text, re.IGNORECASE):
            _add(float(m.group(1).replace(",", ".")))

    return sorted(result, key=lambda d: float(d.km) if isinstance(d.km, (int, float)) else 999)


# ---------------------------------------------------------------------------
# Detail enrichment (optional — fills horario and status)
# ---------------------------------------------------------------------------
def _enrich_details(corridas: list[Corrida]) -> None:
    # Only enrich if the basic scrape gave us no horario/status for big events
    to_enrich = [c for c in corridas if c.horario is None and c.inscricoes_abertas is None]
    if not to_enrich:
        return

    def _fetch(c: Corrida) -> None:
        fonte = c.fontes[0]
        url = fonte.link_evento
        if not url or url == BASE:
            return
        try:
            resp = get(url, timeout=10)
            if resp.status_code != 200:
                return
            soup = BeautifulSoup(resp.text, "lxml")
            text = soup.get_text(" ").lower()

            # Status
            if any(k in text for k in ("registration closed", "sold out", "inscriptions closed")):
                c.inscricoes_abertas = False
                fonte.links_inscricao = []
            elif any(k in text for k in ("register now", "sign up", "register", "entry open")):
                c.inscricoes_abertas = True
                fonte.links_inscricao = [url]

            # Horario: look for "HH:MM" or "HHhMM" near "start"
            m = re.search(r"\bstart[^.]*?(\d{1,2})[h:](\d{2})\b", text, re.IGNORECASE)
            if not m:
                m = re.search(r"(\d{1,2})[h:](\d{2})\b", text)
            if m:
                h = int(m.group(1))
                if 4 <= h <= 12:
                    c.horario = f"{h:02d}:{m.group(2)}"
        except Exception:
            pass

    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = [ex.submit(_fetch, c) for c in to_enrich[:20]]  # cap at 20
        for f in as_completed(futs):
            pass
