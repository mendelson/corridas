"""Asics Stockholm Marathon scraper (stockholmmarathon.se)"""
from ._base import scrape_major

SOURCE_NAME = "Stockholm Marathon"
URL         = "https://www.stockholmmarathon.se/en/"
KNOWN_DATE  = "2026-06-06"
HORARIO     = "12:00"
LOCALIZACAO = "Estocolmo, Suécia"

_OPEN   = ["register", "sign up", "anmäl", "anmälan öppen", "registration open"]
_CLOSED = ["anmälan stängd", "sold out", "registration closed"]


def scrape():
    return scrape_major(
        source_name=SOURCE_NAME, titulo="Asics Stockholm Marathon",
        url=URL, known_date=KNOWN_DATE, horario=HORARIO,
        localizacao=LOCALIZACAO, cidade=LOCALIZACAO,
        open_kw=_OPEN, closed_kw=_CLOSED,
    )
