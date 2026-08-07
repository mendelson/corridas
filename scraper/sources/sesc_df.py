"""Scraper for sescdf.com.br/corridas — Liferay portal, DF-only events

The SESC DF running page is a Liferay portal. Each event card contains:

  <h3>                  → event title
  <i class="la-running"> → identifies this card as a running event
  <h5>DD/MM/YYYY …</h5> → event date
  <h6>…</h6>            → location (neighbourhood / park)
  <div class="card-text"> → free-text description with distances
  <a class="btn btn-secondary" href="…">Saiba Mais</a> → detail page URL

Horário is NOT listed on the event card — it must be fetched from the
"Saiba Mais" detail page.  Events without a published start time are
skipped (the detail page gets the time closer to the event date).


BLOCKED SINCE 2026-08-02 (disabled 2026-08-07) - F5 BIG-IP ASM, site-wide, and
the failure mode is the trap here: the WAF answers **HTTP 200** with a 246-byte
"The requested URL was rejected. Please consult with your administrator." page
carrying a support ID. Because the status is 200, http_client's WAF detection
(403/406/429) never fires, raise_for_status() passes, and the parser simply
finds no event cards - so the source reported a plain "0 corridas encontradas"
and looked exactly like the generic-selector parser bug the README warns about.
It is not one.

Measured across every path, /robots.txt and / included, so it is an edge block
on the client IP class rather than a moved page. Re-enable by uncommenting in
scraper/sources/__init__.py and scraper/main.py once a GET of
https://www.sescdf.com.br/robots.txt from CI returns something that is NOT the
rejection page - checking the status code alone will not tell you, since the
block is served as 200. Grep the body for "Request Rejected".
"""
from __future__ import annotations
import re
from bs4 import BeautifulSoup

from ..http_client import get
from ..models import Corrida, Distancia, FonteInfo
from ..utils import normalize_titulo, slugify, now_iso, today_iso, extract_distances_from_text
from .. import geo as _geo

URL = "https://www.sescdf.com.br/corridas"
BASE = "https://www.sescdf.com.br"
SOURCE_NAME = "SESC DF"

_CANONICAL = [(42.195, 41.5, 43.0), (21.097, 20.5, 21.5)]

_DATE_RE = re.compile(r"(\d{2})/(\d{2})/(\d{4})")

# Keyword-anchored: "às 7h30", "saída: 07:00", "largada: 8h", "horário: 08h30"
_TIME_KW_RE = re.compile(
    r"(?:às?|sa[íi]da|largada|in[íi]cio|partida|hor[áa]rio|hora)\s*:?\s*"
    r"(\d{1,2})[hH:]([0-5]\d)"
    r"|(?:às?|sa[íi]da|largada|in[íi]cio|partida|hor[áa]rio|hora)\s*:?\s*"
    r"(\d{1,2})\s*[hH](?:oras?)?\b(?!\d)",
    re.IGNORECASE,
)

# Generic fallback: "07h30", "07:30", "7h"
_TIME_RE = re.compile(
    r"\b(\d{1,2})[hH:]([0-5]\d)\s*(?:min\s*)?[hH]?\b(?!\s*[kK])"
    r"|\b(\d{1,2})\s*[hH]\b(?!\s*\d)",
    re.IGNORECASE,
)

_KM_RE = re.compile(r"\b(\d+(?:[.,]\d+)?)\s*[kK][mM]?\b")


def scrape() -> list[Corrida]:
    try:
        resp = get(URL)
        resp.raise_for_status()
    except Exception as e:
        print(f"[{SOURCE_NAME}] erro: {e}")
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    today = today_iso()
    now = now_iso()

    corridas: list[Corrida] = []
    seen_ids: set[str] = set()

    for card in _find_cards(soup):
        try:
            c = _parse_card(card, today, now)
        except Exception as e:
            print(f"[{SOURCE_NAME}] erro ao parsear card: {e}")
            continue
        if c and c.id not in seen_ids:
            seen_ids.add(c.id)
            corridas.append(c)

    print(f"[{SOURCE_NAME}] {len(corridas)} corridas encontradas")
    return corridas


def _find_cards(soup) -> list:
    """Return card containers that have a la-running icon."""
    cards = []
    seen_ids = set()
    for icon in soup.find_all("i", class_=lambda c: c and "la-running" in c):
        # Walk up to a container that has both a heading and a date
        container = icon.parent
        for _ in range(4):
            if container.find(["h2", "h3", "h4"]) and _card_has_date(container):
                break
            parent = container.parent
            if parent is None or parent.name in ("html", "body"):
                break
            container = parent
        if id(container) not in seen_ids:
            seen_ids.add(id(container))
            cards.append(container)
    return cards


def _card_has_date(el) -> bool:
    return bool(_DATE_RE.search(el.get_text(" ", strip=True)))


def _parse_card(card, today: str, now: str) -> Corrida | None:
    text = card.get_text(" ", strip=True)

    # Date
    m = _DATE_RE.search(text)
    if not m:
        return None
    day, month, year = m.groups()
    data_evento = f"{year}-{month}-{day}"
    if data_evento < today:
        return None

    # Title from first significant heading
    titulo_raw = ""
    for tag in ["h2", "h3", "h4"]:
        el = card.find(tag)
        if el:
            titulo_raw = el.get_text(" ", strip=True)
            break
    titulo = normalize_titulo(titulo_raw)
    if not titulo or len(titulo) < 3:
        return None

    # Link: "Saiba Mais" button — required to fetch horario
    link_tag = card.find("a", class_=lambda c: c and "btn" in c)
    if not link_tag:
        link_tag = card.find("a", href=True)
    href = (link_tag["href"] if link_tag else "").strip()
    if href.startswith("/"):
        href = BASE + href
    link = href or URL

    # Horario: must fetch detail page
    horario = _fetch_horario(link) if link != URL else None
    # Horário no longer mandatory (policy 2026-07-11): keep the event without it.
    # if horario is None:
    #     return None

    # Distances from card description text
    desc_el = card.find(class_=lambda c: c and "card-text" in c)
    dist_text = desc_el.get_text(" ", strip=True) if desc_el else text
    distancias = _extract_distances(dist_text)
    if not distancias:
        distancias = _extract_distances(text)
    if not distancias:
        return None

    stable_id = f"sescdf_{slugify(titulo)}_{data_evento}"
    estado = _geo.resolve("Brasília, DF", "Brasília", "BR")[1] or "DF"
    return Corrida(
        id=stable_id,
        titulo=titulo,
        data_evento=data_evento,
        horario=horario,
        localizacao="Brasília, DF",
        cidade="Brasília",
        estado=estado,
        pais="BR",
        distancias=distancias,
        imagem_url=None,
        inscricoes_abertas=None,
        periodo_inscricao=None,
        fontes=[FonteInfo(
            nome=SOURCE_NAME,
            link_evento=link,
            links_inscricao=[link],
            tipo="organizador",
        )],
        miss_count=0,
        first_seen_at=now,
        updated_at=now,
    )


_BC_API = "https://brasilcorrida.com.br/api/src/Site/EventoDetalhe.php"
# O SESC publica links do Brasil Corrida com query de tracking entre o domínio
# e o hash (ex.: brasilcorrida.com.br/?fbclid=…#/evento/slug) — o [^#]* absorve
# qualquer coisa antes do fragmento.
_BC_SLUG_RE = re.compile(r"brasilcorrida\.com\.br/[^#]*#/evento/([^?&#]+)")


def _fetch_horario(url: str) -> str | None:
    """Fetch the event detail page and extract the start time.

    When the URL is a brasilcorrida.com.br SPA hash link, use their REST API
    (EventoDetalhe.php?eventoToken=…) to get the published start time.
    """
    m = _BC_SLUG_RE.search(url)
    if m:
        token = m.group(1)
        try:
            resp = get(f"{_BC_API}?eventoToken={token}")
            if resp.status_code == 200:
                ev = resp.json()
                hora = ev.get("eve_hora_largada") or ""
                if hora:
                    parts = hora.split(":")
                    h = int(parts[0])
                    mi = int(parts[1]) if len(parts) > 1 else 0
                    if 4 <= h <= 23:
                        return f"{h:02d}:{mi:02d}"
        except Exception:
            pass
        return None

    try:
        resp = get(url)
        if resp.status_code != 200:
            return None
        text = BeautifulSoup(resp.text, "lxml").get_text(" ", strip=True)
        return _extract_horario(text)
    except Exception:
        return None


def _extract_horario(text: str) -> str | None:
    if not text:
        return None
    # Try keyword-anchored first
    m = _TIME_KW_RE.search(text)
    if m:
        if m.group(1) is not None:
            h, mi = int(m.group(1)), int(m.group(2))
        else:
            h, mi = int(m.group(3)), 0
        if 4 <= h <= 23:
            return f"{h:02d}:{mi:02d}"
    # Generic fallback
    m = _TIME_RE.search(text)
    if m:
        if m.group(1) is not None:
            h, mi = int(m.group(1)), int(m.group(2))
        else:
            h, mi = int(m.group(3)), 0
        if 4 <= h <= 23:
            return f"{h:02d}:{mi:02d}"
    return None


def _extract_distances(text: str) -> list[Distancia]:
    return [Distancia(km=km, data=None, horario=None) for km in extract_distances_from_text(text, min_km=1.0)]
