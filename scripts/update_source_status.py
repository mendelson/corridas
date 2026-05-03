#!/usr/bin/env python3
"""
Update README.md source tables with CI test results.

Usage:
    python scripts/update_source_status.py <results_dir>

Each *.json file in <results_dir> must contain:
    {"source": "<module_path>", "status": "ok|fail", "tested_at": "<ISO timestamp>"}

Persistent state lives in data/source-status.json.
The README is updated in-place: status columns are added on the first run and
refreshed on every subsequent run. The source module name is embedded as an
HTML comment in the first cell of each row so future runs can match reliably
even if display names change.
"""
from __future__ import annotations
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

README = Path("README.md")
STATUS_JSON = Path("data/source-status.json")

# Module path → display name as it appears in the README first column
_MODULE_TO_NAME: dict[str, str] = {
    # Brazilian calendar sources
    "ticket_sports":         "Ticket Sports",
    "circuito_das_estacoes": "Circuito das Estações",
    "central_da_corrida":    "Central da Corrida",
    "tf_sports":             "TF Sports",
    "yescom":                "Yescom",
    "brasil_corrida":        "Brasil Corrida",
    "iguana_sports":         "Iguana Sports",
    "ativo":                 "Ativo",
    "mks_esportes":          "MKS Esportes",
    "corridas_brasil":       "Corridas Brasil",
    "minhas_inscricoes":     "Minhas Inscrições",
    "runner_brasil":         "Runner Brasil",
    "portal_das_corridas":   "Portal das Corridas",
    "godream":               "GoDream",
    # DF-specific sources
    "brasil_que_corre":      "Brasil que Corre",
    "correr_brasilia":       "Correr Brasília",
    "sesc_df":               "SESC DF",
    # BR single-event sources
    "maratona_rio":          "Maratona do Rio",
    "maratona_porto_alegre": "Maratona de Porto Alegre",
    "sp_city_marathon":      "SP City Marathon",
    "sao_silvestre":         "São Silvestre",
    "volta_do_lago":         "Volta do Lago",
    # WAF/blocked sources
    "liverun":               "Live Run",
    "lets_do_this":          "Let's Do This",
    "world_marathons":       "World Marathons",
    "corridas_br":           "Corridas BR",
    "bora_correr":           "Bora Correr",
    # International
    "majors/cardiff_half":   "Cardiff Half Marathon",
    # World Marathon Majors
    "majors/tokyo":          "Tokyo Marathon",
    "majors/boston":         "Boston Marathon",
    "majors/brighton":       "Brighton Marathon",
    "majors/paris":          "Paris Marathon",
    "majors/london":         "TCS London Marathon",
    "majors/prague":         "Prague Marathon",
    "majors/copenhagen":     "Copenhagen Marathon",
    "majors/edinburgh":      "Edinburgh Marathon Festival",
    "majors/stockholm":      "Stockholm Marathon",
    "majors/manchester":     "Manchester Marathon",
    "majors/sydney":         "TCS Sydney Marathon",
    "majors/great_north_run": "Great North Run",
    "majors/berlin":         "BMW Berlin Marathon",
    "majors/manchester_half": "Manchester Half Marathon",
    "majors/chicago":        "Bank of America Chicago Marathon",
    "majors/amsterdam":      "Amsterdam Marathon",
    "majors/venice":         "Venice Marathon",
    "majors/dublin":         "Dublin City Marathon",
    "majors/nyc":            "TCS New York City Marathon",
    "majors/athens":         "Athens Classic Marathon",
    "majors/valencia":       "Valencia Marathon",
}

_NAME_TO_MODULE: dict[str, str] = {v: k for k, v in _MODULE_TO_NAME.items()}

_STATUS_HEADERS = ("Testado em", "Status", "Últ. sucesso")
_COMMENT_RE = re.compile(r"<!--([a-z_/]+)-->")


# ---------------------------------------------------------------------------
# Status JSON helpers
# ---------------------------------------------------------------------------

def _load_status() -> dict:
    if STATUS_JSON.exists():
        try:
            return json.loads(STATUS_JSON.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_status(status: dict) -> None:
    STATUS_JSON.parent.mkdir(exist_ok=True)
    STATUS_JSON.write_text(
        json.dumps(status, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _apply_results(status: dict, results_dir: Path) -> dict:
    for f in sorted(results_dir.glob("*.json")):
        try:
            r = json.loads(f.read_text(encoding="utf-8"))
            source = r["source"]
            tested_at = r["tested_at"]
            ok = r.get("status") == "ok"
            prev = status.get(source, {})
            status[source] = {
                "tested_at": tested_at,
                "status": "ok" if ok else "fail",
                "last_success": tested_at if ok else prev.get("last_success"),
            }
        except Exception as e:
            print(f"  Warning: skipping {f.name}: {e}", file=sys.stderr)
    return status


def _fmt(ts: str | None) -> str:
    if not ts:
        return "—"
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return ts[:16]


# ---------------------------------------------------------------------------
# Markdown table helpers
# ---------------------------------------------------------------------------

def _split_cells(line: str) -> list[str]:
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return s.split("|")


def _is_sep(cells: list[str]) -> bool:
    """True if this row is a Markdown table separator (e.g. |---|---|)."""
    return bool(cells) and all(
        re.fullmatch(r"\s*:?-+:?\s*", c) for c in cells
    )


def _module_of(cell: str) -> str | None:
    """Extract module name from an embedded HTML comment, or look up by display name."""
    m = _COMMENT_RE.search(cell)
    if m:
        return m.group(1)
    return _NAME_TO_MODULE.get(cell.strip())


def _rebuild(cells: list[str]) -> str:
    return "| " + " | ".join(c.strip() for c in cells) + " |\n"


# ---------------------------------------------------------------------------
# Table processing
# ---------------------------------------------------------------------------

def _process_table(rows: list[str], status: dict) -> list[str]:
    """Add (first run) or refresh (subsequent runs) status columns in one table."""
    if len(rows) < 3:
        return rows

    header_cells = _split_cells(rows[0])
    has_cols = any(h.strip() in _STATUS_HEADERS for h in header_cells)

    # Only touch tables that contain at least one known source row
    has_src = any(
        _module_of(_split_cells(r)[0])
        for r in rows[2:]          # skip header + separator
        if _split_cells(r)
    )
    if not has_src:
        return rows

    out: list[str] = []
    for idx, row in enumerate(rows):
        cells = _split_cells(row)

        if idx == 0:  # header row
            if not has_cols:
                cells += list(_STATUS_HEADERS)
            out.append(_rebuild(cells))

        elif _is_sep(cells):  # separator row
            if not has_cols:
                cells += ["---", "---", "---"]
            out.append(_rebuild(cells))

        else:  # data row
            if not cells:
                out.append(row)
                continue

            module = _module_of(cells[0])

            # Embed module name as invisible HTML comment for future matching
            if module and "<!--" not in cells[0]:
                cells[0] = cells[0].strip() + f"<!--{module}-->"

            if has_cols:
                # Only update if we have fresh data for this source
                if module and module in status:
                    s = status[module]
                    cells[-3] = _fmt(s.get("tested_at"))
                    cells[-2] = "✅" if s.get("status") == "ok" else "❌"
                    cells[-1] = _fmt(s.get("last_success"))
                # else: preserve whatever is already in cells[-3:-1]
            else:
                # First run: append new cells
                if module and module in status:
                    s = status[module]
                    cells += [_fmt(s.get("tested_at")),
                               "✅" if s.get("status") == "ok" else "❌",
                               _fmt(s.get("last_success"))]
                else:
                    cells += ["—", "—", "—"]

            out.append(_rebuild(cells))

    return out


def update_readme(status: dict) -> None:
    text = README.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)

    out: list[str] = []
    i = 0
    while i < len(lines):
        if not lines[i].strip().startswith("|"):
            out.append(lines[i])
            i += 1
            continue

        # Collect all contiguous table lines
        j = i
        while j < len(lines) and lines[j].strip().startswith("|"):
            j += 1

        processed = _process_table(lines[i:j], status)
        out.extend(processed)
        i = j

    README.write_text("".join(out), encoding="utf-8")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: update_source_status.py <results_dir>", file=sys.stderr)
        sys.exit(1)

    results_dir = Path(sys.argv[1])
    if not results_dir.is_dir():
        print(f"Error: {results_dir} is not a directory", file=sys.stderr)
        sys.exit(1)

    status = _load_status()
    status = _apply_results(status, results_dir)
    _save_status(status)
    update_readme(status)
    print(f"Done. Status tracked for {len(status)} source(s).")


if __name__ == "__main__":
    main()
