"""Scraper for ticketsports.com.br — Playwright (SPA)"""
from __future__ import annotations
import re

from ..models import Corrida, Distancia, FonteInfo, Inscricao
from ..utils import (
    normalize_date, normalize_time, normalize_titulo, normalize_valor,
    slugify, infer_estado, is_bsb_event, now_iso, today_iso
)

URL = "https://www.ticketsports.com.br/"
BASE = "https://www.ticketsports.com.br"
SOURCE_NAME = "Ticket Sports"

_MARATONAS_ALVO = [
    "maratona de sao paulo", "maratona do rio", "maratona de porto alegre",
    "maratona de florianopolis", "maratona de curitiba", "maratona de belo horizonte",
    "maratona de fortaleza", "maratona de salvador", "maratona de recife",
    "maratona de manaus", "maratona caixa", "maratona de brasilia",
]


def scrape() -> list[Corrida]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(f"[{SOURCE_NAME}] playwright não instalado")
        return []

    corridas: list[Corrida] = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.set_extra_http_headers({
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                )
            })

            # Search for corridas in DF
            search_url = f"{BASE}/sport/corrida-de-rua"
            page.goto(search_url, timeout=30000)
            page.wait_for_load_state("networkidle", timeout=30000)

            from bs4 import BeautifulSoup
            soup = BeautifulSoup(page.content(), "lxml")
            browser.close()

            for el in _find_events(soup):
                try:
                    corrida = _parse_event(el)
                    if not corrida:
                        continue
                    titulo_lower = corrida.titulo.lower()
                    if is_bsb_event(corrida.localizacao, corrida.titulo) or \
                       any(m in titulo_lower for m in _MARATONAS_ALVO):
                        corridas.append(corrida)
                except Exception as e:
                    print(f"[{SOURCE_NAME}] erro: {e}")
    except Exception as e:
        print(f"[{SOURCE_NAME}] erro playwright: {e}")

    print(f"[{SOURCE_NAME}] {len(corridas)} corridas encontradas")
    return corridas


def _find_events(soup):
    for sel in [".event-card", ".race-card", ".card", "article", ".event", ".item"]:
        els = soup.select(sel)
        if len(els) > 1:
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

    link_tag = el.find("a", href=True)
    link = link_tag["href"] if link_tag else URL
    if link.startswith("/"):
        link = BASE + link

    inscricoes = _extract_inscricoes(el, BASE)
    inscricoes_abertas: bool | None = any(i.disponivel for i in inscricoes) if inscricoes else None

    now = now_iso()
    today = today_iso()

    fonte = FonteInfo(
        nome=SOURCE_NAME,
        link_evento=link,
        links_inscricao=[i.link for i in inscricoes if i.link],
        inscricoes=inscricoes,
    )

    return Corrida(
        id=f"{slugify(titulo)}_{estado.lower()}_{today}",
        titulo=titulo,
        data_evento=data or "",
        horario=normalize_time(text),
        localizacao=localizacao,
        cidade=cidade,
        estado=estado,
        distancias=_extract_distances(text),
        imagem_url=imagem_url,
        inscricoes_abertas=inscricoes_abertas,
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


def _extract_inscricoes(el, base: str) -> list[Inscricao]:
    result = []
    for btn in el.find_all("a", href=True):
        text = btn.get_text(strip=True)
        href = btn["href"]
        if href.startswith("/"):
            href = base + href
        valor_match = re.search(r"R\$\s*[\d.,]+", text)
        valor = normalize_valor(valor_match.group(0)) if valor_match else None
        if any(k in text.lower() for k in ["inscri", "comprar", "r$"]):
            result.append(Inscricao(
                descricao=text or "Inscrição",
                valor=valor,
                disponivel=True,
                link=href,
            ))
    return result
