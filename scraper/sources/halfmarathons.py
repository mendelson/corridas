"""Scraper for HalfMarathons.net — US half-marathon, 10K, 5K calendar.

WordPress REST API at /wp-json/wp/v2/races.  Each post carries race
metadata in `meta` and state in `class_list` as `race-calendar-{slug}`.
Distances stored as miles strings to match RunSignup convention.
"""
from __future__ import annotations
import re
from datetime import date, datetime, timezone
from urllib.parse import urlparse

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


def _fetch_page(page: int) -> tuple[list[dict] | None, int]:
    """Fetch one API page, returning (posts, total_pages).

    The halfmarathons.net WordPress REST API is occasionally served behind a
    Cloudflare JS-challenge that returns an HTML interstitial instead of JSON.
    A plain GET then fails to parse ("Expecting value: line 1 column 1"). The
    API itself is healthy, so this is transient — retry the page a few times
    before giving up.

    Returns (None, 0) only when every attempt fails — the caller decides whether
    that ends pagination.
    """
    last_total = page
    for attempt in range(3):
        try:
            resp = get(
                _API,
                params={"per_page": _PER_PAGE, "page": page},
                source=SOURCE_NAME,
                timeout=25,
            )
        except Exception as e:
            print(f"[{SOURCE_NAME}] page {page} erro (tentativa {attempt + 1}): {e}")
            continue

        if resp.status_code in (400, 404):
            return [], last_total  # genuine past-end-of-results

        if resp.status_code != 200:
            print(f"[{SOURCE_NAME}] page {page} HTTP {resp.status_code} (tentativa {attempt + 1})")
            continue

        try:
            posts: list[dict] = resp.json()
        except Exception as e:
            snippet = (resp.text or "")[:80].replace("\n", " ")
            print(f"[{SOURCE_NAME}] page {page} JSON erro (tentativa {attempt + 1}): {e} | {snippet!r}")
            continue

        last_total = int(resp.headers.get("X-WP-TotalPages", page) or page)
        return posts, last_total

    return None, last_total


def scrape() -> list[Corrida]:
    today = today_iso()
    corridas: list[Corrida] = []

    page = 0
    while True:
        page += 1
        posts, total_pages = _fetch_page(page)

        if posts is None:
            print(f"[{SOURCE_NAME}] page {page} falhou após todas as tentativas — parando")
            break
        if not posts:
            break

        for post in posts:
            c = _parse_post(post, today)
            if c:
                corridas.append(c)

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
    # cidade holds the bare city name (used for dedup/geo); the human-readable
    # "City, Country" string lives in localizacao. Previously cidade carried the
    # country too (e.g. "Savannah, EUA"), polluting the city field.
    cidade = city
    localizacao = f"{city}, {country}" if city else country

    # Links
    reg_link: str = meta.get("registration-link") or post.get("link") or _BASE
    event_link: str = post.get("link") or reg_link

    # Distances. Priority: structured meta.distance → external registration/
    # results page (UltraSignup/RunSignup) for the handful of trail/ultra events
    # whose distance the API leaves blank. The event title is NEVER parsed for
    # distances — only explicit structured fields count.
    raw_distances: list[str] = meta.get("distance") or []
    distancias = _parse_distances(raw_distances)
    if not distancias:
        distancias = _fetch_distances_external(reg_link)
    if not distancias:
        # No determinable fixed distance in any structured source — skip rather
        # than guess from the title.
        print(f"[{SOURCE_NAME}] sem distância determinável, pulando: {titulo!r}")
        return None

    # ID: stable from WP post ID + year
    post_id = post.get("id") or slugify(titulo)
    race_id = f"halfmarathons_{post_id}_{data_evento[:4]}"

    horario = _normalize_time(meta.get("starting-time"))
    # Horário no longer mandatory (policy 2026-07-11): keep the event without it.
    # if horario is None:
    #     return None  # starting-time not yet published — skip until it is

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


# Spelled-out small numbers that appear in race names ("Five Mile", "Ten Mile").
_SPELLED_NUM = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "twelve": 12, "fifteen": 15,
}


def _format_mi(raw: str) -> str:
    f = float(raw)
    return f"{int(f)} mi" if f.is_integer() else f"{f} mi"


def _extract_distance_tokens(text: str) -> list[Distancia]:
    """Extract race distances from free text (event title or an external
    registration/results page). Recognises half-marathon/marathon, numeric and
    spelled-out mile distances, and km tokens. Returns canonicalised Distancias."""
    tl = (text or "").lower()
    seen: set[object] = set()
    result: list[Distancia] = []

    def _add(km: float | str) -> None:
        key = km if isinstance(km, str) else round(float(km))
        if key not in seen:
            seen.add(key)
            result.append(Distancia(km=km, data=None, horario=None))

    # Half marathon — "half marathon", bare "half" (on this site it always means
    # half marathon: "Killeen Half Marafun", "Hard As Hell Half"), or "1/2 Marathon"
    # (UltraSignup's label). Strip these before the full-marathon check so the
    # "marathon" inside "1/2 Marathon" doesn't also register as a full marathon.
    _half_re = r'half[\s-]?marathon|\bhalf\b|1\s*/\s*2\s*marathon'
    if re.search(_half_re, tl):
        _add(21.097)
    t = re.sub(_half_re, '', tl)
    if re.search(r'\bmarathon\b', t):
        _add(42.195)

    # Numeric miles: "50 Miler", "14 mile", "5-mile"
    for n in re.findall(r'\b(\d+(?:\.\d+)?)\s*-?\s*mile[rs]?\b', tl):
        f = float(n)
        if 1 <= f <= 200:
            _add(_format_mi(n))
    # Spelled-out miles: "Five Mile"
    for word, val in _SPELLED_NUM.items():
        if re.search(rf'\b{word}\s*-?\s*mile[rs]?\b', tl):
            _add(_format_mi(str(val)))

    # Kilometres: "10k", "50 km"
    for n in re.findall(r'\b(\d+(?:\.\d+)?)\s*k(?:m)?\b', tl):
        km = float(n)
        if 3 <= km <= 200:
            _add(km)

    # Time-based events ("24 Hour Run", "6-hour", "12 hr") have no fixed distance;
    # represent them with a verbatim time label (km is polymorphic — the frontend
    # passes non-numeric strings through unchanged, like the "N mi" convention).
    for n in re.findall(r'\b(\d+)\s*-?\s*(?:hours?|hrs?)\b', tl):
        _add(f"{n}h")

    return sorted(result, key=_dist_sort_key)


def _dist_sort_key(d: Distancia) -> float:
    """Sort numeric km ascending, miles by their km equivalent, and non-numeric
    labels (timed events like '24h') last."""
    s = str(d.km)
    if s.endswith(" mi"):
        try:
            return float(s[:-3]) * 1.60934
        except ValueError:
            return 9e9
    try:
        return float(s)
    except ValueError:
        return 9e9


_RSU_RACEID_RE = re.compile(r'race_?id["\']?\s*[:=]\s*["\']?(\d{4,})', re.IGNORECASE)


def _fetch_distances_external(url: str) -> list[Distancia]:
    """Last resort for the handful of trail/ultra events whose distance is absent
    from the halfmarathons.net API and the event title: read it from the external
    registration page, using a parser tuned to each platform's clean structured
    source (never a raw full-body scan, which fabricates distances)."""
    if not url or not url.startswith("http") or "halfmarathons.net" in url:
        return []
    host = urlparse(url).netloc.lower()
    try:
        resp = get(url, source=SOURCE_NAME, timeout=20)
        resp.raise_for_status()
        html = resp.text
    except Exception as e:
        print(f"[{SOURCE_NAME}] fetch externo falhou ({url[:60]}): {e}")
        return []

    if "ultrasignup.com" in host:
        return _distances_ultrasignup(html)
    if "runsignup.com" in host:
        return _distances_runsignup(html)
    # Generic platforms (oregontrailruns, …): the meta/og description lists the
    # distances cleanly ("… Half Marathon, 10K, or 5K options.") without the
    # navigation noise that pollutes the page body.
    return _distances_from_meta(html)


def _distances_ultrasignup(html: str) -> list[Distancia]:
    """UltraSignup exposes the distances differently per page type:
      • results_event.aspx — anchors with class event_link / event_selected_link
        ('50 Miler', '50K', '1/2 Marathon');
      • register.aspx — registration fee rows tagged summary-fee-calculation-label
        ('50 Mile Registration …')."""
    labels = re.findall(
        r"class=['\"]event(?:_selected)?_link['\"][^>]*>([^<]+)<", html, re.IGNORECASE
    )
    labels += re.findall(
        r"class=['\"]summary-fee-calculation-label['\"][^>]*>([^<]+)<", html, re.IGNORECASE
    )
    return _extract_distance_tokens(" , ".join(labels))


def _distances_runsignup(html: str) -> list[Distancia]:
    """RunSignup loads distances via JS, but the page embeds a numeric raceId.
    Hit the public REST race endpoint for the structured race_events list."""
    m = _RSU_RACEID_RE.search(html)
    if not m:
        return []
    race_id = m.group(1)
    try:
        resp = get(
            f"https://runsignup.com/rest/race/{race_id}?format=json&events=T",
            source=SOURCE_NAME, timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"[{SOURCE_NAME}] runsignup REST {race_id}: {e}")
        return []
    race = data.get("race") if isinstance(data, dict) else None
    if not isinstance(race, dict):
        return []
    events = race.get("race_events") or race.get("events") or []
    # The structured `distance` field is authoritative ("14 Miles"); the event
    # `name` ("2027 Sheetz-to-Sheetz Trail Run") usually carries no distance.
    parts = " , ".join(
        f"{ev.get('distance', '')} {ev.get('name', '')}"
        for ev in events if isinstance(ev, dict)
    )
    return _extract_distance_tokens(parts)


def _distances_from_meta(html: str) -> list[Distancia]:
    """Read the distances from the page's meta description / og:description."""
    for pat in (
        r'<meta[^>]+(?:name|property)=["\'](?:og:)?description["\'][^>]+content=["\']([^"\']+)',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:name|property)=["\'](?:og:)?description["\']',
    ):
        m = re.search(pat, html, re.IGNORECASE)
        if m:
            dists = _extract_distance_tokens(_strip_html(m.group(1)))
            if dists:
                return dists
    return []


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text).strip()
