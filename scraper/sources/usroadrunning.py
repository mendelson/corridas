"""Scraper for usroadrunning.com — US Road Running themed race series.

US Road Running is a US race organizer that runs themed events (Medal Madness,
Haunted, Eagle, Ninja …) as 5K / 10K / Half-Marathon races across dozens of US
cities. Registration is handled on RunSignup (each event's `offers.url` points
there), but this organizer site is the source of record and exposes clean,
complete schema.org data.

Ingestion — the per-state search listing embeds, inline, a full
`@type: ["Event","SportsEvent"]` JSON-LD block for each of the next ~20 upcoming
events, so no per-event detail fetch is needed:

    GET /Races/NearMe/RaceSearch.php?event_type=running_race&state=<ST>
        [&start_date=YYYY-MM-DD]      # paginate forward through the calendar

Each Event block carries `name`, `startDate` (date **and** start time),
`location.address` (city / state / country) and `image`. We page forward by
setting `start_date` to the day after the last event seen, until a page returns
no new upcoming events.

Distances come from the structured `keywords`/`description` fields (e.g.
"… 5K, 10K, Half Marathon, running race …"), parsed via the shared
extract_distances_from_text helper — never from the title.
"""
from __future__ import annotations
import json
import re
from datetime import date, datetime, timedelta

from bs4 import BeautifulSoup

from ..http_client import get
from .. import geo as _geo
from ..models import Corrida, Distancia, FonteInfo
from ..utils import normalize_titulo, now_iso, today_iso, extract_distances_from_text

SOURCE_NAME = "US Road Running"
BASE = "https://usroadrunning.com"
_SEARCH = f"{BASE}/Races/NearMe/RaceSearch.php"
_LOOKAHEAD_DAYS = 365
_MAX_PAGES_PER_STATE = 18  # safety cap on the start_date pagination loop

_US_STATES: frozenset[str] = frozenset({
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID",
    "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS",
    "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK",
    "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV",
    "WI", "WY", "DC",
})

_ID_RE = re.compile(r"/Races/[A-Z]{2}/[^/]+/(\d+)-", re.IGNORECASE)


# ---------------------------------------------------------------------------
def scrape() -> list[Corrida]:
    today = today_iso()
    end_date = (date.today() + timedelta(days=_LOOKAHEAD_DAYS)).isoformat()
    seen: dict[str, Corrida] = {}

    for st in sorted(_US_STATES):
        _scrape_state(st, today, end_date, seen)

    result = list(seen.values())
    print(f"[{SOURCE_NAME}] {len(result)} corridas encontradas")
    return result


def _scrape_state(st: str, today: str, end_date: str, seen: dict[str, Corrida]) -> None:
    start_date: str | None = None
    for _page in range(_MAX_PAGES_PER_STATE):
        params = {"event_type": "running_race", "state": st}
        if start_date:
            params["start_date"] = start_date
        try:
            resp = get(_SEARCH, params=params, source=SOURCE_NAME, timeout=30)
            resp.raise_for_status()
        except Exception as e:
            print(f"[{SOURCE_NAME}] {st} {start_date or ''}: {e}")
            return

        events = _parse_events(resp.text, today, end_date)
        new = 0
        max_date = start_date
        for c in events:
            if c.id not in seen:
                seen[c.id] = c
                new += 1
            if max_date is None or c.data_evento > max_date:
                max_date = c.data_evento

        if new == 0 or not max_date or max_date >= end_date:
            break
        nxt = (datetime.strptime(max_date, "%Y-%m-%d").date() + timedelta(days=1)).isoformat()
        if nxt == start_date:  # no forward progress — stop
            break
        start_date = nxt


def _parse_events(html: str, today: str, end_date: str) -> list[Corrida]:
    soup = BeautifulSoup(html, "lxml")
    out: list[Corrida] = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except Exception:
            continue
        # The listing wraps everything in a single JSON-LD document whose
        # `@graph` holds the ItemList + one Event/SportsEvent per race, so flatten
        # both the top-level objects and any @graph members.
        candidates: list[dict] = []
        for top in (data if isinstance(data, list) else [data]):
            if not isinstance(top, dict):
                continue
            graph = top.get("@graph")
            if isinstance(graph, list):
                candidates.extend(g for g in graph if isinstance(g, dict))
            else:
                candidates.append(top)
        for blk in candidates:
            types = blk.get("@type")
            types = types if isinstance(types, list) else [types]
            if "SportsEvent" not in types and "Event" not in types:
                continue
            c = _parse_event(blk, today, end_date)
            if c:
                out.append(c)
    return out


def _parse_event(blk: dict, today: str, end_date: str) -> Corrida | None:
    name = (blk.get("name") or "").strip()
    if not name or len(name) < 4:
        return None

    # Date + start time (horario) from startDate "2026-06-06T08:00:00-05:00"
    m = re.match(r"(\d{4}-\d{2}-\d{2})T(\d{2}):(\d{2})", str(blk.get("startDate") or ""))
    if not m:
        return None
    data_evento = m.group(1)
    if data_evento < today or data_evento > end_date:
        return None
    h, mi = int(m.group(2)), int(m.group(3))
    if not (0 <= h <= 23 and 0 <= mi <= 59):
        return None
    horario = f"{h:02d}:{mi:02d}"

    # Location from the PostalAddress
    loc = blk.get("location") or {}
    addr = (loc.get("address") or {}) if isinstance(loc, dict) else {}
    cidade = (addr.get("addressLocality") or "").strip()
    estado = (addr.get("addressRegion") or "").strip().upper()
    pais = (addr.get("addressCountry") or "US").strip().upper()
    if pais != "US":
        return None
    if estado not in _US_STATES and cidade:
        _, geo_estado = _geo.resolve(cidade, "", "US")
        estado = (geo_estado or "").strip().upper()
    estado = _geo.validate_estado("US", estado)
    if not estado or not cidade:
        return None

    distancias = _parse_distances(blk)
    if not distancias:
        return None

    url = (blk.get("url") or blk.get("@id") or "").split("#")[0]
    mid = _ID_RE.search(url)
    if not mid:
        return None
    eid = mid.group(1)

    image = None
    img = blk.get("image")
    if isinstance(img, list) and img:
        image = img[0]
    elif isinstance(img, str):
        image = img

    now = now_iso()
    link = url or BASE
    return Corrida(
        id=f"usrr_{eid}",
        titulo=normalize_titulo(name),
        data_evento=data_evento,
        horario=horario,
        localizacao=f"{cidade}, {estado}",
        cidade=cidade,
        estado=estado,
        pais="US",
        distancias=distancias,
        imagem_url=image,
        inscricoes_abertas=None,
        periodo_inscricao=None,
        fontes=[FonteInfo(
            nome=SOURCE_NAME,
            link_evento=link,
            links_inscricao=[link],
            tipo="organizador",
        )],
        miss_count=0,
        first_seen_at=now,
        updated_at=now,
    )


def _parse_distances(blk: dict) -> list[Distancia]:
    """Parse distances from the event's structured fields, not its title.

    Prefer the `keywords` tag list (e.g. "US Road Running, 5K, 10K, Half
    Marathon, running race, …"), falling back to the `description`. Both are
    dedicated text fields that enumerate the distances explicitly; titles are
    not a reliable distance source. Parsing goes through the shared
    `extract_distances_from_text` helper (5K→5, 10K→10, "Half Marathon"→21.097)."""
    kw = blk.get("keywords")
    if isinstance(kw, (list, tuple)):
        kw = ", ".join(str(x) for x in kw)
    field = kw or blk.get("description") or ""

    seen: set = set()
    out: list[Distancia] = []
    for km in extract_distances_from_text(field, min_km=1.0, named_in_prose=True):
        if km not in seen:
            seen.add(km)
            out.append(Distancia(km=km, data=None, horario=None))
    return out
