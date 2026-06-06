# Distance-extraction audit — the shared-suffix bug class

_Audited 2026-06-04. Scope: every scraper under `scraper/sources/`._

## The bug

Distance lists in Portuguese/Spanish prose carry a **single shared `km`
suffix**: in `"3, 5 e 10 km"` only the `10` is adjacent to the unit token. A
naive per-number regex (`\b(\d+)\s*km\b`) therefore captures **only the last
value** and silently drops `3` and `5`, producing **incomplete distances**.
The same class also covers:

- Spanish lists with the `y` connector (`"5, 10 y 21 km"`) and English `and`.
- Slash/pipe/semicolon lists (`"5 / 10 / 21 km"`).
- **Phantom marathons**: inferring `maratona`/`marathon` from loose prose
  ("a maior maratona de rua do DF") when the event offers no 42 km.
- Capturing non-distance numbers (years, prices, ages, times).

This was fixed ad-hoc in `correr_brasilia` (PR #196) and `central_da_corrida`
(PR #198) before this audit generalised the fix.

## The fix — one shared helper

`scraper/utils.py::extract_distances_from_text()` is the single source of truth,
ported from the gold-standard `correr_brasilia._extract_distances`:

```python
extract_distances_from_text(text, *, min_km=3.0, max_km=200.0,
                            allow_named=True, named_in_prose=False,
                            title="", max_results=8) -> list[float]
```

Resolution order (first non-empty wins): explicit token lists → shared-km-suffix
lists → labelled value → prose-safe numeric scan → parenthetical title list. It
canonical-snaps 21→21.097 / 42→42.195 and near-dedups within 0.5 km. Connectors
cover pt (`e`/`ou`), es (`y`) and en (`and`). Named distances count **only as
enumeration tokens** unless `named_in_prose=True` is passed (use only for short,
reliable title strings) — this is what prevents phantom marathons.

Unit tests live inline in the helper's development and cover every failing input
listed below.

## Per-source disposition

| Source | Distance origin | Before | Action taken |
|---|---|---|---|
| `correr_brasilia` | JSON-LD prose | reference impl | gold standard — unchanged |
| `central_da_corrida` | regulamento prose | own list parser, **no shared-suffix** | fixed in #198 (own shared-suffix parser; not the shared helper) |
| `iguana_sports` | card/detail prose | naive per-number | **routed through helper** (`min_km=3`) |
| `mks_esportes` | title + prose | naive per-number + named blocks | numeric scan → helper (`allow_named=False`); named blocks kept |
| `sesc_df` | page prose | naive per-number | **routed through helper** (`min_km=1`) |
| `poupex` | page prose | naive per-number | **routed through helper** (`min_km=1`) |
| `minhas_inscricoes` | page prose | naive per-number | **routed through helper** (`min_km=1, max_km=250`) |
| `yescom` | headings + text | naive per-number, integer-only | **routed through helper** (`min_km=1, max_km=60`); integer-only filter kept |
| `carreras_mexico` | título (es) | naive per-number, **no `y`** | **routed through helper**; also fixed a fallback bug that mislabelled "medio maratón" (es) as a full marathon |
| `asdeporte` | título + prose (es) | `_DIST_RE` per-number, **no `y`**, has miles | helper for km/named; miles path kept |
| `ticket_sports` | título + detail prose | naive per-number (fallback only) | fallback routed through helper |
| `largada_esportiva` | structured + text fallback | structured safe; fallback naive | fallback routed through helper |
| `bora_correr` | `(5/10km)` hint | handles `/`, two-item `e` | superseded by helper's `/`+list handling |
| `corridas_brasil` | table cell | partial | **not modified** (reactivation forbidden by project policy) |
| `atletis`, `ativo`, `brasil_corrida`, `tf_sports`, `tf_sports_app`, `portal_das_corridas`, `halfmarathons` | structured fields (primary) | safe primary, naive fallback | primary path safe; fallbacks low-impact, hardened where touched |
| `runner_brasil` | `Percurso: 5 / 10 / 21 km` | splits on all `\d+` | already safe |
| `runsignup`, `raceroster`, `circuito_das_estacoes`, `asdeporte`(structured) | structured per-distance | one token each | safe — no change |
| `sp_city_marathon`, `maratona_rio`, `maratona_porto_alegre`, all `evento_unico/*` | hardcoded constants | n/a | safe — no change |
| `volta_do_lago` | prose | naive per-number | source being disabled |
| `world_athletics` | título | naive per-number | source disabled |

## Notes

- The per-source `_CANONICAL = [(42.195, …), (21.097, …)]` constant is now
  duplicated across ~15 files; the shared helper owns the canonical logic
  (`utils._CANONICAL_KM`). Sources routed through the helper no longer reference
  their local copy — left in place to keep diffs minimal; a future cleanup can
  remove the dead constants.
- Structured-API sources (Ticket Sports schedule, RunSignup sub-events, Race
  Roster `distances[]`) parse one distance per array element and are immune to
  the shared-suffix bug by construction.
