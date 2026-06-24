"""Project data/corridas.json into a slimmed web/corridas.json.

data/corridas.json is the scraper's full state (reconcile metadata, source
bookkeeping). The frontend only reads a subset of it, yet the web copy used to
be a byte-identical 20 MB duplicate downloaded by every visitor before the app
becomes interactive. This script writes web/corridas.json as a projection with
only what app.js consumes:

- top-level fields actually read by the frontend (drops id, miss_count,
  updated_at, periodo_inscricao, inscricoes_abertas);
- null/empty optional values omitted (the frontend already handles absence);
- fontes[].links_inscricao omitted when it merely duplicates link_evento —
  the frontend's documented fallback uses link_evento in that case;
- per-distance data/horario omitted when null (the expanded-card table only
  renders those columns when values differ, and absent == absent).

Event *content* is unchanged: same events, same order, same values.

Run in the pipeline instead of `cp data/corridas.json web/corridas.json`:
  python scripts/generate_web_data.py
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FULL = ROOT / "data" / "corridas.json"
SLIM = ROOT / "web" / "corridas.json"
BOOT = ROOT / "web" / "corridas-boot.json"

# First-paint shard window, anchored on the dataset's own gerado_em date (NOT
# the wall clock — keeps the file reproducible from data/corridas.json alone).
# −15d matches the frontend's default "past15" period filter; +60d covers the
# first screens of the date-sorted list. The full file loads in background.
BOOT_PAST_DAYS = 15
BOOT_FUTURE_DAYS = 60

# Top-level event fields the frontend reads (see app.js: c.<field>).
KEEP = (
    "titulo", "data_evento", "horario", "localizacao", "cidade", "estado",
    "pais", "distancias", "first_seen_at", "fontes",
    "selo", "major",
)
# Required fields are always kept even when empty, so the data-quality tests
# keep validating the web copy as-is.
ALWAYS = {"titulo", "data_evento", "localizacao", "estado", "pais",
          "distancias", "fontes"}


def _slim_distancia(d: dict) -> dict:
    out = {"km": d.get("km")}
    if d.get("data"):
        out["data"] = d["data"]
    if d.get("horario"):
        out["horario"] = d["horario"]
    return out


def _slim_fonte(f: dict) -> dict:
    out = {"nome": f.get("nome"), "link_evento": f.get("link_evento"),
           "tipo": f.get("tipo")}
    links = f.get("links_inscricao") or []
    if links and links != [f.get("link_evento")]:
        out["links_inscricao"] = links
    return out


def _slim_event(ev: dict) -> dict:
    out = {}
    for k in KEEP:
        v = ev.get(k)
        if k == "distancias":
            out[k] = [_slim_distancia(d) for d in (v or [])]
        elif k == "fontes":
            out[k] = [_slim_fonte(f) for f in (v or [])]
        elif v or k in ALWAYS:
            out[k] = v
    return out


def boot_window(gerado_em: str | None) -> tuple[str, str]:
    """[from, to] ISO dates for the boot shard, anchored on gerado_em."""
    from datetime import date, timedelta
    try:
        anchor = date.fromisoformat((gerado_em or "")[:10])
    except ValueError:
        anchor = date.today()
    return ((anchor - timedelta(days=BOOT_PAST_DAYS)).isoformat(),
            (anchor + timedelta(days=BOOT_FUTURE_DAYS)).isoformat())


def main() -> None:
    data = json.loads(FULL.read_text(encoding="utf-8"))
    corridas = data["corridas"] if isinstance(data, dict) else data
    gerado_em = data.get("gerado_em") if isinstance(data, dict) else None
    slim_events = [_slim_event(ev) for ev in corridas]
    slim = {
        "gerado_em": gerado_em,
        "total": len(corridas),
        "corridas": slim_events,
    }
    SLIM.write_text(json.dumps(slim, ensure_ascii=False, separators=(",", ":")),
                    encoding="utf-8")

    lo, hi = boot_window(gerado_em)
    boot_events = [ev for ev in slim_events if lo <= (ev.get("data_evento") or "") <= hi]
    boot = {
        "gerado_em": gerado_em,
        "parcial": True,  # tells app.js to fetch the full file in background
        "total": len(boot_events),
        "corridas": boot_events,
    }
    BOOT.write_text(json.dumps(boot, ensure_ascii=False, separators=(",", ":")),
                    encoding="utf-8")
    print(f"web/corridas.json: {len(corridas)} eventos, "
          f"{SLIM.stat().st_size/1e6:.1f} MB (full: {FULL.stat().st_size/1e6:.1f} MB)")
    print(f"web/corridas-boot.json: {len(boot_events)} eventos "
          f"({lo}..{hi}), {BOOT.stat().st_size/1e6:.1f} MB")


if __name__ == "__main__":
    main()
