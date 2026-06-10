"""Generate pre-rendered event content + JSON-LD into the language shells.

The site is a client-side SPA: without this, the initial HTML carries zero
event content and search engines index an empty shell. Since the data exists
at build time (web/corridas.json), this script injects, into each
web/{lang}/index.html, between HTML markers:

  1. a static, semantic list of the next upcoming events inside
     <main id="cardsList"> — app.js clears and re-renders this container on
     boot, so the pre-render is what crawlers (and users on slow connections)
     see first, and the SPA behaviour is unchanged;
  2. a schema.org ItemList of SportsEvent entries (JSON-LD) enabling rich
     results.

Both blocks are identical in *content* across languages (same events), only
the shell around them is localized — same-content alternates, not cloaking.

Run after each scrape (data pipeline) so the events stay fresh:
  python scripts/generate_prerender.py
"""
from __future__ import annotations

import html
import json
import re
from datetime import date
from pathlib import Path

from generate_sitemap import LANGS  # single source of truth

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"

MAX_EVENTS = 120

PRERENDER_START = "<!-- prerender:events:start -->"
PRERENDER_END = "<!-- prerender:events:end -->"
JSONLD_START = "<!-- prerender:jsonld:start -->"
JSONLD_END = "<!-- prerender:jsonld:end -->"


def _fmt_km(km) -> str:
    """Mirror the frontend's formatKm: floats become NK, strings pass through."""
    if isinstance(km, str):
        return km
    if km == int(km):
        return f"{int(km)}K"
    return f"{km:g}K"


def _event_link(ev: dict) -> str:
    for fonte in ev.get("fontes") or []:
        links = fonte.get("links_inscricao") or []
        if links and links[0]:
            return links[0]
        if fonte.get("link_evento"):
            return fonte["link_evento"]
    return ""


def select_events(corridas: list[dict], today: str) -> list[dict]:
    upcoming = [c for c in corridas if (c.get("data_evento") or "") >= today]
    upcoming.sort(key=lambda c: c.get("data_evento") or "9999")
    return upcoming[:MAX_EVENTS]


def build_html(events: list[dict]) -> str:
    parts = []
    for ev in events:
        titulo = html.escape(ev.get("titulo") or "")
        data_ev = html.escape(ev.get("data_evento") or "")
        loc = html.escape(ev.get("localizacao") or "")
        dists = " · ".join(
            html.escape(_fmt_km(d.get("km")))
            for d in (ev.get("distancias") or []) if d.get("km") is not None
        )
        link = html.escape(_event_link(ev))
        title_html = f'<a href="{link}" rel="nofollow">{titulo}</a>' if link else titulo
        parts.append(
            "<article>"
            f"<h3>{title_html}</h3>"
            f"<p><time datetime=\"{data_ev}\">{data_ev}</time> — {loc}</p>"
            + (f"<p>{dists}</p>" if dists else "")
            + "</article>"
        )
    return "\n".join(parts)


def build_jsonld(events: list[dict]) -> str:
    items = []
    for i, ev in enumerate(events, start=1):
        item = {
            "@type": "SportsEvent",
            "name": ev.get("titulo") or "",
            "sport": "Running",
            "startDate": ev.get("data_evento") or "",
            "eventStatus": "https://schema.org/EventScheduled",
            "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode",
            "location": {
                "@type": "Place",
                "name": ev.get("localizacao") or "",
                "address": {
                    "@type": "PostalAddress",
                    "addressLocality": (ev.get("cidade") or "").split(",")[0],
                    "addressRegion": ev.get("estado") or "",
                    "addressCountry": ev.get("pais") or "",
                },
            },
        }
        link = _event_link(ev)
        if link:
            item["url"] = link
        if ev.get("imagem_url"):
            item["image"] = ev["imagem_url"]
        items.append({"@type": "ListItem", "position": i, "item": item})
    data = {"@context": "https://schema.org", "@type": "ItemList",
            "numberOfItems": len(items), "itemListElement": items}
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def _replace_block(text: str, start: str, end: str, payload: str, path: Path) -> str:
    pattern = re.compile(re.escape(start) + r".*?" + re.escape(end), re.DOTALL)
    if not pattern.search(text):
        raise SystemExit(f"{path}: markers {start} … {end} not found")
    return pattern.sub(start + "\n" + payload + "\n" + end, text)


def main() -> None:
    data = json.loads((WEB / "corridas.json").read_text(encoding="utf-8"))
    corridas = data["corridas"] if isinstance(data, dict) else data
    events = select_events(corridas, date.today().isoformat())
    html_block = build_html(events)
    jsonld_block = f'<script type="application/ld+json">{build_jsonld(events)}</script>'

    for prefix, _code in LANGS:
        path = WEB / prefix / "index.html"
        text = path.read_text(encoding="utf-8")
        text = _replace_block(text, PRERENDER_START, PRERENDER_END, html_block, path)
        text = _replace_block(text, JSONLD_START, JSONLD_END, jsonld_block, path)
        path.write_text(text, encoding="utf-8")
    print(f"pre-rendered {len(events)} events into {len(LANGS)} shells")


if __name__ == "__main__":
    main()
