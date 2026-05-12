"""Brighton Marathon scraper (brightonmarathon.co.uk)"""
from ._base import scrape_major

SOURCE_NAME = "Brighton Marathon"
URL         = "https://www.londonmarathonevents.co.uk/brighton-marathon-weekend"
KNOWN_DATE  = "2027-04-04"
HORARIO     = "09:15"
LOCALIZACAO = "Brighton, Reino Unido"

_OPEN   = ["register", "sign up", "enter now", "book now", "registration open"]
_CLOSED = ["registration closed", "sold out", "entries closed"]


def scrape():
    return scrape_major(
        source_name=SOURCE_NAME, titulo="Brighton Marathon",
        url=URL, known_date=KNOWN_DATE,
        known_dates=[KNOWN_DATE], horario=HORARIO,
        localizacao=LOCALIZACAO, cidade=LOCALIZACAO,
        pais="GB",
        open_kw=_OPEN, closed_kw=_CLOSED,
        distances_km=[42.195, 21.097, 10.0],
    )
