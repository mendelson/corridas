"""Shared helpers for World Marathon Majors scrapers."""
from __future__ import annotations
import re
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
        # 1. og:image, 2. twitter:image, 3. first non-logo photo in page
        imagem_url = (
            _og_image(soup)
            or _twitter_image(soup)
            or _first_race_photo(soup)
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


def _og_image(soup) -> str | None:
    tag = soup.find("meta", property="og:image")
    return tag.get("content") if tag else None


def _twitter_image(soup) -> str | None:
    tag = soup.find("meta", attrs={"name": "twitter:image"})
    return tag.get("content") if tag else None


def _first_race_photo(soup) -> str | None:
    """First non-logo, non-sponsor JPG/PNG found in img tags."""
    for img in soup.find_all("img", src=True):
        src = img.get("src", "")
        if src.lower().endswith((".jpg", ".jpeg", ".png")) and not _SKIP_IMG.search(src):
            return src if src.startswith("http") else None
    return None


def _check_status(soup, open_kw: list[str], closed_kw: list[str]) -> bool | None:
    text = soup.get_text(" ").lower()
    if any(k in text for k in closed_kw):
        return False
    if any(k in text for k in open_kw):
        return True
    return None
