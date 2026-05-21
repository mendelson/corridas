"""Scraper for carrerasmexico.com — uses the Tiempometa public JS API.

The carrerasmexico.com homepage embeds a Tiempometa widget. We bypass the
widget and call its API directly:

  GET https://www.tiempometa.com/api3/js_site/event_search
    ?api_key=<public-api-key>
    &type=Calle        # road races only ("Carreras de Calle")
    &month=YYYY-MM     # optional
    &state=<UF>        # optional
    &page=<n>
    &page_size=<n>
    &callback=<jsonp>  # JSONP wrapper

The response is JSONP: `callback({...json...});`. We strip the wrapper.
"""
from __future__ import annotations
import json
import re
from datetime import date, timedelta

from ..http_client import get
from ..models import Corrida, Distancia, FonteInfo
from ..utils import normalize_titulo, slugify, now_iso, today_iso
from .. import geo as _geo

SOURCE_NAME = "Carreras México"
BASE = "https://carrerasmexico.com"
API = "https://www.tiempometa.com/api3/js_site/event_search"

# Public API key exposed in carrerasmexico's #tm_event_list div
API_KEY = "48513987f33edea8"
PAGE_SIZE = 100

# Tiempometa state codes (verbatim, as the widget accepts them)
_STATE_FULL_BY_CODE: dict[str, str] = {
    "AGU": "Aguascalientes", "BCN": "Baja California", "BCS": "Baja California Sur",
    "CAM": "Campeche", "CHP": "Chiapas", "CHH": "Chihuahua",
    "COA": "Coahuila", "COL": "Colima", "DIF": "Ciudad de México",
    "DUR": "Durango", "GUA": "Guanajuato", "GRO": "Guerrero",
    "HID": "Hidalgo", "JAL": "Jalisco", "MEX": "Estado de México",
    "MIC": "Michoacán", "MOR": "Morelos", "NAY": "Nayarit",
    "NLE": "Nuevo León", "OAX": "Oaxaca", "PUE": "Puebla",
    "QUE": "Querétaro", "ROO": "Quintana Roo", "SLP": "San Luis Potosí",
    "SIN": "Sinaloa", "SON": "Sonora", "TAB": "Tabasco",
    "TAM": "Tamaulipas", "TLA": "Tlaxcala", "VER": "Veracruz",
    "YUC": "Yucatán", "ZAC": "Zacatecas",
}

# carrerasmexico uses DIF for Mexico City; the rest of the codebase uses CMX
_NORMALIZE_UF = {"DIF": "CMX"}

# Canonical distances
_CANON_KM = {21: 21.097, 42: 42.195}

# Months to query — current month + next 12 months
def _months_ahead(n: int = 12) -> list[str]:
    today = date.today()
    months: list[str] = []
    y, m = today.year, today.month
    for _ in range(n + 1):
        months.append(f"{y:04d}-{m:02d}")
        m += 1
        if m > 12:
            m = 1
            y += 1
    return months


def scrape() -> list[Corrida]:
    today = today_iso()
    now = now_iso()
    corridas: dict[str, Corrida] = {}

    # PROBE: try multiple endpoints/param shapes to find one that returns 200
    print(f"[{SOURCE_NAME}] === probing endpoint variations ===")
    probe_variations = [
        # (label, url, params)
        ("events-bare", f"https://www.tiempometa.com/api3/js_site/events",
         {"api_key": API_KEY, "page": 1, "page_size": 5}),
        ("events-with-target", f"https://www.tiempometa.com/api3/js_site/events",
         {"api_key": API_KEY, "page": 1, "page_size": 5, "target_url": "https://carrerasmexico.com/"}),
        ("event_search-bare", f"https://www.tiempometa.com/api3/js_site/event_search",
         {"api_key": API_KEY, "page": 1, "page_size": 5}),
        ("event_search-all", f"https://www.tiempometa.com/api3/js_site/event_search",
         {"api_key": API_KEY, "state": "", "month": "", "type": "", "page": 1, "page_size": 5}),
        ("event_search-typeCalle", f"https://www.tiempometa.com/api3/js_site/event_search",
         {"api_key": API_KEY, "state": "", "month": "", "type": "Calle", "page": 1, "page_size": 5}),
        ("events_carousel", f"https://www.tiempometa.com/api3/js_site/events_carousel",
         {"api_key": API_KEY, "ranking": "C", "page_size": 5}),
        ("smart_events", f"https://www.tiempometa.com/api/js_site/smart_events",
         {"api_key": API_KEY, "page": 1, "page_size": 5}),
    ]
    headers_with_referer = {"Referer": "https://carrerasmexico.com/", "Origin": "https://carrerasmexico.com"}
    import httpx as _httpx
    for label, url, params in probe_variations:
        try:
            # Try direct httpx call so we control headers entirely (skip http_client proxy chain)
            r = _httpx.get(url, params={**params, "callback": "cb"}, headers=headers_with_referer, timeout=20, follow_redirects=True)
            body_preview = r.text[:300].replace("\n", " ")
            print(f"[{SOURCE_NAME}] PROBE {label}: HTTP {r.status_code}; len={len(r.text)}; body[:300]={body_preview}")
        except Exception as e:
            print(f"[{SOURCE_NAME}] PROBE {label}: exception {e}")
    print(f"[{SOURCE_NAME}] === end probe ===")

    debugged = False
    for month in _months_ahead(12):
        page = 1
        while True:
            params = {
                "api_key": API_KEY,
                "type": "Calle",       # road races only
                "month": month,
                "state": "",
                "page": page,
                "page_size": PAGE_SIZE,
                "callback": "cb",
            }
            try:
                resp = get(API, params=params, source=SOURCE_NAME, timeout=30)
                resp.raise_for_status()
            except Exception as e:
                print(f"[{SOURCE_NAME}] {month} p{page}: erro {e}")
                break

            data = _parse_jsonp(resp.text)
            if data is None:
                print(f"[{SOURCE_NAME}] {month} p{page}: jsonp parse falhou; raw[:200]={resp.text[:200]}")
                break

            if not debugged:
                print(f"[{SOURCE_NAME}] PROBE month={month} keys={list(data.keys())}")
                events_dbg = data.get("events") or data.get("data") or []
                if events_dbg:
                    print(f"[{SOURCE_NAME}] PROBE first event keys: {list(events_dbg[0].keys())}")
                    print(f"[{SOURCE_NAME}] PROBE first event: {json.dumps(events_dbg[0], ensure_ascii=False)[:600]}")
                debugged = True

            events = data.get("events") or data.get("data") or []
            if not events:
                break

            for ev in events:
                try:
                    c = _parse_event(ev, today, now)
                    if c and c.id not in corridas:
                        corridas[c.id] = c
                except Exception as e:
                    print(f"[{SOURCE_NAME}] erro parse: {e}")

            total = data.get("total") or data.get("total_count") or 0
            if page * PAGE_SIZE >= total or len(events) < PAGE_SIZE:
                break
            page += 1

    result = list(corridas.values())
    print(f"[{SOURCE_NAME}] {len(result)} corridas encontradas")
    return result


def _parse_jsonp(text: str) -> dict | None:
    """Strip the JSONP wrapper: cb({...}); → {...}"""
    text = text.strip()
    # Find first '(' and last ')'
    lp = text.find("(")
    rp = text.rfind(")")
    if lp < 0 or rp < 0 or rp <= lp:
        # Maybe already JSON
        try:
            return json.loads(text)
        except Exception:
            return None
    inner = text[lp + 1:rp]
    try:
        return json.loads(inner)
    except Exception:
        return None


def _parse_event(ev: dict, today: str, now: str) -> Corrida | None:
    # Tiempometa event field names — discovered from the probe
    nombre = (ev.get("name") or ev.get("title") or ev.get("event_name") or "").strip()
    titulo = normalize_titulo(nombre)
    if not titulo or len(titulo) < 3:
        return None

    # Date: try multiple field names
    date_raw = (
        ev.get("event_date") or ev.get("date") or ev.get("start_date")
        or ev.get("fecha") or ""
    )
    data_evento = _normalize_date(date_raw)
    if not data_evento or data_evento < today:
        return None

    # Location
    estado_raw = (ev.get("state") or ev.get("estado") or "").strip()
    estado = _NORMALIZE_UF.get(estado_raw, estado_raw)
    cidade = (ev.get("city") or ev.get("ciudad") or ev.get("location") or "").strip()
    if not estado:
        _pais_geo, est_geo = _geo.resolve(cidade, "", "MX")
        estado = est_geo or ""
    localizacao = f"{cidade}, {estado}" if cidade and estado else cidade or estado or "México"

    # Distances
    distancias = _extract_distances(ev)

    # Event URL — registration or info page
    event_url = (
        ev.get("registration_url") or ev.get("url") or ev.get("link")
        or ev.get("event_url") or BASE
    )

    # Image
    imagem_url = ev.get("image_url") or ev.get("image") or ev.get("photo") or None

    event_id = ev.get("id") or ev.get("event_id") or slugify(titulo)
    fonte = FonteInfo(
        nome=SOURCE_NAME,
        link_evento=str(event_url),
        links_inscricao=[str(event_url)] if event_url and event_url != BASE else [],
    )
    return Corrida(
        id=f"cm_{event_id}",
        titulo=titulo,
        data_evento=data_evento,
        horario=_extract_time(ev),
        localizacao=localizacao,
        cidade=cidade,
        estado=estado or "",
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


def _normalize_date(raw: str) -> str | None:
    if not raw:
        return None
    s = str(raw).strip()
    # Already ISO?
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    # DD/MM/YYYY
    m = re.match(r"^(\d{1,2})[/-](\d{1,2})[/-](\d{4})$", s)
    if m:
        return f"{m.group(3)}-{m.group(2).zfill(2)}-{m.group(1).zfill(2)}"
    return None


def _extract_time(ev: dict) -> str | None:
    for k in ("start_time", "time", "horario", "hora"):
        v = ev.get(k)
        if v:
            m = re.search(r"(\d{1,2}):(\d{2})", str(v))
            if m:
                return f"{int(m.group(1)):02d}:{m.group(2)}"
    return None


def _extract_distances(ev: dict) -> list[Distancia]:
    """Pull km values from any distance field or from the title."""
    seen: set[float] = set()
    result: list[Distancia] = []

    # Try structured distances
    for k in ("distances", "subevents", "categorias", "modalidades"):
        items = ev.get(k)
        if isinstance(items, list):
            for it in items:
                if isinstance(it, dict):
                    raw = it.get("distance") or it.get("km") or it.get("name") or it.get("title")
                elif isinstance(it, (int, float)):
                    raw = it
                else:
                    raw = str(it)
                km = _parse_km(raw)
                if km is not None and km not in seen:
                    seen.add(km)
                    result.append(Distancia(km=km, data=None, horario=None))

    # Fallback: parse from title/description
    if not result:
        text = " ".join(str(ev.get(k) or "") for k in ("name", "title", "description", "subtitle"))
        for n in re.findall(r"\b(\d+(?:[.,]\d+)?)\s*[kK](?:m|M)?\b", text):
            km = float(n.replace(",", "."))
            key = round(km)
            canon = _CANON_KM.get(key, km)
            if canon not in seen and 3 <= canon <= 200:
                seen.add(canon)
                result.append(Distancia(km=canon, data=None, horario=None))

    return sorted(result, key=lambda d: d.km if isinstance(d.km, (int, float)) else 999)


def _parse_km(raw) -> float | None:
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        km = float(raw)
        return km if 1 <= km <= 200 else None
    s = str(raw).strip().lower()
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*k", s)
    if not m:
        return None
    km = float(m.group(1).replace(",", "."))
    key = round(km)
    km = _CANON_KM.get(key, km)
    return km if 1 <= km <= 200 else None
