"""Scraper for runnerbrasil.com.br

The homepage lists upcoming events as <article class="caixa3"> cards, each
linking to a detail page (Runner_CalendarioDetalhe.aspx?idEvento=<id>). The
cards themselves carry only "DD/MM - City", so we follow each link and parse
the detail page, which exposes structured spans:

    Main_label_Nome       → event title
    Main_label_Dt_Evento  → "Data: DD/MM/YYYY" (may include time as "07h00")
    Main_label_Percurso   → "Percurso: 5 / 10 / 21 km"
    Main_label_Local      → "Local: City - UF"

Start time is NOT always on the detail page itself — many events only list the
time on the linked external inscription platform (Ticket Sports, Atletis, etc.)
or on the race's own website.  We follow those links to find the time.
Events within the next 3 months without a published start time are skipped;
further-out events are kept (horário is filled in as they approach).
"""
from __future__ import annotations
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date

from bs4 import BeautifulSoup

from ..http_client import get
from ..models import Corrida, Distancia, FonteInfo
from ..utils import (
    normalize_date, normalize_titulo, now_iso, today_iso, horario_required,
)
from .. import geo as _geo

URL = "https://www.runnerbrasil.com.br/"
BASE = "https://www.runnerbrasil.com.br"
SOURCE_NAME = "Runner Brasil"

_CANONICAL = [(42.195, 41.5, 43.0), (21.097, 20.5, 21.5)]

# Domains of known inscription/registration platforms that typically show start times
_INSC_DOMAINS = (
    "ticketsports.com.br", "ticket.com.br",
    "atletis.com.br", "sympla.com.br",
    "ativo.com", "minhasinscricoes.com.br",
    "portaldascorridas.com.br", "raceroster.com",
    "runsignup.com", "eventbrite.com", "yescom.com.br",
)


def scrape() -> list[Corrida]:
    try:
        resp = get(URL)
        resp.raise_for_status()
    except Exception as e:
        print(f"[{SOURCE_NAME}] erro: {e}")
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    detail_urls = _find_detail_urls(soup)
    print(f"[{SOURCE_NAME}] {len(detail_urls)} eventos no calendário")

    corridas: list[Corrida] = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = {ex.submit(_scrape_detail, url): url for url in detail_urls}
        for fut in as_completed(futures):
            url = futures[fut]
            try:
                corrida = fut.result()
                if corrida:
                    corridas.append(corrida)
            except Exception as e:
                print(f"[{SOURCE_NAME}] erro em {url}: {e}")

    print(f"[{SOURCE_NAME}] {len(corridas)} corridas encontradas")
    return corridas


def _find_detail_urls(soup) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()
    for a in soup.find_all("a", href=re.compile(r"CalendarioDetalhe\.aspx\?idEvento=", re.I)):
        href = a["href"]
        if href.startswith("/"):
            href = BASE + href
        if href not in seen:
            seen.add(href)
            urls.append(href)
    return urls


def _find_external_url(soup: BeautifulSoup) -> str | None:
    """Return the first external inscription-platform or race-website link."""
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not href.startswith("http"):
            continue
        if "runnerbrasil.com.br" in href:
            continue
        if any(domain in href for domain in _INSC_DOMAINS):
            return href
        text = a.get_text(strip=True).lower()
        if "inscri" in text or "registr" in text or "clique aqui" in text:
            return href
    return None


def _fetch_horario_from_url(url: str) -> str | None:
    """Fetch a page and try to extract a start time from its text."""
    try:
        resp = get(url, timeout=15)
        if resp.status_code != 200:
            return None
        text = BeautifulSoup(resp.text, "lxml").get_text(" ", strip=True)
        return _extract_horario(text)
    except Exception:
        return None


def _scrape_detail(url: str) -> Corrida | None:
    resp = get(url)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")

    titulo_raw = _label_text(soup, "Main_label_Nome")
    titulo = normalize_titulo(titulo_raw)
    if not titulo or len(titulo) < 3:
        return None

    data_raw = _label_text(soup, "Main_label_Dt_Evento")
    data = _extract_date(data_raw)
    if not data:
        return None
    if data < today_iso():
        return None

    # 1. Try the detail page itself (date field, dedicated spans, full text)
    horario = (
        _extract_horario(data_raw)
        or _extract_horario(_label_text(soup, "Main_label_Hr_Evento"))
        or _extract_horario(_label_text(soup, "Main_label_Horario"))
        or _extract_horario(_label_text(soup, "Main_label_Hora"))
        or _extract_horario(soup.get_text(" ", strip=True))
    )

    # 2. Follow the external inscription-platform link (Ticket Sports, Atletis…)
    insc_url = _find_external_url(soup) if horario is None else None
    if horario is None and insc_url:
        horario = _fetch_horario_from_url(insc_url)

    # 3. Try the race's own website (Main_label_Site)
    site_raw = _label_text(soup, "Main_label_Site").strip()
    site_url = (site_raw if site_raw.startswith("http") else "https://" + site_raw) if site_raw else None
    if horario is None and site_url:
        horario = _fetch_horario_from_url(site_url)

    # Horário is no longer mandatory (policy change 2026-07-11 —
    # horario_required() always returns False): events without a published
    # start time are kept. The deep-fetch extraction above still runs at full
    # effort, and the guard stays here so the strict 3-month policy can be
    # restored via utils.horario_required().
    if horario is None and horario_required(data):
        print(f"[{SOURCE_NAME}] sem horário (prova em até 3 meses), pulando: {titulo!r}")
        return None

    local_raw = _label_text(soup, "Main_label_Local")
    localizacao, cidade, estado = _parse_local(local_raw)

    percurso_raw = _label_text(soup, "Main_label_Percurso")
    distancias = _extract_distances(percurso_raw)
    if not distancias:
        print(f"[{SOURCE_NAME}] sem distâncias, pulando: {titulo!r}")
        return None

    # Prefer inscription URL → site URL → runner_brasil URL for links
    link_evento = url
    links_inscricao = [insc_url or site_url or url]

    m = re.search(r"idEvento=(\d+)", url)
    ev_id = f"runnerbrasil_{m.group(1)}" if m else f"runnerbrasil_{data}"

    now = now_iso()
    fonte = FonteInfo(
        nome=SOURCE_NAME,
        link_evento=link_evento,
        links_inscricao=links_inscricao,
        tipo="calendario",
    )
    return Corrida(
        id=ev_id,
        titulo=titulo,
        data_evento=data,
        horario=horario,
        localizacao=localizacao,
        cidade=cidade,
        estado=estado,
        pais="BR",
        distancias=distancias,
        imagem_url=None,
        inscricoes_abertas=None,
        periodo_inscricao=None,
        fontes=[fonte],
        miss_count=0,
        first_seen_at=now,
        updated_at=now,
    )


def _label_text(soup, span_id: str) -> str:
    el = soup.find(id=span_id)
    if not el:
        return ""
    text = el.get_text(" ", strip=True)
    return re.sub(r"^[^:]{1,15}:\s*", "", text).strip()


_HORARIO_RE = re.compile(
    r"\b(\d{1,2})[hH:]([0-5]\d)\s*(?:min\s*)?[hH]?\b(?!\s*[kK])"
    r"|\b(\d{1,2})\s*[hH]\b(?!\s*\d)",
    re.IGNORECASE,
)

_HORARIO_KW_RE = re.compile(
    r"(?:às?|sa[íi]da|largada|in[íi]cio|partida|hor[áa]rio|hora)\s*:?\s*"
    r"(\d{1,2})[hH:]([0-5]\d)"
    r"|(?:às?|sa[íi]da|largada|in[íi]cio|partida|hor[áa]rio|hora)\s*:?\s*"
    r"(\d{1,2})\s*[hH]\b(?!\d)",
    re.IGNORECASE,
)


def _extract_horario(text: str) -> str | None:
    if not text:
        return None
    for pattern in (_HORARIO_KW_RE, _HORARIO_RE):
        m = pattern.search(text)
        if not m:
            continue
        if m.group(1) is not None:
            h, mi = int(m.group(1)), int(m.group(2))
        elif m.lastindex and m.lastindex >= 3 and m.group(3) is not None:
            h, mi = int(m.group(3)), 0
        else:
            continue
        if 4 <= h <= 23 and 0 <= mi <= 59:
            return f"{h:02d}:{mi:02d}"
    return None


def _extract_date(text: str) -> str | None:
    m = re.search(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b", text)
    if m:
        return normalize_date(m.group(0))
    m = re.search(r"\b(\d{1,2})/(\d{1,2})(?!/\d)", text)
    if m:
        d, mo = int(m.group(1)), int(m.group(2))
        if 1 <= d <= 31 and 1 <= mo <= 12:
            yr = date.today().year
            candidate = f"{yr}-{mo:02d}-{d:02d}"
            if candidate < today_iso():
                candidate = f"{yr + 1}-{mo:02d}-{d:02d}"
            return candidate
    return None


def _parse_local(text: str) -> tuple[str, str, str]:
    """Parse 'Guarujá - SP' → ('Guarujá, SP', 'Guarujá', 'SP')."""
    text = text.strip()
    estado = ""
    cidade = text
    m = re.search(r"^(.*?)\s*[-–]\s*([A-Z]{2})\b", text)
    if m:
        cidade = m.group(1).strip()
        estado = m.group(2)
    if not estado:
        _pais_geo, _estado_geo = _geo.resolve(text or cidade, cidade, "BR")
        estado = _estado_geo or ""
    localizacao = f"{cidade}, {estado}" if estado else cidade
    return localizacao, cidade, estado


def _extract_distances(text: str) -> list[Distancia]:
    """Parse 'Percurso: 5 / 10 / 21 km' → [5, 10, 21.097]."""
    seen: set[float] = set()
    result: list[Distancia] = []
    for raw in re.findall(r"(\d+(?:[.,]\d+)?)", text):
        try:
            km = float(raw.replace(",", "."))
        except ValueError:
            continue
        if not (1 <= km <= 250):
            continue
        for canon, lo, hi in _CANONICAL:
            if lo <= km <= hi:
                km = canon
                break
        if km not in seen:
            seen.add(km)
            result.append(Distancia(km=km, data=None, horario=None))
    return result
