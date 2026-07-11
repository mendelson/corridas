"""Scraper for the Tênis Certo Provas Telegram channel.

The channel (@teniscertoprovas) posts running-event announcements interleaved
with shoe-deal / coupon / photo ads. Race posts follow a fixed labelled format:

    💙 <Race name> 💙
    🔗 https://tenis.cc/<short>      (affiliate registration link, carries a coupon)
    📍 Local: <City>, <UF>
    🗓️ Datas: <DD[ e DD]/MM/YY[YY]>
    🏁 Distâncias: 5Km, 21Km, 42Km e Kids

We read the public web preview (https://t.me/s/<channel>), which renders each
message as HTML — no API/auth needed. Every event field comes from a LABELLED
line (Local / Datas / Distâncias / 🔗), never from the title. Horário isn't in
the post, so (like runner_brasil) we follow the registration link to read it;
near-term events still lacking one are skipped, far-future ones are kept.

Pagination: the preview returns the latest ~20 messages plus ``?before=<id>`` to
page back. We page back until the posts are older than the look-back window
(date-based stop — not a result cap).
"""
from __future__ import annotations
import re
from datetime import date, timedelta

from bs4 import BeautifulSoup

from ..http_client import get
from ..models import Corrida, Distancia, FonteInfo
from ..utils import (
    normalize_titulo, now_iso, today_iso, horario_required,
)
from .. import geo as _geo

SOURCE_NAME = "Tênis Certo"
CHANNEL = "teniscertoprovas"
BASE = f"https://t.me/s/{CHANNEL}"

# Look back this far in the channel history (posts older than this can only carry
# already-past races). Date-based bound on pagination, not a result cap.
_LOOKBACK_DAYS = 120

_CANONICAL = [(42.195, 41.5, 43.0), (21.097, 20.5, 21.5)]
_UF_RE = re.compile(r",\s*([A-Z]{2})\b")
_DATE_RE = re.compile(r"(\d{1,2})(?:\s*e\s*\d{1,2})?\s*/\s*(\d{1,2})\s*/\s*(\d{2,4})")
_KM_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*[kK][mM]?\b")
# Non-running distance segments to drop from the Distâncias line.
_WALK_KIDS_RE = re.compile(r"caminhada|kids|infantil|walk", re.IGNORECASE)

# Horário ("07h00", "07:00", "às 7h") — mirrors the other BR calendar scrapers.
_HORARIO_RE = re.compile(
    r"(?:às?|sa[íi]da|largada|in[íi]cio|partida|hor[áa]rio|hora)\s*:?\s*"
    r"(\d{1,2})[hH:]([0-5]\d)"
    r"|(\d{1,2})[hH:]([0-5]\d)\s*(?:h(?:oras?)?)?\b(?!\s*[kK])",
    re.IGNORECASE,
)


def _label_line(text: str, *markers: str) -> str | None:
    """Return the content after a labelled marker line (e.g. 'Local:')."""
    for line in text.splitlines():
        low = line.lower()
        for mk in markers:
            if mk in low:
                # Drop everything up to and including the label's colon.
                after = line.split(":", 1)[1] if ":" in line else line
                return after.strip()
    return None


def _parse_date(datas: str) -> str | None:
    m = _DATE_RE.search(datas)
    if not m:
        return None
    d, mo, y = m.group(1), m.group(2), m.group(3)
    if len(y) == 2:
        y = "20" + y
    try:
        return f"{int(y):04d}-{int(mo):02d}-{int(d):02d}"
    except ValueError:
        return None


def _parse_distances(dist_line: str) -> list[Distancia]:
    seen: list[float] = []
    # Split into segments so a "(caminhada)"/"Kids" annotation only drops its own
    # distance, not the running ones.
    for seg in re.split(r",|\be\b", dist_line):
        if _WALK_KIDS_RE.search(seg):
            continue
        m = _KM_RE.search(seg)
        if not m:
            continue
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
        if not any(abs(km - s) < 0.5 for s in seen):
            seen.append(km)
    return [Distancia(km=k, data=None, horario=None) for k in sorted(seen)]


def _extract_horario(text: str) -> str | None:
    if not text:
        return None
    m = _HORARIO_RE.search(text)
    if not m:
        return None
    h, mi = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4))
    try:
        return f"{int(h):02d}:{int(mi):02d}"
    except (TypeError, ValueError):
        return None


def _fetch_horario_from_link(url: str) -> str | None:
    """Follow the registration link and read a start time from the page text."""
    try:
        resp = get(url, timeout=15)
        if resp.status_code != 200:
            return None
        text = BeautifulSoup(resp.text, "lxml").get_text(" ", strip=True)
        return _extract_horario(text)
    except Exception:
        return None


def _parse_message(div) -> Corrida | None:
    text_el = div.select_one(".tgme_widget_message_text")
    if not text_el:
        return None
    # Preserve line breaks (the labelled fields are one per line).
    for br in text_el.find_all("br"):
        br.replace_with("\n")
    text = text_el.get_text("\n")

    local = _label_line(text, "local")
    datas = _label_line(text, "datas", "data")
    dists = _label_line(text, "distância", "distancia", "distâncias", "distancias")
    # A race post carries all three labelled fields; ads (coupons/photos) don't.
    if not (local and datas and dists):
        return None

    data_evento = _parse_date(datas)
    if not data_evento:
        return None

    uf_m = _UF_RE.search(local)
    if not uf_m:
        return None
    estado = uf_m.group(1)
    cidade = local.split(",")[0].strip()
    if not cidade:
        return None

    distancias = _parse_distances(dists)
    if not distancias:
        return None

    # Title: the first non-empty line, stripped of decorative emojis. Used ONLY
    # for the título — no field is parsed out of it.
    titulo = ""
    for line in text.splitlines():
        s = re.sub(r"[^\w\sÀ-ÿ&/().-]", "", line).strip()
        if len(s) >= 3:
            titulo = normalize_titulo(s)
            break
    if not titulo or len(titulo) < 3:
        return None

    # Registration link (🔗) — first tenis.cc / external link in the message.
    link = None
    for a in text_el.find_all("a", href=True):
        href = a["href"]
        if href.startswith("http") and "t.me" not in href:
            link = href
            break
    if not link:
        return None

    horario = _extract_horario(text) or _fetch_horario_from_link(link)
    # Horário is no longer mandatory (policy change 2026-07-11 —
    # horario_required() always returns False): events without one are kept.
    # Extraction above still runs at full effort; the guard stays for easy
    # restoration of the strict policy via utils.horario_required().
    if horario is None and horario_required(data_evento):
        return None

    # Canonicalise the subdivision from the city (the post's UF is the fallback).
    _pais, _estado = _geo.resolve(cidade, "", "BR")
    if _estado:
        estado = _estado

    post_id = (div.get("data-post") or "").split("/")[-1]
    ev_id = f"teniscerto_{post_id}" if post_id else f"teniscerto_{data_evento}_{cidade.lower().replace(' ', '-')}"

    now = now_iso()
    return Corrida(
        id=ev_id,
        titulo=titulo,
        data_evento=data_evento,
        horario=horario,
        localizacao=f"{cidade}, {estado}",
        cidade=cidade,
        estado=estado,
        pais="BR",
        distancias=distancias,
        imagem_url=None,
        inscricoes_abertas=None,
        periodo_inscricao=None,
        fontes=[FonteInfo(
            nome=SOURCE_NAME,
            link_evento=link,
            links_inscricao=[link],
            tipo="calendario",
        )],
        miss_count=0,
        first_seen_at=now,
        updated_at=now,
    )


def _page_messages(html: str):
    soup = BeautifulSoup(html, "lxml")
    return soup.select(".tgme_widget_message")


def _oldest_id_and_date(divs) -> tuple[int | None, str | None]:
    """Smallest message id on the page (for ?before=) and its post date."""
    ids = []
    oldest_date = None
    for d in divs:
        post = (d.get("data-post") or "").split("/")[-1]
        if post.isdigit():
            ids.append(int(post))
        t = d.select_one("time[datetime]")
        if t and t.get("datetime"):
            day = t["datetime"][:10]
            if oldest_date is None or day < oldest_date:
                oldest_date = day
    return (min(ids) if ids else None), oldest_date


def scrape() -> list[Corrida]:
    cutoff = (date.today() - timedelta(days=_LOOKBACK_DAYS)).isoformat()
    by_id: dict[str, Corrida] = {}
    before: int | None = None
    seen_pages: set[int] = set()

    while True:
        url = BASE + (f"?before={before}" if before else "")
        try:
            resp = get(url, timeout=20)
            resp.raise_for_status()
        except Exception as e:
            print(f"[{SOURCE_NAME}] erro ao buscar {url}: {e}")
            break

        divs = _page_messages(resp.text)
        if not divs:
            break

        for d in divs:
            try:
                c = _parse_message(d)
            except Exception as e:
                print(f"[{SOURCE_NAME}] erro ao processar mensagem: {e}")
                c = None
            if c and c.data_evento >= today_iso():
                by_id[c.id] = c

        oldest_id, oldest_date = _oldest_id_and_date(divs)
        # Stop: no more pages, no progress, or we've paged past the look-back window.
        if not oldest_id or oldest_id in seen_pages:
            break
        seen_pages.add(oldest_id)
        if oldest_date and oldest_date < cutoff:
            break
        before = oldest_id

    corridas = list(by_id.values())
    print(f"[{SOURCE_NAME}] {len(corridas)} corrida(s) encontrada(s)")
    return corridas
