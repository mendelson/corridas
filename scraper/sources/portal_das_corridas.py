"""Scraper for portaldascorridas.com.br

Wix Events site. The hub has no public REST API, but every event has a
dedicated `/event-details/<slug>` page that embeds a full `schema.org/Event`
JSON-LD block plus a Wix `fullAddress` blob and a registration-form
`Percurso` (route) field with the canonical distance options.

Discovery pipeline:
  1. Fetch `event-pages-sitemap.xml` → ~570 event URLs with `lastmod`
  2. Drop URLs whose `lastmod` is older than ~9 months (very likely past
     events that have not been touched since)
  3. Cap the per-run fetch list to keep proxy budget bounded
  4. Fetch each detail page; parse JSON-LD for date/title/image, Wix blob
     for city/state, and "Percurso" form options for distances
  5. Drop events whose race date is already past

The previous scraper used Playwright with generic CSS selectors (.event /
.race / article) that never matched the Wix DOM — same false-positive
"broken" pattern as bora_correr and brasil_que_corre.
"""
from __future__ import annotations
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta

from ..http_client import get
from ..models import Corrida, Distancia, FonteInfo
from ..utils import normalize_titulo, now_iso, today_iso

SOURCE_NAME = "Portal das Corridas"
SITE_BASE   = "https://www.portaldascorridas.com.br"
SITEMAP_URL = f"{SITE_BASE}/event-pages-sitemap.xml"

# Tunables — keep proxy budget bounded.
_LASTMOD_LOOKBACK_DAYS = 270   # ~9 months
_MAX_EVENTS_PER_RUN    = 120
_FETCH_WORKERS         = 6

_CANONICAL = [(42.195, 41.5, 43.0), (21.097, 20.5, 21.5)]

_JSONLD_RE   = re.compile(
    r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.DOTALL,
)
_EVENTID_RE  = re.compile(r'"eventId":"([0-9a-f-]{36})"')
_PERCURSO_RE = re.compile(r'"label":"Percurso","options":\[([^\]]+)\]')
# Broader: any form options block whose label contains distance-related keywords
_FORM_OPTS_RE = re.compile(
    r'"label":"([^"]*(?:percurso|categoria|distanci|modalid)[^"]*)"'
    r'[^]]*"options":\[([^\]]+)\]',
    re.IGNORECASE,
)
_KM_RE       = re.compile(r"(\d+(?:[.,]\d+)?)\s*KM", re.IGNORECASE)
# km pattern for general text fallback
_KM_TEXT_RE  = re.compile(r"\b(\d+(?:[.,]\d+)?)\s*k(?:m)?\b", re.IGNORECASE)


def scrape() -> list[Corrida]:
    urls = _list_recent_event_urls()
    if not urls:
        print(f"[{SOURCE_NAME}] nenhuma URL de evento candidata")
        return []
    print(f"[{SOURCE_NAME}] {len(urls)} páginas para inspecionar")

    today = today_iso()
    now   = now_iso()

    corridas: list[Corrida] = []
    seen_ids: set[str] = set()

    with ThreadPoolExecutor(max_workers=_FETCH_WORKERS) as ex:
        futures = {ex.submit(_fetch_event, url, today, now): url for url in urls}
        for fut in as_completed(futures):
            url = futures[fut]
            try:
                c = fut.result()
            except Exception as e:
                print(f"[{SOURCE_NAME}] erro em {url}: {e}")
                continue
            if c and c.id not in seen_ids:
                seen_ids.add(c.id)
                corridas.append(c)

    print(f"[{SOURCE_NAME}] {len(corridas)} corridas encontradas")
    return corridas


def _list_recent_event_urls() -> list[str]:
    try:
        resp = get(SITEMAP_URL)
        resp.raise_for_status()
    except Exception as e:
        print(f"[{SOURCE_NAME}] erro ao buscar sitemap: {e}")
        return []

    entries: list[tuple[str, str]] = re.findall(
        r"<loc>([^<]+)</loc>\s*<lastmod>([^<]+)</lastmod>", resp.text
    )
    cutoff = (date.today() - timedelta(days=_LASTMOD_LOOKBACK_DAYS)).isoformat()
    recent = [(u, lm) for (u, lm) in entries if lm[:10] >= cutoff]
    recent.sort(key=lambda p: p[1], reverse=True)
    return [u for (u, _) in recent[:_MAX_EVENTS_PER_RUN]]


def _fetch_event(url: str, today: str, now: str) -> Corrida | None:
    try:
        resp = get(url)
        resp.raise_for_status()
    except Exception:
        return None
    return _parse_event(resp.text, url, today, now)


def _parse_event(html: str, url: str, today: str, now: str) -> Corrida | None:
    ld = _extract_jsonld_event(html)
    if not ld:
        return None

    start_iso = ld.get("startDate") or ""
    if not start_iso or len(start_iso) < 10:
        return None
    data_evento = start_iso[:10]
    if data_evento < today:
        return None

    titulo = normalize_titulo(ld.get("name") or "")
    if not titulo or len(titulo) < 3:
        return None

    raw_time = start_iso[11:16] if len(start_iso) >= 16 and start_iso[10] == "T" else None
    horario = raw_time if (raw_time and int(raw_time[:2]) >= 4) else None
    if not horario:
        return None
    image   = (ld.get("image") or {}).get("url") if isinstance(ld.get("image"), dict) else None

    pais, estado, cidade = _extract_location(html, ld)
    localizacao = ", ".join(p for p in [cidade, estado] if p) or (ld.get("location") or {}).get("address", "")

    distancias = _extract_distances(html, titulo)
    if not distancias:
        print(f"[{SOURCE_NAME}] sem distâncias, pulando: {titulo!r}")
        return None

    eid_m = _EVENTID_RE.search(html)
    stable_id = f"portaldc_{eid_m.group(1)}" if eid_m else f"portaldc_{url.rsplit('/', 1)[-1]}"

    return Corrida(
        id=stable_id,
        titulo=titulo,
        data_evento=data_evento,
        horario=horario,
        localizacao=localizacao,
        cidade=cidade or "",
        estado=estado or "",
        pais=pais or "BR",
        distancias=distancias,
        imagem_url=image,
        inscricoes_abertas=None,
        periodo_inscricao=None,
        fontes=[FonteInfo(
            nome=SOURCE_NAME,
            link_evento=url,
            links_inscricao=[url],
            tipo="inscricao",
        )],
        miss_count=0,
        first_seen_at=now,
        updated_at=now,
    )


def _extract_jsonld_event(html: str) -> dict | None:
    for body in _JSONLD_RE.findall(html):
        try:
            obj = json.loads(body)
        except Exception:
            continue
        if isinstance(obj, list):
            for item in obj:
                if isinstance(item, dict) and item.get("@type") == "Event":
                    return item
        elif isinstance(obj, dict) and obj.get("@type") == "Event":
            return obj
    return None


def _extract_location(html: str, ld: dict) -> tuple[str, str, str]:
    """Prefer Wix fullAddress (structured) over JSON-LD location (freeform)."""
    idx = html.find('"fullAddress"')
    if idx != -1:
        window = html[idx: idx + 2000]
        cm = re.search(r'"country"\s*:\s*"([A-Z]{2})"', window)
        sm = re.search(r'"subdivision"\s*:\s*"([A-Z]{2,6})"', window)
        ci = re.search(r'"city"\s*:\s*"([^"]{1,80})"', window)
        if cm and ci:
            return cm.group(1), sm.group(1) if sm else "", ci.group(1)
    # Fallback to JSON-LD's freeform address — country defaults to BR.
    loc = ld.get("location") or {}
    addr = loc.get("address") if isinstance(loc, dict) else ""
    if isinstance(addr, str) and addr:
        parts = [p.strip() for p in re.split(r"[,\-]", addr) if p.strip()]
        cidade = parts[0] if parts else ""
        estado = parts[-1] if len(parts) > 1 and len(parts[-1]) == 2 else ""
        return "BR", estado, cidade
    return "BR", "", ""


def _extract_distances(html: str, titulo: str = "") -> list[Distancia]:
    """Use the registration form's Percurso options, broader form fields, then title."""
    seen: list[float] = []

    def _add_km(raw: float) -> None:
        km = raw
        for canon, lo, hi in _CANONICAL:
            if lo <= raw <= hi:
                km = canon
                break
        if 1 <= km <= 200 and not any(abs(km - s) < 0.5 for s in seen):
            seen.append(km)

    def _scan_options(options_str: str) -> None:
        for opt in re.findall(r'"([^"]+)"', options_str):
            for km_match in _KM_RE.finditer(opt):
                try:
                    _add_km(float(km_match.group(1).replace(",", ".")))
                except ValueError:
                    pass

    # 1. Exact "Percurso" form label
    m = _PERCURSO_RE.search(html)
    if m:
        _scan_options(m.group(1))

    # 2. Broader form labels (Categoria, Distância, Modalidade, etc.)
    if not seen:
        for fm in _FORM_OPTS_RE.finditer(html):
            _scan_options(fm.group(2))

    # 3. Title keyword extraction (meia maratona, marathon, Xkm)
    if not seen and titulo:
        tl = titulo.lower()
        if re.search(r'meia[\s-]?maratona|half[\s-]?marathon', tl):
            _add_km(21.097)
        t_stripped = re.sub(r'meia[\s-]?maratona|half[\s-]?marathon', '', tl)
        if re.search(r'\bmaratona\b|\bmarathon\b', t_stripped):
            _add_km(42.195)
        for nm in re.findall(r'\b(\d+(?:[.,]\d+)?)\s*k(?:m)?\b', tl):
            try:
                _add_km(float(nm.replace(',', '.')))
            except ValueError:
                pass

    # 4. Scan page text for km values as last resort (noise-prone, use only when nothing else worked)
    if not seen:
        stripped = re.sub(r'<[^>]+>', ' ', html)
        for nm in _KM_TEXT_RE.findall(stripped):
            try:
                _add_km(float(nm.replace(',', '.')))
            except ValueError:
                pass

    return sorted(
        [Distancia(km=k, data=None, horario=None) for k in seen],
        key=lambda d: float(d.km),
    )
