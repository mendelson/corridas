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


# ---------------------------------------------------------------------------
# Page <head>: canonical + hreflang + localized title/description
# ---------------------------------------------------------------------------

import re as _re

_PAGES = {prefix: WEB / prefix / "index.html" for prefix, _ in GEN.LANGS}
_CANON_RE = _re.compile(r'<link rel="canonical" href="([^"]+)"')
_HREFLANG_RE = _re.compile(r'<link rel="alternate" hreflang="([^"]+)" href="([^"]+)"')
_TITLE_RE = _re.compile(r"<title>([^<]*)</title>")
_DESC_RE = _re.compile(r'<meta name="description" content="([^"]*)"')

_EXPECTED_ALTS = {code: f"{BASE}/{prefix}/" for prefix, code in GEN.LANGS}
_EXPECTED_ALTS["x-default"] = f"{BASE}/"


def test_every_language_page_has_exactly_one_correct_canonical():
    for prefix, path in _PAGES.items():
        html = path.read_text(encoding="utf-8")
        canons = _CANON_RE.findall(html)
        assert canons == [f"{BASE}/{prefix}/"], f"{path}: canonical = {canons}"


def test_every_language_page_declares_full_reciprocal_hreflang():
    """Each page must carry the SAME full alternate cluster (all languages +
    x-default) with absolute hrefs — reciprocity is what Google requires."""
    for prefix, path in _PAGES.items():
        html = path.read_text(encoding="utf-8")
        alts = dict(_HREFLANG_RE.findall(html))
        assert alts == _EXPECTED_ALTS, (
            f"{path}: hreflang drift: {set(alts.items()) ^ set(_EXPECTED_ALTS.items())}"
        )


def test_root_redirect_page_has_canonical_hreflang_and_noscript():
    html = (WEB / "index.html").read_text(encoding="utf-8")
    assert _CANON_RE.findall(html) == [f"{BASE}/"]
    assert dict(_HREFLANG_RE.findall(html)) == _EXPECTED_ALTS
    assert "<noscript>" in html and 'href="/pt/"' in html, (
        "root page must link the language homes for non-JS crawlers"
    )


def test_titles_and_descriptions_are_localized_and_distinct():
    """Generic identical titles across languages waste the SERP snippet; each
    language must have its own non-trivial title and description."""
    titles, descs = {}, {}
    for prefix, path in _PAGES.items():
        html = path.read_text(encoding="utf-8")
        (title,) = _TITLE_RE.findall(html)
        (desc,) = _DESC_RE.findall(html)
        assert len(title) >= 25, f"{path}: title too short/generic: {title!r}"
        assert len(desc) >= 60, f"{path}: description too short: {desc!r}"
        titles[prefix] = title
        descs[prefix] = desc
    assert len(set(titles.values())) == len(titles), f"duplicated titles: {titles}"
    assert len(set(descs.values())) == len(descs), f"duplicated descriptions: {descs}"


# ---------------------------------------------------------------------------
# Pre-rendered event content + JSON-LD (generated by scripts/generate_prerender.py)
# ---------------------------------------------------------------------------

import html as _html
import json as _json

_PR_BLOCK_RE = _re.compile(
    r"<!-- prerender:events:start -->(.*?)<!-- prerender:events:end -->", _re.DOTALL)
_JSONLD_BLOCK_RE = _re.compile(
    r'<!-- prerender:jsonld:start -->\s*<script type="application/ld\+json">(.*?)</script>',
    _re.DOTALL)
_ARTICLE_TITLE_RE = _re.compile(r'<h2 class="card-title">(?:<a [^>]*>)?([^<]+)')


def _prerender_blocks():
    out = {}
    for prefix, path in _PAGES.items():
        m = _PR_BLOCK_RE.search(path.read_text(encoding="utf-8"))
        assert m, f"{path}: prerender markers missing"
        out[prefix] = m.group(1).strip()
    return out


def test_prerender_present_capped_and_styled():
    """Each shell carries pre-rendered cards using the real card markup —
    the page must look like the site before app.js boots (no unstyled flash)."""
    blocks = _prerender_blocks()
    counts = {p: b.count('<article class="card prerender"') for p, b in blocks.items()}
    for p, n in counts.items():
        assert 1 <= n <= 200, f"{p}: {n} pre-rendered cards"
        assert "<article>" not in blocks[p], f"{p}: bare unstyled <article> in pre-render"
        for cls in ("card-collapsed", "card-body", "card-title", "card-meta"):
            assert cls in blocks[p], f"{p}: pre-render missing .{cls} markup"


def test_prerender_localized_per_language():
    """Selection is per-language: targeted countries lead each shell's block,
    so the blocks must NOT all be identical (worldwide aggregator — each
    locale gets the events its audience searches for)."""
    gp_path = ROOT / "scripts" / "generate_prerender.py"
    import sys as _sys
    _sys.path.insert(0, str(ROOT / "scripts"))
    try:
        spec = importlib.util.spec_from_file_location("generate_prerender", gp_path)
        gp = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gp)
    finally:
        _sys.path.pop(0)

    data = _json.loads((WEB / "corridas.json").read_text(encoding="utf-8"))
    corridas = data["corridas"] if isinstance(data, dict) else data
    title_paises: dict[str, set] = {}
    for c in corridas:
        title_paises.setdefault(c.get("titulo"), set()).add(c.get("pais") or "")

    blocks = _prerender_blocks()
    assert len(set(blocks.values())) > 1, (
        "pre-rendered blocks are identical across languages — localization lost"
    )
    claimed = set().union(*gp.LANG_COUNTRIES.values())
    for prefix, block in blocks.items():
        titles = [_html.unescape(t.strip()) for t in _ARTICLE_TITLE_RE.findall(block)]
        assert titles, f"{prefix}: no titles extracted from pre-render block"
        allowed = gp.LANG_COUNTRIES.get(prefix)
        first = titles[0]
        paises = title_paises.get(first, set())
        if allowed is None:  # en — global fallback: first event not claimed elsewhere
            assert paises - claimed or not paises & claimed, (
                f"en: first pre-rendered event '{first}' belongs to another locale ({paises})"
            )
        else:
            assert paises & allowed, (
                f"{prefix}: first pre-rendered event '{first}' not in {sorted(allowed)} ({paises})"
            )


def test_prerender_titles_exist_in_corridas_json():
    data = _json.loads((WEB / "corridas.json").read_text(encoding="utf-8"))
    corridas = data["corridas"] if isinstance(data, dict) else data
    titles = {c.get("titulo") for c in corridas}
    for prefix, block in _prerender_blocks().items():
        extracted = [_html.unescape(t.strip()) for t in _ARTICLE_TITLE_RE.findall(block)]
        assert extracted, f"{prefix}: no titles extracted from pre-render block"
        missing = [t for t in extracted if t not in titles]
        assert not missing, (
            f"{prefix}: pre-rendered events absent from corridas.json: {missing[:5]}"
        )


def test_jsonld_itemlist_valid_and_consistent():
    for prefix, path in _PAGES.items():
        text = path.read_text(encoding="utf-8")
        m = _JSONLD_BLOCK_RE.search(text)
        assert m, f"{path}: JSON-LD block missing"
        data = _json.loads(m.group(1))
        assert data["@type"] == "ItemList"
        items = data["itemListElement"]
        assert data["numberOfItems"] == len(items) > 0
        n_articles = _PR_BLOCK_RE.search(text).group(1).count("<article")
        assert len(items) == n_articles, f"{path}: JSON-LD/HTML count mismatch"
        for li in items:
            ev = li["item"]
            assert ev["@type"] == "SportsEvent"
            assert ev["name"], f"{path}: SportsEvent without name"
            assert _re.fullmatch(r"\d{4}-\d{2}-\d{2}", ev["startDate"]), (
                f"{path}: bad startDate {ev['startDate']!r}"
            )


# ---------------------------------------------------------------------------
# Open Graph / Twitter Cards
# ---------------------------------------------------------------------------

_OG_RE = _re.compile(r'<meta property="og:([a-z_:]+)" content="([^"]*)"')
_TW_RE = _re.compile(r'<meta name="twitter:([a-z]+)" content="([^"]*)"')
_OG_LOCALES = {"pt": "pt_BR", "en": "en_US", "es": "es_ES", "de": "de_DE", "fr": "fr_FR"}


def test_og_tags_consistent_with_head():
    """og:title/url must mirror the page's own title/canonical — divergence
    means stale tags producing wrong share previews."""
    for prefix, path in _PAGES.items():
        html = path.read_text(encoding="utf-8")
        og = {}
        for k, v in _OG_RE.findall(html):
            og.setdefault(k, v)
        (title,) = _TITLE_RE.findall(html)
        (canon,) = _CANON_RE.findall(html)
        assert og.get("title") == title, f"{path}: og:title != <title>"
        assert og.get("url") == canon, f"{path}: og:url != canonical"
        assert og.get("type") == "website"
        assert og.get("image", "").startswith("https://"), f"{path}: og:image not absolute"
        assert og.get("locale") == _OG_LOCALES[prefix], f"{path}: og:locale"
        tw = dict(_TW_RE.findall(html))
        assert tw.get("card") == "summary", f"{path}: twitter:card missing"
        assert tw.get("title") == title, f"{path}: twitter:title != <title>"
