"""GOLDEN RULE guard — no hardcoded event data in scrapers.

A scraper must read every event field — date, distances, location, start time,
links — live from the source at scrape time, and emit nothing for a field it
cannot read (CLAUDE.md "GOLDEN RULE: no hardcoded event data, anywhere"). A
hardcoded value silently goes stale: that is exactly how the POA, Rio and SP
City marathons disappeared from the aggregator (a `_FALLBACK_DATA` / `KNOWN_DATE`
in the past, emitted when the computed year guard threw the live date away).

This test fails the build — and therefore the PR — when a source file contains a
hardcoded-event-data signature:

  * a ``_FALLBACK_DATA`` / ``_FALLBACK_INSC``-style date or link fallback constant
  * a ``KNOWN_DATE`` / ``known_dates`` hardcoded date
  * a module-level ISO date-literal constant (``NAME = "2026-07-26"``)
  * a ``_target_year()`` guard (the pattern that discards a live date when it
    doesn't match a computed year)

It is a *ratchet*: the ``_MIGRATING`` allowlist below is the set of single-event
sources that still carry a hardcoded date fallback and are being moved to live
extraction (schema.org ``startDate`` etc.). **The allowlist may only SHRINK** —
never add to it. Removing a file from it is the proof its source went fully
dynamic. Any new source (or any allowlisted source that regresses after being
removed) fails this test.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

_SOURCES = Path(__file__).resolve().parent.parent / "scraper" / "sources"

# Single-event sources still carrying a hardcoded date fallback, pending their
# migration to live date extraction. DO NOT ADD ENTRIES — this set may only
# shrink. Remove a file the moment its scraper reads the date live.
_MIGRATING: set[str] = {
    "evento_unico/sao_silvestre.py",
    "evento_unico/amsterdam.py",
    "evento_unico/athens.py",
    "evento_unico/berlin.py",
    "evento_unico/boston.py",
    "evento_unico/brighton.py",
    "evento_unico/cardiff_half.py",
    "evento_unico/chicago.py",
    "evento_unico/copenhagen.py",
    "evento_unico/dublin.py",
    "evento_unico/edinburgh.py",
    "evento_unico/great_north_run.py",
    "evento_unico/london.py",
    "evento_unico/manchester.py",
    "evento_unico/manchester_half.py",
    "evento_unico/nyc.py",
    "evento_unico/paris.py",
    "evento_unico/prague.py",
    "evento_unico/stockholm.py",
    "evento_unico/sydney.py",
    "evento_unico/tokyo.py",
    "evento_unico/valencia.py",
    "evento_unico/venice.py",
}

_SIGNATURES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r'^\s*_?FALLBACK_\w*\s*=', re.MULTILINE),
     "_FALLBACK_* hardcoded date/link fallback constant"),
    (re.compile(r'(?:^|\W)KNOWN_DATES?\b\s*=|^\s*known_dates?\s*=', re.MULTILINE),
     "KNOWN_DATE hardcoded date constant"),
    (re.compile(r'^[A-Z_]+\s*=\s*[\'"]20\d\d-\d\d-\d\d', re.MULTILINE),
     'module-level ISO date literal (NAME = "YYYY-MM-DD")'),
    (re.compile(r'\bdef\s+_target_year\b'),
     "_target_year() guard (discards live dates that don't match a computed year)"),
]


def _source_files() -> list[Path]:
    return [p for p in _SOURCES.rglob("*.py") if "__pycache__" not in p.parts]


def test_no_hardcoded_event_data() -> None:
    violations: list[str] = []
    for py in _source_files():
        rel = py.relative_to(_SOURCES).as_posix()
        if rel in _MIGRATING:
            continue
        text = py.read_text(encoding="utf-8")
        for pattern, desc in _SIGNATURES:
            if pattern.search(text):
                violations.append(f"{rel}: {desc}")
    assert not violations, (
        "Hardcoded event data detected — read it live from the source instead "
        "(CLAUDE.md GOLDEN RULE):\n  " + "\n  ".join(sorted(violations))
    )


def test_migration_allowlist_only_shrinks() -> None:
    """Every allowlisted file must (a) still exist and (b) still actually carry a
    hardcoded-date signature. A file that no longer matches must be removed from
    the allowlist so the guard starts enforcing it."""
    stale: list[str] = []
    for rel in sorted(_MIGRATING):
        path = _SOURCES / rel
        if not path.exists():
            stale.append(f"{rel}: file no longer exists — remove from _MIGRATING")
            continue
        text = path.read_text(encoding="utf-8")
        if not any(p.search(text) for p, _ in _SIGNATURES):
            stale.append(f"{rel}: no longer has a hardcoded-date signature — "
                         "remove from _MIGRATING so it's enforced")
    assert not stale, "Stale _MIGRATING entries:\n  " + "\n  ".join(stale)
