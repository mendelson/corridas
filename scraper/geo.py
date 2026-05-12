"""Geo-resolution utilities: locations index, Nominatim lookup, persistent cache."""
from __future__ import annotations
import difflib
import json
import time
from pathlib import Path

from unidecode import unidecode

_LOCATIONS_DIR = Path(__file__).parent.parent / "locations"
_CACHE_PATH = Path(__file__).parent.parent / "data" / "geo_cache.json"

# Loaded once at import time
_LOCATIONS: dict[str, dict] = {}           # iso2 → { "name", "subdivisions" }
_SUBDIV_BY_CODE: dict[str, dict[str, str]] = {}  # iso2 → { code → name }
_SUBDIV_BY_NAME: dict[str, dict[str, str]] = {}  # iso2 → { lower(name) → code }


def _load_locations() -> None:
    for path in _LOCATIONS_DIR.glob("*.json"):
        iso2 = path.stem.upper()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        _LOCATIONS[iso2] = data
        by_code: dict[str, str] = {}
        by_name: dict[str, str] = {}
        for sub in data.get("subdivisions", []):
            code = sub["code"]
            name = sub["name"]
            by_code[code] = name
            by_name[name.lower()] = code
            by_name[unidecode(name.lower())] = code
        _SUBDIV_BY_CODE[iso2] = by_code
        _SUBDIV_BY_NAME[iso2] = by_name


_load_locations()

_cache: dict[str, dict] | None = None
_last_nominatim_call: float = 0.0


def _load_cache() -> dict[str, dict]:
    global _cache
    if _cache is None:
        try:
            _cache = json.loads(_CACHE_PATH.read_text(encoding="utf-8"))
        except Exception:
            _cache = {}
    return _cache


def _save_cache() -> None:
    if _cache is None:
        return
    _CACHE_PATH.write_text(
        json.dumps(_cache, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _cache_key(localizacao: str, cidade: str) -> str:
    parts = (localizacao or "") + " " + (cidade or "")
    return unidecode(parts.lower().strip())


def _match_subdiv(pais: str, state_name: str) -> str:
    """Match a free-text state name from Nominatim to a known subdivision code."""
    by_name = _SUBDIV_BY_NAME.get(pais, {})
    if not by_name or not state_name:
        return ""
    key = state_name.lower()
    key_ascii = unidecode(key)
    if key in by_name:
        return by_name[key]
    if key_ascii in by_name:
        return by_name[key_ascii]
    matches = difflib.get_close_matches(key_ascii, list(by_name.keys()), n=1, cutoff=0.8)
    if matches:
        return by_name[matches[0]]
    return ""


def resolve(localizacao: str, cidade: str, pais_hint: str | None = None) -> tuple[str, str]:
    """Return (pais_iso2, estado_code) for a location string.

    Looks up the persistent cache first; falls back to Nominatim if not found.
    Returns ("??", "") on complete failure.
    """
    global _last_nominatim_call

    cache = _load_cache()
    key = _cache_key(localizacao, cidade)

    if key in cache:
        entry = cache[key]
        return entry.get("pais", "??"), entry.get("estado", "")

    query = ", ".join(p for p in (localizacao, cidade) if p)
    if not query:
        return (pais_hint or "??", "")

    # Rate-limit: 1 request per second (Nominatim policy)
    elapsed = time.monotonic() - _last_nominatim_call
    if elapsed < 1.0:
        time.sleep(1.0 - elapsed)

    try:
        import httpx
        resp = httpx.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": query, "format": "json", "addressdetails": "1", "limit": "1"},
            headers={"User-Agent": "corridas-aggregator/1.0 (github.com/corridas)"},
            timeout=10,
        )
        _last_nominatim_call = time.monotonic()
        data = resp.json()
    except Exception:
        _last_nominatim_call = time.monotonic()
        return (pais_hint or "??", "")

    if not data:
        return (pais_hint or "??", "")

    address = data[0].get("address", {})
    country_code = (address.get("country_code") or "").upper()
    if not country_code:
        return (pais_hint or "??", "")

    state_name = address.get("state") or address.get("province") or ""
    estado = _match_subdiv(country_code, state_name)

    result = {"pais": country_code, "estado": estado}
    cache[key] = result
    _save_cache()
    return country_code, estado


def validate_estado(pais: str, estado: str) -> str:
    """Return estado if it exists in the locations index for pais, else ''."""
    return estado if estado in _SUBDIV_BY_CODE.get(pais, {}) else ""
