"""TCS New York City Marathon scraper"""
from __future__ import annotations
import re
from bs4 import BeautifulSoup

from ...http_client import get
from ...models import Corrida, Distancia, FonteInfo, Inscricao
from ...utils import normalize_date, slugify, now_iso, today_iso, extract_date_from_soup

URL = "https://www.nyrr.org/races/tcsnycmarathon"
INSCRICAO_URL = "https://www.nyrr.org/races/tcsnycmarathon"
SOURCE_NAME = "TCS New York City Marathon"
KNOWN_DATE = "2026-11-01"  # TCS NYC Marathon 2026: November 1, 2026


def scrape() -> list[Corrida]:
    try:
        resp = get(INSCRICAO_URL)
        resp.raise_for_status()
    except Exception as e:
        print(f"[{SOURCE_NAME}] erro: {e}")
        return [_placeholder()]

    soup = BeautifulSoup(resp.text, "lxml")
    data = _extract_date(soup)
    imagem_url = _extract_image(soup)
    inscricoes_abertas = _check_inscricoes(soup)

    now = now_iso()
    today = today_iso()
    titulo = "TCS New York City Marathon"

    fonte = FonteInfo(
        nome=SOURCE_NAME, link_evento=INSCRICAO_URL,
        links_inscricao=[INSCRICAO_URL],
        inscricoes=[Inscricao(
            descricao="TCS NYC Marathon",
            valor=None,
            disponivel=inscricoes_abertas if inscricoes_abertas is not None else False,
            link=INSCRICAO_URL,
        )],
    )

    return [Corrida(
        id=f"{slugify(titulo)}_int_{today}",
        titulo=titulo,
        data_evento=data or KNOWN_DATE,
        horario="08:00",
        localizacao="Nova York, EUA",
        cidade="Nova York, EUA",
        estado="INT",
        distancias=[Distancia(km=42.195, data=None, horario=None)],
        imagem_url=imagem_url,
        inscricoes_abertas=inscricoes_abertas,
        periodo_inscricao=None,
        fontes=[fonte],
        miss_count=0,
        first_seen_at=now,
        updated_at=now,
    )]


def _extract_date(soup) -> str | None:
    return extract_date_from_soup(soup)

def _extract_image(soup) -> str | None:
    img = soup.find("meta", property="og:image")
    return img.get("content") if img else None


def _check_inscricoes(soup) -> bool | None:
    text = soup.get_text().lower()
    if any(k in text for k in ["register now", "entry open", "apply"]):
        return True
    if any(k in text for k in ["entry closed", "registration closed"]):
        return False
    return None


def _placeholder() -> Corrida:
    now = now_iso()
    today = today_iso()
    titulo = "TCS New York City Marathon"
    fonte = FonteInfo(nome=SOURCE_NAME, link_evento=INSCRICAO_URL, links_inscricao=[INSCRICAO_URL], inscricoes=[])
    return Corrida(
        id=f"{slugify(titulo)}_int_{today}",
        titulo=titulo, data_evento=KNOWN_DATE, horario="08:00",
        localizacao="Nova York, EUA", cidade="Nova York, EUA", estado="INT",
        distancias=[Distancia(km=42.195, data=None, horario=None)],
        imagem_url=None, inscricoes_abertas=None, periodo_inscricao=None,
        fontes=[fonte], miss_count=0, first_seen_at=now, updated_at=now,
    )
