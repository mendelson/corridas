"""Comrades Marathon — the world's oldest/largest ultramarathon (KwaZulu-Natal, ZA).

Not a World Marathon Major and not on any aggregator platform, so it needs a
dedicated single-event scraper. The course ALTERNATES direction each year —
"Up Run" (Durban → Pietermaritzburg) vs "Down Run" (Pietermaritzburg → Durban)
— so distance and finish city change per edition.

Everything is read from the page on every run; nothing is hardcoded (CLAUDE.md:
event data must be obtained explicitly from page content — if it isn't there,
emit nothing, never guess). Future editions therefore update automatically.
If the page can't be fetched or parsed, the scraper returns [] (the health
monitor flags the regression); it never ships stale/guessed data.

Extracted from comrades.com/race-information (probed 2026-06-12):
  * date    — weekday-anchored "Sunday, DD Month YYYY" (expo dates carry no
              weekday, so they're never matched);
  * distance — "the race distance is 85.77km";
  * finish  — "…finishes in Pietermaritzburg".
horario is left unset: the start is batched by group (05h00/05h15/05h30), so
there is no single official gun time to read (horario is optional).
"""
from __future__ import annotations

import html
import re

from bs4 import BeautifulSoup

from ...http_client import get
from ...models import Corrida, Distancia, FonteInfo
from ...utils import slugify, now_iso, today_iso
from ... import geo as _geo
from ._base import _og_image, _twitter_image, _first_race_photo, _check_status

SOURCE_NAME = "Comrades Marathon"
URL = "https://comrades.com/race-information"
PAIS = "ZA"

_MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july",
     "august", "september", "october", "november", "december"], 1)}

# Race date: weekday-anchored full date. Expo dates ("07 Jun 2026") carry no
# weekday, so this never matches them.
_DATE_RE = re.compile(
    r"\b(?:Sunday|Sun)[,\s]+(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", re.IGNORECASE)
_DIST_RE = re.compile(r"race distance is\s*(\d+(?:\.\d+)?)\s*km", re.IGNORECASE)
_FINISH_RE = re.compile(r"finish(?:es)?\s+in\s+([A-Z][A-Za-z]+(?:\s[A-Z][A-Za-z]+)?)")

_OPEN = ["enter now", "entries open", "register now", "entries are open"]
_CLOSED = ["entries closed", "sold out", "entries are closed", "entry closed"]


def _parse_page(soup: BeautifulSoup) -> dict | None:
    """Extract {data, km, cidade} explicitly from the page, or None if any is missing."""
    text = html.unescape(re.sub(r"\s+", " ", soup.get_text(" ", strip=True)))

    md = _DATE_RE.search(text)
    mon = _MONTHS.get(md.group(2).lower()) if md else None
    if not md or not mon:
        return None
    data = f"{md.group(3)}-{mon:02d}-{int(md.group(1)):02d}"

    dm = _DIST_RE.search(text)
    if not dm:
        return None
    km = float(dm.group(1))
    if not 80 <= km <= 95:  # sanity: Comrades is ~85–90 km
        return None

    fm = _FINISH_RE.search(text)
    if not fm:
        return None
    cidade = fm.group(1).strip()

    return {"data": data, "km": km, "cidade": cidade}


def scrape() -> list[Corrida]:
    today = today_iso()
    try:
        resp = get(URL, source=SOURCE_NAME)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
    except Exception as e:
        print(f"[{SOURCE_NAME}] erro ao buscar página: {e}")
        return []

    ed = _parse_page(soup)
    if not ed:
        print(f"[{SOURCE_NAME}] não foi possível extrair data/distância/chegada da página")
        return []
    if ed["data"] < today:
        print(f"[{SOURCE_NAME}] edição {ed['data']} já passou — aguardando anúncio")
        return []

    _pais, estado = _geo.resolve(ed["cidade"], "", PAIS)
    if estado == "" or _pais != PAIS:
        print(f"[{SOURCE_NAME}] estado não resolvido para '{ed['cidade']}' — pulando")
        return []

    imagem_url = _og_image(soup, URL) or _twitter_image(soup, URL) or _first_race_photo(soup, URL)
    inscricoes_abertas = _check_status(soup, _OPEN, _CLOSED)
    now = now_iso()
    corrida = Corrida(
        id=f"{slugify('Comrades Marathon')}_{PAIS.lower()}_{ed['data'][:4]}",
        titulo="Comrades Marathon",
        data_evento=ed["data"],
        horario=None,  # batched group starts — no single gun time on the page
        localizacao=f"{ed['cidade']}, KwaZulu-Natal",
        cidade=ed["cidade"],
        estado=estado,
        pais=PAIS,
        distancias=[Distancia(km=ed["km"], data=None, horario=None)],
        imagem_url=imagem_url,
        inscricoes_abertas=inscricoes_abertas,
        periodo_inscricao=None,
        fontes=[FonteInfo(nome=SOURCE_NAME, link_evento=URL,
                          links_inscricao=[URL], tipo="organizador")],
        miss_count=0,
        first_seen_at=now,
        updated_at=now,
    )
    print(f"[{SOURCE_NAME}] 1 edição ({ed['data']}, {ed['cidade']}/{estado}, {ed['km']}km)")
    return [corrida]
