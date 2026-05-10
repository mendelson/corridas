"""BMW Berlin Marathon scraper"""
from ._base import scrape_major

SOURCE_NAME = "BMW Berlin Marathon"
URL = "https://www.bmw-berlin-marathon.com/en/"
KNOWN_DATE = "2026-09-27"
HORARIO = "09:15"
LOCALIZACAO = "Berlim, Alemanha"

_OPEN   = ["register now", "registration open", "apply", "entry open", "entries open", "register for", "jetzt anmelden"]
_CLOSED = ["registration closed", "sold out", "entry closed", "anmeldung geschlossen"]


def scrape():
    return scrape_major(
        source_name=SOURCE_NAME, titulo="BMW Berlin Marathon",
        url=URL, known_date=KNOWN_DATE,
        known_dates=[KNOWN_DATE], horario=HORARIO,
        localizacao=LOCALIZACAO, cidade=LOCALIZACAO,
        open_kw=_OPEN, closed_kw=_CLOSED,
    )
