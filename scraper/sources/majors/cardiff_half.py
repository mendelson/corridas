"""Cardiff Half Marathon scraper (cardiffhalfmarathon.co.uk)"""
from ._base import scrape_major

SOURCE_NAME = "Cardiff Half Marathon"
URL         = "https://www.cardiffhalfmarathon.co.uk/"
KNOWN_DATE  = "2026-10-04"
HORARIO     = "09:30"
LOCALIZACAO = "Cardiff, Reino Unido"

_OPEN   = ["register", "sign up", "enter now", "book now", "registration open"]
_CLOSED = ["registration closed", "sold out", "entries closed"]


def scrape():
    return scrape_major(
        source_name=SOURCE_NAME, titulo="Cardiff Half Marathon",
        url=URL, known_date=KNOWN_DATE, horario=HORARIO,
        localizacao=LOCALIZACAO, cidade=LOCALIZACAO,
        open_kw=_OPEN, closed_kw=_CLOSED,
        distances_km=[21.097],
    )
