"""Scraper for Race Roster (raceroster.com) — North American race registration.

Race Roster hosts thousands of running events, primarily in Canada and the US,
with growing international coverage.

Strategy: hit the public REST search API at /api/v2/events/search, paginate
through results, filter to running-category events, and apply keyword
inclusion/exclusion filters.  Mile distances are preserved as strings
("N mi") per the project convention; Canadian/US events are geolocated by
the province/state fields in the API response.
"""
from __future__ import annotations
import re
from datetime import date, timedelta

from ..http_client import get
from ..models import Corrida, Distancia, FonteInfo
from ..utils import normalize_titulo, slugify, now_iso, today_iso
from .. import geo as _geo

BASE        = "https://raceroster.com"
SOURCE_NAME = "Race Roster"
_API_BASE   = f"{BASE}/api/v2"

_LOOKAHEAD_DAYS   = 365
_RESULTS_PER_PAGE = 25   # Race Roster default page size
_MAX_PAGES        = 40   # up to 1 000 events

# CA provinces
_CA_PROVINCES: set[str] = {
    "AB", "BC", "MB", "NB", "NL", "NS", "NT", "NU", "ON", "PE", "QC", "SK", "YT",
}

# US states
_US_STATES: set[str] = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID",
    "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS",
    "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK",
    "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV",
    "WI", "WY", "DC",
}

_ISO_TO_PT: dict[str, str] = {
    "CA": "Canadá",     "US": "EUA",         "GB": "Reino Unido",
    "AU": "Austrália",  "NZ": "Nova Zelândia", "IE": "Irlanda",
    "DE": "Alemanha",   "FR": "França",       "ES": "Espanha",
    "MX": "México",     "BR": "Brasil",       "ZA": "África do Sul",
    "JP": "Japão",      "KR": "Coreia do Sul", "NL": "Países Baixos",
    "BE": "Bélgica",    "CH": "Suíça",        "AT": "Áustria",
    "SE": "Suécia",     "NO": "Noruega",      "DK": "Dinamarca",
    "FI": "Finlândia",  "PT": "Portugal",     "IT": "Itália",
    "PL": "Polônia",    "CZ": "República Tcheca",
}

_RUNNING_KW = re.compile(
    r"\b(run|running|race|marathon|marath|5k|10k|15k|21k|42k"
    r"|half[\s\-]?marathon|ultra|trail|road\s*race|fun\s*run"
    r"|colour\s*run|color\s*run|mud\s*run)\b",
    re.IGNORECASE,
)

_NON_RUNNING = re.compile(
    r"\b(triathlon|duathlon|aquathlon|aquabike|cycling|cycle|cyclist"
    r"|swim\s*meet|swimming|open\s*water|paddle|kayak|canoe|rowing"
    r"|spartan|obstacle|ocr|crossfit|yoga|golf|soccer|tennis"
    r"|football|hockey|skating|skiing|snowshoe)\b",
    re.IGNORECASE,
)

# Known running category identifiers used by Race Roster
_RUNNING_CATEGORIES: set[str] = {
    "running", "road-running", "road running", "road_running",
    "trail-running", "trail running", "trail_running",
    "5k", "10k", "half-marathon", "marathon", "ultra",
    "fun-run", "obstacle-course",  # some fun runs are tagged here
}


def scrape() -> list[Corrida]:
    today_s = today_iso()
    start   = date.today().strftime("%Y-%m-%d")
    end     = (date.today() + timedelta(days=_LOOKAHEAD_DAYS)).strftime("%Y-%m-%d")

    events   = _fetch_all_events(start, end)
    corridas = []
    skipped  = 0
    for ev in events:
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
        batch = _fetch_page(start, end, page)
        if batch is None:
            break
        events = batch.get("data") or batch.get("events") or batch.get("results") or []
        if isinstance(events, dict):
            events = events.get("data") or []
        if not events:
            break
        result.extend(events)
        total = (
            batch.get("total")
            or batch.get("total_count")
            or batch.get("meta", {}).get("total")
            or 0
        )
        print(f"[{SOURCE_NAME}] página {page}: {len(events)} eventos (total≈{total})")
        if len(events) < _RESULTS_PER_PAGE or (total and len(result) >= total):
            break
    return result


def _fetch_page(start: str, end: str, page: int) -> dict | None:
    # Race Roster public search API
    url = f"{_API_BASE}/events/search"
    params = {
        "status":        "upcoming",
        "start_date":    start,
        "end_date":      end,
        "page":          page,
        "per_page":      _RESULTS_PER_PAGE,
        "sort":          "start_date",
        "sort_direction": "asc",
    }
    try:
        resp = get(url, params=params, source=SOURCE_NAME, timeout=30)
    except Exception as e:
        print(f"[{SOURCE_NAME}] erro HTTP página {page}: {e}")
        return None

    if resp.status_code == 404 and page > 1:
        return None
    if resp.status_code != 200:
        print(f"[{SOURCE_NAME}] HTTP {resp.status_code} página {page}")
        if page == 1:
            # Try alternate endpoint
            return _fetch_page_v1(start, end)
        return None

    try:
        return resp.json()
    except Exception as e:
        print(f"[{SOURCE_NAME}] JSON inválido página {page}: {e}")
        return None


def _fetch_page_v1(start: str, end: str) -> dict | None:
    """Fallback: try v1 API endpoint."""
    url = f"{BASE}/api/v1/events"
    params = {
        "upcoming":   "true",
        "start_date": start,
        "end_date":   end,
        "per_page":   _RESULTS_PER_PAGE,
    }
    try:
        resp = get(url, params=params, source=SOURCE_NAME, timeout=30)
        if resp.status_code == 200:
            print(f"[{SOURCE_NAME}] usando API v1")
            return resp.json()
    except Exception as e:
        print(f"[{SOURCE_NAME}] v1 falhou: {e}")
    return None


# ---------------------------------------------------------------------------
def _is_running_event(ev: dict) -> bool:
    """Return True if the event should be kept as a running event."""
    name    = (ev.get("name") or ev.get("title") or "").strip()
    cats    = ev.get("categories") or ev.get("tags") or []
    if isinstance(cats, list):
        for c in cats:
            s = (c.get("slug") or c.get("name") or c if isinstance(c, str) else "").lower()
            if s in _RUNNING_CATEGORIES:
                return True

    # Fall back to title keywords
    if _NON_RUNNING.search(name):
        return False
    return bool(_RUNNING_KW.search(name))


_MI_RE = re.compile(r"(\d+(?:\.\d+)?)\s*mi(?:le)?\b", re.IGNORECASE)
_KM_RE = re.compile(r"(\d+(?:\.\d+)?)\s*k(?:m)?\b",   re.IGNORECASE)


def _parse_distances(ev: dict) -> list[Distancia]:
    seen: set = set()
    result: list[Distancia] = []

    # Structured distance sub-events
    for sub in (ev.get("sub_events") or ev.get("races") or ev.get("distances") or []):
        if not isinstance(sub, dict):
            continue
        raw_name = (sub.get("name") or sub.get("distance_label") or "").lower()
        raw_dist = sub.get("distance") or sub.get("distance_km") or sub.get("distance_mi")
        unit     = (sub.get("distance_unit") or sub.get("unit") or "").lower()

        km: float | str | None = None

        if raw_dist:
            try:
                n = float(raw_dist)
                if "mi" in unit or "mile" in unit:
                    km = f"{int(n) if n == int(n) else n:g} mi"
                else:
                    km = n if 1 <= n <= 250 else None
            except (ValueError, TypeError):
                pass

        if km is None:
            km = _parse_distance_from_label(raw_name)

        if km is None or km in seen:
            continue
        seen.add(km)
        result.append(Distancia(km=km, data=None, horario=None))

    # Fall back: extract from event name
    if not result:
        name = (ev.get("name") or ev.get("title") or "").lower()
        result = _parse_distance_from_name(name, seen)

    return result


def _parse_distance_from_label(label: str) -> float | str | None:
    label = label.lower()
    if "marathon" in label and "half" not in label:
        return 42.195
    if "half" in label and "marathon" in label:
        return 21.097
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
        val = float(m.group(1))
        key = f"{int(val) if val == int(val) else val:g} mi"
        if key not in seen:
            seen.add(key)
            result.append(Distancia(km=key, data=None, horario=None))
    for m in _KM_RE.finditer(name):
        val = float(m.group(1))
        if 1 <= val <= 250 and val not in seen:
            seen.add(val)
            result.append(Distancia(km=val, data=None, horario=None))
    return result


def _parse_event(ev: dict, today: str) -> Corrida | None:
    name_raw = (ev.get("name") or ev.get("title") or "").strip()
    if not name_raw:
        return None

    titulo = normalize_titulo(name_raw)
    if not titulo or len(titulo) < 4:
        return None

    if not _is_running_event(ev):
        return None

    # Date
    date_raw = (
        ev.get("start_date") or ev.get("date") or ev.get("event_date") or ""
    )
    if not date_raw:
        return None
    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})", str(date_raw).strip())
    if not m:
        return None
    data_evento = f"{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}"
    if data_evento < today:
        return None

    # Distances
    distancias = _parse_distances(ev)
    if not distancias:
        return None

    # Location
    city    = (ev.get("city") or ev.get("location_city") or "").strip()
    state   = (ev.get("state") or ev.get("province") or ev.get("location_state") or "").strip().upper()
    country = (ev.get("country") or ev.get("country_code") or "CA").strip().upper()

    pais = country if len(country) == 2 else "CA"

    if pais == "CA":
        estado    = state if state in _CA_PROVINCES else ""
        loc_parts = [p for p in (city, state, "Canadá") if p]
    elif pais == "US":
        estado    = state if state in _US_STATES else ""
        loc_parts = [p for p in (city, state, "EUA") if p]
    else:
        estado      = _geo.validate_estado(pais, state)
        country_pt  = _ISO_TO_PT.get(pais, country)
        loc_parts   = [p for p in (city, country_pt) if p]

    localizacao = ", ".join(loc_parts) or "Internacional"

    # Event link
    slug = (ev.get("slug") or ev.get("event_slug") or "")
    ev_id = (ev.get("id") or ev.get("event_id") or "")
    if slug:
        link = f"{BASE}/events/{slug}"
    elif ev_id:
        link = f"{BASE}/events/{ev_id}"
    else:
        link = ev.get("url") or ev.get("link") or BASE

    if link and not link.startswith("http"):
        link = BASE + ("" if link.startswith("/") else "/") + link

    image = ev.get("image_url") or ev.get("logo_url") or None

    year  = data_evento[:4]
    rid   = ev_id or slugify(titulo)
    now   = now_iso()

    return Corrida(
        id=f"raceroster_{rid}_{year}",
        titulo=titulo,
        data_evento=data_evento,
        horario=None,
        localizacao=localizacao,
        cidade=localizacao,
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
