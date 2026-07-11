"""Scraper for Asdeporte.com — Mexican multi-sport event platform.

Next.js site. Events are loaded client-side, but the SSR __NEXT_DATA__ script
contains pageProps.recomended — a list of upcoming featured public events.
We paginate through the /eventos listing pages, collecting unique events by id.
"""
from __future__ import annotations
import json
import re
from datetime import datetime

from bs4 import BeautifulSoup

from ..http_client import get
from ..models import Corrida, Distancia, FonteInfo
from ..utils import normalize_titulo, slugify, now_iso, today_iso, extract_distances_from_text
from .. import geo as _geo

SOURCE_NAME = "Asdeporte"
_BASE       = "https://www.asdeporte.com"
_LIST_URL   = f"{_BASE}/eventos"

_MX_STATES: dict[str, str] = {
    "aguascalientes": "AGU", "baja california": "BCN", "baja california sur": "BCS",
    "campeche": "CAM", "chiapas": "CHP", "chihuahua": "CHH",
    "coahuila": "COA", "coahuila de zaragoza": "COA",
    "colima": "COL", "cdmx": "CMX", "ciudad de mexico": "CMX",
    "ciudad de méxico": "CMX", "df": "CMX", "distrito federal": "CMX",
    "durango": "DUR", "guanajuato": "GUA", "guerrero": "GRO", "hidalgo": "HID",
    "jalisco": "JAL", "estado de mexico": "MEX", "estado de méxico": "MEX",
    "michoacan": "MIC", "michoacán": "MIC", "morelos": "MOR",
    "nayarit": "NAY", "nuevo leon": "NLE", "nuevo león": "NLE", "oaxaca": "OAX",
    "puebla": "PUE", "queretaro": "QUE", "querétaro": "QUE",
    "quintana roo": "ROO", "san luis potosi": "SLP", "san luis potosí": "SLP",
    "sinaloa": "SIN", "sonora": "SON", "tabasco": "TAB", "tamaulipas": "TAM",
    "tlaxcala": "TLA", "veracruz": "VER", "yucatan": "YUC", "yucatán": "YUC",
    "zacatecas": "ZAC",
}

_MX_CITY_STATE: dict[str, str] = {
    "guadalajara": "JAL", "zapopan": "JAL", "tonala": "JAL", "tlaquepaque": "JAL",
    "monterrey": "NLE", "san nicolas de los garza": "NLE", "montemorelos": "NLE",
    "san pedro garza garcia": "NLE", "apodaca": "NLE", "linares": "NLE",
    "cdmx": "CMX", "ciudad de mexico": "CMX", "ciudad de méxico": "CMX",
    "puebla": "PUE", "cholula": "PUE",
    "queretaro": "QUE", "querétaro": "QUE",
    "cancun": "ROO", "cancún": "ROO", "playa del carmen": "ROO", "cozumel": "ROO",
    "merida": "YUC", "mérida": "YUC",
    "tijuana": "BCN", "ensenada": "BCN", "mexicali": "BCN",
    "san luis potosi": "SLP", "san luis potosí": "SLP",
    "aguascalientes": "AGU",
    "oaxaca": "OAX",
    "toluca": "MEX", "ecatepec": "MEX", "naucalpan": "MEX", "metepec": "MEX",
    "huehuetoca": "MEX", "texcoco": "MEX", "tlalnepantla": "MEX",
    "bosque de aragon": "CMX", "bosque de aragón": "CMX",
    "azcapotzalco": "CMX", "iztapalapa": "CMX", "xochimilco": "CMX",
    "morelia": "MIC", "uruapan": "MIC",
    "veracruz": "VER", "xalapa": "VER",
    "chihuahua": "CHH", "ciudad juarez": "CHH", "ciudad juárez": "CHH",
    "culiacan": "SIN", "culiacán": "SIN", "mazatlan": "SIN", "mazatlán": "SIN",
    "hermosillo": "SON",
    "acapulco": "GRO",
    "tuxtla gutierrez": "CHP", "tuxtla gutiérrez": "CHP",
    "tepic": "NAY",
    "colima": "COL",
    "campeche": "CAM",
    "zacatecas": "ZAC",
    "durango": "DUR",
    "villahermosa": "TAB",
    "chetumal": "ROO", "la paz": "BCS",
    "guanajuato": "GUA", "leon": "GUA", "léon": "GUA", "irapuato": "GUA",
    "tlaxcala": "TLA",
    "cuernavaca": "MOR",
    "ciudad victoria": "TAM", "tampico": "TAM", "matamoros": "TAM", "reynosa": "TAM",
    "saltillo": "COA", "torreon": "COA", "torreón": "COA",
    "pachuca": "HID", "pachuca de soto": "HID", "tulancingo": "HID",
}

# Skip these event types
_NON_RUNNING = re.compile(
    r"\btriath?lon\b|\bduath?lon\b|\baqua\b|\bciclismo\b|\bciclovia\b"
    r"|\bnado\b|\bnataci[oó]n\b|\bpaddl\b|\bkayak\b|\bspartan\b"
    r"|\bobst[aá]culo\b|\btower.?run\b|\biroman\b|\bironman\b",
    re.IGNORECASE,
)

_RUNNING_KW = re.compile(
    r"\b(?:carre?ra|maraton|marath|run|running|5k|10k|21k|42k"
    r"|medio.?marat[oó]n|half.?marathon|trail|ultra)\b",
    re.IGNORECASE,
)

_VENUE_KW = re.compile(
    r"\b(calle|paseo|avenida|av\.|blvd|boulevard|parque|plaza|estadio"
    r"|interior|km\s*\d|carretera|periférico|periferico|circuito|jardines"
    r"|prolongacion|prolongación|glorieta|andador|privada)\b",
    re.IGNORECASE,
)

_DIST_RE = re.compile(
    r"\b(\d+(?:\.\d+)?)\s*(?:k|km|kms?)\b"
    r"|\b(\d+(?:\.\d+)?)\s*mi(?:les?)?\b"
    r"|\b(marat[oó]n|marath)\b"
    r"|\b(medio.?marat[oó]n|half.?marathon)\b",
    re.IGNORECASE,
)


def scrape() -> list[Corrida]:
    today = today_iso()
    corridas: list[Corrida] = []
    seen_ids: set[str] = set()

    page = 0
    while True:
        page += 1
        try:
            resp = get(
                _LIST_URL,
                params={"competencias": "publicas", "pagina": page},
                source=SOURCE_NAME,
                timeout=30,
            )
        except Exception as e:
            print(f"[{SOURCE_NAME}] page {page} erro: {e}")
            break

        if resp.status_code in (400, 404):
            break
        try:
            resp.raise_for_status()
        except Exception as e:
            print(f"[{SOURCE_NAME}] page {page} HTTP {resp.status_code}: {e}")
            break

        soup = BeautifulSoup(resp.text, "lxml")
        events = _extract_events(soup)
        if not events:
            break

        new_this_page = 0
        for ev in events:
            ev_id = ev.get("id") or ""
            if ev_id and ev_id in seen_ids:
                continue
            if ev_id:
                seen_ids.add(ev_id)
            c = _parse_event(ev, today)
            if c:
                corridas.append(c)
                new_this_page += 1

        # Stop when no new events appeared (recomended list is static per page)
        if page > 1 and new_this_page == 0:
            break

    print(f"[{SOURCE_NAME}] {len(corridas)} corrida(s) encontrada(s)")
    return corridas


def _extract_events(soup: BeautifulSoup) -> list[dict]:
    script = soup.find("script", {"id": "__NEXT_DATA__"})
    if not script or not script.string:
        return []
    try:
        data = json.loads(script.string)
    except Exception:
        return []
    pp = data.get("props", {}).get("pageProps", {})
    return pp.get("recomended") or []


def _parse_event(ev: dict, today: str) -> Corrida | None:
    titulo_raw = (ev.get("nameEvent") or "").strip()
    if not titulo_raw:
        return None
    titulo = normalize_titulo(titulo_raw)

    if _NON_RUNNING.search(titulo) and not _RUNNING_KW.search(titulo):
        return None
    if not _RUNNING_KW.search(titulo):
        return None

    date_raw = ev.get("date") or ""
    if not date_raw:
        return None
    try:
        data_evento = date_raw[:10]  # "YYYY-MM-DD"
        datetime.strptime(data_evento, "%Y-%m-%d")
    except ValueError:
        return None
    if data_evento < today:
        return None

    horario: str | None = None
    if len(date_raw) > 10:
        mt = re.search(r"[T ](\d{2}):(\d{2})", date_raw)
        if mt:
            h, mi = int(mt.group(1)), int(mt.group(2))
            if 4 <= h <= 23 and 0 <= mi <= 59:  # exclude midnight placeholders
                horario = f"{h:02d}:{mi:02d}"

    # Prefer explicit city/state fields if the API provides them
    api_city  = (ev.get("city") or ev.get("municipality") or "").strip()
    api_state = (ev.get("state") or ev.get("stateName") or "").strip()
    place     = (ev.get("place") or "").strip()
    ciudad, estado = _parse_location(place, api_city, api_state)
    if not estado:
        _, estado = _geo.resolve(place or api_city, "", "MX")
    if not estado:
        # estado must come from structured fields (API place/city/state) or the
        # geo resolver — never scanned out of the event title. Skip if unknown.
        print(f"[{SOURCE_NAME}] estado indeterminável, pulando: {titulo!r}")
        return None

    route = ev.get("routeConvocatoria") or ""
    event_link = _BASE + route if route.startswith("/") else (route or _LIST_URL)

    # Distances + horário come from the event's convocatoria page (structured
    # __NEXT_DATA__ / page fields) — never parsed out of the title.
    distancias: list[Distancia] = []
    if event_link != _LIST_URL:
        extra_dists, extra_horario = _fetch_event_details(event_link)
        distancias = extra_dists
        if not horario and extra_horario:
            horario = extra_horario
    if not distancias:
        print(f"[{SOURCE_NAME}] sem distâncias estruturadas, pulando: {titulo!r}")
        return None
    # Horário no longer mandatory (policy 2026-07-11): keep the event without it.
    # if not horario:
    #     print(f"[{SOURCE_NAME}] sem horário, pulando: {titulo!r}")
    #     return None

    imagem = ev.get("imgEventDesktop") or ev.get("imgEvent") or None

    ev_id = ev.get("id") or slugify(titulo + "_" + data_evento)
    race_id = f"asdeporte_{ev_id}"
    now = now_iso()

    return Corrida(
        id=race_id,
        titulo=titulo,
        data_evento=data_evento,
        horario=horario,
        localizacao=ciudad,  # already "City, México"
        cidade=ciudad,
        estado=estado,
        pais="MX",
        distancias=distancias,
        imagem_url=imagem,
        inscricoes_abertas=None,
        periodo_inscricao=None,
        fontes=[FonteInfo(nome=SOURCE_NAME, link_evento=event_link, links_inscricao=[event_link], tipo="inscricao")],
        miss_count=0,
        first_seen_at=now,
        updated_at=now,
    )


_CITY_SUBSTR_RE: dict[str, tuple[re.Pattern, str]] = {
    city: (re.compile(r"\b" + re.escape(city) + r"\b"), code)
    for city, code in sorted(_MX_CITY_STATE.items(), key=lambda x: -len(x[0]))
}


def _parse_location(text: str, api_city: str = "", api_state: str = "") -> tuple[str, str]:
    """Returns (ciudad, estado_code). All Asdeporte events are in Mexico."""

    def _norm(s: str) -> str:
        return re.sub(r"[^\w\s]", "", s).lower().strip()

    # If the API already gave us separate state/city fields, use them first
    if api_state:
        estado = _MX_STATES.get(_norm(api_state)) or _MX_CITY_STATE.get(_norm(api_state)) or ""
        ciudad = api_city or text or ""
        if not ciudad or ciudad.lower() in ("mexico", "méxico"):
            ciudad = "México"
        elif not ciudad.endswith("México"):
            ciudad = f"{ciudad}, México"
        return ciudad, estado

    if not text and not api_city:
        return "México", ""

    combined = text or api_city
    parts = [p.strip() for p in combined.split(",")]

    # Scan reversed parts for a known Mexican state name
    for part in reversed(parts):
        key = _norm(part)
        if key in _MX_STATES:
            estado = _MX_STATES[key]
            ciudad = parts[0]
            if _looks_like_venue(ciudad):
                return "México", estado
            return f"{ciudad}, México", estado

    # No state name found — try exact city lookup on each comma-part
    for part in parts:
        estado = _MX_CITY_STATE.get(_norm(part), "")
        if estado:
            ciudad = part if not _looks_like_venue(part) else "México"
            if ciudad != "México" and not ciudad.endswith("México"):
                ciudad = f"{ciudad}, México"
            return ciudad, estado

    # Substring search: find any known city name anywhere in the full text
    norm_full = _norm(combined)
    for city, (pattern, code) in _CITY_SUBSTR_RE.items():
        if pattern.search(norm_full):
            return f"{city.title()}, México", code

    # Fallback: unknown city
    ciudad = parts[0] if parts else combined
    if _looks_like_venue(ciudad) or not ciudad or ciudad.lower() in ("mexico", "méxico"):
        return "México", ""
    return f"{ciudad}, México", ""


def _looks_like_venue(text: str) -> bool:
    return bool(re.search(r"\d", text) or _VENUE_KW.search(text) or len(text) > 50)


_NEXT_DATA_RE = re.compile(
    r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>\s*(\{.*?\})\s*</script>',
    re.DOTALL,
)


_TIME_RE = re.compile(
    r"\b(\d{1,2})[hH:]([0-5]\d)\s*(?:min\s*)?[hH]?\b(?!\s*[kK])"
    r"|\b(\d{1,2})\s*[hH]\b(?!\s*\d)",
    re.IGNORECASE,
)


def _extract_horario(text: str) -> str | None:
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


def _fetch_event_details(url: str) -> tuple[list[Distancia], str | None]:
    """Fetch the event convocatoria page; return (distances, horario)."""
    try:
        resp = get(url, source=SOURCE_NAME, timeout=25)
        resp.raise_for_status()
        html = resp.text
    except Exception as e:
        print(f"[{SOURCE_NAME}] fetch externo falhou ({url[:70]}): {e}")
        return [], None

    horario: str | None = None

    # Try __NEXT_DATA__ first — richer structured data
    m = _NEXT_DATA_RE.search(html)
    if m:
        try:
            data = json.loads(m.group(1))
            page_props = data.get("props", {}).get("pageProps", {})
            event_obj = page_props.get("event") or page_props.get("data") or {}
            # Extract horario from event date field
            for date_key in ("date", "dateStart", "startDate", "fecha"):
                date_val = event_obj.get(date_key) or ""
                if date_val and len(date_val) > 10:
                    mt = re.search(r"[T ](\d{2}):(\d{2})", date_val)
                    if mt:
                        h, mi = int(mt.group(1)), int(mt.group(2))
                        if 4 <= h <= 23 and 0 <= mi <= 59:
                            horario = f"{h:02d}:{mi:02d}"
            # Try categories array for distances
            for cat in (event_obj.get("categories") or event_obj.get("modalidades") or []):
                if isinstance(cat, dict):
                    val = cat.get("distance") or cat.get("distancia") or cat.get("categoria") or ""
                    if val:
                        dists = _parse_distances(str(val))
                        if dists:
                            return dists, horario
            # Try top-level distance field
            top_dist = event_obj.get("distance") or event_obj.get("distancia") or ""
            if top_dist:
                dists = _parse_distances(str(top_dist))
                if dists:
                    return dists, horario
            # Scan the entire __NEXT_DATA__ blob with the distance regex
            dists = _parse_distances(m.group(1))
            if dists:
                return dists, horario
        except Exception:
            pass

    # Last resort: regex over page text
    plain_text = re.sub(r"<[^>]+>", " ", html)
    if not horario:
        horario = _extract_horario(plain_text)
    return _parse_distances(plain_text), horario


def _parse_distances(titulo: str) -> list[Distancia]:
    result: list[Distancia] = []
    seen: set = set()
    # Numeric km + named distances (maratón / medio maratón), shared-suffix and
    # Spanish-"y"-connector aware. named_in_prose=True preserves the prior
    # behaviour of recognising a standalone "Maratón"/"Medio Maratón".
    for km in extract_distances_from_text(titulo, min_km=1.0, named_in_prose=True):
        key = round(float(km))
        if key not in seen:
            seen.add(key)
            result.append(Distancia(km=km, data=None, horario=None))
    # Miles distances are preserved verbatim as "N mi" strings (formatKm passes
    # them through); the km helper only handles kilometres.
    for m in re.finditer(r"\b(\d+(?:\.\d+)?)\s*mi(?:les?)?\b", titulo, re.IGNORECASE):
        mi = f"{m.group(1)} mi"
        if mi not in seen:
            seen.add(mi)
            result.append(Distancia(km=mi, data=None, horario=None))
    return result

