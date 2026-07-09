"""Scraper for SP City Marathon — fully dynamic from the Iguana Sports calendar.

No hardcoded event data. The Iguana "Calendário" blog
(``/blogs/calendario-corridas-de-rua``) lists each event as an article. The SP
City Marathon article (handle ``sp-city-marathon-<year>``) carries a structured
header — ``<Event> DD Mon YYYY HH:MM City | UF | País`` — plus the offered
distances in its body. This scraper discovers the article by its stable
``sp-city-marathon`` handle (so it auto-rolls to each next edition), reads the
date / start time / location / distances live, and links to the Iguana product
for registration. Emits nothing if the article isn't found or the edition has
already happened — never a stored/past value.

Note: the Shopify product handle is an opaque code (e.g. ``etnk26``) with no
date, which is why a ``products/sp-city-marathon-<year>.json`` guess fails; the
calendar article is the authoritative, human-readable source.
"""
from __future__ import annotations
import re

from bs4 import BeautifulSoup

from ..http_client import get
from ..models import Corrida, Distancia, FonteInfo
from ..utils import normalize_titulo, now_iso, today_iso
from .. import geo as _geo

BASE        = "https://iguanasports.com.br"
BLOG_INDEX  = f"{BASE}/blogs/calendario-corridas-de-rua"
SOURCE_NAME = "SP City Marathon"

# One recurring annual event: after each edition and before the next is announced
# this scraper correctly returns nothing. test_source treats that empty result as
# expected downtime, not a health failure. See scraper/test_source.py.
SINGLE_EVENT = True

_HANDLE_RE = re.compile(r'/blogs/calendario-corridas-de-rua/(sp-city-marathon-\d{4})', re.I)
_MON = {'jan': 1, 'fev': 2, 'mar': 3, 'abr': 4, 'mai': 5, 'jun': 6,
        'jul': 7, 'ago': 8, 'set': 9, 'out': 10, 'nov': 11, 'dez': 12}
# Structured event header: "26 Jul 2026 05:15 São Paulo | SP | Brasil"
_HEADER_RE = re.compile(
    r'(\d{1,2})\s+(jan|fev|mar|abr|mai|jun|jul|ago|set|out|nov|dez)\w*\s+(20\d{2})'
    r'\s+(\d{1,2}):(\d{2})\s+([^|]+?)\s*\|\s*([A-Za-zÀ-ú]{2})\s*\|',
    re.IGNORECASE,
)
_NNK_RE = re.compile(r'(\d{1,3})[.,](\d)\s?K\b')
_CANON = [(42.195, 41.5, 43.0), (21.097, 20.5, 21.5)]


def _find_article_handles(soup: BeautifulSoup) -> list[str]:
    handles: list[str] = []
    for a in soup.find_all("a", href=True):
        m = _HANDLE_RE.search(a["href"])
        if m and m.group(1) not in handles:
            handles.append(m.group(1))
    return handles


def _distances(html: str, text: str) -> list[float]:
    kms: set[float] = set()
    for a, b in _NNK_RE.findall(html):
        v = float(f"{a}.{b}")
        for canon, lo, hi in _CANON:
            if lo <= v <= hi:
                v = canon
                break
        if 3 <= v <= 200:
            kms.add(v)
    if not kms:  # keyword fallback
        tl = text.lower()
        if re.search(r'meia[\s-]?maratona', tl):
            kms.add(21.097)
        if re.search(r'(?<!meia.)\bmaratona\b', tl):
            kms.add(42.195)
    return sorted(kms)


def _og_image(soup: BeautifulSoup) -> str | None:
    tag = soup.find("meta", property="og:image")
    return tag["content"] if tag and tag.get("content") else None


def _registration_link(soup: BeautifulSoup, fallback: str) -> str:
    for a in soup.find_all("a", href=True):
        if "/products/" in a["href"]:
            return a["href"] if a["href"].startswith("http") else BASE + a["href"]
    return fallback


def _parse_article(html: str, url: str, today: str) -> Corrida | None:
    soup = BeautifulSoup(html, "lxml")
    text = soup.get_text(" ")

    m = _HEADER_RE.search(text)
    if not m:
        return None
    d, mon, y, hh, mm, city, uf = m.groups()
    mo = _MON.get(mon.lower()[:3])
    if not mo:
        return None
    data_evento = f"{y}-{mo:02d}-{int(d):02d}"
    if data_evento < today:
        return None
    horario = f"{int(hh):02d}:{mm}"
    cidade, uf = city.strip(), uf.upper()

    distancias_km = _distances(html, text)
    if not distancias_km:
        return None

    title_tag = soup.find("title")
    raw_title = (title_tag.get_text() if title_tag else "")
    raw_title = re.split(r'[–\-|]', raw_title)[0].strip()  # drop "– Iguana Sports"
    titulo = normalize_titulo(raw_title) or SOURCE_NAME

    pais, estado = _geo.resolve(f"{cidade}, {uf}", cidade, "BR")
    estado = estado or uf
    now = now_iso()
    fonte = FonteInfo(
        nome=SOURCE_NAME,
        link_evento=url,
        links_inscricao=[_registration_link(soup, url)],
        tipo="organizador",
    )
    return Corrida(
        id=f"sp-city-marathon-sp-{y}",
        titulo=titulo,
        data_evento=data_evento,
        horario=horario,
        localizacao=f"{cidade}, {uf}",
        cidade=cidade,
        estado=estado,
        pais=pais or "BR",
        distancias=[Distancia(km=k, data=None, horario=horario) for k in distancias_km],
        imagem_url=_og_image(soup),
        inscricoes_abertas=None,
        periodo_inscricao=None,
        fontes=[fonte],
        miss_count=0,
        first_seen_at=now,
        updated_at=now,
    )


def scrape() -> list[Corrida]:
    try:
        resp = get(BLOG_INDEX)
        resp.raise_for_status()
        index = BeautifulSoup(resp.text, "lxml")
    except Exception as e:
        print(f"[{SOURCE_NAME}] índice do calendário inacessível: {e}")
        return []

    handles = _find_article_handles(index)
    if not handles:
        print(f"[{SOURCE_NAME}] artigo SP City não encontrado no calendário")
        return []

    today = today_iso()
    out: list[Corrida] = []
    for h in handles:
        url = f"{BLOG_INDEX}/{h}"
        try:
            r = get(url)
            r.raise_for_status()
        except Exception as e:
            print(f"[{SOURCE_NAME}] artigo {h} falhou: {e}")
            continue
        c = _parse_article(r.text, url, today)
        if c:
            out.append(c)

    print(f"[{SOURCE_NAME}] {len(out)} corrida(s) encontrada(s)")
    return out
