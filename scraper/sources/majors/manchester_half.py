"""Manchester Half Marathon scraper (manchesterhalfmarathon.com)"""
from ._base import scrape_major

SOURCE_NAME = "Manchester Half Marathon"
URL         = "https://www.manchesterhalfmarathon.com/"
KNOWN_DATE  = "2026-10-04"
KNOWN_DATE_NEXT = "2027-10-03"
HORARIO     = "09:00"
LOCALIZACAO = "Manchester, Reino Unido"

_OPEN   = ["register", "sign up", "enter now", "book now", "registration open"]
_CLOSED = ["registration closed", "sold out", "entries closed"]


def scrape():
    return scrape_major(
        source_name=SOURCE_NAME, titulo="Manchester Half Marathon",
        url=URL, known_date=KNOWN_DATE,
        known_dates=[KNOWN_DATE, KNOWN_DATE_NEXT], horario=HORARIO,
        localizacao=LOCALIZACAO, cidade=LOCALIZACAO,
        open_kw=_OPEN, closed_kw=_CLOSED,
        distances_km=[21.097],
    )
