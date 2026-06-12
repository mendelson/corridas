"""Comrades Marathon — the world's oldest/largest ultramarathon (KwaZulu-Natal, ZA).

Not a World Marathon Major and not on any of our aggregator platforms, so it
needs a dedicated single-event scraper. Two specifics drive the design:

  * The course ALTERNATES direction each year ("Up Run" Durban→Pietermaritzburg
    vs "Down Run" Pietermaritzburg→Durban), so the distance and finish city
    change per edition — they must come from the page, never be guessed/carried.
  * The race-information page lists EXPO dates ("07–10 Jun 2026") *before* race
    day, so the shared scaffold's "earliest future date per year" extraction
    would pick the expo, not the race. Hence we pin the confirmed edition's
    explicit values (read from the page) instead of auto-extracting dates, and
    re-fetch only to refresh image/registration status.

Confirmed 2026 edition (from comrades.com/race-information, probed 2026-06-12):
  "The 'UP RUN' starts in Durban and finishes in Pietermaritzburg … Sunday,
   14 June 2026 … The race distance is 85.77km."
"""
from __future__ import annotations

from bs4 import BeautifulSoup

from ...http_client import get
from ...models import Corrida, Distancia, FonteInfo
from ...utils import slugify, now_iso, today_iso
from ._base import _og_image, _twitter_image, _first_race_photo, _check_status

SOURCE_NAME = "Comrades Marathon"
URL = "https://comrades.com/race-information"
PAIS = "ZA"
ESTADO = "KZN"  # KwaZulu-Natal — both Durban and Pietermaritzburg are in KZN

# Confirmed editions only — each entry's distance/finish-city is read from the
# official page for THAT edition (the up/down alternation forbids carrying one
# edition's distance to another). Add the next edition here once published.
_EDITIONS = [
    {
        "data": "2026-06-14",
        "horario": "05:45",          # traditional Comrades gun time (05h45 SAST)
        "km": 85.77,                 # 2026 "Up Run", explicit on race-information
        "cidade": "Pietermaritzburg",  # Up Run finish
    },
]

_OPEN = ["enter now", "entries open", "register now", "entries are open"]
_CLOSED = ["entries closed", "sold out", "entries are closed", "entry closed"]


def scrape() -> list[Corrida]:
    today = today_iso()
    editions = [e for e in _EDITIONS if e["data"] >= today]
    if not editions:
        print(f"[{SOURCE_NAME}] nenhuma edição futura confirmada — aguardando anúncio")
        return []

    imagem_url = None
    inscricoes_abertas = None
    try:
        resp = get(URL, source=SOURCE_NAME)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        imagem_url = _og_image(soup, URL) or _twitter_image(soup, URL) or _first_race_photo(soup, URL)
        inscricoes_abertas = _check_status(soup, _OPEN, _CLOSED)
    except Exception as e:
        print(f"[{SOURCE_NAME}] erro ao buscar página (mantendo dados confirmados): {e}")

    now = now_iso()
    results = []
    for ed in editions:
        year = ed["data"][:4]
        cidade = ed["cidade"]
        results.append(Corrida(
            id=f"{slugify('Comrades Marathon')}_{PAIS.lower()}_{year}",
            titulo="Comrades Marathon",
            data_evento=ed["data"],
            horario=ed["horario"],
            localizacao=f"{cidade}, KwaZulu-Natal",
            cidade=cidade,
            estado=ESTADO,
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
        ))
    print(f"[{SOURCE_NAME}] {len(results)} edição(ões) confirmada(s)")
    return results
