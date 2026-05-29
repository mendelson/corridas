"""Volkswagen Prague Marathon scraper (runczech.com)

Edição 2026: 10 de maio (já realizada). KNOWN_DATE usa data provisória de 2027
até que o site anuncie oficialmente — extract_all_future_dates sobrescreve
automaticamente quando a data real aparecer na página.
"""
from ._base import scrape_major

SOURCE_NAME = "Prague Marathon"
URL         = "https://www.runczech.com/en/races/volkswagen-prague-marathon"
KNOWN_DATE  = "2027-05-09"  # Provisório: primeira semana de maio 2027 (padrão histórico)
HORARIO     = "09:00"
LOCALIZACAO = "Praga, República Tcheca"

_OPEN   = ["register", "sign up", "enter now", "entries open", "registration open"]
_CLOSED = ["registration closed", "sold out", "entry closed", "entries closed"]


def scrape():
    return scrape_major(
        source_name=SOURCE_NAME, titulo="Volkswagen Prague Marathon",
        url=URL, known_date=KNOWN_DATE,
        known_dates=[KNOWN_DATE], horario=HORARIO,
        localizacao=LOCALIZACAO, cidade=LOCALIZACAO,
        pais="CZ",
        open_kw=_OPEN, closed_kw=_CLOSED,
    )
