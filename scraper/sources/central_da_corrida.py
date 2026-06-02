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

    raw_text = " ".join(filter(None, [
        titulo,
        event.get("regulamento"),
        event.get("descricao_evento"),
    ]))
    distancias = _extract_distances(raw_text, titulo_kw=titulo)

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


_CANON_KM: dict[int, float] = {21: 21.097, 42: 42.195}


def _fetch_distances_from_url(url: str) -> list[Distancia]:
    try:
        resp = get(url, source=SOURCE_NAME, timeout=15)
        resp.raise_for_status()
        page_text = re.sub(r"<[^>]+>", " ", resp.text)
        return _extract_distances(page_text)
    except Exception as e:
        print(f"[{SOURCE_NAME}] fetch externo falhou ({url[:60]}): {e}")
        return []


def _extract_distances(text: str, titulo_kw: str = "") -> list[Distancia]:
    # Strip Bubble rich-text markup
    text = re.sub(r"\[.*?\]", " ", text)
    # Strip age-restriction clauses ("percurso de 10 km até 30 km: 18 anos")
    text = _PERCURSO_RE.sub(" ", text)
    # Strip hydration/supply interval mentions ("a cada 2,5km")
    text = _INTERVAL_RE.sub(" ", text)

    seen: set[int] = set()
    result: list[Distancia] = []

    # Keyword recognition: only check the title so that "maratona" appearing in
    # race regulations or descriptions (e.g. "equivalent to a marathon effort")
    # does not incorrectly add 42.195 km to non-marathon events.
    kw_text = titulo_kw.lower() if titulo_kw else text.lower()
    if re.search(r'meia[\s-]?maratona|half[\s-]marathon', kw_text):
        seen.add(21)
        result.append(Distancia(km=21.097, data=None, horario=None))
    t_stripped = re.sub(r'meia[\s-]?maratona|half[\s-]marathon', '', kw_text)
    if re.search(r'\bmaratona\b|\bmarathon\b', t_stripped):
        seen.add(42)
        result.append(Distancia(km=42.195, data=None, horario=None))

    nums = re.findall(r"\b(\d+(?:[.,]\d+)?)\s*k(?:m)?\b", text, re.IGNORECASE)
    for n in nums:
        km = float(n.replace(",", "."))
        key = round(km)
        if key not in seen and 3 <= km <= 200:  # ≥3 km: exclude walks/kids/hydration noise
            seen.add(key)
            canonical = _CANON_KM.get(key, km)
            result.append(Distancia(km=canonical, data=None, horario=None))
    return result
