"""Tests for the per-event static pages (scripts/generate_event_pages.py).

Date-tolerant where the eligible set depends on "today" (so a PR run a few
days after the committed scrape doesn't false-fail), strict everywhere else:
slug stability, page structure/JSON-LD, sitemap<->files bijection, the
Cloudflare file-count hard cap, and internal pre-render links resolving to
real pages.
"""
import importlib.util
import json
import re
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
OUT = WEB / "evento"


def _gen():
    spec = importlib.util.spec_from_file_location(
        "generate_event_pages", ROOT / "scripts" / "generate_event_pages.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


GEN = _gen()


def _full_events():
    d = json.loads((ROOT / "data" / "corridas.json").read_text(encoding="utf-8"))
    return d["corridas"] if isinstance(d, dict) else d


def _registry():
    return json.loads((ROOT / "data" / "event-slugs.json").read_text(encoding="utf-8"))


def test_pages_exist_only_for_eligible_br_events():
    """Every page belongs to a BR event within the (slack-padded) window, and
    every clearly-eligible BR event has a page."""
    events = {e["id"]: e for e in _full_events()}
    registry = _registry()
    files = {f.name for f in OUT.glob("*.html")}
    slug_to_id = {v: k for k, v in registry.items()}

    loose_cutoff = (date.today() - timedelta(days=GEN.PAST_GRACE_DAYS + 15)).isoformat()
    for fname in files:
        slug = fname[:-5]
        eid = slug_to_id.get(slug)
        assert eid, f"page {fname} has no registry entry"
        ev = events.get(eid)
        assert ev is None or (
            ev.get("pais") == "BR" and ev.get("data_evento", "") >= loose_cutoff
        ), f"page {fname} for non-eligible event {eid}"

    strict_cutoff = (date.today() - timedelta(days=GEN.PAST_GRACE_DAYS - 15)).isoformat()
    missing = [e["id"] for e in events.values()
               if e.get("pais") == "BR" and e.get("data_evento", "") >= strict_cutoff
               and f"{registry.get(e['id'], '?')}.html" not in files]
    assert not missing, f"eligible BR events without a page: {missing[:5]}"


def test_under_cloudflare_hard_cap():
    n = len(list(OUT.glob("*.html")))
    assert 0 < n <= GEN.HARD_CAP, f"{n} pages vs cap {GEN.HARD_CAP}"


def test_page_structure_and_jsonld():
    sample = sorted(OUT.glob("*.html"))[:25]
    assert sample
    for f in sample:
        s = f.read_text(encoding="utf-8")
        assert "<h1>" in s, f.name
        (canon,) = re.findall(r'<link rel="canonical" href="([^"]+)"', s)
        assert canon == f"{GEN.BASE}/evento/{f.name[:-5]}", f.name
        m = re.search(r'<script type="application/ld\+json">(.*?)</script>', s, re.DOTALL)
        d = json.loads(m.group(1))
        assert d["@type"] == "SportsEvent" and d["name"], f.name
        assert re.match(r"\d{4}-\d{2}-\d{2}", d["startDate"]), f.name
        assert d["location"]["address"]["addressCountry"] == "BR", f.name
        assert 'class="ep-fonte"' in s, f"{f.name}: no source links"


def test_pages_are_deterministic():
    """Same event data must produce byte-identical pages (no git churn)."""
    registry = _registry()
    slug_to_id = {v: k for k, v in registry.items()}
    events = {e["id"]: e for e in _full_events()}
    for f in sorted(OUT.glob("*.html"))[:25]:
        eid = slug_to_id[f.name[:-5]]
        if eid in events:
            assert f.read_text(encoding="utf-8") == GEN.build_page(
                events[eid], f.name[:-5]), f"{f.name} not reproducible"


def test_slug_registry_is_stable():
    """assign_slug must return the registered slug untouched for known ids."""
    registry = _registry()
    eid, slug = next(iter(registry.items()))
    out = GEN.assign_slug({"id": eid, "titulo": "TITULO COMPLETAMENTE DIFERENTE"},
                          dict(registry), set(registry.values()))
    assert out == slug, "existing slug changed when title changed"


def test_sitemap_matches_files():
    sm = (WEB / "sitemap-eventos.xml").read_text(encoding="utf-8")
    urls = set(re.findall(r"<loc>([^<]+)</loc>", sm))
    files = {f"{GEN.BASE}/evento/{f.name[:-5]}" for f in OUT.glob("*.html")}
    assert urls == files, (
        f"sitemap/files drift: {len(urls ^ files)} differing entries")


def test_robots_advertises_events_sitemap():
    robots = (WEB / "robots.txt").read_text(encoding="utf-8")
    assert f"Sitemap: {GEN.BASE}/sitemap-eventos.xml" in robots


def test_prerender_internal_links_resolve():
    for prefix in ("pt", "en", "es", "de", "fr"):
        s = (WEB / prefix / "index.html").read_text(encoding="utf-8")
        for slug in re.findall(r'href="/evento/([^"]+)"', s):
            assert (OUT / f"{slug}.html").exists(), (
                f"{prefix}: pre-render links to missing page {slug}")
