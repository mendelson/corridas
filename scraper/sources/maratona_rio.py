"""Scraper for Maratona do Rio (maratonadorio.com.br)

Data extraída dinamicamente do site oficial (URL estável, conteúdo
atualizado a cada edição). Link de inscrição (GoDream) buscado no HTML
do site. Se a busca falhar, usa dados da última edição conhecida.

Estrutura: evento multi-day de 4 dias (5K qui, 10K sex, 21K sáb, 42K dom).
Datas das distâncias menores calculadas a partir do dia da maratona.
"""
from __future__ import annotations
import re
from datetime import date, timedelta

from bs4 import BeautifulSoup

from ..http_client import get
from ..models import Corrida, Distancia, FonteInfo
from ..utils import normalize_date, now_iso, today_iso

SITE_URL    = "https://www.maratonadorio.com.br/"
SITE_EN_URL = "https://www.maratonadorio.com.br/en"
SOURCE_NAME = "Maratona do Rio"

# Horários do regulamento mais recente (referência)
_H_5K       = "16:00"
_H_10K      = "07:00"
_H_21K      = "05:30"
_H_42K      = "05:30"

# Fallback: última edição conhecida (2026, semana de 4-7 jun)
_FALLBACK_DATA_42K = "2026-06-07"
_FALLBACK_INSC     = "https://www.godream.com.br/evento/maratona-do-rio-2026-publico-geral-6808310"


def _target_year() -> int:
    today = date.today()
    # Evento tipicamente em junho; após agosto busca o próximo ano
    if today < date(today.year, 8, 1):
        return today.year
    return today.year + 1


def _fetch_site() -> BeautifulSoup | None:
    for url in [SITE_URL, SITE_EN_URL]:
        try:
            resp = get(url)
            if resp.status_code == 200:
                return BeautifulSoup(resp.text, "lxml")
        except Exception:
            pass
    return None


def _extract_marathon_date(text: str) -> str | None:
    """Extrai a data da maratona (42K = último dia do evento).

    Suporta:
    - "4, 5, 6 e 7 de junho de 2026"   → "2026-06-07"
    - "4 a 7 de junho de 2026"         → "2026-06-07"
    - "7 de junho de 2026"             → "2026-06-07"
    """
    # "N1, N2, ... e N_last de mês de ano"
    m = re.search(
        r'(?:\d{1,2}[\s,]+)+e\s+(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})',
        text, re.IGNORECASE,
    )
    if m:
        return normalize_date(f"{m.group(1)} de {m.group(2)} de {m.group(3)}")

    # "N1 a N2 de mês de ano"
    m = re.search(
        r'\d{1,2}\s+a\s+(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})',
        text, re.IGNORECASE,
    )
    if m:
        return normalize_date(f"{m.group(1)} de {m.group(2)} de {m.group(3)}")

    # Data única
    m = re.search(r'\d{1,2}\s+de\s+\w+\s+de\s+\d{4}', text, re.IGNORECASE)
    if m:
        return normalize_date(m.group(0))

    return None


def _find_inscricao_link(soup: BeautifulSoup) -> str | None:
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "godream.com.br" in href and "/evento/" in href:
            return href
    for a in soup.find_all("a", href=True):
        text = a.get_text(strip=True).lower()
        href = a["href"]
        if any(k in text for k in ["inscri", "comprar", "register"]) and href.startswith("http"):
            return href
    return None


def _fetch_og_image(soup: BeautifulSoup | None) -> str | None:
    if not soup:
        return None
    tag = soup.find("meta", property="og:image")
    if tag and tag.get("content"):
        return tag["content"]
    # Site Next.js: fallback to first carousel image
    for img in soup.find_all("img", src=True):
        src = img.get("src", "")
        if "static.maratonadorio.com.br/media/upload/slide/" in src:
            return src
    return None


def scrape() -> list[Corrida]:
    year = _target_year()
    soup = _fetch_site()

    data_42k = inscricao_url = None

    if soup:
        data_42k = _extract_marathon_date(soup.get_text(" "))
        inscricao_url = _find_inscricao_link(soup)

    # Validate extracted year matches target
    if data_42k and not data_42k.startswith(str(year)):
        data_42k = None

    data_42k = data_42k or _FALLBACK_DATA_42K
    inscricao_url = inscricao_url or _FALLBACK_INSC

    # Calcular datas dos outros dias (evento de 4 dias: qui-sex-sáb-dom)
    d_42k = date.fromisoformat(data_42k)
    data_21k = (d_42k - timedelta(days=1)).isoformat()
    data_10k = (d_42k - timedelta(days=2)).isoformat()
    data_5k  = (d_42k - timedelta(days=3)).isoformat()

    distancias = [
        Distancia(km=5.0,    data=data_5k,  horario=_H_5K),
        Distancia(km=10.0,   data=data_10k, horario=_H_10K),
        Distancia(km=21.097, data=data_21k, horario=_H_21K),
        Distancia(km=42.195, data=data_42k, horario=_H_42K),
    ]

    imagem_url = _fetch_og_image(soup)
    now = now_iso()
    titulo = "Maratona do Rio"
    fonte = FonteInfo(
        nome=SOURCE_NAME,
        link_evento=SITE_URL,
        links_inscricao=[inscricao_url],
    )
    return [Corrida(
        id=f"maratona-do-rio-rj-{year}",
        titulo=titulo,
        data_evento=data_42k,
        horario=_H_42K,
        localizacao="Rio de Janeiro, RJ",
        cidade="Rio de Janeiro",
        estado="RJ",
        distancias=distancias,
        imagem_url=imagem_url,
        inscricoes_abertas=True,
        periodo_inscricao=None,
        fontes=[fonte],
        miss_count=0,
        first_seen_at=now,
        updated_at=now,
    )]
