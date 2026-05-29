"""Scraper for carrerasmexico.com — uses the Tiempometa public widget API.

The carrerasmexico.com homepage embeds a Tiempometa widget. We bypass the
widget and call its API directly. The API returns JavaScript that wraps
HTML content in a jQuery `.html(...)` call:

    $("#tiempometa_event_list_div").html('<div id="tm_js_container">…</div>');

We strip the wrapper and parse the inner HTML.

Endpoint that works (HTTP 200):
  GET https://www.tiempometa.com/api3/js_site/events
    ?api_key=48513987f33edea8           # public; baked into the widget div
    &page=<N>
    &page_size=<N>
    &target_url=https://carrerasmexico.com/

`/api3/js_site/event_search` returns 500 — broken upstream; don't use it.
"""
from __future__ import annotations
import html as _html_mod
import json
import re
from typing import Optional

from bs4 import BeautifulSoup

from concurrent.futures import ThreadPoolExecutor, as_completed
import httpx

from ..http_client import get, HEADERS
from ..models import Corrida, Distancia, FonteInfo
from ..utils import normalize_titulo, slugify, now_iso, today_iso
from .. import geo as _geo

SOURCE_NAME = "Carreras México"
BASE = "https://carrerasmexico.com"
API = "https://www.tiempometa.com/api3/js_site/events"
API_KEY = "48513987f33edea8"
PAGE_SIZE = 50
MAX_PAGES = 20  # 1000 events upper bound — far more than carrerasmexico ever has

_CANON_KM = {21: 21.097, 42: 42.195}

# carrerasmexico uses DIF for CDMX; standard UF is CMX
_NORMALIZE_UF = {"DIF": "CMX"}


def scrape() -> list[Corrida]:
    today = today_iso()
    now = now_iso()
    corridas: dict[str, Corrida] = {}

    for page in range(0, MAX_PAGES):  # Tiempometa pages are 0-indexed
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

        if page == 0:
            print(f"[{SOURCE_NAME}] PROBE page0 raw repr[:400]: {resp.text[:400]!r}")

        html = _extract_html(resp.text)
        if html is None:
            print(f"[{SOURCE_NAME}] page {page}: payload inesperado; raw[:200]={resp.text[:200]}")
            break

        if page == 0:
            print(f"[{SOURCE_NAME}] PROBE page0 html repr[:400]: {html[:400]!r}")

        soup = BeautifulSoup(html, "lxml")
        items = soup.select(".tm_event_list_item")

        if page == 0:
            print(f"[{SOURCE_NAME}] PROBE page 0: {len(items)} items; today={today}")
            for i, el in enumerate(items[:3]):
                title_div = el.find(class_="tm_event_list_title")
                titulo_raw = title_div.get_text(" ", strip=True) if title_div else "<NOT FOUND>"
                month_el = el.find(class_="tm_date_month")
                day_el = el.find(class_="tm_date_day")
                month_raw = month_el.get_text(" ", strip=True) if month_el else "<NOT FOUND>"
                day_raw = day_el.get_text(" ", strip=True) if day_el else "<NOT FOUND>"
                data_evento = _extract_date_from_widget(el, today)
                all_hrefs = [a["href"] for a in el.find_all("a", href=True)]
                all_classes = sorted({cls for tag in el.find_all(class_=True) for cls in tag.get("class", [])})
                img_el = el.find("img")
                img_src = (img_el.get("src") or img_el.get("data-src") or "") if img_el else ""
                print(f"[{SOURCE_NAME}] PROBE item[{i}]: titulo={titulo_raw[:60]!r} date={data_evento!r} img={img_src[:100]!r}")
                print(f"[{SOURCE_NAME}] PROBE item[{i}] classes: {all_classes}")
                for j, h in enumerate(all_hrefs):
                    print(f"[{SOURCE_NAME}] PROBE item[{i}] anchor[{j}]: {h[:140]!r}")

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
    print(f"[{SOURCE_NAME}] {len(result)} corridas encontradas")
    return result


def _enrich_locations(corridas: list[Corrida]) -> None:
    """Fetch convocatoria.php in parallel to populate cidade/estado from JSON-LD."""
    import os
    if os.environ.get("SCRAPER_TEST"):
        return  # skip in test_source CI — only needed in full pipeline
    needs_location = [c for c in corridas if not c.cidade]
    if not needs_location:
        return
    print(f"[{SOURCE_NAME}] buscando localização para {len(needs_location)} eventos...")

    def fetch(c: Corrida) -> tuple[Corrida, str, str, str | None]:
        ev_id = c.id.replace("cm_", "")
        cidade, estado, horario = _fetch_location_from_convocatoria(ev_id)
        return c, cidade, estado, horario

    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(fetch, c): c for c in needs_location}
        for future in as_completed(futures):
            try:
                c, cidade, estado, horario = future.result()
            except Exception as e:
                print(f"[{SOURCE_NAME}] enrich erro: {e}")
                continue
            if cidade:
                c.cidade = cidade
                c.estado = estado
                c.localizacao = f"{cidade}, {estado or 'México'}"
                print(f"[{SOURCE_NAME}] localização: {c.titulo[:30]} → {c.localizacao}")
            if horario and not c.horario:
                c.horario = horario


def _extract_html(payload: str) -> Optional[str]:
    """Strip the jQuery wrapper to get the inner HTML payload.

    Tiempometa returns:
        $("#tiempometa_event_list_div").html('<div…>…</div>');

    The payload has two layers of escaping:
      1. JS string escapes (\\', \\", \\/) — Tiempometa uses \\/ for closing tags
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
    # Decode HTML entities — two passes handle double-encoded &amp;lt; → &lt; → <
    raw = re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), raw)
    raw = _html_mod.unescape(raw)
    raw = _html_mod.unescape(raw)
    return raw


def _parse_event(el, today: str, now: str) -> Optional[Corrida]:
    """Parse a .tm_event_list_item div into a Corrida."""
    # Title: <div class="tm_event_list_title">…</div>
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

    # Location populated later in _enrich_locations (parallel convocatoria.php fetch)
    cidade, estado, localizacao = "", "", "México"

    distancias = _extract_distances(titulo)

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
            r"(\d{1,2})\s+(?:de\s+)?([a-záéíóú]+)\s+(?:de\s+)?(\d{4})",
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
    """Fetch convocatoria.php and extract (cidade, estado, horario) from JSON-LD SportsEvent schema."""
    url = f"{BASE}/convocatoria.php?event={event_id}&api_key={API_KEY}"
    # Stream and stop after 30KB — JSON-LD is in the first ~5KB of the <head>
    try:
        with httpx.stream("GET", url, headers=HEADERS, follow_redirects=True,
                          timeout=httpx.Timeout(connect=8, read=8, write=5, pool=5)) as r:
            if r.status_code >= 400:
                print(f"[{SOURCE_NAME}] convocatoria {event_id[:8]}: HTTP {r.status_code}")
                return "", ""
            content = b""
            for chunk in r.iter_bytes(chunk_size=4096):
                content += chunk
                if len(content) >= 30_000:
                    break
        html = content.decode("utf-8", errors="replace")
    except Exception as e:
        print(f"[{SOURCE_NAME}] convocatoria {event_id[:8]}: erro {e}")
        return "", ""
    soup = BeautifulSoup(html, "lxml")
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            schema = json.loads(script.string or "")
        except Exception:
            continue
        if isinstance(schema, list):
            schema = next((s for s in schema if isinstance(s, dict) and s.get("@type") == "SportsEvent"), None)
        if not isinstance(schema, dict) or schema.get("@type") != "SportsEvent":
            continue
        loc = schema.get("location", {})
        loc_name = loc.get("name", "") if isinstance(loc, dict) else ""
        if not loc_name:
            continue
        parts = re.split(r",\s*", loc_name, maxsplit=1)
        cidade = parts[0].strip()
        estado_raw = parts[1].strip() if len(parts) > 1 else ""
        estado = _state_to_code(estado_raw)
        if not estado and cidade:
            _, estado = _geo.resolve(cidade, "", "MX")
            estado = estado or ""
        # Extract time from startDate: "2026-09-26T09:30:00-06:00"
        horario: str | None = None
        start_dt = schema.get("startDate") or ""
        mt = re.search(r"[T ](\d{2}):(\d{2})", start_dt)
        if mt:
            h, mi = int(mt.group(1)), int(mt.group(2))
            if 0 <= h <= 23 and 0 <= mi <= 59:
                horario = f"{h:02d}:{mi:02d}"
        return cidade, estado, horario
    return "", "", None


def _extract_location(el, text: str) -> tuple[str, str]:
    """Return (cidade, estado_code). estado_code is a Tiempometa UF (DIF, MEX, NLE, …)."""
    # Try classes that signal location (including Tiempometa tm_* prefix variants)
    loc_el = el.find(class_=re.compile(
        r"tm_(event_)?(city|state|location|place|ciudad|lugar)|event_(city|state|location|place)|ciudad|lugar",
        re.IGNORECASE,
    ))
    if loc_el:
        loc_text = loc_el.get_text(" ", strip=True)
        # Often "City, State" or "City - State"
        parts = re.split(r"[,\-–]\s*", loc_text)
        cidade = parts[0].strip() if parts else ""
        estado = parts[1].strip() if len(parts) > 1 else ""
        return cidade, _state_to_code(estado)
    return "", ""


_STATE_NAME_TO_CODE = {
    "aguascalientes": "AGU", "baja california": "BCN", "baja california sur": "BCS",
    "campeche": "CAM", "chiapas": "CHP", "chihuahua": "CHH",
    "coahuila": "COA", "colima": "COL",
    "cdmx": "CMX", "ciudad de méxico": "CMX", "ciudad de mexico": "CMX",
    "distrito federal": "CMX",
    "durango": "DUR", "guanajuato": "GUA", "guerrero": "GRO", "hidalgo": "HID",
    "jalisco": "JAL", "estado de méxico": "MEX", "estado de mexico": "MEX",
    "méxico": "MEX",
    "michoacán": "MIC", "michoacan": "MIC", "morelos": "MOR",
    "nayarit": "NAY", "nuevo león": "NLE", "nuevo leon": "NLE",
    "oaxaca": "OAX", "puebla": "PUE", "querétaro": "QUE", "queretaro": "QUE",
    "quintana roo": "ROO", "san luis potosí": "SLP", "san luis potosi": "SLP",
    "sinaloa": "SIN", "sonora": "SON", "tabasco": "TAB", "tamaulipas": "TAM",
    "tlaxcala": "TLA", "veracruz": "VER", "yucatán": "YUC", "yucatan": "YUC",
    "zacatecas": "ZAC",
}


def _state_to_code(raw: str) -> str:
    raw = (raw or "").strip().lower()
    if not raw:
        return ""
    # Already a 2-3-letter UF?
    if re.match(r"^[A-Z]{2,3}$", raw, re.IGNORECASE):
        u = raw.upper()
        return _NORMALIZE_UF.get(u, u)
    return _STATE_NAME_TO_CODE.get(raw, "")


def _extract_distances(text: str) -> list[Distancia]:
    seen: set[float] = set()
    result: list[Distancia] = []
    for n in re.findall(r"\b(\d+(?:[.,]\d+)?)\s*[kK](?:m|M)?\b", text):
        km = float(n.replace(",", "."))
        key = round(km)
        canon = _CANON_KM.get(key, km)
        if canon not in seen and 3 <= canon <= 200:
            seen.add(canon)
            result.append(Distancia(km=canon, data=None, horario=None))
    return sorted(result, key=lambda d: d.km if isinstance(d.km, (int, float)) else 999)
