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


def _mk(titulo, data, cidade, estado, pais, km=42.195):
    return Corrida(
        id="x", titulo=titulo, data_evento=data, horario="07:00",
        localizacao=f"{cidade}, {estado}", cidade=cidade, estado=estado,
        distancias=[Distancia(km=km, data=None, horario=None)],
        imagem_url=None, inscricoes_abertas=None, periodo_inscricao=None,
        fontes=[FonteInfo(nome="x", link_evento="http://x",
                          links_inscricao=["http://x"], tipo="organizador")],
        miss_count=0, first_seen_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00", pais=pais)


# Dynamic majors: build the list the way _fetch_majors would from cache rows.
def _majors_from(rows):
    from scraper.utils import normalize_titulo_merge
    out = []
    for m in rows:
        toks = set(normalize_titulo_merge(m["name"]).split()) - es._MAJOR_STOP
        out.append({"tokens": toks, "iso2": m["iso2"], "name": m["name"]})
    return out


_CUR_MAJORS = _majors_from([
    {"name": "Berlin Marathon", "iso2": "DE"},
    {"name": "Sydney Marathon", "iso2": "AU"},
    {"name": "New York City Marathon", "iso2": "US"},
    {"name": "Tokyo Marathon", "iso2": "JP"},
])


def test_majors_matched_by_title_and_country():
    # A Major match requires the city tokens in BOTH the title AND the event's own
    # city, and a full-marathon distance (the stored city is the local/English
    # form, e.g. "Berlin, Alemanha" — as in the real data).
    berlin = _mk("BMW Berlin Marathon", "2026-09-27", "Berlin, Alemanha", "BE", "DE")
    sydney = _mk("TCS Sydney Marathon", "2026-08-30", "Sydney, NSW", "NSW", "AU")
    nyc = _mk("TCS New York City Marathon", "2026-11-01", "New York, NY", "NY", "US")
    sp = _mk("Maratona de São Paulo", "2026-04-12", "São Paulo", "SP", "BR")
    for c in (berlin, sydney, nyc, sp):
        es._apply_majors(c, _CUR_MAJORS)
    assert berlin.major and sydney.major and nyc.major
    assert not sp.major


def test_majors_reject_false_positives():
    # The membership token is just a city name, so a loose "token in title +
    # country" test mislabelled every same-city race. These must all be rejected:
    cases = [
        # Boston qualifier whose title says "Boston Marathon" but is held elsewhere
        _mk("I'm Bound For Boston Marathon – Seattle", "2026-06-14", "Olympia, WA, EUA", "WA", "US"),
        # A marathon merely held in the city, not the Major itself
        _mk("Lakefront Marathon", "2026-10-04", "Chicago, IL, EUA", "IL", "US"),
        # Same-city non-marathons: a 5K, a half, and (yes) an open-water swim
        _mk("Chicago Legends 5K", "2026-06-27", "Chicago, IL, EUA", "IL", "US", km=5.0),
        _mk("Chicago Half Marathon & 5K", "2026-09-27", "Chicago, IL, EUA", "IL", "US", km=21.097),
        _mk("Open Water Swim Chicago", "2026-07-07", "Chicago, IL, EUA", "IL", "US", km=8.0),
    ]
    for c in cases:
        es._apply_majors(c, _CUR_MAJORS)
        assert not c.major, c.titulo


def test_major_requires_country_match():
    # A "Tokyo"-named race in the wrong country must not become a Major.
    fake = _mk("Tokyo Run Brasil", "2026-03-07", "São Paulo", "SP", "BR")
    es._apply_majors(fake, _CUR_MAJORS)
    assert not fake.major


def test_majors_auto_adapt_to_membership():
    # If Wikidata stops listing a race, it stops being a Major next run —
    # and a newly-added race becomes one. No code change needed.
    only_sydney = _majors_from([{"name": "Sydney Marathon", "iso2": "AU"}])
    berlin = _mk("BMW Berlin Marathon", "2026-09-27", "Berlim", "BE", "DE")
    sydney = _mk("TCS Sydney Marathon", "2026-08-30", "Sydney", "NSW", "AU")
    es._apply_majors(berlin, only_sydney)
    es._apply_majors(sydney, only_sydney)
    assert sydney.major and not berlin.major


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
