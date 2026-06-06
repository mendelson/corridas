"""Manchester Marathon scraper (manchestermarathon.com)"""
from ._base import scrape_major

SOURCE_NAME = "Manchester Marathon"
URL         = "https://www.manchestermarathon.co.uk/"
KNOWN_DATE  = "2027-04-18"
HORARIO     = "09:00"
LOCALIZACAO = "Manchester, Reino Unido"

_OPEN   = ["register", "sign up", "enter now", "book now", "registration open"]
_CLOSED = ["registration closed", "sold out", "entries closed"]


def scrape():
    return scrape_major(
        source_name=SOURCE_NAME, titulo="Manchester Marathon",
        url=URL, known_date=KNOWN_DATE,
        known_dates=[KNOWN_DATE], horario=HORARIO,
        localizacao=LOCALIZACAO, cidade=LOCALIZACAO,
        pais="GB",
        open_kw=_OPEN, closed_kw=_CLOSED,
    )
