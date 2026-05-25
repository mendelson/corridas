#!/usr/bin/env python3
"""Apply geo_cache fixes to corridas.json without making any HTTP calls."""
import json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scraper import geo as _geo

CORRIDAS_PATH = Path("data/corridas.json")
WEB_PATH = Path("web/corridas.json")

_valid_states_cache = {}

def _get_valid_states(pais):
    if pais not in _valid_states_cache:
        f = Path(f"web/locations/{pais}.json")
        if f.exists():
            data = json.loads(f.read_text())
            _valid_states_cache[pais] = {s["code"] for s in data.get("subdivisions", [])}
        else:
            _valid_states_cache[pais] = None
    return _valid_states_cache[pais]

raw = json.loads(CORRIDAS_PATH.read_text())
# corridas.json is either a list or a dict with a 'corridas' key
if isinstance(raw, list):
    data = raw
    wrapper = None
else:
    wrapper = raw
    data = raw.get("corridas", raw)

fixed_estado = 0
fixed_pais = 0
removed = 0

new_corridas = []
for c in data:
    loc = c.get("localizacao", "")

    # Skip events with empty localizacao (enforced by _is_valid)
    if not loc:
        print(f"  REMOVING (no localizacao): {c['id']} — {c.get('titulo','')}")
        removed += 1
        continue

    pais = c.get("pais", "")
    estado = c.get("estado", "")

    # Clear invalid estado
    if estado and estado not in ("??", "INT") and pais:
        valid = _get_valid_states(pais)
        if valid is not None and estado not in valid:
            print(f"  CLEARING bad estado={estado!r} for pais={pais} on {c['id']}")
            c["estado"] = ""
            estado = ""

    needs_estado = not estado or estado in ("??", "INT")
    needs_pais = not pais or pais in ("??", "", "INT")

    if needs_estado or needs_pais:
        cidade = c.get("cidade", "") or c.get("localizacao", "")
        city_part = cidade.split(",")[0].strip() if cidade else ""

        # Skip virtual/online city names
        if city_part.lower() in ("anytime", "virtual", "online"):
            print(f"  REMOVING (virtual city): {c['id']} — {c.get('titulo','')}")
            removed += 1
            continue

        if city_part:
            resolved_pais, resolved_estado = _geo.resolve(city_part, "", pais or "BR")
            if needs_pais and resolved_pais and resolved_pais not in ("??", ""):
                c["pais"] = resolved_pais
                pais = resolved_pais
                fixed_pais += 1
            if needs_estado and resolved_estado:
                c["estado"] = resolved_estado
                fixed_estado += 1
                if resolved_pais and resolved_pais != pais and resolved_pais not in ("??", ""):
                    c["pais"] = resolved_pais
                    fixed_pais += 1

    new_corridas.append(c)

print(f"\nResults: removed={removed}, fixed_estado={fixed_estado}, fixed_pais={fixed_pais}")
print(f"Events before: {len(data)}, after: {len(new_corridas)}")

if wrapper is not None:
    wrapper["corridas"] = new_corridas
    wrapper["total"] = len(new_corridas)
    out = wrapper
else:
    out = new_corridas

CORRIDAS_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2))
WEB_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2))
print("Saved corridas.json and web/corridas.json")
