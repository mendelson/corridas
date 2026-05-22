"""Shared helpers for World Marathon Majors scrapers."""
from __future__ import annotations
import re
from urllib.parse import urlparse
from bs4 import BeautifulSoup

from ...http_client import get
from ...models import Corrida, Distancia, FonteInfo
from ...utils import slugify, now_iso, today_iso, extract_date_from_soup, extract_all_future_dates
from ... import geo as _geo

# Skip logos, icons, sponsors, and thumbnails when hunting for a race photo
_SKIP_IMG = re.compile(
    r"logo|icon|sponsor|cropped|favicon|white|_\d+x\d+\.|"
    r"adidas|schneider|bofa|wawhite|abbottwmm|isolation",
    re.IGNORECASE,
)

_SUSPICIOUS_HOST = re.compile(
    r"casino|silver|gold|crypto|bet|poker|loan|forex|pharma|"
    r"adult|xxx|porn|drug|pill|slot|wager|clickad|doubleclick|"
    r"adserv|tracker|analytics",
    re.IGNORECASE,
)


def _same_domain(img_url: str, page_url: str) -> bool:
    try:
        img_host  = urlparse(img_url).hostname or ''
        page_host = urlparse(page_url).hostname or ''
        if _SUSPICIOUS_HOST.search(img_host):
            return False
        def base(h: str) -> str:
            parts = h.lstrip('www.').split('.')
            return '.'.join(parts[-2:]) if len(parts) >= 2 else h
        return base(img_host) == base(page_host)
    except Exception:
        return False


def _resolve_dates(known_dates: list[str], today: str) -> list[str]:
    """Return only future confirmed known dates. Never projects or infers dates."""
    return sorted(d for d in known_dates if d >= today)


def scrape_major(
    *,
    source_name: str,
    titulo: str,
    url: str,
    known_date: str,
    known_dates: list[str] | None = None,
    horario: str,
    localizacao: str,
    cidade: str,
    pais: str,
    open_kw: list[str],
    closed_kw: list[str],
    ssl_verify: bool = True,
    known_image: str | None = None,
    distances_km: list[float] | None = None,
) -> list[Corrida]:
    soup = None
    try:
        resp = get(url, source=source_name, verify=ssl_verify)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
    except Exception as e:
        if ssl_verify:
            print(f"[{source_name}] erro ao buscar página: {e}")

    today = today_iso()
    all_known = sorted(set(known_dates or []) | {known_date})

    imagem_url = None
    inscricoes_abertas = None

    if soup:
        # Try to extract all future editions directly from the page
        live_dates = extract_all_future_dates(soup, today)
        if not live_dates:
            # Fall back to single-date extraction (catches dates slightly in the past too)
            single = extract_date_from_soup(soup)
            if single and single >= today:
                live_dates = [single]
        dates_to_use = live_dates if live_dates else _resolve_dates(all_known, today)

        imagem_url = (
            _og_image(soup, url)
            or _twitter_image(soup, url)
            or _first_race_photo(soup, url)
        )
        inscricoes_abertas = _check_status(soup, open_kw, closed_kw)
    else:
        dates_to_use = _resolve_dates(all_known, today)

    imagem_url = imagem_url or known_image
    now = now_iso()
    fonte = FonteInfo(
        nome=source_name,
        link_evento=url,
        links_inscricao=[url],
    )

    city_only = cidade.split(",")[0].strip()
    _, resolved_estado = _geo.resolve(city_only, "", pais)

    # Keep only earliest date per year — multi-day festivals share the same event id
    dates_by_year: dict[str, str] = {}
    for d in dates_to_use:
        yr = d[:4]
        if yr not in dates_by_year or d < dates_by_year[yr]:
            dates_by_year[yr] = d
    dates_to_use = sorted(dates_by_year.values())

    results = []
    for data in dates_to_use:
        year = data[:4]
        results.append(Corrida(
            id=f"{slugify(titulo)}_{pais.lower()}_{year}",
            titulo=titulo,
            data_evento=data,
            horario=horario,
            localizacao=localizacao,
            cidade=cidade,
            estado=resolved_estado,
            distancias=[Distancia(km=km, data=None, horario=None) for km in (distances_km or [42.195])],
            imagem_url=imagem_url,
            inscricoes_abertas=inscricoes_abertas,
            periodo_inscricao=None,
            fontes=[fonte],
            miss_count=0,
            first_seen_at=now,
            updated_at=now,
            pais=pais,
        ))

    if not results:
        print(f"[{source_name}] nenhuma edição futura identificada")

    return results


def _og_image(soup, page_url: str) -> str | None:
    tag = soup.find("meta", property="og:image")
    src = tag.get("content") if tag else None
    return src if src and _same_domain(src, page_url) else None


def _twitter_image(soup, page_url: str) -> str | None:
    tag = soup.find("meta", attrs={"name": "twitter:image"})
    src = tag.get("content") if tag else None
    return src if src and _same_domain(src, page_url) else None


def _first_race_photo(soup, page_url: str) -> str | None:
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
