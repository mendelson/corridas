from __future__ import annotations
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


# GitHub-hosted runners have no IPv6 route. Dual-stack hosts (e.g. Hostinger,
# which serves correrbrasilia.com.br with an AAAA record) intermittently get
# resolved AAAA-first, and connect() dies with ENETUNREACH (Errno 101) before
# any HTTP exchange. Binding the local side to 0.0.0.0 forces AF_INET, and
# transport-level retries absorb one-off connect hiccups.
def _request(url: str, headers: dict, verify: bool, timeout, **kwargs) -> httpx.Response:
    transport = httpx.HTTPTransport(verify=verify, retries=2, local_address="0.0.0.0")
    with httpx.Client(
        transport=transport, headers=headers,
        follow_redirects=True, timeout=timeout,
    ) as client:
        return client.get(url, **kwargs)


def get(url: str, **kwargs) -> httpx.Response:
    """HTTP GET with browser-like headers.

    Every scraper calls this. The request is made directly with httpx; there is
    no third-party proxy layer. When a site answers with a WAF status
    (403/406/429) this raises ``httpx.HTTPStatusError`` so the caller can fall
    through to Playwright (``scraper/playwright_client.py``), which still does
    basic anti-bot evasion.

    extra_headers={...} merges per-call header overrides on top of HEADERS —
    needed by JSON/XHR endpoints that reject document-style requests (e.g.
    raceroster's search API answers 202 with an empty body unless it sees
    Accept: application/json + a same-origin Referer/Origin).
    """
    # Pop kwargs that are not httpx-native
    kwargs.pop("source", None)
    verify        = kwargs.pop("verify", True)
    timeout       = kwargs.pop("timeout", TIMEOUT)
    extra_headers = kwargs.pop("extra_headers", None)
    headers       = {**HEADERS, **extra_headers} if extra_headers else HEADERS

    resp = _request(url, headers, verify, timeout, **kwargs)
    if resp.status_code in _WAF_STATUSES:
        domain = urllib.parse.urlparse(url).netloc
        raise httpx.HTTPStatusError(
            f"{domain} bloqueado ({resp.status_code})",
            request=resp.request, response=resp,
        )
    return resp


def get_direct(url: str, **kwargs) -> httpx.Response:
    """HTTP GET without WAF-raising — for optional/non-critical requests."""
    kwargs.pop("source", None)
    timeout = kwargs.pop("timeout", TIMEOUT)
    verify = kwargs.pop("verify", True)
    extra_headers = kwargs.pop("extra_headers", None)
    headers = {**HEADERS, **extra_headers} if extra_headers else HEADERS
    return _request(url, headers, verify, timeout, **kwargs)


# Kept for backward compatibility — get() is the single entry point.
get_with_fallback = get
