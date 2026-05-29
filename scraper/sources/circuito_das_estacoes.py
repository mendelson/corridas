"""Scraper for circuitodasestacoes.com.br via hotsites.nortemkt.com/api.

Single API call returns all 27 cities × 4 seasons (Outono/Inverno/Primavera/Verão).
Each city+season pair becomes one Corrida entry.
"""
from __future__ import annotations
import re

from ..http_client import get
from ..models import Corrida, Distancia, FonteInfo
from ..utils import normalize_date, slugify, now_iso
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


def scrape() -> list[Corrida]:
    try:
        resp = get(_API, timeout=15)
        resp.raise_for_status()
        data = resp.json()["data"]["event"]
    except Exception as e:
        print(f"[{SOURCE_NAME}] erro: {e}")
        return []

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
                corrida = _build_corrida(city, loc_slug, estado, stage, now)
                if corrida:
                    corridas.append(corrida)
            except Exception as e:
                print(f"[{SOURCE_NAME}] erro {city}/{stage.get('name')}: {e}")

    print(f"[{SOURCE_NAME}] {len(corridas)} corridas encontradas")
    return corridas


def _build_corrida(
    city: str, loc_slug: str, estado: str, stage: dict, now: str
) -> Corrida | None:
    stage_name: str = stage.get("name", "")
    stage_slug: str = stage.get("slug", "")
    date_raw: str | None = stage.get("date")
    finished: bool = stage.get("finished", False)
    coming_soon: bool = stage.get("coming_soon", False)

    if not stage_name or not date_raw:
        return None

    data_evento = normalize_date(date_raw)
    if not data_evento:
        return None

    # Extract time from ISO datetime if present: "2026-05-10T07:00:00"
    horario: str | None = None
    if date_raw and len(date_raw) > 10:
        mt = re.search(r"[T ](\d{2}):(\d{2})", date_raw)
        if mt:
            h, mi = int(mt.group(1)), int(mt.group(2))
            if 0 <= h <= 23 and 0 <= mi <= 59:
                horario = f"{h:02d}:{mi:02d}"
    # Also check stage-level time field
    if not horario:
        time_raw = stage.get("time") or stage.get("hour") or stage.get("start_time") or ""
        mt2 = re.search(r"(\d{1,2})[hH:]([0-5]\d)", str(time_raw))
        if mt2:
            h, mi = int(mt2.group(1)), int(mt2.group(2))
            if 0 <= h <= 23 and 0 <= mi <= 59:
                horario = f"{h:02d}:{mi:02d}"

    year = data_evento[:4]

    titulo = f"Circuito das Estações - {stage_name} - {city}"

    link_evento = f"{_SITE_BASE}/{loc_slug}/{stage_slug}"
    # RunningLand is the official registration platform
    insc_url = f"{_RL_BASE}/circuito-das-estacoes-{year}-{stage_slug}-{loc_slug}"

    if finished:
        inscricoes_abertas = False
    elif coming_soon:
        inscricoes_abertas = None
    else:
        inscricoes_abertas = True

    distancias = [
        Distancia(km=_parse_km(m["name"]), data=None, horario=None)
        for m in stage.get("modalities", [])
        if _parse_km(m["name"]) is not None
    ]

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
    import re
    m = re.match(r"^(\d+(?:\.\d+)?)\s*k", name, re.IGNORECASE)
    if m:
        return float(m.group(1))
    return None
