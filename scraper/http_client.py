from __future__ import annotations
import httpx

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
}

TIMEOUT = 30


def get(url: str, **kwargs) -> httpx.Response:
    return httpx.get(url, headers=HEADERS, timeout=TIMEOUT, follow_redirects=True, **kwargs)
