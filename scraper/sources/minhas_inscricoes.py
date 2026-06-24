"""Scraper for minhasinscricoes.com.br — Brazilian race registration platform.

The calendar (/pt-br/calendario?url=<modality>) server-renders every event as a
<div class="thumbnail card-default"> card containing:

    .titulo-destaque               → event title
    <p><i.fa-calendar-alt> DD/MM/YYYY → event date
    <i.fa-map-marker> <span>City, UF</span> → location
    a[data-evento-key=<uuid>]      → redirect link to the event page

The card itself has no distances, so we follow the redirect (which serves the
full event page) and parse distances from the registration prose. The redirect
page also exposes the canonical event URL via og:url.

The calendar is split by modality (the "Tipo de Evento" filter). We scrape every
*running* modality (road, trail, ultra) — a road-running-only calendar misses
trail/ultra events entirely (e.g. the UAI Ultramaratona dos Anjos, a trail run).
Each modality is paginated: page 1 is the calendar page, pages 2..N come from the
AJAX `Calendario/Filtro` endpoint (identical card markup). We paginate until a
page returns no new events — never a fixed page cap (CLAUDE.md: check every
result a source returns).
"""
from __future__ import annotations
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from bs4 import BeautifulSoup

from ..http_client import get
from ..models import Corrida, Distancia, FonteInfo
from ..utils import normalize_date, normalize_time, normalize_titulo, now_iso, today_iso, extract_distances_from_text
from .. import geo as _geo

BASE = "https://minhasinscricoes.com.br"
CALENDARIO_URL = f"{BASE}/pt-br/calendario"
FILTRO_URL = f"{BASE}/pt-br/Calendario/Filtro"
SOURCE_NAME = "Minhas Inscrições"

# Running modalities on the platform's "Tipo de Evento" filter, addressed by the
# friendly ?url=<slug> shortcut (which pre-checks a single Tipo). Scraping per
# running modality means we only follow detail-page redirects for running events
# instead of every cycling/triathlon/swimming card. This is classification (which
# categories count as running), not event data — analogous to the inclusion
# keyword lists other sources use.
_RUNNING_MODALITIES = ("corrida-de-rua", "trail-run", "ultramaratona")

_CANONICAL = [(42.195, 41.5, 43.0), (21.097, 20.5, 21.5)]
# Drop hydration/abastecimento mentions that aren't race distances
_INTERVAL = re.compile(
    r"a cada \d+(?:[.,]\d+)?\s*km?\b|cada \d+(?:[.,]\d+)?\s*km?\b"
    r"|\d+(?:[.,]\d+)?\s*km?\s*(?:de hidrat|de água|de abastec)",
    re.IGNORECASE,
)


def _card_key(card) -> str:
    el = card.find(attrs={"data-evento-key": True})
    return el["data-evento-key"] if el else ""


def _iter_modality_cards(slug: str):
    """Yield every event card for one modality, across all calendar pages.

    Page 1 is the server-rendered calendar; pages 2..N come from the AJAX
    `Calendario/Filtro` fragment (same `.thumbnail.card-default` markup). Stops
    when a page contributes no new event keys — this terminates both on a truly
    empty page and on paginators that clamp an out-of-range page to the last one
    (so there is no fixed page cap, and no infinite loop either).
    """
    seen: set[str] = set()

    def _emit(cards):
        new = []
        for c in cards:
            key = _card_key(c)
            if key and key in seen:
                continue
            if key:
                seen.add(key)
            new.append(c)
        return new

    # Page 1 — the calendar page itself.
    try:
        resp = get(f"{CALENDARIO_URL}?url={slug}")
        resp.raise_for_status()
    except Exception as e:
        print(f"[{SOURCE_NAME}] erro ao buscar modalidade {slug}: {e}")
        return
    cards = BeautifulSoup(resp.text, "lxml").select(".thumbnail.card-default")
    new = _emit(cards)
    yield from new
    if not new:
        return

    # Pages 2..N — the Filtro fragment endpoint (GET works despite the form's
    # data-ajax-method="POST"; the page/filter state lives in the query string).
    hoje = date.today().strftime("%d/%m/%Y")
    pagina = 2
    while True:
        params = {
            "pagina": pagina,
            "Valor": "0,500",
            "PesquisaDataInicio": hoje,
            "PesquisaDataFim": "31/12/9999",
            "url": slug,
            "exclusivo": "False",
            "internacional": "False",
            "qtipos": "1",
        }
        try:
            resp = get(FILTRO_URL, params=params)
            resp.raise_for_status()
        except Exception as e:
            print(f"[{SOURCE_NAME}] erro na página {pagina} de {slug}: {e}")
            break
        cards = BeautifulSoup(resp.text, "lxml").select(".thumbnail.card-default")
        new = _emit(cards)
        if not new:
            break
        yield from new
        pagina += 1


def scrape() -> list[Corrida]:
    # Collect candidate cards across every running modality (network-light: a
    # handful of listing pages), deduped by key. Then fetch the per-event detail
    # pages — the expensive part, one request each — in parallel. Hundreds of
    # detail fetches done sequentially would dominate the run; the thread pool
    # keeps the whole source well inside the pipeline's per-source budget without
    # dropping any event (CLAUDE.md: large source → more parallelism, never caps).
    metas: list[dict] = []
    seen_keys: set[str] = set()
    for slug in _RUNNING_MODALITIES:
        count = 0
        for card in _iter_modality_cards(slug):
            # An event listed under several modalities (e.g. a trail ultra) is
            # fetched/parsed once — dedup by key before the detail-page fetch.
            key = _card_key(card)
            if key and key in seen_keys:
                continue
            if key:
                seen_keys.add(key)
            try:
                meta = _parse_card_meta(card)
            except Exception as e:
                print(f"[{SOURCE_NAME}] erro: {e}")
                continue
            if meta:
                metas.append(meta)
                count += 1
        print(f"[{SOURCE_NAME}] modalidade {slug}: {count} candidato(s)")

    print(f"[{SOURCE_NAME}] {len(metas)} candidato(s); buscando páginas de detalhe...")
    corridas: list[Corrida] = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = {ex.submit(_build_corrida, m): m for m in metas}
        for fut in as_completed(futures):
            try:
                corrida = fut.result()
                if corrida:
                    corridas.append(corrida)
            except Exception as e:
                print(f"[{SOURCE_NAME}] erro: {e}")

    print(f"[{SOURCE_NAME}] {len(corridas)} corridas encontradas")
    return corridas


def _parse_card_meta(card) -> dict | None:
    """Network-free parse of a calendar card → metadata dict, or None to skip.

    Everything cheap (title, date, location, redirect URL) is read here so the
    only per-event network call left is the detail-page fetch in _build_corrida,
    which runs in parallel.
    """
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
    localizacao, cidade, estado = _parse_location(cap)
    if not estado:
        return None

    # Redirect link via data-evento-key
    keycode = _card_key(card)
    redirect_url = (
        f"{BASE}/pt-br/ClickEventos/Redirecionar?origem=1&keycode={keycode}"
        if keycode else f"{CALENDARIO_URL}?url=corrida-de-rua"
    )
    return {
        "titulo": titulo, "data": data, "localizacao": localizacao,
        "cidade": cidade, "estado": estado, "keycode": keycode,
        "redirect_url": redirect_url,
    }


def _build_corrida(meta: dict) -> Corrida | None:
    """Fetch the event detail page and assemble a Corrida (runs in a worker)."""
    # Fetch the event page for distances, canonical URL, and start time
    link_evento, distancias, horario = _fetch_event_page(meta["redirect_url"])
    if not distancias:
        return None
    if horario is None:
        return None  # start time not yet published — skip until it is
    if not link_evento:
        link_evento = meta["redirect_url"]

    keycode, data, cidade = meta["keycode"], meta["data"], meta["cidade"]
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
        titulo=meta["titulo"],
        data_evento=data,
        horario=horario,
        localizacao=meta["localizacao"],
        cidade=cidade,
        estado=meta["estado"],
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


def _parse_location(cap) -> tuple[str, str, str]:
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
    return [Distancia(km=km, data=None, horario=None) for km in extract_distances_from_text(text, min_km=1.0, max_km=250.0)]
