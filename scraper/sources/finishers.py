"""Scraper for finishers.com â Typesense `races` list + per-event start time.

finishers.com is a Next.js/Vercel site (no WAF â the old README "blocked like
Ahotu" note was never tested and is false). Two structured data sources:

1. A hosted **Typesense** cluster (search-only host+key in the public JS bundle)
   backs the race search. The `races` collection holds every race with its
   discipline, distance, date, location, slug â everything EXCEPT the start
   time. Worldwide; we keep `raceDiscipline:=road` (street running).

2. The **event page data route** `/_next/data/{buildId}/en/event/{slug}.json`
   carries `pageProps.races[].time` (the start time, e.g. "08:30:00"), which
   the search index omits.

Each event is enriched with its start time from (2) — horário is extracted
with maximum effort, though since 2026-07-11 it is no longer mandatory (events
without a published time are kept). Because that's one fetch per event, a persistent cache
(data/finishers_horarios.json, like data/geo_cache.json) means each event's
time is fetched once and reused; only new events are fetched on later runs, and
a per-run cap bounds the very first cold run. Events still without a published
time are kept and re-tried on later runs until a time appears.

Each Typesense doc is one race of an event; grouped by `eventId` into one
Corrida (eventNameâtitulo, editionStartDateâdata, raceDistanceâdistancias,
city+countryCodeâlocation via geo._match_subdiv, /course/{slug}âlink).
"""
from __future__ import annotations

import json
import re
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import httpx

from ..http_client import get
from ..models import Corrida, Distancia, FonteInfo
from ..utils import normalize_titulo, now_iso, today_iso
from .. import geo as _geo

SOURCE_NAME = "Finishers"
BASE = "https://www.finishers.com"
EVENT_URL = BASE + "/course/{slug}"

# Last-known Typesense search-only credentials (from the bundle 2026-06-10);
# refreshed from the live bundle each run, these are only the fallback.
_TS_HOST_FALLBACK = "vn2qtcjsbg0ea481p-1.a1.typesense.net"
_TS_KEY_FALLBACK = "G1BPjGr3KDU7n6yylcfOREpRVGUBpKYW"

_PER_PAGE = 250
_FETCH_WORKERS = 10

_CACHE_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "finishers_horarios.json"

_TS_CONFIG_RE = re.compile(
    r'host:"([a-z0-9-]+\.[a-z0-9]+\.typesense\.net)"'
    r'[^{}]{0,160}?apiKey:"([A-Za-z0-9]{16,})"'
)
_CHUNK_RE = re.compile(r'/_next/static/chunks/[0-9]+-[a-f0-9]+\.js')
_BUILDID_RE = re.compile(r'"buildId":"([A-Za-z0-9_-]+)"')

_REGION_PREFIX_RE = re.compile(
    r"^(?:state of|estado de|estado do|Ã©tat de|etat de|rÃ©gion|regione|provincia|"
    r"province|bundesland|land)\s+", re.IGNORECASE)

_CANONICAL = [(42.195, 41.0, 43.0), (21.097, 20.5, 21.5)]


# ---------------------------------------------------------------------------
# Live config from the JS bundle (resilient to credential / build rotation)
# ---------------------------------------------------------------------------

def _get_ts_config() -> tuple[str, str]:
    try:
        html = get(f"{BASE}/courses").text
        for chunk in dict.fromkeys(_CHUNK_RE.findall(html)):
            try:
                js = get(f"{BASE}{chunk}").text
            except Exception:
                continue
            m = _TS_CONFIG_RE.search(js)
            if m:
                return m.group(1), m.group(2)
    except Exception as e:
        print(f"[{SOURCE_NAME}] typesense config extraction failed ({e}); fallback")
    return _TS_HOST_FALLBACK, _TS_KEY_FALLBACK


def _get_build_id() -> str | None:
    for path in (f"{BASE}/en/courses", f"{BASE}/courses"):
        try:
            m = _BUILDID_RE.search(get(path).text)
            if m:
                return m.group(1)
        except Exception:
            continue
    return None


# ---------------------------------------------------------------------------
# Stage 1 â Typesense road race list
# ---------------------------------------------------------------------------

def _search(host: str, key: str, page: int, now_unix: int) -> dict:
    body = {"searches": [{
        "collection": "races", "q": "*", "query_by": "eventName",
        "filter_by": f"raceDiscipline:=road && raceDate:>={now_unix}",
        "sort_by": "raceDate:asc", "per_page": _PER_PAGE, "page": page,
    }]}
    resp = httpx.post(
        f"https://{host}/multi_search", params={"x-typesense-api-key": key},
        json=body, timeout=30,
        headers={"Accept": "application/json", "Origin": BASE, "Referer": BASE + "/"},
    )
    resp.raise_for_status()
    return resp.json()["results"][0]


# ---------------------------------------------------------------------------
# Stage 2 â per-event start time (cached)
# ---------------------------------------------------------------------------

def _load_cache() -> dict[str, str]:
    try:
        return json.loads(_CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_cache(cache: dict[str, str]) -> None:
    try:
        _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _CACHE_PATH.write_text(
            json.dumps(cache, ensure_ascii=False, sort_keys=True, indent=0),
            encoding="utf-8")
    except Exception as e:
        print(f"[{SOURCE_NAME}] nÃ£o consegui salvar o cache de horÃ¡rios: {e}")


def _fetch_time(slug: str, build_id: str | None) -> str | None:
    """Fetch the event page and return its earliest race start time as HH:MM."""
    payloads = []
    if build_id:
        try:
            r = httpx.get(f"{BASE}/_next/data/{build_id}/en/event/{slug}.json",
                          timeout=25, headers={"Accept": "application/json"})
            if r.status_code == 200:
                payloads.append(r.json())
        except Exception:
            pass
    if not payloads:  # fallback: parse __NEXT_DATA__ from the HTML page
        try:
            html = get(f"{BASE}/en/event/{slug}").text
            m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
            if m:
                payloads.append(json.loads(m.group(1)).get("props", {}))
        except Exception:
            return None
    for p in payloads:
        pp = p.get("pageProps") or p.get("props", {}).get("pageProps") or p
        times = []
        for race in (pp.get("races") or []):
            t = race.get("time")
            if isinstance(t, str) and re.match(r"\d{1,2}:\d{2}", t):
                times.append(t[:5])
        if times:
            return min(times)
    return None


# ---------------------------------------------------------------------------
# Field helpers
# ---------------------------------------------------------------------------

def _canon(km: float) -> float:
    for canon, lo, hi in _CANONICAL:
        if lo <= km <= hi:
            return canon
    return km


def _distance(doc: dict):
    raw = doc.get("raceDistance")
    unit = (doc.get("raceDistanceUnit") or "meters").lower()
    if not raw or raw <= 0:
        return None
    if "mile" in unit or unit == "mi":
        return f"{round(raw, 2):g} mi"
    km = raw / 1000.0 if raw > 500 else float(raw)
    if not (1.0 <= km <= 300.0):
        return None
    return _canon(round(km, 3))


def _estado(doc: dict, pais: str) -> str:
    for key in ("level1_pt", "level1_en", "level1"):
        name = doc.get(key)
        if not name:
            continue
        for cand in (name, _REGION_PREFIX_RE.sub("", name)):
            code = _geo._match_subdiv(pais, cand)
            if code:
                return code
    return ""


def _event_date(docs: list[dict]) -> str:
    for d in docs:
        iso = d.get("editionStartDate")
        if iso and re.fullmatch(r"\d{4}-\d{2}-\d{2}", iso):
            return iso
    ts = min((d.get("raceDate") or 0) for d in docs)
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d") if ts else ""


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def scrape() -> list[Corrida]:
    host, key = _get_ts_config()
    now_unix = int(time.time())

    by_event: dict[str, list[dict]] = defaultdict(list)
    seen = 0
    page = 0
    while True:  # no cap — paginate until the scan is exhausted (breaks below)
        page += 1
        try:
            res = _search(host, key, page, now_unix)
        except Exception as e:
            print(f"[{SOURCE_NAME}] erro na pÃ¡gina {page}: {e}")
            break
        hits = res.get("hits") or []
        if not hits:
            break
        for h in hits:
            doc = h.get("document") or {}
            if doc.get("eventId"):
                by_event[doc["eventId"]].append(doc)
        seen += len(hits)
        if seen >= (res.get("found") or 0):
            break
    print(f"[{SOURCE_NAME}] {len(by_event)} eventos road (de {seen} provas) no Typesense")

    # Stage 2: fill missing start times (cached), soonest events first, capped.
    cache = _load_cache()
    ordered = sorted(by_event.items(), key=lambda kv: _event_date(kv[1]) or "9999")
    todo = [(eid, docs[0].get("eventSlug")) for eid, docs in ordered
            if eid not in cache and docs[0].get("eventSlug")]
    if todo:
        build_id = _get_build_id()
        print(f"[{SOURCE_NAME}] buscando horÃ¡rio de {len(todo)} eventos novos (buildId={build_id})")
        with ThreadPoolExecutor(max_workers=_FETCH_WORKERS) as ex:
            futs = {ex.submit(_fetch_time, slug, build_id): eid for eid, slug in todo}
            for fut in as_completed(futs):
                eid = futs[fut]
                try:
                    cache[eid] = fut.result() or ""
                except Exception:
                    cache[eid] = ""
        _save_cache(cache)

    today = today_iso()
    now = now_iso()
    corridas: list[Corrida] = []
    for eid, docs in by_event.items():
        horario = cache.get(eid) or None
        # Horário no longer mandatory (policy 2026-07-11): keep the event without it.
        # if not horario:
        #     continue  # no published start time â skip (project requirement)

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
        slug = head.get("eventSlug")
        if not pais or not slug:
            continue
        cidade = head.get("city") or ""
        estado = _estado(head, pais)
        localizacao = ", ".join(p for p in (cidade, estado) if p) or cidade
        link = EVENT_URL.format(slug=slug)

        image = head.get("image")
        imagem = (f"https://res.cloudinary.com/kavval/image/upload/q_auto:good,f_auto/{image}"
                  if image else None)

        fonte = FonteInfo(nome=SOURCE_NAME, link_evento=link,
                          links_inscricao=[link], tipo="calendario")
        corridas.append(Corrida(
            id=f"finishers_{eid}", titulo=titulo, data_evento=data_evento,
            horario=horario, localizacao=localizacao, cidade=cidade,
            estado=estado, pais=pais, distancias=distancias, imagem_url=imagem,
            inscricoes_abertas=None, periodo_inscricao=None, fontes=[fonte],
            miss_count=0, first_seen_at=now, updated_at=now,
        ))

    print(f"[{SOURCE_NAME}] {len(corridas)} corridas encontradas")
    return corridas
