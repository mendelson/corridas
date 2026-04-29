"""Scraper for centraldacorrida.com.br"""
from __future__ import annotations
import re
from bs4 import BeautifulSoup

from ..http_client import get
from ..models import Corrida, Distancia, FonteInfo, Inscricao
from ..utils import (
    normalize_date, normalize_time, normalize_titulo, normalize_valor,
    slugify, infer_estado, is_bsb_event, now_iso, today_iso
)

BASE = "https://centraldacorrida.com.br"
URLS = [
    f"{BASE}/corridas/?estado=df",
    f"{BASE}/corridas/",
]
SOURCE_NAME = "Central da Corrida"

_MARATONAS_ALVO = [
    "maratona de sao paulo", "maratona do rio", "maratona de porto alegre",
    "maratona de florianopolis", "maratona de curitiba", "maratona de belo horizonte",
    "maratona de fortaleza", "maratona de salvador", "maratona de recife",
    "maratona de manaus", "maratona caixa", "maratona de brasilia",
]


def scrape() -> list[Corrida]:
    corridas: list[Corrida] = []
    seen_titles: set[str] = set()

    for url in URLS:
        try:
            resp = get(url)
            resp.raise_for_status()
        except Exception as e:
            print(f"[{SOURCE_NAME}] erro ao buscar {url}: {e}")
            continue

        soup = BeautifulSoup(resp.text, "lxml")
        for el in _find_events(soup):
            try:
                corrida = _parse_event(el, url)
                if not corrida:
                    continue
                titulo_lower = corrida.titulo.lower()
                is_target = (
                    is_bsb_event(corrida.localizacao, corrida.titulo)
                    or any(m in titulo_lower for m in _MARATONAS_ALVO)
                )
                if is_target and corrida.titulo not in seen_titles:
                    seen_titles.add(corrida.titulo)
                    corridas.append(corrida)
            except Exception as e:
                print(f"[{SOURCE_NAME}] erro ao parsear evento: {e}")

    print(f"[{SOURCE_NAME}] {len(corridas)} corridas encontradas")
    return corridas


def _find_events(soup):
    for sel in [".evento", ".race-card", ".card", "article", ".post", ".item"]:
        els = soup.select(sel)
        if els:
            return els
    return soup.find_all("li")


def _parse_event(el, page_url: str) -> Corrida | None:
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

    img = el.find("img")
    imagem_url = (img.get("src") or img.get("data-src")) if img else None
    if imagem_url and imagem_url.startswith("/"):
        imagem_url = BASE + imagem_url

    link_tag = el.find("a", href=True)
    link = link_tag["href"] if link_tag else page_url
    if link.startswith("/"):
        link = BASE + link

    distancias = _extract_distances(text)
    inscricoes = _extract_inscricoes(el)
    inscricoes_abertas: bool | None = None
    if inscricoes:
        inscricoes_abertas = any(i.disponivel for i in inscricoes)

    now = now_iso()
    today = today_iso()
    cidade = localizacao.split(",")[0].strip() if localizacao else ""

    fonte = FonteInfo(
        nome=SOURCE_NAME,
        link_evento=link,
        links_inscricao=_extract_links_inscricao(el, BASE),
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
        distancias=distancias,
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
    for cls in ["local", "location", "cidade", "place", "endereco"]:
        loc = el.find(class_=re.compile(cls, re.IGNORECASE))
        if loc:
            return loc.get_text(strip=True)
    m = re.search(r"(Brasília|São Paulo|Rio de Janeiro|Curitiba|Porto Alegre|[A-Z][a-z]+-[A-Z]{2})", text)
    if m:
        return m.group(1)
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


def _extract_inscricoes(el) -> list[Inscricao]:
    result = []
    for btn in el.find_all("a", href=True):
        btn_text = btn.get_text(strip=True).lower()
        if any(k in btn_text for k in ["inscri", "inscrever", "comprar", "valor"]):
            result.append(Inscricao(
                descricao=btn.get_text(strip=True),
                valor=None,
                disponivel=True,
                link=btn["href"],
            ))
    return result


def _extract_links_inscricao(el, base: str) -> list[str]:
    links = []
    for a in el.find_all("a", href=True):
        href = a["href"]
        text = a.get_text(strip=True).lower()
        if any(k in text for k in ["inscri", "inscrever", "comprar"]):
            if href.startswith("/"):
                href = base + href
            links.append(href)
    return links
