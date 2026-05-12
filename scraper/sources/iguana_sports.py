"""Scraper for iguanasports.com.br — calendar blog listing."""
from __future__ import annotations
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

from bs4 import BeautifulSoup

from ..http_client import get
from ..models import Corrida, Distancia, FonteInfo
from ..utils import normalize_titulo, slugify, now_iso, today_iso
from .. import geo as _geo

BASE = "https://www.iguanasports.com.br"
CALENDAR_URL = f"{BASE}/blogs/calendario-corridas-de-rua"
SOURCE_NAME = "Iguana Sports"

_PT_MONTHS = {
    "jan": "01", "fev": "02", "mar": "03", "abr": "04",
    "mai": "05", "jun": "06", "jul": "07", "ago": "08",
    "set": "09", "out": "10", "nov": "11", "dez": "12",
}

_CANONICAL = [(42.195, 41.5, 43.0), (21.097, 20.5, 21.5)]

_INTERVAL_RE = re.compile(
    r"a cada \d+(?:[.,]\d+)?\s*k(?:m)?\b"
    r"|cada \d+(?:[.,]\d+)?\s*k(?:m)?\b"
    r"|\d+(?:[.,]\d+)?\s*k(?:m)?\s*(?:de hidrat|de água|de abastec)",
    re.IGNORECASE,
)

# Matches "26 Jul 2026 05:15" (listing page format)
_DATE_RE = re.compile(
    r"\b(\d{1,2})\s+([A-Za-z]{3})\s+(\d{4})(?:\s+(\d{1,2}):(\d{2}))?"
)


def scrape() -> list[Corrida]:
    try:
        resp = get(CALENDAR_URL)
        resp.raise_for_status()
    except Exception as e:
        print(f"[{SOURCE_NAME}] erro ao buscar calendário: {e}")
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    cards = _parse_listing(soup)
    if not cards:
        print(f"[{SOURCE_NAME}] nenhum card encontrado na listagem")
        return []

    today = today_iso()
    now = now_iso()
    corridas: list[Corrida] = []

    # Fetch inscription links in parallel
    def _fetch_insc(slug: str) -> str | None:
        try:
            resp = get(f"{CALENDAR_URL}/{slug}")
            resp.raise_for_status()
            return _find_insc_link(BeautifulSoup(resp.text, "lxml"), slug)
        except Exception:
            return None

    with ThreadPoolExecutor(max_workers=6) as ex:
        futures = {ex.submit(_fetch_insc, card["slug"]): card for card in cards}
        for fut in as_completed(futures):
            card = futures[fut]
            insc_link = fut.result()

            data_evento = card["data_evento"]
            if not data_evento or data_evento < today:
                continue

            inscricoes_abertas = True if insc_link else None
            links_insc = [insc_link] if insc_link else []
            cidade, estado = card["cidade"], card["estado"]
            if not estado:
                _pais_geo, estado = _geo.resolve(cidade or titulo, "", "BR")
                pais = _pais_geo or "BR"
            else:
                pais = "BR"
            localizacao = f"{cidade}, {estado}" if cidade and estado else cidade or estado or ""
            titulo = card["titulo"]

            fonte = FonteInfo(
                nome=SOURCE_NAME,
                link_evento=f"{CALENDAR_URL}/{card['slug']}",
                links_inscricao=links_insc,
            )

            corridas.append(Corrida(
                id=f"{slugify(titulo)}_{estado.lower()}_{today}",
                titulo=titulo,
                data_evento=data_evento,
                horario=card["horario"],
                localizacao=localizacao,
                cidade=cidade,
                estado=estado,
                pais=pais,
                distancias=card["distancias"],
                imagem_url=card["imagem_url"],
                inscricoes_abertas=inscricoes_abertas,
                periodo_inscricao=None,
                fontes=[fonte],
                miss_count=0,
                first_seen_at=now,
                updated_at=now,
            ))

    print(f"[{SOURCE_NAME}] {len(corridas)} corridas encontradas")
    return corridas


# ---------------------------------------------------------------------------
# Listing page parser
# ---------------------------------------------------------------------------

def _parse_listing(soup: BeautifulSoup) -> list[dict]:
    cards = []
    seen_slugs: set[str] = set()

    for h3 in soup.find_all("h3"):
        titulo = normalize_titulo(h3.get_text(strip=True))
        if not titulo or len(titulo) < 3:
            continue

        container = h3.parent
        if not container:
            continue

        texts = [el.get_text(" ", strip=True) for el in container.find_all(["p", "span"])]
        all_text = " ".join(texts)

        data_evento, horario = _parse_date(texts)
        cidade, estado = _parse_location(texts)
        distancias = _parse_distances(all_text)

        # Event slug from first link in the container
        slug = None
        for a in container.find_all("a", href=True):
            href = a["href"]
            if "/blogs/calendario-corridas-de-rua/" in href:
                slug = href.rstrip("/").split("/")[-1]
                break
        if not slug or slug in seen_slugs:
            continue
        seen_slugs.add(slug)

        # Image: og:image not available per-card; skip for now (fetched later if needed)
        img = container.find("img")
        imagem_url = None
        if img:
            src = img.get("src") or img.get("data-src") or ""
            imagem_url = src if src.startswith("http") else (BASE + src if src.startswith("/") else None)

        cards.append({
            "titulo": titulo,
            "slug": slug,
            "data_evento": data_evento,
            "horario": horario,
            "cidade": cidade,
            "estado": estado,
            "distancias": distancias,
            "imagem_url": imagem_url,
        })

    return cards


def _parse_date(texts: list[str]) -> tuple[str, str | None]:
    """Find 'DD Mmm YYYY HH:MM' in card texts."""
    for t in texts:
        m = _DATE_RE.search(t)
        if not m:
            continue
        mo = _PT_MONTHS.get(m.group(2).lower()[:3])
        if not mo:
            continue
        iso = f"{m.group(3)}-{mo}-{m.group(1).zfill(2)}"
        horario = f"{int(m.group(4)):02d}:{m.group(5)}" if m.group(4) else None
        return iso, horario
    return "", None


def _parse_location(texts: list[str]) -> tuple[str, str]:
    """Extract city and state from 'City | ST | ...' pattern."""
    for t in texts:
        if "|" not in t:
            continue
        parts = [s.strip() for s in t.split("|")]
        if len(parts) >= 2 and len(parts[1]) == 2 and parts[1].isupper():
            return parts[0].strip(), parts[1].strip()
    return "", ""


def _parse_distances(text: str) -> list[Distancia]:
    clean = _INTERVAL_RE.sub(" ", text)
    seen: set[float] = set()
    result: list[Distancia] = []
    for n in re.findall(r"\b(\d+(?:[.,]\d+)?)\s*[Kk]\b", clean):
        km = float(n.replace(",", "."))
        for canon, lo, hi in _CANONICAL:
            if lo <= km <= hi:
                km = canon
                break
        if km not in seen and 3 <= km <= 200:
            seen.add(km)
            result.append(Distancia(km=km, data=None, horario=None))
    return sorted(result, key=lambda d: d.km)


def _find_insc_link(soup: BeautifulSoup, slug: str) -> str | None:
    """Return inscription URL if an 'INSCREVA-SE' button exists."""
    products_path = f"/products/{slug}"
    for a in soup.find_all("a", href=True):
        href = a["href"]
        text = a.get_text(strip=True).lower()
        if "inscreva" in text or "inscrição" in text or "inscricao" in text:
            if "/products/" in href:
                return href if href.startswith("http") else BASE + href
        if products_path in href:
            return href if href.startswith("http") else BASE + href
    return None
