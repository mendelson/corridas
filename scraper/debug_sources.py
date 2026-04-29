"""Debug script: fetches each source and saves HTML structure + scrape results."""
from __future__ import annotations
import json, re, traceback
from pathlib import Path
from bs4 import BeautifulSoup
from .http_client import get

OUTPUT = Path(__file__).parent.parent / "debug" / "source_debug.json"
OUTPUT.parent.mkdir(exist_ok=True)

SOURCES_HTTP = [
    ("Correr Brasília",     "https://correrbrasilia.com.br/calendario/"),
    ("Corridas BR",         "https://www.corridasbr.com.br/df/calendario.asp"),
    ("Corridas Brasil",     "https://corridasbrasil.com.br/calendario/"),
    ("Brasil que Corre",    "https://brasilquecorre.com/distritofederal"),
    ("Central da Corrida",  "https://centraldacorrida.com.br/corridas/?estado=df"),
    ("Minhas Inscrições",   "https://minhasinscricoes.com.br/pt-br/calendario?url=corrida-de-rua"),
    ("LiveRun",             "https://www.liverun.com.br/"),
    ("Runner Brasil",       "https://www.runnerbrasil.com.br/"),
    ("Brasil Corrida",      "https://brasilcorrida.com.br/"),
    ("Bora Correr",         "https://coelhodeprograma.com.br/boracorrer/"),
    ("TF Sports",           "https://www.tfsports.com.br/run-series/"),
    ("SESC DF",             "https://www.sescdf.com.br/corridas"),
    ("BMW Berlin",          "https://www.bmw-berlin-marathon.com/en/"),
    ("Boston",              "https://www.baa.org/races/boston-marathon/"),
    ("Chicago",             "https://www.chicagomarathon.com/"),
    ("London",              "https://www.tcslondonmarathon.com/"),
    ("NYC",                 "https://www.nyrr.org/races/tcsnycmarathon"),
    ("Sydney",              "https://www.tcssydneymarathon.com.au/"),
    ("Tokyo",               "https://www.marathon.tokyo/en/"),
]

def _top_classes(soup, n=20):
    """Most common CSS classes in the page."""
    from collections import Counter
    counter = Counter()
    for tag in soup.find_all(True):
        for cls in (tag.get("class") or []):
            counter[cls] += 1
    return counter.most_common(n)

def _table_sample(soup):
    """Sample first table rows."""
    tables = soup.find_all("table")
    result = []
    for i, tbl in enumerate(tables[:3]):
        rows = tbl.find_all("tr")
        sample = []
        for row in rows[:5]:
            cells = [td.get_text(" ", strip=True)[:80] for td in row.find_all(["td","th"])]
            links = [a["href"] for a in row.find_all("a", href=True)]
            sample.append({"cells": cells, "links": links})
        result.append({"table_index": i, "total_rows": len(rows), "sample_rows": sample})
    return result

def _article_sample(soup):
    """Sample first articles/events."""
    result = []
    for sel in [".event", ".race", "article", ".card", ".item", ".post"]:
        els = soup.select(sel)
        if len(els) >= 2:
            sample = []
            for el in els[:5]:
                txt = el.get_text(" ", strip=True)[:200]
                links = [(a.get_text(strip=True)[:50], a["href"]) for a in el.find_all("a", href=True)][:3]
                classes = list(set(c for t in el.find_all(True) for c in (t.get("class") or [])))[:10]
                sample.append({"text": txt, "links": links, "inner_classes": classes})
            result.append({"selector": sel, "count": len(els), "sample": sample})
            break
    return result

def _og_meta(soup):
    og = {}
    for tag in soup.find_all("meta"):
        prop = tag.get("property","") or tag.get("name","")
        if prop.startswith("og:") or prop in ("description","keywords"):
            og[prop] = tag.get("content","")[:150]
    return og

def debug_source(name, url):
    result = {"name": name, "url": url, "status": None, "error": None}
    try:
        resp = get(url)
        result["status"] = resp.status_code
        if resp.status_code != 200:
            result["error"] = f"HTTP {resp.status_code}"
            return result
        soup = BeautifulSoup(resp.text, "lxml")
        result["title"] = (soup.find("title") or soup.new_tag("x")).get_text(strip=True)[:100]
        result["top_classes"] = _top_classes(soup)
        result["tables"] = _table_sample(soup)
        result["articles"] = _article_sample(soup)
        result["og_meta"] = _og_meta(soup)
        # Raw text snippet
        result["text_snippet"] = soup.get_text(" ", strip=True)[:500]
    except Exception as e:
        result["error"] = traceback.format_exc()[-300:]
    return result

def main():
    results = []
    for name, url in SOURCES_HTTP:
        print(f"  fetching {name}...")
        r = debug_source(name, url)
        results.append(r)
        print(f"    status={r['status']} error={r.get('error','')[:60]}")

    OUTPUT.write_text(json.dumps(results, ensure_ascii=False, indent=2))
    print(f"\nSaved to {OUTPUT}")

if __name__ == "__main__":
    main()
