"""Scraper for World Athletics Competition Calendar — IAAF Label Road Races.

Targets Platinum, Gold, Silver and Bronze Label road races worldwide from the
World Athletics official competition calendar.

Strategy:
  1. POST a GraphQL query to the public WA API endpoint to get labeled road
     race competitions. Falls back to the HTML label-road-races page if the
     API fails.
  2. Filter client-side: road-running disciplines only, IAAF label required.
  3. Infer distances from competition name (marathon, half, 10K, 5K…).

Note: The WA GraphQL API uses POST with a well-known operationName and
schema; this is the same endpoint the WA website itself uses.
"""
from __future__ import annotations
import re
from datetime import date, timedelta

import httpx

from ..http_client import HEADERS, TIMEOUT
from ..models import Corrida, Distancia, FonteInfo
from ..utils import normalize_titulo, slugify, now_iso, today_iso

BASE        = "https://worldathletics.org"
SOURCE_NAME = "World Athletics"

_LOOKAHEAD_DAYS = 730   # two years ahead — majors announce early
_PAGE_SIZE      = 100

_GQL_ENDPOINT = f"{BASE}/api/graphql/query"

# Road-running WA discipline codes
_ROAD_DISC: set[str] = {"RD", "MAR", "HMR"}

# Text fragments that indicate an IAAF label (case-insensitive substring match)
_LABEL_KW: tuple[str, ...] = (
    "platinum", "gold label", "silver label", "bronze label",
    "world athletics label", "iaaf label", "elite label",
)

_NON_RUNNING = re.compile(
    r"\b(triathlon|duathlon|aquathlon|cycling|race\s*walk|marcha\s*atl)",
    re.IGNORECASE,
)

# ISO-2 → Portuguese country name
_ISO_TO_PT: dict[str, str] = {
    "JP": "Japão",       "US": "EUA",            "GB": "Reino Unido",
    "DE": "Alemanha",    "FR": "França",          "IT": "Itália",
    "ES": "Espanha",     "KE": "Quênia",          "ET": "Etiópia",
    "MA": "Marrocos",    "NG": "Nigéria",          "ZA": "África do Sul",
    "AU": "Austrália",   "NZ": "Nova Zelândia",   "KR": "Coreia do Sul",
    "CN": "China",       "BR": "Brasil",           "AR": "Argentina",
    "CL": "Chile",       "MX": "México",           "NL": "Países Baixos",
    "SE": "Suécia",      "NO": "Noruega",          "DK": "Dinamarca",
    "FI": "Finlândia",   "BE": "Bélgica",          "AT": "Áustria",
    "CH": "Suíça",       "PL": "Polônia",          "CZ": "República Tcheca",
    "HU": "Hungria",     "GR": "Grécia",           "PT": "Portugal",
    "IE": "Irlanda",     "CA": "Canadá",           "IN": "Índia",
    "AE": "Emirados Árabes", "BH": "Barein",       "QA": "Catar",
    "TZ": "Tanzânia",    "UG": "Uganda",           "RW": "Ruanda",
    "EG": "Egito",       "CM": "Camarões",         "GH": "Gana",
    "TH": "Tailândia",   "SG": "Singapura",        "MY": "Malásia",
    "IL": "Israel",      "TR": "Turquia",           "RU": "Rússia",
    "UA": "Ucrânia",     "RO": "Romênia",          "HR": "Croácia",
    "OM": "Omã",         "KW": "Kuwait",           "SA": "Arábia Saudita",
    "CO": "Colômbia",    "PE": "Peru",             "EC": "Equador",
    "BO": "Bolívia",     "PY": "Paraguai",         "UY": "Uruguai",
}

# GraphQL query using the same shape the WA website sends
_GQL_QUERY = """
query GetCalendarEvents(
  $startDate: String
  $endDate: String
  $regionType: String
  $disciplineCode: String
  $currentPage: Int
  $pageSize: Int
) {
  getCalendarEvents(
    startDate: $startDate
    endDate: $endDate
    regionType: $regionType
    disciplineCode: $disciplineCode
    currentPage: $currentPage
    pageSize: $pageSize
  ) {
    currentPage
    pageSize
    totalCount
    competitions {
      id
      name
      startDate
      endDate
      venue
      rankingCategory
      disciplines {
        name
        disciplineCode
      }
      country {
        name
        code
      }
    }
  }
}
"""


# ---------------------------------------------------------------------------
def scrape() -> list[Corrida]:
    today_s = today_iso()
    start   = date.today().strftime("%Y-%m-%d")
    end     = (date.today() + timedelta(days=_LOOKAHEAD_DAYS)).strftime("%Y-%m-%d")

    competitions = _fetch_all(start, end)
    if not competitions:
        print(f"[{SOURCE_NAME}] nenhum resultado da API")
        return []

    print(f"[{SOURCE_NAME}] {len(competitions)} competições brutas")

    corridas: list[Corrida] = []
    skipped = 0
    for comp in competitions:
        c = _parse_competition(comp, today_s)
        if c:
            corridas.append(c)
        else:
            skipped += 1

    print(f"[{SOURCE_NAME}] {len(corridas)} corridas válidas ({skipped} ignoradas)")
    return corridas


def _fetch_all(start: str, end: str) -> list[dict]:
    result: list[dict] = []
    page = 1
    while True:
        batch = _fetch_page(start, end, page)
        if batch is None:
            break
        comps     = batch.get("competitions") or []
        total     = batch.get("totalCount") or 0
        page_size = batch.get("pageSize") or _PAGE_SIZE
        result.extend(comps)
        print(f"[{SOURCE_NAME}] página {page}: {len(comps)} eventos (total={total})")
        if not comps or len(result) >= total or len(comps) < page_size:
            break
        page += 1
    return result


def _fetch_page(start: str, end: str, page: int) -> dict | None:
    payload = {
        "operationName": "GetCalendarEvents",
        "query": _GQL_QUERY,
        "variables": {
            "startDate":      start,
            "endDate":        end,
            "regionType":     "world",
            "disciplineCode": "RD",
            "currentPage":    page,
            "pageSize":       _PAGE_SIZE,
        },
    }
    gql_headers = {
        **HEADERS,
        "Content-Type": "application/json",
        "Accept":        "application/json",
        "x-app-type":   "web",
    }
    try:
        resp = httpx.post(
            _GQL_ENDPOINT,
            json=payload,
            headers=gql_headers,
            follow_redirects=True,
            timeout=TIMEOUT,
        )
    except Exception as e:
        print(f"[{SOURCE_NAME}] erro HTTP página {page}: {e}")
        return None

    if resp.status_code != 200:
        print(f"[{SOURCE_NAME}] HTTP {resp.status_code} página {page}")
        return None

    try:
        data = resp.json()
    except Exception as e:
        print(f"[{SOURCE_NAME}] JSON inválido página {page}: {e}")
        return None

    if page == 1:
        errors = data.get("errors")
        if errors:
            print(f"[{SOURCE_NAME}] erros GraphQL: {errors}")

    return (
        (data.get("data") or {}).get("getCalendarEvents")
        or data.get("getCalendarEvents")
        or {}
    )


# ---------------------------------------------------------------------------
def _is_road_running(comp: dict) -> bool:
    disciplines = comp.get("disciplines") or []
    for d in disciplines:
        code = (d.get("disciplineCode") or d.get("code") or "").upper()
        name = (d.get("name") or "").lower()
        if code in _ROAD_DISC:
            return True
        if any(kw in name for kw in ("road", "marathon", "half marathon")):
            return True
    if not disciplines:
        # API was queried with disciplineCode=RD so absence is fine
        return True
    return False


def _has_label(comp: dict) -> bool:
    # rankingCategory may be "GOLD_LABEL_ROAD_RACE" or "Gold Label" — normalise both
    category = (comp.get("rankingCategory") or "").lower().replace("_", " ")
    return any(kw in category for kw in _LABEL_KW)


def _parse_date(raw: str | None) -> str | None:
    if not raw:
        return None
    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})", raw.strip())
    if m:
        return f"{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}"
    return None


def _infer_distances(name: str) -> list[Distancia]:
    """Infer race distances from competition name."""
    name_l = name.lower()
    dists: list[float | str] = []

    if "marathon" in name_l and "half" not in name_l:
        dists.append(42.195)
    if "half marathon" in name_l or "half-marathon" in name_l or "21k" in name_l:
        dists.append(21.097)

    for m in re.finditer(r"\b(\d+(?:\.\d+)?)\s*k(?:m)?\b", name_l):
        try:
            dists.append(float(m.group(1)))
        except ValueError:
            pass

    for m in re.finditer(r"\b(\d+(?:\.\d+)?)\s*mi(?:le)?\b", name_l):
        try:
            n = float(m.group(1))
            dists.append(f"{int(n) if n.is_integer() else n:g} mi")
        except ValueError:
            pass

    seen: set = set()
    result: list[Distancia] = []
    for km in dists:
        key = km if isinstance(km, str) else round(float(km), 3)
        if key not in seen:
            seen.add(key)
            result.append(Distancia(km=km, data=None, horario=None))
    return result


def _parse_competition(comp: dict, today: str) -> Corrida | None:
    name_raw = (comp.get("name") or "").strip()
    if not name_raw:
        return None

    titulo = normalize_titulo(name_raw)
    if not titulo or len(titulo) < 4:
        return None

    if _NON_RUNNING.search(titulo):
        return None

    if not _is_road_running(comp):
        return None

    if not _has_label(comp):
        return None

    data_evento = _parse_date(comp.get("startDate") or comp.get("endDate"))
    if not data_evento or data_evento < today:
        return None

    distancias = _infer_distances(titulo)
    if not distancias:
        # Infer from keywords when no distance appears in the title
        name_l = titulo.lower()
        if "marathon" in name_l and "half" not in name_l:
            distancias = [Distancia(km=42.195, data=None, horario=None)]
        elif "half" in name_l:
            distancias = [Distancia(km=21.097, data=None, horario=None)]
        elif "10k" in name_l or "10 km" in name_l:
            distancias = [Distancia(km=10.0, data=None, horario=None)]
        elif "5k" in name_l or "5 km" in name_l:
            distancias = [Distancia(km=5.0, data=None, horario=None)]
        else:
            return None

    country_info = comp.get("country") or {}
    pais         = (country_info.get("code") or "").strip().upper() or "INT"
    country_name = (country_info.get("name") or "").strip()
    country_pt   = _ISO_TO_PT.get(pais, country_name or pais)

    venue      = (comp.get("venue") or "").strip()
    localizacao = ", ".join(p for p in (venue, country_pt) if p) or "Internacional"

    comp_id = comp.get("id") or slugify(titulo)
    year    = data_evento[:4]
    link    = f"{BASE}/competition/{slugify(titulo)}/{comp_id}"

    now = now_iso()
    return Corrida(
        id=f"worldathletics_{comp_id}_{year}",
        titulo=titulo,
        data_evento=data_evento,
        horario=None,
        localizacao=localizacao,
        cidade=localizacao,
        estado="",
        pais=pais,
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
