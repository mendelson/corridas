"""Shared Playwright helper with basic bot-detection evasion."""
from __future__ import annotations

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# Minimal JS injected before page load to hide automation signals
_STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'languages', {get: () => ['pt-BR', 'pt', 'en-US', 'en']});
window.chrome = {runtime: {}};
"""


def get_page_html(url: str, timeout: int = 30_000, wait: str = "networkidle") -> str | None:
    """Return rendered HTML for *url* using a stealth Chromium browser, or None on failure."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled"],
            )
            ctx = browser.new_context(
                user_agent=_USER_AGENT,
                viewport={"width": 1280, "height": 720},
                locale="pt-BR",
                extra_http_headers={"Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8"},
            )
            page = ctx.new_page()
            page.add_init_script(_STEALTH_JS)
            # Wait only for the DOM, never the full "load" event: many target sites
            # hang on a third-party subresource (ads, analytics, slow CDN images)
            # that never completes, so goto() with the default wait_until="load"
            # raises a 30s timeout even though the page's HTML is already there.
            # domcontentloaded returns as soon as the document is parsed; the
            # best-effort wait_for_load_state below then gives client-rendered
            # content a chance to settle without ever blocking the result.
            page.goto(url, timeout=timeout, wait_until="domcontentloaded")
            try:
                page.wait_for_load_state(wait, timeout=timeout)
            except Exception:
                pass  # timeout on networkidle is OK — grab whatever rendered
            html = page.content()
            browser.close()
        return html
    except Exception as e:
        print(f"[playwright] {url}: {e}")
        return None
