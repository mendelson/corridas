"""Scraper for tfsports.com.br — uses Strapi CMS API (painel-website.tfsports.com.br)."""
from __future__ import annotations
import json
import re
import unicodedata
import httpx
from bs4 import BeautifulSoup

from ..models import Corrida, Distancia, FonteInfo
from ..utils import normalize_titulo, slugify, infer_estado, now_iso, today_iso

BASE = "https://www.tfsports.com.br"
API_BASE = "https://painel-website.tfsports.com.br/api"
LIST_URL = (
    f"{API_BASE}/run-series"
    "?publicationState=live"
    "&populate[eventData]=*"
    "&populate[pageSeo][populate]=*"
    "&pagination[pageSize]=100"
)
SOURCE_NAME = "TF Sports"

_TIMEOUT = 30
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
_HEADERS_HTML = {
    "User-Agent": _UA,
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.7",
}

_BR_STATES = {
    "AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA",
    "MG", "MS", "MT", "PA", "PB", "PE", "PI", "PR", "RJ", "RN",
    "RO", "RR", "RS", "SC", "SE", "SP", "TO",
}


# ---------------------------------------------------------------------------
# Token extraction
# ---------------------------------------------------------------------------

def _get_bearer_token() -> str | None:
    """Extract Bearer token from the compiled Next.js app bundle.

    Next.js minifies the Authorization header as:
      "Bearer ".concat("TOKEN...") — so we need patterns for that form.
    """
    try:
        resp = httpx.get(
            f"{BASE}/run-series/",
            headers=_HEADERS_HTML,
            timeout=_TIMEOUT,
            follow_redirects=True,
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        for script in soup.find_all("script", src=True):
            src = script.get("src", "")
            if "_app" not in src or not src.endswith(".js"):
                continue
            bundle_url = src if src.startswith("http") else f"{BASE}{src}"
            bundle = httpx.get(
                bundle_url, headers=_HEADERS_HTML, timeout=_TIMEOUT, follow_redirects=True
            )
            bundle.raise_for_status()
            text = bundle.text
            for pat in [
                # "Bearer ".concat("TOKEN") — typical Next.js minified bundle pattern
                r'"Bearer\s+"\s*\.\s*concat\s*\(\s*"([^"]{20,})"',
                # Simpler concat form without spaces
                r'concat\s*\(\s*"([a-f0-9]{40,})"',
                # Plain "Bearer TOKEN" in a single string
                r'"Bearer\s+([\w\-_]{20,})"',
                # JWT (ey... prefix)
                r'"(ey[\w\-_.]{20,})"',
            ]:
                m = re.search(pat, text)
                if m:
                    return m.group(1)
    except Exception as e:
        print(f"[{SOURCE_NAME}] erro ao extrair token: {e}")
    return None


# ---------------------------------------------------------------------------
# Location parsing
# ---------------------------------------------------------------------------

def _strip_symbols(text: str) -> str:
    """Remove emoji and Symbol-Other characters."""
    return "".join(c for c in text if not unicodedata.category(c).startswith("So")).strip()


def _parse_location(location: str | None) -> tuple[str, str]:
    """
    Parse (city, state) from strings like:
      '📍 Rua X, 123 - Bairro, São Paulo - SP, 04543-011'
    Splits on comma, looks for 'Cidade - UF' from the end.
    """
    if not location:
        return "", "??"
    clean = _strip_symbols(location)
    parts = [p.strip() for p in clean.split(",")]
    for part in reversed(parts):
        m = re.match(r"^([A-ZÀ-Ü][A-Za-zÀ-ÿ .]+?)\s*[-–]\s*([A-Z]{2})$", part.strip())
        if m and m.group(2) in _BR_STATES:
            return m.group(1).strip(), m.group(2).strip()
    return clean[:60], "??"


# ---------------------------------------------------------------------------
# Distance extraction
# ---------------------------------------------------------------------------

def _km_from_val(val) -> float | None:
    if isinstance(val, (int, float)):
        km = float(val)
    elif isinstance(val, str):
        try:
            km = float(val.replace(",", ".").strip().rstrip("k").rstrip("m"))
        except ValueError:
            return None
    else:
        return None
    return km if 3 <= km <= 100 else None


def _distances_from_api(attrs: dict) -> list[Distancia]:
    """Look for distance data in the Strapi API response."""
    for key in ("distances", "modalities", "categories", "distancias"):
        raw = attrs.get(key)
        if not isinstance(raw, list):
            ed = attrs.get("eventData") or {}
            raw = ed.get(key)
        if isinstance(raw, list) and raw:
            seen: set[float] = set()
            result: list[Distancia] = []
            for item in raw:
                km_raw = None
                if isinstance(item, dict):
                    km_raw = (
                        item.get("km") or item.get("distance")
                        or item.get("value") or item.get("distancia")
                    )
                else:
                    km_raw = item
                km = _km_from_val(km_raw)
                if km and km not in seen:
                    seen.add(km)
                    result.append(Distancia(km=km, data=None, horario=None))
            if result:
                return result
    return []


def _distances_from_next_data(slug: str) -> list[Distancia]:
    """Try to extract distances from __NEXT_DATA__ on the event detail page."""
    try:
        resp = httpx.get(
            f"{BASE}/run-series/{slug}",
            headers=_HEADERS_HTML,
            timeout=_TIMEOUT,
            follow_redirects=True,
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        tag = soup.find("script", id="__NEXT_DATA__")
        if not tag or not tag.string:
            return []
        data = json.loads(tag.string)
        # Search entire JSON dump for "km" keys
        text = json.dumps(data)
        nums = re.findall(r'"km"\s*:\s*(\d+(?:\.\d+)?)', text)
        seen: set[float] = set()
        result: list[Distancia] = []
        for n in nums:
            km = float(n)
            if km not in seen and 3 <= km <= 100:
                seen.add(km)
                result.append(Distancia(km=km, data=None, horario=None))
        return result
    except Exception:
        return []


def _distances_from_title(titulo: str) -> list[Distancia]:
    nums = re.findall(r"\b(\d+(?:[.,]\d+)?)\s*[kK][mM]?\b", titulo)
    seen: set[float] = set()
    result: list[Distancia] = []
    for n in nums:
        km = float(n.replace(",", "."))
        if km not in seen and 3 <= km <= 100:
            seen.add(km)
            result.append(Distancia(km=km, data=None, horario=None))
    return result


_TF_DEFAULT_DISTANCES = [
    Distancia(km=5.0, data=None, horario=None),
    Distancia(km=10.0, data=None, horario=None),
]


def _get_distances(attrs: dict, slug: str) -> list[Distancia]:
    d = _distances_from_api(attrs)
    if d:
        return d
    d = _distances_from_next_data(slug)
    if d:
        return d
    d = _distances_from_title(attrs.get("title", ""))
    if d:
        return d
    # Track&Field Run Series is a standardized circuit — always 5km and 10km
    return _TF_DEFAULT_DISTANCES


# ---------------------------------------------------------------------------
# Image extraction
# ---------------------------------------------------------------------------

def _extract_image(attrs: dict) -> str | None:
    """Extract image URL from pageSeo.metaImage (Strapi media format)."""
    seo = attrs.get("pageSeo") or {}
    img_data = seo.get("metaImage", {})
    if isinstance(img_data, dict):
        inner = img_data.get("data", {})
        if inner:
            img_attrs = inner.get("attributes", {})
            # Prefer small format (700px), fallback to original
            small = img_attrs.get("formats", {}).get("small", {}).get("url")
            return small or img_attrs.get("url")
    return None


# ---------------------------------------------------------------------------
# Main scraper
# ---------------------------------------------------------------------------

def scrape() -> list[Corrida]:
    token = _get_bearer_token()
    if not token:
        print(f"[{SOURCE_NAME}] token não encontrado, tentando sem autenticação")

    api_headers = {
        "User-Agent": _UA,
        "Accept": "application/json",
    }
    if token:
        api_headers["Authorization"] = f"Bearer {token}"

    try:
        resp = httpx.get(LIST_URL, headers=api_headers, timeout=_TIMEOUT, follow_redirects=True)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"[{SOURCE_NAME}] erro ao buscar API: {e}")
        return []

    events = data.get("data", [])
    now = now_iso()
    today = today_iso()
    corridas: list[Corrida] = []

    for event in events:
        try:
            attrs = event.get("attributes", {})
            titulo = normalize_titulo(attrs.get("title", ""))
            if not titulo or len(titulo) < 3:
                continue
            slug = attrs.get("slug", "")
            ed = attrs.get("eventData") or {}

            data_evento = ed.get("startDate") or ""
            location_raw = ed.get("location") or ""
            is_closed = ed.get("isSubscriptionClosed")

            city, state = _parse_location(location_raw)
            if state == "??":
                inferred = infer_estado(location_raw + " " + titulo)
                state = inferred or "??"

            localizacao = f"{city}, {state}" if city else state

            distancias = _get_distances(attrs, slug)
            imagem_url = _extract_image(attrs)

            link_evento = f"{BASE}/run-series/{slug}"
            inscricoes_abertas = None if is_closed is None else (not is_closed)
            links_insc = [link_evento]

            fonte = FonteInfo(
                nome=SOURCE_NAME,
                link_evento=link_evento,
                links_inscricao=links_insc,
            )
            corridas.append(Corrida(
                id=f"{slugify(titulo)}_{state.lower()}_{today}",
                titulo=titulo,
                data_evento=data_evento,
                horario=None,
                localizacao=localizacao,
                cidade=city,
                estado=state,
                distancias=distancias,
                imagem_url=imagem_url,
                inscricoes_abertas=inscricoes_abertas,
                periodo_inscricao=None,
                fontes=[fonte],
                miss_count=0,
                first_seen_at=now,
                updated_at=now,
            ))
        except Exception as e:
            print(f"[{SOURCE_NAME}] erro ao processar '{attrs.get('title', '?')}': {e}")

    print(f"[{SOURCE_NAME}] {len(corridas)} corridas encontradas")
    return corridas
