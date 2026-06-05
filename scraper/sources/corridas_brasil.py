"""Scraper for corridasbrasil.com.br/calendario/

The calendar shows a table with event rows (<tr height="35">):
  Col 0: date "DD/MM/YY"
  Col 1: city name
  Col 2: event name + detail link (mostra-prova/?c=ID&prova=Name)
  Col 3: distances "5km" / "10/5km" / "15/10/5km"

The listing does NOT show horario. Each detail page (mostra-prova/) adds:
  - State code (from region link ?c=Region&d=UF)
  - External organizer/registration URL (from "Informacoes" link)

Horario is fetched from the external organizer page via full-text regex scan.
"""
from __future__ import annotations
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

from bs4 import BeautifulSoup

from ..http_client import get
from ..models import Corrida, Distancia, FonteInfo
from ..utils import normalize_titulo, slugify, now_iso, today_iso
from .. import geo as _geo

URL = "https://corridasbrasil.com.br/calendario/"
BASE = "https://corridasbrasil.com.br"
SOURCE_NAME = "Corridas Brasil"

_CANONICAL = [(42.195, 41.5, 43.0), (21.097, 20.5, 21.5)]

_TIME_RE = re.compile(
    r"\b(\d{1,2})[hH:]([0-5]\d)\s*(?:min\s*)?[hH]?\b(?!\s*[kK])"
    r"|\b(\d{1,2})\s*[hH]\b(?!\s*\d)",
    re.IGNORECASE,
)

_LOOKAHEAD_DAYS = 90


def scrape() -> list[Corrida]:
    today = today_iso()
    try:
        resp = get(URL)
        resp.raise_for_status()
    except Exception as e:
        print(f"[{SOURCE_NAME}] erro: {e}")
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    raw_events = _parse_listing(soup, today)
    if not raw_events:
        print(f"[{SOURCE_NAME}] nenhum evento na listagem")
        return []

    print(f"[{SOURCE_NAME}] {len(raw_events)} eventos na listagem, buscando detalhes...")

    # Phase 1: fetch detail pages (state + organizer URL)
    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = {ex.submit(_fetch_detail, ev["detail_url"]): ev for ev in raw_events}
        for fut in as_completed(futures):
            ev = futures[fut]
            try:
                detail = fut.result()
                if detail:
                    ev.update(detail)
            except Exception:
                pass

    # Phase 2: fetch organizer pages for horario
    need_horario = [ev for ev in raw_events if ev.get("org_url") and not ev.get("horario")]
    if need_horario:
        with ThreadPoolExecutor(max_workers=8) as ex:
            futures2 = {ex.submit(_fetch_horario_from_url, ev["org_url"]): ev
                        for ev in need_horario}
            for fut in as_completed(futures2):
                ev = futures2[fut]
                try:
                    h = fut.result()
                    if h:
                        ev["horario"] = h
                except Exception:
                    pass

    corridas: list[Corrida] = []
    for ev in raw_events:
        try:
            c = _build_corrida(ev)
            if c:
                corridas.append(c)
        except Exception as e:
            print(f"[{SOURCE_NAME}] erro '{ev.get('titulo')}': {e}")

    print(f"[{SOURCE_NAME}] {len(corridas)} corridas encontradas")
    return corridas


def _parse_listing(soup, today: str) -> list[dict]:
    from datetime import date, timedelta
    cutoff = (date.fromisoformat(today) + timedelta(days=_LOOKAHEAD_DAYS)).isoformat()

    events: list[dict] = []
    for tr in soup.find_all("tr", height="35"):
        tds = tr.find_all("td")
        if len(tds) < 4:
            continue

        date_str = _parse_date(tds[0].get_text(strip=True))
        if not date_str or date_str < today or date_str > cutoff:
            continue

        city = tds[1].get_text(strip=True).strip().title()

        name_el = tds[2].find("a", class_="tabela") or tds[2].find("a")
        name_text = name_el.get_text(strip=True) if name_el else tds[2].get_text(strip=True)
        titulo = normalize_titulo(name_text)
        if not titulo or len(titulo) < 3:
            continue

        link_el = tds[2].find("a", href=True)
        detail_url = link_el["href"] if link_el else ""
        if detail_url.startswith("/"):
            detail_url = BASE + detail_url
        if not detail_url:
            continue

        dist_text = tds[3].get_text(strip=True)
        distancias = _extract_distances(dist_text)
        if not distancias:
            distancias = _distances_from_title(titulo.lower())
        if not distancias:
            continue

        m = re.search(r"[?&]c=(\d+)", detail_url)
        ev_id = f"corridasbrasil_{m.group(1)}" if m else f"corridasbrasil_{slugify(titulo)}_{date_str}"

        events.append({
            "id": ev_id,
            "titulo": titulo,
            "data": date_str,
            "cidade": city,
            "detail_url": detail_url,
            "distancias": distancias,
            "estado": "",
            "horario": None,
            "org_url": None,
        })

    return events


def _fetch_detail(url: str) -> dict | None:
    """Fetch mostra-prova detail page → extract state code and organizer URL."""
    try:
        resp = get(url)
        if resp.status_code != 200:
            return None
        soup = BeautifulSoup(resp.text, "lxml")

        estado = ""
        for a in soup.find_all("a", href=True):
            href = a["href"]
            m = re.search(r"[?&]d=([A-Z]{2})\b", href)
            if m:
                estado = m.group(1)
                break

        org_url: str | None = None
        for td in soup.find_all("td"):
            span = td.find("span", class_="tipo4")
            if span and "Informacoes" in span.get_text():
                sibling_td = td.find_next_sibling("td")
                if sibling_td:
                    a = sibling_td.find("a", href=True)
                    if a and a["href"].startswith("http"):
                        org_url = a["href"]
                break

        return {"estado": estado, "org_url": org_url}
    except Exception:
        return None


def _fetch_horario_from_url(url: str) -> str | None:
    """Fetch organizer/registration page and extract start time."""
    for _attempt in range(2):
        try:
            resp = get(url)
            if resp.status_code != 200:
                continue
            soup = BeautifulSoup(resp.text, "lxml")
            h = _extract_horario(soup.get_text(" ", strip=True))
            if h:
                return h
        except Exception:
            pass
    return None


def _build_corrida(ev: dict) -> Corrida | None:
    horario = ev.get("horario")
    if not horario:
        return None

    cidade = ev["cidade"]
    estado = ev.get("estado") or ""
    if not estado:
        _, estado = _geo.resolve(cidade, cidade, "BR")
        estado = estado or ""

    localizacao = f"{cidade}, {estado}" if estado else cidade
    detail_url = ev["detail_url"]

    now = now_iso()
    fonte = FonteInfo(
        nome=SOURCE_NAME,
        link_evento=detail_url,
        links_inscricao=[ev.get("org_url") or detail_url],
        tipo="calendario",
    )
    return Corrida(
        id=ev["id"],
        titulo=ev["titulo"],
        data_evento=ev["data"],
        horario=horario,
        localizacao=localizacao,
        cidade=cidade,
        estado=estado,
        pais="BR",
        distancias=ev["distancias"],
        imagem_url=None,
        inscricoes_abertas=None,
        periodo_inscricao=None,
        fontes=[fonte],
        miss_count=0,
        first_seen_at=now,
        updated_at=now,
    )


def _parse_date(text: str) -> str | None:
    m = re.search(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b", text)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 1 <= d <= 31 and 1 <= mo <= 12:
            return f"{y}-{mo:02d}-{d:02d}"
    m = re.search(r"\b(\d{1,2})/(\d{1,2})/(\d{2})\b", text)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3)) + 2000
        if 1 <= d <= 31 and 1 <= mo <= 12:
            return f"{y}-{mo:02d}-{d:02d}"
    return None


def _extract_distances(dist_text: str) -> list[Distancia]:
    """Parse '5km', '10/5km', '15/10/5km', '21/10km' etc."""
    dist_text = dist_text.strip()
    seen: set[float] = set()
    result: list[Distancia] = []

    # Pattern: group of numbers separated by "/" followed by single "km"
    m = re.match(r"^([\d./\s,]+)\s*[kK][mM]?\s*$", dist_text)
    if m:
        nums = re.findall(r"\d+(?:[.,]\d+)?", m.group(1))
    else:
        # Fallback: individual "Nkm" tokens
        nums = re.findall(r"(\d+(?:[.,]\d+)?)\s*[kK][mM]?\b", dist_text)

    for n in nums:
        try:
            km = float(n.replace(",", "."))
        except ValueError:
            continue
        for canon, lo, hi in _CANONICAL:
            if lo <= km <= hi:
                km = canon
                break
        if km not in seen and 3 <= km <= 200:
            seen.add(km)
            result.append(Distancia(km=km, data=None, horario=None))

    return sorted(result, key=lambda d: d.km)


def _distances_from_title(titulo_lower: str) -> list[Distancia]:
    seen: set[float] = set()
    result: list[Distancia] = []
    if "meia maratona" in titulo_lower or "half marathon" in titulo_lower:
        seen.add(21.097)
        result.append(Distancia(km=21.097, data=None, horario=None))
    if re.search(r"(?<!meia )\bmaratona\b|(?<!half )\bmarathon\b", titulo_lower):
        if 42.195 not in seen:
            seen.add(42.195)
            result.append(Distancia(km=42.195, data=None, horario=None))
    for mm in re.finditer(r"\b(\d+(?:[.,]\d+)?)\s*k[m]?\b", titulo_lower):
        km = float(mm.group(1).replace(",", "."))
        for canon, lo, hi in _CANONICAL:
            if lo <= km <= hi:
                km = canon
                break
        if km not in seen and 3 <= km <= 200:
            seen.add(km)
            result.append(Distancia(km=km, data=None, horario=None))
    return sorted(result, key=lambda d: d.km)


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
    if 4 <= h <= 23:
        return f"{h:02d}:{mi:02d}"
    return None
