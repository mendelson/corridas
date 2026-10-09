"""Regression: atletis must not scrape (or emit) the same event id twice.

Real case (monitor run 2026-10-08, failing since 2026-10-03): the
/events/coordinates map listed one event more than once, so the scraper emitted
``atletis_4966`` twice and ``test_source`` failed with "IDs duplicados no batch".
The Corrida id comes only from the trailing number of the event URL, so
candidates are de-duplicated by that number before any page is fetched.
"""
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from scraper.sources import atletis
except ImportError as exc:  # pragma: no cover — frontend test job lacks scraper deps
    pytest.skip(f"dependências do scraper indisponíveis: {exc}",
                allow_module_level=True)


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def _feature(path, name="Corrida Teste", when=None):
    when = when or (date.today() + timedelta(days=30)).strftime("%d/%m/%Y")
    return {"properties": {"url": path, "name": name, "date": when}}


def test_duplicate_map_entries_are_fetched_once(monkeypatch):
    features = [
        _feature("/evento/corrida-teste-4966"),
        _feature("/evento/corrida-teste-4966/"),   # same event, trailing slash
        _feature("/evento/outro-slug-4966"),        # same numeric id, other slug
        _feature("/evento/outra-corrida-5000"),
    ]
    monkeypatch.setattr(atletis, "get",
                        lambda *a, **k: _Resp({"features": features}))

    fetched = []

    def fake_scrape_event(url, hint_name, today, now):
        fetched.append(url)
        return atletis.Corrida(
            id=f"atletis_{atletis._extract_id(url)}", titulo=hint_name,
            data_evento=today, horario=None, localizacao="X", cidade="X",
            estado="SP", pais="BR", distancias=[], imagem_url=None,
            inscricoes_abertas=True, periodo_inscricao=None, fontes=[],
            miss_count=0, first_seen_at=now, updated_at=now,
        )

    monkeypatch.setattr(atletis, "_scrape_event", fake_scrape_event)

    result = atletis.scrape()

    ids = [c.id for c in result]
    assert sorted(ids) == ["atletis_4966", "atletis_5000"]
    assert len(fetched) == 2
