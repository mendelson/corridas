"""Scraper for sescdf.com.br/corridas — always DF"""
from __future__ import annotations
import re
from bs4 import BeautifulSoup

from ..http_client import get
from ..models import Corrida, Distancia, FonteInfo
from ..utils import (
    normalize_date, normalize_time, normalize_titulo,
    slugify, now_iso, today_iso
)

URL = "https://www.sescdf.com.br/corridas"
BASE = "https://www.sescdf.com.br"
SOURCE_NAME = "SESC DF"


def scrape() -> list[Corrida]:
    try:
        resp = get(URL)
        resp.raise_for_status()
    except Exception as e:
        print(f"[{SOURCE_NAME}] erro: {e}")
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    corridas: list[Corrida] = []

    for el in _find_events(soup):
        try:
            corrida = _parse_event(el)
            if corrida:
                corridas.append(corrida)
        except Exception as e:
            print(f"[{SOURCE_NAME}] erro: {e}")

    print(f"[{SOURCE_NAME}] {len(corridas)} corridas encontradas")
    return corridas


def _find_events(soup):
    for sel in [".event", ".race", ".card", "article", ".post", ".item", "li", "tr"]:
        els = soup.select(sel)
        if len(els) > 1:
            return els
    return []


def _parse_event(el) -> Corrida | None:
    text = el.get_text(" ", strip=True)
    if not text or len(text) < 5:
        return None

    heading = el.find(["h1", "h2", "h3", "h4", "strong"])
    titulo_raw = heading.get_text(strip=True) if heading else text[:80]
    titulo = normalize_titulo(titulo_raw)
    if not titulo or len(titulo) < 3:
        return None

    data = _extract_date(text)

    img = el.find("img")
    imagem_url = (img.get("src") or img.get("data-src")) if img else None
    if imagem_url and imagem_url.startswith("/"):
        imagem_url = BASE + imagem_url

    link_tag = el.find("a", href=True)
    link = link_tag["href"] if link_tag else URL
    if link.startswith("/"):
        link = BASE + link

    now = now_iso()
    today = today_iso()

    has_link = link != URL
    fonte = FonteInfo(
        nome=SOURCE_NAME,
        link_evento=link,
        links_inscricao=[link] if has_link else [],
    )

    return Corrida(
        id=f"{slugify(titulo)}_df_{today}",
        titulo=titulo,
        data_evento=data or "",
        horario=normalize_time(text),
        localizacao="Brasília-DF",
        cidade="Brasília",
        estado="DF",
        distancias=_extract_distances(text),
        imagem_url=imagem_url,
        inscricoes_abertas=True if has_link else None,
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
