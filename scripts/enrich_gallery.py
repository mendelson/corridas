#!/usr/bin/env python3
"""Enrich web/gallery/races.json from the Strava + Polar links on each event.

The personal gallery (web/gallery/races.json) lists hand-curated runs. Some
entries are added with only their Strava and Polar share links and every other
field blank. This script fills the blanks by reading those public pages:

  * name  -> the Strava activity title (emojis stripped). Strava is the source
             of truth for titles, per product decision.
  * date  -> the activity date (Polar share page, falling back to Strava).
  * km    -> the distance (Polar, falling back to Strava), snapped to the
             canonical 21.097 / 42.195 when close.
  * type  -> inferred from km (marathon / half / ten / race).
  * city/estado/pais -> best-effort from the Strava location line.

It only ever *fills blank* fields — values already present are left untouched —
so it is safe to re-run and is the reusable mechanism for future additions.

The Strava/Polar hosts are blocked from the dev sandbox, so this runs in CI
(the runner has internet) via .github/workflows/enrich-gallery.yml.

Usage:
  python scripts/enrich_gallery.py            # enrich in place
  python scripts/enrich_gallery.py --dump-dir gallery-debug   # also save HTML
"""
import argparse
import json
import os
import re
import sys
import unicodedata
from pathlib import Path

RACES = Path("web/gallery/races.json")

# --- emoji / title cleanup -------------------------------------------------
_EMOJI = re.compile(
    "["
    "\U0001F300-\U0001FAFF"   # symbols & pictographs, emoji extensions
    "\U00002600-\U000027BF"   # misc symbols + dingbats
    "\U0001F1E6-\U0001F1FF"   # regional indicators (flags)
    "\U0000FE00-\U0000FE0F"   # variation selectors
    "\U00002190-\U000021FF"   # arrows (often decorative)
    "\U00002B00-\U00002BFF"   # misc symbols & arrows
    "\U0000200D"              # zero-width joiner
    "]+",
    flags=re.UNICODE,
)
_STRAVA_PREFIX = re.compile(r".*\bStrava\s*[:：]\s*", re.IGNORECASE | re.DOTALL)
_STRAVA_SUFFIX = re.compile(r"\s*[|\-–—·]\s*Strava\s*$", re.IGNORECASE)


def clean_title(raw: str) -> str:
    if not raw:
        return ""
    s = raw.strip()
    # "Mateus on Strava: <title>" / "... no Strava: <title>" -> "<title>"
    m = _STRAVA_PREFIX.match(s)
    if m:
        s = s[m.end():]
    s = _STRAVA_SUFFIX.sub("", s)        # "<title> | Strava" -> "<title>"
    s = _EMOJI.sub("", s)
    s = s.replace("’", "'").strip()
    s = re.sub(r"\s{2,}", " ", s)
    return s.strip(" -–—·|").strip()


# --- distance / type -------------------------------------------------------
def snap_km(km: float):
    if km is None:
        return ""
    if 20.4 <= km <= 21.7:
        return 21.097
    if 41.4 <= km <= 42.7:
        return 42.195
    if 9.6 <= km <= 10.4:
        return 10.0
    return round(km, 1)


def infer_type(km) -> str:
    try:
        v = float(km)
    except (TypeError, ValueError):
        return ""
    if v >= 41.4:
        return "marathon"
    if 20.4 <= v <= 21.7:
        return "half"
    if 9.6 <= v <= 10.4:
        return "ten"
    return "race"


_KM_RE = re.compile(r"(\d{1,3}[.,]\d{1,3})\s*km", re.IGNORECASE)
_DATE_PATTERNS = [
    (re.compile(r"(\d{4})-(\d{2})-(\d{2})"), lambda m: f"{m[1]}-{m[2]}-{m[3]}"),
    (re.compile(r"(\d{2})[./](\d{2})[./](\d{4})"), lambda m: f"{m[3]}-{m[2]}-{m[1]}"),
]


def parse_km(text: str):
    if not text:
        return None
    best = None
    for m in _KM_RE.finditer(text):
        v = float(m.group(1).replace(",", "."))
        if 1 <= v <= 300 and (best is None or v > best):
            best = v
    return best


_PT_MONTHS = {"janeiro": "01", "fevereiro": "02", "marco": "03", "abril": "04",
              "maio": "05", "junho": "06", "julho": "07", "agosto": "08",
              "setembro": "09", "outubro": "10", "novembro": "11", "dezembro": "12"}
_PT_DATE = re.compile(r"(\d{1,2})\s+de\s+([a-zç]+)\s+de\s+(\d{4})", re.IGNORECASE)


def parse_date(text: str):
    if not text:
        return None
    for rx, fmt in _DATE_PATTERNS:
        m = rx.search(text)
        if m:
            return fmt(m)
    m = _PT_DATE.search(text)
    if m:
        mon = _PT_MONTHS.get(_norm(m.group(2)))
        if mon:
            return f"{m.group(3)}-{mon}-{int(m.group(1)):02d}"
    return None


# --- page fetching (Playwright) -------------------------------------------
def fetch_pages(strava_url, polar_url, dump_dir=None, tag=""):
    """Return dict with raw text/og fields scraped from both pages."""
    from playwright.sync_api import sync_playwright

    out = {"strava_title": "", "strava_desc": "", "strava_loc": "",
           "strava_text": "", "polar_text": "", "final_strava": ""}
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox"])
        ctx = browser.new_context(
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
            locale="pt-BR", viewport={"width": 1280, "height": 900},
        )
        pg = ctx.new_page()

        if strava_url:
            try:
                pg.goto(strava_url, wait_until="domcontentloaded", timeout=45000)
                pg.wait_for_timeout(3500)
                out["final_strava"] = pg.url
                out["strava_title"] = _meta(pg, "og:title")
                out["strava_desc"] = _meta(pg, "og:description")
                out["strava_loc"] = pg.evaluate(
                    "()=>{const e=document.querySelector('.location, [class*=location], .activity-summary .location');return e?e.textContent.trim():''}")
                out["strava_text"] = pg.evaluate("()=>document.body?document.body.innerText.slice(0,4000):''")
                if dump_dir:
                    Path(dump_dir, f"strava_{tag}.html").write_text(pg.content(), encoding="utf-8")
            except Exception as e:
                print(f"   strava fetch error: {e}", file=sys.stderr)

        if polar_url:
            try:
                pg.goto(polar_url, wait_until="domcontentloaded", timeout=45000)
                pg.wait_for_timeout(4500)
                out["polar_text"] = pg.evaluate("()=>document.body?document.body.innerText.slice(0,4000):''")
                if dump_dir:
                    Path(dump_dir, f"polar_{tag}.html").write_text(pg.content(), encoding="utf-8")
            except Exception as e:
                print(f"   polar fetch error: {e}", file=sys.stderr)

        ctx.close(); browser.close()
    return out


def _meta(pg, prop):
    try:
        return pg.evaluate(
            "(p)=>{const m=document.querySelector(`meta[property='${p}']`)||document.querySelector(`meta[name='${p}']`);return m?m.content:''}",
            prop) or ""
    except Exception:
        return ""


# --- location (best-effort) ------------------------------------------------
_BR_STATES = None


def br_uf(name):
    global _BR_STATES
    if _BR_STATES is None:
        _BR_STATES = {}
        try:
            j = json.load(open("web/locations/BR.json", encoding="utf-8"))
            for s in j.get("subdivisions", []):
                _BR_STATES[_norm(s["name"])] = s["code"]
        except Exception:
            pass
    return _BR_STATES.get(_norm(name), "")


def _norm(s):
    return unicodedata.normalize("NFD", s or "").encode("ascii", "ignore").decode().lower().strip()


def parse_location(text):
    """From a 'City, State, Country' style string return (city, estado, pais)."""
    if not text:
        return "", "", ""
    parts = [p.strip() for p in re.split(r"[,•·|]", text) if p.strip()]
    if not parts:
        return "", "", ""
    city = parts[0]
    pais, estado = "", ""
    joined = _norm(text)
    if "bra" in joined.split()[-1:][0] if joined.split() else "":
        pais = "BR"
    if "brazil" in joined or "brasil" in joined:
        pais = "BR"
    if pais == "BR" and len(parts) >= 2:
        estado = br_uf(parts[1])
    return city, estado, pais


# --- main ------------------------------------------------------------------
def needs_enrich(r):
    return (not r.get("name") or not r.get("date") or r.get("km") in ("", None)
            or not r.get("type"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump-dir", default=None)
    args = ap.parse_args()
    if args.dump_dir:
        Path(args.dump_dir).mkdir(parents=True, exist_ok=True)

    races = json.loads(RACES.read_text(encoding="utf-8"))
    changed = 0
    for i, r in enumerate(races):
        # always normalise the title (strips any "| Strava" / emojis), even if
        # already set — fixes earlier runs that kept Strava's suffix.
        if r.get("name"):
            c = clean_title(r["name"])
            if c != r["name"]:
                print(f"[{i}] name normalized: {r['name']!r} -> {c!r}")
                r["name"] = c; changed += 1
        # cheap fix first: type can be inferred from an existing km
        if not r.get("type") and r.get("km") not in ("", None):
            r["type"] = infer_type(r["km"]); changed += 1
            print(f"[{i}] type <- {r['type']} (from km {r['km']})")

        if not (not r.get("name") or not r.get("date") or r.get("km") in ("", None)):
            continue
        strava, polar = r.get("strava", ""), r.get("deviceUrl", "")
        if "polar.com" not in polar:
            polar = ""
        print(f"[{i}] fetching: strava={strava} polar={polar}")
        d = fetch_pages(strava, polar, args.dump_dir, tag=str(i))
        print(f"      strava og:title={d['strava_title']!r}")
        print(f"      strava og:desc={d['strava_desc'][:160]!r}")
        print(f"      strava loc={d['strava_loc']!r} final={d['final_strava']}")
        print(f"      polar text head={d['polar_text'][:160]!r}")

        if not r.get("name"):
            nm = clean_title(d["strava_title"])
            if nm:
                r["name"] = nm; changed += 1; print(f"      name <- {nm!r}")
        if r.get("km") in ("", None):
            km = parse_km(d["strava_desc"]) or parse_km(d["strava_text"]) or parse_km(d["polar_text"])
            if km:
                r["km"] = snap_km(km); changed += 1; print(f"      km <- {r['km']}")
        if not r.get("type") and r.get("km") not in ("", None):
            r["type"] = infer_type(r["km"]); print(f"      type <- {r['type']}")
        if not r.get("date"):
            dt = parse_date(d["polar_text"]) or parse_date(d["strava_text"]) or parse_date(d["strava_desc"])
            if dt:
                r["date"] = dt; changed += 1; print(f"      date <- {dt}")
        if not r.get("city"):
            city, estado, pais = parse_location(d["strava_loc"])
            if city:
                r["city"] = city; changed += 1; print(f"      city <- {city!r}")
            if estado and not r.get("estado"):
                r["estado"] = estado
            if pais and not r.get("pais"):
                r["pais"] = pais

    RACES.write_text(json.dumps(races, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\nDone. fields changed: {changed}")
    # report still-missing
    miss = [(i, [k for k in ("name", "date", "km", "type", "city", "pais", "estado") if r.get(k) in ("", None)])
            for i, r in enumerate(races) if needs_enrich(r) or not r.get("city")]
    if miss:
        print("Still missing:")
        for i, ks in miss:
            print(f"  [{i}] {ks}  strava={races[i].get('strava','')}")


if __name__ == "__main__":
    main()
