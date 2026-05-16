"""Scraper for World Athletics Label Road Races — public HTML page.

Targets the annually-updated labeled road race list at:
  https://worldathletics.org/competitions/world-athletics-label-road-races

The page is a Next.js SSR page.  We extract the embedded __NEXT_DATA__ JSON
from the page HTML and parse competition entries from the page props.

Only events with an IAAF label are included (Platinum, Gold, Silver, Bronze).
Distances are inferred from the competition name.

Note: The WA GraphQL API requires rotating credentials that are embedded in
the site's JS and change periodically — that approach is not maintainable.
This HTML-scraping approach uses the public page directly, with the standard
http_client proxy chain (Scrapestack / Apify) as fallback for Cloudflare.
"""
from __future__ import annotations
import json
import re
from datetime import date, timedelta

from bs4 import BeautifulSoup

from ..http_client import get
from ..models import Corrida, Distancia, FonteInfo
from ..utils import normalize_titulo, slugify, now_iso, today_iso

BASE        = "https://worldathletics.org"
SOURCE_NAME = "World Athletics"

_PAGE_URL   = f"{BASE}/competitions/world-athletics-label-road-races"
_LOOKAHEAD_DAYS = 730  # two years — labeled races announced well in advance

# Text fragments that signal an IAAF label (matched after underscore→space normalisation)
_LABEL_KW: tuple[str, ...] = (
    "platinum", "gold", "silver", "bronze",
    "world athletics label", "iaaf label", "elite label",
)

_NON_RUNNING = re.compile(
    r"\b(triathlon|duathlon|aquathlon|cycling|race\s*walk|marcha\s*atl)",
    re.IGNORECASE,
)

# ISO-2 → Portuguese country name
_ISO_TO_PT: dict[str, str] = {
    "JP": "Japão",    "US": "EUA",         "GB": "Reino Unido",
    "DE": "Alemanha", "FR": "França",       "IT": "Itália",
    "ES": "Espanha",  "KE": "Quênia",       "ET": "Etiópia",
    "MA": "Marrocos", "NG": "Nigéria",      "ZA": "África do Sul",
    "AU": "Austrália","NZ":"Nova Zelândia", "KR": "Coreia do Sul",
    "CN": "China",    "BR": "Brasil",       "AR": "Argentina",
    "CL": "Chile",    "MX": "México",       "NL": "Países Baixos",
    "SE": "Suécia",   "NO": "Noruega",      "DK": "Dinamarca",
    "FI": "Finlândia","BE": "Bélgica",      "AT": "Áustria",
    "CH": "Suíça",    "PL": "Polônia",      "CZ": "República Tcheca",
    "HU": "Hungria",  "GR": "Grécia",       "PT": "Portugal",
    "IE": "Irlanda",  "CA": "Canadá",       "IN": "Índia",
    "AE": "Emirados Árabes", "BH": "Barein", "QA": "Catar",
    "TZ": "Tanzânia", "UG": "Uganda",       "RW": "Ruanda",
    "EG": "Egito",    "CM": "Camarões",     "GH": "Gana",
    "TH": "Tailândia","SG": "Singapura",    "IL": "Israel",
    "TR": "Turquia",  "CO": "Colômbia",     "PE": "Peru",
    "BM": "Bermuda",  "OM": "Omã",          "SA": "Arábia Saudita",
}

# 3-letter IOC/ISO-alpha3 → 2-letter ISO-alpha2 (WA API uses 3-letter codes)
_ISO3_TO_ISO2: dict[str, str] = {
    "CHN": "CN", "ESP": "ES", "USA": "US", "BRA": "BR", "THA": "TH",
    "JPN": "JP", "ITA": "IT", "GER": "DE", "CZE": "CZ", "POR": "PT",
    "GBR": "GB", "FRA": "FR", "KEN": "KE", "ETH": "ET", "MAR": "MA",
    "AUS": "AU", "NZL": "NZ", "KOR": "KR", "NLD": "NL", "SWE": "SE",
    "NOR": "NO", "DNK": "DK", "FIN": "FI", "BEL": "BE", "AUT": "AT",
    "CHE": "CH", "POL": "PL", "HUN": "HU", "GRC": "GR", "IRL": "IE",
    "CAN": "CA", "IND": "IN", "ARE": "AE", "BHR": "BH", "QAT": "QA",
    "TZA": "TZ", "UGA": "UG", "RWA": "RW", "EGY": "EG", "CMR": "CM",
    "GHA": "GH", "THA": "TH", "SGP": "SG", "ISR": "IL", "TUR": "TR",
    "COL": "CO", "PER": "PE", "BMU": "BM", "OMN": "OM", "SAU": "SA",
    "ARG": "AR", "CHL": "CL", "MEX": "MX", "ZAF": "ZA", "NGA": "NG",
    "ALB": "AL", "PRT": "PT", "RSA": "ZA", "ECU": "EC", "VEN": "VE",
    "URY": "UY", "CRI": "CR", "SLO": "SI", "SVK": "SK", "ROU": "RO",
    "BLR": "BY", "UKR": "UA", "SRB": "RS", "CRO": "HR", "SVN": "SI",
}


# ---------------------------------------------------------------------------
def scrape() -> list[Corrida]:
    today_s = today_iso()

    competitions = _fetch_competitions()
    if not competitions:
        print(f"[{SOURCE_NAME}] nenhum dado obtido da página")
        return []

    print(f"[{SOURCE_NAME}] {len(competitions)} competições brutas")

    corridas: list[Corrida] = []
    skipped = 0
    end_date = (date.today() + timedelta(days=_LOOKAHEAD_DAYS)).isoformat()
    for comp in competitions:
        c = _parse_competition(comp, today_s, end_date)
        if c:
            corridas.append(c)
        else:
            skipped += 1

    print(f"[{SOURCE_NAME}] {len(corridas)} corridas válidas ({skipped} ignoradas)")
    return corridas


def _fetch_competitions() -> list[dict]:
    """Fetch the WA label road races page and extract the competition list."""
    try:
        resp = get(_PAGE_URL, source=SOURCE_NAME, timeout=30)
    except Exception as e:
        print(f"[{SOURCE_NAME}] erro ao buscar página: {e}")
        return []

    if resp.status_code != 200:
        print(f"[{SOURCE_NAME}] HTTP {resp.status_code}")
        return []

    # Strategy 1: extract __NEXT_DATA__ embedded JSON
    comps = _parse_next_data(resp.text)
    if comps:
        return comps

    # Strategy 2: parse HTML tables / cards directly
    comps = _parse_html_table(resp.text)
    if comps:
        return comps

    print(f"[{SOURCE_NAME}] nenhuma estrutura de dados reconhecida na página")
    return []


def _parse_next_data(html: str) -> list[dict]:
    """Extract competition list from Next.js __NEXT_DATA__ script tag."""
    soup = BeautifulSoup(html, "lxml")
    tag  = soup.find("script", id="__NEXT_DATA__")
    if not tag or not tag.string:
        return []
    try:
        data = json.loads(tag.string)
    except Exception:
        return []

    pp = data.get("props", {}).get("pageProps", {})

    # Primary: calendarEvents.results (confirmed structure as of 2026)
    cal = pp.get("calendarEvents") or {}
    if isinstance(cal, dict):
        items = cal.get("results") or []
        if isinstance(items, list) and items:
            print(f"[{SOURCE_NAME}] calendarEvents.results: {len(items)} itens")
            return items

    # Fallback: top-level list keys
    for key in ("competitions", "labelRaces", "events", "races", "roadRaces", "results"):
        items = pp.get(key) or []
        if isinstance(items, list) and items:
            print(f"[{SOURCE_NAME}] __NEXT_DATA__['{key}']: {len(items)} itens")
            return items

    # Fallback: nested dicts
    for v in pp.values():
        if isinstance(v, dict):
            for key2 in ("competitions", "events", "races", "results", "items", "data"):
                items = v.get(key2) or []
                if isinstance(items, list) and items:
                    return items
        if isinstance(v, list) and v and isinstance(v[0], dict):
            if any(k in v[0] for k in ("name", "startDate", "venue", "country")):
                return v

    return []


def _parse_html_table(html: str) -> list[dict]:
    """Fallback: try to extract event data from HTML tables or structured divs."""
    soup  = BeautifulSoup(html, "lxml")
    items = []

    # Look for JSON-like data in any script tag
    for script in soup.find_all("script"):
        src = script.string or ""
        if "startDate" in src or "rankingCategory" in src:
            # Try to extract a JSON array from JS assignment
            for m in re.finditer(r'(\[\s*\{.*?\}\s*\])', src, re.DOTALL):
                try:
                    parsed = json.loads(m.group(1))
                    if isinstance(parsed, list) and parsed:
                        if any(k in parsed[0] for k in ("name", "startDate")):
                            items.extend(parsed)
                except Exception:
                    pass

    return items


# ---------------------------------------------------------------------------
def _has_label(comp: dict) -> bool:
    # competitionSubgroup: "Label", "Gold", "Platinum", "Elite" (2026 API)
    # rankingCategory:     "E", "B", "GW", "A", "C", "GL"  (codes)
    # Older/fallback fields may use full text labels.
    subgroup = (comp.get("competitionSubgroup") or "").strip()
    if subgroup:
        return True  # all items returned by this page are WA Label Road Races

    category = (
        comp.get("rankingCategory")
        or comp.get("labelCode")
        or comp.get("label")
        or comp.get("category")
        or ""
    )
    category = str(category).lower().replace("_", " ")
    return any(kw in category for kw in _LABEL_KW)


def _parse_date(raw: str | None) -> str | None:
    if not raw:
        return None
    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})", raw.strip())
    if m:
        return f"{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}"
    return None


def _infer_distances(name: str) -> list[Distancia]:
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


def _parse_competition(comp: dict, today: str, end_date: str) -> Corrida | None:
    name_raw = (comp.get("name") or comp.get("title") or "").strip()
    if not name_raw:
        return None

    titulo = normalize_titulo(name_raw)
    if not titulo or len(titulo) < 4:
        return None

    if _NON_RUNNING.search(titulo):
        return None

    if not _has_label(comp):
        return None

    data_evento = _parse_date(
        comp.get("startDate") or comp.get("start_date") or comp.get("date")
    )
    if not data_evento or data_evento < today or data_evento > end_date:
        return None

    distancias = _infer_distances(titulo)
    if not distancias:
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

    # Location — country field may be 3-letter ISO (e.g. "BRA") or 2-letter ("BR")
    country_raw = comp.get("country") or comp.get("countryCode") or ""
    if isinstance(country_raw, str):
        country_raw = country_raw.strip().upper()
        # Normalise 3-letter IOC/ISO-3166-alpha3 to 2-letter
        pais = _ISO3_TO_ISO2.get(country_raw, country_raw if len(country_raw) == 2 else "INT")
    else:
        pais = "INT"
    country_pt = _ISO_TO_PT.get(pais, pais)

    # venueWithoutCountry is city-only; fall back to venue (may include country in parens)
    city = (comp.get("venueWithoutCountry") or comp.get("venue") or comp.get("city") or "").strip()
    # Strip trailing "  (XXX)" artefact from venueWithoutCountry if present
    city = re.sub(r"\s*\([A-Z]{2,3}\)\s*$", "", city).strip()
    localizacao = ", ".join(p for p in (city, country_pt) if p) or "Internacional"

    comp_id = comp.get("id") or slugify(titulo)
    year    = data_evento[:4]
    # Build URL from slugified name + id (WA URL pattern)
    name_slug = re.sub(r"[^a-z0-9]+", "-", titulo.lower()).strip("-")
    link = (comp.get("url") or comp.get("link")
            or f"{BASE}/competitions/road-running/{name_slug}-{comp_id}")
    if link and not link.startswith("http"):
        link = BASE + ("" if link.startswith("/") else "/") + link

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
