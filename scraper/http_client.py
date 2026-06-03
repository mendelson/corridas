from __future__ import annotations
import os
import urllib.parse
import httpx

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
}

TIMEOUT = 30
_WAF_STATUSES = {403, 406, 429}

SCRAPESTACK_KEY      = os.getenv("SCRAPESTACK_KEY", "")
APIFY_PROXY_PASSWORD = os.getenv("APIFY_PROXY_PASSWORD", "") or os.getenv("APIFY_TOKEN", "")


def get(url: str, **kwargs) -> httpx.Response:
    """HTTP GET with automatic WAF fallback: direct → Scrapestack → Apify proxy.

    All scrapers use this function. Fallback is transparent and requires no
    per-scraper configuration. New scrapers get it automatically.

    render_js=True passes &render_js=1 to Scrapestack so it executes JavaScript
    before returning the page — needed for Cloudflare-protected JS-challenge sites.
    """
    # Pop kwargs that are not httpx-native
    kwargs.pop("source", None)
    verify     = kwargs.pop("verify", True)
    timeout    = kwargs.pop("timeout", TIMEOUT)
    render_js  = kwargs.pop("render_js", False)

    _domain = urllib.parse.urlparse(url).netloc

    # 1. Direct request
    try:
        resp = httpx.get(
            url, headers=HEADERS, follow_redirects=True,
            verify=verify, timeout=timeout, **kwargs,
        )
        if resp.status_code not in _WAF_STATUSES:
            return resp
        print(f"[proxy] {_domain} bloqueado ({resp.status_code}), tentando Scrapestack...")
    except (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError) as e:
        print(f"[proxy] {_domain} falhou diretamente ({type(e).__name__}: {e}), tentando Scrapestack...")

    # 2. Scrapestack
    if SCRAPESTACK_KEY:
        try:
            ss_url = (
                "http://api.scrapestack.com/scrape"
                f"?access_key={SCRAPESTACK_KEY}"
                f"&url={urllib.parse.quote(url, safe='')}"
                + ("&render_js=1" if render_js else "")
            )
            resp = httpx.get(ss_url, headers=HEADERS, follow_redirects=True, timeout=timeout)
            if resp.status_code < 400:
                print(f"[proxy] {_domain} obtido via Scrapestack")
                return resp
            print(f"[proxy] Scrapestack retornou {resp.status_code} para {_domain}, tentando Apify...")
        except Exception as e:
            print(f"[proxy] Scrapestack falhou para {_domain}: {e}")

    # 3. Apify proxy
    if APIFY_PROXY_PASSWORD:
        try:
            resp = httpx.get(
                url,
                headers=HEADERS,
                follow_redirects=True,
                timeout=timeout,
                proxy=f"http://auto:{APIFY_PROXY_PASSWORD}@proxy.apify.com:8000",
            )
            if resp.status_code < 400:
                print(f"[proxy] {_domain} obtido via Apify")
                return resp
            print(f"[proxy] Apify retornou {resp.status_code} para {_domain}")
        except Exception as e:
            print(f"[proxy] Apify falhou para {_domain}: {e}")

    raise httpx.HTTPStatusError(
        f"todos os métodos falharam para {url}",
        request=httpx.Request("GET", url),
        response=httpx.Response(503),
    )


def get_direct(url: str, **kwargs) -> httpx.Response:
    """HTTP GET without proxy fallback — for optional/non-critical requests."""
    kwargs.pop("source", None)
    kwargs.setdefault("timeout", TIMEOUT)
    return httpx.get(url, headers=HEADERS, follow_redirects=True, **kwargs)


# Kept for backward compatibility — get() already includes fallback
get_with_fallback = get
