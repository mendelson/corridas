"""Run a single scraper source and report results — used by CI test workflows."""
from __future__ import annotations
import importlib
import json
import sys


def run(source: str) -> int:
    """Import and run source.scrape(). Returns exit code (0 = pass, 1 = fail)."""
    mod = None
    for mod_path in [
        f"scraper.sources.{source}",
        f"scraper.sources.majors.{source.split('/')[-1]}",
    ]:
        try:
            mod = importlib.import_module(mod_path)
            break
        except ModuleNotFoundError:
            continue

    if mod is None:
        print(f"❌  fonte '{source}' não encontrada")
        return 1

    try:
        results = mod.scrape()
    except Exception as exc:
        print(f"❌  {source}: exceção durante scrape()\n    {exc}")
        return 1

    n = len(results)
    if n == 0:
        print(f"⚠️   {source}: 0 eventos retornados")
        return 1

    print(f"✅  {source}: {n} evento(s)")
    for r in results[:5]:
        dists = ", ".join(str(d.km) for d in (r.distancias or []))
        line = {"titulo": r.titulo, "data": r.data_evento, "estado": r.estado}
        if dists:
            line["km"] = dists
        print("   ", json.dumps(line, ensure_ascii=False))
    if n > 5:
        print(f"    ... e mais {n - 5}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("uso: python -m scraper.test_source <source>")
        sys.exit(1)
    sys.exit(run(sys.argv[1]))
