"""Tests for the SEO surface: robots.txt and the generated sitemap.xml.

These are pure file/logic tests — no live server, no network. They exercise the
sitemap *generator* (not just the committed artifact) so a regression in
scripts/generate_sitemap.py fails the suite, and they assert real semantic
properties (reciprocal hreflang, absolute URLs, robots↔sitemap host agreement)
rather than mere presence — so they can't pass on a broken-but-non-empty file.
"""
import importlib.util
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"

SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"
XHTML_NS = "http://www.w3.org/1999/xhtml"
_LOC = f"{{{SITEMAP_NS}}}loc"
_URL = f"{{{SITEMAP_NS}}}url"
_LASTMOD = f"{{{SITEMAP_NS}}}lastmod"
_LINK = f"{{{XHTML_NS}}}link"


def _load_generator():
    """Import scripts/generate_sitemap.py (scripts/ is not a package)."""
    path = ROOT / "scripts" / "generate_sitemap.py"
    spec = importlib.util.spec_from_file_location("generate_sitemap", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


GEN = _load_generator()
BASE = GEN.BASE
EXPECTED_LOCS = {f"{BASE}/{prefix}/" for prefix, _ in GEN.LANGS}
EXPECTED_HREFLANGS = {code for _, code in GEN.LANGS} | {"x-default"}


def _parse(xml_text):
    """Return {loc: {hreflang: href}} from a sitemap XML string."""
    root = ET.fromstring(xml_text)
    out = {}
    for url in root.findall(_URL):
        loc = url.findtext(_LOC)
        alts = {}
        for link in url.findall(_LINK):
            assert link.get("rel") == "alternate", "xhtml:link must be rel=alternate"
            alts[link.get("hreflang")] = link.get("href")
        out[loc] = alts
    return out


# ---------------------------------------------------------------------------
# Generator-level semantics (fails if the generator logic breaks)
# ---------------------------------------------------------------------------

def test_generator_emits_exactly_the_five_localized_homes():
    parsed = _parse(GEN.build_sitemap())
    assert set(parsed) == EXPECTED_LOCS, (
        f"sitemap <loc> set drifted: {set(parsed) ^ EXPECTED_LOCS}"
    )


def test_every_url_declares_full_reciprocal_hreflang():
    """Each page must point to *all* language alternates + x-default, with the
    correct absolute href — that reciprocity is exactly what Google requires."""
    parsed = _parse(GEN.build_sitemap())
    code_to_url = {code: f"{BASE}/{prefix}/" for prefix, code in GEN.LANGS}
    code_to_url["x-default"] = f"{BASE}/"
    for loc, alts in parsed.items():
        assert set(alts) == EXPECTED_HREFLANGS, f"{loc} missing alternates: {EXPECTED_HREFLANGS ^ set(alts)}"
        for code, href in alts.items():
            assert href == code_to_url[code], f"{loc} hreflang={code} -> {href}"
            assert href.startswith("https://"), f"hreflang href not absolute https: {href}"


def test_lastmod_present_and_iso_dated():
    root = ET.fromstring(GEN.build_sitemap())
    for url in root.findall(_URL):
        lm = url.findtext(_LASTMOD)
        assert lm and len(lm) == 10 and lm[4] == "-" and lm[7] == "-", f"bad lastmod {lm!r}"


# ---------------------------------------------------------------------------
# Committed artifact must stay in sync with the generator (drift guard)
# ---------------------------------------------------------------------------

def test_committed_sitemap_is_wellformed_and_matches_generator():
    committed = (WEB / "sitemap.xml").read_text(encoding="utf-8")
    # Compare structure only — lastmod is date-stamped and legitimately differs
    # across days, so ignoring it avoids a daily false failure while still
    # catching any structural drift (locs / hreflang).
    assert _parse(committed) == _parse(GEN.build_sitemap()), (
        "web/sitemap.xml is stale — re-run scripts/generate_sitemap.py"
    )


# ---------------------------------------------------------------------------
# robots.txt
# ---------------------------------------------------------------------------

def test_robots_allows_crawling_and_advertises_sitemap():
    robots = (WEB / "robots.txt").read_text(encoding="utf-8")
    lines = [l.strip() for l in robots.splitlines() if l.strip()]
    assert "User-agent: *" in lines
    assert "Allow: /" in lines
    assert any(l.lower().startswith("disallow: /") and l.split(":", 1)[1].strip() == "/"
               for l in lines) is False, "robots.txt must not Disallow the whole site"
    sitemap_lines = [l for l in lines if l.lower().startswith("sitemap:")]
    assert sitemap_lines, "robots.txt must declare a Sitemap:"
    # The advertised sitemap must live on the same canonical origin the
    # generator anchors every URL to — a mismatch would silently de-list us.
    assert sitemap_lines[0].split(":", 1)[1].strip() == f"{BASE}/sitemap.xml"
