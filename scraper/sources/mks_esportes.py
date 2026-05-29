"""Scraper for mksesportes.com.br — Wix site, SSR body text extraction."""
from __future__ import annotations
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

from bs4 import BeautifulSoup

from ..http_client import get
from ..models import Corrida, Distancia, FonteInfo
from ..utils import normalize_titulo, slugify, infer_estado, now_iso, today_iso
from .. import geo as _geo

BASE = "https://www.mksesportes.com.br"
SITEMAP_URL = f"{BASE}/pages-sitemap.xml"
SOURCE_NAME = "MKS Esportes"

# Known locations by URL slug (used when location can't be extracted from text)
_KNOWN_LOCATIONS: dict[str, tuple[str, str]] = {
    "meia-das-pontes": ("Brasília", "DF"),
    "meiadebuzios": ("Búzios", "RJ"),
    "bsb-ultra": ("Brasília", "DF"),
    "10kbrasilia": ("Brasília", "DF"),
    "ultradachapada": ("Alto Paraíso", "GO"),
    "country-club-montanha": ("Brasília", "DF"),
    "taboquinha-montanha": ("Brasília", "DF"),
    "uce-515": ("Brasília", "DF"),
}

# Slugs that are nav / about / non-event pages
_SKIP_SLUGS = {
    "", "quem-somos", "resultados", "classificados", "projetos", "mks-clube",
    "members", "virtuais", "blank", "projects", "papo-de-30", "general-6",
    "corrida",  # listing page, not a specific event
    # Non-running sports
    "triathlon", "duathlon", "aguasabertas", "copa-brasilia-de-triathlon",
    "tri-257", "duathlon-endurance", "triathlon-endurance",
    "aguasabertasbuzios", "aguasabertasbrasilia", "calendário", "calendario",
}

_NON_RUNNING_TITLE = re.compile(
    r"\btriathlon\b|\bduathlon\b|\baquabike\b|\baquathlon\b"
    r"|\bnatação\b|\bciclismo\b|\bpedalada\b|\bswinrun\b|\bswimsrun\b",
    re.IGNORECASE,
)

_PT_MONTHS = {
    "janeiro": "01", "fevereiro": "02", "março": "03", "marco": "03",
    "abril": "04", "maio": "05", "junho": "06", "julho": "07",
    "agosto": "08", "setembro": "09", "outubro": "10",
    "novembro": "11", "dezembro": "12",
}

_CANONICAL = [(42.195, 41.5, 43.0), (21.097, 20.5, 21.5)]

_INTERVAL_RE = re.compile(
    r"a cada \d+(?:[.,]\d+)?\s*k(?:m)?\b"
    r"|cada \d+(?:[.,]\d+)?\s*k(?:m)?\b"
    r"|\d+(?:[.,]\d+)?\s*k(?:m)?\s*(?:de hidrat|de água|de abastec)",
    re.IGNORECASE,
)

# Full date: "7 de junho de 2025"
_FULL_DATE_RE = re.compile(
    r"\b(\d{1,2})\s+de\s+([a-záéíóúãõâêôç]+)\s+de\s+(\d{4})\b",
    re.IGNORECASE,
)
# Partial date: "7 de março" (no year — resolved via context)
_PARTIAL_DATE_RE = re.compile(
    r"\b(\d{1,2})\s+de\s+([a-záéíóúãõâêôç]+)\b",
    re.IGNORECASE,
)
# Numeric: "10/09/2023"
_NUMERIC_DATE_RE = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")
# Time: "6:30 hrs", "7h00", "às 7 horas"
_TIME_RE = re.compile(r"\b(\d{1,2})(?:h|:)(\d{2})|\bàs?\s+(\d{1,2})\s+horas?", re.IGNORECASE)

# City/state in text: "em CITY - UF", "cidade de CITY - UF", "CITY - UF"
_CITY_STATE_RE = re.compile(
    r"(?:em|na cidade de|na|,\s*)\s*([A-ZÁÉÍÓÚÀÂÃÊÔÕÇ][A-Za-záéíóúàâãêôõç\s]+?)\s*[-–]\s*([A-Z]{2})\b"
)


def _discover_urls() -> list[str]:
    """Combine sitemap + nav links from homepage to catch pages missing from sitemap."""
    seen: set[str] = set()
    urls: list[str] = []

    def _add(u: str) -> None:
        u = u.rstrip("/")
        if u not in seen:
            seen.add(u)
            urls.append(u)

    try:
        resp = get(SITEMAP_URL)
        resp.raise_for_status()
        for u in re.findall(r"<loc>(https://www\.mksesportes\.com\.br[^<]*)</loc>", resp.text):
            _add(u)
    except Exception as e:
        print(f"[{SOURCE_NAME}] erro ao buscar sitemap: {e}")

    # Also harvest nav links from the homepage (catches pages absent from sitemap)
    try:
        resp = get(BASE)
        resp.raise_for_status()
        for href in re.findall(r'href="(https://www\.mksesportes\.com\.br[^"]*)"', resp.text):
            _add(href.split("?")[0].split("#")[0])
    except Exception:
        pass

    return urls


def scrape() -> list[Corrida]:
    today = today_iso()
    urls = _discover_urls()
    if not urls:
        print(f"[{SOURCE_NAME}] nenhuma URL encontrada")
        return []

    event_urls = _filter_event_urls(urls)

    corridas: list[Corrida] = []
    with ThreadPoolExecutor(max_workers=6) as ex:
        futures = {ex.submit(_parse_event_page, url, today): url for url in event_urls}
        for fut in as_completed(futures):
            try:
                c = fut.result()
                if c:
                    corridas.append(c)
            except Exception as e:
                print(f"[{SOURCE_NAME}] erro ao parsear {futures[fut]}: {e}")

    print(f"[{SOURCE_NAME}] {len(corridas)} corridas encontradas")
    return corridas


def _filter_event_urls(urls: list[str]) -> list[str]:
    result = []
    for url in urls:
        path = url.replace(BASE, "").strip("/").lower()
        slug = path.split("/")[-1] if path else ""
        if slug and slug not in _SKIP_SLUGS:
            result.append(url)
    return result


def _parse_event_page(url: str, today: str) -> Corrida | None:
    try:
        resp = get(url)
        resp.raise_for_status()
    except Exception as e:
        print(f"[{SOURCE_NAME}] erro ao buscar {url}: {e}")
        return None

    soup = BeautifulSoup(resp.text, "lxml")

    # Title
    title_tag = soup.find("title")
    raw_title = title_tag.get_text(strip=True) if title_tag else ""
    raw_title = re.sub(r"\s*[|\-]\s*Mksesportes.*$", "", raw_title, flags=re.IGNORECASE).strip()
    titulo = normalize_titulo(raw_title)
    if not titulo or len(titulo) < 3:
        return None
    if _NON_RUNNING_TITLE.search(titulo):
        return None

    # Body text (Wix SSR pre-renders rich text content)
    body = soup.find("body")
    text = body.get_text(" ", strip=True) if body else ""

    data_evento = _extract_date(text, today)
    if not data_evento or data_evento < today:
        return None

    horario = _extract_time(text)
    distancias = _extract_distances(titulo.lower(), text)

    slug = url.rstrip("/").split("/")[-1].lower()
    if slug in _KNOWN_LOCATIONS:
        cidade, estado = _KNOWN_LOCATIONS[slug]
    else:
        cidade, estado = _extract_location(text, titulo)
    localizacao = f"{cidade}, {estado}" if cidade and estado else cidade or estado or ""

    og_img = soup.find("meta", property="og:image")
    imagem = og_img.get("content") if og_img else None

    _pais_geo, _estado_geo = _geo.resolve(localizacao, cidade, "BR")
    pais = _pais_geo or "BR"
    estado = estado or _estado_geo or ""

    now = now_iso()
    fonte = FonteInfo(
        nome=SOURCE_NAME,
        link_evento=url,
        links_inscricao=[url],
        tipo="organizador",
    )

    return Corrida(
        id=f"mks_{slugify(titulo)}",
        titulo=titulo,
        data_evento=data_evento,
        horario=horario,
        localizacao=localizacao,
        cidade=cidade,
        estado=estado,
        pais=pais,
        distancias=distancias,
        imagem_url=imagem,
        inscricoes_abertas=None,
        periodo_inscricao=None,
        fontes=[fonte],
        miss_count=0,
        first_seen_at=now,
        updated_at=now,
    )


def _extract_date(text: str, today: str) -> str | None:
    today_year = int(today[:4])

    # 1. Full date "DD de MONTH de YYYY"
    full_dates = []
    for m in _FULL_DATE_RE.finditer(text):
        mo = _PT_MONTHS.get(m.group(2).lower())
        year = int(m.group(3))
        if mo and today_year - 1 <= year <= today_year + 3:
            full_dates.append(f"{year}-{mo}-{m.group(1).zfill(2)}")
    if full_dates:
        future = [d for d in full_dates if d >= today]
        return min(future) if future else None

    # 2. Numeric "DD/MM/YYYY"
    for m in _NUMERIC_DATE_RE.finditer(text):
        year = int(m.group(3))
        if today_year - 1 <= year <= today_year + 3:
            d = f"{year}-{m.group(2).zfill(2)}-{m.group(1).zfill(2)}"
            if d >= today:
                return d

    # 3. Partial date + context year ("7 de março" + "Em 2027")
    years = sorted(set(
        int(y) for y in re.findall(r"\b(20[2-9]\d)\b", text)
        if today_year <= int(y) <= today_year + 3
    ))
    if years:
        for m in _PARTIAL_DATE_RE.finditer(text):
            mo = _PT_MONTHS.get(m.group(2).lower())
            if not mo:
                continue
            for year in years:
                d = f"{year}-{mo}-{m.group(1).zfill(2)}"
                if d >= today:
                    return d

    return None


def _extract_time(text: str) -> str | None:
    for m in _TIME_RE.finditer(text):
        h = int(m.group(1) or m.group(3) or 0)
        mi = m.group(2) or "00"
        if 5 <= h <= 20:
            return f"{h:02d}:{mi}"
    return None


def _extract_distances(titulo_lower: str, text: str) -> list[Distancia]:
    seen: set[float] = set()
    result: list[Distancia] = []

    def _add(km: float) -> None:
        for canon, lo, hi in _CANONICAL:
            if lo <= km <= hi:
                km = canon
                break
        if km not in seen and 3 <= km <= 200:
            seen.add(km)
            result.append(Distancia(km=km, data=None, horario=None))

    text_lower = text.lower()
    if "meia maratona" in titulo_lower or "meia maratona" in text_lower:
        _add(21.097)
    if "meia de" in titulo_lower:  # "Meia de Búzios"
        _add(21.097)
    # "maratona" but not "meia maratona" or "ultra maratona" / "ultramaratona"
    if re.search(r"(?<!meia )(?<!ultra )\bmaratona\b", titulo_lower) or \
       re.search(r"(?<!meia )(?<!ultra )\bmaratona\b", text_lower):
        if 42.195 not in seen:
            _add(42.195)

    clean = _INTERVAL_RE.sub(" ", text)
    for m in re.finditer(r"\b(\d+(?:[.,]\d+)?)\s*k(?:m)?\b", clean, re.IGNORECASE):
        km = float(m.group(1).replace(",", "."))
        _add(km)

    return sorted(result, key=lambda d: d.km)


def _extract_location(text: str, titulo: str) -> tuple[str, str]:
    for m in _CITY_STATE_RE.finditer(text):
        city = m.group(1).strip().title()
        state = m.group(2).upper()
        if len(state) == 2 and city:
            return city, state

    _, _geo_state = _geo.resolve(text, "", "BR")
    state = infer_estado(text, titulo) or _geo_state or ""
    return "", state
