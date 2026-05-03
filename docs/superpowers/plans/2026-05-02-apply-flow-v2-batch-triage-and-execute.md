# Apply-Flow v2 — Batch Triage UI + Execute Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **REVISED 2026-05-02** post ai-chat pressure-test. Added Task 0 (ledger schema migration), expanded Task 2 (tracker.py with status enum + ledger upsert + atomicity), inserted Task 9.5 (ats_signals.py), expanded Task 10 (execute loop with confirmation poll + uncertainty-aware writes). See the revised spec for the full state-authority model.

**Goal:** Add `/pipeline review --batch` (writes a vault triage markdown from the Plan 1 manifest) and `/pipeline execute` (drives Playwright through ticked cards, pauses for human submit, polls for ATS confirmation, logs Applied/Unverified/Failed to Application Tracker, with ledger-first authority for retry semantics).

**Architecture:** Five new Python modules + one shared helper inside `pipeline/`. (1) `triage_writer.py` reads the manifest + scored JSON and writes a daily triage markdown into the vault. (2) `execute.py` parses the triage markdown, filters by ledger eligibility, drives a persistent Playwright session through eligible cards (override resume + CL via `set_input_files`), pauses per card for human review/submit, polls for ATS confirmation, then writes status-aware tracker + ledger rows. (3) `tracker.py` + `tracker_cli.py` extract the Application-Tracker-write + dedup-ledger logic with status enum (Applied | Unverified | Failed) and ledger upsert (attempt_count + last_attempt_at) and atomicity wrapper (`record_attempt`). (4) `ats_signals.py` provides typed dispatch for post-submit confirmation detection (Greenhouse only Plan 2). (5) `migrate_ledger.py` is a one-shot idempotent script adding `last_attempt_at` and `attempt_count` columns to existing ledger.tsv. Plus one small change to `cover_letter.py` (persist `.md` alongside `.pdf`) and one extraction (`override_greenhouse_artifacts()` from `apply_flow_poc.py`).

**Tech Stack:** Python 3.x, Playwright (already installed), `pyyaml` (existing), `pytest` (existing dev dep), no new external dependencies.

**Spec source:** `/Users/jhh/code/the-dossier-apply-flow-v2/docs/superpowers/specs/2026-05-02-apply-flow-v2-batch-triage-and-execute-design.md`

**Worktree:** `~/code/the-dossier-apply-flow-v2/` on branch `feat/apply-flow-v2`. All paths below are relative to that worktree unless absolute.

**Invocation pattern:** Run scripts as `cd ~/code/the-dossier-apply-flow-v2 && pipeline/.venv/bin/python3 -m pipeline.<module>`. The venv is local to this worktree (created during setup, not shared with main worktree). Tests run as `pipeline/.venv/bin/python3 -m pytest pipeline/tests/ -q`.

**Predecessor plans (read for style + context):**
- `docs/superpowers/plans/2026-05-01-apply-flow-v1-cl-pdf-pregeneration.md` — Plan 1 (manifest contract this reads)
- `docs/superpowers/plans/2026-05-01-cl-cli-backend-pivot.md` — CLI backend swap
- `docs/superpowers/plans/2026-04-30-apply-flow-poc.md` — POC (provides `override_resume`, `override_cover_letter`)

---

## Locked Decisions (from spec, do not relitigate)

| Question | Decision |
|---|---|
| Markdown shape | Option A: section-per-card, verbose, vault-side |
| Triage path | `~/Documents/Second Brain/99_System/Job Search/Daily Triage YYYY-MM-DD.md` |
| Unresolved-URL strategy | Strategy C: surface with strikethrough checkbox + warning |
| State authority | **Ledger is truth.** Markdown is intent. `build_queue` filters by `ledger_eligible(card)` |
| Persistence | Markdown `[x] apply` → `[x] applied` (cosmetic only on confirmed); ledger upsert with status + attempt_count + last_attempt_at is the durable record |
| Submit mode | Pause-before-submit per card |
| Submit verification | Post-Enter, `ats_signals.detect_confirmation` polls ~10s for Greenhouse signals (URL or DOM). Hit → Applied; miss → Unverified |
| Tier A pitch | End-of-session prompt (only Confirmed-Applied A grades) |
| Outreach hook | Skip — Application Tracker only |
| CL preview source | First 200 chars of persisted `.md` sibling of CL PDF |
| Tracker integration | Extract to `pipeline/tracker.py`; `/apply` skill calls `tracker_cli.py`. Tracker is append-only attempt log (status enum: Applied / Unverified / Failed) |
| Simplify wait | `simplify_wait_seconds` config (default 3) + `--simplify-wait` flag + `PIPELINE_EXECUTE_SIMPLIFY_WAIT` env. Sleep is floor; poll for done up to 2× as ceiling |

---

## File Structure

**Create (committed):**
- `pipeline/migrate_ledger.py` — one-shot idempotent migration adding `last_attempt_at` + `attempt_count` columns
- `pipeline/triage_writer.py` — manifest + scored JSON → daily triage markdown
- `pipeline/execute.py` — parser + Playwright driver + state writer (ledger-first queue)
- `pipeline/tracker.py` — Application Tracker append + ledger upsert + `record_attempt` atomicity wrapper + `ledger_eligible` rule encoding
- `pipeline/tracker_cli.py` — thin `python -m` wrapper for `/apply` skill use (with `--status` flag)
- `pipeline/cl_flag_scan.py` — regex-based CL pre-flight scanner
- `pipeline/ats_signals.py` — typed dispatch for post-submit confirmation detection (Greenhouse only Plan 2)
- `pipeline/tests/test_migrate_ledger.py`
- `pipeline/tests/test_triage_writer.py`
- `pipeline/tests/test_execute_parser.py`
- `pipeline/tests/test_execute_state.py`
- `pipeline/tests/test_cl_flag_scan.py`
- `pipeline/tests/test_tracker.py`
- `pipeline/tests/test_ats_signals.py`
- `pipeline/tests/test_execute_e2e.py` (slow-marked, gated)
- `pipeline/tests/fixtures/manifest_sample.json`
- `pipeline/tests/fixtures/scored_with_artifacts.json`
- `pipeline/tests/fixtures/triage_sample.md`
- `pipeline/tests/fixtures/cl_with_placeholder.md`
- `pipeline/tests/fixtures/cl_clean.md`
- `pipeline/tests/fixtures/fake_greenhouse.html`
- `pipeline/tests/fixtures/fake_greenhouse_thanks.html` (confirmation page for ats_signals tests)
- `pipeline/tests/fixtures/tracker_sample.md`
- `pipeline/tests/fixtures/ledger_sample.tsv`
- `pipeline/tests/fixtures/ledger_premigration.tsv` (without new columns)
- `pipeline/apply_flow_v2_README.md` — Operator docs for Plan 2

**Modify (committed):**
- `pipeline/cover_letter.py` — also write `.md` alongside `.pdf` in PDF render path (~3 LOC)
- `pipeline/apply_flow_poc.py` — extract `override_greenhouse_artifacts()` as importable function
- `.claude/skills/pipeline/SKILL.md` — add `review --batch` and `execute` subcommand sections
- `.claude/skills/apply/SKILL.md` — replace tracker steps with `python -m pipeline.tracker_cli` invocation

**Reference (read-only):**
- `pipeline/data/pregenerated/{date}-manifest.json` — input contract from Plan 1
- `pipeline/data/scored/{date}.json` — for `rationale`, `red_flags`, `salary`, `lane`
- `pipeline/data/cover_letters/output/{name}.md` — CL preview source (after cover_letter.py change)
- `~/Documents/Second Brain/02_Projects/Job Search/R - Application Tracker.md` — write target
- `pipeline/data/ledger.tsv` — dedup ledger

---

## Task Decomposition

15 tasks across 8 phases. Each task is independently committable.

| Phase | Tasks | Description |
|---|---|---|
| 0. Schema migration | 0 | `migrate_ledger.py` adds last_attempt_at + attempt_count columns |
| A. Foundation | 1, 2, 3 | CL `.md` persistence + tracker extraction (status enum + upsert + atomicity) |
| B. /apply skill rewrite | 4 | Skill markdown delegates to `tracker_cli --status applied` |
| C. CL flag scanner | 5 | Pre-flight regex scanner (used by execute) |
| D. triage_writer | 6, 7 | Pure functions, then file I/O + idempotency |
| E. execute parser/state | 8 | Pure parser + state-write functions |
| F. execute Playwright | 9, 9.5, 10 | POC extraction + ats_signals.py + main loop with verification poll |
| G. /pipeline skill + e2e + README | 11, 12, 13 | Skill markdown + gated e2e + operator docs |

---

## Phase 0 — Schema migration

### Task 0: Implement `pipeline/migrate_ledger.py` — one-shot ledger column migration

**Files:**
- Create: `pipeline/migrate_ledger.py`
- Create: `pipeline/tests/test_migrate_ledger.py`
- Create: `pipeline/tests/fixtures/ledger_premigration.tsv`

**Context:** The pressure-test (2026-05-02) exposed that the existing ledger schema can't represent uncertainty. Plan 2 adds two columns (`last_attempt_at` ISO timestamp, `attempt_count` int) and expands the status enum (was `applied | seen | pitched`; gains `unverified | failed | skipped`). This task ships the one-shot migration. Subsequent tasks assume the new schema is in place.

The migration is **idempotent**: if the new columns already exist in the header, it's a no-op. Backfill: existing rows get `last_attempt_at = date_first_seen`, `attempt_count = 1`. Status values stay as-is.

- [ ] **Step 1: Create the pre-migration fixture**

`pipeline/tests/fixtures/ledger_premigration.tsv` (use literal tabs, not spaces):

```
url	company	normalized_title	location	date_first_seen	score	grade	status
	Updater	technical product lead		2026-03-25			applied
	ActBlue	product manager		2026-03-24			applied
https://example.com	Pitched Co	pm		2026-04-15			pitched
```

- [ ] **Step 2: Write failing tests in `pipeline/tests/test_migrate_ledger.py`**

```python
"""Tests for pipeline.migrate_ledger — one-shot ledger schema migration."""
import csv
import shutil
from pathlib import Path

import pytest

from pipeline.migrate_ledger import migrate_ledger, MigrationResult

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def pre_ledger(tmp_path):
    p = tmp_path / "ledger.tsv"
    shutil.copy(FIXTURES / "ledger_premigration.tsv", p)
    return p


def _read_rows(path):
    with open(path) as f:
        return list(csv.DictReader(f, delimiter="\t"))


def test_migration_adds_new_columns(pre_ledger):
    result = migrate_ledger(pre_ledger)
    assert result == MigrationResult.MIGRATED

    with open(pre_ledger) as f:
        header = f.readline().strip().split("\t")
    assert "last_attempt_at" in header
    assert "attempt_count" in header


def test_migration_backfills_last_attempt_at(pre_ledger):
    migrate_ledger(pre_ledger)
    rows = _read_rows(pre_ledger)
    by_company = {r["company"]: r for r in rows}
    assert by_company["Updater"]["last_attempt_at"] == "2026-03-25"
    assert by_company["ActBlue"]["last_attempt_at"] == "2026-03-24"


def test_migration_backfills_attempt_count(pre_ledger):
    migrate_ledger(pre_ledger)
    rows = _read_rows(pre_ledger)
    for r in rows:
        assert r["attempt_count"] == "1"


def test_migration_preserves_existing_status(pre_ledger):
    migrate_ledger(pre_ledger)
    rows = _read_rows(pre_ledger)
    by_company = {r["company"]: r for r in rows}
    assert by_company["Updater"]["status"] == "applied"
    assert by_company["Pitched Co"]["status"] == "pitched"


def test_migration_idempotent(pre_ledger):
    """Running twice is a no-op."""
    migrate_ledger(pre_ledger)
    first_text = pre_ledger.read_text()
    result = migrate_ledger(pre_ledger)
    assert result == MigrationResult.ALREADY_MIGRATED
    assert pre_ledger.read_text() == first_text


def test_migration_handles_missing_file(tmp_path):
    p = tmp_path / "nope.tsv"
    result = migrate_ledger(p)
    assert result == MigrationResult.MISSING


def test_migration_preserves_row_count(pre_ledger):
    pre_count = len(_read_rows(pre_ledger))
    migrate_ledger(pre_ledger)
    post_count = len(_read_rows(pre_ledger))
    assert pre_count == post_count
```

- [ ] **Step 3: Run to verify failure**

```bash
cd ~/code/the-dossier-apply-flow-v2 && pipeline/.venv/bin/python3 -m pytest pipeline/tests/test_migrate_ledger.py -v
```
Expected: FAIL — `No module named pipeline.migrate_ledger`.

- [ ] **Step 4: Implement `pipeline/migrate_ledger.py`**

```python
"""One-shot, idempotent ledger schema migration.

Adds `last_attempt_at` and `attempt_count` columns to existing ledger.tsv.
Existing rows get backfilled: last_attempt_at = date_first_seen, attempt_count = 1.

Run once after upgrading to Plan 2; not part of normal /pipeline flow.

Usage:
    cd ~/code/the-dossier-apply-flow-v2 && pipeline/.venv/bin/python3 -m pipeline.migrate_ledger
    cd ~/code/the-dossier-apply-flow-v2 && pipeline/.venv/bin/python3 -m pipeline.migrate_ledger --ledger-path /path/to/ledger.tsv
"""
from __future__ import annotations

import argparse
import csv
import enum
import sys
from pathlib import Path


NEW_COLUMNS = ("last_attempt_at", "attempt_count")


class MigrationResult(enum.Enum):
    MIGRATED = "migrated"
    ALREADY_MIGRATED = "already_migrated"
    MISSING = "missing"


def migrate_ledger(ledger_path: Path) -> MigrationResult:
    """Add last_attempt_at + attempt_count columns to ledger.tsv if missing.
    Backfills existing rows. Idempotent."""
    if not ledger_path.exists():
        return MigrationResult.MISSING

    with open(ledger_path) as f:
        reader = csv.DictReader(f, delimiter="\t")
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])

    if all(c in fieldnames for c in NEW_COLUMNS):
        return MigrationResult.ALREADY_MIGRATED

    # Backfill new columns
    for col in NEW_COLUMNS:
        if col not in fieldnames:
            fieldnames.append(col)
    for r in rows:
        if "last_attempt_at" not in r or not r.get("last_attempt_at"):
            r["last_attempt_at"] = r.get("date_first_seen", "")
        if "attempt_count" not in r or not r.get("attempt_count"):
            r["attempt_count"] = "1"

    with open(ledger_path, "w") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        for r in rows:
            writer.writerow(r)

    return MigrationResult.MIGRATED


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger-path",
                        default=str(Path(__file__).resolve().parent / "data" / "ledger.tsv"))
    args = parser.parse_args(argv)

    result = migrate_ledger(Path(args.ledger_path))
    if result == MigrationResult.MIGRATED:
        print(f"[migrate-ledger] migrated: {args.ledger_path}")
        return 0
    elif result == MigrationResult.ALREADY_MIGRATED:
        print(f"[migrate-ledger] already migrated: {args.ledger_path}")
        return 0
    elif result == MigrationResult.MISSING:
        print(f"[migrate-ledger] file not found: {args.ledger_path}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: Run tests to verify pass**

```bash
cd ~/code/the-dossier-apply-flow-v2 && pipeline/.venv/bin/python3 -m pytest pipeline/tests/test_migrate_ledger.py -v
```
Expected: 7 passed.

- [ ] **Step 6: Run migration against the real ledger (manual smoke test)**

Run against the main worktree's ledger to confirm it works on real data. **DO NOT commit the modified ledger.tsv** — it's gitignored, but worth confirming.

```bash
cd ~/code/the-dossier-apply-flow-v2 && pipeline/.venv/bin/python3 -m pipeline.migrate_ledger \
  --ledger-path /Users/jhh/code/the-dossier/pipeline/data/ledger.tsv
```
Expected: `[migrate-ledger] migrated: ...` (or `already migrated` on subsequent runs).

Verify by eyeballing the file:
```bash
head -3 /Users/jhh/code/the-dossier/pipeline/data/ledger.tsv
```
Expected: header includes `last_attempt_at` and `attempt_count`; existing rows have populated values.

**IMPORTANT:** This migration runs against the shared ledger. The new columns are forward-compatible — old code (Plan 1, current main branch) reads via `csv.DictReader` and ignores unknown columns. So you can migrate now even before merging.

- [ ] **Step 7: Run full suite**

```bash
cd ~/code/the-dossier-apply-flow-v2 && pipeline/.venv/bin/python3 -m pytest pipeline/ -q -m "not slow"
```
Expected: 48+ passed (41 baseline + 7 new).

- [ ] **Step 8: Commit**

```bash
git add pipeline/migrate_ledger.py pipeline/tests/test_migrate_ledger.py pipeline/tests/fixtures/ledger_premigration.tsv
git commit -m "$(cat <<'EOF'
feat(migrate-ledger): one-shot idempotent ledger schema migration

Adds last_attempt_at + attempt_count columns to existing ledger.tsv.
Backfills last_attempt_at = date_first_seen, attempt_count = 1.
No-op if columns already present.

Forward-compatible: old code reads via csv.DictReader and ignores
unknown columns, so this can run before Plan 2 merges to main.

Required for Plan 2's ledger_eligible() retry semantics — without
attempt_count and last_attempt_at, unverified-status retry rules
can't be encoded.
EOF
)"
```

---

## Phase A — Foundation

### Task 1: Persist CL markdown alongside PDF in cover_letter.py

**Files:**
- Modify: `pipeline/cover_letter.py:417-420` (the section right before `html_to_pdf` is called)
- Test: `pipeline/tests/test_cover_letter.py` (add new test method)

**Context:** Currently the `--markdown-only` flag is the only path that writes the `.md` file. The PDF render path generates prose in-memory and goes straight to PDF. Plan 2 needs the `.md` available for the triage_writer's CL preview line. Smallest possible change: write the `.md` as a side effect of the PDF path too.

- [ ] **Step 1: Add failing test in `pipeline/tests/test_cover_letter.py`**

Find the section of test_cover_letter.py with the existing render tests (look for `def test_render_cl_html` or similar). Add this test after it:

```python
def test_pdf_path_also_writes_markdown(tmp_path, monkeypatch):
    """When the PDF render path runs, the .md sibling is also written."""
    from pipeline.cover_letter import _render_to_disk

    out_pdf = tmp_path / "Jared-Hawkins-AcmeCo-PM-2026-05-02.pdf"
    out_md = out_pdf.with_suffix(".md")

    # Stub html_to_pdf so we don't actually render
    monkeypatch.setattr(
        "pipeline.cover_letter.html_to_pdf",
        lambda html, path: path.write_bytes(b"%PDF-1.4 stub"),
    )

    prose = "Hello AcmeCo, I am applying for the PM role."
    html = "<html><body>fake</body></html>"
    _render_to_disk(prose, html, out_pdf)

    assert out_pdf.exists()
    assert out_md.exists()
    assert out_md.read_text() == prose
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd ~/code/the-dossier-apply-flow-v2 && pipeline/.venv/bin/python3 -m pytest pipeline/tests/test_cover_letter.py::test_pdf_path_also_writes_markdown -v
```
Expected: FAIL with `AttributeError: module 'pipeline.cover_letter' has no attribute '_render_to_disk'`.

- [ ] **Step 3: Implement `_render_to_disk` and refactor `main()` to use it**

In `pipeline/cover_letter.py`, near the bottom but BEFORE `def main()`:

```python
def _render_to_disk(prose: str, html: str, out_path: Path) -> None:
    """Write CL artifacts: PDF at out_path, markdown at out_path.with_suffix('.md')."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    md_path = out_path.with_suffix(".md")
    md_path.write_text(prose)
    html_to_pdf(html, out_path)
```

Then add this import near the top of `cover_letter.py` (next to other `from pipeline.*` imports if any, or just above `def main`):

```python
from pipeline.pdf_render import html_to_pdf
```

(It's already imported lazily inside `main()` at line ~418; lift it to module level so `_render_to_disk` and the test's monkeypatch see the same name.)

In `main()`, replace lines 417-420 (the block that does `html = render_cl_html(...)` then `html_to_pdf(html, out_path)`) with:

```python
    html = render_cl_html(prose, source, args.company, args.role, date_str)
    _render_to_disk(prose, html, out_path)
    print(f"[cover-letter] generated: {out_path}")
```

Remove the lazy `from pipeline.pdf_render import html_to_pdf` line that's currently inside `main()`.

- [ ] **Step 4: Run the test to verify it passes**

```bash
cd ~/code/the-dossier-apply-flow-v2 && pipeline/.venv/bin/python3 -m pytest pipeline/tests/test_cover_letter.py -v
```
Expected: all tests pass (the new one plus the existing ones).

- [ ] **Step 5: Update `pregenerate.generate_cl_for_card` to also use the new pathway**

Open `pipeline/pregenerate.py` and find `generate_cl_for_card` (around line 181-206). It currently calls `html_to_pdf(html, out_path)` directly. Change the last two lines to use `_render_to_disk` so pregenerate also writes `.md`:

```python
    from pipeline.cover_letter import _render_to_disk
    html = render_cl_html(prose, source, card["company"], card["title"], date_str)
    _render_to_disk(prose, html, out_path)
    return out_path
```

Also delete the now-unused `from pipeline.pdf_render import html_to_pdf` line at the top of `generate_cl_for_card` (it's no longer referenced — `_render_to_disk` handles the PDF render internally).

- [ ] **Step 6: Run full pipeline test suite to confirm no regression**

```bash
cd ~/code/the-dossier-apply-flow-v2 && pipeline/.venv/bin/python3 -m pytest pipeline/ -q -m "not slow"
```
Expected: 49+ passed (48 from Task 0 baseline + 1 new test in this task).

- [ ] **Step 7: Commit**

```bash
git add pipeline/cover_letter.py pipeline/pregenerate.py pipeline/tests/test_cover_letter.py
git commit -m "$(cat <<'EOF'
feat(cover-letter): persist .md alongside .pdf in render path

The triage_writer in Plan 2 needs the CL prose available for the preview
line in the daily triage markdown. Smallest change: write the .md as a
side effect of the existing PDF render path. The --markdown-only flag
keeps its existing meaning (skip PDF entirely).

Also updates pregenerate.generate_cl_for_card to use the same helper.
EOF
)"
```

---

### Task 2: Implement `pipeline/tracker.py` — Tracker (append-only) + ledger upsert + eligibility + atomicity

**Files:**
- Create: `pipeline/tracker.py`
- Create: `pipeline/tests/test_tracker.py`
- Create: `pipeline/tests/fixtures/tracker_sample.md`
- Create: `pipeline/tests/fixtures/ledger_sample.tsv` (post-migration shape, has the new columns)

**Context:** The `/apply` skill currently performs Application Tracker writes through Claude-driven Edit-tool calls. Plan 2's `execute.py` needs the same operation in pure Python. The pressure-test (2026-05-02) added these requirements:

1. Tracker is an **append-only attempt log**: each submission attempt produces one row. Status enum (Applied | Unverified | Failed) reflects that attempt's outcome.
2. Ledger is the **current-state record**: one row per (company, normalized_role). `upsert_ledger_row` finds-or-creates the row, increments `attempt_count`, sets `last_attempt_at`. Status enum (applied | unverified | failed | skipped + pre-existing seen | pitched).
3. **`ledger_eligible(card)`** encodes retry semantics: applied blocks always; unverified <24h cooling down; failed/unverified-old eligible.
4. **`record_attempt(card, status)`** is the atomicity wrapper — appends tracker row + upserts ledger row in a try/except so partial failure rolls back.

Task 0 (migrate_ledger) must run before this task so the ledger fixture has the new columns.

- [ ] **Step 1: Create test fixtures**

Create `pipeline/tests/fixtures/tracker_sample.md` with this exact content:

```markdown
---
Domain: "[[D - Career & Job Search]]"
tags: [job-search, tracker]
---

# Application Tracker

| Company | Role | Source | Date | Status | Notes |
|---|---|---|---|---|---|
| Updater | Technical Product Lead | Pipeline | 2026-03-25 | Applied | Pipeline logged |
| ActBlue | Product Manager | Pipeline | 2026-03-24 | Applied | Pipeline logged |
```

Create `pipeline/tests/fixtures/ledger_sample.tsv` with this exact content (post-migration shape; use literal tabs, not spaces):

```
url	company	normalized_title	location	date_first_seen	score	grade	status	last_attempt_at	attempt_count
	Updater	technical product lead		2026-03-25			applied	2026-03-25	1
	ActBlue	product manager		2026-03-24			applied	2026-03-24	1
```

- [ ] **Step 2: Write failing tests in `pipeline/tests/test_tracker.py`**

```python
"""Tests for pipeline.tracker — Tracker append + ledger upsert + eligibility + atomicity."""
import shutil
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from pipeline.tracker import (
    AppStatus,
    AppendResult,
    LedgerOp,
    normalize_title,
    format_tracker_row,
    append_tracker_row,
    upsert_ledger_row,
    ledger_eligible,
    record_attempt,
    remove_last_row,
)

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def tracker_path(tmp_path):
    p = tmp_path / "Tracker.md"
    shutil.copy(FIXTURES / "tracker_sample.md", p)
    return p


@pytest.fixture
def ledger_path(tmp_path):
    p = tmp_path / "ledger.tsv"
    shutil.copy(FIXTURES / "ledger_sample.tsv", p)
    return p


# --- normalize_title ---

def test_normalize_title_lowercases_and_strips_seniority():
    assert normalize_title("Senior Product Manager") == "product manager"
    assert normalize_title("Sr. Product Manager") == "product manager"
    assert normalize_title("Principal Product Manager") == "principal product manager"


def test_normalize_title_strips_location_suffix():
    assert normalize_title("Product Manager - Seattle, WA") == "product manager"
    assert normalize_title("Product Manager (Remote)") == "product manager"


# --- format_tracker_row + append_tracker_row (status-aware) ---

def test_format_tracker_row_default_status_applied():
    row = format_tracker_row(
        company="Orkes", role="Product Manager", source="Pipeline",
        date="2026-05-02", status=AppStatus.APPLIED, notes="Pipeline logged",
    )
    assert row == "| Orkes | Product Manager | Pipeline | 2026-05-02 | Applied | Pipeline logged |"


def test_format_tracker_row_unverified():
    row = format_tracker_row(
        company="X", role="Y", source="Pipeline",
        date="2026-05-02", status=AppStatus.UNVERIFIED, notes="",
    )
    assert "| Unverified |" in row


def test_format_tracker_row_failed():
    row = format_tracker_row(
        company="X", role="Y", source="Pipeline",
        date="2026-05-02", status=AppStatus.FAILED, notes="selector miss",
    )
    assert "| Failed |" in row
    assert "selector miss" in row


def test_append_tracker_row_appends_status(tracker_path):
    result = append_tracker_row(
        tracker_path, company="Orkes", role="Product Manager",
        source="Pipeline", date="2026-05-02",
        status=AppStatus.UNVERIFIED, notes="",
    )
    assert result == AppendResult.APPENDED
    text = tracker_path.read_text()
    assert "| Orkes | Product Manager | Pipeline | 2026-05-02 | Unverified |" in text
    # Existing rows preserved
    assert "Updater" in text


def test_append_tracker_row_creates_file_if_missing(tmp_path):
    p = tmp_path / "missing-tracker.md"
    result = append_tracker_row(
        p, company="X", role="Y", source="Pipeline",
        date="2026-05-02", status=AppStatus.APPLIED, notes="",
    )
    assert result == AppendResult.CREATED
    text = p.read_text()
    assert "| Company | Role | Source | Date | Status | Notes |" in text
    assert "| X | Y | Pipeline | 2026-05-02 | Applied |  |" in text


# --- upsert_ledger_row ---

def test_upsert_ledger_creates_new_row(ledger_path):
    op = upsert_ledger_row(
        ledger_path, url="https://example.com/jobs/9",
        company="NewCo", role="PM", location="Remote",
        date="2026-05-02", score="3.5", grade="B",
        status=AppStatus.APPLIED,
    )
    assert op == LedgerOp.CREATED

    import csv
    with open(ledger_path) as f:
        rows = list(csv.DictReader(f, delimiter="\t"))
    by_company = {r["company"]: r for r in rows}
    new_row = by_company["NewCo"]
    assert new_row["status"] == "applied"
    assert new_row["attempt_count"] == "1"
    assert new_row["last_attempt_at"] == "2026-05-02"


def test_upsert_ledger_updates_existing_row_increments_attempt_count(ledger_path):
    op = upsert_ledger_row(
        ledger_path, url="", company="Updater", role="Technical Product Lead",
        location="", date="2026-05-02", score="", grade="",
        status=AppStatus.UNVERIFIED,
    )
    assert op == LedgerOp.UPDATED

    import csv
    with open(ledger_path) as f:
        rows = list(csv.DictReader(f, delimiter="\t"))
    by_company = {r["company"]: r for r in rows}
    updater = by_company["Updater"]
    assert updater["status"] == "unverified"
    assert updater["attempt_count"] == "2"  # was 1, now 2
    assert updater["last_attempt_at"] == "2026-05-02"
    # date_first_seen preserved (still original)
    assert updater["date_first_seen"] == "2026-03-25"


def test_upsert_ledger_failed_status(ledger_path):
    op = upsert_ledger_row(
        ledger_path, url="https://x.com", company="ZetaCo", role="PM",
        location="", date="2026-05-02", score="", grade="A",
        status=AppStatus.FAILED,
    )
    assert op == LedgerOp.CREATED
    import csv
    with open(ledger_path) as f:
        rows = list(csv.DictReader(f, delimiter="\t"))
    by_company = {r["company"]: r for r in rows}
    assert by_company["ZetaCo"]["status"] == "failed"


# --- ledger_eligible (authority rules) ---

def test_ledger_eligible_returns_true_for_missing_row(ledger_path):
    assert ledger_eligible(ledger_path, company="NewCo", role="PM") is True


def test_ledger_eligible_returns_false_for_applied(ledger_path):
    assert ledger_eligible(
        ledger_path, company="Updater", role="Technical Product Lead",
    ) is False


def test_ledger_eligible_returns_false_for_unverified_within_24h(ledger_path):
    # Set Updater to unverified with a fresh timestamp
    now = datetime.now()
    upsert_ledger_row(
        ledger_path, url="", company="Updater", role="Technical Product Lead",
        location="", date=now.date().isoformat(), score="", grade="",
        status=AppStatus.UNVERIFIED,
    )
    # last_attempt_at gets set to today by upsert; should not be eligible yet
    assert ledger_eligible(
        ledger_path, company="Updater", role="Technical Product Lead",
    ) is False


def test_ledger_eligible_returns_true_for_unverified_after_24h(ledger_path, monkeypatch):
    # Set Updater to unverified with a stale timestamp
    upsert_ledger_row(
        ledger_path, url="", company="Updater", role="Technical Product Lead",
        location="", date="2026-04-30", score="", grade="",
        status=AppStatus.UNVERIFIED,
    )
    # Force ledger_eligible to think "now" is far in the future
    fake_now = datetime(2026, 5, 2, 12, 0, 0)
    assert ledger_eligible(
        ledger_path, company="Updater", role="Technical Product Lead",
        now=fake_now,
    ) is True


def test_ledger_eligible_returns_true_for_failed(ledger_path):
    upsert_ledger_row(
        ledger_path, url="", company="Updater", role="Technical Product Lead",
        location="", date="2026-05-02", score="", grade="",
        status=AppStatus.FAILED,
    )
    assert ledger_eligible(
        ledger_path, company="Updater", role="Technical Product Lead",
    ) is True


def test_ledger_eligible_returns_true_for_skipped(ledger_path):
    upsert_ledger_row(
        ledger_path, url="", company="Updater", role="Technical Product Lead",
        location="", date="2026-05-02", score="", grade="",
        status=AppStatus.SKIPPED,
    )
    assert ledger_eligible(
        ledger_path, company="Updater", role="Technical Product Lead",
    ) is True


# --- record_attempt (atomicity) ---

def test_record_attempt_writes_both_tracker_and_ledger(tracker_path, ledger_path):
    record_attempt(
        tracker_path=tracker_path, ledger_path=ledger_path,
        url="https://example.com/jobs/9",
        company="Orkes", role="Product Manager", source="Pipeline",
        location="Seattle", date="2026-05-02", score="3.8", grade="B",
        status=AppStatus.APPLIED, notes="",
    )

    # Tracker has new row
    assert "| Orkes |" in tracker_path.read_text()

    # Ledger has new row
    import csv
    with open(ledger_path) as f:
        rows = list(csv.DictReader(f, delimiter="\t"))
    assert any(r["company"] == "Orkes" for r in rows)


def test_record_attempt_rolls_back_tracker_on_ledger_failure(tracker_path, ledger_path, monkeypatch):
    """If ledger write fails, the tracker row is removed so states stay consistent."""
    pre_text = tracker_path.read_text()

    def boom(*args, **kwargs):
        raise IOError("simulated ledger write failure")
    monkeypatch.setattr("pipeline.tracker.upsert_ledger_row", boom)

    with pytest.raises(IOError):
        record_attempt(
            tracker_path=tracker_path, ledger_path=ledger_path,
            url="https://example.com/jobs/X",
            company="Orkes", role="Product Manager", source="Pipeline",
            location="", date="2026-05-02", score="", grade="B",
            status=AppStatus.APPLIED, notes="",
        )

    # Tracker file is unchanged from the pre-call state
    assert tracker_path.read_text() == pre_text


def test_remove_last_row_removes_only_matching_company(tracker_path):
    # Append a row, then remove it
    append_tracker_row(
        tracker_path, company="Orkes", role="PM", source="Pipeline",
        date="2026-05-02", status=AppStatus.APPLIED, notes="",
    )
    pre_text_with_orkes = tracker_path.read_text()
    assert "Orkes" in pre_text_with_orkes

    remove_last_row(tracker_path, expected_company="Orkes", expected_date="2026-05-02")
    post = tracker_path.read_text()
    assert "Orkes" not in post
    assert "Updater" in post  # Existing rows preserved
    assert "ActBlue" in post


def test_remove_last_row_no_op_if_company_doesnt_match(tracker_path):
    append_tracker_row(
        tracker_path, company="Orkes", role="PM", source="Pipeline",
        date="2026-05-02", status=AppStatus.APPLIED, notes="",
    )
    pre = tracker_path.read_text()
    # Try to remove a different company (defensive against race)
    remove_last_row(tracker_path, expected_company="WrongCo", expected_date="2026-05-02")
    assert tracker_path.read_text() == pre  # No change
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
cd ~/code/the-dossier-apply-flow-v2 && pipeline/.venv/bin/python3 -m pytest pipeline/tests/test_tracker.py -v
```
Expected: all FAIL with `ModuleNotFoundError: pipeline.tracker`.

- [ ] **Step 4: Implement `pipeline/tracker.py`**

```python
"""Application Tracker + dedup ledger writers.

Two surfaces:
- Tracker is APPEND-ONLY: each submission attempt produces one row.
  Status enum reflects that attempt's outcome.
- Ledger is UPSERT (one row per company+normalized_role). Records current
  state, attempt_count, last_attempt_at. Authoritative for ledger_eligible
  retry decisions.

`record_attempt` wraps both writes in atomicity (rollback tracker on
ledger failure) so states stay consistent.

Used by:
- pipeline.tracker_cli (called from /apply skill, default status=applied)
- pipeline.execute (Plan 2, called per-submit with verified status)
"""
from __future__ import annotations

import csv
import enum
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional


TRACKER_HEADER = "| Company | Role | Source | Date | Status | Notes |"
TRACKER_DIVIDER = "|---|---|---|---|---|---|"

UNVERIFIED_COOLDOWN = timedelta(hours=24)


class AppStatus(enum.Enum):
    APPLIED = "applied"
    UNVERIFIED = "unverified"
    FAILED = "failed"
    SKIPPED = "skipped"


# Tracker uses Title Case for human readability
_TRACKER_STATUS_DISPLAY = {
    AppStatus.APPLIED: "Applied",
    AppStatus.UNVERIFIED: "Unverified",
    AppStatus.FAILED: "Failed",
    AppStatus.SKIPPED: "Skipped",
}


class AppendResult(enum.Enum):
    APPENDED = "appended"
    CREATED = "created"


class LedgerOp(enum.Enum):
    CREATED = "created"
    UPDATED = "updated"


_LOCATION_SUFFIX = re.compile(
    r"\s*[-(\[].*?(remote|onsite|hybrid|[A-Z]{2}|seattle|new york|san francisco)[\])]?\s*$",
    re.IGNORECASE,
)


def normalize_title(title: str) -> str:
    """Lowercase, strip seniority prefixes (except principal/lead which we keep),
    strip trailing location suffixes."""
    t = title.strip().lower()
    t = re.sub(r"^(senior|sr\.?|junior|jr\.?|staff)\s+", "", t)
    t = _LOCATION_SUFFIX.sub("", t)
    return t.strip()


def format_tracker_row(
    *, company: str, role: str, source: str, date: str,
    status: AppStatus, notes: str,
) -> str:
    """Format a single tracker table row. Pipe-separated, no wikilinks."""
    status_display = _TRACKER_STATUS_DISPLAY[status]
    return f"| {company} | {role} | {source} | {date} | {status_display} | {notes} |"


def append_tracker_row(
    tracker_path: Path,
    *,
    company: str, role: str, source: str, date: str,
    status: AppStatus, notes: str,
) -> AppendResult:
    """Append a new row to the Application Tracker. Append-only: never deduplicates."""
    row = format_tracker_row(
        company=company, role=role, source=source, date=date,
        status=status, notes=notes,
    )

    if not tracker_path.exists():
        tracker_path.parent.mkdir(parents=True, exist_ok=True)
        tracker_path.write_text(
            f"{TRACKER_HEADER}\n{TRACKER_DIVIDER}\n{row}\n"
        )
        return AppendResult.CREATED

    text = tracker_path.read_text()
    if not text.endswith("\n"):
        text += "\n"
    tracker_path.write_text(text + row + "\n")
    return AppendResult.APPENDED


def remove_last_row(
    tracker_path: Path, *, expected_company: str, expected_date: str,
) -> bool:
    """Remove the LAST row from the tracker IF it matches expected_company AND expected_date.
    Defensive: returns False (no-op) if the last row doesn't match. Used for atomicity rollback.
    """
    if not tracker_path.exists():
        return False
    text = tracker_path.read_text()
    lines = text.splitlines(keepends=True)
    if not lines:
        return False
    # Walk backward to find the last data row (skip blank lines)
    for i in range(len(lines) - 1, -1, -1):
        line = lines[i].strip()
        if not line:
            continue
        if not line.startswith("| ") or "---" in line or "Company | Role" in line:
            return False  # Hit header/divider before finding data row → mismatch
        # Parse company + date (cols 1 and 4)
        parts = [p.strip() for p in line.strip("|").split("|")]
        if len(parts) < 5:
            return False
        if parts[0] == expected_company and parts[3] == expected_date:
            del lines[i]
            tracker_path.write_text("".join(lines))
            return True
        return False  # Last row doesn't match
    return False


def upsert_ledger_row(
    ledger_path: Path,
    *,
    url: str, company: str, role: str, location: str,
    date: str, score: str, grade: str,
    status: AppStatus,
) -> LedgerOp:
    """Find-or-create row by (company, normalized_role).
    - On update: increments attempt_count, sets last_attempt_at = today, updates status.
    - On create: attempt_count=1, last_attempt_at = date.
    """
    norm_role = normalize_title(role)
    norm_company = company.strip()

    rows: list[dict[str, str]] = []
    fieldnames = [
        "url", "company", "normalized_title", "location",
        "date_first_seen", "score", "grade", "status",
        "last_attempt_at", "attempt_count",
    ]

    if ledger_path.exists():
        with open(ledger_path) as f:
            reader = csv.DictReader(f, delimiter="\t")
            rows = list(reader)
            if reader.fieldnames:
                fieldnames = list(reader.fieldnames)

    # Update existing
    for r in rows:
        if (
            r.get("company", "").strip().lower() == norm_company.lower()
            and r.get("normalized_title", "").strip().lower() == norm_role
        ):
            r["status"] = status.value
            r["last_attempt_at"] = date
            try:
                r["attempt_count"] = str(int(r.get("attempt_count", "0") or "0") + 1)
            except ValueError:
                r["attempt_count"] = "1"
            _write_ledger(ledger_path, fieldnames, rows)
            return LedgerOp.UPDATED

    # Create new
    rows.append({
        "url": url, "company": norm_company, "normalized_title": norm_role,
        "location": location, "date_first_seen": date,
        "score": score, "grade": grade,
        "status": status.value,
        "last_attempt_at": date, "attempt_count": "1",
    })
    _write_ledger(ledger_path, fieldnames, rows)
    return LedgerOp.CREATED


def ledger_eligible(
    ledger_path: Path, *, company: str, role: str,
    now: Optional[datetime] = None,
) -> bool:
    """True if the card is eligible for a submit attempt.

    Rules (see spec "State Authority + Uncertainty Model"):
    - No row → eligible
    - status=applied → not eligible (always blocks)
    - status=failed → eligible (user re-tick path)
    - status=skipped → eligible
    - status=unverified, last_attempt_at within 24h → not eligible (cooling down)
    - status=unverified, last_attempt_at older than 24h → eligible (auto-retry)
    """
    if not ledger_path.exists():
        return True

    if now is None:
        now = datetime.now()

    norm_role = normalize_title(role)
    norm_company = company.strip().lower()

    with open(ledger_path) as f:
        reader = csv.DictReader(f, delimiter="\t")
        for r in reader:
            if (
                r.get("company", "").strip().lower() == norm_company
                and r.get("normalized_title", "").strip().lower() == norm_role
            ):
                status = (r.get("status") or "").strip().lower()
                if status == "applied":
                    return False
                if status in ("failed", "skipped"):
                    return True
                if status == "unverified":
                    last = (r.get("last_attempt_at") or "").strip()
                    if not last:
                        return True
                    try:
                        last_dt = datetime.fromisoformat(last)
                    except ValueError:
                        return True
                    return (now - last_dt) >= UNVERIFIED_COOLDOWN
                # Unknown status (seen, pitched, etc.) → eligible
                return True
    return True


def record_attempt(
    *,
    tracker_path: Path, ledger_path: Path,
    url: str, company: str, role: str, source: str,
    location: str, date: str, score: str, grade: str,
    status: AppStatus, notes: str,
) -> None:
    """Atomicity wrapper: tracker append + ledger upsert succeed or both fail.

    On ledger failure, the tracker row is removed via remove_last_row(). The
    'expected' guard makes the rollback defensive against unexpected concurrent
    writes (single-user CLI, shouldn't happen, but cheap insurance)."""
    append_tracker_row(
        tracker_path,
        company=company, role=role, source=source,
        date=date, status=status, notes=notes,
    )
    try:
        upsert_ledger_row(
            ledger_path, url=url, company=company, role=role,
            location=location, date=date, score=score, grade=grade,
            status=status,
        )
    except Exception:
        remove_last_row(
            tracker_path, expected_company=company, expected_date=date,
        )
        raise


def _write_ledger(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        for r in rows:
            writer.writerow(r)
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd ~/code/the-dossier-apply-flow-v2 && pipeline/.venv/bin/python3 -m pytest pipeline/tests/test_tracker.py -v
```
Expected: all 19 tests pass.

- [ ] **Step 6: Run full suite to confirm no regression**

```bash
cd ~/code/the-dossier-apply-flow-v2 && pipeline/.venv/bin/python3 -m pytest pipeline/ -q -m "not slow"
```
Expected: 68+ passed.

- [ ] **Step 7: Commit**

```bash
git add pipeline/tracker.py pipeline/tests/test_tracker.py pipeline/tests/fixtures/tracker_sample.md pipeline/tests/fixtures/ledger_sample.tsv
git commit -m "$(cat <<'EOF'
feat(tracker): status-aware tracker + ledger upsert + atomicity

Tracker is append-only with AppStatus enum (Applied | Unverified | Failed
| Skipped). Ledger is upsert keyed on (company, normalized_role) with
attempt_count + last_attempt_at columns.

ledger_eligible() encodes the authority rules: applied blocks always;
unverified within 24h cools down; failed/unverified-old eligible for
retry. record_attempt() wraps tracker append + ledger upsert with
remove_last_row() rollback so partial failure leaves states consistent.

normalize_title and ledger_eligible are pure; the rest take path args
so tests can use tmp_path fixtures.
EOF
)"
```

---

### Task 3: Implement `pipeline/tracker_cli.py` — `python -m` wrapper for the /apply skill

**Files:**
- Create: `pipeline/tracker_cli.py`
- Create: `pipeline/tests/test_tracker_cli.py`

**Context:** The `/apply` skill is markdown invoked by Claude. It can't import Python directly, but it can run subprocesses. `tracker_cli.py` is a thin CLI on top of `tracker.py` so the skill can call `python -m pipeline.tracker_cli --company X --role Y ...`.

- [ ] **Step 1: Write failing tests in `pipeline/tests/test_tracker_cli.py`**

```python
"""Tests for pipeline.tracker_cli — CLI wrapper around tracker.py."""
import csv
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
WORKTREE_ROOT = Path(__file__).resolve().parent.parent.parent


def _run_cli(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "pipeline.tracker_cli"] + args,
        cwd=WORKTREE_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_tracker_cli_default_status_applied(tmp_path):
    tracker = tmp_path / "Tracker.md"
    shutil.copy(FIXTURES / "tracker_sample.md", tracker)
    ledger = tmp_path / "ledger.tsv"
    shutil.copy(FIXTURES / "ledger_sample.tsv", ledger)

    result = _run_cli([
        "--company", "Orkes",
        "--role", "Product Manager",
        "--source", "Pipeline",
        "--date", "2026-05-02",
        "--notes", "Pipeline logged",
        "--tracker-path", str(tracker),
        "--ledger-path", str(ledger),
    ])
    assert result.returncode == 0, result.stderr
    assert "Tracker:" in result.stdout
    assert "Ledger:" in result.stdout

    text = tracker.read_text()
    assert "| Orkes | Product Manager | Pipeline | 2026-05-02 | Applied | Pipeline logged |" in text


def test_tracker_cli_status_unverified_writes_unverified(tmp_path):
    tracker = tmp_path / "Tracker.md"
    shutil.copy(FIXTURES / "tracker_sample.md", tracker)
    ledger = tmp_path / "ledger.tsv"
    shutil.copy(FIXTURES / "ledger_sample.tsv", ledger)

    result = _run_cli([
        "--company", "Orkes", "--role", "PM",
        "--source", "Pipeline", "--date", "2026-05-02",
        "--status", "unverified",
        "--tracker-path", str(tracker), "--ledger-path", str(ledger),
    ])
    assert result.returncode == 0
    assert "| Orkes | PM | Pipeline | 2026-05-02 | Unverified |" in tracker.read_text()


def test_tracker_cli_warns_on_duplicate_applied(tmp_path):
    """If ledger says (company, role) already applied, warn but still log."""
    tracker = tmp_path / "Tracker.md"
    shutil.copy(FIXTURES / "tracker_sample.md", tracker)
    ledger = tmp_path / "ledger.tsv"
    shutil.copy(FIXTURES / "ledger_sample.tsv", ledger)

    result = _run_cli([
        "--company", "Updater",
        "--role", "Technical Product Lead",
        "--source", "Pipeline", "--date", "2026-05-02",
        "--tracker-path", str(tracker), "--ledger-path", str(ledger),
    ])
    assert "duplicate" in result.stdout.lower() or "already applied" in result.stdout.lower()
    assert result.returncode == 0


def test_tracker_cli_no_ledger_flag(tmp_path):
    tracker = tmp_path / "Tracker.md"
    shutil.copy(FIXTURES / "tracker_sample.md", tracker)

    result = _run_cli([
        "--company", "Orkes", "--role", "PM",
        "--source", "Pipeline", "--date", "2026-05-02",
        "--tracker-path", str(tracker),
        "--no-ledger",
    ])
    assert result.returncode == 0
    assert "Tracker:" in result.stdout
    assert "Ledger:" not in result.stdout


def test_tracker_cli_invalid_status_rejected(tmp_path):
    result = _run_cli([
        "--company", "X", "--role", "Y",
        "--source", "Pipeline", "--date", "2026-05-02",
        "--status", "bogus",
    ])
    assert result.returncode != 0
    assert "invalid" in result.stderr.lower() or "choice" in result.stderr.lower()
```

- [ ] **Step 2: Run to verify failure**

```bash
cd ~/code/the-dossier-apply-flow-v2 && pipeline/.venv/bin/python3 -m pytest pipeline/tests/test_tracker_cli.py -v
```
Expected: FAIL with `No module named pipeline.tracker_cli`.

- [ ] **Step 3: Implement `pipeline/tracker_cli.py`**

```python
"""CLI wrapper around pipeline.tracker for use from the /apply skill markdown.

The skill cannot import Python directly, so it shells out to:
    python -m pipeline.tracker_cli --company X --role Y --source Pipeline --date YYYY-MM-DD --status applied ...

Default paths point at the user's vault and pipeline ledger; tests override via
--tracker-path and --ledger-path.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pipeline.tracker import (
    AppStatus,
    ledger_eligible,
    record_attempt,
    append_tracker_row,
)


DEFAULT_TRACKER = Path.home() / "Documents" / "Second Brain" / "02_Projects" / "Job Search" / "R - Application Tracker.md"
DEFAULT_LEDGER = Path(__file__).resolve().parent / "data" / "ledger.tsv"

_STATUS_CHOICES = ["applied", "unverified", "failed", "skipped"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--company", required=True)
    parser.add_argument("--role", required=True)
    parser.add_argument("--source", default="Pipeline")
    parser.add_argument("--date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--url", default="")
    parser.add_argument("--location", default="")
    parser.add_argument("--score", default="")
    parser.add_argument("--grade", default="")
    parser.add_argument("--notes", default="")
    parser.add_argument("--status", choices=_STATUS_CHOICES, default="applied",
                        help="Application outcome status (default: applied).")
    parser.add_argument("--tracker-path", default=str(DEFAULT_TRACKER))
    parser.add_argument("--ledger-path", default=str(DEFAULT_LEDGER))
    parser.add_argument("--no-ledger", action="store_true",
                        help="Skip ledger update; only writes tracker row.")
    args = parser.parse_args(argv)

    tracker_path = Path(args.tracker_path)
    ledger_path = Path(args.ledger_path)
    status = AppStatus(args.status)

    # Dedup warn (consult ledger, but do NOT block — caller asked to log)
    if not args.no_ledger and not ledger_eligible(
        ledger_path, company=args.company, role=args.role,
    ):
        print(f"[tracker-cli] WARNING: ledger says {args.company} - {args.role} is not eligible (duplicate or cooling down). Logging anyway.")

    notes = args.notes or ("Pipeline logged" if args.source == "Pipeline" else "")

    if args.no_ledger:
        # Tracker only, no ledger upsert
        result = append_tracker_row(
            tracker_path,
            company=args.company, role=args.role, source=args.source,
            date=args.date, status=status, notes=notes,
        )
        print(f"Tracker: {result.value} {tracker_path}")
    else:
        # Tracker + ledger via atomicity wrapper
        record_attempt(
            tracker_path=tracker_path, ledger_path=ledger_path,
            url=args.url, company=args.company, role=args.role,
            source=args.source, location=args.location,
            date=args.date, score=args.score, grade=args.grade,
            status=status, notes=notes,
        )
        print(f"Tracker: appended to {tracker_path}")
        print(f"Ledger: updated {ledger_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd ~/code/the-dossier-apply-flow-v2 && pipeline/.venv/bin/python3 -m pytest pipeline/tests/test_tracker_cli.py -v
```
Expected: 5 passed.

- [ ] **Step 5: Run full suite**

```bash
cd ~/code/the-dossier-apply-flow-v2 && pipeline/.venv/bin/python3 -m pytest pipeline/ -q -m "not slow"
```
Expected: 73+ passed.

- [ ] **Step 6: Commit**

```bash
git add pipeline/tracker_cli.py pipeline/tests/test_tracker_cli.py
git commit -m "$(cat <<'EOF'
feat(tracker): add status-aware tracker_cli for /apply skill subprocess

`python -m pipeline.tracker_cli --status applied` (default) logs through
the new record_attempt atomicity wrapper. Status enum surfaces as a
--status choice argument.

Used by /apply skill (default applied) and by Plan 2's execute.py per
submit (via the underlying tracker.py functions, not the CLI).
EOF
)"
```

---

## Phase B — /apply skill rewrite

### Task 4: Rewrite `/apply` skill markdown to delegate to tracker_cli

**Files:**
- Modify: `.claude/skills/apply/SKILL.md` (replace Step 6 + Step 7 of the skill)

**Context:** Steps 6 (Log to Application Tracker) and Step 7 (Update Dedup Ledger) of the /apply skill currently use Claude Edit-tool steps to manipulate the tracker markdown table and the TSV ledger. Replace those steps with a single subprocess invocation to `tracker_cli`.

- [ ] **Step 1: Read current /apply skill steps 6-7**

```bash
sed -n '143,189p' ~/code/the-dossier-apply-flow-v2/.claude/skills/apply/SKILL.md
```
Expected output: the existing Step 6 + Step 7 markdown blocks (lines 143-189).

- [ ] **Step 2: Replace Step 6 + Step 7 with a single tracker_cli step**

Open `.claude/skills/apply/SKILL.md` and replace the Step 6 block (line 143 `### Step 6: Log to Application Tracker`) through the end of the Step 7 block (the `Confirm: "Ledger updated."` line) with this single new section:

```markdown
### Step 6: Log to Application Tracker + Ledger

Run the tracker CLI as a subprocess. Status defaults to `applied` for /apply
invocations (user explicitly clicked submit and is logging it):

```bash
cd ~/code/the-dossier-apply-flow-v2 && pipeline/.venv/bin/python3 -m pipeline.tracker_cli \
  --company "[Company]" \
  --role "[Role Title]" \
  --source "[source]" \
  --date "$(date +%Y-%m-%d)" \
  --url "[url-if-any]" \
  --location "[location-if-known]" \
  --score "[score-if-from-pipeline]" \
  --grade "[grade-if-from-pipeline]" \
  --notes "[notes]" \
  --status applied
```

Pass `--no-ledger` if `--no-ledger` was passed to /apply.

The CLI:
- Consults the ledger via `ledger_eligible`; warns if not eligible (already
  applied OR within unverified cooldown) but does NOT block — caller asked to log.
- Writes via `record_attempt` atomicity wrapper: appends Tracker row + upserts
  ledger row in a try/except that rolls back on partial failure.
- Tracker write creates the file if missing; ledger write creates the file if
  missing.

Print whatever the CLI emits. The CLI handles all the markdown table format
and TSV column ordering — do NOT do any manipulation in skill steps.

Advanced: pass `--status unverified|failed|skipped` for retroactive logging
of non-Applied outcomes (rare; mostly for execute.py callers).
```

(Then renumber the existing Step 8 to Step 7.)

- [ ] **Step 3: Verify the file is well-formed markdown**

```bash
cd ~/code/the-dossier-apply-flow-v2 && head -200 .claude/skills/apply/SKILL.md | grep -E "^### Step "
```
Expected: Step 1 through Step 7 (one less than before, since we collapsed 6+7).

- [ ] **Step 4: Manual smoke test (no tests needed for skill markdown)**

Inspect by eye:
```bash
cd ~/code/the-dossier-apply-flow-v2 && cat .claude/skills/apply/SKILL.md
```
Expected: skill reads cleanly, single subprocess invocation in place of two Edit-tool blocks.

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/apply/SKILL.md
git commit -m "$(cat <<'EOF'
refactor(apply-skill): delegate tracker writes to tracker_cli subprocess

Replaces the Edit-tool-based tracker markdown manipulation and TSV ledger
manipulation with a single `python -m pipeline.tracker_cli` invocation.
Same user-facing behavior; eliminates a class of formatting bugs (column
count mismatches, wikilink-in-table issues).
EOF
)"
```

---

## Phase C — CL flag scanner

### Task 5: Implement `pipeline/cl_flag_scan.py` — pre-flight regex scanner

**Files:**
- Create: `pipeline/cl_flag_scan.py`
- Create: `pipeline/tests/test_cl_flag_scan.py`
- Create: `pipeline/tests/fixtures/cl_with_placeholder.md`
- Create: `pipeline/tests/fixtures/cl_clean.md`

**Context:** The 2026-05-01 CL quality test surfaced an Orkes CL with `[X billion events/day]` literal in the body and a "fill in before sending" meta-comment. The CL system prompt now forbids these (commit c8664ba), but execute mode's pre-flight should still scan as a safety net. Warn-only — user decides proceed/skip/quit.

- [ ] **Step 1: Create test fixtures**

`pipeline/tests/fixtures/cl_clean.md`:

```
Hello AcmeCo Hiring Team,

I have spent fifteen years shipping B2B platforms and want to bring that
experience to your team. The product story I find most compelling is the
data-pipeline angle. Looking forward to talking.

Sincerely,
Jared
```

`pipeline/tests/fixtures/cl_with_placeholder.md`:

```
Hello Orkes Hiring Team,

Conductor handles [X billion events/day] in production environments — exactly
the scale where I spent my last role. Things to fill in before sending:
the specific orchestrator name and a war story that fits.

Sincerely,
Jared
```

- [ ] **Step 2: Write failing tests**

`pipeline/tests/test_cl_flag_scan.py`:

```python
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
```

- [ ] **Step 3: Run to verify failure**

```bash
cd ~/code/the-dossier-apply-flow-v2 && pipeline/.venv/bin/python3 -m pytest pipeline/tests/test_cl_flag_scan.py -v
```
Expected: FAIL — `No module named pipeline.cl_flag_scan`.

- [ ] **Step 4: Implement `pipeline/cl_flag_scan.py`**

```python
"""CL pre-flight scanner: regex-detect placeholder/draft markers that should
not appear in a final cover letter.

Used by execute.py before each card. Warn-only — user decides proceed/skip/quit.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class FlagMatch:
    pattern_name: str
    matched_text: str
    context: str  # ~80 chars surrounding the match
    position: int


# Patterns. Word-boundary on [X to avoid matching legit product names like [X-Series].
_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("X_PLACEHOLDER", re.compile(r"\[X[\s\]]", re.IGNORECASE)),
    ("INSERT_PLACEHOLDER", re.compile(r"\[INSERT\b", re.IGNORECASE)),
    ("FILL_IN", re.compile(r"\bfill in\b", re.IGNORECASE)),
    ("BEFORE_SENDING", re.compile(r"\bbefore\s+sending\b", re.IGNORECASE)),
]


def scan_cl_text(text: str, context_chars: int = 80) -> list[FlagMatch]:
    """Scan CL prose for placeholder/draft markers.

    Returns empty list if clean. Each match includes ~context_chars of surrounding
    text so the user can see what triggered it.
    """
    matches: list[FlagMatch] = []
    for name, regex in _PATTERNS:
        for m in regex.finditer(text):
            start = max(0, m.start() - context_chars // 2)
            end = min(len(text), m.end() + context_chars // 2)
            context = text[start:end].replace("\n", " ").strip()
            matches.append(FlagMatch(
                pattern_name=name,
                matched_text=m.group(0),
                context=context,
                position=m.start(),
            ))
    matches.sort(key=lambda f: f.position)
    return matches
```

- [ ] **Step 5: Run tests to verify pass**

```bash
cd ~/code/the-dossier-apply-flow-v2 && pipeline/.venv/bin/python3 -m pytest pipeline/tests/test_cl_flag_scan.py -v
```
Expected: 6 passed.

- [ ] **Step 6: Empirical validation against real CLs**

Sanity-check the scanner against the 5 real CLs in the worktree (none should flag, post-fix):

```bash
cd ~/code/the-dossier-apply-flow-v2 && for f in pipeline/data/cover_letters/output/*.md; do
  echo "=== $(basename $f) ==="
  pipeline/.venv/bin/python3 -c "
from pathlib import Path
from pipeline.cl_flag_scan import scan_cl_text
matches = scan_cl_text(Path('$f').read_text())
print(f'  flags: {len(matches)}')
for m in matches:
    print(f'    {m.pattern_name}: {m.matched_text!r} in {m.context!r}')
" 2>/dev/null || echo "  (file not found — skipping)"
done
```

(The CLs from 2026-05-01/02 may not all have `.md` siblings yet — Task 1 was the change that started persisting them. If the loop says "skipping" for some, that's fine; the test fixtures already cover the patterns.)

Expected: zero flags on the post-fix CLs. If any real CL flags, investigate before proceeding (false positive = pattern needs tightening).

- [ ] **Step 7: Run full suite**

```bash
cd ~/code/the-dossier-apply-flow-v2 && pipeline/.venv/bin/python3 -m pytest pipeline/ -q -m "not slow"
```
Expected: 79+ passed.

- [ ] **Step 8: Commit**

```bash
git add pipeline/cl_flag_scan.py pipeline/tests/test_cl_flag_scan.py pipeline/tests/fixtures/cl_clean.md pipeline/tests/fixtures/cl_with_placeholder.md
git commit -m "$(cat <<'EOF'
feat(cl-flag-scan): regex pre-flight for placeholder/draft leakage

Safety net before execute submits a card. The CL system prompt was
hardened on 2026-05-01 to forbid [X], [INSERT], "fill in", and meta-
comments, but a regex scanner closes the loop in case a future prompt
regression slips one through. Warn-only — user decides proceed/skip/quit.
EOF
)"
```

---

## Phase D — triage_writer

### Task 6: Implement `pipeline/triage_writer.py` pure functions (data shaping)

**Files:**
- Create: `pipeline/triage_writer.py` (pure functions only at this stage)
- Create: `pipeline/tests/test_triage_writer.py`
- Create: `pipeline/tests/fixtures/manifest_sample.json`
- Create: `pipeline/tests/fixtures/scored_with_artifacts.json`

**Context:** Pure-function-first. Module reads manifest (artifact contract from Plan 1) + scored JSON (editorial content) and emits a markdown string. Zero file I/O in this task — just data shaping. Task 7 adds the file-reading and idempotency-guard wrappers.

- [ ] **Step 1: Create fixtures**

`pipeline/tests/fixtures/manifest_sample.json` (3 cards, mirrors real Plan 1 output):

```json
{
  "date": "2026-05-02",
  "scored_file": "pipeline/data/scored/2026-05-02.json",
  "generated_at": "2026-05-02T09:00:00",
  "counts": {"generated": 2, "cached": 1, "failures": 0},
  "generated": [
    {
      "company": "AcmeCo",
      "role": "Senior PM",
      "url": "https://job-boards.greenhouse.io/acmeco/jobs/123",
      "grade": "A",
      "archetype": "product_management",
      "resume_pdf": "/abs/Jared-Hawkins-AcmeCo-Senior-PM-2026-05-02.pdf",
      "cl_pdf": "/abs/Jared-Hawkins-AcmeCo-Senior-PM-2026-05-02.pdf",
      "jd_cache": "/abs/AcmeCo-Senior-PM-2026-05-02.txt"
    },
    {
      "company": "BetaInc",
      "role": "Product Manager",
      "url": "https://jobs.lever.co/betainc/abc",
      "grade": "B",
      "archetype": "product_management",
      "resume_pdf": "/abs/Jared-Hawkins-BetaInc-Product-Manager-2026-05-02.pdf",
      "cl_pdf": "/abs/Jared-Hawkins-BetaInc-Product-Manager-2026-05-02.pdf",
      "jd_cache": "/abs/BetaInc-Product-Manager-2026-05-02.txt"
    }
  ],
  "cached": [
    {
      "company": "Charlie Corp",
      "role": "PM",
      "url": "https://www.adzuna.com/details/4567",
      "grade": "B",
      "archetype": "operations",
      "resume_pdf": "/abs/Jared-Hawkins-Charlie-Corp-PM-2026-05-02.pdf",
      "cl_pdf": "/abs/Jared-Hawkins-Charlie-Corp-PM-2026-05-02.pdf",
      "jd_cache": "/abs/Charlie-Corp-PM-2026-05-02.txt"
    }
  ],
  "failures": []
}
```

`pipeline/tests/fixtures/scored_with_artifacts.json` (4 cards: 3 in manifest + 1 unprocessed):

```json
[
  {
    "title": "Senior PM",
    "company": "AcmeCo",
    "url": "https://job-boards.greenhouse.io/acmeco/jobs/123",
    "resolved_url": "https://job-boards.greenhouse.io/acmeco/jobs/123",
    "salary": "$200,000-$240,000",
    "grade": "A",
    "archetype": "product_management",
    "lane": "A",
    "rationale": "Direct PM fit; strong AI tailwind.",
    "red_flags": [],
    "status": "new"
  },
  {
    "title": "Product Manager",
    "company": "BetaInc",
    "url": "https://jobs.lever.co/betainc/abc",
    "resolved_url": "https://jobs.lever.co/betainc/abc",
    "salary": "$160,000-$190,000",
    "grade": "B",
    "archetype": "product_management",
    "lane": "A",
    "rationale": "Solid B-grade dev tools PM.",
    "red_flags": ["small team"],
    "status": "new"
  },
  {
    "title": "PM",
    "company": "Charlie Corp",
    "url": "https://www.adzuna.com/details/4567",
    "salary": "",
    "grade": "B",
    "archetype": "operations",
    "lane": "B",
    "rationale": "Generic ops-style PM; B grade.",
    "red_flags": [],
    "status": "new"
  },
  {
    "title": "PM Specialist",
    "company": "DeltaCo",
    "url": "https://www.adzuna.com/details/9999",
    "salary": "$120,000-$140,000",
    "grade": "B",
    "archetype": "operations",
    "lane": "B",
    "rationale": "B grade, no resolved URL.",
    "red_flags": [],
    "status": "new"
  }
]
```

(Note: DeltaCo is in the scored JSON but NOT in the manifest — Plan 1 likely filtered it for some reason. triage_writer should ONLY render cards from the manifest, period. The "unresolved URL" case for triage_writer purposes is a card in the manifest whose `url` is an Adzuna redirector — Charlie Corp here.)

- [ ] **Step 2: Write failing tests**

`pipeline/tests/test_triage_writer.py`:

```python
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
```

- [ ] **Step 3: Run to verify failure**

```bash
cd ~/code/the-dossier-apply-flow-v2 && pipeline/.venv/bin/python3 -m pytest pipeline/tests/test_triage_writer.py -v
```
Expected: FAIL — `No module named pipeline.triage_writer`.

- [ ] **Step 4: Implement `pipeline/triage_writer.py` — pure functions only**

```python
"""Triage writer: manifest + scored JSON → daily triage markdown for the vault.

This module exposes pure functions only (no file I/O). The CLI wrapper that
reads files from disk and writes the output is added in Task 7.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable


# Hosts that indicate an unresolved aggregator redirect (Strategy C).
_UNRESOLVED_HOSTS = (
    "adzuna.com",
    "indeed.com",
    "linkedin.com/jobs",
    "glassdoor.com",
    "ziprecruiter.com",
)


def is_unresolved_url(url: str) -> bool:
    """True if URL points at an aggregator/redirector rather than a direct ATS link."""
    if not url:
        return True
    return any(host in url.lower() for host in _UNRESOLVED_HOSTS)


def truncate_preview(text: str, max_chars: int = 200) -> str:
    """Truncate to max_chars with ellipsis suffix; pass through if short enough.

    Newlines collapsed to spaces for single-line render in the triage markdown.
    """
    cleaned = " ".join(text.split())
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[:max_chars] + "..."


def _read_cl_preview(cl_pdf_path: str, max_chars: int = 200) -> str:
    """Look up the .md sibling of the CL PDF and return its first max_chars truncated.

    Returns empty string if the .md doesn't exist (e.g., manually-generated CL).
    """
    md_path = Path(cl_pdf_path).with_suffix(".md")
    if not md_path.exists():
        return ""
    return truncate_preview(md_path.read_text(), max_chars=max_chars)


def extract_card_data(manifest: dict, scored: list[dict]) -> list[dict]:
    """Merge manifest entries (artifact paths) with scored JSON entries (editorial content).

    Returns one dict per card with both sets of fields, keyed by URL match.
    Cards in manifest but not scored get empty editorial fields (instead of being dropped).
    """
    scored_by_url = {c.get("resolved_url") or c.get("url"): c for c in scored}

    out = []
    for entry in list(manifest.get("generated", [])) + list(manifest.get("cached", [])):
        url = entry["url"]
        scored_card = scored_by_url.get(url, {})
        out.append({
            "grade": entry["grade"],
            "company": entry["company"],
            "role": entry["role"],
            "url": url,
            "archetype": entry.get("archetype", ""),
            "resume_pdf": entry["resume_pdf"],
            "cl_pdf": entry["cl_pdf"],
            "salary": scored_card.get("salary", ""),
            "fit": scored_card.get("rationale", ""),
            "risks": scored_card.get("red_flags", []),
            "lane": scored_card.get("lane", ""),
            "cl_preview": _read_cl_preview(entry["cl_pdf"]),
            "unresolved": is_unresolved_url(url),
        })
    return out


def format_card_section(card: dict) -> str:
    """Format a single card as a markdown section (Option A shape)."""
    grade = card["grade"]
    title_line = f"## [{grade}] {card['company']} — {card['role']}\n"

    if card["unresolved"]:
        return (
            title_line
            + f"- URL unresolved (Adzuna redirect only) — run `/pipeline resolve-urls` first\n"
            + f"- ~~[ ] apply~~ ~~[ ] skip~~\n"
        )

    salary = card["salary"] or "not listed"
    archetype = card["archetype"] or "—"
    lane = card["lane"] or "—"
    fit = card["fit"] or "(no rationale on file)"
    risks_list = card.get("risks") or []
    risks = "; ".join(risks_list) if risks_list else "(none flagged)"
    cl_preview = card.get("cl_preview") or ""
    cl_preview_line = (
        f"- CL preview: \"{cl_preview}\"\n" if cl_preview
        else f"- CL preview: (no preview available)\n"
    )

    return (
        title_line
        + f"- Salary: {salary} | Archetype: {archetype} | Lane: {lane}\n"
        + f"- Fit: {fit}\n"
        + f"- Risks: {risks}\n"
        + f"- JD: {card['url']}\n"
        + f"- Resume: {card['resume_pdf']}\n"
        + f"- CL: {card['cl_pdf']}\n"
        + cl_preview_line
        + f"- [ ] apply\n"
        + f"- [ ] skip\n"
    )


def format_triage_markdown(
    cards: list[dict], date_str: str, manifest_path: str,
) -> str:
    """Assemble the full triage markdown: header + counts banner + sorted card sections."""
    sorted_cards = sorted(
        cards, key=lambda c: (c["grade"], c["company"].lower())
    )
    n_total = len(sorted_cards)
    n_unresolved = sum(1 for c in sorted_cards if c["unresolved"])

    header = (
        f"---\n"
        f"created: {date_str}\n"
        f"tags: [job-search, triage]\n"
        f"---\n\n"
        f"# Daily Triage {date_str}\n\n"
        f"{n_total} A/B cards · {n_unresolved} unresolved · manifest: {manifest_path}\n\n"
    )
    if n_total > 0:
        header += "Tick `[x] apply` on cards to apply to. Run `/pipeline execute` after.\n\n---\n\n"
    else:
        header += "(no cards in manifest)\n"

    sections = "\n".join(format_card_section(c) for c in sorted_cards)
    return header + sections
```

- [ ] **Step 5: Run tests to verify pass**

```bash
cd ~/code/the-dossier-apply-flow-v2 && pipeline/.venv/bin/python3 -m pytest pipeline/tests/test_triage_writer.py -v
```
Expected: 13 passed.

- [ ] **Step 6: Run full suite**

```bash
cd ~/code/the-dossier-apply-flow-v2 && pipeline/.venv/bin/python3 -m pytest pipeline/ -q -m "not slow"
```
Expected: 92+ passed.

- [ ] **Step 7: Commit**

```bash
git add pipeline/triage_writer.py pipeline/tests/test_triage_writer.py pipeline/tests/fixtures/manifest_sample.json pipeline/tests/fixtures/scored_with_artifacts.json
git commit -m "$(cat <<'EOF'
feat(triage-writer): pure functions for daily triage markdown

extract_card_data merges manifest (artifact paths) and scored JSON
(editorial content) by URL. format_card_section emits one Option A
section. format_triage_markdown assembles the header banner + sorted
sections. is_unresolved_url + truncate_preview are exposed for reuse.

File I/O wrapper + idempotency guard come in Task 7.
EOF
)"
```

---

### Task 7: Add `triage_writer.py` CLI wrapper + idempotency guard

**Files:**
- Modify: `pipeline/triage_writer.py` (add CLI + file-reading wrapper)
- Modify: `pipeline/tests/test_triage_writer.py` (append idempotency tests)

**Context:** Task 6 covered pure functions. Now add the file-I/O wrapper, the idempotency guard ("refuse to overwrite if `[x] apply` or `[x] applied` marks exist"), and the `if __name__ == "__main__"` CLI.

- [ ] **Step 1: Append failing idempotency tests to `test_triage_writer.py`**

Add to the end of the file:

```python
import shutil

from pipeline.triage_writer import (
    write_triage_note,
    has_triage_marks,
)


def test_has_triage_marks_detects_x_apply(tmp_path):
    p = tmp_path / "Daily Triage 2026-05-02.md"
    p.write_text("## [A] X — Y\n- [x] apply\n- [ ] skip\n")
    assert has_triage_marks(p) is True


def test_has_triage_marks_detects_x_applied(tmp_path):
    p = tmp_path / "Daily Triage 2026-05-02.md"
    p.write_text("## [A] X — Y\n- [x] applied\n- [ ] skip\n")
    assert has_triage_marks(p) is True


def test_has_triage_marks_returns_false_for_unchecked(tmp_path):
    p = tmp_path / "Daily Triage 2026-05-02.md"
    p.write_text("## [A] X — Y\n- [ ] apply\n- [ ] skip\n")
    assert has_triage_marks(p) is False


def test_has_triage_marks_returns_false_for_missing_file(tmp_path):
    p = tmp_path / "nope.md"
    assert has_triage_marks(p) is False


def test_write_triage_note_creates_file(tmp_path, manifest, scored):
    out = tmp_path / "vault" / "99_System" / "Job Search" / "Daily Triage 2026-05-02.md"
    write_triage_note(manifest, scored, out, manifest_path="manifest.json", force=False)
    assert out.exists()
    text = out.read_text()
    assert "Daily Triage 2026-05-02" in text
    assert "AcmeCo" in text


def test_write_triage_note_refuses_to_overwrite_with_marks(tmp_path, manifest, scored):
    out = tmp_path / "Daily Triage 2026-05-02.md"
    out.write_text("## [A] Existing — PM\n- [x] apply\n- [ ] skip\n")
    with pytest.raises(RuntimeError, match="Triage in progress"):
        write_triage_note(manifest, scored, out, manifest_path="manifest.json", force=False)


def test_write_triage_note_force_overwrites(tmp_path, manifest, scored):
    out = tmp_path / "Daily Triage 2026-05-02.md"
    out.write_text("## [A] Existing — PM\n- [x] apply\n- [ ] skip\n")
    write_triage_note(manifest, scored, out, manifest_path="manifest.json", force=True)
    text = out.read_text()
    assert "AcmeCo" in text
    assert "Existing" not in text


def test_write_triage_note_creates_parent_dirs(tmp_path, manifest, scored):
    out = tmp_path / "vault" / "99_System" / "Job Search" / "Daily Triage.md"
    assert not out.parent.exists()
    write_triage_note(manifest, scored, out, manifest_path="m.json", force=False)
    assert out.parent.exists()
    assert out.exists()
```

- [ ] **Step 2: Run to verify failure**

```bash
cd ~/code/the-dossier-apply-flow-v2 && pipeline/.venv/bin/python3 -m pytest pipeline/tests/test_triage_writer.py -v -k "has_triage_marks or write_triage_note"
```
Expected: FAIL on the new tests — `cannot import name 'write_triage_note'`.

- [ ] **Step 3: Add the CLI wrapper functions to `pipeline/triage_writer.py`**

Append at the end of the file (before `if __name__ == "__main__"` block, which we'll add after):

```python
import argparse
import json
import re
import sys
from datetime import date


_TRIAGE_MARK_RE = re.compile(r"\[x\]\s+(apply|applied)", re.IGNORECASE)


def has_triage_marks(path: Path) -> bool:
    """True if the file exists and contains any [x] apply or [x] applied marks."""
    if not path.exists():
        return False
    text = path.read_text()
    return bool(_TRIAGE_MARK_RE.search(text))


def write_triage_note(
    manifest: dict,
    scored: list[dict],
    output_path: Path,
    *,
    manifest_path: str,
    force: bool,
) -> None:
    """End-to-end: cards → markdown → file. Honors idempotency guard.

    Raises RuntimeError if output_path has triage marks and force is False.
    """
    if has_triage_marks(output_path) and not force:
        raise RuntimeError(
            f"Triage in progress at {output_path} — pass --force to overwrite."
        )
    cards = extract_card_data(manifest, scored)
    md = format_triage_markdown(
        cards,
        date_str=manifest.get("date") or date.today().isoformat(),
        manifest_path=manifest_path,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(md)


def _default_manifest_path() -> Path | None:
    """Most recent manifest in pipeline/data/pregenerated/."""
    pipeline_dir = Path(__file__).resolve().parent
    manifest_dir = pipeline_dir / "data" / "pregenerated"
    if not manifest_dir.exists():
        return None
    candidates = sorted(manifest_dir.glob("[0-9]*-manifest.json"))
    return candidates[-1] if candidates else None


def _default_output_path(date_str: str) -> Path:
    return (
        Path.home() / "Documents" / "Second Brain" / "99_System"
        / "Job Search" / f"Daily Triage {date_str}.md"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default=None,
                        help="Path to manifest JSON. Defaults to most recent.")
    parser.add_argument("--scored-file", default=None,
                        help="Path to scored JSON. Defaults to manifest's scored_file field.")
    parser.add_argument("--output", default=None,
                        help="Output markdown path. Defaults to vault path keyed by manifest date.")
    parser.add_argument("--force", action="store_true",
                        help="Overwrite even if triage marks present.")
    args = parser.parse_args(argv)

    manifest_path = Path(args.manifest) if args.manifest else _default_manifest_path()
    if not manifest_path or not manifest_path.exists():
        print("[triage-writer] no manifest found — run /pipeline pregenerate first.",
              file=sys.stderr)
        return 2

    manifest = json.loads(manifest_path.read_text())

    scored_path = Path(args.scored_file) if args.scored_file else Path(manifest["scored_file"])
    # Resolve relative path against the worktree root (parent of pipeline dir).
    if not scored_path.is_absolute():
        scored_path = Path(__file__).resolve().parent.parent / scored_path
    if not scored_path.exists():
        print(f"[triage-writer] scored file not found: {scored_path}", file=sys.stderr)
        return 2
    scored = json.loads(scored_path.read_text())

    output_path = Path(args.output) if args.output else _default_output_path(manifest["date"])

    try:
        write_triage_note(
            manifest, scored, output_path,
            manifest_path=str(manifest_path), force=args.force,
        )
    except RuntimeError as e:
        print(f"[triage-writer] {e}", file=sys.stderr)
        return 1

    print(f"[triage-writer] wrote {output_path}")
    print(f"[triage-writer] {manifest['counts']['generated'] + manifest['counts']['cached']} cards from {manifest_path.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify pass**

```bash
cd ~/code/the-dossier-apply-flow-v2 && pipeline/.venv/bin/python3 -m pytest pipeline/tests/test_triage_writer.py -v
```
Expected: 21 passed (13 from Task 6 + 8 new).

- [ ] **Step 5: Smoke test against real Plan 1 manifest**

```bash
cd ~/code/the-dossier-apply-flow-v2 && pipeline/.venv/bin/python3 -m pipeline.triage_writer \
  --manifest /Users/jhh/code/the-dossier/pipeline/data/pregenerated/2026-04-22-manifest.json \
  --scored-file /Users/jhh/code/the-dossier/pipeline/data/scored/2026-04-22.json \
  --output /tmp/test-triage.md
```
Expected: `[triage-writer] wrote /tmp/test-triage.md` printed; file exists with all 5 cards from the real manifest.

```bash
head -30 /tmp/test-triage.md
```
Eyeball: counts banner, A grade first, real CL preview text from one of the persisted `.md` files (or `(no preview available)` if the MD wasn't persisted by Plan 1's PDF render path).

- [ ] **Step 6: Run full suite**

```bash
cd ~/code/the-dossier-apply-flow-v2 && pipeline/.venv/bin/python3 -m pytest pipeline/ -q -m "not slow"
```
Expected: 100+ passed.

- [ ] **Step 7: Commit**

```bash
git add pipeline/triage_writer.py pipeline/tests/test_triage_writer.py
git commit -m "$(cat <<'EOF'
feat(triage-writer): file I/O + idempotency guard + CLI

write_triage_note refuses to overwrite a triage note with [x] apply or
[x] applied marks unless --force, so user triage state can't be wiped
by a re-run. CLI defaults: most recent manifest, scored_file from the
manifest itself, output path keyed by manifest date in the vault.
EOF
)"
```

---

## Phase E — execute parser/state

### Task 8: Implement `pipeline/execute.py` parser + state writer (pure functions)

**Files:**
- Create: `pipeline/execute.py` (pure functions only at this stage)
- Create: `pipeline/tests/test_execute_parser.py`
- Create: `pipeline/tests/test_execute_state.py`
- Create: `pipeline/tests/fixtures/triage_sample.md`

**Context:** Pure functions for parsing the triage markdown back to card structs and rewriting checkbox state. No Playwright, no subprocess. Task 10 layers Playwright on top.

- [ ] **Step 1: Create the triage_sample.md fixture**

`pipeline/tests/fixtures/triage_sample.md`:

```markdown
---
created: 2026-05-02
tags: [job-search, triage]
---

# Daily Triage 2026-05-02

3 A/B cards · 1 unresolved · manifest: pregenerated/2026-05-02-manifest.json

Tick `[x] apply` on cards to apply to. Run `/pipeline execute` after.

---

## [A] AcmeCo — Senior PM
- Salary: $200,000-$240,000 | Archetype: product_management | Lane: A
- Fit: Direct PM fit; strong AI tailwind.
- Risks: (none flagged)
- JD: https://job-boards.greenhouse.io/acmeco/jobs/123
- Resume: /abs/Jared-Hawkins-AcmeCo-Senior-PM-2026-05-02.pdf
- CL: /abs/Jared-Hawkins-AcmeCo-Senior-PM-2026-05-02.pdf
- CL preview: "Hello AcmeCo Hiring Team..."
- [x] apply
- [ ] skip

## [B] BetaInc — Product Manager
- Salary: $160,000-$190,000 | Archetype: product_management | Lane: A
- Fit: Solid B-grade dev tools PM.
- Risks: small team
- JD: https://jobs.lever.co/betainc/abc
- Resume: /abs/Jared-Hawkins-BetaInc-Product-Manager-2026-05-02.pdf
- CL: /abs/Jared-Hawkins-BetaInc-Product-Manager-2026-05-02.pdf
- CL preview: "BetaInc's dev tools..."
- [ ] apply
- [ ] skip

## [B] Charlie Corp — PM
- URL unresolved (Adzuna redirect only) — run `/pipeline resolve-urls` first
- ~~[ ] apply~~ ~~[ ] skip~~
```

- [ ] **Step 2: Write failing parser tests**

`pipeline/tests/test_execute_parser.py`:

```python
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
```

- [ ] **Step 3: Write failing state-writer tests**

`pipeline/tests/test_execute_state.py`:

```python
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
```

- [ ] **Step 4: Run to verify failure**

```bash
cd ~/code/the-dossier-apply-flow-v2 && pipeline/.venv/bin/python3 -m pytest pipeline/tests/test_execute_parser.py pipeline/tests/test_execute_state.py -v
```
Expected: FAIL — `No module named pipeline.execute`.

- [ ] **Step 5: Implement `pipeline/execute.py` (pure functions only — Playwright in Task 10)**

```python
"""Apply-flow execute mode.

Reads a daily triage markdown, queues [x] apply cards, drives a Playwright
session through them with pause-before-submit, then flips checkbox state
and logs to the Application Tracker.

This module contains pure functions for parsing + state rewrites in the
top half. The Playwright loop and CLI are added in Task 10.
"""
from __future__ import annotations

import enum
import re
from dataclasses import dataclass
from pathlib import Path


class CheckboxState(enum.Enum):
    UNCHECKED = "unchecked"      # [ ] apply
    APPLY = "apply"               # [x] apply  (queued)
    APPLIED = "applied"           # [x] applied (done)
    SKIPPED = "skipped"           # [ ] apply skipped
    ERROR = "error"               # [x] apply error: <msg>
    UNRESOLVED = "unresolved"     # ~~[ ] apply~~ ~~[ ] skip~~


@dataclass
class Card:
    grade: str
    company: str
    role: str
    url: str
    resume_pdf: str
    cl_pdf: str
    state: CheckboxState


# Section regex — captures everything from `## [GRADE] Company — Role` up to next `##` or EOF.
_SECTION_RE = re.compile(
    r"^## \[(?P<grade>[A-Z])\] (?P<company>.+?) — (?P<role>.+?)$"
    r"(?P<body>.*?)(?=^## |\Z)",
    re.MULTILINE | re.DOTALL,
)


def _extract_field(body: str, label: str) -> str:
    """Pull the value after `- {label}: ` in a section body."""
    m = re.search(rf"^- {re.escape(label)}: (.+)$", body, re.MULTILINE)
    return m.group(1).strip() if m else ""


def _classify_state(body: str) -> CheckboxState:
    if "URL unresolved" in body or "~~[ ] apply~~" in body:
        return CheckboxState.UNRESOLVED
    if re.search(r"^- \[x\] apply error:", body, re.MULTILINE):
        return CheckboxState.ERROR
    if re.search(r"^- \[x\] applied\b", body, re.MULTILINE):
        return CheckboxState.APPLIED
    if re.search(r"^- \[x\] apply\b", body, re.MULTILINE):
        return CheckboxState.APPLY
    if re.search(r"^- \[ \] apply skipped\b", body, re.MULTILINE):
        return CheckboxState.SKIPPED
    return CheckboxState.UNCHECKED


def parse_triage_markdown(text: str) -> list[Card]:
    """Parse a triage markdown into a list of Card structs."""
    cards: list[Card] = []
    for m in _SECTION_RE.finditer(text):
        body = m.group("body")
        cards.append(Card(
            grade=m.group("grade"),
            company=m.group("company").strip(),
            role=m.group("role").strip(),
            url=_extract_field(body, "JD"),
            resume_pdf=_extract_field(body, "Resume"),
            cl_pdf=_extract_field(body, "CL"),
            state=_classify_state(body),
        ))
    return cards


def _rewrite_card_apply_line(text: str, url: str, new_line: str) -> str:
    """Find the card section whose JD URL matches, replace the `[x] apply` (or `[ ] apply`)
    line with new_line. Idempotent: no match → no change."""
    sections = list(_SECTION_RE.finditer(text))
    out_chunks = []
    last_end = 0
    for m in sections:
        body = m.group("body")
        section_url = _extract_field(body, "JD")
        if section_url != url:
            continue

        # Locate the apply checkbox line in this section
        apply_re = re.compile(
            r"^- (\[x\] apply\b.*|\[ \] apply\b.*|\[x\] applied\b.*|\[ \] apply skipped\b.*)$",
            re.MULTILINE,
        )
        body_match = apply_re.search(body)
        if not body_match:
            continue

        # Splice in
        body_start = m.start("body")
        line_start = body_start + body_match.start()
        line_end = body_start + body_match.end()
        out_chunks.append(text[last_end:line_start])
        out_chunks.append(new_line)
        last_end = line_end

    if not out_chunks:
        return text
    out_chunks.append(text[last_end:])
    return "".join(out_chunks)


def flip_apply_to_applied(path: Path, *, url: str) -> None:
    """Rewrite the `[x] apply` line for the given URL → `[x] applied`."""
    text = path.read_text()
    new = _rewrite_card_apply_line(text, url, "- [x] applied")
    if new != text:
        path.write_text(new)


def flip_apply_to_skipped(path: Path, *, url: str) -> None:
    text = path.read_text()
    new = _rewrite_card_apply_line(text, url, "- [ ] apply skipped")
    if new != text:
        path.write_text(new)


def flip_apply_to_error(path: Path, *, url: str, message: str) -> None:
    text = path.read_text()
    new = _rewrite_card_apply_line(text, url, f"- [x] apply error: {message}")
    if new != text:
        path.write_text(new)
```

- [ ] **Step 6: Run tests to verify pass**

```bash
cd ~/code/the-dossier-apply-flow-v2 && pipeline/.venv/bin/python3 -m pytest pipeline/tests/test_execute_parser.py pipeline/tests/test_execute_state.py -v
```
Expected: 13 passed (8 parser + 5 state).

- [ ] **Step 7: Run full suite**

```bash
cd ~/code/the-dossier-apply-flow-v2 && pipeline/.venv/bin/python3 -m pytest pipeline/ -q -m "not slow"
```
Expected: 113+ passed.

- [ ] **Step 8: Commit**

```bash
git add pipeline/execute.py pipeline/tests/test_execute_parser.py pipeline/tests/test_execute_state.py pipeline/tests/fixtures/triage_sample.md
git commit -m "$(cat <<'EOF'
feat(execute): triage markdown parser + checkbox state rewrites

Pure functions only. parse_triage_markdown returns Card structs with a
CheckboxState enum (unchecked/apply/applied/skipped/error/unresolved).
flip_apply_to_* helpers rewrite the apply line for a given URL using
section-scoped replacement, leaving other cards untouched.
EOF
)"
```

---

## Phase F — execute Playwright integration

### Task 9: Extract `override_greenhouse_artifacts()` from `apply_flow_poc.py`

**Files:**
- Modify: `pipeline/apply_flow_poc.py` (add new function; existing functions kept)

**Context:** The POC has two helpers: `override_resume()` and `override_cover_letter()`. Wrap them as a single `override_greenhouse_artifacts(page, resume_path, cl_path)` function so `execute.py` can call one thing.

- [ ] **Step 1: Add the wrapper function in `pipeline/apply_flow_poc.py`**

After the existing `override_cover_letter` function (line 119), add:

```python
def override_greenhouse_artifacts(page, resume_path: Path, cl_path: Path) -> None:
    """Override Simplify-attached resume and CL on a Greenhouse form.

    POC-validated 2026-05-01. Single ATS only — Lever/Ashby in Plan 3.
    """
    override_resume(page, resume_path)
    override_cover_letter(page, cl_path)
```

(No tests for this — it's a one-line wrapper around already-tested-via-POC functions. Behavior is verified end-to-end in Task 12's e2e test.)

- [ ] **Step 2: Verify import works**

```bash
cd ~/code/the-dossier-apply-flow-v2 && pipeline/.venv/bin/python3 -c "from pipeline.apply_flow_poc import override_greenhouse_artifacts; print(override_greenhouse_artifacts)"
```
Expected: `<function override_greenhouse_artifacts at 0x...>` printed.

- [ ] **Step 3: Run full suite to confirm no regression**

```bash
cd ~/code/the-dossier-apply-flow-v2 && pipeline/.venv/bin/python3 -m pytest pipeline/ -q -m "not slow"
```
Expected: 113+ passed (no count change — POC extraction adds no tests).

- [ ] **Step 4: Commit**

```bash
git add pipeline/apply_flow_poc.py
git commit -m "$(cat <<'EOF'
feat(apply-flow-poc): expose override_greenhouse_artifacts() wrapper

Single entry point for execute.py to call into the POC's resume + CL
override pattern. Existing override_resume() and override_cover_letter()
are preserved for the standalone POC script.
EOF
)"
```

---

### Task 9.5: Implement `pipeline/ats_signals.py` — confirmation detection dispatch

**Files:**
- Create: `pipeline/ats_signals.py`
- Create: `pipeline/tests/test_ats_signals.py`
- Create: `pipeline/tests/fixtures/fake_greenhouse_thanks.html`

**Context:** Post-Enter, execute needs to verify the application actually submitted (per ai-chat pressure-test). Greenhouse-only in Plan 2; Plan 3 adds Lever/Ashby to the same dispatch table. Polls every 500ms for URL match OR DOM match within `timeout_seconds`. Conservative on miss (returns False → caller writes Unverified).

- [ ] **Step 1: Create the fake confirmation page fixture**

`pipeline/tests/fixtures/fake_greenhouse_thanks.html`:

```html
<!doctype html>
<html>
<head><title>Application submitted</title></head>
<body>
<h1>Thank you for applying!</h1>
<p>We've received your application and will be in touch.</p>
<div data-application-confirmation>true</div>
</body>
</html>
```

- [ ] **Step 2: Write failing tests in `pipeline/tests/test_ats_signals.py`**

```python
"""Tests for pipeline.ats_signals — typed dispatch for post-submit confirmation."""
from unittest.mock import MagicMock

import pytest

from pipeline.ats_signals import detect_confirmation, greenhouse_confirmed


# -- greenhouse_confirmed: unit-test with mocked page --

def _make_mock_page(*, url="https://job-boards.greenhouse.io/x/jobs/1", h1_text=None, has_confirmation_attr=False):
    """Build a Playwright-page-shaped mock."""
    page = MagicMock()
    page.url = url

    h1_loc = MagicMock()
    if h1_text:
        h1_loc.is_visible.return_value = True
        h1_loc.text_content.return_value = h1_text
    else:
        h1_loc.is_visible.return_value = False
        h1_loc.text_content.return_value = ""

    confirm_loc = MagicMock()
    confirm_loc.is_visible.return_value = has_confirmation_attr

    def locator(selector):
        if "h1" in selector:
            return h1_loc
        if "data-application-confirmation" in selector:
            return confirm_loc
        return MagicMock(is_visible=MagicMock(return_value=False))
    page.locator.side_effect = locator
    return page


def test_greenhouse_confirmed_url_match_confirmation():
    page = _make_mock_page(url="https://job-boards.greenhouse.io/x/jobs/1/confirmation")
    assert greenhouse_confirmed(page, timeout_seconds=1) is True


def test_greenhouse_confirmed_url_match_thanks():
    page = _make_mock_page(url="https://job-boards.greenhouse.io/x/applications/12345/thanks")
    assert greenhouse_confirmed(page, timeout_seconds=1) is True


def test_greenhouse_confirmed_dom_match_thank_you():
    page = _make_mock_page(h1_text="Thank you for your application")
    assert greenhouse_confirmed(page, timeout_seconds=1) is True


def test_greenhouse_confirmed_dom_match_data_attr():
    page = _make_mock_page(has_confirmation_attr=True)
    assert greenhouse_confirmed(page, timeout_seconds=1) is True


def test_greenhouse_confirmed_no_signal_returns_false_after_timeout():
    page = _make_mock_page()  # No URL, no h1, no attr
    assert greenhouse_confirmed(page, timeout_seconds=1) is False


# -- detect_confirmation dispatch --

def test_detect_confirmation_dispatches_greenhouse_url():
    page = _make_mock_page(url="https://job-boards.greenhouse.io/x/jobs/1/confirmation")
    assert detect_confirmation(
        page,
        url="https://job-boards.greenhouse.io/x/jobs/1",
        timeout_seconds=1,
    ) is True


def test_detect_confirmation_unknown_ats_returns_false():
    page = _make_mock_page(url="https://workday.com/jobs/abc/done")
    assert detect_confirmation(
        page,
        url="https://workday.com/jobs/abc",
        timeout_seconds=1,
    ) is False
```

- [ ] **Step 3: Run to verify failure**

```bash
cd ~/code/the-dossier-apply-flow-v2 && pipeline/.venv/bin/python3 -m pytest pipeline/tests/test_ats_signals.py -v
```
Expected: FAIL — `No module named pipeline.ats_signals`.

- [ ] **Step 4: Implement `pipeline/ats_signals.py`**

```python
"""ATS-typed dispatch for post-submit confirmation detection.

Plan 2 ships Greenhouse only. Plan 3 will add Lever and Ashby to the same
dispatch table. Returns False on unknown ATS (conservative — caller writes
Unverified, user reconciles).
"""
from __future__ import annotations

import re
import time
from urllib.parse import urlparse


_GREENHOUSE_URL_PATTERNS = [
    re.compile(r"/confirmation\b", re.IGNORECASE),
    re.compile(r"/applications/\d+/thanks\b", re.IGNORECASE),
    re.compile(r"[?&]application_submitted=true\b", re.IGNORECASE),
]
_GREENHOUSE_THANKYOU_TEXT = re.compile(r"thank\s*you", re.IGNORECASE)


def greenhouse_confirmed(page, timeout_seconds: int = 10) -> bool:
    """Poll for Greenhouse confirmation signal up to timeout_seconds.

    Returns True on:
    - URL match on /confirmation, /applications/N/thanks, or ?application_submitted=true
    - DOM h1 containing "thank you" (case-insensitive)
    - DOM element with [data-application-confirmation] attribute

    Returns False on timeout (conservative miss).
    """
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        # URL check (cheap)
        try:
            url = page.url or ""
        except Exception:
            url = ""
        for pat in _GREENHOUSE_URL_PATTERNS:
            if pat.search(url):
                return True

        # DOM check: h1 with "thank you"
        try:
            h1 = page.locator("h1").first
            if h1.is_visible(timeout=200):
                text = h1.text_content() or ""
                if _GREENHOUSE_THANKYOU_TEXT.search(text):
                    return True
        except Exception:
            pass

        # DOM check: data-application-confirmation attribute
        try:
            confirm = page.locator("[data-application-confirmation]").first
            if confirm.is_visible(timeout=200):
                return True
        except Exception:
            pass

        time.sleep(0.5)

    return False


def detect_confirmation(page, url: str, timeout_seconds: int = 10) -> bool:
    """Dispatch on URL host. Plan 2: Greenhouse only.

    Unknown ATS returns False (caller writes Unverified). Plan 3 will add
    Lever (jobs.lever.co) and Ashby (jobs.ashbyhq.com) handlers.
    """
    host = urlparse(url).netloc.lower()
    if "greenhouse.io" in host or "boards.greenhouse.io" in host:
        return greenhouse_confirmed(page, timeout_seconds=timeout_seconds)
    return False
```

- [ ] **Step 5: Run tests to verify pass**

```bash
cd ~/code/the-dossier-apply-flow-v2 && pipeline/.venv/bin/python3 -m pytest pipeline/tests/test_ats_signals.py -v
```
Expected: 7 passed.

- [ ] **Step 6: Run full suite**

```bash
cd ~/code/the-dossier-apply-flow-v2 && pipeline/.venv/bin/python3 -m pytest pipeline/ -q -m "not slow"
```
Expected: 120+ passed.

- [ ] **Step 7: Commit**

```bash
git add pipeline/ats_signals.py pipeline/tests/test_ats_signals.py pipeline/tests/fixtures/fake_greenhouse_thanks.html
git commit -m "$(cat <<'EOF'
feat(ats-signals): post-submit confirmation poll for Greenhouse

Resolves the "human Enter = submitted" trust gap from the ai-chat
pressure-test. detect_confirmation dispatches by URL host;
greenhouse_confirmed polls 500ms intervals up to timeout for URL
patterns (/confirmation, /applications/N/thanks, ?application_submitted)
or DOM signals (h1 "thank you", [data-application-confirmation]).

Returns False on miss — caller writes Unverified, 24h auto-retry
window kicks in via ledger semantics. Conservative by design: signal
combinations chosen to minimize false positives (no bare "thank you"
text matches, etc.).

Plan 2: Greenhouse only. Plan 3 will add Lever + Ashby to the same
dispatch table.
EOF
)"
```

---

### Task 10: Implement `execute.py` Playwright loop + CLI (with confirmation poll + status-aware writes)

**Files:**
- Modify: `pipeline/execute.py` (add Playwright loop, CLI, end-of-session prompt)
- Create: `pipeline/tests/test_execute_session.py`

**Context:** Now that the parser + state writer + tracker (with status enum + atomicity) + ats_signals are all in place, layer the Playwright session loop on top. Per the revised spec:
1. CL flag scan → warn-only prompt.
2. Launch Chromium with persistent profile + side-loaded Simplify.
3. Navigate to URL.
4. `simplify_wait_seconds` floor + poll-for-Simplify-done up to 2× ceiling.
5. `override_greenhouse_artifacts(page, resume, cl)`.
6. Pause for human review (Enter / s / q).
7. **On Enter:** `ats_signals.detect_confirmation()` poll. Confirmed → status=Applied + flip checkbox; miss → status=Unverified + leave checkbox at `[x] apply` (24h auto-retry path).
8. **On 's':** status=Skipped, no tracker row, flip to `[ ] apply skipped`.
9. **On exception:** status=Failed, flip to `[x] apply error: <msg>`.
10. End-of-session: counts breakdown (confirmed/unverified/failed), unverified reconciliation list, Tier A pitch list (grade A confirmed only).

**Queue construction is ledger-first:** `build_queue(triage_text, ledger_path)` filters cards in markdown `[x] apply` AND `ledger_eligible(card)`. Cards blocked by ledger surface in `--dry-run` output but don't run.

The Playwright launch + page interaction code is hard to unit-test without a real browser. We'll mock the Playwright launcher in unit tests for the session loop, and put the real-browser test in Task 12's gated e2e.

- [ ] **Step 1: Write failing tests for the session loop (mocked Playwright)**

`pipeline/tests/test_execute_session.py`:

```python
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
        "\tAcmeCo\tsenior pm\t\t2026-04-01\t\tA\tapplied\t2026-04-01\t1\n"
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
        "\tAcmeCo\tsenior pm\t\t2026-04-01\t\tA\tfailed\t2026-04-01\t1\n"
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
```

- [ ] **Step 2: Run to verify failure**

```bash
cd ~/code/the-dossier-apply-flow-v2 && pipeline/.venv/bin/python3 -m pytest pipeline/tests/test_execute_session.py -v
```
Expected: FAIL — `cannot import name 'format_pitch_summary'` (etc).

- [ ] **Step 3: Append session-loop functions and CLI to `pipeline/execute.py`**

Append to the end of the existing `pipeline/execute.py`:

```python
import argparse
import json
import os
import sys
import time
from datetime import date
from typing import Optional


# ---------------------------------------------------------------------------
# Queue + summary helpers (pure; ledger-aware)
# ---------------------------------------------------------------------------

def build_queue(triage_text: str, ledger_path: Path) -> list[Card]:
    """Cards in [x] apply state, filtered by ledger_eligible (state authority).

    A card is in the queue iff:
    1. Markdown has `[x] apply` (intent), AND
    2. Ledger says it's eligible (no `applied` row; no fresh `unverified` row).
    """
    from pipeline.tracker import ledger_eligible
    apply_cards = [c for c in parse_triage_markdown(triage_text)
                   if c.state == CheckboxState.APPLY]
    return [c for c in apply_cards
            if ledger_eligible(ledger_path, company=c.company, role=c.role)]


def format_pitch_summary(submitted: list[dict]) -> str:
    """End-of-session prompt: Grade A companies that were Confirmed-Applied.

    Excludes Unverified, Failed, and B grades. Returns "" if no qualifying
    submissions (so caller can decide whether to print)."""
    a_applied = [s for s in submitted
                 if s.get("grade") == "A" and s.get("status") == "applied"]
    if not a_applied:
        return ""
    lines = ["Tier A applied today — run /pitch for:"]
    for s in a_applied:
        lines.append(f"  - {s['company']}")
    return "\n".join(lines)


def format_session_summary(attempts: list[dict], queue_size: int) -> str:
    """Print line breakdown: 'N attempts → A applied · U unverified · F failed'."""
    n_applied = sum(1 for a in attempts if a.get("status") == "applied")
    n_unverified = sum(1 for a in attempts if a.get("status") == "unverified")
    n_failed = sum(1 for a in attempts if a.get("status") == "failed")
    return (f"Session done: {len(attempts)} attempts → "
            f"{n_applied} applied · {n_unverified} unverified · {n_failed} failed")


def format_unverified_section(attempts: list[dict]) -> str:
    """Per-card reconciliation list for Unverified attempts (24h auto-retry)."""
    unverified = [a for a in attempts if a.get("status") == "unverified"]
    if not unverified:
        return ""
    lines = ["", "Unverified (manual reconciliation may be needed):"]
    for a in unverified:
        lines.append(f"  - [{a.get('grade', '?')}] {a.get('company', '?')} — "
                     f"{a.get('role', '?')}")
        if a.get("url"):
            lines.append(f"    URL: {a['url']}")
        lines.append("    Auto-retry eligible after 24h (ledger unverified). "
                     "Force-resolve: edit ledger.tsv or run "
                     "`tracker_cli --status applied`")
    return "\n".join(lines)


def resolve_simplify_wait(
    flag_value: Optional[int], config_value: Optional[int],
) -> int:
    """Resolve simplify_wait_seconds: flag > env > config > default 3."""
    if flag_value is not None:
        return flag_value
    env = os.environ.get("PIPELINE_EXECUTE_SIMPLIFY_WAIT")
    if env is not None:
        try:
            return int(env)
        except ValueError:
            pass
    if config_value is not None:
        return config_value
    return 3


# ---------------------------------------------------------------------------
# Playwright session helpers (NOT unit-tested — covered by Task 12 e2e)
# ---------------------------------------------------------------------------

def _wait_for_simplify_done(page, base_seconds: int) -> None:
    """Sleep base_seconds (floor), then poll for Simplify-done up to 2*base (ceiling).

    Done = 'Autofill this page' button gone OR email field populated.
    Times out gracefully — logs warning, returns.
    """
    time.sleep(base_seconds)
    deadline = time.time() + base_seconds * 2
    while time.time() < deadline:
        # Email field populated?
        email = page.locator('input[type="email"], input[name*="email" i]').first
        try:
            value = email.input_value(timeout=200)
            if value:
                return
        except Exception:
            pass
        # Autofill button still showing?
        autofill_btn = page.locator('button:has-text("Autofill")').first
        try:
            if not autofill_btn.is_visible(timeout=200):
                return
        except Exception:
            return
        time.sleep(0.5)
    print(f"[execute] WARNING: Simplify autofill not detected within "
          f"{base_seconds * 3}s — proceeding anyway.")


def _prompt_user(message: str, valid_keys: tuple[str, ...]) -> str:
    """Read one keystroke + Enter from stdin. Loops until a valid key is supplied."""
    while True:
        print(message, end=" ", flush=True)
        try:
            response = input().strip().lower() or "p"  # Empty = Enter = "p"roceed
        except EOFError:
            return "q"
        if response in valid_keys:
            return response


def _run_one_card(
    card: Card, page, *, simplify_wait: int,
    triage_path: Path, tracker_path: Path, ledger_path: Path,
    attempts: list[dict],
) -> None:
    """Process one card. Side-effects: page navigation, file overrides,
    confirmation poll, tracker + ledger upsert (atomic), triage markdown rewrite.

    All paths to write a status: applied (confirmed), unverified (poll missed),
    failed (exception), skipped (user 's')."""
    from pipeline.tracker import AppStatus, record_attempt, upsert_ledger_row

    print(f"\n--- [{card.grade}] {card.company} — {card.role} ---")
    today = date.today().isoformat()

    def _record_failed(message: str) -> None:
        try:
            upsert_ledger_row(
                ledger_path, url=card.url, company=card.company, role=card.role,
                location="", date=today, score="", grade=card.grade,
                status=AppStatus.FAILED,
            )
        except Exception as e:
            print(f"[execute] WARNING: ledger write failed during failure handler: {e}")
        flip_apply_to_error(triage_path, url=card.url, message=message)
        attempts.append({
            "company": card.company, "grade": card.grade, "role": card.role,
            "url": card.url, "status": "failed",
        })

    # CL pre-flight scan
    cl_md_path = Path(card.cl_pdf).with_suffix(".md")
    if cl_md_path.exists():
        from pipeline.cl_flag_scan import scan_cl_text
        flags = scan_cl_text(cl_md_path.read_text())
        if flags:
            print(f"[execute] CL flag scan: {len(flags)} match(es)")
            for f in flags:
                print(f"  - {f.pattern_name}: {f.matched_text!r} … {f.context!r}")
            choice = _prompt_user(
                "Proceed despite CL flags? [p]roceed / [s]kip / [q]uit:",
                ("p", "s", "q"),
            )
            if choice == "s":
                upsert_ledger_row(
                    ledger_path, url=card.url, company=card.company, role=card.role,
                    location="", date=today, score="", grade=card.grade,
                    status=AppStatus.SKIPPED,
                )
                flip_apply_to_skipped(triage_path, url=card.url)
                attempts.append({
                    "company": card.company, "grade": card.grade,
                    "role": card.role, "url": card.url, "status": "skipped",
                })
                return
            if choice == "q":
                raise KeyboardInterrupt("user quit at flag prompt")

    # Navigate
    print(f"[execute] navigating: {card.url}")
    try:
        page.goto(card.url, wait_until="domcontentloaded", timeout=30_000)
    except Exception as e:
        print(f"[execute] page load failed: {e}")
        _record_failed(f"page load: {e}")
        return

    # Wait for Simplify
    _wait_for_simplify_done(page, simplify_wait)

    # Override artifacts
    from pipeline.apply_flow_poc import override_greenhouse_artifacts
    try:
        override_greenhouse_artifacts(
            page, Path(card.resume_pdf), Path(card.cl_pdf),
        )
    except Exception as e:
        print(f"[execute] override failed: {e}")
        _record_failed(f"override: {e}")
        return

    # Pause for human submit
    choice = _prompt_user(
        f"Form ready for {card.company} — {card.role}. "
        f"[Enter]=submitted / [s]=skip / [q]=quit:",
        ("p", "s", "q"),
    )
    if choice == "s":
        upsert_ledger_row(
            ledger_path, url=card.url, company=card.company, role=card.role,
            location="", date=today, score="", grade=card.grade,
            status=AppStatus.SKIPPED,
        )
        flip_apply_to_skipped(triage_path, url=card.url)
        attempts.append({
            "company": card.company, "grade": card.grade,
            "role": card.role, "url": card.url, "status": "skipped",
        })
        return
    if choice == "q":
        raise KeyboardInterrupt("user quit at submit prompt")

    # Post-Enter: poll for confirmation signal (resolves the "trust gap")
    from pipeline.ats_signals import detect_confirmation
    print(f"[execute] polling for confirmation signal (~10s)...")
    confirmed = detect_confirmation(page, url=card.url, timeout_seconds=10)

    status = AppStatus.APPLIED if confirmed else AppStatus.UNVERIFIED
    print(f"[execute] result: {'confirmed' if confirmed else 'unverified (no signal in 10s)'}")

    # Atomic write: tracker append + ledger upsert (rolls back tracker on ledger fail)
    try:
        record_attempt(
            tracker_path=tracker_path, ledger_path=ledger_path,
            url=card.url, company=card.company, role=card.role,
            source="Pipeline", location="", date=today,
            score="", grade=card.grade,
            status=status, notes="Pipeline logged",
        )
    except Exception as e:
        print(f"[execute] WARNING: record_attempt failed (tracker rolled back): {e}")
        attempts.append({
            "company": card.company, "grade": card.grade, "role": card.role,
            "url": card.url, "status": "failed",
        })
        flip_apply_to_error(triage_path, url=card.url, message=f"record_attempt: {e}")
        return

    # Markdown checkbox flip (cosmetic; ledger is truth)
    if confirmed:
        flip_apply_to_applied(triage_path, url=card.url)
    # On unverified: leave [x] apply alone so 24h auto-retry path works

    attempts.append({
        "company": card.company, "grade": card.grade, "role": card.role,
        "url": card.url, "status": status.value,
    })
    print(f"[execute] {status.value}: {card.company} — {card.role}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

PIPELINE_DIR = Path(__file__).resolve().parent
DEFAULT_TRACKER = (
    Path.home() / "Documents" / "Second Brain" / "02_Projects" / "Job Search"
    / "R - Application Tracker.md"
)
DEFAULT_LEDGER = PIPELINE_DIR / "data" / "ledger.tsv"


def _default_triage_path() -> Path:
    today = date.today().isoformat()
    return (
        Path.home() / "Documents" / "Second Brain" / "99_System"
        / "Job Search" / f"Daily Triage {today}.md"
    )


def _load_simplify_wait_from_config() -> Optional[int]:
    cfg_path = PIPELINE_DIR / "config.yaml"
    if not cfg_path.exists():
        return None
    try:
        import yaml
        cfg = yaml.safe_load(cfg_path.read_text()) or {}
        return cfg.get("apply_flow", {}).get("simplify_wait_seconds")
    except Exception:
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("note_path", nargs="?", default=None,
                        help="Path to triage note. Defaults to today's vault file.")
    parser.add_argument("--simplify-wait", type=int, default=None,
                        help="Override simplify_wait_seconds (default: config / env / 3).")
    parser.add_argument("--dry-run", action="store_true",
                        help="Parse triage and print queue, no Playwright.")
    parser.add_argument("--tracker-path", default=str(DEFAULT_TRACKER))
    parser.add_argument("--ledger-path", default=str(DEFAULT_LEDGER))
    args = parser.parse_args(argv)

    triage_path = Path(args.note_path) if args.note_path else _default_triage_path()
    if not triage_path.exists():
        print(f"[execute] no triage note at {triage_path} — run /pipeline review --batch first.",
              file=sys.stderr)
        return 2

    ledger_path = Path(args.ledger_path)
    queue = build_queue(triage_path.read_text(), ledger_path)
    print(f"[execute] queue: {len(queue)} card(s) (after ledger eligibility filter)")
    for c in queue:
        print(f"  - [{c.grade}] {c.company} — {c.role}")

    if args.dry_run:
        return 0
    if not queue:
        print("[execute] nothing to do.")
        return 0

    simplify_wait = resolve_simplify_wait(
        flag_value=args.simplify_wait,
        config_value=_load_simplify_wait_from_config(),
    )
    print(f"[execute] simplify_wait={simplify_wait}s")

    # Launch Playwright session (POC pattern)
    from pipeline.apply_flow_poc import _resolve_simplify_extension_path, PROFILE_DIR
    from playwright.sync_api import sync_playwright

    if not PROFILE_DIR.exists():
        print(f"[execute] no Chrome profile — run apply_flow_poc.py bootstrap first.",
              file=sys.stderr)
        return 2
    ext_path = _resolve_simplify_extension_path()

    attempts: list[dict] = []
    tracker_path = Path(args.tracker_path)
    # ledger_path already set above for build_queue

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=False,
            channel="chrome",
            args=[
                f"--disable-extensions-except={ext_path}",
                f"--load-extension={ext_path}",
                "--no-default-browser-check",
            ],
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        try:
            for card in queue:
                _run_one_card(
                    card, page,
                    simplify_wait=simplify_wait,
                    triage_path=triage_path,
                    tracker_path=tracker_path,
                    ledger_path=ledger_path,
                    attempts=attempts,
                )
        except KeyboardInterrupt as e:
            print(f"\n[execute] stopped: {e}")
        finally:
            ctx.close()

    # End-of-session summary: counts → unverified reconciliation → Tier A pitch
    print()
    print(format_session_summary(attempts, queue_size=len(queue)))
    unverified_section = format_unverified_section(attempts)
    if unverified_section:
        print(unverified_section)
    pitch = format_pitch_summary(attempts)
    if pitch:
        print()
        print(pitch)

    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run unit tests to verify pass**

```bash
cd ~/code/the-dossier-apply-flow-v2 && pipeline/.venv/bin/python3 -m pytest pipeline/tests/test_execute_session.py pipeline/tests/test_execute_parser.py pipeline/tests/test_execute_state.py -v
```
Expected: 22+ passed (parser 8 + state 5 + session 9).

- [ ] **Step 5: Smoke test the dry-run path against the real triage note from Task 7's smoke test**

```bash
cd ~/code/the-dossier-apply-flow-v2 && cp /tmp/test-triage.md /tmp/test-triage-with-tick.md
# Manually pre-tick one card so the queue isn't empty
sed -i '' 's/- \[ \] apply$/- [x] apply/' /tmp/test-triage-with-tick.md
pipeline/.venv/bin/python3 -m pipeline.execute /tmp/test-triage-with-tick.md --dry-run
```
Expected: `[execute] queue: N card(s)` with at least one card listed; `[execute] nothing to do.` if zero ticked.

- [ ] **Step 6: Run full suite**

```bash
cd ~/code/the-dossier-apply-flow-v2 && pipeline/.venv/bin/python3 -m pytest pipeline/ -q -m "not slow"
```
Expected: 130+ passed.

- [ ] **Step 7: Commit**

```bash
git add pipeline/execute.py pipeline/tests/test_execute_session.py
git commit -m "$(cat <<'EOF'
feat(execute): session loop with confirmation poll + status-aware writes

build_queue, format_pitch_summary, format_session_summary,
format_unverified_section, resolve_simplify_wait are pure (unit-
tested). _run_one_card drives the Playwright session and is covered
by Task 12 e2e.

Per-card outcome flow (resolves the "human Enter = submitted" trust
gap from the ai-chat pressure-test):
1. CL flag scan (warn-only)
2. Navigate, override artifacts
3. Pause for human submit
4. ats_signals.detect_confirmation poll (~10s)
5. Confirmed → status=Applied, atomic record_attempt, flip [x] applied
   Miss → status=Unverified, atomic record_attempt, leave [x] apply
6. Exception path → status=Failed, flip [x] apply error: <msg>

Queue is ledger-first via build_queue + ledger_eligible. Markdown
intent + ledger truth. Drift resolves toward ledger.

End-of-session: counts breakdown + unverified reconciliation list +
Tier A pitch list (only Confirmed-Applied A grades).
EOF
)"
```

---

## Phase G — /pipeline skill + e2e + README

### Task 11: Update `/pipeline` skill markdown

**Files:**
- Modify: `.claude/skills/pipeline/SKILL.md` (add `review --batch` and `execute` sections)

**Context:** The /pipeline skill needs documentation entries for the two new subcommands.

- [ ] **Step 1: Find the existing usage table at the top of `.claude/skills/pipeline/SKILL.md`**

```bash
sed -n '1,30p' ~/code/the-dossier-apply-flow-v2/.claude/skills/pipeline/SKILL.md
```

- [ ] **Step 2: Add two new rows to the Usage section**

In the Usage code block (around lines 11-19), add these two lines BEFORE the closing ` ``` `:

```
/pipeline review --batch   Write daily triage markdown for vault triage
/pipeline execute          Drive Playwright through ticked apply cards
```

- [ ] **Step 3: Add a new section "Stage 4: Batch Triage + Execute" at the end of the skill**

After the existing flag-handling section (`/pipeline --grade A`), and before the `## Full Run Flow` heading, append a new section:

```markdown

---

## Batch Triage + Execute (apply-flow v2)

For high-volume daily applications, the batch flow lets you triage on phone and execute at desk.

### `/pipeline review --batch`

Writes a daily triage markdown to `~/Documents/Second Brain/99_System/Job Search/Daily Triage YYYY-MM-DD.md`.

```bash
cd ~/code/the-dossier-apply-flow-v2 && pipeline/.venv/bin/python3 -m pipeline.triage_writer
```

Optional flags:
- `--manifest PATH` — pin a specific manifest (default: most recent)
- `--scored-file PATH` — pin a scored JSON (default: from manifest)
- `--output PATH` — pin output path (default: vault path keyed by manifest date)
- `--force` — overwrite even if `[x] apply`/`[x] applied` marks exist

Pre-req: run `/pipeline pregenerate` (Plan 1) first to build the manifest.

The note has one section per Grade A/B card with grade/title/company/salary/fit/risks/JD/resume/CL/CL-preview/checkboxes. Cards with unresolved (Adzuna redirector) URLs render with strikethrough checkboxes and a "run /pipeline resolve-urls first" warning — not part of the apply queue.

### `/pipeline execute [<note-path>]`

Reads the daily triage markdown, queues `[x] apply` cards, drives Playwright through them with pause-before-submit, then logs to the Application Tracker and flips the checkbox to `[x] applied`.

```bash
cd ~/code/the-dossier-apply-flow-v2 && pipeline/.venv/bin/python3 -m pipeline.execute
```

Optional flags:
- Positional `<note-path>` — pin a triage note (default: today's vault file)
- `--simplify-wait N` — Simplify autofill wait floor in seconds (default 3 from config; env `PIPELINE_EXECUTE_SIMPLIFY_WAIT` also honored)
- `--dry-run` — parse + report queue, no Playwright
- `--tracker-path PATH` — override the Application Tracker path
- `--ledger-path PATH` — override the dedup ledger path

Pre-reqs:
- Run `/pipeline review --batch` first to write the triage note.
- Tick `[x] apply` on cards to apply to.
- One-time setup: `~/code/the-dossier-apply-flow-v2/pipeline/.venv/bin/python3 pipeline/apply_flow_poc.py bootstrap` to create the persistent Chrome profile and log in to Simplify.

Per-card flow:
1. CL pre-flight scan (warn-only — `[X` / `[INSERT` / `"fill in"` / `"before sending"`).
2. Navigate to the card's URL.
3. Wait for Simplify autofill (floor + poll up to 2× ceiling).
4. Override resume + CL via `set_input_files`.
5. Pause: `Form ready. [Enter]=submitted / [s]=skip / [q]=quit`.
6. On Enter: tracker append → flip `[x] apply` → `[x] applied`.
7. On 's': flip `[x] apply` → `[ ] apply skipped`. No tracker write.
8. On 'q': stop loop. Remaining queued cards stay queued for next run.

End-of-session summary lists Grade A submissions for `/pitch` follow-up.

Out of scope (Plan 3): Lever, Ashby, custom essay LLM pass, programmatic Simplify autofill trigger.

---

```

- [ ] **Step 4: Verify the file is well-formed**

```bash
cd ~/code/the-dossier-apply-flow-v2 && grep "^## " .claude/skills/pipeline/SKILL.md
```
Expected: includes both `## Full Run Flow` and `## Batch Triage + Execute (apply-flow v2)`.

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/pipeline/SKILL.md
git commit -m "$(cat <<'EOF'
docs(pipeline-skill): document review --batch and execute subcommands

Adds Usage rows and a "Batch Triage + Execute" section covering pre-reqs,
flags, per-card flow, and out-of-scope items for Plan 2.
EOF
)"
```

---

### Task 12: End-to-end integration test (gated, slow)

**Files:**
- Create: `pipeline/tests/test_execute_e2e.py`
- Create: `pipeline/tests/fixtures/fake_greenhouse.html`

**Context:** Boots a fake Greenhouse-shape HTML fixture on a localhost HTTP server. Drives execute against a triage note pointing at it. Verifies file inputs received the right paths, checkbox flips, tracker rows. No real Simplify, no real ATS.

This test is `@pytest.mark.slow` and not in the default suite. Plan 1's existing `test_pdf_render.py` follows the same pattern for the slow PDF render test.

- [ ] **Step 1: Create the fake Greenhouse HTML fixture**

`pipeline/tests/fixtures/fake_greenhouse.html`:

```html
<!doctype html>
<html>
<head><title>Apply for X at FakeCo</title></head>
<body>
<h1>Apply for X at FakeCo</h1>
<form>
  <label>Email <input type="email" name="email" id="email" /></label>
  <label>Resume <input type="file" name="resume" id="resume" accept=".pdf" /></label>
  <label>Cover Letter <input type="file" name="cover_letter" id="cover_letter" accept=".pdf" /></label>
  <button type="submit">Submit</button>
</form>
</body>
</html>
```

- [ ] **Step 2: Write the e2e test**

`pipeline/tests/test_execute_e2e.py`:

```python
"""Slow e2e: fake Greenhouse via http.server + real Playwright."""
import http.server
import shutil
import socketserver
import tempfile
import threading
from contextlib import contextmanager
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@contextmanager
def _serve_fixtures():
    """Boot http.server on an ephemeral port serving the fixtures dir."""
    handler = lambda *a, **kw: http.server.SimpleHTTPRequestHandler(
        *a, directory=str(FIXTURES), **kw,
    )
    httpd = socketserver.TCPServer(("127.0.0.1", 0), handler)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}/fake_greenhouse.html"
    finally:
        httpd.shutdown()


@pytest.mark.slow
def test_execute_e2e_overrides_files_and_logs(tmp_path, monkeypatch):
    """Happy-path execute against fake Greenhouse: override + tracker write + flip."""
    # 1. Build a real resume + CL PDF on disk (just empty bytes — we check the override path)
    resume_pdf = tmp_path / "resume.pdf"
    resume_pdf.write_bytes(b"%PDF-1.4 stub\n")
    cl_pdf = tmp_path / "cl.pdf"
    cl_pdf.write_bytes(b"%PDF-1.4 stub\n")
    cl_md = cl_pdf.with_suffix(".md")
    cl_md.write_text("Hello FakeCo, I'm applying.")

    # 2. Tracker + ledger fixtures
    tracker_path = tmp_path / "Tracker.md"
    shutil.copy(FIXTURES / "tracker_sample.md", tracker_path)
    ledger_path = tmp_path / "ledger.tsv"
    shutil.copy(FIXTURES / "ledger_sample.tsv", ledger_path)

    with _serve_fixtures() as url:
        # 3. Triage note pointing at fake URL
        triage_path = tmp_path / "Daily Triage 2026-05-02.md"
        triage_path.write_text(
            f"# Daily Triage 2026-05-02\n\n"
            f"## [A] FakeCo — X\n"
            f"- JD: {url}\n"
            f"- Resume: {resume_pdf}\n"
            f"- CL: {cl_pdf}\n"
            f"- [x] apply\n"
        )

        # 4. Stub user prompts: always proceed
        from pipeline import execute as exec_mod
        monkeypatch.setattr(exec_mod, "_prompt_user", lambda *a, **kw: "p")

        # 5. Run main()
        rc = exec_mod.main([
            str(triage_path),
            "--simplify-wait", "1",
            "--tracker-path", str(tracker_path),
            "--ledger-path", str(ledger_path),
        ])
        assert rc == 0

    # 6. Verify checkbox flipped
    text = triage_path.read_text()
    assert "[x] applied" in text

    # 7. Verify tracker row appended
    tracker_text = tracker_path.read_text()
    assert "| FakeCo | X | Pipeline | " in tracker_text
```

- [ ] **Step 3: Run the slow test**

```bash
cd ~/code/the-dossier-apply-flow-v2 && pipeline/.venv/bin/python3 -m pytest pipeline/tests/test_execute_e2e.py -v -m slow
```
Expected: PASS. Wall time ~10-15s (Chromium spin-up).

If Playwright Chromium isn't installed (cache version drift from Plan 1), this may fail with the "Looks like Playwright was just installed" message — install with:
```bash
pipeline/.venv/bin/playwright install chromium
```

If Simplify extension isn't side-loaded (POC bootstrap not run): the test should still pass because the fake Greenhouse doesn't trigger Simplify (no real autofill). The `_wait_for_simplify_done` will time out gracefully and proceed.

- [ ] **Step 4: Run full default suite to confirm slow test is gated**

```bash
cd ~/code/the-dossier-apply-flow-v2 && pipeline/.venv/bin/python3 -m pytest pipeline/ -q -m "not slow"
```
Expected: 130+ passed, 2+ deselected (the new e2e + the existing slow PDF test).

- [ ] **Step 5: Commit**

```bash
git add pipeline/tests/test_execute_e2e.py pipeline/tests/fixtures/fake_greenhouse.html
git commit -m "$(cat <<'EOF'
test(execute): gated e2e against fake Greenhouse fixture

Boots http.server on ephemeral port serving fake_greenhouse.html.
Drives execute via Playwright; verifies file inputs received the right
paths, checkbox flipped to applied, tracker row appended.

Pure happy-path. No real Simplify, no real ATS. Marked @pytest.mark.slow
so default suite stays network-free.
EOF
)"
```

---

### Task 13: Operator README

**Files:**
- Create: `pipeline/apply_flow_v2_README.md`

**Context:** Operator docs covering the full Plan 2 flow: pregenerate → review --batch → triage on phone → execute. Mirrors Plan 1's `apply_flow_v1_README.md`.

- [ ] **Step 1: Write `pipeline/apply_flow_v2_README.md`**

```markdown
# Apply-Flow v2 — Batch Triage + Execute

Plan 2 of the apply-flow v1 build. Adds two commands on top of Plan 1's pre-generation:
- `/pipeline review --batch` writes a daily triage markdown into the vault.
- `/pipeline execute` reads ticked cards and drives Playwright through them.

## Daily flow

1. **Overnight (or any time):** `/pipeline pregenerate` (Plan 1) — generates resume + CL PDFs and writes the manifest.
2. **Morning:** `/pipeline review --batch` — writes `~/Documents/Second Brain/99_System/Job Search/Daily Triage YYYY-MM-DD.md`.
3. **Phone (anywhere, any time):** open the triage note in Obsidian. Tick `[x] apply` on cards to apply to.
4. **At desk:** `/pipeline execute` — runs through the queue, pauses per card for human submit.

End-of-session output lists Grade A applications for `/pitch` follow-up.

## One-time setup

```bash
# Build the venv (if not done by Plan 1)
cd ~/code/the-dossier-apply-flow-v2/pipeline && python3.14 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/playwright install chromium

# Bootstrap the persistent Chrome profile + Simplify side-load + login
.venv/bin/python3 ~/code/the-dossier-apply-flow-v2/pipeline/apply_flow_poc.py bootstrap
```

The bootstrap step opens Chrome with the side-loaded Simplify extension. Log in to your Simplify account; cookies persist. You only do this once per machine.

## Triage (`/pipeline review --batch`)

```bash
cd ~/code/the-dossier-apply-flow-v2 && pipeline/.venv/bin/python3 -m pipeline.triage_writer
```

Defaults:
- Most recent manifest in `pipeline/data/pregenerated/`.
- Output path keyed by manifest date in vault.
- Refuses to overwrite a triage note that has any `[x] apply`/`[x] applied` marks unless `--force`.

Output shape (Option A — section per card):

```markdown
## [A] AcmeCo — Senior PM
- Salary: $200,000 | Archetype: product_management | Lane: A
- Fit: Direct PM fit; strong AI tailwind.
- Risks: (none flagged)
- JD: https://job-boards.greenhouse.io/acmeco/jobs/123
- Resume: /abs/.../resume.pdf
- CL: /abs/.../cl.pdf
- CL preview: "Hello AcmeCo Hiring Team..."
- [ ] apply
- [ ] skip
```

Cards with unresolved (Adzuna redirector) URLs render with strikethrough checkboxes and a warning — they're not in the apply queue. Run `/pipeline resolve-urls` to convert them.

## Execute (`/pipeline execute`)

```bash
cd ~/code/the-dossier-apply-flow-v2 && pipeline/.venv/bin/python3 -m pipeline.execute
```

Defaults: today's triage note in vault. Pass a positional path to override.

Useful flags:
- `--dry-run` — parse + show queue, no Playwright
- `--simplify-wait N` — Simplify autofill wait floor in seconds
- `--tracker-path PATH` / `--ledger-path PATH` — override default vault paths

Per-card behavior:
1. CL pre-flight scan — warns if `[X`, `[INSERT`, `"fill in"`, or `"before sending"` appear in the CL prose. User decides proceed/skip/quit.
2. Navigate to URL. Wait for Simplify (floor + poll up to 2×).
3. Override resume + CL via `set_input_files`.
4. Pause with form on screen. `[Enter]` = submitted, `[s]` = skip, `[q]` = quit.
5. On submit: append to Application Tracker → flip `[x] apply` to `[x] applied`.

Resume mid-flight: re-running execute on the same note skips `[x] applied` cards automatically. If you killed the session mid-card, that card stays `[x] apply` for next run; tracker dedup catches the duplicate if it already submitted.

## Configuration

`pipeline/config.yaml` may include:

```yaml
apply_flow:
  simplify_wait_seconds: 3
```

Resolution order for `simplify_wait_seconds`: `--simplify-wait` flag > `PIPELINE_EXECUTE_SIMPLIFY_WAIT` env > config > default 3.

## Tests

```bash
cd ~/code/the-dossier-apply-flow-v2 && pipeline/.venv/bin/python3 -m pytest pipeline/ -q -m "not slow"
```

The slow gated tests (browser-real PDF render + e2e Playwright happy path) run with `-m slow`.

## Out of scope (Plan 3)

- Multi-ATS adapters (Lever, Ashby) — currently Greenhouse only.
- LLM essay pass for textareas.
- Programmatic Simplify autofill triggering (currently waits for Simplify; doesn't click "Autofill this page").
- Fully unattended submit.
```

- [ ] **Step 2: Commit**

```bash
git add pipeline/apply_flow_v2_README.md
git commit -m "$(cat <<'EOF'
docs(apply-flow-v2): operator README for Plan 2 batch flow

Covers daily flow, one-time bootstrap, /pipeline review --batch + execute
usage, configuration resolution order, test invocation, and Plan 3 scope.
EOF
)"
```

---

## Acceptance Checklist

After all 15 tasks (0, 1-13, plus 9.5) complete:

- [ ] `pipeline/.venv/bin/python3 -m pytest pipeline/ -q -m "not slow"` reports 130+ passed.
- [ ] `pipeline/.venv/bin/python3 -m pytest pipeline/ -q -m slow` runs the e2e and PDF tests (1 e2e + 1 PDF = 2 slow tests pass).
- [ ] `/pipeline review --batch` writes a triage note for the existing 2026-04-22 manifest, with all 5 cards present, A grade first, alphabetical within grade, real CL preview text from the persisted `.md` files.
- [ ] `/pipeline execute --dry-run` against a hand-ticked triage note prints the queue (filtered by `ledger_eligible`) without launching Playwright.
- [ ] `pipeline/.venv/bin/python3 -m pipeline.migrate_ledger` is idempotent: first run reports `migrated`, second run reports `already migrated`, no diff.
- [ ] `/apply` skill markdown invokes `python -m pipeline.tracker_cli --status applied` and not Edit-tool table manipulation.
- [ ] `pipeline/cover_letter.py` writes `.md` alongside `.pdf` for both `--markdown-only` and the default PDF path.
- [ ] `pipeline/apply_flow_poc.py` exposes `override_greenhouse_artifacts(page, resume, cl)`.
- [ ] `pipeline/ats_signals.greenhouse_confirmed` returns True for all of: URL with `/confirmation`, URL with `/applications/N/thanks`, DOM with `<h1>Thank you</h1>`, DOM with `[data-application-confirmation]`. False after timeout with no signal.
- [ ] `pipeline/tracker.ledger_eligible` correctly returns True/False per the rules table (applied blocks; failed/skipped eligible; unverified <24h cooling down; unverified >24h eligible).
- [ ] `pipeline/tracker.record_attempt` rolls back the tracker row when the ledger upsert raises (atomicity test passes).
- [ ] All commits are individually clean (no fixup/wip messages, each commit's tests pass).

## Estimate

| Task | Hours |
|---|---|
| 0 — migrate_ledger.py | 1.0 |
| 1 — CL .md persistence | 0.3 |
| 2 — tracker.py (status enum + upsert + atomicity + ledger_eligible) | 2.5 |
| 3 — tracker_cli.py (with --status flag) | 0.7 |
| 4 — /apply skill rewrite | 0.5 |
| 5 — cl_flag_scan.py | 0.7 |
| 6 — triage_writer pure | 1.5 |
| 7 — triage_writer CLI | 1.0 |
| 8 — execute parser/state | 1.5 |
| 9 — POC extraction | 0.2 |
| 9.5 — ats_signals.py | 1.5 |
| 10 — execute Playwright loop (with confirmation poll + status-aware writes) | 2.5 |
| 11 — /pipeline skill | 0.3 |
| 12 — e2e integration | 1.0 |
| 13 — README | 0.3 |
| **Total** | **~15 hrs** |

(Original spec estimated 9 hrs; pre-pressure-test plan was 11 hrs. The +4 over the original plan reflects: schema migration (Task 0, +1), tracker.py expansion for status enum + upsert + atomicity + ledger_eligible (+1), ats_signals module + tests (+1.5), execute.py expansion for verification poll + status-aware writes + atomicity wiring (+1). The dialogue's 28 hrs over-corrected; 15 is the honest number.)

---

*Plan written 2026-05-02 from the approved spec. **Revised 2026-05-02** to incorporate ai-chat pressure-test findings (submission verification, schema for uncertainty, ledger-first authority, atomicity wrapper). Next: subagent-driven-development to execute task-by-task.*
