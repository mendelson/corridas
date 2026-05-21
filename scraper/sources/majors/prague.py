"""Volkswagen Prague Marathon scraper (runczech.com)

Edição 2026: 10 de maio (já realizada). Retorna 0 eventos até que a data
2027 seja anunciada oficialmente no site — o scraper vai encontrá-la
automaticamente via extract_all_future_dates quando disponível.
"""
from ._base import scrape_major

SOURCE_NAME = "Prague Marathon"
URL         = "https://www.runczech.com/en/races/volkswagen-prague-marathon"
KNOWN_DATE  = "2026-05-10"  # Edição 2026 encerrada; sem data futura confirmada
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
