# Apply-Flow POC

Validates the Playwright-overrides-Simplify-autofill pattern on a single Greenhouse listing. Scope: prove the technical pattern. No batching, no LLM essay handling, no logging.

## Prerequisites

- Google Chrome stable installed at `/Applications/Google Chrome.app/`
- Simplify Copilot extension installed in your regular Chrome (the script side-loads from your existing install at `~/Library/Application Support/Google/Chrome/Default/Extensions/pbanhockgagggenencehbnadejlgchfc/`)
- A Simplify account (you'll log in once during bootstrap)
- The pipeline venv at `~/code/the-dossier/pipeline/.venv/` (Playwright + Chromium installed)

## One-time setup

```bash
cd ~/code/the-dossier && pipeline/.venv/bin/python3 ~/code/the-dossier-poc/pipeline/apply_flow_poc.py bootstrap
```

A new Chrome window opens with Simplify side-loaded:
1. Verify the Simplify icon is in the toolbar (pin via the puzzle icon if not visible)
2. The page lands on https://simplify.jobs — log in to your account
3. Close the Chrome window when done. Login cookies save to the isolated profile.

Profile is saved to `pipeline/.cache/chrome-profile/` (gitignored).

**Note:** Google OAuth is blocked in Playwright-controlled browsers. If your Simplify account uses Google sign-in, the side-loaded extension may still surface your saved profile data without an explicit Google login. If not, you may need to use email/password auth, or fall back to running Playwright against your default Chrome profile (requires closing all Chrome windows first).

## Run the POC

```bash
cd ~/code/the-dossier && pipeline/.venv/bin/python3 ~/code/the-dossier-poc/pipeline/apply_flow_poc.py
```

Expected:
- Chrome opens with Simplify side-loaded, navigates to LVT JD URL
- Script waits ~5 sec (Simplify on Greenhouse needs an explicit click to autofill — POC does not trigger this)
- Script uploads the tailored resume PDF directly to the resume file input
- Script uploads the CL PDF directly to the cover letter file input (no UI click — bypasses the OS file picker)
- Browser pauses for review

You manually click submit (or close browser to abandon).

## Success criteria

- Resume in form is the tailored PDF (filename starts with `Jared-Hawkins-LVT-...`)
- Cover letter in form is the user-provided CL PDF
- No Playwright errors in terminal
- Form is in submit-ready state

## Failure modes

- Simplify popup didn't fire → bump `SIMPLIFY_AUTOFILL_WAIT_SEC` from 5 to 10
- Resume override didn't take → Simplify may have race-overwritten; bump the post-override settle from 2_000ms in `override_resume()`
- CL Attach button not found → Greenhouse CL picker selectors may have changed; inspect the form's HTML and update locator strings in `override_cover_letter()`
- Resume file input not found → check the form for the actual `id` / `name` attribute and update the selector in `override_resume()`

## Config (top of `apply_flow_poc.py`)

- `JD_URL` — currently hardcoded to LVT Sr Director PM
- `RESUME_PATH` — pre-generated tailored resume PDF
- `COVER_LETTER_PATH` — test CL PDF (any PDF works for upload mechanism testing; POC doesn't submit)
- `SIMPLIFY_AUTOFILL_WAIT_SEC` — wait time after page load for Simplify to autofill standard fields
- `SIMPLIFY_EXTENSION_ID` — Chrome Web Store ID for Simplify (used to find the extension dir)
