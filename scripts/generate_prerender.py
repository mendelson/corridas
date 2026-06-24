"""Generate pre-rendered event content + JSON-LD into the language shells.

The site is a client-side SPA: without this, the initial HTML carries zero
event content and search engines index an empty shell. Since the data exists
at build time (web/corridas.json), this script injects, into each
web/{lang}/index.html, between HTML markers:

  1. a static list of upcoming events inside <main id="cardsList">, using the
     SAME markup/classes as the real cards (`.card .card-collapsed …`) so the
     page already looks like the site while app.js boots — no unstyled flash.
     app.js clears and re-renders this container on boot, so SPA behaviour is
     unchanged. The `prerender` marker class lets tests (and tooling) tell
     these apart from live cards.
  2. a schema.org ItemList of SportsEvent entries (JSON-LD) enabling rich
     results.

Selection is LOCALIZED per language: each shell pre-renders the events its
audience actually searches for (pt → BR/PT, de → DE/AT/CH, …), padded with
worldwide events (targeted ones first) up to MAX_EVENTS so low-volume locales
still ship substantial content. The site is a worldwide aggregator — every
locale is first-class (see CLAUDE.md).

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

# Countries whose audience primarily searches in each language. "en" is the
# global fallback: it claims everything not claimed by another locale.
LANG_COUNTRIES: dict[str, set[str]] = {
    "pt": {"BR", "PT"},
    "es": {"ES", "MX", "AR", "CL", "CO", "PE", "UY", "PY", "BO", "EC", "VE",
           "CR", "PA", "GT", "DO", "SV", "HN", "NI", "CU"},
    "de": {"DE", "AT", "CH"},
    "fr": {"FR", "BE", "LU", "MC"},
}

_MONTHS = {
    "pt": ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
           "agosto", "setembro", "outubro", "novembro", "dezembro"],
    "en": ["January", "February", "March", "April", "May", "June", "July",
           "August", "September", "October", "November", "December"],
    "es": ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
           "agosto", "septiembre", "octubre", "noviembre", "diciembre"],
    "de": ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli",
           "August", "September", "Oktober", "November", "Dezember"],
    "fr": ["janvier", "février", "mars", "avril", "mai", "juin", "juillet",
           "août", "septembre", "octobre", "novembre", "décembre"],
}


def _fmt_date(iso: str, lang: str) -> str:
    """Human date in the shell's language (mirrors the frontend's long form)."""
    try:
        y, m, d = iso.split("-")
        month = _MONTHS[lang][int(m) - 1]
    except (ValueError, IndexError, KeyError):
        return iso
    day = int(d)
    if lang == "en":
        return f"{month} {day}, {y}"
    if lang == "de":
        return f"{day}. {month} {y}"
    if lang == "fr":
        return f"{day} {month} {y}"
    return f"{day} de {month} de {y}"  # pt / es


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


def select_events(corridas: list[dict], today: str, lang: str) -> list[dict]:
    """Language-targeted events first (by date), padded with worldwide ones."""
    upcoming = [c for c in corridas if (c.get("data_evento") or "") >= today]
    upcoming.sort(key=lambda c: c.get("data_evento") or "9999")

    countries = LANG_COUNTRIES.get(lang)
    if countries is None:  # "en": everything not claimed by another locale
        claimed = set().union(*LANG_COUNTRIES.values())
        targeted = [c for c in upcoming if (c.get("pais") or "") not in claimed]
    else:
        targeted = [c for c in upcoming if (c.get("pais") or "") in countries]

    selected = targeted[:MAX_EVENTS]
    if len(selected) < MAX_EVENTS:
        seen = {id(c) for c in selected}
        pad = [c for c in upcoming if id(c) not in seen]
        selected += pad[: MAX_EVENTS - len(selected)]
    return selected


def build_html(events: list[dict], lang: str) -> str:
    parts = []
    for ev in events:
        titulo = html.escape(ev.get("titulo") or "")
        data_iso = html.escape(ev.get("data_evento") or "")
        data_human = html.escape(_fmt_date(ev.get("data_evento") or "", lang))
        loc = html.escape(ev.get("localizacao") or "")
        pills = "".join(
            f'<span class="dist-pill">{html.escape(_fmt_km(d.get("km")))}</span>'
            for d in (ev.get("distancias") or []) if d.get("km") is not None
        )
        link = html.escape(_event_link(ev))
        title_html = f'<a href="{link}" rel="nofollow">{titulo}</a>' if link else titulo
        parts.append(
            '<article class="card prerender" role="listitem">'
            '<div class="card-collapsed">'
            '<div class="card-body">'
            f'<div class="card-top"><h2 class="card-title">{title_html}</h2></div>'
            '<div class="card-meta">'
            f'<span class="card-date"><time datetime="{data_iso}">{data_human}</time></span>'
            f'<span class="card-location">{loc}</span>'
            "</div>"
            + (f'<div class="card-footer"><div class="card-distances">{pills}</div></div>' if pills else "")
            + "</div></div></article>"
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
            item["offers"] = {
                "@type": "Offer",
                "url": link,
                "availability": "https://schema.org/InStock",
            }
        # Multi-day events: per-distance dates differ → endDate = last day.
        dist_dates = {d.get("data") for d in (ev.get("distancias") or []) if d.get("data")}
        dist_dates.add(ev.get("data_evento") or "")
        dist_dates.discard("")
        if len(dist_dates) > 1:
            item["endDate"] = max(dist_dates)
        # Only a fonte the pipeline classified as the event's own organizer
        # may be claimed as schema.org organizer — registration platforms and
        # calendars are not the organizer.
        org = next((f for f in (ev.get("fontes") or [])
                    if f.get("tipo") == "organizador" and f.get("nome")), None)
        if org:
            item["organizer"] = {"@type": "Organization", "name": org["nome"]}
            if org.get("link_evento"):
                item["organizer"]["url"] = org["link_evento"]
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
    today = date.today().isoformat()

    for prefix, _code in LANGS:
        events = select_events(corridas, today, prefix)
        html_block = build_html(events, prefix)
        jsonld_block = f'<script type="application/ld+json">{build_jsonld(events)}</script>'
        path = WEB / prefix / "index.html"
        text = path.read_text(encoding="utf-8")
        text = _replace_block(text, PRERENDER_START, PRERENDER_END, html_block, path)
        text = _replace_block(text, JSONLD_START, JSONLD_END, jsonld_block, path)
        path.write_text(text, encoding="utf-8")
        print(f"{prefix}: pre-rendered {len(events)} events")


if __name__ == "__main__":
    main()
