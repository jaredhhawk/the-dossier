"""Tests for pipeline.execute checkbox-rewrite functions."""
import shutil
from pathlib import Path

import pytest

from pipeline.execute import (
    flip_apply_to_applied,
    flip_apply_to_skipped,
    flip_apply_to_error,
)

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def triage_path(tmp_path):
    p = tmp_path / "Daily Triage 2026-05-02.md"
    shutil.copy(FIXTURES / "triage_sample.md", p)
    return p


def test_flip_apply_to_applied_changes_only_target_card(triage_path):
    flip_apply_to_applied(triage_path, url="https://job-boards.greenhouse.io/acmeco/jobs/123")
    text = triage_path.read_text()

    # Acme's [x] apply became [x] applied
    acme_section = text.split("## [B] BetaInc")[0]
    assert "[x] applied" in acme_section
    assert "- [x] apply\n" not in acme_section  # The original line is gone

    # BetaInc untouched ([ ] apply stays)
    beta_section = text.split("## [B] BetaInc")[1].split("## [B] Charlie")[0]
    assert "- [ ] apply\n" in beta_section
    assert "[x] applied" not in beta_section


def test_flip_apply_to_skipped(triage_path):
    flip_apply_to_skipped(triage_path, url="https://job-boards.greenhouse.io/acmeco/jobs/123")
    text = triage_path.read_text()
    acme_section = text.split("## [B] BetaInc")[0]
    assert "[ ] apply skipped" in acme_section


def test_flip_apply_to_error_includes_message(triage_path):
    flip_apply_to_error(
        triage_path,
        url="https://job-boards.greenhouse.io/acmeco/jobs/123",
        message="page timeout",
    )
    text = triage_path.read_text()
    acme_section = text.split("## [B] BetaInc")[0]
    assert "[x] apply error: page timeout" in acme_section


def test_flip_is_idempotent_on_already_applied(triage_path):
    """Flipping a card that's already [x] applied is a no-op (not an error)."""
    flip_apply_to_applied(triage_path, url="https://job-boards.greenhouse.io/acmeco/jobs/123")
    flip_apply_to_applied(triage_path, url="https://job-boards.greenhouse.io/acmeco/jobs/123")
    text = triage_path.read_text()
    acme_section = text.split("## [B] BetaInc")[0]
    assert acme_section.count("[x] applied") == 1


def test_flip_handles_url_not_in_file(triage_path):
    """No crash if URL doesn't match any card."""
    flip_apply_to_applied(triage_path, url="https://nonexistent.example/123")
    # File unchanged
    original = (FIXTURES / "triage_sample.md").read_text()
    assert triage_path.read_text() == original
