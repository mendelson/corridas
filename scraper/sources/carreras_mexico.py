"""Scraper for carrerasmexico.com â uses the Tiempometa public widget API.

The carrerasmexico.com homepage embeds a Tiempometa widget. We bypass the
widget and call its API directly. The API returns JavaScript that wraps
HTML content in a jQuery `.html(...)` call:

    $("#tiempometa_event_list_div").html('<div id="tm_js_container">â¦</div>');

We strip the wrapper and parse the inner HTML.

Endpoint that works (HTTP 200):
  GET https://www.tiempometa.com/api3/js_site/events
    ?api_key=48513987f33edea8           # public; baked into the widget div
    &page=<N>
    &page_size=<N>
    &target_url=https://carrerasmexico.com/

`/api3/js_site/event_search` returns 500 â broken upstream; don't use it.
"""
from __future__ import annotations
import html as _html_mod
import re
from typing import Optional

from bs4 import BeautifulSoup

from concurrent.futures import ThreadPoolExecutor, as_completed

from ..http_client import get
from ..models import Corrida, Distancia, FonteInfo
from ..utils import normalize_titulo, slugify, now_iso, today_iso, extract_distances_from_text
from .. import geo as _geo

SOURCE_NAME = "Carreras MÃ©xico"
BASE = "https://carrerasmexico.com"
API = "https://www.tiempometa.com/api3/js_site/events"
# Event-detail widget. The 2025 convocatoria.php redesign dropped the
# SportsEvent JSON-LD; date/time, location and distances are now injected
# client-side from this JSONP endpoint (jQuery `.html(...)` payload). The
# `<div class="tiempometa_calling">` block in the response carries the
# organizer's full convocatoria prose, already rendered.
CALLING_API = "https://www.tiempometa.com/api3/js_site/calling"
API_KEY = "48513987f33edea8"
PAGE_SIZE = 50

_CANON_KM = {21: 21.097, 42: 42.195}

# Tiempometa uses its own state abbreviations that diverge from the ISO-3166-2
# MX codes used in web/locations/MX.json. Map the known divergences; anything not
# listed is validated against MX.json (and geo-resolved) downstream, so an unknown
# code never reaches the data as an invalid subdivision.
_NORMALIZE_UF = {
    "DIF": "CMX", "CDMX": "CMX",           # Ciudad de MÃ©xico (ISO CMX)
    "TLX": "TLA", "TLAX": "TLA",           # Tlaxcala (ISO TLA)
    "AGS": "AGU",                          # Aguascalientes (ISO AGU)
    "DGO": "DUR",                          # Durango (ISO DUR)
    "GTO": "GUA",                          # Guanajuato (ISO GUA)
    "HGO": "HID",                          # Hidalgo (ISO HID)
    "QRO": "QUE",                          # QuerÃ©taro (ISO QUE)
    "QROO": "ROO",                         # Quintana Roo (ISO ROO)
    "NL": "NLE", "NVL": "NLE",             # Nuevo LeÃ³n (ISO NLE)
    "BC": "BCN",                           # Baja California (ISO BCN)
    "MICH": "MIC", "CHIS": "CHP", "CHIH": "CHH",
    "COAH": "COA", "TAMPS": "TAM", "EDOMEX": "MEX",
}


def scrape() -> list[Corrida]:
    today = today_iso()
    now = now_iso()
    corridas: dict[str, Corrida] = {}

    page = -1
    while True:  # no cap — paginate until the last page (breaks below)
        page += 1  # Tiempometa: 0-indexed
        params = {
            "api_key": API_KEY,
            "page": page,
            "page_size": PAGE_SIZE,
            "target_url": f"{BASE}/",
        }
        try:
            resp = get(API, params=params, source=SOURCE_NAME, timeout=30)
            resp.raise_for_status()
        except Exception as e:
            print(f"[{SOURCE_NAME}] page {page}: erro {e}")
            break

        html = _extract_html(resp.text)
        if html is None:
            print(f"[{SOURCE_NAME}] page {page}: payload inesperado; raw[:200]={resp.text[:200]}")
            break

        soup = BeautifulSoup(html, "lxml")
        items = soup.select(".tm_event_list_item")

        if not items:
            break

        page_added = 0
        for el in items:
            try:
                c = _parse_event(el, today, now)
                if c and c.id not in corridas:
                    corridas[c.id] = c
                    page_added += 1
            except Exception as e:
                print(f"[{SOURCE_NAME}] erro parse: {e}")

        print(f"[{SOURCE_NAME}] page {page}: {len(items)} items, {page_added} added")
        if len(items) < PAGE_SIZE:
            break

    result = list(corridas.values())
    _enrich_locations(result)
    before = len(result)
    # Emit only events with every hard-required field. HorÃ¡rio and a valid MX
    # subdivision come from the convocatoria page (behind a JS anti-bot challenge,
    # fetched via Playwright); events where they couldn't be recovered are dropped
    # rather than stored invalid.
    # Horário no longer mandatory (policy 2026-07-11): it was removed from the
    # hard-required filter below (original kept for reference); cidade, distâncias
    # and a valid MX subdivision are still required.
    # result = [
    #     c for c in result
    #     if c.horario and c.cidade and c.distancias and _geo.validate_estado("MX", c.estado)
    # ]
    result = [
        c for c in result
        if c.cidade and c.distancias and _geo.validate_estado("MX", c.estado)
    ]
    dropped = before - len(result)
    if dropped:
        print(f"[{SOURCE_NAME}] descartados {dropped} eventos sem cidade/UF/distância válida")
    print(f"[{SOURCE_NAME}] {len(result)} corridas encontradas")
    return result


def _enrich_locations(corridas: list[Corrida]) -> None:
    """Fetch convocatoria.php in parallel to populate cidade/estado AND horÃ¡rio
    from the per-event JSON-LD SportsEvent schema.

    This runs in test_source CI too: horÃ¡rio is a hard-required field and is
    only available on the convocatoria page (the Tiempometa widget list carries
    no start time). The fetch is cheap â carrerasmexico never lists more than a
    few dozen events, each response is streamed with a 30 KB cap, 3 in parallel."""
    needs_fetch = [c for c in corridas if not c.cidade or not c.horario or not c.distancias]
    if not needs_fetch:
        return
    print(f"[{SOURCE_NAME}] buscando convocatoria para {len(needs_fetch)} eventos...")

    def fetch(c: Corrida) -> tuple[Corrida, str, str, str | None, list[Distancia]]:
        ev_id = c.id.replace("cm_", "")
        cidade, estado, horario, distancias = _fetch_location_from_convocatoria(ev_id)
        return c, cidade, estado, horario, distancias

    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(fetch, c): c for c in needs_fetch}
        for future in as_completed(futures):
            try:
                c, cidade, estado, horario, distancias = future.result()
            except Exception as e:
                print(f"[{SOURCE_NAME}] enrich erro: {e}")
                continue
            if cidade:
                c.cidade = cidade
                c.estado = estado
                c.localizacao = f"{cidade}, {estado or 'MÃ©xico'}"
                print(f"[{SOURCE_NAME}] localizaÃ§Ã£o: {c.titulo[:30]} â {c.localizacao}")
            if horario and not c.horario:
                c.horario = horario
            if distancias and not c.distancias:
                c.distancias = distancias


def _extract_html(payload: str) -> Optional[str]:
    """Strip the jQuery wrapper to get the inner HTML payload.

    Tiempometa returns:
        $("#tiempometa_event_list_div").html('<divâ¦>â¦</div>');

    The payload has two layers of escaping:
      1. JS string escapes (\\', \\", \\/) â Tiempometa uses \\/ for closing tags
      2. Some tags are entity-encoded (&lt;\\/a&gt; instead of </a>)
    Both must be undone for BeautifulSoup to parse correctly.
    """
    m = re.search(r"\.html\(\s*'(.*?)'\s*\)\s*;?\s*$", payload, re.DOTALL)
    if not m:
        m = re.search(r'\.html\(\s*"(.*?)"\s*\)\s*;?\s*$', payload, re.DOTALL)
    if not m:
        return None
    raw = m.group(1)
    # Undo JS string escapes (order matters: \\ first so we don't double-convert)
    raw = (raw
           .replace("\\\\", "\\")
           .replace("\\'", "'")
           .replace('\\"', '"')
           .replace("\\/", "/")
           .replace("\\n", "\n")
           .replace("\\t", "\t"))
    # Decode HTML entities â two passes handle double-encoded &amp;lt; â &lt; â <
    raw = re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), raw)
    raw = _html_mod.unescape(raw)
    raw = _html_mod.unescape(raw)
    return raw


def _parse_event(el, today: str, now: str) -> Optional[Corrida]:
    """Parse a .tm_event_list_item div into a Corrida."""
    # Title: <div class="tm_event_list_title">â¦</div>
    title_div = el.find(class_="tm_event_list_title")
    titulo_raw = title_div.get_text(" ", strip=True) if title_div else ""
    titulo = normalize_titulo(titulo_raw)
    if not titulo or len(titulo) < 3:
        return None

    # Date: 3 separate divs (weekday/month/day) from the Tiempometa widget
    data_evento = _extract_date_from_widget(el, today)
    if not data_evento or data_evento < today:
        return None

    imagem_url = None
    img = el.find("img")
    if img:
        imagem_url = img.get("src") or img.get("data-src")
        if imagem_url and imagem_url.startswith("//"):
            imagem_url = "https:" + imagem_url

    # The individual event page is convocatoria.php?event=<hex>&api_key=<key>.
    # The widget anchors point to the root /?event=<hex> (which shows the full list),
    # so we extract the hex event_id and build the convocatoria.php URL ourselves.
    event_id_param = ""
    external_link = ""
    for a in el.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith(("#", "javascript")):
            continue
        if href.startswith("/"):
            href = "https://www.tiempometa.com" + href
        elif not href.startswith("http"):
            continue
        ma = re.search(r"event=([a-f0-9]+)", href)
        if ma and not event_id_param:
            event_id_param = ma.group(1)
        if "carrerasmexico.com" not in href and "tiempometa.com" not in href and href != BASE:
            if not external_link:
                external_link = href

    if event_id_param:
        cm_link = f"{BASE}/convocatoria.php?event={event_id_param}&api_key={API_KEY}"
    else:
        cm_link = BASE
    link = external_link or cm_link

    # Location AND distances are populated later in _enrich_locations from the
    # convocatoria detail page (parallel fetch) â never parsed from the title.
    cidade, estado, localizacao = "", "", "MÃ©xico"
    distancias: list[Distancia] = []

    event_id = event_id_param or slugify(titulo)
    fonte = FonteInfo(
        nome=SOURCE_NAME,
        link_evento=link,
        links_inscricao=[link],
        tipo="calendario",
    )
    return Corrida(
        id=f"cm_{event_id}",
        titulo=titulo,
        data_evento=data_evento,
        horario=None,
        localizacao=localizacao,
        cidade=cidade,
        estado=estado,
        pais="MX",
        distancias=distancias,
        imagem_url=imagem_url,
        inscricoes_abertas=None,
        periodo_inscricao=None,
        fontes=[fonte],
        miss_count=0,
        first_seen_at=now,
        updated_at=now,
    )


# Tiempometa abbreviates Spanish month names. "May" appears as "Mai" on the widget.
_TM_MONTH_ABBR = {
    "ene": "01", "feb": "02", "mar": "03", "abr": "04",
    "may": "05", "mai": "05",  # both spellings
    "jun": "06", "jul": "07", "ago": "08",
    "sep": "09", "oct": "10", "nov": "11", "dic": "12",
}


def _extract_date_from_widget(el, today_iso_str: str) -> Optional[str]:
    """Combine the three Tiempometa date divs (weekday/month/day) + infer year."""
    month_el = el.find(class_="tm_date_month")
    day_el = el.find(class_="tm_date_day")
    if not month_el or not day_el:
        return None
    month_raw = month_el.get_text(" ", strip=True).lower()
    day_raw = day_el.get_text(" ", strip=True)
    mo = _TM_MONTH_ABBR.get(month_raw[:3])
    if not mo:
        return None
    m = re.search(r"(\d{1,2})", day_raw)
    if not m:
        return None
    day = m.group(1).zfill(2)
    # Year inference: current year if the date is still upcoming, else next year
    year, today_mo, today_day = today_iso_str.split("-")
    if (mo, day) >= (today_mo, today_day):
        return f"{year}-{mo}-{day}"
    return f"{int(year) + 1}-{mo}-{day}"


_MX_MONTHS = {
    "enero": "01", "febrero": "02", "marzo": "03", "abril": "04",
    "mayo": "05", "junio": "06", "julio": "07", "agosto": "08",
    "septiembre": "09", "setiembre": "09", "octubre": "10",
    "noviembre": "11", "diciembre": "12",
    "ene": "01", "feb": "02", "mar": "03", "abr": "04",
    "may": "05", "jun": "06", "jul": "07", "ago": "08",
    "sep": "09", "oct": "10", "nov": "11", "dic": "12",
}


def _extract_date(el, text: str) -> Optional[str]:
    # Try dedicated date elements first
    date_el = el.find(class_=re.compile(r"event_date|date|fecha", re.IGNORECASE))
    candidates: list[str] = []
    if date_el:
        candidates.append(date_el.get_text(" ", strip=True))
    candidates.append(text)

    for s in candidates:
        # "15 de marzo de 2026" / "15 marzo 2026"
        m = re.search(
            r"(\d{1,2})\s+(?:de\s+)?([a-zÃ¡Ã©Ã­Ã³Ãº]+)\s+(?:de\s+)?(\d{4})",
            s, re.IGNORECASE,
        )
        if m:
            mo = _MX_MONTHS.get(m.group(2).lower())
            if mo:
                return f"{m.group(3)}-{mo}-{m.group(1).zfill(2)}"
        # YYYY-MM-DD
        m = re.search(r"(\d{4})-(\d{2})-(\d{2})", s)
        if m:
            return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
        # DD/MM/YYYY
        m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", s)
        if m:
            return f"{m.group(3)}-{m.group(2).zfill(2)}-{m.group(1).zfill(2)}"
    return None


def _fetch_location_from_convocatoria(event_id: str) -> tuple[str, str, str | None]:
    """Fetch the event detail via the TiempoMeta `calling` widget and parse
    (cidade, estado, horario) from the rendered convocatoria prose.

    The convocatoria.php redesign (2025) dropped the SportsEvent JSON-LD and now
    injects the event data client-side from /api3/js_site/calling â a JSONP
    `$("#â¦").html('â¦')` payload. Inside it, `<div class="tiempometa_calling">`
    holds the organizer's full convocatoria text, already rendered: FECHA (with
    the start time), SALIDA/SEDE (the Mexican state), and the route distances.
    The static convocatoria.php HTML only has empty placeholders, which is why
    the old SportsEvent-based extraction returned nothing and every event was
    dropped.
    """
    url = f"{CALLING_API}?event_id={event_id}&api_key={API_KEY}&callback=cb"
    payload = ""
    try:
        resp = get(url, source=SOURCE_NAME, timeout=30)
        if resp.status_code < 400:
            payload = resp.text
        else:
            print(f"[{SOURCE_NAME}] calling {event_id[:8]}: HTTP {resp.status_code}")
    except Exception as e:
        print(f"[{SOURCE_NAME}] calling {event_id[:8]}: {e}")

    if not payload:
        return "", "", None, []

    inner = _extract_html(payload)
    if not inner:
        return "", "", None, []

    soup = BeautifulSoup(inner, "lxml")
    prose_el = soup.find(class_="tiempometa_calling")
    prose = (prose_el or soup).get_text(" ", strip=True)
    if not prose:
        return "", "", None, []

    horario = _horario_from_prose(prose)
    cidade, estado = _location_from_prose(prose)
    distancias = _extract_distances(prose)  # from the convocatoria text, not the title
    return cidade, estado, horario, distancias


def _build_horario(h_str: str, m_str: str, suffix: str | None) -> str | None:
    """Build a 24-hour "HH:MM" (04:00â23:59) from a parsed time + optional suffix.

    A 12-hour clock suffix is honoured: "7:00 p.m." â 19:00, "12:00 a.m." â 00:00,
    "12:30 p.m." stays 12:30. A "hrs"/"horas" (or no) suffix is treated as already
    24-hour. Times outside 04:00â23:59 after conversion are rejected as noise."""
    h, mi = int(h_str), int(m_str)
    suf = re.sub(r"[\s.]", "", (suffix or "").lower())
    if suf == "pm" and h < 12:
        h += 12
    elif suf == "am" and h == 12:
        h = 0
    if 4 <= h <= 23 and 0 <= mi <= 59:
        return f"{h:02d}:{mi:02d}"
    return None


def _horario_from_prose(text: str) -> str | None:
    """Extract a plausible start time (HH:MM, 04:00â23:59) from convocatoria prose.

    Convocatorias state it as e.g. "FECHA: 7 de junio de 2026, 9:30 hrs." or
    "Hora de salida: 7:00 p.m.". Prefer a keyword-anchored match, then fall back
    to any HH:MM carrying an explicit hrs/am/pm suffix (bare numbers like a
    distance "10:00" without a unit are ignored). 12-hour times are converted to
    24-hour via the am/pm suffix (see _build_horario)."""
    # 1. Keyword-anchored (fecha/hora/salida/inicio/arranque/largada â HH[:.]MM)
    mt = re.search(
        r"(?:fecha|hora(?:rio)?(?:\s*de\s*(?:salida|inicio|arranque|largada))?|"
        r"salida|inicio|arranque|largada)[^\d]{0,40}?"
        r"\b([0-9]{1,2})[:.hH]([0-5][0-9])\s*(hrs?|horas?|a\.?\s*m\.?|p\.?\s*m\.?)?",
        text, re.IGNORECASE,
    )
    if mt:
        t = _build_horario(mt.group(1), mt.group(2), mt.group(3))
        if t:
            return t
    # 2. Any time with an explicit hrs/am/pm suffix
    for m in re.finditer(
        r"\b([0-9]{1,2})[:.hH]([0-5][0-9])\s*(hrs?|horas?|a\.?\s*m\.?|p\.?\s*m\.?)",
        text, re.IGNORECASE,
    ):
        t = _build_horario(m.group(1), m.group(2), m.group(3))
        if t:
            return t
    return None


def _location_from_prose(text: str) -> tuple[str, str]:
    """Return (cidade, estado_code) by scanning prose for a Mexican state name.

    estado drives the frontend location label (validated against MX.json); when
    the prose also exposes a "<City>, <State>" pair we keep the city, otherwise
    cidade falls back to the state name so `localizacao` is never empty.
    State names are scanned longest-first so "baja california sur" matches
    before "baja california", etc. (`_STATE_NAME_TO_CODE` is defined below, so
    the sort is resolved here at call time rather than at import.)"""
    low = text.lower()
    for name in sorted(_STATE_NAME_TO_CODE.keys(), key=len, reverse=True):
        if len(name) < 5:  # skip the short ambiguous abbreviations in the map
            continue
        idx = low.find(name)
        if idx == -1:
            continue
        estado = _geo.validate_estado("MX", _STATE_NAME_TO_CODE[name])
        if not estado:
            continue
        # Prefer an explicit "<City>, <State>" pair appearing just before the name
        cidade = ""
        m = re.search(
            r"([A-ZÃÃÃÃÃÃ][\wÃÃÃÃÃÃÃ¡Ã©Ã­Ã³ÃºÃ±.\-]+(?:\s+[A-ZÃÃÃÃÃÃa-zÃ±Ã¡Ã©Ã­Ã³Ãº.\-]+){0,2})"
            r"\s*,\s*" + re.escape(text[idx:idx + len(name)]),
            text,
        )
        if m:
            cand = m.group(1).strip(" .,-")
            # Reject obvious non-city captures (sentence fragments)
            if 2 <= len(cand) <= 40 and cand.lower() != name:
                cidade = cand
        if not cidade:
            cidade = text[idx:idx + len(name)].title()
        return cidade, estado
    return "", ""


def _extract_location(el, text: str) -> tuple[str, str]:
    """Return (cidade, estado_code). estado_code is a Tiempometa UF (DIF, MEX, NLE, â¦)."""
    # Try classes that signal location (including Tiempometa tm_* prefix variants)
    loc_el = el.find(class_=re.compile(
        r"tm_(event_)?(city|state|location|place|ciudad|lugar)|event_(city|state|location|place)|ciudad|lugar",
        re.IGNORECASE,
    ))
    if loc_el:
        loc_text = loc_el.get_text(" ", strip=True)
        # Often "City, State" or "City - State"
        parts = re.split(r"[,\-â]\s*", loc_text)
        cidade = parts[0].strip() if parts else ""
        estado = parts[1].strip() if len(parts) > 1 else ""
        return cidade, _state_to_code(estado)
    return "", ""


_STATE_NAME_TO_CODE = {
    "aguascalientes": "AGU", "baja california": "BCN", "baja california sur": "BCS",
    "campeche": "CAM", "chiapas": "CHP", "chihuahua": "CHH",
    "coahuila": "COA", "colima": "COL",
    "cdmx": "CMX", "ciudad de mÃ©xico": "CMX", "ciudad de mexico": "CMX",
    "distrito federal": "CMX",
    "durango": "DUR", "guanajuato": "GUA", "guerrero": "GRO", "hidalgo": "HID",
    "jalisco": "JAL", "estado de mÃ©xico": "MEX", "estado de mexico": "MEX",
    "mÃ©xico": "MEX",
    "michoacÃ¡n": "MIC", "michoacan": "MIC", "morelos": "MOR",
    "nayarit": "NAY", "nuevo leÃ³n": "NLE", "nuevo leon": "NLE",
    "oaxaca": "OAX", "puebla": "PUE", "querÃ©taro": "QUE", "queretaro": "QUE",
    "quintana roo": "ROO", "san luis potosÃ­": "SLP", "san luis potosi": "SLP",
    "sinaloa": "SIN", "sonora": "SON", "tabasco": "TAB", "tamaulipas": "TAM",
    "tlaxcala": "TLA", "veracruz": "VER", "yucatÃ¡n": "YUC", "yucatan": "YUC",
    "zacatecas": "ZAC",
}


def _state_to_code(raw: str) -> str:
    raw = (raw or "").strip()
    if not raw:
        return ""
    # Already a 2-4-letter UF (Tiempometa codes can be up to 4 chars, e.g. QROO)?
    if re.match(r"^[A-Za-z]{2,4}$", raw):
        u = raw.upper()
        return _NORMALIZE_UF.get(u, u)
    return _STATE_NAME_TO_CODE.get(raw.lower(), "")


def _extract_distances(text: str) -> list[Distancia]:
    seen: set[float] = set()
    result: list[Distancia] = []
    # Shared-suffix + Spanish-"y"-connector aware ("5, 10 y 21 km" â [5,10,21.097]);
    # named distances are handled by the keyword fallback below (allow_named=False).
    for canon in extract_distances_from_text(text, min_km=3.0, allow_named=False):
        if canon not in seen:
            seen.add(canon)
            result.append(Distancia(km=canon, data=None, horario=None))
    if not result:
        # No numeric distance: fall back to a named distance found in the prose.
        # The helper correctly maps "medio maratÃ³n" â 21.097 and a standalone
        # "maratÃ³n" â 42.195 (the previous regex checked "media", missing the
        # Mexican "medio maratÃ³n" and mislabelling it as a full marathon).
        for canon in extract_distances_from_text(text, min_km=3.0, named_in_prose=True):
            if canon not in seen:
                seen.add(canon)
                result.append(Distancia(km=canon, data=None, horario=None))
    return sorted(result, key=lambda d: d.km if isinstance(d.km, (int, float)) else 999)
