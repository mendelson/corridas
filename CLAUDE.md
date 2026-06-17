# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

A static-site aggregator for road-running events, hosted on GitHub Pages. A Python scraper runs on a 4-hour cron in GitHub Actions, hits ~50 distinct sources (Brazilian calendars, single-event sites, World Marathon Majors, US/UK platforms), deduplicates and merges results, and commits the resulting `data/corridas.json` (also copied to `web/corridas.json`). The frontend is plain HTML/CSS/JS — no framework, no build step. The site is multilingual (pt/en/es/de/fr) with separate `web/{lang}/index.html` shells loading the same `web/app.js`.

**The site is a worldwide aggregator — not a Brazilian site that happens to list other countries.** All 5 locales (pt/en/es/de/fr) and all supported countries/locations are first-class. Every product decision — UX, SEO, prerendered content, static pages, filters, copy — must serve every supported language and location, never only pt/BR. Do not scope a feature to Brazil by default; if a rollout must be phased, the phasing criterion must be explicit and justified (e.g. volume, cost caps), not an assumption that Brazil is "the" audience.

## Common commands

```bash
# Install (Python 3.12)
pip install -r requirements.txt
playwright install chromium --with-deps

# Run the full pipeline locally — writes data/corridas.json
python -m scraper.main

# Test a single source (used by CI). Path is the module name under scraper/sources/
# or scraper/sources/evento_unico/. Prints first 5 events and FAILURE_NOTE: line on
# failure, returns exit 1 on failure or zero events.
python -m scraper.test_source ticket_sports
python -m scraper.test_source evento_unico/london

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
4. **`_find_all_photos()` / `_enrich_images()`** opportunistically pull missing images via OG tags or platform-specific photo galleries (`scraper/fotos.py`). Uses `http_client.get_direct()` (no WAF-raising) for these optional fetches.
5. **`save()`** sorts by `data_evento`, writes `data/corridas.json` (and the workflow then copies it to `web/corridas.json`).

The `Corrida` dataclass (`scraper/models.py`) is the canonical shape — including `Distancia.km` which can be a `float` (kilometres) **or a `str` like `"5 mi"`** (miles preserved verbatim — the frontend's `formatKm` passes strings through). Don't normalize miles to km. `Distancia.data` and `Distancia.horario` are per-distance overrides; the frontend only renders those columns when **values differ across distances**.

### HTTP fallback chain (`scraper/http_client.py`)

Every scraper calls `get(url, ...)`. It makes a **direct `httpx` request** with
browser-like headers — there is no third-party proxy layer. (Scrapestack and
Apify were removed in 2026-06: both trial keys had lapsed and every fallback
through them returned 429/403, so they only added latency without ever
succeeding.) A WAF status (403/406/429) raises `httpx.HTTPStatusError` so the
caller can fall through to **Playwright** (`scraper/playwright_client.py` — basic
anti-detection: disables `navigator.webdriver`, fakes `window.chrome`). Pass
`extra_headers={...}` to merge per-call header overrides on top of the shared
`HEADERS` (e.g. the `Accept: application/json` + `Referer`/`Origin` triplet
raceroster's XHR API needs). `get_direct()` is identical but does not raise on
WAF statuses — used by `fotos.py` for optional image fetches.

### Adding a new source

1. Create `scraper/sources/<name>.py` exporting `scrape() -> list[Corrida]`. Use `from ..models import Corrida, Distancia, FonteInfo` and `from ..http_client import get`. Each `Corrida` must include exactly one `FonteInfo` (the merger handles multi-source consolidation later). Set `first_seen_at` / `updated_at` to `now_iso()`.
2. Register the module in **both** `scraper/sources/__init__.py` (the import block) and `scraper/main.py` (`SOURCES` list — order is unimportant but keep section comments consistent).
3. Add the module name (e.g. `runsignup` or `evento_unico/london`) to the dropdown options in `.github/workflows/monitor-source-health.yml`. Sort alphabetically within the existing groupings.
4. Reference patterns: `ticket_sports.py` for direct JSON APIs, `tf_sports.py` for Strapi APIs with Bearer tokens scraped from a Next.js bundle, `runsignup.py` for paginated REST APIs, `evento_unico/_base.py` for the shared single-event scaffold.
5. Strict scope: title-keyword filtering (running terms in, non-running out) is mandatory for general-purpose platforms (`sympla.py`, `runsignup.py`) — they list thousands of unrelated events. Always apply both an inclusion and an exclusion regex, mirroring `sympla.py` `_RUNNING_KW` / `_NON_RUNNING_KW`.
6. **Every `FonteInfo` must declare `tipo`** — one of the three values below. This is enforced by `test_source.py` (hard failure if missing or invalid). The frontend uses `tipo` to order source buttons (inscription/organizer first, calendar last).

### Source `tipo` categorization

Every source module must set `tipo` on its `FonteInfo`. The three categories and current assignments:

| `tipo` | Meaning | Current sources |
|---|---|---|
| `"inscricao"` | Platform where the user actually registers | `atletis`, `ativo`, `asdeporte`, `minhas_inscricoes`, `portal_das_corridas`, `raceroster`, `runsignup`, `ticket_sports`, `yescom` |
| `"organizador"` | Official race organizer — owns and runs the event | `circuito_das_estacoes`, `maratona_porto_alegre`, `maratona_rio`, `mks_esportes`, `sao_silvestre`, `sesc_df`, `sp_city_marathon`, `tf_sports`, `tf_sports_app`, `usroadrunning`, `volta_do_lago`, all `evento_unico/` |
| `"calendario"` | Aggregator/calendar that lists events but doesn't process registration | `bora_correr`, `brasil_corrida`, `brasil_que_corre`, `carreras_mexico`, `central_da_corrida`, `correr_brasilia`, `corridas_brasil`, `halfmarathons`, `iguana_sports`, `largada_esportiva`, `runner_brasil`, `world_athletics` |

When in doubt: if you can click a "register" button on that source's page and pay money, it's `"inscricao"`. If the site is the race's official page, it's `"organizador"`. Otherwise, `"calendario"`.

### Source naming conventions

- `id` field on `Corrida`: stable identifier the scraper produces. Used by `reconcile()` to match across runs. Common patterns: `ts_<event_id>` for Ticket Sports, `runsignup_<race_id>_<year>`, `<slug>_<state>_<event_date>` for scraped calendar sources. Never use the scrape/run date in an ID — it changes every run, breaking exact-ID reconciliation and resetting `first_seen_at`.
- **Subdivisions reference data lives in exactly one place: `web/locations/{pais}.json`.** This single directory is served statically to the frontend (`web/app.js` fetches `../locations/{iso2}.json`) **and** read by the scraper's geo resolver (`scraper/geo.py`) and the pipeline (`scraper/main.py`). It is regenerated by `scripts/generate_locations.py`, which writes straight into `web/locations/`. There is **no** second top-level `locations/` copy — that historical duplicate drifted out of sync and was removed; `tests/test_locations.py` guards against it returning. Never reintroduce a parallel locations directory.
- **Every event must be mapped to exactly one country (`pais`) and one state/province (`estado`).** `"INT"` is never an acceptable value for either field.
  - `pais` must be a valid ISO-3166-1 alpha-2 code (e.g. `"BR"`, `"US"`, `"MX"`).
  - `estado` must be a recognised subdivision code for that country as defined in `web/locations/{pais}.json`, or an empty string `""` if the subdivision is unknown or the country has no subdivisions in the repo. Leave it `""` — the pipeline's `_resolve_missing_locations()` will attempt to fill it in via `geo.resolve()` and the persistent Nominatim cache.
  - **Never discard an event solely because its country or state is hard to determine.** Always try `geo.resolve(city, "", pais_hint)` before giving up. Only skip the event if even the country cannot be resolved.
  - Brazilian states: 2-letter UFs (`SP`, `DF`, `SE`…). The `Corrida.estado` field drives the frontend's location filter.
- **Location display in the frontend must use only values from the JSON files.** The `_buildCardLocation()` function in `app.js` enforces this: for non-BR events it validates `c.estado` against the loaded `web/locations/{pais}.json` subdivisions and uses the localized subdivision name (via `_SUBDIV_LABELS`) when the code is valid. If `estado` is empty or not in the JSON, it falls back to `c.cidade` (first comma-segment). This means:
  - A scraper that sets `estado="VE"` for an Italian event will show "Venice" (EN) / "Veneza" (PT) / "Venecia" (ES) / "Venedig" (DE) / "Venise" (FR) — automatically in all languages.
  - A scraper that sets a free-text city or wrong-country code will display the raw city name instead.
  - **Never invent subdivision codes.** Only use codes present in `web/locations/{pais}.json`. If the correct province/state isn't in the file, add it to both the JSON file and `_SUBDIV_LABELS` in `app.js`.
  - **`_SUBDIV_LABELS` in `app.js`** must be kept in sync: whenever a new country's `web/locations/{country}.json` is used and its subdivisions appear in events, add localized labels for those subdivisions. Only add an entry when the localized name differs meaningfully from the JSON file's English name (e.g. Venice → Veneza/Venecia/Venedig/Venise; DF → Brasília instead of "Distrito Federal"). Current countries with entries: MX, DE, GB, AT, ES, CA, NL, IT, JP, GR, DK, SE, IE, FR, PT, PL, CZ, NO, FI, CH, BR.
- For TF Sports specifically: many addresses end with `, SP` regardless of the actual state. The `tf_sports.py` scraper has a CEP→UF range table (`_CEP_RANGES`) that overrides a contradictory trailing UF — preserve this when modifying.

### CI workflows

- **`data-pipeline.yml`** — four times daily (00:00, 06:00, 12:00 and 18:00 UTC) + on push to `scraper/`/`web/`. Runs `scraper.main`, projects the slim web copy, and delivers the data via an **automated PR with auto-merge** (`data/scrape-*` branch; squash subject carries `[skip ci]`). Main has required status checks (ruleset), so no workflow pushes to it directly — the status/test-log commits follow the same PR flow (`ci/status-*`, `ci/test-log-*`). Requires the `AUTOMERGE_PAT` secret (PRs created with the default token don't trigger workflows).
- **`monitor-source-health.yml`** — daily 09:00 UTC + on push to `scraper/sources/`. Builds a job matrix dynamically: when shared infra (`models.py`, `utils.py`, `http_client.py`, `playwright_client.py`) changes, all sources are tested; otherwise only changed source files. Each job uploads a single-result artifact, then a final `update-readme` job aggregates all artifacts and runs `scripts/update_source_status.py` to refresh README tables and `data/source-status.json` (the source's row in README.md uses an embedded HTML comment `<!--module_name-->` for stable matching).
- **`diagnose-source.yml`** — manual trigger with a `source` input; uploads full log as artifact.
- **`verify-truth.yml`** — daily 14:30 UTC + manual. Samples ~40 future events (75% single-source first; no event resampled for 14 days), re-fetches each fonte page and compares **independently of the scraper**: schema.org Event JSON-LD (startDate / addressRegion / street "Cidade-UF") plus a BR "Cidade-UF" pattern scan. **Location divergence fails the run** (the CPTR class: page says "Pirenópolis-GO", site shows "Brasília, DF"); date divergence is a warning only (postponements are legit). State in `data/truth-check.json`, delivered via PR + auto-merge (`ci/truth-*`). This catches *wrong-but-valid* data that `tests/` (which only check validity) cannot.

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

## Failing-source circuit breaker (disable-first, then fix)

**When a source starts failing consistently, keep `main` green by splitting the
work into two PRs — one source per PR:**

1. **PR A — disable.** Comment the source out of the `SOURCES` list in
   `scraper/main.py` (and its import in `scraper/sources/__init__.py`) with a
   dated note. This is a small, safe change: the failing source stops being
   scraped, so the data-quality tests can't be poisoned by it. Validate with the
   test actions and **merge as soon as they pass** — `main` is now healthy again.
2. **PR B — fix.** On a separate branch, diagnose and repair the scraper
   (probe → understand → implement, per the sections below), re-enable the source
   (uncomment it), and **merge only when its `validate` is green**.

**One PR per source, always.** Never bundle a disable (or a fix) for two sources
into the same PR. This keeps `main` continuously deployable and makes each
rollback/diagnosis independent.

Apply this only to a **genuine, repeatable** failure — confirm it isn't a
transient blip (a single matrix flake, a seasonal lull, or an already-disabled
source like `world_athletics`) before opening the disable PR. A source that
fails once but passes on re-check does not get disabled.

## Diagnosing and dropping failing sources

**"0 eventos" alone is not sufficient evidence of WAF blocking.** A source returning zero events could be WAF, but it could equally be a scraper bug, a changed site structure, a seasonal lull with no upcoming events, or an API endpoint that moved. Never drop a source or declare it WAF-blocked based solely on a failed CI result.

The correct process before removing a source:

1. **Read the CI logs.** Trigger the "Diagnosticar Fonte" workflow (`diagnose-source.yml`) with the source name and download the full log artifact. Look for explicit HTTP error codes (403, 429, Cloudflare challenge page, WAF fingerprint in HTML), not just "0 eventos".
2. **Distinguish root causes:**
   - HTTP 403/406 on the direct request + Playwright also blocked → likely WAF. Confirm by checking whether the response body is a Cloudflare challenge page (look for `cf-ray`, `cf-mitigated`, or `Just a moment...` in the HTML).
   - Empty HTML / missing CSS selectors / JSON parse error / changed API path → scraper bug or site restructure — fix the scraper.
   - No events in the date range → not a failure; leave the source active.
3. **Only drop a source** once you have unambiguous confirmation (explicit HTTP blocks across all proxy layers, or Cloudflare challenge HTML confirmed in logs) that the block is at datacenter-IP level and no bypass exists. Document the reason in the README commit message and the source-status.json.
4. When dropping: remove the `.py` file, remove from `__init__.py`, `main.py` SOURCES list, `.github/workflows/monitor-source-health.yml` dropdown, the README table row, and `data/source-status.json`.

### Recurring failure pattern: "generic CSS selectors never matched"

Several sources have been dropped in the past with notes like *"Seletores CSS
genéricos nunca casaram com o HTML real do site"* (`bora_correr`,
`brasil_que_corre`, `portal_das_corridas`) or *"0 eventos retornados"* with
no other diagnosis. **This is almost always a scraper bug, not a blocked
site.** The old scraper template tried `article` / `.event` / `.race` /
`.post` / `.card` in order; `article` matches every WordPress post and stops
the loop before reaching the real container — but the site itself is
typically reachable and well-structured (JSON-LD, custom table, REST API,
sitemap…). Always probe the URL and inspect the real DOM before declaring
inviability. The `correr_brasilia` (JSON-LD) and `bora_correr` (custom HTML
table) revivals both followed this exact pattern.

## Exploring and validating new sources

**Never write a scraper before probing the target.** The correct flow is:
probe → understand → implement → test via CI. Skipping the probe phase leads
to scrapers that guess at field names and API paths, which wastes CI minutes
and produces false "inviable" conclusions.

### Phase 1 — Probe (before writing any code)

Use the **"Probe URL"** GitHub Actions workflow (Actions → Probe URL → Run
workflow). It runs in ~1 minute, uses the full proxy chain
(direct `httpx` request), and uploads the full response as an artifact.

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
| Single known event page | `scraper/sources/evento_unico/_base.py` |
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
- The HTTP status of the direct request (and any Playwright fallback)
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

## GOLDEN RULE: no hardcoded event data, anywhere

**Every event field — date, distance, location, time, title, image, registration
link — must be read at scrape time from the source (page content, API field, or
structured data). Nothing about a specific event may be baked into the code.**

This is the single most important data rule in the project. It outranks
convenience: a scraper that hardcodes a "known" value is wrong even when that
value is currently correct, because it will silently go stale or wrong when the
source changes, and it hides breakage (the scraper looks healthy while serving a
frozen value).

Concretely forbidden:
- `KNOWN_DATE = "2026-09-27"` style fallbacks that get emitted when live
  extraction fails;
- hardcoded distances, start times, cities/states, or finish lines for a
  specific event;
- any per-event constant that substitutes for reading the source.

Allowed (these are not event data):
- **Reference/geographic invariants**: subdivision tables in `web/locations/`,
  the persistent `data/geo_cache.json` (city→state resolution), `_CEP_RANGES`,
  ISO country lists. These describe the world, not a specific edition.
- **Classification keywords**: running/non-running regexes (`_RUNNING_KW`,
  `_NON_RUNNING_KW`). They decide *whether* to include an event, never *what its
  values are*.
- **The source URL / selectors / parse patterns** a scraper uses to reach and
  read the data.

When the source cannot be read, emit nothing for that field (or skip the event
if a required field is missing) — never substitute a stored value. A source that
returns `[]` because its page changed is the system working correctly: the
health monitor flags it and we fix the parser, instead of shipping a lie.

## Never infer event data from opaque IDs

Event information (dates, location, title) must be obtained **explicitly** from page content, API response fields, or structured data — never inferred from ID strings, URL slugs, or opaque identifiers. Platform IDs like `02605131942` in a URL are opaque: they encode nothing meaningful and must never be decoded as a date, location, or any other value. If explicit data is not available from a page or API field, leave the field empty or unset — do not guess.

## Never extract event data from the title

The event **title** (the race name) is the source for the `titulo` field and **nothing else**. Never parse the title to obtain distances, dates, location/city/state, horário, or any other field — even when the value seems to be "right there" in the name (e.g. "Corrida 5K e 10K", "Maratona de Veneza", "… Half Marathon 10K 5K"). Those values must come from a **dedicated structured field or an explicit non-title region of the page** (an API distance field, a `<distance>`/percurso block, an address/venue field, a date field, etc.).

**The information is virtually always available in another field — find it.** Every platform that publishes an event exposes its distances, date and location somewhere structured: an API attribute, a registration/convocatoria detail page, a "Percurso"/"Distâncias" block, an address field. The fix for a title-extraction shortcut is therefore almost always to **read the real field** (fetch the detail page if needed), not to drop the event. Treat skipping as a genuine last resort, used only when no structured field anywhere carries the value — never as a substitute for looking.

This is **stricter** than the opaque-ID rule above: a title is real page content, but the race name is not a reliable structured carrier of distance/location, and parsing it produces wrong data (a "Montezuma" festival held in Savannah/NY, a "Copa" race whose distances are guessed, etc.).

**Filtering by title keywords is different and still required.** Deciding *whether* an event is a running event from its name — the mandatory inclusion/exclusion regexes on general-purpose platforms (`_RUNNING_KW` / `_NON_RUNNING_KW`, see `sympla.py`/`runsignup.py`) — is allowed: that classifies the event, it does not extract a field value from the name. The ban is specifically on reading distances/dates/locations *out of* the title.

Practical patterns to remove when you see them: `_distances_from_title(titulo)`, `_parse_distances(titulo)`, `infer_estado(..., titulo)`, `_parse_location(..., titulo)`, `_infer_distances(titulo)` and similar — replace with the structured field, or `geo.resolve(city, "", pais)` for the state, or skip the event.

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


### bora_correr.py — custom HTML table, not WordPress (restored 2026-05-24)

`coelhodeprograma.com.br/boracorrer/` is a **custom (non-WordPress) DF running
calendar**. No `/wp-json/`, no RSS, no JSON-LD — but the server-rendered HTML
contains a `<table id="tabDados">` with one row per event. Each `<tr>` has
three `<td>`s: date (`DD/MM/YYYY`), `<a href="EVENT_URL">Title<br/>(distance
hints like "10/5km")</a>`, and an action cell with a UUID accessible via
`obterDadosReport('UUID', …)`.

**Why it was dropped**: the original scraper used the same generic-selector
pattern as the old `correr_brasilia.py` (`.event`, `.race`, `.card`,
`article`, `.post`, `.item`) and none of those match this custom DOM. It was
declared "broken" without checking the real structure. The site was always
reachable.

Use the UUID for stable IDs (`boracorrer_<uuid>`). Distances come from the
parenthesized hint in cell 2 — apply `_CANONICAL` snapping (21.097 / 42.195)
and 0.5km near-dedup, same as `correr_brasilia.py`.

### brasil_que_corre.py — Locaweb page builder, plain-text widgets (restored 2026-05-24)

`brasilquecorre.com/distritofederal` is a **custom site built on what looks
like a Locaweb page builder** (CSS prefix `cs-`). No `/wp-json/`, no RSS,
no JSON-LD. Each event is a `<div class="cs-text-widget">` whose innerText
follows a fixed layout:

  `TITLE  &nbsp;  DD[ e DD] de MES de YYYY  CITY [/ UF]  Xkm, Ykm (corrida) ORGANIZER`

Example: `ONERUN SUNSET   23 de Maio de 2026 Brasília / DF 1km, 5km, 10km e 21km (corrida) ONE23 GO`

**Why it was dropped**: same generic-selector pattern as `correr_brasilia` /
`bora_correr` — `.event/article/.race/.post` never matched `cs-text-widget`.
The site is reachable and well-structured.

Parser splits on the first `DD de MES de YYYY` match: everything before is
the title, the date populates `data_evento`, distances are extracted from
`(corrida)`-annotated segments only (filtering out walking/kids/OCR sections).
Use the widget `id` attribute (a UUID assigned by the page builder) for
stable IDs (`bqc_<uuid>`). Each event links back to the listing page since
no per-event URL exists.

### portal_das_corridas.py — Wix Events site (restored 2026-05-24)

`portaldascorridas.com.br` is a **Wix.com Website Builder** site that doubles
as a Brazilian race registration platform — Wix Events manages the inscriptions
("O Portal das Corridas não é responsável pela organização do evento. Apenas
gerenciamos o processo de inscrição online."). The old scraper used Playwright
with generic CSS selectors that never matched the Wix DOM — same false-positive
"broken" pattern as bora_correr / brasil_que_corre.

Architecture:
- **Discovery**: `event-pages-sitemap.xml` (Wix-generated) lists every event
  detail page with a `<lastmod>` date — ~570 entries spanning multiple years.
- **Detail pages**: each `/event-details/<slug>` is a Wix SPA with all event
  data embedded in the server-rendered HTML — no public REST API needed.

Extraction sources per page (use in this priority order):
1. **JSON-LD `@type: "Event"`** block — single `<script type="application/ld+json">`
   element with `name`, `startDate` (already in local TZ — race date), `image.url`.
2. **Wix `fullAddress` blob** — richer than the JSON-LD freeform `location.address`;
   gives `country` (ISO-2), `subdivision` (state code), `city`.
3. **`"label":"Percurso","options":[...]` block** — the registration form's
   distance field. Source of truth for distances; the page's free-text prose
   sometimes contradicts it. Only numeric `Xkm` options become `Distancia.km`
   (drop `KIDS` / `CAMINHADA` etc.).
4. **`"eventId":"<uuid>"`** for the stable ID (`portaldc_<uuid>`).

Cost discipline: the sitemap has ~570 events but many are years old. The
scraper filters by `lastmod >= today - 270 days` and caps the per-run fetch
list at 120 entries to keep proxy budget bounded. The pipeline's date filter
then drops any past events that slipped through the lastmod window.

### corridas_br — DO NOT REACTIVATE

`corridasbr.com.br/df/calendario.asp` is **permanently dropped, not because
of WAF or scraper bugs**. The site itself is a low-quality directory whose
event data is **frequently wrong** (wrong dates, wrong distances, wrong
links) and never carries real registration URLs — every "register" link
just redirects to other aggregators we already scrape directly. Even if it
starts returning 200 again, do not re-add it. The user explicitly forbids
reactivation.


## Autonomy: CI and iteration

Claude must run tests and iterate **independently**, without asking the user to trigger GitHub Actions workflows. Push changes to the feature branch and let CI validate them autonomously. To probe a URL, push a `probe-config.json` to the `probe` branch and poll `probe-output/result.md` for results. To test a source, push the scraper change and monitor the `Monitorar Saúde das Fontes` workflow. To run the full pipeline, push to `scraper/` and let `data-pipeline.yml` run. **Never ask the user to manually run "Sondar URL", "Monitorar Saúde das Fontes", or "Diagnosticar Fonte"** — trigger them by pushing the appropriate changes and monitoring the outcome via `mcp__github__*` tools.

## PR workflow

Every code change must go through a PR before merging into main.

**Each PR must treat exactly one subject.** A PR that adds a new scraper must not also fix another scraper. A PR that fixes location errors must not also add a test. When in doubt: one task, one PR. This makes CI failures easier to diagnose and rollbacks safer.

**Every branch gets a draft PR the moment it exists.** Open the draft PR as soon as the branch is created (before, or immediately after, the first commit) — never develop on a branch that has no PR. This lets any other agent pick the work up at any time, even if this session abandons it mid-way. The **only** exception is a purely throwaway branch (a diagnostic probe, a spike) that will *never* be eligible to merge — those need no PR.

**The draft PR body is a hand-off document.** Write it so a fresh agent could finish the work without context. It must state, in plain terms:
- **Objective** — what the change is and why.
- **Definition of done** — the concrete end state (what must be true to call it finished).
- **Merge requirements** — exactly what must pass/hold before it can merge (CI green, specific behaviour verified via `/verify`, etc.).

**Prefer GitHub native auto-merge over a manual merge.** When you mark a PR ready, also enable auto-merge so the PR lands itself the instant its required checks pass — even if this session ends first. Do **not** sit polling and then merge by hand; that's why PRs stopped auto-merging. The repo has auto-merge enabled (the data/CI bot PRs depend on it), so a PR only fails to auto-merge if you forgot to enable it.

1. **Create a feature branch** (descriptive name) and **immediately open a draft PR** (`mcp__github__create_pull_request`, `draft: true`) carrying the objective / definition-of-done / merge-requirements body above. CI does not run on draft PRs.
2. **Develop freely** — push commits without CI interference; keep the PR body current as the plan firms up.
3. **Mark ready** (`mcp__github__update_pull_request`, `draft: false`) — this triggers CI — **and enable auto-merge** (`mcp__github__enable_pr_auto_merge`, `mergeMethod: SQUASH`) in the same step. For UI changes, run `/verify` before marking ready.
4. **Let it land.** Watch via `subscribe_pr_activity`; if a required check **fails**, diagnose, fix, and push — auto-merge re-arms and fires when green. Only fall back to a manual `mcp__github__merge_pull_request` if auto-merge is unavailable for that PR.
5. **Scrape triggers automatically** on merge via `data-pipeline.yml` (`pull_request: types: [closed]` + merged guard).

**A PR may only be merged when ALL CI test actions pass.** This is a hard requirement — auto-merge enforces it; never bypass it with a manual merge over pending/failing checks.

### Every PR must reach a conclusion

**No PR may be left open indefinitely.** Every PR ends in one of two states:

1. **Merged** — CI is green and the change is accepted into `main`.
2. **Closed (without merge)** — the change is abandoned, superseded, or no longer needed. Always leave a closing comment explaining why (e.g. "superseded by #N", "approach changed, see #M", "no longer needed because …").

Open PRs without an active task driving them are a maintenance debt: they accumulate merge conflicts, confuse reviewers, and obscure what's actually in flight. When picking up work, audit any open PRs you (or a previous session) authored:

- If still relevant → finish the work, get CI green, merge.
- If superseded or abandoned → close with a one-line explanation.
- If blocked on external input → leave a comment with the blocker and check back; close it if the blocker can't be resolved.

When you create a new PR, you own driving it to a conclusion within the same session whenever possible. Do not open a PR and walk away from it.

### Audit open PRs at session start

**At the start of every session (or whenever resuming work), list all open PRs with `mcp__github__list_pull_requests` and triage each one before starting new work:**

- Check CI status (`get_check_runs`) for any PR that is non-draft and not yet merged.
- If all checks pass → merge immediately, do not let it sit.
- If checks are failing → diagnose and fix before opening new PRs.
- If the PR is stale (no recent activity, superseded, or the branch has diverged badly) → close it with a comment explaining why.

A PR left unchecked across sessions accumulates merge conflicts, blocks the data pipeline from getting fixes, and wastes CI minutes on every subsequent push. **Never open a new session's first PR without first clearing the backlog.**

### CI polling loop — never leave a ready PR unmerged

**When waiting for CI checks on any PR, poll `mcp__github__pull_request_read` with `method=get_check_runs` continuously (no sleep between calls) until all checks reach a terminal state (`conclusion: success` or `conclusion: failure`):**

1. **All `conclusion: success`** → merge immediately via `mcp__github__merge_pull_request`. Do not wait for user confirmation.
2. **Any `conclusion: failure`** → diagnose the failure, fix the code, push a new commit, and continue polling from the new head commit.
3. **`status: in_progress` / `status: queued`** → poll again.

After every PR merges into main, check if the main CI passes by looking at the most recent commit's check runs on main. If tests fail on main, open a new PR to fix them and apply the same loop.

**The loop must continue until `main` has 100% green CI.** Do not stop between PRs — clear the entire queue, then verify main is green.

## Event data quality requirements

These are hard requirements enforced by `tests/test_site.py::test_all_events_have_required_fields` and `scraper/test_source.py`. All tests use **zero tolerance — no thresholds**. A single failing event fails the test.

### Required fields per event

Every event in `data/corridas.json` (and `web/corridas.json`) must satisfy **all** of the following simultaneously:

1. **`localizacao`** — non-empty string (city + state, or at least city).
2. **`pais`** — a valid ISO-3166-1 alpha-2 code that exists as a file in `web/locations/{pais}.json`.
3. **`estado`** — a valid subdivision code that exists in `web/locations/{pais}.json`'s `subdivisions` list. Must be non-empty. If the subdivision cannot be determined, the event must not be stored until it can be resolved.
4. **`pais` + `estado` are displayed in the same language** (the frontend localizes both via `_localizeCountryByIso2` and `_localizeSubdiv`). This means both must be resolvable in all 5 UI locales.
5. **`distancias`** — non-empty list of `Distancia` objects.
6. **`data_evento`** — non-empty date string (`YYYY-MM-DD`).
7. **At least one valid link** — at least one `FonteInfo` in `fontes` must have a non-empty `link_evento` or `links_inscricao[0]`.
8. **`FonteInfo.tipo`** — every `FonteInfo` must have a valid `tipo` value (`"inscricao"`, `"organizador"`, or `"calendario"`). Missing or invalid `tipo` is a hard test failure.

`horario` is not required (many events don't announce start time in advance).

### Location fix policy

- **Never add or modify `web/locations/*.json` files to make a test pass.** The location JSON files are reference data, not scraper output. The correct fix is always to improve the scraper and/or `data/geo_cache.json`.
- **Only `data/geo_cache.json` can be updated** as a location fix (alongside scraper improvements).
- When `geo.resolve()` returns a wrong country or empty estado, fix the cache by adding a country-qualified entry: `"{city_query}||{pais.lower()}"` → `{"pais": ..., "estado": ...}`.
- If an event's state genuinely cannot be determined from available data, the event should be **excluded** from the scraper's output (not stored with empty estado).
- **Never use thresholds** — even 1 event with invalid location is a failing test.

### Failing-test response policy

**A failing data-quality test must never be "fixed" by removing the offending events from `corridas.json`.** The correct response is always to fix the scraper so it stops producing invalid output. Concretely:

- **Direct edits to `corridas.json` / `web/corridas.json` to drop events are forbidden as a test-fix.** The next scrape will regenerate the file from scraper output anyway, so dropping events from the JSON only masks the bug for one cycle.
- **Fix at the source.** If a scraper emits events with missing required fields, the scraper itself must either (a) extract the missing data from a deeper page fetch, (b) enrich via `geo.resolve()` / cache, or (c) refuse to emit the event at all (`require_location=True`-style upfront skip). Option (c) is itself a scraper fix — it prevents the invalid event from ever entering the data — and is acceptable when no deeper data source exists.
- **Adding missing reference data is allowed only for true gaps**, not as a band-aid. Example: a real ISO-3166-1 country with valid subdivisions that genuinely was never added to `web/locations/` is a reference-data gap, not a test-fix. Even so, prefer fixing the scraper to map the event to an existing country when possible.
- **Always investigate before dropping.** Probe the event's source page (via the Probe URL workflow) to confirm whether the missing data actually exists somewhere fetchable. Only after confirming no fetchable data exists may the scraper skip the event upfront.

### Source test requirements

`scraper/test_source.py` validates each source in isolation. In addition to the existing checks:
- Events with no `distancias` are flagged as info (>30% is a warning, >70% is a failure).
- Events with no link in `fontes` are a **hard failure**.
- Missing `horario` is reported informally (informational only, not a failure).

### Data correction on next scrape

The reconcile pipeline (`main.py`) is designed so that:
- `_update_from()` always clears `estado` when the incoming scrape returns empty, allowing `_resolve_missing_locations()` to retry.
- `_resolve_missing_locations()` fills in empty `estado` (and fixes `INT`/`??` values) via `geo.resolve()` with the persistent geo cache.
- Therefore: fixing the geo cache + scraper is sufficient; the next CI scrape will propagate correct values to `corridas.json`.
