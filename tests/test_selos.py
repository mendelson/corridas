"""Tests for the selos/majors enrichment (no network).

Majors are a reference match (deterministic); the World Athletics selo matcher
is tuned for precision (a miss = no badge, safe; a wrong match would mislabel).
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    from scraper import enrichment_selos as es
    from scraper.models import Corrida, Distancia, FonteInfo
except ImportError as exc:  # pragma: no cover — frontend job lacks scraper deps
    pytest.skip(f"deps indisponíveis: {exc}", allow_module_level=True)


def _mk(titulo, data, cidade, estado, pais):
    return Corrida(
        id="x", titulo=titulo, data_evento=data, horario="07:00",
        localizacao=f"{cidade}, {estado}", cidade=cidade, estado=estado,
        distancias=[Distancia(km=42.195, data=None, horario=None)],
        imagem_url=None, inscricoes_abertas=None, periodo_inscricao=None,
        fontes=[FonteInfo(nome="x", link_evento="http://x",
                          links_inscricao=["http://x"], tipo="organizador")],
        miss_count=0, first_seen_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00", pais=pais)


def test_majors_matched_by_title_and_country():
    berlin = _mk("BMW Berlin Marathon", "2026-09-27", "Berlim", "BE", "DE")
    sydney = _mk("TCS Sydney Marathon", "2026-08-30", "Sydney", "NSW", "AU")
    sp = _mk("Maratona de São Paulo", "2026-04-12", "São Paulo", "SP", "BR")
    for c in (berlin, sydney, sp):
        es._apply_majors(c)
    assert berlin.major and sydney.major
    assert not sp.major


def test_major_requires_country_match():
    # A "Tokyo"-named race in the wrong country must not become a Major.
    fake = _mk("Tokyo Run Brasil", "2026-03-07", "São Paulo", "SP", "BR")
    es._apply_majors(fake)
    assert not fake.major


def test_selo_matcher_precision():
    wa = {"nome": es.normalize_titulo_merge("30ª Maratona Internacional de São Paulo"),
          "cidade": es.normalize_titulo_merge("São Paulo"), "iso2": "BR",
          "data": "2026-04-12", "selo": "label"}
    hit = _mk("Maratona Internacional de São Paulo", "2026-04-12", "São Paulo", "SP", "BR")
    assert es._matches(hit, wa)
    # Wrong country → no match
    other_country = _mk("Maratona Internacional de São Paulo", "2026-04-12", "São Paulo", "SP", "PT")
    assert not es._matches(other_country, wa)
    # Far-off date → no match
    wrong_date = _mk("Maratona Internacional de São Paulo", "2026-09-01", "São Paulo", "SP", "BR")
    assert not es._matches(wrong_date, wa)
    # Unrelated race same day/country → no match
    unrelated = _mk("Corrida do Trabalhador", "2026-04-12", "Santos", "SP", "BR")
    assert not es._matches(unrelated, wa)


def test_date_tolerance():
    assert es._date_close("2026-04-12", "2026-04-13")
    assert es._date_close("2026-04-12", "2026-04-12")
    assert not es._date_close("2026-04-12", "2026-04-20")
