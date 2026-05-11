"""Scraper for Asdeporte.com — Mexican multi-sport event platform.

Server-rendered HTML at /eventos?competencias=publicas&pagina=N.
Filters for running events (carreras); skips triathlons, cycling, etc.
"""
from __future__ import annotations
import re
from datetime import datetime

from bs4 import BeautifulSoup

from ..http_client import get
from ..models import Corrida, Distancia, FonteInfo
from ..utils import normalize_titulo, slugify, now_iso, today_iso

SOURCE_NAME = "Asdeporte"
_BASE       = "https://www.asdeporte.com"
_LIST_URL   = f"{_BASE}/eventos"
_MAX_PAGES  = 10

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

_MONTHS_ES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4,
    "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
    "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
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

# Distances embedded in title: "5k", "10K", "21K", "42K", "10 mi", etc.
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

        if page == 1:
            _debug_html(soup)

        cards = _find_cards(soup)
        if not cards:
            break

        prev_len = len(corridas)
        for card in cards:
            c = _parse_card(card, today)
            if c:
                corridas.append(c)

        # If we got cards but none were future running events, keep paginating
        # Stop only if the page itself is empty of cards
        if page > 1 and len(cards) < 5:
            break

    print(f"[{SOURCE_NAME}] {len(corridas)} corrida(s) encontrada(s)")
    return corridas


def _debug_html(soup: BeautifulSoup) -> None:
    # Check __NEXT_DATA__ for server-side JSON
    next_data = soup.find("script", {"id": "__NEXT_DATA__"})
    if next_data:
        print(f"[{SOURCE_NAME}] DEBUG __NEXT_DATA__ found, len={len(next_data.string or '')}")
        print(f"[{SOURCE_NAME}] DEBUG __NEXT_DATA__[:3000]:\n{(next_data.string or '')[:3000]}")

    # Check what _find_cards() actually returns
    cards = _find_cards(soup)
    print(f"[{SOURCE_NAME}] DEBUG _find_cards count={len(cards)}")
    for i, c in enumerate(cards[:2]):
        print(f"[{SOURCE_NAME}] DEBUG card[{i}] tag={c.name} classes={c.get('class')} html:\n{str(c)[:1000]}")


def _find_cards(soup: BeautifulSoup) -> list:
    # Will be refined once we see the actual HTML structure
    candidates = (
        soup.find_all("article")
        or soup.find_all("div", class_=re.compile(r"event|card|evento|race", re.I))
        or soup.find_all("li", class_=re.compile(r"event|card|evento|race", re.I))
    )
    return candidates


def _parse_card(card, today: str) -> Corrida | None:
    title_el = (
        card.find(["h1", "h2", "h3", "h4"])
        or card.find(class_=re.compile(r"title|nombre|name", re.I))
    )
    if not title_el:
        return None

    titulo = normalize_titulo(title_el.get_text(" ", strip=True))
    if not titulo:
        return None

    # Filter: skip non-running events
    if _NON_RUNNING.search(titulo) and not _RUNNING_KW.search(titulo):
        return None
    if not _RUNNING_KW.search(titulo):
        return None

    # Date: look for text like "20 septiembre 2026"
    text = card.get_text(" ", strip=True)
    data_evento = _parse_date_es(text)
    if not data_evento or data_evento < today:
        return None

    # Location
    loc_el = card.find(class_=re.compile(r"loc|city|lugar|ciudad|estado", re.I))
    location_text = loc_el.get_text(" ", strip=True) if loc_el else ""
    if not location_text:
        # Fallback: look for city,state pattern in card text
        m = re.search(r"([A-ZÁÉÍÓÚa-záéíóúüñ][^\n,]{2,40}),\s*([A-ZÁÉÍÓÚa-záéíóúñ][^\n,]{2,30})", text)
        location_text = m.group(0) if m else ""

    ciudad, estado = _parse_location(location_text)

    # Link
    link_el = card.find("a", href=True)
    event_link = _BASE + link_el["href"] if link_el and link_el["href"].startswith("/") else (link_el["href"] if link_el else _LIST_URL)

    # Distances from title
    distancias = _parse_distances(titulo)

    post_id = slugify(titulo + "_" + data_evento)
    race_id = f"asdeporte_{post_id}"
    now = now_iso()

    return Corrida(
        id=race_id,
        titulo=titulo,
        data_evento=data_evento,
        horario=None,
        localizacao=f"{ciudad}, {estado}" if ciudad else estado,
        cidade=ciudad,
        estado=estado,
        distancias=distancias,
        imagem_url=None,
        inscricoes_abertas=None,
        periodo_inscricao=None,
        fontes=[FonteInfo(nome=SOURCE_NAME, link_evento=event_link, links_inscricao=[event_link])],
        miss_count=0,
        first_seen_at=now,
        updated_at=now,
    )


def _parse_date_es(text: str) -> str | None:
    m = re.search(
        r"(\d{1,2})\s+(enero|febrero|marzo|abril|mayo|junio|julio|agosto"
        r"|septiembre|octubre|noviembre|diciembre)\s+(\d{4})",
        text, re.IGNORECASE,
    )
    if not m:
        return None
    day, month_es, year = int(m.group(1)), m.group(2).lower(), int(m.group(3))
    month = _MONTHS_ES.get(month_es)
    if not month:
        return None
    try:
        return datetime(year, month, day).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _parse_location(text: str) -> tuple[str, str]:
    if not text:
        return "", "INT"
    parts = [p.strip() for p in text.split(",")]
    ciudad = parts[0] if parts else ""
    state_raw = parts[1].lower() if len(parts) > 1 else ""
    estado = _MX_STATES.get(state_raw, "INT")
    return ciudad, estado


def _parse_distances(titulo: str) -> list[Distancia]:
    result: list[Distancia] = []
    seen: set = set()
    for m in _DIST_RE.finditer(titulo):
        km_str, mi_str, marat, medio = m.group(1), m.group(2), m.group(3), m.group(4)
        if marat:
            km = 42.195
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
