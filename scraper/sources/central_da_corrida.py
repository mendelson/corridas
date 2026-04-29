"""Scraper for centraldacorrida.com.br — Supabase edge-function API"""
from __future__ import annotations
import re
from datetime import datetime, timezone, timedelta

from ..http_client import get
from ..models import Corrida, Distancia, FonteInfo
from ..utils import (
    normalize_titulo, slugify, is_bsb_event, now_iso, today_iso,
)

BASE = "https://centraldacorrida.com.br"
API_URL = "https://tudmqbzxfbrjljpdpili.supabase.co/functions/v1/eventos-publicos"
SOURCE_NAME = "Central da Corrida"

BRT = timezone(timedelta(hours=-3))

_MARATONAS_ALVO = [
    "maratona de sao paulo", "maratona do rio", "maratona de porto alegre",
    "maratona de florianopolis", "maratona de curitiba", "maratona de belo horizonte",
    "maratona de fortaleza", "maratona de salvador", "maratona de recife",
    "maratona de manaus", "maratona caixa", "maratona de brasilia",
]

_CLOSED_KW = {"encerrad", "esgotad"}


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


def _parse_event(event: dict, today: str) -> Corrida | None:
    if event.get("Publicado") != "sim":
        return None

    titulo = normalize_titulo(event.get("Nome_evento") or "")
    if not titulo or len(titulo) < 3:
        return None

    estado = event.get("Estado") or "??"
    cidade = event.get("Cidade") or ""
    localizacao = f"{cidade}, {estado}" if cidade else estado

    titulo_lower = titulo.lower()
    is_target = (
        is_bsb_event(localizacao, titulo)
        or any(m in titulo_lower for m in _MARATONAS_ALVO)
    )
    if not is_target:
        return None

    data_evento, horario = _parse_datetime(event.get("Data_evento") or "")

    imagem_url = _parse_image(event.get("imagem"))

    slug = event.get("slug") or ""
    link_evento = f"{BASE}/evento/{slug}" if slug else BASE

    raw_text = " ".join(filter(None, [
        event.get("regulamento"),
        event.get("descricao_evento"),
    ]))
    distancias = _extract_distances(raw_text)

    inscricoes_abertas = _parse_inscricoes_abertas(event)

    now = now_iso()
    fonte = FonteInfo(
        nome=SOURCE_NAME,
        link_evento=link_evento,
        links_inscricao=[link_evento] if inscricoes_abertas else [],
        inscricoes=[],
    )

    return Corrida(
        id=f"{slugify(titulo)}_{estado.lower()}_{today}",
        titulo=titulo,
        data_evento=data_evento,
        horario=horario,
        localizacao=localizacao,
        cidade=cidade,
        estado=estado,
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
        return "https:" + raw
    return raw


def _parse_inscricoes_abertas(event: dict) -> bool | None:
    be = (event.get("bota_encerrado") or "").lower()
    if any(k in be for k in _CLOSED_KW):
        return False
    # yn_codigo_evento_encerrrado="sim" means restricted/not yet open to public
    if (event.get("yn_codigo_evento_encerrrado") or "").lower() == "sim":
        return False
    # Published events not definitively closed default to open ("Inscreva-se")
    return True


def _extract_distances(text: str) -> list[Distancia]:
    # Strip Bubble rich-text markup
    text = re.sub(r"\[.*?\]", " ", text)
    nums = re.findall(r"\b(\d+(?:[.,]\d+)?)\s*k(?:m)?\b", text, re.IGNORECASE)
    seen: set[float] = set()
    result: list[Distancia] = []
    for n in nums:
        km = float(n.replace(",", "."))
        if km not in seen and 1 <= km <= 200:
            seen.add(km)
            result.append(Distancia(km=km, data=None, horario=None))
    return result
