"""
Pytest fixtures for end-to-end site tests.

Starts a local HTTP server on port 8765 serving the web/ directory and
provides browser fixtures with geo mocking.
"""
import json
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
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
    server = HTTPServer(("127.0.0.1", SERVER_PORT), _Handler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{SERVER_PORT}"
    server.shutdown()


def _add_geo_mocks(context):
    """Route all IP-geolocation API calls to return a deterministic SP response."""
    fake_body = json.dumps(GEO_FAKE)

    def handle(route, request):
        route.fulfill(
            status=200,
            content_type="application/json",
            body=fake_body,
        )

    context.route("**/ipwho.is/**", handle)
    context.route("**/freeipapi.com/**", handle)
    context.route("**/api.ip.sb/**", handle)


@pytest.fixture
def page_pt(browser, live_server):
    ctx = browser.new_context(locale="pt-BR")
    _add_geo_mocks(ctx)
    page = ctx.new_page()
    page.goto(live_server + "/pt/", wait_until="networkidle")
    page.wait_for_selector(".card", timeout=15000)
    yield page
    ctx.close()


@pytest.fixture
def page_en(browser, live_server):
    ctx = browser.new_context(locale="en-US")
    _add_geo_mocks(ctx)
    page = ctx.new_page()
    page.goto(live_server + "/en/", wait_until="networkidle")
    page.wait_for_selector(".card", timeout=15000)
    yield page
    ctx.close()
