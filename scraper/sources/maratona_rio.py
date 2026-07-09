"""Scraper for Maratona do Rio (maratonadorio.com.br).

Fully dynamic — no hardcoded event data. Every mutable field is read live from
the official site, so the scraper auto-rolls to each next edition on its own:

- **Date**: the homepage counts down to the edition (a ``DD/MM/YYYY`` banner).
  The earliest future date on the page is the upcoming edition.
- **Distances**: the "Provas" menu enumerates the offered races (5K/10K/21K/42K…).
- **Registration link**: discovered from the page; falls back to the official
  site URL (always a valid link) when no dedicated registration URL is present.

Emits nothing if the homepage can't be read, no future date is found, or no
distances are listed — never substitutes a stored/past value.
"""
from __future__ import annotations
import re

from bs4 import BeautifulSoup

from ..http_client import get
from ..models import Corrida, Distancia, FonteInfo
from ..utils import normalize_date, now_iso, today_iso
from .. import geo as _geo

SITE_URL    = "https://www.maratonadorio.com.br/"
SITE_EN_URL = "https://www.maratonadorio.com.br/en"
SOURCE_NAME = "Maratona do Rio"

# One recurring annual event: after each edition and before the next is announced
# this scraper correctly returns nothing. test_source treats that empty result as
# expected downtime, not a health failure. See scraper/test_source.py.
SINGLE_EVENT = True

# Canonical metric distances for the named races
_CANON = {5: 5.0, 10: 10.0, 21: 21.097, 42: 42.195}


def _fetch_site() -> BeautifulSoup | None:
    for url in (SITE_URL, SITE_EN_URL):
        try:
            resp = get(url)
            if resp.status_code == 200:
                return BeautifulSoup(resp.text, "lxml")
        except Exception:
            pass
    return None


def _extract_date(text: str, today: str) -> str | None:
    """The edition date — the earliest *future* date the page advertises.

    The homepage shows a countdown to the next edition as ``DD/MM/YYYY``; older
    ``N de mês de ano`` / ``N a N de mês de ano`` formats are also accepted so the
    parser keeps working if the layout changes.
    """
    candidates: set[str] = set()
    for d, m, y in re.findall(r'\b(\d{1,2})/(\d{1,2})/(20\d{2})\b', text):
        candidates.add(f"{y}-{int(m):02d}-{int(d):02d}")
    for m in re.finditer(r'(\d{1,2})\s+a\s+(\d{1,2})\s+de\s+(\w+)\s+de\s+(20\d{2})', text, re.IGNORECASE):
        iso = normalize_date(f"{m.group(2)} de {m.group(3)} de {m.group(4)}")
        if iso:
            candidates.add(iso)
    for m in re.finditer(r'(\d{1,2})\s+de\s+(\w+)\s+de\s+(20\d{2})', text, re.IGNORECASE):
        iso = normalize_date(m.group(0))
        if iso:
            candidates.add(iso)
    future = sorted(d for d in candidates if d >= today)
    return future[0] if future else None


def _extract_distances(text: str) -> list[float]:
    """Offered distances from the 'Provas' menu (e.g. 'Provas 5K 10K 21K 42K')."""
    m = re.search(r'Provas\s+((?:\d{1,2}\s?[Kk]\s*)+)', text)
    if not m:
        return []
    kms: list[float] = []
    for d in re.findall(r'(\d{1,2})\s?[Kk]', m.group(1)):
        v = int(d)
        km = _CANON.get(v, float(v))
        if 1 <= km <= 200 and km not in kms:
            kms.append(km)
    return sorted(kms)


def _find_inscricao_link(soup: BeautifulSoup) -> str | None:
    # Prefer a dedicated registration platform link, then any inscription/sales link.
    for a in soup.find_all("a", href=True):
        if re.search(r'godream|ticketsports|sympla|brasilcorrida|ativo\.com', a["href"], re.IGNORECASE):
            return a["href"]
    for a in soup.find_all("a", href=True):
        label = (a.get_text(strip=True) or "").lower()
        href = a["href"]
        if any(k in label for k in ("inscri", "comprar", "register", "canais de venda")) and href.startswith("http"):
            return href
    return None


def _fetch_og_image(soup: BeautifulSoup) -> str | None:
    tag = soup.find("meta", property="og:image")
    if tag and tag.get("content"):
        return tag["content"]
    for img in soup.find_all("img", src=True):
        if "static.maratonadorio.com.br/media/upload/slide/" in img.get("src", ""):
            return img["src"]
    return None


def scrape() -> list[Corrida]:
    soup = _fetch_site()
    if not soup:
        print(f"[{SOURCE_NAME}] site inacessível")
        return []

    today = today_iso()
    text = soup.get_text(" ")

    data_evento = _extract_date(text, today)
    if not data_evento:
        print(f"[{SOURCE_NAME}] nenhuma data futura encontrada — ignorando")
        return []

    kms = _extract_distances(text)
    if not kms:
        print(f"[{SOURCE_NAME}] nenhuma distância estruturada — ignorando")
        return []

    link = _find_inscricao_link(soup) or SITE_URL
    distancias = [Distancia(km=km, data=None, horario=None) for km in kms]

    now = now_iso()
    estado = _geo.resolve("Rio de Janeiro, RJ", "Rio de Janeiro", "BR")[1] or "RJ"
    fonte = FonteInfo(
        nome=SOURCE_NAME,
        link_evento=SITE_URL,
        links_inscricao=[link],
        tipo="organizador",
    )
    print(f"[{SOURCE_NAME}] 1 corrida: {data_evento} dist={kms}")
    return [Corrida(
        id=f"maratona-do-rio-rj-{data_evento[:4]}",
        titulo="Maratona do Rio",
        data_evento=data_evento,
        horario=None,
        localizacao="Rio de Janeiro, RJ",
        cidade="Rio de Janeiro",
        estado=estado,
        pais="BR",
        distancias=distancias,
        imagem_url=_fetch_og_image(soup),
        inscricoes_abertas=None,
        periodo_inscricao=None,
        fontes=[fonte],
        miss_count=0,
        first_seen_at=now,
        updated_at=now,
    )]
