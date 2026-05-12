"""Scraper for brasilcorrida.com.br — AngularJS app backed by REST API."""
from __future__ import annotations
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

from ..http_client import get
from ..models import Corrida, Distancia, FonteInfo, PeriodoInscricao
from ..utils import normalize_titulo, slugify, now_iso, today_iso

API_BASE = "https://brasilcorrida.com.br/api/src/Site"
CARD_URL = f"{API_BASE}/EventosCard.php"
DETAIL_URL = f"{API_BASE}/EventoDetalhe.php"
EVENT_BASE = "https://brasilcorrida.com.br/#/evento"
INSC_BASE = "https://brasilcorrida.com.br/#/inscricao"
S3_BASE = "https://midia.recebedigital.com.br/"
SOURCE_NAME = "Brasil Corrida"

_RUNNING_MODS = {477, 478, 479, 480, 481, 482, 489}  # corrida de rua + kids variants
_RUNNING_MOD_NAMES = {"corrida de rua", "corrida de montanha", "trail running",
                      "corrida kids", "corrida", "corrida de revezamento"}

_CANONICAL = [(42.195, 41.5, 43.0), (21.097, 20.5, 21.5)]


def scrape() -> list[Corrida]:
    today = today_iso()
    try:
        resp = get(CARD_URL)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"[{SOURCE_NAME}] erro ao buscar API: {e}")
        return []

    events = data.get("calendario") or []
    if not events:
        print(f"[{SOURCE_NAME}] nenhum evento no calendario")
        return []

    # Filter to running events only, deduplicate by eve_id
    seen_ids: set[int] = set()
    to_fetch: list[dict] = []
    for ev in events:
        eid = ev.get("eve_id")
        if eid in seen_ids:
            continue
        mod_name = (ev.get("mod_descricao") or "").lower()
        mod_id = ev.get("eve_mod_id")
        if mod_name in _RUNNING_MOD_NAMES or mod_id in _RUNNING_MODS:
            seen_ids.add(eid)
            to_fetch.append(ev)

    corridas: list[Corrida] = []
    with ThreadPoolExecutor(max_workers=6) as ex:
        futures = {ex.submit(_fetch_and_parse, ev, today): ev for ev in to_fetch}
        for fut in as_completed(futures):
            try:
                c = fut.result()
                if c:
                    corridas.append(c)
            except Exception as e:
                ev = futures[fut]
                print(f"[{SOURCE_NAME}] erro '{ev.get('eve_nome')}': {e}")

    print(f"[{SOURCE_NAME}] {len(corridas)} corridas encontradas")
    return corridas


def _fetch_and_parse(ev_card: dict, today: str) -> Corrida | None:
    token = ev_card.get("eve_token", "")
    if not token:
        return None

    try:
        resp = get(f"{DETAIL_URL}?eventoToken={token}")
        resp.raise_for_status()
        ev = resp.json()
    except Exception:
        ev = ev_card  # fall back to card data

    titulo = normalize_titulo(ev.get("eve_nome") or ev_card.get("eve_nome") or "")
    if not titulo or len(titulo) < 3:
        return None

    data_evento = (ev.get("eve_data_evento") or "")[:10]
    if not data_evento or data_evento < today:
        return None

    hora_raw = ev.get("eve_hora_largada") or ""
    horario = hora_raw[:5] if hora_raw else None

    cidade_raw = (ev.get("cid_descricao") or ev_card.get("cid_descricao") or "").title()
    estado = (ev.get("eve_end_uf") or ev_card.get("eve_end_uf") or "??").upper()
    localizacao = f"{cidade_raw}, {estado}" if cidade_raw else estado

    distancias = _parse_distances(ev.get("distancias") or [])

    img_path = ev.get("eve_img_destaque") or ev_card.get("eve_img_destaque")
    imagem_url = (S3_BASE + img_path) if img_path else None

    insc_ini = ev.get("eve_data_insc_ini")
    insc_fim = ev.get("eve_data_insc_fim")
    periodo = PeriodoInscricao(abertura=insc_ini, encerramento=insc_fim) if (insc_ini or insc_fim) else None

    link_evento = f"{EVENT_BASE}/{token}"
    links_inscricao = [link_evento]

    now = now_iso()
    fonte = FonteInfo(
        nome=SOURCE_NAME,
        link_evento=link_evento,
        links_inscricao=links_inscricao,
    )

    return Corrida(
        id=f"brasilcorrida_{ev.get('eve_id') or slugify(titulo)}",
        titulo=titulo,
        data_evento=data_evento,
        horario=horario,
        localizacao=localizacao,
        cidade=cidade_raw,
        estado=estado,
        pais="BR",
        distancias=distancias,
        imagem_url=imagem_url,
        inscricoes_abertas=None,
        periodo_inscricao=periodo,
        fontes=[fonte],
        miss_count=0,
        first_seen_at=now,
        updated_at=now,
    )


def _parse_distances(raw: list[dict]) -> list[Distancia]:
    seen: set[float] = set()
    result: list[Distancia] = []
    for item in raw:
        try:
            km = float(str(item.get("edt_distancia") or 0).replace(",", "."))
        except (ValueError, TypeError):
            continue
        for canon, lo, hi in _CANONICAL:
            if lo <= km <= hi:
                km = canon
                break
        if km not in seen and 3 <= km <= 200:
            seen.add(km)
            result.append(Distancia(km=km, data=None, horario=None))
    return sorted(result, key=lambda d: d.km)
