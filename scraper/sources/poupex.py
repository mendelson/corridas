"""Scraper for corrida.poupex.com.br

Official site for the Corrida POUPEX, an annual road race held in Brasília (DF),
typically in late July at 18h00. The site is a static WordPress theme — all
key facts are available without JavaScript:

  og:description → date ("25 de julho de 2026"), time ("às 18 horas"),
                   city/state ("Brasília (DF)")
  page body      → distance badges "5km / CORRIDA", "10km / CORRIDA"
  INSCREVA-SE link → Ativo.com registration page
  og:image       → event banner
"""
from __future__ import annotations
import re
from datetime import date

from bs4 import BeautifulSoup

from ..http_client import get
from ..models import Corrida, Distancia, FonteInfo
from ..utils import now_iso, today_iso

SITE_URL = "https://corrida.poupex.com.br/"
SOURCE_NAME = "Corrida POUPEX"

_CANONICAL = [(42.195, 41.5, 43.0), (21.097, 20.5, 21.5)]

_MONTHS = {
    "janeiro": 1, "jan": 1,  "fevereiro": 2, "fev": 2,
    "março": 3, "marco": 3, "mar": 3,
    "abril": 4, "abr": 4,  "maio": 5, "mai": 5,
    "junho": 6, "jun": 6,  "julho": 7, "jul": 7,
    "agosto": 8, "ago": 8, "setembro": 9, "set": 9,
    "outubro": 10, "out": 10, "novembro": 11, "nov": 11,
    "dezembro": 12, "dez": 12,
}

_DATE_RE = re.compile(
    r"\b(\d{1,2})\s+de\s+([A-Za-zçãéíóú]+)\s+de\s+(\d{4})\b",
    re.IGNORECASE,
)

# Keyword-anchored time: "às 18 horas", "às 18h", "às 18h30", "largada: 18:00"
_TIME_RE = re.compile(
    r"(?:às?|sa[íi]da|largada|in[íi]cio|partida|hor[áa]rio|hora)\s*:?\s*"
    r"(\d{1,2})[hH:]([0-5]\d)"
    r"|(?:às?|sa[íi]da|largada|in[íi]cio|partida|hor[áa]rio|hora)\s*:?\s*"
    r"(\d{1,2})\s*[hH](?:oras?)?\b(?!\d)",
    re.IGNORECASE,
)

_KM_RE = re.compile(r"\b(\d+(?:[.,]\d+)?)\s*[kK][mM]\b")


def _fetch_html() -> str | None:
    """Fetch SITE_URL via proxy chain, falling back to Playwright."""
    html_text: str | None = None
    try:
        resp = get(SITE_URL)
        resp.raise_for_status()
        html_text = resp.text
    except Exception as e:
        print(f"[{SOURCE_NAME}] proxy chain falhou: {e}; tentando Playwright...")

    # Also try Playwright when proxy chain returned HTML without expected meta tags
    if html_text:
        soup_check = BeautifulSoup(html_text, "lxml")
        og = soup_check.find("meta", attrs={"property": "og:description"})
        if not og or not og.get("content"):
            print(f"[{SOURCE_NAME}] og:description ausente na resposta; tentando Playwright...")
            html_text = None

    if not html_text:
        try:
            from ..playwright_client import get_page_html
            html_text = get_page_html(SITE_URL, timeout=30_000)
            if html_text:
                print(f"[{SOURCE_NAME}] Playwright ok")
        except Exception as e2:
            print(f"[{SOURCE_NAME}] Playwright falhou: {e2}")

    return html_text


def scrape() -> list[Corrida]:
    html_text = _fetch_html()
    if not html_text:
        print(f"[{SOURCE_NAME}] todos os métodos falharam")
        return []

    soup = BeautifulSoup(html_text, "lxml")

    og_desc = _meta(soup, "og:description") or ""
    og_image = _meta(soup, "og:image") or None
    full_text = og_desc + " " + soup.get_text(" ", strip=True)

    # Date from og:description (most reliable)
    m = _DATE_RE.search(og_desc)
    if not m:
        print(f"[{SOURCE_NAME}] data não encontrada em og:description")
        return []
    day, month_name, year_str = m.groups()
    month = _MONTHS.get(month_name.lower().strip("."))
    if not month:
        print(f"[{SOURCE_NAME}] mês desconhecido: {month_name!r}")
        return []
    year = int(year_str)
    data_evento = f"{year:04d}-{month:02d}-{int(day):02d}"
    if data_evento < today_iso():
        print(f"[{SOURCE_NAME}] evento já passou ({data_evento})")
        return []

    # Time: try og:description first, then full page, then broad fallback
    horario = _extract_horario(og_desc) or _extract_horario(full_text)
    if horario is None:
        horario = _extract_horario_broad(full_text)
    if horario is None:
        print(f"[{SOURCE_NAME}] horário não encontrado")
        return []

    # Distances from page content (badges like "5km CORRIDA", "10km CORRIDA")
    distancias = _extract_distances(full_text)
    if not distancias:
        print(f"[{SOURCE_NAME}] distâncias não encontradas")
        return []

    # Registration link: INSCREVA-SE / Inscrições button pointing off-site
    inscricao_url: str | None = None
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        txt = a.get_text(strip=True).lower()
        if (
            href.startswith("http")
            and href.rstrip("/") != SITE_URL.rstrip("/")
            and any(k in txt for k in ["inscrev", "inscri", "comprar", "registr"])
        ):
            inscricao_url = href
            break

    link = inscricao_url or SITE_URL
    now = now_iso()

    fonte = FonteInfo(
        nome=SOURCE_NAME,
        link_evento=SITE_URL,
        links_inscricao=[link],
        tipo="organizador",
    )

    corrida = Corrida(
        id=f"poupex-brasilia-df-{year}",
        titulo=f"Corrida POUPEX {year}",
        data_evento=data_evento,
        horario=horario,
        localizacao="Brasília, DF",
        cidade="Brasília",
        estado="DF",
        pais="BR",
        distancias=distancias,
        imagem_url=og_image,
        inscricoes_abertas=True if inscricao_url else None,
        periodo_inscricao=None,
        fontes=[fonte],
        miss_count=0,
        first_seen_at=now,
        updated_at=now,
    )
    print(f"[{SOURCE_NAME}] {data_evento} {horario} — {', '.join(str(d.km) for d in distancias)}")
    return [corrida]


def _meta(soup, property_name: str) -> str | None:
    tag = soup.find("meta", attrs={"property": property_name})
    if tag and tag.get("content"):
        return tag["content"].strip()
    return None


def _extract_horario_broad(text: str) -> str | None:
    """Fallback: any HH:MM or HHhMM in 04:00–23:59 range, no keyword required."""
    for m in re.finditer(r"\b(\d{1,2})[hH:]([0-5]\d)\b", text):
        h, mi = int(m.group(1)), int(m.group(2))
        if 4 <= h <= 23:
            return f"{h:02d}:{mi:02d}"
    return None


def _extract_horario(text: str) -> str | None:
    if not text:
        return None
    m = _TIME_RE.search(text)
    if not m:
        return None
    if m.group(1) is not None:
        h, mi = int(m.group(1)), int(m.group(2))
    else:
        h, mi = int(m.group(3)), 0
    if 4 <= h <= 23:
        return f"{h:02d}:{mi:02d}"
    return None


def _extract_distances(text: str) -> list[Distancia]:
    seen: list[float] = []
    for m in _KM_RE.finditer(text):
        try:
            raw = float(m.group(1).replace(",", "."))
        except ValueError:
            continue
        if raw < 1 or raw > 200:
            continue
        km = raw
        for canon, lo, hi in _CANONICAL:
            if lo <= raw <= hi:
                km = canon
                break
        if any(abs(km - s) < 0.5 for s in seen):
            continue
        seen.append(km)
    return sorted(
        [Distancia(km=k, data=None, horario=None) for k in seen],
        key=lambda d: float(d.km),
    )
