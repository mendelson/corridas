"""Venice Marathon scraper (venicemarathon.it)

Edição 2026: 25 de outubro. Inclui as três distâncias do fim-de-semana:
  - Full Marathon (42km): saída em Stra/Padova → chegada em Veneza
  - Half Marathon (21km): saída na Villa Pisani
  - 10 km Run: saída em Veneza

Horários de referência das edições recentes; o scraper tenta buscar dados ao
vivo mas aceita falha silenciosa (o site retorna 403 para bots).
"""
from __future__ import annotations

from bs4 import BeautifulSoup

from ...http_client import get
from ...models import Corrida, Distancia, FonteInfo
from ...utils import now_iso, today_iso, extract_date_from_soup

SOURCE_NAME   = "Venice Marathon"
URL           = "https://www.venicemarathon.it/en/"
URL_TIMETABLE = "https://www.venicemarathon.it/en/race/timetable/"

# ── Fallback values (from 2025 edition) ─────────────────────────────────────
KNOWN_DATE  = "2026-10-25"
LOCALIZACAO = "Veneza, Itália"

# Per-distance reference start times (Venice local time, UTC+1 in October)
_DISTANCES: list[tuple[float, str]] = [
    (42.195, "09:15"),  # Marathon — start in Stra/Padova
    (21.097, "09:30"),  # Half marathon — start at Villa Pisani
    (10.0,   "08:45"),  # 10 km run — start in Venice
]

_OPEN_KW   = ["register", "registration open", "sign up", "enter now",
               "registrati", "iscriviti", "iscrizioni aperte"]
_CLOSED_KW = ["sold out", "registration closed", "registrations closed",
               "iscrizioni chiuse", "esaurito"]


def scrape() -> list[Corrida]:
    today = today_iso()
    if KNOWN_DATE < today:
        return []

    data:              str        = KNOWN_DATE
    imagem_url:        str | None = None
    inscricoes_abertas: bool | None = None

    # Best-effort live fetch — silently fall through on network errors / 403
    for url in (URL_TIMETABLE, URL):
        try:
            resp = get(url, timeout=10)
            if resp.status_code != 200:
                continue
            soup = BeautifulSoup(resp.text, "lxml")

            raw_date = extract_date_from_soup(soup)
            if raw_date and raw_date >= today:
                data = raw_date

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

    year = data[:4]
    now  = now_iso()

    distancias = [
        Distancia(km=km, data=None, horario=horario)
        for km, horario in _DISTANCES
    ]

    fonte = FonteInfo(
        nome=SOURCE_NAME,
        link_evento=URL,
        links_inscricao=[URL] if inscricoes_abertas else [],
    )

    return [Corrida(
        id=f"venice-marathon_int_{year}",
        titulo="Maratona de Veneza",
        data_evento=data,
        horario=_DISTANCES[0][1],  # marathon start time as event horario
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
    )]
