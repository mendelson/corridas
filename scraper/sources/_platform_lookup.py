"""Domain-based platform lookup for calendar scrapers (bora_correr, brasil_que_corre, …).

When a calendar aggregator links to an external platform, we want the button text
and tipo to reflect the *destination* platform, not the calendar itself.

Each entry: (domain_fragment, display_name, FonteInfo tipo)
"""
from __future__ import annotations
import os
from urllib.parse import urlparse

from ..models import FonteTipo

_PLATFORMS: list[tuple[str, str, FonteTipo]] = [
    # Registration platforms
    ("ticketsports.com.br",           "Ticket Sports",         "inscricao"),
    ("ticketagora.com.br",            "Ticket Sports",         "inscricao"),
    ("page.ticketsports.com.br",      "Ticket Sports",         "inscricao"),
    ("sympla.com.br",                 "Sympla",                "inscricao"),
    ("minhasinscricoes.com.br",       "Minhas Inscrições",     "inscricao"),
    ("atletis.com.br",                "Atletis",               "inscricao"),
    ("racetimer.com.br",              "RaceTimer",             "inscricao"),
    ("corridasbrasil.com.br",         "Corridas Brasil",       "inscricao"),
    # Race organizers
    ("tfsports.com.br",               "TF Sports",             "organizador"),
    ("circuitodasestacoes.com.br",    "Circuito das Estações", "organizador"),
    ("trackandfieldrun.com.br",       "Track & Field",         "organizador"),
    ("brutusrace.com.br",             "Brutus Race",           "organizador"),
    # Other calendars / aggregators
    ("centraldacorrida.com.br",       "Central da Corrida",    "calendario"),
    ("brasilcorrida.com.br",          "Brasil Corrida",        "calendario"),
    ("esportes.agenciasisters.com.br","Agência Sisters",        "calendario"),
    ("runbrasil.com.br",              "Run Brasil",            "calendario"),
]


def _domain(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")


def _lookup(url: str) -> tuple[str, FonteTipo] | None:
    """Return (nome, tipo) for url if domain matches a known platform, else None."""
    d = _domain(url)
    for fragment, nome, tipo in _PLATFORMS:
        if fragment in d:
            return nome, tipo
    return None


def resolve_redirect(url: str) -> str:
    """Follow HTTP redirects and return the final URL.

    Used only when the direct domain lookup fails (unknown domain).
    Skipped in SCRAPER_TEST mode to keep CI fast.
    """
    if os.environ.get("SCRAPER_TEST"):
        return url
    try:
        from ..http_client import get_direct
        resp = get_direct(url, timeout=5)
        return str(resp.url)
    except Exception:
        return url


def nome_tipo_for_url(
    url: str,
    fallback_nome: str,
    fallback_tipo: FonteTipo,
) -> tuple[str, FonteTipo]:
    """Return (display_name, tipo) for a given URL.

    1. Try direct domain lookup.
    2. If unknown, follow HTTP redirect and try again (skipped in SCRAPER_TEST).
    3. Fall back to (fallback_nome, fallback_tipo).
    """
    if not url:
        return fallback_nome, fallback_tipo

    result = _lookup(url)
    if result:
        return result

    final_url = resolve_redirect(url)
    if final_url != url:
        result = _lookup(final_url)
        if result:
            return result

    return fallback_nome, fallback_tipo
