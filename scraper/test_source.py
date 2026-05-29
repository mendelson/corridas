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
    missing_distancias = 0
    bad_dist_shape = 0
    missing_link = 0
    missing_horario = 0
    missing_tipo = 0
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

        # Hard: distancias com shape errado (FonteInfo vazou para o campo errado)
        for d in (r.distancias or []):
            if not hasattr(d, "km") or hasattr(d, "nome"):
                bad_dist_shape += 1
                break

        # Threshold: sem distâncias (>70% = hard failure, >30% = warning, else info)
        if not r.distancias:
            missing_distancias += 1

        # Hard: sem link válido em qualquer FonteInfo
        has_link = False
        for f in (r.fontes or []):
            if f.link_evento or (f.links_inscricao and f.links_inscricao[0]):
                has_link = True
                break
        if not has_link:
            missing_link += 1

        # Hard: tipo inválido em qualquer FonteInfo
        for f in (r.fontes or []):
            if getattr(f, "tipo", None) not in ("inscricao", "organizador", "calendario"):
                missing_tipo += 1
                break

        # Info: sem horário (many events don't announce start time in advance)
        if not r.horario:
            missing_horario += 1

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
    if bad_dist_shape:
        failures.append(
            f"{bad_dist_shape}/{n} eventos com distancia de shape inválido "
            "(FonteInfo vazou para distancias?)"
        )
    if missing_link:
        failures.append(f"{missing_link}/{n} eventos sem nenhum link válido em fontes")
    if missing_tipo:
        failures.append(
            f"{missing_tipo}/{n} eventos com FonteInfo sem tipo válido "
            "(deve ser 'inscricao', 'organizador' ou 'calendario')"
        )

    # Hard failures — zero tolerance
    if missing_date:
        failures.append(f"{missing_date}/{n} eventos sem data_evento")
    if stale_date:
        failures.append(f"{stale_date}/{n} eventos com data > 30 dias no passado")

    # Distâncias: >70% missing = hard failure, >30% = warning, else info
    dist_frac = missing_distancias / n if n else 0
    if dist_frac > 0.70:
        failures.append(f"{missing_distancias}/{n} eventos sem distâncias")
    elif dist_frac > 0.30:
        warnings.append(f"{missing_distancias}/{n} eventos sem distâncias (>{int(dist_frac*100)}%)")
    elif missing_distancias:
        print(f"ℹ️   {source}: {missing_distancias}/{n} eventos sem distâncias")

    # Horário: informational only — many events don't announce start time in advance
    if missing_horario:
        print(f"ℹ️   {source}: {missing_horario}/{n} eventos sem horário")

    for w in warnings:
        print(f"⚠️   {source}: {w}")

    return failures


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("uso: python -m scraper.test_source <source>")
        sys.exit(1)
    sys.exit(run(sys.argv[1]))
