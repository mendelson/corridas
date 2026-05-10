"""Edinburgh Marathon Festival scraper (edinburghmarathon.com)"""
from ._base import scrape_major

SOURCE_NAME = "Edinburgh Marathon Festival"
URL         = "https://www.edinburghmarathon.com/"
KNOWN_DATE  = "2026-05-24"
HORARIO     = "10:00"
LOCALIZACAO = "Edimburgo, Reino Unido"

_OPEN   = ["register", "sign up", "enter now", "book now", "registration open"]
_CLOSED = ["registration closed", "sold out", "entries closed"]


def scrape():
    return scrape_major(
        source_name=SOURCE_NAME, titulo="Edinburgh Marathon Festival",
        url=URL, known_date=KNOWN_DATE,
        known_dates=[KNOWN_DATE], horario=HORARIO,
        localizacao=LOCALIZACAO, cidade=LOCALIZACAO,
        open_kw=_OPEN, closed_kw=_CLOSED,
        distances_km=[42.195, 21.097],
    )
