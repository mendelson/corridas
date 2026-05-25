"""Orchestrator: run all scrapers, merge, persist data/corridas.json"""
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

from .merger import are_duplicates, merge_rodada
from .models import Corrida, Distancia, FonteInfo, PeriodoInscricao
from .utils import now_iso, today_iso, normalize_cidade, validate_image_url
from .http_client import get as http_get
from . import geo as _geo

# ---------------------------------------------------------------------------
# Source registry
# ---------------------------------------------------------------------------

from .sources import (
    central_da_corrida,
    ticket_sports,
    maratona_rio,
    maratona_porto_alegre,
    sp_city_marathon,
    sao_silvestre,
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
    # letsdothis,   # inviável: WAF bloqueia todos os proxies — ver README
    world_athletics,
)
from .sources.majors import (
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
    paris,
    edinburgh,
    great_north_run,
    cardiff_half,
    manchester,
    manchester_half,
    brighton,
)

SOURCES = [
    # API-based / well-structured (nationwide)
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
    correr_brasilia,
    bora_correr,
    brasil_que_corre,
    sesc_df,
    # Multi-city circuit events (via dedicated API)
    circuito_das_estacoes,
    # Brazilian running event platforms
    largada_esportiva,
    # Single major events (BR)
    maratona_rio,
    maratona_porto_alegre,
    sp_city_marathon,
    sao_silvestre,
    # World Majors
    tokyo,
    boston,
    london,
    berlin,
    chicago,
    nyc,
    sydney,
    venice,
    # European Marathons
    prague,
    copenhagen,
    stockholm,
    amsterdam,
    dublin,
    athens,
    valencia,
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
    # Mexican running calendars
    asdeporte,
    carreras_mexico,
    # IAAF Label Road Races
    world_athletics,
]

DATA_PATH       = Path(__file__).parent.parent / "data" / "corridas.json"
HIST_DIR        = Path(__file__).parent.parent / "data" / "historico"
STATUS_PATH     = Path(__file__).parent.parent / "data" / "source-status.json"


# ---------------------------------------------------------------------------
# JSON serialization helpers
# ---------------------------------------------------------------------------

def _corrida_to_dict(c: Corrida) -> dict:
    d = asdict(c)
    return d


def _dict_to_corrida(d: dict) -> Corrida:
    distancias = [Distancia(**dist) for dist in d.get("distancias", [])]
    fontes = []
    for f in d.get("fontes", []):
        fontes.append(FonteInfo(
            nome=f["nome"],
            link_evento=f["link_evento"],
            links_inscricao=f.get("links_inscricao", []),
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
        return {c["id"]: _dict_to_corrida(c) for c in raw.get("corridas", [])}
    except Exception as e:
        print(f"[main] erro ao carregar JSON existente: {e}")
        return {}


def _find_all_photos(corridas: list[Corrida]) -> None:
    """Search photo platforms for events that occurred in the last 30 days.

    Events older than 30 days keep whatever fotos were stored previously but
    are never re-queried. Events in the active window are re-queried every
    scraping run so newly published photos are picked up promptly.
    """
    from datetime import date as _d, timedelta as _td
    from .fotos import find_event_photos

    today_str = _d.today().isoformat()
    cutoff_str = (_d.today() - _td(days=30)).isoformat()

    to_check = [
        c for c in corridas
        if c.data_evento and cutoff_str <= c.data_evento <= today_str
    ]
    if not to_check:
        return

    print(f"[main] buscando fotos em plataformas para {len(to_check)} evento(s)...")

    def _check(c: Corrida) -> tuple[Corrida, list[dict]]:
        return c, find_event_photos({"titulo": c.titulo, "data_evento": c.data_evento})

    found = 0
    with ThreadPoolExecutor(max_workers=5) as ex:
        futs = {ex.submit(_check, c): c for c in to_check}
        for fut in as_completed(futs):
            try:
                c, fotos = fut.result()
                if fotos:
                    c.fotos = fotos
                    found += 1
            except Exception:
                pass

    print(f"[main] fotos encontradas para {found}/{len(to_check)} evento(s)")


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
    """Fill in empty estado (and incorrect pais) using geo.resolve() + cache."""
    fixed = 0
    for c in corridas:
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


_GENERIC_IMAGE_PATTERNS = [
    "logo", "favicon", "placeholder", "default", "banner",
    "LargeRectangle", "No_Empty_Space", "no-image", "sem-imagem",
]


def _is_generic_image(url: str) -> bool:
    url_lower = url.lower()
    if url_lower.endswith(".gif"):
        return True
    return any(p.lower() in url_lower for p in _GENERIC_IMAGE_PATTERNS)


def _og_image_from_url(url: str) -> str | None:
    from bs4 import BeautifulSoup
    try:
        resp = http_get(url, timeout=15)
        if resp.status_code != 200:
            return None
        soup = BeautifulSoup(resp.text, "lxml")
        tag = soup.find("meta", property="og:image")
        if tag:
            content = tag.get("content", "")
            if content and not _is_generic_image(content):
                return validate_image_url(content, source_domain=url)
    except Exception:
        pass
    return None


def _check_and_refresh_links(existing: Corrida) -> bool:
    """Check if any inscription link is still live (HTTP 200).
    If yes, opportunistically refresh og:image from the page.
    Returns True if at least one link is reachable."""
    from bs4 import BeautifulSoup
    links = [l for fonte in existing.fontes for l in fonte.links_inscricao]
    if not links:
        return False
    for link in links:
        try:
            resp = http_get(link, timeout=15)
            if resp.status_code != 200:
                continue
            if not existing.imagem_url:
                soup = BeautifulSoup(resp.text, "lxml")
                tag = soup.find("meta", property="og:image")
                if tag:
                    content = tag.get("content", "")
                    if content and not _is_generic_image(content):
                        existing.imagem_url = validate_image_url(content, source_domain=link)
            return True
        except Exception:
            pass
    return False


def _enrich_images(corridas: list[Corrida]) -> None:
    """For events without an image, try to fetch og:image from their event pages."""
    missing = [c for c in corridas if not c.imagem_url]
    if not missing:
        return
    print(f"[main] buscando imagens para {len(missing)} evento(s) sem foto...")

    def _try_fetch(c: Corrida) -> tuple[Corrida, str | None]:
        # Try link_evento and links_inscricao for each fonte
        candidates: list[str] = []
        for fonte in c.fontes:
            if fonte.link_evento:
                candidates.append(fonte.link_evento)
            candidates.extend(fonte.links_inscricao)
        for url in dict.fromkeys(candidates):  # deduplicate preserving order
            img = _og_image_from_url(url)
            if img:
                return c, img
        return c, None

    found = 0
    with ThreadPoolExecutor(max_workers=10) as ex:
        futures = {ex.submit(_try_fetch, c): c for c in missing}
        for fut in as_completed(futures):
            try:
                c, img = fut.result()
                if img:
                    c.imagem_url = img
                    found += 1
            except Exception:
                pass

    print(f"[main] {found}/{len(missing)} imagens encontradas")


def _find_match(incoming: Corrida, estado_anterior: dict[str, Corrida]) -> Corrida | None:
    # Exact id match
    if incoming.id in estado_anterior:
        return estado_anterior[incoming.id]
    # Similarity match (same criteria as merger)
    for existing in estado_anterior.values():
        if are_duplicates(incoming, existing):
            return existing
    return None


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
        unmatched_future.append(existing)

    # Check inscription links in parallel for unmatched future events
    if unmatched_future:
        print(f"[main] verificando links de {len(unmatched_future)} evento(s) não encontrado(s) no scrape...")
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = {executor.submit(_check_and_refresh_links, ev): ev for ev in unmatched_future}
            for future in as_completed(futures):
                existing = futures[future]
                try:
                    link_valid = future.result()
                except Exception:
                    link_valid = False

                if link_valid:
                    print(f"[main] '{existing.titulo}' — link válido, miss_count zerado")
                    existing.miss_count = 0
                    existing.updated_at = now_iso()
                    result.append(existing)
                else:
                    existing.miss_count += 1
                    if existing.miss_count < 10:
                        result.append(existing)
                    else:
                        print(f"[main] removendo '{existing.titulo}' (miss_count={existing.miss_count})")

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
    scraper.sources.majors.london   → majors/london
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


def run_all_scrapers() -> list[Corrida]:
    all_corridas: list[Corrida] = []
    ordered, failed = _prioritize_failed(SOURCES)
    if failed:
        print(f"[main] priorizando {len(failed)} fonte(s) com falha anterior: "
              f"{', '.join(_source_status_key(s) for s in failed)}")

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(src.scrape): src.__name__ for src in ordered}
        for future in as_completed(futures):
            source_name = futures[future]
            try:
                corridas = future.result()
                all_corridas.extend(corridas)
            except Exception as e:
                print(f"[main] fonte {source_name} falhou: {e}")

    return all_corridas


def _sanitize_images(corridas: list[Corrida]) -> None:
    """Validate imagem_url for all events.

    Non-BR events: image must come from the same registered domain as the event
    source OR a known trusted CDN.
    BR events: only reject images with suspicious host keywords.
    """
    cleared = 0
    for c in corridas:
        if not c.imagem_url:
            continue
        if c.pais != 'BR':
            source_domains = [f.link_evento for f in c.fontes if f.link_evento]
            valid = any(validate_image_url(c.imagem_url, source_domain=d) for d in source_domains) \
                    if source_domains else bool(validate_image_url(c.imagem_url))
        else:
            # BR events: only check for suspicious keywords, CDNs/image hosts are trusted
            valid = bool(validate_image_url(c.imagem_url))
        if not valid:
            print(f"[main] removendo imagem inválida de '{c.titulo}': {c.imagem_url[:60]}")
            c.imagem_url = None
            cleared += 1
    if cleared:
        print(f"[main] {cleared} imagem(ns) inválida(s) removida(s)")


def main() -> None:
    print("[main] iniciando scraping...")
    estado_anterior = load_existing()
    print(f"[main] {len(estado_anterior)} corridas no estado anterior")

    raw = run_all_scrapers()
    print(f"[main] {len(raw)} registros coletados (antes do merge)")

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
    _ensure_inscricao_links(final)
    # _find_all_photos(final)
    _enrich_images(final)
    _sanitize_images(final)
    save(final)


if __name__ == "__main__":
    main()
