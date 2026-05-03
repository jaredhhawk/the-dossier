"""Application Tracker + dedup ledger writers.

Two surfaces:
- Tracker is APPEND-ONLY: each submission attempt produces one row.
  Status enum reflects that attempt's outcome.
- Ledger is UPSERT (one row per company+normalized_role). Records current
  state, attempt_count, last_attempt_at. Authoritative for ledger_eligible
  retry decisions.

`record_attempt` wraps both writes in atomicity (rollback tracker on
ledger failure) so states stay consistent.

Used by:
- pipeline.tracker_cli (called from /apply skill, default status=applied)
- pipeline.execute (Plan 2, called per-submit with verified status)
"""
from __future__ import annotations

import csv
import enum
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional


TRACKER_HEADER = "| Company | Role | Source | Date | Status | Notes |"
TRACKER_DIVIDER = "|---|---|---|---|---|---|"

UNVERIFIED_COOLDOWN = timedelta(hours=24)


class AppStatus(enum.Enum):
    APPLIED = "applied"
    UNVERIFIED = "unverified"
    FAILED = "failed"
    SKIPPED = "skipped"


_TRACKER_STATUS_DISPLAY = {
    AppStatus.APPLIED: "Applied",
    AppStatus.UNVERIFIED: "Unverified",
    AppStatus.FAILED: "Failed",
    AppStatus.SKIPPED: "Skipped",
}


class AppendResult(enum.Enum):
    APPENDED = "appended"
    CREATED = "created"


class LedgerOp(enum.Enum):
    CREATED = "created"
    UPDATED = "updated"


_LOCATION_SUFFIX = re.compile(
    r"\s*[-(\[].*?(remote|onsite|hybrid|[A-Z]{2}|seattle|new york|san francisco)[\])]?\s*$",
    re.IGNORECASE,
)


def normalize_title(title: str) -> str:
    """Lowercase, strip seniority prefixes (except principal/lead which carry meaning),
    strip trailing location suffixes."""
    t = title.strip().lower()
    t = re.sub(r"^(senior|sr\.?|junior|jr\.?|staff)\s+", "", t)
    t = _LOCATION_SUFFIX.sub("", t)
    return t.strip()


def format_tracker_row(
    *, company: str, role: str, source: str, date: str,
    status: AppStatus, notes: str,
) -> str:
    """Format a single tracker table row. Pipe-separated, no wikilinks."""
    status_display = _TRACKER_STATUS_DISPLAY[status]
    return f"| {company} | {role} | {source} | {date} | {status_display} | {notes} |"


def append_tracker_row(
    tracker_path: Path,
    *,
    company: str, role: str, source: str, date: str,
    status: AppStatus, notes: str,
) -> AppendResult:
    """Append a new row to the Application Tracker. Append-only: never deduplicates."""
    row = format_tracker_row(
        company=company, role=role, source=source, date=date,
        status=status, notes=notes,
    )

    if not tracker_path.exists():
        tracker_path.parent.mkdir(parents=True, exist_ok=True)
        tracker_path.write_text(
            f"{TRACKER_HEADER}\n{TRACKER_DIVIDER}\n{row}\n"
        )
        return AppendResult.CREATED

    text = tracker_path.read_text()
    if not text.endswith("\n"):
        text += "\n"
    tracker_path.write_text(text + row + "\n")
    return AppendResult.APPENDED


def remove_last_row(
    tracker_path: Path, *, expected_company: str, expected_date: str,
) -> bool:
    """Remove the LAST row from the tracker IF it matches expected_company AND expected_date.
    Defensive: returns False (no-op) if the last row doesn't match. Used for atomicity rollback.
    """
    if not tracker_path.exists():
        return False
    text = tracker_path.read_text()
    lines = text.splitlines(keepends=True)
    if not lines:
        return False
    for i in range(len(lines) - 1, -1, -1):
        line = lines[i].strip()
        if not line:
            continue
        if not line.startswith("| ") or "---" in line or "Company | Role" in line:
            return False
        parts = [p.strip() for p in line.strip("|").split("|")]
        if len(parts) < 5:
            return False
        if parts[0] == expected_company and parts[3] == expected_date:
            del lines[i]
            tracker_path.write_text("".join(lines))
            return True
        return False
    return False


def upsert_ledger_row(
    ledger_path: Path,
    *,
    url: str, company: str, role: str, location: str,
    date: str, score: str, grade: str,
    status: AppStatus,
) -> LedgerOp:
    """Find-or-create row by (company, normalized_role).
    - On update: increments attempt_count, sets last_attempt_at = today, updates status.
    - On create: attempt_count=1, last_attempt_at = date.
    """
    norm_role = normalize_title(role)
    norm_company = company.strip()

    rows: list[dict[str, str]] = []
    fieldnames = [
        "url", "company", "normalized_title", "location",
        "date_first_seen", "score", "grade", "status",
        "last_attempt_at", "attempt_count",
    ]

    if ledger_path.exists():
        with open(ledger_path) as f:
            reader = csv.DictReader(f, delimiter="\t")
            rows = list(reader)
            if reader.fieldnames:
                fieldnames = list(reader.fieldnames)

    for r in rows:
        if (
            r.get("company", "").strip().lower() == norm_company.lower()
            and r.get("normalized_title", "").strip().lower() == norm_role
        ):
            r["status"] = status.value
            r["last_attempt_at"] = date
            try:
                r["attempt_count"] = str(int(r.get("attempt_count", "0") or "0") + 1)
            except ValueError:
                r["attempt_count"] = "1"
            _write_ledger(ledger_path, fieldnames, rows)
            return LedgerOp.UPDATED

    rows.append({
        "url": url, "company": norm_company, "normalized_title": norm_role,
        "location": location, "date_first_seen": date,
        "score": score, "grade": grade,
        "status": status.value,
        "last_attempt_at": date, "attempt_count": "1",
    })
    _write_ledger(ledger_path, fieldnames, rows)
    return LedgerOp.CREATED


def ledger_eligible(
    ledger_path: Path, *, company: str, role: str,
    now: Optional[datetime] = None,
) -> bool:
    """True if the card is eligible for a submit attempt.

    Rules (see spec "State Authority + Uncertainty Model"):
    - No row → eligible
    - status=applied → not eligible (always blocks)
    - status=failed → eligible (user re-tick path)
    - status=skipped → eligible
    - status=unverified, last_attempt_at within 24h → not eligible (cooling down)
    - status=unverified, last_attempt_at older than 24h → eligible (auto-retry)
    """
    if not ledger_path.exists():
        return True

    if now is None:
        now = datetime.now()

    norm_role = normalize_title(role)
    norm_company = company.strip().lower()

    with open(ledger_path) as f:
        reader = csv.DictReader(f, delimiter="\t")
        for r in reader:
            if (
                r.get("company", "").strip().lower() == norm_company
                and r.get("normalized_title", "").strip().lower() == norm_role
            ):
                status = (r.get("status") or "").strip().lower()
                if status == "applied":
                    return False
                if status in ("failed", "skipped"):
                    return True
                if status == "unverified":
                    last = (r.get("last_attempt_at") or "").strip()
                    if not last:
                        return True
                    try:
                        last_dt = datetime.fromisoformat(last)
                    except ValueError:
                        return True
                    return (now - last_dt) >= UNVERIFIED_COOLDOWN
                return True
    return True


def record_attempt(
    *,
    tracker_path: Path, ledger_path: Path,
    url: str, company: str, role: str, source: str,
    location: str, date: str, score: str, grade: str,
    status: AppStatus, notes: str,
) -> None:
    """Atomicity wrapper: tracker append + ledger upsert succeed or both fail.

    On ledger failure, the tracker row is removed via remove_last_row()."""
    append_tracker_row(
        tracker_path,
        company=company, role=role, source=source,
        date=date, status=status, notes=notes,
    )
    try:
        upsert_ledger_row(
            ledger_path, url=url, company=company, role=role,
            location=location, date=date, score=score, grade=grade,
            status=status,
        )
    except Exception:
        remove_last_row(
            tracker_path, expected_company=company, expected_date=date,
        )
        raise


def _write_ledger(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    """Write ledger via temp file + rename for atomicity. Preserves Unix newlines.

    Uses extrasaction="ignore" defensively in case rows have extra keys."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=fieldnames, delimiter="\t",
            lineterminator="\n", extrasaction="ignore",
        )
        writer.writeheader()
        for r in rows:
            writer.writerow(r)
    tmp.rename(path)
