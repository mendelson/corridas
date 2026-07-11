"""Scraper for brasilquecorre.com/distritofederal

Custom (non-WordPress) site built on what looks like a Locaweb page builder.
Each event lives in a `<div class="cs-text-widget">` with this structure:

  <h5><a href="EXTERNAL_EVENT_URL">TITLE</a></h5>
  <p>&nbsp;</p>
  <p>DD[ e DD] de MES de YYYY</p>
  <p>CITY [/ UF]</p>
  <p>Xkm, Ykm... (corrida)</p>
  <p>ORGANIZER</p>

47 of 52 event widgets contain a direct link to the registration platform
(centraldacorrida.com.br, ticketsports.com.br, brasilcorrida.com.br, etc.).
link_evento is set to that external URL; the platform name is inferred from
the domain so the merger can correctly attribute the source.

Start times are not on the listing page — each event's external link
(Ticket Sports, CDC, Brasil Corrida, etc.) is fetched to extract the time.
The HTTP fallback chain handles Cloudflare/SPA sites where needed.

The original scraper used generic CSS selectors (.event/.race/article) that
never matched this DOM and was incorrectly dropped as "broken".
"""
from __future__ import annotations
import re
from urllib.parse import urlparse
from bs4 import BeautifulSoup

from ..http_client import get
from ..models import Corrida, Distancia, FonteInfo
from ..utils import normalize_titulo, slugify, now_iso, today_iso

URL = "https://brasilquecorre.com/distritofederal"
SOURCE_NAME = "Brasil que Corre"

_DOMAIN_TO_SOURCE: list[tuple[str, str]] = [
    ("ticketsports.com.br",        "Ticket Sports"),
    ("ticketagora.com.br",         "Ticket Sports"),
    ("page.ticketsports.com.br",   "Ticket Sports"),
    ("sympla.com.br",              "Sympla"),
    ("tfsports.com.br",            "TF Sports"),
    ("centraldacorrida.com.br",    "Central da Corrida"),
    ("minhasinscricoes.com.br",    "Minhas Inscrições"),
    ("brasilcorrida.com.br",       "Brasil Corrida"),
    ("circuitodasestacoes.com.br", "Circuito das Estações"),
    ("brutusrace.com.br",          "Brutus Race"),
]

def _nome_for_link(url: str) -> str:
    domain = urlparse(url).netloc.lower().removeprefix("www.")
    for fragment, nome in _DOMAIN_TO_SOURCE:
        if fragment in domain:
            return nome
    return SOURCE_NAME

_CANONICAL = [(42.195, 41.5, 43.0), (21.097, 20.5, 21.5)]

_MONTHS = {
    "janeiro": 1, "jan": 1,  "fevereiro": 2, "fev": 2,
    "março":   3, "marco": 3, "mar": 3,
    "abril":   4, "abr": 4,  "maio":      5, "mai": 5,
    "junho":   6, "jun": 6,  "julho":     7, "jul": 7,
    "agosto":  8, "ago": 8,  "setembro":  9, "set": 9,
    "outubro":10, "out":10,  "novembro": 11, "nov":11,
    "dezembro":12,"dez":12,
}

# "23 de Maio de 2026" or "13 e 14 de Junho de 2026" — capture first day.
_DATE_RE = re.compile(
    r"\b(\d{1,2})(?:\s*e\s*\d{1,2})?\s*de\s*([A-Za-zçãéíóú]+)\s*de\s*(\d{4})\b",
    re.IGNORECASE,
)
_KM_RE = re.compile(r"\b(\d+(?:[.,]\d+)?)\s*[kK][mM]\b")
# Only pick distances tagged as "corrida" (running) — skip caminhada/infantil/OCR.
_CORRIDA_SEGMENT_RE = re.compile(
    r"([0-9.,\sekmKM\-+]+?)\s*\(\s*corrida[^)]*\)",
    re.IGNORECASE,
)

_UF_NORM: dict[str, str] = {
    "Distrito Federal": "DF", "Goiás": "GO", "Minas Gerais": "MG",
    "São Paulo": "SP", "Rio de Janeiro": "RJ", "Bahia": "BA",
}

_TIME_RE = re.compile(
    r"\b(\d{1,2})[hH:]([0-5]\d)\s*(?:min\s*)?[hH]?\b(?!\s*[kK])"
    r"|\b(\d{1,2})\s*[hH]\b(?!\s*\d)",
    re.IGNORECASE,
)


def _fetch_horario_from_link(url: str) -> str | None:
    """Fetch external event page (with JS-rendering fallback) and extract start time."""
    for _attempt in range(2):
        try:
            resp = get(url)
            if resp.status_code != 200:
                continue
            soup = BeautifulSoup(resp.text, "lxml")
            text = soup.get_text(" ", strip=True)
            m = _TIME_RE.search(text)
            if not m:
                continue
            if m.group(1) is not None:
                h, mi = int(m.group(1)), int(m.group(2))
            else:
                h, mi = int(m.group(3)), 0
            if 4 <= h <= 23 and 0 <= mi <= 59:
                return f"{h:02d}:{mi:02d}"
        except Exception:
            pass
    return None


def scrape() -> list[Corrida]:
    try:
        resp = get(URL)
        resp.raise_for_status()
    except Exception as e:
        print(f"[{SOURCE_NAME}] erro ao buscar {URL}: {e}")
        return []

    soup  = BeautifulSoup(resp.text, "lxml")
    today = today_iso()
    now   = now_iso()

    corridas: list[Corrida] = []
    seen_ids: set[str] = set()

    for widget in soup.find_all("div", class_="cs-text-widget"):
        try:
            c = _parse_widget(widget, today, now)
        except Exception as e:
            print(f"[{SOURCE_NAME}] erro ao parsear widget: {e}")
            continue
        if c and c.id not in seen_ids:
            seen_ids.add(c.id)
            corridas.append(c)

    print(f"[{SOURCE_NAME}] {len(corridas)} corridas encontradas")
    return corridas


def _parse_widget(widget, today: str, now: str) -> Corrida | None:
    # Extract external event link from <h5><a href> — present in 47 of 52 event widgets.
    # This is the real event page (CDC, Ticket Sports, Brasil Corrida, etc.), not BQC itself.
    link: str | None = None
    h5 = widget.find("h5")
    if h5:
        a = h5.find("a", href=True)
        if a:
            href = a.get("href", "").strip()
            if href and href.startswith("http"):
                link = href

    text = widget.get_text(" ", strip=True)
    if not text or len(text) < 20:
        return None

    # Date must be present; if not, this isn't an event widget (section header etc).
    m = _DATE_RE.search(text)
    if not m:
        return None
    day, month_name, year = m.groups()
    month = _MONTHS.get(month_name.lower().strip("."))
    if not month:
        return None
    data_evento = f"{int(year):04d}-{month:02d}-{int(day):02d}"
    if data_evento < today:
        return None

    # Title = everything before the date. Strip trailing punctuation.
    titulo_raw = text[: m.start()].strip(" -–|")
    titulo = normalize_titulo(titulo_raw)
    if not titulo or len(titulo) < 3:
        return None

    # City / state: look for the <p> that comes right after the date <p>.
    cidade, estado = "Brasília", "DF"
    paras = [p.get_text(" ", strip=True) for p in widget.find_all("p") if p.get_text(strip=True)]
    for i, p_text in enumerate(paras):
        if _DATE_RE.search(p_text) and i + 1 < len(paras):
            loc_raw = paras[i + 1]
            loc_parts = [x.strip() for x in loc_raw.split("/")]
            if len(loc_parts) == 2:
                cidade = loc_parts[0].strip()
                estado_raw = loc_parts[1].strip()
                estado = _UF_NORM.get(estado_raw, estado_raw)
            elif loc_parts and loc_parts[0]:
                cidade = loc_parts[0].strip()
            break
    localizacao = f"{cidade}, {estado}" if estado else cidade

    # Distances from the text that follows the date match.
    after_date = text[m.end():].strip()
    distancias = _extract_distances(after_date)

    # Stable ID: prefer the page-builder widget id attribute; fall back to date+slug.
    widget_id = widget.get("id", "").strip()
    stable_id = f"bqc_{widget_id}" if widget_id else f"bqc_{data_evento}_{slugify(titulo)[:40]}"

    link_evento = link or URL

    # Fetch the external event page to get the start time.
    horario = _fetch_horario_from_link(link_evento) if link_evento != URL else None
    # Horário no longer mandatory (policy 2026-07-11): keep the event without it.
    # if horario is None:
    #     return None

    return Corrida(
        id=stable_id,
        titulo=titulo,
        data_evento=data_evento,
        horario=horario,
        localizacao=localizacao,
        cidade=cidade,
        estado=estado,
        pais="BR",
        distancias=distancias,
        imagem_url=None,
        inscricoes_abertas=None,
        periodo_inscricao=None,
        fontes=[FonteInfo(
            nome=_nome_for_link(link_evento),
            link_evento=link_evento,
            links_inscricao=[link_evento],
            tipo="calendario",
        )],
        miss_count=0,
        first_seen_at=now,
        updated_at=now,
    )


def _extract_distances(text: str) -> list[Distancia]:
    """Parse "1km, 5km, 10km e 21km (corrida)" — keep only running segments."""
    # Collect all "X km" mentions that appear inside a (corrida) parenthetical.
    raw_km: list[float] = []
    for seg in _CORRIDA_SEGMENT_RE.findall(text):
        for m in _KM_RE.finditer(seg):
            try:
                raw_km.append(float(m.group(1).replace(",", ".")))
            except ValueError:
                pass

    # If no (corrida) annotation, fall back to all km mentions (some events omit it).
    if not raw_km:
        for m in _KM_RE.finditer(text):
            try:
                raw_km.append(float(m.group(1).replace(",", ".")))
            except ValueError:
                pass

    seen: list[float] = []
    for raw in raw_km:
        if raw < 1 or raw > 200:
            continue
        km = raw
        for canon, lo, hi in _CANONICAL:
            if lo <= raw <= hi:
                km = canon
                break
        if any(abs(km - s) < 0.5 for s in seen):
            continue
        seen.append(km)
    return sorted(
        [Distancia(km=k, data=None, horario=None) for k in seen],
        key=lambda d: float(d.km),
    )
