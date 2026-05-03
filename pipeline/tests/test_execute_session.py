"""Tests for execute.py session loop and end-of-session prompt (mocked Playwright)."""
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def triage_path(tmp_path):
    p = tmp_path / "Daily Triage 2026-05-02.md"
    shutil.copy(FIXTURES / "triage_sample.md", p)
    # Pre-tick AcmeCo and BetaInc so we have two cards in queue
    text = p.read_text()
    text = text.replace(
        "- [ ] apply\n- [ ] skip\n\n## [B] Charlie",
        "- [x] apply\n- [ ] skip\n\n## [B] Charlie",
    )
    p.write_text(text)
    return p


@pytest.fixture
def empty_ledger(tmp_path):
    p = tmp_path / "ledger.tsv"
    p.write_text(
        "url\tcompany\tnormalized_title\tlocation\tdate_first_seen\tscore\tgrade\tstatus\tlast_attempt_at\tattempt_count\n"
    )
    return p


# -- Pitch summary --

def test_pitch_summary_lists_only_grade_a_confirmed():
    from pipeline.execute import format_pitch_summary
    summary = format_pitch_summary(submitted=[
        {"company": "AcmeCo", "grade": "A", "status": "applied"},
        {"company": "BetaInc", "grade": "B", "status": "applied"},
        {"company": "GammaCorp", "grade": "A", "status": "applied"},
        {"company": "DeltaCo", "grade": "A", "status": "unverified"},
    ])
    assert "AcmeCo" in summary
    assert "GammaCorp" in summary
    assert "BetaInc" not in summary  # B doesn't trigger pitch
    assert "DeltaCo" not in summary  # Unverified doesn't trigger pitch


def test_pitch_summary_empty_when_no_grade_a_applied():
    from pipeline.execute import format_pitch_summary
    summary = format_pitch_summary(submitted=[
        {"company": "X", "grade": "B", "status": "applied"},
        {"company": "Y", "grade": "A", "status": "unverified"},
    ])
    assert summary == ""


# -- Simplify wait resolution --

def test_simplify_wait_resolves_flag_over_env_over_config(monkeypatch):
    from pipeline.execute import resolve_simplify_wait
    monkeypatch.setenv("PIPELINE_EXECUTE_SIMPLIFY_WAIT", "10")
    assert resolve_simplify_wait(flag_value=5, config_value=3) == 5
    assert resolve_simplify_wait(flag_value=None, config_value=3) == 10
    monkeypatch.delenv("PIPELINE_EXECUTE_SIMPLIFY_WAIT")
    assert resolve_simplify_wait(flag_value=None, config_value=3) == 3
    assert resolve_simplify_wait(flag_value=None, config_value=None) == 3


# -- build_queue: ledger-first filtering --

def test_build_queue_skips_non_apply_states(triage_path, empty_ledger):
    from pipeline.execute import build_queue
    queue = build_queue(triage_path.read_text(), empty_ledger)
    companies = [c.company for c in queue]
    assert "AcmeCo" in companies
    assert "BetaInc" in companies
    assert "Charlie Corp" not in companies  # Unresolved


def test_build_queue_filters_by_ledger_eligibility(triage_path, tmp_path):
    """Cards with ledger status=applied are filtered out even if [x] apply in markdown."""
    ledger = tmp_path / "ledger.tsv"
    ledger.write_text(
        "url\tcompany\tnormalized_title\tlocation\tdate_first_seen\tscore\tgrade\tstatus\tlast_attempt_at\tattempt_count\n"
        "\tAcmeCo\tpm\t\t2026-04-01\t\tA\tapplied\t2026-04-01\t1\n"
    )
    from pipeline.execute import build_queue
    queue = build_queue(triage_path.read_text(), ledger)
    companies = [c.company for c in queue]
    assert "AcmeCo" not in companies  # Already applied per ledger
    assert "BetaInc" in companies     # Still eligible


def test_build_queue_keeps_failed_status_cards(triage_path, tmp_path):
    """Failed in ledger → eligible (user re-tick path)."""
    ledger = tmp_path / "ledger.tsv"
    ledger.write_text(
        "url\tcompany\tnormalized_title\tlocation\tdate_first_seen\tscore\tgrade\tstatus\tlast_attempt_at\tattempt_count\n"
        "\tAcmeCo\tpm\t\t2026-04-01\t\tA\tfailed\t2026-04-01\t1\n"
    )
    from pipeline.execute import build_queue
    queue = build_queue(triage_path.read_text(), ledger)
    companies = [c.company for c in queue]
    assert "AcmeCo" in companies


# -- Session-summary formatter --

def test_session_summary_breaks_down_by_status():
    from pipeline.execute import format_session_summary
    summary = format_session_summary(
        attempts=[
            {"company": "AcmeCo", "grade": "A", "status": "applied"},
            {"company": "BetaInc", "grade": "B", "status": "applied"},
            {"company": "DeltaCo", "grade": "A", "status": "unverified"},
            {"company": "EpsilonCo", "grade": "B", "status": "failed"},
        ],
        queue_size=4,
    )
    assert "4 attempts" in summary
    assert "2 applied" in summary
    assert "1 unverified" in summary
    assert "1 failed" in summary


def test_session_summary_lists_unverified_for_reconciliation():
    from pipeline.execute import format_unverified_section
    section = format_unverified_section(
        attempts=[
            {"company": "DeltaCo", "grade": "A", "status": "unverified",
             "url": "https://example.com/jobs/9", "role": "PM"},
        ],
    )
    assert "DeltaCo" in section
    assert "manual reconciliation" in section.lower() or "auto-retry" in section.lower()
    assert "https://example.com/jobs/9" in section
