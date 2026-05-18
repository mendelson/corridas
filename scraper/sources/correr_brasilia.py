"""Scraper for correrbrasilia.com.br/calendario/"""
from __future__ import annotations
import re
from bs4 import BeautifulSoup

from ..http_client import get
from ..models import Corrida, Distancia, FonteInfo
from ..utils import (
    normalize_date, normalize_time, normalize_titulo, slugify, now_iso, today_iso
)
from .. import geo as _geo

URL = "https://correrbrasilia.com.br/calendario/"
SOURCE_NAME = "Correr Brasília"


def scrape() -> list[Corrida]:
    try:
        resp = get(URL)
        resp.raise_for_status()
    except Exception as e:
        print(f"[{SOURCE_NAME}] erro ao buscar {URL}: {e}")
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    corridas: list[Corrida] = []

    # Each event is typically in an article or table row
    # Try common patterns: .event, article, table rows
    events = soup.select("article") or soup.select(".event") or soup.select("tr")

    for el in events:
        try:
            corrida = _parse_event(el)
            if corrida:
                corridas.append(corrida)
        except Exception as e:
            print(f"[{SOURCE_NAME}] erro ao parsear evento: {e}")

    print(f"[{SOURCE_NAME}] {len(corridas)} corridas encontradas")
    return corridas


def _parse_event(el) -> Corrida | None:
    text = el.get_text(" ", strip=True)
    if not text or len(text) < 5:
        return None

    # Extract title — first heading or strong text
    titulo_raw = ""
    for tag in ["h1", "h2", "h3", "h4", "strong", "b", "a"]:
        found = el.find(tag)
        if found and found.get_text(strip=True):
            titulo_raw = found.get_text(strip=True)
            break
    if not titulo_raw:
        return None

    titulo = normalize_titulo(titulo_raw)

    # Date — search in text
    data = _extract_date(text)

    # Image
    img = el.find("img")
    imagem_url = img["src"] if img and img.get("src") else None
    if imagem_url and imagem_url.startswith("/"):
        imagem_url = "https://correrbrasilia.com.br" + imagem_url

    # Link
    link_tag = el.find("a", href=True)
    link = link_tag["href"] if link_tag else URL
    if link.startswith("/"):
        link = "https://correrbrasilia.com.br" + link

    # Distances
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
        id=f"{slugify(titulo)}_df_{data or 'sd'}",
        titulo=titulo,
        data_evento=data or "",
        horario=normalize_time(text),
        localizacao="Brasília-DF",
        cidade="Brasília",
        estado=estado,
        pais="BR",
        distancias=distancias,
        imagem_url=imagem_url,
        inscricoes_abertas=True if has_link else None,
        periodo_inscricao=None,
        fontes=[fonte],
        miss_count=0,
        first_seen_at=now,
        updated_at=now,
    )


def _extract_date(text: str) -> str | None:
    # Try DD/MM/YYYY
    m = re.search(r"\d{1,2}/\d{1,2}/\d{4}", text)
    if m:
        return normalize_date(m.group(0))
    # Try "10 de agosto de 2025"
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
