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

# Probe any URL before writing a scraper — shows JSON structure, __NEXT_DATA__,
# auth requirements, pagination. Completes in ~1 min. Full response saved as artifact.
# → run "Probe URL" workflow with inputs: url, method (GET/POST), params, body, headers

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

- `id` field on `Corrida`: stable identifier the scraper produces. Used by `reconcile()` to match across runs. Common patterns: `ts_<event_id>` for Ticket Sports, `runsignup_<race_id>_<year>`, `<slug>_<state>_<event_date>` for scraped calendar sources. Never use the scrape/run date in an ID — it changes every run, breaking exact-ID reconciliation and resetting `first_seen_at`.
- **Every event must be mapped to exactly one country (`pais`) and one state/province (`estado`).** `"INT"` is never an acceptable value for either field.
  - `pais` must be a valid ISO-3166-1 alpha-2 code (e.g. `"BR"`, `"US"`, `"MX"`).
  - `estado` must be a recognised subdivision code for that country as defined in `web/locations/{pais}.json`, or an empty string `""` if the subdivision is unknown or the country has no subdivisions in the repo. Leave it `""` — the pipeline's `_resolve_missing_locations()` will attempt to fill it in via `geo.resolve()` and the persistent Nominatim cache.
  - **Never discard an event solely because its country or state is hard to determine.** Always try `geo.resolve(city, "", pais_hint)` before giving up. Only skip the event if even the country cannot be resolved.
  - Brazilian states: 2-letter UFs (`SP`, `DF`, `SE`…). The `Corrida.estado` field drives the frontend's location filter.
- **Location display in the frontend must use only values from the JSON files.** The `_buildCardLocation()` function in `app.js` enforces this: for non-BR events it validates `c.estado` against the loaded `web/locations/{pais}.json` subdivisions and uses the localized subdivision name (via `_SUBDIV_LABELS`) when the code is valid. If `estado` is empty or not in the JSON, it falls back to `c.cidade` (first comma-segment). This means:
  - A scraper that sets `estado="VE"` for an Italian event will show "Venice" (EN) / "Veneza" (PT) / "Venecia" (ES) / "Venedig" (DE) / "Venise" (FR) — automatically in all languages.
  - A scraper that sets a free-text city or wrong-country code will display the raw city name instead.
  - **Never invent subdivision codes.** Only use codes present in `web/locations/{pais}.json`. If the correct province/state isn't in the file, add it to both the JSON file and `_SUBDIV_LABELS` in `app.js`.
  - **`_SUBDIV_LABELS` in `app.js`** must be kept in sync: whenever a new country's `web/locations/{country}.json` is used and its subdivisions appear in events, add localized labels for those subdivisions. Current countries with labels beyond BR/US/CA/GB/AU: IT, JP, GR, DK, SE, IE, FR, PT, PL, CZ, NO, FI, CH, NL.
- For TF Sports specifically: many addresses end with `, SP` regardless of the actual state. The `tf_sports.py` scraper has a CEP→UF range table (`_CEP_RANGES`) that overrides a contradictory trailing UF — preserve this when modifying.

### CI workflows

- **`scrape.yml`** — four times daily (00:00, 06:00, 12:00 and 18:00 UTC) + on push to `scraper/`/`web/`. Runs `scraper.main`, copies `corridas.json` to `web/`, commits with `[skip ci]`.
- **`test-sources.yml`** — daily 09:00 UTC + on push to `scraper/sources/`. Builds a job matrix dynamically: when shared infra (`models.py`, `utils.py`, `http_client.py`, `playwright_client.py`) changes, all sources are tested; otherwise only changed source files. Each job uploads a single-result artifact, then a final `update-readme` job aggregates all artifacts and runs `scripts/update_source_status.py` to refresh README tables and `data/source-status.json` (the source's row in README.md uses an embedded HTML comment `<!--module_name-->` for stable matching).
- **`debug-scraper.yml`** — manual trigger with a `source` input; uploads full log as artifact.

### Frontend (`web/`)

- `index.html` redirects to `/{LANG}` based on `navigator.language`. `LANG` is determined by URL path prefix (`/pt`, `/en`, …) and falls back to `BROWSER_LANG`.
- `app.js` is one file, ~1800 lines. Top of file: `STRINGS` table (5 locales, all UI strings), state object, geolocation pipeline (IP-based via `ipwho.is`/`freeipapi.com`/`api.ip.sb`). The custom dropdown widgets (`estado-filter-*`, `fonte-filter-*`) replace native `<select>` for styling and multi-select. Card template lives inline in each `*/index.html` as `<template id="cardTemplate">`.
- Filter persistence: `localStorage['corridas_filters']` (object with `estado`, `fontes` set, distance pills, etc.). `sessionStorage['_geoCache']` is used to carry detected geo across cross-language navigation so the new page applies the location filter immediately.
- "Novo" badge logic: an event is "new" when `first_seen_at >= threeDaysAgo` (3-day window). The badge appears on cards **and** on month-section headers (any event in the month qualifying). The `<span class="badge-novo">` element must exist in the card template — JS uses `card.querySelector('.badge-novo')` and silently no-ops if missing.
- The expanded card's distance table only renders the **Date** or **Horário** column when values differ across distances. If every `Distancia` shares the same date or horário, that column is suppressed (the value is already on the card-level header).
- `periodo_inscricao` is stored in the data model but **never displayed** in the frontend. Do not add any UI for it — no section title, no dates, no block of any kind.
- `links_inscricao` in each `FonteInfo` should always be `[link_evento]` — the source page where the event data was scraped from. **No conditional logic based on `inscricoes_abertas`.** The button always shows and always leads to the source event page.
- **Every event must have at least one real, working link.** Never emit `links_inscricao=[]` from a scraper; if a more specific registration URL isn't available, fall back to `[link_evento]`. The pipeline (`_ensure_inscricao_links()` in `scraper/main.py`) also enforces this as a final safety net, and the frontend falls back to `link_evento` when `links_inscricao` is missing — but scrapers should still produce non-empty links to begin with.

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

## Exploring and validating new sources

**Never write a scraper before probing the target.** The correct flow is:
probe → understand → implement → test via CI. Skipping the probe phase leads
to scrapers that guess at field names and API paths, which wastes CI minutes
and produces false "inviable" conclusions.

### Phase 1 — Probe (before writing any code)

Use the **"Probe URL"** GitHub Actions workflow (Actions → Probe URL → Run
workflow). It runs in ~1 minute, uses the full proxy chain
(direct → Scrapestack → Apify), and uploads the full response as an artifact.

**Always probe at least two URLs per source:**

1. The **HTML listing page** (e.g. `https://raceroster.com/events`) — even if
   you suspect there's an API. Many platforms that protect their API still
   serve all data in `__NEXT_DATA__` on the public HTML page.
2. Any **suspected API endpoint** (e.g. `https://raceroster.com/api/v2/events`).

**Interpreting probe output:**

| Result | Meaning | Strategy |
|---|---|---|
| HTTP 200 + JSON with event list | Public REST API ✅ | REST scraper, paginate |
| HTTP 200 + HTML with `__NEXT_DATA__` containing events | Next.js SSR ✅ | Extract `__NEXT_DATA__` (see `asdeporte.py`) |
| HTTP 200 + HTML, no `__NEXT_DATA__`, no embedded JSON | Client-side SPA | Playwright or inviable |
| HTTP 401 / 403 on API, but 200 on HTML page | API requires auth, HTML is public | Scrape HTML instead |
| HTTP 401 / 403 on both | Auth required or WAF | Check if there's a widget/embed endpoint |
| HTTP 200 + JSON `{"errors": [...]}` | API exists but auth/schema wrong | Fix query or headers |

**Probe inputs reference:**

```
URL:     https://example.com/events?category=running
Method:  GET
Params:  {"page": 1, "per_page": 5}          ← query string params (GET)
Body:    {"operationName":"X","variables":{}} ← POST body (GraphQL)
Headers: {"Authorization": "Bearer token"}   ← extra headers
```

### Phase 2 — Understand the data structure

From the probe artifact (`probe-output/response.txt`) and console output, map:

- **Event name**: which field? (`name`, `title`, `nameEvent`, …)
- **Date**: which field and format? ISO `YYYY-MM-DD`, Unix timestamp, `dd/mm/yyyy`?
- **Location**: city, state/region, country — separate fields or a single string?
- **Distances**: structured sub-events array, or embedded in the event name?
- **Pagination**: `page`/`per_page` params? `Link` response header? Cursor-based?
- **Auth**: did the probe succeed without credentials? If 401/403, is there a
  public HTML alternative?

Spend five minutes reading the probe output before writing a single line of code.

### Phase 3 — Implement

Choose the right pattern:

| Probe finding | Reference scraper |
|---|---|
| Paginated REST JSON API | `runsignup.py`, `halfmarathons.py` |
| Next.js `__NEXT_DATA__` | `asdeporte.py` |
| Strapi / Next.js with token in JS bundle | `tf_sports.py` |
| Single known event page | `scraper/sources/majors/_base.py` |
| Playwright needed | `largada_esportiva.py` |

Multi-sport platforms (anything listing cycling, triathlon, yoga, …) **must**
have both `_RUNNING_KW` (inclusion) and `_NON_RUNNING` (exclusion) regexes.
Check `sympla.py` for the canonical pattern.

### Phase 4 — Test via CI (not locally)

Outbound HTTP is blocked in the Claude Code sandbox. Do not attempt local
`python -m scraper.test_source` runs and conclude a source is broken — it
will always return 0 events in the sandbox. Use CI exclusively:

```
# Quick test — matrix job, result visible in ~3 min:
Actions → "Test Sources" → Run workflow → source: <name>

# Full log with all print() output — best for debugging field parsing:
Actions → "Debug Scraper"  → Run workflow → source: <name>
```

Download the log artifact and look for:
- The HTTP status on each attempt (direct / Scrapestack / Apify)
- How many raw events were fetched before filtering
- Which filter (`_is_running_event`, `_parse_distances`, date check) dropped events
- Whether the JSON structure matched what you saw in the probe

### Phase 5 — Validate results

A passing CI run (`✅ N eventos`) is necessary but not sufficient. Check:

- **Diversity**: are events from multiple cities/regions, or all the same?
- **Distances**: do they look right? (1–250 km, or `"N mi"` for miles)
- **Dates**: all in the future and within the lookahead window?
- **No garbage**: titles that look like nav links, JS variable names, empty strings?
- **No non-running**: spot-check for cycling, triathlon, swimming events
- **Stable IDs**: run twice — do the same events get the same `id`?

### Common pitfalls

- **Only testing the API, not the HTML page.** Platforms like Race Roster have
  a public `/events` page that may have `__NEXT_DATA__` even when their API
  requires OAuth. Always probe both.
- **Assuming "0 eventos" = inviable.** Could be: wrong date range, seasonal
  lull, filter too strict, or the scraper crashed silently. Read the full log.
- **Rotating credentials.** If a GraphQL API needs a key that rotates (e.g.
  World Athletics), the HTML page is often the viable alternative.
- **Sandbox HTTP block.** `httpx`, `WebFetch`, and local `test_source` all
  return 403 in the Claude Code sandbox. Never declare a source inviable based
  on local/sandbox results alone.
- **Baking dates into IDs.** IDs must be stable across runs. `event_123_2026`
  is fine; `event_123_2026-05-15` forces re-creation on every scrape run.

## Sandbox / local-dev caveats

This repository is often touched from a Claude Code sandbox where outbound HTTP is restricted (`Host not in allowlist` returning 403). When a scraper appears to fail locally with 403 from `httpx`, that's almost always the sandbox — not the source. Validate fixes by pushing and watching `Test Sources` CI rather than relying on local runs.

## Never infer event data from opaque IDs

Event information (dates, location, title) must be obtained **explicitly** from page content, API response fields, or structured data — never inferred from ID strings, URL slugs, or opaque identifiers. Platform IDs like `02605131942` in a URL are opaque: they encode nothing meaningful and must never be decoded as a date, location, or any other value. If explicit data is not available from a page or API field, leave the field empty or unset — do not guess.

## Source-specific research notes

These are findings from past deep-dives. Read before touching the relevant sources.

### correr_brasilia.py — EventOn JSON-LD (fixed 2026-05-23)

**Root cause of "1 event returned" bug**: The original scraper used
`soup.select("article") or soup.select(".event") or ...`. WordPress injects
`<article>` tags for every post, so the `article` selector always matched first
and returned only 1 generic article — the `.eventon_list_event` CSS path was
never reached.

**Fix**: Switch to parsing `<script type="application/ld+json">` blocks. The
EventOn WordPress plugin embeds a full `schema.org/Event` JSON-LD object per
event with `@type`, `name`, `startDate`, `url`, `image`, and `location`.
This is far more reliable than HTML structure. See current `correr_brasilia.py`.

ID scheme: EventOn emits `@id` values like `"event_44938_0"` — use those when
present (`correrbsb_event_44938_0`) for stability; fall back to
`correrbsb_{slug}_{year}` for events that lack a numeric ID.

### TF Sports — architecture map (researched 2026-05-23)

TF Sports operates **three separate backend systems**. Know which one you're
dealing with before probing:

| Domain | What it is | Auth |
|---|---|---|
| `painel-website.tfsports.com.br/api` | Strapi CMS (website content) | Public for `run-series`; 403 for `events` |
| `api.prod.tfsports.com.br` | Mobile app backend (REST + GraphQL) | **All endpoints require Bearer token** |
| `link.prod.tfsports.com.br/events/{slug}` | Deeplink SPA — opens app | No event data; redirects to app store |
| `events.tfsports.com.br` | Planned/decommissioned web app | DNS does not resolve (as of 2026-05-23) |
| `assets-prod.tfsports.com.br` | S3/CloudFront asset storage | Static files only |

**Strapi CMS** (`painel-website.tfsports.com.br/api`): The `run-series`
collection is publicly paginated at `/api/run-series?populate=...&locale=pt-BR`.
The `events` collection exists but returns 403. Approximately 1900 events were
scanned across all locales — Flying Run is **not** in Strapi.

**Mobile API** (`api.prod.tfsports.com.br`): Every endpoint —
`/events`, `/events/{id}`, `/events?slug=...`, `/graphql` — returns
`{"message":"Unauthorized"}` or `{"message":"Missing Authentication Token"}`.
No anonymous/public access path was found. The domain may also be
geo-restricted (DNS fails from GitHub Actions in some runs, resolves in others).

**Deeplink service**: `link.prod.tfsports.com.br/events/{slug}` is a generic
SPA. The redirect JS does `window.location.href.replace("https://","tfsports://")`,
i.e. universal links into the mobile app. No event metadata is in the HTML.
Flying Run's slug is `flying-run-sunset-braslia-2026` (note: missing "i", typo
from TF Sports side).

**Bottom line**: Flying Run Sunset Brasília and similar TF Sports app-native
events are **not accessible** via any public API. They are sourced via
`correr_brasilia.py` (which aggregates them from correrbrasilia.com.br).
Do not re-investigate TF Sports mobile auth — the path is closed.

### tf_sports_app.py — what it actually finds

`tf_sports_app.py` queries the Strapi `run-series` collection with
`locale=pt-BR`. It successfully finds pt-BR-only events (e.g. Run Series IDs
102824+) that `tf_sports.py` (which uses the pt-BR Bearer token from the Next.js
bundle) misses. The two scrapers are complementary; keep both active.
Flying Run is not in Strapi and will never appear via `tf_sports_app.py`.

## Autonomy: CI and iteration

Claude must run tests and iterate **independently**, without asking the user to trigger GitHub Actions workflows. Push changes to the feature branch and let CI validate them autonomously. To probe a URL, push a `probe-config.json` to the `probe` branch and poll `probe-output/result.md` for results. To test a source, push the scraper change and monitor the `Test Sources` workflow. To run the full pipeline, push to `scraper/` and let `scrape.yml` run. **Never ask the user to manually run "Probe URL", "Test Sources", or "Debug Scraper"** — trigger them by pushing the appropriate changes and monitoring the outcome via `mcp__github__*` tools.