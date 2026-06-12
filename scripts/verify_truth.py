#!/usr/bin/env python3
"""Amostral truth-checker: stored event data vs the source page itself.

The data-quality tests guarantee VALIDITY (every event has a plausible state,
link, distances). They cannot catch a value that is wrong-but-valid — e.g. an
event displayed as "Brasília, DF" whose own source page says "Pirenópolis-GO"
(the CPTR case, 2026-06-12). This script closes that gap by sampling events
daily, re-fetching each fonte page and comparing INDEPENDENTLY of the scraper
that produced the record:

  1. schema.org Event JSON-LD on the page → startDate / addressRegion /
     street-address "Cidade - UF" tail  (high precision);
  2. BR-only fallback: a "Cidade-UF" pattern scan over the page text — flags
     only when the stored UF appears in no pattern at all while a single other
     UF dominates (≥3 hits, unanimous)  (tuned for precision over recall).

Severity: location divergence = ERRO (workflow fails); date divergence =
SUSPEITA (warning only — postponements are legit and the next scrape syncs).

State lives in data/truth-check.json: per-event last-checked timestamps (an
event is not resampled for RECHECK_DAYS) + the latest findings.
"""
from __future__ import annotations

import json
import random
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bs4 import BeautifulSoup

from scraper.http_client import get

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "corridas.json"
STATE = ROOT / "data" / "truth-check.json"

SAMPLE_SIZE = 40
RECHECK_DAYS = 14
FETCH_TIMEOUT = 20

_UFS = set("AC AL AM AP BA CE DF ES GO MA MG MS MT PA PB PE PI PR RJ RN RO RR RS SC SE SP TO".split())
# "Pirenópolis-GO", "Formosa - GO", "Palmas/PR" — em texto de página.
_CITY_UF_RE = re.compile(r"[A-Za-zÀ-ÿ.'’]\s*[-/–]\s*([A-Z]{2})\b")
_STREET_UF_RE = re.compile(r"-\s*([A-Z]{2})\s*,?\s*\d{5}-?\d{3}")


def _jsonld_events(soup: BeautifulSoup) -> list[dict]:
    out = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except Exception:
            continue
        for item in data if isinstance(data, list) else [data]:
            if isinstance(item, dict) and item.get("@type") in ("Event", "SportsEvent"):
                out.append(item)
    return out


def _jsonld_facts(items: list[dict]) -> tuple[set[str], set[str]]:
    """(dates, BR UFs) declared by the page's own JSON-LD."""
    dates: set[str] = set()
    ufs: set[str] = set()
    for ev in items:
        sd = ev.get("startDate") or ""
        if re.match(r"\d{4}-\d{2}-\d{2}", sd):
            dates.add(sd[:10])
        locs = ev.get("location") or []
        for place in locs if isinstance(locs, list) else [locs]:
            if not isinstance(place, dict):
                continue
            addr = place.get("address") or {}
            if isinstance(addr, dict):
                region = (addr.get("addressRegion") or "").strip().upper()
                if region in _UFS:
                    ufs.add(region)
                street = addr.get("streetAddress") or ""
                m = _STREET_UF_RE.search(street)
                if m and m.group(1) in _UFS:
                    ufs.add(m.group(1))
    return dates, ufs


def _pattern_ufs(text: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for m in _CITY_UF_RE.finditer(text):
        uf = m.group(1)
        if uf in _UFS:
            counts[uf] = counts.get(uf, 0) + 1
    return counts


def check_event(ev: dict) -> dict:
    """Fetch the first fonte page and compare. Returns a finding dict."""
    fonte = (ev.get("fontes") or [{}])[0]
    url = fonte.get("link_evento") or (fonte.get("links_inscricao") or [""])[0]
    base = {"id": ev.get("id"), "titulo": ev.get("titulo"),
            "estado": ev.get("estado"), "pais": ev.get("pais"),
            "data_evento": ev.get("data_evento"), "url": url,
            "fonte": fonte.get("nome")}
    if not url:
        return {**base, "status": "sem_url"}
    try:
        resp = get(url, timeout=FETCH_TIMEOUT)
        if resp.status_code != 200:
            return {**base, "status": "inacessivel", "http": resp.status_code}
        html = resp.text
    except Exception as e:
        return {**base, "status": "inacessivel", "erro": str(e)[:120]}

    soup = BeautifulSoup(html, "lxml")
    dates, jsonld_ufs = _jsonld_facts(_jsonld_events(soup))

    problemas: list[str] = []
    avisos: list[str] = []

    # 1. JSON-LD (alta precisão)
    if ev.get("pais") == "BR" and jsonld_ufs and ev.get("estado") not in jsonld_ufs:
        problemas.append(f"UF: página declara {sorted(jsonld_ufs)}, site exibe {ev.get('estado')}")
    if dates and ev.get("data_evento") not in dates:
        avisos.append(f"data: página declara {sorted(dates)}, site exibe {ev.get('data_evento')}")

    # 2. Varredura de padrões Cidade-UF (BR; só contradição forte)
    if ev.get("pais") == "BR" and not jsonld_ufs:
        counts = _pattern_ufs(soup.get_text(" ", strip=True))
        stored = ev.get("estado")
        if counts and stored not in counts:
            dominant, hits = max(counts.items(), key=lambda kv: kv[1])
            if hits >= 3 and len(counts) == 1:
                problemas.append(
                    f"UF: página menciona apenas {dominant} ({hits}×), site exibe {stored}"
                )

    if problemas:
        return {**base, "status": "erro", "problemas": problemas, "avisos": avisos}
    if avisos:
        return {**base, "status": "suspeita", "avisos": avisos}
    return {**base, "status": "ok"}


def pick_sample(corridas: list[dict], checked: dict[str, str]) -> list[dict]:
    today = date.today().isoformat()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=RECHECK_DAYS)).isoformat()
    eligible = [c for c in corridas
                if (c.get("data_evento") or "") >= today
                and checked.get(c.get("id") or "", "") < cutoff]
    single = [c for c in eligible if len(c.get("fontes") or []) == 1]
    multi = [c for c in eligible if len(c.get("fontes") or []) > 1]
    random.shuffle(single)
    random.shuffle(multi)
    n_single = min(len(single), int(SAMPLE_SIZE * 0.75))
    return single[:n_single] + multi[: SAMPLE_SIZE - n_single]


def main() -> None:
    data = json.loads(DATA.read_text(encoding="utf-8"))
    corridas = data["corridas"] if isinstance(data, dict) else data

    state = {}
    if STATE.exists():
        try:
            state = json.loads(STATE.read_text(encoding="utf-8"))
        except Exception:
            state = {}
    checked: dict[str, str] = state.get("checked", {})

    sample = pick_sample(corridas, checked)
    now = datetime.now(timezone.utc).isoformat()
    findings = []
    for ev in sample:
        f = check_event(ev)
        findings.append(f)
        checked[ev.get("id") or ""] = now
        mark = {"ok": "✅", "erro": "❌", "suspeita": "⚠️"}.get(f["status"], "•")
        print(f"{mark} {f['status']:11} | {(f.get('titulo') or '')[:45]:45} | {f.get('fonte')}")
        for p in f.get("problemas", []) + f.get("avisos", []):
            print(f"      ↳ {p}")

    # Janela móvel do estado: ids antigos saem para o arquivo não crescer sem fim.
    horizon = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()
    checked = {k: v for k, v in checked.items() if v >= horizon}
    erros = [f for f in findings if f["status"] == "erro"]
    state = {"verificado_em": now, "checked": checked,
             "ultimo_resultado": {
                 "amostra": len(findings),
                 "erros": len(erros),
                 "suspeitas": sum(1 for f in findings if f["status"] == "suspeita"),
                 "inacessiveis": sum(1 for f in findings if f["status"] == "inacessivel"),
                 "achados": [f for f in findings if f["status"] in ("erro", "suspeita")],
             }}
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=1) + "\n",
                     encoding="utf-8")

    print(f"\nAmostra: {len(findings)} | erros: {len(erros)} | "
          f"suspeitas: {state['ultimo_resultado']['suspeitas']} | "
          f"inacessíveis: {state['ultimo_resultado']['inacessiveis']}")
    if erros:
        print("\nDIVERGÊNCIA DE LOCALIZAÇÃO CONFIRMADA:", file=sys.stderr)
        for f in erros:
            print(f"  ❌ {f['titulo']} — {'; '.join(f['problemas'])} — {f['url']}",
                  file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
