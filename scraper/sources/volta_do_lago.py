"""Scraper for Corrida da Volta do Lago Paranoá — Brasília, DF

Primary source: Largada Esportiva REST API (largadaesportiva.com.br/api/Events).
Ticket Sports is kept as a fallback in case the event migrates platforms.
The official site (voltadolago.com.br) is a JS SPA that cannot be scraped directly.
"""
from __future__ import annotations
import json
import re

from ..http_client import get
from ..models import Corrida, Distancia, FonteInfo
from ..utils import normalize_titulo, infer_estado, now_iso, today_iso
from .. import geo as _geo

SOURCE_NAME = "Volta do Lago"

_LE_API  = "https://largadaesportiva.com.br/api/Events"
_LE_BASE = "https://largadaesportiva.com.br"
_TS_API  = "https://www.ticketsports.app/api/events/list"
_TS_BASE = "https://www.ticketsports.com.br"

_MATCH_RE = re.compile(
    r"volta\s+d[ao]\s+lago\s+paran[oó]|volta\s+d[ao]\s+lago",
    re.IGNORECASE,
)

_DIST_RE  = re.compile(r"\b(\d+(?:[.,]\d+)?)\s*km?\b", re.IGNORECASE)
_CANON_KM = {21: 21.097, 42: 42.195}

_DATE_ISO = re.compile(r"\b(202\d|203\d)-(0[1-9]|1[0-2])-(\d{2})\b")
_DATE_RE1 = re.compile(r"\b(\d{1,2})[/.\-](\d{1,2})[/.\-](202\d|203\d)\b")
_DATE_RE2 = re.compile(
    r"\b(\d{1,2})\s+de\s+([a-záéíóúãõâêô]+)\s+de\s+(202\d|203\d)\b",
    re.IGNORECASE,
)
_PT_MONTHS = {
    "jan": "01", "fev": "02", "mar": "03", "abr": "04",
    "mai": "05", "jun": "06", "jul": "07", "ago": "08",
    "set": "09", "out": "10", "nov": "11", "dez": "12",
    "janeiro": "01", "fevereiro": "02", "março": "03", "marco": "03",
    "abril": "04", "maio": "05", "junho": "06", "julho": "07",
    "agosto": "08", "setembro": "09", "outubro": "10",
    "novembro": "11", "dezembro": "12",
}


def scrape() -> list[Corrida]:
    today = today_iso()

    # 1. Largada Esportiva REST API — primary
    result = _search_largada_esportiva(today)
    if result:
        print(f"[{SOURCE_NAME}] {len(result)} corrida(s) encontrada(s) via Largada Esportiva")
        return result

    # 2. Ticket Sports — fallback
    result = _search_ticket_sports(today)
    if result:
        print(f"[{SOURCE_NAME}] {len(result)} corrida(s) encontrada(s) via Ticket Sports")
        return result

    print(f"[{SOURCE_NAME}] evento não encontrado em nenhuma plataforma")
    return []


# ---------------------------------------------------------------------------
# Largada Esportiva
# ---------------------------------------------------------------------------

def _search_largada_esportiva(today: str) -> list[Corrida]:
    try:
        resp = get(_LE_API, source=SOURCE_NAME, timeout=20)
        resp.raise_for_status()
        events = resp.json()
    except Exception as e:
        print(f"[{SOURCE_NAME}] Largada Esportiva erro: {e}")
        return []

    if not isinstance(events, list):
        return []

    results = []
    for ev in events:
        name = ev.get("name") or ""
        if not _MATCH_RE.search(name):
            continue

        # start field is an ISO datetime string: "2026-07-05T04:00:00.000Z"
        raw_start = ev.get("start") or ""
        data_evento = raw_start[:10] if len(raw_start) >= 10 else ""
        if not data_evento or data_evento < today:
            continue

        distancias = _extract_distances(ev.get("regulation") or "")
        ev_id = ev.get("id")
        link = f"{_LE_BASE}/event/{ev_id}"
        localizacao, cidade, estado = _extract_location(ev, name)
        now = now_iso()
        results.append(Corrida(
            id=f"volta-do-lago_{estado.lower() or 'df'}_{data_evento[:4]}",
            titulo=normalize_titulo(name),
            data_evento=data_evento,
            horario=None,
            localizacao=localizacao,
            cidade=cidade,
            estado=estado or "DF",
        pais="BR",
            distancias=distancias,
            imagem_url=None,
            inscricoes_abertas=None,
            periodo_inscricao=None,
            fontes=[FonteInfo(nome="Largada Esportiva", link_evento=link, links_inscricao=[link])],
            miss_count=0,
            first_seen_at=now,
            updated_at=now,
        ))

    return results


# ---------------------------------------------------------------------------
# Ticket Sports (fallback)
# ---------------------------------------------------------------------------

def _search_ticket_sports(today: str) -> list[Corrida]:
    for term in ("volta lago", "volta do lago", "lago paranoa"):
        try:
            resp = get(_TS_API, params={"quantity": 50, "atlheteId": 0, "term": term})
            resp.raise_for_status()
            events: list[dict] = json.loads(resp.content.decode("utf-8"))
        except Exception as e:
            print(f"[{SOURCE_NAME}] Ticket Sports erro (term={term!r}): {e}")
            continue

        for ev in events:
            title = ev.get("title") or ev.get("nome") or ""
            if not _MATCH_RE.search(title):
                continue
            c = _parse_ts_event(ev, today)
            if c:
                return [c]

    return []


def _parse_ts_event(ev: dict, today: str) -> Corrida | None:
    title  = ev.get("title") or ev.get("nome") or ""
    titulo = normalize_titulo(title)
    if not titulo:
        return None

    event_id = ev.get("id") or ev.get("eventId") or ""
    slug     = ev.get("url") or ev.get("slug") or ""
    link     = (f"{_TS_BASE}/{slug}" if slug else
                f"{_TS_BASE}/evento/{event_id}" if event_id else _TS_BASE)

    raw_date = (ev.get("date") or ev.get("data") or
                ev.get("startDate") or ev.get("dataInicio") or "")
    data_evento = _parse_date(raw_date) or ""

    if data_evento and data_evento < today:
        return None

    dist_text = " ".join(filter(None, [
        ev.get("description") or "", ev.get("descricao") or "",
        ev.get("modalidades") or "",
    ]))
    distancias = _extract_distances(dist_text)

    imagem = ev.get("image") or ev.get("foto") or ev.get("banner") or None
    if imagem and imagem.startswith("//"):
        imagem = "https:" + imagem

    localizacao, cidade, estado = _extract_location(ev, title)
    now = now_iso()
    return Corrida(
        id=f"volta-do-lago_{estado.lower() or 'df'}_{data_evento[:4] if data_evento else today[:4]}",
        titulo=titulo,
        data_evento=data_evento,
        horario=None,
        localizacao=localizacao,
        cidade=cidade,
        estado=estado or "DF",
        pais="BR",
        distancias=distancias,
        imagem_url=imagem or None,
        inscricoes_abertas=None,
        periodo_inscricao=None,
        fontes=[FonteInfo(nome=SOURCE_NAME, link_evento=link, links_inscricao=[link])],
        miss_count=0,
        first_seen_at=now,
        updated_at=now,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_location(ev: dict, name: str) -> tuple[str, str, str]:
    """Return (localizacao, cidade, estado) from a Largada Esportiva API event dict."""
    cidade = ev.get("cidade") or ev.get("city") or ev.get("municipio") or ""
    uf = (ev.get("estado") or ev.get("uf") or ev.get("state") or "").strip().upper()
    if len(uf) != 2:
        uf = ""
    address = ev.get("address") or ev.get("local") or ev.get("location") or ""

    if not uf:
        uf = infer_estado(address, name) or _geo.resolve(address, "", "BR")[1] or ""

    # Try to parse "City, UF" or "City – UF" pattern from address
    if not cidade and address:
        m = re.search(
            r"\b([A-ZÁÉÍÓÚÂÊÔÃÕa-záéíóúâêôãõç][A-Za-záéíóúâêôãõç\s]{2,25})\s*[,–\-]\s*([A-Z]{2})\b",
            address,
        )
        if m:
            cidade = normalize_titulo(m.group(1).strip())
            if not uf:
                uf = m.group(2)

    if cidade and uf:
        localizacao = f"{cidade}, {uf}"
    elif uf:
        localizacao = uf
    elif cidade:
        localizacao = cidade
    else:
        localizacao = address[:60].strip() if address else ""

    return localizacao, cidade, uf


def _parse_date(raw: str) -> str | None:
    if not raw:
        return None
    m = _DATE_ISO.search(raw)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    m = _DATE_RE1.search(raw)
    if m:
        d, mo, y = m.group(1).zfill(2), m.group(2).zfill(2), m.group(3)
        return f"{y}-{mo}-{d}"
    m = _DATE_RE2.search(raw)
    if m:
        mo = _PT_MONTHS.get(m.group(2).lower())
        if mo:
            return f"{m.group(3)}-{mo}-{m.group(1).zfill(2)}"
    return None


def _extract_distances(text: str) -> list[Distancia]:
    if not text:
        return []
    seen: set[int] = set()
    result: list[Distancia] = []
    if re.search(r"meia\s+maratona|half\s+marathon", text, re.IGNORECASE):
        seen.add(21)
        result.append(Distancia(km=21.097, data=None, horario=None))
    if re.search(r"(?<!meia\s)\bmaratona\b", text, re.IGNORECASE):
        if 42 not in seen:
            seen.add(42)
            result.append(Distancia(km=42.195, data=None, horario=None))
    for m in _DIST_RE.finditer(text):
        km = float(m.group(1).replace(",", "."))
        key = round(km)
        if 3 <= km <= 200 and key not in seen:
            seen.add(key)
            result.append(Distancia(km=_CANON_KM.get(key, km), data=None, horario=None))
    return sorted(result, key=lambda d: float(d.km) if isinstance(d.km, (int, float)) else 999)
