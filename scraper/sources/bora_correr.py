"""Scraper for coelhodeprograma.com.br/boracorrer/

The site is a custom (non-WordPress) running calendar for DF and surroundings.
Events are server-rendered in a #tabDados HTML table — each row has 3 cells:
  [0] date as DD/MM/YYYY (may include a time: "30/05/2026 07:00h")
  [1] <a href="EVENT_URL">Title<br />(distance hints)</a>
  [2] action buttons containing the UUID via obterDadosReport('UUID',…)

The original scraper used generic CSS selectors (.event/.race/article) that
never matched this DOM and was dropped on the wrong assumption it was blocked.
"""
from __future__ import annotations
import re
import html as html_mod
from urllib.parse import urlparse
from bs4 import BeautifulSoup

from ..http_client import get
from ..models import Corrida, Distancia, FonteInfo
from ..utils import normalize_titulo, now_iso, today_iso

URL = "https://coelhodeprograma.com.br/boracorrer/"
SOURCE_NAME = "Bora Correr"

_DOMAIN_TO_SOURCE: list[tuple[str, str]] = [
    ("ticketsports.com.br",      "Ticket Sports"),
    ("ticketagora.com.br",       "Ticket Sports"),
    ("page.ticketsports.com.br", "Ticket Sports"),
    ("sympla.com.br",            "Sympla"),
    ("tfsports.com.br",          "TF Sports"),
    ("centraldacorrida.com.br",  "Central da Corrida"),
    ("minhasinscricoes.com.br",  "Minhas Inscrições"),
    ("brasilcorrida.com.br",     "Brasil Corrida"),
    ("circuitodasestacoes.com.br", "Circuito das Estações"),
    ("esportes.agenciasisters.com.br", "Agência Sisters"),
]


def _nome_for_link(url: str) -> str:
    domain = urlparse(url).netloc.lower().removeprefix("www.")
    for fragment, nome in _DOMAIN_TO_SOURCE:
        if fragment in domain:
            return nome
    return SOURCE_NAME

# Snap nearby values to the canonical race distance (same pattern as ativo.py).
_CANONICAL = [(42.195, 41.5, 43.0), (21.097, 20.5, 21.5)]

_DATE_RE = re.compile(r"(\d{2})/(\d{2})/(\d{4})")
_UUID_RE = re.compile(r"obterDadosReport\('([0-9a-f-]+)'", re.I)
_KM_RE   = re.compile(r"\b(\d+(?:[.,]\d+)?)\s*[kK][mM]?\b")

# Orienteering and other non-running event keywords — skip silently
_NON_RUNNING_RE = re.compile(
    r"\borientak?[çc]|\bse orienta\b|\bbuss?ola\b|\borienteering\b"
    r"|\bciclismo\b|\bbike\b|\bciclo\b|\bnatação\b|\btriathlon\b|\btriatlol\b",
    re.IGNORECASE,
)

# Time patterns: "07h30", "07:30h", "07:30", "7h" — must not be followed by km.
_TIME_RE = re.compile(
    r"\b(\d{1,2})[hH:]([0-5]\d)\s*(?:min\s*)?[hH]?\b(?!\s*[kK])"
    r"|\b(\d{1,2})\s*[hH]\b(?!\s*\d)",
    re.IGNORECASE,
)


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

    table = soup.find("table", id="tabDados")
    if not table:
        print(f"[{SOURCE_NAME}] tabela #tabDados não encontrada")
        return []

    corridas: list[Corrida] = []
    seen_ids: set[str] = set()

    for tr in table.find_all("tr", class_=["impar", "par"]):
        try:
            c = _parse_row(tr, today, now)
        except Exception as e:
            print(f"[{SOURCE_NAME}] erro ao parsear linha: {e}")
            continue
        if c and c.id not in seen_ids:
            seen_ids.add(c.id)
            corridas.append(c)

    print(f"[{SOURCE_NAME}] {len(corridas)} corridas encontradas")
    return corridas


def _parse_row(tr, today: str, now: str) -> Corrida | None:
    cells = tr.find_all("td")
    if len(cells) < 3:
        return None

    # Cell 0: date (DD/MM/YYYY) and optional time
    cell0_text = cells[0].get_text(" ", strip=True)
    m = _DATE_RE.search(cell0_text)
    if not m:
        return None
    day, month, year = m.groups()
    data_evento = f"{year}-{month}-{day}"
    if data_evento < today:
        return None

    # Try to get horario from cell 0 first (time may follow the date)
    horario = _extract_horario(cell0_text)

    # Title + distances + link from cell 1
    link_tag = cells[1].find("a")
    if not link_tag:
        return None
    _href = link_tag.get("href", "").strip()
    _parsed = urlparse(_href)
    if _href and _parsed.path not in ("", "/"):
        link = _href
    else:
        # No specific event page — skip (likely orienteering/non-running events)
        return None

    # The title text and the distance hint are separated by <br />
    inner_html  = link_tag.decode_contents()
    parts       = re.split(r"<br\s*/?>", inner_html, maxsplit=1, flags=re.I)
    titulo_raw  = html_mod.unescape(_strip_tags(parts[0]))
    dist_hint   = html_mod.unescape(_strip_tags(parts[1])) if len(parts) > 1 else ""
    titulo = normalize_titulo(titulo_raw)
    if not titulo or len(titulo) < 3:
        return None
    if _NON_RUNNING_RE.search(titulo_raw) or _NON_RUNNING_RE.search(dist_hint):
        return None  # orienteering / non-running event

    # Horario fallback: check dist_hint and full cell 1 text
    if horario is None:
        horario = _extract_horario(dist_hint) or _extract_horario(cells[1].get_text(" ", strip=True))

    # Last resort: fetch the event detail page for the start time
    if horario is None:
        horario = _fetch_horario_from_detail(link)

    if horario is None:
        return None

    # Stable ID — UUID from the report button if present, else fallback to date+title
    uuid_m = _UUID_RE.search(str(cells[2]))
    if uuid_m:
        stable_id = f"boracorrer_{uuid_m.group(1)}"
    else:
        stable_id = f"boracorrer_{data_evento}_{titulo[:40].lower().replace(' ', '-')}"

    distancias = _extract_distances(dist_hint)

    return Corrida(
        id=stable_id,
        titulo=titulo,
        data_evento=data_evento,
        horario=horario,
        localizacao="Brasília, DF",
        cidade="Brasília",
        estado="DF",
        pais="BR",
        distancias=distancias,
        imagem_url=None,
        inscricoes_abertas=None,
        periodo_inscricao=None,
        fontes=[FonteInfo(
            nome=_nome_for_link(link),
            link_evento=link,
            links_inscricao=[link],
            tipo="calendario",
        )],
        miss_count=0,
        first_seen_at=now,
        updated_at=now,
    )


def _fetch_horario_from_detail(url: str) -> str | None:
    """Fetch the event page (Ticket Sports / CDC / etc.) and extract start time."""
    try:
        resp = get(url)
        if resp.status_code != 200:
            return None
        soup = BeautifulSoup(resp.text, "lxml")
        return _extract_horario(soup.get_text(" ", strip=True))
    except Exception:
        return None


def _strip_tags(s: str) -> str:
    return re.sub(r"<[^>]+>", "", s).strip()


def _extract_horario(text: str) -> str | None:
    """Parse times like '07h30', '07:30h', '07:30', '7h' from free text."""
    if not text:
        return None
    m = _TIME_RE.search(text)
    if not m:
        return None
    if m.group(1) is not None:
        h, mi = int(m.group(1)), int(m.group(2))
    else:
        h, mi = int(m.group(3)), 0
    return f"{h:02d}:{mi:02d}"


def _normalize_dist_text(text: str) -> str:
    """Expand shared-suffix patterns so _KM_RE can match each number individually.

    Examples:
      '5/10km'      → '5km 10km'
      '5/10/21km'   → '5km 10km 21km'
      '5 e 10 km'   → '5km 10km'
    """
    # Slash/comma separated: 5/10km or 5/10/21km
    text = re.sub(
        r"(\d+(?:[.,]\d+)?)(?:/(\d+(?:[.,]\d+)?))+\s*([kK][mM]?\b)",
        lambda m: " ".join(
            n + m.group(3)
            for n in re.split(r"/", m.group(0).rsplit(m.group(3), 1)[0])
        ),
        text,
    )
    # "e"-separated with shared suffix: "5 e 10 km" → "5km 10km"
    text = re.sub(
        r"(\d+(?:[.,]\d+)?)\s+e\s+(\d+(?:[.,]\d+)?)\s+([kK][mM]\b)",
        lambda m: f"{m.group(1)}{m.group(3)} {m.group(2)}{m.group(3)}",
        text,
        flags=re.IGNORECASE,
    )
    return text


def _extract_distances(text: str) -> list[Distancia]:
    """Parse distance hints like '(10/5km)' or '(5 e 10 km)' or '(5km e 10km)'."""
    if not text:
        return []
    text = _normalize_dist_text(text)
    seen: list[float] = []
    for m in _KM_RE.finditer(text):
        try:
            raw = float(m.group(1).replace(",", "."))
        except ValueError:
            continue
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

