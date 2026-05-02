"""Schneider Electric Paris Marathon scraper (schneiderelectricparismarathon.com)

Edição 2026: 5 de abril (já realizada). Known date ajustado para 2027.
"""
from ._base import scrape_major

SOURCE_NAME = "Paris Marathon"
URL         = "https://www.schneiderelectricparismarathon.com/en/"
KNOWN_DATE  = "2027-04-04"
HORARIO     = "08:30"
LOCALIZACAO = "Paris, França"

_OPEN   = ["register", "sign up", "enter now", "registration open",
           "s'inscrire", "inscriptions ouvertes"]
_CLOSED = ["registration closed", "sold out", "inscriptions fermées", "complet"]


def scrape():
    return scrape_major(
        source_name=SOURCE_NAME, titulo="Schneider Electric Paris Marathon",
        url=URL, known_date=KNOWN_DATE,
        known_dates=[KNOWN_DATE], horario=HORARIO,
        localizacao=LOCALIZACAO, cidade=LOCALIZACAO,
        open_kw=_OPEN, closed_kw=_CLOSED,
    )
