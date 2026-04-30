"""Scraper for SP City Marathon 2026 (Iguana Sports / Nike)

10ª edição, 26 jul 2026. Apenas 42K e 21K, largada única às 05:15
na Praça Charles Miller (Pacaembu). Dados hardcoded conforme
regulamento publicado; imagem og buscada dinamicamente no site.
"""
from __future__ import annotations
from bs4 import BeautifulSoup

from ..http_client import get
from ..models import Corrida, Distancia, FonteInfo
from ..utils import slugify, now_iso, today_iso

URL           = "https://iguanasports.com.br/blogs/calendario-corridas-de-rua/sp-city-marathon-2026"
INSCRICAO_URL = "https://iguanasports.com.br/products/sp-city-marathon-2026"
SOURCE_NAME   = "SP City Marathon"

_DATA_EVENTO = "2026-07-26"

_DISTANCIAS = [
    Distancia(km=21.097, data="2026-07-26", horario="05:15"),
    Distancia(km=42.195, data="2026-07-26", horario="05:15"),
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
    titulo = "SP City Marathon"
    fonte = FonteInfo(
        nome=SOURCE_NAME,
        link_evento=URL,
        links_inscricao=[INSCRICAO_URL],
    )
    return Corrida(
        id=f"{slugify(titulo)}_sp_{today}",
        titulo=titulo,
        data_evento=_DATA_EVENTO,
        horario="05:15",
        localizacao="São Paulo, SP",
        cidade="São Paulo",
        estado="SP",
        distancias=_DISTANCIAS,
        imagem_url=imagem_url,
        inscricoes_abertas=True,
        periodo_inscricao=None,
        fontes=[fonte],
        miss_count=0,
        first_seen_at=now,
        updated_at=now,
    )
