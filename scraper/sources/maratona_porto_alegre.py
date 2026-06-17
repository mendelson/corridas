"""Scraper for Maratona Internacional de Porto Alegre.

Fully dynamic — no hardcoded event data. The flow is:

1. Fetch the official organizer homepage (maratonadeportoalegre.com.br). The
   homepage always advertises the current edition via an "INSCRIÇÕES" button
   that links to the edition's Ticket Sports event page
   (``ticketsports.com.br/e/...-<eventId>``).
2. Extract that ``eventId`` from the link.
3. Read every field — title, date, start time, location, distances, image —
   from the Ticket Sports detail API (``/api/events/detail?eventId=<id>``),
   which returns fully structured data.

Because the organizer updates the homepage's "INSCRIÇÕES" link each year, the
scraper auto-rolls to each next edition on its own: when 2027 becomes 2028 the
homepage will point at a new eventId and this scraper picks it up with zero code
changes. Nothing about a specific edition is baked into the code; if the
homepage, the link, or the API can't be read — or the edition has already
happened — the scraper emits nothing.

Distances come from the registration *modality* entries and the PROGRAMAÇÃO
block of the detail payload — never parsed out of the event title.
"""
from __future__ import annotations
import re

from bs4 import BeautifulSoup

from ..http_client import get
from ..models import Corrida, Distancia, FonteInfo
from ..utils import normalize_titulo, now_iso, today_iso
from .. import geo as _geo

SITE_URL    = "https://maratonadeportoalegre.com.br/"
SOURCE_NAME = "Maratona de Porto Alegre"
DETAIL_URL  = "https://www.ticketsports.app/api/events/detail"

# Last "-<digits>" of a ticketsports.com.br/e/<slug>-<id> URL is the event id.
_TS_EVENT_RE = re.compile(r'ticketsports\.com\.br/e/[^"\'\s]*-(\d+)', re.IGNORECASE)

# Distance classification (read from modality/PROGRAMAÇÃO content, never the title)
_KIDS = re.compile(r'maratoninha|infantil|\bkids?\b|caminhada|\bpet\b', re.IGNORECASE)
_HALF = re.compile(r'meia\s+maratona|half\s*marathon', re.IGNORECASE)
_FULL = re.compile(r'(?<!meia\s)maratona\b|(?<!half[\s-])marathon\b', re.IGNORECASE)
# A timed "Largada" entry: "6h30min: Largada: Meia Maratona" / "6h: Largada: Maratona"
_LARGADA_RE = re.compile(
    r'(\d{1,2})h(\d{2})?(?:min)?\s*:?\s*largada\s*:?\s*(meia\s+maratona|maratona)',
    re.IGNORECASE,
)
_DDMM_RE = re.compile(r'\((\d{1,2})/(\d{1,2})\)')
_REALDATE_RE = re.compile(r'(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{1,2}):(\d{2}))?')


def _find_ts_event_id(soup: BeautifulSoup) -> str | None:
    for a in soup.find_all("a", href=True):
        m = _TS_EVENT_RE.search(a["href"])
        if m:
            return m.group(1)
    return None


def _content_items(detail: dict) -> list[dict]:
    return [it for it in (detail.get("eventContents") or []) if isinstance(it, dict)]


def _modality_distances(detail: dict) -> set[float]:
    """Offered race distances, taken from the registration modality entries.

    Ticket Sports emits one ``eventContents`` entry per offered distance whose
    title reads e.g. "Maratona de Porto Alegre (42.195m)" /
    "Meia Maratona de Porto Alegre (21.097m)". A MODALIDADES/DISTÂNCIAS block
    enumerates the same set in prose. We map the race-type keyword to its
    canonical metric distance and also pick up explicit "N km" tokens, dropping
    kids/walk modalities. This deliberately ignores the free-text body so it
    never picks up qualifying-time tables ("Prova de 10km: 30min35s").
    """
    kms: set[float] = set()

    # (a) one modality entry per offered distance
    for it in _content_items(detail):
        title = (it.get("title") or "").strip()
        if not title or _KIDS.search(title):
            continue
        if _HALF.search(title):
            kms.add(21.097)
        elif _FULL.search(title):
            kms.add(42.195)
        for m in re.finditer(r'(\d+(?:[.,]\d+)?)\s*km\b', title, re.IGNORECASE):
            v = float(m.group(1).replace(",", "."))
            if 3 <= v <= 200:
                kms.add(v)

    # (b) cross-check against the MODALIDADES / DISTÂNCIAS prose block
    for it in _content_items(detail):
        if not re.search(r'modalidade|dist[âa]ncia', it.get("title") or "", re.IGNORECASE):
            continue
        txt = BeautifulSoup(it.get("description") or "", "lxml").get_text(" ")
        for seg in re.split(r'[;\n]', txt):
            if _KIDS.search(seg):
                continue
            if _HALF.search(seg):
                kms.add(21.097)
            elif _FULL.search(seg):
                kms.add(42.195)

    return kms


def _programacao_schedule(detail: dict, year: str) -> dict[float, tuple[str, str | None]]:
    """Per-distance (date, horário) parsed from the PROGRAMAÇÃO block.

    The block is laid out as "PROGRAMAÇÃO (DD/MM) – DIA" sections, each listing
    timed "Largada" lines. We anchor on the *Largada* line so the general start
    is captured (not the earlier wheelchair/special wave). Returns only what is
    confidently matched; callers fall back to the event-level date/time.
    """
    sched: dict[float, tuple[str, str | None]] = {}
    for it in _content_items(detail):
        if "programa" not in (it.get("title") or "").lower():
            continue
        txt = BeautifulSoup(it.get("description") or "", "lxml").get_text(" ")
        parts = _DDMM_RE.split(txt)
        # parts = [pre, dd, mm, block, dd, mm, block, ...]
        for i in range(1, len(parts) - 2, 3):
            dd, mm, block = parts[i], parts[i + 1], parts[i + 2]
            try:
                date = f"{year}-{int(mm):02d}-{int(dd):02d}"
            except ValueError:
                continue
            for m in _LARGADA_RE.finditer(block):
                if _KIDS.search(m.group(0)):
                    continue
                h, mn = int(m.group(1)), m.group(2) or "00"
                horario = f"{h:02d}:{mn}" if 4 <= h <= 22 else None
                km = 21.097 if "meia" in m.group(3).lower() else 42.195
                sched.setdefault(km, (date, horario))
    return sched


def _parse_address(addr: str) -> tuple[str, str]:
    """('A definir, Porto Alegre, RS, Brasil') → ('Porto Alegre', 'RS')."""
    segs = [s.strip() for s in addr.split(",") if s.strip()]
    for i, s in enumerate(segs):
        if len(s) == 2 and s.isupper() and s.isalpha():
            return (segs[i - 1] if i > 0 else ""), s
    skip = {"brasil", "brazil", "a definir", "local a definir"}
    cand = [s for s in segs if s.lower() not in skip]
    return (cand[0] if cand else ""), ""


def _build(detail: dict) -> Corrida | None:
    titulo = normalize_titulo(detail.get("title") or "")
    if not titulo or len(titulo) < 3:
        return None

    rd = _REALDATE_RE.search(detail.get("realDate") or "")
    if not rd:
        return None
    year = rd.group(1)
    real_date = f"{rd.group(1)}-{rd.group(2)}-{rd.group(3)}"
    real_horario = f"{int(rd.group(4)):02d}:{rd.group(5)}" if rd.group(4) else None

    schedule = _programacao_schedule(detail, year)
    for km in _modality_distances(detail):
        schedule.setdefault(km, (None, None))
    if not schedule:
        print(f"[{SOURCE_NAME}] sem distâncias estruturadas — ignorando")
        return None

    distancias = [
        Distancia(km=km, data=d, horario=h)
        for km, (d, h) in sorted(schedule.items())
    ]

    # Headline date/time = the longest distance (the marathon); fall back to the
    # platform's structured realDate when a per-distance date wasn't matched.
    longest = max(distancias, key=lambda d: d.km if isinstance(d.km, (int, float)) else 0.0)
    data_evento = longest.data or real_date
    horario = longest.horario or real_horario

    if data_evento < today_iso():
        print(f"[{SOURCE_NAME}] edição já ocorreu ({data_evento}) — ignorando")
        return None

    cidade, uf = _parse_address(detail.get("address") or "")
    pais, estado = _geo.resolve(detail.get("address") or cidade or "Porto Alegre, RS",
                                cidade, "BR")
    estado = estado or uf
    pais = pais or "BR"
    localizacao = f"{cidade}, {estado}".strip(", ") if cidade else (estado or "")

    if detail.get("isSoldOut"):
        inscricoes_abertas: bool | None = False
    elif detail.get("isAcceptingRegistration"):
        inscricoes_abertas = True
    else:
        inscricoes_abertas = None

    link = detail.get("uri") or SITE_URL
    now = now_iso()
    fonte = FonteInfo(
        nome=SOURCE_NAME,
        link_evento=link,
        links_inscricao=[link],
        tipo="organizador",
    )
    return Corrida(
        id=f"maratona-porto-alegre-rs-{year}",
        titulo=titulo,
        data_evento=data_evento,
        horario=horario,
        localizacao=localizacao or "Porto Alegre, RS",
        cidade=cidade or "Porto Alegre",
        estado=estado,
        pais=pais,
        distancias=distancias,
        imagem_url=detail.get("logoImageSource") or None,
        inscricoes_abertas=inscricoes_abertas,
        periodo_inscricao=None,
        fontes=[fonte],
        miss_count=0,
        first_seen_at=now,
        updated_at=now,
    )


def scrape() -> list[Corrida]:
    try:
        resp = get(SITE_URL)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
    except Exception as e:
        print(f"[{SOURCE_NAME}] homepage inacessível: {e}")
        return []

    event_id = _find_ts_event_id(soup)
    if not event_id:
        print(f"[{SOURCE_NAME}] nenhum link de evento Ticket Sports na homepage")
        return []

    try:
        dresp = get(DETAIL_URL, params={"eventId": event_id})
        dresp.raise_for_status()
        detail = dresp.json()
    except Exception as e:
        print(f"[{SOURCE_NAME}] detalhe Ticket Sports {event_id} falhou: {e}")
        return []

    corrida = _build(detail)
    if not corrida:
        return []
    print(f"[{SOURCE_NAME}] 1 corrida encontrada (TS {event_id}): {corrida.titulo}")
    return [corrida]
