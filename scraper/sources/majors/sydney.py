"""TCS Sydney Marathon scraper"""
from ._base import scrape_major

SOURCE_NAME = "TCS Sydney Marathon"
URL = "https://www.tcssydneymarathon.com.au/"
KNOWN_DATE = "2026-09-20"
HORARIO = "07:00"
LOCALIZACAO = "Sydney, Austrália"

_OPEN   = ["enter now", "register", "entries open", "apply", "entry open"]
_CLOSED = ["entries closed", "entry closed", "sold out", "registration closed"]


def scrape():
    # Site has SSL issues — disable verification
    return scrape_major(
        source_name=SOURCE_NAME, titulo="TCS Sydney Marathon",
        url=URL, known_date=KNOWN_DATE, horario=HORARIO,
        localizacao=LOCALIZACAO, cidade=LOCALIZACAO,
        open_kw=_OPEN, closed_kw=_CLOSED,
        ssl_verify=False,
    )
