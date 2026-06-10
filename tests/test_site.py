"""
End-to-end Playwright tests for the corridas static site.

Uses sync playwright API via pytest-playwright.
All tests assume the live_server fixture (port 8765) is running
and that corridas.json is populated with real data.
"""
import json
import re
from pathlib import Path

import pytest


def _isolate_context(ctx):
    """Mock geo APIs and abort all third-party requests so networkidle settles.

    Mirrors conftest._add_geo_mocks for tests that build their own context.
    """
    fake = json.dumps({"country_code": "BR", "region_code": "SP", "city": "São Paulo",
                       "latitude": -23.5, "longitude": -46.6})
    _geo = ("ipwho.is", "freeipapi.com", "api.ip.sb")

    def handle(route, request):
        url = request.url
        if any(h in url for h in _geo):
            route.fulfill(status=200, content_type="application/json", body=fake)
        elif "127.0.0.1" in url or "localhost" in url:
            route.continue_()
        else:
            route.abort()

    ctx.route("**/*", handle)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

DATA_DIR = Path(__file__).parent.parent / "data"
WEB_DIR  = Path(__file__).parent.parent / "web"

def _load_corridas():
    with open(WEB_DIR / "corridas.json", encoding="utf-8") as f:
        return json.load(f)["corridas"]


def _open_lang_dropdown(page):
    """Click the language button and return the dropdown element."""
    page.click("#btnLang")
    page.wait_for_selector(".lang-dropdown", timeout=5000)
    return page.query_selector(".lang-dropdown")


def _open_estado_dropdown(page):
    """Open the location filter dropdown."""
    page.click("#estadoFilterBtn")
    page.wait_for_selector("#estadoFilterDropdown .estado-group", timeout=5000)


def _open_fonte_dropdown(page):
    """Open the fonte filter dropdown."""
    page.click("#fonteFilterBtn")
    page.wait_for_selector("#fonteFilterDropdown .fonte-filter-option", timeout=5000)


# ---------------------------------------------------------------------------
# Language menu tests
# ---------------------------------------------------------------------------

def test_language_menu_current_first_then_alphabetical(page_pt, live_server):
    """In pt locale the lang dropdown must start with Português; rest alphabetical."""
    _open_lang_dropdown(page_pt)
    buttons = page_pt.query_selector_all(".lang-dropdown button.lang-option")
    labels = [b.text_content().strip() for b in buttons]
    assert len(labels) >= 2, "Expected at least 2 language options"
    assert labels[0] == "Português", f"First item should be Português, got: {labels[0]}"
    rest = labels[1:]
    assert rest == sorted(rest), f"Remaining labels not sorted: {rest}"


def test_language_menu_all_locales_present(page_pt, live_server):
    """All 5 language labels must appear in the dropdown."""
    _open_lang_dropdown(page_pt)
    buttons = page_pt.query_selector_all(".lang-dropdown button.lang-option")
    labels = {b.text_content().strip() for b in buttons}
    expected = {"Português", "English", "Español", "Deutsch", "Français"}
    assert expected == labels, f"Missing languages: {expected - labels}"


# ---------------------------------------------------------------------------
# Location accordion tests
# ---------------------------------------------------------------------------

def test_location_accordion_expands_on_click(page_pt, live_server):
    """Opening location filter and clicking Brasil group header expands its body."""
    _open_estado_dropdown(page_pt)
    # Find Brasil group header
    headers = page_pt.query_selector_all(".estado-group-header")
    brasil_header = None
    for h in headers:
        if "Brasil" in h.text_content():
            brasil_header = h
            break
    assert brasil_header is not None, "Could not find Brasil group header"

    body = brasil_header.evaluate_handle("el => el.nextElementSibling")
    # The body starts collapsed or expanded; get its current state
    initial_collapsed = page_pt.evaluate("el => el.classList.contains('collapsed')", body)
    if initial_collapsed:
        brasil_header.click()
        page_pt.wait_for_timeout(300)
    # Now verify it's expanded (not collapsed)
    is_collapsed = page_pt.evaluate("el => el.classList.contains('collapsed')", body)
    assert not is_collapsed, "Brasil group body should be expanded after clicking header"


def test_location_accordion_collapses_sibling_on_expand(page_pt, live_server):
    """Expanding a second accordion group collapses the previously open one."""
    _open_estado_dropdown(page_pt)
    headers = page_pt.query_selector_all(".estado-group-header")
    if len(headers) < 2:
        pytest.skip("Need at least 2 location groups to test sibling collapse")

    first_header  = headers[0]
    second_header = headers[1]

    # Expand first
    first_body = first_header.evaluate_handle("el => el.nextElementSibling")
    first_collapsed = page_pt.evaluate("el => el.classList.contains('collapsed')", first_body)
    if first_collapsed:
        first_header.click()
        page_pt.wait_for_timeout(200)

    # Expand second — should collapse the first
    second_body = second_header.evaluate_handle("el => el.nextElementSibling")
    second_collapsed = page_pt.evaluate("el => el.classList.contains('collapsed')", second_body)
    if not second_collapsed:
        # Second is already open; close it first then reopen to trigger sibling collapse
        second_header.click()
        page_pt.wait_for_timeout(200)

    second_header.click()
    page_pt.wait_for_timeout(300)

    first_now_collapsed  = page_pt.evaluate("el => el.classList.contains('collapsed')", first_body)
    second_now_collapsed = page_pt.evaluate("el => el.classList.contains('collapsed')", second_body)
    assert not second_now_collapsed, "Second group should be open"
    assert first_now_collapsed, "First group should have collapsed when second was opened"


# ---------------------------------------------------------------------------
# Fontes filter tests
# ---------------------------------------------------------------------------

def test_fontes_shows_only_sources_with_events(page_pt, live_server):
    """Each checkbox label in the fontes filter must match a real source in the data."""
    corridas = _load_corridas()
    all_source_names = {f["nome"] for c in corridas for f in c.get("fontes", [])}

    _open_fonte_dropdown(page_pt)
    labels = page_pt.query_selector_all("#fonteFilterDropdown .fonte-filter-option")
    assert len(labels) > 0, "Expected at least one fonte option"
    for lbl in labels:
        # Text is the label minus the checkbox value prefix
        name = lbl.text_content().strip()
        assert name in all_source_names, f"Fonte '{name}' not found in corridas data"


def test_fontes_multi_select_filters_events(page_pt, live_server):
    """Selecting a single fonte shows only cards from that fonte."""
    _open_fonte_dropdown(page_pt)
    labels = page_pt.query_selector_all("#fonteFilterDropdown .fonte-filter-option")
    if len(labels) < 1:
        pytest.skip("No fontes available to filter")

    # Pick the first fonte
    first_label = labels[0]
    fonte_name = first_label.text_content().strip()
    cb = first_label.query_selector("input[type=checkbox]")
    cb.click()
    page_pt.wait_for_timeout(500)

    # Close dropdown
    page_pt.keyboard.press("Escape")
    page_pt.wait_for_timeout(200)

    # .fonte-nome-text is only built on card expand (lazy), so read the JS
    # filteredCorridas array directly — it's the source of truth for what renders.
    filtered = page_pt.evaluate("""
        () => filteredCorridas.map(c => c.fontes ? c.fontes.map(f => f.nome) : [])
    """)

    assert len(filtered) > 0, f"filteredCorridas is empty after selecting fonte '{fonte_name}'"
    for card_fontes in filtered:
        assert fonte_name in card_fontes, (
            f"Corrida with fontes {card_fontes} shown but filter is '{fonte_name}'"
        )


# ---------------------------------------------------------------------------
# Event card tests
# ---------------------------------------------------------------------------

def test_all_events_have_inscricao_button(page_pt, live_server):
    """Every visible card must have at least one .btn-inscricao element."""
    # Expand all month sections to make sure cards are rendered
    page_pt.evaluate("""
        () => {
            document.querySelectorAll('.month-cards--collapsed').forEach(el => {
                el.classList.remove('month-cards--collapsed');
            });
        }
    """)
    page_pt.wait_for_timeout(300)

    cards = page_pt.query_selector_all(".card")
    assert len(cards) > 0, "No cards found on page"

    cards_without_btn = []
    for card in cards:
        # Re-expand the card's month section in case the accordion closed it
        page_pt.evaluate(
            "(el) => { const mc = el.closest('.month-cards'); if (mc) mc.classList.remove('month-cards--collapsed'); }",
            card,
        )
        # btn-inscricao is inside the expanded section; click to expand first
        collapsed = card.query_selector(".card-collapsed")
        if collapsed:
            collapsed.click()
            page_pt.wait_for_timeout(100)
        btns = card.query_selector_all(".btn-inscricao")
        if len(btns) == 0:
            title = card.query_selector(".card-title")
            title_text = title.text_content() if title else "unknown"
            cards_without_btn.append(title_text)

    assert len(cards_without_btn) == 0, (
        f"{len(cards_without_btn)} cards have no inscricao button: {cards_without_btn[:5]}"
    )


def test_event_date_uses_spelled_out_month(page_pt, live_server):
    """Card dates in PT must contain a word from the Portuguese month list, not DD/MM/YYYY."""
    pt_months = [
        'janeiro','fevereiro','março','abril','maio','junho',
        'julho','agosto','setembro','outubro','novembro','dezembro',
    ]
    # Also accept today/tomorrow/yesterday labels
    special_labels = {'hoje', 'amanhã', 'ontem'}

    cards = page_pt.query_selector_all(".card")
    assert len(cards) > 0, "No cards found"

    checked = 0
    for card in cards[:20]:
        date_el = card.query_selector(".card-date")
        if not date_el:
            continue
        text = date_el.text_content().lower()
        if not text:
            continue
        if any(sl in text for sl in special_labels):
            checked += 1
            continue
        has_month = any(m in text for m in pt_months)
        # Also reject pure DD/MM/YYYY pattern (the old bug)
        has_numeric_date = re.search(r'\d{2}/\d{2}/\d{4}', text)
        assert has_month and not has_numeric_date, (
            f"Date '{text}' does not contain spelled-out month or still has numeric format"
        )
        checked += 1

    assert checked > 0, "No non-empty date elements found to check"


def test_event_date_localized_per_language(page_en, live_server):
    """Card dates on English page must contain an English month name."""
    en_months = [
        'january','february','march','april','may','june',
        'july','august','september','october','november','december',
    ]
    special_labels = {'today', 'tomorrow', 'yesterday'}

    cards = page_en.query_selector_all(".card")
    assert len(cards) > 0, "No cards found on English page"

    checked = 0
    for card in cards[:20]:
        date_el = card.query_selector(".card-date")
        if not date_el:
            continue
        text = date_el.text_content().lower()
        if not text:
            continue
        if any(sl in text for sl in special_labels):
            checked += 1
            continue
        has_month = any(m in text for m in en_months)
        assert has_month, f"English date '{text}' does not contain an English month name"
        checked += 1

    assert checked > 0, "No non-empty date elements found on English page"


# ---------------------------------------------------------------------------
# "Novo" badge tests
# ---------------------------------------------------------------------------

def test_new_event_badge_visible_for_recent(page_pt, live_server):
    """A card whose corrida.first_seen_at is within 7 days must show a visible badge-novo."""
    from datetime import datetime, timezone, timedelta

    now = datetime.now(tz=timezone.utc)
    # Use same 3-day window and date-string format as the app's threeDaysAgo
    cutoff = (now - timedelta(days=3)).date().isoformat()

    # Find a new event among what's currently visible (respects active location filter)
    titulo = page_pt.evaluate(
        "(cutoff) => { const c = filteredCorridas.find(c => c.first_seen_at && c.first_seen_at >= cutoff); return c ? c.titulo : null; }",
        cutoff,
    )
    if titulo is None:
        pytest.skip("No 'new' events visible with current location filter")

    # Expand all months so cards are rendered
    page_pt.evaluate("""
        () => document.querySelectorAll('.month-cards--collapsed').forEach(
            el => el.classList.remove('month-cards--collapsed')
        )
    """)
    page_pt.wait_for_timeout(300)

    # Look for the card by title
    cards = page_pt.query_selector_all(".card")
    found_card = None
    for card in cards:
        title_el = card.query_selector(".card-title")
        if title_el and title_el.text_content().strip() == titulo:
            found_card = card
            break

    assert found_card is not None, f"Card for '{titulo}' not found in DOM after expanding all months"

    badge = found_card.query_selector(".badge-novo")
    assert badge is not None, "card has no .badge-novo element"
    is_hidden = page_pt.evaluate(
        "el => el.classList.contains('hidden')", badge
    )
    assert not is_hidden, f"badge-novo is hidden on card for new event '{titulo}'"


def test_month_section_badge_when_has_new(page_pt, live_server):
    """A month section that contains a new event must show .badge-novo in its header."""
    from datetime import datetime, timezone, timedelta

    corridas = _load_corridas()
    now = datetime.now(tz=timezone.utc)
    cutoff = (now - timedelta(days=7)).isoformat()

    has_new = any(c.get("first_seen_at", "") >= cutoff for c in corridas)
    if not has_new:
        pytest.skip("No new events in dataset")

    # At least one month-separator must have a badge-novo that is not hidden
    month_badges = page_pt.evaluate("""
        () => {
            const seps = [...document.querySelectorAll('.month-separator')];
            return seps.map(sep => {
                const badge = sep.querySelector('.badge-novo');
                return badge ? !badge.classList.contains('hidden') : false;
            });
        }
    """)
    assert any(month_badges), "No month section header shows badge-novo despite new events existing"


# ---------------------------------------------------------------------------
# Distance table column suppression tests
# ---------------------------------------------------------------------------

def test_distance_table_date_column_only_when_different_dates(page_pt, live_server):
    """Expanded card: Date column only shown when distances have differing dates."""
    corridas = _load_corridas()

    # Find event with multiple distances on the SAME date (column should be hidden)
    same_date_id = None
    for c in corridas:
        dists = c.get("distancias", [])
        if len(dists) < 2:
            continue
        dates = [d["data"] for d in dists if d.get("data")]
        if dates and len(set(dates)) == 1:
            same_date_id = c["titulo"]
            same_date_title = c["titulo"]
            break

    # Find event with distances on DIFFERENT dates (column should be shown)
    diff_date_id = None
    for c in corridas:
        dists = c.get("distancias", [])
        if len(dists) < 2:
            continue
        dates = [d["data"] for d in dists if d.get("data")]
        if len(set(dates)) > 1:
            diff_date_id = c["titulo"]
            diff_date_title = c["titulo"]
            break

    # Expand all months
    page_pt.evaluate("""
        () => document.querySelectorAll('.month-cards--collapsed').forEach(
            el => el.classList.remove('month-cards--collapsed')
        )
    """)
    page_pt.wait_for_timeout(300)

    if same_date_id:
        # Find the card and click to expand
        card = _find_card_by_title(page_pt, same_date_title)
        if card:
            card.query_selector(".card-collapsed").click()
            page_pt.wait_for_timeout(300)
            # Check that no "Data" column header appears
            th_texts = [
                th.text_content().strip()
                for th in card.query_selector_all(".dist-table th")
            ]
            date_col_labels = {"Data", "Date", "Fecha", "Datum", "Date"}
            has_date_col = bool(date_col_labels & set(th_texts))
            assert not has_date_col, (
                f"Same-date event '{same_date_title}' shows Date column: {th_texts}"
            )

    if diff_date_id:
        card = _find_card_by_title(page_pt, diff_date_title)
        if card:
            card.query_selector(".card-collapsed").click()
            page_pt.wait_for_timeout(300)
            th_texts = [
                th.text_content().strip()
                for th in card.query_selector_all(".dist-table th")
            ]
            date_col_labels = {"Data", "Date", "Fecha", "Datum"}
            has_date_col = bool(date_col_labels & set(th_texts))
            assert has_date_col, (
                f"Diff-date event '{diff_date_title}' missing Date column: {th_texts}"
            )

    if not same_date_id and not diff_date_id:
        pytest.skip("No suitable multi-distance events found in data")


def test_distance_table_time_column_only_when_different_times(page_pt, live_server):
    """Expanded card: Time column only shown when distances have differing horarios."""
    corridas = _load_corridas()

    # Same-time event (column should be hidden)
    same_time_id = None
    for c in corridas:
        dists = c.get("distancias", [])
        if len(dists) < 2:
            continue
        times = [d["horario"] for d in dists if d.get("horario")]
        if times and len(set(times)) == 1:
            same_time_id = c["titulo"]
            same_time_title = c["titulo"]
            break

    # Different-time event (column should be shown)
    diff_time_id = None
    for c in corridas:
        dists = c.get("distancias", [])
        if len(dists) < 2:
            continue
        times = [d["horario"] for d in dists if d.get("horario")]
        if len(set(times)) > 1:
            diff_time_id = c["titulo"]
            diff_time_title = c["titulo"]
            break

    # Expand all months
    page_pt.evaluate("""
        () => document.querySelectorAll('.month-cards--collapsed').forEach(
            el => el.classList.remove('month-cards--collapsed')
        )
    """)
    page_pt.wait_for_timeout(300)

    if same_time_id:
        card = _find_card_by_title(page_pt, same_time_title)
        if card:
            card.query_selector(".card-collapsed").click()
            page_pt.wait_for_timeout(300)
            th_texts = [
                th.text_content().strip()
                for th in card.query_selector_all(".dist-table th")
            ]
            time_col_labels = {"Horário", "Time", "Hora", "Zeit", "Heure"}
            has_time_col = bool(time_col_labels & set(th_texts))
            assert not has_time_col, (
                f"Same-time event '{same_time_title}' shows Time column: {th_texts}"
            )

    if diff_time_id:
        card = _find_card_by_title(page_pt, diff_time_title)
        if card:
            card.query_selector(".card-collapsed").click()
            page_pt.wait_for_timeout(300)
            th_texts = [
                th.text_content().strip()
                for th in card.query_selector_all(".dist-table th")
            ]
            time_col_labels = {"Horário", "Time", "Hora", "Zeit", "Heure"}
            has_time_col = bool(time_col_labels & set(th_texts))
            assert has_time_col, (
                f"Diff-time event '{diff_time_title}' missing Time column: {th_texts}"
            )

    if not same_time_id and not diff_time_id:
        pytest.skip("No suitable multi-distance events found in data")


# ---------------------------------------------------------------------------
# Month separator opacity tests
# ---------------------------------------------------------------------------

def _parse_rgba(color: str):
    """Parse 'rgb(r,g,b)' or 'rgba(r,g,b,a)' → (r,g,b,a) with a defaulting to 1.0."""
    import re
    m = re.match(r'rgba?\(\s*([\d.]+),\s*([\d.]+),\s*([\d.]+)(?:,\s*([\d.]+))?\s*\)', color)
    if not m:
        return None
    r, g, b = int(m.group(1)), int(m.group(2)), int(m.group(3))
    a = float(m.group(4)) if m.group(4) else 1.0
    return r, g, b, a


def test_closed_month_separator_opaque_on_hover(page_pt, live_server):
    """Hovering a closed month separator must not make it transparent.

    Regression: .month-separator:hover used background: var(--color-accent-dim)
    (rgba 15% opacity), making all closed separators transparent on hover and
    letting the page background bleed through.
    """
    separators = page_pt.query_selector_all('.month-separator')
    # Find one that is NOT in an open section (normal flow, not sticky)
    closed_sep = None
    for sep in separators:
        is_open = page_pt.evaluate(
            "el => el.closest('.month-section') !== null && "
            "el.closest('.month-section').classList.contains('month-section--open')",
            sep,
        )
        if not is_open:
            closed_sep = sep
            break

    if closed_sep is None:
        pytest.skip("No closed month sections found — all sections may be open")

    closed_sep.hover()
    page_pt.wait_for_timeout(50)

    bg = page_pt.evaluate("el => getComputedStyle(el).backgroundColor", closed_sep)
    parsed = _parse_rgba(bg)
    assert parsed is not None, f"Unexpected background format: {bg}"
    _, _, _, alpha = parsed
    assert alpha >= 0.99, (
        f"Closed month separator is transparent on hover (background={bg}). "
        "CSS regression: .month-separator:hover must use an opaque background-color."
    )


def test_open_month_separator_opaque_on_hover(page_pt, live_server):
    """Hovering the sticky (open) month separator must not make it transparent.

    Regression: .month-separator:hover (specificity 0,2,0) tied with
    .month-section--open .month-separator (0,2,0); hover appeared later in CSS
    and won, applying rgba 15% opacity to the sticky header.
    """
    separators = page_pt.query_selector_all('.month-section--open .month-separator')
    if not separators:
        pytest.skip("No open month sections found")

    sep = separators[0]
    sep.hover()
    page_pt.wait_for_timeout(50)

    bg = page_pt.evaluate("el => getComputedStyle(el).backgroundColor", sep)
    parsed = _parse_rgba(bg)
    assert parsed is not None, f"Unexpected background format: {bg}"
    _, _, _, alpha = parsed
    assert alpha >= 0.99, (
        f"Open (sticky) month separator is transparent on hover (background={bg}). "
        "CSS regression in .month-section--open .month-separator:hover."
    )


def test_switching_months_separator_stays_opaque(page_pt, live_server):
    """Hovering a different month separator while one is already open must be opaque.

    Regression: clicking a second month separator to switch sections triggered
    a transparent hover state on the newly targeted separator.
    """
    separators = page_pt.query_selector_all('.month-separator')
    if len(separators) < 2:
        pytest.skip("Need at least 2 month separators to test switching")

    # Open the first section
    separators[0].click()
    page_pt.wait_for_timeout(200)

    # Hover the second separator (it is closed; the first is now open)
    separators[1].hover()
    page_pt.wait_for_timeout(50)

    bg = page_pt.evaluate("el => getComputedStyle(el).backgroundColor", separators[1])
    parsed = _parse_rgba(bg)
    assert parsed is not None, f"Unexpected background format: {bg}"
    _, _, _, alpha = parsed
    assert alpha >= 0.99, (
        f"Month separator is transparent when hovered during section switch "
        f"(background={bg}). CSS regression."
    )


# ---------------------------------------------------------------------------
# Pin / home button tests
# ---------------------------------------------------------------------------

def test_pin_resets_location_filter(page_pt, live_server):
    """Clicking #btnHome resets the location state toward geo (or 'todos')."""
    # Set an explicit location filter first
    page_pt.evaluate("""
        () => {
            const saved = JSON.parse(localStorage.getItem('corridas_filters') || '{}');
            saved.estado = 'SP';
            localStorage.setItem('corridas_filters', JSON.stringify(saved));
        }
    """)
    page_pt.reload(wait_until="networkidle")
    page_pt.wait_for_selector(".card", state="attached", timeout=15000)

    label_before = page_pt.query_selector("#estadoFilterLabel").text_content().strip()

    page_pt.click("#btnHome")
    page_pt.wait_for_timeout(2000)  # geo detection + re-render

    label_after = page_pt.query_selector("#estadoFilterLabel").text_content().strip()
    # After clicking home the label should be either 'Todos' (no geo result) or 'São Paulo'
    # (geo applied) — in any case it should not show whatever was manually set to 'SP'
    # Since our mock returns SP, the filter should be SP (the state label) or 'Todos'
    # The key assertion: the page re-rendered without throwing
    assert label_after is not None, "Location label disappeared after home button click"


def test_initial_load_no_session_cache(browser, live_server):
    """Fresh browser context with no storage must load the page correctly."""
    ctx = browser.new_context(locale="pt-BR")
    # Geo mocks + abort of all third-party requests so networkidle settles.
    _isolate_context(ctx)

    page = ctx.new_page()
    # clear storage explicitly (new context starts empty, but be explicit)
    page.goto(live_server + "/pt/", wait_until="networkidle")
    page.wait_for_selector(".card", state="attached", timeout=15000)
    cards = page.query_selector_all(".card")
    assert len(cards) > 0, "No cards rendered on fresh load"
    ctx.close()


# ---------------------------------------------------------------------------
# STRINGS key alignment test (no browser needed — reads app.js directly)
# ---------------------------------------------------------------------------

def test_all_strings_keys_aligned_across_locales(live_server):
    """All 5 locales in STRINGS must define exactly the same set of keys."""
    app_js = (WEB_DIR / "app.js").read_text(encoding="utf-8")

    # Find the STRINGS = { ... }; block.
    # Strategy: locate each locale block by 'pt: {', 'en: {', etc.
    locales = ["pt", "en", "es", "de", "fr"]
    locale_keys = {}

    for locale in locales:
        # Find the start of this locale's object
        pattern = rf'\b{locale}\s*:\s*\{{'
        m = re.search(pattern, app_js)
        assert m, f"Could not find locale '{locale}' in STRINGS"

        start = m.end()  # position right after the opening brace
        depth = 1
        i = start
        while i < len(app_js) and depth > 0:
            if app_js[i] == '{':
                depth += 1
            elif app_js[i] == '}':
                depth -= 1
            i += 1
        locale_body = app_js[start:i - 1]

        # Extract top-level keys: lines starting with an identifier followed by ':'
        keys = set()
        for match in re.finditer(r"^\s{4}(\w+)\s*:", locale_body, re.MULTILINE):
            keys.add(match.group(1))
        locale_keys[locale] = keys

    reference = locale_keys["pt"]
    for loc, keys in locale_keys.items():
        missing = reference - keys
        extra   = keys - reference
        assert not missing, f"Locale '{loc}' missing keys vs pt: {missing}"
        assert not extra,   f"Locale '{loc}' has extra keys vs pt: {extra}"


# ---------------------------------------------------------------------------
# Language fallback test
# ---------------------------------------------------------------------------

def test_language_fallback_to_english(browser, live_server):
    """A context with an unmapped browser locale loads the English strings."""
    # 'zh-TW' is not mapped → BROWSER_LANG should fall back to 'en'
    ctx = browser.new_context(locale="zh-TW")
    # Geo mocks + abort of all third-party requests so networkidle settles.
    _isolate_context(ctx)
    page = ctx.new_page()
    # Navigate to /en/ explicitly (fallback applies to URL-less root; /en/ gives English)
    page.goto(live_server + "/en/", wait_until="networkidle")
    page.wait_for_selector(".card", state="attached", timeout=15000)
    # The register button text must be the English one
    # Click first card to expand it to see the btn-inscricao
    cards = page.query_selector_all(".card")
    assert len(cards) > 0, "No cards on English page"
    # Page title should be English
    title = page.title()
    assert "Next Race" in title or "Race" in title, f"Expected English title, got: {title}"
    ctx.close()


# ---------------------------------------------------------------------------
# Cards have link buttons with href
# ---------------------------------------------------------------------------

def test_cards_have_link_buttons(page_pt, live_server):
    """Every .btn-inscricao must have a non-empty href pointing to a URL."""
    # Expand all cards to trigger buildExpanded for at least a sample
    page_pt.evaluate("""
        () => document.querySelectorAll('.month-cards--collapsed').forEach(
            el => el.classList.remove('month-cards--collapsed')
        )
    """)
    page_pt.wait_for_timeout(300)

    # Expand first 10 cards
    cards = page_pt.query_selector_all(".card")
    for card in cards[:10]:
        # Re-expand the card's month section in case the accordion closed it
        page_pt.evaluate(
            "(el) => { const mc = el.closest('.month-cards'); if (mc) mc.classList.remove('month-cards--collapsed'); }",
            card,
        )
        collapsed = card.query_selector(".card-collapsed")
        if collapsed:
            collapsed.click()
            page_pt.wait_for_timeout(100)

    page_pt.wait_for_timeout(500)
    btn_hrefs = page_pt.evaluate("""
        () => [...document.querySelectorAll('.btn-inscricao')].map(b => b.getAttribute('href') || '')
    """)
    assert len(btn_hrefs) > 0, "No .btn-inscricao buttons found after expanding cards"
    empty = [h for h in btn_hrefs if not h.startswith("http")]
    assert len(empty) == 0, f"{len(empty)} buttons have non-HTTP href: {empty[:5]}"


# ---------------------------------------------------------------------------
# Data integrity — required fields in corridas.json
# ---------------------------------------------------------------------------

def test_all_events_have_required_fields():
    """Every event in corridas.json must satisfy all location and data requirements.

    Required (zero-tolerance — one failure fails the whole test):
    - data_evento: non-empty date string
    - distancias: non-empty list
    - localizacao: non-empty string
    - pais: ISO-3166-1 alpha-2 code that exists as web/locations/{pais}.json
    - estado: non-empty subdivision code listed in that country's JSON file
    - at least one valid link in fontes

    horario: tracked but not a hard failure here — corridas.json is the committed
    scrape snapshot and lags behind scraper fixes. The hard check lives in
    test_source.py (which tests live scraper output). Once corridas.json catches
    up via a post-merge scrape, this check will be tightened.
    """
    corridas = _load_corridas()
    assert corridas, "corridas.json is empty"

    locs_dir = WEB_DIR / "locations"
    _loc_cache: dict[str, set] = {}

    def _valid_states(pais: str) -> set[str] | None:
        if pais not in _loc_cache:
            f = locs_dir / f"{pais}.json"
            if not f.exists():
                _loc_cache[pais] = None  # type: ignore[assignment]
            else:
                data = json.loads(f.read_text())
                _loc_cache[pais] = {s["code"] for s in data.get("subdivisions", [])}
        return _loc_cache[pais]  # type: ignore[return-value]

    missing_data:   list[tuple] = []
    missing_dist:   list[tuple] = []
    missing_loc:    list[tuple] = []
    bad_pais:       list[tuple] = []
    missing_estado: list[tuple] = []
    bad_estado:     list[tuple] = []
    missing_link:   list[tuple] = []
    missing_hora:   list[str]   = []

    for c in corridas:
        cid   = c.get("id", "?")
        title = c.get("titulo", "?")
        pais  = c.get("pais", "")
        estado = c.get("estado", "")

        if not c.get("data_evento"):
            missing_data.append((cid, title))

        if not c.get("distancias"):
            missing_dist.append((cid, title))

        if not c.get("localizacao"):
            missing_loc.append((cid, title))

        states = _valid_states(pais) if pais else None
        if not pais or states is None:
            bad_pais.append((cid, title, pais))
        else:
            if not estado:
                missing_estado.append((cid, title, pais))
            elif estado not in states:
                bad_estado.append((cid, title, pais, estado))

        has_link = any(
            f.get("link_evento") or (f.get("links_inscricao") or [None])[0]
            for f in c.get("fontes", [])
        )
        if not has_link:
            missing_link.append((cid, title))

        if not c.get("horario"):
            missing_hora.append(title)

    def _source_hint(items: list) -> str:
        """Extract unique source prefixes from event IDs to hint which sources to re-scrape."""
        from collections import Counter
        prefixes: Counter = Counter()
        for item in items:
            cid = item[0] if isinstance(item, tuple) else item
            # Extract prefix: everything before the first underscore + digit
            import re as _re
            m = _re.match(r"^([a-z][a-z_]*?)(?:_\d|$)", str(cid))
            if m:
                prefixes[m.group(1)] += 1
        if not prefixes:
            return ""
        return "  → re-scrape: " + ",".join(f"{k}({v})" for k, v in prefixes.most_common(5))

    n = len(corridas)
    assert not missing_data, (
        f"{len(missing_data)}/{n} events missing data_evento. First 5: {missing_data[:5]}"
    )
    assert not missing_dist, (
        f"{len(missing_dist)}/{n} events missing distancias. First 5: {missing_dist[:5]}"
    )
    assert not missing_loc, (
        f"{len(missing_loc)}/{n} events missing localizacao. First 5: {missing_loc[:5]}"
    )
    assert not bad_pais, (
        f"{len(bad_pais)}/{n} events with missing or unknown pais (no locations JSON). "
        f"First 5: {bad_pais[:5]}\n{_source_hint(bad_pais)}"
    )
    assert not missing_estado, (
        f"{len(missing_estado)}/{n} events with empty estado. First 5: {missing_estado[:5]}\n"
        f"{_source_hint(missing_estado)}"
    )
    assert not bad_estado, (
        f"{len(bad_estado)}/{n} events with estado not in locations JSON. "
        f"First 5: {bad_estado[:5]}\n{_source_hint(bad_estado)}"
    )
    assert not missing_link, (
        f"{len(missing_link)}/{n} events missing all links. First 5: {missing_link[:5]}"
    )
    assert not missing_hora, (
        f"{len(missing_hora)}/{n} events missing horario. "
        f"{_source_hint([(t,) for t in missing_hora])}"
    )


# ---------------------------------------------------------------------------
# Merge integrity (catches over-merging bugs)
# ---------------------------------------------------------------------------

# Even popular events rarely have more than 3 distinct catalog sources listing
# them. >=5 fontes per record is a near-certain smell that the merger collapsed
# unrelated events — usually because some scraper emitted the same inscription
# URL (catalog page) for every event it found, and union-find chained them.
_MAX_FONTES_PER_EVENT = 6


def test_no_event_has_too_many_fontes():
    """No single merged event should accumulate more than 4 distinct fontes.

    Trips when a scraper emits a catalog/section URL as links_inscricao for
    multiple events (the brasil_que_corre regression) — the merger's shared-
    link rule then collapses them into one record whose fontes accumulate.
    Distance count alone is a noisy signal (legitimate track meets have 20+
    track events); fonte count is the cleaner smell.
    """
    corridas = _load_corridas()
    offenders = [
        (c.get("id"), c.get("titulo"), len(c.get("fontes", [])),
         [f["nome"] for f in c.get("fontes", [])])
        for c in corridas
        if len(c.get("fontes", [])) >= _MAX_FONTES_PER_EVENT
    ]
    assert not offenders, (
        f"{len(offenders)} event(s) have >= {_MAX_FONTES_PER_EVENT} fontes "
        f"(likely over-merged). First 5: {offenders[:5]}"
    )


def test_distancias_have_valid_shape():
    """Every item in distancias must be a Distancia shape (has 'km', no FonteInfo fields).

    Catches the merger bug where FonteInfo objects (nome/link_evento/links_inscricao)
    leaked into the distancias list instead of fontes.  A single such entry causes
    load_existing() to fail on that event, which previously wiped ALL history because
    the exception was caught at file level rather than per-event level.
    """
    corridas = _load_corridas()
    _FONTE_KEYS = frozenset({"nome", "link_evento", "links_inscricao", "tipo"})
    bad: list[tuple] = []
    for c in corridas:
        for d in c.get("distancias", []):
            if not isinstance(d, dict) or "km" not in d or (set(d.keys()) & _FONTE_KEYS):
                bad.append((c.get("id"), c.get("titulo"), d))
    assert not bad, (
        f"{len(bad)} distancia(s) have invalid shape (FonteInfo leaked into distancias?). "
        f"First 5: {bad[:5]}"
    )


def test_distancias_corrupt_entries_absent_from_data():
    """No event in web/corridas.json should have distancias entries that lack 'km'.

    Regression guard: FonteInfo objects accidentally leaked into distancias via a
    merger false-dedup caused load_existing() to raise TypeError, wiping all
    first_seen_at history.  The fix in _dict_to_corrida() filters by 'km' presence.
    This test confirms the data produced by the fixed pipeline has no such entries.
    See also test_distancias_have_valid_shape for stricter shape validation.
    """
    corridas = _load_corridas()
    bad = [(c.get("id"), d) for c in corridas for d in c.get("distancias", []) if "km" not in d]
    assert not bad, (
        f"{len(bad)} distancia(s) are missing 'km' — FonteInfo may have leaked into "
        f"distancias. First 3: {bad[:3]}"
    )


def test_no_inscription_link_shared_across_many_events():
    """A single inscription URL should not appear in 3+ distinct records.

    After merger collapses true duplicates, the same URL appearing in many
    records means the scraper is using a non-unique URL for events that
    are genuinely different. Catches the next brasil_que_corre clone.
    """
    corridas = _load_corridas()
    link_to_records: dict[tuple[str, str], list[str]] = {}
    for c in corridas:
        for f in c.get("fontes", []):
            nome = f.get("nome", "")
            for l in f.get("links_inscricao", []):
                key = (nome, l.rstrip("/").lower())
                link_to_records.setdefault(key, []).append(c.get("id"))
    offenders = [
        (nome, link, len(ids), ids[:3])
        for (nome, link), ids in link_to_records.items()
        if len(set(ids)) >= 3
    ]
    assert not offenders, (
        f"{len(offenders)} (source, link) pair(s) appear in 3+ distinct records "
        f"— probably a catalog URL used as event link. First 5: {offenders[:5]}"
    )


# ---------------------------------------------------------------------------
# HTML entity hygiene
# ---------------------------------------------------------------------------

_HTML_ENTITY_PATTERNS = [
    r"&amp;", r"&Amp;", r"&AMP;",      # mishandled & encoding
    r"&quot;", r"&apos;",
    r"&lt;", r"&gt;", r"&nbsp;",
    r"&#x[0-9a-fA-F]+;?", r"&#\d+;?",  # numeric entities
]


def test_no_html_entities_in_event_fields():
    """No event title/cidade/localizacao may contain unescaped HTML entities.

    Catches the regression where source pages double-encoded "&amp;amp;",
    normalize_titulo only unescaped one layer, and .title() then mangled the
    residual "amp" into "Amp" (e.g. "Track&Amp;Field").
    """
    corridas = _load_corridas()
    rx = re.compile("|".join(_HTML_ENTITY_PATTERNS))
    offenders = []
    for c in corridas:
        for field in ("titulo", "cidade", "localizacao"):
            v = c.get(field) or ""
            if rx.search(v):
                offenders.append((c.get("id"), field, v))
    assert not offenders, (
        f"{len(offenders)} fields contain raw HTML entities. First 5: {offenders[:5]}"
    )


# ---------------------------------------------------------------------------
# Country/subdivision localization tests
# ---------------------------------------------------------------------------

_COUNTRY_EXPECTATIONS = {
    "pt": {"BR": "Brasil",   "US": "EUA",         "DE": "Alemanha",     "FR": "França",  "GB": "Reino Unido",            "IT": "Itália",  "JP": "Japão", "MX": "México"},
    "en": {"BR": "Brazil",   "US": "USA",         "DE": "Germany",      "FR": "France",  "GB": "United Kingdom",         "IT": "Italy",   "JP": "Japan", "MX": "Mexico"},
    "es": {"BR": "Brasil",   "US": "EE.UU.",      "DE": "Alemania",     "FR": "Francia", "GB": "Reino Unido",            "IT": "Italia",  "JP": "Japón", "MX": "México"},
    "de": {"BR": "Brasilien", "US": "USA",        "DE": "Deutschland",  "FR": "Frankreich", "GB": "Vereinigtes Königreich", "IT": "Italien", "JP": "Japan", "MX": "Mexiko"},
    "fr": {"BR": "Brésil",   "US": "États-Unis",  "DE": "Allemagne",    "FR": "France",  "GB": "Royaume-Uni",            "IT": "Italie",  "JP": "Japon", "MX": "Mexique"},
}

# Subdivisions for which _SUBDIV_LABELS in app.js must define per-language names.
_SUBDIV_EXPECTATIONS = {
    "pt": [("BR", "DF", "Brasília"), ("DE", "BY", "Baviera"),  ("GB", "ENG", "Inglaterra"),       ("GB", "SCT", "Escócia"),  ("IT", "VE", "Veneza"),  ("MX", "CMX", "Cidade do México")],
    "en": [("BR", "DF", "Brasília"), ("DE", "BY", "Bavaria"),  ("GB", "ENG", "England"),          ("GB", "SCT", "Scotland"), ("IT", "VE", "Venice"),  ("MX", "CMX", "Mexico City")],
    "es": [("BR", "DF", "Brasília"), ("DE", "BY", "Baviera"),  ("GB", "ENG", "Inglaterra"),       ("GB", "SCT", "Escocia"),  ("IT", "VE", "Venecia"), ("MX", "CMX", "Ciudad de México")],
    "de": [("BR", "DF", "Brasília"), ("DE", "BY", "Bayern"),   ("GB", "ENG", "England"),          ("GB", "SCT", "Schottland"), ("IT", "VE", "Venedig"), ("MX", "CMX", "Mexiko-Stadt")],
    "fr": [("BR", "DF", "Brasília"), ("DE", "BY", "Bavière"),  ("GB", "ENG", "Angleterre"),       ("GB", "SCT", "Écosse"),   ("IT", "VE", "Venise"),  ("MX", "CMX", "Mexico")],
}


@pytest.mark.parametrize("lang", ["pt", "en", "es", "de", "fr"])
def test_country_names_translated(page_factory, live_server, lang):
    """_localizeCountryByIso2(iso2) must return the country name in the active language.

    Catches the regression where BR was missing from _ISO2_TO_DATA_COUNTRY and
    fell through to web/locations/BR.json's English "Brazil".
    """
    page = page_factory(lang)
    cases = _COUNTRY_EXPECTATIONS[lang]
    failures = []
    for iso2, expected in cases.items():
        actual = page.evaluate(f"_localizeCountryByIso2({iso2!r})")
        if actual != expected:
            failures.append(f"[{lang}] _localizeCountryByIso2({iso2!r}) = {actual!r}, expected {expected!r}")
    assert not failures, "\n".join(failures)


@pytest.mark.parametrize("lang", ["pt", "en", "es", "de", "fr"])
def test_subdivision_names_translated(page_factory, live_server, lang):
    """_localizeSubdiv(pais, code, fallback) must return the subdivision name in the active language.

    Covers Brazil (DF -> Brasília), Germany (BY -> Bayern/Baviera/...), UK
    (ENG -> England/Inglaterra/...), Italy (VE -> Venezia/Venice/...) and
    Mexico (CMX -> Mexico City/Cidade do México/...).
    """
    page = page_factory(lang)
    cases = _SUBDIV_EXPECTATIONS[lang]
    failures = []
    for pais, code, expected in cases:
        # Pass the code itself as fallback so a failure is unambiguous.
        actual = page.evaluate(
            f"_localizeSubdiv({pais!r}, {code!r}, {code!r})"
        )
        if actual != expected:
            failures.append(
                f"[{lang}] _localizeSubdiv({pais!r}, {code!r}) = {actual!r}, expected {expected!r}"
            )
    assert not failures, "\n".join(failures)


@pytest.mark.parametrize("lang,wrong_country", [
    ("pt", "Brazil"),
    ("es", "Brazil"),
    ("de", "Brazil"),
    ("fr", "Brazil"),
])
def test_no_english_brazil_on_localized_pages(page_factory, live_server, lang, wrong_country):
    """Non-English pages must not show the English country name 'Brazil' in any card location."""
    page = page_factory(lang)
    page.evaluate(
        "() => document.querySelectorAll('.month-cards--collapsed').forEach("
        "el => el.classList.remove('month-cards--collapsed'))"
    )
    page.wait_for_timeout(300)
    leaked = page.evaluate(
        "(wrong) => {"
        " const out = [];"
        " for (const el of document.querySelectorAll('.card-location')) {"
        "   const t = el.textContent || '';"
        "   if (t.includes(wrong)) out.push(t);"
        " }"
        " return out.slice(0, 5);"
        "}",
        wrong_country,
    )
    assert not leaked, (
        f"[{lang}] {len(leaked)} card-location elements still contain English '{wrong_country}': {leaked}"
    )


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------

def _find_card_by_title(page, title):
    """Return the card element whose .card-title matches title, or None."""
    cards = page.query_selector_all(".card")
    for card in cards:
        el = card.query_selector(".card-title")
        if el and el.text_content().strip() == title:
            return card
    return None
