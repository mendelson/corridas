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
from .. import geo as _geo

SOURCE_NAME = "HalfMarathons.net"
_BASE       = "https://halfmarathons.net"
_API        = f"{_BASE}/wp-json/wp/v2/races"
_PER_PAGE   = 100

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

_SLUG_ISO2: dict[str, str] = {
    "canada":         "CA",
    "united-kingdom": "GB",
    "australia":      "AU",
    "germany":        "DE",
    "france":         "FR",
    "ireland":        "IE",
    "spain":          "ES",
    "italy":          "IT",
    "netherlands":    "NL",
}

# US state slug → ISO 3166-2:US code
_US_SLUG_TO_STATE: dict[str, str] = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
    "california": "CA", "colorado": "CO", "connecticut": "CT", "delaware": "DE",
    "district-of-columbia": "DC", "florida": "FL", "georgia": "GA",
    "hawaii": "HI", "idaho": "ID", "illinois": "IL", "indiana": "IN",
    "iowa": "IA", "kansas": "KS", "kentucky": "KY", "louisiana": "LA",
    "maine": "ME", "maryland": "MD", "massachusetts": "MA", "michigan": "MI",
    "minnesota": "MN", "mississippi": "MS", "missouri": "MO", "montana": "MT",
    "nebraska": "NE", "nevada": "NV", "new-hampshire": "NH", "new-jersey": "NJ",
    "new-mexico": "NM", "new-york": "NY", "north-carolina": "NC",
    "north-dakota": "ND", "ohio": "OH", "oklahoma": "OK", "oregon": "OR",
    "pennsylvania": "PA", "rhode-island": "RI", "south-carolina": "SC",
    "south-dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT",
    "vermont": "VT", "virginia": "VA", "washington": "WA",
    "west-virginia": "WV", "wisconsin": "WI", "wyoming": "WY",
}
_US_STATE_SLUGS = set(_US_SLUG_TO_STATE)

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
_MI_RE   = re.compile(r"^(\d+(?:\.\d+)?)-mile$", re.IGNORECASE)
_KM_RE   = re.compile(r"^(\d+(?:\.\d+)?)k$",    re.IGNORECASE)
_TIME_RE = re.compile(
    r"(\d{1,2}):(\d{2})\s*([AaPp][Mm])?|(\d{1,2})\s*[hH]\s*(\d{2})?",
)


def _normalize_time(raw: str | None) -> str | None:
    """Normalize starting-time to HH:MM. Handles '7:00 AM', '7:00 PM', '07:30', '7h00'."""
    if not raw:
        return None
    raw = raw.strip()
    m = _TIME_RE.search(raw)
    if not m:
        return None
    if m.group(1) is not None:
        h, mi = int(m.group(1)), int(m.group(2))
        ampm = (m.group(3) or "").upper()
        if ampm == "PM" and h != 12:
            h += 12
        elif ampm == "AM" and h == 12:
            h = 0
    else:
        h = int(m.group(4))
        mi = int(m.group(5)) if m.group(5) else 0
    if not (0 <= h <= 23 and 0 <= mi <= 59):
        return None
    return f"{h:02d}:{mi:02d}"


def scrape() -> list[Corrida]:
    today = today_iso()
    corridas: list[Corrida] = []

    page = 0
    while True:
        page += 1
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

    # Determine country and state from class_list slugs
    country = "EUA"  # default — the site is almost entirely US events
    pais = "US"
    estado = ""
    for cls in (post.get("class_list") or []):
        slug = cls.replace("race-calendar-", "") if cls.startswith("race-calendar-") else None
        if not slug:
            continue
        if slug in _SLUG_COUNTRY:
            country = _SLUG_COUNTRY[slug]
            pais = _SLUG_ISO2[slug]
            break
        if slug in _US_STATE_SLUGS:
            country = "EUA"
            pais = "US"
            estado = _US_SLUG_TO_STATE[slug]
            break

    city: str = meta.get("city") or ""
    if not estado and city:
        _, estado = _geo.resolve(city, "", pais)
    if not city and not estado:
        return None  # no location data — can't determine required estado
    cidade = f"{city}, {country}" if city else country
    localizacao = cidade

    # Distances
    raw_distances: list[str] = meta.get("distance") or []
    distancias = _parse_distances(raw_distances)
    if not distancias:
        distancias = _parse_distances_from_title(titulo)

    # Links
    reg_link: str = meta.get("registration-link") or post.get("link") or _BASE
    event_link: str = post.get("link") or reg_link

    # ID: stable from WP post ID + year
    post_id = post.get("id") or slugify(titulo)
    race_id = f"halfmarathons_{post_id}_{data_evento[:4]}"

    horario = _normalize_time(meta.get("starting-time"))
    if horario is None:
        return None  # starting-time not yet published — skip until it is

    now = now_iso()
    return Corrida(
        id=race_id,
        titulo=titulo,
        data_evento=data_evento,
        horario=horario,
        localizacao=localizacao,
        cidade=cidade,
        estado=estado,
        pais=pais,
        distancias=distancias,
        imagem_url=None,
        inscricoes_abertas=None,
        periodo_inscricao=None,
        fontes=[FonteInfo(nome=SOURCE_NAME, link_evento=event_link, links_inscricao=[event_link], tipo="calendario")],
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


def _parse_distances_from_title(title: str) -> list[Distancia]:
    """Fallback: extract distances from post title when meta.distance is empty."""
    title_l = title.lower()
    seen: set[object] = set()
    result: list[Distancia] = []

    def _add(km: float | str) -> None:
        key = km if isinstance(km, str) else round(float(km))
        if key not in seen:
            seen.add(key)
            result.append(Distancia(km=km, data=None, horario=None))

    if re.search(r'half[\s-]marathon', title_l):
        _add(21.097)
    t = re.sub(r'half[\s-]marathon', '', title_l)
    if re.search(r'\bmarathon\b', t):
        _add(42.195)

    for n in re.findall(r'\b(\d+(?:\.\d+)?)k\b', title_l):
        km = float(n)
        if 3 <= km <= 200:
            _add(km)

    for n in re.findall(r'\b(\d+(?:\.\d+)?)-mile\b', title_l):
        _add(f"{n} mi")

    return sorted(result, key=lambda d: float(str(d.km).replace(" mi", "")) * 1.60934 if " mi" in str(d.km) else float(str(d.km)))


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text).strip()
