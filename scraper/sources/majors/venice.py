"""Venice Marathon scraper (venicemarathon.it)

Edição 2026: 25 de outubro. Inclui as três distâncias do fim-de-semana:
  - Full Marathon (42km): saída em Stra/Padova → chegada em Veneza
  - Half Marathon (21km): saída na Villa Pisani
  - 10 km Run: saída em Veneza
"""
from __future__ import annotations

from bs4 import BeautifulSoup

from ...http_client import get
from ...models import Corrida, Distancia, FonteInfo
from ...utils import now_iso, today_iso, extract_all_future_dates, extract_date_from_soup

SOURCE_NAME = "Venice Marathon"
URL           = "https://www.venicemarathon.it/en/"
URL_TIMETABLE = "https://www.venicemarathon.it/en/race/timetable/"

KNOWN_DATE  = "2026-10-25"  # confirmed; only used as fallback when site is unreachable
LOCALIZACAO = "Veneza, Itália"

_DISTANCES: list[tuple[float, str]] = [
    (42.195, "09:15"),
    (21.097, "09:30"),
    (10.0,   "08:45"),
]

_OPEN_KW   = ["register", "registration open", "sign up", "enter now",
               "registrati", "iscriviti", "iscrizioni aperte"]
_CLOSED_KW = ["sold out", "registration closed", "registrations closed",
               "iscrizioni chiuse", "esaurito"]


def scrape() -> list[Corrida]:
    today = today_iso()

    dates_to_use: list[str] = []
    imagem_url: str | None = None
    inscricoes_abertas: bool | None = None

    for url in (URL_TIMETABLE, URL):
        try:
            resp = get(url, timeout=10)
            if resp.status_code != 200:
                continue
            soup = BeautifulSoup(resp.text, "lxml")

            live_dates = extract_all_future_dates(soup, today)
            if not live_dates:
                single = extract_date_from_soup(soup)
                if single and single >= today:
                    live_dates = [single]
            if live_dates:
                dates_to_use = live_dates

            tag = soup.find("meta", property="og:image")
            if tag and tag.get("content"):
                imagem_url = tag["content"]

            text = soup.get_text(" ").lower()
            if any(k in text for k in _CLOSED_KW):
                inscricoes_abertas = False
            elif any(k in text for k in _OPEN_KW):
                inscricoes_abertas = True

            break
        except Exception:
            continue

    # Fallback to the single confirmed date only — never speculate on next year
    if not dates_to_use and KNOWN_DATE >= today:
        dates_to_use = [KNOWN_DATE]

    if not dates_to_use:
        return []

    now = now_iso()
    distancias = [Distancia(km=km, data=None, horario=h) for km, h in _DISTANCES]
    fonte = FonteInfo(
        nome=SOURCE_NAME,
        link_evento=URL,
        links_inscricao=[URL],
    )

    results = []
    for data in dates_to_use:
        year = data[:4]
        results.append(Corrida(
            id=f"venice-marathon_int_{year}",
            titulo="Maratona de Veneza",
            data_evento=data,
            horario=_DISTANCES[0][1],
            localizacao=LOCALIZACAO,
            cidade=LOCALIZACAO,
            estado="INT",
            distancias=distancias,
            imagem_url=imagem_url,
            inscricoes_abertas=inscricoes_abertas,
            periodo_inscricao=None,
            fontes=[fonte],
            miss_count=0,
            first_seen_at=now,
            updated_at=now,
        ))
    return results
