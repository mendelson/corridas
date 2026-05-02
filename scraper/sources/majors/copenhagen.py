"""Copenhagen Marathon scraper (copenhagenmarathon.dk)"""
from ._base import scrape_major

SOURCE_NAME = "Copenhagen Marathon"
URL         = "https://copenhagenmarathon.dk/en/"
KNOWN_DATE  = "2026-05-17"
KNOWN_DATE_NEXT = "2027-05-16"
HORARIO     = "09:30"
LOCALIZACAO = "Copenhague, Dinamarca"

_OPEN   = ["register", "sign up", "enter now", "registration open", "tilmeld"]
_CLOSED = ["registration closed", "sold out", "tilmelding lukket"]


def scrape():
    return scrape_major(
        source_name=SOURCE_NAME, titulo="Copenhagen Marathon",
        url=URL, known_date=KNOWN_DATE,
        known_dates=[KNOWN_DATE, KNOWN_DATE_NEXT], horario=HORARIO,
        localizacao=LOCALIZACAO, cidade=LOCALIZACAO,
        open_kw=_OPEN, closed_kw=_CLOSED,
    )
