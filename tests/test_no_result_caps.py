"""Guard — no source may cap or discard its results.

A scraper must fetch and check EVERY result a source returns; it may never keep
only the first N and drop the rest, nor defer the rest to a later run (a rotating
window). Quality over speed (CLAUDE.md "no result caps"). This is how the
worldsmarathons majors were silently missing: only the first 400 of ~7000 sitemap
events were ever fetched.

This test fails the build — and the PR — when a source file contains a
result-cap signature:

  * a cap constant: a name like ``_MAX_EVENTS`` / ``_MAX_PAGES`` /
    ``_MAX_RESULTS`` / ``_MAX_NEW_FETCHES`` / ``…_PER_RUN`` assigned a number;
  * a slice limited by such a constant (``urls[:_MAX_EVENTS]``);
  * a result collection sliced to a fixed count (``events[:500]``).

It is deliberately conservative (it targets result-list names, not text
truncations like ``raw[:200]`` or sub-field lists like distance ``values[:8]``),
but it catches every standard way an agent would reintroduce a cap. New sources
and edits are all scanned; there is no allowlist.
"""
from __future__ import annotations

import re
from pathlib import Path

_SOURCES = Path(__file__).resolve().parent.parent / "scraper" / "sources"

# variable names that hold a source's *results* (events to emit), where slicing
# to a fixed count means discarding results.
_RESULT_VARS = (
    r"urls|events|races|corridas|results|docs|entries|eventos|recent|todo|hits|"
    r"items|products|links|rows|window|slugs|cards|posts|provas"
)

_SIGNATURES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r'^\s*_?[A-Z0-9_]*MAX[A-Z0-9_]*'
                r'(?:EVENTS|PAGES|RESULTS|FETCHES|ITEMS|RACES|URLS|DOCS)[A-Z0-9_]*\s*=\s*\d',
                re.MULTILINE),
     "result-cap constant (_MAX_EVENTS/_MAX_PAGES/… = N)"),
    (re.compile(r'^\s*_?[A-Z][A-Z0-9_]*_PER_RUN\s*=\s*\d', re.MULTILINE),
     "per-run result cap constant (…_PER_RUN = N)"),
    (re.compile(r'\[\s*:\s*_?[A-Z][A-Z0-9_]*(?:MAX|LIMIT|CAP)[A-Z0-9_]*\s*\]'),
     "slice limited by a MAX/LIMIT/CAP constant"),
    (re.compile(rf'\b(?:{_RESULT_VARS})\b\s*\[\s*:\s*\d+\s*\]'),
     "result collection sliced to a fixed count"),
]


def test_no_result_caps() -> None:
    violations: list[str] = []
    for py in _SOURCES.rglob("*.py"):
        if "__pycache__" in py.parts:
            continue
        rel = py.relative_to(_SOURCES).as_posix()
        text = py.read_text(encoding="utf-8")
        for pattern, desc in _SIGNATURES:
            for m in pattern.finditer(text):
                if "PDF" in m.group(0).upper():
                    continue  # bound on parsing one document, not a result cap
                line = text.count("\n", 0, m.start()) + 1
                violations.append(f"{rel}:{line}: {desc} — `{m.group(0).strip()}`")
    assert not violations, (
        "Result cap detected — fetch/check EVERY result, never a prefix "
        "(CLAUDE.md: no result caps):\n  " + "\n  ".join(sorted(violations))
    )
