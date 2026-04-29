"""Boston Marathon scraper"""
from __future__ import annotations
import re
from bs4 import BeautifulSoup

from ...http_client import get
from ...models import Corrida, Distancia, FonteInfo, Inscricao
from ...utils import normalize_date, slugify, now_iso, today_iso

URL = "https://www.baa.org/"
INSCRICAO_URL = "https://www.baa.org/races/boston-marathon/"
SOURCE_NAME = "Boston Marathon"


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
    titulo = "Boston Marathon"

    fonte = FonteInfo(
        nome=SOURCE_NAME, link_evento=INSCRICAO_URL,
        links_inscricao=[INSCRICAO_URL],
        inscricoes=[Inscricao(
            descricao="Boston Marathon",
            valor=None,
            disponivel=inscricoes_abertas if inscricoes_abertas is not None else False,
            link=INSCRICAO_URL,
        )],
    )

    return [Corrida(
        id=f"{slugify(titulo)}_int_{today}",
        titulo=titulo,
        data_evento=data or "",
        horario="09:00",
        localizacao="Boston, EUA",
        cidade="Boston, EUA",
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
    for tag in soup.find_all(["time", "p", "span", "h1", "h2", "h3"], limit=50):
        text = tag.get_text(strip=True)
        m = re.search(r"(April|March|May)\s+\d{1,2},?\s+20\d{2}", text, re.IGNORECASE)
        if m:
            return normalize_date(m.group(0))
    return None


def _extract_image(soup) -> str | None:
    img = soup.find("meta", property="og:image")
    return img.get("content") if img else None


def _check_inscricoes(soup) -> bool | None:
    text = soup.get_text().lower()
    if any(k in text for k in ["register now", "registration open", "apply"]):
        return True
    if any(k in text for k in ["registration closed", "sold out"]):
        return False
    return None


def _placeholder() -> Corrida:
    now = now_iso()
    today = today_iso()
    titulo = "Boston Marathon"
    fonte = FonteInfo(nome=SOURCE_NAME, link_evento=INSCRICAO_URL, links_inscricao=[INSCRICAO_URL], inscricoes=[])
    return Corrida(
        id=f"{slugify(titulo)}_int_{today}",
        titulo=titulo, data_evento="", horario=None,
        localizacao="Boston, EUA", cidade="Boston, EUA", estado="INT",
        distancias=[Distancia(km=42.195, data=None, horario=None)],
        imagem_url=None, inscricoes_abertas=None, periodo_inscricao=None,
        fontes=[fonte], miss_count=0, first_seen_at=now, updated_at=now,
    )
