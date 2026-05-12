"""Scraper for corridasbr.com.br/df/calendario.asp"""
from __future__ import annotations
import re
from urllib.parse import urljoin, urlparse, urlunparse, parse_qs, urlencode
from bs4 import BeautifulSoup

from ..http_client import get
from ..models import Corrida, Distancia, FonteInfo
from ..utils import (
    normalize_date, normalize_time, normalize_titulo, slugify, now_iso, today_iso
)
from .. import geo as _geo

URL = "https://www.corridasbr.com.br/df/calendario.asp"
BASE = "https://www.corridasbr.com.br/df/"
SOURCE_NAME = "Corridas BR"


def _clean_event_url(href: str) -> str:
    """Build absolute URL keeping only mostracorrida.asp?escolha=N.
    The site embeds the event title (with spaces) directly in the href,
    which breaks URL parsing — we strip everything except 'escolha'."""
    href = href.strip()
    abs_url = urljoin(BASE, href)
    parsed = urlparse(abs_url)
    qs = parse_qs(parsed.query, keep_blank_values=False)
    # Keep only 'escolha' (the event id)
    cleaned_qs = {}
    if "escolha" in qs:
        # parse_qs may have split malformed values; pick the first numeric chunk
        val = qs["escolha"][0]
        m = re.match(r"\d+", val)
        if m:
            cleaned_qs["escolha"] = m.group(0)
    new_query = urlencode(cleaned_qs)
    return urlunparse(parsed._replace(query=new_query, fragment=""))


def scrape() -> list[Corrida]:
    try:
        resp = get(URL)
        resp.raise_for_status()
    except Exception as e:
        print(f"[{SOURCE_NAME}] erro ao buscar {URL}: {e}")
        return []

    # Old ASP site declares charset=iso-8859-1 with a typo (`https-equiv`),
    # so httpx auto-detection fails. Force windows-1252 (cp1252 superset of latin-1).
    html_text = resp.content.decode("windows-1252", errors="replace")
    soup = BeautifulSoup(html_text, "lxml")
    corridas: list[Corrida] = []

    rows = soup.select("table tr") or soup.select("tr")
    for row in rows:
        try:
            corrida = _parse_row(row)
            if corrida:
                corridas.append(corrida)
        except Exception as e:
            print(f"[{SOURCE_NAME}] erro ao parsear linha: {e}")

    # Fallback: try divs/articles
    if not corridas:
        for el in soup.select("div.evento, div.race, article, .item"):
            try:
                corrida = _parse_div(el)
                if corrida:
                    corridas.append(corrida)
            except Exception as e:
                print(f"[{SOURCE_NAME}] erro ao parsear div: {e}")

    print(f"[{SOURCE_NAME}] {len(corridas)} corridas encontradas")
    return corridas


def _parse_row(row) -> Corrida | None:
    cells = row.find_all(["td", "th"])
    if len(cells) < 2:
        return None
    text = " ".join(c.get_text(strip=True) for c in cells)
    if not text or len(text) < 10:
        return None

    # Skip header rows
    if any(h in text.lower() for h in ["data", "evento", "prova", "cidade"]):
        first = cells[0].get_text(strip=True).lower()
        if first in ("data", "evento", "prova"):
            return None

    # First cell must contain a valid date
    data = normalize_date(cells[0].get_text(strip=True))
    if not data:
        return None

    # Find the event link — skip city-filter links (por_cidade.asp, por_estado.asp)
    event_link = None
    titulo_raw = None
    for a in row.find_all("a", href=True):
        href = a["href"]
        if "por_cidade" in href or "por_estado" in href or "por_distancia" in href:
            continue
        event_link = href
        titulo_raw = a.get_text(strip=True)
        break

    # Fallback: use the non-date, non-city cell text
    if not titulo_raw:
        for cell in cells[1:]:
            txt = cell.get_text(strip=True)
            if txt and len(txt) > 3 and not re.match(r'^[\d/\-\.]+$', txt):
                titulo_raw = txt
                break

    titulo = normalize_titulo(titulo_raw or "")
    if not titulo or len(titulo) < 3:
        return None

    link = _clean_event_url(event_link) if event_link else URL

    distancias = _extract_distances(text)

    now = now_iso()
    today = today_iso()

    has_link = link != URL
    fonte = FonteInfo(
        nome=SOURCE_NAME,
        link_evento=link,
        links_inscricao=[link] if has_link else [],
    )

    estado = _geo.resolve("Brasília-DF", "Brasília", "BR")[1] or "DF"
    return Corrida(
        id=f"{slugify(titulo)}_df_{today}",
        titulo=titulo,
        data_evento=data or "",
        horario=normalize_time(text),
        localizacao="Brasília-DF",
        cidade="Brasília",
        estado=estado,
        pais="BR",
        distancias=distancias,
        imagem_url=None,
        inscricoes_abertas=True if has_link else None,
        periodo_inscricao=None,
        fontes=[fonte],
        miss_count=0,
        first_seen_at=now,
        updated_at=now,
    )


def _parse_div(el) -> Corrida | None:
    text = el.get_text(" ", strip=True)
    if not text or len(text) < 10:
        return None

    heading = el.find(["h1", "h2", "h3", "h4", "strong"])
    titulo_raw = heading.get_text(strip=True) if heading else text[:60]
    titulo = normalize_titulo(titulo_raw)
    if not titulo:
        return None

    data = _extract_date(text)
    link_tag = el.find("a", href=True)
    link = _clean_event_url(link_tag["href"]) if link_tag else URL

    distancias = _extract_distances(text)
    now = now_iso()
    today = today_iso()

    fonte = FonteInfo(nome=SOURCE_NAME, link_evento=link, links_inscricao=[])
    estado = _geo.resolve("Brasília-DF", "Brasília", "BR")[1] or "DF"
    return Corrida(
        id=f"{slugify(titulo)}_df_{today}",
        titulo=titulo,
        data_evento=data or "",
        horario=normalize_time(text),
        localizacao="Brasília-DF",
        cidade="Brasília",
        estado=estado,
        pais="BR",
        distancias=distancias,
        imagem_url=None,
        inscricoes_abertas=None,
        periodo_inscricao=None,
        fontes=[fonte],
        miss_count=0,
        first_seen_at=now,
        updated_at=now,
    )


def _extract_date(text: str) -> str | None:
    m = re.search(r"\d{1,2}/\d{1,2}/\d{4}", text)
    if m:
        return normalize_date(m.group(0))
    m = re.search(r"\d{1,2}\s+de\s+\w+\s+de\s+\d{4}", text, re.IGNORECASE)
    if m:
        return normalize_date(m.group(0))
    return None


def _extract_distances(text: str) -> list[Distancia]:
    nums = re.findall(r"\b(\d+)\s*[kK][mM]?\b", text)
    seen: set[float] = set()
    result = []
    for n in nums:
        km = float(n)
        if km not in seen and 1 <= km <= 200:
            seen.add(km)
            result.append(Distancia(km=km, data=None, horario=None))
    return result
