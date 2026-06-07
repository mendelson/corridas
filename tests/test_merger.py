"""Unit tests for the merger dedup rules (scraper.merger.are_duplicates).

Focus: the single-token brand-title rule added to fix events like the Corrida
POUPEX, whose title collapses to one token after stop-word/year stripping
("Corrida POUPEX 2026" -> "poupex") and therefore used to escape title
similarity entirely, leaving the same event split across several records.

Pure logic, no network — but it imports scraper.merger, so requirements-test.txt
must provide unidecode + python-dateutil.
"""
from __future__ import annotations

import pytest

from scraper.merger import are_duplicates
from scraper.models import Corrida, Distancia, FonteInfo


def _corrida(titulo, *, cidade, estado, data, kms, pais="BR", link=None, source="S"):
    # Each event gets a UNIQUE inscription link by default, so the conclusive
    # shared-link rule never fires and the tests actually exercise the
    # title/date/distance logic. Pass an explicit `link` to test link sharing.
    if link is None:
        link = f"https://ex.test/{source}/{titulo}/{cidade}/{data}".replace(" ", "-")
    return Corrida(
        id=f"{titulo}-{cidade}-{data}",
        titulo=titulo,
        data_evento=data,
        horario="18:00",
        localizacao=f"{cidade}, {estado}",
        cidade=cidade,
        estado=estado,
        distancias=[Distancia(km=k, data=None, horario=None) for k in kms],
        imagem_url=None,
        inscricoes_abertas=None,
        periodo_inscricao=None,
        fontes=[FonteInfo(nome=source, link_evento=link, links_inscricao=[link], tipo="calendario")],
        miss_count=0,
        first_seen_at="2026-01-01T00:00:00",
        updated_at="2026-01-01T00:00:00",
        pais=pais,
    )


# ── positive cases: the fix ───────────────────────────────────────────────────

def test_poupex_single_token_same_event_merges():
    """'Corrida POUPEX 2026' normalizes to the single token 'poupex'; same city,
    date and overlapping distances must now be recognized as one event."""
    a = _corrida("Corrida POUPEX 2026", cidade="Brasília", estado="DF",
                 data="2026-07-25", kms=[5.0, 10.0], source="Ativo")
    b = _corrida("Corrida Poupex 2026", cidade="Brasília", estado="DF",
                 data="2026-07-25", kms=[5.0, 10.0], source="Correr Brasília")
    assert are_duplicates(a, b) is True


def test_venice_single_token_merges():
    a = _corrida("Maratona de Veneza", cidade="Veneza", estado="VE",
                 data="2026-10-25", kms=[42.195, 21.097, 10.0], pais="IT", source="Venice Marathon")
    b = _corrida("Maratona De Veneza 2026", cidade="Veneza", estado="VE",
                 data="2026-10-25", kms=[10.0, 21.097, 42.195], pais="IT", source="Ticket Sports")
    assert are_duplicates(a, b) is True


def test_partial_distance_overlap_still_merges():
    """Atletis reports only 21k, Corridas Brasil reports 5/10/21 — they overlap."""
    a = _corrida("Meia Maratona de Treviso", cidade="Treviso", estado="SC",
                 data="2026-06-21", kms=[21.097], source="Atletis")
    b = _corrida("Meia Maratona de Treviso", cidade="Treviso", estado="SC",
                 data="2026-06-21", kms=[5.0, 10.0, 21.097], source="Corridas Brasil")
    assert are_duplicates(a, b) is True


# ── anti-regression: the >=2-token guard's intent must be preserved ───────────

def test_copa_cross_city_does_not_merge():
    """'Corrida da Copa' and 'Copa Run' both reduce to 'copa' but are in different
    cities/states — they must never merge (the original guard's whole point)."""
    a = _corrida("Corrida da Copa", cidade="Santo Ângelo", estado="RS",
                 data="2026-06-13", kms=[2.0, 5.0])
    b = _corrida("Copa Run", cidade="Brasília", estado="DF",
                 data="2026-06-13", kms=[5.0, 10.0])
    assert are_duplicates(a, b) is False


def test_same_token_same_state_different_city_does_not_merge():
    a = _corrida("Corrida Copa", cidade="São Paulo", estado="SP",
                 data="2026-06-13", kms=[5.0])
    b = _corrida("Copa Corrida", cidade="Campinas", estado="SP",
                 data="2026-06-13", kms=[5.0])
    assert are_duplicates(a, b) is False


def test_same_token_different_date_does_not_merge():
    """The single-token rule requires the EXACT same date."""
    a = _corrida("Corrida POUPEX 2026", cidade="Brasília", estado="DF",
                 data="2026-07-25", kms=[5.0, 10.0])
    b = _corrida("Corrida POUPEX 2026", cidade="Brasília", estado="DF",
                 data="2026-07-26", kms=[5.0, 10.0])
    assert are_duplicates(a, b) is False


def test_disjoint_distances_does_not_merge():
    """Same brand/city/date but fully disjoint distances → different editions."""
    a = _corrida("Corrida POUPEX 2026", cidade="Brasília", estado="DF",
                 data="2026-07-25", kms=[5.0], source="Atletis")
    b = _corrida("Corrida POUPEX 2026", cidade="Brasília", estado="DF",
                 data="2026-07-25", kms=[10.0], source="Corridas Brasil")
    assert are_duplicates(a, b) is False


def test_distinct_brands_same_city_date_do_not_merge():
    """Two genuinely different races on the same day in the same city."""
    a = _corrida("Maratona Pão de Açúcar", cidade="São Paulo", estado="SP",
                 data="2026-09-01", kms=[42.195])
    b = _corrida("Corrida do Trabalhador", cidade="São Paulo", estado="SP",
                 data="2026-09-01", kms=[42.195])
    assert are_duplicates(a, b) is False
