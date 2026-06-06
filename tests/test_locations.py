"""Tests for the unified subdivisions reference data (web/locations/).

There is exactly ONE copy of the per-country subdivisions index, under
web/locations/. It is served statically to the frontend (web/app.js) and read
by the scraper's geo resolver (scraper/geo.py) and by the data pipeline
(scraper/main.py). These tests guard that invariant and the integrity of the
data, so the historical split-brain (a second top-level locations/ that drifted
out of sync) cannot silently come back.

Pure-stdlib only — no scraper imports — so it runs in the frontend CI job,
which installs just requirements-test.txt.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
WEB_LOCATIONS = REPO_ROOT / "web" / "locations"
LEGACY_LOCATIONS = REPO_ROOT / "locations"
GEO_PY = REPO_ROOT / "scraper" / "geo.py"

# A few countries that must always be present (heavily used by the scrapers,
# and the two — BM/HK — that previously existed only in the web/ copy).
_REQUIRED_COUNTRIES = ["BR", "US", "MX", "GB", "DE", "FR", "ES", "IT", "BM", "HK"]


def _country_files() -> list[Path]:
    return sorted(WEB_LOCATIONS.glob("*.json"))


def test_single_canonical_locations_dir() -> None:
    """web/locations/ is the only copy — the legacy top-level locations/ is gone."""
    assert WEB_LOCATIONS.is_dir(), "web/locations/ must exist"
    assert not LEGACY_LOCATIONS.exists(), (
        "A second top-level locations/ directory exists again. The subdivisions "
        "data must live only in web/locations/ to avoid split-brain drift."
    )


def test_locations_populated() -> None:
    files = _country_files()
    assert len(files) > 150, f"expected many country files, found {len(files)}"


@pytest.mark.parametrize("iso2", _REQUIRED_COUNTRIES)
def test_required_country_present(iso2: str) -> None:
    assert (WEB_LOCATIONS / f"{iso2}.json").is_file(), f"missing web/locations/{iso2}.json"


def test_every_country_file_is_valid() -> None:
    """Each country JSON parses and has a name + well-formed subdivisions list."""
    problems: list[str] = []
    for f in _country_files():
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            problems.append(f"{f.name}: invalid JSON ({e})")
            continue

        if not isinstance(data.get("name"), str) or not data["name"].strip():
            problems.append(f"{f.name}: missing/empty 'name'")

        subs = data.get("subdivisions")
        if not isinstance(subs, list):
            problems.append(f"{f.name}: 'subdivisions' must be a list")
            continue

        seen_codes: set[str] = set()
        for i, sub in enumerate(subs):
            if not isinstance(sub, dict):
                problems.append(f"{f.name}: subdivision #{i} is not an object")
                continue
            code = sub.get("code")
            name = sub.get("name")
            if not isinstance(code, str) or not code.strip():
                problems.append(f"{f.name}: subdivision #{i} has missing/empty 'code'")
            if not isinstance(name, str) or not name.strip():
                problems.append(f"{f.name}: subdivision #{i} has missing/empty 'name'")
            if isinstance(code, str):
                if code in seen_codes:
                    problems.append(f"{f.name}: duplicate subdivision code '{code}'")
                seen_codes.add(code)

    assert not problems, "Invalid location files:\n  " + "\n  ".join(problems)


def test_filename_matches_iso2_shape() -> None:
    """Every file is named like an ISO-3166-1 alpha-2 code: two uppercase letters."""
    bad = [f.name for f in _country_files() if not re.fullmatch(r"[A-Z]{2}\.json", f.name)]
    assert not bad, f"unexpected location filenames: {bad}"


def test_geo_resolver_reads_web_locations() -> None:
    """scraper/geo.py points its index at web/locations/ (the canonical copy).

    Checked at the source level to avoid importing scraper.geo (which pulls in
    runtime deps not installed in the frontend test job).
    """
    src = GEO_PY.read_text(encoding="utf-8")
    m = re.search(r"_LOCATIONS_DIR\s*=\s*(.+)", src)
    assert m, "could not find _LOCATIONS_DIR assignment in scraper/geo.py"
    assignment = m.group(1)
    assert '"web"' in assignment and '"locations"' in assignment, (
        f"geo.py _LOCATIONS_DIR must resolve to web/locations/, got: {assignment!r}"
    )
