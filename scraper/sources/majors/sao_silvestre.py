"""Scraper for Corrida Internacional de São Silvestre

Realizada todo dia 31 de dezembro na Avenida Paulista, São Paulo-SP,
desde 1925. Distância oficial: 15 km. Inscrições exclusivamente via
Ticket Sports (parceria renovada até 2027).

Data e edição são computadas dinamicamente: sempre 31/12 do ano corrente
(ou do próximo ano se a edição já passou). O link de inscrição no Ticket
Sports é extraído dinamicamente do site oficial; se não encontrado, cai
de volta para o site oficial.

Retorna lista vazia quando o horário de largada ainda não foi divulgado —
comportamento esperado entre edições (Jan–Out de cada ano).
"""
from __future__ import annotations
from datetime import date
import re

from bs4 import BeautifulSoup

from ...http_client import get
from ...models import Corrida, Distancia, FonteInfo
from ...utils import now_iso, today_iso
from ... import geo as _geo

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

_RACE_TIME_RE = re.compile(
    r"(?:sa[íi]da|largada|in[íi]cio|partida|hor[áa]rio|come[çc]a|come[çc]o)"
    r"[^0-9]{0,50}(\d{1,2})[hH:]([0-5]\d)"
    r"|(?:sa[íi]da|largada|in[íi]cio|partida|hor[áa]rio)"
    r"[^0-9]{0,50}(\d{1,2})\s*[hH]\b(?!\d)",
    re.IGNORECASE,
)


def _fetch_page_data() -> tuple[str | None, str | None]:
    """Fetch the official site once; return (inscricao_url, horario)."""
    for _attempt in range(2):
        result = _try_fetch_page()
        if result[1] is not None:
            return result
    return None, None


def _try_fetch_page() -> tuple[str | None, str | None]:
    """Single fetch attempt of the official site; return (inscricao_url, horario)."""
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
        horario: str | None = None
        full_text = soup.get_text(" ", strip=True)
        for pattern in (_RACE_TIME_RE, _TIME_RE):
            m = pattern.search(full_text)
            if not m:
                continue
            if m.group(1) is not None:
                h, mi = int(m.group(1)), int(m.group(2))
            elif m.lastindex and m.lastindex >= 3 and m.group(3) is not None:
                h, mi = int(m.group(3)), 0
            else:
                continue
            if 4 <= h <= 23 and 0 <= mi <= 59:
                horario = f"{h:02d}:{mi:02d}"
                break
        return inscricao_url, horario
    except Exception:
        pass
    return None, None


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
    if horario is None:
        print(f"[{SOURCE_NAME}] sem horário publicado no site oficial — evento não incluído")
        return []
    imagem_url = _fetch_og_image()
    return [_build(year, data_evento, inscricao_url, imagem_url, horario)]


def _build(year: int, data_evento: str, inscricao_url: str | None, imagem_url: str | None, horario: str | None = None) -> Corrida:
    now = now_iso()
    edicao = year - 1925  # 100ª em 2025, 101ª em 2026, etc.
    titulo = f"{edicao}ª Corrida Internacional de São Silvestre"
    estado = _geo.resolve("São Paulo, SP", "São Paulo", "BR")[1] or "SP"

    links_inscricao = [inscricao_url] if inscricao_url else [SITE_URL]

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
