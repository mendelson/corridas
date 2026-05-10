"""Bank of America Chicago Marathon scraper"""
from ._base import scrape_major

SOURCE_NAME = "Bank of America Chicago Marathon"
URL = "https://www.chicagomarathon.com/"
KNOWN_DATE = "2026-10-11"
HORARIO = "07:30"
LOCALIZACAO = "Chicago, EUA"

_OPEN   = ["register now", "registration open", "apply", "enter now", "lottery open", "entries open"]
_CLOSED = ["registration closed", "sold out", "lottery closed", "entry closed"]


def scrape():
    return scrape_major(
        source_name=SOURCE_NAME, titulo="Bank of America Chicago Marathon",
        url=URL, known_date=KNOWN_DATE,
        known_dates=[KNOWN_DATE], horario=HORARIO,
        localizacao=LOCALIZACAO, cidade=LOCALIZACAO,
        open_kw=_OPEN, closed_kw=_CLOSED,
    )
