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
    titulo = normalize_titulo(ev.get("name") or "")
    if not titulo or len(titulo) < 3:
        return None

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
    distancias = _extract_distances(desc, titulo)

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


def _extract_distances(desc: str, titulo: str = "") -> list[Distancia]:
    """Extract race distances from description (primary) with title as fallback.

    Canonical ranges snap nearby values to exact distances:
      41.5–43.0 km → 42.195 (maratona)
      20.5–21.5 km → 21.097 (meia-maratona)
    Near-dedup (0.5 km window) prevents duplicates from repeated mentions.
    """
    values = _parse_km_values(desc, min_km=1.0)
    if not values:
        values = _parse_km_values(titulo, min_km=1.0)
    return sorted(
        [Distancia(km=km, data=None, horario=None) for km in values],
        key=lambda d: float(d.km),
    )


def _parse_km_values(text: str, min_km: float) -> list[float]:
    seen: list[float] = []
    for m in re.finditer(r"\b(\d+(?:[.,]\d+)?)\s*[kK][mM]?\b", text):
        try:
            raw = float(m.group(1).replace(",", "."))
        except ValueError:
            continue
        if raw < min_km or raw > 200:
            continue
        # Snap to canonical distances (meia-maratona, maratona)
        km = raw
        for canon, lo, hi in _CANONICAL:
            if lo <= raw <= hi:
                km = canon
                break
        # Near-dedup: skip if already seen this canonical value
        if any(abs(km - s) < 0.5 for s in seen):
            continue
        seen.append(km)
    return seen
