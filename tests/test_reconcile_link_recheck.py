"""Regression test for reconcile's link recheck (_check_and_refresh_links).

A future event whose page is alive must NOT be counted as a miss — even when the
page is behind a WAF (Cloudflare 403/429), or reachable only via link_evento and
not links_inscricao (the inscription URL can 404 once registration closes). Only
a hard 404/410 or a connection failure means the page is actually gone.
"""
from __future__ import annotations

import pytest

pytest.importorskip("httpx")  # scraper deps (httpx) are only installed in the scraper env

import scraper.main as main
from scraper.models import Corrida, FonteInfo


def _event(*, link_evento: str = "", insc: list[str] | None = None) -> Corrida:
    return Corrida(
        id="x", titulo="T", data_evento="2099-01-01", horario=None,
        localizacao="L", cidade="C", estado="DF", pais="BR", distancias=[],
        imagem_url="already-set", inscricoes_abertas=None, periodo_inscricao=None,
        fontes=[FonteInfo(nome="S", link_evento=link_evento,
                          links_inscricao=insc or [], tipo="inscricao")],
        miss_count=0, first_seen_at="", updated_at="",
    )


class _Resp:
    def __init__(self, status_code: int):
        self.status_code = status_code
        self.text = ""


def test_waf_status_counts_as_alive(monkeypatch):
    for status in (403, 406, 429, 503):
        monkeypatch.setattr(main, "http_get_direct", lambda url, **k: _Resp(status))
        assert main._check_and_refresh_links(_event(insc=["https://x/e/1"])) is True


def test_hard_404_counts_as_dead(monkeypatch):
    monkeypatch.setattr(main, "http_get_direct", lambda url, **k: _Resp(404))
    assert main._check_and_refresh_links(_event(insc=["https://x/e/1"])) is False


def test_link_evento_is_checked_not_only_inscricao(monkeypatch):
    monkeypatch.setattr(main, "http_get_direct", lambda url, **k: _Resp(200))
    assert main._check_and_refresh_links(_event(link_evento="https://x/e/1")) is True


def test_connection_failure_counts_as_dead(monkeypatch):
    def boom(url, **k):
        raise RuntimeError("connection refused")
    monkeypatch.setattr(main, "http_get_direct", boom)
    assert main._check_and_refresh_links(_event(insc=["https://x/e/1"])) is False
