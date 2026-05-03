"""Scraper for worldsmarathons.com — calendário global de maratonas.

Estratégia:
  1. Fetch da página principal para obter o buildId do Next.js
  2. Fetch de /_next/data/{buildId}/marathons.json para obter dados server-side
  3. Fallback: parsing direto de __NEXT_DATA__ no HTML
  4. Fallback: parsing de cards HTML
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
_MIN_KM     = 10.0

# Pages to try if /_next/data/ approach fails
_FALLBACK_URLS = [
    f"{BASE}/marathons?continent=europe&future=1",
    f"{BASE}/marathons?continent=europe",
    f"{BASE}/marathons",
]

_EN_TO_PT: dict[str, str] = {
    "portugal":          "Portugal",
    "spain":             "Espanha",
    "france":            "França",
    "italy":             "Itália",
    "germany":           "Alemanha",
    "united kingdom":    "Reino Unido",
    "uk":                "Reino Unido",
    "england":           "Reino Unido",
    "scotland":          "Reino Unido",
    "wales":             "Reino Unido",
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

_EU_COUNTRIES = set(_EN_TO_PT.keys())

_ISO2_MAP = {
    "pt": "portugal", "es": "spain", "fr": "france", "it": "italy",
    "de": "germany", "gb": "united kingdom", "uk": "united kingdom",
    "nl": "netherlands", "be": "belgium", "ch": "switzerland",
    "at": "austria", "se": "sweden", "no": "norway", "dk": "denmark",
    "fi": "finland", "ie": "ireland", "gr": "greece", "cz": "czech republic",
    "pl": "poland", "hu": "hungary", "hr": "croatia", "ro": "romania",
    "bg": "bulgaria", "sk": "slovakia", "si": "slovenia", "lu": "luxembourg",
    "ee": "estonia", "lv": "latvia", "lt": "lithuania", "is": "iceland",
    "rs": "serbia", "me": "montenegro", "mk": "north macedonia",
    "al": "albania", "ba": "bosnia", "tr": "turkey", "ua": "ukraine",
}

_CANONICAL = [(42.195, 41.5, 43.0), (21.097, 20.5, 21.5)]


def scrape() -> list[Corrida]:
    today = today_iso()
    raw: list[dict] = []

    # ── Strategy 1: /_next/data/{buildId}/ API ─────────────────────────────
    raw = _try_next_data_api()
    if raw:
        print(f"[{SOURCE_NAME}] {len(raw)} candidatos via /_next/data/")
    else:
        # ── Strategy 2: HTML page parsing (fallback) ────────────────────────
        for url in _FALLBACK_URLS:
            try:
                resp = get(url, source=SOURCE_NAME)
            except Exception as e:
                print(f"[{SOURCE_NAME}] erro ao buscar {url}: {e}")
                continue

            if resp.status_code != 200:
                print(f"[{SOURCE_NAME}] HTTP {resp.status_code} para {url}")
                continue

            print(f"[{SOURCE_NAME}] HTTP 200 para {url} ({len(resp.text)} bytes)")
            soup = BeautifulSoup(resp.text, "lxml")

            raw = _extract_from_any_script(soup)
            if raw:
                print(f"[{SOURCE_NAME}] {len(raw)} candidatos via script JSON")
                break

            raw = _extract_html_cards(soup)
            if raw:
                print(f"[{SOURCE_NAME}] {len(raw)} candidatos via HTML cards")
                break

            print(f"[{SOURCE_NAME}] sem dados reconhecíveis em {url}")

    if not raw:
        print(f"[{SOURCE_NAME}] sem dados — nenhuma estratégia funcionou")
        return []

    corridas: list[Corrida] = []
    skipped_date = skipped_country = skipped_dist = 0

    for item in raw:
        try:
            c, reason = _parse_item(item, today)
            if c:
                corridas.append(c)
            elif reason == "date":
                skipped_date += 1
            elif reason == "country":
                skipped_country += 1
            elif reason == "dist":
                skipped_dist += 1
        except Exception as e:
            name = item.get("name") or item.get("title") or "?"
            print(f"[{SOURCE_NAME}] erro ao parsear '{name}': {e}")

    print(
        f"[{SOURCE_NAME}] {len(corridas)} corridas | "
        f"filtradas: {skipped_date} sem data, {skipped_country} país não-EU, "
        f"{skipped_dist} sem distância"
    )

    _enrich_details(corridas)
    return corridas


# ---------------------------------------------------------------------------
# Strategy 1: /_next/data/{buildId}/ — fetches pre-rendered page props
# ---------------------------------------------------------------------------
def _try_next_data_api() -> list[dict]:
    # First, fetch the main page to find the buildId
    try:
        resp = get(f"{BASE}/marathons?continent=europe&future=1", source=SOURCE_NAME)
    except Exception as e:
        print(f"[{SOURCE_NAME}] erro ao buscar página principal: {e}")
        return []

    if resp.status_code != 200:
        print(f"[{SOURCE_NAME}] HTTP {resp.status_code} na página principal")
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    build_id = _get_build_id(soup)

    if not build_id:
        print(f"[{SOURCE_NAME}] buildId não encontrado")
        return []

    print(f"[{SOURCE_NAME}] buildId={build_id}")

    # Try several page paths for the /_next/data/ API
    data_paths = [
        f"/_next/data/{build_id}/marathons.json?continent=europe&future=1",
        f"/_next/data/{build_id}/marathons.json?continent=europe",
        f"/_next/data/{build_id}/marathons.json",
        f"/_next/data/{build_id}/index.json?continent=europe&future=1",
        f"/_next/data/{build_id}/races.json?continent=europe&future=1",
    ]

    for path in data_paths:
        url = BASE + path
        try:
            resp = get(url, timeout=15)
        except Exception:
            continue

        if resp.status_code != 200:
            continue

        try:
            data = resp.json()
        except Exception:
            continue

        print(f"[{SOURCE_NAME}] _next/data OK: {url} ({len(resp.text)} bytes)")
        raw = _find_race_list(data)
        if raw:
            return raw
        # Log top-level keys to aid debugging if structure not recognized
        if isinstance(data, dict):
            pprops = data.get("pageProps", {})
            print(f"[{SOURCE_NAME}] pageProps keys: {list(pprops.keys())[:10] if isinstance(pprops, dict) else type(pprops)}")

    return []


def _get_build_id(soup) -> str | None:
    # 1. Try __NEXT_DATA__ JSON directly
    tag = soup.find("script", id="__NEXT_DATA__")
    if tag:
        try:
            data = json.loads(tag.string or "")
            build_id = data.get("buildId")
            if build_id:
                return build_id
        except Exception:
            pass

    # 2. Extract from /_next/static/{buildId}/ in script src attrs
    for script in soup.find_all("script", src=True):
        m = re.search(r'/_next/static/([^/]+)/', script["src"])
        if m:
            return m.group(1)

    # 3. Look in inline scripts
    for script in soup.find_all("script"):
        if not script.string:
            continue
        m = re.search(r'"buildId"\s*:\s*"([^"]+)"', script.string)
        if m:
            return m.group(1)

    return None


# ---------------------------------------------------------------------------
# Strategy 2: look in all script tags for embedded JSON race data
# ---------------------------------------------------------------------------
def _extract_from_any_script(soup) -> list[dict]:
    # Try __NEXT_DATA__ first
    tag = soup.find("script", id="__NEXT_DATA__")
    if tag:
        try:
            data = json.loads(tag.string or "")
            result = _find_race_list(data)
            if result:
                return result
            # Log structure for debugging
            if isinstance(data, dict):
                pprops = data.get("pageProps", {})
                print(f"[{SOURCE_NAME}] __NEXT_DATA__ encontrado, pageProps keys: "
                      f"{list(pprops.keys())[:10] if isinstance(pprops, dict) else type(pprops)}")
        except Exception:
            pass

    # Try all other script tags with JSON content
    for script in soup.find_all("script"):
        content = script.string or ""
        if len(content) < 100 or '"name"' not in content:
            continue
        # Look for JSON arrays
        for m in re.finditer(r'\[(\s*\{[^[\]]{20,})\]', content):
            try:
                arr = json.loads('[' + m.group(1) + ']')
                candidates = [x for x in arr if isinstance(x, dict) and _looks_like_race(x)]
                if len(candidates) >= 2:
                    return candidates
            except Exception:
                pass

    return []


# ---------------------------------------------------------------------------
# __NEXT_DATA__ recursive search
# ---------------------------------------------------------------------------
def _find_race_list(obj, depth: int = 0) -> list[dict]:
    if depth > 12:
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
    return any(k in keys for k in (
        "name", "title", "race_name", "marathon_name", "event_name", "nome",
    ))


# ---------------------------------------------------------------------------
# HTML card extraction (last resort fallback)
# ---------------------------------------------------------------------------
_CARD_SELECTORS = [
    ".race-card", ".marathon-card", ".event-card", ".race-item",
    "article.race", "article.marathon", "article.event",
    ".races-list .item", ".marathons-list .item",
    "[class*='race-item']", "[class*='marathon-item']", "[class*='event-item']",
    "li.race", "li.event", "li.marathon",
    "tr[data-race]", "tr[data-id]",
]

_DATE_RE = re.compile(
    r"(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})"
    r"|(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})"
    r"|(\d{1,2})\s+(\w+)\s+(\d{4})",
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
    date_str = None
    m = _DATE_RE.search(text)
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
# Parse a raw race dict → Corrida
# ---------------------------------------------------------------------------
_FIELD_ALIASES: dict[str, list[str]] = {
    "name":      ["name", "title", "race_name", "marathon_name", "event_name", "Nome"],
    "date":      ["date", "start_date", "event_date", "race_date", "startDate",
                  "datetime", "data", "next_date", "nextDate", "next_event_date",
                  "raceDate", "eventDate"],
    "city":      ["city", "cidade", "location", "town", "venue", "place", "city_name",
                  "cityName"],
    "country":   ["country", "country_name", "pais", "nation", "countryName"],
    "url":       ["url", "website", "link", "href", "registration_url", "entry_url",
                  "slug", "permalink", "raceUrl"],
    "image":     ["image", "logo", "photo", "img", "banner", "cover", "imageUrl",
                  "image_url", "logoUrl", "thumbnail", "photo_url"],
    "status":    ["status", "registration_status", "entry_status", "state",
                  "registration_state"],
    "distances": ["distances", "distancias", "categories", "events", "races",
                  "race_types", "raceTypes"],
}


def _get(obj: dict, key: str) -> str | None:
    for alias in _FIELD_ALIASES.get(key, [key]):
        v = obj.get(alias)
        if v is None:
            continue
        if isinstance(v, str) and v.strip():
            return v.strip()
        if isinstance(v, (int, float)):
            return str(v)
        if isinstance(v, dict):
            for subkey in ("name", "label", "title", "value", "en"):
                sv = v.get(subkey)
                if isinstance(sv, str) and sv.strip():
                    return sv.strip()
    return None


def _parse_item(item: dict, today: str) -> tuple[Corrida | None, str]:
    name_raw = _get(item, "name") or ""
    titulo = normalize_titulo(name_raw)
    if not titulo or len(titulo) < 4:
        return None, "name"

    raw_date = _get(item, "date") or ""
    data_evento = _parse_date(raw_date)
    if not data_evento or data_evento < today:
        return None, "date"

    country_raw = (_get(item, "country") or "").lower().strip()
    if country_raw and country_raw not in _EU_COUNTRIES:
        resolved = _ISO2_MAP.get(country_raw, country_raw)
        if resolved not in _EU_COUNTRIES:
            return None, "country"
        country_raw = resolved

    country_pt = _EN_TO_PT.get(country_raw, "") if country_raw else ""
    city_raw   = _get(item, "city") or ""
    localizacao = f"{city_raw}, {country_pt}".strip(", ") if city_raw and country_pt else (city_raw or country_pt or "Europa")
    cidade = localizacao

    url_raw = _get(item, "url") or ""
    if url_raw.startswith("http"):
        link = url_raw
    elif url_raw:
        link = BASE + "/" + url_raw.lstrip("/")
    else:
        link = BASE

    imagem_url = _get(item, "image") or None

    distancias = _parse_distances(item)
    if not distancias:
        return None, "dist"
    if all(d.km < _MIN_KM for d in distancias if isinstance(d.km, (int, float))):
        return None, "dist"

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
        cidade=cidade,
        estado="INT",
        distancias=distancias,
        imagem_url=imagem_url,
        inscricoes_abertas=inscricoes_abertas,
        periodo_inscricao=None,
        fontes=[fonte],
        miss_count=0,
        first_seen_at=now,
        updated_at=now,
    ), "ok"


_ISO_DATE_RE   = re.compile(r"(\d{4})[/\-](\d{1,2})[/\-](\d{1,2})")
_BR_DATE_RE    = re.compile(r"(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})")
_WORDS_DATE_RE = re.compile(r"(\d{1,2})\s+(\w+)\s+(\d{4})", re.IGNORECASE)

_MARATHON_KW = re.compile(
    r"\bmarathon\b|\bmaratona\b|\bmaratón\b|\bmaratonin\b",
    re.IGNORECASE,
)
_HALF_KW = re.compile(
    r"\bhalf\b|\bmeia\b|\bmedia\b|\bhalbmarathon\b|\bsemi\b",
    re.IGNORECASE,
)


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

    raw_dists = (
        item.get("distances") or item.get("categories") or
        item.get("events") or item.get("races") or
        item.get("race_types") or []
    )
    if isinstance(raw_dists, list):
        for d in raw_dists:
            if isinstance(d, (int, float)):
                _add(float(d))
            elif isinstance(d, str):
                m = re.search(r"(\d+(?:[.,]\d+)?)", d)
                if m:
                    _add(float(m.group(1).replace(",", ".")))
            elif isinstance(d, dict):
                for k in ("km", "distance", "length", "distancia", "distance_km", "meters"):
                    v = d.get(k)
                    if isinstance(v, (int, float)):
                        _add(float(v) / (1000 if k == "meters" else 1)); break
                    if isinstance(v, str):
                        m = re.search(r"(\d+(?:[.,]\d+)?)", v)
                        if m:
                            _add(float(m.group(1).replace(",", "."))); break

    for s in item.get("distances_raw") or []:
        try:
            _add(float(str(s).replace(",", ".")))
        except ValueError:
            pass

    if not result:
        text = (item.get("text") or item.get("name") or item.get("title") or "")
        text_lower = text.lower()
        has_half    = _HALF_KW.search(text)
        has_marathon = _MARATHON_KW.search(text)
        if has_half and has_marathon:
            _add(21.097); _add(42.195)
        elif has_half:
            _add(21.097)
        elif has_marathon:
            _add(42.195)
        for m in re.finditer(r"\b(\d+(?:[.,]\d+)?)\s*km?\b", text, re.IGNORECASE):
            _add(float(m.group(1).replace(",", ".")))

    return sorted(result, key=lambda d: float(d.km) if isinstance(d.km, (int, float)) else 999)


# ---------------------------------------------------------------------------
# Detail enrichment (optional)
# ---------------------------------------------------------------------------
def _enrich_details(corridas: list[Corrida]) -> None:
    to_enrich = [c for c in corridas if c.horario is None and c.inscricoes_abertas is None]
    if not to_enrich:
        return

    def _fetch(c: Corrida) -> None:
        url = c.fontes[0].link_evento
        if not url or url == BASE:
            return
        try:
            resp = get(url, timeout=10)
            if resp.status_code != 200:
                return
            soup = BeautifulSoup(resp.text, "lxml")
            text = soup.get_text(" ").lower()
            if any(k in text for k in ("registration closed", "sold out", "inscriptions closed")):
                c.inscricoes_abertas = False
                c.fontes[0].links_inscricao = []
            elif any(k in text for k in ("register now", "sign up", "register", "entry open")):
                c.inscricoes_abertas = True
                c.fontes[0].links_inscricao = [url]
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
        for f in as_completed([ex.submit(_fetch, c) for c in to_enrich[:20]]):
            pass
