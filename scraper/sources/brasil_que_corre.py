"""Scraper for brasilquecorre.com/distritofederal"""
from __future__ import annotations
import re
from bs4 import BeautifulSoup

from ..http_client import get
from ..models import Corrida, Distancia, FonteInfo
from ..utils import (
    normalize_date, normalize_time, normalize_titulo, slugify,
    infer_estado, now_iso, today_iso
)

URL = "https://brasilquecorre.com/distritofederal"
SOURCE_NAME = "Brasil que Corre"


def scrape() -> list[Corrida]:
    try:
        resp = get(URL)
        resp.raise_for_status()
    except Exception as e:
        print(f"[{SOURCE_NAME}] erro ao buscar {URL}: {e}")
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    corridas: list[Corrida] = []

    # Common patterns for race calendar sites
    selectors = [
        "article.event", "div.event", ".race-item", ".corrida",
        "article", ".entry", ".post",
    ]
    events = []
    for sel in selectors:
        events = soup.select(sel)
        if events:
            break

    if not events:
        events = soup.find_all("article")

    for el in events:
        try:
            corrida = _parse_event(el)
            if corrida:
                corridas.append(corrida)
        except Exception as e:
            print(f"[{SOURCE_NAME}] erro ao parsear evento: {e}")

    print(f"[{SOURCE_NAME}] {len(corridas)} corridas encontradas")
    return corridas


def _parse_event(el) -> Corrida | None:
    text = el.get_text(" ", strip=True)
    if not text or len(text) < 10:
        return None

    heading = el.find(["h1", "h2", "h3", "h4", "strong", "b"])
    titulo_raw = heading.get_text(strip=True) if heading else None
    if not titulo_raw:
        link_tag = el.find("a")
        titulo_raw = link_tag.get_text(strip=True) if link_tag else text[:80]
    titulo = normalize_titulo(titulo_raw or "")
    if not titulo or len(titulo) < 3:
        return None

    data = _extract_date(text)
    localizacao = _extract_localizacao(el, text)
    estado = infer_estado(localizacao, titulo) or "DF"

    img = el.find("img")
    imagem_url = img.get("src") or img.get("data-src") if img else None
    if imagem_url and imagem_url.startswith("/"):
        imagem_url = "https://brasilquecorre.com" + imagem_url

    link_tag = el.find("a", href=True)
    link = link_tag["href"] if link_tag else URL
    if link.startswith("/"):
        link = "https://brasilquecorre.com" + link

    distancias = _extract_distances(text)

    now = now_iso()
    today = today_iso()
    cidade = "Brasília" if estado == "DF" else localizacao.split(",")[0].strip()

    has_link = link != URL
    fonte = FonteInfo(
        nome=SOURCE_NAME,
        link_evento=link,
        links_inscricao=[link] if has_link else [],
    )

    return Corrida(
        id=f"{slugify(titulo)}_{estado.lower()}_{today}",
        titulo=titulo,
        data_evento=data or "",
        horario=normalize_time(text),
        localizacao=localizacao,
        cidade=cidade,
        estado=estado,
        distancias=distancias,
        imagem_url=imagem_url,
        inscricoes_abertas=True if has_link else None,
        periodo_inscricao=None,
        fontes=[fonte],
        miss_count=0,
        first_seen_at=now,
        updated_at=now,
    )


def _extract_date(text: str) -> str | None:
    m = re.search(r"\d{1,2}/\d{1,2}/\d{4}", text)
    if m:
        return normalize_date(m.group(0))
    m = re.search(r"\d{1,2}\s+de\s+\w+\s+de\s+\d{4}", text, re.IGNORECASE)
    if m:
        return normalize_date(m.group(0))
    # ISO in text
    m = re.search(r"\d{4}-\d{2}-\d{2}", text)
    if m:
        return m.group(0)
    return None


def _extract_localizacao(el, text: str) -> str:
    # Look for address-like element
    for cls in ["location", "local", "endereco", "place", "cidade"]:
        loc_el = el.find(class_=re.compile(cls, re.IGNORECASE))
        if loc_el:
            loc = loc_el.get_text(strip=True)
            if loc:
                return loc
    # Fallback: search text for known city patterns
    if re.search(r"bras[ií]lia|distrito federal|\bDF\b", text, re.IGNORECASE):
        return "Brasília-DF"
    return "Brasília-DF"


def _extract_distances(text: str) -> list[Distancia]:
    nums = re.findall(r"\b(\d+)\s*[kK][mM]?\b", text)
    seen: set[float] = set()
    result = []
    for n in nums:
        km = float(n)
        if km not in seen and 1 <= km <= 200:
            seen.add(km)
            result.append(Distancia(km=km, data=None, horario=None))
    return result
