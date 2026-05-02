"""Valencia Trinidad Alfonso Marathon scraper (valenciaciudaddelrunning.com)"""
from ._base import scrape_major

SOURCE_NAME = "Valencia Marathon"
URL         = "https://valenciaciudaddelrunning.com/en/marathon/"
KNOWN_DATE  = "2026-12-06"
KNOWN_DATE_NEXT = "2027-12-05"
HORARIO     = "08:30"
LOCALIZACAO = "Valência, Espanha"

_OPEN   = ["register", "sign up", "enter now", "registration open", "inscríbete",
           "inscripción abierta"]
_CLOSED = ["registration closed", "sold out", "inscripción cerrada", "agotado"]


def scrape():
    return scrape_major(
        source_name=SOURCE_NAME, titulo="Valencia Trinidad Alfonso Marathon",
        url=URL, known_date=KNOWN_DATE,
        known_dates=[KNOWN_DATE, KNOWN_DATE_NEXT], horario=HORARIO,
        localizacao=LOCALIZACAO, cidade=LOCALIZACAO,
        open_kw=_OPEN, closed_kw=_CLOSED,
    )
