"""Great North Run scraper (greatrun.org) — world's largest half marathon"""
from ._base import scrape_major

SOURCE_NAME = "Great North Run"
URL         = "https://www.greatrun.org/events/great-north-run/"
KNOWN_DATE  = "2026-09-13"
KNOWN_DATE_NEXT = "2027-09-12"
HORARIO     = "10:57"
LOCALIZACAO = "Newcastle, Reino Unido"

_OPEN   = ["register", "sign up", "enter now", "book now", "registration open",
           "ballot open", "apply now"]
_CLOSED = ["registration closed", "sold out", "ballot closed", "entries closed"]


def scrape():
    return scrape_major(
        source_name=SOURCE_NAME, titulo="Great North Run",
        url=URL, known_date=KNOWN_DATE,
        known_dates=[KNOWN_DATE, KNOWN_DATE_NEXT], horario=HORARIO,
        localizacao=LOCALIZACAO, cidade=LOCALIZACAO,
        open_kw=_OPEN, closed_kw=_CLOSED,
        distances_km=[21.097],
    )
