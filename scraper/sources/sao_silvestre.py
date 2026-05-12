"""Scraper for Corrida Internacional de São Silvestre

Realizada todo dia 31 de dezembro na Avenida Paulista, São Paulo-SP,
desde 1925. Distância oficial: 15 km. Inscrições exclusivamente via
Ticket Sports (parceria renovada até 2027).

Data e edição são computadas dinamicamente: sempre 31/12 do ano corrente
(ou do próximo ano se a edição já passou). O link de inscrição no Ticket
Sports é extraído dinamicamente do site oficial; se não encontrado, cai
de volta para o site oficial.
"""
from __future__ import annotations
from datetime import date
import re

from bs4 import BeautifulSoup

from ..http_client import get
from ..models import Corrida, Distancia, FonteInfo
from ..utils import slugify, now_iso, today_iso

SITE_URL    = "https://www.saosilvestre.com.br"
SOURCE_NAME = "São Silvestre"

_DISTANCIA_KM = 15.0


def _target_year() -> int:
    today = date.today()
    if today <= date(today.year, 12, 31):
        return today.year
    return today.year + 1


def _fetch_inscricao_url() -> str | None:
    """Try to extract the Ticket Sports registration link from the official site."""
    try:
        resp = get(SITE_URL)
        if resp.status_code != 200:
            return None
        soup = BeautifulSoup(resp.text, "lxml")
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "ticketsports.com.br" in href and "/e/" in href:
                return href
        # Also check for generic inscription links
        for a in soup.find_all("a", href=True):
            href = a["href"]
            text = a.get_text(strip=True).lower()
            if any(k in text for k in ["inscri", "comprar", "inscreva"]) and href.startswith("http"):
                return href
    except Exception:
        pass
    return None


def _fetch_og_image() -> str | None:
    try:
        resp = get(SITE_URL)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "lxml")
            tag = soup.find("meta", property="og:image")
            if tag and tag.get("content"):
                return tag["content"]
    except Exception:
        pass
    return None


def scrape() -> list[Corrida]:
    year = _target_year()
    data_evento = f"{year}-12-31"
    inscricao_url = _fetch_inscricao_url()
    imagem_url = _fetch_og_image()
    return [_build(year, data_evento, inscricao_url, imagem_url)]


def _build(year: int, data_evento: str, inscricao_url: str | None, imagem_url: str | None) -> Corrida:
    now = now_iso()
    today = today_iso()
    edicao = year - 1925  # 100ª em 2025, 101ª em 2026, etc.
    titulo = f"{edicao}ª Corrida Internacional de São Silvestre"

    links_inscricao = [inscricao_url] if inscricao_url else []

    fonte = FonteInfo(
        nome=SOURCE_NAME,
        link_evento=SITE_URL,
        links_inscricao=links_inscricao,
    )

    return Corrida(
        id=f"sao-silvestre-sp-{year}",
        titulo=titulo,
        data_evento=data_evento,
        horario=None,
        localizacao="São Paulo, SP",
        cidade="São Paulo",
        estado="SP",
        pais="BR",
        distancias=[Distancia(km=_DISTANCIA_KM, data=data_evento, horario=None)],
        imagem_url=imagem_url,
        inscricoes_abertas=True if links_inscricao else None,
        periodo_inscricao=None,
        fontes=[fonte],
        miss_count=0,
        first_seen_at=now,
        updated_at=now,
    )
