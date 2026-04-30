"""Scraper for liverun.com.br — calendar + event detail pages."""
from __future__ import annotations
import re
from datetime import date, timedelta
from bs4 import BeautifulSoup

from ..http_client import get
from ..models import Corrida, Distancia, FonteInfo
from ..utils import (
    normalize_titulo, slugify, now_iso, today_iso,
)

BASE = "https://www.liverun.com.br"
CALENDAR_URL = f"{BASE}/calendario"
INSCRICAO_BASE = "https://www.appliveexperience.com.br/evento"
SOURCE_NAME = "Live Run"

# Matches hydration/interval mentions that generate false km values
_INTERVAL_RE = re.compile(
    r"a cada \d+(?:[.,]\d+)?\s*k(?:m)?\b"
    r"|cada \d+(?:[.,]\d+)?\s*k(?:m)?\b"
    r"|\d+(?:[.,]\d+)?\s*k(?:m)?\s*(?:de hidrat|de água|de abastec)",
    re.IGNORECASE,
)

# Matches schedule time spans (HH:MM)
_TIME_SPAN_RE = re.compile(r"^\d{1,2}:\d{2}$")

# "Largada 21 Km" / "Largada 10 e 5 Km" — real mass start, excludes PCD and Kids
_LARGADA_RE = re.compile(r"^largada\s+(?!pcd)(?!kids)", re.IGNORECASE)


def scrape() -> list[Corrida]:
    try:
        resp = get(CALENDAR_URL)
        resp.raise_for_status()
    except Exception as e:
        print(f"[{SOURCE_NAME}] erro ao buscar calendário: {e}")
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    corridas: list[Corrida] = []

    for a in soup.find_all("a", href=True):
        href = a.get("href", "")
        if "/etapa/" not in href:
            continue
        try:
            corrida = _parse_card(a, href)
            if corrida:
                corridas.append(corrida)
        except Exception as e:
            slug = href.split("/etapa/")[-1]
            print(f"[{SOURCE_NAME}] erro no card '{slug}': {e}")

    print(f"[{SOURCE_NAME}] {len(corridas)} corridas encontradas")
    return corridas


# ---------------------------------------------------------------------------
# Card parsing (calendar page)
# ---------------------------------------------------------------------------

def _parse_card(a, href: str) -> Corrida | None:
    slug = href.split("/etapa/")[-1].strip("/")

    # City and state from the title attribute: "São Paulo - SP"
    title_attr = a.get("title", "")
    city, state = _parse_location(title_attr)
    if not city:
        return None

    localizacao = f"{city}, {state}" if state else city
    titulo = _event_title(slug, city)

    # Date: DD/MM text in the card — no year, infer it
    data_evento = _parse_card_date(a)

    # Distances: spans containing km values, min 3 km, no Kids
    distancias_base = _parse_card_distances(a)

    # Inscription status: span containing "Inscrições"
    inscricoes_abertas = _parse_card_status(a)

    # Registration link: derived from slug (appliveexperience.com.br)
    link_evento = f"{BASE}/etapa/{slug}"
    link_inscricao = f"{INSCRICAO_BASE}/{slug}"

    # Fetch detail page to get per-distance start times
    distancias = _enrich_with_schedule(slug, distancias_base, data_evento)

    horario = None
    times = [d.horario for d in distancias if d.horario]
    if times:
        horario = min(times)

    # Image from card
    img = a.find("img")
    imagem_url = None
    if img:
        imagem_url = img.get("src") or img.get("data-src")

    now = now_iso()
    today = today_iso()

    links_insc = [link_inscricao] if inscricoes_abertas is not False else []
    fonte = FonteInfo(
        nome=SOURCE_NAME,
        link_evento=link_evento,
        links_inscricao=links_insc,
    )

    return Corrida(
        id=f"{slugify(titulo)}_{state.lower()}_{today}",
        titulo=titulo,
        data_evento=data_evento or "",
        horario=horario,
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
    )


def _parse_location(title_attr: str) -> tuple[str, str]:
    """Parse 'City - SP' or 'City - State' from title attribute."""
    if not title_attr:
        return "", ""
    m = re.match(r"^(.+?)\s*[-–]\s*([A-Z]{2})$", title_attr.strip())
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return title_attr.strip(), ""


def _event_title(slug: str, city: str) -> str:
    """Construct a human-readable event title from the slug pattern."""
    sl = slug.lower()
    if sl.startswith("live42k"):
        kind = "42K"
    elif sl.startswith("live21k"):
        kind = "21K"
    elif "trail" in sl:
        kind = "Trail"
    elif "experience" in sl and "trail" not in sl:
        kind = "Experience"
    else:
        kind = "RUN"
    year_m = re.search(r"(20\d{2})$", slug)
    year_sfx = f" {year_m.group(1)}" if year_m else ""
    return normalize_titulo(f"LIVE! {kind} {city}{year_sfx}")


def _parse_card_date(a) -> str | None:
    """Find DD/MM date in card text and infer the year."""
    text = a.get_text(" ", strip=True)
    m = re.search(r"\b(\d{1,2})/(\d{1,2})\b", text)
    if not m:
        return None
    day, month = int(m.group(1)), int(m.group(2))
    if not (1 <= day <= 31 and 1 <= month <= 12):
        return None
    year = _infer_year(day, month)
    return f"{year}-{month:02d}-{day:02d}"


def _infer_year(day: int, month: int) -> int:
    """Use current year; bump to next year if the date is more than 30 days past."""
    today = date.today()
    year = today.year
    try:
        candidate = date(year, month, day)
    except ValueError:
        return year
    if candidate < today - timedelta(days=30):
        year += 1
    return year


def _parse_card_distances(a) -> list[Distancia]:
    """Extract distances (≥3 km) from card spans, skipping Kids/hydration."""
    # Collect km values from all spans that look like distances
    text = a.get_text(" ", strip=True)
    # Strip hydration/interval noise first
    text = _INTERVAL_RE.sub(" ", text)
    nums = re.findall(r"\b(\d+(?:[.,]\d+)?)\s*[Kk][Mm]?\b", text)
    seen: set[float] = set()
    result: list[Distancia] = []
    for n in nums:
        km = float(n.replace(",", "."))
        if km not in seen and 3 <= km <= 100:
            seen.add(km)
            result.append(Distancia(km=km, data=None, horario=None))
    return result


def _parse_card_status(a) -> bool | None:
    """Detect inscription open/closed status from the card's status span."""
    for span in a.find_all("span"):
        text = span.get_text(strip=True).lower()
        if "inscrições" in text or "inscricoes" in text:
            if any(kw in text for kw in ("abertas", "aberta", "última", "ultima", "pré", "pre")):
                return True
            if any(kw in text for kw in ("encerrad", "esgotad")):
                return False
    return None


# ---------------------------------------------------------------------------
# Detail page: per-distance start times
# ---------------------------------------------------------------------------

def _enrich_with_schedule(
    slug: str,
    distancias: list[Distancia],
    data_evento: str | None,
) -> list[Distancia]:
    """Fetch the event detail page and attach start times to each distance."""
    if not distancias:
        return distancias

    try:
        resp = get(f"{BASE}/etapa/{slug}")
        resp.raise_for_status()
    except Exception as e:
        print(f"[{SOURCE_NAME}] erro ao buscar detalhe '{slug}': {e}")
        return distancias

    soup = BeautifulSoup(resp.text, "lxml")
    schedule = _parse_schedule(soup)

    if not schedule:
        return distancias

    result: list[Distancia] = []
    for d in distancias:
        horario = schedule.get(d.km)
        if horario is None and schedule:
            # Site uses a generic schedule template that may not list exact km;
            # map to nearest listed distance.  For longer distances (marathon etc.)
            # that exceed the template's max, pick the longest listed entry
            # because it has the earliest start.
            if d.km > max(schedule):
                horario = schedule[max(schedule)]
            else:
                nearest = min(schedule, key=lambda k: abs(k - d.km))
                horario = schedule[nearest]
        result.append(Distancia(km=d.km, data=data_evento, horario=horario))
    return result


def _parse_schedule(soup: BeautifulSoup) -> dict[float, str]:
    """
    Parse the "Programação da arena" schedule.

    Structure: pairs of <span>HH:MM</span> / <span>Description</span> siblings.
    We only capture lines matching "Largada X Km" (not PCD, not Kids).
    """
    schedule: dict[float, str] = {}

    for time_span in soup.find_all("span", string=_TIME_SPAN_RE):
        time_str = time_span.get_text(strip=True)
        desc_el = time_span.find_next_sibling()
        if not desc_el:
            continue
        desc = desc_el.get_text(strip=True)

        if not _LARGADA_RE.match(desc):
            continue

        # Extract all km values from description: "Largada 10 e 5 Km" → [10, 5]
        # Numbers may appear before a single "Km" suffix: split on first km unit
        km_unit = re.search(r"[Kk][Mm]\b", desc)
        prefix = desc[:km_unit.start()] if km_unit else desc
        kms_raw = re.findall(r"\b(\d+(?:[.,]\d+)?)\b", prefix)
        for n in kms_raw:
            km = float(n.replace(",", "."))
            if 3 <= km <= 100 and km not in schedule:
                schedule[km] = time_str

    return schedule
