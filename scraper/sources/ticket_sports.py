"""Scraper for ticketsports.com.br — JSON API"""
from __future__ import annotations
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

from bs4 import BeautifulSoup

from ..http_client import get
from ..models import Corrida, Distancia, FonteInfo
from ..utils import (
    normalize_titulo, slugify, infer_estado, now_iso, today_iso,
)

BASE = "https://www.ticketsports.com.br"
API_URL = "https://www.ticketsports.app/api/events/list"
DETAIL_URL = "https://www.ticketsports.app/api/events/detail"
SOURCE_NAME = "Ticket Sports"

_BATCH = 2000
_DETAIL_WORKERS = 8

# Keywords that indicate award/ceremony context — not a race start time
_AWARD_KW = re.compile(
    r"premia[çc]|cerim[oô]n|trof[eé]u|award|entrega\s+de\s+kits?",
    re.IGNORECASE,
)

# Keywords that indicate non-running events (triathlon, swimming, cycling, etc.)
_NON_RUNNING_KW = [
    "triathlon", "triathon", "ironman", "duathlon",
    "natação", "natacao", "águas abertas", "aguas abertas", "swimrun",
    "federação de triathlon", "federacao de triathlon",
    "granfondo", "gran fondo", "granfondo", "gran-fondo",
    "ciclismo", "pedalada", "bike tour",
]

# Addresses that indicate a virtual/online event with no fixed location
_VIRTUAL_ADDR_KW = {
    "de onde você estiver", "de onde voce estiver",
    "virtual", "online",
}

# City/country fragments that conclusively identify an international event
_INTL_CITY_KW = {
    "buenos aires", "assunção", "assuncao", "montevideo", "montevidéu",
    "punta del este", "santiago", "lima", "bogotá", "bogota",
    "paris", "london", "londres", "berlin", "berlim", "amsterdam",
    "amsterdam", "rotterdam", "madrid", "barcelona", "rome", "roma",
    "veneza", "venice", "venezia", "florença", "florence",
    "colonia agip", "nove colli",
    "porto", "lisboa", "lisbon",          # Portugal — not Porto Alegre (has ", RS")
    "new york", "boston", "chicago", "tokyo", "tóquio", "sydney",
    "patagonia argentina", "patagônia argentina",
}

# Maps city keyword → country name (PT) for display in localizacao
_CITY_TO_COUNTRY: list[tuple[str, str]] = [
    ("buenos aires", "Argentina"), ("patagonia argentina", "Argentina"),
    ("patagônia argentina", "Argentina"),
    ("assunção", "Paraguai"), ("assuncao", "Paraguai"),
    ("montevideo", "Uruguai"), ("montevidéu", "Uruguai"),
    ("punta del este", "Uruguai"),
    ("santiago", "Chile"),
    ("lima", "Peru"),
    ("bogotá", "Colômbia"), ("bogota", "Colômbia"),
    ("paris", "França"),
    ("london", "Reino Unido"), ("londres", "Reino Unido"),
    ("berlin", "Alemanha"), ("berlim", "Alemanha"),
    ("amsterdam", "Holanda"), ("rotterdam", "Holanda"),
    ("madrid", "Espanha"), ("barcelona", "Espanha"),
    ("veneza", "Itália"), ("venice", "Itália"), ("venezia", "Itália"),
    ("florença", "Itália"), ("florence", "Itália"),
    ("rome", "Itália"), ("roma", "Itália"),
    ("colonia agip", "Itália"), ("nove colli", "Itália"),
    ("porto", "Portugal"), ("lisboa", "Portugal"), ("lisbon", "Portugal"),
    ("new york", "EUA"), ("boston", "EUA"), ("chicago", "EUA"),
    ("tokyo", "Japão"), ("tóquio", "Japão"),
    ("sydney", "Austrália"),
]


def scrape() -> list[Corrida]:
    today = today_iso()
    try:
        resp = get(API_URL, params={"quantity": _BATCH, "atlheteId": 0, "term": ""})
        resp.raise_for_status()
        events: list[dict] = json.loads(resp.content.decode("utf-8"))
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


_DAY_RE = re.compile(
    r"(?:^|\n)\s*dia\s+(\d{1,2})\s+de\s+([a-záéíóúãõâêô]+)\s+de\s+(\d{4})",
    re.IGNORECASE,
)

_PT_MONTHS = {
    "janeiro": "01", "fevereiro": "02", "março": "03", "marco": "03",
    "abril": "04", "maio": "05", "junho": "06", "julho": "07",
    "agosto": "08", "setembro": "09", "outubro": "10",
    "novembro": "11", "dezembro": "12",
}


def _extract_schedule(text: str) -> dict[float, tuple[str | None, str | None]]:
    """Parse multi-day schedule text into {km: (iso_date, horario)}.

    Handles events where different distances race on different days, e.g.:
      Dia 21 de novembro de 2026
        Atletas inscritos 5 km e 10 km – largada 18h00
      Dia 22 de novembro de 2026
        Atletas inscritos na maratona – PCD 5h00 …
        Atletas inscritos na meia maratona – PCD 6h00 …
    """
    day_hits = list(_DAY_RE.finditer(text))
    if not day_hits:
        return {}

    schedule: dict[float, tuple[str | None, str | None]] = {}

    for i, m in enumerate(day_hits):
        mo = _PT_MONTHS.get(m.group(2).lower())
        if not mo:
            continue
        date = f"{m.group(3)}-{mo}-{m.group(1).zfill(2)}"
        end = day_hits[i + 1].start() if i + 1 < len(day_hits) else len(text)
        day_block = text[m.end():end]

        # Split the day block into per-distance sub-sections at "Atletas inscritos"
        sub_blocks = re.split(r"(?i)atletas inscritos", day_block)

        # If no sub-sections found, treat the whole day as one block
        if len(sub_blocks) == 1:
            sub_blocks = [day_block]

        for sub in sub_blocks:
            if not sub.strip():
                continue

            # Extract km values from this sub-block
            sub_lower = sub.lower()
            raw = re.findall(r"\b(\d+(?:[.,]\d+)?)\s*k(?:m)?\b", sub, re.IGNORECASE)
            kms: list[float] = [float(n.replace(",", ".")) for n in raw]
            kms = [k for k in kms if 3 <= k <= 200]
            kms = _canonicalize(kms)

            if "meia maratona" in sub_lower or "half marathon" in sub_lower:
                if 21.097 not in kms:
                    kms.append(21.097)
            if re.search(r"(?<!meia )\bmaratona\b", sub_lower) and 42.195 not in kms:
                kms.append(42.195)

            if not kms:
                continue

            # Earliest start time in this sub-block (skip PCD-only entries)
            times = [
                f"{int(h):02d}:{mn}"
                for h, mn in re.findall(r"(\d{1,2})h(\d{2})", sub, re.IGNORECASE)
                if 4 <= int(h) <= 22
            ]
            earliest = min(times) if times else None

            for km in kms:
                if km not in schedule:
                    schedule[km] = (date, earliest)

    return schedule


def _fetch_detail_distances(corrida: Corrida) -> None:
    event_id = corrida.id.removeprefix("ts_")
    try:
        resp = get(DETAIL_URL, params={"eventId": event_id})
        resp.raise_for_status()
        detail = resp.json()
    except Exception as e:
        print(f"[{SOURCE_NAME}] detalhe '{corrida.titulo}' falhou: {e}")
        return

    texts_nl: list[str] = []
    texts_sp: list[str] = []
    for item in detail.get("eventContents") or []:
        for key in ("description", "content", "text", "value"):
            val = item.get(key)
            if isinstance(val, str) and val:
                if "<" in val:
                    texts_nl.append(BeautifulSoup(val, "lxml").get_text("\n"))
                    texts_sp.append(BeautifulSoup(val, "lxml").get_text(" "))
                else:
                    texts_nl.append(val)
                    texts_sp.append(val)
    for key in ("description", "details", "eventDescription"):
        val = detail.get(key)
        if isinstance(val, str) and val:
            texts_nl.append(val)
            texts_sp.append(val)

    # Try multi-day schedule extraction first (different distances on different days)
    schedule = _extract_schedule("\n".join(texts_nl))
    if schedule:
        corrida.distancias = [
            Distancia(km=km, data=date, horario=horario)
            for km, (date, horario) in sorted(schedule.items())
        ]
    else:
        dists = _extract_distances_from_text(" ".join(texts_sp))
        if dists:
            # Section-header times are more reliable than inline regex matches
            # (inline regex can pick up award-ceremony times instead of start times).
            # When available, section times always win.
            section_times = _extract_times_from_sections(texts_nl)
            for d in dists:
                km_key = next((k for k in section_times if abs(k - d.km) < 0.5), None)
                if km_key is not None:
                    d.horario = section_times[km_key]
            corrida.distancias = dists

    # Set event-level horario from per-distance times or realDate fallback
    per_dist_times = [d.horario for d in corrida.distancias if d.horario]
    if per_dist_times:
        corrida.horario = min(per_dist_times)
    elif corrida.horario is None:
        real_date = detail.get("realDate") or ""
        m = re.search(r"\d{4}-\d{2}-\d{2}\s+(\d{1,2}):(\d{2})", real_date)
        if m:
            corrida.horario = f"{int(m.group(1)):02d}:{m.group(2)}"


def _enrich_all_distances(corridas: list[Corrida]) -> None:
    with ThreadPoolExecutor(max_workers=_DETAIL_WORKERS) as ex:
        futures = {ex.submit(_fetch_detail_distances, c): c for c in corridas}
        for fut in as_completed(futures):
            pass  # errors already logged inside


def _is_running(titulo_lower: str) -> bool:
    return not any(kw in titulo_lower for kw in _NON_RUNNING_KW)


def _parse_event(ev: dict, today: str) -> Corrida | None:
    titulo_raw = ev.get("title") or ""
    titulo = normalize_titulo(titulo_raw)
    if not titulo or len(titulo) < 3:
        return None

    titulo_lower = titulo.lower()
    addr = ev.get("address") or ""

    if not _is_running(titulo_lower):
        return None

    cidade, estado = _split_address(addr)
    if not estado:
        combined = (addr + " " + titulo).lower()
        if any(kw in combined for kw in _INTL_CITY_KW):
            estado = "INT"
        else:
            estado = infer_estado(addr, titulo) or "??"

    # Enrich international locations with country name
    if estado == "INT" and addr and "," not in addr:
        addr_lower = addr.lower()
        for kw, country in _CITY_TO_COUNTRY:
            if kw in addr_lower:
                addr = f"{addr}, {country}"
                break

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

# Matches the first time on a line: "6h55:", "7h00 Largada..."
_SECTION_TIME_RE = re.compile(r"^\s*(\d{1,2})h(\d{2})\b")


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


def _extract_times_from_sections(texts: list[str]) -> dict[float, str]:
    """Extract distance→time from section-header schedules like:

        Maratona (42km):
        6h55: Largada...

        Meia Maratona (21km) e 10km:
        7h00: Largada...

        5km:
        7h30: Largada...
    """
    result: dict[float, str] = {}
    lines = [ln.strip() for text in texts for ln in text.split("\n") if ln.strip()]
    for i, line in enumerate(lines):
        if not line.endswith(":"):
            continue
        if _AWARD_KW.search(line):
            continue
        kms: list[float] = []
        for m in re.finditer(r"(?<![.,])\b(\d+(?:[.,]\d+)?)\s*km\b", line, re.IGNORECASE):
            try:
                km = float(m.group(1).replace(",", "."))
                for canon, lo, hi in _CANONICAL:
                    if lo <= km <= hi:
                        km = canon
                        break
                if 3 <= km <= 200:
                    kms.append(km)
            except ValueError:
                pass
        if not kms:
            continue
        for j in range(i + 1, min(i + 5, len(lines))):
            tm = _SECTION_TIME_RE.match(lines[j])
            if tm:
                h, mn = int(tm.group(1)), tm.group(2)
                if 4 <= h <= 22:
                    horario = f"{h:02d}:{mn}"
                    for km in kms:
                        if km not in result:
                            result[km] = horario
                break
    return result


def _extract_distances_from_text(text: str) -> list[Distancia]:
    """Extract distances from a detail description (authoritative source)."""
    # Extract per-distance start times (e.g. "5KM: 07h00 | 3KM: 07h30")
    time_map: dict[float, str] = {}
    for m in _DIST_TIME_RE.finditer(text):
        ctx = text[max(0, m.start() - 80): m.end() + 20]
        if _AWARD_KW.search(ctx):
            continue
        km = float(m.group(1).replace(",", "."))
        h = int(m.group(2))
        mi = m.group(3)
        if 5 <= h <= 22:  # sanity: event start times, not completion times like 1h30
            time_map[km] = f"{h:02d}:{mi}"

    clean = _INTERVAL_RE.sub(" ", text)
    # (?<![.,]) prevents matching mid-number fragments like "097" from "21.097,5 km"
    raw = re.findall(r"(?<![.,])\b(\d+(?:[.,]\d+)?)\s*k(?:m)?\b", clean, re.IGNORECASE)
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
