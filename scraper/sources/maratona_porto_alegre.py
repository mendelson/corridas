"""Scraper for Maratona Internacional de Porto Alegre

Data extraída dinamicamente do site oficial (homepage sempre exibe a
edição atual). Link de inscrição buscado no HTML do site oficial (Ticket
Sports). Se a busca dinâmica falhar, usa dados da última edição conhecida.

Estrutura do evento: multi-day, distâncias mais curtas no 1º dia e
42K no 2º dia. Padrão de 2 dias mantido como referência.
"""
from __future__ import annotations
import re
from datetime import date, timedelta

from bs4 import BeautifulSoup

from ..http_client import get
from ..models import Corrida, Distancia, FonteInfo
from ..utils import normalize_date, now_iso, today_iso

SITE_URL    = "https://maratonadeportoalegre.com.br/"
SOURCE_NAME = "Maratona de Porto Alegre"

# Horários do regulamento mais recente (referência)
_H_CURTAS = "09:00"
_H_MEIA   = "06:30"
_H_MARATONA = "06:00"

# Fallback: última edição conhecida (2026)
_FALLBACK_DATA1 = "2026-05-30"  # dia 1: 5K, 10K, 21K
_FALLBACK_DATA2 = "2026-05-31"  # dia 2: 42K
_FALLBACK_INSC  = "https://www.ticketsports.com.br/e/41-maratona-internacional-de-porto-alegre-olympikus-2026-72850"


def _target_year() -> int:
    today = date.today()
    # Evento tipicamente em maio/junho; após agosto busca o próximo ano
    if today < date(today.year, 8, 1):
        return today.year
    return today.year + 1


def _fetch_site() -> BeautifulSoup | None:
    try:
        resp = get(SITE_URL)
        if resp.status_code == 200:
            return BeautifulSoup(resp.text, "lxml")
    except Exception:
        pass
    return None


def _extract_dates(text: str) -> tuple[str | None, str | None]:
    """Extrai datas de 'N1 e N2 de mês de ano' ou variações."""
    # "30 e 31 de maio de 2026"
    m = re.search(
        r'(\d{1,2})\s+e\s+(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})',
        text, re.IGNORECASE,
    )
    if m:
        d1, d2, month, year = m.group(1), m.group(2), m.group(3), m.group(4)
        iso1 = normalize_date(f"{d1} de {month} de {year}")
        iso2 = normalize_date(f"{d2} de {month} de {year}")
        if iso1 and iso2:
            return iso1, iso2
    # "30 a 31 de maio de 2026"
    m = re.search(
        r'(\d{1,2})\s+a\s+(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})',
        text, re.IGNORECASE,
    )
    if m:
        d1, d2, month, year = m.group(1), m.group(2), m.group(3), m.group(4)
        iso1 = normalize_date(f"{d1} de {month} de {year}")
        iso2 = normalize_date(f"{d2} de {month} de {year}")
        if iso1 and iso2:
            return iso1, iso2
    # Data única — usa como dia 2; dia 1 = dia 2 - 1
    m = re.search(r'\d{1,2}\s+de\s+\w+\s+de\s+\d{4}', text, re.IGNORECASE)
    if m:
        iso2 = normalize_date(m.group(0))
        if iso2:
            d = date.fromisoformat(iso2)
            iso1 = (d - timedelta(days=1)).isoformat()
            return iso1, iso2
    return None, None


def _find_inscricao_link(soup: BeautifulSoup) -> str | None:
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "ticketsports.com.br" in href and "/e/" in href:
            return href
    return None


def _fetch_og_image(soup: BeautifulSoup | None) -> str | None:
    if soup:
        tag = soup.find("meta", property="og:image")
        if tag and tag.get("content"):
            return tag["content"]
    return None


def scrape() -> list[Corrida]:
    year = _target_year()
    soup = _fetch_site()

    data1 = data2 = inscricao_url = None

    if soup:
        text = soup.get_text(" ")
        data1, data2 = _extract_dates(text)
        inscricao_url = _find_inscricao_link(soup)

    # Validate extracted year matches target
    if data2 and not data2.startswith(str(year)):
        data1 = data2 = None

    data1 = data1 or _FALLBACK_DATA1
    data2 = data2 or _FALLBACK_DATA2
    inscricao_url = inscricao_url or _FALLBACK_INSC

    imagem_url = _fetch_og_image(soup)

    distancias = [
        Distancia(km=5.0,    data=data1, horario=_H_CURTAS),
        Distancia(km=10.0,   data=data1, horario=_H_CURTAS),
        Distancia(km=21.097, data=data1, horario=_H_MEIA),
        Distancia(km=42.195, data=data2, horario=_H_MARATONA),
    ]

    now = now_iso()
    titulo = "Maratona Internacional de Porto Alegre"
    fonte = FonteInfo(
        nome=SOURCE_NAME,
        link_evento=SITE_URL,
        links_inscricao=[inscricao_url],
    )
    return [Corrida(
        id=f"maratona-porto-alegre-rs-{year}",
        titulo=titulo,
        data_evento=data2,
        horario=_H_MARATONA,
        localizacao="Porto Alegre, RS",
        cidade="Porto Alegre",
        estado="RS",
        pais="BR",
        distancias=distancias,
        imagem_url=imagem_url,
        inscricoes_abertas=True,
        periodo_inscricao=None,
        fontes=[fonte],
        miss_count=0,
        first_seen_at=now,
        updated_at=now,
    )]
