"""Scraper for RunSignup (runsignup.com) — US/global race registration platform.

RunSignup hosts thousands of running events worldwide, mostly in the US.
US events frequently advertise distances in miles (e.g. "5 Mile",
"13.1 Miles"); some races mix km and miles within the same event.

We preserve the original unit:
  • km distances are stored as floats (5.0, 10.0, 21.097, 42.195…)
  • mile distances are stored as strings ("5 mi", "13.1 mi") so the frontend
    renders them as-is via formatKm()'s string passthrough.

Strategy: hit the public REST API at /Rest/races, paginate, parse each
race's events array. No HTML scraping needed.
"""
from __future__ import annotations
import re
from datetime import date, timedelta

from ..http_client import get
from ..models import Corrida, Distancia, FonteInfo
from ..utils import normalize_titulo, slugify, now_iso, today_iso


BASE        = "https://runsignup.com"
API_URL     = f"{BASE}/Rest/races"
SOURCE_NAME = "RunSignup"

_MAX_PAGES        = 15
_RESULTS_PER_PAGE = 250          # API max
_LOOKAHEAD_DAYS   = 365

_US_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID",
    "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS",
    "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK",
    "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV",
    "WI", "WY", "DC",
}

_NON_RUNNING = re.compile(
    r"\btriathlon\b|\bduathlon\b|\baquathlon\b|\baquabike\b"
    r"|\bcycling\b|\bcyclocross\b|\bbike\s*ride\b"
    r"|\bswim\s*meet\b|\bpaddle\b|\bkayak\b"
    r"|\bspartan\b|\bobstacle\s*race\b|\bocr\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
def scrape() -> list[Corrida]:
    today_s = today_iso()
    start   = date.today().strftime("%m/%d/%Y")
    end     = (date.today() + timedelta(days=_LOOKAHEAD_DAYS)).strftime("%m/%d/%Y")

    races: list[dict] = []
    for page in range(1, _MAX_PAGES + 1):
        url = (
            f"{API_URL}?format=json"
            f"&events=T"
            f"&start_date={start}"
            f"&end_date={end}"
            f"&page={page}"
            f"&results_per_page={_RESULTS_PER_PAGE}"
        )
        try:
            resp = get(url, source=SOURCE_NAME, timeout=30)
        except Exception as e:
            print(f"[{SOURCE_NAME}] erro ao buscar página {page}: {e}")
            break
        if resp.status_code != 200:
            print(f"[{SOURCE_NAME}] HTTP {resp.status_code} na página {page}")
            break
        try:
            data = resp.json()
        except Exception as e:
            print(f"[{SOURCE_NAME}] JSON inválido na página {page}: {e}")
            break

        if page == 1 and isinstance(data, dict):
            print(f"[{SOURCE_NAME}] API response keys: {list(data.keys())}")
            total = data.get("total_results") or data.get("total") or data.get("num_results") or "?"
            print(f"[{SOURCE_NAME}] total_results: {total}")

        page_races = data.get("races", []) if isinstance(data, dict) else []
        if not page_races:
            break
        races.extend(page_races)
        print(f"[{SOURCE_NAME}] página {page}: {len(page_races)} corridas")
        if len(page_races) < _RESULTS_PER_PAGE:
            break

    if not races:
        print(f"[{SOURCE_NAME}] nenhuma corrida retornada pela API")
        return []

    print(f"[{SOURCE_NAME}] {len(races)} corridas brutas no total")

    corridas: list[Corrida] = []
    skipped = 0
    for entry in races:
        race = entry.get("race") if isinstance(entry, dict) else None
        if not isinstance(race, dict):
            race = entry if isinstance(entry, dict) else None
        if not race:
            continue
        try:
            c = _parse_race(race, today_s)
            if c:
                corridas.append(c)
            else:
                skipped += 1
        except Exception as e:
            print(f"[{SOURCE_NAME}] erro ao parsear '{race.get('name', '?')}': {e}")

    print(f"[{SOURCE_NAME}] {len(corridas)} corridas válidas ({skipped} ignoradas)")
    return corridas


# ---------------------------------------------------------------------------
# Distance parsing — preserves miles vs. kilometres
# ---------------------------------------------------------------------------
_NUM_RE   = re.compile(r"(\d+(?:[.,]\d+)?)")
_KM_UNITS = ("km", "kilometer", "kilometre")
_MI_UNITS = ("miles", "mile", "mi")  # longest first


def _parse_distance(raw: str) -> float | str | None:
    """Parse a free-text distance string.

    Returns:
        float — when the distance is in kilometres (or a known canonical race)
        str   — when the distance is in miles, formatted as "N mi"
        None  — when unparseable or non-running
    """
    if not raw:
        return None
    s = raw.strip().lower()

    if not s:
        return None

    # Named distances — always in km
    if "ultra" in s:
        # length varies (50K, 50mi, 100K, 100mi…) — fall through to numeric parse
        pass
    if "half marathon" in s or re.fullmatch(r"\s*(half|hm)\s*", s):
        return 21.097
    if "marathon" in s and "half" not in s:
        return 42.195

    m = _NUM_RE.search(s)
    if not m:
        return None
    try:
        num = float(m.group(1).replace(",", "."))
    except ValueError:
        return None
    rest = s[m.end():].strip()

    # Kilometres
    if any(u in rest for u in _KM_UNITS) or rest.startswith("k"):
        return num

    # Miles — explicit unit
    if any(u in rest for u in _MI_UNITS):
        return _format_miles(num)
    # Single trailing "m" (US convention: "5M" = 5 miles).
    # Reject "met" / "meter" / "metres".
    if rest.startswith("m") and not rest.startswith(("met", "mt")):
        return _format_miles(num)

    # No unit — assume km if value looks like a typical race distance
    if 1 <= num <= 200:
        return num
    return None


def _format_miles(num: float) -> str:
    if num.is_integer():
        return f"{int(num)} mi"
    # Trim trailing zeros (5.10 → 5.1)
    return f"{num:g} mi"


def _parse_distances(events: list[dict]) -> list[Distancia]:
    seen: set = set()
    result: list[Distancia] = []
    for ev in events or []:
        if not isinstance(ev, dict):
            continue
        if _NON_RUNNING.search((ev.get("name") or "")):
            continue
        # Try structured distance + units fields first, then fall back to name.
        raw_dist  = ev.get("distance")
        raw_units = (ev.get("distance_units") or "").strip().upper()
        km: float | str | None = None
        if raw_dist:
            num_str = str(raw_dist).strip()
            if raw_units == "M":
                # RunSignup uses "M" for miles
                try:
                    km = _format_miles(float(num_str))
                except ValueError:
                    pass
            elif raw_units in ("K", "KM", ""):
                try:
                    num = float(num_str)
                    km = num if 1 <= num <= 200 else None
                except ValueError:
                    pass
        if km is None:
            for field in ("distance", "name"):
                raw = ev.get(field)
                if not raw:
                    continue
                km = _parse_distance(str(raw))
                if km is not None:
                    break
        if km is None or km in seen:
            continue
        seen.add(km)
        result.append(Distancia(km=km, data=None, horario=None))
    return result


# ---------------------------------------------------------------------------
# Date handling
# ---------------------------------------------------------------------------
_DATE_FIELDS_RACE  = ("next_date", "start_date", "date")
_DATE_FIELDS_EVENT = ("start_time", "start_date", "date")


def _normalize_date(s: str) -> str | None:
    s = s.strip()
    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})", s)
    if m:
        return f"{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}"
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})", s)
    if m:
        return f"{m.group(3)}-{m.group(1).zfill(2)}-{m.group(2).zfill(2)}"
    return None


def _extract_date(race: dict, events: list[dict]) -> str | None:
    for f in _DATE_FIELDS_RACE:
        v = race.get(f)
        if isinstance(v, str) and len(v) >= 8:
            d = _normalize_date(v)
            if d:
                return d
    for ev in events or []:
        if not isinstance(ev, dict):
            continue
        for f in _DATE_FIELDS_EVENT:
            v = ev.get(f)
            if isinstance(v, str) and len(v) >= 8:
                d = _normalize_date(v)
                if d:
                    return d
    return None


# ---------------------------------------------------------------------------
# Race → Corrida
# ---------------------------------------------------------------------------
def _parse_race(race: dict, today: str) -> Corrida | None:
    name_raw = race.get("name") or ""
    titulo   = normalize_titulo(name_raw)
    if not titulo or len(titulo) < 4:
        return None
    if _NON_RUNNING.search(titulo):
        return None

    events = race.get("race_events") or race.get("events") or []
    if not isinstance(events, list):
        events = []

    data_evento = _extract_date(race, events)
    if not data_evento or data_evento < today:
        return None

    distancias = _parse_distances(events)
    if not distancias:
        return None

    addr    = race.get("address") or {}
    city    = (addr.get("city") or "").strip()
    state   = (addr.get("state") or "").strip().upper()
    country = (addr.get("country_code") or "").strip().upper() or "US"

    if country == "US":
        estado    = state if state in _US_STATES else "INT"
        loc_parts = [p for p in (city, state, "EUA") if p]
    else:
        estado    = "INT"
        loc_parts = [p for p in (city, country) if p]
    localizacao = ", ".join(loc_parts) or "Internacional"

    race_id = race.get("race_id") or race.get("id")
    link    = race.get("url") or (
        f"{BASE}/Race/{state}/{slugify(city) if city else 'US'}/{race_id}"
        if race_id else BASE
    )
    if link and not link.startswith("http"):
        link = BASE + ("" if link.startswith("/") else "/") + link

    image = race.get("logo_url") or race.get("logo") or None

    now  = now_iso()
    year = data_evento[:4]
    return Corrida(
        id=f"runsignup_{race_id or slugify(titulo)}_{year}",
        titulo=titulo,
        data_evento=data_evento,
        horario=None,
        localizacao=localizacao,
        cidade=localizacao,
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
