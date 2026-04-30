"""Scraper for maratonadorio.com.br"""
from __future__ import annotations
from bs4 import BeautifulSoup

from ..http_client import get
from ..models import Corrida, Distancia, FonteInfo, Inscricao
from ..utils import slugify, now_iso, today_iso, extract_date_from_soup

URL = "https://www.maratonadorio.com.br/"
SOURCE_NAME = "Maratona do Rio"
KNOWN_DATE = "2026-06-21"  # 3º domingo de junho, edição 2026

_DISTANCIAS = [
    Distancia(km=42.195, data=None, horario=None),
    Distancia(km=21.097, data=None, horario=None),
    Distancia(km=10.0,   data=None, horario=None),
    Distancia(km=6.0,    data=None, horario=None),
]


def scrape() -> list[Corrida]:
    try:
        resp = get(URL)
        resp.raise_for_status()
    except Exception as e:
        print(f"[{SOURCE_NAME}] erro ao buscar {URL}: {e}")
        return [_build(KNOWN_DATE, None, None)]

    soup = BeautifulSoup(resp.text, "lxml")
    data = extract_date_from_soup(soup) or KNOWN_DATE
    imagem_url = _og_image(soup)
    inscricoes_abertas = _check_inscricoes(soup)

    return [_build(data, imagem_url, inscricoes_abertas)]


def _build(data: str, imagem_url: str | None, inscricoes_abertas: bool | None) -> Corrida:
    now = now_iso()
    today = today_iso()
    titulo = "Maratona do Rio"
    fonte = FonteInfo(
        nome=SOURCE_NAME,
        link_evento=URL,
        links_inscricao=[URL],
        inscricoes=[Inscricao(
            descricao="Maratona do Rio",
            valor=None,
            disponivel=inscricoes_abertas if inscricoes_abertas is not None else False,
            link=URL,
        )],
    )
    return Corrida(
        id=f"{slugify(titulo)}_rj_{today}",
        titulo=titulo,
        data_evento=data,
        horario="06:00",
        localizacao="Rio de Janeiro, RJ",
        cidade="Rio de Janeiro",
        estado="RJ",
        distancias=_DISTANCIAS,
        imagem_url=imagem_url,
        inscricoes_abertas=inscricoes_abertas,
        periodo_inscricao=None,
        fontes=[fonte],
        miss_count=0,
        first_seen_at=now,
        updated_at=now,
    )


def _og_image(soup) -> str | None:
    tag = soup.find("meta", property="og:image")
    return tag.get("content") if tag else None


def _check_inscricoes(soup) -> bool | None:
    text = soup.get_text().lower()
    if any(k in text for k in ["inscreva-se", "inscrições abertas", "comprar", "garantir vaga"]):
        return True
    if any(k in text for k in ["inscrições encerradas", "esgotado", "encerradas"]):
        return False
    return None
