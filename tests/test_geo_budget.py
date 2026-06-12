"""The per-run Nominatim budget must stop hitting the network once spent.

Cache misses cost a serial ~1s Nominatim call each; an unbounded run can spend
hours geocoding and pin the CI runner. Once the budget is exhausted, resolve()
must return unresolved WITHOUT sleeping or making a network call (the event is
dropped this run and resolved later as the persistent cache fills).
"""
import pytest

geo = pytest.importorskip("scraper.geo")


def test_budget_exhausted_skips_network(monkeypatch):
    monkeypatch.setattr(geo, "_MAX_LOOKUPS", 0)
    monkeypatch.setattr(geo, "_lookup_count", 0)
    monkeypatch.setattr(geo, "_budget_warned", False)
    # If the budget gate fails, resolve() would sleep before the network call —
    # make that an immediate, loud failure.
    monkeypatch.setattr(
        geo.time, "sleep",
        lambda *a, **k: pytest.fail("resolve() must not sleep/network once budget is spent"))

    # A city that cannot be in the committed cache → forced miss → budget gate.
    pais, estado = geo.resolve("Zzxqv Nonexistent Place 99181", "", "BR")
    assert (pais, estado) == ("BR", ""), (pais, estado)


def test_under_budget_increments_counter(monkeypatch):
    """Below the limit, a miss is allowed through (counter increments); we stub
    the network so the test stays offline."""
    httpx = pytest.importorskip("httpx")  # only installed in the scraper env
    monkeypatch.setattr(geo, "_MAX_LOOKUPS", 5)
    monkeypatch.setattr(geo, "_lookup_count", 0)
    monkeypatch.setattr(geo.time, "sleep", lambda *a, **k: None)

    class _Resp:
        @staticmethod
        def json():
            return []  # empty → resolve returns the hint, no cache write

    monkeypatch.setattr(httpx, "get", lambda *a, **k: _Resp())

    pais, estado = geo.resolve("Another Uncached Town 44120", "", "US")
    assert pais == "US"
    assert geo._lookup_count == 1
