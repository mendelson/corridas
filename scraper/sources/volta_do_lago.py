"""Scraper for Corrida da Volta do Lago Paranoá — Brasília, DF

Site oficial: voltadolago.com.br
Evento anual em Brasília, percurso ao redor do Lago Paranoá.
"""
from __future__ import annotations
import json
import re
from datetime import date

from bs4 import BeautifulSoup

from ..http_client import get
from ..models import Corrida, Distancia, FonteInfo
from ..utils import (
    normalize_date, normalize_titulo, normalize_time, slugify, now_iso, today_iso,
)

BASE        = "https://voltadolago.com.br"
SOURCE_NAME = "Volta do Lago"

_OPEN_KW   = ["inscrições abertas", "inscreva-se", "inscrição", "inscrições",
               "garantir vaga", "clique aqui", "cadastre-se", "inscricoes abertas",
               "aberto", "aberta", "participe"]
_CLOSED_KW = ["inscrições encerradas", "esgotado", "encerrado", "encerrada",
               "vagas esgotadas", "inscricoes encerradas"]

_PAGES = [
    BASE + "/",
    BASE + "/corrida/",
    BASE + "/corrida-de-rua/",
    BASE + "/inscricao/",
    BASE + f"/{date.today().year}/",
    BASE + f"/corrida-{date.today().year}/",
    BASE + f"/volta-{date.today().year}/",
]


def scrape() -> list[Corrida]:
    soup = None
    final_url = BASE + "/"
    for url in _PAGES:
        try:
            resp = get(url, source=SOURCE_NAME, render_js=True, timeout=30)
            if resp.status_code == 200 and len(resp.text) > 500:
                soup = BeautifulSoup(resp.text, "lxml")
                final_url = url
                break
        except Exception:
            continue

    if soup is None:
        print(f"[{SOURCE_NAME}] site inacessível, sem dados para retornar")
        return []

    text_full = soup.get_text(" ", strip=True)

    # ── Try __NEXT_DATA__ (Next.js) ──────────────────────────────────────────
    result = _try_next_data(soup, final_url)
    if result:
        print(f"[{SOURCE_NAME}] 1 corrida encontrada via __NEXT_DATA__")
        return result

    # ── Try standard HTML extraction ─────────────────────────────────────────
    result = _try_html(soup, text_full, final_url)
    if result:
        print(f"[{SOURCE_NAME}] 1 corrida encontrada via HTML")
        return result

    print(f"[{SOURCE_NAME}] site acessível mas sem dados reconhecíveis")
    return []


# ---------------------------------------------------------------------------
# Next.js strategy
# ---------------------------------------------------------------------------
def _try_next_data(soup, page_url: str) -> list[Corrida] | None:
    tag = soup.find("script", id="__NEXT_DATA__")
    if not tag:
        return None
    try:
        data = json.loads(tag.string or "")
    except Exception:
        return None

    text = json.dumps(data, ensure_ascii=False)
    data_evento = _extract_date_from_str(text)
    if not data_evento:
        return None

    titulo_raw = (
        _jget(data, "pageProps", "event", "name")
        or _jget(data, "pageProps", "titulo")
        or _jget(data, "pageProps", "title")
        or "Corrida da Volta do Lago"
    )
    titulo = normalize_titulo(titulo_raw)

    distancias = _extract_distances_from_str(text)
    if not distancias:
        distancias = _guess_distances(titulo)

    link = _find_insc_link(soup) or page_url

    return [_build(titulo, data_evento, distancias, link, None)]


# ---------------------------------------------------------------------------
# HTML strategy
# ---------------------------------------------------------------------------
def _try_html(soup, text_full: str, page_url: str) -> list[Corrida] | None:
    data_evento = _extract_date_from_str(text_full)
    if not data_evento:
        return None

    titulo = _extract_titulo(soup) or "Corrida da Volta do Lago"
    distancias = _extract_distances_from_str(text_full)
    if not distancias:
        distancias = _guess_distances(titulo)

    horario_str = normalize_time(text_full)
    imagem_url = _extract_image(soup)
    link = _find_insc_link(soup) or page_url

    return [_build(titulo, data_evento, distancias, link, imagem_url, horario_str)]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
_PT_MONTHS = {
    "jan": "01", "fev": "02", "mar": "03", "abr": "04",
    "mai": "05", "jun": "06", "jul": "07", "ago": "08",
    "set": "09", "out": "10", "nov": "11", "dez": "12",
    "janeiro": "01", "fevereiro": "02", "março": "03", "marco": "03",
    "abril": "04", "maio": "05", "junho": "06", "julho": "07",
    "agosto": "08", "setembro": "09", "outubro": "10",
    "novembro": "11", "dezembro": "12",
}

_YEAR_RE  = re.compile(r"\b(202\d|203\d)\b")
_DATE_RE1 = re.compile(r"\b(\d{1,2})[/.\-](\d{1,2})[/.\-](202\d|203\d)\b")
_DATE_RE2 = re.compile(
    r"\b(\d{1,2})\s+de\s+([a-záéíóúãõâêô]+)\s+de\s+(202\d|203\d)\b",
    re.IGNORECASE,
)
_DATE_RE3 = re.compile(
    r"\b(\d{1,2})\s+([a-záéíóúãõâêô]{3,})\s+(202\d|203\d)\b",
    re.IGNORECASE,
)
_DIST_RE  = re.compile(r"\b(\d+(?:[.,]\d+)?)\s*km?\b", re.IGNORECASE)
_INSC_RE  = re.compile(
    r"href=[\"'](https?://[^\"']*(?:sympla|ticketsports|ticket\.com\.br"
    r"|minhasinscricoes|even3|ativo\.com|inscricao|inscreva)[^\"']*)[\"']",
    re.IGNORECASE,
)


def _extract_date_from_str(text: str) -> str | None:
    m = _DATE_RE1.search(text)
    if m:
        d, mo, y = m.group(1).zfill(2), m.group(2).zfill(2), m.group(3)
        return f"{y}-{mo}-{d}"
    m = _DATE_RE2.search(text)
    if m:
        mo = _PT_MONTHS.get(m.group(2).lower())
        if mo:
            return f"{m.group(3)}-{mo}-{m.group(1).zfill(2)}"
    m = _DATE_RE3.search(text)
    if m:
        mo = _PT_MONTHS.get(m.group(2).lower()[:3])
        if mo:
            return f"{m.group(3)}-{mo}-{m.group(1).zfill(2)}"
    return None


def _extract_distances_from_str(text: str) -> list[Distancia]:
    seen: set[float] = set()
    result: list[Distancia] = []
    # "meia maratona" / "half marathon"
    if re.search(r"meia\s+maratona|half\s+marathon", text, re.IGNORECASE):
        seen.add(21.097); result.append(Distancia(km=21.097, data=None, horario=None))
    if re.search(r"(?<!meia\s)\bmaratona\b|(?<!half\s)\bmarathon\b", text, re.IGNORECASE):
        if 42.195 not in seen:
            seen.add(42.195); result.append(Distancia(km=42.195, data=None, horario=None))
    for m in _DIST_RE.finditer(text):
        km = float(m.group(1).replace(",", "."))
        if 3 <= km <= 100 and km not in seen:
            seen.add(km); result.append(Distancia(km=km, data=None, horario=None))
    return sorted(result, key=lambda d: float(d.km) if isinstance(d.km, (int, float)) else 999)


def _guess_distances(titulo: str) -> list[Distancia]:
    """Last-resort fallback: infer distances from title keywords."""
    t = titulo.lower()
    if "meia" in t:
        return [Distancia(km=21.097, data=None, horario=None)]
    if "maratona" in t:
        return [Distancia(km=42.195, data=None, horario=None)]
    # Default: 5km + 10km (typical Brasília recreational race)
    return [
        Distancia(km=5.0,  data=None, horario=None),
        Distancia(km=10.0, data=None, horario=None),
    ]


def _extract_titulo(soup) -> str | None:
    for sel in ["h1", "h2", ".event-title", ".titulo", ".title", "title"]:
        tag = soup.select_one(sel)
        if tag:
            t = normalize_titulo(tag.get_text(strip=True))
            if t and len(t) > 4:
                return t
    return None


def _extract_image(soup) -> str | None:
    for sel in ["meta[property='og:image']", "meta[name='twitter:image']"]:
        tag = soup.select_one(sel)
        if tag and tag.get("content"):
            return tag["content"]
    for img in soup.find_all("img", src=True):
        src = img["src"]
        if re.search(r"\.(jpg|jpeg|png|webp)", src, re.IGNORECASE):
            if not re.search(r"logo|icon|sponsor|pixel|favicon", src, re.IGNORECASE):
                return src if src.startswith("http") else BASE + src
    return None


def _find_insc_link(soup) -> str | None:
    html = str(soup)
    m = _INSC_RE.search(html)
    if m:
        return m.group(1)
    # Fallback: any <a> with "inscrição" or "inscreva" text
    for a in soup.find_all("a", href=True):
        txt = a.get_text(" ", strip=True).lower()
        if any(k in txt for k in ("inscrição", "inscreva", "inscrever", "participe")):
            href = a["href"]
            return href if href.startswith("http") else BASE + href
    return None


def _jget(obj, *keys):
    for k in keys:
        if not isinstance(obj, dict):
            return None
        obj = obj.get(k)
    return obj if isinstance(obj, str) else None


def _build(
    titulo: str,
    data_evento: str,
    distancias: list[Distancia],
    link: str,
    imagem_url: str | None,
    horario: str | None = None,
) -> Corrida:
    now   = now_iso()
    return Corrida(
        id=f"volta-do-lago_df_{data_evento[:4]}",
        titulo=titulo,
        data_evento=data_evento,
        horario=horario,
        localizacao="Brasília, DF",
        cidade="Brasília",
        estado="DF",
        distancias=distancias,
        imagem_url=imagem_url,
        inscricoes_abertas=None,
        periodo_inscricao=None,
        fontes=[FonteInfo(
            nome=SOURCE_NAME,
            link_evento=link,
            links_inscricao=[link],
        )],
        miss_count=0,
        first_seen_at=now,
        updated_at=now,
    )
