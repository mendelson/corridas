"""Scraper for Race Roster (raceroster.com) — North American race registration.

Race Roster hosts thousands of running events, primarily in the US and Canada.
Uses the public search API at search.raceroster.com (no auth required).

API: https://search.raceroster.com/search?q=<term>&l=100&p=<page>
  - l: page size (max 100); p: 0-based page number
  - No server-side upcoming filter — filter client-side by event.category == "upcoming"
  - No auth required; no rate limiting observed

Multiple search terms cover distinct running event types; results deduped by eventId.
"""
from __future__ import annotations
import re
from datetime import date, timedelta

from ..http_client import get
from .. import geo as _geo
from ..models import Corrida, Distancia, FonteInfo
from ..utils import normalize_titulo, now_iso, today_iso

SOURCE_NAME = "Race Roster"
_SEARCH_API = "https://search.raceroster.com/search"
_PAGE_SIZE  = 100

_LOOKAHEAD_DAYS = 365

_SEARCH_TERMS = ["running", "marathon", "5k", "10k", "half marathon", "trail run"]

_NON_RUNNING = re.compile(
    r"\b(triathlon|duathlon|aquathlon|aquabike|cycling|cycle|cyclist"
    r"|swim\s*meet|swimming|open\s*water|paddle|kayak|rowing"
    r"|spartan|obstacle|ocr|crossfit|yoga|golf|soccer|tennis"
    r"|football|hockey|skating|skiing|snowshoe)\b",
    re.IGNORECASE,
)

_ISO_TO_PT: dict[str, str] = {
    "CA": "Canadá",      "US": "EUA",           "GB": "Reino Unido",
    "AU": "Austrália",   "NZ": "Nova Zelândia",  "IE": "Irlanda",
    "DE": "Alemanha",    "FR": "França",         "ES": "Espanha",
    "MX": "México",      "BR": "Brasil",         "ZA": "África do Sul",
    "JP": "Japão",       "KR": "Coreia do Sul",  "NL": "Países Baixos",
    "BE": "Bélgica",     "CH": "Suíça",          "AT": "Áustria",
    "SE": "Suécia",      "NO": "Noruega",        "DK": "Dinamarca",
    "FI": "Finlândia",   "PT": "Portugal",       "IT": "Itália",
    "PL": "Polônia",     "CZ": "República Tcheca",
}

_CA_PROVINCES: frozenset[str] = frozenset({
    "AB", "BC", "MB", "NB", "NL", "NS", "NT", "NU", "ON", "PE", "QC", "SK", "YT",
})
_US_STATES: frozenset[str] = frozenset({
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID",
    "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS",
    "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK",
    "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV",
    "WI", "WY", "DC",
})


# ---------------------------------------------------------------------------
def scrape() -> list[Corrida]:
    today_s  = today_iso()
    end_date = (date.today() + timedelta(days=_LOOKAHEAD_DAYS)).isoformat()

    seen_ids: set[int] = set()
    raw: list[dict] = []
    for term in _SEARCH_TERMS:
        for ev in _fetch_term(term):
            eid = ev.get("eventId")
            if eid and eid not in seen_ids:
                seen_ids.add(eid)
                raw.append(ev)

    print(f"[{SOURCE_NAME}] {len(raw)} eventos únicos após dedup")

    corridas, skipped = [], 0
    for ev in raw:
        c = _parse_event(ev, today_s, end_date)
        if c:
            corridas.append(c)
        else:
            skipped += 1

    print(f"[{SOURCE_NAME}] {len(corridas)} corridas válidas ({skipped} ignoradas)")
    return corridas


def _fetch_term(term: str) -> list[dict]:
    results: list[dict] = []
    page = -1
    while True:
        page += 1
        try:
            resp = get(_SEARCH_API, params={"q": term, "l": _PAGE_SIZE, "p": page},
                       source=SOURCE_NAME, timeout=30)
        except Exception as e:
            print(f"[{SOURCE_NAME}] erro '{term}' p{page}: {e}")
            break
        if resp.status_code != 200:
            print(f"[{SOURCE_NAME}] HTTP {resp.status_code} '{term}' p{page}")
            break
        try:
            data = resp.json()
        except Exception:
            break

        batch = data.get("data") or []
        if not batch:
            break
        results.extend(batch)

        if all(ev.get("category") == "past" for ev in batch):
            break  # upcoming events exhausted for this term
        if not data.get("meta", {}).get("nextPage"):
            break

    upcoming_count = sum(1 for e in results if e.get("category") == "upcoming")
    print(f"[{SOURCE_NAME}] '{term}': {upcoming_count} upcoming de {len(results)}")
    return results


# ---------------------------------------------------------------------------
_MI_RE = re.compile(r"^(\d+(?:\.\d+)?)\s*mi(?:le)?$", re.IGNORECASE)
_KM_RE = re.compile(r"^(\d+(?:\.\d+)?)\s*km?$",       re.IGNORECASE)


def _parse_dist_str(s: str) -> "float | str | None":
    s = s.strip()
    m = _MI_RE.match(s)
    if m:
        n = float(m.group(1))
        return f"{int(n) if n == int(n) else n:g} mi"
    m = _KM_RE.match(s)
    if m:
        n = float(m.group(1))
        return n if 1 <= n <= 250 else None
    return None


def _parse_distances(ev: dict) -> list[Distancia]:
    seen: set = set()
    result: list[Distancia] = []

    for raw in (ev.get("distances") or []):
        if not isinstance(raw, str):
            continue
        km = _parse_dist_str(raw)
        if km is not None and km not in seen:
            seen.add(km)
            result.append(Distancia(km=km, data=None, horario=None))

    if not result:
        for sub in (ev.get("subEvents") or []):
            raw = sub.get("distance") or ""
            if not raw:
                continue
            km = _parse_dist_str(raw)
            if km is not None and km not in seen:
                seen.add(km)
                result.append(Distancia(km=km, data=None, horario=None))

    if not result:
        name = (ev.get("name") or "").lower()
        if "marathon" in name and "half" not in name:
            result.append(Distancia(km=42.195, data=None, horario=None))
        elif "half" in name:
            result.append(Distancia(km=21.097, data=None, horario=None))

    return result


def _has_running_subevents(ev: dict) -> bool:
    subs = ev.get("subEvents") or []
    if not subs:
        return True  # no subEvent type info — trust the search query
    return any((sub.get("eventType") or "").lower() == "running" for sub in subs)


# ---------------------------------------------------------------------------
def _parse_event(ev: dict, today: str, end_date: str) -> "Corrida | None":
    if ev.get("category") != "upcoming":
        return None

    name_raw = (ev.get("name") or "").strip()
    if not name_raw:
        return None

    titulo = normalize_titulo(name_raw)
    if not titulo or len(titulo) < 4:
        return None

    if _NON_RUNNING.search(titulo):
        return None

    if not _has_running_subevents(ev):
        return None

    date_raw = ev.get("date") or ""
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", str(date_raw))
    if not m:
        return None
    data_evento = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    if data_evento < today or data_evento > end_date:
        return None

    distancias = _parse_distances(ev)
    if not distancias:
        return None

    loc    = ev.get("location") or {}
    city   = (loc.get("city") or "").strip()
    prov   = loc.get("province") or {}
    state  = (prov.get("abbreviation") or "").strip().upper()
    pais   = (loc.get("countryISO") or "US").strip().upper()

    if pais == "CA":
        estado, country_pt = (state if state in _CA_PROVINCES else ""), "Canadá"
    elif pais == "US":
        estado, country_pt = (state if state in _US_STATES else ""), "EUA"
    else:
        estado, country_pt = "", _ISO_TO_PT.get(pais, pais)

    # Try geo resolution for any unresolved state.
    # Trust the cache even when it disagrees with the API's countryISO —
    # the RaceRoster API occasionally mislabels countries (e.g. Eswatini as ZA).
    if not estado and city:
        _r_pais, _r_estado = _geo.resolve(city, "", pais)
        if _r_pais not in ("??", ""):
            if _r_pais != pais:
                pais = _r_pais
                country_pt = _ISO_TO_PT.get(pais, pais)
            estado = _r_estado or ""

    if not estado:
        return None

    localizacao = ", ".join(p for p in (city, estado or country_pt) if p) or country_pt or pais

    link  = ev.get("url") or f"https://raceroster.com/events/{ev.get('eventId', '')}"
    image = ev.get("logo") or None
    year  = data_evento[:4]
    eid   = ev.get("eventId") or 0
    now   = now_iso()

    return Corrida(
        id=f"raceroster_{eid}_{year}",
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
