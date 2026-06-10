"""Scraper for finishers.com — Typesense `races` collection, road discipline.

finishers.com is a Next.js/Vercel site whose race search is backed by a hosted
Typesense cluster. The search-only API key + host live in the public JS bundle
(like a public Algolia search key); we extract them at runtime (resilient to
rotation) and query the `races` collection directly — a clean paginated JSON
API, no WAF (the old "blocked like Ahotu" note in the README was never tested
and is false: every endpoint returns HTTP 200).

Scope: `raceDiscipline:=road` (street running) only — the collection also holds
trail, triathlon, cycling, etc. Worldwide. Each Typesense doc is one race
(distance) of an event; we group by `eventId` into one Corrida with several
Distancia.

Field map (from the live schema): eventName→titulo, eventSlug→link
(/course/{slug}), editionStartDate→data_evento, raceDistance/raceDistanceUnit→
distancias, city + countryCode→location (estado matched offline against
web/locations via geo._match_subdiv; pipeline's geo.resolve fills the rest).
"""
from __future__ import annotations

import re
import time
from collections import defaultdict
from datetime import datetime, timezone

import httpx

from ..http_client import get
from ..models import Corrida, Distancia, FonteInfo
from ..utils import normalize_titulo, now_iso, today_iso
from .. import geo as _geo

SOURCE_NAME = "Finishers"
BASE = "https://www.finishers.com"
EVENT_URL = BASE + "/course/{slug}"

# Last-known Typesense search-only credentials (extracted from the bundle on
# 2026-06-10). _get_ts_config() refreshes these from the live bundle each run;
# these are only the fallback if extraction fails.
_TS_HOST_FALLBACK = "vn2qtcjsbg0ea481p-1.a1.typesense.net"
_TS_KEY_FALLBACK = "G1BPjGr3KDU7n6yylcfOREpRVGUBpKYW"

_PER_PAGE = 250
_MAX_PAGES = 80  # safety bound (≈20k docs); road set is ~11k worldwide

_TS_CONFIG_RE = re.compile(
    r'host:"([a-z0-9-]+\.[a-z0-9]+\.typesense\.net)"'
    r'[^{}]{0,160}?apiKey:"([A-Za-z0-9]{16,})"'
)
_CHUNK_RE = re.compile(r'/_next/static/chunks/[0-9]+-[a-f0-9]+\.js')

# region-name prefixes Finishers prepends in various languages
_REGION_PREFIX_RE = re.compile(
    r"^(?:state of|estado de|estado do|état de|etat de|région|regione|provincia|"
    r"province|bundesland|land)\s+", re.IGNORECASE)

_CANONICAL = [(42.195, 41.0, 43.0), (21.097, 20.5, 21.5)]


def _get_ts_config() -> tuple[str, str]:
    """Extract the Typesense host + search key from the live JS bundle.

    Mirrors tf_sports' token-from-bundle approach so credential rotation
    doesn't silently break the source. Falls back to the last-known constants.
    """
    try:
        html = get(f"{BASE}/courses").text
        for chunk in dict.fromkeys(_CHUNK_RE.findall(html)):  # dedupe, keep order
            try:
                js = get(f"{BASE}{chunk}").text
            except Exception:
                continue
            m = _TS_CONFIG_RE.search(js)
            if m:
                print(f"[{SOURCE_NAME}] typesense config extracted from {chunk}")
                return m.group(1), m.group(2)
        print(f"[{SOURCE_NAME}] config not found in bundle — using fallback")
    except Exception as e:
        print(f"[{SOURCE_NAME}] config extraction failed ({e}) — using fallback")
    return _TS_HOST_FALLBACK, _TS_KEY_FALLBACK


def _search(host: str, key: str, page: int, now_unix: int) -> dict:
    body = {"searches": [{
        "collection": "races",
        "q": "*",
        "query_by": "eventName",
        "filter_by": f"raceDiscipline:=road && raceDate:>={now_unix}",
        "sort_by": "raceDate:asc",
        "per_page": _PER_PAGE,
        "page": page,
    }]}
    resp = httpx.post(
        f"https://{host}/multi_search",
        params={"x-typesense-api-key": key},
        json=body, timeout=30,
        headers={"Accept": "application/json", "Origin": BASE, "Referer": BASE + "/"},
    )
    resp.raise_for_status()
    return resp.json()["results"][0]


def _canon(km: float) -> float:
    for canon, lo, hi in _CANONICAL:
        if lo <= km <= hi:
            return canon
    return km


def _distance(doc: dict):
    """Return a Distancia.km value (float km, or '<n> mi' string) or None."""
    raw = doc.get("raceDistance")
    unit = (doc.get("raceDistanceUnit") or "meters").lower()
    if not raw or raw <= 0:
        return None
    if "mile" in unit or unit == "mi":
        miles = round(raw, 2)
        return f"{miles:g} mi"
    # meters / kilometers → km
    km = raw / 1000.0 if raw > 500 else float(raw)
    if not (1.0 <= km <= 300.0):
        return None
    return _canon(round(km, 3))


def _estado(doc: dict, pais: str) -> str:
    """Match the event's region name to a subdivision code offline (no Nominatim).

    The pipeline's _resolve_missing_locations() fills any that stay empty.
    """
    for key in ("level1_pt", "level1_en", "level1"):
        name = doc.get(key)
        if not name:
            continue
        for candidate in (name, _REGION_PREFIX_RE.sub("", name)):
            code = _geo._match_subdiv(pais, candidate)
            if code:
                return code
    return ""


def _event_date(docs: list[dict]) -> str:
    for d in docs:
        iso = d.get("editionStartDate")
        if iso and re.fullmatch(r"\d{4}-\d{2}-\d{2}", iso):
            return iso
    # fallback: raceDate unix → date
    ts = min((d.get("raceDate") or 0) for d in docs)
    if ts:
        return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
    return ""


def scrape() -> list[Corrida]:
    host, key = _get_ts_config()
    now_unix = int(time.time())

    by_event: dict[str, list[dict]] = defaultdict(list)
    seen_total = 0
    for page in range(1, _MAX_PAGES + 1):
        try:
            res = _search(host, key, page, now_unix)
        except Exception as e:
            print(f"[{SOURCE_NAME}] erro na página {page}: {e}")
            break
        hits = res.get("hits") or []
        if not hits:
            break
        for h in hits:
            doc = h.get("document") or {}
            eid = doc.get("eventId")
            if eid:
                by_event[eid].append(doc)
        seen_total += len(hits)
        if seen_total >= (res.get("found") or 0):
            break

    today = today_iso()
    now = now_iso()
    corridas: list[Corrida] = []
    for eid, docs in by_event.items():
        head = docs[0]
        titulo = normalize_titulo(head.get("eventName") or "")
        if not titulo:
            continue
        data_evento = _event_date(docs)
        if not data_evento or data_evento < today:
            continue

        seen_km: set = set()
        distancias: list[Distancia] = []
        for d in docs:
            km = _distance(d)
            if km is not None and km not in seen_km:
                seen_km.add(km)
                distancias.append(Distancia(km=km, data=None, horario=None))
        if not distancias:
            continue
        distancias.sort(key=lambda x: x.km if isinstance(x.km, (int, float)) else 9e9)

        pais = (head.get("countryCode") or "").upper()
        if not pais:
            continue
        cidade = head.get("city") or ""
        estado = _estado(head, pais)
        localizacao = ", ".join(p for p in (cidade, estado) if p) or cidade

        slug = head.get("eventSlug")
        if not slug:
            continue
        link = EVENT_URL.format(slug=slug)

        image = head.get("image")
        imagem = (f"https://res.cloudinary.com/kavval/image/upload/q_auto:good,f_auto/{image}"
                  if image else None)

        fonte = FonteInfo(
            nome=SOURCE_NAME,
            link_evento=link,
            links_inscricao=[link],
            tipo="calendario",
        )
        corridas.append(Corrida(
            id=f"finishers_{eid}",
            titulo=titulo,
            data_evento=data_evento,
            horario=None,
            localizacao=localizacao,
            cidade=cidade,
            estado=estado,
            pais=pais,
            distancias=distancias,
            imagem_url=imagem,
            inscricoes_abertas=None,
            periodo_inscricao=None,
            fontes=[fonte],
            miss_count=0,
            first_seen_at=now,
            updated_at=now,
        ))

    print(f"[{SOURCE_NAME}] {len(corridas)} corridas (de {len(by_event)} eventos road)")
    return corridas
