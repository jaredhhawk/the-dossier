"""Tests for cover-letter generator pure functions."""
from datetime import date
from pathlib import Path

import pytest

from pipeline.cover_letter import (
    _make_claude_cli_adapter,
    _make_default_adapter,
    _strip_markdown_fences,
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


@pytest.mark.parametrize("raw,expected", [
    # No fences — passthrough
    ("Just plain prose.\n\nSecond paragraph.", "Just plain prose.\n\nSecond paragraph."),
    # Triple-backtick wrap
    ("```\nProse content.\nMore.\n```", "Prose content.\nMore."),
    # Triple-backtick with language tag
    ("```text\nProse content.\nMore.\n```", "Prose content.\nMore."),
    # Trailing newline after closing fence
    ("```\nProse.\n```\n", "Prose."),
    # Leading whitespace before opening fence
    ("  ```\nProse.\n```", "Prose."),
    # Only closing fence, no opening (degenerate; leave fence alone)
    ("Prose.\n```", "Prose.\n```"),
    # Empty input
    ("", ""),
    # Just whitespace
    ("   \n  ", "   \n  "),
])
def test_strip_markdown_fences(raw, expected):
    assert _strip_markdown_fences(raw) == expected


def test_claude_cli_adapter_constructs_correct_argv(monkeypatch):
    """Verify the subprocess argv matches what `claude --print` expects."""
    captured = {}

    class FakeCompletedProcess:
        returncode = 0
        stdout = "Generated prose."
        stderr = ""

    def fake_run(argv, **kwargs):
        captured["argv"] = argv
        captured["kwargs"] = kwargs
        return FakeCompletedProcess()

    import pipeline.cover_letter as cl
    monkeypatch.setattr(cl.subprocess, "run", fake_run)

    adapter = _make_claude_cli_adapter()
    response = adapter.messages_create(
        model="claude-sonnet-4-6",
        max_tokens=1200,
        system=[{"type": "text", "text": "SYSTEM PROMPT", "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": "USER MESSAGE"}],
    )

    argv = captured["argv"]
    assert argv[0] == "claude"
    assert "--print" in argv
    tools_idx = argv.index("--tools")
    assert argv[tools_idx + 1] == ""
    assert "--no-session-persistence" in argv
    sysp_idx = argv.index("--system-prompt")
    assert argv[sysp_idx + 1] == "SYSTEM PROMPT"
    model_idx = argv.index("--model")
    assert argv[model_idx + 1] == "claude-sonnet-4-6"
    assert argv[-1] == "USER MESSAGE"

    assert captured["kwargs"]["capture_output"] is True
    assert captured["kwargs"]["text"] is True

    assert response.content[0].text == "Generated prose."


def test_claude_cli_adapter_strips_markdown_fences(monkeypatch):
    """Adapter applies _strip_markdown_fences to subprocess stdout."""
    class FakeCompletedProcess:
        returncode = 0
        stdout = "```\nFenced prose.\n```\n"
        stderr = ""

    def fake_run(argv, **kwargs):
        return FakeCompletedProcess()

    import pipeline.cover_letter as cl
    monkeypatch.setattr(cl.subprocess, "run", fake_run)

    adapter = _make_claude_cli_adapter()
    response = adapter.messages_create(
        model="m", max_tokens=100,
        system=[{"type": "text", "text": "S"}],
        messages=[{"role": "user", "content": "U"}],
    )
    assert response.content[0].text == "Fenced prose."


def test_claude_cli_adapter_raises_on_nonzero_exit(monkeypatch):
    """Subprocess failure becomes a RuntimeError with stderr in the message."""
    class FakeCompletedProcess:
        returncode = 1
        stdout = ""
        stderr = "claude: authentication failed"

    def fake_run(argv, **kwargs):
        return FakeCompletedProcess()

    import pipeline.cover_letter as cl
    monkeypatch.setattr(cl.subprocess, "run", fake_run)

    adapter = _make_claude_cli_adapter()
    with pytest.raises(RuntimeError, match="authentication failed"):
        adapter.messages_create(
            model="m", max_tokens=100,
            system=[{"type": "text", "text": "S"}],
            messages=[{"role": "user", "content": "U"}],
        )


def test_claude_cli_adapter_ignores_cache_control_field(monkeypatch):
    """The Anthropic-specific cache_control field is ignored — only the text matters."""
    captured = {}

    class FakeCompletedProcess:
        returncode = 0
        stdout = "ok"
        stderr = ""

    def fake_run(argv, **kwargs):
        captured["argv"] = argv
        return FakeCompletedProcess()

    import pipeline.cover_letter as cl
    monkeypatch.setattr(cl.subprocess, "run", fake_run)

    adapter = _make_claude_cli_adapter()
    adapter.messages_create(
        model="m", max_tokens=100,
        system=[{"type": "text", "text": "SYS", "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": "U"}],
    )
    argv = captured["argv"]
    assert "SYS" in argv
    argv_str = " ".join(argv)
    assert "cache_control" not in argv_str
    assert "ephemeral" not in argv_str


def test_make_default_adapter_returns_cli_when_env_unset(monkeypatch):
    monkeypatch.delenv("PIPELINE_CL_BACKEND", raising=False)
    import pipeline.cover_letter as cl

    class FakeCP:
        returncode = 0
        stdout = "ok"
        stderr = ""

    monkeypatch.setattr(cl.subprocess, "run", lambda *a, **k: FakeCP())

    adapter = _make_default_adapter()
    response = adapter.messages_create(
        model="m", max_tokens=10,
        system=[{"type": "text", "text": "S"}],
        messages=[{"role": "user", "content": "U"}],
    )
    assert response.content[0].text == "ok"


def test_make_default_adapter_returns_cli_when_env_explicit(monkeypatch):
    monkeypatch.setenv("PIPELINE_CL_BACKEND", "claude_cli")
    import pipeline.cover_letter as cl

    class FakeCP:
        returncode = 0
        stdout = "via cli"
        stderr = ""

    monkeypatch.setattr(cl.subprocess, "run", lambda *a, **k: FakeCP())

    adapter = _make_default_adapter()
    response = adapter.messages_create(
        model="m", max_tokens=10,
        system=[{"type": "text", "text": "S"}],
        messages=[{"role": "user", "content": "U"}],
    )
    assert response.content[0].text == "via cli"


def test_make_default_adapter_raises_on_unknown_backend(monkeypatch):
    monkeypatch.setenv("PIPELINE_CL_BACKEND", "openai")
    with pytest.raises(ValueError, match="PIPELINE_CL_BACKEND"):
        _make_default_adapter()
