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
from .. import geo as _geo

SITE_URL    = "https://www.saosilvestre.com.br"
SOURCE_NAME = "São Silvestre"

_DISTANCIA_KM = 15.0


def _target_year() -> int:
    today = date.today()
    if today <= date(today.year, 12, 31):
        return today.year
    return today.year + 1


_TIME_RE = re.compile(
    r"\b(\d{1,2})[hH:]([0-5]\d)\s*(?:min\s*)?[hH]?\b(?!\s*[kK])"
    r"|\b(\d{1,2})\s*[hH]\b(?!\s*\d)",
    re.IGNORECASE,
)


def _fetch_page_data() -> tuple[str | None, str | None]:
    """Fetch the official site once; return (inscricao_url, horario)."""
    try:
        resp = get(SITE_URL)
        if resp.status_code != 200:
            return None, None
        soup = BeautifulSoup(resp.text, "lxml")
        inscricao_url: str | None = None
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "ticketsports.com.br" in href and "/e/" in href:
                inscricao_url = href
                break
        if not inscricao_url:
            for a in soup.find_all("a", href=True):
                href = a["href"]
                text = a.get_text(strip=True).lower()
                if any(k in text for k in ["inscri", "comprar", "inscreva"]) and href.startswith("http"):
                    inscricao_url = href
                    break
        # Extract start time from page text
        horario: str | None = None
        full_text = soup.get_text(" ", strip=True)
        m = _TIME_RE.search(full_text)
        if m:
            if m.group(1) is not None:
                h, mi = int(m.group(1)), int(m.group(2))
            else:
                h, mi = int(m.group(3)), 0
            if 0 <= h <= 23 and 0 <= mi <= 59:
                horario = f"{h:02d}:{mi:02d}"
        return inscricao_url, horario
    except Exception:
        pass
    return None, None


def _fetch_inscricao_url() -> str | None:
    """Try to extract the Ticket Sports registration link from the official site."""
    inscricao_url, _ = _fetch_page_data()
    return inscricao_url


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
    inscricao_url, horario = _fetch_page_data()
    imagem_url = _fetch_og_image()
    return [_build(year, data_evento, inscricao_url, imagem_url, horario)]


def _build(year: int, data_evento: str, inscricao_url: str | None, imagem_url: str | None, horario: str | None = None) -> Corrida:
    now = now_iso()
    today = today_iso()
    edicao = year - 1925  # 100ª em 2025, 101ª em 2026, etc.
    titulo = f"{edicao}ª Corrida Internacional de São Silvestre"
    estado = _geo.resolve("São Paulo, SP", "São Paulo", "BR")[1] or "SP"

    links_inscricao = [inscricao_url] if inscricao_url else []

    fonte = FonteInfo(
        nome=SOURCE_NAME,
        link_evento=SITE_URL,
        links_inscricao=links_inscricao,
        tipo="organizador",
    )

    return Corrida(
        id=f"sao-silvestre-sp-{year}",
        titulo=titulo,
        data_evento=data_evento,
        horario=horario,
        localizacao="São Paulo, SP",
        cidade="São Paulo",
        estado=estado,
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
