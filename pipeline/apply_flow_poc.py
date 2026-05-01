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

# Side-load Simplify from user's regular Chrome install (Web Store install is blocked under Playwright control).
# Auto-detect latest version dir at runtime in _resolve_simplify_extension_path().
SIMPLIFY_EXTENSION_ID = "pbanhockgagggenencehbnadejlgchfc"
USER_CHROME_EXTENSIONS_DIR = Path.home() / "Library" / "Application Support" / "Google" / "Chrome" / "Default" / "Extensions"


def _resolve_simplify_extension_path() -> Path:
    """Find the latest installed Simplify extension version in user's Chrome profile."""
    ext_dir = USER_CHROME_EXTENSIONS_DIR / SIMPLIFY_EXTENSION_ID
    if not ext_dir.exists():
        sys.exit(
            f"[error] Simplify not installed in your regular Chrome.\n"
            f"  Expected: {ext_dir}\n"
            f"  Install Simplify in Chrome first: https://chromewebstore.google.com/detail/{SIMPLIFY_EXTENSION_ID}"
        )
    versions = sorted([d for d in ext_dir.iterdir() if d.is_dir()])
    if not versions:
        sys.exit(f"[error] No Simplify extension version dirs in {ext_dir}")
    return versions[-1]


def bootstrap():
    """One-time setup: launch Chrome with side-loaded Simplify so user can log in.

    Web Store install is blocked under Playwright control, so we side-load Simplify
    from the user's regular Chrome install via --load-extension. The user only
    needs to log in to simplify.jobs in this session; cookies persist in PROFILE_DIR.
    Run ONCE before run().
    """
    ext_path = _resolve_simplify_extension_path()
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[bootstrap] Profile dir:       {PROFILE_DIR}")
    print(f"[bootstrap] Simplify loaded from: {ext_path}")
    print("[bootstrap] In the browser that opens:")
    print("  1. Verify the Simplify icon is in the toolbar (pin it via the puzzle icon if not visible)")
    print("  2. The page opens to https://simplify.jobs — log in to your account")
    print("  3. Close the browser when done. Login cookies are saved.")
    print()

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
        page = ctx.new_page()
        page.goto("https://simplify.jobs")
        try:
            page.wait_for_event("close", timeout=0)
        except Exception:
            pass
        ctx.close()

    print(f"[bootstrap] Profile saved at {PROFILE_DIR}.")
    print(f"[bootstrap] Next: cd ~/code/the-dossier && pipeline/.venv/bin/python3 ~/code/the-dossier-poc/pipeline/apply_flow_poc.py")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "bootstrap":
        bootstrap()
    else:
        print("Usage:")
        print("  python apply_flow_poc.py bootstrap  # one-time profile setup")
        print("  python apply_flow_poc.py            # run the POC (after bootstrap)")
        sys.exit(1)
