"""Search photo platforms for published race photos.

Platforms implemented (requests + BeautifulSoup only, no Playwright):
  - Foco Radical  (focoradical.com.br)  — search via busca= parameter
  - Fotop         (fotop.com.br)         — parse /?cat=1 event listing
  - FinisherPix   (finisherpix.com)      — filter[query] search API
  - CorrepraFoto  (correprafoto.com.br)  — parse /categorias.aspx?cat=1

Platforms requiring Playwright (not implemented):
  - Sportograf, Fotto (full SPA, server returns empty shell)

Platforms unreachable from non-Brazilian IPs (connection refused):
  - Woosat, Doublefocus, Onphoto, ProPhoto Run, Speed4Run
"""
from __future__ import annotations

import re
import unicodedata

from bs4 import BeautifulSoup

from .http_client import get as http_get

# ---------------------------------------------------------------------------
# Shared text-normalisation helpers
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

            link_text = a.get_text(strip=True)
            parent_text = (
                a.parent.get_text(separator=" ", strip=True) if a.parent else ""
            )
            slug_raw = href.split("/prova/", 1)[-1]
            slug_body = re.sub(r"^\d{8}-", "", slug_raw)
            slug_body = re.sub(r"-\d+$", "", slug_body).replace("-", " ")

            if not any(
                _title_match(titulo, candidate)
                for candidate in (link_text, parent_text, slug_body)
                if candidate
            ):
                continue

            prova_url = f"{_FR_BASE}{href}"
            if _focoradical_has_photos(prova_url):
                return prova_url

    except Exception as exc:
        print(f"[fotos] focoradical error: {exc}")

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
# Fotop  (fotop.com.br)
# ---------------------------------------------------------------------------

_FOTOP_BASE = "https://fotop.com.br"
_FOTOP_EVENT_RE = re.compile(r"/fotos/eventos\?evento=(\d+)")
# "928.776 fotos" or "1.234 fotos" — Brazilian dot-as-thousands separator
_FOTOP_FOTO_RE = re.compile(r"([\d.]+)\s+fotos?", re.IGNORECASE)


def _search_fotop(titulo: str, data_evento: str) -> str | None:
    """Parse Fotop's running-events listing and return a URL if photos found."""
    if not titulo:
        return None

    try:
        resp = http_get(f"{_FOTOP_BASE}/?cat=1", timeout=15)
        if resp.status_code != 200:
            return None

        soup = BeautifulSoup(resp.text, "lxml")

        for a in soup.find_all("a", href=_FOTOP_EVENT_RE):
            href: str = a.get("href", "")

            # Title: try link text, then nearest parent container text
            title_text = a.get_text(strip=True)
            if not title_text and a.parent:
                title_text = a.parent.get_text(separator=" ", strip=True)

            if not _title_match(titulo, title_text):
                continue

            event_url = (
                f"{_FOTOP_BASE}{href}" if href.startswith("/") else href
            )
            if _fotop_has_photos(event_url):
                return event_url

    except Exception as exc:
        print(f"[fotos] fotop error: {exc}")

    return None


def _fotop_has_photos(url: str) -> bool:
    try:
        resp = http_get(url, timeout=15)
        if resp.status_code != 200:
            return False
        m = _FOTOP_FOTO_RE.search(resp.text)
        if not m:
            return False
        # Remove thousands dots: "928.776" → 928776
        count = int(m.group(1).replace(".", ""))
        return count > 0
    except Exception:
        return False


# ---------------------------------------------------------------------------
# FinisherPix  (finisherpix.com)
# ---------------------------------------------------------------------------

_FPX_BASE = "https://www.finisherpix.com"
_FPX_SEARCH = f"{_FPX_BASE}/en/events/search"


def _search_finisherpix(titulo: str, data_evento: str) -> str | None:
    """Use FinisherPix's filter[query] search API."""
    if not titulo:
        return None

    year = data_evento[:4] if data_evento else None
    params: dict = {"filter[query]": titulo, "filter[upcoming]": "0"}
    if year:
        params["filter[year]"] = year

    try:
        resp = http_get(_FPX_SEARCH, params=params, timeout=15)
        if resp.status_code != 200:
            return None

        soup = BeautifulSoup(resp.text, "lxml")

        for div in soup.find_all("div", attrs={"data-event-title": True}):
            event_title = div.get("data-event-title", "")
            event_path = div.get("data-event-url", "")

            if not event_path:
                # fallback: look for a link inside the div
                a = div.find("a", href=re.compile(r"/en/event/\d+"))
                if a:
                    event_path = a.get("href", "")

            if not _title_match(titulo, event_title):
                continue

            return f"{_FPX_BASE}{event_path}" if event_path.startswith("/") else event_path

    except Exception as exc:
        print(f"[fotos] finisherpix error: {exc}")

    return None


# ---------------------------------------------------------------------------
# CorrepraFoto  (correprafoto.com.br)
# ---------------------------------------------------------------------------

_CPF_BASE = "https://www.correprafoto.com.br"
_CPF_HREF_RE = re.compile(r"fotos-\d+,")


def _search_correprafoto(titulo: str, data_evento: str) -> str | None:
    """Parse CorrepraFoto's running-events listing (cat=1).

    Cards show "Fotos disponíveis!" when published and "Em breve!" when not —
    so a single request is enough; no extra event-page fetch needed.
    """
    if not titulo:
        return None

    try:
        resp = http_get(
            f"{_CPF_BASE}/categorias.aspx?cat=1", timeout=15
        )
        if resp.status_code != 200:
            return None

        soup = BeautifulSoup(resp.text, "lxml")

        for h5 in soup.find_all("h5"):
            a = h5.find("a", href=_CPF_HREF_RE)
            if not a:
                continue

            title = a.get_text(strip=True)
            if not _title_match(titulo, title):
                continue

            # Walk up to the card container to check photo status
            card = h5.find_parent()
            if card:
                card_text = card.get_text(separator=" ", strip=True)
                if "Em breve" in card_text:
                    continue  # photos not yet published

            href = a.get("href", "")
            return f"{_CPF_BASE}/{href}"

    except Exception as exc:
        print(f"[fotos] correprafoto error: {exc}")

    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def find_event_photos(corrida: dict) -> list[dict]:
    """Search all photo platforms for a past event.

    Returns a list of ``{"plataforma": str, "url": str}`` dicts for each
    platform that has published photos confirmed for this event.

    Platforms are searched sequentially to stay polite to each server;
    concurrency across *events* is handled by the caller (_find_all_photos).
    """
    titulo = corrida.get("titulo", "")
    data_evento = corrida.get("data_evento", "")

    results: list[dict] = []

    for search_fn, nome in (
        (_search_focoradical,  "Foco Radical"),
        (_search_fotop,        "Fotop"),
        (_search_correprafoto, "CorrepraFoto"),
        (_search_finisherpix,  "FinisherPix"),
    ):
        try:
            url = search_fn(titulo, data_evento)
            if url:
                results.append({"plataforma": nome, "url": url})
        except Exception as exc:
            print(f"[fotos] {nome} unexpected error: {exc}")

    return results
