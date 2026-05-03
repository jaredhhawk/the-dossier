"""Tests for pipeline.execute parser — markdown → card structs."""
from pathlib import Path

import pytest

from pipeline.execute import (
    parse_triage_markdown,
    Card,
    CheckboxState,
)

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def triage_text():
    return (FIXTURES / "triage_sample.md").read_text()


def test_parse_returns_three_cards(triage_text):
    cards = parse_triage_markdown(triage_text)
    assert len(cards) == 3


def test_parse_extracts_basic_fields(triage_text):
    cards = parse_triage_markdown(triage_text)
    by_company = {c.company: c for c in cards}
    acme = by_company["AcmeCo"]
    assert acme.grade == "A"
    assert acme.role == "Senior PM"
    assert acme.url == "https://job-boards.greenhouse.io/acmeco/jobs/123"
    assert acme.resume_pdf == "/abs/Jared-Hawkins-AcmeCo-Senior-PM-2026-05-02.pdf"
    assert acme.cl_pdf == "/abs/Jared-Hawkins-AcmeCo-Senior-PM-2026-05-02.pdf"


def test_parse_checkbox_state_apply(triage_text):
    cards = parse_triage_markdown(triage_text)
    by_company = {c.company: c for c in cards}
    assert by_company["AcmeCo"].state == CheckboxState.APPLY
    assert by_company["BetaInc"].state == CheckboxState.UNCHECKED


def test_parse_unresolved_card_state(triage_text):
    cards = parse_triage_markdown(triage_text)
    by_company = {c.company: c for c in cards}
    charlie = by_company["Charlie Corp"]
    assert charlie.state == CheckboxState.UNRESOLVED


def test_parse_handles_applied_state():
    md = (
        "## [A] X — Y\n"
        "- JD: https://example.com\n"
        "- Resume: /r.pdf\n"
        "- CL: /c.pdf\n"
        "- [x] applied\n"
        "- [ ] skip\n"
    )
    cards = parse_triage_markdown(md)
    assert cards[0].state == CheckboxState.APPLIED


def test_parse_handles_skipped_state():
    md = (
        "## [A] X — Y\n"
        "- JD: https://example.com\n"
        "- Resume: /r.pdf\n"
        "- CL: /c.pdf\n"
        "- [ ] apply skipped\n"
    )
    cards = parse_triage_markdown(md)
    assert cards[0].state == CheckboxState.SKIPPED


def test_parse_handles_error_state():
    md = (
        "## [A] X — Y\n"
        "- JD: https://example.com\n"
        "- Resume: /r.pdf\n"
        "- CL: /c.pdf\n"
        "- [x] apply error: page timeout\n"
    )
    cards = parse_triage_markdown(md)
    assert cards[0].state == CheckboxState.ERROR


def test_parse_tolerates_blank_lines_between_sections(triage_text):
    cards = parse_triage_markdown(triage_text)
    assert len(cards) == 3
