"""Scraper for corridasbrasil.com.br/calendario/"""
from __future__ import annotations
import re
from bs4 import BeautifulSoup

from ..http_client import get
from ..models import Corrida, Distancia, FonteInfo
from ..utils import (
    normalize_date, normalize_time, normalize_titulo,
    slugify, infer_estado, now_iso, today_iso,
    validate_image_url,
)

URL = "https://corridasbrasil.com.br/calendario/"
BASE = "https://corridasbrasil.com.br"
SOURCE_NAME = "Corridas Brasil"


def scrape() -> list[Corrida]:
    try:
        resp = get(URL)
        resp.raise_for_status()
    except Exception as e:
        print(f"[{SOURCE_NAME}] erro: {e}")
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    corridas: list[Corrida] = []

    for el in _find_events(soup):
        try:
            corrida = _parse_event(el)
            if corrida:
                corridas.append(corrida)
        except Exception as e:
            print(f"[{SOURCE_NAME}] erro: {e}")

    print(f"[{SOURCE_NAME}] {len(corridas)} corridas encontradas")
    return corridas


def _find_events(soup):
    for sel in [".event", ".race", ".card", "article", ".item", ".post", "tr"]:
        els = soup.select(sel)
        if len(els) > 2:
            return els
    return []


def _parse_event(el) -> Corrida | None:
    text = el.get_text(" ", strip=True)
    if not text or len(text) < 5:
        return None

    heading = el.find(["h1", "h2", "h3", "h4", "strong"])
    titulo_raw = heading.get_text(strip=True) if heading else text[:80]
    titulo = normalize_titulo(titulo_raw)
    if not titulo or len(titulo) < 3:
        return None

    data = _extract_date(text)
    localizacao = _extract_localizacao(el, text)
    estado = infer_estado(localizacao, titulo) or "??"
    cidade = localizacao.split(",")[0].strip()

    img = el.find("img")
    imagem_url = (img.get("src") or img.get("data-src")) if img else None
    if imagem_url and imagem_url.startswith("/"):
        imagem_url = BASE + imagem_url
    imagem_url = validate_image_url(imagem_url)

    link_tag = el.find("a", href=True)
    link = link_tag["href"] if link_tag else URL
    if link.startswith("/"):
        link = BASE + link

    now = now_iso()
    today = today_iso()

    fonte = FonteInfo(nome=SOURCE_NAME, link_evento=link, links_inscricao=[])
    return Corrida(
        id=f"{slugify(titulo)}_{estado.lower()}_{today}",
        titulo=titulo,
        data_evento=data or "",
        horario=normalize_time(text),
        localizacao=localizacao,
        cidade=cidade,
        estado=estado,
        pais="BR",
        distancias=_extract_distances(text),
        imagem_url=imagem_url,
        inscricoes_abertas=None,
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
    return None


def _extract_localizacao(el, text: str) -> str:
    for cls in ["local", "location", "cidade", "place"]:
        loc = el.find(class_=re.compile(cls, re.IGNORECASE))
        if loc:
            val = loc.get_text(strip=True)
            if val:
                return val
    m = re.search(r"([A-Z][a-záéíóúãõâêô]+(?:\s[A-Z][a-záéíóúãõâêô]+)*)\s*[-–]\s*([A-Z]{2})", text)
    if m:
        return m.group(0)
    return ""


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
