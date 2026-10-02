"""Render the per-language share cards web/og-{lang}.png (1200×630).

Every language shell points og:image / twitter:image at its own card, so a
link shared in Japanese previews in Japanese. The cards are plain text on the
site's dark background — headline in two lines (accent + white), subtitle,
tagline, distance pills and the domain — rendered by Chromium from HTML, which
gets shaping right for every script the site ships (Thai, Hebrew RTL, CJK)
without a font pipeline of our own.

Latin, Cyrillic, Greek and Hebrew use DejaVu Sans (what the original five cards
were drawn with); CJK and Thai fall back to Noto Sans from Google Fonts, so the
machine running this needs network access. It is a manual tool — run it when a
language is added or its copy changes; it is not part of the data pipeline.

  python scripts/generate_og_images.py            # only cards that are missing
  python scripts/generate_og_images.py ja th he   # (re)render these
  python scripts/generate_og_images.py --all      # re-render every card
"""
from __future__ import annotations

import html
import re
import sys
import urllib.request
from pathlib import Path

from generate_sitemap import LANGS

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"

# headline line 1 (accent), line 2 (white), subtitle, tagline
COPY: dict[str, tuple[str, str, str, str]] = {
    "pt": ("PRÓXIMA", "CORRIDA", "Calendário de corridas de rua", "Datas, distâncias e inscrições sempre atualizadas"),
    "en": ("NEXT", "RACE", "Road running race calendar", "Dates, distances and registrations always up to date"),
    "es": ("PRÓXIMA", "CARRERA", "Calendario de carreras de calle", "Fechas, distancias e inscripciones siempre actualizadas"),
    "de": ("NÄCHSTES", "RENNEN", "Laufkalender für Straßenläufe", "Termine, Distanzen und Anmeldungen immer aktuell"),
    "fr": ("PROCHAINE", "COURSE", "Calendrier des courses sur route", "Dates, distances et inscriptions toujours à jour"),
    "it": ("PROSSIMA", "GARA", "Calendario delle corse su strada", "Date, distanze e iscrizioni sempre aggiornate"),
    "nl": ("VOLGENDE", "WEDSTRIJD", "Hardloopkalender voor wegwedstrijden", "Data, afstanden en inschrijvingen altijd actueel"),
    "pt-pt": ("PRÓXIMA", "CORRIDA", "Calendário de corridas de estrada", "Datas, distâncias e inscrições sempre atualizadas"),
    "ru": ("СЛЕДУЮЩИЙ", "ЗАБЕГ", "Календарь шоссейных забегов", "Даты, дистанции и регистрация — всегда актуально"),
    "pl": ("NASTĘPNY", "BIEG", "Kalendarz biegów ulicznych", "Daty, dystanse i zapisy zawsze aktualne"),
    "cs": ("DALŠÍ", "ZÁVOD", "Kalendář silničních běhů", "Termíny, vzdálenosti a registrace vždy aktuální"),
    "sk": ("ĎALŠÍ", "BEH", "Kalendár cestných behov", "Termíny, vzdialenosti a registrácie vždy aktuálne"),
    "sl": ("NASLEDNJI", "TEK", "Koledar cestnih tekov", "Datumi, razdalje in prijave vedno ažurni"),
    "hr": ("SLJEDEĆA", "UTRKA", "Kalendar cestovnih utrka", "Datumi, udaljenosti i prijave uvijek ažurni"),
    "hu": ("KÖVETKEZŐ", "VERSENY", "Országúti futóversenyek naptára", "Időpontok, távok és nevezések mindig naprakészen"),
    "el": ("ΕΠΟΜΕΝΟΣ", "ΑΓΩΝΑΣ", "Ημερολόγιο αγώνων δρόμου", "Ημερομηνίες, αποστάσεις και εγγραφές πάντα ενημερωμένες"),
    "da": ("NÆSTE", "LØB", "Løbskalender for gadeløb", "Datoer, distancer og tilmeldinger altid opdateret"),
    "nb": ("NESTE", "LØP", "Løpskalender for gateløp", "Datoer, distanser og påmeldinger alltid oppdatert"),
    "sv": ("NÄSTA", "LOPP", "Loppkalender för gatulopp", "Datum, distanser och anmälningar alltid aktuella"),
    "fi": ("SEURAAVA", "JUOKSU", "Maantiejuoksujen kalenteri", "Päivämäärät, matkat ja ilmoittautumiset aina ajan tasalla"),
    "ja": ("次の", "レースへ", "ロードレースカレンダー", "日程・距離・エントリー情報を常に最新に"),
    "ko": ("다음", "레이스", "로드 레이스 캘린더", "일정, 거리, 참가 신청 정보를 항상 최신으로"),
    "zh-cn": ("下一场", "比赛", "路跑赛事日历", "日期、距离和报名信息实时更新"),
    "zh-tw": ("下一場", "比賽", "路跑賽事行事曆", "日期、距離與報名資訊即時更新"),
    "th": ("งานวิ่ง", "ครั้งต่อไป", "ปฏิทินงานวิ่งถนน", "วันที่ ระยะทาง และการสมัครที่อัปเดตเสมอ"),
    "he": ("המרוץ", "הבא", "לוח מרוצי כביש", "תאריכים, מרחקים והרשמה — תמיד מעודכנים"),
    "id": ("LOMBA", "BERIKUTNYA", "Kalender lomba lari jalan raya", "Tanggal, jarak, dan pendaftaran selalu terbaru"),
    "ms": ("LARIAN", "SETERUSNYA", "Kalendar larian jalan raya", "Tarikh, jarak dan pendaftaran sentiasa dikemas kini"),
}

# Script-specific fallbacks after DejaVu Sans (which has no CJK or Thai).
EXTRA_FONT = {
    "ja": "Noto Sans JP", "ko": "Noto Sans KR", "zh-cn": "Noto Sans SC",
    "zh-tw": "Noto Sans TC", "th": "Noto Sans Thai",
}
HTML_LANG = {"pt": "pt-BR", "pt-pt": "pt-PT", "zh-cn": "zh-CN", "zh-tw": "zh-TW"}
RTL = {"he"}

TEMPLATE = """<!DOCTYPE html>
<html lang="{lang}" dir="{dir}"><head><meta charset="utf-8">
{font_link}
<style>
  html, body {{ margin: 0; width: 1200px; height: 630px; overflow: hidden; }}
  body {{ background: #0f0f0f; position: relative;
         font-family: 'DejaVu Sans', {extra} sans-serif; }}
  .stripes {{ position: absolute; inset: 0; overflow: hidden; }}
  .stripes i {{ position: absolute; top: -120px; width: 70px; height: 900px;
               background: #1c1411; transform: skewX(-25deg); opacity: .85; }}
  [dir=rtl] .stripes {{ transform: scaleX(-1); }}
  .box {{ position: absolute; inset-inline-start: 86px; top: 139px; width: 1000px; }}
  .h {{ font-weight: 700; line-height: 1.05; white-space: nowrap; letter-spacing: .02em; width: max-content; }}
  .h1 {{ color: #ff6b35; }}
  .h2 {{ color: #f0f0f0; margin-top: 8px; }}
  .sub {{ color: #f0f0f0; font-size: 40px; margin-top: 30px; white-space: nowrap; width: max-content; }}
  .tag {{ color: #9a9a9a; font-size: 33px; margin-top: 6px; white-space: nowrap; width: max-content; }}
  .pills {{ position: absolute; inset-inline-start: 86px; top: 528px; display: flex; gap: 14px; }}
  .pill {{ border: 2px solid #ff6b35; background: #331d15; color: #ff6b35; border-radius: 26px;
           font-size: 28px; font-weight: 700; padding: 8px 20px; line-height: 32px; }}
  .domain {{ position: absolute; inset-inline-end: 84px; top: 556px; color: #a8a8a8; font-size: 30px; }}
</style></head>
<body>
  <div class="stripes"><i style="left:900px"></i><i style="left:1030px"></i><i style="left:1160px"></i><i style="left:1290px"></i></div>
  <div class="box">
    <div class="h h1" id="h1">{h1}</div>
    <div class="h h2" id="h2">{h2}</div>
    <div class="sub" id="sub">{sub}</div>
    <div class="tag" id="tag">{tag}</div>
  </div>
  <div class="pills"><span class="pill">5K</span><span class="pill">10K</span><span class="pill">21K</span><span class="pill">42K</span></div>
  <div class="domain"><bdi dir="ltr">run.mmendelson.com</bdi></div>
</body></html>
"""

# Shrink the headline until both lines fit the text column (long words like
# "СЛЕДУЮЩИЙ" or "BERIKUTNYA" would otherwise run into the stripes).
FIT_JS = """async () => {
  const fit = (ids, size, max, min) => {
    const els = ids.map(id => document.getElementById(id));
    const fits = () => els.every(e => e.scrollWidth <= max);
    els.forEach(e => e.style.fontSize = size + 'px');
    while (!fits() && size > min) { size -= 1; els.forEach(e => e.style.fontSize = size + 'px'); }
    return size;
  };
  await document.fonts.ready;
  const size = fit(['h1', 'h2'], 104, 640, 56);
  // Subtitle and tagline must stay on one line each, inside the margins.
  fit(['sub'], 40, 1028, 24);
  fit(['tag'], 33, 1028, 20);
  // Resizing can pull in further font subsets (CJK fonts are split by
  // unicode-range); wait for those too before the screenshot.
  await document.fonts.ready;
  return size;
}"""


def page_html(lang: str) -> str:
    h1, h2, sub, tag = (html.escape(x) for x in COPY[lang])
    extra_font = EXTRA_FONT.get(lang)
    link = ""
    extra = ""
    if extra_font:
        fam = extra_font.replace(" ", "+")
        link = (f'<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
                f'family={fam}:wght@400;700&display=block">')
        extra = f"'{extra_font}',"
    return TEMPLATE.format(lang=HTML_LANG.get(lang, lang), dir="rtl" if lang in RTL else "ltr",
                           font_link=link, extra=extra, h1=h1, h2=h2, sub=sub, tag=tag)


_FONT_HOSTS = re.compile(r"https://fonts\.(googleapis|gstatic)\.com/.*")


def _fetch_font(route) -> None:
    """Serve Google Fonts requests through Python's own HTTP stack.

    The headless browser does not always share the machine's proxy and CA
    settings (it does not in the sandboxes this runs in), and a font that
    fails to load silently falls back to whatever the OS has — wrong weight,
    wrong glyphs. urllib honours HTTPS_PROXY and the system trust store.
    """
    req = urllib.request.Request(
        route.request.url, headers={"User-Agent": route.request.headers.get("user-agent", "")})
    with urllib.request.urlopen(req, timeout=60) as resp:
        body = resp.read()
        ctype = resp.headers.get("Content-Type", "application/octet-stream")
    route.fulfill(status=200, body=body,
                  headers={"Content-Type": ctype, "Access-Control-Allow-Origin": "*"})


def main(argv: list[str]) -> int:
    from playwright.sync_api import sync_playwright

    known = [p for p, _ in LANGS]
    missing_copy = [p for p in known if p not in COPY]
    if missing_copy:
        raise SystemExit(f"no share-card copy for: {missing_copy}")
    if "--all" in argv:
        targets = known
    elif argv:
        targets = [a for a in argv if not a.startswith("-")]
        unknown = [t for t in targets if t not in known]
        if unknown:
            raise SystemExit(f"unknown languages: {unknown}")
    else:
        targets = [p for p in known if not (WEB / f"og-{p}.png").exists()]
    if not targets:
        print("every share card exists (pass languages or --all to re-render)")
        return 0

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1200, "height": 630})
        page.route(_FONT_HOSTS, _fetch_font)
        for lang in targets:
            page.set_content(page_html(lang), wait_until="networkidle")
            size = page.evaluate(FIT_JS)
            page.wait_for_timeout(300)
            out = WEB / f"og-{lang}.png"
            page.screenshot(path=str(out), clip={"x": 0, "y": 0, "width": 1200, "height": 630})
            print(f"wrote {out.relative_to(ROOT)} (headline {size}px)")
        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
