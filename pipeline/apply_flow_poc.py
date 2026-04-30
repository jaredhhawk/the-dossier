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
