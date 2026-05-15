"""Scraper for Let's Do This (letsdothis.com) — UK/global sports event platform.

Let's Do This is a UK-based platform covering running, cycling, triathlon,
swimming and other sports.  Strict inclusion/exclusion filters are mandatory.

Strategy: hit the public events search API (REST or GraphQL) filtered to the
"running" category, paginate through results, and apply keyword filters to
reject any non-running events that slip through category tags.

Mile distances are preserved as strings ("N mi") per project convention.
"""
from __future__ import annotations
import re
from datetime import date, timedelta

from ..http_client import get
from ..models import Corrida, Distancia, FonteInfo
from ..utils import normalize_titulo, slugify, now_iso, today_iso
from .. import geo as _geo

BASE        = "https://www.letsdothis.com"
API_BASE    = "https://api.letsdothis.com"
SOURCE_NAME = "Let's Do This"

_LOOKAHEAD_DAYS   = 365
_RESULTS_PER_PAGE = 24
_MAX_PAGES        = 30   # up to 720 events

# Running-inclusive keywords — at least one must be present
_RUNNING_KW = re.compile(
    r"\b(run|running|race|marathon|half[\s\-]?marathon|5k|10k|15k|20k|21k|42k"
    r"|ultra|trail|fun\s*run|colour\s*run|color\s*run|mud\s*run|obstacle\s*run"
    r"|park\s*run|parkrun|road\s*race|cross[\s\-]?country)\b",
    re.IGNORECASE,
)

# Non-running keywords — any match rejects the event
_NON_RUNNING = re.compile(
    r"\b(triathlon|duathlon|aquathlon|aquabike|ironman|swim\b|swimming"
    r"|open\s*water|cycling|cycle|cyclist|bike\s*ride|sportive|gran\s*fondo"
    r"|granfondo|paddle|kayak|canoe|rowing|yoga|pilates|golf|tennis"
    r"|football|soccer|rugby|cricket|hockey|basketball|crossfit"
    r"|spartan|obstacle\s*course|ocr|adventure\s*race"
    r"|tower\s*run|stair\s*climb|ski|snowshoe)\b",
    re.IGNORECASE,
)

# ISO-2 → Portuguese country name
_ISO_TO_PT: dict[str, str] = {
    "GB": "Reino Unido",  "US": "EUA",           "AU": "Austrália",
    "IE": "Irlanda",      "DE": "Alemanha",       "FR": "França",
    "ES": "Espanha",      "IT": "Itália",          "NL": "Países Baixos",
    "BE": "Bélgica",      "CH": "Suíça",          "AT": "Áustria",
    "SE": "Suécia",       "NO": "Noruega",         "DK": "Dinamarca",
    "FI": "Finlândia",    "PT": "Portugal",        "ZA": "África do Sul",
    "CA": "Canadá",       "NZ": "Nova Zelândia",   "JP": "Japão",
    "SG": "Singapura",    "IN": "Índia",           "AE": "Emirados Árabes",
}

# UK admin regions → subdivision codes (for the location filter)
_UK_REGION_CODES: dict[str, str] = {
    "england":              "ENG", "london":               "LND",
    "greater london":       "LND", "scotland":             "SCT",
    "wales":                "WLS", "northern ireland":     "NIR",
    "yorkshire":            "YOR", "lancashire":           "LAN",
    "manchester":           "MAN", "kent":                 "KEN",
    "surrey":               "SUR", "essex":                "ESS",
    "hampshire":            "HAM", "west yorkshire":       "WYK",
    "south yorkshire":      "SYK", "west midlands":        "WMD",
    "east midlands":        "EMD", "east of england":      "EAE",
    "south west":           "SWE", "south east":           "SEE",
    "north east":           "NEE", "north west":           "NWE",
}


def scrape() -> list[Corrida]:
    today_s = today_iso()
    start   = date.today().strftime("%Y-%m-%d")
    end     = (date.today() + timedelta(days=_LOOKAHEAD_DAYS)).strftime("%Y-%m-%d")

    raw_events = _fetch_all_events(start, end)
    print(f"[{SOURCE_NAME}] {len(raw_events)} eventos brutos")

    corridas: list[Corrida] = []
    skipped = 0
    for ev in raw_events:
        c = _parse_event(ev, today_s)
        if c:
            corridas.append(c)
        else:
            skipped += 1

    print(f"[{SOURCE_NAME}] {len(corridas)} corridas válidas ({skipped} ignoradas)")
    return corridas


def _fetch_all_events(start: str, end: str) -> list[dict]:
    result: list[dict] = []
    for page in range(1, _MAX_PAGES + 1):
        batch = _fetch_page(page, start, end)
        if batch is None:
            break
        events = _extract_events(batch)
        if not events:
            break
        result.extend(events)
        total = _extract_total(batch)
        print(f"[{SOURCE_NAME}] página {page}: {len(events)} eventos (total≈{total})")
        if len(events) < _RESULTS_PER_PAGE or (total and len(result) >= total):
            break
    return result


def _fetch_page(page: int, start: str, end: str) -> dict | None:
    # Primary: REST API
    for url, params in [
        (
            f"{API_BASE}/v1/events",
            {
                "category": "running",
                "start_date": start,
                "end_date": end,
                "page": page,
                "per_page": _RESULTS_PER_PAGE,
                "sort": "date_asc",
            },
        ),
        (
            f"{API_BASE}/v2/events",
            {
                "activity": "running",
                "from":     start,
                "to":       end,
                "page":     page,
                "limit":    _RESULTS_PER_PAGE,
            },
        ),
        (
            f"{BASE}/api/events",
            {
                "category": "running",
                "from":     start,
                "to":       end,
                "page":     page,
                "limit":    _RESULTS_PER_PAGE,
            },
        ),
    ]:
        try:
            resp = get(url, params=params, source=SOURCE_NAME, timeout=30)
        except Exception as e:
            print(f"[{SOURCE_NAME}] erro {url}: {e}")
            continue

        if resp.status_code == 200:
            try:
                data = resp.json()
                if data and (
                    isinstance(data, list)
                    or data.get("events")
                    or data.get("data")
                    or data.get("results")
                ):
                    print(f"[{SOURCE_NAME}] API ativa: {url}")
                    return data
            except Exception:
                pass
        elif page == 1:
            print(f"[{SOURCE_NAME}] {url} → HTTP {resp.status_code}")

    return None


def _extract_events(data) -> list[dict]:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("events", "data", "results", "items"):
            v = data.get(key)
            if isinstance(v, list):
                return v
    return []


def _extract_total(data) -> int:
    if isinstance(data, dict):
        for key in ("total", "total_count", "count", "totalCount"):
            v = data.get(key)
            if isinstance(v, int):
                return v
        meta = data.get("meta") or data.get("pagination") or {}
        if isinstance(meta, dict):
            return meta.get("total") or meta.get("count") or 0
    return 0


# ---------------------------------------------------------------------------
_MI_RE = re.compile(r"(\d+(?:\.\d+)?)\s*mi(?:le)?\b", re.IGNORECASE)
_KM_RE = re.compile(r"(\d+(?:\.\d+)?)\s*k(?:m)?\b",   re.IGNORECASE)


def _parse_distances(ev: dict) -> list[Distancia]:
    seen: set = set()
    result: list[Distancia] = []

    # Structured distances: sub-events array
    for sub in (ev.get("distances") or ev.get("sub_events") or ev.get("races") or []):
        if not isinstance(sub, dict):
            continue
        label = (sub.get("name") or sub.get("label") or "").lower()
        raw   = sub.get("distance") or sub.get("distance_km")
        unit  = (sub.get("unit") or sub.get("distance_unit") or "").lower()
        km    = _resolve_km(raw, unit, label)
        if km is not None and km not in seen:
            seen.add(km)
            result.append(Distancia(km=km, data=None, horario=None))

    # Distance from a top-level field
    if not result:
        raw   = ev.get("distance") or ev.get("distance_km")
        unit  = (ev.get("unit") or ev.get("distance_unit") or "").lower()
        label = (ev.get("name") or ev.get("title") or "").lower()
        km    = _resolve_km(raw, unit, label)
        if km is not None and km not in seen:
            seen.add(km)
            result.append(Distancia(km=km, data=None, horario=None))

    # Extract from event title
    if not result:
        name = (ev.get("name") or ev.get("title") or "").lower()
        result = _parse_distance_from_name(name, seen)

    return result


def _resolve_km(raw, unit: str, label: str) -> float | str | None:
    # Named canonical distances
    if "marathon" in label and "half" not in label:
        return 42.195
    if "half" in label and "marathon" in label:
        return 21.097

    if raw is not None:
        try:
            n = float(raw)
            if "mi" in unit or "mile" in unit:
                return f"{int(n) if n == int(n) else n:g} mi"
            if 1 <= n <= 250:
                return n
        except (ValueError, TypeError):
            pass

    # Parse numeric from label
    m = _MI_RE.search(label)
    if m:
        n = float(m.group(1))
        return f"{int(n) if n == int(n) else n:g} mi"
    m = _KM_RE.search(label)
    if m:
        n = float(m.group(1))
        return n if 1 <= n <= 250 else None
    return None


def _parse_distance_from_name(name: str, seen: set) -> list[Distancia]:
    result: list[Distancia] = []
    if "marathon" in name and "half" not in name and 42.195 not in seen:
        result.append(Distancia(km=42.195, data=None, horario=None))
        seen.add(42.195)
    if ("half" in name and "marathon" in name) and 21.097 not in seen:
        result.append(Distancia(km=21.097, data=None, horario=None))
        seen.add(21.097)
    for m in _MI_RE.finditer(name):
        n   = float(m.group(1))
        key = f"{int(n) if n == int(n) else n:g} mi"
        if key not in seen:
            seen.add(key)
            result.append(Distancia(km=key, data=None, horario=None))
    for m in _KM_RE.finditer(name):
        n = float(m.group(1))
        if 1 <= n <= 250 and n not in seen:
            seen.add(n)
            result.append(Distancia(km=n, data=None, horario=None))
    return result


def _parse_date(ev: dict) -> str | None:
    for key in ("start_date", "date", "event_date", "starts_at", "from"):
        raw = ev.get(key)
        if not raw:
            continue
        m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})", str(raw).strip())
        if m:
            return f"{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}"
    return None


def _parse_location(ev: dict) -> tuple[str, str, str, str]:
    """Returns (localizacao, cidade, estado, pais_iso2)."""
    location = ev.get("location") or ev.get("venue") or {}
    if isinstance(location, str):
        # Plain string location — use as-is
        return location, location, "", "GB"

    city    = (location.get("city") or location.get("town") or ev.get("city") or "").strip()
    region  = (location.get("region") or location.get("county") or location.get("state") or "").strip()
    country = (location.get("country") or location.get("country_code") or ev.get("country") or "GB").strip().upper()

    pais = country if len(country) == 2 else "GB"

    if pais == "GB":
        region_lower = region.lower()
        estado = _UK_REGION_CODES.get(region_lower, "")
        if not estado and city:
            _, estado = _geo.resolve(city, "", "GB")
        country_pt = "Reino Unido"
    elif pais == "US":
        estado = _geo.validate_estado("US", region.upper())
        country_pt = "EUA"
    elif pais == "IE":
        estado = ""
        country_pt = "Irlanda"
    else:
        estado     = _geo.validate_estado(pais, region)
        country_pt = _ISO_TO_PT.get(pais, country)

    loc_parts   = [p for p in (city, region, country_pt) if p]
    localizacao = ", ".join(loc_parts) or country_pt or "Internacional"

    return localizacao, localizacao, estado, pais


def _parse_event(ev: dict, today: str) -> Corrida | None:
    name_raw = (ev.get("name") or ev.get("title") or "").strip()
    if not name_raw:
        return None

    titulo = normalize_titulo(name_raw)
    if not titulo or len(titulo) < 4:
        return None

    # Strict keyword check
    if _NON_RUNNING.search(titulo):
        return None
    if not _RUNNING_KW.search(titulo):
        # Check category tags before giving up
        cats = ev.get("categories") or ev.get("tags") or ev.get("activity_types") or []
        is_running = any(
            "run" in (c.get("slug") or c.get("name") or c if isinstance(c, str) else "").lower()
            for c in (cats if isinstance(cats, list) else [])
        )
        if not is_running:
            return None

    data_evento = _parse_date(ev)
    if not data_evento or data_evento < today:
        return None

    distancias = _parse_distances(ev)
    if not distancias:
        return None

    localizacao, cidade, estado, pais = _parse_location(ev)

    ev_id   = ev.get("id") or ev.get("event_id") or ev.get("slug") or slugify(titulo)
    ev_slug = ev.get("slug") or ev.get("url_slug") or ""
    link    = ev.get("url") or ev.get("link") or ev.get("event_url") or ""
    if not link and ev_slug:
        link = f"{BASE}/gb/e/{ev_slug}"
    if not link:
        link = f"{BASE}/gb/e/"
    if link and not link.startswith("http"):
        link = BASE + ("" if link.startswith("/") else "/") + link

    image = ev.get("image_url") or ev.get("image") or ev.get("cover_image") or None
    year  = data_evento[:4]
    now   = now_iso()

    return Corrida(
        id=f"letsdothis_{ev_id}_{year}",
        titulo=titulo,
        data_evento=data_evento,
        horario=None,
        localizacao=localizacao,
        cidade=cidade,
        estado=estado,
        pais=pais,
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
