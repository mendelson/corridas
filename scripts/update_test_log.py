"""
update_test_log.py — append a test-run entry to data/site-test-log.json.

Usage:
    python scripts/update_test_log.py <path-to-pytest-json-report.json>

Reads the pytest-json-report output, appends a summary entry to
data/site-test-log.json, and keeps at most 100 runs (oldest dropped first).
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

MAX_RUNS = 100
LOG_FILE = Path(__file__).parent.parent / "data" / "site-test-log.json"


def _git_info():
    commit = os.environ.get("GIT_COMMIT", "")
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

    return commit, branch


def _parse_report(report_path: Path) -> dict:
    with open(report_path, encoding="utf-8") as f:
        report = json.load(f)

    summary = report.get("summary", {})
    passed  = summary.get("passed",  0)
    failed  = summary.get("failed",  0)
    skipped = summary.get("skipped", 0)
    total   = summary.get("total",   passed + failed + skipped)
    duration_s = report.get("duration", 0.0)

    results = []
    for test in report.get("tests", []):
        outcome  = test.get("outcome", "unknown")
        nodeid   = test.get("nodeid", "")
        # Use just the test function name (strip file prefix)
        name = nodeid.split("::")[-1] if "::" in nodeid else nodeid
        call = test.get("call", {})
        duration_ms = round((call.get("duration", 0.0)) * 1000, 1)
        message = ""
        if outcome == "failed":
            longrepr = call.get("longrepr", "")
            # Keep only the last few lines for brevity
            if isinstance(longrepr, str):
                lines = longrepr.strip().splitlines()
                message = "\n".join(lines[-5:]) if lines else longrepr
            elif isinstance(longrepr, list):
                message = "\n".join(str(x) for x in longrepr[-5:])
        results.append({
            "name": name,
            "status": outcome,
            "duration_ms": duration_ms,
            "message": message,
        })

    return {
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "total": total,
        "duration_s": round(duration_s, 2),
        "results": results,
    }


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

    commit, branch = _git_info()
    parsed = _parse_report(report_path)

    entry = {
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "commit": commit,
        "branch": branch,
        **parsed,
    }

    runs.append(entry)

    # Keep only the most recent MAX_RUNS entries
    if len(runs) > MAX_RUNS:
        runs = runs[-MAX_RUNS:]

    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(runs, f, indent=2, ensure_ascii=False)

    print(
        f"Logged run: passed={entry['passed']} failed={entry['failed']} "
        f"skipped={entry['skipped']} total={entry['total']} "
        f"duration={entry['duration_s']}s → {LOG_FILE}"
    )


if __name__ == "__main__":
    main()
