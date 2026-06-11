"""
Pytest fixtures for end-to-end site tests.

Starts a local HTTP server on port 8765 serving the web/ directory and
provides browser fixtures with geo mocking.
"""
import json
import threading
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
import pytest

WEB_DIR = Path(__file__).parent.parent / "web"
SERVER_PORT = 8765
GEO_FAKE = {"country_code": "BR", "region_code": "SP", "city": "São Paulo", "latitude": -23.5, "longitude": -46.6}


class _Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_DIR), **kwargs)

    def log_message(self, *args):
        pass  # suppress server logs during tests


@pytest.fixture(scope="session")
def live_server():
    server = ThreadingHTTPServer(("127.0.0.1", SERVER_PORT), _Handler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{SERVER_PORT}"
    server.shutdown()


def _add_geo_mocks(context):
    """Make the browser context deterministic and self-contained for e2e tests.

    A single catch-all route handles every request the page issues:

    * IP-geolocation APIs (ipwho.is / freeipapi.com / api.ip.sb) are fulfilled
      with a fixed São Paulo response so the location pipeline is deterministic.
    * Same-origin requests (the local test server on 127.0.0.1 / localhost) are
      allowed through untouched — that's the site we're actually testing.
    * Every other (third-party) request is aborted. Event-photo CDNs, Google
      Fonts and similar resources are irrelevant to what the tests assert, and
      a single slow/hanging external host would otherwise keep ``networkidle``
      from ever settling, timing out ``page.goto`` after 30s. Aborting them is
      what makes the suite independent of third-party uptime — not a test
      shortcut, but the removal of an external dependency we don't control.

    Using one combined handler (instead of separate geo routes plus a catch-all)
    avoids any dependence on Playwright's route-matching order.
    """
    fake_body = json.dumps(GEO_FAKE)
    _GEO_HOSTS = ("ipwho.is", "freeipapi.com", "api.ip.sb")

    def handle(route, request):
        url = request.url
        if any(h in url for h in _GEO_HOSTS):
            route.fulfill(status=200, content_type="application/json", body=fake_body)
        elif "127.0.0.1" in url or "localhost" in url:
            route.continue_()
        else:
            route.abort()

    context.route("**/*", handle)


def pytest_collection_modifyitems(items):
    """Inject each test's docstring into user_properties for the JSON report."""
    for item in items:
        doc = getattr(item.obj, "__doc__", None)
        if doc:
            first_line = doc.strip().split("\n")[0].strip()
            if first_line:
                item.user_properties.append(("description", first_line))


@pytest.fixture
def page_pt(browser, live_server):
    ctx = browser.new_context(locale="pt-BR")
    _add_geo_mocks(ctx)
    page = ctx.new_page()
    page.goto(live_server + "/pt/", wait_until="networkidle")
    page.wait_for_selector(".card:not(.prerender)", state="attached", timeout=15000)
    yield page
    ctx.close()


@pytest.fixture
def page_en(browser, live_server):
    ctx = browser.new_context(locale="en-US")
    _add_geo_mocks(ctx)
    page = ctx.new_page()
    page.goto(live_server + "/en/", wait_until="networkidle")
    page.wait_for_selector(".card:not(.prerender)", state="attached", timeout=15000)
    yield page
    ctx.close()


@pytest.fixture
def page_factory(browser, live_server):
    """Factory yielding a page for the requested UI language ('pt', 'en', 'es', 'de', 'fr')."""
    _locales = {"pt": "pt-BR", "en": "en-US", "es": "es-ES", "de": "de-DE", "fr": "fr-FR"}
    contexts = []

    def make(lang: str):
        ctx = browser.new_context(locale=_locales[lang])
        _add_geo_mocks(ctx)
        page = ctx.new_page()
        page.goto(live_server + f"/{lang}/", wait_until="networkidle")
        page.wait_for_selector(".card:not(.prerender)", state="attached", timeout=15000)
        contexts.append(ctx)
        return page

    yield make
    for ctx in contexts:
        ctx.close()
