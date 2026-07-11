"""Scraper for circuitodasestacoes.com.br via hotsites.nortemkt.com/api.

Single API call returns all 27 cities × 4 seasons (Outono/Inverno/Primavera/Verão).
Each city+season pair becomes one Corrida entry.

Start times (HORÁRIO DE LARGADA) are not in the stage objects themselves — they
live in the API's `pages` array, nested inside subInfos components.  When not yet
published the value is "Em breve"; in that case the event is skipped (useless for
planning without a known start time).
"""
from __future__ import annotations
import re

from ..http_client import get
from ..models import Corrida, Distancia, FonteInfo
from ..utils import normalize_date, now_iso, today_iso
from .. import geo as _geo

_API = "https://hotsites.nortemkt.com/api/events/circuito-das-estacoes"
_SITE_BASE = "https://www.circuitodasestacoes.com.br"
_RL_BASE = "https://www.runningland.com.br"
SOURCE_NAME = "Circuito das Estações"

_CITY_STATE: dict[str, str] = {
    "São Paulo":            "SP",
    "Rio de Janeiro":       "RJ",
    "Belo Horizonte":       "MG",
    "Brasília":             "DF",
    "Salvador":             "BA",
    "Recife":               "PE",
    "Fortaleza":            "CE",
    "Curitiba":             "PR",
    "Porto Alegre":         "RS",
    "Campinas":             "SP",
    "Florianópolis":        "SC",
    "Manaus":               "AM",
    "Belém":                "PA",
    "Ribeirão Preto":       "SP",
    "São José dos Campos":  "SP",
    "Vitória":              "ES",
    "Palmas":               "TO",
    "Anápolis":             "GO",
    "Cuiabá":               "MT",
    "São Luís":             "MA",
    "Goiânia":              "GO",
    "Imperatriz":           "MA",
    "João Pessoa":          "PB",
    "Teresina":             "PI",
    "Natal":                "RN",
    "Aracaju":              "SE",
    "Campo Grande":         "MS",
}

_TIME_RE = re.compile(r"\b(\d{1,2})[hH:]([0-5]\d)\b")
_KM_TIME_RE = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*[kK][mM]?\s*[–\-:]\s*(\d{1,2})[hH:]([0-5]\d)",
)


def scrape() -> list[Corrida]:
    try:
        resp = get(_API, timeout=15)
        resp.raise_for_status()
        full = resp.json()["data"]
        data = full["event"]
        pages = full.get("pages", [])
    except Exception as e:
        print(f"[{SOURCE_NAME}] erro: {e}")
        return []

    horario_map = _build_horario_map(pages)

    corridas: list[Corrida] = []
    now = now_iso()

    for loc in data.get("locations", []):
        city: str = loc["name"]
        loc_slug: str = loc["slug"]
        estado: str = _CITY_STATE.get(city) or _geo.resolve(city, "", "BR")[1] or ""
        stages = loc.get("stages") or []

        if not stages:
            continue

        for stage in stages:
            try:
                corrida = _build_corrida(city, loc_slug, estado, stage, now, horario_map)
                if corrida:
                    corridas.append(corrida)
            except Exception as e:
                print(f"[{SOURCE_NAME}] erro {city}/{stage.get('name')}: {e}")

    print(f"[{SOURCE_NAME}] {len(corridas)} corridas encontradas")
    return corridas


def _build_horario_map(pages: list) -> dict[tuple[str, str], str]:
    """Extract per-(loc_slug, stage_slug) HORÁRIO DE LARGADA HTML from the pages array."""
    result: dict[tuple[str, str], str] = {}
    for page in pages:
        if page.get("type") != "stage":
            continue
        loc_slug = (page.get("location") or {}).get("slug", "")
        stage_slug = (page.get("stage") or {}).get("slug", "")
        if not loc_slug or not stage_slug:
            continue
        html_value = _find_horario_html(page)
        if html_value is not None:
            result[(loc_slug, stage_slug)] = html_value
    return result


def _find_horario_html(obj) -> str | None:
    """Recursively find the subInfo with title containing 'HORÁRIO' and return its value."""
    if isinstance(obj, dict):
        sub = obj.get("subInfos")
        if sub and isinstance(sub, list):
            for s in sub:
                if "HORÁRIO" in str(s.get("title", "")).upper():
                    return s.get("value") or ""
        for v in obj.values():
            r = _find_horario_html(v)
            if r is not None:
                return r
    elif isinstance(obj, list):
        for item in obj:
            r = _find_horario_html(item)
            if r is not None:
                return r
    return None


def _parse_horario_html(html_value: str) -> str | None:
    """Return the earliest HH:MM start time from an HORÁRIO DE LARGADA HTML string.

    Returns None when time is not yet published ("Em breve" or no valid time found).
    """
    text = re.sub(r"<[^>]+>", " ", html_value).replace("&nbsp;", " ").strip()
    if not text or "em breve" in text.lower():
        return None
    minutes: list[int] = []
    for m in _TIME_RE.finditer(text):
        h, mi = int(m.group(1)), int(m.group(2))
        if 4 <= h <= 23 and 0 <= mi <= 59:
            minutes.append(h * 60 + mi)
    if not minutes:
        return None
    earliest = min(minutes)
    return f"{earliest // 60:02d}:{earliest % 60:02d}"


def _parse_per_dist_horarios(html_value: str) -> dict[float, str]:
    """Parse per-distance start times from the HORÁRIO HTML value.

    Example input: "<p>13km: 06h00</p><p>10km: 06h45</p><p>5km: 07h40</p>"
    Returns: {13.0: "06:00", 10.0: "06:45", 5.0: "07:40"}
    """
    text = re.sub(r"<[^>]+>", " ", html_value).replace("&nbsp;", " ")
    result: dict[float, str] = {}
    for m in _KM_TIME_RE.finditer(text):
        try:
            km = float(m.group(1).replace(",", "."))
        except ValueError:
            continue
        h, mi = int(m.group(2)), int(m.group(3))
        if 4 <= h <= 23 and 0 <= mi <= 59 and 1 <= km <= 250:
            result[km] = f"{h:02d}:{mi:02d}"
    return result


def _build_corrida(
    city: str, loc_slug: str, estado: str, stage: dict, now: str,
    horario_map: dict[tuple[str, str], str],
) -> Corrida | None:
    stage_name: str = stage.get("name", "")
    stage_slug: str = stage.get("slug", "")
    date_raw: str | None = stage.get("date")
    finished: bool = stage.get("finished", False)
    coming_soon: bool = stage.get("coming_soon", False)

    if not stage_name or not date_raw:
        return None

    data_evento = normalize_date(date_raw)
    if not data_evento or data_evento < today_iso():
        return None

    # Look up published start time from the pages data
    horario_html = horario_map.get((loc_slug, stage_slug), "")
    horario = _parse_horario_html(horario_html)
    # Horário no longer mandatory (policy 2026-07-11): keep the event without it.
    # if horario is None:
    #     return None  # start time not yet published — skip until it is

    per_dist = _parse_per_dist_horarios(horario_html)

    year = data_evento[:4]

    titulo = f"Circuito das Estações - {stage_name} - {city}"

    link_evento = f"{_SITE_BASE}/{loc_slug}/{stage_slug}"
    insc_url = f"{_RL_BASE}/circuito-das-estacoes-{year}-{stage_slug}-{loc_slug}"

    if finished:
        inscricoes_abertas = False
    elif coming_soon:
        inscricoes_abertas = None
    else:
        inscricoes_abertas = True

    distancias: list[Distancia] = []
    for m in stage.get("modalities", []):
        km = _parse_km(m["name"])
        if km is None:
            continue
        dist_horario = per_dist.get(km)
        distancias.append(Distancia(km=km, data=None, horario=dist_horario))

    if not distancias:
        return None

    return Corrida(
        id=f"circuito-das-estacoes-{loc_slug}-{stage_slug}",
        titulo=titulo,
        data_evento=data_evento,
        horario=horario,
        localizacao=f"{city}, {estado}" if estado else city,
        cidade=city,
        estado=estado,
        pais="BR",
        distancias=distancias,
        imagem_url=None,
        inscricoes_abertas=inscricoes_abertas,
        periodo_inscricao=None,
        fontes=[FonteInfo(
            nome=SOURCE_NAME,
            link_evento=link_evento,
            links_inscricao=[insc_url],
            tipo="organizador",
        )],
        miss_count=0,
        first_seen_at=now,
        updated_at=now,
    )


def _parse_km(name: str) -> float | None:
    """'5k' → 5.0, '21k' → 21.0, '13k' → 13.0, etc."""
    m = re.match(r"^(\d+(?:\.\d+)?)\s*k", name, re.IGNORECASE)
    if m:
        return float(m.group(1))
    return None
