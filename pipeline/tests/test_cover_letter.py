"""Tests for cover-letter generator pure functions."""
from datetime import date
from pathlib import Path

from pipeline.cover_letter import (
    build_cl_output_path,
    build_cl_prompt,
    cl_artifact_exists,
    generate_cl_text,
    render_cl_html,
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


def test_render_cl_html_escapes_prose_metacharacters(source_minimal):
    """Untrusted prose containing HTML metacharacters must be escaped, not injected."""
    html_out = render_cl_html(
        prose='Para with <script>alert(1)</script> & ampersand.',
        source=source_minimal,
        company="X", role="Y", date_str="2026-04-22",
    )
    assert "&lt;script&gt;" in html_out
    assert "&amp;" in html_out
    assert "<script>" not in html_out, "raw <script> tag leaked into output"


def test_render_cl_html_escapes_company_and_role(source_minimal):
    """Company and role flow into the template; metacharacters must be escaped."""
    html_out = render_cl_html(
        prose="Body.",
        source=source_minimal,
        company="A&B <Inc>", role="PM <Senior>", date_str="2026-04-22",
    )
    assert "A&amp;B &lt;Inc&gt;" in html_out
    assert "PM &lt;Senior&gt;" in html_out
    assert "<Inc>" not in html_out
    assert "<Senior>" not in html_out


def test_build_cl_prompt_contains_jd_company_role(source_minimal):
    archetype_template = {
        "headline": "Principal PM | AI Systems",
        "summary_variant": "product_management",
    }
    p = build_cl_prompt(
        source=source_minimal,
        archetype_template=archetype_template,
        company="Acme",
        role="Senior PM",
        jd_text="Acme is hiring a Senior PM to lead our platform team.",
    )
    # System prompt — cacheable
    assert "system" in p
    assert "Senior PM with 10 years" in p["system"]  # bio summary
    # User prompt — varies per card
    assert "user" in p
    assert "Acme" in p["user"]
    assert "Senior PM" in p["user"]
    assert "lead our platform team" in p["user"]
    assert "Principal PM | AI Systems" in p["user"] or "Principal PM" in p["system"]


def test_build_cl_prompt_marks_system_block_for_caching(source_minimal):
    """System block must be returned in the shape Anthropic SDK accepts for prompt caching."""
    p = build_cl_prompt(
        source=source_minimal,
        archetype_template={"headline": "X", "summary_variant": "product_management"},
        company="Acme", role="PM", jd_text="...",
    )
    # We document the contract: system is a string we'll wrap with cache_control
    # at call time. Test that it's stable (same input → same output).
    p2 = build_cl_prompt(
        source=source_minimal,
        archetype_template={"headline": "X", "summary_variant": "product_management"},
        company="DifferentCompany", role="DifferentRole", jd_text="different",
    )
    assert p["system"] == p2["system"], "System block must not vary per-card (breaks prompt caching)"


def test_generate_cl_text_uses_injected_client(source_minimal):
    """Client injection lets tests skip the network."""
    class FakeClient:
        def __init__(self):
            self.calls = []

        def messages_create(self, **kwargs):
            self.calls.append(kwargs)
            class Msg:
                content = [type("Block", (), {"text": "Dear Acme,\n\nI am applying...\n\nBest,\nJared"})()]
            return Msg()

    fake = FakeClient()
    text = generate_cl_text(
        prompt={"system": "S", "user": "U"},
        client=fake,
        model="claude-sonnet-4-6",
    )
    assert "I am applying" in text
    assert len(fake.calls) == 1
    # Confirms model + system + user passed through; cache_control on system block
    assert fake.calls[0]["model"] == "claude-sonnet-4-6"
    # System block must be the cacheable list-of-blocks shape
    assert isinstance(fake.calls[0]["system"], list)
    assert fake.calls[0]["system"][0].get("cache_control") == {"type": "ephemeral"}


def test_generate_cl_text_respects_env_var_when_no_model_arg(source_minimal, monkeypatch):
    """PIPELINE_CL_MODEL env var overrides the default when no model arg is passed."""
    class FakeClient:
        def __init__(self):
            self.calls = []

        def messages_create(self, **kwargs):
            self.calls.append(kwargs)
            class Msg:
                content = [type("Block", (), {"text": "x"})()]
            return Msg()

    monkeypatch.setenv("PIPELINE_CL_MODEL", "claude-test-model-id")
    fake = FakeClient()
    generate_cl_text(prompt={"system": "S", "user": "U"}, client=fake)
    assert fake.calls[0]["model"] == "claude-test-model-id"
