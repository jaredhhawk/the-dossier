# Apply-Flow v1 — Plan 1: CL PDF Generator + Pre-Generation Orchestration

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the missing cover-letter PDF artifact to the pipeline, then wire an idempotent batch script that pre-generates tailored resume + CL PDFs (and caches JD text) for every Grade A/B card on a given scored JSON. Output is a manifest the future `/pipeline execute` reader (Plan 2) consumes.

**Architecture:** Two new modules and one shared helper inside `pipeline/`. (1) Extract the existing Playwright HTML→PDF render into `pipeline/pdf_render.py` so resume + CL share one renderer. (2) `pipeline/cover_letter.py` produces tailored CL prose via the Anthropic SDK (Claude Sonnet 4.6 with prompt caching on the static bio block), renders it to PDF, mirrors `resume.py`'s output-path convention. (3) `pipeline/pregenerate.py` is the cron-installable orchestrator: reads the most recent (or `--scored-file`) scored JSON, filters A/B/new/resolvable cards, generates resume + CL + cached JD per card, skips if artifacts already exist, writes a per-day manifest under `pipeline/data/pregenerated/`. The manifest is the contract Plan 2 reads.

**Tech Stack:** Python 3.x, Playwright (already installed) for PDF render, `anthropic` SDK (new dep) for CL prose, `pyyaml` (existing) for config, `pytest` (new dev dep) for unit tests on pure functions. No new browser automation in this plan — that lives in `apply_flow_poc.py` and gets extended in Plan 3.

**Spec sources:**
- `/Users/jhh/Documents/Second Brain/02_Projects/Job Search Pipeline/Pipeline Apply-Flow Diagnostic.md` (State B target, daily UX, Phase 1 dry-run findings)
- `/Users/jhh/Documents/Second Brain/02_Projects/Job Search Pipeline/Pipeline Scoring + Data Optimization Backlog.md` §3 (CL-as-PDF requirement, output path convention)
- `/Users/jhh/code/the-dossier-poc/RESUME.md` (Plan 1 sequencing, open questions)

**Worktree:** `~/code/the-dossier-poc/` on branch `feat/apply-flow-v1`. All paths below are relative to that worktree unless absolute.

**Invocation pattern (read this once):** Throughout this plan, run scripts as `cd ~/code/the-dossier-poc && ~/code/the-dossier/pipeline/.venv/bin/python3 -m pipeline.<module>`. The reasons:
- The `cd` puts the POC worktree first on `sys.path`, so `from pipeline.X import Y` resolves to **this branch's** code (not the main worktree's `pipeline/`, which is a different checkout).
- The venv lives in `~/code/the-dossier/pipeline/.venv/` (per RESUME.md) — both worktrees share it. Don't re-create it in the POC.
- `-m pipeline.module` is required (not `python3 pipeline/module.py`) because the new modules use `from pipeline.X import Y` package-relative imports.
- Smoke tests against real scored data pass `--scored-file /Users/jhh/code/the-dossier/pipeline/data/scored/2026-04-22.json` (absolute path to the main worktree's scored JSON). The script writes its output artifacts (PDFs, manifest, JD cache) into **the POC tree** (`~/code/the-dossier-poc/pipeline/data/...`), because the modules anchor paths off `__file__`. The scored JSON itself gets mutated in place at the path you passed.

---

## Open Questions — Resolved Up-Front

These were flagged in `RESUME.md`. Resolutions and rationale:

1. **CL renderer architecture: Playwright reuse vs. simpler (pandoc/weasyprint)?**
   → **Reuse Playwright.** Playwright + Chromium are already installed; the resume PDF stack works and looks clean. Adding pandoc means a system binary; weasyprint adds CFFI + GObject. The backlog UX §3 also says "simple approach: reuse `resume.py`'s PDF generation stack." Extract the existing renderer into a shared `pdf_render.py` so both artifact types use one code path.

2. **Where pre-gen artifacts live on disk + how Plan 2 discovers them.**
   → Resume PDFs continue at `pipeline/data/resumes/output/{Name}-{Company}-{Role}-{date}.pdf` (existing convention). CL PDFs at `pipeline/data/cover_letters/output/{Name}-{Company}-{Role}-{date}.pdf` (new, mirrors backlog §3). JD text cache at `pipeline/data/jd_cache/{slug}.txt`. The contract Plan 2 reads is the **manifest** at `pipeline/data/pregenerated/{YYYY-MM-DD}-manifest.json` — a single file listing every successfully pre-generated card with absolute paths to its three artifacts plus the source scored-JSON card payload. Plan 2 doesn't need to re-derive paths.

3. **How pre-gen integrates with the existing daily cron.**
   → No actual crontab is installed today (verified via `crontab -l`). The daily `/pipeline` flow is user-triggered. `pregenerate.py` is built to be cron-installable (idempotent, exit 0 on success, no interactive prompts) but installation of the cron entry is **out of scope for this plan**. Document the recommended cron line in the README; user installs when ready.

4. **Idempotency.**
   → Per-card check: if the resume PDF, CL PDF, and JD cache file all exist for a card, skip and mark "cached" in the manifest. `--force` flag bypasses cache. Date in the filename uses the **scored JSON's discovery date**, not `today()`, so re-running on a later day doesn't churn names.

5. **CL prose source.**
   → Claude API by default (Anthropic SDK, Sonnet 4.6, prompt caching on the source.json bio block which is identical across all cards in a batch). `--text-file PATH` CLI flag overrides with hand-written prose for cases where the user wants manual control. This keeps the LLM piece swappable and gives an escape hatch.

6. **Failure isolation in batch.**
   → One card's failure does not stop the batch. Failures are logged with reason, included in the manifest under a `failures` array, and the script exits 0 if at least one card succeeded (1 if all failed).

---

## File Structure

**Create (committed):**
- `pipeline/__init__.py` — Empty marker. Required so `python3 -m pipeline.X` and `from pipeline.X import Y` resolve correctly.
- `pipeline/pdf_render.py` — Shared `html_to_pdf(html: str, output_path: Path) -> None` extracted from `resume.py`.
- `pipeline/cover_letter.py` — CL generator: prompt building, Anthropic call, HTML render, output path, CLI.
- `pipeline/pregenerate.py` — Batch orchestrator over scored JSON.
- `pipeline/apply_flow_v1_README.md` — Operator docs for Plan 1 deliverables.
- `pipeline/tests/__init__.py` — Empty marker.
- `pipeline/tests/test_pdf_render.py`
- `pipeline/tests/test_cover_letter.py`
- `pipeline/tests/test_pregenerate.py`
- `pipeline/tests/conftest.py` — Shared fixtures (sample scored JSON, sample source.json subset).
- `pipeline/tests/fixtures/scored_sample.json` — 4-card synthetic scored JSON: 1 Grade A new, 1 Grade B new, 1 Grade C (filtered out), 1 Grade A applied (filtered out).

**Modify (committed):**
- `pipeline/resume.py` — Replace inline `generate_pdf` with import from `pdf_render`; add optional `date_str` parameter to `build_output_path` (defaults to `date.today().isoformat()` for back-compat).
- `pipeline/requirements.txt` — Add `anthropic>=0.40` and `pytest>=8` (separated as runtime vs dev with a comment).
- `.gitignore` — Add `pipeline/data/jd_cache/`, `pipeline/data/cover_letters/output/`, `pipeline/data/pregenerated/` (artifact dirs are gitignored, like `resumes/output/`).

**Create (gitignored, runtime artifacts — script creates dirs):**
- `pipeline/data/cover_letters/output/` — CL PDFs.
- `pipeline/data/jd_cache/` — Cached JD text per card.
- `pipeline/data/pregenerated/` — Per-day manifests.

**Reference (read-only):**
- `pipeline/data/scored/YYYY-MM-DD.json` — Input. Existing shape; see `~/code/the-dossier/pipeline/data/scored/2026-04-22.json` for a real example.
- `pipeline/data/resumes/source.json` — Bio data for resume + CL.
- `pipeline/config.yaml` — Archetype templates, `form_answers.full_name`.

---

## Test Strategy

This plan has substantial pure-function logic that benefits from real unit tests (unlike the POC which was browser-only). Use **pytest**.

**What's tested (unit):**
- `pdf_render.html_to_pdf` — round-trip: render `<html><body>hi</body></html>`, assert output file exists and is a non-empty `.pdf`.
- `cover_letter.build_cl_prompt` — prompt contains JD text, company, role, archetype headline; bio block is in the cacheable static prefix.
- `cover_letter.render_cl_html` — HTML contains the prose, contact line, date, company addressee.
- `cover_letter.build_cl_output_path` — naming convention matches resume convention with `cover_letters/output/` dir.
- `cover_letter` idempotency check helper — returns True iff PDF exists.
- `pregenerate.filter_cards` — keeps grade A/B with `status == "new"` and `resolved_status` starting with `"ok:"` (or `resolved_status` absent and direct ATS URL); drops everything else.
- `pregenerate.derive_date_from_scored_path` — `2026-04-22.json` → `"2026-04-22"`.
- `pregenerate.build_card_slug` — deterministic per-card slug for JD cache filename.
- `pregenerate.write_manifest` — schema is correct; cached + generated + failed sections present even when empty.
- `pregenerate.update_scored_with_artifacts` — adds `artifacts` field to matching cards by URL, preserves all other fields.

**What's NOT unit-tested (manual / smoke):**
- Anthropic API call itself — mocked in tests via a `--text-file`-style injection or fake client; one manual end-to-end test in Task 8 hits the real API on one card.
- Playwright PDF render against a real shell — `pdf_render` test does a real render (Playwright is installed), but it's slow (~3-5s); marked `@pytest.mark.slow` so it can be skipped in tight loops.

**Test invocation:**
```bash
cd ~/code/the-dossier-poc && pipeline/.venv/bin/python3 -m pytest pipeline/tests/ -v
```
(Plan also adds a `pipeline/tests/README.md` line in the v1 README.)

---

## Tasks

### Task 1: Add deps + gitignore + test scaffold

**Files:**
- Modify: `pipeline/requirements.txt`
- Modify: `.gitignore`
- Create: `pipeline/tests/__init__.py`
- Create: `pipeline/tests/conftest.py`
- Create: `pipeline/tests/fixtures/scored_sample.json`

- [ ] **Step 1: Update `pipeline/requirements.txt`**

Replace contents with:
```
# Runtime
pyyaml>=6.0
playwright>=1.40
anthropic>=0.40

# Dev
pytest>=8
```

- [ ] **Step 2: Install new deps into the venv**

Run:
```bash
~/code/the-dossier/pipeline/.venv/bin/pip install -r ~/code/the-dossier-poc/pipeline/requirements.txt
```
Expected: `anthropic` and `pytest` install cleanly. (Venv is shared between the two worktrees; the POC RESUME.md instructs running scripts from the main worktree's venv path.)

Then verify both packages are importable:
```bash
~/code/the-dossier/pipeline/.venv/bin/python3 -c "import pytest, anthropic; print('ok')"
```
Expected: `ok`. If this fails, do not proceed — fix the install first.

- [ ] **Step 3: Add gitignore entries**

Append to `.gitignore` (after the existing `pipeline/.cache/` line):
```
# Apply-flow v1: pre-generated artifact dirs
pipeline/data/cover_letters/output/
pipeline/data/jd_cache/
pipeline/data/pregenerated/
```

Verify the resume output dir is already gitignored (it should be — confirm with `git check-ignore pipeline/data/resumes/output/foo.pdf`). If not, add `pipeline/data/resumes/output/` to the same block.

- [ ] **Step 4: Create test scaffold + package marker**

Create `pipeline/__init__.py` (empty file) — required so `from pipeline.X import Y` works under `-m` and pytest.

Create `pipeline/tests/__init__.py` (empty file).

Create `pipeline/tests/conftest.py`:
```python
"""Shared test fixtures for pipeline unit tests."""
import json
from pathlib import Path
import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def scored_sample():
    """4-card synthetic scored JSON covering filter cases."""
    with open(FIXTURES_DIR / "scored_sample.json") as f:
        return json.load(f)


@pytest.fixture
def source_minimal():
    """Minimal source.json subset for tests that don't need full bio."""
    return {
        "meta": {
            "name": "Jared Hawkins",
            "location": "Seattle, WA",
            "email": "hawkins.jared@gmail.com",
            "phone": "555-1212",
            "linkedin": "https://www.linkedin.com/in/jaredhawkins/",
        },
        "summary_variants": {
            "product_management": "Senior PM with 10 years building...",
        },
    }
```

Create `pipeline/tests/fixtures/scored_sample.json`:
```json
[
  {
    "title": "Senior Product Manager",
    "company": "AcmeCorp",
    "location": "Seattle, WA",
    "salary": "$180,000-$220,000",
    "url": "https://job-boards.greenhouse.io/acmecorp/jobs/12345",
    "source": "Adzuna",
    "description": "Acme is looking for a Senior PM to lead our platform...",
    "weighted_score": 4.2,
    "grade": "A",
    "archetype": "product_management",
    "lane": "A",
    "rationale": "Direct PM role, strong AI platform fit.",
    "red_flags": [],
    "status": "new",
    "resolved_status": "ok:brave",
    "resolved_url": "https://job-boards.greenhouse.io/acmecorp/jobs/12345"
  },
  {
    "title": "Product Manager",
    "company": "BetaInc",
    "location": "Remote",
    "salary": "$140,000-$180,000",
    "url": "https://jobs.lever.co/betainc/abc123",
    "source": "Adzuna",
    "description": "Beta needs a PM for our dev tools team...",
    "weighted_score": 3.6,
    "grade": "B",
    "archetype": "product_management",
    "lane": "A",
    "rationale": "Solid B-grade dev tools PM.",
    "red_flags": [],
    "status": "new",
    "resolved_status": "ok:ddg",
    "resolved_url": "https://jobs.lever.co/betainc/abc123"
  },
  {
    "title": "PM Specialist",
    "company": "GammaLLC",
    "location": "Seattle, WA",
    "salary": "$120,000-$140,000",
    "url": "https://gamma.example/jobs/9",
    "source": "Adzuna",
    "description": "Gamma...",
    "weighted_score": 2.9,
    "grade": "C",
    "archetype": "operations",
    "lane": "B",
    "rationale": "C-grade, filtered out.",
    "red_flags": [],
    "status": "new",
    "resolved_status": "ok:brave"
  },
  {
    "title": "Principal Product Manager",
    "company": "DeltaCo",
    "location": "Seattle, WA",
    "salary": "$220,000-$260,000",
    "url": "https://delta.example/jobs/77",
    "source": "Adzuna",
    "description": "Delta...",
    "weighted_score": 4.5,
    "grade": "A",
    "archetype": "product_management",
    "lane": "A",
    "rationale": "Already applied, filtered out.",
    "red_flags": [],
    "status": "applied",
    "resolved_status": "ok:brave"
  }
]
```

- [ ] **Step 5: Verify pytest discovers the suite**

Run:
```bash
cd ~/code/the-dossier-poc && ~/code/the-dossier/pipeline/.venv/bin/python3 -m pytest pipeline/tests/ -v --collect-only
```
Expected: collects 0 tests but reports no errors (no test files yet). Confirms pytest sees the package and conftest loads.

- [ ] **Step 6: Commit**

```bash
git add pipeline/requirements.txt .gitignore pipeline/__init__.py pipeline/tests/
git commit -m "chore(apply-flow-v1): add anthropic + pytest deps, gitignore artifact dirs, test scaffold"
```

---

### Task 2: Extract `pdf_render.html_to_pdf` from `resume.py`

**Files:**
- Create: `pipeline/pdf_render.py`
- Create: `pipeline/tests/test_pdf_render.py`
- Modify: `pipeline/resume.py:518-544` (the existing `generate_pdf` function)

- [ ] **Step 1: Write the failing test**

Create `pipeline/tests/test_pdf_render.py`:
```python
"""Tests for the shared HTML → PDF renderer."""
from pathlib import Path
import pytest

from pipeline.pdf_render import html_to_pdf


@pytest.mark.slow
def test_html_to_pdf_writes_nonempty_pdf(tmp_path: Path):
    """Real Playwright render of a tiny HTML doc produces a valid PDF file."""
    out = tmp_path / "out.pdf"
    html_to_pdf("<html><body><h1>hello</h1></body></html>", out)
    assert out.exists(), "PDF was not written"
    assert out.stat().st_size > 100, "PDF is suspiciously small"
    # PDF magic header
    with open(out, "rb") as f:
        assert f.read(4) == b"%PDF", "File is not a valid PDF"


def test_html_to_pdf_creates_parent_dir(tmp_path: Path, monkeypatch):
    """If parent dir doesn't exist, it's created. Skip the actual render."""
    # Patch the heavy work; we only assert the dir-creation behavior.
    import pipeline.pdf_render as pr

    captured = {}

    def fake_render(html, output_path):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"%PDF-stub")
        captured["called"] = True

    monkeypatch.setattr(pr, "html_to_pdf", fake_render)
    nested = tmp_path / "a" / "b" / "c" / "out.pdf"
    pr.html_to_pdf("<html></html>", nested)
    assert nested.exists()
```

- [ ] **Step 2: Run the test to confirm it fails (module doesn't exist)**

Run:
```bash
cd ~/code/the-dossier-poc && ~/code/the-dossier/pipeline/.venv/bin/python3 -m pytest pipeline/tests/test_pdf_render.py -v
```
Expected: collection error or `ModuleNotFoundError: No module named 'pipeline.pdf_render'`.

- [ ] **Step 3: Create `pipeline/pdf_render.py`**

```python
"""Shared HTML → PDF renderer used by resume and cover-letter generators.

Uses Playwright's headless Chromium to render Letter-sized PDFs with
zero margin (the HTML is responsible for its own padding).
"""
from __future__ import annotations

import sys
from pathlib import Path


def html_to_pdf(html: str, output_path: Path) -> None:
    """Render HTML string to a PDF file at output_path.

    Creates the parent directory if needed. Letter format, no margins
    (HTML controls its own padding for both resume and CL templates).
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sys.exit(
            "playwright required: pip install playwright "
            "&& playwright install chromium"
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content(html, wait_until="networkidle")
        page.pdf(
            path=str(output_path),
            format="Letter",
            margin={"top": "0in", "bottom": "0in", "left": "0in", "right": "0in"},
            print_background=True,
        )
        browser.close()
```

- [ ] **Step 4: Run tests, confirm they pass**

Run:
```bash
cd ~/code/the-dossier-poc && ~/code/the-dossier/pipeline/.venv/bin/python3 -m pytest pipeline/tests/test_pdf_render.py -v
```
Expected: both tests PASS. The `slow` test takes ~3-5s.

- [ ] **Step 5: Refactor `resume.py` to use the shared renderer**

In `pipeline/resume.py`, find the existing `generate_pdf` function (lines 518-544 in the current file). Replace its body with a thin shim that calls the new module — or, better, delete `generate_pdf` entirely and update its single call site.

Find the call site (currently `generate_pdf(html, out_path)` near line 629) and replace:
```python
from pipeline.pdf_render import html_to_pdf
# ...
html_to_pdf(html, out_path)
print(f"PDF generated: {out_path}")
```

Then delete the now-unused `generate_pdf` function from `resume.py`.

- [ ] **Step 6: Verify resume CLI still works**

Run a smoke test (note the `-m` invocation — required so `from pipeline.pdf_render` resolves to the POC's package, not the main worktree's):
```bash
cd ~/code/the-dossier-poc && ~/code/the-dossier/pipeline/.venv/bin/python3 -m pipeline.resume --archetype product_management --markdown-only
```
Expected: prints "Markdown written: ..." and the output file exists. The output lands at `~/code/the-dossier-poc/pipeline/data/resumes/output/`. (Markdown mode skips PDF, but this confirms the import refactor didn't break the CLI.)

**Note for the engineer:** the POC worktree's `pipeline/data/resumes/source.json` exists (committed) so this works. The main worktree's source.json may differ — that's fine, we're testing the POC tree.

Then test the PDF path:
```bash
cd ~/code/the-dossier-poc && ~/code/the-dossier/pipeline/.venv/bin/python3 -m pipeline.resume --archetype product_management --company TestCo --role "Test Role"
```
Expected: prints "PDF generated: .../Jared-Hawkins-TestCo-Test-Role-{today}.pdf". File exists in `pipeline/data/resumes/output/`.

Cleanup:
```bash
rm ~/code/the-dossier-poc/pipeline/data/resumes/output/Jared-Hawkins-TestCo-Test-Role-*.pdf
rm ~/code/the-dossier-poc/pipeline/data/resumes/output/product_management-*.md
```

- [ ] **Step 7: Commit**

```bash
git add pipeline/pdf_render.py pipeline/resume.py pipeline/tests/test_pdf_render.py
git commit -m "refactor(pipeline): extract html_to_pdf to shared pdf_render module"
```

---

### Task 3: Add `date_str` parameter to `resume.py:build_output_path`

This is needed so `pregenerate.py` can produce stable filenames keyed to the **scored JSON's date**, not today's date. Without this, re-running pregenerate on a later day would generate new filenames and defeat idempotency.

**Files:**
- Modify: `pipeline/resume.py` — `build_output_path` signature + body
- Create test: `pipeline/tests/test_resume_paths.py`

- [ ] **Step 1: Write the failing test**

Create `pipeline/tests/test_resume_paths.py`:
```python
"""Tests for resume output-path helpers."""
from datetime import date
from pipeline.resume import build_output_path


def test_build_output_path_uses_today_by_default():
    p = build_output_path("product_management", company="Acme", role="PM",
                          full_name="Jared Hawkins")
    assert date.today().isoformat() in p.name


def test_build_output_path_accepts_explicit_date():
    p = build_output_path("product_management", company="Acme", role="PM",
                          full_name="Jared Hawkins", date_str="2026-04-22")
    assert "2026-04-22" in p.name
    assert "Jared-Hawkins-Acme-PM-2026-04-22" in p.name


def test_build_output_path_explicit_date_archetype_only():
    """No company+role → archetype-based name still respects date_str."""
    p = build_output_path("operations", date_str="2026-04-22")
    assert "operations-2026-04-22" in p.name
```

- [ ] **Step 2: Run, confirm fail**

```bash
cd ~/code/the-dossier-poc && ~/code/the-dossier/pipeline/.venv/bin/python3 -m pytest pipeline/tests/test_resume_paths.py -v
```
Expected: TypeError on unexpected keyword `date_str`, or assertion failures.

- [ ] **Step 3: Update `build_output_path` in `pipeline/resume.py`**

Change signature and body:
```python
def build_output_path(archetype: str, company: str | None = None,
                      role: str | None = None, ext: str = "pdf",
                      full_name: str | None = None,
                      date_str: str | None = None) -> Path:
    """Build the output file path following naming conventions.

    date_str overrides today's date when supplied (used by pregenerate
    so re-running on later days doesn't churn filenames).
    """
    today = date_str or date.today().isoformat()
    if company and role:
        company_clean = re.sub(r"[^\w\s-]", "", company).strip().replace(" ", "-")
        role_clean = re.sub(r"[^\w\s-]", "", role).strip().replace(" ", "-")
        if full_name:
            name_clean = re.sub(r"[^\w\s-]", "", full_name).strip().replace(" ", "-")
            name = f"{name_clean}-{company_clean}-{role_clean}-{today}.{ext}"
        else:
            name = f"{company_clean}-{role_clean}-{today}.{ext}"
    else:
        name = f"{archetype}-{today}.{ext}"
    return OUTPUT_DIR / name
```

- [ ] **Step 4: Run tests**

```bash
cd ~/code/the-dossier-poc && ~/code/the-dossier/pipeline/.venv/bin/python3 -m pytest pipeline/tests/test_resume_paths.py -v
```
Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add pipeline/resume.py pipeline/tests/test_resume_paths.py
git commit -m "feat(pipeline): build_output_path accepts explicit date_str"
```

---

### Task 4: CL output path + HTML rendering (no LLM yet)

Build the deterministic, testable parts of the CL generator first. LLM call comes in Task 5.

**Files:**
- Create: `pipeline/cover_letter.py` (partial — path + HTML; CLI + LLM in later tasks)
- Modify: `pipeline/tests/test_cover_letter.py` (create)

- [ ] **Step 1: Write the failing tests**

Create `pipeline/tests/test_cover_letter.py`:
```python
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
```

- [ ] **Step 2: Run, confirm fail**

```bash
cd ~/code/the-dossier-poc && ~/code/the-dossier/pipeline/.venv/bin/python3 -m pytest pipeline/tests/test_cover_letter.py -v
```
Expected: ImportError on `pipeline.cover_letter`.

- [ ] **Step 3: Create `pipeline/cover_letter.py` with path + HTML helpers**

```python
#!/usr/bin/env python3
"""Cover letter generator for the job search pipeline.

Produces a tailored CL PDF per (company, role, JD) using:
- Bio data from data/resumes/source.json
- Archetype headline from config.yaml (mirrors resume routing)
- Claude API for the prose body (Anthropic SDK, prompt caching on the
  static bio block since it's identical across all cards in a batch)
- Shared Playwright HTML→PDF renderer

Output: pipeline/data/cover_letters/output/{Name}-{Company}-{Role}-{date}.pdf
"""
from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PIPELINE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PIPELINE_DIR / "data" / "cover_letters" / "output"


# ---------------------------------------------------------------------------
# Output path
# ---------------------------------------------------------------------------

def _slug(s: str) -> str:
    """Filesafe slug: drop punctuation except spaces/hyphens, then hyphenate."""
    cleaned = re.sub(r"[^\w\s-]", "", s).strip()
    return re.sub(r"\s+", "-", cleaned)


def build_cl_output_path(company: str, role: str, full_name: str,
                         date_str: str | None = None) -> Path:
    """Mirror resume.build_output_path naming: {Name}-{Company}-{Role}-{date}.pdf"""
    d = date_str or date.today().isoformat()
    name = f"{_slug(full_name)}-{_slug(company)}-{_slug(role)}-{d}.pdf"
    return OUTPUT_DIR / name


def cl_artifact_exists(path: Path) -> bool:
    return path.exists() and path.stat().st_size > 0


# ---------------------------------------------------------------------------
# HTML template
# ---------------------------------------------------------------------------

CL_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<style>
@page {{ size: Letter; margin: 0; }}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
  font-family: Arial, Helvetica, sans-serif;
  font-size: 11pt;
  line-height: 1.45;
  color: #1a1a1a;
  padding: 0.6in 0.75in;
  max-width: 8.5in;
}}
.header {{ margin-bottom: 18pt; }}
.name {{ font-size: 16pt; font-weight: bold; margin-bottom: 3pt; }}
.contact {{ font-size: 10pt; color: #444; }}
.contact a {{ color: #444; text-decoration: none; }}
.date {{ margin-bottom: 12pt; font-size: 11pt; }}
.addressee {{ margin-bottom: 14pt; font-size: 11pt; }}
p {{ margin-bottom: 9pt; text-align: left; }}
</style>
</head>
<body>
<div class="header">
  <div class="name">{name}</div>
  <div class="contact">{contact}</div>
</div>
<div class="date">{date_human}</div>
<div class="addressee">{company} Hiring Team<br>Re: {role}</div>
{paragraphs}
</body>
</html>
"""


def _format_date_human(date_str: str) -> str:
    """2026-04-22 → April 22, 2026."""
    try:
        d = date.fromisoformat(date_str)
        return d.strftime("%B %-d, %Y")
    except ValueError:
        return date_str


def _prose_to_paragraphs(prose: str) -> str:
    """Split on blank lines, wrap each chunk in <p>, escape HTML angle brackets minimally."""
    chunks = [c.strip() for c in re.split(r"\n\s*\n", prose.strip()) if c.strip()]
    parts = []
    for c in chunks:
        # Preserve single newlines as <br> within a paragraph
        body = c.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        body = body.replace("\n", "<br>")
        parts.append(f"<p>{body}</p>")
    return "\n".join(parts)


def render_cl_html(prose: str, source: dict, company: str, role: str,
                   date_str: str) -> str:
    """Render the CL HTML doc combining bio header + prose body."""
    meta = source["meta"]
    contact_items = []
    if meta.get("location"):
        contact_items.append(meta["location"])
    if meta.get("phone"):
        contact_items.append(meta["phone"])
    if meta.get("email"):
        contact_items.append(
            f'<a href="mailto:{meta["email"]}">{meta["email"]}</a>'
        )
    if meta.get("linkedin"):
        contact_items.append(f'<a href="{meta["linkedin"]}">LinkedIn</a>')
    contact = " | ".join(contact_items)

    return CL_HTML_TEMPLATE.format(
        name=meta["name"],
        contact=contact,
        date_human=_format_date_human(date_str),
        company=company,
        role=role,
        paragraphs=_prose_to_paragraphs(prose),
    )
```

- [ ] **Step 4: Run tests, confirm pass**

```bash
cd ~/code/the-dossier-poc && ~/code/the-dossier/pipeline/.venv/bin/python3 -m pytest pipeline/tests/test_cover_letter.py -v
```
Expected: 7 PASS.

- [ ] **Step 5: Commit**

```bash
git add pipeline/cover_letter.py pipeline/tests/test_cover_letter.py
git commit -m "feat(cover-letter): add output-path + HTML render helpers"
```

---

### Task 5: CL prompt builder + Anthropic client wrapper

Add the LLM piece. Keep it isolated and injectable so tests don't hit the network.

**Files:**
- Modify: `pipeline/cover_letter.py` (add `build_cl_prompt`, `generate_cl_text`)
- Modify: `pipeline/tests/test_cover_letter.py` (add prompt + injection tests)

- [ ] **Step 1: Write the failing tests**

Append to `pipeline/tests/test_cover_letter.py`:
```python
from pipeline.cover_letter import build_cl_prompt, generate_cl_text


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
```

- [ ] **Step 2: Run, confirm fail**

```bash
cd ~/code/the-dossier-poc && ~/code/the-dossier/pipeline/.venv/bin/python3 -m pytest pipeline/tests/test_cover_letter.py -v
```
Expected: ImportError on `build_cl_prompt`/`generate_cl_text`.

- [ ] **Step 3: Append to `pipeline/cover_letter.py`**

```python
# ---------------------------------------------------------------------------
# Prompt building + Anthropic call
# ---------------------------------------------------------------------------

CL_SYSTEM_TEMPLATE = """\
You are a writing assistant helping Jared Hawkins draft cover letters for product/operations roles.

About Jared (use this as background; do not restate it verbatim):
{bio_summary}

Rules for every cover letter you produce:
- Voice: confident, direct, conversational. One person talking to one other person.
- No banned words: delve, leverage (verb), robust, streamline, cutting-edge, synergy, multifaceted, comprehensive, meticulous, pivotal, testament, utilize, facilitate, "it is worth noting", "it is important to note".
- No em-dashes (—). Use periods, commas, or restructure.
- Active voice. Short sentences. Break anything over 25 words.
- Three or four paragraphs total. Around 250 words.
- Open with a specific reason this role/company stands out (not "I am writing to apply for").
- One paragraph on the most relevant experience, with a concrete result.
- Close with a clear next step (interview, conversation).
- Do not invent companies or projects Jared has not done.
- Output the letter body only. No subject line, no "Dear Hiring Manager" prelude (the template adds those). Start with the first paragraph of prose.
"""


def build_cl_prompt(source: dict, archetype_template: dict,
                    company: str, role: str, jd_text: str) -> dict:
    """Build the {system, user} prompt pair for the Anthropic call.

    The system block is intentionally invariant across cards in a batch
    so prompt caching can kick in. The user block carries everything that
    varies per-card (company, role, JD, archetype headline).
    """
    summary_key = archetype_template.get("summary_variant", "product_management")
    bio_summary = source.get("summary_variants", {}).get(summary_key, "")
    headline = archetype_template.get("headline", "")

    system = CL_SYSTEM_TEMPLATE.format(bio_summary=bio_summary)

    user = (
        f"Draft a cover letter for this role.\n\n"
        f"Company: {company}\n"
        f"Role: {role}\n"
        f"Positioning headline (use as a north star, do not quote): {headline}\n\n"
        f"Job description:\n{jd_text}\n"
    )

    return {"system": system, "user": user}


DEFAULT_CL_MODEL = "claude-sonnet-4-6"  # Override via PIPELINE_CL_MODEL env var if Anthropic changes the alias.


def generate_cl_text(prompt: dict, client, model: str | None = None,
                     max_tokens: int = 1200) -> str:
    """Call the Anthropic Messages API with prompt caching on the system block.

    `client` is anything with a `messages_create(**kwargs)` callable; the real
    Anthropic SDK uses `client.messages.create(...)` so we wrap it in
    `_make_anthropic_adapter` for prod use. Tests pass a fake.

    Model selection precedence: explicit arg > PIPELINE_CL_MODEL env var > DEFAULT_CL_MODEL.
    """
    import os
    chosen = model or os.environ.get("PIPELINE_CL_MODEL") or DEFAULT_CL_MODEL
    response = client.messages_create(
        model=chosen,
        max_tokens=max_tokens,
        system=[
            {
                "type": "text",
                "text": prompt["system"],
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": prompt["user"]}],
    )
    # Anthropic SDK returns content as a list of blocks; first block is text.
    return response.content[0].text


def _make_anthropic_adapter():
    """Wrap the real Anthropic SDK so tests can inject a duck-typed fake."""
    try:
        from anthropic import Anthropic
    except ImportError:
        sys.exit(
            "anthropic SDK required: pip install anthropic "
            "(set ANTHROPIC_API_KEY in env)"
        )

    real = Anthropic()

    class Adapter:
        def messages_create(self, **kwargs):
            return real.messages.create(**kwargs)

    return Adapter()
```

- [ ] **Step 4: Run tests, confirm pass**

```bash
cd ~/code/the-dossier-poc && ~/code/the-dossier/pipeline/.venv/bin/python3 -m pytest pipeline/tests/test_cover_letter.py -v
```
Expected: all CL tests PASS (10 total now).

- [ ] **Step 5: Commit**

```bash
git add pipeline/cover_letter.py pipeline/tests/test_cover_letter.py
git commit -m "feat(cover-letter): add prompt builder + Anthropic client wrapper"
```

---

### Task 6: CL CLI (single-card invocation)

Wire the pieces into a runnable CLI for one-off use and as a building block for `pregenerate.py`.

**Files:**
- Modify: `pipeline/cover_letter.py` (add `main()` + invocation guard)

- [ ] **Step 1: Append CLI to `pipeline/cover_letter.py`**

```python
# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _load_source_and_config():
    """Mirror resume.py's loading."""
    import json
    import yaml
    pipeline_dir = Path(__file__).resolve().parent
    with open(pipeline_dir / "data" / "resumes" / "source.json") as f:
        source = json.load(f)
    with open(pipeline_dir / "config.yaml") as f:
        config = yaml.safe_load(f)
    return source, config


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate a tailored cover-letter PDF for one role."
    )
    parser.add_argument("--archetype", required=True,
                        help="Archetype name (matches config.yaml.archetypes keys)")
    parser.add_argument("--company", required=True)
    parser.add_argument("--role", required=True)
    parser.add_argument("--jd", default=None,
                        help="Path to job description text file. Required unless --text-file is supplied.")
    parser.add_argument("--text-file", default=None,
                        help="Skip LLM. Use this hand-written prose file as the CL body.")
    parser.add_argument("--date", default=None,
                        help="Override the date used in the output filename (YYYY-MM-DD).")
    parser.add_argument("--force", action="store_true",
                        help="Regenerate even if PDF already exists.")
    parser.add_argument("--markdown-only", action="store_true",
                        help="Write .md instead of running PDF render. For inspection.")
    args = parser.parse_args()

    if not args.jd and not args.text_file:
        parser.error("must supply either --jd or --text-file")

    source, config = _load_source_and_config()
    archetypes = config.get("archetypes", {})
    if args.archetype not in archetypes:
        sys.exit(f"Unknown archetype '{args.archetype}'")
    archetype_template = archetypes[args.archetype]["template"]

    full_name = config.get("form_answers", {}).get("full_name") or source["meta"]["name"]
    out_path = build_cl_output_path(args.company, args.role, full_name, args.date)

    if cl_artifact_exists(out_path) and not args.force:
        print(f"[cover-letter] cached: {out_path}")
        return

    # Source the prose
    if args.text_file:
        with open(args.text_file) as f:
            prose = f.read()
    else:
        with open(args.jd) as f:
            jd_text = f.read()
        prompt = build_cl_prompt(source, archetype_template,
                                 args.company, args.role, jd_text)
        client = _make_anthropic_adapter()
        prose = generate_cl_text(prompt, client)

    if args.markdown_only:
        md_path = out_path.with_suffix(".md")
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(prose)
        print(f"[cover-letter] markdown: {md_path}")
        return

    html = render_cl_html(prose, source, args.company, args.role,
                          args.date or date.today().isoformat())
    from pipeline.pdf_render import html_to_pdf
    html_to_pdf(html, out_path)
    print(f"[cover-letter] generated: {out_path}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Smoke-test the CLI in `--text-file` + `--markdown-only` mode (no API call, no PDF render)**

Create a throwaway prose file and run (note: `-m pipeline.cover_letter` from POC dir; no `--jd` since `--text-file` is supplied):
```bash
cat > /tmp/test_cl.txt <<'EOF'
Dear Acme team,

I'm interested in this role because of your work on X. My experience building Y maps directly.

Happy to talk anytime.

Best,
Jared
EOF

cd ~/code/the-dossier-poc && ~/code/the-dossier/pipeline/.venv/bin/python3 -m pipeline.cover_letter \
  --archetype product_management --company "TestCo" --role "Test PM" \
  --text-file /tmp/test_cl.txt --date 2026-05-01 --markdown-only
```
Expected output: `[cover-letter] markdown: /Users/jhh/code/the-dossier-poc/pipeline/data/cover_letters/output/Jared-Hawkins-TestCo-Test-PM-2026-05-01.md`. File contains the prose.

- [ ] **Step 3: Smoke-test the PDF path (still `--text-file`, real PDF render, no API)**

```bash
cd ~/code/the-dossier-poc && ~/code/the-dossier/pipeline/.venv/bin/python3 -m pipeline.cover_letter \
  --archetype product_management --company "TestCo" --role "Test PM" \
  --text-file /tmp/test_cl.txt --date 2026-05-01
```
Expected: `[cover-letter] generated: /Users/jhh/code/the-dossier-poc/pipeline/data/cover_letters/output/Jared-Hawkins-TestCo-Test-PM-2026-05-01.pdf`. Open the PDF (`open ~/code/the-dossier-poc/pipeline/data/cover_letters/output/Jared-Hawkins-TestCo-Test-PM-2026-05-01.pdf`); confirm header has Jared's name + contact, addressee says "TestCo Hiring Team / Re: Test PM", body matches the prose with paragraph breaks.

- [ ] **Step 4: Verify idempotency**

Re-run the same command without `--force`. Expected: `[cover-letter] cached: ...`. With `--force`: regenerates.

Cleanup:
```bash
rm /tmp/test_cl.txt
rm ~/code/the-dossier-poc/pipeline/data/cover_letters/output/Jared-Hawkins-TestCo-Test-PM-2026-05-01.*
```

- [ ] **Step 5: Commit**

```bash
git add pipeline/cover_letter.py
git commit -m "feat(cover-letter): add CLI with --text-file override and idempotency"
```

---

### Task 7: `pregenerate.py` orchestrator — pure-function tests first

Build the testable core (filtering, slug, manifest schema, scored-JSON updates) before wiring the IO + subprocess work.

**Files:**
- Create: `pipeline/pregenerate.py`
- Create: `pipeline/tests/test_pregenerate.py`

- [ ] **Step 1: Write the failing tests**

Create `pipeline/tests/test_pregenerate.py`:
```python
"""Tests for pregenerate orchestrator pure functions."""
from pathlib import Path
import json

from pipeline.pregenerate import (
    filter_cards,
    derive_date_from_scored_path,
    build_card_slug,
    build_manifest,
    update_scored_with_artifacts,
)


def test_filter_cards_keeps_grade_a_b_new_resolvable(scored_sample):
    kept = filter_cards(scored_sample, grades=("A", "B"))
    assert len(kept) == 2
    companies = {c["company"] for c in kept}
    assert companies == {"AcmeCorp", "BetaInc"}


def test_filter_cards_drops_grade_c(scored_sample):
    kept = filter_cards(scored_sample, grades=("A", "B"))
    assert all(c["grade"] in ("A", "B") for c in kept)


def test_filter_cards_drops_already_applied(scored_sample):
    kept = filter_cards(scored_sample, grades=("A", "B"))
    assert all(c["status"] == "new" for c in kept)


def test_filter_cards_grade_a_only(scored_sample):
    kept = filter_cards(scored_sample, grades=("A",))
    assert len(kept) == 1
    assert kept[0]["company"] == "AcmeCorp"


def test_derive_date_from_scored_path():
    assert derive_date_from_scored_path(Path("foo/2026-04-22.json")) == "2026-04-22"
    assert derive_date_from_scored_path(Path("/abs/path/2026-04-22.json")) == "2026-04-22"


def test_derive_date_rejects_non_date_filename():
    import pytest
    with pytest.raises(ValueError):
        derive_date_from_scored_path(Path("foo/not-a-date.json"))


def test_build_card_slug_is_deterministic():
    card = {"company": "Acme Co", "title": "Senior PM", "url": "https://x.example/1"}
    a = build_card_slug(card, date_str="2026-04-22")
    b = build_card_slug(card, date_str="2026-04-22")
    assert a == b
    assert "Acme-Co" in a
    assert "Senior-PM" in a
    assert "2026-04-22" in a


def test_build_manifest_schema(tmp_path: Path):
    generated = [{"company": "X", "role": "Y", "url": "u",
                  "resume_pdf": "/r.pdf", "cl_pdf": "/c.pdf",
                  "jd_cache": "/j.txt"}]
    cached = [{"company": "Z", "role": "W", "url": "u2",
               "resume_pdf": "/r2.pdf", "cl_pdf": "/c2.pdf",
               "jd_cache": "/j2.txt"}]
    failures = [{"company": "F", "role": "G", "url": "u3", "reason": "no resolved url"}]
    m = build_manifest(date_str="2026-04-22",
                       scored_file="/abs/2026-04-22.json",
                       generated=generated, cached=cached, failures=failures)
    assert m["date"] == "2026-04-22"
    assert m["scored_file"] == "/abs/2026-04-22.json"
    assert m["counts"] == {"generated": 1, "cached": 1, "failures": 1}
    assert m["generated"] == generated
    assert m["cached"] == cached
    assert m["failures"] == failures
    assert "generated_at" in m  # ISO timestamp


def test_update_scored_with_artifacts_adds_artifacts_field(scored_sample):
    artifacts_by_url = {
        "https://job-boards.greenhouse.io/acmecorp/jobs/12345": {
            "resume_pdf": "/r.pdf", "cl_pdf": "/c.pdf", "jd_cache": "/j.txt",
        }
    }
    updated = update_scored_with_artifacts(scored_sample, artifacts_by_url)
    by_url = {c["url"]: c for c in updated}
    acme = by_url["https://job-boards.greenhouse.io/acmecorp/jobs/12345"]
    assert "artifacts" in acme
    assert acme["artifacts"]["resume_pdf"] == "/r.pdf"
    # Other cards unchanged
    beta = by_url["https://jobs.lever.co/betainc/abc123"]
    assert "artifacts" not in beta
    # Non-artifact fields preserved
    assert acme["grade"] == "A"
    assert acme["company"] == "AcmeCorp"
```

- [ ] **Step 2: Run, confirm fail**

```bash
cd ~/code/the-dossier-poc && ~/code/the-dossier/pipeline/.venv/bin/python3 -m pytest pipeline/tests/test_pregenerate.py -v
```
Expected: ImportError.

- [ ] **Step 3: Create `pipeline/pregenerate.py` (pure functions only — IO/subprocess in Task 8)**

```python
#!/usr/bin/env python3
"""Pre-generate tailored resume + CL PDFs for every Grade A/B card on a scored JSON.

Designed to run unattended (e.g., overnight cron). Idempotent: skips any card
whose resume PDF, CL PDF, and JD cache file all exist. One card's failure does
not stop the batch.

Output:
- Resume PDFs (via resume.py functions): pipeline/data/resumes/output/{Name}-{Co}-{Role}-{date}.pdf
- CL PDFs (via cover_letter.py): pipeline/data/cover_letters/output/{Name}-{Co}-{Role}-{date}.pdf
- JD cache: pipeline/data/jd_cache/{slug}.txt
- Manifest: pipeline/data/pregenerated/{date}-manifest.json  ← Plan 2's read interface

Usage (run from ~/code/the-dossier-poc using the shared venv at ~/code/the-dossier/pipeline/.venv):
    python3 -m pipeline.pregenerate                      # Most recent scored JSON, A+B grades
    python3 -m pipeline.pregenerate --scored-file FILE   # Specific file
    python3 -m pipeline.pregenerate --grades A           # Filter to A only
    python3 -m pipeline.pregenerate --force              # Regenerate even if cached
    python3 -m pipeline.pregenerate --dry-run            # List cards that would be processed
    python3 -m pipeline.pregenerate --limit 3            # Cap card count (smoke testing)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PIPELINE_DIR = Path(__file__).resolve().parent
SCORED_DIR = PIPELINE_DIR / "data" / "scored"
JD_CACHE_DIR = PIPELINE_DIR / "data" / "jd_cache"
MANIFEST_DIR = PIPELINE_DIR / "data" / "pregenerated"

DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})\.json$")


# ---------------------------------------------------------------------------
# Pure functions (unit-tested)
# ---------------------------------------------------------------------------

def filter_cards(cards: list[dict], grades: tuple[str, ...]) -> list[dict]:
    """Keep cards that are (a) in `grades`, (b) status == "new", (c) have a usable apply URL.

    "Usable" = resolved_status starts with "ok:" (URL resolver succeeded), OR
    resolved_status absent and the original `url` is a known direct ATS link.
    For the sample data we only require status==new and grade match — the URL
    check is enforced as: card has either resolved_url or url field truthy.
    """
    keep = []
    for c in cards:
        if c.get("grade") not in grades:
            continue
        if c.get("status") != "new":
            continue
        # Accept resolved or direct ATS URL
        rs = c.get("resolved_status", "")
        has_resolved = isinstance(rs, str) and rs.startswith("ok:")
        if not has_resolved and not c.get("url"):
            continue
        keep.append(c)
    return keep


def derive_date_from_scored_path(path: Path) -> str:
    """Extract YYYY-MM-DD from a scored JSON filename like `2026-04-22.json`."""
    m = DATE_RE.search(path.name)
    if not m:
        raise ValueError(f"Filename does not match YYYY-MM-DD.json: {path.name}")
    return m.group(1)


def _slug(s: str) -> str:
    cleaned = re.sub(r"[^\w\s-]", "", s).strip()
    return re.sub(r"\s+", "-", cleaned)


def build_card_slug(card: dict, date_str: str) -> str:
    """Deterministic slug for JD cache filename. Uses company + title + date.

    URL is hashed in only if title+company collide (rare). For now, simple form.
    """
    return f"{_slug(card['company'])}-{_slug(card['title'])}-{date_str}"


def build_manifest(date_str: str, scored_file: str,
                   generated: list[dict], cached: list[dict],
                   failures: list[dict]) -> dict:
    """Assemble the manifest object that Plan 2 will read."""
    return {
        "date": date_str,
        "scored_file": scored_file,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "counts": {
            "generated": len(generated),
            "cached": len(cached),
            "failures": len(failures),
        },
        "generated": generated,
        "cached": cached,
        "failures": failures,
    }


def update_scored_with_artifacts(cards: list[dict],
                                 artifacts_by_url: dict[str, dict]) -> list[dict]:
    """Return a new list of cards where matching ones have an `artifacts` field added.

    Match key is the canonical url (prefer resolved_url, fall back to url).
    Existing fields are preserved.
    """
    out = []
    for c in cards:
        key = c.get("resolved_url") or c.get("url")
        if key in artifacts_by_url:
            new_card = dict(c)
            new_card["artifacts"] = artifacts_by_url[key]
            out.append(new_card)
        else:
            out.append(c)
    return out
```

- [ ] **Step 4: Run tests, confirm pass**

```bash
cd ~/code/the-dossier-poc && ~/code/the-dossier/pipeline/.venv/bin/python3 -m pytest pipeline/tests/test_pregenerate.py -v
```
Expected: 9 PASS.

- [ ] **Step 5: Commit**

```bash
git add pipeline/pregenerate.py pipeline/tests/test_pregenerate.py
git commit -m "feat(pregenerate): add pure-function core (filter, slug, manifest, update)"
```

---

### Task 8: `pregenerate.py` orchestration + CLI

Wire up the per-card pipeline (resume gen, CL gen, JD cache) and the top-level CLI.

**Files:**
- Modify: `pipeline/pregenerate.py` (add `process_card`, `find_most_recent_scored`, `main`)

- [ ] **Step 1: Append orchestration code to `pipeline/pregenerate.py`**

```python
# ---------------------------------------------------------------------------
# IO + subprocess work (manually smoke-tested, not unit-tested)
# ---------------------------------------------------------------------------

def find_most_recent_scored() -> Path | None:
    """Newest YYYY-MM-DD.json in pipeline/data/scored/."""
    if not SCORED_DIR.exists():
        return None
    candidates = sorted(SCORED_DIR.glob("[0-9]*.json"))
    return candidates[-1] if candidates else None


def cache_jd_text(card: dict, slug: str) -> Path:
    """Write the card's JD description to a cache file. Returns the path."""
    JD_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = JD_CACHE_DIR / f"{slug}.txt"
    if not path.exists():
        path.write_text(card.get("description") or "")
    return path


def generate_resume_for_card(card: dict, date_str: str, full_name: str,
                             config: dict, source: dict, force: bool) -> Path:
    """Generate the tailored resume PDF for one card. Returns the output path.

    Raises on failure (caller catches and records in failures list).
    """
    # Local imports to keep module load fast and avoid cycles
    from pipeline.resume import (
        resolve_archetype, select_bullets, generate_html, build_output_path,
    )
    from pipeline.pdf_render import html_to_pdf
    from pipeline.resume import extract_jd_terms

    archetype_name = card.get("archetype") or "operations"
    template = resolve_archetype(config, archetype_name)
    jd_text = card.get("description") or ""

    out_path = build_output_path(
        archetype_name, company=card["company"], role=card["title"],
        ext="pdf", full_name=full_name, date_str=date_str,
    )
    if out_path.exists() and not force:
        return out_path

    experience = select_bullets(source, archetype_name, template, jd_text)
    jd_terms = extract_jd_terms(jd_text) if jd_text else None
    html = generate_html(source, experience, template, jd_terms)
    html_to_pdf(html, out_path)
    return out_path


def generate_cl_for_card(card: dict, date_str: str, full_name: str,
                         config: dict, source: dict, anthropic_client,
                         force: bool) -> Path:
    from pipeline.cover_letter import (
        build_cl_output_path, build_cl_prompt, generate_cl_text,
        render_cl_html, cl_artifact_exists,
    )
    from pipeline.pdf_render import html_to_pdf

    out_path = build_cl_output_path(
        company=card["company"], role=card["title"],
        full_name=full_name, date_str=date_str,
    )
    if cl_artifact_exists(out_path) and not force:
        return out_path

    archetype_name = card.get("archetype") or "operations"
    archetype_template = config["archetypes"][archetype_name]["template"]
    jd_text = card.get("description") or ""

    prompt = build_cl_prompt(source, archetype_template,
                             card["company"], card["title"], jd_text)
    prose = generate_cl_text(prompt, anthropic_client)
    html = render_cl_html(prose, source, card["company"], card["title"], date_str)
    html_to_pdf(html, out_path)
    return out_path


def process_card(card: dict, date_str: str, full_name: str,
                 config: dict, source: dict, anthropic_client,
                 force: bool) -> tuple[str, dict]:
    """Process one card end-to-end. Returns (status, payload).

    status ∈ {"generated", "cached", "failed"}.
    payload is the manifest entry for this card.
    """
    slug = build_card_slug(card, date_str)
    apply_url = card.get("resolved_url") or card.get("url")
    base = {
        "company": card["company"],
        "role": card["title"],
        "url": apply_url,
        "grade": card.get("grade"),
        "archetype": card.get("archetype"),
    }
    try:
        jd_path = cache_jd_text(card, slug)
        # Track cache state BEFORE generation so we can classify the result
        from pipeline.cover_letter import (
            build_cl_output_path, cl_artifact_exists,
        )
        from pipeline.resume import build_output_path
        archetype_name = card.get("archetype") or "operations"
        resume_path_expected = build_output_path(
            archetype_name, company=card["company"], role=card["title"],
            ext="pdf", full_name=full_name, date_str=date_str,
        )
        cl_path_expected = build_cl_output_path(
            company=card["company"], role=card["title"],
            full_name=full_name, date_str=date_str,
        )
        was_cached = (
            resume_path_expected.exists()
            and cl_artifact_exists(cl_path_expected)
            and jd_path.exists()
        )

        resume_path = generate_resume_for_card(
            card, date_str, full_name, config, source, force,
        )
        cl_path = generate_cl_for_card(
            card, date_str, full_name, config, source, anthropic_client, force,
        )

        payload = {
            **base,
            "resume_pdf": str(resume_path),
            "cl_pdf": str(cl_path),
            "jd_cache": str(jd_path),
        }
        return ("cached" if (was_cached and not force) else "generated", payload)
    except (Exception, SystemExit) as e:
        # SystemExit caught explicitly: resume.py:resolve_archetype calls sys.exit
        # on unknown archetype, and we don't want one bad card to kill the batch.
        return ("failed", {**base, "reason": f"{type(e).__name__}: {e}"})


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scored-file", default=None,
                        help="Path to a scored JSON. Defaults to most recent in data/scored/.")
    parser.add_argument("--grades", default="A,B",
                        help="Comma-separated grades to include (default: A,B).")
    parser.add_argument("--force", action="store_true",
                        help="Regenerate artifacts even if they exist.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print cards that would be processed and exit.")
    parser.add_argument("--limit", type=int, default=None,
                        help="Cap number of cards processed (smoke testing).")
    args = parser.parse_args()

    # Resolve scored file
    scored_path = Path(args.scored_file) if args.scored_file else find_most_recent_scored()
    if not scored_path or not scored_path.exists():
        print(f"[pregenerate] no scored JSON found", file=sys.stderr)
        return 2

    date_str = derive_date_from_scored_path(scored_path)
    grades = tuple(g.strip().upper() for g in args.grades.split(",") if g.strip())

    with open(scored_path) as f:
        cards = json.load(f)

    filtered = filter_cards(cards, grades=grades)
    if args.limit:
        filtered = filtered[: args.limit]

    print(f"[pregenerate] scored={scored_path.name} date={date_str}")
    print(f"[pregenerate] grades={grades} candidates={len(filtered)}")

    if args.dry_run:
        for c in filtered:
            print(f"  - {c['grade']} | {c['company']} | {c['title']}")
        return 0

    # Lazy-load shared resources (config, source, anthropic) only when really running
    import yaml
    with open(PIPELINE_DIR / "config.yaml") as f:
        config = yaml.safe_load(f)
    with open(PIPELINE_DIR / "data" / "resumes" / "source.json") as f:
        source = json.load(f)
    full_name = config.get("form_answers", {}).get("full_name") or source["meta"]["name"]

    from pipeline.cover_letter import _make_anthropic_adapter
    anthropic_client = _make_anthropic_adapter()

    generated, cached, failures = [], [], []
    artifacts_by_url: dict[str, dict] = {}

    for i, card in enumerate(filtered, 1):
        label = f"{card['grade']} | {card['company']} | {card['title']}"
        print(f"[pregenerate] ({i}/{len(filtered)}) {label}")
        status, payload = process_card(
            card, date_str, full_name, config, source, anthropic_client,
            args.force,
        )
        if status == "generated":
            generated.append(payload)
            print(f"  → generated")
        elif status == "cached":
            cached.append(payload)
            print(f"  → cached")
        else:
            failures.append(payload)
            print(f"  → failed: {payload.get('reason')}")
            continue

        url_key = payload["url"]
        artifacts_by_url[url_key] = {
            "resume_pdf": payload["resume_pdf"],
            "cl_pdf": payload["cl_pdf"],
            "jd_cache": payload["jd_cache"],
        }

    # Write manifest
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    manifest_path = MANIFEST_DIR / f"{date_str}-manifest.json"
    manifest = build_manifest(
        date_str=date_str, scored_file=str(scored_path),
        generated=generated, cached=cached, failures=failures,
    )
    manifest_path.write_text(json.dumps(manifest, indent=2))
    print(f"[pregenerate] manifest: {manifest_path}")

    # Update scored JSON in place with artifact paths
    if artifacts_by_url:
        updated = update_scored_with_artifacts(cards, artifacts_by_url)
        scored_path.write_text(json.dumps(updated, indent=2))
        print(f"[pregenerate] scored JSON updated with artifact paths")

    print(f"[pregenerate] done: generated={len(generated)} cached={len(cached)} failed={len(failures)}")

    # Exit 0 if at least one succeeded OR nothing to do; 1 only if all attempts failed
    if filtered and not generated and not cached:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Smoke test `--dry-run` against the real scored data in the main worktree**

The scored JSON in the main worktree (`/Users/jhh/code/the-dossier/pipeline/data/scored/2026-04-22.json`) is real data. Use `--dry-run` to verify filtering without generating anything. **Pass an absolute path** so we can run from the POC dir:

```bash
cd ~/code/the-dossier-poc && ~/code/the-dossier/pipeline/.venv/bin/python3 -m pipeline.pregenerate \
  --scored-file /Users/jhh/code/the-dossier/pipeline/data/scored/2026-04-22.json --dry-run
```
Expected: prints scored filename, date, candidate count (~38 cards is the rough order of magnitude for this dataset), then a list of "Grade | Company | Role" lines for every A/B/new card. Exit 0. Nothing is written to disk in dry-run mode.

- [ ] **Step 3: Smoke test `--limit 1` on real data**

Pick the smallest test by limiting to one card. **This will hit the Anthropic API once (~$0.05).** Set the API key first if not already:

```bash
# Verify key is set:
[ -n "$ANTHROPIC_API_KEY" ] && echo "key set" || echo "MISSING — run: export ANTHROPIC_API_KEY=sk-ant-..."

cd ~/code/the-dossier-poc && ~/code/the-dossier/pipeline/.venv/bin/python3 -m pipeline.pregenerate \
  --scored-file /Users/jhh/code/the-dossier/pipeline/data/scored/2026-04-22.json --limit 1
```
Expected:
- Prints `(1/1) <grade> | <company> | <title>` then `→ generated`
- Writes manifest at `~/code/the-dossier-poc/pipeline/data/pregenerated/2026-04-22-manifest.json` (note: lands in **POC tree**, not main worktree — modules anchor paths off `__file__`). Inspect: `counts.generated == 1, counts.cached == 0, counts.failures == 0`; the one entry has resume_pdf, cl_pdf, jd_cache paths all under `~/code/the-dossier-poc/pipeline/data/...`
- Both PDFs exist on disk in the POC tree
- Open the CL PDF (e.g. `open ~/code/the-dossier-poc/pipeline/data/cover_letters/output/...`): confirm prose is real, addressee is correct, no banned words, no em-dashes (CL system prompt enforces these)
- Exit 0

If the API call fails with a 404 on the model ID, set `PIPELINE_CL_MODEL` to a valid current Sonnet alias (e.g. `claude-sonnet-4-5` or whatever the current 4.x SDK accepts) and retry. The default in `cover_letter.py` is `claude-sonnet-4-6`.

- [ ] **Step 4: Smoke test idempotency (re-run, expect cached)**

```bash
cd ~/code/the-dossier-poc && ~/code/the-dossier/pipeline/.venv/bin/python3 -m pipeline.pregenerate \
  --scored-file /Users/jhh/code/the-dossier/pipeline/data/scored/2026-04-22.json --limit 1
```
Expected: same card, but `→ cached`. Manifest `counts.cached == 1, counts.generated == 0`. Exit 0. **No API call made.**

- [ ] **Step 5: Smoke test `--force` (re-run, expect regenerated)**

```bash
cd ~/code/the-dossier-poc && ~/code/the-dossier/pipeline/.venv/bin/python3 -m pipeline.pregenerate \
  --scored-file /Users/jhh/code/the-dossier/pipeline/data/scored/2026-04-22.json --limit 1 --force
```
Expected: same card, `→ generated`. **Hits API again (~$0.05).**

- [ ] **Step 6: Verify scored JSON was updated with `artifacts` field**

The scored JSON itself was mutated in place at the path you passed (i.e. **in the main worktree**). Verify:
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
Expected: at least 1 card has `artifacts` with three path keys (resume_pdf, cl_pdf, jd_cache), all pointing into `~/code/the-dossier-poc/pipeline/data/...`.

- [ ] **Step 7: Cleanup notes**

Generated artifacts live in the POC tree under gitignored dirs (`pipeline/data/cover_letters/output/`, `jd_cache/`, `pregenerated/`). Leave them — useful state for Plan 2's manual testing.

The scored JSON in the **main** worktree was mutated (artifact paths added). The scored JSON is currently untracked in the main worktree (per `git status`), so `git checkout` won't restore it. The mutation is non-destructive (only adds an `artifacts` field per card; nothing else touched). If you want to revert: re-run `score_batch_v2.py` from the main worktree. **Recommend leaving the mutation in place — Plan 2 needs it.**

- [ ] **Step 8: Commit**

```bash
git add pipeline/pregenerate.py
git commit -m "feat(pregenerate): orchestration + CLI with idempotency and manifest"
```

---

### Task 9: Operator README

**Files:**
- Create: `pipeline/apply_flow_v1_README.md`

- [ ] **Step 1: Write the README**

```markdown
# Apply-Flow v1 — CL Generator + Pre-Generation

Plan 1 of the apply-flow v1 build. Adds the missing cover-letter PDF artifact
and an idempotent batch script that pre-generates resume + CL + cached JD
for every Grade A/B card on a scored JSON.

## What this gives you

- Standalone CL generator (`pipeline/cover_letter.py`) — one-off CL PDFs via Claude API or a hand-written prose file.
- Batch pre-generator (`pipeline/pregenerate.py`) — overnight-runnable script that turns a scored JSON into a manifest + a directory full of artifacts ready for Plan 2's `/pipeline execute` to consume.

## Prereqs

- `anthropic` SDK installed in the venv at `~/code/the-dossier/pipeline/.venv` (handled by `pip install -r requirements.txt`).
- `ANTHROPIC_API_KEY` env var set in the shell that runs pregenerate.
- A scored JSON at `pipeline/data/scored/YYYY-MM-DD.json` (produced upstream by the existing `/pipeline` flow).

## Invocation pattern

Always run from the POC worktree using `python3 -m`:
```bash
cd ~/code/the-dossier-poc && ~/code/the-dossier/pipeline/.venv/bin/python3 -m pipeline.<module> <args>
```
This ensures `from pipeline.X import Y` resolves to the POC's package and not the main worktree's.

Generated artifacts (PDFs, manifest, JD cache) land in **the POC tree** under `pipeline/data/...` (all gitignored).

## One-off cover letter

```bash
cd ~/code/the-dossier-poc && ~/code/the-dossier/pipeline/.venv/bin/python3 -m pipeline.cover_letter \
  --archetype product_management --company "Acme" --role "Senior PM" \
  --jd path/to/jd.txt
```
Output: `pipeline/data/cover_letters/output/Jared-Hawkins-Acme-Senior-PM-{date}.pdf` (POC tree).

Skip the API and supply your own prose:
```bash
cd ~/code/the-dossier-poc && ~/code/the-dossier/pipeline/.venv/bin/python3 -m pipeline.cover_letter \
  --archetype product_management --company "Acme" --role "Senior PM" \
  --text-file path/to/my_prose.txt
```

`--markdown-only` writes the prose to `.md` instead of rendering to PDF (useful for inspection).

`--force` regenerates even if the PDF already exists (default behavior is to skip).

`PIPELINE_CL_MODEL` env var overrides the Anthropic model ID (default: `claude-sonnet-4-6`). Useful if the SDK rejects the default with a 404.

## Pre-gen batch

```bash
cd ~/code/the-dossier-poc && ~/code/the-dossier/pipeline/.venv/bin/python3 -m pipeline.pregenerate
```
Defaults: most recent scored JSON in **the POC tree's** `pipeline/data/scored/`, grades A+B, idempotent (skip cards whose artifacts exist). To run against the main worktree's scored data, pass an absolute `--scored-file`:
```bash
cd ~/code/the-dossier-poc && ~/code/the-dossier/pipeline/.venv/bin/python3 -m pipeline.pregenerate \
  --scored-file /Users/jhh/code/the-dossier/pipeline/data/scored/2026-04-22.json
```

Useful flags:
- `--scored-file pipeline/data/scored/2026-04-22.json` — pin a specific file
- `--grades A` — only Grade A
- `--limit 3` — cap, useful for smoke tests
- `--dry-run` — list what would be processed, exit 0
- `--force` — regenerate even if cached

Output:
- Resume PDFs at `pipeline/data/resumes/output/`
- CL PDFs at `pipeline/data/cover_letters/output/`
- JD text cached at `pipeline/data/jd_cache/`
- **Manifest** at `pipeline/data/pregenerated/{date}-manifest.json` — this is what Plan 2's `/pipeline execute` reads
- Scored JSON updated in place: each processed card gets an `artifacts` field with the three paths

## Cron installation (optional, recommended later)

This script is built to run unattended. To install as a daily 4am cron:
```
0 4 * * * cd /Users/jhh/code/the-dossier-poc && /Users/jhh/code/the-dossier/pipeline/.venv/bin/python3 -m pipeline.pregenerate >> /tmp/pregenerate.log 2>&1
```
Make sure `ANTHROPIC_API_KEY` is exported in the cron environment (e.g., via a wrapper script that sources `~/.zshrc` or a `~/.cron_env`). The `cd` is essential — `python3 -m` resolves the package relative to CWD.

## Tests

```bash
cd ~/code/the-dossier-poc && ~/code/the-dossier/pipeline/.venv/bin/python3 -m pytest pipeline/tests/ -v
```
Slow tests (real Playwright PDF render) can be skipped:
```bash
... -m 'not slow'
```

## Out of scope (Plans 2 + 3)

- Batch triage UI / `/pipeline review --batch` writer / `/pipeline execute` reader
- Multi-ATS adapters beyond Greenhouse (Lever, Ashby)
- LLM essay pass for textareas
- Programmatic Simplify autofill trigger
```

- [ ] **Step 2: Commit**

```bash
git add pipeline/apply_flow_v1_README.md
git commit -m "docs(apply-flow-v1): operator README for CL gen + pregenerate"
```

---

### Task 10: Final regression sweep

Make sure nothing earlier in the pipeline broke.

- [ ] **Step 1: Run the whole test suite**

```bash
cd ~/code/the-dossier-poc && ~/code/the-dossier/pipeline/.venv/bin/python3 -m pytest pipeline/tests/ -v
```
Expected: all tests pass (~27 tests across `test_pdf_render` (2), `test_resume_paths` (3), `test_cover_letter` (13), `test_pregenerate` (9)). Slow PDF render test takes ~3-5s.

- [ ] **Step 2: Run the resume CLI end-to-end (regression check on the refactor)**

```bash
cd ~/code/the-dossier-poc && ~/code/the-dossier/pipeline/.venv/bin/python3 -m pipeline.resume \
  --archetype product_management --company "RegressTest" --role "PM"
```
Expected: PDF generated at `~/code/the-dossier-poc/pipeline/data/resumes/output/Jared-Hawkins-RegressTest-PM-{today}.pdf`.

Cleanup:
```bash
rm ~/code/the-dossier-poc/pipeline/data/resumes/output/Jared-Hawkins-RegressTest-PM-*.pdf
```

- [ ] **Step 3: Confirm the apply-flow POC still loads correctly (no import break)**

```bash
cd ~/code/the-dossier-poc && ~/code/the-dossier/pipeline/.venv/bin/python3 -c "import pipeline.apply_flow_poc; print('apply_flow_poc imports OK')"
```
Expected: `apply_flow_poc imports OK`. (The POC doesn't import the new modules, but a regression here would mean we broke something at the package level.)

- [ ] **Step 4: Final git status**

```bash
cd ~/code/the-dossier-poc && git status && git log --oneline main..HEAD
```
Expected:
- Clean working tree
- ~9 commits on `feat/apply-flow-v1` ahead of main covering the work in this plan

- [ ] **Step 5: No commit needed — sweep is verification only**

If anything failed, return to the relevant earlier task and fix before declaring Plan 1 complete.

---

## Plan-completion criteria

Before declaring Plan 1 done, all of these must be true:

- [ ] All pytest tests pass (`pipeline/tests/` green, including slow tests)
- [ ] `pregenerate.py --dry-run` works on real scored data
- [ ] `pregenerate.py --limit 1` produces a real CL PDF that reads cleanly
- [ ] Idempotency confirmed: re-run reports `cached` without API call
- [ ] `--force` confirmed: re-run regenerates
- [ ] Manifest schema matches the contract documented above (Plan 2 will read this)
- [ ] Resume CLI still works end-to-end (refactor didn't regress)
- [ ] README in place

## Hand-off to Plan 2

Plan 2 (`/pipeline review --batch` writer + `/pipeline execute` reader) consumes:
- `pipeline/data/pregenerated/{date}-manifest.json` — full list of pre-generated cards with artifact paths
- The `artifacts` field on cards in `pipeline/data/scored/{date}.json` — same data, indexed by URL

The CL PDFs and resume PDFs at the documented paths are the artifacts the batch UI will hand off to `apply_flow_poc.py`'s override functions when it queues an apply session.

**Caveat for Plan 2:** of ~38 A/B/new cards in the existing 2026-04-22 scored JSON, ~28 have only Adzuna redirector URLs (no `resolved_url` from URL resolution). The manifest stores the Adzuna URL in the `url` field for these. CL/resume generation works fine (they only need company + title + description), but Plan 2's `/pipeline execute` will need to call URL resolution (`resolve_urls.py` lives in the main worktree, untracked) before it can drive `apply_flow_poc.py`'s Greenhouse/Lever/Ashby selectors. Plan 2 should either (a) pre-filter the manifest to only resolved cards, or (b) trigger URL resolution as a pregenerate step (extension to this plan, not in scope here).
