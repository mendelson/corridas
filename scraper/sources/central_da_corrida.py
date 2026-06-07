"""Scraper for centraldacorrida.com.br — Supabase edge-function API"""
from __future__ import annotations
import re
from datetime import datetime, timezone, timedelta

from ..http_client import get
from ..models import Corrida, Distancia, FonteInfo
from ..utils import (
    normalize_titulo, slugify, now_iso, today_iso,
    validate_image_url,
)
from .. import geo as _geo

BASE = "https://centraldacorrida.com.br"
API_URL = "https://tudmqbzxfbrjljpdpili.supabase.co/functions/v1/eventos-publicos"
SOURCE_NAME = "Central da Corrida"

BRT = timezone(timedelta(hours=-3))

_OPEN_KW = ("abertas", "aberto", "últimas unidades", "ultimas unidades",
            "pré venda", "pre venda", "pré-venda", "pre-venda")
_CLOSED_KW = ("encerrad", "esgotad")


def scrape() -> list[Corrida]:
    today = today_iso()
    try:
        resp = get(f"{API_URL}?Data_evento=gte.{today}")
        resp.raise_for_status()
        events: list[dict] = resp.json()
    except Exception as e:
        print(f"[{SOURCE_NAME}] erro ao buscar API: {e}")
        return []

    corridas: list[Corrida] = []
    for event in events:
        try:
            corrida = _parse_event(event, today)
            if corrida:
                corridas.append(corrida)
        except Exception as e:
            print(f"[{SOURCE_NAME}] erro ao parsear evento '{event.get('Nome_evento')}': {e}")

    print(f"[{SOURCE_NAME}] {len(corridas)} corridas encontradas")
    return corridas


_KIDS_RE = re.compile(
    r'\bkids?\b|\bpezinho\s+veloz\b|\binfantil\b|\bgraesp\s+kids\b',
    re.IGNORECASE,
)
_URL_RE = re.compile(r'https?://[^\s\[\]"\'<>]+')


def _parse_event(event: dict, today: str) -> Corrida | None:
    if event.get("Publicado") != "sim":
        return None

    # Drop explicitly cancelled events
    ativo = (event.get("Ativo") or "").strip().lower()
    if ativo in ("não", "nao", "no"):
        return None

    titulo = normalize_titulo(event.get("Nome_evento") or "")
    if not titulo or len(titulo) < 3:
        return None

    # Drop kids events — no adult distances exist for these
    if _KIDS_RE.search(titulo):
        return None

    estado = event.get("Estado") or ""
    cidade = event.get("Cidade") or ""
    _pais_geo, _estado_geo = _geo.resolve(cidade, "", "BR")
    pais = _pais_geo or "BR"
    if not estado:
        estado = _estado_geo or ""
    localizacao = f"{cidade}, {estado}" if cidade else estado

    data_evento, horario = _parse_datetime(event.get("Data_evento") or "")
    if not data_evento or horario is None:
        return None  # Data_evento null or unparseable — start time not published

    imagem_url = _parse_image(event.get("imagem"))

    slug = event.get("slug") or ""
    link_evento = f"{BASE}/evento/{slug}" if slug else BASE

    # Distances come from the event's regulamento/description prose (its explicit
    # distance enumeration) — never from the title.
    raw_text = " ".join(filter(None, [
        event.get("regulamento"),
        event.get("descricao_evento"),
    ]))
    distancias = _extract_distances(raw_text)

    # Fallback: try external URLs embedded in regulamento / mais_informacoes
    if not distancias:
        for field_name in ("regulamento", "mais_informacoes", "link_inscricao"):
            field_val = event.get(field_name) or ""
            for m in _URL_RE.finditer(field_val):
                ext_url = m.group(0).rstrip(".,;)")
                if "centraldacorrida.com.br" in ext_url:
                    continue
                distancias = _fetch_distances_from_url(ext_url)
                if distancias:
                    break
            if distancias:
                break

    if not distancias:
        print(f"[{SOURCE_NAME}] sem distâncias, pulando: {titulo!r}")
        return None

    inscricoes_abertas = _parse_inscricoes_abertas(event)

    now = now_iso()
    fonte = FonteInfo(
        nome=SOURCE_NAME,
        link_evento=link_evento,
        links_inscricao=[link_evento],
        tipo="calendario",
    )

    return Corrida(
        id=f"{slugify(titulo)}_{estado.lower()}_{data_evento or 'sd'}",
        titulo=titulo,
        data_evento=data_evento,
        horario=horario,
        localizacao=localizacao,
        cidade=cidade,
        estado=estado,
        pais=pais,
        distancias=distancias,
        imagem_url=imagem_url,
        inscricoes_abertas=inscricoes_abertas,
        periodo_inscricao=None,
        fontes=[fonte],
        miss_count=0,
        first_seen_at=now,
        updated_at=now,
    )


def _parse_datetime(raw: str) -> tuple[str, str | None]:
    if not raw or raw == "null":
        return "", None
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        dt_brt = dt.astimezone(BRT)
        return dt_brt.strftime("%Y-%m-%d"), dt_brt.strftime("%H:%M")
    except Exception:
        return "", None


def _parse_image(raw: str | None) -> str | None:
    if not raw or raw in ("null", ""):
        return None
    if raw.startswith("//"):
        raw = "https:" + raw
    return validate_image_url(raw)


def _parse_inscricoes_abertas(event: dict) -> bool | None:
    ba = (event.get("botao_aberto") or "").lower().strip()
    # API field has a typo; try both spellings
    be = (event.get("botao_encerrado") or event.get("bota_encerrado") or "").lower().strip()

    # Closed signal always wins — events can close after the open button was set
    if be and be != "null" and any(kw in be for kw in _CLOSED_KW):
        return False

    if ba and ba != "null":
        if any(kw in ba for kw in _OPEN_KW):
            return True

    return None


_PERCURSO_RE = re.compile(
    r"percurso\s+(?:de\s+\d+|até\s+\d+|superior\s+a\s+\d+|com\s+\d+)[^;.]*",
    re.IGNORECASE,
)

_INTERVAL_RE = re.compile(
    r"a cada \d+(?:[.,]\d+)?\s*k(?:m)?\b"
    r"|cada \d+(?:[.,]\d+)?\s*k(?:m)?\b"
    r"|\d+(?:[.,]\d+)?\s*k(?:m)?\s*(?:de hidrat|de água|de abastec)",
    re.IGNORECASE,
)

# Canonical distance windows: snap noisy values to the exact standard distance.
_CANONICAL = [(42.195, 41.5, 43.0), (21.097, 20.5, 21.5)]
_MIN_KM = 3.0  # ≥3 km: exclude walks/kids/hydration noise

# Named distances ("meia maratona"/"maratona") and their English forms. Half is
# matched (and stripped) before the full-marathon check so "meia maratona" never
# also counts as a full marathon.
_HALF_MARATHON_RE = re.compile(r"meia[\s-]?maratona|half[\s-]?marathon", re.IGNORECASE)
_FULL_MARATHON_RE = re.compile(r"\bmaratona\b|\bmarathon\b", re.IGNORECASE)

# A single distance "token": an explicit numeric km value OR a named distance.
# Named distances are first-class — but honoured ONLY when they appear as a token
# inside a distance enumeration (a list element or a labelled value), never loose
# in prose. That distinction keeps colloquial "a maior maratona do DF" from
# injecting a phantom 42.195 km (mirrors correr_brasilia after #196).
_DIST_TOKEN = (
    r"(?:meia[\s-]?maratona|half[\s-]?marathon|maratona|marathon"
    r"|\d+(?:[.,]\d+)?\s*[kK][mM]?)"
)

# A distance list: 2+ tokens joined by connectors — "5km, 10km e meia maratona".
_DIST_LIST_RE = re.compile(
    rf"{_DIST_TOKEN}(?:\s*(?:,|;|/|\||\be\b|\bou\b)\s*{_DIST_TOKEN})+",
    re.IGNORECASE,
)

# A labelled single distance: "Modalidade: Maratona", "Distância: 42km".
_DIST_LABEL = r"dist[âa]ncias?|modalidades?|percursos?|provas?|categorias?|trajetos?"
_DIST_LABELLED_RE = re.compile(
    rf"(?:{_DIST_LABEL})\s*:?\s*({_DIST_TOKEN})",
    re.IGNORECASE,
)

# Shared km suffix ("3, 5 e 10 km") — numbers sharing a single trailing km unit.
# This is the common Brazilian-Portuguese enumeration form where only the last
# value carries "km"; the old per-number regex captured just that last value and
# silently dropped the rest (e.g. "3, 5 e 10 km" → only 10).
_DIST_SHARED_SUFFIX_RE = re.compile(
    r"(\d+(?:[.,]\d+)?)"
    r"(?:\s*(?:,|e|ou)\s*(\d+(?:[.,]\d+)?))+"
    r"\s*[kK][mM]?\b",
    re.IGNORECASE,
)


def _fetch_distances_from_url(url: str) -> list[Distancia]:
    try:
        resp = get(url, source=SOURCE_NAME, timeout=15)
        resp.raise_for_status()
        page_text = re.sub(r"<[^>]+>", " ", resp.text)
        return _extract_distances(page_text)
    except Exception as e:
        print(f"[{SOURCE_NAME}] fetch externo falhou ({url[:60]}): {e}")
        return []


def _token_to_km(tok: str) -> float | None:
    """Convert one distance token (numeric km or a named distance) to kilometres."""
    t = tok.strip().lower()
    if _HALF_MARATHON_RE.search(t):
        return 21.097
    if _FULL_MARATHON_RE.search(t):
        return 42.195
    m = re.match(r"(\d+(?:[.,]\d+)?)", t)
    if m:
        try:
            return float(m.group(1).replace(",", "."))
        except ValueError:
            return None
    return None


def _filter_km_values(raw_values: list[float]) -> list[float]:
    seen: list[float] = []
    for raw in raw_values:
        if raw < _MIN_KM or raw > 200:
            continue
        km = raw
        for canon, lo, hi in _CANONICAL:
            if lo <= raw <= hi:
                km = canon
                break
        if any(abs(km - s) < 0.5 for s in seen):
            continue
        seen.append(km)
    return seen


def _extract_distances(text: str) -> list[Distancia]:
    """Extract race distances from the event's dedicated distance enumeration.

    Distances always come from an explicit enumeration — a distance list, a
    labelled value, or a shared-suffix number group ("3, 5 e 10 km"). Named
    distances ("maratona"/"meia maratona") are honoured only as enumeration
    tokens, never inferred from loose prose, so colloquial usage no longer
    injects a phantom marathon. Numeric values are canonical-snapped so
    42 / 42,2 / 42.195 collapse to one distance (likewise 21).
    """
    # Strip Bubble rich-text markup and noise clauses before matching.
    text = re.sub(r"\[.*?\]", " ", text)
    text = _PERCURSO_RE.sub(" ", text)      # age-restriction clauses
    text = _INTERVAL_RE.sub(" ", text)      # hydration/supply interval mentions

    raw: list[float] = []

    # 1. Distance lists (2+ tokens) — the most reliable enumeration. Tokens may be
    #    numeric ("10km") or named ("meia maratona") as long as they're members.
    for list_m in _DIST_LIST_RE.finditer(text):
        for tok_m in re.finditer(_DIST_TOKEN, list_m.group(0), re.IGNORECASE):
            km = _token_to_km(tok_m.group(0))
            if km is not None:
                raw.append(km)
    # 2. Shared km suffix ("3, 5 e 10 km") — numbers sharing one trailing km.
    for m in _DIST_SHARED_SUFFIX_RE.finditer(text):
        for num_m in re.finditer(r"(\d+(?:[.,]\d+)?)", m.group(0)):
            try:
                raw.append(float(num_m.group(1).replace(",", ".")))
            except ValueError:
                pass

    if not raw:
        # 3. Labelled single distance ("Modalidade: Maratona", "Distância: 42km").
        for lab_m in _DIST_LABELLED_RE.finditer(text):
            km = _token_to_km(lab_m.group(1))
            if km is not None:
                raw.append(km)
    if not raw:
        # 4. Any explicit numeric km mention (prose-safe — only reads numbers).
        for m in re.finditer(r"\b(\d+(?:[.,]\d+)?)\s*[kK][mM]?\b", text):
            try:
                raw.append(float(m.group(1).replace(",", ".")))
            except ValueError:
                pass

    values = _filter_km_values(raw)
    return sorted(
        [Distancia(km=km, data=None, horario=None) for km in values[:8]],
        key=lambda d: float(d.km),
    )
