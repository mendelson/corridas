"""Scraper for worldsmarathons.com — global marathon/running-event directory.

Server-rendered Angular site (no WAF). Each /marathon/<slug> page embeds all the
data we need in *structured* fields — never parsed from the title:

- JSON-LD `@type:"Event"`  → name, startDate (date), location.Place
  (addressLocality + addressCountry ISO-2), image.
- An embedded data blob    → `local_start_time`/`start_time` ("09:00" → horário)
  and `raceDistances` (each distance in metres, e.g. 42195 → 42.195 km).

Discovery: robots.txt → index-sitemap-en.xml → marathons-sitemap-en.xml, which
lists every /marathon/<slug> URL.

See docs/source-research/worldsmarathons.md.
"""
from __future__ import annotations
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta

from bs4 import BeautifulSoup

from ..http_client import get
from .. import geo as _geo
from ..models import Corrida, Distancia, FonteInfo
from ..utils import normalize_titulo, now_iso, today_iso

SOURCE_NAME = "World's Marathons"
BASE = "https://worldsmarathons.com"
_SITEMAP = f"{BASE}/marathons-sitemap-en.xml"
_LOOKAHEAD_DAYS = 540
_CANONICAL = [(42.195, 41.0, 43.0), (21.097, 20.5, 21.5)]

_START_TIME_RE = re.compile(r'"(?:local_)?start_time"\s*:\s*"(\d{1,2}):(\d{2})"')
_DISTANCE_RE = re.compile(r'"distance"\s*:\s*(\d+(?:\.\d+)?)')
_SLUG_RE = re.compile(r"/marathon/([a-z0-9][a-z0-9\-]*)/?$", re.IGNORECASE)


# ---------------------------------------------------------------------------
def scrape() -> list[Corrida]:
    today = today_iso()
    end_date = (date.today() + timedelta(days=_LOOKAHEAD_DAYS)).isoformat()

    urls = _event_urls()
    if not urls:
        print(f"[{SOURCE_NAME}] nenhuma URL de evento no sitemap")
        return []
    # No cap: EVERY event in the sitemap is fetched and checked, never a prefix
    # or a rotating window — discarding results is forbidden. Quality over speed.
    print(f"[{SOURCE_NAME}] {len(urls)} eventos no sitemap; buscando todos")

    corridas: list[Corrida] = []
    with ThreadPoolExecutor(max_workers=16) as pool:
        futures = {pool.submit(_fetch_event, u, today, end_date): u for u in urls}
        for fut in as_completed(futures):
            try:
                c = fut.result()
            except Exception as e:
                print(f"[{SOURCE_NAME}] erro {futures[fut]}: {e}")
                c = None
            if c:
                corridas.append(c)

    print(f"[{SOURCE_NAME}] {len(corridas)} corridas encontradas")
    return corridas


def _event_urls() -> list[str]:
    try:
        resp = get(_SITEMAP, source=SOURCE_NAME, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        print(f"[{SOURCE_NAME}] sitemap erro: {e}")
        return []
    urls: list[str] = []
    seen: set[str] = set()
    for m in re.finditer(r"<loc>\s*([^<\s]+)\s*</loc>", resp.text):
        u = m.group(1).strip()
        if _SLUG_RE.search(u) and u not in seen:
            seen.add(u)
            urls.append(u)
    return urls


def _fetch_event(url: str, today: str, end_date: str) -> Corrida | None:
    try:
        resp = get(url, source=SOURCE_NAME, timeout=30)
        resp.raise_for_status()
    except Exception:
        return None
    return _parse_event(resp.text, url, today, end_date)


def _parse_event(html: str, url: str, today: str, end_date: str) -> Corrida | None:
    ev = _jsonld_event(html)
    if not ev:
        return None

    name = (ev.get("name") or "").strip()
    if not name or len(name) < 4:
        return None
    titulo = normalize_titulo(name)

    m = re.match(r"(\d{4}-\d{2}-\d{2})", str(ev.get("startDate") or ""))
    if not m:
        return None
    data_evento = m.group(1)
    if data_evento < today or data_evento > end_date:
        return None

    # horario from the structured start-time field — OPTIONAL. Many events,
    # including several Abbott World Marathon Majors (Berlin, Tokyo, Chicago…),
    # publish no start time on worldsmarathons. horario is not a required field,
    # so a missing start time must NOT drop the event — requiring it here is what
    # silently hid the majors (only 13 of ~7000 pages carry a start_time).
    horario = None
    mt = _START_TIME_RE.search(html)
    if mt:
        h, mi = int(mt.group(1)), int(mt.group(2))
        if 0 <= h <= 23 and 0 <= mi <= 59:
            horario = f"{h:02d}:{mi:02d}"

    loc = ev.get("location") or {}
    addr = (loc.get("address") or {}) if isinstance(loc, dict) else {}
    cidade = (addr.get("addressLocality") or (loc.get("name") if isinstance(loc, dict) else "") or "").strip()
    pais = (addr.get("addressCountry") or "").strip().upper()
    if len(pais) != 2 or not cidade:
        return None
    _rp, estado = _geo.resolve(cidade, "", pais)
    if _rp and _rp not in ("??", ""):
        pais = _rp
    estado = _geo.validate_estado(pais, estado or "")
    if not estado:
        return None

    distancias = _parse_distances(html)
    if not distancias:
        return None

    image = None
    img = ev.get("image")
    if isinstance(img, list) and img:
        image = img[0]
    elif isinstance(img, str):
        image = img

    slug_m = _SLUG_RE.search(url)
    eid = slug_m.group(1) if slug_m else titulo.lower().replace(" ", "-")[:50]
    now = now_iso()
    return Corrida(
        id=f"wm_{eid}",
        titulo=titulo,
        data_evento=data_evento,
        horario=horario,
        localizacao=f"{cidade}, {estado}",
        cidade=cidade,
        estado=estado,
        pais=pais,
        distancias=distancias,
        imagem_url=image,
        inscricoes_abertas=None,
        periodo_inscricao=None,
        fontes=[FonteInfo(
            nome=SOURCE_NAME,
            link_evento=url,
            links_inscricao=[url],
            tipo="calendario",
        )],
        miss_count=0,
        first_seen_at=now,
        updated_at=now,
    )


def _jsonld_event(html: str) -> dict | None:
    soup = BeautifulSoup(html, "lxml")
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except Exception:
            continue
        for blk in (data if isinstance(data, list) else [data]):
            if not isinstance(blk, dict):
                continue
            t = blk.get("@type")
            types = t if isinstance(t, list) else [t]
            if "Event" in types and blk.get("startDate"):
                return blk
    return None


def _parse_distances(html: str) -> list[Distancia]:
    """Distances from the structured `distance` (metres) fields in raceDistances."""
    seen: set = set()
    out: list[Distancia] = []
    for mt in _DISTANCE_RE.finditer(html):
        metres = float(mt.group(1))
        if not (500 <= metres <= 200_000):
            continue
        km = round(metres / 1000.0, 3)
        for canon, lo, hi in _CANONICAL:
            if lo <= km <= hi:
                km = canon
                break
        if km not in seen:
            seen.add(km)
            out.append(Distancia(km=km, data=None, horario=None))
    return sorted(out, key=lambda d: d.km if isinstance(d.km, (int, float)) else 999)
