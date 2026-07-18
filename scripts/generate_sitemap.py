"""Generate web/sitemap.xml for the multilingual static site.

The site ships five language shells (web/{lang}/index.html) that are
equivalent translations of the same calendar. Search engines need a sitemap
that (a) lists every localized home and (b) declares the reciprocal hreflang
alternates so the right language is served per region instead of being treated
as duplicate content.

`lastmod` tracks the freshness of the underlying data (web/corridas.json), so
the sitemap is regenerated on every scrape by the data pipeline.

Run standalone:  python scripts/generate_sitemap.py
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

# Canonical production origin. Every absolute URL is anchored here.
BASE = "https://run.mmendelson.com"

# UI language path prefix -> hreflang code. The path prefix is what appears in
# the URL (/pt/, /en/ …); the hreflang code is the BCP-47 tag search engines
# match against. pt is region-qualified (pt-BR) because the audience is Brazil.
LANGS: list[tuple[str, str]] = [
    ("pt", "pt-BR"),
    ("en", "en"),
    ("es", "es"),
    ("de", "de"),
    ("fr", "fr"),
]

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"


def _lastmod() -> str:
    """Date of the most recent data refresh, as YYYY-MM-DD."""
    data_file = WEB / "corridas.json"
    if data_file.exists():
        ts = data_file.stat().st_mtime
        return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
    return date.today().isoformat()


def _alternates() -> str:
    """The shared <xhtml:link> block: every language + x-default.

    Declared identically inside every <url> entry, as required for reciprocal
    hreflang annotations.
    """
    links = [
        f'    <xhtml:link rel="alternate" hreflang="{code}" '
        f'href="{escape(f"{BASE}/{prefix}/")}"/>'
        for prefix, code in LANGS
    ]
    links.append(
        f'    <xhtml:link rel="alternate" hreflang="x-default" href="{escape(BASE + "/")}"/>'
    )
    return "\n".join(links)


def build_sitemap() -> str:
    lastmod = _lastmod()
    alternates = _alternates()
    entries = []
    for prefix, _code in LANGS:
        loc = escape(f"{BASE}/{prefix}/")
        entries.append(
            "  <url>\n"
            f"    <loc>{loc}</loc>\n"
            f"    <lastmod>{lastmod}</lastmod>\n"
            f"{alternates}\n"
            "  </url>"
        )
    # The gallery is a single-URL page (it self-localizes on the same URL, so
    # no hreflang cluster). Listed in the sitemap but not linked from the app —
    # it is reached directly.
    entries.append(
        "  <url>\n"
        f"    <loc>{escape(f'{BASE}/gallery/')}</loc>\n"
        f"    <lastmod>{lastmod}</lastmod>\n"
        "  </url>"
    )
    body = "\n".join(entries)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"\n'
        '        xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
        f"{body}\n"
        "</urlset>\n"
    )


def main() -> None:
    out = WEB / "sitemap.xml"
    out.write_text(build_sitemap(), encoding="utf-8")
    print(f"wrote {out.relative_to(ROOT)} ({len(LANGS)} localized URLs)")


if __name__ == "__main__":
    main()
