"""Scraper for ativo.com — JSON API"""
from __future__ import annotations
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

from bs4 import BeautifulSoup

from ..http_client import get
from ..models import Corrida, Distancia, FonteInfo
from ..utils import normalize_titulo, now_iso, today_iso
from .. import geo as _geo

API_URL = "https://www.ativo.com/eventos.json"
PAY_BASE = "https://pay.ativo.com/evento"
SOURCE_NAME = "Ativo"

_RUNNING_TYPES = {"corrida de rua", "corrida de montanha", "trail running", "corrida"}

_CANONICAL = [(42.195, 41.5, 43.0), (21.097, 20.5, 21.5)]

# Keyword-anchored time for Brazilian Portuguese race pages
_HORARIO_KW_RE = re.compile(
    r"(?:hor[aá]rio|largada|in[íi]cio|sa[íi]da|hora\s+de\s+(?:in[íi]cio|largada|sa[íi]da))"
    r"[^0-9]{0,40}(\d{1,2})[h:](\d{2})"
    r"|(?:hor[aá]rio|largada|in[íi]cio)[^0-9]{0,40}(\d{1,2})\s*[hH]\b",
    re.IGNORECASE,
)
_GENERIC_TIME_RE = re.compile(
    r"\b(\d{1,2})[h:](\d{2})\s*(?:h(?:rs?|oras?)?)?\b(?!\s*(?:km|k\b))",
    re.IGNORECASE,
)


def scrape() -> list[Corrida]:
    today = today_iso()
    try:
        resp = get(API_URL)
        resp.raise_for_status()
        events: list[dict] = resp.json()
    except Exception as e:
        print(f"[{SOURCE_NAME}] erro ao buscar API: {e}")
        return []

    corridas: list[Corrida] = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(_parse_event, ev, today): ev for ev in events}
        for future in as_completed(futures):
            ev = futures[future]
            try:
                corrida = future.result()
                if corrida:
                    corridas.append(corrida)
            except Exception as e:
                print(f"[{SOURCE_NAME}] erro ao parsear '{ev.get('post_title')}': {e}")

    print(f"[{SOURCE_NAME}] {len(corridas)} corridas encontradas")
    return corridas


def _parse_km(s: str) -> float | None:
    m = re.match(r"(\d+(?:[.,]\d+)?)\s*k(?:m)?", s.strip(), re.IGNORECASE)
    if not m:
        return None
    km = float(m.group(1).replace(",", "."))
    for canon, lo, hi in _CANONICAL:
        if lo <= km <= hi:
            return canon
    return km if 1 <= km <= 200 else None


def _extract_horario_from_json(ev: dict) -> str | None:
    """Pull start time from any field in a per-event JSON dict."""
    # Datetime fields with embedded time component
    for key in ("dt_evento", "dt_inicio", "dt_largada", "start_date", "start_datetime"):
        dt = ev.get(key) or ""
        if isinstance(dt, str) and len(dt) > 10:
            m_t = re.search(r"[T ](\d{2}):(\d{2})", dt)
            if m_t:
                h, mi = int(m_t.group(1)), int(m_t.group(2))
                if 4 <= h <= 23 and 0 <= mi <= 59:
                    return f"{h:02d}:{mi:02d}"
    # Time-only fields
    for key in ("hora_largada", "horario", "hora_inicio", "hora_evento",
                "ds_horario", "hr_evento", "tm_evento", "hora", "hora_inicio_evento"):
        val = ev.get(key) or ""
        if isinstance(val, str) and val.strip():
            m_t = re.search(r"(\d{1,2}):(\d{2})", val)
            if m_t:
                h, mi = int(m_t.group(1)), int(m_t.group(2))
                if 4 <= h <= 23 and 0 <= mi <= 59:
                    return f"{h:02d}:{mi:02d}"
    return None


def _fetch_horario_from_page(url: str) -> str | None:
    """Fetch the HTML event page and extract start time from visible text."""
    try:
        resp = get(url, source=SOURCE_NAME, timeout=20)
        if resp.status_code != 200:
            return None
        soup = BeautifulSoup(resp.text, "lxml")
        text = soup.get_text(" ", strip=True)
        m = _HORARIO_KW_RE.search(text)
        if m:
            if m.group(1) is not None:
                h, mi = int(m.group(1)), int(m.group(2))
            else:
                h, mi = int(m.group(3)), 0
            if 4 <= h <= 23:
                return f"{h:02d}:{mi:02d}"
        m = _GENERIC_TIME_RE.search(text)
        if m:
            h, mi = int(m.group(1)), int(m.group(2))
            if 4 <= h <= 23:
                return f"{h:02d}:{mi:02d}"
    except Exception as e:
        print(f"[{SOURCE_NAME}] HTML page fetch falhou ({url[:60]}): {e}")
    return None


def _fetch_event_json(url: str) -> tuple[list[Distancia], str | None]:
    """Fetch the per-event JSON (post_json); return (distances, horario)."""
    try:
        resp = get(url, source=SOURCE_NAME, timeout=15)
        resp.raise_for_status()
        ev = resp.json()
    except Exception as e:
        print(f"[{SOURCE_NAME}] fetch JSON falhou ({url[:60]}): {e}")
        return [], None
    seen: set[float] = set()
    result: list[Distancia] = []
    for d in ev.get("distancias") or []:
        km = _parse_km(d.get("ds_distancia") or "")
        if km is not None and km >= 3 and km not in seen:
            seen.add(km)
            result.append(Distancia(km=km, data=None, horario=None))
    if not result:
        titulo_fallback = normalize_titulo(ev.get("post_title") or "")
        result = _distances_from_title(titulo_fallback.lower())
    horario = _extract_horario_from_json(ev)
    return sorted(result, key=lambda d: d.km), horario


def _parse_event(ev: dict, today: str) -> Corrida | None:
    tipo = (ev.get("ds_tipo_evento") or "").lower()
    if tipo not in _RUNNING_TYPES:
        return None

    if ev.get("fl_suspenso"):
        return None

    titulo = normalize_titulo(ev.get("post_title") or "")
    if not titulo or len(titulo) < 3:
        return None

    dt_raw = ev.get("dt_evento") or ""
    data_evento = dt_raw[:10] if len(dt_raw) >= 10 else None
    if not data_evento or data_evento < today:
        return None

    # Try all time fields available in the listing payload first
    horario: str | None = _extract_horario_from_json(ev)

    estado = (ev.get("ds_estado") or "").strip()
    cidade = (ev.get("ds_cidade") or "").strip()
    localizacao = f"{cidade}, {estado}" if cidade and estado else cidade or estado or ""

    distancias: list[Distancia] = []
    seen: set[float] = set()
    for d in ev.get("distancias") or []:
        km = _parse_km(d.get("ds_distancia") or "")
        if km is not None and km >= 3 and km not in seen:
            seen.add(km)
            distancias.append(Distancia(km=km, data=None, horario=None))
    distancias.sort(key=lambda d: d.km)

    if not distancias:
        distancias = _distances_from_title(titulo.lower())

    event_id = str(ev.get("id_evento") or "")
    pay_link = f"{PAY_BASE}/{event_id}" if event_id else None
    post_json_url = ev.get("post_json") or ""
    event_page = post_json_url.replace("/index.json", "") or "https://www.ativo.com"

    # Fetch per-event JSON when listing data lacks distances or horario
    if (not distancias or not horario) and post_json_url:
        extra_dists, extra_horario = _fetch_event_json(post_json_url)
        if not distancias and extra_dists:
            distancias = extra_dists
        if not horario and extra_horario:
            horario = extra_horario

    # Last resort: scrape the HTML event page for start time
    if not horario and event_page and event_page != "https://www.ativo.com":
        horario = _fetch_horario_from_page(event_page)

    if not distancias:
        print(f"[{SOURCE_NAME}] sem distâncias, pulando: {titulo!r}")
        return None
    if not horario:
        print(f"[{SOURCE_NAME}] sem horário, pulando: {titulo!r}")
        return None

    _pais_geo, _estado_geo = _geo.resolve(localizacao, cidade, "BR")
    pais = _pais_geo or "BR"
    estado = estado or _estado_geo or ""

    now = now_iso()
    fonte = FonteInfo(
        nome=SOURCE_NAME,
        link_evento=event_page,
        links_inscricao=[pay_link] if pay_link else [event_page],
        tipo="inscricao",
    )

    return Corrida(
        id=f"ativo_{event_id}",
        titulo=titulo,
        data_evento=data_evento,
        horario=horario,
        localizacao=localizacao,
        cidade=cidade,
        estado=estado,
        pais=pais,
        distancias=distancias,
        imagem_url=ev.get("thumbnail") or None,
        inscricoes_abertas=None,
        periodo_inscricao=None,
        fontes=[fonte],
        miss_count=0,
        first_seen_at=now,
        updated_at=now,
    )


def _distances_from_title(titulo_lower: str) -> list[Distancia]:
    seen: set[float] = set()
    result: list[Distancia] = []

    if "meia maratona" in titulo_lower or "half marathon" in titulo_lower:
        seen.add(21.097)
        result.append(Distancia(km=21.097, data=None, horario=None))

    if re.search(r"(?<!meia )\bmaratona\b|(?<!half )\bmarathon\b", titulo_lower):
        if 42.195 not in seen:
            seen.add(42.195)
            result.append(Distancia(km=42.195, data=None, horario=None))

    for m in re.finditer(r"\b(\d+(?:[.,]\d+)?)\s*k(?:m)?\b", titulo_lower):
        km = float(m.group(1).replace(",", "."))
        for canon, lo, hi in _CANONICAL:
            if lo <= km <= hi:
                km = canon
                break
        if km not in seen and 3 <= km <= 200:
            seen.add(km)
            result.append(Distancia(km=km, data=None, horario=None))

    return sorted(result, key=lambda d: d.km)
