"""Dublin City Marathon scraper (dublincitymarathon.ie)"""
from ._base import scrape_major

SOURCE_NAME = "Dublin City Marathon"
URL         = "https://www.irishlifedublinmarathon.ie/"
KNOWN_DATE  = "2026-10-25"
KNOWN_DATE_NEXT = "2027-10-31"
HORARIO     = "09:00"
LOCALIZACAO = "Dublin, Irlanda"

_OPEN   = ["register", "sign up", "enter now", "registration open", "entries open"]
_CLOSED = ["registration closed", "sold out", "entry closed", "entries closed"]


def scrape():
    return scrape_major(
        source_name=SOURCE_NAME, titulo="Dublin City Marathon",
        url=URL, known_date=KNOWN_DATE,
        known_dates=[KNOWN_DATE, KNOWN_DATE_NEXT], horario=HORARIO,
        localizacao=LOCALIZACAO, cidade=LOCALIZACAO,
        open_kw=_OPEN, closed_kw=_CLOSED,
    )
