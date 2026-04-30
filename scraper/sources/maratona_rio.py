"""Scraper for maratonadorio.com.br (Maratona do Rio 2026)

Edição 2026 é multi-day (4–7 jun). Dados de distância e horário são
hardcoded conforme regulamento publicado; apenas a imagem og é
buscada dinamicamente no site oficial.
"""
from __future__ import annotations
from bs4 import BeautifulSoup

from ..http_client import get
from ..models import Corrida, Distancia, FonteInfo
from ..utils import slugify, now_iso, today_iso

URL          = "https://www.maratonadorio.com.br/"
INSCRICAO_URL = "https://www.godream.com.br/evento/maratona-do-rio-2026-publico-geral-6808310"
SOURCE_NAME  = "Maratona do Rio"

# 2026: evento corre de 4 a 7 de junho. data_evento = último dia (42K),
# garantindo que o card permaneça visível até o encerramento do evento.
_DATA_EVENTO = "2026-06-07"

# Cada distância tem data e horário próprios conforme regulamento 2026.
_DISTANCIAS = [
    Distancia(km=5.0,    data="2026-06-04", horario="16:00"),
    Distancia(km=10.0,   data="2026-06-05", horario="07:00"),
    Distancia(km=21.097, data="2026-06-06", horario="05:30"),
    Distancia(km=42.195, data="2026-06-07", horario="05:30"),
]


def scrape() -> list[Corrida]:
    imagem_url = _fetch_og_image()
    return [_build(imagem_url)]


def _fetch_og_image() -> str | None:
    for url in [URL, INSCRICAO_URL]:
        try:
            resp = get(url)
            if resp.status_code != 200:
                continue
            soup = BeautifulSoup(resp.text, "lxml")
            # og:image (preferred)
            tag = soup.find("meta", property="og:image")
            if tag and tag.get("content"):
                return tag["content"]
            # Site is Next.js and often lacks og:image — fall back to first
            # carousel/slide image from the static CDN
            for img in soup.find_all("img", src=True):
                src = img.get("src", "")
                if "static.maratonadorio.com.br/media/upload/slide/" in src:
                    return src
        except Exception:
            pass
    return None


def _build(imagem_url: str | None) -> Corrida:
    now = now_iso()
    today = today_iso()
    titulo = "Maratona do Rio"
    fonte = FonteInfo(
        nome=SOURCE_NAME,
        link_evento=URL,
        links_inscricao=[INSCRICAO_URL],
    )
    return Corrida(
        id=f"{slugify(titulo)}_rj_{today}",
        titulo=titulo,
        data_evento=_DATA_EVENTO,
        horario="05:30",
        localizacao="Rio de Janeiro, RJ",
        cidade="Rio de Janeiro",
        estado="RJ",
        distancias=_DISTANCIAS,
        imagem_url=imagem_url,
        inscricoes_abertas=True,
        periodo_inscricao=None,
        fontes=[fonte],
        miss_count=0,
        first_seen_at=now,
        updated_at=now,
    )
