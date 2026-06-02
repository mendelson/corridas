"""Scraper for correrbrasilia.com.br/calendario/

Parses JSON-LD schema.org/Event blocks embedded by the EventOn WordPress
plugin — more reliable than trying to parse the calendar widget's HTML.
"""
from __future__ import annotations
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup

from ..http_client import get
from ..models import Corrida, Distancia, FonteInfo
from ..utils import normalize_titulo, slugify, now_iso, today_iso
from .. import geo as _geo

URL = "https://correrbrasilia.com.br/calendario/"
SOURCE_NAME = "Correr Brasília"

_TIME_RE = re.compile(
    r"\b(\d{1,2})[hH:]([0-5]\d)\s*(?:min\s*)?[hH]?\b(?!\s*[kK])"
    r"|\b(\d{1,2})\s*[hH]\b(?!\s*\d)",
    re.IGNORECASE,
)


def _fetch_event_page(url: str) -> tuple[list[Distancia], str | None]:
    """Fetch the individual event page and extract distances and horario."""
    try:
        resp = get(url)
        if resp.status_code != 200:
            return [], None
        soup = BeautifulSoup(resp.text, "lxml")
        # Try JSON-LD first
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "")
            except Exception:
                continue
            if not isinstance(data, dict) or data.get("@type") != "Event":
                continue
            desc = data.get("description") or ""
            dists = _extract_distances(desc, data.get("name") or "")
            _, horario = _parse_start_date(data.get("startDate") or "")
            if dists:
                return dists, horario
        # Fallback: parse free text
        text = soup.get_text(" ", strip=True)
        dists = _extract_distances(text, "")
        horario = _extract_horario(text)
        return dists, horario
    except Exception:
        return [], None


def _extract_horario(text: str) -> str | None:
    if not text:
        return None
    m = _TIME_RE.search(text)
    if not m:
        return None
    if m.group(1) is not None:
        h, mi = int(m.group(1)), int(m.group(2))
    else:
        h, mi = int(m.group(3)), 0
    if 4 <= h <= 23 and 0 <= mi <= 59:
        return f"{h:02d}:{mi:02d}"
    return None


def scrape() -> list[Corrida]:
    try:
        resp = get(URL)
        resp.raise_for_status()
    except Exception as e:
        print(f"[{SOURCE_NAME}] erro ao buscar {URL}: {e}")
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    today = today_iso()
    now = now_iso()

    # First pass: parse all JSON-LD events from the listing page
    candidates: list[dict] = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except Exception:
            continue
        if not isinstance(data, dict) or data.get("@type") != "Event":
            continue
        candidates.append(data)

    corridas: list[Corrida] = []
    seen_ids: set[str] = set()

    # Identify events that need a detail-page fetch (no distances or no horario)
    needs_detail: list[tuple[dict, str]] = []
    first_pass: list[Corrida] = []
    for data in candidates:
        try:
            c = _parse_event(data, today, now)
        except Exception as e:
            print(f"[{SOURCE_NAME}] erro ao parsear evento: {e}")
            continue
        if c is None:
            continue
        if not c.distancias or not c.horario:
            url = data.get("url") or ""
            if url and url != URL:
                needs_detail.append((data, url))
            # keep in first_pass without distancias/horario — will be enriched or dropped
        first_pass.append(c)

    # Second pass: fetch detail pages for events still missing distances or horario
    detail_map: dict[str, tuple[list[Distancia], str | None]] = {}
    if needs_detail:
        def _fetch(item: tuple[dict, str]) -> tuple[str, list[Distancia], str | None]:
            ev_data, url = item
            dists, horario = _fetch_event_page(url)
            return url, dists, horario

        with ThreadPoolExecutor(max_workers=8) as ex:
            futures = {ex.submit(_fetch, item): item for item in needs_detail}
            for fut in as_completed(futures):
                url, dists, horario = fut.result()
                detail_map[url] = (dists, horario)

    for data in candidates:
        try:
            c = _parse_event(data, today, now)
        except Exception:
            continue
        if c is None:
            continue

        event_url = data.get("url") or ""
        if (not c.distancias or not c.horario) and event_url in detail_map:
            extra_dists, extra_horario = detail_map[event_url]
            if not c.distancias and extra_dists:
                c = _replace_distancias(c, extra_dists)
            if not c.horario and extra_horario:
                c = _replace_horario(c, extra_horario)

        if not c.distancias:
            print(f"[{SOURCE_NAME}] sem distâncias, pulando: {c.titulo!r}")
            continue
        if not c.horario:
            print(f"[{SOURCE_NAME}] sem horário, pulando: {c.titulo!r}")
            continue

        if c.id not in seen_ids:
            seen_ids.add(c.id)
            corridas.append(c)

    print(f"[{SOURCE_NAME}] {len(corridas)} corridas encontradas")
    return corridas


def _replace_distancias(c: "Corrida", dists: list[Distancia]) -> "Corrida":
    from dataclasses import replace
    return replace(c, distancias=dists)


def _replace_horario(c: "Corrida", horario: str) -> "Corrida":
    from dataclasses import replace
    return replace(c, horario=horario)


def _parse_event(ev: dict, today: str, now: str) -> Corrida | None:
    titulo_raw = normalize_titulo(ev.get("name") or "")
    if not titulo_raw or len(titulo_raw) < 3:
        return None
    # Keep the parenthetical distances in the title — it distinguishes entries like
    # "Live!42K - Brasília 2026 (5km e 10km)" from "Live!42K - Brasília 2026 (21km e 42km)".
    # Stripping them caused the merger to collapse distinct events with different distances.
    titulo = titulo_raw

    if _NON_RUNNING_RE.search(titulo_raw):
        return None  # orienteering / non-running event
    if _KIDS_RE.search(titulo_raw):
        return None  # kids-only event (e.g. Marotinga) — no adult distances

    date_str, horario = _parse_start_date(ev.get("startDate") or "")
    if date_str and date_str < today:
        return None

    # Use EventOn @id ("event_44938_0") when present for a stable key;
    # otherwise fall back to slug+year so IDs never embed the run date.
    eid = ev.get("@id") or ""
    if eid and re.match(r"event_\d+", eid):
        stable_id = f"correrbsb_{eid}"
    else:
        year = date_str[:4] if date_str else "sd"
        stable_id = f"correrbsb_{slugify(titulo[:50])}_{year}"

    url = ev.get("url") or URL
    image = ev.get("image") or None

    location_raw = ev.get("location") or []
    if isinstance(location_raw, dict):
        location_raw = [location_raw]
    place = location_raw[0] if location_raw else {}
    place_name = place.get("name") or ""
    address = place.get("address") or {}
    street = address.get("streetAddress") or ""

    address_locality = address.get("addressLocality") or ""
    address_region = address.get("addressRegion") or ""

    # Use addressLocality as city; fall back to "Brasília" (this calendar is Brasília-focused)
    city = address_locality or "Brasília"

    # Resolve estado: prefer addressRegion if it's a valid UF code, then geocode
    if address_region:
        estado = _geo.validate_estado("BR", address_region.strip())
        if not estado:
            _, estado = _geo.resolve(city, "", "BR")
        estado = estado or "DF"
    else:
        geo_query = ", ".join(p for p in [city, place_name, street] if p) or "Brasília, DF"
        _, estado = _geo.resolve(geo_query, "", "BR")
        estado = estado or "DF"

    localizacao = f"{city}, {estado}"

    desc = ev.get("description") or ""
    distancias = _extract_distances(desc, titulo_raw)

    return Corrida(
        id=stable_id,
        titulo=titulo,
        data_evento=date_str or "",
        horario=horario,
        localizacao=localizacao,
        cidade=city,
        estado=estado,
        pais="BR",
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


def _parse_start_date(raw: str) -> tuple[str, str | None]:
    """Parse "2026-8-8T16:00-3:00" → ("2026-08-08", "16:00")."""
    if not raw:
        return "", None
    m = re.match(r"(\d{4})-(\d{1,2})-(\d{1,2})T(\d{2}:\d{2})", raw)
    if not m:
        return "", None
    year, month, day, time_part = m.groups()
    return f"{year}-{int(month):02d}-{int(day):02d}", time_part


# Canonical distance windows: snap noisy values from descriptions
# to the exact standard distance (matches ativo.py / mks_esportes.py).
_CANONICAL = [(42.195, 41.5, 43.0), (21.097, 20.5, 21.5)]

# Orienteering and other non-running events — skip silently
_NON_RUNNING_RE = re.compile(
    r"\borientak?[çc]|\bse orienta\b|\bbuss?ola\b|\borienteering\b"
    r"|\bciclismo\b|\bbike\b|\bnatação\b|\btriathlon\b",
    re.IGNORECASE,
)

# Kids-only events — no adult distances exist for these. "Marotinga" is a
# Brasília kids-run brand whose title carries no "kids"/"infantil" marker,
# so it must be matched by name. Mirrors central_da_corrida._KIDS_RE.
_KIDS_RE = re.compile(
    r"\bkids?\b|\binfantil\b|\bmarotinga\b|\bpezinho\s+veloz\b",
    re.IGNORECASE,
)

# Matches 2+ distances listed together: "7km e 14km", "7km, 14km, 21km", "7K|14K"
_DIST_LIST_RE = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*[kK][mM]?"
    r"(?:\s*(?:,|e|ou|/|\|)\s*\d+(?:[.,]\d+)?\s*[kK][mM]?)+",
    re.IGNORECASE,
)



def _extract_distances(desc: str, titulo: str = "") -> list[Distancia]:
    """Extract race distances.

    Priority:
      1. Grouped list in description ("7km e 14km") — the EventOn plugin embeds
         explicit "Distância: Xkm e Ykm" metadata in the description, making this
         the most reliable source for the specific distances offered at this edition.
      2. Any km mention in description.
      3. Parenthetical hint in title as last resort.
    """
    # Priority 1: grouped list pattern in description (e.g. "Distância: 5km e 10km")
    values = _parse_km_values_from_list(desc, min_km=1.0)
    if not values:
        # Priority 2: any km mention in description
        values = _parse_km_values(desc, min_km=1.0)
    if not values:
        # Priority 3: parenthetical hint in title only
        paren = re.search(r"\([^)]*\d+\s*[kK][mM]?[^)]*\)", titulo)
        if paren:
            values = _parse_km_values(paren.group(0), min_km=1.0)
    return sorted(
        [Distancia(km=km, data=None, horario=None) for km in values[:8]],
        key=lambda d: float(d.km),
    )


def _filter_km_values(raw_values: list[float], min_km: float) -> list[float]:
    seen: list[float] = []
    for raw in raw_values:
        if raw < min_km or raw > 200:
            continue
        km = raw
        for canon, lo, hi in _CANONICAL:
            if lo <= raw <= hi:
                km = canon
                break
        if any(abs(km - s) < 0.5 for s in seen):
            continue
        seen.append(km)
    return seen


def _parse_km_values_from_list(text: str, min_km: float) -> list[float]:
    """Extract distances only from grouped list patterns like '7km e 14km'."""
    raw: list[float] = []
    for list_m in _DIST_LIST_RE.finditer(text):
        for m in re.finditer(r"(\d+(?:[.,]\d+)?)\s*[kK][mM]?", list_m.group(0), re.IGNORECASE):
            try:
                raw.append(float(m.group(1).replace(",", ".")))
            except ValueError:
                pass
    return _filter_km_values(raw, min_km)


def _parse_km_values(text: str, min_km: float) -> list[float]:
    raw: list[float] = []
    for m in re.finditer(r"\b(\d+(?:[.,]\d+)?)\s*[kK][mM]?\b", text):
        try:
            raw.append(float(m.group(1).replace(",", ".")))
        except ValueError:
            continue
    return _filter_km_values(raw, min_km)
