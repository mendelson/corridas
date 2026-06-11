"""Scraper for contapassos.com.br — Brasília race registration platform.

Next.js App Router site. The home page is server-rendered with the full event
list embedded in the RSC payload (``self.__next_f.push`` chunks): the
``initialEventos`` array carries, per event, structured ``categorias``
(distances like "5KM"), ``dataEvento``, ``horarioLargada``, ``cidade``/
``estado`` (UF), card/banner image URLs, slug and status. No separate API
call is needed — everything comes from one GET on the home page.

Event detail pages live at /eventos/{slug}.
"""
from __future__ import annotations
import json
import re

from ..http_client import get
from ..models import Corrida, Distancia, FonteInfo
from ..utils import normalize_titulo, now_iso, today_iso

SOURCE_NAME = "Conta Passos"
BASE = "https://www.contapassos.com.br"

# RSC flight chunks: self.__next_f.push([1,"<js-string>"])
_PUSH_RE = re.compile(r'self\.__next_f\.push\(\[1,"((?:[^"\\]|\\.)*)"\]\)')

_KM_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*km", re.IGNORECASE)

# Categories that are not the running race itself (mirrors portal_das_corridas:
# only running distances become Distancia entries).
_NON_RUN_CAT_RE = re.compile(r"caminhada|kids|infantil|pcd", re.IGNORECASE)


def _extract_initial_eventos(html: str) -> list[dict]:
    """Decode the RSC flight chunks and brace-count the initialEventos array."""
    for m in _PUSH_RE.finditer(html):
        try:
            decoded = json.loads(f'"{m.group(1)}"')
        except ValueError:
            continue
        key = decoded.find('"initialEventos":')
        if key == -1:
            continue
        start = decoded.index("[", key)
        depth = 0
        for j in range(start, len(decoded)):
            ch = decoded[j]
            if ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
                if depth == 0:
                    return json.loads(decoded[start:j + 1])
    return []


def _parse_distancias(categorias: list[dict]) -> list[Distancia]:
    kms: list[float] = []
    for cat in categorias or []:
        nome = cat.get("nome") or ""
        if _NON_RUN_CAT_RE.search(nome):
            continue
        m = _KM_RE.search(cat.get("distancia") or "")
        if not m:
            continue
        km = float(m.group(1).replace(",", "."))
        if 1 <= km <= 250 and km not in kms:
            kms.append(km)
    return [Distancia(km=km, data=None, horario=None) for km in sorted(kms)]


def scrape() -> list[Corrida]:
    today = today_iso()
    try:
        resp = get(f"{BASE}/")
        resp.raise_for_status()
        eventos = _extract_initial_eventos(resp.text)
    except Exception as e:
        print(f"[{SOURCE_NAME}] erro ao buscar home: {e}")
        return []

    corridas: list[Corrida] = []
    for ev in eventos:
        try:
            corrida = _parse_event(ev, today)
            if corrida:
                corridas.append(corrida)
        except Exception as e:
            print(f"[{SOURCE_NAME}] erro ao parsear '{ev.get('titulo')}': {e}")

    print(f"[{SOURCE_NAME}] {len(corridas)} corridas encontradas")
    return corridas


def _parse_event(ev: dict, today: str) -> Corrida | None:
    titulo = normalize_titulo(ev.get("titulo") or "")
    if not titulo or len(titulo) < 3:
        return None

    data_evento = (ev.get("dataEvento") or "")[:10]
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", data_evento) or data_evento < today:
        return None

    distancias = _parse_distancias(ev.get("categorias") or [])
    if not distancias:
        print(f"[{SOURCE_NAME}] pulando '{titulo}' (sem distâncias de corrida)")
        return None

    horario = None
    m = re.fullmatch(r"(\d{1,2}):(\d{2})", (ev.get("horarioLargada") or "").strip())
    if m:
        horario = f"{int(m.group(1)):02d}:{m.group(2)}"

    cidade = (ev.get("cidade") or "").strip()
    estado = (ev.get("estado") or "").strip().upper()
    if len(estado) != 2 or not estado.isalpha():
        estado = ""

    slug = ev.get("slug") or ""
    link = f"{BASE}/eventos/{slug}" if slug else BASE

    status = (ev.get("status") or "").upper()
    if "ABERT" in status or status == "PRE_VENDA":
        inscricoes_abertas: bool | None = True
    elif "ENCERRAD" in status or "ESGOTAD" in status:
        inscricoes_abertas = False
    else:
        inscricoes_abertas = None

    now = now_iso()
    fonte = FonteInfo(
        nome=SOURCE_NAME,
        link_evento=link,
        links_inscricao=[link],
        tipo="inscricao",
    )

    return Corrida(
        id=f"contapassos_{ev['id']}",
        titulo=titulo,
        data_evento=data_evento,
        horario=horario,
        localizacao=f"{cidade}, {estado}" if cidade and estado else (cidade or estado),
        cidade=cidade,
        estado=estado,
        pais="BR",
        distancias=distancias,
        imagem_url=ev.get("cardImagemUrl") or ev.get("bannerImagemUrl") or None,
        inscricoes_abertas=inscricoes_abertas,
        periodo_inscricao=None,
        fontes=[fonte],
        miss_count=0,
        first_seen_at=now,
        updated_at=now,
    )
