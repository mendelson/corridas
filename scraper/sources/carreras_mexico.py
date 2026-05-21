"""Scraper for carrerasmexico.com — calendar of Mexican road running events.

Listing page: /eventos.php
State-filtered: /eventos.php?edo=<CODE>  (e.g. DIF=CDMX, MEX, NLE, JAL...)

This is a probe-first scraper: on the first invocation it logs the HTML
structure so the CI log reveals the actual page layout. Subsequent runs
parse based on what we learned.
"""
from __future__ import annotations
import re
from bs4 import BeautifulSoup

from ..http_client import get
from ..models import Corrida, Distancia, FonteInfo
from ..utils import normalize_titulo, slugify, now_iso, today_iso
from .. import geo as _geo

BASE = "https://www.carrerasmexico.com"
LISTING = f"{BASE}/eventos.php"
SOURCE_NAME = "Carreras México"

# carrerasmexico organizes events by state via ?edo=<CODE>. These are the codes
# we've observed in indexed URLs. Confirmed: DIF (CDMX), MEX, NLE, JAL, PUE,
# MIC, QUE, MOR, TAM. Other 3-letter ISO-like codes inferred for remaining states.
_STATE_PARAMS = [
    "DIF",  # CDMX (Distrito Federal)
    "MEX",  # Estado de México
    "NLE",  # Nuevo León
    "JAL",  # Jalisco
    "PUE",  # Puebla
    "MIC",  # Michoacán
    "QUE",  # Querétaro
    "MOR",  # Morelos
    "TAM",  # Tamaulipas
    "AGU", "BCN", "BCS", "CAM", "CHP", "CHH", "COA", "COL",
    "DUR", "GUA", "GRO", "HID", "NAY", "OAX", "QUI", "ROO",
    "SLP", "SIN", "SON", "TAB", "TLA", "VER", "YUC", "ZAC",
]

# Spanish month names → ISO month
_MX_MONTHS = {
    "enero": "01", "febrero": "02", "marzo": "03", "abril": "04",
    "mayo": "05", "junio": "06", "julio": "07", "agosto": "08",
    "septiembre": "09", "setiembre": "09", "octubre": "10",
    "noviembre": "11", "diciembre": "12",
    "ene": "01", "feb": "02", "mar": "03", "abr": "04",
    "may": "05", "jun": "06", "jul": "07", "ago": "08",
    "sep": "09", "oct": "10", "nov": "11", "dic": "12",
}

# carrerasmexico state code → standard MX UF used by the rest of the codebase
_STATE_CODE_MAP = {
    "DIF": "CMX",  # Distrito Federal → Ciudad de México
}

# Title-keyword filtering — running events only
_RUNNING_KW = re.compile(
    r"\b(carrera|caminata|maraton|maratón|medio[- ]?marat[oó]n|"
    r"half[- ]?marathon|trail|run(ning)?|10\s*k|5\s*k|21\s*k|42\s*k|"
    r"ultra(maratón|marathon)?)\b",
    re.IGNORECASE,
)
_NON_RUNNING_KW = re.compile(
    r"\b(triatl[oó]n|aquat(h|l)on|duatl[oó]n|ciclismo|natación|"
    r"swim|bike|cycling|spartan|crossfit|mtb|open\s*water)\b",
    re.IGNORECASE,
)

_DATE_DMY = re.compile(r"(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{4})")
_DATE_ES = re.compile(
    r"(\d{1,2})\s+(?:de\s+)?([a-záéíóú]+)\s+(?:de(?:l)?\s+)?(\d{4})",
    re.IGNORECASE,
)


def scrape() -> list[Corrida]:
    # PROBE: fetch the Tiempometa JS widget once, dump the API URL patterns
    try:
        js = get("https://www.tiempometa.com/assets/tm3_js_api.js", source=SOURCE_NAME, timeout=30)
        if js.status_code == 200:
            txt = js.text
            print(f"[{SOURCE_NAME}] PROBE tm3_js_api.js length={len(txt)}")
            # Dump any AJAX URL templates / endpoint references
            import re as _re
            for pat in [
                r"url\s*[:=]\s*['\"]([^'\"]+)['\"]",
                r"\$\.(get|post|ajax|getJSON)\s*\(\s*['\"]([^'\"]+)['\"]",
                r"fetch\s*\(\s*['\"]([^'\"]+)['\"]",
                r"https?://[^\s\"'<>]+(?:events|api|carreras|json)[^\s\"'<>]*",
                r"(events_template|events_carousel|event_search)\s*[=:].*?function\s*\([^)]*\)\s*\{[^}]{0,500}",
            ]:
                for m in _re.finditer(pat, txt):
                    print(f"[{SOURCE_NAME}]   match: {m.group(0)[:300]}")
            # Look for the function bodies specifically
            for fn in ("events_template", "events_carousel", "event_search"):
                m = _re.search(rf"{fn}\s*[=:]\s*function[^{{]*\{{(.*?)\}}\s*[,;]?", txt, _re.DOTALL)
                if m:
                    print(f"[{SOURCE_NAME}] FN {fn} body (first 600 chars):")
                    print(m.group(1)[:600])
    except Exception as e:
        print(f"[{SOURCE_NAME}] PROBE failed: {e}")

    today = today_iso()
    now = now_iso()
    corridas: list[Corrida] = []
    seen_ids: set[str] = set()
    debugged = False

    for edo in _STATE_PARAMS:
        url = f"{LISTING}?edo={edo}"
        try:
            resp = get(url, source=SOURCE_NAME, timeout=30)
            resp.raise_for_status()
        except Exception as e:
            print(f"[{SOURCE_NAME}] {edo}: erro {e}")
            continue

        soup = BeautifulSoup(resp.text, "lxml")
        if not debugged:
            print(f"[{SOURCE_NAME}] === PROBE state={edo} ===")
            _debug_structure(soup, resp.text)
            debugged = True

        state_corridas: list[Corrida] = []
        for el in _find_events(soup):
            try:
                corrida = _parse_event(el, today, now, default_estado=edo)
                if corrida and corrida.id not in seen_ids:
                    seen_ids.add(corrida.id)
                    state_corridas.append(corrida)
            except Exception as e:
                print(f"[{SOURCE_NAME}] {edo}: erro ao parsear: {e}")

        print(f"[{SOURCE_NAME}] {edo}: {len(state_corridas)} corridas")
        corridas.extend(state_corridas)

    print(f"[{SOURCE_NAME}] {len(corridas)} corridas encontradas (total)")
    return corridas


def _debug_structure(soup: BeautifulSoup, raw: str) -> None:
    """Log enough to diagnose missing event content."""
    title = soup.title.string.strip() if soup.title and soup.title.string else "no title"
    print(f"[{SOURCE_NAME}] DEBUG title: {title}")
    print(f"[{SOURCE_NAME}] DEBUG response length: {len(raw)} chars")
    links = soup.find_all("a", href=True)
    print(f"[{SOURCE_NAME}] DEBUG {len(links)} links")
    for a in links[:20]:
        print(f"[{SOURCE_NAME}]   href: {a['href'][:120]}")
    # Look for keywords that signal events are present (or absent)
    raw_lower = raw.lower()
    for kw in ("evento", "carrera", "fecha", "inscrip", "5k", "10k", "21k", "42k", "maratón", "maraton"):
        n = raw_lower.count(kw)
        if n > 0:
            print(f"[{SOURCE_NAME}] DEBUG keyword '{kw}': {n} occurrences in raw HTML")
    # Look for embedded JSON or data attributes
    scripts = soup.find_all("script")
    print(f"[{SOURCE_NAME}] DEBUG {len(scripts)} <script> tags")
    for i, s in enumerate(scripts):
        src = s.get("src", "")
        if src:
            print(f"[{SOURCE_NAME}]   script[{i}] src={src}")
    # Any tiempometa references in raw HTML
    import re as _re
    for m in _re.finditer(r"https?://[^\s\"']+tiempometa[^\s\"']*", raw, _re.IGNORECASE):
        print(f"[{SOURCE_NAME}] DEBUG tiempometa URL: {m.group(0)}")
    # The Tiempometa() bootstrap call — show params
    for m in _re.finditer(r"Tiempometa\.\w+\([^)]+\)", raw):
        print(f"[{SOURCE_NAME}] DEBUG Tiempometa call: {m.group(0)}")
    # Look for any data-* attributes that might carry the widget config
    for el in soup.find_all(attrs={"id": _re.compile(r"tm_|tiempometa", _re.IGNORECASE)}):
        print(f"[{SOURCE_NAME}] DEBUG widget element: {str(el)[:300]}")
    # Dump first 3000 chars of <body> verbatim — last resort to see what's there
    body = soup.find("body")
    body_str = str(body)[:3000] if body else "no body"
    print(f"[{SOURCE_NAME}] DEBUG body[:3000]: {body_str}")


def _find_events(soup: BeautifulSoup) -> list:
    """Try common selectors. Returns list of event elements."""
    for sel in [
        "tr.evento", "div.evento", "article.evento", "li.evento",
        ".race-card", ".event-card", "article", "tr", ".carrera",
    ]:
        els = soup.select(sel)
        if len(els) >= 3:
            return els
    # Fallback: any element that contains both a date and the word "carrera"
    return [el for el in soup.find_all(["div", "tr", "li", "article"])
            if _looks_like_event(el)]


def _looks_like_event(el) -> bool:
    txt = el.get_text(" ", strip=True)
    if len(txt) < 20 or len(txt) > 1000:
        return False
    has_date = bool(_DATE_DMY.search(txt) or _DATE_ES.search(txt))
    return has_date and _RUNNING_KW.search(txt) is not None


def _parse_event(el, today: str, now: str, default_estado: str = "") -> Corrida | None:
    text = el.get_text(" ", strip=True)
    if not text or len(text) < 10:
        return None

    # Title from heading or strong; fallback to first link
    heading = el.find(["h1", "h2", "h3", "h4", "h5", "strong"])
    titulo_raw = heading.get_text(strip=True) if heading else None
    if not titulo_raw:
        link = el.find("a")
        titulo_raw = link.get_text(strip=True) if link else text[:80]

    titulo = normalize_titulo(titulo_raw)
    if not titulo or len(titulo) < 4:
        return None

    # Title-keyword gate
    if not _RUNNING_KW.search(titulo) and not _RUNNING_KW.search(text[:200]):
        return None
    if _NON_RUNNING_KW.search(titulo):
        return None

    data = _extract_date(text)
    if not data or data < today:
        return None

    cidade, estado = _extract_location(el, text)
    if estado:
        estado = _STATE_CODE_MAP.get(estado, estado)
    if not estado:
        estado = _STATE_CODE_MAP.get(default_estado, default_estado)
    if not estado:
        _pais_geo, estado = _geo.resolve(cidade, "", "MX")
    localizacao = f"{cidade}, {estado}" if cidade and estado else cidade or estado or "México"

    distancias = _extract_distances(text)

    link_tag = el.find("a", href=True)
    link = link_tag["href"] if link_tag else LISTING
    if link.startswith("/"):
        link = BASE + link
    elif not link.startswith("http"):
        link = f"{BASE}/{link}"

    img = el.find("img")
    imagem_url = (img.get("src") or img.get("data-src")) if img else None
    if imagem_url and imagem_url.startswith("/"):
        imagem_url = BASE + imagem_url

    fonte = FonteInfo(
        nome=SOURCE_NAME,
        link_evento=link,
        links_inscricao=[link] if link != LISTING else [],
    )
    return Corrida(
        id=f"cm_{slugify(titulo)}_{estado.lower()}_{data}",
        titulo=titulo,
        data_evento=data,
        horario=None,
        localizacao=localizacao,
        cidade=cidade,
        estado=estado,
        pais="MX",
        distancias=distancias,
        imagem_url=imagem_url,
        inscricoes_abertas=None,
        periodo_inscricao=None,
        fontes=[fonte],
        miss_count=0,
        first_seen_at=now,
        updated_at=now,
    )


def _extract_date(text: str) -> str | None:
    m = _DATE_DMY.search(text)
    if m:
        d, mo, y = m.group(1), m.group(2), m.group(3)
        return f"{y}-{mo.zfill(2)}-{d.zfill(2)}"
    m = _DATE_ES.search(text)
    if m:
        d, mes, y = m.group(1), m.group(2).lower(), m.group(3)
        mo = _MX_MONTHS.get(mes)
        if mo:
            return f"{y}-{mo}-{d.zfill(2)}"
    return None


def _extract_location(el, text: str) -> tuple[str, str]:
    """Return (cidade, estado) — estado is a UF code or empty."""
    # Try elements with a location-ish class
    for cls in ("ciudad", "city", "lugar", "localidad", "estado", "venue"):
        loc = el.find(class_=re.compile(cls, re.IGNORECASE))
        if loc:
            val = loc.get_text(strip=True)
            if val:
                # "Ciudad, Estado" or "Ciudad - Estado"
                parts = re.split(r"[,\-–]", val)
                return parts[0].strip(), (parts[1].strip() if len(parts) > 1 else "")
    return "", ""


def _extract_distances(text: str) -> list[Distancia]:
    seen: set[float] = set()
    result: list[Distancia] = []
    for n in re.findall(r"\b(\d+(?:[.,]\d+)?)\s*[kK](?:m|M)?\b", text):
        km = float(n.replace(",", "."))
        if 21.0 <= km <= 21.2:
            km = 21.097
        elif 41.5 <= km <= 43.0:
            km = 42.195
        if km not in seen and 3 <= km <= 200:
            seen.add(km)
            result.append(Distancia(km=km, data=None, horario=None))
    return sorted(result, key=lambda d: d.km)
