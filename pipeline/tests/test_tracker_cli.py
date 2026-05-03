"""Tests for pipeline.tracker_cli — CLI wrapper around tracker.py."""
import csv
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
WORKTREE_ROOT = Path(__file__).resolve().parent.parent.parent


def _run_cli(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "pipeline.tracker_cli"] + args,
        cwd=WORKTREE_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_tracker_cli_default_status_applied(tmp_path):
    tracker = tmp_path / "Tracker.md"
    shutil.copy(FIXTURES / "tracker_sample.md", tracker)
    ledger = tmp_path / "ledger.tsv"
    shutil.copy(FIXTURES / "ledger_sample.tsv", ledger)

    result = _run_cli([
        "--company", "Orkes",
        "--role", "Product Manager",
        "--source", "Pipeline",
        "--date", "2026-05-02",
        "--notes", "Pipeline logged",
        "--tracker-path", str(tracker),
        "--ledger-path", str(ledger),
    ])
    assert result.returncode == 0, result.stderr
    assert "Tracker:" in result.stdout
    assert "Ledger:" in result.stdout

    text = tracker.read_text()
    assert "| Orkes | Product Manager | Pipeline | 2026-05-02 | Applied | Pipeline logged |" in text


def test_tracker_cli_status_unverified_writes_unverified(tmp_path):
    tracker = tmp_path / "Tracker.md"
    shutil.copy(FIXTURES / "tracker_sample.md", tracker)
    ledger = tmp_path / "ledger.tsv"
    shutil.copy(FIXTURES / "ledger_sample.tsv", ledger)

    result = _run_cli([
        "--company", "Orkes", "--role", "PM",
        "--source", "Pipeline", "--date", "2026-05-02",
        "--status", "unverified",
        "--tracker-path", str(tracker), "--ledger-path", str(ledger),
    ])
    assert result.returncode == 0
    assert "| Orkes | PM | Pipeline | 2026-05-02 | Unverified |" in tracker.read_text()


def test_tracker_cli_warns_on_duplicate_applied(tmp_path):
    """If ledger says (company, role) already applied, warn but still log."""
    tracker = tmp_path / "Tracker.md"
    shutil.copy(FIXTURES / "tracker_sample.md", tracker)
    ledger = tmp_path / "ledger.tsv"
    shutil.copy(FIXTURES / "ledger_sample.tsv", ledger)

    result = _run_cli([
        "--company", "Updater",
        "--role", "Technical Product Lead",
        "--source", "Pipeline", "--date", "2026-05-02",
        "--tracker-path", str(tracker), "--ledger-path", str(ledger),
    ])
    assert "duplicate" in result.stdout.lower() or "already applied" in result.stdout.lower()
    assert result.returncode == 0


def test_tracker_cli_no_ledger_flag(tmp_path):
    tracker = tmp_path / "Tracker.md"
    shutil.copy(FIXTURES / "tracker_sample.md", tracker)

    result = _run_cli([
        "--company", "Orkes", "--role", "PM",
        "--source", "Pipeline", "--date", "2026-05-02",
        "--tracker-path", str(tracker),
        "--no-ledger",
    ])
    assert result.returncode == 0
    assert "Tracker:" in result.stdout
    assert "Ledger:" not in result.stdout


def test_tracker_cli_invalid_status_rejected(tmp_path):
    result = _run_cli([
        "--company", "X", "--role", "Y",
        "--source", "Pipeline", "--date", "2026-05-02",
        "--status", "bogus",
    ])
    assert result.returncode != 0
    assert "invalid" in result.stderr.lower() or "choice" in result.stderr.lower()
