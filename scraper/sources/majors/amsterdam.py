"""TCS Amsterdam Marathon scraper (tcsamsterdammarathon.nl)"""
from ._base import scrape_major

SOURCE_NAME = "Amsterdam Marathon"
URL         = "https://www.tcsamsterdammarathon.nl/en/"
KNOWN_DATE  = "2026-10-18"
HORARIO     = "09:15"
LOCALIZACAO = "Amsterdã, Países Baixos"

_OPEN   = ["register", "sign up", "enter now", "registration open", "entries open",
           "inschrijven", "inschrijving open"]
_CLOSED = ["registration closed", "sold out", "inschrijving gesloten"]


def scrape():
    return scrape_major(
        source_name=SOURCE_NAME, titulo="TCS Amsterdam Marathon",
        url=URL, known_date=KNOWN_DATE, horario=HORARIO,
        localizacao=LOCALIZACAO, cidade=LOCALIZACAO,
        open_kw=_OPEN, closed_kw=_CLOSED,
    )
