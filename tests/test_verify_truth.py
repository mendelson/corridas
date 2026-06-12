"""Unit tests for the sampled truth-checker decision logic (no network).

Guards the precision tuning: it must flag the CPTR-class error (page says one
UF, site shows another) while staying silent on legit events and ambiguous
pages — false positives would page the maintainer for nothing.
"""
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    spec = importlib.util.spec_from_file_location("verify_truth", ROOT / "scripts" / "verify_truth.py")
    vt = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(vt)
except ImportError as exc:  # pragma: no cover — frontend job lacks scraper deps
    pytest.skip(f"deps indisponíveis: {exc}", allow_module_level=True)

from bs4 import BeautifulSoup


def _ufs_and_counts(html):
    soup = BeautifulSoup(html, "lxml")
    dates, ufs = vt._jsonld_facts(vt._jsonld_events(soup))
    counts = vt._pattern_ufs(soup.get_text(" ", strip=True))
    return ufs, counts


def test_jsonld_uf_mismatch_is_caught():
    html = """<script type="application/ld+json">
    {"@type":"Event","startDate":"2026-06-28",
     "location":{"@type":"Place","address":{"@type":"PostalAddress",
       "streetAddress":"Beira Rio, Pirenópolis - GO, 72980-000"}}}
    </script>"""
    _, ufs = vt._jsonld_facts(vt._jsonld_events(BeautifulSoup(html, "lxml")))
    assert ufs == {"GO"}  # stored "DF" would mismatch → erro


def test_pattern_scan_flags_unanimous_other_uf():
    html = "<p>Beira Rio, Pirenópolis-GO</p><p>largada Pirenópolis-GO</p><p>trail Pirenópolis-GO</p>"
    _, counts = _ufs_and_counts(html)
    stored = "DF"
    flag = bool(counts and stored not in counts and max(counts.values()) >= 3 and len(counts) == 1)
    assert flag is True


def test_no_false_positive_on_legit_state():
    html = "<p>Brasília-DF</p><p>Asa Sul - DF</p><p>largada DF</p>"
    _, counts = _ufs_and_counts(html)
    assert not (counts and "DF" not in counts)


def test_ambiguous_page_not_flagged():
    html = "<p>São Paulo-SP</p><p>parceria Rio-RJ</p><p>São Paulo-SP</p><p>São Paulo-SP</p>"
    _, counts = _ufs_and_counts(html)
    stored = "MG"
    flag = bool(counts and stored not in counts and max(counts.values()) >= 3 and len(counts) == 1)
    assert flag is False  # two UFs present → no unanimous verdict
