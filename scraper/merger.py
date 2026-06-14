from __future__ import annotations
import difflib
import re
import unicodedata
from collections import defaultdict
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
        (len(c.fontes[0].links_inscricao) * 2 if c.fontes else 0)
    )


# ---------------------------------------------------------------------------
# Similarity helpers
# ---------------------------------------------------------------------------

def _titulo_similarity(a: str, b: str) -> float:
    na = normalize_titulo_merge(a)
    nb = normalize_titulo_merge(b)
    if not na or not nb:
        return 0.0
    # Single-word normalizations are too generic to drive merging.
    # "Corrida da Copa" and "Copa Run" both reduce to "copa", giving
    # sim=1.0 and causing cross-city false merges. Require ≥2 meaningful
    # tokens from both titles before using title similarity as a signal.
    if len(na.split()) < 2 or len(nb.split()) < 2:
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
    # brasil_que_corre catalog page — fixed to use #widget-id anchors but kept
    # here in case stale data still carries the bare URL.
    "https://brasilquecorre.com/distritofederal",
}

# Auto-detected generic links: populated per-run with URLs that appear as
# inscription links across many distinct events from the same source.
_RUN_GENERIC_LINKS: set[str] = set()


_TS_ID_RE = re.compile(r"ticketsports\.com\.br/e/[^/]*?-(\d+)/?$", re.IGNORECASE)


def _norm_link(url: str) -> str:
    # Ticket Sports URLs come in two formats for the same event:
    #   slug:  .../e/minions-run-brasilia-2026-86573   (from bora_correr, html calendars)
    #   name:  .../e/MINIONS+RUN+-+BRASÍLIA+2026-86573 (from ticket_sports API)
    # Normalize both to just the numeric event ID so the merger deduplicates them.
    m = _TS_ID_RE.search(url)
    if m:
        return f"ticketsports.com.br/e/{m.group(1)}"
    return url.rstrip("/").lower()


def _detect_overused_links(registros: list[Corrida], threshold: int = 3) -> set[str]:
    """A scraper that emits the same inscription URL for >=N distinct events is
    almost certainly producing a catalog/section link, not an event link. Treat
    such URLs as generic so the merger's shared-link rule doesn't collapse all
    those events into one record (the brasil_que_corre regression).
    """
    counts: dict[tuple[str, str], int] = defaultdict(int)
    for r in registros:
        for f in r.fontes:
            for l in f.links_inscricao:
                counts[(f.nome, _norm_link(l))] += 1
    return {link for (_, link), n in counts.items() if n >= threshold}


def _shared_inscription_link(a: Corrida, b: Corrida) -> bool:
    """True if both events share at least one event-specific inscription link."""
    generic = _GENERIC_LINKS | _RUN_GENERIC_LINKS

    def specific_links(c: Corrida) -> set[str]:
        return {
            _norm_link(l)
            for f in c.fontes
            for l in f.links_inscricao
            if _norm_link(l) not in generic
        }
    la, lb = specific_links(a), specific_links(b)
    return bool(la and lb and la & lb)


def _title_words_contained(a: Corrida, b: Corrida) -> bool:
    """True when all words of the shorter title appear in the longer one (≥3 words)."""
    wa = normalize_titulo_merge(a.titulo).split()
    wb = normalize_titulo_merge(b.titulo).split()
    shorter, longer = (wa, wb) if len(wa) <= len(wb) else (wb, wa)
    return len(shorter) >= 2 and all(w in longer for w in shorter)


def _km_key(km) -> object:
    """Normalize km for deduplication: 21.0 and 21.097 are the same distance."""
    if isinstance(km, str):
        return km
    return round(km)


def _norm_city(s: str) -> str:
    s = unicodedata.normalize('NFKD', s.strip().lower())
    return ''.join(c for c in s if not unicodedata.combining(c))


def _city_mismatch(a: Corrida, b: Corrida) -> bool:
    """True when both records declare an explicit city and those cities differ.

    Distinct cities within the same state are strong evidence of distinct events
    (e.g. a 10 K race in São Paulo vs one in Campinas on the same date).
    We normalize away accents before comparing so "São Paulo" == "Sao Paulo".
    """
    ca = _norm_city(a.cidade or '')
    cb = _norm_city(b.cidade or '')
    return bool(ca and cb and ca != cb)


def _distances_disjoint(a: Corrida, b: Corrida) -> bool:
    """True when both events have distances and none overlap.

    Two events from the same brand but different editions (e.g. "Event (5km)"
    vs "Event (21km)") appear similar in title but are truly distinct. Completely
    disjoint distance sets is a strong signal that they must not be merged.
    """
    if not a.distancias or not b.distancias:
        return False
    a_km = {_km_key(d.km) for d in a.distancias}
    b_km = {_km_key(d.km) for d in b.distancias}
    return not bool(a_km & b_km)


def are_duplicates(a: Corrida, b: Corrida) -> bool:
    # Shared event-specific inscription link is conclusive — state mismatch is fine
    if _shared_inscription_link(a, b):
        return True

    # Completely disjoint distances → different events even if names look similar
    # (e.g. "Event (5km e 10km)" vs "Event (21km e 42km)")
    if _distances_disjoint(a, b):
        return False

    sim = _titulo_similarity(a.titulo, b.titulo)

    if a.estado != b.estado:
        # Cross-state: allow merge only for Brazilian events where the state
        # mismatch is a known data-quality pattern (e.g. GO vs DF for events
        # in the Greater Brasília metro area that different sources classify
        # differently). Requires very high title similarity + exact same date.
        # US and other multi-state event series (Firecracker 5k, Freedom Run…)
        # are intentionally excluded via the pais check.
        if (
            a.pais == "BR" and b.pais == "BR"
            and sim >= 0.95
            and a.data_evento and b.data_evento
            and a.data_evento == b.data_evento
        ):
            return True
        return False

    # Same state: if both records name a distinct city, treat them as different events.
    # Two races with identical titles in São Paulo and Campinas are not the same race.
    # The only conclusive override is a shared inscription link (handled above).
    city_diff = _city_mismatch(a, b)

    if sim >= 0.95 and _date_ok_relaxed(a, b):
        return not city_diff
    if sim >= 0.85 and _date_ok(a, b):
        return not city_diff
    if a.data_evento and b.data_evento and a.data_evento == b.data_evento:
        if sim >= 0.75:
            return not city_diff
        if _title_words_contained(a, b):
            return not city_diff

    # Identical normalized brand title on the EXACT same date (same state + city).
    # Catches events whose title collapses to a single token after stop-word/year
    # stripping — e.g. "Corrida POUPEX 2026" → "poupex" — which _titulo_similarity
    # deliberately reports as 0.0 (the >=2-token guard against generic single-word
    # false merges). Requiring identical tokens + same city + the exact same date
    # keeps that guard's intent: "Corrida da Copa" (Santo Ângelo) and "Copa Run"
    # (Brasília) both reduce to "copa" but never merge — different cities. Disjoint
    # distances already returned False above, so survivors share at least one.
    na = normalize_titulo_merge(a.titulo)
    nb = normalize_titulo_merge(b.titulo)
    if (
        na and na == nb
        and not city_diff
        and a.data_evento and b.data_evento
        and a.data_evento == b.data_evento
    ):
        return True

    return False


# ---------------------------------------------------------------------------
# Merge two corridas (champion absorbs extra)
# ---------------------------------------------------------------------------


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
    global _RUN_GENERIC_LINKS
    _RUN_GENERIC_LINKS = _detect_overused_links(registros)
    if _RUN_GENERIC_LINKS:
        print(
            f"[merger] {len(_RUN_GENERIC_LINKS)} URL(s) detected as overused inscription "
            f"links (treating as generic): {sorted(_RUN_GENERIC_LINKS)[:5]}"
        )

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

    # Candidate generation, then confirm with are_duplicates. A naive all-pairs
    # loop is O(n^2) and, on a cold run (~15k+ raw events), spends tens of minutes
    # here in pure CPU with no output — the unbounded phase behind the pipeline
    # timeouts. are_duplicates can only return True via one of three disjoint
    # conditions, so we only compare pairs that could possibly match:
    #   (1) they share a specific (non-generic) inscription link — conclusive,
    #   (2) same state AND event dates within 31 days (covers every same-state
    #       title/date path; the relaxed window tops out at 30 days), or
    #   (3) Brazilian events on the EXACT same date across different states.
    # Every other pair is guaranteed non-duplicate, so skipping it is exact —
    # the dedup result is identical to the all-pairs version, just far faster.
    generic = _GENERIC_LINKS | _RUN_GENERIC_LINKS

    # (1) shared specific inscription link
    link_idx: dict[str, list[int]] = defaultdict(list)
    for i, r in enumerate(registros):
        for nl in {_norm_link(l) for f in r.fontes for l in f.links_inscricao}:
            if nl and nl not in generic:
                link_idx[nl].append(i)
    for idxs in link_idx.values():
        first = idxs[0]
        for k in idxs[1:]:
            if find(first) != find(k) and are_duplicates(registros[first], registros[k]):
                union(first, k)

    def _pdate(s: str):
        try:
            return date.fromisoformat(s[:10])
        except Exception:
            return None
    pdates = [_pdate(r.data_evento) if r.data_evento else None for r in registros]

    # (2) same state, dates within 31 days (sorted sliding window)
    by_state: dict[str, list[int]] = defaultdict(list)
    for i in range(n):
        if pdates[i] is not None:
            by_state[registros[i].estado].append(i)
    for idxs in by_state.values():
        idxs.sort(key=lambda i: pdates[i])
        for a in range(len(idxs)):
            ia = idxs[a]
            for b in range(a + 1, len(idxs)):
                ib = idxs[b]
                if (pdates[ib] - pdates[ia]).days > 31:
                    break
                if find(ia) != find(ib) and are_duplicates(registros[ia], registros[ib]):
                    union(ia, ib)

    # (3) Brazilian events on the exact same date, across states
    by_date_br: dict[str, list[int]] = defaultdict(list)
    for i in range(n):
        if pdates[i] is not None and registros[i].pais == "BR":
            by_date_br[registros[i].data_evento[:10]].append(i)
    for idxs in by_date_br.values():
        for a in range(len(idxs)):
            ia = idxs[a]
            for b in range(a + 1, len(idxs)):
                ib = idxs[b]
                if registros[ia].estado != registros[ib].estado \
                        and find(ia) != find(ib) \
                        and are_duplicates(registros[ia], registros[ib]):
                    union(ia, ib)

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
