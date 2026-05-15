"""Quick API probe: fetch a URL and dump its structure for source discovery.

Usage (CLI):
  python scripts/probe_url.py <url> [method] [params_json] [body_json] [headers_json]

Usage (config file — used by the probe branch CI loop):
  python scripts/probe_url.py --config probe-config.json

probe-config.json format (single):
  {"url": "https://...", "method": "GET", "params": {}, "body": null, "headers": {}}

probe-config.json format (multiple probes):
  [
    {"url": "https://...", "method": "GET"},
    {"url": "https://...", "method": "POST", "body": {"query": "..."}}
  ]

Outputs:
  - HTTP status code and content-type
  - JSON: recursive key/type/sample dump
  - HTML: __NEXT_DATA__ structure + embedded JSON scan
  - Raw response saved to probe-output/<slug>.txt
"""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).parent.parent))

from scraper.http_client import get, HEADERS, TIMEOUT  # noqa: E402
import httpx  # noqa: E402

OUT_DIR = Path("probe-output")


# ---------------------------------------------------------------------------
# Structure dumper
# ---------------------------------------------------------------------------

def _dump_json_structure(obj, prefix: str = "", depth: int = 0) -> list[str]:
    lines = []
    if depth > 4:
        lines.append(f"{prefix}  ...")
        return lines
    if isinstance(obj, dict):
        lines.append(f"{prefix}dict ({len(obj)} keys):")
        for i, (k, v) in enumerate(obj.items()):
            if i >= 20:
                lines.append(f"{prefix}  ... ({len(obj) - 20} more keys)")
                break
            vtype = type(v).__name__
            if isinstance(v, (dict, list)):
                lines.append(f"{prefix}  [{k!r}] ({vtype}):")
                lines.extend(_dump_json_structure(v, prefix + "    ", depth + 1))
            else:
                val = repr(v)
                if len(val) > 140:
                    val = val[:140] + "…"
                lines.append(f"{prefix}  [{k!r}] = {val}")
    elif isinstance(obj, list):
        lines.append(f"{prefix}list ({len(obj)} items):")
        if obj:
            lines.append(f"{prefix}  [0] sample:")
            lines.extend(_dump_json_structure(obj[0], prefix + "    ", depth + 1))
            if len(obj) > 1:
                lines.append(f"{prefix}  ... ({len(obj) - 1} more items)")
    else:
        lines.append(f"{prefix}{str(repr(obj))[:200]}")
    return lines


def _dump_next_data(html: str) -> list[str]:
    m = re.search(
        r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>',
        html, re.DOTALL,
    )
    if not m:
        return []
    try:
        data = json.loads(m.group(1))
        lines = ["\n=== __NEXT_DATA__ structure ==="]
        lines.extend(_dump_json_structure(data))
        return lines
    except Exception as e:
        return [f"  __NEXT_DATA__ parse error: {e}"]


def _find_embedded_json(html: str) -> list[str]:
    lines = []
    scripts = re.findall(r'<script[^>]*>(.*?)</script>', html, re.DOTALL)
    kw = {"name", "date", "startDate", "id", "title", "events"}
    for i, s in enumerate(scripts):
        s = s.strip()
        if not s:
            continue
        for pattern in [
            r'(\[\s*\{[^<]{50,}?\}\s*\])',
            r'window\.__(?:data|state|props|INITIAL_STATE)\s*=\s*(\{.*?\});',
        ]:
            for m in re.finditer(pattern, s, re.DOTALL):
                try:
                    parsed = json.loads(m.group(1))
                    sample = parsed[0] if isinstance(parsed, list) else parsed
                    if isinstance(sample, dict) and kw & set(sample.keys()):
                        lines.append(f"\n=== Embedded JSON in script[{i}] ===")
                        lines.extend(_dump_json_structure(parsed))
                except Exception:
                    pass
    return lines


# ---------------------------------------------------------------------------
# Single probe
# ---------------------------------------------------------------------------

def run_probe(cfg: dict) -> list[str]:
    url     = cfg["url"]
    method  = cfg.get("method", "GET").upper()
    params  = cfg.get("params") or {}
    body    = cfg.get("body")
    extra_h = cfg.get("headers") or {}

    lines = [
        "",
        f"{'=' * 60}",
        f"  {method} {url}",
        f"{'=' * 60}",
    ]
    if params:  lines.append(f"  params:  {json.dumps(params)}")
    if body:    lines.append(f"  body:    {json.dumps(body)[:200]}")
    if extra_h: lines.append(f"  headers: {json.dumps(extra_h)}")

    try:
        if method == "POST":
            merged = {**HEADERS, "Content-Type": "application/json", **extra_h}
            resp = httpx.post(
                url, json=body, params=params, headers=merged,
                follow_redirects=True, timeout=TIMEOUT,
            )
            lines.append(f"\n[direct POST] HTTP {resp.status_code}")
        else:
            kw = {}
            if params:  kw["params"] = params
            if extra_h: kw["headers"] = extra_h
            resp = get(url, source="probe", timeout=30, **kw)
            lines.append(f"\n[get chain]   HTTP {resp.status_code}")
    except Exception as e:
        lines.append(f"\nERROR: {e}")
        return lines

    ct = resp.headers.get("content-type", "")
    lines += [
        f"  Content-Type:   {ct}",
        f"  Response size:  {len(resp.content)} bytes",
    ]

    # Save full raw response
    OUT_DIR.mkdir(exist_ok=True)
    slug = re.sub(r"[^\w]", "_", urlparse(url).netloc + urlparse(url).path)[:60]
    raw_path = OUT_DIR / f"{slug}.txt"
    raw_path.write_bytes(resp.content)
    lines.append(f"  Full response → probe-output/{raw_path.name}")

    if "json" in ct:
        try:
            data = resp.json()
            lines.append("\n--- JSON structure ---")
            lines.extend(_dump_json_structure(data))
        except Exception as e:
            lines.append(f"JSON parse error: {e}")
            lines.append("Raw (first 500):" + resp.text[:500])
    elif "html" in ct or resp.text.lstrip().startswith("<"):
        lines.append(f"\n--- HTML page ({len(resp.text)} chars) ---")
        nd = _dump_next_data(resp.text)
        if nd:
            lines.extend(nd)
        else:
            lines.append("  No __NEXT_DATA__ found.")
            emb = _find_embedded_json(resp.text)
            if emb:
                lines.extend(emb)
            else:
                lines.append("  No embedded JSON found.")
            lines.append("\n--- First 1000 chars of HTML ---")
            lines.append(resp.text[:1000])
    else:
        lines.append("\n--- Raw response (first 1000 chars) ---")
        lines.append(resp.text[:1000])

    return lines


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    args = sys.argv[1:]

    if args and args[0] == "--config":
        # Config-file mode: read probe-config.json
        config_path = Path(args[1] if len(args) > 1 else "probe-config.json")
        raw = json.loads(config_path.read_text())
        configs = raw if isinstance(raw, list) else [raw]
    elif args:
        # CLI mode: probe_url.py <url> [method] [params] [body] [headers]
        configs = [{
            "url":     args[0],
            "method":  args[1] if len(args) > 1 else "GET",
            "params":  json.loads(args[2]) if len(args) > 2 and args[2].strip() else {},
            "body":    json.loads(args[3]) if len(args) > 3 and args[3].strip() else None,
            "headers": json.loads(args[4]) if len(args) > 4 and args[4].strip() else {},
        }]
    else:
        print("Usage: probe_url.py <url> [method] [params_json] [body_json] [headers_json]")
        print("       probe_url.py --config probe-config.json")
        sys.exit(1)

    all_lines = [f"# Probe results — {len(configs)} request(s)\n"]
    for cfg in configs:
        all_lines.extend(run_probe(cfg))

    output = "\n".join(all_lines)
    print(output)

    # Also write summary to probe-output/result.md
    OUT_DIR.mkdir(exist_ok=True)
    (OUT_DIR / "result.md").write_text(output, encoding="utf-8")


if __name__ == "__main__":
    main()
