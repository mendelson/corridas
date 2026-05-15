"""Quick API probe: fetch a URL and dump its structure for source discovery.

Usage:
  python scripts/probe_url.py <url> [method] [params_json] [body_json] [headers_json]

Outputs:
  - HTTP status and response headers
  - If JSON: top-level keys + truncated sample of each value
  - If HTML: checks for __NEXT_DATA__ and dumps its structure; lists script tags
  - Full raw response saved to probe-output/response.txt
"""
from __future__ import annotations
import json
import os
import sys
from pathlib import Path

# Add repo root to path so scraper package is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from scraper.http_client import get, HEADERS, TIMEOUT  # noqa: E402
import httpx  # noqa: E402


def _dump_json_structure(obj, prefix: str = "", depth: int = 0) -> None:
    if depth > 4:
        print(f"{prefix}  ...")
        return
    if isinstance(obj, dict):
        print(f"{prefix}dict ({len(obj)} keys):")
        for i, (k, v) in enumerate(obj.items()):
            if i >= 15:
                print(f"{prefix}  ... ({len(obj) - 15} more keys)")
                break
            vtype = type(v).__name__
            if isinstance(v, (dict, list)):
                print(f"{prefix}  [{k!r}] ({vtype}):")
                _dump_json_structure(v, prefix + "    ", depth + 1)
            else:
                val_repr = repr(v)
                if len(val_repr) > 120:
                    val_repr = val_repr[:120] + "…"
                print(f"{prefix}  [{k!r}] = {val_repr}")
    elif isinstance(obj, list):
        print(f"{prefix}list ({len(obj)} items):")
        if obj:
            print(f"{prefix}  [0] sample:")
            _dump_json_structure(obj[0], prefix + "    ", depth + 1)
            if len(obj) > 1:
                print(f"{prefix}  ... ({len(obj) - 1} more items)")
    else:
        print(f"{prefix}{repr(obj)!s:.200}")


def _dump_next_data(html: str) -> bool:
    import re
    m = re.search(r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>', html, re.DOTALL)
    if not m:
        return False
    try:
        data = json.loads(m.group(1))
        print("\n=== __NEXT_DATA__ structure ===")
        _dump_json_structure(data)
        return True
    except Exception as e:
        print(f"  __NEXT_DATA__ parse error: {e}")
        return False


def _find_embedded_json(html: str) -> None:
    import re
    # Find script tags with JSON-like content
    scripts = re.findall(r'<script[^>]*>(.*?)</script>', html, re.DOTALL)
    for i, s in enumerate(scripts):
        s = s.strip()
        if not s:
            continue
        # Look for JSON arrays or objects with event-like keys
        for pattern in [
            r'(\[\s*\{[^<]{50,}?\}\s*\])',
            r'window\.__(?:data|state|props|INITIAL_STATE)\s*=\s*(\{.*?\});',
        ]:
            for m in re.finditer(pattern, s, re.DOTALL):
                try:
                    parsed = json.loads(m.group(1))
                    kw = {"name", "date", "startDate", "id", "title", "events"}
                    if isinstance(parsed, (dict, list)):
                        sample = parsed[0] if isinstance(parsed, list) else parsed
                        if isinstance(sample, dict) and kw & set(sample.keys()):
                            print(f"\n=== Embedded JSON in script[{i}] ===")
                            _dump_json_structure(parsed)
                except Exception:
                    pass


def main() -> None:
    args = sys.argv[1:]
    if not args:
        print("Usage: probe_url.py <url> [GET|POST] [params_json] [body_json] [headers_json]")
        sys.exit(1)

    url          = args[0]
    method       = (args[1] if len(args) > 1 else "GET").upper()
    params_json  = args[2] if len(args) > 2 else ""
    body_json    = args[3] if len(args) > 3 else ""
    headers_json = args[4] if len(args) > 4 else ""

    params  = json.loads(params_json)  if params_json.strip()  else {}
    body    = json.loads(body_json)    if body_json.strip()    else None
    extra_h = json.loads(headers_json) if headers_json.strip() else {}

    print(f"=== Probing: {method} {url} ===")
    if params:
        print(f"  params:  {params}")
    if body:
        print(f"  body:    {json.dumps(body)[:200]}")
    if extra_h:
        print(f"  headers: {extra_h}")
    print()

    try:
        if method == "POST":
            merged_headers = {**HEADERS, "Content-Type": "application/json", **extra_h}
            resp = httpx.post(url, json=body, params=params, headers=merged_headers,
                              follow_redirects=True, timeout=TIMEOUT)
            print(f"[direct POST] HTTP {resp.status_code}")
        else:
            resp = get(url, params=params, headers=extra_h if extra_h else {},
                       source="probe", timeout=30)
            print(f"[get chain]   HTTP {resp.status_code}")
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    print(f"  Content-Type: {resp.headers.get('content-type', '—')}")
    print(f"  Content-Length: {resp.headers.get('content-length', '—')} bytes")
    print(f"  Response size: {len(resp.content)} bytes")

    # Save full response
    out_dir = Path("probe-output")
    out_dir.mkdir(exist_ok=True)
    (out_dir / "response.txt").write_bytes(resp.content)
    print(f"\nFull response saved to probe-output/response.txt")

    ct = resp.headers.get("content-type", "")
    if "json" in ct:
        try:
            data = resp.json()
            print("\n=== JSON structure ===")
            _dump_json_structure(data)
        except Exception as e:
            print(f"JSON parse error: {e}")
            print("Raw (first 500 chars):", resp.text[:500])
    elif "html" in ct or resp.text.lstrip().startswith("<"):
        print("\n=== HTML page ===")
        print(f"  Length: {len(resp.text)} chars")
        found = _dump_next_data(resp.text)
        if not found:
            print("  No __NEXT_DATA__ found.")
            _find_embedded_json(resp.text)
            # Show first 1000 chars
            print("\n--- First 800 chars of response ---")
            print(resp.text[:800])
    else:
        print("\n--- Raw response (first 1000 chars) ---")
        print(resp.text[:1000])


if __name__ == "__main__":
    main()
