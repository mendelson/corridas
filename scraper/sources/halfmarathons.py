"""Scraper for HalfMarathons.net — US half-marathon, 10K, 5K calendar.

WordPress REST API at /wp-json/wp/v2/races.  Each post carries race
metadata in `meta` and state in `class_list` as `race-calendar-{slug}`.
Distances stored as miles strings to match RunSignup convention.
"""
from __future__ import annotations
import re
from datetime import date, datetime, timezone

from ..http_client import get
from ..models import Corrida, Distancia, FonteInfo
from ..utils import normalize_titulo, slugify, now_iso, today_iso

SOURCE_NAME = "HalfMarathons.net"
_BASE       = "https://halfmarathons.net"
_API        = f"{_BASE}/wp-json/wp/v2/races"
_PER_PAGE   = 100
_MAX_PAGES  = 50   # 100 events/page × 50 = up to 5,000 events

# Slug → country label (PT). All non-US slugs explicitly mapped; US slugs fall
# through to the default "EUA" so they appear grouped under the USA in the filter.
_SLUG_COUNTRY: dict[str, str] = {
    "canada":         "Canadá",
    "united-kingdom": "Reino Unido",
    "australia":      "Austrália",
    "germany":        "Alemanha",
    "france":         "França",
    "ireland":        "Irlanda",
    "spain":          "Espanha",
    "italy":          "Itália",
    "netherlands":    "Países Baixos",
}

# US state slugs — presence means the event is in the USA
_US_STATE_SLUGS = {
    "alabama", "alaska", "arizona", "arkansas", "california", "colorado",
    "connecticut", "delaware", "district-of-columbia", "florida", "georgia",
    "hawaii", "idaho", "illinois", "indiana", "iowa", "kansas", "kentucky",
    "louisiana", "maine", "maryland", "massachusetts", "michigan", "minnesota",
    "mississippi", "missouri", "montana", "nebraska", "nevada", "new-hampshire",
    "new-jersey", "new-mexico", "new-york", "north-carolina", "north-dakota",
    "ohio", "oklahoma", "oregon", "pennsylvania", "rhode-island",
    "south-carolina", "south-dakota", "tennessee", "texas", "utah", "vermont",
    "virginia", "washington", "west-virginia", "wisconsin", "wyoming",
}

# Distance label → canonical km value or miles string
_DIST_MAP: dict[str, float | str] = {
    "marathon": 42.195,
    "half-marathon": 21.097,
    "10k": 10.0,
    "5k": 5.0,
    "10-mile": "10 mi",
    "15k": 15.0,
    "8k": 8.0,
    "4-mile": "4 mi",
    "5-mile": "5 mi",
}
_MI_RE = re.compile(r"^(\d+(?:\.\d+)?)-mile$", re.IGNORECASE)
_KM_RE = re.compile(r"^(\d+(?:\.\d+)?)k$",    re.IGNORECASE)


def scrape() -> list[Corrida]:
    today = today_iso()
    corridas: list[Corrida] = []

    for page in range(1, _MAX_PAGES + 1):
        try:
            resp = get(
                _API,
                params={"per_page": _PER_PAGE, "page": page},
                source=SOURCE_NAME,
                timeout=20,
            )
        except Exception as e:
            print(f"[{SOURCE_NAME}] page {page} erro: {e}")
            break

        if resp.status_code in (400, 404):
            break  # past end of results
        try:
            resp.raise_for_status()
        except Exception as e:
            print(f"[{SOURCE_NAME}] page {page} HTTP {resp.status_code}: {e}")
            break

        try:
            posts: list[dict] = resp.json()
        except Exception as e:
            print(f"[{SOURCE_NAME}] page {page} JSON erro: {e}")
            break

        if not posts:
            break

        for post in posts:
            c = _parse_post(post, today)
            if c:
                corridas.append(c)

        total_pages = int(resp.headers.get("X-WP-TotalPages", page))
        if page >= total_pages:
            break

    print(f"[{SOURCE_NAME}] {len(corridas)} corrida(s) encontrada(s)")
    return corridas


def _parse_post(post: dict, today: str) -> Corrida | None:
    meta: dict = post.get("meta") or {}

    # Date: Unix timestamp
    raw_ts = meta.get("date")
    if not raw_ts:
        return None
    try:
        data_evento = datetime.fromtimestamp(int(raw_ts), tz=timezone.utc).strftime("%Y-%m-%d")
    except (ValueError, OSError):
        return None

    if data_evento < today:
        return None

    title_rendered = (post.get("title") or {}).get("rendered") or ""
    titulo = normalize_titulo(_strip_html(title_rendered))
    if not titulo:
        return None

    # Determine country from class_list slugs; all events are estado=INT
    country = "EUA"  # default — the site is almost entirely US events
    for cls in (post.get("class_list") or []):
        slug = cls.replace("race-calendar-", "") if cls.startswith("race-calendar-") else None
        if not slug:
            continue
        if slug in _SLUG_COUNTRY:
            country = _SLUG_COUNTRY[slug]
            break
        if slug in _US_STATE_SLUGS:
            country = "EUA"
            break

    city: str = meta.get("city") or ""
    cidade = f"{city}, {country}" if city else country
    localizacao = cidade

    # Distances
    raw_distances: list[str] = meta.get("distance") or []
    distancias = _parse_distances(raw_distances)

    # Links
    reg_link: str = meta.get("registration-link") or post.get("link") or _BASE
    event_link: str = post.get("link") or reg_link

    # ID: stable from WP post ID + year
    post_id = post.get("id") or slugify(titulo)
    race_id = f"halfmarathons_{post_id}_{data_evento[:4]}"

    now = now_iso()
    return Corrida(
        id=race_id,
        titulo=titulo,
        data_evento=data_evento,
        horario=meta.get("starting-time") or None,
        localizacao=localizacao,
        cidade=cidade,
        estado="INT",
        distancias=distancias,
        imagem_url=None,
        inscricoes_abertas=None,
        periodo_inscricao=None,
        fontes=[FonteInfo(nome=SOURCE_NAME, link_evento=event_link, links_inscricao=[reg_link])],
        miss_count=0,
        first_seen_at=now,
        updated_at=now,
    )


def _parse_distances(raw: list[str]) -> list[Distancia]:
    seen: set[object] = set()
    result: list[Distancia] = []
    for label in raw:
        slug = label.lower().replace(" ", "-")
        if slug in _DIST_MAP:
            km = _DIST_MAP[slug]
        else:
            m = _MI_RE.match(slug)
            if m:
                km = f"{m.group(1)} mi"
            else:
                m = _KM_RE.match(slug)
                if m:
                    km = float(m.group(1))
                else:
                    continue
        key = km if isinstance(km, str) else round(float(km))
        if key not in seen:
            seen.add(key)
            result.append(Distancia(km=km, data=None, horario=None))
    return sorted(result, key=lambda d: float(str(d.km).replace(" mi", "")) if " mi" not in str(d.km) else float(str(d.km).replace(" mi", "")) * 1.60934)


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text).strip()
