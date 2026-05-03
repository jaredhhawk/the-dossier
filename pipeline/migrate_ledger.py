"""One-shot, idempotent ledger schema migration.

Adds `last_attempt_at` and `attempt_count` columns to existing ledger.tsv.
Existing rows get backfilled: last_attempt_at = date_first_seen, attempt_count = 1.

Run once after upgrading to Plan 2; not part of normal /pipeline flow.

Usage:
    cd ~/code/the-dossier-apply-flow-v2 && pipeline/.venv/bin/python3 -m pipeline.migrate_ledger
    cd ~/code/the-dossier-apply-flow-v2 && pipeline/.venv/bin/python3 -m pipeline.migrate_ledger --ledger-path /path/to/ledger.tsv
"""
from __future__ import annotations

import argparse
import csv
import enum
import sys
from pathlib import Path


NEW_COLUMNS = ("last_attempt_at", "attempt_count")


class MigrationResult(enum.Enum):
    MIGRATED = "migrated"
    ALREADY_MIGRATED = "already_migrated"
    MISSING = "missing"


def migrate_ledger(ledger_path: Path) -> MigrationResult:
    """Add last_attempt_at + attempt_count columns to ledger.tsv if missing.
    Backfills existing rows. Idempotent."""
    if not ledger_path.exists():
        return MigrationResult.MISSING

    with open(ledger_path) as f:
        reader = csv.DictReader(f, delimiter="\t")
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])

    if all(c in fieldnames for c in NEW_COLUMNS):
        return MigrationResult.ALREADY_MIGRATED

    # Backfill new columns
    for col in NEW_COLUMNS:
        if col not in fieldnames:
            fieldnames.append(col)
    for r in rows:
        if not r.get("last_attempt_at"):
            r["last_attempt_at"] = r.get("date_first_seen", "")
        if not r.get("attempt_count"):
            r["attempt_count"] = "1"

    tmp_path = ledger_path.with_suffix(".tsv.tmp")
    with open(tmp_path, "w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=fieldnames,
            delimiter="\t",
            lineterminator="\n",
            extrasaction="ignore",
        )
        writer.writeheader()
        for r in rows:
            writer.writerow(r)
    tmp_path.rename(ledger_path)

    return MigrationResult.MIGRATED


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger-path",
                        default=str(Path(__file__).resolve().parent / "data" / "ledger.tsv"))
    args = parser.parse_args(argv)

    result = migrate_ledger(Path(args.ledger_path))
    if result == MigrationResult.MIGRATED:
        print(f"[migrate-ledger] migrated: {args.ledger_path}")
        return 0
    elif result == MigrationResult.ALREADY_MIGRATED:
        print(f"[migrate-ledger] already migrated: {args.ledger_path}")
        return 0
    elif result == MigrationResult.MISSING:
        print(f"[migrate-ledger] file not found: {args.ledger_path}", file=sys.stderr)
        return 2
    else:
        raise RuntimeError(f"Unknown result: {result}")


if __name__ == "__main__":
    sys.exit(main())
