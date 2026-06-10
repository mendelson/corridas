"""Generate one static, indexable page per (Brazilian) event.

Phase 1 of the per-event-page plan: only `pais == "BR"` events (core
audience, ~2k pages — far from Cloudflare Pages' 20k file limit) get a page
under web/evento/{slug}.html, served as https://run.mmendelson.com/evento/{slug}
(Cloudflare Pages clean URLs). Each page carries the event's own <h1>, date,
location, distances, source links, canonical, OG tags and a standalone
schema.org SportsEvent JSON-LD — the long-tail landing target ("corrida X
cidade ano") the SPA cannot provide.

Guarantees:
- **Stable URLs.** Slugs are assigned once per event id and persisted in
  data/event-slugs.json; later title fixes never move the page.
- **Deterministic bytes.** A page is a pure function of its event's data (no
  timestamps), so unchanged events produce identical files and no git churn.
- **Lifecycle.** Pages exist for events from 30 days past onwards; stale
  files are removed on regeneration. A hard cap aborts the pipeline long
  before the Cloudflare 20k-file limit.
- **Discovery.** web/sitemap-eventos.xml lists every page (robots.txt
  advertises it); the pre-render block links event titles internally.

Run in the pipeline after the web projection:
  python scripts/generate_event_pages.py
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import unicodedata
from datetime import date, timedelta
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from generate_sitemap import BASE  # canonical origin — single source of truth  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "corridas.json"          # full file — has stable ids
REGISTRY = ROOT / "data" / "event-slugs.json"
OUT_DIR = ROOT / "web" / "evento"
SITEMAP = ROOT / "web" / "sitemap-eventos.xml"

ELIGIBLE_PAIS = "BR"
PAST_GRACE_DAYS = 30      # keep a page this long after the event
HARD_CAP = 18_000         # Cloudflare Pages rejects deploys over 20k files

_TIPO_ORDER = {"inscricao": 0, "organizador": 1, "calendario": 2}
_MES = ["", "janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
        "agosto", "setembro", "outubro", "novembro", "dezembro"]


def slugify(text: str) -> str:
    s = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()
    return s[:80] or "evento"


def _fmt_km(km) -> str:
    if isinstance(km, str):
        return km
    return f"{int(km)}K" if km == int(km) else f"{km:g}K"


def _fmt_data_pt(iso: str) -> str:
    y, m, d = iso.split("-")
    return f"{int(d)} de {_MES[int(m)]} de {y}"


def load_registry() -> dict[str, str]:
    if REGISTRY.exists():
        return json.loads(REGISTRY.read_text(encoding="utf-8"))
    return {}


def assign_slug(ev: dict, registry: dict[str, str], taken: set[str]) -> str:
    """Slug for the event id: reuse forever once assigned, else mint a new
    unique one (title slug + short id hash to disambiguate homonyms)."""
    eid = ev["id"]
    if eid in registry:
        return registry[eid]
    suffix = hashlib.sha1(eid.encode()).hexdigest()[:6]
    slug = f"{slugify(ev.get('titulo') or 'evento')}-{suffix}"
    while slug in taken:  # paranoia: hash collision after truncation
        suffix += "x"
        slug = f"{slugify(ev.get('titulo') or 'evento')}-{suffix}"
    registry[eid] = slug
    return slug


def select_events(corridas: list[dict], today: date) -> list[dict]:
    cutoff = (today - timedelta(days=PAST_GRACE_DAYS)).isoformat()
    return [c for c in corridas
            if c.get("pais") == ELIGIBLE_PAIS and (c.get("data_evento") or "") >= cutoff]


def _sources_html(ev: dict) -> str:
    fontes = sorted(ev.get("fontes") or [],
                    key=lambda f: _TIPO_ORDER.get(f.get("tipo"), 9))
    parts = []
    for f in fontes:
        link = (f.get("links_inscricao") or [None])[0] or f.get("link_evento")
        if not link:
            continue
        nome = html.escape(f.get("nome") or "Fonte")
        parts.append(
            f'<a class="ep-fonte" href="{html.escape(link)}" rel="nofollow noopener"'
            f' target="_blank">{nome}</a>')
    return "\n      ".join(parts)


def build_page(ev: dict, slug: str) -> str:
    titulo = html.escape(ev.get("titulo") or "")
    data_iso = ev.get("data_evento") or ""
    data_fmt = _fmt_data_pt(data_iso)
    horario = ev.get("horario") or ""
    loc = html.escape(ev.get("localizacao") or "")
    url = f"{BASE}/evento/{slug}"
    dists = [_fmt_km(d.get("km")) for d in (ev.get("distancias") or [])
             if d.get("km") is not None]
    dists_txt = ", ".join(dists)
    desc = html.escape(
        f"{ev.get('titulo')} em {ev.get('localizacao')} — {data_fmt}"
        + (f" às {horario}" if horario else "")
        + (f". Distâncias: {dists_txt}." if dists_txt else ".")
        + " Inscrições e detalhes.")
    imagem = ev.get("imagem_url") or f"{BASE}/logomendi-favicon.png"

    start = f"{data_iso}T{horario}" if horario else data_iso
    jsonld = {
        "@context": "https://schema.org",
        "@type": "SportsEvent",
        "name": ev.get("titulo") or "",
        "sport": "Running",
        "startDate": start,
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
        "image": imagem,
        "url": url,
    }

    pills = " ".join(f'<span class="dist-pill">{html.escape(d)}</span>' for d in dists)
    img_html = (
        f'\n    <img class="ep-img" src="{html.escape(ev["imagem_url"])}" alt="{titulo}"'
        f' loading="lazy" referrerpolicy="no-referrer" />'
        if ev.get("imagem_url") else "")
    horario_html = f" · {html.escape(horario)}" if horario else ""

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta name="theme-color" content="#FF6B35" />
  <title>{titulo} — {data_fmt} | Próxima Corrida</title>
  <meta name="description" content="{desc}" />
  <link rel="canonical" href="{url}" />
  <link rel="icon" type="image/x-icon" href="/favicon.ico" />
  <meta property="og:type" content="website" />
  <meta property="og:site_name" content="Próxima Corrida" />
  <meta property="og:title" content="{titulo} — {data_fmt}" />
  <meta property="og:description" content="{desc}" />
  <meta property="og:url" content="{url}" />
  <meta property="og:image" content="{html.escape(imagem)}" />
  <meta property="og:locale" content="pt_BR" />
  <meta name="twitter:card" content="summary" />
  <meta name="twitter:title" content="{titulo} — {data_fmt}" />
  <meta name="twitter:description" content="{desc}" />
  <link rel="stylesheet" href="../style.css" />
  <style>
    .ep-wrap {{ max-width: 720px; margin: 0 auto; padding: 16px; }}
    .ep-img {{ max-width: 100%; border-radius: 8px; margin: 12px 0; }}
    .ep-meta {{ color: var(--color-text-dim, #aaa); margin: 8px 0; }}
    .ep-fontes {{ display: flex; flex-wrap: wrap; gap: 8px; margin: 16px 0; }}
    .ep-fonte {{ background: var(--color-accent, #FF6B35); color: #fff; padding: 10px 16px;
                 border-radius: 6px; text-decoration: none; font-weight: 600; }}
    .ep-back {{ color: var(--color-accent, #FF6B35); text-decoration: none; }}
  </style>
  <script type="application/ld+json">{json.dumps(jsonld, ensure_ascii=False, separators=(",", ":"))}</script>
</head>
<body>
  <div class="ep-wrap">
    <p><a class="ep-back" href="/pt/">← Próxima Corrida — calendário de corridas</a></p>
    <h1>{titulo}</h1>
    <p class="ep-meta"><time datetime="{data_iso}">{data_fmt}</time>{horario_html}</p>
    <p class="ep-meta">{loc}</p>
    <p>{pills}</p>{img_html}
    <h2>Inscrições e informações</h2>
    <div class="ep-fontes">
      {_sources_html(ev)}
    </div>
  </div>
</body>
</html>
"""


def build_sitemap(slugs: list[str]) -> str:
    urls = "\n".join(
        f"  <url><loc>{xml_escape(f'{BASE}/evento/{s}')}</loc></url>"
        for s in sorted(slugs))
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            f"{urls}\n</urlset>\n")


def main(today: date | None = None) -> None:
    today = today or date.today()
    data = json.loads(DATA.read_text(encoding="utf-8"))
    corridas = data["corridas"] if isinstance(data, dict) else data
    events = select_events(corridas, today)
    if len(events) > HARD_CAP:
        raise SystemExit(
            f"{len(events)} event pages would exceed the hard cap of {HARD_CAP} "
            "(Cloudflare Pages limit safety) — tighten eligibility first.")

    registry = load_registry()
    taken = set(registry.values())
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    slugs = []
    for ev in events:
        slug = assign_slug(ev, registry, taken)
        taken.add(slug)
        slugs.append(slug)
        (OUT_DIR / f"{slug}.html").write_text(build_page(ev, slug), encoding="utf-8")

    wanted = {f"{s}.html" for s in slugs}
    removed = 0
    for f in OUT_DIR.glob("*.html"):
        if f.name not in wanted:
            f.unlink()
            removed += 1

    REGISTRY.write_text(
        json.dumps(registry, ensure_ascii=False, indent=0, sort_keys=True),
        encoding="utf-8")
    SITEMAP.write_text(build_sitemap(slugs), encoding="utf-8")
    print(f"event pages: {len(slugs)} written, {removed} stale removed")


if __name__ == "__main__":
    main()
