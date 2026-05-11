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
from ..utils import normalize_titulo, slugify, now_iso, today_iso

SOURCE_NAME = "Asdeporte"
_BASE       = "https://www.asdeporte.com"
_LIST_URL   = f"{_BASE}/eventos"
_MAX_PAGES  = 15

_MX_STATES: dict[str, str] = {
    "aguascalientes": "AGS", "baja california": "BC", "baja california sur": "BCS",
    "campeche": "CAM", "chiapas": "CHIS", "chihuahua": "CHIH", "coahuila": "COAH",
    "colima": "COL", "cdmx": "CDMX", "ciudad de mexico": "CDMX",
    "ciudad de méxico": "CDMX", "durango": "DGO", "guanajuato": "GTO",
    "guerrero": "GRO", "hidalgo": "HGO", "jalisco": "JAL", "mexico": "MEX",
    "méxico": "MEX", "michoacan": "MICH", "michoacán": "MICH", "morelos": "MOR",
    "nayarit": "NAY", "nuevo leon": "NL", "nuevo león": "NL", "oaxaca": "OAX",
    "puebla": "PUE", "queretaro": "QRO", "querétaro": "QRO",
    "quintana roo": "QROO", "san luis potosi": "SLP", "san luis potosí": "SLP",
    "sinaloa": "SIN", "sonora": "SON", "tabasco": "TAB", "tamaulipas": "TAMPS",
    "tlaxcala": "TLAX", "veracruz": "VER", "yucatan": "YUC", "yucatán": "YUC",
    "zacatecas": "ZAC",
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

    for page in range(1, _MAX_PAGES + 1):
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

    place = (ev.get("place") or "").strip()
    ciudad, estado = _parse_location(place)

    route = ev.get("routeConvocatoria") or ""
    event_link = _BASE + route if route.startswith("/") else (route or _LIST_URL)

    distancias = _parse_distances(titulo)
    imagem = ev.get("imgEventDesktop") or ev.get("imgEvent") or None

    ev_id = ev.get("id") or slugify(titulo + "_" + data_evento)
    race_id = f"asdeporte_{ev_id}"
    now = now_iso()

    return Corrida(
        id=race_id,
        titulo=titulo,
        data_evento=data_evento,
        horario=None,
        localizacao=ciudad,  # already "City, México"
        cidade=ciudad,
        estado=estado,
        distancias=distancias,
        imagem_url=imagem,
        inscricoes_abertas=None,
        periodo_inscricao=None,
        fontes=[FonteInfo(nome=SOURCE_NAME, link_evento=event_link, links_inscricao=[event_link])],
        miss_count=0,
        first_seen_at=now,
        updated_at=now,
    )


def _parse_location(text: str) -> tuple[str, str]:
    """Returns (ciudad, "INT"). All Asdeporte events are in Mexico.

    ciudad is formatted as "City, México" so the frontend's _extractCountry
    can correctly group these events under the México section.
    """
    if not text:
        return "México", "INT"
    parts = [p.strip() for p in text.split(",")]
    # Pick first non-numeric part as the city name; numeric parts are
    # street addresses (e.g. "Paseo de Los Parques Y Paseo de Las Peñas")
    ciudad = ""
    for part in parts:
        if not re.search(r"\d", part) and len(part) > 2:
            ciudad = part
            break
    if not ciudad:
        ciudad = parts[0] if parts else ""
    return (f"{ciudad}, México" if ciudad else "México"), "INT"


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
