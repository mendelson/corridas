"""Volkswagen Prague Marathon scraper (runczech.com)"""
from ._base import scrape_major

SOURCE_NAME = "Prague Marathon"
URL         = "https://www.runczech.com/en/events/prague-international-marathon-2026"
KNOWN_DATE  = "2026-05-10"
HORARIO     = "09:00"
LOCALIZACAO = "Praga, República Tcheca"

_OPEN   = ["register", "sign up", "enter now", "entries open", "registration open"]
_CLOSED = ["registration closed", "sold out", "entry closed", "entries closed"]


def scrape():
    return scrape_major(
        source_name=SOURCE_NAME, titulo="Volkswagen Prague Marathon",
        url=URL, known_date=KNOWN_DATE, horario=HORARIO,
        localizacao=LOCALIZACAO, cidade=LOCALIZACAO,
        open_kw=_OPEN, closed_kw=_CLOSED,
    )
