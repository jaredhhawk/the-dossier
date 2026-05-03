"""Tests for pipeline.cl_flag_scan — regex pre-flight for CL placeholder leaks."""
from pathlib import Path

import pytest

from pipeline.cl_flag_scan import scan_cl_text, FlagMatch

FIXTURES = Path(__file__).parent / "fixtures"


def test_clean_cl_returns_no_flags():
    text = (FIXTURES / "cl_clean.md").read_text()
    matches = scan_cl_text(text)
    assert matches == []


def test_placeholder_cl_flags_X_bracket():
    text = (FIXTURES / "cl_with_placeholder.md").read_text()
    matches = scan_cl_text(text)
    pattern_names = {m.pattern_name for m in matches}
    assert "X_PLACEHOLDER" in pattern_names
    assert "FILL_IN" in pattern_names


def test_INSERT_pattern_matches():
    text = "Mention [INSERT METRIC] before the close."
    matches = scan_cl_text(text)
    assert len(matches) >= 1
    assert any(m.pattern_name == "INSERT_PLACEHOLDER" for m in matches)


def test_before_sending_pattern_matches():
    text = "Note to self: rewrite the second paragraph before sending."
    matches = scan_cl_text(text)
    assert any(m.pattern_name == "BEFORE_SENDING" for m in matches)


def test_X_pattern_is_word_boundary_not_substring():
    """[X-Series] is a legit product name fragment — should NOT flag."""
    text = "I worked on the [X-Series] platform during my last role."
    matches = scan_cl_text(text)
    pattern_names = {m.pattern_name for m in matches}
    assert "X_PLACEHOLDER" not in pattern_names


def test_match_includes_context_snippet():
    text = (FIXTURES / "cl_with_placeholder.md").read_text()
    matches = scan_cl_text(text)
    # Each match should include enough context to show the user
    assert all(len(m.context) >= 20 for m in matches)
    assert all(m.matched_text in m.context for m in matches)
