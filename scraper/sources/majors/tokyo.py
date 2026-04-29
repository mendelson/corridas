"""Tokyo Marathon scraper"""
from __future__ import annotations
import re
from bs4 import BeautifulSoup

from ...http_client import get
from ...models import Corrida, Distancia, FonteInfo, Inscricao
from ...utils import normalize_date, normalize_time, slugify, now_iso, today_iso

URL = "https://www.marathon.tokyo/en/"
INSCRICAO_URL = "https://www.marathon.tokyo/en/participants/"
SOURCE_NAME = "Tokyo Marathon"


def scrape() -> list[Corrida]:
    try:
        resp = get(URL)
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
    titulo = "Tokyo Marathon"

    fonte = FonteInfo(
        nome=SOURCE_NAME,
        link_evento=URL,
        links_inscricao=[INSCRICAO_URL],
        inscricoes=[Inscricao(
            descricao="Tokyo Marathon",
            valor=None,
            disponivel=inscricoes_abertas if inscricoes_abertas is not None else False,
            link=INSCRICAO_URL,
        )],
    )

    return [Corrida(
        id=f"{slugify(titulo)}_int_{today}",
        titulo=titulo,
        data_evento=data or "",
        horario="09:10",
        localizacao="Tóquio, Japão",
        cidade="Tóquio, Japão",
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
    for tag in soup.find_all(["time", "p", "span", "div"], limit=50):
        text = tag.get_text(strip=True)
        m = re.search(r"\b(20\d{2})\b", text)
        if m:
            year = m.group(1)
            # Tokyo is typically in March
            date_m = re.search(r"(\w+\s+\d{1,2})", text)
            if date_m:
                return normalize_date(f"{date_m.group(1)}, {year}")
    return None


def _extract_image(soup) -> str | None:
    img = soup.find("meta", property="og:image")
    if img:
        return img.get("content")
    img = soup.find("img")
    return img.get("src") if img else None


def _check_inscricoes(soup) -> bool | None:
    text = soup.get_text().lower()
    if any(k in text for k in ["entry open", "registration open", "apply now"]):
        return True
    if any(k in text for k in ["entry closed", "registration closed"]):
        return False
    return None


def _placeholder() -> Corrida:
    now = now_iso()
    today = today_iso()
    titulo = "Tokyo Marathon"
    fonte = FonteInfo(
        nome=SOURCE_NAME, link_evento=URL,
        links_inscricao=[INSCRICAO_URL],
        inscricoes=[],
    )
    return Corrida(
        id=f"{slugify(titulo)}_int_{today}",
        titulo=titulo, data_evento="", horario=None,
        localizacao="Tóquio, Japão", cidade="Tóquio, Japão", estado="INT",
        distancias=[Distancia(km=42.195, data=None, horario=None)],
        imagem_url=None, inscricoes_abertas=None, periodo_inscricao=None,
        fontes=[fonte], miss_count=0, first_seen_at=now, updated_at=now,
    )
