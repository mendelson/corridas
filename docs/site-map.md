# Site map & routes — run.mmendelson.com

Reference for every public path the site serves, how routing works, and which
files back each route. The frontend is a static, no-build SPA (plain HTML/CSS/JS)
generated under `web/` and deployed as-is.

## Hosting

- **Custom domain:** `https://run.mmendelson.com`
- **Platform:** Cloudflare Pages (build output = the `web/` directory).
- **Origin/mirrors:** `corridas.pages.dev` (production alias) and
  `*.corridas.pages.dev` (per-deploy previews). Both mirrors are kept out of
  search indexes via `web/_headers` (`X-Robots-Tag: noindex`) so only the custom
  domain ranks.
- Cloudflare-Pages-specific files live at the web root: `web/_headers`
  (response headers) and `web/_redirects` (301 rules).

## Routes

| Path | Backing file | Indexed | Purpose |
|---|---|---|---|
| `/` | `web/index.html` | x-default | Language splash: client-side redirect to a `/{lang}` shell based on `navigator.languages`. |
| `/{lang}`, `/{lang}/` | `web/{lang}/index.html` | ✅ | App shell, one per UI language — 28 of them (table below). |
| `/gallery` | `web/gallery/index.html` | ✅ | Personal activities timeline. Not linked from the app — reached directly; listed in the sitemap. Localized in all 28 languages **without** a per-language URL. |
| `/favorites`, `/favorites/*` | — (301) | — | Legacy → redirects to `/gallery`. |
| `/highlights`, `/highlights/*` | — (301) | — | Legacy → redirects to `/gallery`. |

### UI languages

The site ships the 28 locales of the Connect IQ Store listings — the same set
as apps.mmendelson.com. `scripts/generate_sitemap.py` `LANGS` is the single
list (URL prefix → hreflang) that the shells, sitemap, pre-render and tests read.

| Prefix | hreflang | Prefix | hreflang | Prefix | hreflang | Prefix | hreflang |
|---|---|---|---|---|---|---|---|
| `pt` | pt-BR | `en` | en | `es` | es | `de` | de |
| `fr` | fr | `it` | it | `nl` | nl | `pt-pt` | pt-PT |
| `ru` | ru | `pl` | pl | `cs` | cs | `sk` | sk |
| `sl` | sl | `hr` | hr | `hu` | hu | `el` | el |
| `da` | da | `nb` | nb | `sv` | sv | `fi` | fi |
| `ja` | ja | `ko` | ko | `zh-cn` | zh-CN | `zh-tw` | zh-TW |
| `th` | th | `he` | he (`dir="rtl"`) | `id` | id | `ms` | ms |

The Store's own codes differ for four of them: `pt_BR`→`/pt/`, `iw`→`/he/`,
`in`→`/id/`, `zh_CN`/`zh_TW`→`/zh-cn/`/`/zh-tw/`.

### Root redirect (`/`)

`web/index.html` walks `navigator.languages` and `window.location.replace()`s
to the first supported shell, anything else→`/en`. Regional variants are told
apart by subtag (`pt-PT`/`pt-AO`…→`/pt-pt`, `zh-TW`/`zh-HK`/`zh-Hant`→`/zh-tw`)
and the aliases `iw`, `in`, `no`/`nn` fold into `he`, `id`, `nb` — the same
mapping as `_langFromTag` in `app.js`. It also declares `hreflang` alternates
for all 28 languages plus `x-default`. It is generated with the shells.

### Language shells (`/{lang}/`)

Each `web/{lang}/index.html` is **generated** by `scripts/generate_shells.py`
from `scripts/templates/shell.html` — UI text comes from `STRINGS` in `app.js`,
crawler-only copy (description, footer intro) from the generator's `SEO` table.
Never hand-edit a shell; edit the template/strings and regenerate
(`--check` reports stale shells). Each one is the full application: a server-side
**pre-rendered** event list + `application/ld+json` structured data (regenerated
by `scripts/generate_prerender.py` so titles/JSON-LD match the latest data),
plus the inline `<template id="cardTemplate">`. They all load the same
`web/app.js` and `web/style.css`.

- **The language is determined purely by the URL path prefix** (`app.js` reads
  `window.location.pathname`). There are no other routes.
- **Filtering is client-side only.** State/distance/source filters do **not**
  change the URL (no query string, no hash). Selections persist in
  `localStorage['corridas_filters']`; detected geo is carried across language
  switches via `sessionStorage`. So there are no per-filter or per-event URLs to
  index — the 28 language roots are the only indexable pages.
- **PWA:** `web/manifest.json` ("Mendi Corre") + `web/service-worker.js`.

### Gallery (`/gallery`)

Personal page — not linked from the app (reached directly), but indexed and
listed in `sitemap.xml`. A horizontal chronological timeline; each event
shows its localized date, a distance badge, and brand-logo buttons (Strava,
Garmin, Polar) linking to the external activity. It localizes in all 28 UI
languages from `navigator.languages` **on the same `/gallery` URL** (no path
prefix).
Asset: `web/gallery/polar-logo.png`.

**Its current colors are final by owner preference — do not restyle the
gallery's palette.**

## Static data & assets (web root)

| File | Purpose |
|---|---|
| `web/corridas.json` | Slim projection of the event data consumed by `app.js`. |
| `web/corridas-boot.json` | Smaller "boot" shard for fast first paint. |
| `web/locations/{iso2}.json` | Country → subdivisions reference data (states/provinces), shared by the frontend and the scraper. |
| `web/sitemap.xml` | Lists the 28 `/{lang}/` roots + `/gallery/` (regenerated by `scripts/generate_sitemap.py`). |
| `web/robots.txt` | `Allow: /`, points at the sitemap. |
| `web/_headers` | `noindex` for `*.pages.dev` mirrors. |
| `web/_redirects` | 301s from `/favorites*`, `/highlights*` and the localized words for "gallery" to `/gallery`. |
| `web/app.js` | The whole frontend (~1800 lines): strings table, state, filters, rendering. |
| `web/style.css` | Styles for the app shells. |
| `web/manifest.json`, `web/service-worker.js` | PWA manifest + offline service worker. |
| `web/shoe-favicon.svg` | Primary favicon: the shoe mascot with a slow wear-marks animation (generated by `scripts/gen-shoe-favicon.js` from `web/gallery/shoe-wear.js` — never edit by hand). Chromium/Firefox animate it; Safari falls back to the static clean frame or the raster icons below. |
| `web/favicon.ico`, `web/logomendi-favicon.png` | Raster fallback icons (declared after the SVG). |
| `web/og-{lang}.png` | Per-language Open Graph share images, one per UI language (rendered by `scripts/generate_og_images.py`). |

## How the data behind the pages is produced

The event data (`web/corridas.json` / `web/corridas-boot.json`) and the
pre-rendered shells are generated by the scraper pipeline (`scraper/main.py`)
and committed by the `data-pipeline` GitHub Actions workflow (runs 4×/day and on
pushes to `scraper/`/`web/`). See `CLAUDE.md` for the pipeline architecture.

## SEO summary

- The five `/{lang}/` roots (reciprocal `hreflang` alternates) and `/gallery/`
  are indexable and listed in `sitemap.xml`.
- The `*.pages.dev` mirrors are explicitly de-indexed.
- There is no dynamic/parameterized URL surface to crawl — filters are in-memory.
