"""Tokyo Marathon scraper"""
from ._base import scrape_major

SOURCE_NAME = "Tokyo Marathon"
URL = "https://www.marathon.tokyo/en/"
KNOWN_DATE = "2027-03-07"
HORARIO = "09:10"
LOCALIZACAO = "Tóquio, Japão"

_OPEN   = ["entry open", "registration open", "apply now", "entries open", "register"]
_CLOSED = ["entry closed", "registration closed", "entry period has ended"]


def scrape():
    return scrape_major(
        source_name=SOURCE_NAME, titulo="Tokyo Marathon",
        url=URL, known_date=KNOWN_DATE,
        known_dates=[KNOWN_DATE], horario=HORARIO,
        localizacao=LOCALIZACAO, cidade=LOCALIZACAO,
        pais="JP",
        open_kw=_OPEN, closed_kw=_CLOSED,
    )
