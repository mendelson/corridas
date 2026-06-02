"""Scraper for ativo.com — JSON API"""
from __future__ import annotations
import re

from ..http_client import get
from ..models import Corrida, Distancia, FonteInfo
from ..utils import normalize_titulo, now_iso, today_iso
from .. import geo as _geo

API_URL = "https://www.ativo.com/eventos.json"
PAY_BASE = "https://pay.ativo.com/evento"
SOURCE_NAME = "Ativo"

_RUNNING_TYPES = {"corrida de rua", "corrida de montanha", "trail running", "corrida"}

_CANONICAL = [(42.195, 41.5, 43.0), (21.097, 20.5, 21.5)]


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
    for ev in events:
        try:
            corrida = _parse_event(ev, today)
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


def _fetch_event_json(url: str) -> tuple[list[Distancia], str | None]:
    """Fetch the per-event JSON (post_json); return (distances, horario)."""
    try:
        resp = get(url, source=SOURCE_NAME, timeout=15)
        resp.raise_for_status()
        ev = resp.json()
    except Exception as e:
        print(f"[{SOURCE_NAME}] fetch externo falhou ({url[:60]}): {e}")
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
    # Try to extract horario from event JSON date fields
    horario: str | None = None
    for key in ("dt_evento", "dt_inicio", "start_date"):
        dt = ev.get(key) or ""
        if len(dt) > 10:
            m_t = re.search(r"[T ](\d{2}):(\d{2})", dt)
            if m_t:
                h, mi = int(m_t.group(1)), int(m_t.group(2))
                if 4 <= h <= 23 and 0 <= mi <= 59:
                    horario = f"{h:02d}:{mi:02d}"
                    break
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

    horario: str | None = None
    if len(dt_raw) > 10:
        m_t = re.search(r"[T ](\d{2}):(\d{2})", dt_raw)
        if m_t:
            h, mi = int(m_t.group(1)), int(m_t.group(2))
            if 4 <= h <= 23 and 0 <= mi <= 59:  # exclude midnight placeholders
                horario = f"{h:02d}:{mi:02d}"

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

    # Fetch the per-event JSON when listing data has no distances or no horario
    if (not distancias or not horario) and post_json_url:
        extra_dists, extra_horario = _fetch_event_json(post_json_url)
        if not distancias and extra_dists:
            distancias = extra_dists
        if not horario and extra_horario:
            horario = extra_horario
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
