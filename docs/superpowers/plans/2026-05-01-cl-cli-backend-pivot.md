# CL Generator: Claude Code CLI Backend Pivot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `claude --print` subprocess backend to `pipeline/cover_letter.py` so cover-letter generation bills against the user's Claude Max subscription instead of the Anthropic API. Make it the default backend, keep the Anthropic SDK adapter as an opt-in fallback. Then resume Task 8 smoke tests on the user's Max sub.

**Architecture:** New `_make_claude_cli_adapter()` exposes the same duck-typed `messages_create(**kwargs)` interface as the existing `_make_anthropic_adapter()`, so `generate_cl_text()` consumes either backend identically. A `_make_default_adapter()` dispatcher reads `PIPELINE_CL_BACKEND` env var (default `claude_cli`) to pick. Subprocess invocation: `claude --print --tools "" --no-session-persistence --system-prompt <text> --model <name> <user_text>`. Defensive markdown-fence stripping on response (model occasionally wraps prose in ```​ despite instructions). System prompt updated to forbid markdown. `pregenerate.py` switches its single adapter call site to the dispatcher.

**Tech Stack:** Python stdlib `subprocess`, `os`, `re`, `pytest` (subprocess.run mocked via monkeypatch). No new dependencies.

**Spec source:** This plan document (mid-execution mini-plan; the parent Plan 1 is `2026-05-01-apply-flow-v1-cl-pdf-pregeneration.md`).

**Worktree:** `/Users/jhh/code/the-dossier-poc/` on branch `feat/apply-flow-v1`. Last commit before this plan: `359d123` (Task 8 orchestration). Tree should be clean before starting.

---

## Pre-flight notes (resolved)

- **CLI verified working:** `claude --print --system-prompt "..." --tools "" --no-session-persistence "user message"` exits 0 cleanly, stdout is just the response, stderr empty, ~13s per call. Default mode uses Max sub (no API key needed). `--bare` would force ANTHROPIC_API_KEY auth — DO NOT use `--bare`.
- **Code-fence quirk:** the smoke test produced output wrapped in ` ``` ` markdown fences. Mitigation: (a) update `CL_SYSTEM_TEMPLATE` to explicitly forbid markdown formatting, (b) defensively strip leading/trailing fences in the adapter regardless.
- **Model selection:** `--model claude-sonnet-4-6` works. Default if `PIPELINE_CL_MODEL` unset: `claude-sonnet-4-6` (existing constant `DEFAULT_CL_MODEL`). Apply same precedence (explicit arg > env > default) as the Anthropic backend.
- **Backend selection:** env var `PIPELINE_CL_BACKEND` only. Values: `claude_cli` (default), `anthropic_sdk`. Anything else → ValueError with helpful message.
- **`generate_cl_text` signature unchanged.** Existing tests pass without modification. The `system` arg shape (list of blocks with `cache_control`) is Anthropic-SDK-specific; the CLI adapter ignores `cache_control` and serializes only the `text` field of the first block.
- **Tests are subprocess-free.** All new tests use `monkeypatch.setattr(subprocess, "run", ...)` to inject a fake. No real `claude` invocation in pytest.

---

## File Structure

**Modify:**
- `pipeline/cover_letter.py` — add `_make_claude_cli_adapter`, `_make_default_adapter`, `_strip_markdown_fences`; update `CL_SYSTEM_TEMPLATE`; update `_make_anthropic_adapter` docstring TODO (mark swap as done).
- `pipeline/pregenerate.py:318-319` — swap `_make_anthropic_adapter` call for `_make_default_adapter`.
- `pipeline/tests/test_cover_letter.py` — add 5 new tests for CLI adapter, dispatcher, fence stripping.

**Update (memory, outside the worktree):**
- `~/.claude/projects/-Users-jhh-Documents-Second-Brain/memory/project_pipeline_cl_cost_followup.md` — mark "shipped during Task 8" instead of deferred.

**Out of scope:**
- README docs — covered by Task 9 of parent Plan 1.
- Standalone `cover_letter.py` CLI — picks up the dispatcher automatically; no flag changes needed.
- Cron environment — covered by Task 9 of parent Plan 1.

---

## Test Strategy

5 new pytest tests covering the new code paths, all using subprocess mocking. The existing 13 cover-letter tests remain unchanged and must still pass.

**What's tested:**
- `_make_claude_cli_adapter` returns an object with a working `messages_create` method
- The adapter constructs the right `subprocess.run` argv (flags, system prompt, model, user message)
- The adapter parses subprocess stdout into the expected `response.content[0].text` shape
- The adapter strips leading/trailing markdown code fences when the model adds them
- The adapter raises `RuntimeError` (with `from e`) on non-zero subprocess exit
- `_make_default_adapter()` returns a CLI adapter when `PIPELINE_CL_BACKEND` unset OR set to `claude_cli`
- `_make_default_adapter()` returns the Anthropic adapter when `PIPELINE_CL_BACKEND=anthropic_sdk`
- `_make_default_adapter()` raises ValueError on unknown backend value

**What's NOT tested (manual smoke):**
- A real `claude --print` invocation. That happens during the Task 8 smoke tests after this plan ships.

**Test invocation:**
```bash
cd ~/code/the-dossier-poc && ~/code/the-dossier/pipeline/.venv/bin/python3 -m pytest pipeline/tests/test_cover_letter.py -v
```
Expected: 13 existing PASS + 5 new PASS = 18 PASS.

---

## Tasks

### Task 1: Update CL_SYSTEM_TEMPLATE to forbid markdown formatting

**Files:**
- Modify: `pipeline/cover_letter.py:147-165` (CL_SYSTEM_TEMPLATE)

- [ ] **Step 1: Edit the template**

In `pipeline/cover_letter.py`, find the `CL_SYSTEM_TEMPLATE` rule that starts with `- Output plain text only.` (currently line 163) and replace that single rule with two rules:

```
- Output plain text only. Do not use HTML tags or HTML entities (the rendering layer escapes everything; HTML in your output will appear as literal escaped text in the PDF).
- Do not wrap your response in markdown code fences (```), backticks, or any other markdown formatting. Output bare prose only.
```

The two new rules replace the one existing rule. The rest of the template stays unchanged.

- [ ] **Step 2: Run tests to confirm no regression**

```bash
cd ~/code/the-dossier-poc && ~/code/the-dossier/pipeline/.venv/bin/python3 -m pytest pipeline/tests/test_cover_letter.py -v
```
Expected: 13 PASSED. None of the existing tests pin the exact template content; they assert structure (system block is invariant across calls, contains the bio, etc.).

- [ ] **Step 3: Commit**

```bash
cd ~/code/the-dossier-poc && git add pipeline/cover_letter.py
git commit -m "feat(cover-letter): forbid markdown code fences in CL system prompt"
```

---

### Task 2: Add `_strip_markdown_fences` helper + tests

A defensive post-processing step. The system prompt forbids markdown, but LLMs ignore instructions sometimes. Strip leading/trailing ` ``` ` lines if present, leave inner content untouched.

**Files:**
- Modify: `pipeline/cover_letter.py` — add `_strip_markdown_fences` (private helper)
- Modify: `pipeline/tests/test_cover_letter.py` — add 1 test (parametrized internally for multiple inputs)

- [ ] **Step 1: Write the failing test**

Append to `pipeline/tests/test_cover_letter.py`:

```python
import pytest

from pipeline.cover_letter import _strip_markdown_fences


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
```

- [ ] **Step 2: Run, confirm fail**

```bash
cd ~/code/the-dossier-poc && ~/code/the-dossier/pipeline/.venv/bin/python3 -m pytest pipeline/tests/test_cover_letter.py::test_strip_markdown_fences -v
```
Expected: ImportError on `_strip_markdown_fences` (collection failure).

- [ ] **Step 3: Implement the helper**

Add to `pipeline/cover_letter.py`, in a logical location near `_prose_to_paragraphs` (which is also a private string helper). Suggest placing it just before `_prose_to_paragraphs` (around line 104):

```python
def _strip_markdown_fences(s: str) -> str:
    """Remove leading/trailing ``` markdown code fences if present.

    LLM occasionally wraps prose in markdown code blocks despite system-prompt
    instructions. Strips a single opening fence (with optional language tag)
    at the start and a single closing fence at the end. Leaves inner content
    untouched. Pass-through for unfenced input.
    """
    stripped = s.strip()
    if not stripped:
        return s  # preserve original whitespace if input was just whitespace
    # Match opening fence: optional whitespace, then ``` optionally followed by
    # a language tag, then a newline. Match closing fence: a newline, then ```,
    # then optional trailing whitespace at end of string.
    opening = re.match(r"^```\w*\n", stripped)
    closing = re.search(r"\n```\s*$", stripped)
    if opening and closing:
        return stripped[opening.end():closing.start()]
    return s
```

- [ ] **Step 4: Run tests, confirm pass**

```bash
cd ~/code/the-dossier-poc && ~/code/the-dossier/pipeline/.venv/bin/python3 -m pytest pipeline/tests/test_cover_letter.py::test_strip_markdown_fences -v
```
Expected: 8 parametrized cases PASS.

- [ ] **Step 5: Run the full cover-letter test file to confirm no regression**

```bash
cd ~/code/the-dossier-poc && ~/code/the-dossier/pipeline/.venv/bin/python3 -m pytest pipeline/tests/test_cover_letter.py -v
```
Expected: 13 + 8 (parametrized count as 8) = 21 PASSED.

- [ ] **Step 6: Commit**

```bash
cd ~/code/the-dossier-poc && git add pipeline/cover_letter.py pipeline/tests/test_cover_letter.py
git commit -m "feat(cover-letter): add _strip_markdown_fences defensive post-processor"
```

---

### Task 3: Implement `_make_claude_cli_adapter` + tests

The new backend. Constructs the right `subprocess.run` invocation, parses stdout, applies `_strip_markdown_fences`, raises RuntimeError on subprocess failure.

**Files:**
- Modify: `pipeline/cover_letter.py` — add `_make_claude_cli_adapter`
- Modify: `pipeline/tests/test_cover_letter.py` — add 4 tests

- [ ] **Step 1: Write the failing tests**

Append to `pipeline/tests/test_cover_letter.py`:

```python
from pipeline.cover_letter import _make_claude_cli_adapter


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

    # Verify argv shape
    argv = captured["argv"]
    assert argv[0] == "claude"
    assert "--print" in argv
    assert "--tools" in argv
    # --tools "" must be passed as two separate argv entries: "--tools", ""
    tools_idx = argv.index("--tools")
    assert argv[tools_idx + 1] == ""
    assert "--no-session-persistence" in argv
    assert "--system-prompt" in argv
    sysp_idx = argv.index("--system-prompt")
    assert argv[sysp_idx + 1] == "SYSTEM PROMPT"
    assert "--model" in argv
    model_idx = argv.index("--model")
    assert argv[model_idx + 1] == "claude-sonnet-4-6"
    # User message is the last positional arg
    assert argv[-1] == "USER MESSAGE"

    # Verify subprocess.run kwargs
    assert captured["kwargs"]["capture_output"] is True
    assert captured["kwargs"]["text"] is True
    # check=False because we want to inspect returncode ourselves and raise
    # RuntimeError with stderr context (test_claude_cli_adapter_raises_on_failure)

    # Verify response shape — duck-typed to match Anthropic SDK
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
    # Argv should contain SYS but NOT any cache_control serialization
    argv = captured["argv"]
    assert "SYS" in argv
    argv_str = " ".join(argv)
    assert "cache_control" not in argv_str
    assert "ephemeral" not in argv_str
```

- [ ] **Step 2: Run, confirm fail**

```bash
cd ~/code/the-dossier-poc && ~/code/the-dossier/pipeline/.venv/bin/python3 -m pytest pipeline/tests/test_cover_letter.py -k "claude_cli_adapter" -v
```
Expected: 4 collection errors (ImportError on `_make_claude_cli_adapter`).

- [ ] **Step 3: Implement `_make_claude_cli_adapter`**

First, add `import subprocess` to the top-level imports of `pipeline/cover_letter.py` (after `import re`, before `import sys`):

```python
import html
import os
import re
import subprocess
import sys
```

Then add `_make_claude_cli_adapter` immediately after `_make_anthropic_adapter` (so the two backends sit side-by-side):

```python
def _make_claude_cli_adapter():
    """Wrap the `claude --print` subprocess so generation bills against the user's
    Claude Max subscription instead of the Anthropic API.

    Returns an object with `messages_create(**kwargs)` matching the duck-typed
    contract used by `generate_cl_text`. Anthropic-specific fields (cache_control)
    are ignored — only the raw system text and user message flow through.

    Raises RuntimeError on non-zero subprocess exit (with stderr in the message).
    """
    class Adapter:
        def messages_create(self, **kwargs):
            system_blocks = kwargs.get("system", [])
            system_text = system_blocks[0]["text"] if system_blocks else ""
            messages = kwargs.get("messages", [])
            user_text = messages[0]["content"] if messages else ""
            model = kwargs.get("model", DEFAULT_CL_MODEL)

            argv = [
                "claude",
                "--print",
                "--tools", "",
                "--no-session-persistence",
                "--system-prompt", system_text,
                "--model", model,
                user_text,
            ]
            result = subprocess.run(
                argv, capture_output=True, text=True, check=False,
            )
            if result.returncode != 0:
                raise RuntimeError(
                    f"claude --print failed (exit {result.returncode}): "
                    f"{result.stderr.strip() or '<no stderr>'}"
                )

            text = _strip_markdown_fences(result.stdout)

            # Mimic the Anthropic SDK response shape that generate_cl_text expects.
            class _Block:
                def __init__(self, t): self.text = t
            class _Response:
                def __init__(self, t): self.content = [_Block(t)]
            return _Response(text)

    return Adapter()
```

- [ ] **Step 4: Run tests, confirm pass**

```bash
cd ~/code/the-dossier-poc && ~/code/the-dossier/pipeline/.venv/bin/python3 -m pytest pipeline/tests/test_cover_letter.py -k "claude_cli_adapter" -v
```
Expected: 4 PASSED.

- [ ] **Step 5: Run the full cover-letter test file**

```bash
cd ~/code/the-dossier-poc && ~/code/the-dossier/pipeline/.venv/bin/python3 -m pytest pipeline/tests/test_cover_letter.py -v
```
Expected: 25 PASSED (13 original + 8 parametrized fence-strip cases + 4 CLI adapter).

- [ ] **Step 6: Commit**

```bash
cd ~/code/the-dossier-poc && git add pipeline/cover_letter.py pipeline/tests/test_cover_letter.py
git commit -m "feat(cover-letter): add Claude Code CLI subprocess backend"
```

---

### Task 4: Add `_make_default_adapter` dispatcher + tests

The single entry point that picks a backend based on `PIPELINE_CL_BACKEND`. Default `claude_cli`.

**Files:**
- Modify: `pipeline/cover_letter.py` — add `_make_default_adapter`
- Modify: `pipeline/tests/test_cover_letter.py` — add 3 tests

- [ ] **Step 1: Write the failing tests**

Append to `pipeline/tests/test_cover_letter.py`:

```python
from pipeline.cover_letter import _make_default_adapter


def test_make_default_adapter_returns_cli_when_env_unset(monkeypatch):
    monkeypatch.delenv("PIPELINE_CL_BACKEND", raising=False)
    # Patch subprocess so the adapter doesn't try to actually invoke claude
    import pipeline.cover_letter as cl

    class FakeCP:
        returncode = 0
        stdout = "ok"
        stderr = ""

    monkeypatch.setattr(cl.subprocess, "run", lambda *a, **k: FakeCP())

    adapter = _make_default_adapter()
    # Verify it's the CLI adapter by exercising it and checking the duck-typed shape works
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
```

We deliberately do NOT test the `anthropic_sdk` branch in pytest (it would require either installing anthropic OR mocking the import — both add noise for marginal value). The Anthropic adapter has its own existing tests; the dispatcher is a 5-line if/elif/else and the unknown-backend branch is the only behavior worth pinning.

- [ ] **Step 2: Run, confirm fail**

```bash
cd ~/code/the-dossier-poc && ~/code/the-dossier/pipeline/.venv/bin/python3 -m pytest pipeline/tests/test_cover_letter.py -k "make_default_adapter" -v
```
Expected: 3 collection errors (ImportError on `_make_default_adapter`).

- [ ] **Step 3: Implement `_make_default_adapter`**

Add to `pipeline/cover_letter.py` immediately after `_make_claude_cli_adapter`:

```python
def _make_default_adapter():
    """Pick the backend per PIPELINE_CL_BACKEND env var (default: claude_cli).

    Values:
      - "claude_cli" (default): subprocess to `claude --print`. Uses Max sub.
      - "anthropic_sdk": Anthropic SDK. Requires ANTHROPIC_API_KEY env var.

    Raises ValueError on any other value. Callers (CLI entry points) should
    catch RuntimeError from the underlying adapter constructors and convert
    to a user-facing exit.
    """
    backend = os.environ.get("PIPELINE_CL_BACKEND", "claude_cli")
    if backend == "claude_cli":
        return _make_claude_cli_adapter()
    if backend == "anthropic_sdk":
        return _make_anthropic_adapter()
    raise ValueError(
        f"PIPELINE_CL_BACKEND={backend!r} is not recognized. "
        f"Valid values: 'claude_cli' (default), 'anthropic_sdk'."
    )
```

- [ ] **Step 4: Run tests, confirm pass**

```bash
cd ~/code/the-dossier-poc && ~/code/the-dossier/pipeline/.venv/bin/python3 -m pytest pipeline/tests/test_cover_letter.py -k "make_default_adapter" -v
```
Expected: 3 PASSED.

- [ ] **Step 5: Run the full cover-letter test file**

```bash
cd ~/code/the-dossier-poc && ~/code/the-dossier/pipeline/.venv/bin/python3 -m pytest pipeline/tests/test_cover_letter.py -v
```
Expected: 28 PASSED (13 original + 8 fence + 4 CLI + 3 dispatcher).

- [ ] **Step 6: Commit**

```bash
cd ~/code/the-dossier-poc && git add pipeline/cover_letter.py pipeline/tests/test_cover_letter.py
git commit -m "feat(cover-letter): add backend dispatcher with PIPELINE_CL_BACKEND env var"
```

---

### Task 5: Wire `pregenerate.py` to use the dispatcher

One-line swap. The existing import + call at lines 318-319 changes from `_make_anthropic_adapter` to `_make_default_adapter`.

**Files:**
- Modify: `pipeline/pregenerate.py:318-319`

- [ ] **Step 1: Apply the swap**

In `pipeline/pregenerate.py`, find lines 318-319:

```python
    from pipeline.cover_letter import _make_anthropic_adapter
    anthropic_client = _make_anthropic_adapter()
```

Replace with:

```python
    from pipeline.cover_letter import _make_default_adapter
    anthropic_client = _make_default_adapter()
```

(The local variable is still named `anthropic_client` for now — renaming it across `process_card` and `generate_cl_for_card` signatures would be a churn-y diff for negligible clarity gain. Future cleanup if anyone cares; leave it.)

- [ ] **Step 2: Run the full test suite to confirm no regression**

```bash
cd ~/code/the-dossier-poc && ~/code/the-dossier/pipeline/.venv/bin/python3 -m pytest pipeline/tests/ -v
```
Expected: all tests PASS (~32 total — 28 cover-letter + 2 pdf_render + 3 resume_paths + 9 pregenerate − any overlap. Actual count: pdf_render 2 + resume_paths 3 + cover_letter 28 + pregenerate 9 = 42 — wait, that's wrong. Re-count: cover_letter has 13 from prior tasks + 8 parametrized fence + 4 CLI adapter + 3 dispatcher = 28; total = 2+3+28+9 = **42 tests**.)

If pytest reports a different number, double-check that test counts include the parametrized expansion (each `@pytest.mark.parametrize` case counts as one test).

- [ ] **Step 3: Commit**

```bash
cd ~/code/the-dossier-poc && git add pipeline/pregenerate.py
git commit -m "refactor(pregenerate): use _make_default_adapter dispatcher"
```

---

### Task 6: Update `_make_anthropic_adapter` docstring (mark swap as shipped)

Cleanup step. The TODO in the docstring currently says "post-Plan 1 follow-up." That's no longer true.

**Files:**
- Modify: `pipeline/cover_letter.py` — `_make_anthropic_adapter` docstring (currently lines 230-244)

- [ ] **Step 1: Edit the docstring**

In `pipeline/cover_letter.py`, find `_make_anthropic_adapter`'s docstring. Replace the entire `TODO (post-Plan 1):` block with:

```python
def _make_anthropic_adapter():
    """Anthropic SDK backend. Opt-in via PIPELINE_CL_BACKEND=anthropic_sdk.

    Default backend is now `_make_claude_cli_adapter` (see `_make_default_adapter`).
    The Anthropic SDK path remains available as an escape hatch when the Max
    subscription is unavailable, rate-limited, or for users who prefer API billing.

    Raises RuntimeError if the anthropic package isn't installed. Callers
    (CLI entry points) should catch and convert to a user-facing exit.
    """
```

- [ ] **Step 2: Run tests to confirm no regression (docstring change only)**

```bash
cd ~/code/the-dossier-poc && ~/code/the-dossier/pipeline/.venv/bin/python3 -m pytest pipeline/tests/test_cover_letter.py -v
```
Expected: 28 PASSED (no change from Task 5).

- [ ] **Step 3: Commit**

```bash
cd ~/code/the-dossier-poc && git add pipeline/cover_letter.py
git commit -m "docs(cover-letter): mark Claude CLI backend as shipped (no longer post-Plan-1 TODO)"
```

---

### Task 7: Manual smoke test of the CLI adapter end-to-end (no API)

Confirm the wiring actually works by invoking pregenerate.py with `--limit 1` against the real scored data. This uses the user's Max sub. Expected: ~13 seconds, no API charge, valid CL PDF produced.

This is the moment of truth — if the CLI adapter has a bug not caught by mocked tests (e.g., a flag name typo, an argv-quoting issue), it surfaces here.

**Files:**
- (none modified; this is verification only)

- [ ] **Step 1: Verify the `claude` binary is on PATH and authenticated**

```bash
which claude && claude --version
```
Expected: prints a path and a version string. If `claude: command not found`, install Claude Code first.

```bash
echo "test" | claude --print --tools "" --no-session-persistence "say hi" 2>&1 | head -3
```
Expected: a brief response from Claude. If you get an auth prompt or login error, run `claude` interactively once first to authenticate.

- [ ] **Step 2: Confirm tree is clean**

```bash
cd ~/code/the-dossier-poc && git status
```
Expected: clean working tree.

- [ ] **Step 3: Run pregenerate `--limit 1` against real scored data**

```bash
cd ~/code/the-dossier-poc && ~/code/the-dossier/pipeline/.venv/bin/python3 -m pipeline.pregenerate \
  --scored-file /Users/jhh/code/the-dossier/pipeline/data/scored/2026-04-22.json --limit 1
```
Expected:
- Stdout shows `[pregenerate] scored=2026-04-22.json date=2026-04-22`, `[pregenerate] grades=('A', 'B') candidates=1` (with `--limit 1`), then `(1/1) <grade> | <company> | <title>`, then `→ generated`, then `[pregenerate] manifest: ...` and `[pregenerate] done: generated=1 cached=0 failed=0`.
- Wall time ~15-20s (CL gen via CLI is ~13s + resume render ~2-3s + IO).
- Exit code 0.
- No mention of API key or Anthropic SDK errors.
- A real CL PDF lands at `~/code/the-dossier-poc/pipeline/data/cover_letters/output/Jared-Hawkins-*.pdf`.

If the run fails with a `claude` auth error, stop and surface the error — there's an environment issue, not a code issue.

If the run fails with a Python error in the adapter, that's a real bug — capture the traceback, escalate.

- [ ] **Step 4: Inspect the generated CL**

```bash
ls -la ~/code/the-dossier-poc/pipeline/data/cover_letters/output/Jared-Hawkins-*.pdf
file ~/code/the-dossier-poc/pipeline/data/cover_letters/output/Jared-Hawkins-*.pdf
```
Expected: a single new PDF, `file` reports `PDF document, version 1.4` (or similar).

If you want to eyeball the prose quality, open the PDF:
```bash
open ~/code/the-dossier-poc/pipeline/data/cover_letters/output/Jared-Hawkins-*.pdf
```
Look for: real prose (not literal markdown fences in the body), correct addressee, no banned words.

- [ ] **Step 5: Inspect the manifest**

```bash
cat ~/code/the-dossier-poc/pipeline/data/pregenerated/2026-04-22-manifest.json | head -30
```
Expected: `counts.generated == 1`, `counts.cached == 0`, `counts.failures == 0`. The single entry has `resume_pdf`, `cl_pdf`, `jd_cache` paths all under `~/code/the-dossier-poc/pipeline/data/...`.

- [ ] **Step 6: Re-run to verify idempotency**

```bash
cd ~/code/the-dossier-poc && ~/code/the-dossier/pipeline/.venv/bin/python3 -m pipeline.pregenerate \
  --scored-file /Users/jhh/code/the-dossier/pipeline/data/scored/2026-04-22.json --limit 1
```
Expected: `→ cached`. Manifest counts.cached == 1, counts.generated == 0. **No `claude` invocation made.** Wall time should be sub-second (just file existence checks + manifest write).

- [ ] **Step 7: Re-run with `--force`**

```bash
cd ~/code/the-dossier-poc && ~/code/the-dossier/pipeline/.venv/bin/python3 -m pipeline.pregenerate \
  --scored-file /Users/jhh/code/the-dossier/pipeline/data/scored/2026-04-22.json --limit 1 --force
```
Expected: `→ generated`, ~15-20s wall time again, new `claude` invocation. PDF mtime updates.

- [ ] **Step 8: Verify scored JSON mutation**

```bash
python3 -c "
import json
with open('/Users/jhh/code/the-dossier/pipeline/data/scored/2026-04-22.json') as f:
    cards = json.load(f)
with_art = [c for c in cards if 'artifacts' in c]
print(f'cards with artifacts: {len(with_art)}')
if with_art:
    print(json.dumps(with_art[0]['artifacts'], indent=2))
"
```
Expected: at least 1 card with `artifacts` field containing 3 path keys.

- [ ] **Step 9: No commit — this is verification only**

If everything in Steps 3-8 passed, this plan's core deliverable (Task 8 smoke tests on Max sub) is verified. Move to Task 8.

If any step failed, do NOT proceed. Report the failure with full output so we can diagnose.

---

### Task 8: Update memory + close out

Final cleanup. Mark the post-Plan-1 follow-up as shipped during Plan 1.

**Files:**
- Modify: `~/.claude/projects/-Users-jhh-Documents-Second-Brain/memory/project_pipeline_cl_cost_followup.md`

- [ ] **Step 1: Update the memory file**

Replace the file's content with:

```markdown
---
name: Pipeline CL generator — Claude CLI backend (shipped)
description: Cover-letter generation defaults to claude --print subprocess, billing against Max sub instead of API. Anthropic SDK remains opt-in via PIPELINE_CL_BACKEND=anthropic_sdk.
type: project
---

**Status: SHIPPED 2026-05-01** during Plan 1 Task 8 mid-execution pivot. Mini-plan: `~/code/the-dossier-poc/docs/superpowers/plans/2026-05-01-cl-cli-backend-pivot.md`.

`pipeline/cover_letter.py` now exposes two backends behind a `_make_default_adapter()` dispatcher:
- **`claude_cli`** (default): subprocess to `claude --print --tools "" --no-session-persistence --system-prompt <text> --model <name> <user_text>`. Uses Claude Max sub auth. ~13s per call. Defensive markdown-fence stripping on response.
- **`anthropic_sdk`** (opt-in via `PIPELINE_CL_BACKEND=anthropic_sdk`): the original Anthropic SDK path. Requires `ANTHROPIC_API_KEY`. Kept as escape hatch for when Max is down/rate-limited.

`PIPELINE_CL_MODEL` env var continues to select the model for both backends (default `claude-sonnet-4-6`).

`pregenerate.py` uses the dispatcher at line 318-319 (variable still named `anthropic_client` — cosmetic, not worth the diff churn to rename).

**Operator README (Task 9 of Plan 1) should document:**
- `PIPELINE_CL_BACKEND={claude_cli|anthropic_sdk}` env var
- `PIPELINE_CL_MODEL=<model>` env var
- Cron environment needs `claude` on PATH (or `ANTHROPIC_API_KEY` exported if using `anthropic_sdk` backend)
- Subprocess auth requires user to have run `claude` interactively at least once

**Tradeoffs as observed:**
- ~13s per call vs ~1s API. For a 38-card batch: ~8 min CLI vs ~38s API.
- No prompt-cache observability under CLI mode (CC does its own caching internally).
- Subprocess test mocking pattern (monkeypatch `subprocess.run`) is heavier than the duck-typed FakeClient pattern but still entirely network-free.
```

- [ ] **Step 2: Verify the index pointer in `MEMORY.md` is still accurate**

```bash
grep -n "CL cost follow-up\|cl_cost_followup" ~/.claude/projects/-Users-jhh-Documents-Second-Brain/memory/MEMORY.md
```

If the index entry still says "TODO comment in code" or anything pre-shipping, update it to reflect the shipped state. Suggested replacement:

In `~/.claude/projects/-Users-jhh-Documents-Second-Brain/memory/MEMORY.md`, find the line containing `project_pipeline_cl_cost_followup.md` and replace with:

```
- [Pipeline CL backend](project_pipeline_cl_cost_followup.md) — Shipped 2026-05-01. Default backend is `claude --print` subprocess (Max sub). `PIPELINE_CL_BACKEND=anthropic_sdk` for SDK fallback.
```

- [ ] **Step 3: No git commit**

Memory files live outside the worktree and are not tracked by the project's git repo. They're a personal cross-conversation persistence layer.

---

## Plan-completion criteria

Before declaring this mini-plan done, all of these must be true:

- [ ] All pytest tests pass (full suite: ~42 tests across 4 files)
- [ ] CL_SYSTEM_TEMPLATE forbids markdown formatting
- [ ] `_strip_markdown_fences` exists with unit-test coverage of edge cases
- [ ] `_make_claude_cli_adapter` exists with subprocess-mock test coverage
- [ ] `_make_default_adapter` dispatches on `PIPELINE_CL_BACKEND` env var, defaults to `claude_cli`
- [ ] `pregenerate.py` calls `_make_default_adapter`
- [ ] Manual smoke test (Task 7): real `pregenerate.py --limit 1` invocation succeeds via Max sub, produces valid CL PDF, idempotent on re-run, regenerates with --force
- [ ] Memory file marks the follow-up as shipped

## Hand-off back to Plan 1

After this mini-plan ships, return to **Plan 1, Task 8** and consider Steps 3-6 already complete (covered by this plan's Task 7). Proceed to Plan 1, Task 9 (Operator README), making sure the README covers `PIPELINE_CL_BACKEND` and the auth requirement (user must have run `claude` interactively at least once for cron to work).
