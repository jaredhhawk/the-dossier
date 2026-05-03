"""CLI wrapper around pipeline.tracker for use from the /apply skill markdown.

The skill cannot import Python directly, so it shells out to:
    python -m pipeline.tracker_cli --company X --role Y --source Pipeline --date YYYY-MM-DD --status applied ...

Default paths point at the user's vault and pipeline ledger; tests override via
--tracker-path and --ledger-path.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pipeline.tracker import (
    AppStatus,
    ledger_eligible,
    record_attempt,
    append_tracker_row,
)


DEFAULT_TRACKER = Path.home() / "Documents" / "Second Brain" / "02_Projects" / "Job Search" / "R - Application Tracker.md"
DEFAULT_LEDGER = Path(__file__).resolve().parent / "data" / "ledger.tsv"

_STATUS_CHOICES = ["applied", "unverified", "failed", "skipped"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--company", required=True)
    parser.add_argument("--role", required=True)
    parser.add_argument("--source", default="Pipeline")
    parser.add_argument("--date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--url", default="")
    parser.add_argument("--location", default="")
    parser.add_argument("--score", default="")
    parser.add_argument("--grade", default="")
    parser.add_argument("--notes", default="")
    parser.add_argument("--status", choices=_STATUS_CHOICES, default="applied",
                        help="Application outcome status (default: applied).")
    parser.add_argument("--tracker-path", default=str(DEFAULT_TRACKER))
    parser.add_argument("--ledger-path", default=str(DEFAULT_LEDGER))
    parser.add_argument("--no-ledger", action="store_true",
                        help="Skip ledger update; only writes tracker row.")
    args = parser.parse_args(argv)

    tracker_path = Path(args.tracker_path)
    ledger_path = Path(args.ledger_path)
    status = AppStatus(args.status)

    # Dedup warn (consult ledger, but do NOT block — caller asked to log)
    if not args.no_ledger and not ledger_eligible(
        ledger_path, company=args.company, role=args.role,
    ):
        print(f"[tracker-cli] WARNING: ledger says {args.company} - {args.role} is not eligible (duplicate or cooling down). Logging anyway.")

    notes = args.notes or ("Pipeline logged" if args.source == "Pipeline" else "")

    if args.no_ledger:
        result = append_tracker_row(
            tracker_path,
            company=args.company, role=args.role, source=args.source,
            date=args.date, status=status, notes=notes,
        )
        print(f"Tracker: {result.value} {tracker_path}")
    else:
        record_attempt(
            tracker_path=tracker_path, ledger_path=ledger_path,
            url=args.url, company=args.company, role=args.role,
            source=args.source, location=args.location,
            date=args.date, score=args.score, grade=args.grade,
            status=status, notes=notes,
        )
        print(f"Tracker: appended to {tracker_path}")
        print(f"Ledger: updated {ledger_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
