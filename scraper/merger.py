from __future__ import annotations
import difflib
from datetime import date, timedelta

from .models import Corrida, Distancia, FonteInfo
from .utils import normalize_titulo_merge


# ---------------------------------------------------------------------------
# Completeness score
# ---------------------------------------------------------------------------

def score(c: Corrida) -> int:
    return (
        bool(c.titulo) * 2 +
        bool(c.data_evento) * 2 +
        bool(c.horario) +
        bool(c.localizacao) +
        bool(c.imagem_url) * 2 +
        len(c.distancias) +
        bool(c.inscricoes_abertas is not None) +
        bool(c.periodo_inscricao) +
        bool(c.periodo_inscricao and c.periodo_inscricao.encerramento) +
        len(c.fontes[0].links_inscricao) * 2
    )


# ---------------------------------------------------------------------------
# Similarity helpers
# ---------------------------------------------------------------------------

def _titulo_similarity(a: str, b: str) -> float:
    na = normalize_titulo_merge(a)
    nb = normalize_titulo_merge(b)
    if not na or not nb:
        return 0.0
    return difflib.SequenceMatcher(None, na, nb).ratio()


def _date_ok(a: Corrida, b: Corrida) -> bool:
    """True when dates are within tolerance or at least one is absent."""
    if not a.data_evento or not b.data_evento:
        return True
    try:
        da = date.fromisoformat(a.data_evento)
        db = date.fromisoformat(b.data_evento)
    except ValueError:
        return True
    return abs((da - db).days) <= 14


def _date_ok_relaxed(a: Corrida, b: Corrida) -> bool:
    """Relaxed tolerance (≤ 30 days) for very high title similarity."""
    if not a.data_evento or not b.data_evento:
        return True
    try:
        da = date.fromisoformat(a.data_evento)
        db = date.fromisoformat(b.data_evento)
    except ValueError:
        return True
    return abs((da - db).days) <= 30


# Generic/login links that don't identify a specific event
_GENERIC_LINKS: set[str] = {
    "https://www.ticketagora.com.br/entrar/participante",
}


def _shared_inscription_link(a: Corrida, b: Corrida) -> bool:
    """True if both events share at least one event-specific inscription link."""
    def specific_links(c: Corrida) -> set[str]:
        return {
            l.rstrip("/").lower()
            for f in c.fontes
            for l in f.links_inscricao
            if l.rstrip("/").lower() not in _GENERIC_LINKS
        }
    la, lb = specific_links(a), specific_links(b)
    return bool(la and lb and la & lb)


def _title_words_contained(a: Corrida, b: Corrida) -> bool:
    """True when all words of the shorter title appear in the longer one (≥3 words)."""
    wa = normalize_titulo_merge(a.titulo).split()
    wb = normalize_titulo_merge(b.titulo).split()
    shorter, longer = (wa, wb) if len(wa) <= len(wb) else (wb, wa)
    return len(shorter) >= 3 and all(w in longer for w in shorter)


def are_duplicates(a: Corrida, b: Corrida) -> bool:
    # Shared event-specific inscription link is conclusive — state mismatch is fine
    if _shared_inscription_link(a, b):
        return True
    if a.estado != b.estado:
        return False
    sim = _titulo_similarity(a.titulo, b.titulo)
    if sim >= 0.95 and _date_ok_relaxed(a, b):
        return True
    if sim >= 0.85 and _date_ok(a, b):
        return True
    if a.data_evento and b.data_evento and a.data_evento == b.data_evento:
        # Same exact date: strong similarity or one title contained in the other
        if sim >= 0.75:
            return True
        if _title_words_contained(a, b):
            return True
    return False


# ---------------------------------------------------------------------------
# Merge two corridas (champion absorbs extra)
# ---------------------------------------------------------------------------

def _km_key(km) -> object:
    """Normalize km for deduplication: 21.0 and 21.097 are the same distance."""
    if isinstance(km, str):
        return km
    return round(km)


def _merge_distancias(base: list[Distancia], extra: list[Distancia]) -> list[Distancia]:
    existing_keys = {_km_key(d.km) for d in base}
    result = list(base)
    for d in extra:
        key = _km_key(d.km)
        if key not in existing_keys:
            result.append(d)
            existing_keys.add(key)
    return result


def _dedup_links(links: list[str]) -> list[str]:
    seen: set[str] = set()
    out = []
    for link in links:
        if link not in seen:
            seen.add(link)
            out.append(link)
    return out


def _absorb_fonte(champion: Corrida, fonte: FonteInfo) -> None:
    for existing in champion.fontes:
        if existing.nome == fonte.nome:
            existing.links_inscricao = _dedup_links(existing.links_inscricao + fonte.links_inscricao)
            return
    fonte.links_inscricao = _dedup_links(fonte.links_inscricao)
    champion.fontes.append(fonte)


def _merge_pair(champion: Corrida, extra: Corrida) -> Corrida:
    if not champion.imagem_url and extra.imagem_url:
        champion.imagem_url = extra.imagem_url
    champion.distancias = _merge_distancias(champion.distancias, extra.distancias)
    if champion.inscricoes_abertas is None and extra.inscricoes_abertas is not None:
        champion.inscricoes_abertas = extra.inscricoes_abertas
    if champion.periodo_inscricao is None and extra.periodo_inscricao is not None:
        champion.periodo_inscricao = extra.periodo_inscricao
    for fonte in extra.fontes:
        _absorb_fonte(champion, fonte)
    return champion


# ---------------------------------------------------------------------------
# Public: merge a single scraping round
# ---------------------------------------------------------------------------

def merge_rodada(registros: list[Corrida]) -> list[Corrida]:
    n = len(registros)
    group_id = list(range(n))  # union-find (flat)

    def find(i: int) -> int:
        while group_id[i] != i:
            group_id[i] = group_id[group_id[i]]
            i = group_id[i]
        return i

    def union(i: int, j: int) -> None:
        ri, rj = find(i), find(j)
        if ri != rj:
            group_id[rj] = ri

    for i in range(n):
        for j in range(i + 1, n):
            if are_duplicates(registros[i], registros[j]):
                union(i, j)

    # Group by root
    groups: dict[int, list[int]] = {}
    for i in range(n):
        root = find(i)
        groups.setdefault(root, []).append(i)

    result: list[Corrida] = []
    for indices in groups.values():
        if len(indices) == 1:
            result.append(registros[indices[0]])
            continue

        # Elect champion by completeness score
        best = max(indices, key=lambda i: score(registros[i]))
        champion = registros[best]
        for i in indices:
            if i != best:
                champion = _merge_pair(champion, registros[i])
        result.append(champion)

    return result
