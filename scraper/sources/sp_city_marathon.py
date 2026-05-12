"""Scraper for SP City Marathon (Nike / Iguana Sports)

Data e link de inscrição buscados dinamicamente via Shopify JSON API
(iguanasports.com.br/products/sp-city-marathon-{year}.json).
Distâncias fixas (21K + 42K); horário do regulamento mais recente como
referência enquanto o novo regulamento não é publicado.
"""
from __future__ import annotations
import re
from datetime import date

from bs4 import BeautifulSoup

from ..http_client import get
from ..models import Corrida, Distancia, FonteInfo
from ..utils import normalize_date, now_iso, today_iso
from .. import geo as _geo

BASE_URL    = "https://iguanasports.com.br"
BLOG_BASE   = f"{BASE_URL}/blogs/calendario-corridas-de-rua"
SOURCE_NAME = "SP City Marathon"

_REF_HORARIO = "05:15"  # referência do regulamento 2026
_DISTANCES   = [21.097, 42.195]

# Fallback: última edição conhecida
_FALLBACK_YEAR = 2026
_FALLBACK_DATA = "2026-07-26"
_FALLBACK_INSC = f"{BASE_URL}/products/sp-city-marathon-2026"
_FALLBACK_BLOG = f"{BLOG_BASE}/sp-city-marathon-2026"


def _target_year() -> int:
    today = date.today()
    # Evento tipicamente em julho; após setembro busca o próximo ano
    if today < date(today.year, 9, 1):
        return today.year
    return today.year + 1


def _fetch_shopify(year: int) -> dict | None:
    try:
        resp = get(f"{BASE_URL}/products/sp-city-marathon-{year}.json")
        if resp.status_code == 200:
            return resp.json().get("product")
    except Exception:
        pass
    return None


def _extract_date(body_html: str) -> str | None:
    text = BeautifulSoup(body_html, "lxml").get_text(" ")
    m = re.search(r'\d{1,2}\s+de\s+\w+\s+de\s+\d{4}', text, re.IGNORECASE)
    if m:
        return normalize_date(m.group(0))
    m = re.search(r'\d{1,2}/\d{1,2}/\d{4}', text)
    if m:
        return normalize_date(m.group(0))
    return None


def _fetch_og_image(urls: list[str]) -> str | None:
    for url in urls:
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


def scrape() -> list[Corrida]:
    year = _target_year()
    product = _fetch_shopify(year)

    if product:
        data_evento = _extract_date(product.get("body_html", "")) or _FALLBACK_DATA
        inscricao_url = f"{BASE_URL}/products/sp-city-marathon-{year}"
        blog_url = f"{BLOG_BASE}/sp-city-marathon-{year}"
        titulo = product.get("title") or f"SP City Marathon {year}"
        inscricoes_abertas: bool | None = True
    else:
        data_evento = _FALLBACK_DATA
        inscricao_url = _FALLBACK_INSC
        blog_url = _FALLBACK_BLOG
        titulo = f"SP City Marathon {year}"
        inscricoes_abertas = None

    imagem_url = _fetch_og_image([blog_url, inscricao_url])
    distancias = [Distancia(km=km, data=data_evento, horario=_REF_HORARIO) for km in _DISTANCES]

    now = now_iso()
    estado = _geo.resolve("São Paulo, SP", "São Paulo", "BR")[1] or "SP"
    fonte = FonteInfo(
        nome=SOURCE_NAME,
        link_evento=blog_url,
        links_inscricao=[inscricao_url],
    )
    return [Corrida(
        id=f"sp-city-marathon-sp-{year}",
        titulo=titulo,
        data_evento=data_evento,
        horario=_REF_HORARIO,
        localizacao="São Paulo, SP",
        cidade="São Paulo",
        estado=estado,
        pais="BR",
        distancias=distancias,
        imagem_url=imagem_url,
        inscricoes_abertas=inscricoes_abertas,
        periodo_inscricao=None,
        fontes=[fonte],
        miss_count=0,
        first_seen_at=now,
        updated_at=now,
    )]
