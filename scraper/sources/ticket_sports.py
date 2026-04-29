"""Scraper for ticketsports.com.br — JSON API"""
from __future__ import annotations
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

from bs4 import BeautifulSoup

from ..http_client import get
from ..models import Corrida, Distancia, FonteInfo
from ..utils import (
    normalize_titulo, slugify, is_bsb_event, infer_estado, now_iso, today_iso,
)

BASE = "https://www.ticketsports.com.br"
API_URL = "https://www.ticketsports.app/api/events/list"
DETAIL_URL = "https://www.ticketsports.app/api/events/detail"
SOURCE_NAME = "Ticket Sports"

_BATCH = 2000
_DETAIL_WORKERS = 8

_MARATONAS_ALVO = [
    "maratona de sao paulo", "maratona do rio", "maratona de porto alegre",
    "maratona de florianopolis", "maratona de curitiba", "maratona de belo horizonte",
    "maratona de fortaleza", "maratona de salvador", "maratona de recife",
    "maratona de manaus", "maratona caixa", "maratona de brasilia",
    "maratona monumental", "maratona banco do brasil",
]

# Keywords that indicate non-running events (triathlon, swimming, etc.)
_NON_RUNNING_KW = [
    "triathlon", "triathon", "ironman", "duathlon",
    "natação", "natacao", "águas abertas", "aguas abertas", "swimrun",
    "federação de triathlon", "federacao de triathlon",
]


def scrape() -> list[Corrida]:
    today = today_iso()
    try:
        resp = get(API_URL, params={"quantity": _BATCH, "atlheteId": 0, "term": ""})
        resp.raise_for_status()
        events: list[dict] = resp.json()
    except Exception as e:
        print(f"[{SOURCE_NAME}] erro ao buscar API: {e}")
        return []

    corridas: list[Corrida] = []
    for ev in events:
        try:
            corrida = _parse_event(ev, today)
            if corrida:
                corridas.append(corrida)
        except Exception as e:
            print(f"[{SOURCE_NAME}] erro ao parsear '{ev.get('title')}': {e}")

    # Always fetch detail for every event — detail description is authoritative
    _enrich_all_distances(corridas)

    print(f"[{SOURCE_NAME}] {len(corridas)} corridas encontradas")
    return corridas


def _fetch_detail_distances(corrida: Corrida) -> None:
    event_id = corrida.id.removeprefix("ts_")
    try:
        resp = get(DETAIL_URL, params={"eventId": event_id})
        resp.raise_for_status()
        detail = resp.json()
    except Exception as e:
        print(f"[{SOURCE_NAME}] detalhe '{corrida.titulo}' falhou: {e}")
        return

    texts: list[str] = []
    for item in detail.get("eventContents") or []:
        for key in ("description", "content", "text", "value"):
            val = item.get(key)
            if isinstance(val, str) and val:
                texts.append(BeautifulSoup(val, "lxml").get_text(" "))
    for key in ("description", "details", "eventDescription"):
        val = detail.get(key)
        if isinstance(val, str) and val:
            texts.append(val)

    dists = _extract_distances_from_text(" ".join(texts))
    if dists:
        corrida.distancias = dists
    # If detail returns nothing, keep whatever title-based extraction found


def _enrich_all_distances(corridas: list[Corrida]) -> None:
    with ThreadPoolExecutor(max_workers=_DETAIL_WORKERS) as ex:
        futures = {ex.submit(_fetch_detail_distances, c): c for c in corridas}
        for fut in as_completed(futures):
            pass  # errors already logged inside


_DF_MARKERS = (", df", "brasília", "brasilia", "distrito federal",
               "taguatinga", "ceilândia", "ceilandia", "sobradinho, df",
               "samambaia", "plano piloto")


def _is_df_event(addr: str) -> bool:
    """Strict DF check using the address string only.

    Deliberately avoids is_bsb_event() because that function matches
    'guara' as a substring, causing false positives for cities like
    Guaratinguetá, Guarapuava, and Guaramirim.
    """
    addr_l = addr.lower()
    return any(marker in addr_l for marker in _DF_MARKERS)


def _is_target(addr: str, titulo_lower: str) -> bool:
    if _is_df_event(addr):
        return True
    if any(m in titulo_lower for m in _MARATONAS_ALVO):
        return True
    return False


def _is_running(titulo_lower: str) -> bool:
    return not any(kw in titulo_lower for kw in _NON_RUNNING_KW)


def _parse_event(ev: dict, today: str) -> Corrida | None:
    titulo_raw = ev.get("title") or ""
    titulo = normalize_titulo(titulo_raw)
    if not titulo or len(titulo) < 3:
        return None

    titulo_lower = titulo.lower()
    addr = ev.get("address") or ""

    if not _is_target(addr, titulo_lower):
        return None
    if not _is_running(titulo_lower):
        return None

    cidade, estado = _split_address(addr)
    if not estado:
        estado = infer_estado(addr, titulo) or "??"

    data_evento = _parse_date(ev.get("date") or "")
    if not data_evento or data_evento < today:
        return None

    status_raw = (ev.get("status") or "").lower()
    if ev.get("isSoldOut"):
        inscricoes_abertas: bool | None = False
    elif any(kw in status_raw for kw in ("encerrado", "esgotado", "fechado", "sold")):
        inscricoes_abertas = False
    elif "aberto" in status_raw:
        inscricoes_abertas = True
    else:
        inscricoes_abertas = None

    link = ev.get("uri") or BASE
    if link.startswith("//"):
        link = "https:" + link

    now = now_iso()
    fonte = FonteInfo(
        nome=SOURCE_NAME,
        link_evento=link,
        links_inscricao=[link] if inscricoes_abertas else [],
        inscricoes=[],
    )

    return Corrida(
        id=f"ts_{ev['eventId']}",
        titulo=titulo,
        data_evento=data_evento,
        horario=None,
        localizacao=addr or cidade,
        cidade=cidade,
        estado=estado,
        distancias=_extract_distances(titulo_lower),
        imagem_url=ev.get("logoImageSource") or None,
        inscricoes_abertas=inscricoes_abertas,
        periodo_inscricao=None,
        fontes=[fonte],
        miss_count=0,
        first_seen_at=now,
        updated_at=now,
    )


def _split_address(addr: str) -> tuple[str, str]:
    """'São Paulo, SP' → ('São Paulo', 'SP')"""
    parts = addr.rsplit(",", 1)
    if len(parts) == 2:
        state = parts[1].strip()
        if len(state) == 2 and state.isupper():
            return parts[0].strip(), state
    return addr.strip(), ""


def _parse_date(raw: str) -> str | None:
    """Extract the earliest date from raw string (handles 'DD e DD/MM/YYYY' etc.)."""
    if not raw:
        return None
    # Try all DD/MM/YYYY occurrences and return the earliest future-leaning one
    matches = re.findall(r"(\d{1,2})/(\d{1,2})/(\d{4})", raw)
    if matches:
        dates = [f"{y}-{m.zfill(2)}-{d.zfill(2)}" for d, m, y in matches]
        return sorted(dates)[0]
    # Portuguese long form: "18 DE ABRIL DE 2027"
    _MONTHS = {
        "janeiro": "01", "fevereiro": "02", "março": "03", "marco": "03",
        "abril": "04", "maio": "05", "junho": "06", "julho": "07",
        "agosto": "08", "setembro": "09", "outubro": "10",
        "novembro": "11", "dezembro": "12",
    }
    m = re.search(r"(\d{1,2})\s+de\s+([a-záéíóúãõâêô]+)\s+de\s+(\d{4})", raw, re.IGNORECASE)
    if m:
        mo = _MONTHS.get(m.group(2).lower())
        if mo:
            return f"{m.group(3)}-{mo}-{m.group(1).zfill(2)}"
    return None


_INTERVAL_RE = re.compile(
    r"a cada \d+(?:[.,]\d+)?\s*k(?:m)?\b"
    r"|cada \d+(?:[.,]\d+)?\s*k(?:m)?\b"
    r"|\d+(?:[.,]\d+)?\s*k(?:m)?\s*(?:de hidrat|de água|de abastec)",
    re.IGNORECASE,
)

_CANONICAL = [(42.195, 41.5, 43.0), (21.097, 20.5, 21.5)]

# Matches "5KM: 07h00", "10km - 08:30" etc. to extract per-distance start times
_DIST_TIME_RE = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*k(?:m)?\b\s*[:\-–]?\s*(\d{1,2})[h:](\d{2})",
    re.IGNORECASE,
)


def _canonicalize(kms: list[float]) -> list[float]:
    """Replace values near known canonical distances; deduplicate."""
    out: list[float] = []
    seen: set[float] = set()
    for km in kms:
        for canon, lo, hi in _CANONICAL:
            if lo <= km <= hi:
                km = canon
                break
        if km not in seen:
            seen.add(km)
            out.append(km)
    return out


def _extract_distances_from_text(text: str) -> list[Distancia]:
    """Extract distances from a detail description (authoritative source)."""
    # Extract per-distance start times (e.g. "5KM: 07h00 | 3KM: 07h30")
    time_map: dict[float, str] = {}
    for m in _DIST_TIME_RE.finditer(text):
        km = float(m.group(1).replace(",", "."))
        h = int(m.group(2))
        mi = m.group(3)
        if 5 <= h <= 22:  # sanity: event start times, not completion times like 1h30
            time_map[km] = f"{h:02d}:{mi}"

    clean = _INTERVAL_RE.sub(" ", text)
    raw = re.findall(r"\b(\d+(?:[.,]\d+)?)\s*k(?:m)?\b", clean, re.IGNORECASE)
    kms = [float(n.replace(",", ".")) for n in raw]
    kms = [k for k in kms if 3 <= k <= 200]  # ≥3 km: filter walking/kids/hydration noise
    kms = _canonicalize(kms)

    result = []
    for k in sorted(kms):
        horario = time_map.get(k)
        if not horario:
            for tk, tv in time_map.items():
                if abs(tk - k) <= 0.5:
                    horario = tv
                    break
        result.append(Distancia(km=k, data=None, horario=horario))
    return result


def _extract_distances(titulo_lower: str) -> list[Distancia]:
    """Title-based fallback — used only when detail API returns nothing."""
    seen: set[float] = set()
    result: list[Distancia] = []

    # Half marathon must be checked before full to avoid "maratona" false-matching
    if "meia maratona" in titulo_lower or "half marathon" in titulo_lower:
        seen.add(21.097)
        result.append(Distancia(km=21.097, data=None, horario=None))

    # Full marathon: "maratona"/"marathon" only when NOT preceded by "meia"/"half"
    if re.search(r"(?<!meia )\bmaratona\b|(?<!half )\bmarathon\b", titulo_lower):
        if 42.195 not in seen:
            seen.add(42.195)
            result.append(Distancia(km=42.195, data=None, horario=None))

    # Numeric: "5k", "10km", "42 km"
    for m in re.finditer(r"\b(\d+(?:[.,]\d+)?)\s*k(?:m)?\b", titulo_lower):
        km = float(m.group(1).replace(",", "."))
        km_c = next((c for c, lo, hi in _CANONICAL if lo <= km <= hi), km)
        if km_c not in seen and 1 <= km <= 200:
            seen.add(km_c)
            result.append(Distancia(km=km_c, data=None, horario=None))

    return sorted(result, key=lambda d: d.km if isinstance(d.km, (int, float)) else 999)
