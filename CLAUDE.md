# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

A static-site aggregator for road-running events, hosted on GitHub Pages. A Python scraper runs on a 4-hour cron in GitHub Actions, hits ~50 distinct sources (Brazilian calendars, single-event sites, World Marathon Majors, US/UK platforms), deduplicates and merges results, and commits the resulting `data/corridas.json` (also copied to `web/corridas.json`). The frontend is plain HTML/CSS/JS — no framework, no build step. The site is multilingual (pt/en/es/de/fr) with separate `web/{lang}/index.html` shells loading the same `web/app.js`.

## Common commands

```bash
# Install (Python 3.12)
pip install -r requirements.txt
playwright install chromium --with-deps

# Run the full pipeline locally — writes data/corridas.json
python -m scraper.main

# Test a single source (used by CI). Path is the module name under scraper/sources/
# or scraper/sources/majors/. Prints first 5 events and FAILURE_NOTE: line on
# failure, returns exit 1 on failure or zero events.
python -m scraper.test_source ticket_sports
python -m scraper.test_source majors/london

# Debug a source with full pipeline log via GitHub Actions UI
# → run "Debug Scraper" workflow with input=<source-name>

# Manually re-run all source tests (workflow updates README + data/source-status.json)
# → run "Test Sources" workflow with input="all"

# Serve the static site locally (any static server works, e.g.):
python -m http.server -d web 8000
```

There is no test suite, no linter, and no build step. Source health is verified end-to-end by the `Test Sources` matrix workflow, which runs each source as an independent job.

## Architecture

### Scraper pipeline (`scraper/main.py`)

1. **`run_all_scrapers()`** invokes each module in `SOURCES` in a `ThreadPoolExecutor`. Every source module exports a `scrape() -> list[Corrida]` function — that's the entire interface. Failures in one source never block the others.
2. **`reconcile()`** matches each freshly-scraped `Corrida` against `data/corridas.json` from the previous run by `id` and by `merger.are_duplicates()`. Found matches are updated via `_update_from`, missing ones increment `miss_count` and are dropped after 10 consecutive misses.
3. **`merger.merge_rodada()`** runs a within-batch dedup: same event seen in multiple sources collapses into one record whose champion is selected by `merger.score()` (completeness heuristic), and whose `fontes` list accumulates every source that found it. Title similarity uses `normalize_titulo_merge` + `difflib.SequenceMatcher`; date tolerance is 14 days (30 if titles match almost exactly).
4. **`_find_all_photos()` / `_enrich_images()`** opportunistically pull missing images via OG tags or platform-specific photo galleries (`scraper/fotos.py`). Uses `http_client.get_direct()` to avoid burning Scrapestack credits.
5. **`save()`** sorts by `data_evento`, writes `data/corridas.json` (and the workflow then copies it to `web/corridas.json`).

The `Corrida` dataclass (`scraper/models.py`) is the canonical shape — including `Distancia.km` which can be a `float` (kilometres) **or a `str` like `"5 mi"`** (miles preserved verbatim — the frontend's `formatKm` passes strings through). Don't normalize miles to km. `Distancia.data` and `Distancia.horario` are per-distance overrides; the frontend only renders those columns when **values differ across distances**.

### HTTP fallback chain (`scraper/http_client.py`)

Every scraper calls `get(url, ...)`. The chain is:

1. Direct `httpx` request with browser-like headers
2. **Scrapestack** (`SCRAPESTACK_KEY` env) — pass `render_js=True` to make it execute JS for Cloudflare-challenge sites
3. **Apify residential proxy** (`APIFY_PROXY_PASSWORD` / `APIFY_TOKEN` env)

WAF statuses (403/406/429) trigger fallback automatically; transient httpx exceptions (timeout/connect) re-raise. Sources can fall through to **Playwright** (`scraper/playwright_client.py` — basic anti-detection: disables `navigator.webdriver`, fakes `window.chrome`) when even the proxy chain fails. `get_direct()` skips the proxy chain entirely — used by `fotos.py`.

### Adding a new source

1. Create `scraper/sources/<name>.py` exporting `scrape() -> list[Corrida]`. Use `from ..models import Corrida, Distancia, FonteInfo` and `from ..http_client import get`. Each `Corrida` must include exactly one `FonteInfo` (the merger handles multi-source consolidation later). Set `first_seen_at` / `updated_at` to `now_iso()`.
2. Register the module in **both** `scraper/sources/__init__.py` (the import block) and `scraper/main.py` (`SOURCES` list — order is unimportant but keep section comments consistent).
3. Add the module name (e.g. `runsignup` or `majors/london`) to the dropdown options in `.github/workflows/test-sources.yml`. Sort alphabetically within the existing groupings.
4. Reference patterns: `ticket_sports.py` for direct JSON APIs, `tf_sports.py` for Strapi APIs with Bearer tokens scraped from a Next.js bundle, `runsignup.py` for paginated REST APIs, `majors/_base.py` for the shared single-event scaffold.
5. Strict scope: title-keyword filtering (running terms in, non-running out) is mandatory for general-purpose platforms (`sympla.py`, `runsignup.py`) — they list thousands of unrelated events. Always apply both an inclusion and an exclusion regex, mirroring `sympla.py` `_RUNNING_KW` / `_NON_RUNNING_KW`.

### Source naming conventions

- `id` field on `Corrida`: stable identifier the scraper produces. Used by `reconcile()` to match across runs. Common patterns: `ts_<event_id>` for Ticket Sports, `runsignup_<race_id>_<year>`, `<slug>_<state>_<today>`. Don't bake the run date into IDs of stable events — it forces re-creation on every run.
- Brazilian states use 2-letter UFs (`SP`, `DF`, `SE`…). International events use `INT`. The `Corrida.estado` field drives the frontend's location filter.
- For TF Sports specifically: many addresses end with `, SP` regardless of the actual state. The `tf_sports.py` scraper has a CEP→UF range table (`_CEP_RANGES`) that overrides a contradictory trailing UF — preserve this when modifying.

### CI workflows

- **`scrape.yml`** — twice daily (06:00 and 18:00 UTC) + on push to `scraper/`/`web/`. Runs `scraper.main`, copies `corridas.json` to `web/`, commits with `[skip ci]`.
- **`test-sources.yml`** — daily 09:00 UTC + on push to `scraper/sources/`. Builds a job matrix dynamically: when shared infra (`models.py`, `utils.py`, `http_client.py`, `playwright_client.py`) changes, all sources are tested; otherwise only changed source files. Each job uploads a single-result artifact, then a final `update-readme` job aggregates all artifacts and runs `scripts/update_source_status.py` to refresh README tables and `data/source-status.json` (the source's row in README.md uses an embedded HTML comment `<!--module_name-->` for stable matching).
- **`debug-scraper.yml`** — manual trigger with a `source` input; uploads full log as artifact.

### Frontend (`web/`)

- `index.html` redirects to `/{LANG}` based on `navigator.language`. `LANG` is determined by URL path prefix (`/pt`, `/en`, …) and falls back to `BROWSER_LANG`.
- `app.js` is one file, ~1800 lines. Top of file: `STRINGS` table (5 locales, all UI strings), state object, geolocation pipeline (IP-based via `ipwho.is`/`freeipapi.com`/`api.ip.sb`). The custom dropdown widgets (`estado-filter-*`, `fonte-filter-*`) replace native `<select>` for styling and multi-select. Card template lives inline in each `*/index.html` as `<template id="cardTemplate">`.
- Filter persistence: `localStorage['corridas_filters']` (object with `estado`, `fontes` set, distance pills, etc.). `sessionStorage['_geoCache']` is used to carry detected geo across cross-language navigation so the new page applies the location filter immediately.
- "Novo" badge logic: an event is "new" when `Date.now() - first_seen_at < 7 days`. The badge appears on cards **and** on month-section headers (any event in the month qualifying). The `<span class="badge-novo">` element must exist in the card template — JS uses `card.querySelector('.badge-novo')` and silently no-ops if missing.
- The expanded card's distance table only renders the **Date** or **Horário** column when values differ across distances. If every `Distancia` shares the same date or horário, that column is suppressed (the value is already on the card-level header).
- `periodo_inscricao` is stored in the data model but **never displayed** in the frontend. Do not add any UI for it — no section title, no dates, no block of any kind.
- `links_inscricao` in each `FonteInfo` should always be `[link_evento]` — the source page where the event data was scraped from. **No conditional logic based on `inscricoes_abertas`.** The button always shows and always leads to the source event page.

### Frontend distances are unit-aware

`Distancia.km` is intentionally polymorphic: `5.0` renders as `5K`, `21.097` as `21K`, the string `"5 mi"` renders verbatim. When adding a source with mixed-unit distances (RunSignup is the canonical example), keep miles as `"<n> mi"` strings — do not convert.

## README is the source of truth for source status

`README.md` carries per-source health tables that are regenerated by `scripts/update_source_status.py` from artifact JSON. Don't hand-edit the status/timestamp columns — they'll be overwritten. Display names and URLs in the first three columns are hand-maintained; the script preserves them.

## Diagnosing and dropping failing sources

**"0 eventos" alone is not sufficient evidence of WAF blocking.** A source returning zero events could be WAF, but it could equally be a scraper bug, a changed site structure, a seasonal lull with no upcoming events, or an API endpoint that moved. Never drop a source or declare it WAF-blocked based solely on a failed CI result.

The correct process before removing a source:

1. **Read the CI logs.** Trigger the "Debug Scraper" workflow (`debug-scraper.yml`) with the source name and download the full log artifact. Look for explicit HTTP error codes (403, 429, Cloudflare challenge page, WAF fingerprint in HTML), not just "0 eventos".
2. **Distinguish root causes:**
   - HTTP 403/406 from all fallbacks (direct + Scrapestack + Apify proxy) + Playwright also blocked → likely WAF. Confirm by checking whether the response body is a Cloudflare challenge page (look for `cf-ray`, `cf-mitigated`, or `Just a moment...` in the HTML).
   - Empty HTML / missing CSS selectors / JSON parse error / changed API path → scraper bug or site restructure — fix the scraper.
   - No events in the date range → not a failure; leave the source active.
3. **Only drop a source** once you have unambiguous confirmation (explicit HTTP blocks across all proxy layers, or Cloudflare challenge HTML confirmed in logs) that the block is at datacenter-IP level and no bypass exists. Document the reason in the README commit message and the source-status.json.
4. When dropping: remove the `.py` file, remove from `__init__.py`, `main.py` SOURCES list, `.github/workflows/test-sources.yml` dropdown, the README table row, and `data/source-status.json`.

## Sandbox / local-dev caveats

This repository is often touched from a Claude Code sandbox where outbound HTTP is restricted (`Host not in allowlist` returning 403). When a scraper appears to fail locally with 403 from `httpx`, that's almost always the sandbox — not the source. Validate fixes by pushing and watching `Test Sources` CI rather than relying on local runs.