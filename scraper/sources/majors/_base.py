"""Shared helpers for World Marathon Majors scrapers."""
from __future__ import annotations
from bs4 import BeautifulSoup

from ...http_client import get
from ...models import Corrida, Distancia, FonteInfo
from ...utils import slugify, now_iso, today_iso, extract_date_from_soup


def scrape_major(
    *,
    source_name: str,
    titulo: str,
    url: str,
    known_date: str,
    horario: str,
    localizacao: str,
    cidade: str,
    open_kw: list[str],
    closed_kw: list[str],
    ssl_verify: bool = True,
) -> list[Corrida]:
    soup = None
    try:
        resp = get(url, verify=ssl_verify)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
    except Exception as e:
        print(f"[{source_name}] erro ao buscar página: {e}")

    today = today_iso()
    year = known_date[:4]

    data = None
    imagem_url = None
    inscricoes_abertas = None

    if soup:
        raw_date = extract_date_from_soup(soup)
        # Only use scraped date if it's in the future
        if raw_date and raw_date >= today:
            data = raw_date
        imagem_url = _og_image(soup)
        inscricoes_abertas = _check_status(soup, open_kw, closed_kw)

    data = data or known_date

    now = now_iso()
    fonte = FonteInfo(
        nome=source_name,
        link_evento=url,
        links_inscricao=[url] if inscricoes_abertas else [],
    )

    return [Corrida(
        id=f"{slugify(titulo)}_int_{year}",
        titulo=titulo,
        data_evento=data,
        horario=horario,
        localizacao=localizacao,
        cidade=cidade,
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


def _og_image(soup) -> str | None:
    tag = soup.find("meta", property="og:image")
    return tag.get("content") if tag else None


def _check_status(soup, open_kw: list[str], closed_kw: list[str]) -> bool | None:
    text = soup.get_text(" ").lower()
    if any(k in text for k in closed_kw):
        return False
    if any(k in text for k in open_kw):
        return True
    return None
