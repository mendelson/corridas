"""Generate the language shells web/{lang}/index.html (and the root redirect
page web/index.html) from one template.

The site ships one static shell per UI language — 28 of them, the same set as
the Connect IQ Store listings. Hand-maintaining 28 copies of a 400-line page
is how they drift, so every shell is rendered from scripts/templates/shell.html:

  * UI strings (search box, filters, period options, empty state …) are read
    from the STRINGS table in web/app.js — the same text app.js applies at
    runtime, so the static HTML and the booted app can never disagree;
  * crawler-facing copy that app.js never touches (meta description, footer
    intro, a few aria-labels, the iOS home-screen title) lives in SEO below;
  * the language list itself comes from generate_sitemap.LANGS, which the
    sitemap, the pre-render step and the tests already share.

The pre-rendered event blocks inside each shell are owned by
generate_prerender.py (re-run after every scrape); this script carries them
over untouched, so regenerating the shells never wipes the SEO content. A
brand-new shell starts with empty blocks — run generate_prerender.py after it.

  python scripts/generate_shells.py          # (re)write every shell
  python scripts/generate_shells.py --check  # exit 1 if any shell is stale
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from generate_sitemap import BASE, LANGS  # single source of truth

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
TEMPLATE = ROOT / "scripts" / "templates" / "shell.html"

# Open Graph wants language_TERRITORY.
OG_LOCALES: dict[str, str] = {
    "pt": "pt_BR", "en": "en_US", "es": "es_ES", "de": "de_DE", "fr": "fr_FR",
    "it": "it_IT", "nl": "nl_NL", "pt-pt": "pt_PT", "ru": "ru_RU", "pl": "pl_PL",
    "cs": "cs_CZ", "sk": "sk_SK", "sl": "sl_SI", "hr": "hr_HR", "hu": "hu_HU",
    "el": "el_GR", "da": "da_DK", "nb": "nb_NO", "sv": "sv_SE", "fi": "fi_FI",
    "ja": "ja_JP", "ko": "ko_KR", "zh-cn": "zh_CN", "zh-tw": "zh_TW",
    "th": "th_TH", "he": "he_IL", "id": "id_ID", "ms": "ms_MY",
}

# Each language named in itself, for the crawlable footer links.
NATIVE_NAMES: dict[str, str] = {
    "pt": "Português (Brasil)", "en": "English", "es": "Español", "de": "Deutsch",
    "fr": "Français", "it": "Italiano", "nl": "Nederlands",
    "pt-pt": "Português (Portugal)", "ru": "Русский", "pl": "Polski",
    "cs": "Čeština", "sk": "Slovenčina", "sl": "Slovenščina", "hr": "Hrvatski",
    "hu": "Magyar", "el": "Ελληνικά", "da": "Dansk", "nb": "Norsk bokmål",
    "sv": "Svenska", "fi": "Suomi", "ja": "日本語", "ko": "한국어",
    "zh-cn": "简体中文", "zh-tw": "繁體中文", "th": "ไทย", "he": "עברית",
    "id": "Bahasa Indonesia", "ms": "Bahasa Melayu",
}

RTL = {"he"}

# Copy only the static page needs. `about` is HTML and must wrap the site name
# (STRINGS.headerTitle) in <strong> — the SEO tests look for it there.
SEO: dict[str, dict[str, str]] = {
    "pt": {
        "apple": "Corridas",
        "desc": "Calendário mundial de corridas de rua: Brasil, EUA, México, Europa e World Marathon Majors. Datas, distâncias (5K, 10K, 21K, 42K) e links de inscrição.",
        "about": "O <strong>Calendário de Corridas de Rua</strong> é mundial: encontre provas de 5K, 10K, meia maratona e maratona no Brasil e no mundo, com datas e links de inscrição sempre atualizados.",
        "list": "Lista de corridas", "langs": "Idiomas",
    },
    "en": {
        "apple": "Races",
        "desc": "Worldwide road race calendar: Brazil, USA, Mexico, Europe and the World Marathon Majors. Dates, distances (5K, 10K, half and full marathon) and registration links.",
        "about": "This <strong>Road Running Race Calendar</strong> is worldwide: find 5K, 10K, half marathon and marathon races across the globe, with up-to-date dates and registration links.",
        "list": "Race list", "langs": "Languages",
    },
    "es": {
        "apple": "Carreras",
        "desc": "Calendario mundial de carreras de calle: Brasil, EE. UU., México, Europa y World Marathon Majors. Fechas, distancias (5K, 10K, 21K, 42K) y enlaces de inscripción.",
        "about": "El <strong>Calendario de Carreras de Calle</strong> es mundial: encuentra pruebas de 5K, 10K, media maratón y maratón en todo el mundo, con fechas y enlaces de inscripción siempre actualizados.",
        "list": "Lista de carreras", "langs": "Idiomas",
    },
    "de": {
        "apple": "Läufe",
        "desc": "Weltweiter Laufkalender: Brasilien, USA, Mexiko, Europa und World Marathon Majors. Termine, Distanzen (5K, 10K, Halbmarathon, Marathon) und Anmeldelinks.",
        "about": "Der <strong>Laufkalender Straßenläufe</strong> ist weltweit: Finde 5-km- und 10-km-Läufe, Halbmarathons und Marathons weltweit – mit stets aktuellen Terminen und Anmeldelinks.",
        "list": "Rennenliste", "langs": "Sprachen",
    },
    "fr": {
        "apple": "Courses",
        "desc": "Calendrier mondial des courses à pied : Brésil, États-Unis, Mexique, Europe et World Marathon Majors. Dates, distances (5K, 10K, semi, marathon) et liens d'inscription.",
        "about": "Le <strong>Calendrier des Courses sur Route</strong> est mondial : trouvez des 5 km, 10 km, semi-marathons et marathons dans le monde entier, avec dates et liens d'inscription à jour.",
        "list": "Liste des courses", "langs": "Langues",
    },
    "it": {
        "apple": "Gare",
        "desc": "Calendario mondiale delle corse su strada: Brasile, USA, Messico, Europa e World Marathon Majors. Date, distanze (5K, 10K, mezza maratona e maratona) e link di iscrizione.",
        "about": "Il <strong>Calendario delle corse su strada</strong> è mondiale: trova gare di 5K, 10K, mezza maratona e maratona in tutto il mondo, con date e link di iscrizione sempre aggiornati.",
        "list": "Elenco delle gare", "langs": "Lingue",
    },
    "nl": {
        "apple": "Wedstrijden",
        "desc": "Wereldwijde kalender voor wegwedstrijden: Brazilië, VS, Mexico, Europa en de World Marathon Majors. Data, afstanden (5K, 10K, halve en hele marathon) en inschrijflinks.",
        "about": "De <strong>Hardloopkalender voor wegwedstrijden</strong> is wereldwijd: vind wedstrijden over 5K, 10K, halve marathon en marathon over de hele wereld, met actuele data en inschrijflinks.",
        "list": "Wedstrijdlijst", "langs": "Talen",
    },
    "pt-pt": {
        "apple": "Corridas",
        "desc": "Calendário mundial de corridas de estrada: Brasil, EUA, México, Europa e World Marathon Majors. Datas, distâncias (5K, 10K, meia maratona e maratona) e ligações de inscrição.",
        "about": "O <strong>Calendário de Corridas de Estrada</strong> é mundial: encontre provas de 5K, 10K, meia maratona e maratona em todo o mundo, com datas e ligações de inscrição sempre atualizadas.",
        "list": "Lista de corridas", "langs": "Idiomas",
    },
    "ru": {
        "apple": "Забеги",
        "desc": "Мировой календарь шоссейных забегов: Бразилия, США, Мексика, Европа и World Marathon Majors. Даты, дистанции (5K, 10K, полумарафон и марафон) и ссылки на регистрацию.",
        "about": "<strong>Календарь шоссейных забегов</strong> охватывает весь мир: забеги на 5K и 10K, полумарафоны и марафоны с актуальными датами и ссылками на регистрацию.",
        "list": "Список забегов", "langs": "Языки",
    },
    "pl": {
        "apple": "Biegi",
        "desc": "Światowy kalendarz biegów ulicznych: Brazylia, USA, Meksyk, Europa i World Marathon Majors. Daty, dystanse (5K, 10K, półmaraton i maraton) oraz linki do zapisów.",
        "about": "<strong>Kalendarz biegów ulicznych</strong> obejmuje cały świat: znajdź biegi na 5K i 10K, półmaratony i maratony na całym świecie, z aktualnymi datami i linkami do zapisów.",
        "list": "Lista biegów", "langs": "Języki",
    },
    "cs": {
        "apple": "Závody",
        "desc": "Světový kalendář silničních běhů: Brazílie, USA, Mexiko, Evropa a World Marathon Majors. Termíny, vzdálenosti (5K, 10K, půlmaraton a maraton) a odkazy na registraci.",
        "about": "<strong>Kalendář silničních běhů</strong> pokrývá celý svět: najděte závody na 5K a 10K, půlmaratony a maratony po celém světě s aktuálními termíny a odkazy na registraci.",
        "list": "Seznam závodů", "langs": "Jazyky",
    },
    "sk": {
        "apple": "Behy",
        "desc": "Svetový kalendár cestných behov: Brazília, USA, Mexiko, Európa a World Marathon Majors. Termíny, vzdialenosti (5K, 10K, polmaratón a maratón) a odkazy na registráciu.",
        "about": "<strong>Kalendár cestných behov</strong> pokrýva celý svet: nájdite behy na 5K a 10K, polmaratóny a maratóny po celom svete s aktuálnymi termínmi a odkazmi na registráciu.",
        "list": "Zoznam behov", "langs": "Jazyky",
    },
    "sl": {
        "apple": "Teki",
        "desc": "Svetovni koledar cestnih tekov: Brazilija, ZDA, Mehika, Evropa in World Marathon Majors. Datumi, razdalje (5K, 10K, polmaraton in maraton) ter povezave za prijavo.",
        "about": "<strong>Koledar cestnih tekov</strong> zajema ves svet: poiščite teke na 5K in 10K, polmaratone in maratone po vsem svetu z ažurnimi datumi in povezavami za prijavo.",
        "list": "Seznam tekov", "langs": "Jeziki",
    },
    "hr": {
        "apple": "Utrke",
        "desc": "Svjetski kalendar cestovnih utrka: Brazil, SAD, Meksiko, Europa i World Marathon Majors. Datumi, udaljenosti (5K, 10K, polumaraton i maraton) i poveznice za prijavu.",
        "about": "<strong>Kalendar cestovnih utrka</strong> obuhvaća cijeli svijet: pronađite utrke na 5K i 10K, polumaratone i maratone diljem svijeta, s ažurnim datumima i poveznicama za prijavu.",
        "list": "Popis utrka", "langs": "Jezici",
    },
    "hu": {
        "apple": "Versenyek",
        "desc": "Világszintű országúti futóverseny-naptár: Brazília, USA, Mexikó, Európa és a World Marathon Majors. Időpontok, távok (5K, 10K, félmaraton és maraton) és nevezési linkek.",
        "about": "Az <strong>Országúti futóversenyek naptára</strong> az egész világot lefedi: 5K-s és 10K-s versenyek, félmaratonok és maratonok világszerte, naprakész időpontokkal és nevezési linkekkel.",
        "list": "Versenylista", "langs": "Nyelvek",
    },
    "el": {
        "apple": "Αγώνες",
        "desc": "Παγκόσμιο ημερολόγιο αγώνων δρόμου: Βραζιλία, ΗΠΑ, Μεξικό, Ευρώπη και World Marathon Majors. Ημερομηνίες, αποστάσεις (5K, 10K, ημιμαραθώνιος και μαραθώνιος) και σύνδεσμοι εγγραφής.",
        "about": "Το <strong>Ημερολόγιο αγώνων δρόμου</strong> καλύπτει όλο τον κόσμο: βρείτε αγώνες 5K και 10K, ημιμαραθωνίους και μαραθωνίους παντού, με ενημερωμένες ημερομηνίες και συνδέσμους εγγραφής.",
        "list": "Λίστα αγώνων", "langs": "Γλώσσες",
    },
    "da": {
        "apple": "Løb",
        "desc": "Verdensomspændende kalender over gadeløb: Brasilien, USA, Mexico, Europa og World Marathon Majors. Datoer, distancer (5K, 10K, halvmaraton og maraton) og tilmeldingslinks.",
        "about": "<strong>Løbskalender for gadeløb</strong> dækker hele verden: find løb på 5K og 10K, halvmaratoner og maratoner over hele kloden med opdaterede datoer og tilmeldingslinks.",
        "list": "Liste over løb", "langs": "Sprog",
    },
    "nb": {
        "apple": "Løp",
        "desc": "Verdensomspennende kalender for gateløp: Brasil, USA, Mexico, Europa og World Marathon Majors. Datoer, distanser (5K, 10K, halvmaraton og maraton) og påmeldingslenker.",
        "about": "<strong>Løpskalender for gateløp</strong> dekker hele verden: finn løp på 5K og 10K, halvmaratoner og maratoner over hele kloden, med oppdaterte datoer og påmeldingslenker.",
        "list": "Liste over løp", "langs": "Språk",
    },
    "sv": {
        "apple": "Lopp",
        "desc": "Världsomspännande kalender för gatulopp: Brasilien, USA, Mexiko, Europa och World Marathon Majors. Datum, distanser (5K, 10K, halvmaraton och maraton) och anmälningslänkar.",
        "about": "<strong>Loppkalender för gatulopp</strong> täcker hela världen: hitta lopp på 5K och 10K, halvmaraton och maraton över hela jorden, med aktuella datum och anmälningslänkar.",
        "list": "Lista över lopp", "langs": "Språk",
    },
    "fi": {
        "apple": "Juoksut",
        "desc": "Maailmanlaajuinen maantiejuoksujen kalenteri: Brasilia, Yhdysvallat, Meksiko, Eurooppa ja World Marathon Majors. Päivämäärät, matkat (5K, 10K, puolimaraton ja maraton) ja ilmoittautumislinkit.",
        "about": "<strong>Maantiejuoksujen kalenteri</strong> kattaa koko maailman: löydä 5K- ja 10K-juoksut, puolimaratonit ja maratonit ympäri maailmaa ajantasaisine päivämäärineen ja ilmoittautumislinkkeineen.",
        "list": "Juoksujen luettelo", "langs": "Kielet",
    },
    "ja": {
        "apple": "レース",
        "desc": "世界のロードレースカレンダー：ブラジル、アメリカ、メキシコ、ヨーロッパ、ワールドマラソンメジャーズ（World Marathon Majors）。日程、距離（5K、10K、ハーフマラソン、フルマラソン）、エントリーリンクを掲載。",
        "about": "<strong>ロードレースカレンダー</strong>は世界中を網羅：5K、10K、ハーフマラソン、フルマラソンの大会を、最新の日程とエントリーリンクとともに探せます。",
        "list": "レース一覧", "langs": "言語",
    },
    "ko": {
        "apple": "레이스",
        "desc": "전 세계 로드 레이스 캘린더: 브라질, 미국, 멕시코, 유럽, 월드 마라톤 메이저스(World Marathon Majors). 일정, 거리(5K, 10K, 하프 및 풀 마라톤), 참가 신청 링크를 제공합니다.",
        "about": "<strong>로드 레이스 캘린더</strong>는 전 세계를 다룹니다. 최신 일정과 참가 신청 링크로 세계 곳곳의 5K, 10K, 하프 마라톤, 마라톤 대회를 찾아보세요.",
        "list": "대회 목록", "langs": "언어",
    },
    "zh-cn": {
        "apple": "赛事",
        "desc": "全球路跑赛事日历：巴西、美国、墨西哥、欧洲及世界马拉松大满贯（World Marathon Majors）。提供比赛日期、距离（5K、10K、半程和全程马拉松）及报名链接，信息随时更新。",
        "about": "<strong>路跑赛事日历</strong>覆盖全球：查找世界各地的 5K、10K、半程马拉松和马拉松赛事，日期和报名链接随时更新。",
        "list": "赛事列表", "langs": "语言",
    },
    "zh-tw": {
        "apple": "賽事",
        "desc": "全球路跑賽事行事曆：巴西、美國、墨西哥、歐洲及世界馬拉松大滿貫（World Marathon Majors）。提供比賽日期、距離（5K、10K、半程與全程馬拉松）及報名連結，資訊隨時更新。",
        "about": "<strong>路跑賽事行事曆</strong>涵蓋全球：查找世界各地的 5K、10K、半程馬拉松與馬拉松賽事，日期與報名連結隨時更新。",
        "list": "賽事列表", "langs": "語言",
    },
    "th": {
        "apple": "งานวิ่ง",
        "desc": "ปฏิทินงานวิ่งถนนทั่วโลก: บราซิล สหรัฐอเมริกา เม็กซิโก ยุโรป และ World Marathon Majors พร้อมวันที่ ระยะทาง (5K, 10K, ฮาล์ฟมาราธอนและมาราธอน) และลิงก์สมัคร",
        "about": "<strong>ปฏิทินงานวิ่งถนน</strong>ครอบคลุมทั่วโลก: ค้นหางานวิ่ง 5K, 10K, ฮาล์ฟมาราธอน และมาราธอนทั่วโลก พร้อมวันที่และลิงก์สมัครที่อัปเดตอยู่เสมอ",
        "list": "รายการงานวิ่ง", "langs": "ภาษา",
    },
    "he": {
        "apple": "מרוצים",
        "desc": "לוח עולמי של מרוצי כביש: ברזיל, ארה״ב, מקסיקו, אירופה ו־World Marathon Majors. תאריכים, מרחקים (5K, 10K, חצי מרתון ומרתון) וקישורי הרשמה.",
        "about": "<strong>לוח מרוצי כביש</strong> מכסה את כל העולם: מצאו מרוצי 5K ו־10K, חצאי מרתון ומרתונים בכל רחבי העולם, עם תאריכים וקישורי הרשמה מעודכנים.",
        "list": "רשימת מרוצים", "langs": "שפות",
    },
    "id": {
        "apple": "Lomba",
        "desc": "Kalender lomba lari jalan raya sedunia: Brasil, AS, Meksiko, Eropa, dan World Marathon Majors. Tanggal, jarak (5K, 10K, setengah maraton dan maraton), serta tautan pendaftaran.",
        "about": "<strong>Kalender Lomba Lari Jalan Raya</strong> mencakup seluruh dunia: temukan lomba 5K, 10K, setengah maraton, dan maraton di seluruh dunia, dengan tanggal dan tautan pendaftaran yang selalu terbaru.",
        "list": "Daftar lomba", "langs": "Bahasa",
    },
    "ms": {
        "apple": "Larian",
        "desc": "Kalendar larian jalan raya sedunia: Brazil, AS, Mexico, Eropah dan World Marathon Majors. Tarikh, jarak (5K, 10K, separuh maraton dan maraton) serta pautan pendaftaran.",
        "about": "<strong>Kalendar Larian Jalan Raya</strong> merangkumi seluruh dunia: cari larian 5K, 10K, separuh maraton dan maraton di seluruh dunia, dengan tarikh dan pautan pendaftaran yang sentiasa dikemas kini.",
        "list": "Senarai larian", "langs": "Bahasa",
    },
}

PRERENDER_RE = {
    "PRERENDER_EVENTS": re.compile(
        r"<!-- prerender:events:start -->\n(.*?)\n<!-- prerender:events:end -->", re.S),
    "PRERENDER_JSONLD": re.compile(
        r"<!-- prerender:jsonld:start -->\n(.*?)\n<!-- prerender:jsonld:end -->", re.S),
}

_LOCALE_HEAD_RE = re.compile(r"^  (?:'([a-z-]+)'|([a-z]+)): \{$", re.M)
_STRING_RE = re.compile(r"""^    (\w+): (?:'((?:[^'\\]|\\.)*)'|"((?:[^"\\]|\\.)*)"),$""", re.M)
_PILL_OTHER_RE = re.compile(r"'outros': '((?:[^'\\]|\\.)*)'")


def _unescape(js: str) -> str:
    return re.sub(r"\\(.)", r"\1", js)


def read_strings(app_js: str) -> dict[str, dict[str, str]]:
    """The plain-string entries of app.js STRINGS, per language.

    Parses the literal rather than executing it: every entry the shells need
    is a one-line `key: 'value',` (the format the STRINGS key-alignment test
    already enforces), plus the `outros` distance pill.
    """
    start = app_js.index("const STRINGS = {")
    end = app_js.index("\n};\n", start)
    body = app_js[start:end]
    heads = list(_LOCALE_HEAD_RE.finditer(body))
    out: dict[str, dict[str, str]] = {}
    for i, h in enumerate(heads):
        lang = h.group(1) or h.group(2)
        chunk = body[h.end(): heads[i + 1].start() if i + 1 < len(heads) else len(body)]
        strings = {m.group(1): _unescape(m.group(2) if m.group(2) is not None else m.group(3))
                   for m in _STRING_RE.finditer(chunk)}
        pill = _PILL_OTHER_RE.search(chunk)
        if pill:
            strings["pillOther"] = _unescape(pill.group(1))
        out[lang] = strings
    return out


def _attr(text: str) -> str:
    """Escape for a double-quoted attribute / text node. `&` is left alone:
    the copy never contains an entity-like sequence, and the shells have
    always carried a literal `&` (\"Brazil & Worldwide\")."""
    return text.replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;")


def render(prefix: str, hreflang: str, template: str, strings: dict, existing: str | None) -> str:
    t = strings[prefix]
    seo = SEO[prefix]
    site_name = t["headerTitle"]
    if f"<strong>{site_name}</strong>" not in seo["about"]:
        raise SystemExit(f"{prefix}: SEO about must wrap the site name {site_name!r} in <strong>")

    html_attrs = f'lang="{hreflang}"' + (' dir="rtl"' if prefix in RTL else "")
    values = {
        "HTML_ATTRS": html_attrs,
        "APPLE_TITLE": _attr(seo["apple"]),
        "DESC": _attr(seo["desc"]),
        "TITLE": _attr(t["siteTitle"]),
        "SITE_NAME": _attr(site_name),
        "CANONICAL": f"{BASE}/{prefix}/",
        "OG_IMAGE": f"{BASE}/og-{prefix}.png",
        "OG_LOCALE": OG_LOCALES[prefix],
        "OG_ALTERNATES": "".join(
            f'  <meta property="og:locale:alternate" content="{OG_LOCALES[p]}" />\n'
            for p, _ in LANGS if p != prefix),
        "HREFLANG": "".join(
            f'  <link rel="alternate" hreflang="{code}" href="{BASE}/{p}/" />\n'
            for p, code in LANGS)
            + f'  <link rel="alternate" hreflang="x-default" href="{BASE}/" />\n',
        "PREFIX": prefix,
        "LIST_ARIA": _attr(seo["list"]),
        "LANGS_ARIA": _attr(seo["langs"]),
        "SITE_ABOUT": seo["about"],
        "FOOTER_LANGS": "".join(f'<a href="/{p}/">{NATIVE_NAMES[p]}</a>' for p, _ in LANGS),
    }
    for key, rx in PRERENDER_RE.items():
        m = rx.search(existing) if existing else None
        values[key] = m.group(1) if m else ""

    def sub(m: re.Match) -> str:
        key = m.group(1)
        if key in values:
            return values[key]
        if key not in t:
            raise SystemExit(f"{prefix}: STRINGS has no {key!r} for the shell")
        return _attr(t[key])

    return re.sub(r"\{\{(\w+)\}\}", sub, template)


# The root URL only redirects to a language home. Its detection mirrors
# _langFromTag in app.js (walk navigator.languages; pt-PT/zh-TW and the
# iw/in/no aliases are told apart by subtag); crawlers and no-JS visitors get
# the hreflang cluster and plain links instead.
ROOT_TEMPLATE = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8" />
  <link rel="icon" href="/favicon.ico" sizes="any" />
  <link rel="icon" type="image/png" sizes="32x32" href="/favicon-32.png" />
  <link rel="icon" type="image/png" sizes="192x192" href="/favicon-192.png" />
  <link rel="apple-touch-icon" href="/favicon-180.png" />
  <title>Calendário de Corridas — Race Calendar</title>
  <link rel="canonical" href="{base}/" />
{hreflang}  <script>
    (function () {{
      var SUPPORTED = {supported};
      function fromTag(tag) {{
        var p = String(tag || '').toLowerCase().replace(/_/g, '-').split('-'), b = p[0], sub = p.slice(1);
        function has(list) {{ for (var i = 0; i < sub.length; i++) {{ if (list.indexOf(sub[i]) >= 0) return true; }} return false; }}
        if (b === 'pt') return has(['pt', 'ao', 'mz', 'cv', 'gw', 'st', 'tl']) ? 'pt-pt' : 'pt';
        if (b === 'zh') return has(['hans']) ? 'zh-cn' : (has(['hant', 'tw', 'hk', 'mo']) ? 'zh-tw' : 'zh-cn');
        if (b === 'no' || b === 'nn') return 'nb';
        if (b === 'iw') return 'he';
        if (b === 'in') return 'id';
        return SUPPORTED.indexOf(b) >= 0 ? b : null;
      }}
      var prefs = (navigator.languages && navigator.languages.length) ? navigator.languages : [navigator.language];
      for (var i = 0; i < prefs.length; i++) {{
        var l = fromTag(prefs[i]);
        if (l) {{ window.location.replace('/' + l); return; }}
      }}
      window.location.replace('/en');
    }}());
  </script>
</head>
<body>
  <noscript>
    <p>{links}</p>
  </noscript>
</body>
</html>
"""


def render_root() -> str:
    hreflang = "".join(
        f'  <link rel="alternate" hreflang="{code}" href="{BASE}/{p}/" />\n' for p, code in LANGS
    ) + f'  <link rel="alternate" hreflang="x-default" href="{BASE}/" />\n'
    supported = "[" + ", ".join(f"'{p}'" for p, _ in LANGS) + "]"
    links = " · ".join(f'<a href="/{p}/">{NATIVE_NAMES[p]}</a>' for p, _ in LANGS)
    return ROOT_TEMPLATE.format(base=BASE, hreflang=hreflang, supported=supported, links=links)


def main(argv: list[str]) -> int:
    check = "--check" in argv
    template = TEMPLATE.read_text(encoding="utf-8")
    strings = read_strings((WEB / "app.js").read_text(encoding="utf-8"))
    missing = [p for p, _ in LANGS if p not in strings or p not in SEO or p not in OG_LOCALES]
    if missing:
        raise SystemExit(f"languages without STRINGS/SEO/OG locale: {missing}")

    stale = []
    root = WEB / "index.html"
    root_html = render_root()
    if not root.exists() or root.read_text(encoding="utf-8") != root_html:
        stale.append("/")
        if not check:
            root.write_text(root_html, encoding="utf-8")
            print(f"wrote {root.relative_to(ROOT)}")
    for prefix, hreflang in LANGS:
        path = WEB / prefix / "index.html"
        existing = path.read_text(encoding="utf-8") if path.exists() else None
        html = render(prefix, hreflang, template, strings, existing)
        if html == existing:
            continue
        stale.append(prefix)
        if not check:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(html, encoding="utf-8")
            print(f"wrote {path.relative_to(ROOT)}")
    if check and stale:
        print(f"stale shells (run scripts/generate_shells.py): {stale}")
        return 1
    if not stale:
        print(f"all {len(LANGS)} shells and the root page up to date")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
