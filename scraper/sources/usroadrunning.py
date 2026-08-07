"""Scraper for usroadrunning.com â US Road Running themed race series.

US Road Running is a US race organizer that runs themed events (Medal Madness,
Haunted, Eagle, Ninja â¦) as 5K / 10K / Half-Marathon races across dozens of US
cities. Registration is handled on RunSignup (each event's `offers.url` points
there), but this organizer site is the source of record and exposes clean,
complete schema.org data.

Ingestion - the per-state search listing:

    GET /Races/NearMe/RaceSearch.php?event_type=running_race&state=<ST>
        [&start_date=YYYY-MM-DD]      # paginate forward through the calendar

The listing USED TO embed a full `@type: ["Event","SportsEvent"]` JSON-LD block
per race, so no detail fetch was needed. Around 2026-07-29 the site replaced
those with a single `ItemList` of `ListItem`s carrying only `name`,
`description` and `url` - no `startDate`, no address, no `keywords`. Every
`Event` block disappeared from the listing and this scraper went to 0 events
for 15 consecutive health runs while the site itself stayed perfectly healthy.

The DETAIL PAGES still carry the full Event block, unchanged, so ingestion now
follows each `ListItem.url` and parses the JSON-LD there. Both shapes are
handled - an inline Event block is still used when present, so this keeps
working if the listing ever reverts.

Each Event block carries `name`, `startDate` (date **and** start time),
`location.address` (city / state / country), `keywords` and `image`. We page
forward by setting `start_date` to the day after the last event seen, until a
page returns no new upcoming events.

Nothing is read out of the `ListItem` itself - not its `name`, not its
`description`, and not the `race_date` in its URL. The listing supplies only
the SET OF PAGES to open; every field comes from the detail page's structured
Event block.

Distances come from the structured `keywords`/`description` fields (e.g.
"â¦ 5K, 10K, Half Marathon, running race â¦"), parsed via the shared
extract_distances_from_text helper â never from the title.
"""
from __future__ import annotations
import json
import re
from concurrent.futures import ThreadPoolExecutor
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

_US_STATES: frozenset[str] = frozenset({
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID",
    "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS",
    "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK",
    "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV",
    "WI", "WY", "DC",
})

_ID_RE = re.compile(r"/Races/[A-Z]{2}/[^/]+/(\d+)-", re.IGNORECASE)

# Parallelism for the per-event detail fetches. This bounds how many requests
# are IN FLIGHT, never how many are made: every ListItem on every page is
# fetched and parsed (see "No result caps" in the README).
_DETAIL_WORKERS = 8


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
    _page = -1
    while True:  # no cap — paginate until exhausted (breaks below)
        _page += 1
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
        if nxt == start_date:  # no forward progress â stop
            break
        start_date = nxt


def _parse_events(html: str, today: str, end_date: str) -> list[Corrida]:
    """Events from one listing page, whichever shape the listing is in.

    Inline `Event` blocks are used when present. When the listing carries only
    an `ItemList` of links (the shape since ~2026-07-29), each linked detail
    page is fetched and its own Event block is parsed instead."""
    blocks = _ld_blocks(html)

    out: list[Corrida] = []
    for blk in blocks:
        types = blk.get("@type")
        types = types if isinstance(types, list) else [types]
        if "SportsEvent" not in types and "Event" not in types:
            continue
        c = _parse_event(blk, today, end_date)
        if c:
            out.append(c)
    if out:
        return out

    return _parse_via_detail_pages(blocks, today, end_date)


def _ld_blocks(html: str) -> list[dict]:
    """Every JSON-LD object on the page, with any `@graph` members flattened."""
    soup = BeautifulSoup(html, "lxml")
    blocks: list[dict] = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except Exception:
            continue
        for top in (data if isinstance(data, list) else [data]):
            if not isinstance(top, dict):
                continue
            graph = top.get("@graph")
            if isinstance(graph, list):
                blocks.extend(g for g in graph if isinstance(g, dict))
            else:
                blocks.append(top)
    return blocks


def _listing_urls(blocks: list[dict]) -> list[str]:
    """Detail-page URLs from the listing's ItemList, in listing order.

    Only the URL is taken. The ListItem's `name` and `description` are NOT read
    - the race name is not a structured carrier of distances or location, and
    the `race_date` query parameter is not an event date field. Everything is
    read from the detail page's own Event block."""
    urls: list[str] = []
    seen: set[str] = set()
    for blk in blocks:
        if blk.get("@type") != "ItemList":
            continue
        for item in blk.get("itemListElement") or []:
            if not isinstance(item, dict):
                continue
            url = (item.get("url") or "").strip()
            if not url or not _ID_RE.search(url) or url in seen:
                continue
            seen.add(url)
            urls.append(url)
    return urls


def _parse_via_detail_pages(blocks: list[dict], today: str, end_date: str) -> list[Corrida]:
    """Fetch every ListItem's detail page and parse its Event block."""
    urls = _listing_urls(blocks)
    if not urls:
        return []

    # Every URL the listing exposes is fetched; the pool bounds concurrency
    # only. Order is restored afterwards so pagination sees a stable list.
    with ThreadPoolExecutor(max_workers=_DETAIL_WORKERS) as pool:
        pages = list(pool.map(_fetch_detail, urls))

    out: list[Corrida] = []
    for url, html in zip(urls, pages):
        if not html:
            continue
        for blk in _ld_blocks(html):
            types = blk.get("@type")
            types = types if isinstance(types, list) else [types]
            if "SportsEvent" not in types and "Event" not in types:
                continue
            c = _parse_event(blk, today, end_date)
            if c:
                out.append(c)
            break
    return out


def _fetch_detail(url: str) -> str | None:
    try:
        resp = get(url, source=SOURCE_NAME, timeout=30)
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        print(f"[{SOURCE_NAME}] detalhe {url}: {e}")
        return None


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
    Marathon, running race, â¦"), falling back to the `description`. Both are
    dedicated text fields that enumerate the distances explicitly; titles are
    not a reliable distance source. Parsing goes through the shared
    `extract_distances_from_text` helper (5Kâ5, 10Kâ10, "Half Marathon"â21.097)."""
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
