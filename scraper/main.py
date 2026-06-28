"""Orchestrator: run all scrapers, merge, and persist data/corridas.json."""
from __future__ import annotations
import html as _html
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from datetime import date, timedelta
from pathlib import Path

from .merger import are_duplicates, merge_rodada, _merge_pair
from .enrichment_selos import enrich as _enrich_selos
from .models import Corrida, Distancia, FonteInfo, PeriodoInscricao
from .utils import now_iso, today_iso, normalize_cidade, validate_image_url, is_kids_event, horario_required
from .http_client import get_direct as http_get_direct
from . import geo as _geo

# ---------------------------------------------------------------------------
# Source registry
# ---------------------------------------------------------------------------

from .sources import (
    atletis,
    central_da_corrida,
    conta_passos,
    ticket_sports,
    maratona_rio,
    maratona_porto_alegre,
    sp_city_marathon,
    tf_sports,
    tf_sports_app,
    iguana_sports,
    yescom,
    ativo,
    mks_esportes,
    corridas_brasil,
    minhas_inscricoes,
    correr_brasilia,
    bora_correr,
    brasil_que_corre,
    portal_das_corridas,
    sesc_df,
    runner_brasil,
    brasil_corrida,
    circuito_das_estacoes,
    largada_esportiva,
    volta_do_lago,
    runsignup,
    halfmarathons,
    asdeporte,
    carreras_mexico,
    raceroster,
    usroadrunning,
    worldsmarathons,
    finishers,
    # letsdothis,   # inviável: WAF bloqueia todos os proxies — ver README
    # world_athletics,  # desativada 2026-06-04 — ver docs/source-research/world_athletics.md
)
from .sources.evento_unico import (
    tokyo,
    boston,
    london,
    berlin,
    chicago,
    nyc,
    sydney,
    venice,
    prague,
    copenhagen,
    stockholm,
    amsterdam,
    dublin,
    athens,
    valencia,
    comrades,
    paris,
    edinburgh,
    great_north_run,
    cardiff_half,
    manchester,
    manchester_half,
    brighton,
    sao_silvestre,
)

SOURCES = [
    # API-based / well-structured (nationwide)
    atletis,
    central_da_corrida,
    ticket_sports,
    tf_sports,
    tf_sports_app,
    iguana_sports,
    yescom,
    ativo,
    mks_esportes,
    # Calendar pages (nationwide)
    corridas_brasil,
    minhas_inscricoes,
    runner_brasil,
    brasil_corrida,
    portal_das_corridas,
    # DF-specific sources
    conta_passos,
    correr_brasilia,
    bora_correr,
    brasil_que_corre,
    sesc_df,
    # Multi-city circuit events (via dedicated API)
    circuito_das_estacoes,
    # Brazilian running event platforms
    largada_esportiva,
    # Single-event sources (BR)
    maratona_rio,
    maratona_porto_alegre,
    sp_city_marathon,
    sao_silvestre,
    # Single-event sources (international) — the ⭐ ones below are the 7 Abbott
    # World Marathon Majors; the rest are other notable international races.
    tokyo,
    boston,
    london,
    berlin,
    chicago,
    nyc,
    sydney,
    venice,
    # — more European races
    prague,
    copenhagen,
    stockholm,
    amsterdam,
    dublin,
    athens,
    valencia,
    comrades,
    paris,
    # UK Events
    edinburgh,
    great_north_run,
    cardiff_half,
    manchester,
    manchester_half,
    brighton,
    # Single events (DF)
    volta_do_lago,
    # US/global running calendar
    runsignup,
    halfmarathons,
    raceroster,
    usroadrunning,
    worldsmarathons,
    finishers,
    # Mexican running calendars
    asdeporte,
    carreras_mexico,
    # IAAF Label Road Races
    # world_athletics,  # desativada 2026-06-04 — ver docs/source-research/world_athletics.md
]

# Selective-rescrape mode: when SCRAPER_SOURCES is set, only the listed sources
# are run and other events are patched in-place without touching their miss_count.
# Pass a comma-separated list of source keys (e.g. "worldathletics,runsignup").
# Special value "geo" skips all scrapers and just re-runs _resolve_missing_locations.
_SELECTIVE_SOURCES: frozenset[str] = frozenset(
    s.strip() for s in os.environ.get("SCRAPER_SOURCES", "").split(",") if s.strip()
)

DATA_PATH       = Path(__file__).parent.parent / "data" / "corridas.json"
HIST_DIR        = Path(__file__).parent.parent / "data" / "historico"
STATUS_PATH     = Path(__file__).parent.parent / "data" / "source-status.json"


# ---------------------------------------------------------------------------
# JSON serialization helpers
# ---------------------------------------------------------------------------

# Backfill map for legacy corridas.json records that predate the tipo field.
# Only non-calendario entries are listed; everything else defaults to "calendario".
_LEGACY_TIPO: dict[str, str] = {
    # inscricao
    "Asdeporte":                        "inscricao",
    "Ativo":                            "inscricao",
    "Atletis":                          "inscricao",
    "Minhas Inscrições":                "inscricao",
    "Portal das Corridas":              "inscricao",
    "Race Roster":                      "inscricao",
    "RunSignup":                        "inscricao",
    "Ticket Sports":                    "inscricao",
    "Yescom":                           "inscricao",
    # organizador
    "Circuito das Estações":            "organizador",
    "Maratona de Porto Alegre":         "organizador",
    "Maratona do Rio":                  "organizador",
    "MKS Esportes":                     "organizador",
    "São Silvestre":                    "organizador",
    "SESC DF":                          "organizador",
    "SP City Marathon":                 "organizador",
    "TF Sports":                        "organizador",
    "TF Sports App":                    "organizador",
    "Volta do Lago":                    "organizador",
    # eventos únicos (grandes corridas internacionais)
    "Amsterdam Marathon":               "organizador",
    "Athens Classic Marathon":          "organizador",
    "BMW Berlin Marathon":              "organizador",
    "Bank of America Chicago Marathon": "organizador",
    "Boston Marathon":                  "organizador",
    "Brighton Marathon":                "organizador",
    "Cardiff Half Marathon":            "organizador",
    "Copenhagen Marathon":              "organizador",
    "Dublin City Marathon":             "organizador",
    "Edinburgh Marathon Festival":      "organizador",
    "Great North Run":                  "organizador",
    "Manchester Half Marathon":         "organizador",
    "Manchester Marathon":              "organizador",
    "Paris Marathon":                   "organizador",
    "Prague Marathon":                  "organizador",
    "Stockholm Marathon":               "organizador",
    "TCS London Marathon":              "organizador",
    "TCS New York City Marathon":       "organizador",
    "TCS Sydney Marathon":              "organizador",
    "Tokyo Marathon":                   "organizador",
    "Valencia Marathon":                "organizador",
    "Venice Marathon":                  "organizador",
}


def _corrida_to_dict(c: Corrida) -> dict:
    d = asdict(c)
    return d


def _dict_to_corrida(d: dict) -> Corrida:
    # Only accept dicts with 'km'; FonteInfo objects (nome/link_evento) that
    # leaked into distancias via a past merger bug are silently skipped.
    distancias = [
        Distancia(**dist)
        for dist in d.get("distancias", [])
        if "km" in dist
    ]
    fontes = []
    for f in d.get("fontes", []):
        nome = f.get("nome", "")
        tipo = f.get("tipo") or _LEGACY_TIPO.get(nome, "calendario")
        fontes.append(FonteInfo(
            nome=nome,
            link_evento=f["link_evento"],
            links_inscricao=f.get("links_inscricao", []),
            tipo=tipo,
        ))
    pi = d.get("periodo_inscricao")
    periodo = PeriodoInscricao(**pi) if pi else None
    return Corrida(
        id=d["id"],
        titulo=d["titulo"],
        data_evento=d.get("data_evento", ""),
        horario=d.get("horario"),
        localizacao=d.get("localizacao", ""),
        cidade=d.get("cidade", ""),
        estado=d.get("estado", ""),
        pais=d.get("pais", "BR"),
        distancias=distancias,
        imagem_url=validate_image_url(d.get("imagem_url")),
        inscricoes_abertas=d.get("inscricoes_abertas"),
        periodo_inscricao=periodo,
        fontes=fontes,
        miss_count=d.get("miss_count", 0),
        first_seen_at=d.get("first_seen_at", now_iso()),
        updated_at=d.get("updated_at", now_iso()),
        fotos=d.get("fotos", []),
    )


# ---------------------------------------------------------------------------
# Load / save
# ---------------------------------------------------------------------------

def load_existing() -> dict[str, Corrida]:
    if not DATA_PATH.exists():
        return {}
    try:
        with DATA_PATH.open(encoding="utf-8") as f:
            raw = json.load(f)
    except Exception as e:
        print(f"[main] erro ao carregar JSON existente: {e}")
        return {}
    result: dict[str, Corrida] = {}
    errors = 0
    for c in raw.get("corridas", []):
        try:
            corrida = _dict_to_corrida(c)
            # The stored file can contain duplicate ids (legacy merge bug). When it
            # does, one copy is sometimes corrupt — empty fontes with a FonteInfo
            # leaked into distancias. Keep the more complete copy (more fontes)
            # instead of blindly taking the last occurrence, so a corrupt duplicate
            # never overwrites a healthy record.
            prev = result.get(corrida.id)
            if prev is None or len(corrida.fontes) >= len(prev.fontes):
                result[corrida.id] = corrida
        except Exception as e:
            errors += 1
            print(f"[main] ignorando evento corrompido '{c.get('id', '?')}': {e}")
    if errors:
        print(f"[main] {errors} evento(s) ignorado(s), {len(result)} carregados")
    return result


def _normalize_all_locations(corridas: list[Corrida]) -> None:
    """Normalize cidade/localizacao in-place (accents, HTML entities, casing)."""
    for c in corridas:
        c.cidade = normalize_cidade(c.cidade)
        if c.pais == "BR":
            parts = [p for p in [c.cidade, c.estado] if p]
            c.localizacao = ", ".join(parts)
        else:
            c.localizacao = _html.unescape(c.localizacao or "").strip().strip(", ")


def _resolve_missing_locations(corridas: list[Corrida]) -> None:
    """Fill in empty or invalid estado (and incorrect pais) using geo.resolve() + cache."""
    import json as _json
    from pathlib import Path as _Path

    _valid_states_map: dict[str, set | None] = {}

    def _get_valid_states(pais: str) -> set | None:
        if pais not in _valid_states_map:
            try:
                f = _Path(__file__).parent.parent / "web" / "locations" / f"{pais}.json"
                if f.exists():
                    data = _json.loads(f.read_text())
                    _valid_states_map[pais] = {s["code"] for s in data.get("subdivisions", [])}
                else:
                    _valid_states_map[pais] = None
            except Exception:
                _valid_states_map[pais] = None
        return _valid_states_map[pais]

    fixed = 0
    for c in corridas:
        # Clear obviously invalid estado so _geo.resolve() can retry with correct data
        if c.estado and c.estado not in ("??", "INT") and c.pais:
            valid = _get_valid_states(c.pais)
            if valid is not None and c.estado not in valid:
                c.estado = ""

        needs_estado = not c.estado or c.estado in ("??", "INT")
        needs_pais   = not c.pais  or c.pais  in ("??", "", "INT")
        if c.estado == "INT":
            c.estado = ""
        if c.pais == "INT":
            c.pais = ""
        if not (needs_estado or needs_pais):
            continue
        city_part = (c.cidade or c.localizacao or "").split(",")[0].strip()
        resolved_pais, resolved_estado = _geo.resolve(
            city_part, "", c.pais or "BR"
        )
        if needs_pais and resolved_pais and resolved_pais not in ("??", ""):
            c.pais = resolved_pais
        if needs_estado and resolved_estado:
            c.estado = resolved_estado
            fixed += 1
            # When geo resolves to a different country (wrong-country event), update pais too
            if resolved_pais and resolved_pais != c.pais and resolved_pais not in ("??", ""):
                c.pais = resolved_pais
    if fixed:
        print(f"[main] {fixed} estado(s) resolvido(s) pelo geo cache")


def _ensure_inscricao_links(corridas: list[Corrida]) -> None:
    """Guarantee every FonteInfo has links_inscricao non-empty.

    Per CLAUDE.md: every event must surface at least one working link in
    the UI. When a scraper produces links_inscricao=[] we fall back to
    [link_evento] so the register button is never silently absent.
    """
    fixed = 0
    for c in corridas:
        for fonte in c.fontes:
            if not fonte.links_inscricao and fonte.link_evento:
                fonte.links_inscricao = [fonte.link_evento]
                fixed += 1
    if fixed:
        print(f"[main] {fixed} fonte(s) com links_inscricao preenchido a partir de link_evento")


_KEEP_PAST_DAYS  = 15   # matches frontend's deepest past window (past15 filter)
_ARCHIVE_PAST_DAYS = 40  # events older than this move to historico/


def _archive(corridas: list[Corrida]) -> None:
    """Merge events older than _ARCHIVE_PAST_DAYS into data/historico/YYYY-MM.json."""
    if not corridas:
        return
    HIST_DIR.mkdir(parents=True, exist_ok=True)
    by_month: dict[str, list[Corrida]] = {}
    for c in corridas:
        month = c.data_evento[:7]  # "YYYY-MM"
        by_month.setdefault(month, []).append(c)

    for month, batch in by_month.items():
        path = HIST_DIR / f"{month}.json"
        existing: dict[str, dict] = {}
        if path.exists():
            try:
                existing = {e["id"]: e for e in json.loads(path.read_text())["corridas"]}
            except Exception:
                pass
        for c in batch:
            existing[c.id] = _corrida_to_dict(c)
        records = sorted(existing.values(), key=lambda r: r.get("data_evento", ""))
        path.write_text(
            json.dumps({"mes": month, "total": len(records), "corridas": records},
                       ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    total = sum(len(v) for v in by_month.values())
    print(f"[main] {total} corrida(s) arquivada(s) em {HIST_DIR}")


def save(corridas: list[Corrida]) -> None:
    archive_cutoff = (date.today() - timedelta(days=_ARCHIVE_PAST_DAYS)).isoformat()
    display_cutoff = (date.today() - timedelta(days=_KEEP_PAST_DAYS)).isoformat()

    to_archive = [c for c in corridas if c.data_evento and c.data_evento < archive_cutoff]
    active = [c for c in corridas if not c.data_evento or c.data_evento >= display_cutoff]

    _archive(to_archive)

    corridas_sorted = sorted(
        active,
        key=lambda c: c.data_evento if c.data_evento else "9999-99-99",
    )
    payload = {
        "gerado_em": now_iso(),
        "total": len(corridas_sorted),
        "corridas": [_corrida_to_dict(c) for c in corridas_sorted],
    }
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    with DATA_PATH.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"[main] {len(corridas_sorted)} corridas salvas em {DATA_PATH}")


# ---------------------------------------------------------------------------
# Reconciliation
# ---------------------------------------------------------------------------

def _fields_changed(existing: Corrida, incoming: Corrida) -> bool:
    for field in ["titulo", "data_evento", "horario", "localizacao", "cidade",
                  "estado", "pais", "distancias", "imagem_url", "inscricoes_abertas",
                  "periodo_inscricao", "fontes"]:
        if getattr(existing, field) != getattr(incoming, field):
            return True
    return False


def _update_from(existing: Corrida, incoming: Corrida) -> Corrida:
    # Always refresh titulo/cidade/estado/id from the latest scrape so older
    # broken values (e.g. mojibake before encoding fix) don't persist.
    if incoming.titulo:
        existing.titulo = incoming.titulo
        existing.id = incoming.id
    # Always refresh cidade from the latest scrape so stale values
    # (e.g. event names incorrectly stored as city) don't persist.
    # Sources that enrich cidade in-process (e.g. carreras_mexico) do so
    # before reconcile runs, so enriched values are already in incoming.
    existing.cidade = incoming.cidade
    if incoming.estado and incoming.estado not in ("??", "INT"):
        existing.estado = incoming.estado
    elif not incoming.estado:
        # Clear wrong estados so _resolve_missing_locations() can retry on next run
        existing.estado = ""
    elif existing.estado in ("??", "INT"):
        existing.estado = ""
    if existing.pais == "INT":
        existing.pais = ""
    if incoming.pais and incoming.pais not in ("??", ""):
        existing.pais = incoming.pais
    existing.data_evento = incoming.data_evento or existing.data_evento
    existing.horario = incoming.horario or existing.horario
    existing.localizacao = incoming.localizacao or existing.localizacao
    if incoming.distancias:
        existing.distancias = incoming.distancias
    if incoming.imagem_url:
        existing.imagem_url = incoming.imagem_url
    if incoming.inscricoes_abertas is not None:
        existing.inscricoes_abertas = incoming.inscricoes_abertas
    if incoming.periodo_inscricao is not None:
        existing.periodo_inscricao = incoming.periodo_inscricao
    existing.fontes = incoming.fontes
    existing.miss_count = 0
    existing.updated_at = now_iso()
    return existing


# Statuses that mean "the page exists but is bot-protected" (Cloudflare / WAF
# challenge). A human visiting still sees the event, so these must NOT count as a
# miss — only a hard not-found (404/410) or a connection failure means the page
# is actually gone.
_ALIVE_WAF_STATUS = {403, 406, 429, 503}


def _check_and_refresh_links(existing: Corrida) -> bool:
    """True if the event still has a live page.

    Checks the event page AND every inscription link: once registration closes,
    an inscription URL may 404/redirect while the event page stays up, so both
    must be considered. Uses get_direct (which does NOT raise on a WAF status) so
    a bot-protected-but-live page (e.g. Ticket Sports behind Cloudflare with
    registration closed) counts as alive rather than as a miss.
    """
    links: list[str] = []
    for fonte in existing.fontes:
        if fonte.link_evento:
            links.append(fonte.link_evento)
        links.extend(fonte.links_inscricao)
    links = list(dict.fromkeys(l for l in links if l))  # dedup, drop empties
    if not links:
        return False
    for link in links:
        try:
            resp = http_get_direct(link, timeout=15)
        except Exception:
            continue  # connection error / timeout — try the next link
        sc = resp.status_code
        if sc in _ALIVE_WAF_STATUS:
            return True  # page exists, just bot-protected — keep the event
        if sc != 200:
            continue  # 404/410/etc. — this link is dead, try the next
        return True
    return False


def _find_match(incoming: Corrida, estado_anterior: dict[str, Corrida]) -> Corrida | None:
    # Exact id match
    if incoming.id in estado_anterior:
        return estado_anterior[incoming.id]
    # Similarity match (same criteria as merger)
    for existing in estado_anterior.values():
        if are_duplicates(incoming, existing):
            return existing
    return None


# Wall-clock budget for the unmatched-event link-recheck phase in reconcile().
# Cache/network behaviour is variable, so a time bound is more robust than a
# count. Generous enough that a healthy run (few unmatched events) finishes well
# inside it; small enough that a pathological run (a high-volume source returning
# nothing, dumping its whole catalogue into the recheck) can't ride the CI
# timeout. Override with RECHECK_BUDGET_S. Default 900s = 15 min.
_RECHECK_BUDGET_S: float = float(os.environ.get("RECHECK_BUDGET_S", "900"))

# Wall-clock budget for the whole scraping phase (run_all_scrapers). A healthy
# full run drains in ~15 min; this bounds a single hung source from pinning the
# executor for the entire CI job. Override with SCRAPE_BUDGET_S. Default 1800s.
_SCRAPE_BUDGET_S: float = float(os.environ.get("SCRAPE_BUDGET_S", "1800"))


def reconcile(
    estado_anterior: dict[str, Corrida],
    estado_atual: list[Corrida],
) -> list[Corrida]:
    today = today_iso()
    matched_ids: set[str] = set()
    result: list[Corrida] = []

    for incoming in estado_atual:
        match = _find_match(incoming, estado_anterior)
        if match:
            matched_ids.add(match.id)
            if _fields_changed(match, incoming):
                result.append(_update_from(match, incoming))
            else:
                match.miss_count = 0
                result.append(match)
        else:
            result.append(incoming)

    # Handle events not found in current scrape
    # Index of survivors by (date, state): an unmatched old record that
    # duplicates one of them is a merger leftover (the same race once stored
    # under two source ids). Absorb its fontes into the survivor instead of
    # letting the link-recheck below resurrect the clone forever.
    by_date_uf: dict[tuple, list[Corrida]] = {}
    for kept in result:
        by_date_uf.setdefault((kept.data_evento, kept.estado), []).append(kept)

    unmatched_future: list[Corrida] = []
    for cid, existing in estado_anterior.items():
        if cid in matched_ids:
            continue
        # Past events are kept as-is — no link check needed
        if existing.data_evento and existing.data_evento < today:
            result.append(existing)
            continue
        # Drop events that are now known to be non-running (e.g. cycling events
        # that were added before the filter existed)
        if not _is_valid(existing):
            print(f"[main] removendo '{existing.titulo}' (falhou _is_valid)")
            continue
        twin = next(
            (kept for kept in by_date_uf.get((existing.data_evento, existing.estado), [])
             if are_duplicates(existing, kept)),
            None,
        )
        if twin is not None:
            _merge_pair(twin, existing)
            print(f"[main] '{existing.titulo}' ({existing.id}) absorvido como duplicata de {twin.id}")
            continue
        unmatched_future.append(existing)

    # Check inscription links in parallel for unmatched future events.
    #
    # This rescues events a source merely failed to return this run (a transient
    # blip must not drop a still-live race). But each recheck is a network call,
    # and when a high-volume source returns little or nothing for a run its
    # entire catalogue lands here at once — tens of thousands of checks. Left
    # unbounded the executor runs for over an hour, overflowing the CI timeout
    # and stalling the whole pipeline (the recheck phase, not scraping, was the
    # cause of the data-pipeline/validate timeouts).
    #
    # So the phase is wall-clock bounded, mirroring the Nominatim per-run budget
    # in geo.py: events not rechecked before the deadline are kept untouched
    # (miss_count unchanged — they were never actually checked) and revisited
    # next run, instead of pinning the runner. Only events whose recheck really
    # ran and failed advance toward the miss_count drop threshold.
    if unmatched_future:
        print(f"[main] verificando links de {len(unmatched_future)} evento(s) "
              f"não encontrado(s) no scrape (limite {_RECHECK_BUDGET_S}s)...")
        executor = ThreadPoolExecutor(max_workers=16)
        futures = {executor.submit(_check_and_refresh_links, ev): ev for ev in unmatched_future}
        done: set = set()
        rescued = dropped = 0
        try:
            for future in as_completed(futures, timeout=_RECHECK_BUDGET_S):
                existing = futures[future]
                done.add(future)
                try:
                    link_valid = future.result()
                except Exception:
                    link_valid = False

                if link_valid:
                    existing.miss_count = 0
                    existing.updated_at = now_iso()
                    result.append(existing)
                    rescued += 1
                else:
                    existing.miss_count += 1
                    if existing.miss_count < 10:
                        result.append(existing)
                    else:
                        print(f"[main] removendo '{existing.titulo}' (miss_count={existing.miss_count})")
                        dropped += 1
        except TimeoutError:
            pass

        # Events not reached before the deadline: keep as-is and defer to the
        # next run (do NOT touch miss_count — a missed recheck is not a failure).
        deferred = 0
        for future, existing in futures.items():
            if future not in done:
                result.append(existing)
                deferred += 1

        # Don't block on threads still stuck on a slow socket: each carries its
        # own httpx timeout and dies on its own shortly after. Blocking here
        # (shutdown(wait=True), the implicit `with`-exit behaviour) is exactly
        # what let one hung request pin the job until the CI timeout.
        executor.shutdown(wait=False, cancel_futures=True)
        print(f"[main] recheck de links: {rescued} resgatado(s), {dropped} removido(s), "
              f"{deferred} adiado(s) para a próxima execução")

    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Validation filter
# ---------------------------------------------------------------------------

_NAV_TITLES = {
    "calendário", "calendario", "calendrio", "listagem completa", "listagem",
    "sugira uma corrida", "sugira corrida", "outros estados", "corridasbr",
    "próximas corridas", "proximas corridas", "estados", "distrito federal",
    "espírito santo", "mato grosso", "mato grosso do sul", "minas gerais",
    "pernambuco", "rio de janeiro", "rio grande do norte", "rio grande do sul",
    "são paulo", "santa catarina", "calendário completo", "home", "menu",
    "buscar", "search", "início", "inicio", "sobre", "contato",
}

_NAV_FRAGMENTS = [
    "quero dicas", "por e-mail", "experiências além", "para todos e variados",
    "roteiros que fogem", "inspirações para", "suplementação saudável",
    "do treino ao lifestyle", "calendrio completo", "outros estados:",
]

_NON_RUNNING_KW = [
    # Cycling
    "pedal", "ciclismo", "ciclista", "bicicleta", " bike ", "mtb",
    "cycling", "cyclist", "pedalada", "gravel", "velódromo", "velodrome",
    "granfondo", "gran fondo", "gran-fondo", "fondo", "sportive",
    "uci ", "uci-",
    "l'étape", "l etape", "letape",  # Tour de France cycling sportives
    " gf ",  # Gran Fondo abbreviation (e.g. "6ª GF João Pessoa")
    # Triathlon / multisport
    "triathlon", "triathon", "duathlon", "ironman", "swimrun",
    "aquabike", "aqua bike", "aquathlon",
    # Open water swimming & aquatic sports
    "natação", "natacao", "nado ", "águas abertas", "aguas abertas",
    "travessia",  # open water crossings (Travessia do Fogo, Santos-Guarujá, etc.)
    "aquático", "aquatica", "aquático",
    "remo ", "canoagem", "kayak", "caiaque",
    "stand up paddle", "stand-up paddle",
    # Other non-running sports that may appear in aggregators
    "futebol", "voleibol", "vôlei", "volei", "basquete", "basquetebol",
    "handball", "handebol", "tênis", "badminton", "esgrima",
]

_TRI_DIGIT_RE = re.compile(r'\btri\d', re.IGNORECASE)


def _is_valid(c: Corrida) -> bool:
    # Events without any location are unusable
    if not c.localizacao:
        return False

    titulo_lower = c.titulo.lower().strip()

    # Reject empty or very short titles
    if len(titulo_lower) < 4:
        return False

    # Reject known navigation titles
    if titulo_lower in _NAV_TITLES:
        return False

    # Reject titles that contain navigation fragments
    if any(frag in titulo_lower for frag in _NAV_FRAGMENTS):
        return False

    # Reject non-running events (cycling, swimming, etc.)
    if any(kw in titulo_lower for kw in _NON_RUNNING_KW):
        return False

    # Reject kids-only races (brand names, or kids wording with no adult distance).
    # This also lets stale kids events age out of an existing dataset even when
    # their source page still resolves (the reconcile link-rescue would otherwise
    # keep them forever).
    if is_kids_event(c.titulo, c.distancias):
        return False

    # Reject triathlon events named "Tri<number>" (e.g. "Tri257")
    if _TRI_DIGIT_RE.search(titulo_lower):
        return False

    if not c.data_evento:
        return False

    # Distances are mandatory
    if not c.distancias:
        return False

    # Reject if title looks like concatenated state abbreviations (nav garbage)
    if len(titulo_lower) > 20 and titulo_lower.replace(" ", "").isalpha() and titulo_lower == titulo_lower.lower() and " " not in c.titulo:
        return False

    return True


def _source_status_key(src) -> str:
    """Map a source module to its key in source-status.json.

    scraper.sources.carreras_mexico → carreras_mexico
    scraper.sources.evento_unico.london   → evento_unico/london
    """
    name = src.__name__
    prefix = "scraper.sources."
    return name[len(prefix):].replace(".", "/") if name.startswith(prefix) else name


def _prioritize_failed(sources: list) -> tuple[list, list]:
    """Return (ordered_sources, failed_sources).

    Failed sources (status == 'fail' in the previous run) come first so they
    are submitted to the thread pool immediately. The relative order within
    each group is preserved.
    """
    try:
        prev: dict = json.loads(STATUS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return list(sources), []

    failed, healthy = [], []
    for src in sources:
        if prev.get(_source_status_key(src), {}).get("status") == "fail":
            failed.append(src)
        else:
            healthy.append(src)
    return failed + healthy, failed


def run_all_scrapers(selective: frozenset[str] = frozenset()) -> list[Corrida]:
    active = SOURCES
    if selective:
        if "geo" in selective:
            active = []  # geo-only mode: skip all scrapers, just resolve locations
        else:
            active = [s for s in SOURCES if _source_status_key(s) in selective]
            if not active:
                print(f"[main] AVISO: SCRAPER_SOURCES={selective!r} não casou nenhuma fonte conhecida")
            else:
                print(f"[main] modo seletivo: {[_source_status_key(s) for s in active]}")

    if not active:
        return []

    all_corridas: list[Corrida] = []
    ordered, failed = _prioritize_failed(active)
    if failed:
        print(f"[main] priorizando {len(failed)} fonte(s) com falha anterior: "
              f"{', '.join(_source_status_key(s) for s in failed)}")

    # Each source hits a distinct domain, so concurrency is bounded by the runner,
    # not a shared rate limit (the Scrapestack 429 that justified keeping this at 8
    # was removed in #208). Raised to 12 to drain the queue behind the few slow
    # Playwright-fallback sources faster.
    #
    # Wall-clock bounded: a single source whose scrape() hangs (a socket read that
    # never trips httpx's timeout, a Playwright stall, a redirect loop) would
    # otherwise pin the executor here forever — the `with`-block exit does
    # shutdown(wait=True) and blocks on the stuck thread until the CI job times
    # out. (Observed: all sources done ~12 min in, then 100+ min of silence on one
    # hung source before the kill.) Sources not finished before the deadline are
    # abandoned this run; their events survive via reconcile (kept as unmatched,
    # miss_count untouched) and are re-fetched next run. The names are logged so a
    # repeatedly-hanging source can be diagnosed/disabled.
    executor = ThreadPoolExecutor(max_workers=12)
    futures = {executor.submit(src.scrape): src.__name__ for src in ordered}
    done: set = set()
    try:
        for future in as_completed(futures, timeout=_SCRAPE_BUDGET_S):
            done.add(future)
            source_name = futures[future]
            try:
                corridas = future.result()
                all_corridas.extend(corridas)
            except Exception as e:
                print(f"[main] fonte {source_name} falhou: {e}")
    except TimeoutError:
        hung = [futures[f] for f in futures if f not in done]
        print(f"[main] AVISO: {len(hung)} fonte(s) excederam o limite de "
              f"{_SCRAPE_BUDGET_S}s e foram abandonadas nesta execução "
              f"(eventos preservados via reconcile): {', '.join(sorted(hung))}")
    # Don't block on threads still stuck on a slow socket; each carries its own
    # httpx timeout and dies on its own shortly after.
    executor.shutdown(wait=False, cancel_futures=True)

    return all_corridas


def _selective_patch(
    fresh: list[Corrida],
    existing: dict[str, Corrida],
) -> list[Corrida]:
    """Patch events from selected sources without touching miss_count of others.

    Used in selective-rescrape mode. Events from non-selected sources are kept
    exactly as they are. Events from selected sources are updated or added.
    New events from selected sources not in existing are appended.
    """
    fresh_by_id = {c.id: c for c in fresh}
    result = []
    for cid, c in existing.items():
        if cid in fresh_by_id:
            incoming = fresh_by_id[cid]
            if _fields_changed(c, incoming):
                result.append(_update_from(c, incoming))
            else:
                result.append(c)
        else:
            result.append(c)
    # Append genuinely new events
    for c in fresh:
        if c.id not in existing:
            result.append(c)
    return result


def _drop_invalid_location_events(corridas: list[Corrida]) -> list[Corrida]:
    """Final safety net: remove events whose pais/estado don't satisfy the test requirements.

    This catches any edge cases where scraper-level guards or geo resolution failed to
    produce a valid (pais, estado) pair.  Logged prominently so the root cause can be
    fixed in the relevant scraper.
    """
    import json as _json
    from pathlib import Path as _Path

    _valid: dict[str, set | None] = {}

    def _states(pais: str) -> set | None:
        if pais not in _valid:
            f = _Path(__file__).parent.parent / "web" / "locations" / f"{pais}.json"
            try:
                _valid[pais] = {s["code"] for s in _json.loads(f.read_text()).get("subdivisions", [])} if f.exists() else None
            except Exception:
                _valid[pais] = None
        return _valid[pais]

    ok, dropped = [], []
    for c in corridas:
        states = _states(c.pais) if c.pais else None
        if states is None:
            dropped.append(f"{c.id} (pais={c.pais!r} sem locations JSON)")
        elif not c.estado:
            dropped.append(f"{c.id} (pais={c.pais}, estado vazio)")
        elif c.estado not in states:
            dropped.append(f"{c.id} (pais={c.pais}, estado={c.estado!r} inválido)")
        else:
            ok.append(c)

    if dropped:
        print(f"[main] AVISO: {len(dropped)} evento(s) removido(s) por localização inválida:")
        for d in dropped[:20]:
            print(f"  • {d}")
        if len(dropped) > 20:
            print(f"  … e mais {len(dropped) - 20}")

    return ok


def _strip_overmerged_fontes(corridas: list[Corrida]) -> None:
    """Remove fontes that leaked across many distinct events via a bad merge.

    When the same (source name, inscription link) appears on 3+ distinct event
    records, the link belongs to a single event and was spread to the others by
    a historical over-merge (e.g. a multi-city series whose editions share a
    title and state).  Keep the fonte on events where it is the only source —
    its native record — and strip it from events that still carry another fonte,
    so no event is ever left without a link.  Mirrors the guarantee enforced by
    tests/test_site.py::test_no_inscription_link_shared_across_many_events.
    """
    from collections import defaultdict

    groups: dict[tuple[str, str], list] = defaultdict(list)
    for c in corridas:
        for f in c.fontes:
            for l in (f.links_inscricao or []):
                if l:
                    groups[(f.nome, l.rstrip("/").lower())].append((c, f))

    stripped = 0
    for (nome, link), pairs in groups.items():
        if len({id(c) for c, _ in pairs}) < 3:
            continue
        for c, f in pairs:
            # Only strip when the event keeps at least one other source.
            if len(c.fontes) > 1 and f in c.fontes:
                c.fontes.remove(f)
                stripped += 1
    if stripped:
        print(f"[main] {stripped} fonte(s) sobre-mescladas removidas")


def _drop_linkless_events(corridas: list[Corrida]) -> list[Corrida]:
    """Drop events that carry no usable link.

    An event with no fontes — or whose fontes all lack a link_evento and
    links_inscricao — has no source to point the user at and cannot be fixed by
    _ensure_inscricao_links (there is nothing to attach a link to).  Such records
    are corruption artifacts (e.g. a FonteInfo that leaked into distancias,
    leaving the event source-less).  Mirrors the every-event-has-a-link guarantee
    enforced by tests/test_site.py::test_all_events_have_required_fields.
    """
    ok, dropped = [], []
    for c in corridas:
        has_link = any(
            (f.link_evento or (f.links_inscricao[0] if f.links_inscricao else ""))
            for f in c.fontes
        )
        (ok if has_link else dropped).append(c)
    if dropped:
        print(f"[main] AVISO: {len(dropped)} evento(s) sem link removido(s):")
        for c in dropped[:20]:
            print(f"  • {c.id} ({c.titulo!r})")
    return ok


def _drop_kids_events(corridas: list[Corrida]) -> list[Corrida]:
    """Drop kids-only races from any source.

    `_is_valid` already rejects them on the reconcile path, but fresh events from
    a source that doesn't filter kids itself only reach here, so this final pass
    guarantees no kids-only event is saved. Adult races that merely offer a kids
    sub-event are kept (see utils.is_kids_event)."""
    ok, dropped = [], []
    for c in corridas:
        (dropped if is_kids_event(c.titulo, c.distancias) else ok).append(c)
    if dropped:
        print(f"[main] {len(dropped)} evento(s) kids removido(s):")
        for c in dropped[:20]:
            print(f"  • {c.id} ({c.titulo!r})")
    return ok


def _drop_events_without_horario(corridas: list[Corrida]) -> list[Corrida]:
    """Drop events within the next 3 months that have no published start time.

    Horário is a hard requirement for imminent events: users rely on it to plan
    participation. But events 3+ months out often have no start time announced
    yet — dropping those would hide them needlessly. So keep far-future events
    without a horário (they're re-checked each run and the time is filled in as
    they approach the 3-month window) and only drop near-term ones still missing it.
    """
    ok, dropped = [], []
    for c in corridas:
        (ok if (c.horario or not horario_required(c.data_evento)) else dropped).append(c)
    if dropped:
        print(f"[main] {len(dropped)} evento(s) (próximos 3 meses) sem horário publicado removido(s):")
        for c in dropped[:20]:
            print(f"  • {c.id} ({c.titulo!r}) [{c.data_evento}]")
    return ok


def _drop_nonunique_link_events(corridas: list[Corrida]) -> list[Corrida]:
    """Drop events that share a single (source, link) across 3+ distinct records.

    Runs after _strip_overmerged_fontes, so any group still sharing a link here
    consists of sole-source events — i.e. a scraper emitted the same non-unique
    URL for genuinely different events (the halfmarathons-style bug the test
    test_no_inscription_link_shared_across_many_events guards against). Stripping
    is impossible without orphaning them, so keep the single most complete record
    and drop the rest: three events all pointing at one wrong page is worse than
    one. The next scrape restores them once the source link is unique again.
    """
    from collections import defaultdict

    groups: dict[tuple[str, str], list[Corrida]] = defaultdict(list)
    for c in corridas:
        for f in c.fontes:
            for l in (f.links_inscricao or []):
                if l:
                    groups[(f.nome, l.rstrip("/").lower())].append(c)

    drop_ids: set[int] = set()
    for (nome, link), recs in groups.items():
        distinct = {id(c): c for c in recs}
        if len(distinct) < 3:
            continue
        # Keep the most complete; drop the others.
        keep = max(distinct.values(), key=lambda c: (len(c.fontes), len(c.distancias), bool(c.imagem_url)))
        for c in distinct.values():
            if c is not keep:
                drop_ids.add(id(c))
        print(f"[main] AVISO: link não-único '{nome}' em {len(distinct)} eventos; "
              f"mantido {keep.id}, removidos {len(distinct) - 1}")

    return [c for c in corridas if id(c) not in drop_ids]


def _dedupe_by_id(corridas: list[Corrida]) -> list[Corrida]:
    """Collapse records that share an id, keeping the most complete copy.

    Final safety net before save: reconcile/merge — or a line-based git merge of
    two pipeline runs' JSON — can leave more than one record with the same id.
    The id is the reconcile key and must be unique, so keep a single copy per id,
    preferring the one with more fontes, then more distancias, then an image.
    Mirrors the uniqueness load_existing() enforces on read.
    """
    def _completeness(c: Corrida) -> tuple:
        return (len(c.fontes), len(c.distancias), bool(c.imagem_url), bool(c.horario))

    best: dict[str, Corrida] = {}
    order: list[str] = []
    for c in corridas:
        prev = best.get(c.id)
        if prev is None:
            best[c.id] = c
            order.append(c.id)
        elif _completeness(c) > _completeness(prev):
            best[c.id] = c
    removed = len(corridas) - len(best)
    if removed:
        print(f"[main] {removed} registro(s) duplicado(s) por id colapsado(s)")
    return [best[i] for i in order]


def main() -> None:
    selective = _SELECTIVE_SOURCES
    if selective:
        print(f"[main] modo seletivo: fontes={selective!r}")

    print("[main] iniciando scraping...")
    estado_anterior = load_existing()
    print(f"[main] {len(estado_anterior)} corridas no estado anterior")

    raw = run_all_scrapers(selective)
    print(f"[main] {len(raw)} registros coletados (antes do merge)")

    if selective:
        raw = [c for c in raw if _is_valid(c)]
        merged = merge_rodada(raw)
        final = _selective_patch(merged, estado_anterior)
        final = merge_rodada(final)  # deduplicate after patch (prevents duplicates when new sources overlap existing)
        print(f"[main] {len(final)} corridas após patch seletivo + dedup")
    else:
        raw = [c for c in raw if _is_valid(c)]
        print(f"[main] {len(raw)} registros após validação")

        merged = merge_rodada(raw)
        print(f"[main] {len(merged)} corridas após merge")

        final = reconcile(estado_anterior, merged)
        _today = today_iso()
        final = [c for c in final if _is_valid(c) or (c.data_evento and c.data_evento < _today)]
        print(f"[main] {len(final)} corridas após reconciliação")

        # Second dedup pass: catches duplicates that survived reconcile (e.g. past events
        # copied as-is from estado_anterior without cross-checking the full result)
        final = merge_rodada(final)
        print(f"[main] {len(final)} corridas após dedup final")

    _normalize_all_locations(final)
    _resolve_missing_locations(final)
    final = _drop_invalid_location_events(final)
    _enrich_selos(final)  # World Athletics labels + Abbott Majors (dynamic)
    _strip_overmerged_fontes(final)
    final = _drop_nonunique_link_events(final)
    _ensure_inscricao_links(final)
    final = _drop_linkless_events(final)
    final = _drop_kids_events(final)
    final = _drop_events_without_horario(final)
    final = _dedupe_by_id(final)
    save(final)


if __name__ == "__main__":
    try:
        main()
    except BaseException:
        import traceback
        traceback.print_exc()
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(1)
    # Hard-exit instead of returning normally. The scraping/recheck phases
    # run in thread pools; if a source stalled in a call without a hard timeout
    # (e.g. a Playwright navigation), its non-daemon worker thread stays alive and
    # the interpreter's at-exit join would block on it until the CI job times out
    # — even though all data is already scraped and saved. os._exit skips that
    # join. (Phase budgets bound the work; this bounds the shutdown.)
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)
