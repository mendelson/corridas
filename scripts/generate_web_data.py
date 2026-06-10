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

# Top-level event fields the frontend reads (see app.js: c.<field>).
KEEP = (
    "titulo", "data_evento", "horario", "localizacao", "cidade", "estado",
    "pais", "distancias", "imagem_url", "fotos", "first_seen_at", "fontes",
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


def main() -> None:
    data = json.loads(FULL.read_text(encoding="utf-8"))
    corridas = data["corridas"] if isinstance(data, dict) else data
    slim = {
        "gerado_em": data.get("gerado_em") if isinstance(data, dict) else None,
        "total": len(corridas),
        "corridas": [_slim_event(ev) for ev in corridas],
    }
    SLIM.write_text(json.dumps(slim, ensure_ascii=False, separators=(",", ":")),
                    encoding="utf-8")
    print(f"web/corridas.json: {len(corridas)} eventos, "
          f"{SLIM.stat().st_size/1e6:.1f} MB (full: {FULL.stat().st_size/1e6:.1f} MB)")


if __name__ == "__main__":
    main()
