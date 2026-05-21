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
import re
from typing import Optional

from bs4 import BeautifulSoup

from ..http_client import get
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

        if page == 1:
            print(f"[{SOURCE_NAME}] PROBE raw len={len(resp.text)} first 1500 chars:")
            print(resp.text[:1500])
            print(f"[{SOURCE_NAME}] PROBE raw last 500 chars:")
            print(resp.text[-500:])

        html = _extract_html(resp.text)
        if html is None:
            print(f"[{SOURCE_NAME}] page {page}: payload inesperado; raw[:200]={resp.text[:200]}")
            break

        if page == 1:
            print(f"[{SOURCE_NAME}] PROBE extracted html len={len(html)}; first 1500 chars:")
            print(html[:1500])

        soup = BeautifulSoup(html, "lxml")
        items = soup.select(".tm_event_list_item")

        if page == 0:
            print(f"[{SOURCE_NAME}] PROBE page 0: {len(items)} items")
            if items:
                print(f"[{SOURCE_NAME}] PROBE first item raw HTML:")
                print(str(items[0])[:2000])
                # Try to parse it and dump intermediate values
                el = items[0]
                txt = el.get_text(" ", strip=True)
                print(f"[{SOURCE_NAME}] PROBE first item text: {txt[:300]}")
                t_el = el.find(class_=re.compile(r"event_title|tiempometa_event_link", re.IGNORECASE))
                print(f"[{SOURCE_NAME}] PROBE title_el match: {t_el}")
                if not t_el:
                    t_el = el.find("a")
                    print(f"[{SOURCE_NAME}] PROBE fallback first <a>: {t_el}")
                print(f"[{SOURCE_NAME}] PROBE extracted date: {_extract_date(el, txt)}")
                print(f"[{SOURCE_NAME}] PROBE extracted loc: {_extract_location(el, txt)}")
                print(f"[{SOURCE_NAME}] PROBE today: {today}")

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
    print(f"[{SOURCE_NAME}] {len(result)} corridas encontradas")
    return result


def _extract_html(payload: str) -> Optional[str]:
    """Strip the jQuery wrapper to get the raw HTML payload.

    The response looks like:
        $("#tiempometa_event_list_div").html('<div…>…</div>');
    We need the unescaped content inside the .html('...') call.
    """
    # Match $(...).html('...'); — content is single-quoted with \' escapes
    m = re.search(r"\.html\(\s*'(.*?)'\s*\)\s*;?\s*$", payload, re.DOTALL)
    if not m:
        # Try double quotes
        m = re.search(r'\.html\(\s*"(.*?)"\s*\)\s*;?\s*$', payload, re.DOTALL)
    if not m:
        return None
    raw = m.group(1)
    # JS escape sequences: \' \" \\ \n \t — undo them
    raw = raw.replace("\\'", "'").replace('\\"', '"').replace("\\n", "\n").replace("\\t", "\t").replace("\\\\", "\\")
    return raw


def _parse_event(el, today: str, now: str) -> Optional[Corrida]:
    """Parse a .tm_event_list_item div into a Corrida."""
    text = el.get_text(" ", strip=True)
    if not text:
        return None

    # Title — usually inside a link to the event detail
    title_el = el.find(class_=re.compile(r"event_title|tiempometa_event_link", re.IGNORECASE))
    if not title_el:
        title_el = el.find("a")
    titulo_raw = title_el.get_text(strip=True) if title_el else ""
    titulo = normalize_titulo(titulo_raw)
    if not titulo or len(titulo) < 3:
        return None

    # Date — usually in a dedicated span/div with day/month
    data_evento = _extract_date(el, text)
    if not data_evento or data_evento < today:
        return None

    # Location — city + state
    cidade, estado = _extract_location(el, text)
    if estado:
        estado = _NORMALIZE_UF.get(estado, estado)
    if not estado:
        _pais_geo, est_geo = _geo.resolve(cidade, "", "MX")
        estado = est_geo or ""
    localizacao = f"{cidade}, {estado}" if cidade and estado else cidade or estado or "México"

    # Event link — href on the title link or any "event=<id>" reference
    link = ""
    event_id_param = ""
    for a in el.find_all("a", href=True):
        href = a["href"]
        m = re.search(r"event=([a-f0-9]+)", href)
        if m:
            event_id_param = m.group(1)
        if "event=" in href and not link:
            link = href if href.startswith("http") else f"{BASE}/{href.lstrip('/')}"
            break
    if not link:
        link = BASE

    # Image
    imagem_url = None
    img = el.find("img")
    if img:
        imagem_url = img.get("src") or img.get("data-src")
        if imagem_url and imagem_url.startswith("//"):
            imagem_url = "https:" + imagem_url

    distancias = _extract_distances(text)

    event_id = event_id_param or slugify(titulo)
    fonte = FonteInfo(
        nome=SOURCE_NAME,
        link_evento=link,
        links_inscricao=[link] if link != BASE else [],
    )
    return Corrida(
        id=f"cm_{event_id}",
        titulo=titulo,
        data_evento=data_evento,
        horario=None,
        localizacao=localizacao,
        cidade=cidade,
        estado=estado or "",
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


def _extract_location(el, text: str) -> tuple[str, str]:
    """Return (cidade, estado_code). estado_code is a Tiempometa UF (DIF, MEX, NLE, …)."""
    # Try classes that signal location
    loc_el = el.find(class_=re.compile(r"event_(city|state|location|place)|ciudad|lugar", re.IGNORECASE))
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
