"""Scraper for FMAA — Federación Mexicana de Asociaciones de Atletismo.

WordPress site with The Events Calendar plugin.
API: /wp-json/tribe/events/v1/events
Fallback: /wp-json/wp/v2/posts (posts tagged as events)
"""
from __future__ import annotations
import re
from datetime import datetime

from bs4 import BeautifulSoup

from ..http_client import get
from ..models import Corrida, Distancia, FonteInfo
from ..utils import normalize_titulo, slugify, now_iso, today_iso
from .. import geo as _geo

SOURCE_NAME = "FMAA"
_BASE       = "https://fmaa.apps-mexico.com"
_API        = f"{_BASE}/wp-json/tribe/events/v1/events"
_PER_PAGE   = 50

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
    "guadalajara": "JAL", "zapopan": "JAL",
    "monterrey": "NLE", "san nicolas de los garza": "NLE", "montemorelos": "NLE",
    "apodaca": "NLE", "linares": "NLE",
    "cdmx": "CMX", "ciudad de mexico": "CMX", "ciudad de méxico": "CMX",
    "puebla": "PUE", "cholula": "PUE",
    "queretaro": "QUE", "querétaro": "QUE",
    "cancun": "ROO", "cancún": "ROO", "playa del carmen": "ROO", "cozumel": "ROO",
    "merida": "YUC", "mérida": "YUC",
    "tijuana": "BCN", "ensenada": "BCN", "mexicali": "BCN",
    "san luis potosi": "SLP", "san luis potosí": "SLP",
    "aguascalientes": "AGU",
    "oaxaca": "OAX",
    "toluca": "MEX", "ecatepec": "MEX", "naucalpan": "MEX",
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
    page = 1

    while True:
        try:
            resp = get(
                _API,
                params={"per_page": _PER_PAGE, "page": page, "status": "publish"},
                source=SOURCE_NAME,
                timeout=20,
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

        try:
            data: dict = resp.json()
        except Exception as e:
            print(f"[{SOURCE_NAME}] page {page} JSON erro: {e}")
            break

        if page == 1:
            _debug_response(data)

        events: list[dict] = data.get("events") or []
        if not events:
            break

        for ev in events:
            c = _parse_event(ev, today)
            if c:
                corridas.append(c)

        total_pages = data.get("total_pages", 1)
        if page >= total_pages:
            break
        page += 1

    print(f"[{SOURCE_NAME}] {len(corridas)} corrida(s) encontrada(s)")
    return corridas


def _debug_response(data: dict) -> None:
    import json as _json
    print(f"[{SOURCE_NAME}] DEBUG keys: {list(data.keys())}")
    print(f"[{SOURCE_NAME}] DEBUG total={data.get('total')}, total_pages={data.get('total_pages')}")
    events = data.get("events") or []
    if events:
        ev = events[0]
        print(f"[{SOURCE_NAME}] DEBUG event[0] keys: {list(ev.keys())}")
        print(f"[{SOURCE_NAME}] DEBUG event[0]: {_json.dumps(ev, default=str)[:800]}")


def _parse_event(ev: dict, today: str) -> Corrida | None:
    titulo_raw = (ev.get("title") or "").strip()
    if not titulo_raw:
        return None
    titulo = normalize_titulo(_strip_html(titulo_raw))

    # Date from start_date (ISO format: "2026-09-27 08:00:00")
    start_raw = ev.get("start_date") or ""
    if not start_raw:
        return None
    try:
        data_evento = start_raw[:10]  # "YYYY-MM-DD"
        datetime.strptime(data_evento, "%Y-%m-%d")
    except ValueError:
        return None

    if data_evento < today:
        return None

    # Location — FMAA events are always in Mexico
    venue = ev.get("venue") or {}
    city = (venue.get("city") or "").strip()
    raw_state = (venue.get("stateprovince") or "").strip()
    state_key = re.sub(r"[^\w\s]", "", raw_state).lower().strip()
    estado = _MX_STATES.get(state_key) or _MX_CITY_STATE.get(state_key) or \
             _MX_CITY_STATE.get(re.sub(r"[^\w\s]", "", city).lower().strip()) or ""
    if not estado:
        _, estado = _geo.resolve(city or raw_state, "", "MX")
    cidade = f"{city}, México" if city else "México"
    localizacao = cidade

    # URL
    event_link = ev.get("url") or _BASE

    # Distances from title
    distancias = _parse_distances(titulo)

    post_id = ev.get("id") or slugify(titulo)
    race_id = f"fmaa_{post_id}_{data_evento[:4]}"
    now = now_iso()

    return Corrida(
        id=race_id,
        titulo=titulo,
        data_evento=data_evento,
        horario=start_raw[11:16] if len(start_raw) >= 16 else None,
        localizacao=localizacao,
        cidade=cidade,
        estado=estado,
        pais="MX",
        distancias=distancias,
        imagem_url=None,
        inscricoes_abertas=None,
        periodo_inscricao=None,
        fontes=[FonteInfo(nome=SOURCE_NAME, link_evento=event_link, links_inscricao=[event_link])],
        miss_count=0,
        first_seen_at=now,
        updated_at=now,
    )


def _parse_distances(titulo: str) -> list[Distancia]:
    result: list[Distancia] = []
    seen: set = set()
    for m in _DIST_RE.finditer(titulo):
        km_str, mi_str, marat, medio = m.group(1), m.group(2), m.group(3), m.group(4)
        if marat:
            km: float | str = 42.195
        elif medio:
            km = 21.097
        elif km_str:
            km = float(km_str)
        elif mi_str:
            km = f"{mi_str} mi"
        else:
            continue
        key = km if isinstance(km, str) else round(float(km))
        if key not in seen:
            seen.add(key)
            result.append(Distancia(km=km, data=None, horario=None))
    return result


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text).strip()
