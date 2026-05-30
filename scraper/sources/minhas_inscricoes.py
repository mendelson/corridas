"""Scraper for minhasinscricoes.com.br — Brazilian race registration platform.

The calendar page (/pt-br/calendario?url=corrida-de-rua) server-renders every
event as a <div class="thumbnail card-default"> card containing:

    .titulo-destaque               → event title
    <p><i.fa-calendar-alt> DD/MM/YYYY → event date
    <i.fa-map-marker> <span>City, UF</span> → location
    a[data-evento-key=<uuid>]      → redirect link to the event page

The card itself has no distances, so we follow the redirect (which serves the
full event page) and parse distances from the registration prose. The redirect
page also exposes the canonical event URL via og:url.
"""
from __future__ import annotations
import re
from bs4 import BeautifulSoup

from ..http_client import get
from ..models import Corrida, Distancia, FonteInfo
from ..utils import normalize_date, normalize_time, normalize_titulo, now_iso, today_iso
from .. import geo as _geo

URL = "https://minhasinscricoes.com.br/pt-br/calendario?url=corrida-de-rua"
BASE = "https://minhasinscricoes.com.br"
SOURCE_NAME = "Minhas Inscrições"

_CANONICAL = [(42.195, 41.5, 43.0), (21.097, 20.5, 21.5)]
# Drop hydration/abastecimento mentions that aren't race distances
_INTERVAL = re.compile(
    r"a cada \d+(?:[.,]\d+)?\s*km?\b|cada \d+(?:[.,]\d+)?\s*km?\b"
    r"|\d+(?:[.,]\d+)?\s*km?\s*(?:de hidrat|de água|de abastec)",
    re.IGNORECASE,
)


def scrape() -> list[Corrida]:
    try:
        resp = get(URL)
        resp.raise_for_status()
    except Exception as e:
        print(f"[{SOURCE_NAME}] erro ao buscar {URL}: {e}")
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    cards = soup.select(".thumbnail.card-default")
    print(f"[{SOURCE_NAME}] {len(cards)} cards no calendário")

    corridas: list[Corrida] = []
    for card in cards:
        try:
            corrida = _parse_card(card)
            if corrida:
                corridas.append(corrida)
        except Exception as e:
            print(f"[{SOURCE_NAME}] erro: {e}")

    print(f"[{SOURCE_NAME}] {len(corridas)} corridas encontradas")
    return corridas


def _parse_card(card) -> Corrida | None:
    cap = card.select_one(".caption-evento")
    if not cap:
        return None

    titulo_el = cap.select_one(".titulo-destaque")
    titulo = normalize_titulo(titulo_el.get_text(strip=True) if titulo_el else "")
    if not titulo or len(titulo) < 3:
        return None

    text = cap.get_text(" ", strip=True)

    # Date: DD/MM/YYYY
    m = re.search(r"\b(\d{1,2}/\d{1,2}/\d{4})\b", text)
    data = normalize_date(m.group(1)) if m else None
    if not data or data < today_iso():
        return None

    # Location: <span> after the map-marker icon → "City, UF"
    localizacao, cidade, estado = _parse_location(cap, titulo)
    if not estado:
        return None

    # Redirect link via data-evento-key
    key_el = card.find(attrs={"data-evento-key": True})
    keycode = key_el["data-evento-key"] if key_el else ""
    redirect_url = (
        f"{BASE}/pt-br/ClickEventos/Redirecionar?origem=1&keycode={keycode}"
        if keycode else URL
    )

    # Fetch the event page for distances, canonical URL, and start time
    link_evento, distancias, horario = _fetch_event_page(redirect_url)
    if not distancias:
        return None
    if not link_evento:
        link_evento = redirect_url
    if horario is None:
        return None  # start time not yet published — skip until it is

    ev_id = f"mi_{keycode}" if keycode else f"mi_{data}_{cidade.lower().replace(' ', '')}"

    now = now_iso()
    fonte = FonteInfo(
        nome=SOURCE_NAME,
        link_evento=link_evento,
        links_inscricao=[link_evento],
        tipo="inscricao",
    )
    return Corrida(
        id=ev_id,
        titulo=titulo,
        data_evento=data,
        horario=horario,
        localizacao=localizacao,
        cidade=cidade,
        estado=estado,
        pais="BR",
        distancias=distancias,
        imagem_url=None,
        inscricoes_abertas=None,
        periodo_inscricao=None,
        fontes=[fonte],
        miss_count=0,
        first_seen_at=now,
        updated_at=now,
    )


def _parse_location(cap, titulo: str) -> tuple[str, str, str]:
    """Extract (localizacao, cidade, estado) from 'City, UF' span."""
    raw = ""
    marker = cap.find("i", class_=re.compile("map-marker"))
    if marker:
        span = marker.find_next("span")
        if span:
            raw = span.get_text(" ", strip=True)
    if not raw:
        m = re.search(r"([A-ZÁÉÍÓÚ][\wÀ-ÿ\s.]+?),\s*([A-Z]{2})\b", cap.get_text(" ", strip=True))
        if m:
            raw = m.group(0)

    estado = ""
    cidade = raw
    m = re.search(r"^(.*?),\s*([A-Z]{2})\b", raw)
    if m:
        cidade = m.group(1).strip()
        estado = m.group(2)
    if not estado:
        _pais_geo, _estado_geo = _geo.resolve(raw or cidade, cidade, "BR")
        estado = _estado_geo or ""
    localizacao = f"{cidade}, {estado}" if estado else cidade
    return localizacao, cidade, estado


def _fetch_event_page(url: str) -> tuple[str, list[Distancia], str | None]:
    """Fetch the event page; return (canonical_url, distancias, horario)."""
    try:
        resp = get(url)
        resp.raise_for_status()
    except Exception as e:
        print(f"[{SOURCE_NAME}] erro ao buscar evento {url}: {e}")
        return "", [], None

    soup = BeautifulSoup(resp.text, "lxml")

    canonical = ""
    og = soup.find("meta", property="og:url")
    if og and og.get("content"):
        canonical = og["content"]

    # Distances and start time from the full page text
    text = soup.get_text(" ", strip=True)
    distancias = _extract_distances(text)
    horario = normalize_time(text)
    return canonical, distancias, horario


def _extract_distances(text: str) -> list[Distancia]:
    text = _INTERVAL.sub(" ", text)
    seen: set[float] = set()
    result: list[Distancia] = []
    for raw in re.findall(r"\b(\d+(?:[.,]\d+)?)\s*[kK][mM]\b", text):
        try:
            km = float(raw.replace(",", "."))
        except ValueError:
            continue
        if not (1 <= km <= 250):
            continue
        for canon, lo, hi in _CANONICAL:
            if lo <= km <= hi:
                km = canon
                break
        if km not in seen:
            seen.add(km)
            result.append(Distancia(km=km, data=None, horario=None))
    return sorted(result, key=lambda d: float(d.km))
