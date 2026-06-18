"""TCS New York City Marathon scraper"""
from ._base import scrape_single_event

SOURCE_NAME = "TCS New York City Marathon"
URL = "https://www.nyrr.org/races/tcsnycmarathon"
KNOWN_DATE = "2026-11-01"
HORARIO = "08:00"
LOCALIZACAO = "Nova York, EUA"

_OPEN   = ["register now", "entry open", "apply", "lottery open", "entries open"]
_CLOSED = ["entry closed", "registration closed", "lottery closed"]


def scrape():
    return scrape_single_event(
        source_name=SOURCE_NAME, titulo="TCS New York City Marathon",
        url=URL, known_date=KNOWN_DATE,
        known_dates=[KNOWN_DATE], horario=HORARIO,
        localizacao=LOCALIZACAO, cidade=LOCALIZACAO,
        pais="US",
        open_kw=_OPEN, closed_kw=_CLOSED,
    )
