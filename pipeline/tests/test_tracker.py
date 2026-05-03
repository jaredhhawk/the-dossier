"""Tests for pipeline.tracker — Tracker append + ledger upsert + eligibility + atomicity."""
import shutil
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from pipeline.tracker import (
    AppStatus,
    AppendResult,
    LedgerOp,
    normalize_title,
    format_tracker_row,
    append_tracker_row,
    upsert_ledger_row,
    ledger_eligible,
    record_attempt,
    remove_last_row,
)

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def tracker_path(tmp_path):
    p = tmp_path / "Tracker.md"
    shutil.copy(FIXTURES / "tracker_sample.md", p)
    return p


@pytest.fixture
def ledger_path(tmp_path):
    p = tmp_path / "ledger.tsv"
    shutil.copy(FIXTURES / "ledger_sample.tsv", p)
    return p


# --- normalize_title ---

def test_normalize_title_lowercases_and_strips_seniority():
    assert normalize_title("Senior Product Manager") == "product manager"
    assert normalize_title("Sr. Product Manager") == "product manager"
    assert normalize_title("Principal Product Manager") == "principal product manager"


def test_normalize_title_strips_location_suffix():
    assert normalize_title("Product Manager - Seattle, WA") == "product manager"
    assert normalize_title("Product Manager (Remote)") == "product manager"


# --- format_tracker_row + append_tracker_row (status-aware) ---

def test_format_tracker_row_default_status_applied():
    row = format_tracker_row(
        company="Orkes", role="Product Manager", source="Pipeline",
        date="2026-05-02", status=AppStatus.APPLIED, notes="Pipeline logged",
    )
    assert row == "| Orkes | Product Manager | Pipeline | 2026-05-02 | Applied | Pipeline logged |"


def test_format_tracker_row_unverified():
    row = format_tracker_row(
        company="X", role="Y", source="Pipeline",
        date="2026-05-02", status=AppStatus.UNVERIFIED, notes="",
    )
    assert "| Unverified |" in row


def test_format_tracker_row_failed():
    row = format_tracker_row(
        company="X", role="Y", source="Pipeline",
        date="2026-05-02", status=AppStatus.FAILED, notes="selector miss",
    )
    assert "| Failed |" in row
    assert "selector miss" in row


def test_append_tracker_row_appends_status(tracker_path):
    result = append_tracker_row(
        tracker_path, company="Orkes", role="Product Manager",
        source="Pipeline", date="2026-05-02",
        status=AppStatus.UNVERIFIED, notes="",
    )
    assert result == AppendResult.APPENDED
    text = tracker_path.read_text()
    assert "| Orkes | Product Manager | Pipeline | 2026-05-02 | Unverified |" in text
    assert "Updater" in text


def test_append_tracker_row_creates_file_if_missing(tmp_path):
    p = tmp_path / "missing-tracker.md"
    result = append_tracker_row(
        p, company="X", role="Y", source="Pipeline",
        date="2026-05-02", status=AppStatus.APPLIED, notes="",
    )
    assert result == AppendResult.CREATED
    text = p.read_text()
    assert "| Company | Role | Source | Date | Status | Notes |" in text
    assert "| X | Y | Pipeline | 2026-05-02 | Applied |  |" in text


# --- upsert_ledger_row ---

def test_upsert_ledger_creates_new_row(ledger_path):
    op = upsert_ledger_row(
        ledger_path, url="https://example.com/jobs/9",
        company="NewCo", role="PM", location="Remote",
        date="2026-05-02", score="3.5", grade="B",
        status=AppStatus.APPLIED,
    )
    assert op == LedgerOp.CREATED

    import csv
    with open(ledger_path) as f:
        rows = list(csv.DictReader(f, delimiter="\t"))
    by_company = {r["company"]: r for r in rows}
    new_row = by_company["NewCo"]
    assert new_row["status"] == "applied"
    assert new_row["attempt_count"] == "1"
    assert new_row["last_attempt_at"] == "2026-05-02"


def test_upsert_ledger_updates_existing_row_increments_attempt_count(ledger_path):
    op = upsert_ledger_row(
        ledger_path, url="", company="Updater", role="Technical Product Lead",
        location="", date="2026-05-02", score="", grade="",
        status=AppStatus.UNVERIFIED,
    )
    assert op == LedgerOp.UPDATED

    import csv
    with open(ledger_path) as f:
        rows = list(csv.DictReader(f, delimiter="\t"))
    by_company = {r["company"]: r for r in rows}
    updater = by_company["Updater"]
    assert updater["status"] == "unverified"
    assert updater["attempt_count"] == "2"
    assert updater["last_attempt_at"] == "2026-05-02"
    assert updater["date_first_seen"] == "2026-03-25"


def test_upsert_ledger_failed_status(ledger_path):
    op = upsert_ledger_row(
        ledger_path, url="https://x.com", company="ZetaCo", role="PM",
        location="", date="2026-05-02", score="", grade="A",
        status=AppStatus.FAILED,
    )
    assert op == LedgerOp.CREATED
    import csv
    with open(ledger_path) as f:
        rows = list(csv.DictReader(f, delimiter="\t"))
    by_company = {r["company"]: r for r in rows}
    assert by_company["ZetaCo"]["status"] == "failed"


# --- ledger_eligible (authority rules) ---

def test_ledger_eligible_returns_true_for_missing_row(ledger_path):
    assert ledger_eligible(ledger_path, company="NewCo", role="PM") is True


def test_ledger_eligible_returns_false_for_applied(ledger_path):
    assert ledger_eligible(
        ledger_path, company="Updater", role="Technical Product Lead",
    ) is False


def test_ledger_eligible_returns_false_for_unverified_within_24h(ledger_path):
    now = datetime.now()
    upsert_ledger_row(
        ledger_path, url="", company="Updater", role="Technical Product Lead",
        location="", date=now.date().isoformat(), score="", grade="",
        status=AppStatus.UNVERIFIED,
    )
    assert ledger_eligible(
        ledger_path, company="Updater", role="Technical Product Lead",
    ) is False


def test_ledger_eligible_returns_true_for_unverified_after_24h(ledger_path, monkeypatch):
    upsert_ledger_row(
        ledger_path, url="", company="Updater", role="Technical Product Lead",
        location="", date="2026-04-30", score="", grade="",
        status=AppStatus.UNVERIFIED,
    )
    fake_now = datetime(2026, 5, 2, 12, 0, 0)
    assert ledger_eligible(
        ledger_path, company="Updater", role="Technical Product Lead",
        now=fake_now,
    ) is True


def test_ledger_eligible_returns_true_for_failed(ledger_path):
    upsert_ledger_row(
        ledger_path, url="", company="Updater", role="Technical Product Lead",
        location="", date="2026-05-02", score="", grade="",
        status=AppStatus.FAILED,
    )
    assert ledger_eligible(
        ledger_path, company="Updater", role="Technical Product Lead",
    ) is True


def test_ledger_eligible_returns_true_for_skipped(ledger_path):
    upsert_ledger_row(
        ledger_path, url="", company="Updater", role="Technical Product Lead",
        location="", date="2026-05-02", score="", grade="",
        status=AppStatus.SKIPPED,
    )
    assert ledger_eligible(
        ledger_path, company="Updater", role="Technical Product Lead",
    ) is True


# --- record_attempt (atomicity) ---

def test_record_attempt_writes_both_tracker_and_ledger(tracker_path, ledger_path):
    record_attempt(
        tracker_path=tracker_path, ledger_path=ledger_path,
        url="https://example.com/jobs/9",
        company="Orkes", role="Product Manager", source="Pipeline",
        location="Seattle", date="2026-05-02", score="3.8", grade="B",
        status=AppStatus.APPLIED, notes="",
    )

    assert "| Orkes |" in tracker_path.read_text()

    import csv
    with open(ledger_path) as f:
        rows = list(csv.DictReader(f, delimiter="\t"))
    assert any(r["company"] == "Orkes" for r in rows)


def test_record_attempt_rolls_back_tracker_on_ledger_failure(tracker_path, ledger_path, monkeypatch):
    """If ledger write fails, the tracker row is removed so states stay consistent."""
    pre_text = tracker_path.read_text()

    def boom(*args, **kwargs):
        raise IOError("simulated ledger write failure")
    monkeypatch.setattr("pipeline.tracker.upsert_ledger_row", boom)

    with pytest.raises(IOError):
        record_attempt(
            tracker_path=tracker_path, ledger_path=ledger_path,
            url="https://example.com/jobs/X",
            company="Orkes", role="Product Manager", source="Pipeline",
            location="", date="2026-05-02", score="", grade="B",
            status=AppStatus.APPLIED, notes="",
        )

    assert tracker_path.read_text() == pre_text


def test_remove_last_row_removes_only_matching_company(tracker_path):
    append_tracker_row(
        tracker_path, company="Orkes", role="PM", source="Pipeline",
        date="2026-05-02", status=AppStatus.APPLIED, notes="",
    )
    pre_text_with_orkes = tracker_path.read_text()
    assert "Orkes" in pre_text_with_orkes

    remove_last_row(tracker_path, expected_company="Orkes", expected_date="2026-05-02")
    post = tracker_path.read_text()
    assert "Orkes" not in post
    assert "Updater" in post
    assert "ActBlue" in post


def test_remove_last_row_no_op_if_company_doesnt_match(tracker_path):
    append_tracker_row(
        tracker_path, company="Orkes", role="PM", source="Pipeline",
        date="2026-05-02", status=AppStatus.APPLIED, notes="",
    )
    pre = tracker_path.read_text()
    remove_last_row(tracker_path, expected_company="WrongCo", expected_date="2026-05-02")
    assert tracker_path.read_text() == pre
