"""Tests for cover-letter generator pure functions."""
from datetime import date
from pathlib import Path

from pipeline.cover_letter import (
    build_cl_output_path,
    render_cl_html,
    cl_artifact_exists,
)


def test_build_cl_output_path_basic():
    p = build_cl_output_path(
        company="Acme Co", role="Senior PM",
        full_name="Jared Hawkins", date_str="2026-04-22",
    )
    assert p.name == "Jared-Hawkins-Acme-Co-Senior-PM-2026-04-22.pdf"
    assert "cover_letters" in str(p)
    assert "output" in str(p)


def test_build_cl_output_path_defaults_to_today():
    p = build_cl_output_path(company="X", role="Y", full_name="Z")
    assert date.today().isoformat() in p.name


def test_build_cl_output_path_strips_punctuation():
    p = build_cl_output_path(
        company="A&B, Inc.", role="Sr. PM (AI)",
        full_name="Jared Hawkins", date_str="2026-04-22",
    )
    # Filesafe: no &, no comma, no parens, no period in role/company portions
    assert "&" not in p.name
    assert "," not in p.name


def test_render_cl_html_contains_prose_and_contact(source_minimal):
    html = render_cl_html(
        prose="Dear Acme team,\n\nI am excited to apply...\n\nThanks,\nJared",
        source=source_minimal,
        company="Acme",
        role="Senior PM",
        date_str="2026-04-22",
    )
    assert "I am excited to apply" in html
    assert "Jared Hawkins" in html
    assert "hawkins.jared@gmail.com" in html
    assert "Acme" in html
    assert "2026-04-22" in html or "April 22, 2026" in html


def test_render_cl_html_preserves_paragraphs(source_minimal):
    """Newlines in prose become <p> tags so the PDF lays out correctly."""
    html = render_cl_html(
        prose="Para one.\n\nPara two.\n\nPara three.",
        source=source_minimal,
        company="X", role="Y", date_str="2026-04-22",
    )
    assert html.count("<p>") >= 3


def test_cl_artifact_exists_returns_false_when_missing(tmp_path: Path):
    assert cl_artifact_exists(tmp_path / "nope.pdf") is False


def test_cl_artifact_exists_returns_true_when_present(tmp_path: Path):
    p = tmp_path / "yes.pdf"
    p.write_bytes(b"%PDF-stub")
    assert cl_artifact_exists(p) is True
