"""Scraper for corridasbr.com.br/df/calendario.asp"""
from __future__ import annotations
import re
from bs4 import BeautifulSoup

from ..http_client import get
from ..models import Corrida, Distancia, FonteInfo
from ..utils import (
    normalize_date, normalize_time, normalize_titulo, slugify, now_iso, today_iso
)

URL = "https://www.corridasbr.com.br/df/calendario.asp"
SOURCE_NAME = "Corridas BR"


def scrape() -> list[Corrida]:
    try:
        resp = get(URL)
        resp.raise_for_status()
    except Exception as e:
        print(f"[{SOURCE_NAME}] erro ao buscar {URL}: {e}")
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    corridas: list[Corrida] = []

    # Look for table rows with event data
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

    titulo_raw = cells[1].get_text(strip=True) if len(cells) > 1 else cells[0].get_text(strip=True)
    titulo = normalize_titulo(titulo_raw)
    if not titulo or len(titulo) < 3:
        return None

    link_tag = row.find("a", href=True)
    link = link_tag["href"] if link_tag else URL
    if link.startswith("/"):
        link = "https://www.corridasbr.com.br" + link

    distancias = _extract_distances(text)

    now = now_iso()
    today = today_iso()

    fonte = FonteInfo(
        nome=SOURCE_NAME,
        link_evento=link,
        links_inscricao=[link] if link != URL else [],
        inscricoes=[],
    )

    return Corrida(
        id=f"{slugify(titulo)}_df_{today}",
        titulo=titulo,
        data_evento=data or "",
        horario=normalize_time(text),
        localizacao="Brasília-DF",
        cidade="Brasília",
        estado="DF",
        distancias=distancias,
        imagem_url=None,
        inscricoes_abertas=None,
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
    link = link_tag["href"] if link_tag else URL
    if link.startswith("/"):
        link = "https://www.corridasbr.com.br" + link

    distancias = _extract_distances(text)
    now = now_iso()
    today = today_iso()

    fonte = FonteInfo(nome=SOURCE_NAME, link_evento=link, links_inscricao=[], inscricoes=[])
    return Corrida(
        id=f"{slugify(titulo)}_df_{today}",
        titulo=titulo,
        data_evento=data or "",
        horario=normalize_time(text),
        localizacao="Brasília-DF",
        cidade="Brasília",
        estado="DF",
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
