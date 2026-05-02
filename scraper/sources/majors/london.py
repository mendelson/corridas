"""TCS London Marathon scraper"""
from ._base import scrape_major

SOURCE_NAME = "TCS London Marathon"
URL = "https://www.tcslondonmarathon.com/"
KNOWN_DATE = "2027-04-25"
HORARIO = "09:00"
LOCALIZACAO = "Londres, Reino Unido"

_OPEN   = ["enter now", "ballot open", "register", "apply", "entries open"]
_CLOSED = ["ballot closed", "entry closed", "entries closed", "sold out"]


def scrape():
    return scrape_major(
        source_name=SOURCE_NAME, titulo="TCS London Marathon",
        url=URL, known_date=KNOWN_DATE,
        known_dates=[KNOWN_DATE], horario=HORARIO,
        localizacao=LOCALIZACAO, cidade=LOCALIZACAO,
        open_kw=_OPEN, closed_kw=_CLOSED,
    )
