"""Scraper for coelhodeprograma.com.br/boracorrer/

The site is a custom (non-WordPress) running calendar for DF and surroundings.
Events are server-rendered in a #tabDados HTML table — each row has 3 cells:
  [0] date as DD/MM/YYYY
  [1] <a href="EVENT_URL">Title<br />(distance hints)</a>
  [2] action buttons containing the UUID via obterDadosReport('UUID',…)

The original scraper used generic CSS selectors (.event/.race/article) that
never matched this DOM and was dropped on the wrong assumption it was blocked.
"""
from __future__ import annotations
import re
import html as html_mod
from bs4 import BeautifulSoup

from ..http_client import get
from ..models import Corrida, Distancia, FonteInfo
from ..utils import normalize_titulo, now_iso, today_iso

URL = "https://coelhodeprograma.com.br/boracorrer/"
SOURCE_NAME = "Bora Correr"

# Snap nearby values to the canonical race distance (same pattern as ativo.py).
_CANONICAL = [(42.195, 41.5, 43.0), (21.097, 20.5, 21.5)]

_DATE_RE = re.compile(r"(\d{2})/(\d{2})/(\d{4})")
_UUID_RE = re.compile(r"obterDadosReport\('([0-9a-f-]+)'", re.I)
_KM_RE   = re.compile(r"\b(\d+(?:[.,]\d+)?)\s*[kK][mM]?\b")


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

    # Date — DD/MM/YYYY in cell 0
    m = _DATE_RE.search(cells[0].get_text(" ", strip=True))
    if not m:
        return None
    day, month, year = m.groups()
    data_evento = f"{year}-{month}-{day}"
    if data_evento < today:
        return None

    # Title + distances + link from cell 1
    link_tag = cells[1].find("a")
    if not link_tag:
        return None
    link = link_tag.get("href", "").strip() or URL

    # The title text and the distance hint are separated by <br />
    inner_html  = link_tag.decode_contents()
    parts       = re.split(r"<br\s*/?>", inner_html, maxsplit=1, flags=re.I)
    titulo_raw  = html_mod.unescape(_strip_tags(parts[0]))
    dist_hint   = html_mod.unescape(_strip_tags(parts[1])) if len(parts) > 1 else ""
    titulo = normalize_titulo(titulo_raw)
    if not titulo or len(titulo) < 3:
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
        horario=None,
        localizacao="Brasília, DF",
        cidade="Brasília",
        estado="DF",
        pais="BR",
        distancias=distancias,
        imagem_url=None,
        inscricoes_abertas=None,
        periodo_inscricao=None,
        fontes=[FonteInfo(
            nome=SOURCE_NAME,
            link_evento=link,
            links_inscricao=[link],
        )],
        miss_count=0,
        first_seen_at=now,
        updated_at=now,
    )


def _strip_tags(s: str) -> str:
    return re.sub(r"<[^>]+>", "", s).strip()


def _extract_distances(text: str) -> list[Distancia]:
    """Parse distance hints like '(10/5km)' or '(1 km (caminhada), 5 e 10 km)'."""
    if not text:
        return []
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
