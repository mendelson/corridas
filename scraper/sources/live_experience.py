"""DIAGNOSTIC probe — LIVE! Experience (appliveexperience.com.br) events API.

The site is an Expo/React SPA whose bundle calls a public, anonymous API:
    GET https://api.appliveexperience.com.br/app/events?page=N&limit=50&finished=false
(the Authorization header is only added when a user token exists). Direct httpx
from GitHub Actions gets HTTP 403 from the AWS ELB/WAF. This module exists only
to test whether the Playwright fallback (real browser engine) gets through, and
to dump the JSON shape. It returns [] — read the CI log for the verdict.
"""
from __future__ import annotations
import json
import re

from ..models import Corrida  # noqa: F401  (kept for the scrape() return type)

API = ("https://api.appliveexperience.com.br/app/events"
       "?page=1&limit=50&finished=false")
HDRS = {
    "Accept": "application/json, text/plain, */*",
    "expo-platform": "web",
    "Origin": "https://appliveexperience.com.br",
    "Referer": "https://appliveexperience.com.br/",
}


def _httpx_body() -> str | None:
    try:
        from ..http_client import get
        try:
            r = get(API, extra_headers=HDRS)
        except TypeError:
            r = get(API)  # older get() without extra_headers
        print(f"[httpx]      HTTP {r.status_code}  ({len(r.text)} bytes)")
        return r.text if r.status_code == 200 else None
    except Exception as exc:  # WAF raise / network / etc.
        print(f"[httpx]      blocked/error: {type(exc).__name__}: {str(exc)[:120]}")
        return None


def _playwright_body() -> str | None:
    try:
        from .. import playwright_client
        html = playwright_client.get_page_html(API, wait="domcontentloaded")
    except Exception as exc:
        print(f"[playwright] error: {type(exc).__name__}: {str(exc)[:120]}")
        return None
    if not html:
        print("[playwright] None (blocked or timeout)")
        return None
    if "403 Forbidden" in html or "<title>403" in html:
        print(f"[playwright] still WAF 403 ({len(html)} bytes)")
        return None
    print(f"[playwright] got {len(html)} bytes (WAF bypassed!)")
    m = re.search(r"(\{.*\}|\[.*\])", html, re.S)
    return m.group(1) if m else html


def scrape() -> list:
    print("=== LIVE! Experience API diagnostic ===")
    print(f"URL: {API}")
    body = _httpx_body() or _playwright_body()
    if not body:
        print("VERDICT: API unreachable from CI (httpx AND playwright blocked by WAF).")
        return []
    try:
        data = json.loads(body)
        root = data if isinstance(data, list) else (
            data.get("data") or data.get("events") or data.get("results") or data)
        print(f"VERDICT: JSON OK. top={type(data).__name__} "
              f"items={len(root) if isinstance(root, list) else 'n/a'}")
        first = root[0] if isinstance(root, list) and root else root
        print("FIRST ITEM:", json.dumps(first, ensure_ascii=False)[:1800])
    except Exception as exc:
        print(f"VERDICT: got body but JSON parse failed: {exc}; head={body[:400]!r}")
    return []
