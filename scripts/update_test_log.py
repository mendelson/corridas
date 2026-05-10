"""
update_test_log.py — append a test-run entry to data/site-test-log.json.

Usage:
    python scripts/update_test_log.py <path-to-pytest-json-report.json>

Retention policy:
  - Always keeps the last 30 runs (rolling window).
  - Within those, always preserves the last 5 fully-clean runs (failed == 0).
    If the 30-run window already contains ≥5 clean runs, no extra action needed.
    If it contains fewer, the oldest clean runs beyond the window are preserved
    until the 5-clean quota is met.
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

MAX_RUNS   = 30   # rolling window of recent runs
MAX_CLEAN  = 5    # minimum clean (all-passed) runs to always preserve
LOG_FILE   = Path(__file__).parent.parent / "data" / "site-test-log.json"


def _git_info():
    commit = os.environ.get("GITHUB_SHA") or os.environ.get("GIT_COMMIT", "")
    branch = os.environ.get("GITHUB_REF_NAME", "")

    if not commit:
        try:
            commit = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], text=True
            ).strip()
        except Exception:
            commit = "unknown"

    if not branch:
        try:
            branch = subprocess.check_output(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"], text=True
            ).strip()
        except Exception:
            branch = "unknown"

    # Short commit SHA for display
    short = commit[:8] if commit != "unknown" else "unknown"
    return commit, short, branch


def _parse_report(report_path: Path) -> dict:
    with open(report_path, encoding="utf-8") as f:
        report = json.load(f)

    summary    = report.get("summary", {})
    passed     = summary.get("passed",  0)
    failed     = summary.get("failed",  0)
    skipped    = summary.get("skipped", 0)
    total      = summary.get("total",   passed + failed + skipped)
    duration_s = report.get("duration", 0.0)

    results = []
    for test in report.get("tests", []):
        outcome = test.get("outcome", "unknown")
        nodeid  = test.get("nodeid", "")
        func    = nodeid.split("::")[-1] if "::" in nodeid else nodeid

        # Prefer the human-readable docstring injected via user_properties
        name = next(
            (v for k, v in test.get("user_properties", []) if k == "description"),
            None,
        )
        if not name:
            # Fall back to cleaned function name: test_foo_bar → "foo bar"
            name = func[5:].replace("_", " ") if func.startswith("test_") else func

        call    = test.get("call", {})
        duration_ms = round((call.get("duration", 0.0)) * 1000, 1)
        message = ""
        if outcome == "failed":
            longrepr = call.get("longrepr", "")
            if isinstance(longrepr, str):
                lines = longrepr.strip().splitlines()
                message = "\n".join(lines[-5:]) if lines else longrepr
            elif isinstance(longrepr, list):
                message = "\n".join(str(x) for x in longrepr[-5:])
        results.append({
            "name":        name,
            "status":      outcome,
            "duration_ms": duration_ms,
            "message":     message or None,
        })

    return {
        "passed":     passed,
        "failed":     failed,
        "skipped":    skipped,
        "total":      total,
        "clean":      failed == 0,
        "duration_s": round(duration_s, 2),
        "results":    results,
    }


def _trim(runs: list) -> list:
    """Apply retention policy: last 30 runs + at least 5 clean runs."""
    # Start with the most recent MAX_RUNS
    recent = runs[-MAX_RUNS:]

    # Count clean runs already in the window
    clean_in_window = sum(1 for r in recent if r.get("clean"))
    if clean_in_window >= MAX_CLEAN:
        return recent

    # Need more clean runs — scan older entries (newest-first)
    older = runs[:-MAX_RUNS] if len(runs) > MAX_RUNS else []
    extra_clean = []
    for r in reversed(older):
        if r.get("clean"):
            extra_clean.append(r)
            if clean_in_window + len(extra_clean) >= MAX_CLEAN:
                break

    # Restore chronological order and prepend to window
    extra_clean.reverse()
    return extra_clean + recent


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/update_test_log.py <report.json>", file=sys.stderr)
        sys.exit(1)

    report_path = Path(sys.argv[1])
    if not report_path.exists():
        print(f"Report file not found: {report_path}", file=sys.stderr)
        sys.exit(1)

    # Read existing log
    if LOG_FILE.exists():
        try:
            with open(LOG_FILE, encoding="utf-8") as f:
                runs = json.load(f)
            if not isinstance(runs, list):
                runs = []
        except Exception:
            runs = []
    else:
        runs = []

    commit, short, branch = _git_info()
    parsed = _parse_report(report_path)

    entry = {
        "timestamp":    datetime.now(tz=timezone.utc).isoformat(),
        "commit":       commit,
        "commit_short": short,
        "branch":       branch,
        **parsed,
    }

    runs.append(entry)
    runs = _trim(runs)

    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(runs, f, indent=2, ensure_ascii=False)

    clean_count = sum(1 for r in runs if r.get("clean"))
    print(
        f"Logged run [{short}]: passed={entry['passed']} failed={entry['failed']} "
        f"skipped={entry['skipped']} total={entry['total']} "
        f"duration={entry['duration_s']}s | "
        f"log has {len(runs)} runs ({clean_count} clean) → {LOG_FILE}"
    )


if __name__ == "__main__":
    main()
