"""Tests for pipeline.triage_writer — pure functions only (file I/O in test_triage_writer_io.py)."""
import json
from pathlib import Path

import pytest

from pipeline.triage_writer import (
    is_unresolved_url,
    extract_card_data,
    format_card_section,
    format_triage_markdown,
    truncate_preview,
)

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def manifest():
    return json.loads((FIXTURES / "manifest_sample.json").read_text())


@pytest.fixture
def scored():
    return json.loads((FIXTURES / "scored_with_artifacts.json").read_text())


def test_is_unresolved_url_detects_adzuna():
    assert is_unresolved_url("https://www.adzuna.com/details/123") is True
    assert is_unresolved_url("https://job-boards.greenhouse.io/acme/jobs/1") is False
    assert is_unresolved_url("https://jobs.lever.co/foo/abc") is False
    assert is_unresolved_url("https://jobs.ashbyhq.com/foo/abc") is False


def test_extract_card_data_merges_manifest_and_scored(manifest, scored):
    """For a card in both, output has manifest fields + scored editorial fields."""
    cards = extract_card_data(manifest, scored)
    by_company = {c["company"]: c for c in cards}
    acme = by_company["AcmeCo"]
    assert acme["grade"] == "A"
    assert acme["role"] == "Senior PM"
    assert acme["salary"] == "$200,000-$240,000"
    assert acme["fit"] == "Direct PM fit; strong AI tailwind."
    assert acme["risks"] == []
    assert acme["lane"] == "A"
    assert acme["resume_pdf"] == "/abs/Jared-Hawkins-AcmeCo-Senior-PM-2026-05-02.pdf"
    assert acme["url"] == "https://job-boards.greenhouse.io/acmeco/jobs/123"
    assert acme["unresolved"] is False


def test_extract_card_data_marks_adzuna_unresolved(manifest, scored):
    cards = extract_card_data(manifest, scored)
    by_company = {c["company"]: c for c in cards}
    charlie = by_company["Charlie Corp"]
    assert charlie["unresolved"] is True


def test_extract_card_data_includes_cached_cards(manifest, scored):
    """Manifest's `generated` AND `cached` arrays both produce triage cards."""
    cards = extract_card_data(manifest, scored)
    companies = {c["company"] for c in cards}
    assert "AcmeCo" in companies      # generated
    assert "BetaInc" in companies     # generated
    assert "Charlie Corp" in companies  # cached


def test_extract_card_data_skips_cards_not_in_scored(manifest):
    """If a card is in manifest but not scored JSON, render with placeholder editorial fields."""
    cards = extract_card_data(manifest, scored=[])
    # Should still emit cards from manifest, but with empty fit/salary/risks
    by_company = {c["company"]: c for c in cards}
    assert by_company["AcmeCo"]["fit"] == ""
    assert by_company["AcmeCo"]["salary"] == ""
    assert by_company["AcmeCo"]["risks"] == []


def test_truncate_preview_under_limit_passes_through():
    short = "Hello world"
    assert truncate_preview(short, max_chars=200) == short


def test_truncate_preview_over_limit_appends_ellipsis():
    long = "x" * 250
    out = truncate_preview(long, max_chars=200)
    assert out.endswith("...")
    assert len(out) == 203  # 200 + "..."


def test_format_card_section_resolved():
    card = {
        "grade": "A", "company": "AcmeCo", "role": "Senior PM",
        "salary": "$200,000-$240,000", "archetype": "product_management",
        "lane": "A",
        "fit": "Direct PM fit; strong AI tailwind.",
        "risks": [],
        "url": "https://job-boards.greenhouse.io/acmeco/jobs/123",
        "resume_pdf": "/abs/r.pdf",
        "cl_pdf": "/abs/c.pdf",
        "cl_preview": "Hello AcmeCo, I am applying...",
        "unresolved": False,
    }
    s = format_card_section(card)
    assert s.startswith("## [A] AcmeCo — Senior PM\n")
    assert "Salary: $200,000-$240,000" in s
    assert "Archetype: product_management" in s
    assert "Lane: A" in s
    assert "Fit: Direct PM fit; strong AI tailwind." in s
    assert "Risks: (none flagged)" in s
    assert "JD: https://job-boards.greenhouse.io/acmeco/jobs/123" in s
    assert "Resume: /abs/r.pdf" in s
    assert "CL: /abs/c.pdf" in s
    assert "CL preview: \"Hello AcmeCo, I am applying...\"" in s
    assert "[ ] apply" in s
    assert "[ ] skip" in s


def test_format_card_section_unresolved_uses_strikethrough():
    card = {
        "grade": "B", "company": "Charlie Corp", "role": "PM",
        "salary": "", "archetype": "operations", "lane": "B",
        "fit": "", "risks": [],
        "url": "https://www.adzuna.com/details/4567",
        "resume_pdf": "/abs/r.pdf", "cl_pdf": "/abs/c.pdf",
        "cl_preview": "",
        "unresolved": True,
    }
    s = format_card_section(card)
    assert "URL unresolved" in s
    assert "~~[ ] apply~~" in s
    assert "~~[ ] skip~~" in s
    # No regular [ ] apply line for unresolved
    assert "\n- [ ] apply\n" not in s


def test_format_card_section_red_flags_joined_with_semicolons():
    card = {
        "grade": "B", "company": "X", "role": "Y",
        "salary": "", "archetype": "operations", "lane": "A",
        "fit": "", "risks": ["small team", "comp opaque"],
        "url": "https://example.com",
        "resume_pdf": "/r.pdf", "cl_pdf": "/c.pdf",
        "cl_preview": "",
        "unresolved": False,
    }
    s = format_card_section(card)
    assert "Risks: small team; comp opaque" in s


def test_format_triage_markdown_orders_A_before_B(manifest, scored):
    cards = extract_card_data(manifest, scored)
    md = format_triage_markdown(cards, date_str="2026-05-02",
                                manifest_path="pregenerated/2026-05-02-manifest.json")
    a_pos = md.find("## [A]")
    b_pos = md.find("## [B]")
    assert 0 < a_pos < b_pos


def test_format_triage_markdown_alphabetical_within_grade(manifest, scored):
    cards = extract_card_data(manifest, scored)
    md = format_triage_markdown(cards, date_str="2026-05-02",
                                manifest_path="pregenerated/2026-05-02-manifest.json")
    beta_pos = md.find("BetaInc")
    charlie_pos = md.find("Charlie Corp")
    assert 0 < beta_pos < charlie_pos


def test_format_triage_markdown_includes_counts_banner(manifest, scored):
    cards = extract_card_data(manifest, scored)
    md = format_triage_markdown(cards, date_str="2026-05-02",
                                manifest_path="pregenerated/2026-05-02-manifest.json")
    # "3 A/B cards · 1 unresolved"
    assert "3 A/B cards" in md
    assert "1 unresolved" in md


def test_format_triage_markdown_empty_cards():
    md = format_triage_markdown([], date_str="2026-05-02",
                                manifest_path="empty.json")
    assert "0 A/B cards" in md
    assert "Tick `[x] apply`" not in md or "no cards" in md.lower()
