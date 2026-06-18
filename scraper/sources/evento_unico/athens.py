"""Athens Classic Marathon — The Authentic (athensclassicmarathon.gr)"""
from ._base import scrape_single_event

SOURCE_NAME = "Athens Classic Marathon"
URL         = "https://www.athensauthenticmarathon.gr/en/"
KNOWN_DATE  = "2026-11-08"
HORARIO     = "09:00"
LOCALIZACAO = "Atenas, Grécia"

_OPEN   = ["register", "sign up", "enter now", "registration open", "εγγραφή"]
_CLOSED = ["registration closed", "sold out", "εγγραφές έκλεισαν"]


def scrape():
    return scrape_single_event(
        source_name=SOURCE_NAME, titulo="Athens Classic Marathon",
        url=URL, known_date=KNOWN_DATE,
        known_dates=[KNOWN_DATE], horario=HORARIO,
        localizacao=LOCALIZACAO, cidade=LOCALIZACAO,
        pais="GR",
        open_kw=_OPEN, closed_kw=_CLOSED,
    )
