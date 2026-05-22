"""Run a single scraper source and report results — used by CI test workflows."""
from __future__ import annotations
import importlib
import json
import os
import sys
from datetime import date, timedelta

# Signal scrapers to skip expensive per-event enrichment steps (e.g. fetching
# individual event pages for location data) that are not needed for source health checks.
os.environ.setdefault("SCRAPER_TEST", "1")


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
        msg = str(exc)
        print(f"❌  {source}: exceção durante scrape()\n    {exc}")
        if "403" in msg or "Forbidden" in msg:
            print("FAILURE_NOTE:HTTP 403")
        elif "timeout" in msg.lower() or "timed out" in msg.lower():
            print("FAILURE_NOTE:timeout")
        elif "cloudflare" in msg.lower():
            print("FAILURE_NOTE:Cloudflare")
        else:
            print("FAILURE_NOTE:exceção")
        return 1

    n = len(results)
    if n == 0:
        print(f"⚠️   {source}: 0 eventos retornados")
        print("FAILURE_NOTE:0 eventos")
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

    failures = _validate(source, results)
    if failures:
        for msg in failures:
            print(f"❌  {source}: {msg}")
        print(f"FAILURE_NOTE:{failures[0]}")
        return 1

    return 0


def _validate(source: str, results: list) -> list[str]:
    """Return a list of failure strings (empty = all good)."""
    today = date.today().isoformat()
    stale_cutoff = (date.today() - timedelta(days=30)).isoformat()

    failures: list[str] = []
    warnings: list[str] = []

    bad_titulo = 0
    today_in_id = 0
    missing_date = 0
    stale_date = 0
    seen_ids: dict[str, int] = {}

    for r in results:
        # Hard: título inválido
        if not r.titulo or len(r.titulo) < 3:
            bad_titulo += 1

        # Hard: ID contém a data de hoje → muda a cada run, quebra reconciliação
        if today in (r.id or ""):
            today_in_id += 1

        # Duplicate IDs within the batch
        seen_ids[r.id] = seen_ids.get(r.id, 0) + 1

        # Soft: data ausente ou muito no passado
        if not r.data_evento:
            missing_date += 1
        elif r.data_evento < stale_cutoff:
            stale_date += 1

    n = len(results)

    # Hard failures
    if bad_titulo:
        failures.append(f"{bad_titulo}/{n} eventos com título inválido (vazio ou < 3 chars)")
    if today_in_id:
        failures.append(
            f"{today_in_id}/{n} IDs contêm a data de hoje '{today}' — "
            "ID muda a cada run, quebra first_seen_at"
        )
    dup_ids = {id_: cnt for id_, cnt in seen_ids.items() if cnt > 1}
    if dup_ids:
        examples = list(dup_ids.items())[:3]
        failures.append(
            f"{len(dup_ids)} IDs duplicados no batch: "
            + ", ".join(f"'{k}'×{v}" for k, v in examples)
        )

    # Soft warnings (printed but don't fail unless thresholds exceeded)
    if missing_date / n > 0.5:
        warnings.append(f"{missing_date}/{n} eventos sem data_evento")
    if stale_date / n > 0.3:
        warnings.append(f"{stale_date}/{n} eventos com data > 30 dias no passado")

    for w in warnings:
        print(f"⚠️   {source}: {w}")

    return failures


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("uso: python -m scraper.test_source <source>")
        sys.exit(1)
    sys.exit(run(sys.argv[1]))
