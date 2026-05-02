"""Shared helpers for World Marathon Majors scrapers."""
from __future__ import annotations
import re
from urllib.parse import urlparse
from bs4 import BeautifulSoup

from ...http_client import get
from ...models import Corrida, Distancia, FonteInfo
from ...utils import slugify, now_iso, today_iso, extract_date_from_soup

# Skip logos, icons, sponsors, and thumbnails when hunting for a race photo
_SKIP_IMG = re.compile(
    r"logo|icon|sponsor|cropped|favicon|white|_\d+x\d+\.|"
    r"adidas|schneider|bofa|wawhite|abbottwmm|isolation",
    re.IGNORECASE,
)


def _same_domain(img_url: str, page_url: str) -> bool:
    """Return True if img_url is from the same registered domain as page_url."""
    try:
        img_host  = urlparse(img_url).hostname or ''
        page_host = urlparse(page_url).hostname or ''
        # Accept same host, www. variants, and common CDN subdomains of the same base
        def base(h: str) -> str:
            parts = h.lstrip('www.').split('.')
            return '.'.join(parts[-2:]) if len(parts) >= 2 else h
        return base(img_host) == base(page_host)
    except Exception:
        return False


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
    known_image: str | None = None,
    distances_km: list[float] | None = None,
) -> list[Corrida]:
    soup = None
    try:
        resp = get(url, verify=ssl_verify)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
    except Exception as e:
        # Some sites (e.g. tcssydneymarathon.com.au) block automated access
        # at the SSL layer; fallback to known_date/known_image below.
        if ssl_verify:
            print(f"[{source_name}] erro ao buscar página: {e}")

    today = today_iso()
    year = known_date[:4]

    data = None
    imagem_url = None
    inscricoes_abertas = None

    if soup:
        raw_date = extract_date_from_soup(soup)
        if raw_date and raw_date >= today:
            data = raw_date
        # 1. og:image, 2. twitter:image, 3. first non-logo photo — all restricted to same domain
        imagem_url = (
            _og_image(soup, url)
            or _twitter_image(soup, url)
            or _first_race_photo(soup, url)
        )
        inscricoes_abertas = _check_status(soup, open_kw, closed_kw)

    data = data or known_date
    imagem_url = imagem_url or known_image

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
        distancias=[Distancia(km=km, data=None, horario=None) for km in (distances_km or [42.195])],
        imagem_url=imagem_url,
        inscricoes_abertas=inscricoes_abertas,
        periodo_inscricao=None,
        fontes=[fonte],
        miss_count=0,
        first_seen_at=now,
        updated_at=now,
    )]


def _og_image(soup, page_url: str) -> str | None:
    tag = soup.find("meta", property="og:image")
    src = tag.get("content") if tag else None
    return src if src and _same_domain(src, page_url) else None


def _twitter_image(soup, page_url: str) -> str | None:
    tag = soup.find("meta", attrs={"name": "twitter:image"})
    src = tag.get("content") if tag else None
    return src if src and _same_domain(src, page_url) else None


def _first_race_photo(soup, page_url: str) -> str | None:
    """First non-logo, non-sponsor JPG/PNG from the same domain as the scraped page."""
    for img in soup.find_all("img", src=True):
        src = img.get("src", "")
        if (src.startswith("http")
                and src.lower().endswith((".jpg", ".jpeg", ".png"))
                and not _SKIP_IMG.search(src)
                and _same_domain(src, page_url)):
            return src
    return None


def _check_status(soup, open_kw: list[str], closed_kw: list[str]) -> bool | None:
    text = soup.get_text(" ").lower()
    if any(k in text for k in closed_kw):
        return False
    if any(k in text for k in open_kw):
        return True
    return None
