"""Scraper for maratonadeportoalegre.com.br (41ª Maratona Internacional de Porto Alegre Olympikus 2026)

Evento multi-day (30–31 mai). Dados de distância e horário são
hardcoded conforme regulamento publicado; apenas a imagem og é
buscada dinamicamente no site oficial.
"""
from __future__ import annotations
from bs4 import BeautifulSoup

from ..http_client import get
from ..models import Corrida, Distancia, FonteInfo
from ..utils import slugify, now_iso, today_iso

URL           = "https://maratonadeportoalegre.com.br/"
INSCRICAO_URL = "https://www.ticketsports.com.br/e/41-maratona-internacional-de-porto-alegre-olympikus-2026-72850"
SOURCE_NAME   = "Maratona de Porto Alegre"

# 2026: evento corre 30–31 mai. data_evento = último dia (42K).
_DATA_EVENTO = "2026-05-31"

# Cada distância tem data e horário próprios conforme regulamento 2026.
_DISTANCIAS = [
    Distancia(km=5.0,    data="2026-05-30", horario="09:00"),
    Distancia(km=10.0,   data="2026-05-30", horario="09:00"),
    Distancia(km=21.097, data="2026-05-30", horario="06:30"),
    Distancia(km=42.195, data="2026-05-31", horario="06:00"),
]


def scrape() -> list[Corrida]:
    imagem_url = _fetch_og_image()
    return [_build(imagem_url)]


def _fetch_og_image() -> str | None:
    for url in [URL, INSCRICAO_URL]:
        try:
            resp = get(url)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "lxml")
                tag = soup.find("meta", property="og:image")
                if tag and tag.get("content"):
                    return tag["content"]
        except Exception:
            pass
    return None


def _build(imagem_url: str | None) -> Corrida:
    now = now_iso()
    today = today_iso()
    titulo = "Maratona Internacional de Porto Alegre"
    fonte = FonteInfo(
        nome=SOURCE_NAME,
        link_evento=URL,
        links_inscricao=[INSCRICAO_URL],
    )
    return Corrida(
        id=f"{slugify(titulo)}_rs_{today}",
        titulo=titulo,
        data_evento=_DATA_EVENTO,
        horario="06:00",
        localizacao="Porto Alegre, RS",
        cidade="Porto Alegre",
        estado="RS",
        distancias=_DISTANCIAS,
        imagem_url=imagem_url,
        inscricoes_abertas=True,
        periodo_inscricao=None,
        fontes=[fonte],
        miss_count=0,
        first_seen_at=now,
        updated_at=now,
    )
