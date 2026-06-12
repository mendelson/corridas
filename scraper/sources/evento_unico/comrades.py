"""Comrades Marathon — the world's oldest/largest ultramarathon (KwaZulu-Natal, ZA).

Not a World Marathon Major and not on any aggregator platform, so it needs a
dedicated single-event scraper. Two specifics drive the design:

  * The course ALTERNATES direction each year — "Up Run" (Durban →
    Pietermaritzburg) vs "Down Run" (Pietermaritzburg → Durban) — so the
    distance AND finish city change per edition. They are read from the page
    every run, never carried from one edition to the next.
  * The race-information page lists EXPO dates ("07–10 Jun") *before* race day,
    so a naive "earliest future date" extraction would grab the expo. The race
    date is therefore parsed from the weekday-anchored line ("Sunday, DD Month
    YYYY"), which the expo dates never carry.

The page is parsed live so future editions update automatically. A confirmed
hardcoded edition is the safety net: if the page wording changes and parsing
fails, the known edition is still emitted (and the health monitor flags the
parse regression after 3 misses). Everything is read explicitly — nothing is
guessed (CLAUDE.md: never infer dates/distances).

Probed 2026-06-12 (comrades.com/race-information): "UP RUN starts in Durban
and finishes in Pietermaritzburg … Sunday, 14 June 2026 … race distance is
85.77km".
"""
from __future__ import annotations

import html
import re

from bs4 import BeautifulSoup

from ...http_client import get
from ...models import Corrida, Distancia, FonteInfo
from ...utils import slugify, now_iso, today_iso
from ._base import _og_image, _twitter_image, _first_race_photo, _check_status

SOURCE_NAME = "Comrades Marathon"
URL = "https://comrades.com/race-information"
PAIS = "ZA"
ESTADO = "KZN"  # KwaZulu-Natal — both Durban and Pietermaritzburg are in KZN
HORARIO = "05:45"  # traditional Comrades gun time (05h45 SAST)

# Route invariant (not a guess): the Up Run finishes in Pietermaritzburg, the
# Down Run finishes in Durban.
_FINISH = {"up": "Pietermaritzburg", "down": "Durban"}

# Safety net — the last edition we confirmed by hand. Emitted only if live
# parsing fails AND the date is still future.
_FALLBACK = {"data": "2026-06-14", "km": 85.77, "direction": "up"}

_MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july",
     "august", "september", "october", "november", "december"], 1)}

# Race date: weekday-anchored full date. Expo dates ("07 Jun 2026") carry no
# weekday, so this never matches them.
_DATE_RE = re.compile(
    r"\b(?:Sunday|Sun)[,\s]+(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", re.IGNORECASE)
_DIST_RE = re.compile(r"race distance is\s*(\d+(?:\.\d+)?)\s*km", re.IGNORECASE)
_UP_RE = re.compile(r"\bUP\s+RUN\b", re.IGNORECASE)
_DOWN_RE = re.compile(r"\bDOWN\s+RUN\b", re.IGNORECASE)

_OPEN = ["enter now", "entries open", "register now", "entries are open"]
_CLOSED = ["entries closed", "sold out", "entries are closed", "entry closed"]


def _parse_page(soup: BeautifulSoup) -> dict | None:
    """Extract {data, km, direction} explicitly from the page, or None."""
    text = html.unescape(re.sub(r"\s+", " ", soup.get_text(" ", strip=True)))

    md = _DATE_RE.search(text)
    if not md:
        return None
    mon = _MONTHS.get(md.group(2).lower())
    if not mon:
        return None
    data = f"{md.group(3)}-{mon:02d}-{int(md.group(1)):02d}"

    dm = _DIST_RE.search(text)
    if not dm:
        return None
    km = float(dm.group(1))
    if not 80 <= km <= 95:  # sanity: Comrades is ~85–90 km
        return None

    up, down = bool(_UP_RE.search(text)), bool(_DOWN_RE.search(text))
    direction = "up" if (up and not down) else ("down" if (down and not up) else None)
    if direction is None:
        return None

    return {"data": data, "km": km, "direction": direction}


def scrape() -> list[Corrida]:
    today = today_iso()
    soup = None
    imagem_url = None
    inscricoes_abertas = None
    try:
        resp = get(URL, source=SOURCE_NAME)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        imagem_url = _og_image(soup, URL) or _twitter_image(soup, URL) or _first_race_photo(soup, URL)
        inscricoes_abertas = _check_status(soup, _OPEN, _CLOSED)
    except Exception as e:
        print(f"[{SOURCE_NAME}] erro ao buscar página: {e}")

    edition = _parse_page(soup) if soup else None
    if edition:
        print(f"[{SOURCE_NAME}] edição lida da página: {edition['data']} "
              f"{edition['km']}km ({edition['direction']} run)")
    elif _FALLBACK["data"] >= today:
        edition = _FALLBACK
        print(f"[{SOURCE_NAME}] parsing falhou — usando edição confirmada {edition['data']}")
    else:
        print(f"[{SOURCE_NAME}] sem edição futura na página — aguardando anúncio")
        return []

    if edition["data"] < today:
        print(f"[{SOURCE_NAME}] edição {edition['data']} já passou — aguardando anúncio")
        return []

    cidade = _FINISH[edition["direction"]]
    year = edition["data"][:4]
    now = now_iso()
    corrida = Corrida(
        id=f"{slugify('Comrades Marathon')}_{PAIS.lower()}_{year}",
        titulo="Comrades Marathon",
        data_evento=edition["data"],
        horario=HORARIO,
        localizacao=f"{cidade}, KwaZulu-Natal",
        cidade=cidade,
        estado=ESTADO,
        pais=PAIS,
        distancias=[Distancia(km=edition["km"], data=None, horario=None)],
        imagem_url=imagem_url,
        inscricoes_abertas=inscricoes_abertas,
        periodo_inscricao=None,
        fontes=[FonteInfo(nome=SOURCE_NAME, link_evento=URL,
                          links_inscricao=[URL], tipo="organizador")],
        miss_count=0,
        first_seen_at=now,
        updated_at=now,
    )
    print(f"[{SOURCE_NAME}] 1 edição ({edition['data']}, {cidade})")
    return [corrida]
