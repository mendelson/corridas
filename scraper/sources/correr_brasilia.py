"""Scraper for correrbrasilia.com.br/calendario/

Parses JSON-LD schema.org/Event blocks embedded by the EventOn WordPress
plugin — more reliable than trying to parse the calendar widget's HTML.
"""
from __future__ import annotations
import json
import re
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup

from ..http_client import get
from ..models import Corrida, Distancia, FonteInfo
from ..utils import normalize_titulo, slugify, now_iso, today_iso
from .. import geo as _geo

URL = "https://correrbrasilia.com.br/calendario/"
SOURCE_NAME = "Correr Brasília"

# Freeform "..., Cidade - UF, 00000-000" address tail (Correr Brasília's JSON-LD
# often omits addressLocality/addressRegion but keeps the city/UF in streetAddress).
_CITY_UF_RE = re.compile(r"([A-Za-zÀ-ÿ.'\s]+?)\s*-\s*([A-Z]{2})\s*,?\s*\d{5}-?\d{3}")
_CITY_UF_NOCEP_RE = re.compile(r",\s*([A-Za-zÀ-ÿ.'\s]+?)\s*-\s*([A-Z]{2})\b")


def _city_uf_from_street(street: str) -> tuple[str, str]:
    """Extract (city, UF) from a freeform Brazilian street address, or ("","")."""
    if not street:
        return "", ""
    m = _CITY_UF_RE.search(street) or _CITY_UF_NOCEP_RE.search(street)
    if not m:
        return "", ""
    return m.group(1).strip(" ,-"), m.group(2).upper()


# EventOn HTML location field ("Beira Rio, Pirenópolis-GO", "Praça X, Formosa - GO"):
# the trailing "Cidade-UF" segment. Used as fallback when the event's JSON-LD
# location is null — which happens even when the page shows the venue.
_LOCLINE_UF_RE = re.compile(r"([A-Za-zÀ-ÿ.'\s]+?)\s*[-–]\s*([A-Z]{2})\s*$")


def _city_uf_from_locline(locline: str) -> tuple[str, str]:
    last = locline.split(",")[-1].strip()
    m = _LOCLINE_UF_RE.search(last)
    if not m:
        return "", ""
    return m.group(1).strip(" ,-"), m.group(2).upper()


_TIME_RE = re.compile(
    r"\b(\d{1,2})[hH:]([0-5]\d)\s*(?:min\s*)?[hH]?\b(?!\s*[kK])"
    r"|\b(\d{1,2})\s*[hH]\b(?!\s*\d)",
    re.IGNORECASE,
)


def _fetch_event_page(url: str, use_playwright: bool = False) -> tuple[list[Distancia], str | None, str | None]:
    """Fetch the individual event page and extract distances, horario and the
    external registration link (EventOn "Learn More" → the real inscription
    platform, e.g. esportes.agenciasisters.com.br)."""
    html_text: str | None = None
    try:
        resp = get(url)
        if resp.status_code == 200:
            html_text = resp.text
    except Exception:
        pass
    if not html_text and use_playwright:
        try:
            from ..playwright_client import get_page_html
            html_text = get_page_html(url, timeout=20_000)
        except Exception:
            pass
    if not html_text:
        return [], None, None
    try:
        soup = BeautifulSoup(html_text, "lxml")
        reg_link = _extract_registration_link(soup)
        # Try JSON-LD first
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "")
            except Exception:
                continue
            if not isinstance(data, dict) or data.get("@type") != "Event":
                continue
            desc = data.get("description") or ""
            dists = _extract_distances(desc)
            _, horario = _parse_start_date(data.get("startDate") or "")
            if dists:
                return dists, horario, reg_link
        # Fallback: parse free text
        text = soup.get_text(" ", strip=True)
        dists = _extract_distances(text)
        horario = _extract_horario(text)
        return dists, horario, reg_link
    except Exception:
        return [], None, None


def _extract_registration_link(soup: BeautifulSoup) -> str | None:
    """EventOn stores the organizer's external link (registration page) in the
    "Learn More" row: <a class="evcal_evdata_row evo_clik_row" href="..."> inside
    #event_learnmore (.evo_metarow_learnmore). Return it when it's a real external
    URL (not correrbrasilia itself, not a social network).

    Scoped strictly to the Learn More container: other EventOn rows (location/map,
    organizer) also use `a.evo_clik_row` and can render first, so a page-wide
    `a.evo_clik_row` scan would attach a map/organizer URL as the registration."""
    for a in soup.select(
        "#event_learnmore a[href], .evo_metarow_learnmore a[href]"
    ):
        href = (a.get("href") or "").strip()
        if href.startswith("http") and _is_external_registration(href):
            return href
    return None


def _is_external_registration(url: str) -> bool:
    host = urlparse(url).netloc.lower().removeprefix("www.")
    if not host or "correrbrasilia.com.br" in host:
        return False
    return not any(s in host for s in _SOCIAL_HOSTS)


_SOCIAL_HOSTS = (
    "facebook.", "instagram.", "twitter.", "x.com", "youtube.", "youtu.be",
    "whatsapp.", "wa.me", "t.me", "tiktok.", "linkedin.", "strava.",
)

# Map known registration/inscription platforms to a display name + tipo so the
# extracted "Learn More" link is attributed correctly (the frontend orders
# inscricao buttons first). Unknown domains → name derived from the domain,
# tipo="inscricao" (the Learn More link is the organizer's registration page).
_REG_DOMAIN_MAP: list[tuple[str, str, str]] = [
    ("agenciasisters.com.br",   "Agência Sisters",    "inscricao"),
    ("ticketsports.com.br",     "Ticket Sports",      "inscricao"),
    ("ticketagora.com.br",      "Ticket Sports",      "inscricao"),
    ("sympla.com.br",           "Sympla",             "inscricao"),
    ("ativo.com",               "Ativo",              "inscricao"),
    ("minhasinscricoes.com.br", "Minhas Inscrições",  "inscricao"),
    ("doity.com.br",            "Doity",              "inscricao"),
    ("e-inscricao.com",         "e-Inscrição",        "inscricao"),
    ("brasilcorrida.com.br",    "Brasil Corrida",     "calendario"),
    ("centraldacorrida.com.br", "Central da Corrida", "calendario"),
]


def _registration_fonte(url: str) -> FonteInfo | None:
    """Build an inscription FonteInfo for an extracted external registration URL."""
    host = urlparse(url).netloc.lower().removeprefix("www.")
    nome, tipo = None, "inscricao"
    for frag, n, t in _REG_DOMAIN_MAP:
        if frag in host:
            nome, tipo = n, t
            break
    if nome is None:
        # e.g. "esportes.agenciasisters.com.br" → "Agenciasisters"
        parts = host.split(".")
        base = parts[-3] if len(parts) >= 3 else parts[0]
        nome = base.replace("-", " ").title() or "Inscrição"
    return FonteInfo(nome=nome, link_evento=url, links_inscricao=[url], tipo=tipo)


def _extract_horario(text: str) -> str | None:
    if not text:
        return None
    m = _TIME_RE.search(text)
    if not m:
        return None
    if m.group(1) is not None:
        h, mi = int(m.group(1)), int(m.group(2))
    else:
        h, mi = int(m.group(3)), 0
    if 4 <= h <= 23 and 0 <= mi <= 59:
        return f"{h:02d}:{mi:02d}"
    return None


def scrape() -> list[Corrida]:
    html_text: str | None = None
    used_playwright = False
    try:
        resp = get(URL)
        resp.raise_for_status()
        html_text = resp.text
    except Exception as e:
        print(f"[{SOURCE_NAME}] proxy chain falhou: {e}; tentando Playwright...")
        try:
            from ..playwright_client import get_page_html
            html_text = get_page_html(URL, timeout=30_000)
            if html_text:
                used_playwright = True
                print(f"[{SOURCE_NAME}] Playwright ok para {URL}")
        except Exception as e2:
            print(f"[{SOURCE_NAME}] Playwright falhou: {e2}")

    if not html_text:
        print(f"[{SOURCE_NAME}] todos os métodos falharam para {URL}")
        return []

    soup = BeautifulSoup(html_text, "lxml")
    today = today_iso()
    now = now_iso()

    # EventOn renders each row's venue in the HTML (em.evcal_location[data-n])
    # even when the corresponding JSON-LD block has location: null. Map event
    # URL → location line so _parse_event can fall back to it.
    html_loc_map: dict[str, str] = {}
    for em in soup.select("em.evcal_location[data-n]"):
        loc = (em.get("data-n") or "").strip()
        a = em.find_parent("a", href=True)
        if loc and a:
            html_loc_map[a["href"]] = loc

    # First pass: parse all JSON-LD events from the listing page
    candidates: list[dict] = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except Exception:
            continue
        if not isinstance(data, dict) or data.get("@type") != "Event":
            continue
        candidates.append(data)

    corridas: list[Corrida] = []
    seen_ids: set[str] = set()

    # Fetch each event's detail page once: it carries the external registration
    # link (EventOn "Learn More" → the real inscription platform) and backfills
    # any distances/horario the listing JSON-LD omitted.
    # Lower concurrency when using Playwright to avoid resource exhaustion.
    to_fetch: list[str] = []
    seen_urls: set[str] = set()
    for data in candidates:
        url = data.get("url") or ""
        if url and url != URL and url not in seen_urls:
            seen_urls.add(url)
            to_fetch.append(url)

    max_workers = 3 if used_playwright else 8
    detail_map: dict[str, tuple[list[Distancia], str | None, str | None]] = {}
    if to_fetch:
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            futures = {ex.submit(_fetch_event_page, u, used_playwright): u for u in to_fetch}
            for fut in as_completed(futures):
                url = futures[fut]
                try:
                    detail_map[url] = fut.result()
                except Exception:
                    detail_map[url] = ([], None, None)

    for data in candidates:
        try:
            c = _parse_event(data, today, now, html_loc_map.get(data.get("url") or "", ""))
        except Exception as e:
            print(f"[{SOURCE_NAME}] erro ao parsear evento: {e}")
            continue
        if c is None:
            continue

        event_url = data.get("url") or ""
        if event_url in detail_map:
            extra_dists, extra_horario, reg_link = detail_map[event_url]
            if not c.distancias and extra_dists:
                c = _replace_distancias(c, extra_dists)
            if not c.horario and extra_horario:
                c = _replace_horario(c, extra_horario)
            # Attach the real registration platform as an inscription source.
            if reg_link:
                reg = _registration_fonte(reg_link)
                if reg and all(f.nome != reg.nome for f in c.fontes):
                    c.fontes.append(reg)

        if not c.distancias:
            print(f"[{SOURCE_NAME}] sem distâncias, pulando: {c.titulo!r}")
            continue
        if not c.horario:
            print(f"[{SOURCE_NAME}] sem horário, pulando: {c.titulo!r}")
            continue

        if c.id not in seen_ids:
            seen_ids.add(c.id)
            corridas.append(c)

    print(f"[{SOURCE_NAME}] {len(corridas)} corridas encontradas")
    return corridas


def _replace_distancias(c: "Corrida", dists: list[Distancia]) -> "Corrida":
    from dataclasses import replace
    return replace(c, distancias=dists)


def _replace_horario(c: "Corrida", horario: str) -> "Corrida":
    from dataclasses import replace
    return replace(c, horario=horario)


def _parse_event(ev: dict, today: str, now: str, html_loc: str = "") -> Corrida | None:
    titulo_raw = normalize_titulo(ev.get("name") or "")
    if not titulo_raw or len(titulo_raw) < 3:
        return None
    # Keep the parenthetical distances in the title — it distinguishes entries like
    # "Live!42K - Brasília 2026 (5km e 10km)" from "Live!42K - Brasília 2026 (21km e 42km)".
    # Stripping them caused the merger to collapse distinct events with different distances.
    titulo = titulo_raw

    if _NON_RUNNING_RE.search(titulo_raw):
        return None  # orienteering / non-running event
    if _KIDS_RE.search(titulo_raw):
        return None  # kids-only event (e.g. Marotinga) — no adult distances

    date_str, horario = _parse_start_date(ev.get("startDate") or "")
    if date_str and date_str < today:
        return None

    # Use EventOn @id ("event_44938_0") when present for a stable key;
    # otherwise fall back to slug+year so IDs never embed the run date.
    eid = ev.get("@id") or ""
    if eid and re.match(r"event_\d+", eid):
        stable_id = f"correrbsb_{eid}"
    else:
        year = date_str[:4] if date_str else "sd"
        stable_id = f"correrbsb_{slugify(titulo[:50])}_{year}"

    url = ev.get("url") or URL
    image = ev.get("image") or None

    location_raw = ev.get("location") or []
    if isinstance(location_raw, dict):
        location_raw = [location_raw]
    place = location_raw[0] if location_raw else {}
    place_name = place.get("name") or ""
    address = place.get("address") or {}
    street = address.get("streetAddress") or ""

    address_locality = address.get("addressLocality") or ""
    address_region = address.get("addressRegion") or ""

    # This is a Brasília-focused calendar, but it also lists events held
    # elsewhere (e.g. a Goiânia marathon). The structured addressLocality/
    # addressRegion fields are frequently empty even when the freeform
    # streetAddress carries the real "Cidade - UF, CEP" — defaulting those to
    # Brasília/DF mislocated out-of-DF events. So parse the street address
    # (a structured field) before falling back, and only assume Brasília when
    # there is no address information at all.
    street_city, street_uf = _city_uf_from_street(street)

    city = address_locality or street_city
    estado = _geo.validate_estado("BR", address_region.strip()) if address_region else ""
    if not estado and street_uf:
        estado = _geo.validate_estado("BR", street_uf)
    if not estado:
        geo_query = ", ".join(p for p in [city, place_name, street] if p)
        if geo_query:
            _, estado = _geo.resolve(geo_query, "", "BR")

    # JSON-LD came empty/useless but the page's HTML row names the venue
    # ("Beira Rio, Pirenópolis-GO") — explicit data beats any default.
    if (not city or not estado) and html_loc:
        h_city, h_uf = _city_uf_from_locline(html_loc)
        if h_uf and _geo.validate_estado("BR", h_uf):
            if not estado:
                estado = h_uf
            if not city and h_city:
                city = h_city

    if not city and not estado:
        # No usable address anywhere → this DF calendar's safe default.
        city, estado = "Brasília", "DF"
    elif not city:
        city = "Brasília" if estado == "DF" else (place_name or "")
    elif not estado:
        _, estado = _geo.resolve(f"{city}", "", "BR")

    localizacao = ", ".join(p for p in (city, estado) if p) or "Brasília, DF"

    desc = ev.get("description") or ""
    distancias = _extract_distances(desc)

    return Corrida(
        id=stable_id,
        titulo=titulo,
        data_evento=date_str or "",
        horario=horario,
        localizacao=localizacao,
        cidade=city,
        estado=estado,
        pais="BR",
        distancias=distancias,
        imagem_url=image,
        inscricoes_abertas=None,
        periodo_inscricao=None,
        fontes=[FonteInfo(
            nome=SOURCE_NAME,
            link_evento=url,
            links_inscricao=[url],
            tipo="calendario",
        )],
        miss_count=0,
        first_seen_at=now,
        updated_at=now,
    )


def _parse_start_date(raw: str) -> tuple[str, str | None]:
    """Parse "2026-8-8T16:00-3:00" → ("2026-08-08", "16:00")."""
    if not raw:
        return "", None
    m = re.match(r"(\d{4})-(\d{1,2})-(\d{1,2})T(\d{2}:\d{2})", raw)
    if not m:
        return "", None
    year, month, day, time_part = m.groups()
    return f"{year}-{int(month):02d}-{int(day):02d}", time_part


# Canonical distance windows: snap noisy values from descriptions
# to the exact standard distance (matches ativo.py / mks_esportes.py).
_CANONICAL = [(42.195, 41.5, 43.0), (21.097, 20.5, 21.5)]

# Orienteering and other non-running events — skip silently
_NON_RUNNING_RE = re.compile(
    r"\borientak?[çc]|\bse orienta\b|\bbuss?ola\b|\borienteering\b"
    r"|\bciclismo\b|\bbike\b|\bnatação\b|\btriathlon\b",
    re.IGNORECASE,
)

# Kids-only events — no adult distances exist for these. "Marotinga" is a
# Brasília kids-run brand whose title carries no "kids"/"infantil" marker,
# so it must be matched by name. Mirrors central_da_corrida._KIDS_RE.
_KIDS_RE = re.compile(
    r"\bkids?\b|\binfantil\b|\bmarotinga\b|\bpezinho\s+veloz\b",
    re.IGNORECASE,
)

# Named distances ("meia maratona", "maratona") and their English forms. Half is
# matched first and stripped before the full-marathon check so "meia maratona"
# never also counts as a full marathon.
_HALF_MARATHON_RE = re.compile(r"meia[\s-]?maratona|half[\s-]?marathon", re.IGNORECASE)
_FULL_MARATHON_RE = re.compile(r"\bmaratona\b|\bmarathon\b", re.IGNORECASE)

# A single distance "token": an explicit numeric km value OR a named distance.
# Named distances are first-class distance values — but only when they appear as a
# token inside a distance enumeration (a list element or a labelled value), never
# loose in prose. That distinction is what keeps "a maior maratona de corrida de
# rua do DF" (colloquial) from injecting a phantom 42.195 km.
_DIST_TOKEN = (
    r"(?:meia[\s-]?maratona|half[\s-]?marathon|maratona|marathon"
    r"|\d+(?:[.,]\d+)?\s*[kK][mM]?)"
)

# A distance list: two or more tokens joined by connectors,
# e.g. "5km, 10km e 21km" or "5km, 10km e meia maratona".
_DIST_LIST_RE = re.compile(
    rf"{_DIST_TOKEN}(?:\s*(?:,|;|/|\||\be\b|\bou\b)\s*{_DIST_TOKEN})+",
    re.IGNORECASE,
)

# A labelled single distance: "Distância: Maratona", "Modalidade: 42km".
_DIST_LABEL = r"dist[âa]ncias?|modalidades?|percursos?|provas?|categorias?|trajetos?"
_DIST_LABELLED_RE = re.compile(
    rf"(?:{_DIST_LABEL})\s*:?\s*({_DIST_TOKEN})",
    re.IGNORECASE,
)

# Matches "5 e 10 km" (shared km suffix) — extremely common in Brazilian Portuguese
# e.g. "provas de 5 e 10 km", "distâncias de 5, 10 e 21km"
_DIST_SHARED_SUFFIX_RE = re.compile(
    r"(\d+(?:[.,]\d+)?)"
    r"(?:\s*(?:,|e|ou)\s*(\d+(?:[.,]\d+)?))+"
    r"\s*[kK][mM]?\b",
    re.IGNORECASE,
)


def _token_to_km(tok: str) -> float | None:
    """Convert one distance token (numeric km or a named distance) to kilometres."""
    t = tok.strip().lower()
    if _HALF_MARATHON_RE.search(t):
        return 21.097
    if _FULL_MARATHON_RE.search(t):
        return 42.195
    m = re.match(r"(\d+(?:[.,]\d+)?)", t)
    if m:
        try:
            return float(m.group(1).replace(",", "."))
        except ValueError:
            return None
    return None




# Hydration/support-interval phrases mention distances that are NOT race
# distances ("Pontos de hidratação a cada 3,5km") — strip them before any
# extraction pass, mirroring mks_esportes. Without this, Desafio das Torres
# (10km/21km) gained a phantom 3.5km distance.
_INTERVAL_RE = re.compile(
    r"a cada \d+(?:[.,]\d+)?\s*k(?:m)?\b"
    r"|cada \d+(?:[.,]\d+)?\s*k(?:m)?\b"
    r"|\d+(?:[.,]\d+)?\s*k(?:m)?\s*"
    r"(?:de hidrat|de água|de abastec|de extens|de altimetria|de desn[íi]vel|de eleva)",
    re.IGNORECASE,
)


def _extract_distances(desc: str) -> list[Distancia]:
    """Extract race distances from the event's dedicated distance enumeration.

    Distances come from the description, where the EventOn plugin embeds the
    "Distância: Xkm e Ykm" metadata. We never infer a distance from the event
    title or from free prose — the words "maratona"/"marathon" appear colloquially
    in descriptions ("a maior maratona de corrida de rua do DF") and previously
    injected a phantom 42.195 km into events that don't offer one.

    Named distances are honoured only when they are an actual enumeration token —
    a list element ("5km, 10km e meia maratona") or a labelled value
    ("Modalidade: Maratona") — and normalised to their canonical length:
        "meia maratona" / "half marathon" → 21.097 km
        "maratona" / "marathon"           → 42.195 km
    Numeric values are canonical-snapped so 42 / 42,2 / 42.195 km collapse to a
    single distance (likewise 21 / 21,1 / 21.097).
    """
    desc = _INTERVAL_RE.sub(" ", desc)

    raw: list[float] = []

    # 1. Distance lists (2+ tokens) — the most reliable enumeration. Tokens may be
    #    numeric ("10km") or named ("meia maratona") as long as they are list members.
    for list_m in _DIST_LIST_RE.finditer(desc):
        for tok_m in re.finditer(_DIST_TOKEN, list_m.group(0), re.IGNORECASE):
            km = _token_to_km(tok_m.group(0))
            if km is not None:
                raw.append(km)
    # 2. Shared km suffix ("5 e 10 km") — numbers sharing a single trailing km.
    raw.extend(_parse_shared_suffix(desc, min_km=1.0, snap=False))

    if not raw:
        # 3. Labelled single distance ("Modalidade: Maratona", "Distância: 42km").
        for lab_m in _DIST_LABELLED_RE.finditer(desc):
            km = _token_to_km(lab_m.group(1))
            if km is not None:
                raw.append(km)
    if not raw:
        # 4. Any numeric km mention in the description (named terms are NOT inferred
        #    here — this pass is prose-safe because it only reads explicit numbers).
        raw = _parse_km_values(desc, min_km=1.0, snap=False)

    values = _filter_km_values(raw, min_km=1.0)
    return sorted(
        [Distancia(km=km, data=None, horario=None) for km in values[:8]],
        key=lambda d: float(d.km),
    )


def _parse_shared_suffix(text: str, min_km: float, snap: bool = True) -> list[float]:
    """Extract distances from 'N e M km' patterns (shared km unit suffix)."""
    raw: list[float] = []
    for m in _DIST_SHARED_SUFFIX_RE.finditer(text):
        segment = m.group(0)
        for num_m in re.finditer(r"(\d+(?:[.,]\d+)?)", segment):
            try:
                raw.append(float(num_m.group(1).replace(",", ".")))
            except ValueError:
                pass
    return _filter_km_values(raw, min_km) if snap else raw


def _filter_km_values(raw_values: list[float], min_km: float) -> list[float]:
    seen: list[float] = []
    for raw in raw_values:
        if raw < min_km or raw > 200:
            continue
        km = raw
        for canon, lo, hi in _CANONICAL:
            if lo <= raw <= hi:
                km = canon
                break
        if any(abs(km - s) < 0.5 for s in seen):
            continue
        seen.append(km)
    return seen


def _parse_km_values(text: str, min_km: float, snap: bool = True) -> list[float]:
    raw: list[float] = []
    for m in re.finditer(r"\b(\d+(?:[.,]\d+)?)\s*[kK][mM]?\b", text):
        try:
            raw.append(float(m.group(1).replace(",", ".")))
        except ValueError:
            continue
    return _filter_km_values(raw, min_km) if snap else raw
