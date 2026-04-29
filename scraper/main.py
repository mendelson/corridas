"""Orchestrator: run all scrapers, merge, persist data/corridas.json"""
from __future__ import annotations
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from datetime import date
from pathlib import Path

from .merger import are_duplicates, merge_rodada
from .models import Corrida, Distancia, FonteInfo, Inscricao, PeriodoInscricao
from .utils import now_iso, today_iso

# ---------------------------------------------------------------------------
# Source registry
# ---------------------------------------------------------------------------

from .sources import (
    brasil_que_corre,
    corridas_br,
    correr_brasilia,
    central_da_corrida,
    minhas_inscricoes,
    corridas_brasil,
    bora_correr,
    brasil_corrida,
    runner_brasil,
    liverun,
    tf_sports,
    sesc_df,
    ticket_sports,
    portal_das_corridas,
)
from .sources.majors import (
    tokyo,
    boston,
    london,
    berlin,
    chicago,
    nyc,
    sydney,
)

SOURCES = [
    correr_brasilia,
    corridas_br,
    brasil_que_corre,
    central_da_corrida,
    minhas_inscricoes,
    corridas_brasil,
    bora_correr,
    brasil_corrida,
    runner_brasil,
    liverun,
    tf_sports,
    sesc_df,
    ticket_sports,
    portal_das_corridas,
    tokyo,
    boston,
    london,
    berlin,
    chicago,
    nyc,
    sydney,
]

DATA_PATH = Path(__file__).parent.parent / "data" / "corridas.json"


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
        inscricoes = [Inscricao(**i) for i in f.get("inscricoes", [])]
        fontes.append(FonteInfo(
            nome=f["nome"],
            link_evento=f["link_evento"],
            links_inscricao=f.get("links_inscricao", []),
            inscricoes=inscricoes,
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
        estado=d.get("estado", "??"),
        distancias=distancias,
        imagem_url=d.get("imagem_url"),
        inscricoes_abertas=d.get("inscricoes_abertas"),
        periodo_inscricao=periodo,
        fontes=fontes,
        miss_count=d.get("miss_count", 0),
        first_seen_at=d.get("first_seen_at", now_iso()),
        updated_at=d.get("updated_at", now_iso()),
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


def save(corridas: list[Corrida]) -> None:
    corridas_sorted = sorted(
        corridas,
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
    for field in ["data_evento", "horario", "localizacao", "distancias",
                  "imagem_url", "inscricoes_abertas", "periodo_inscricao", "fontes"]:
        if getattr(existing, field) != getattr(incoming, field):
            return True
    return False


def _update_from(existing: Corrida, incoming: Corrida) -> Corrida:
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
    for cid, existing in estado_anterior.items():
        if cid in matched_ids:
            continue
        # Past events are kept as-is
        if existing.data_evento and existing.data_evento < today:
            result.append(existing)
            continue
        # Future events: increment miss_count
        existing.miss_count += 1
        if existing.miss_count < 3:
            result.append(existing)
        else:
            print(f"[main] removendo '{existing.titulo}' (miss_count={existing.miss_count})")

    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_all_scrapers() -> list[Corrida]:
    all_corridas: list[Corrida] = []

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(src.scrape): src.__name__ for src in SOURCES}
        for future in as_completed(futures):
            source_name = futures[future]
            try:
                corridas = future.result()
                all_corridas.extend(corridas)
            except Exception as e:
                print(f"[main] fonte {source_name} falhou: {e}")

    return all_corridas


def main() -> None:
    print("[main] iniciando scraping...")
    estado_anterior = load_existing()
    print(f"[main] {len(estado_anterior)} corridas no estado anterior")

    raw = run_all_scrapers()
    print(f"[main] {len(raw)} registros coletados (antes do merge)")

    merged = merge_rodada(raw)
    print(f"[main] {len(merged)} corridas após merge")

    final = reconcile(estado_anterior, merged)
    print(f"[main] {len(final)} corridas após reconciliação")

    save(final)


if __name__ == "__main__":
    main()
