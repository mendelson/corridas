"""Scraper for Corrida da Volta do Lago Paranoá — Brasília, DF

The official site (voltadolago.com.br) is a JavaScript-heavy SPA that cannot be
scraped without full JS rendering. This scraper finds the event on major Brazilian
inscription platforms instead: Ticket Sports (JSON API) and Sympla (HTML/Next.js).
"""
from __future__ import annotations
import json
import re

from bs4 import BeautifulSoup

from ..http_client import get
from ..models import Corrida, Distancia, FonteInfo
from ..utils import normalize_titulo, slugify, now_iso, today_iso

SOURCE_NAME = "Volta do Lago"
BASE_SITE   = "https://voltadolago.com.br"

# ── Ticket Sports ────────────────────────────────────────────────────────────
_TS_API  = "https://www.ticketsports.app/api/events/list"
_TS_BASE = "https://www.ticketsports.com.br"

# ── Sympla ───────────────────────────────────────────────────────────────────
_SYMPLA_BASE = "https://www.sympla.com.br"

# Matches the event name in any title/description
_MATCH_RE = re.compile(
    r"volta\s+d[ao]\s+lago\s+paran[oó]|volta\s+d[ao]\s+lago",
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
_DATE_ISO = re.compile(r"\b(202\d|203\d)-(0[1-9]|1[0-2])-(\d{2})\b")
_DATE_RE1 = re.compile(r"\b(\d{1,2})[/.\-](\d{1,2})[/.\-](202\d|203\d)\b")
_DATE_RE2 = re.compile(
    r"\b(\d{1,2})\s+de\s+([a-záéíóúãõâêô]+)\s+de\s+(202\d|203\d)\b",
    re.IGNORECASE,
)
_DIST_RE  = re.compile(r"\b(\d+(?:[.,]\d+)?)\s*km?\b", re.IGNORECASE)
_CANON_KM = {21: 21.097, 42: 42.195}


def scrape() -> list[Corrida]:
    today = today_iso()

    # 1. Ticket Sports — targeted search
    result = _search_ticket_sports(today)
    if result:
        print(f"[{SOURCE_NAME}] {len(result)} corrida(s) encontrada(s) via Ticket Sports")
        return result

    # 2. Sympla — targeted search
    result = _search_sympla(today)
    if result:
        print(f"[{SOURCE_NAME}] {len(result)} corrida(s) encontrada(s) via Sympla")
        return result

    print(f"[{SOURCE_NAME}] evento não encontrado em nenhuma plataforma")
    return []


# ---------------------------------------------------------------------------
# Ticket Sports
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

    event_id  = ev.get("id") or ev.get("eventId") or ""
    slug      = ev.get("url") or ev.get("slug") or ""
    link      = (f"{_TS_BASE}/{slug}" if slug else
                 f"{_TS_BASE}/evento/{event_id}" if event_id else _TS_BASE)

    # Date
    raw_date = (ev.get("date") or ev.get("data") or
                ev.get("startDate") or ev.get("dataInicio") or "")
    data_evento = _parse_date(raw_date) or ""

    if data_evento and data_evento < today:
        return None

    # Distances
    dist_text = " ".join(filter(None, [
        ev.get("description") or "", ev.get("descricao") or "",
        ev.get("modalidades") or "",
    ]))
    distancias = _extract_distances(dist_text) or _guess_distances(titulo)

    imagem = ev.get("image") or ev.get("foto") or ev.get("banner") or None
    if imagem and imagem.startswith("//"):
        imagem = "https:" + imagem

    now = now_iso()
    return Corrida(
        id=f"volta-do-lago_df_{data_evento[:4] if data_evento else today[:4]}",
        titulo=titulo,
        data_evento=data_evento,
        horario=None,
        localizacao="Brasília, DF",
        cidade="Brasília",
        estado="DF",
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
# Sympla
# ---------------------------------------------------------------------------

def _search_sympla(today: str) -> list[Corrida]:
    for term in ("volta do lago", "volta lago brasilia", "volta lago paranoa"):
        url = f"{_SYMPLA_BASE}/busca?q={term.replace(' ', '+')}"
        try:
            resp = get(url, source=SOURCE_NAME, timeout=30)
            if resp.status_code != 200:
                continue
            soup = BeautifulSoup(resp.text, "lxml")
        except Exception:
            continue

        # Try __NEXT_DATA__ first
        tag = soup.find("script", id="__NEXT_DATA__")
        if tag:
            try:
                data = json.loads(tag.string or "")
                items = _dig(data, "pageProps", "initialData", "results") or []
                for item in items:
                    name = item.get("name") or item.get("title") or ""
                    if _MATCH_RE.search(name):
                        c = _parse_sympla_item(item, today)
                        if c:
                            return [c]
            except Exception:
                pass

        # HTML fallback: look for any card/link containing the event name
        for a in soup.find_all("a", href=True):
            text = a.get_text(" ", strip=True)
            if _MATCH_RE.search(text):
                href = a["href"]
                if not href.startswith("http"):
                    href = _SYMPLA_BASE + href
                c = _parse_sympla_link(text, href, today)
                if c:
                    return [c]

    return []


def _parse_sympla_item(item: dict, today: str) -> Corrida | None:
    title = item.get("name") or item.get("title") or ""
    titulo = normalize_titulo(title)
    if not titulo:
        return None

    slug      = item.get("url") or item.get("id") or ""
    link      = (f"{_SYMPLA_BASE}/evento/{slug}" if slug and not slug.startswith("http")
                 else slug or _SYMPLA_BASE)

    raw_date  = item.get("start_date") or item.get("startDate") or item.get("date") or ""
    data_evento = _parse_date(raw_date) or ""
    if data_evento and data_evento < today:
        return None

    distancias = _extract_distances(
        " ".join(filter(None, [item.get("description") or "", title]))
    ) or _guess_distances(titulo)

    imagem = item.get("image") or item.get("thumb") or item.get("cover") or None

    now = now_iso()
    return Corrida(
        id=f"volta-do-lago_df_{data_evento[:4] if data_evento else today[:4]}",
        titulo=titulo,
        data_evento=data_evento,
        horario=None,
        localizacao="Brasília, DF",
        cidade="Brasília",
        estado="DF",
        distancias=distancias,
        imagem_url=imagem,
        inscricoes_abertas=None,
        periodo_inscricao=None,
        fontes=[FonteInfo(nome=SOURCE_NAME, link_evento=link, links_inscricao=[link])],
        miss_count=0,
        first_seen_at=now,
        updated_at=now,
    )


def _parse_sympla_link(text: str, href: str, today: str) -> Corrida | None:
    titulo = normalize_titulo(text[:120])
    if not titulo:
        return None
    data_evento = _parse_date_from_str(text) or ""
    if data_evento and data_evento < today:
        return None
    distancias = _extract_distances(text) or _guess_distances(titulo)
    now = now_iso()
    return Corrida(
        id=f"volta-do-lago_df_{data_evento[:4] if data_evento else today[:4]}",
        titulo=titulo,
        data_evento=data_evento,
        horario=None,
        localizacao="Brasília, DF",
        cidade="Brasília",
        estado="DF",
        distancias=distancias,
        imagem_url=None,
        inscricoes_abertas=None,
        periodo_inscricao=None,
        fontes=[FonteInfo(nome=SOURCE_NAME, link_evento=href, links_inscricao=[href])],
        miss_count=0,
        first_seen_at=now,
        updated_at=now,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_date(raw: str) -> str | None:
    if not raw:
        return None
    m = _DATE_ISO.search(raw)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    return _parse_date_from_str(raw)


def _parse_date_from_str(text: str) -> str | None:
    m = _DATE_RE1.search(text)
    if m:
        d, mo, y = m.group(1).zfill(2), m.group(2).zfill(2), m.group(3)
        return f"{y}-{mo}-{d}"
    m = _DATE_RE2.search(text)
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
        seen.add(21); result.append(Distancia(km=21.097, data=None, horario=None))
    if re.search(r"(?<!meia\s)\bmaratona\b", text, re.IGNORECASE):
        if 42 not in seen:
            seen.add(42); result.append(Distancia(km=42.195, data=None, horario=None))
    for m in _DIST_RE.finditer(text):
        km = float(m.group(1).replace(",", "."))
        key = round(km)
        if 3 <= km <= 100 and key not in seen:
            seen.add(key)
            result.append(Distancia(km=_CANON_KM.get(key, km), data=None, horario=None))
    return sorted(result, key=lambda d: float(d.km) if isinstance(d.km, (int, float)) else 999)


def _guess_distances(titulo: str) -> list[Distancia]:
    t = titulo.lower()
    if "meia" in t:
        return [Distancia(km=21.097, data=None, horario=None)]
    if "maratona" in t:
        return [Distancia(km=42.195, data=None, horario=None)]
    return [
        Distancia(km=5.0,  data=None, horario=None),
        Distancia(km=10.0, data=None, horario=None),
    ]


def _dig(obj, *keys):
    for k in keys:
        if not isinstance(obj, dict):
            return None
        obj = obj.get(k)
    return obj
