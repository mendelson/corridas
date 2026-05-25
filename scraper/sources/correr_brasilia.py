"""Scraper for correrbrasilia.com.br/calendario/

Parses JSON-LD schema.org/Event blocks embedded by the EventOn WordPress
plugin — more reliable than trying to parse the calendar widget's HTML.
"""
from __future__ import annotations
import json
import re
from bs4 import BeautifulSoup

from ..http_client import get
from ..models import Corrida, Distancia, FonteInfo
from ..utils import normalize_titulo, slugify, now_iso, today_iso
from .. import geo as _geo

URL = "https://correrbrasilia.com.br/calendario/"
SOURCE_NAME = "Correr Brasília"


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

    corridas: list[Corrida] = []
    seen_ids: set[str] = set()

    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except Exception:
            continue
        if not isinstance(data, dict) or data.get("@type") != "Event":
            continue
        try:
            c = _parse_event(data, today, now)
        except Exception as e:
            print(f"[{SOURCE_NAME}] erro ao parsear evento: {e}")
            continue
        if c and c.id not in seen_ids:
            seen_ids.add(c.id)
            corridas.append(c)

    print(f"[{SOURCE_NAME}] {len(corridas)} corridas encontradas")
    return corridas


def _parse_event(ev: dict, today: str, now: str) -> Corrida | None:
    titulo_raw = normalize_titulo(ev.get("name") or "")
    if not titulo_raw or len(titulo_raw) < 3:
        return None
    # Keep the parenthetical distances in the title — it distinguishes entries like
    # "Live!42K - Brasília 2026 (5km e 10km)" from "Live!42K - Brasília 2026 (21km e 42km)".
    # Stripping them caused the merger to collapse distinct events with different distances.
    titulo = titulo_raw

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

    geo_query = ", ".join(p for p in [place_name, street] if p) or "Brasília, DF"
    _, estado = _geo.resolve(geo_query, "", "BR")
    estado = estado or "DF"
    city = place_name.split(",")[0].strip() if place_name else "Brasília"
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
