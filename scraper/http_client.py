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

SCRAPESTACK_KEY = os.getenv("SCRAPESTACK_KEY", "")
APIFY_TOKEN = os.getenv("APIFY_TOKEN", "")


def get(url: str, **kwargs) -> httpx.Response:
    kwargs.setdefault("timeout", TIMEOUT)
    return httpx.get(url, headers=HEADERS, follow_redirects=True, **kwargs)


def get_with_fallback(url: str, source: str = "") -> httpx.Response:
    """Direct request first; on WAF block (403/429) falls back to Scrapestack then Apify."""
    tag = f"[{source}] " if source else ""

    # 1. Direct
    try:
        resp = get(url)
        if resp.status_code not in _WAF_STATUSES:
            return resp
        print(f"{tag}bloqueado ({resp.status_code}), tentando proxies...")
    except (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError):
        raise

    # 2. Scrapestack
    if SCRAPESTACK_KEY:
        try:
            proxy_url = (
                "https://api.scrapestack.com/scrape"
                f"?access_key={SCRAPESTACK_KEY}"
                f"&url={urllib.parse.quote(url, safe='')}"
            )
            resp = get(proxy_url)
            if resp.status_code < 400:
                print(f"{tag}obtido via Scrapestack")
                return resp
            print(f"{tag}Scrapestack retornou {resp.status_code}")
        except Exception as e:
            print(f"{tag}Scrapestack falhou: {e}")

    # 3. Apify proxy
    if APIFY_TOKEN:
        try:
            resp = httpx.get(
                url,
                headers=HEADERS,
                follow_redirects=True,
                timeout=TIMEOUT,
                proxy=f"http://auto:{APIFY_TOKEN}@proxy.apify.com:8000",
            )
            if resp.status_code < 400:
                print(f"{tag}obtido via Apify")
                return resp
            print(f"{tag}Apify retornou {resp.status_code}")
        except Exception as e:
            print(f"{tag}Apify falhou: {e}")

    raise httpx.HTTPStatusError(
        f"todos os métodos falharam para {url}",
        request=httpx.Request("GET", url),
        response=httpx.Response(503),
    )
