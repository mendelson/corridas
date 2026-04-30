"""Search photo platforms for published race photos."""
from __future__ import annotations

import re
import unicodedata

from bs4 import BeautifulSoup

from .http_client import get as http_get

# ---------------------------------------------------------------------------
# Text normalisation helpers
# ---------------------------------------------------------------------------

def _normalize(text: str) -> str:
    text = text.lower().strip()
    text = "".join(
        c for c in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(c)
    )
    text = re.sub(r"[^a-z0-9 ]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


_STOPWORDS = {
    "a", "o", "e", "de", "do", "da", "dos", "das", "em", "no", "na",
    "run", "corrida", "corridas", "maratona", "prova", "copa",
    "i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x",
}


def _title_match(query: str, candidate: str, threshold: float = 0.55) -> bool:
    qwords = set(_normalize(query).split()) - _STOPWORDS
    cwords = set(_normalize(candidate).split()) - _STOPWORDS
    if not qwords:
        return False
    return len(qwords & cwords) / len(qwords) >= threshold


# ---------------------------------------------------------------------------
# Foco Radical  (focoradical.com.br)
# ---------------------------------------------------------------------------

_FR_BASE = "https://www.focoradical.com.br"
_FR_PROVA_DATE_RE = re.compile(r"/prova/(\d{8})-")
_FR_FOTO_COUNT_RE = re.compile(r"(\d+)\s+fotos?", re.IGNORECASE)


def _search_focoradical(titulo: str, data_evento: str) -> str | None:
    """Return the Foco Radical event URL if photos are published, else None."""
    if not titulo or not data_evento:
        return None

    date_slug = data_evento.replace("-", "")          # YYYYMMDD
    terms = _normalize(titulo).replace(" ", "+")
    search_url = (
        f"{_FR_BASE}/site/index"
        f"?busca={terms}&esporte=corridas&per-page=20"
    )

    try:
        resp = http_get(search_url, timeout=15)
        if resp.status_code != 200:
            return None

        soup = BeautifulSoup(resp.text, "lxml")

        for a in soup.find_all("a", href=_FR_PROVA_DATE_RE):
            href: str = a.get("href", "")
            m = _FR_PROVA_DATE_RE.search(href)
            if not m or m.group(1) != date_slug:
                continue

            # Extract title candidates for fuzzy matching
            link_text = a.get_text(strip=True)
            parent_text = (
                a.parent.get_text(separator=" ", strip=True) if a.parent else ""
            )
            # Slug body: strip leading YYYYMMDD- and trailing -ID
            slug_raw = href.split("/prova/", 1)[-1]
            slug_body = re.sub(r"^\d{8}-", "", slug_raw)
            slug_body = re.sub(r"-\d+$", "", slug_body).replace("-", " ")

            if not any(
                _title_match(titulo, candidate)
                for candidate in (link_text, parent_text, slug_body)
                if candidate
            ):
                continue

            # Confirm photos are published
            prova_url = f"{_FR_BASE}{href}"
            if _focoradical_has_photos(prova_url):
                return prova_url

    except Exception as exc:
        print(f"[fotos] focoradical search error: {exc}")

    return None


def _focoradical_has_photos(url: str) -> bool:
    try:
        resp = http_get(url, timeout=15)
        if resp.status_code != 200:
            return False
        m = _FR_FOTO_COUNT_RE.search(resp.text)
        return bool(m and int(m.group(1)) > 0)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def find_event_photos(corrida: dict) -> list[dict]:
    """Search all photo platforms for a past event.

    Returns a list of ``{"plataforma": str, "url": str}`` dicts for each
    platform that has photos published for this event.
    """
    titulo = corrida.get("titulo", "")
    data_evento = corrida.get("data_evento", "")

    results: list[dict] = []

    url = _search_focoradical(titulo, data_evento)
    if url:
        results.append({"plataforma": "Foco Radical", "url": url})

    return results
