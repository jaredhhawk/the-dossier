"""Tests for pipeline.migrate_ledger — one-shot ledger schema migration."""
import csv
import shutil
from pathlib import Path

import pytest

from pipeline.migrate_ledger import migrate_ledger, MigrationResult

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def pre_ledger(tmp_path):
    p = tmp_path / "ledger.tsv"
    shutil.copy(FIXTURES / "ledger_premigration.tsv", p)
    return p


def _read_rows(path):
    with open(path) as f:
        return list(csv.DictReader(f, delimiter="\t"))


def test_migration_adds_new_columns(pre_ledger):
    result = migrate_ledger(pre_ledger)
    assert result == MigrationResult.MIGRATED

    with open(pre_ledger) as f:
        header = f.readline().strip().split("\t")
    assert "last_attempt_at" in header
    assert "attempt_count" in header


def test_migration_backfills_last_attempt_at(pre_ledger):
    migrate_ledger(pre_ledger)
    rows = _read_rows(pre_ledger)
    by_company = {r["company"]: r for r in rows}
    assert by_company["Updater"]["last_attempt_at"] == "2026-03-25"
    assert by_company["ActBlue"]["last_attempt_at"] == "2026-03-24"


def test_migration_backfills_attempt_count(pre_ledger):
    migrate_ledger(pre_ledger)
    rows = _read_rows(pre_ledger)
    for r in rows:
        assert r["attempt_count"] == "1"


def test_migration_preserves_existing_status(pre_ledger):
    migrate_ledger(pre_ledger)
    rows = _read_rows(pre_ledger)
    by_company = {r["company"]: r for r in rows}
    assert by_company["Updater"]["status"] == "applied"
    assert by_company["Pitched Co"]["status"] == "pitched"


def test_migration_idempotent(pre_ledger):
    """Running twice is a no-op."""
    migrate_ledger(pre_ledger)
    first_text = pre_ledger.read_text()
    result = migrate_ledger(pre_ledger)
    assert result == MigrationResult.ALREADY_MIGRATED
    assert pre_ledger.read_text() == first_text


def test_migration_handles_missing_file(tmp_path):
    p = tmp_path / "nope.tsv"
    result = migrate_ledger(p)
    assert result == MigrationResult.MISSING


def test_migration_preserves_row_count(pre_ledger):
    pre_count = len(_read_rows(pre_ledger))
    migrate_ledger(pre_ledger)
    post_count = len(_read_rows(pre_ledger))
    assert pre_count == post_count
