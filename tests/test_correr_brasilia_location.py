"""Regression: correr_brasilia must read the EventOn HTML venue when JSON-LD
location is null.

Real case (reported by the maintainer, 2026-06-12): "CPTR - Copa Vale dos
Pireneus Trail Running" — page shows "Beira Rio, Pirenópolis-GO" in
em.evcal_location[data-n], JSON-LD location is null; the scraper defaulted to
"Brasília, DF" and the site displayed the wrong state.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from scraper.sources import correr_brasilia as cb
except ImportError as exc:  # pragma: no cover — frontend test job lacks scraper deps
    pytest.skip(f"dependências do scraper indisponíveis: {exc}",
                allow_module_level=True)


def test_locline_city_uf_parsing():
    assert cb._city_uf_from_locline("Beira Rio, Pirenópolis-GO") == ("Pirenópolis", "GO")
    assert cb._city_uf_from_locline("Praça Central, Formosa - GO") == ("Formosa", "GO")
    # Venue-only / undefined lines must NOT produce a bogus UF
    assert cb._city_uf_from_locline("A definir") == ("", "")
    assert cb._city_uf_from_locline("Esplanada dos Ministérios") == ("", "")


def test_null_jsonld_location_falls_back_to_html_venue():
    from datetime import date, timedelta
    futuro = (date.today() + timedelta(days=30)).isoformat()
    ev = {
        "@type": "Event",
        "@id": "event_44049_0",
        "name": "CPTR - COPA VALE DOS PIRENEUS TRAIL RUNNING",
        "startDate": f"{futuro}T08:00:00",
        "url": "https://correrbrasilia.com.br/events/cptr/",
        "location": None,
    }
    c = cb._parse_event(ev, "2026-01-01", "2026-01-01T00:00:00+00:00",
                        html_loc="Beira Rio, Pirenópolis-GO")
    assert c is not None
    assert (c.cidade, c.estado) == ("Pirenópolis", "GO")

    # Sem html_loc, o default de calendário-DF continua valendo
    c2 = cb._parse_event(dict(ev), "2026-01-01", "2026-01-01T00:00:00+00:00")
    assert (c2.cidade, c2.estado) == ("Brasília", "DF")
