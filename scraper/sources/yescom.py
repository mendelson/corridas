"""Scraper for yescom.com.br — homepage link discovery + per-event page parsing."""
from __future__ import annotations
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

from bs4 import BeautifulSoup

from ..http_client import get
from ..models import Corrida, Distancia, FonteInfo
from ..utils import normalize_titulo, slugify, infer_estado, now_iso, today_iso
from .. import geo as _geo

BASE = "https://www.yescom.com.br"
SOURCE_NAME = "Yescom"

_PT_MONTHS = {
    "janeiro": "01", "fevereiro": "02", "março": "03", "marco": "03",
    "abril": "04", "maio": "05", "junho": "06", "julho": "07",
    "agosto": "08", "setembro": "09", "outubro": "10",
    "novembro": "11", "dezembro": "12",
}

# Matches "26 setembro 2026" AND "26 de setembro de 2026"
_DATE_RE = re.compile(
    r"\b(\d{1,2})\s+(?:de\s+)?([A-Za-záéíóúãõâêô]+)\s+(?:de\s+)?(\d{4})\b",
    re.IGNORECASE,
)

# Matches the event date in regulation text: "realizada no dia 26 de setembro de 2026"
_RACE_DATE_RE = re.compile(
    r"(?:realizar|realizada|ocorre[r]?|acontece[r]?|prova\s+ser[aá])\s+"
    r"(?:\w+\s+){0,4}dia\s+(\d{1,2})\s+(?:de\s+)?([A-Za-záéíóúãõâêô]+)\s+(?:de\s+)?(\d{4})\b",
    re.IGNORECASE,
)

# "SÃO PAULO • 24 JANEIRO 2027"  or  "BELO HORIZONTE • 6 DEZEMBRO 2026"
_CITY_DATE_RE = re.compile(
    r"^([A-ZÁÉÍÓÚÀÂÃÊÔÕÇ][A-ZÁÉÍÓÚÀÂÃÊÔÕÇ\s]+?)\s*[•·|]\s*\d",
    re.IGNORECASE,
)

_INTERVAL_RE = re.compile(
    r"a cada \d+(?:[.,]\d+)?\s*k(?:m)?\b"
    r"|cada \d+(?:[.,]\d+)?\s*k(?:m)?\b"
    r"|\d+(?:[.,]\d+)?\s*k(?:m)?\s*(?:de hidrat|de água|de abastec)",
    re.IGNORECASE,
)

_CANONICAL = [(42.195, 41.5, 43.0), (21.097, 20.5, 21.5)]

# Time patterns: "07h30", "07:30h", "07:30", "7h", "horário: 7h30" — must not be followed by km
_TIME_RE = re.compile(
    r"\b(\d{1,2})[hH:]([0-5]\d)\s*(?:min\s*)?[hH]?\b(?!\s*[kK])"
    r"|\b(\d{1,2})\s*[hH]\b(?!\s*\d)",
    re.IGNORECASE,
)

# URL path segments → (default city, state)
_STATE_IN_URL = {
    "/rj/": ("Rio de Janeiro", "RJ"),
    "/sp/": ("São Paulo", "SP"),
    "/mg/": ("Belo Horizonte", "MG"),
    "/df/": ("Brasília", "DF"),
    "/rs/": ("Porto Alegre", "RS"),
    "/pr/": ("Curitiba", "PR"),
    "/ba/": ("Salvador", "BA"),
    "/ce/": ("Fortaleza", "CE"),
}

# Known Yescom events and their fixed city/state (for events without city in page)
_KNOWN_LOCATIONS: dict[str, tuple[str, str]] = {
    "maratonasp": ("São Paulo", "SP"),
    "meiasp": ("São Paulo", "SP"),
    "meiadorio": ("Rio de Janeiro", "RJ"),
    "voltadapampulha": ("Belo Horizonte", "MG"),
    "classicrun": ("São Paulo", "SP"),
    "corridagarotada": ("São Paulo", "SP"),
    "supergirl": ("São Paulo", "SP"),
    "cachorridagaroto": ("São Paulo", "SP"),
    "corridatomejerry": ("São Paulo", "SP"),
    "hellokittyfunrun": ("São Paulo", "SP"),  # overridden by URL /rj/ or /sp/
    "miraculousrun": ("Guarulhos", "SP"),
    "dezmilhasgaroto": ("São Paulo", "SP"),
    "corridadocafe": ("São Paulo", "SP"),
}


def scrape() -> list[Corrida]:
    try:
        resp = get(BASE)
        resp.raise_for_status()
    except Exception as e:
        print(f"[{SOURCE_NAME}] erro ao buscar homepage: {e}")
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    event_urls = _discover_events(soup)
    if not event_urls:
        print(f"[{SOURCE_NAME}] nenhum link de evento encontrado")
        return []

    corridas: list[Corrida] = []

    with ThreadPoolExecutor(max_workers=6) as ex:
        futures = {ex.submit(_parse_event_page, url): url for url in event_urls}
        for fut in as_completed(futures):
            url = futures[fut]
            try:
                corrida = fut.result()
                if corrida:
                    corridas.append(corrida)
            except Exception as e:
                print(f"[{SOURCE_NAME}] erro ao parsear {url}: {e}")

    print(f"[{SOURCE_NAME}] {len(corridas)} corridas encontradas")
    return corridas


def _discover_events(soup: BeautifulSoup) -> list[str]:
    seen: set[str] = set()
    urls: list[str] = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "index.asp" not in href:
            continue
        full = href if href.startswith("http") else BASE + href
        if full not in seen:
            seen.add(full)
            urls.append(full)
    return urls


def _parse_event_page(url: str) -> Corrida | None:
    try:
        resp = get(url)
        resp.raise_for_status()
    except Exception as e:
        print(f"[{SOURCE_NAME}] erro ao buscar {url}: {e}")
        return None

    soup = BeautifulSoup(resp.text, "lxml")

    # Title: prefer <title> tag, strip " | Yescom" suffix
    raw_title = ""
    title_tag = soup.find("title")
    if title_tag:
        raw_title = title_tag.get_text(strip=True)
        raw_title = re.sub(r"\s*[\-|]\s*Yescom.*$", "", raw_title, flags=re.IGNORECASE).strip()
    if not raw_title:
        for tag in ["h1", "h2", "h3"]:
            el = soup.find(tag)
            if el:
                raw_title = el.get_text(strip=True)
                break

    titulo = normalize_titulo(raw_title)
    if not titulo or len(titulo) < 3:
        return None

    heading_texts = [
        el.get_text(" ", strip=True)
        for el in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])
    ]
    # Full page text for date extraction (event date hides in regulation paragraphs)
    full_text = soup.get_text(" ", strip=True)

    data_evento = _extract_event_date(heading_texts, full_text)
    city, state, pais = _extract_location(heading_texts, url, titulo)
    localizacao = f"{city}, {state}" if city and state else city or state or ""

    distancias = _extract_distances(soup)
    if not distancias:
        print(f"[{SOURCE_NAME}] sem distâncias, pulando: {titulo!r}")
        return None

    horario = _extract_horario(full_text)
    if not horario:
        print(f"[{SOURCE_NAME}] sem horário, pulando: {titulo!r}")
        return None

    insc_link = _find_inscription_link(soup)
    today = today_iso()
    now = now_iso()

    fonte = FonteInfo(
        nome=SOURCE_NAME,
        link_evento=url,
        links_inscricao=[insc_link] if insc_link else [url],
        tipo="inscricao",
    )

    return Corrida(
        id=f"{slugify(titulo)}_{state.lower()}_{data_evento or 'sd'}",
        titulo=titulo,
        data_evento=data_evento or "",
        horario=horario,
        localizacao=localizacao,
        cidade=city,
        estado=state,
        pais=pais,
        distancias=distancias,
        imagem_url=_find_og_image(soup),
        inscricoes_abertas=True if insc_link else None,
        periodo_inscricao=None,
        fontes=[fonte],
        miss_count=0,
        first_seen_at=now,
        updated_at=now,
    )


def _extract_event_date(heading_texts: list[str], full_text: str) -> str | None:
    # 1. Try heading text first — short-form date like "11 Abril 2026"
    heading_dates: list[str] = []
    for text in heading_texts:
        for m in _DATE_RE.finditer(text):
            mo = _PT_MONTHS.get(m.group(2).lower())
            if not mo:
                continue
            year = int(m.group(3))
            if 2025 <= year <= 2030:
                heading_dates.append(f"{year}-{mo}-{m.group(1).zfill(2)}")
    if heading_dates:
        return sorted(heading_dates)[0]

    # 2. Search body for "realizada no dia X de Month de YYYY" — the authoritative event date
    for m in _RACE_DATE_RE.finditer(full_text):
        mo = _PT_MONTHS.get(m.group(2).lower())
        if not mo:
            continue
        year = int(m.group(3))
        if 2025 <= year <= 2030:
            return f"{year}-{mo}-{m.group(1).zfill(2)}"

    return None


def _extract_horario(text: str) -> str | None:
    """Parse times like '07h30', '07:30h', '07:30', '7h' from event page text."""
    if not text:
        return None
    m = _TIME_RE.search(text)
    if not m:
        return None
    if m.group(1) is not None:
        h, mi = int(m.group(1)), int(m.group(2))
    else:
        h, mi = int(m.group(3)), 0
    if not (4 <= h <= 23 and 0 <= mi <= 59):
        return None
    return f"{h:02d}:{mi:02d}"


def _extract_location(heading_texts: list[str], url: str, titulo: str) -> tuple[str, str, str]:
    # 1. "CITY • DD Month YYYY" pattern in headings
    for text in heading_texts:
        m = _CITY_DATE_RE.match(text.strip())
        if m:
            city_raw = m.group(1).strip().title()
            _pais_geo, _estado_geo = _geo.resolve(city_raw, "", "BR")
            state = infer_estado(city_raw, titulo) or _estado_geo or ""
            return city_raw, state, _pais_geo or "BR"

    # 2. State abbreviation in URL path (e.g. /rj/, /sp/)
    url_lower = url.lower()
    for pattern, (city, uf) in _STATE_IN_URL.items():
        if pattern in url_lower:
            return city, uf, "BR"

    # 3. Known event slug → location
    for slug, (city, uf) in _KNOWN_LOCATIONS.items():
        if f"/{slug}/" in url_lower:
            return city, uf, "BR"

    # 4. Fallback: infer from title, default SP (most Yescom events are SP)
    state = infer_estado("", titulo) or "SP"
    return "", state, "BR"


def _extract_distances(soup: BeautifulSoup) -> list[Distancia]:
    """Extract distances only from headings and short text blocks (avoids regulation noise)."""
    candidate_texts: list[str] = []

    # Headings are authoritative category markers
    for tag in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
        candidate_texts.append(tag.get_text(" ", strip=True))

    # Short spans/li/td that look like category entries (< 80 chars, contain km)
    for tag in soup.find_all(["span", "li", "td", "th", "button"]):
        t = tag.get_text(" ", strip=True)
        if len(t) < 80 and re.search(r"\d+\s*k(?:m)?\b", t, re.IGNORECASE):
            candidate_texts.append(t)

    text = " ".join(candidate_texts)
    clean = _INTERVAL_RE.sub(" ", text)

    seen: set[float] = set()
    result: list[Distancia] = []
    for n in re.findall(r"\b(\d+(?:[.,]\d+)?)\s*k(?:m)?\b", clean, re.IGNORECASE):
        km = float(n.replace(",", "."))
        for canon, lo, hi in _CANONICAL:
            if lo <= km <= hi:
                km = canon
                break
        # Only keep whole-number km or canonical half/full marathon distances
        if km not in (42.195, 21.097) and km != int(km):
            continue
        if km not in seen and 1 <= km <= 60:
            seen.add(km)
            result.append(Distancia(km=km, data=None, horario=None))

    # Fallback: scan the full page text for distances not found in headings/short elements
    if not result:
        full_text = soup.get_text(" ", strip=True)
        clean_full = _INTERVAL_RE.sub(" ", full_text)
        for n in re.findall(r"\b(\d+(?:[.,]\d+)?)\s*k(?:m)?\b", clean_full, re.IGNORECASE):
            km = float(n.replace(",", "."))
            for canon, lo, hi in _CANONICAL:
                if lo <= km <= hi:
                    km = canon
                    break
            if km not in (42.195, 21.097) and km != int(km):
                continue
            if km not in seen and 1 <= km <= 60:
                seen.add(km)
                result.append(Distancia(km=km, data=None, horario=None))

    return sorted(result, key=lambda d: d.km)


def _find_inscription_link(soup: BeautifulSoup) -> str | None:
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "minhasinscricoes.com.br" in href or "inscricao" in href.lower():
            return href if href.startswith("http") else BASE + href
    return None


def _find_og_image(soup: BeautifulSoup) -> str | None:
    tag = soup.find("meta", property="og:image")
    if tag and tag.get("content"):
        return tag["content"]
    return None
