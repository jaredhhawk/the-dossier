# Apply-Flow POC Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Validate that Playwright can override Simplify autofill on a real Greenhouse form by clearing the auto-attached default resume, uploading a tailored PDF, and uploading a tailored cover letter PDF — leaving the form in a "ready to submit" state for manual review.

**Architecture:** Single-file Python script using Playwright sync API + persistent Chromium profile that contains the Simplify Chrome extension and user's Simplify login. Script navigates to a hardcoded Greenhouse JD URL, waits for Simplify to autofill, then targets resume + cover letter file inputs via Greenhouse-specific selectors, replacing Simplify's defaults with pre-generated tailored artifacts. Pauses with browser open for user to review and manually click submit.

**Tech Stack:** Python 3.x, Playwright sync API (already installed in `~/code/the-dossier/pipeline/.venv`), Chromium (Playwright-bundled), Simplify Chrome extension (installed in persistent profile via one-time user bootstrap), Greenhouse ATS form selectors.

**Spec source:** `/Users/jhh/Documents/Second Brain/02_Projects/Job Search Pipeline/Pipeline Apply-Flow Diagnostic.md` (Phase 1 dry-run findings inform selector strategy).

---

## Pre-flight: Open Questions (RESOLVED 2026-04-30)

1. **Chrome profile location** — `~/code/the-dossier/pipeline/.cache/chrome-profile/` ✅
2. **Cover letter PDF for test** — `/Users/jhh/Downloads/CPRS_CoverLetter.pdf` ✅ (any CL PDF works for upload mechanism testing)
3. **POC invocation pattern** — hardcoded LVT URL + paths ✅
4. **Test target** — LVT Sr Director PM ✅
5. **Submit safety** — pause-indefinitely model, no auto-submit ✅

---

## File Structure

POC is intentionally single-file. Future v1 will split into modules.

**Create:**
- `~/code/the-dossier/pipeline/apply_flow_poc.py` — Main POC script
- `~/code/the-dossier/pipeline/apply_flow_poc_README.md` — Bootstrap + run docs

**Create (gitignored, not in repo):**
- `~/code/the-dossier/pipeline/.cache/chrome-profile/` — Persistent Chromium user data dir (created on first launch by bootstrap)

**Modify:**
- `~/code/the-dossier/.gitignore` — Add `pipeline/.cache/` if not already excluded

**Reference (read-only):**
- `~/code/the-dossier/pipeline/data/resumes/output/Jared-Hawkins-LVT-Principal-Product-Manager-Intelligent-Site-Management-2026-04-30.pdf` — Pre-generated resume PDF (already exists from this session)
- User-provided CL PDF (path TBD per Pre-flight Q2)

---

## Note on TDD

POC is mostly browser automation against a live external site. Traditional unit testing doesn't apply — the "test" is watching the script run on a real Greenhouse form, observed by the user. No pure functions in the POC are complex enough to merit isolated unit tests. Manual test protocol (Tasks 4 + 5 + 7) replaces automated tests for this iteration. Frequent commits remain — each task ends with a commit.

---

## Tasks

### Task 1: Add gitignore entry for Chrome profile cache

**Files:**
- Modify: `~/code/the-dossier/.gitignore`

- [ ] **Step 1: Check if .gitignore already excludes pipeline/.cache/**

```bash
grep -n "\.cache\|pipeline/\.cache" ~/code/the-dossier/.gitignore
```
Expected: no matching line (otherwise skip remaining steps in this task).

- [ ] **Step 2: Append exclusion**

Append to `~/code/the-dossier/.gitignore`:
```
# Apply-flow POC: persistent Chrome profile (Simplify extension + login)
pipeline/.cache/
```

- [ ] **Step 3: Verify**

```bash
grep "pipeline/.cache" ~/code/the-dossier/.gitignore
```
Expected: matches.

- [ ] **Step 4: Commit**

```bash
cd ~/code/the-dossier && git add .gitignore && git commit -m "chore: gitignore apply-flow chrome profile cache"
```

---

### Task 2: Create POC scaffold with bootstrap function

**Files:**
- Create: `~/code/the-dossier/pipeline/apply_flow_poc.py`

- [ ] **Step 1: Create the file**

```python
#!/usr/bin/env python3
"""Apply-flow POC: Playwright override over Simplify autofill on Greenhouse.

Scope (intentionally narrow):
- Single Greenhouse JD URL (hardcoded LVT Sr Director PM)
- Validates resume override (clear default + upload tailored PDF)
- Validates CL upload (click upload tab + upload PDF)
- Pauses indefinitely for user review and manual submit
- No essay handling, no submit detection, no logging
"""

from pathlib import Path
import sys
import time

from playwright.sync_api import sync_playwright

# ---- Config (POC: hardcoded) ----
PIPELINE_DIR = Path(__file__).parent
PROFILE_DIR = PIPELINE_DIR / ".cache" / "chrome-profile"

JD_URL = "https://job-boards.greenhouse.io/liveviewtechnologiesinc/jobs/5172740008"
RESUME_PATH = PIPELINE_DIR / "data" / "resumes" / "output" / "Jared-Hawkins-LVT-Principal-Product-Manager-Intelligent-Site-Management-2026-04-30.pdf"
COVER_LETTER_PATH = Path("/Users/jhh/Downloads/CPRS_CoverLetter.pdf")  # Test artifact (any CL PDF works — POC doesn't submit)

SIMPLIFY_AUTOFILL_WAIT_SEC = 5  # Bump if Simplify is slow on user's machine
SIMPLIFY_EXTENSION_INSTALL_URL = "https://chromewebstore.google.com/detail/simplify-copilot-autofill/pbanhockgagggenencehbnadejlgchfc"


def bootstrap():
    """One-time setup: launch persistent Chrome so user can install Simplify + log in.

    Run this ONCE before run(). The profile persists across runs.
    """
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[bootstrap] Launching Chrome with profile at: {PROFILE_DIR}")
    print("[bootstrap] In the browser that opens:")
    print("  1. Install the Simplify Copilot extension (Web Store page is opened for you)")
    print("  2. Log in to your Simplify account at https://simplify.jobs")
    print("  3. Verify the extension is enabled (puzzle icon in toolbar)")
    print("  4. Close the browser when done. Profile is saved.")
    print()

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=False,
            args=["--no-default-browser-check"],
        )
        page = ctx.new_page()
        page.goto(SIMPLIFY_EXTENSION_INSTALL_URL)
        try:
            page.wait_for_event("close", timeout=0)
        except Exception:
            pass
        ctx.close()

    print(f"[bootstrap] Profile saved at {PROFILE_DIR}.")
    print("[bootstrap] Next: set COVER_LETTER_PATH at top of script, then run:")
    print(f"  cd ~/code/the-dossier && pipeline/.venv/bin/python3 pipeline/apply_flow_poc.py")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "bootstrap":
        bootstrap()
    else:
        print("Usage:")
        print("  python apply_flow_poc.py bootstrap  # one-time profile setup")
        print("  python apply_flow_poc.py            # run the POC (after bootstrap)")
        sys.exit(1)
```

- [ ] **Step 2: Verify syntax**

```bash
~/code/the-dossier/pipeline/.venv/bin/python3 -c "import ast; ast.parse(open('/Users/jhh/code/the-dossier/pipeline/apply_flow_poc.py').read())"
```
Expected: no output.

- [ ] **Step 3: Commit**

```bash
cd ~/code/the-dossier && git add pipeline/apply_flow_poc.py && git commit -m "feat(apply-flow): add POC scaffold with bootstrap function"
```

---

### Task 3: USER ACTION — bootstrap Chrome profile (install Simplify + log in)

This is a one-time manual step. ~10-15 min user time.

- [ ] **Step 1: User runs bootstrap**

```bash
cd ~/code/the-dossier && pipeline/.venv/bin/python3 pipeline/apply_flow_poc.py bootstrap
```

- [ ] **Step 2: User installs Simplify extension and logs in**

In the launched Chrome:
- Click "Add to Chrome" on the Web Store page
- Confirm the extension install
- Navigate to https://simplify.jobs and log in
- Pin the extension (puzzle icon → pin Simplify) so it's visible
- Close the browser window

- [ ] **Step 3: Verify the profile was created**

```bash
ls ~/code/the-dossier/pipeline/.cache/chrome-profile/
```
Expected: directory contains `Default/`, `Local State`, etc.

- [ ] **Step 4: USER REPORT BACK** — confirm bootstrap completed cleanly before Task 4. If Simplify didn't install or login didn't stick, troubleshoot before proceeding.

---

### Task 4: Add run() function with navigation + Simplify wait (no override yet)

**Files:**
- Modify: `~/code/the-dossier/pipeline/apply_flow_poc.py`

- [ ] **Step 1: Add run() function above the `if __name__ == "__main__"` block**

```python
def run():
    """Run the POC: open Greenhouse JD, wait for Simplify autofill, override artifacts, pause for review."""
    if not RESUME_PATH.exists():
        sys.exit(f"[error] Resume PDF not found: {RESUME_PATH}")
    if not COVER_LETTER_PATH.exists():
        sys.exit(f"[error] Cover letter PDF not found: {COVER_LETTER_PATH}")
    if not PROFILE_DIR.exists():
        sys.exit(f"[error] Chrome profile not found at {PROFILE_DIR}. Run: python apply_flow_poc.py bootstrap")

    print(f"[run] Resume:       {RESUME_PATH.name}")
    print(f"[run] Cover letter: {COVER_LETTER_PATH.name}")
    print(f"[run] JD:           {JD_URL}")
    print()

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=False,
            args=["--no-default-browser-check"],
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        print(f"[run] Navigating to JD...")
        page.goto(JD_URL, wait_until="domcontentloaded")

        print(f"[run] Waiting {SIMPLIFY_AUTOFILL_WAIT_SEC}s for Simplify to autofill...")
        time.sleep(SIMPLIFY_AUTOFILL_WAIT_SEC)

        print(f"[run] (Override logic will go here in Task 5)")
        print(f"[run] DO NOT auto-submit. Review and submit manually.")
        print(f"[run] Close the browser to exit.")
        try:
            page.wait_for_event("close", timeout=0)
        except KeyboardInterrupt:
            pass
        finally:
            ctx.close()
```

- [ ] **Step 2: Update the CLI dispatch to call run() when no args**

Replace the `else` branch in `if __name__ == "__main__":` block:

```python
    else:
        run()
```

(Removes the `Usage:` print + `sys.exit(1)`.)

- [ ] **Step 3: Verify syntax**

```bash
~/code/the-dossier/pipeline/.venv/bin/python3 -c "import ast; ast.parse(open('/Users/jhh/code/the-dossier/pipeline/apply_flow_poc.py').read())"
```

- [ ] **Step 4: Manual smoke test (navigation only, no override yet)**

User must have completed Task 3 AND set `COVER_LETTER_PATH`.
```bash
cd ~/code/the-dossier && pipeline/.venv/bin/python3 pipeline/apply_flow_poc.py
```
Expected:
- Chrome opens with Simplify visible
- Page navigates to LVT JD
- Simplify autofills standard fields after ~5 sec
- Terminal pauses
- User closes browser; script exits cleanly

If Simplify doesn't autofill, bump `SIMPLIFY_AUTOFILL_WAIT_SEC` to 10 and re-test.

- [ ] **Step 5: Commit**

```bash
cd ~/code/the-dossier && git add pipeline/apply_flow_poc.py && git commit -m "feat(apply-flow): add navigation + simplify wait"
```

---

### Task 5: Add resume + cover letter override logic

The hard part. Greenhouse-specific selectors. Two-step for resume (Simplify auto-attached its default; we replace via set_input_files which also overwrites). Two-step for CL (click "Attach" tab in multi-source picker, then upload).

**Files:**
- Modify: `~/code/the-dossier/pipeline/apply_flow_poc.py`

- [ ] **Step 1: Replace the placeholder line in run() with override calls**

Find:
```python
        print(f"[run] (Override logic will go here in Task 5)")
```
Replace with:
```python
        print(f"[run] Overriding resume...")
        override_resume(page, RESUME_PATH)

        print(f"[run] Overriding cover letter...")
        override_cover_letter(page, COVER_LETTER_PATH)
```

- [ ] **Step 2: Add two helper functions above run()**

```python
def override_resume(page, resume_path: Path):
    """Greenhouse: replace Simplify's auto-attached default resume with tailored PDF.

    set_input_files atomically replaces any existing file on the input.
    Brief settle wait afterward so Simplify doesn't race-overwrite.
    """
    resume_input = page.locator(
        'input[type="file"][id*="resume" i], input[type="file"][name*="resume" i]'
    ).first
    resume_input.wait_for(state="attached", timeout=10_000)
    resume_input.set_input_files(str(resume_path))
    page.wait_for_timeout(2_000)
    print(f"[run]   Resume set to: {resume_path.name}")


def override_cover_letter(page, cl_path: Path):
    """Greenhouse multi-source CL picker: click 'Attach' tab, then upload PDF.

    Per Phase 1 finding: CL field is a picker with Attach / Dropbox / Google Drive / manual entry.
    'Attach' surfaces the file input.
    """
    cl_section = page.get_by_text("Cover Letter", exact=False).first
    cl_section.scroll_into_view_if_needed()

    # Try button role first; fall back to text locator
    attach = page.get_by_role("button", name="Attach", exact=False).first
    if attach.count() == 0 or not attach.is_visible():
        attach = page.get_by_text("Attach", exact=False).first
    attach.click()
    page.wait_for_timeout(500)

    cl_input = page.locator(
        'input[type="file"][id*="cover" i], input[type="file"][name*="cover" i]'
    ).first
    cl_input.wait_for(state="attached", timeout=10_000)
    cl_input.set_input_files(str(cl_path))
    print(f"[run]   Cover letter set to: {cl_path.name}")
```

- [ ] **Step 3: Verify syntax**

```bash
~/code/the-dossier/pipeline/.venv/bin/python3 -c "import ast; ast.parse(open('/Users/jhh/code/the-dossier/pipeline/apply_flow_poc.py').read())"
```

- [ ] **Step 4: Manual end-to-end test**

```bash
cd ~/code/the-dossier && pipeline/.venv/bin/python3 pipeline/apply_flow_poc.py
```
Expected:
- Chrome opens, navigates to LVT JD
- Simplify autofills standard fields
- Script swaps resume to tailored PDF (visible in form: filename now starts with `Jared-Hawkins-LVT-...`)
- Script clicks Attach on CL section, uploads CL PDF
- Browser pauses with form ready for review

Verify: scroll the form, confirm both attachments are the tailored ones (not Simplify defaults). If a selector fails, capture the error and iterate before committing.

- [ ] **Step 5: Commit**

```bash
cd ~/code/the-dossier && git add pipeline/apply_flow_poc.py && git commit -m "feat(apply-flow): add resume + cover letter override on greenhouse"
```

---

### Task 6: Write README

**Files:**
- Create: `~/code/the-dossier/pipeline/apply_flow_poc_README.md`

- [ ] **Step 1: Write the README**

```markdown
# Apply-Flow POC

Validates the Playwright-overrides-Simplify-autofill pattern on a single Greenhouse listing. Scope: prove the technical pattern. No batching, no LLM essay handling, no logging.

## One-time setup

```bash
cd ~/code/the-dossier
pipeline/.venv/bin/python3 pipeline/apply_flow_poc.py bootstrap
```

In the Chrome window that opens:
1. Install Simplify Copilot extension (Web Store page is opened for you)
2. Log in to https://simplify.jobs
3. Pin the extension
4. Close the browser

Profile is saved to `pipeline/.cache/chrome-profile/` (gitignored).

## Run the POC

Edit the top of `apply_flow_poc.py`:
- Set `COVER_LETTER_PATH` to your test CL PDF.

Then:
```bash
cd ~/code/the-dossier
pipeline/.venv/bin/python3 pipeline/apply_flow_poc.py
```

Expected:
- Chrome opens, navigates to LVT JD URL
- Simplify autofills standard fields (~5 sec)
- Script swaps in tailored resume PDF
- Script clicks "Attach" on CL picker, uploads CL PDF
- Browser pauses for review

You manually click submit (or close browser to abandon).

## Success criteria

- Resume in form is the tailored PDF (filename starts with `Jared-Hawkins-LVT-...`)
- Cover letter in form is the user-provided CL PDF
- No Playwright errors in terminal
- Form is in submit-ready state

## Failure modes

- Simplify popup didn't fire → bump `SIMPLIFY_AUTOFILL_WAIT_SEC` from 5 to 10
- Resume override didn't take → Simplify may have race-overwritten; bump the post-override settle from 2_000ms
- CL Attach button not found → Greenhouse CL picker selectors may have changed; inspect form HTML and update selector strings in `override_cover_letter`
```

- [ ] **Step 2: Commit**

```bash
cd ~/code/the-dossier && git add pipeline/apply_flow_poc_README.md && git commit -m "docs(apply-flow): add POC README"
```

---

### Task 7: USER VERIFICATION — confirm POC success criteria

- [ ] **Step 1: User runs the POC end-to-end at least once** (after Tasks 1-6 complete and Task 3 done)

- [ ] **Step 2: User confirms each success criterion**

- ☐ Resume in form is the tailored PDF (filename `Jared-Hawkins-LVT-...`)
- ☐ Cover letter in form is the user-provided CL PDF
- ☐ No Simplify race-overwrite observed (resume stays put after the 2-sec settle)
- ☐ Browser is in submit-ready state
- ☐ User does NOT submit unless they want to actually apply

- [ ] **Step 3: User reports outcome**

- ✅ All criteria met → POC succeeds. Greenlight for spike (next plan: extend to Lever + Ashby + LLM essay handling).
- ❌ Some criteria failed → capture which selectors broke or what behavior was unexpected. Re-plan as needed.

---

## Open Questions

All resolved 2026-04-30 — see Pre-flight section at top of plan.
