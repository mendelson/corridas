"""Boston Marathon scraper"""
from ._base import scrape_major

SOURCE_NAME = "Boston Marathon"
URL = "https://www.baa.org/races/boston-marathon/"
KNOWN_DATE = "2027-04-19"  # Patriots' Day 2027
HORARIO = "09:00"
LOCALIZACAO = "Boston, EUA"

_OPEN   = ["register now", "registration open", "apply", "register for", "submit"]
_CLOSED = ["registration closed", "sold out", "registration is closed"]


def scrape():
    return scrape_major(
        source_name=SOURCE_NAME, titulo="Boston Marathon",
        url=URL, known_date=KNOWN_DATE, horario=HORARIO,
        localizacao=LOCALIZACAO, cidade=LOCALIZACAO,
        open_kw=_OPEN, closed_kw=_CLOSED,
    )
