"""Scraper for atletis.com.br — Brazilian multi-sport event platform.

Discovers events via the GeoJSON endpoint /events/coordinates that powers the
site's event map. Pre-filters by event name, then fetches each candidate page
and parses the embedded schema.org/SportsEvent JSON-LD for full details.

Brazilian-only platform — all events have pais="BR". State derived from
addressRegion (full state name) in JSON-LD, resolved via geo.validate_estado.
"""
from __future__ import annotations
import json
import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from ..http_client import get
from ..models import Corrida, Distancia, FonteInfo
from ..utils import normalize_titulo, now_iso, today_iso
from .. import geo as _geo

SOURCE_NAME = "Atletis"
_BASE = "https://www.atletis.com.br"
_GEOJSON_URL = f"{_BASE}/events/coordinates"

_RUNNING_KW = re.compile(
    r"\b(corrida|corrid|run|trail|rústica|rustica|maratona|meia|treinão|treinao|"
    r"ultra|cross\s*country|pedestre|desafio|5k|10k|21k|42k|"
    r"correndo|atletismo|corre\b)\b",
    re.IGNORECASE,
)

_NON_RUNNING = re.compile(
    r"\b(futeb|volei|vôlei|volley|sinuca|natação|natacao|ciclism|pedal\b|mtb|"
    r"bik[ei]\b|swim\b|tênis|tenis|crossfit|funcional|yoga|zumba|escal[aã]|"
    r"jiu.?jitsu|basquete|badminton|handebol|kayak|surf\b|boxe|muay|judo|"
    r"skate|beach.?tennis|patinação|patinacao|dança|danca|canastra|"
    r"cavalhada|futevolei|futevôlei|beach.?volei|dance\b)\b",
    re.IGNORECASE,
)

_RUNNING_SPORTS = re.compile(
    r"(corrida|run|trail|maratona|meia.maratona|atletismo|caminhada|rústica|rustica|ultra)",
    re.IGNORECASE,
)

_DATE_RE = re.compile(r"(\d{2})/(\d{2})/(\d{4})")
_DIST_RE = re.compile(r"\b(\d+(?:[.,]\d+)?)\s*[Kk][Mm]?\b")

_CANONICAL = [(42.195, 41.5, 43.0), (21.097, 20.5, 21.5)]


def _snap(km: float) -> float:
    for canon, lo, hi in _CANONICAL:
        if lo <= km <= hi:
            return canon
    return km


def scrape() -> list[Corrida]:
    today = today_iso()
    now = now_iso()

    try:
        resp = get(_GEOJSON_URL, source=SOURCE_NAME, timeout=20)
        resp.raise_for_status()
        geojson = resp.json()
    except Exception as e:
        print(f"[{SOURCE_NAME}] erro ao buscar mapa de eventos: {e}")
        return []

    features = geojson.get("features") or []
    candidates: list[tuple[str, str]] = []

    for feat in features:
        props = feat.get("properties") or {}
        url_path = props.get("url") or ""
        name = props.get("name") or ""
        date_raw = props.get("date") or ""

        if not url_path:
            continue

        # Pre-filter date: skip events clearly in the past
        m = _DATE_RE.search(date_raw)
        if m:
            try:
                d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
                if f"{y:04d}-{mo:02d}-{d:02d}" < today:
                    continue
            except (ValueError, IndexError):
                pass

        # Pre-filter name: skip clearly non-running events
        if _NON_RUNNING.search(name) and not _RUNNING_KW.search(name):
            continue

        full_url = _BASE + url_path if url_path.startswith("/") else url_path
        candidates.append((full_url, name))

    print(f"[{SOURCE_NAME}] {len(candidates)} candidatos de {len(features)} eventos")

    corridas: list[Corrida] = []
    _drops: dict[str, int] = {}
    for event_url, hint_name in candidates:
        try:
            c, reason = _scrape_event_dbg(event_url, hint_name, today, now)
            if c:
                corridas.append(c)
            else:
                _drops[reason] = _drops.get(reason, 0) + 1
                if "democracia" in event_url:
                    print(f"[DBG] democracia DROPPED reason={reason}")
        except Exception as e:
            _drops["exception"] = _drops.get("exception", 0) + 1
            print(f"[{SOURCE_NAME}] erro em {event_url}: {e}")

    print(f"[{SOURCE_NAME}] {len(corridas)} corridas encontradas")
    print(f"[DBG] drop reasons: {sorted(_drops.items(), key=lambda x:-x[1])}")
    print(f"[DBG] democracia in found: {any('4405' in f.link_evento for c in corridas for f in c.fontes)}")
    return corridas


def _scrape_event_dbg(url: str, hint_name: str, today: str, now: str):
    """Debug wrapper: returns (Corrida|None, drop_reason)."""
    try:
        resp = get(url, source=SOURCE_NAME, timeout=20)
        if resp.status_code != 200:
            return None, f"http_{resp.status_code}"
        html = resp.text
    except Exception as e:
        return None, f"fetch_exc_{type(e).__name__}"
    soup = BeautifulSoup(html, "lxml")
    ld: dict = {}
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            if isinstance(data, dict) and data.get("@type") == "SportsEvent":
                ld = data
                break
        except Exception:
            continue
    if not ld:
        return None, "no_jsonld"
    sport = ld.get("sport") or ""
    if sport and not _RUNNING_SPORTS.search(sport):
        return None, f"sport_filter:{sport[:20]}"
    if not (ld.get("name") or hint_name):
        return None, "no_title"
    start_raw = ld.get("startDate") or ""
    data_evento, _ = _parse_start_date(start_raw)
    if not data_evento:
        return None, "no_date"
    if data_evento < today:
        return None, "past_date"
    address = (ld.get("location") or {}).get("address") or {}
    city = address.get("addressLocality") or ""
    if not city:
        return None, "no_city"
    state_name = address.get("addressRegion") or ""
    estado = _geo.validate_estado("BR", state_name)
    if not estado and city:
        _, estado = _geo.resolve(city, "", "BR")
    if not estado:
        return None, f"no_estado(region={state_name[:15]})"
    dists = _parse_distances(ld.get("offers") or [])
    if not dists:
        fb = " ".join(filter(None, [ld.get("name") or "", ld.get("description") or ""]))
        dists = _parse_distances_from_text(fb)
    if not dists:
        return None, "no_distancias"
    c = _scrape_event(url, hint_name, today, now)
    return (c, "ok") if c else (None, "scrape_event_none")


def _scrape_event(url: str, hint_name: str, today: str, now: str) -> Corrida | None:
    try:
        resp = get(url, source=SOURCE_NAME, timeout=20)
        if resp.status_code != 200:
            return None
        html = resp.text
    except Exception as e:
        print(f"[{SOURCE_NAME}] erro ao buscar {url}: {e}")
        return None

    soup = BeautifulSoup(html, "lxml")

    # Parse JSON-LD — look for @type: SportsEvent
    ld: dict = {}
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            if isinstance(data, dict) and data.get("@type") == "SportsEvent":
                ld = data
                break
        except Exception:
            continue

    if not ld:
        return None

    # Sport filter
    sport = ld.get("sport") or ""
    if sport and not _RUNNING_SPORTS.search(sport):
        # Only skip if sport is explicitly non-running; "Atletismo" etc. are OK
        return None

    # Title
    titulo = normalize_titulo(ld.get("name") or hint_name)
    if not titulo:
        return None

    # Date and time from startDate: "2026-05-31T07:00:00-03:00"
    start_raw = ld.get("startDate") or ""
    data_evento, horario = _parse_start_date(start_raw)
    if not data_evento:
        return None
    if data_evento < today:
        return None

    # Location
    location = ld.get("location") or {}
    address = location.get("address") or {}
    city = address.get("addressLocality") or ""
    state_name = address.get("addressRegion") or ""

    if not city:
        return None

    estado = _geo.validate_estado("BR", state_name)
    if not estado and city:
        _, estado = _geo.resolve(city, "", "BR")
    if not estado:
        return None

    localizacao = f"{city}, {estado}"

    # Distances from offers; fallback to title/description if none found
    distancias = _parse_distances(ld.get("offers") or [])
    if not distancias:
        fallback_text = " ".join(filter(None, [
            ld.get("name") or "",
            ld.get("description") or "",
        ]))
        distancias = _parse_distances_from_text(fallback_text)
    if not distancias:
        return None

    # Image
    imagem_url = ld.get("image") or None

    # ID from URL: /evento/slug-1234 → atletis_1234
    event_id = _extract_id(url)
    race_id = f"atletis_{event_id}"

    # Registration link: /ingressos/{slug}-{id}
    slug_part = url.rsplit("/", 1)[-1]
    reg_url = f"{_BASE}/ingressos/{slug_part}"

    return Corrida(
        id=race_id,
        titulo=titulo,
        data_evento=data_evento,
        horario=horario,
        localizacao=localizacao,
        cidade=city,
        estado=estado,
        pais="BR",
        distancias=distancias,
        imagem_url=imagem_url,
        inscricoes_abertas=_check_inscricoes(ld),
        periodo_inscricao=None,
        fontes=[FonteInfo(
            nome=SOURCE_NAME,
            link_evento=url,
            links_inscricao=[url],
            tipo="inscricao",
        )],
        miss_count=0,
        first_seen_at=now,
        updated_at=now,
    )


def _parse_start_date(raw: str) -> tuple[str, str | None]:
    """Parse '2026-05-31T07:00:00-03:00' → ('2026-05-31', '07:00')."""
    if not raw:
        return "", None
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})", raw)
    if not m:
        return "", None
    year, month, day, hour, minute = m.groups()
    return f"{year}-{month}-{day}", f"{hour}:{minute}"


def _extract_id(url: str) -> str:
    """Extract numeric event ID from URL like /evento/speed-burguer-run-3381."""
    last = url.rstrip("/").rsplit("/", 1)[-1]
    m = re.search(r"-(\d+)$", last)
    if m:
        return m.group(1)
    return last


def _parse_distances(offers: list) -> list[Distancia]:
    seen: set[float] = set()
    result: list[Distancia] = []
    for offer in offers:
        if not isinstance(offer, dict):
            continue
        name = offer.get("name") or ""
        for m in _DIST_RE.finditer(name):
            try:
                km = float(m.group(1).replace(",", "."))
            except ValueError:
                continue
            km = _snap(km)
            if km not in seen and 1.0 <= km <= 250.0:
                seen.add(km)
                result.append(Distancia(km=km, data=None, horario=None))
    return sorted(result, key=lambda d: float(d.km))


def _parse_distances_from_text(text: str) -> list[Distancia]:
    """Extract distances from free text, e.g. title or description.
    Matches '5K', '10km', '42K', '21.097km', etc.
    Falls back to marathon/half-marathon keywords when no numeric found.
    """
    seen: set[float] = set()
    result: list[Distancia] = []
    for m in _DIST_RE.finditer(text):
        try:
            km = float(m.group(1).replace(",", "."))
        except ValueError:
            continue
        km = _snap(km)
        if km not in seen and 1.0 <= km <= 250.0:
            seen.add(km)
            result.append(Distancia(km=km, data=None, horario=None))
    if not result:
        ltext = text.lower()
        if re.search(r"\b(maratona|marathon|42k)\b", ltext):
            is_half = bool(re.search(r"\b(meia|half|semi|21k)\b", ltext))
            if not is_half:
                result.append(Distancia(km=42.195, data=None, horario=None))
        if re.search(r"\b(meia\s+maratona|half\s+marathon|21k)\b", ltext):
            if 21.097 not in seen:
                result.append(Distancia(km=21.097, data=None, horario=None))
    return sorted(result, key=lambda d: float(d.km))


def _check_inscricoes(ld: dict) -> bool | None:
    """Return True if any offer has availability InStock, None if unknown."""
    offers = ld.get("offers") or []
    if isinstance(offers, dict):
        offers = [offers]
    has_instock = any(
        isinstance(o, dict) and "InStock" in (o.get("availability") or "")
        for o in offers
    )
    if has_instock:
        return True
    all_sold = all(
        isinstance(o, dict) and "InStock" not in (o.get("availability") or "")
        for o in offers
    ) if offers else False
    return None if not all_sold else False
