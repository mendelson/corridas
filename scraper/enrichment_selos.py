"""Enrich aggregated events with official designations — read dynamically.

Two layers, both annotation-only (they never create events, only tag ones we
already aggregated from other sources):

  * **World Athletics road-race label** (Platinum / Gold / Elite / Label) — the
    worldwide authority for road-race quality seals. Read every run from the
    public ``world-athletics-label-road-races`` page (``__NEXT_DATA__`` →
    ``calendarEvents.results``), so labels stay current with zero hardcoding.
    (This is why World Athletics couldn't be a primary *event* source — it has
    no start time — but it's perfect as an enrichment layer.)

  * **Abbott World Marathon Major** — the 7-race club. Abbott publishes no
    machine-readable "these are the Majors" list (their site is a Webflow page
    whose race names live in images/JS). The membership is therefore treated as
    world REFERENCE data (like ``web/locations`` — it describes the world, not a
    specific edition), matched dynamically to our events. It is NOT a per-event
    value baked into any scraper.

Matching is deliberately conservative: normalized-title token overlap + date
proximity + country. A miss just means no badge (safe); a wrong match would
mislabel, so the thresholds favour precision.
"""
from __future__ import annotations

import json
import re
import difflib

from .http_client import get
from .models import Corrida
from .utils import normalize_titulo_merge, today_iso

WA_URL = "https://worldathletics.org/competitions/world-athletics-label-road-races"

# World Athletics competitionSubgroup → our canonical selo code (ranked).
_SELO_MAP = {
    "platinum": "platinum",
    "gold": "gold",
    "elite": "elite",
    "label": "label",
}
_SELO_RANK = {"platinum": 4, "gold": 3, "elite": 2, "label": 1}

# IOC/WA 3-letter country code → ISO-3166-1 alpha-2, for the countries that
# actually carry labels. Reference data (describes the world, not an edition).
_IOC_TO_ISO2 = {
    "BRA": "BR", "USA": "US", "GBR": "GB", "GER": "DE", "FRA": "FR", "ESP": "ES",
    "ITA": "IT", "NED": "NL", "POR": "PT", "JPN": "JP", "CHN": "CN", "AUS": "AU",
    "CAN": "CA", "MEX": "MX", "RSA": "ZA", "KEN": "KE", "ETH": "ET", "IND": "IN",
    "IRL": "IE", "BEL": "BE", "SUI": "CH", "AUT": "AT", "SWE": "SE", "NOR": "NO",
    "DEN": "DK", "FIN": "FI", "POL": "PL", "CZE": "CZ", "GRE": "GR", "TUR": "TR",
    "ARG": "AR", "CHI": "CL", "COL": "CO", "PER": "PE", "URU": "UY", "NZL": "NZ",
    "KOR": "KR", "SGP": "SG", "MAS": "MY", "PHI": "PH", "UAE": "AE", "ISR": "IL",
    "HUN": "HU", "ROU": "RO", "CRO": "HR", "SLO": "SI", "SVK": "SK", "LUX": "LU",
}

# Abbott World Marathon Majors — reference membership (6 classic + Sydney, the
# 7th, added 2025). Matched dynamically to events by title token + city. Each
# entry: (title-token that must appear, city-token that must appear, ISO2).
_MAJORS = [
    ("tokyo", "tokyo", "JP"),
    ("boston", "boston", "US"),
    ("london", "london", "GB"),
    ("berlin", "berlin", "DE"),
    ("chicago", "chicago", "US"),
    ("new york", "new york", "US"),
    ("sydney", "sydney", "AU"),
]


def _fetch_wa_labels() -> list[dict]:
    """Return [{nome_norm, cidade_norm, iso2, data, selo}] from World Athletics."""
    resp = get(WA_URL, source="World Athletics (selos)")
    resp.raise_for_status()
    m = re.search(
        r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
        resp.text, re.S)
    if not m:
        raise ValueError("__NEXT_DATA__ não encontrado")
    data = json.loads(m.group(1))
    results = data["props"]["pageProps"]["calendarEvents"]["results"]

    out = []
    for ev in results:
        sub = (ev.get("competitionSubgroup") or "").strip().lower()
        selo = _SELO_MAP.get(sub)
        if not selo:
            continue
        date = (ev.get("startDate") or "")[:10]
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
            continue
        iso2 = _IOC_TO_ISO2.get((ev.get("countryCode") or "").strip().upper(), "")
        venue = ev.get("venueWithoutCountry") or ev.get("venue") or ""
        out.append({
            "nome": normalize_titulo_merge(ev.get("name") or ""),
            "cidade": normalize_titulo_merge(venue),
            "iso2": iso2,
            "data": date,
            "selo": selo,
        })
    return out


def _date_close(a: str, b: str, tol: int = 2) -> bool:
    """True if two ISO dates are within tol days (timezone/listing slop)."""
    try:
        from datetime import date as _d
        da = _d.fromisoformat(a)
        db = _d.fromisoformat(b)
        return abs((da - db).days) <= tol
    except ValueError:
        return False


def _matches(corrida: Corrida, wa: dict) -> bool:
    if wa["iso2"] and corrida.pais and wa["iso2"] != corrida.pais:
        return False
    if not _date_close(corrida.data_evento or "", wa["data"]):
        return False
    ct = normalize_titulo_merge(corrida.titulo)
    if not ct or not wa["nome"]:
        return False
    sim = difflib.SequenceMatcher(None, ct, wa["nome"]).ratio()
    if sim >= 0.72:
        return True
    # Strong city + meaningful shared tokens (e.g. "maratona internacional sao paulo")
    if wa["cidade"]:
        city_norm = normalize_titulo_merge(corrida.cidade)
        shared = set(ct.split()) & set(wa["nome"].split())
        if city_norm and city_norm in wa["nome"] and len(shared) >= 2:
            return True
    return False


def _apply_majors(corrida: Corrida) -> None:
    ct = normalize_titulo_merge(corrida.titulo)
    city = normalize_titulo_merge(corrida.cidade)
    for title_tok, city_tok, iso2 in _MAJORS:
        if corrida.pais == iso2 and title_tok in ct and (city_tok in city or city_tok in ct):
            corrida.major = True
            return


def enrich(corridas: list[Corrida]) -> None:
    """Annotate corridas in place with selo (World Athletics) and major (Abbott)."""
    # Majors first — pure reference match, never fails.
    for c in corridas:
        _apply_majors(c)

    try:
        labels = _fetch_wa_labels()
    except Exception as e:
        print(f"[selos] World Athletics indisponível — selos preservados do run anterior: {e}")
        return

    today = today_iso()
    future = [w for w in labels if w["data"] >= today]
    print(f"[selos] {len(future)} provas com selo (futuras) no World Athletics")

    n = 0
    for c in corridas:
        if not c.data_evento or c.data_evento < today:
            continue
        best = None
        for w in future:
            if _matches(c, w):
                if best is None or _SELO_RANK[w["selo"]] > _SELO_RANK[best]:
                    best = w["selo"]
        # Only overwrite when we have a fresh match; otherwise clear stale selo
        # so a delabelled race loses the badge next run (selo is dynamic).
        c.selo = best
        if best:
            n += 1
    print(f"[selos] {n} eventos receberam selo World Athletics; "
          f"{sum(1 for c in corridas if c.major)} marcados como Major")
