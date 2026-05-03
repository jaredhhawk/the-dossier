"""Slow e2e: fake Greenhouse via http.server + real Playwright.

Tests the APPLIED path: triage note points at fake_greenhouse_thanks.html,
which already contains the confirmation signal (h1 "Thank you for applying!").
detect_confirmation is patched to bypass the host-dispatch check (localhost
is not "greenhouse.io") and call greenhouse_confirmed directly, so the real
DOM poller runs and detects the signal. Result: Applied status, checkbox
flips to [x] applied, tracker row appended.

Marked @pytest.mark.slow — excluded from the default suite (-m "not slow").
"""
import http.server
import shutil
import socketserver
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
    socketserver.TCPServer.allow_reuse_address = True
    httpd = socketserver.TCPServer(("127.0.0.1", 0), handler)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield port
    finally:
        httpd.shutdown()


# Capture real sync_playwright BEFORE any monkeypatching in tests.
from playwright.sync_api import sync_playwright as _real_sync_playwright


@contextmanager
def _headless_playwright():
    """Context manager yielding a headless Playwright-like object.

    Replaces the persistent-context launch (which needs a Chrome profile +
    Simplify extension) with a plain headless Chromium context. The returned
    object mimics the `p` variable used in execute.main so that
    `p.chromium.launch_persistent_context(...)` succeeds.

    Uses the module-level _real_sync_playwright (captured before monkeypatch)
    to avoid infinite recursion when sync_playwright itself is patched.
    """
    with _real_sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context()

        class _FakeBrowserType:
            def launch_persistent_context(self, user_data_dir, **kwargs):
                return ctx

        class _FakePW:
            chromium = _FakeBrowserType()

        try:
            yield _FakePW()
        finally:
            try:
                ctx.close()
            except Exception:
                pass
            try:
                browser.close()
            except Exception:
                pass


@pytest.mark.slow
def test_execute_e2e_applied_path(tmp_path, monkeypatch):
    """Applied path: fake_greenhouse_thanks.html already shows confirmation signal.

    Flow:
    - http.server serves fixtures dir on ephemeral port
    - Triage note points at fake_greenhouse_thanks.html
      (has h1 "Thank you for applying!" + data-application-confirmation)
    - detect_confirmation is patched to use greenhouse_confirmed directly
      (bypasses host-dispatch; still runs real DOM polling)
    - _prompt_user always returns "p" (proceed/submitted)
    - Playwright navigates to page, confirmation detected -> Applied
    - Checkbox flips to [x] applied
    - Tracker row appended with Status=Applied
    """
    # 1. Build stub resume + CL PDFs (we test the override path, not real PDFs)
    resume_pdf = tmp_path / "resume.pdf"
    resume_pdf.write_bytes(b"%PDF-1.4 stub\n")
    cl_pdf = tmp_path / "cl.pdf"
    cl_pdf.write_bytes(b"%PDF-1.4 stub\n")
    cl_md = cl_pdf.with_suffix(".md")
    cl_md.write_text("Hello FakeCo, I am applying.")

    # 2. Copy tracker + ledger from fixtures
    tracker_path = tmp_path / "Tracker.md"
    shutil.copy(FIXTURES / "tracker_sample.md", tracker_path)
    ledger_path = tmp_path / "ledger.tsv"
    shutil.copy(FIXTURES / "ledger_sample.tsv", ledger_path)

    with _serve_fixtures() as port:
        # fake_greenhouse_thanks.html has h1 "Thank you for applying!" +
        # <div data-application-confirmation> — both are Greenhouse confirmation signals
        url = f"http://127.0.0.1:{port}/fake_greenhouse_thanks.html"

        # 3. Build triage note pointing at the thanks fixture
        triage_path = tmp_path / "Daily Triage 2026-05-02.md"
        triage_path.write_text(
            f"# Daily Triage 2026-05-02\n\n"
            f"## [A] FakeCo — X\n"
            f"- JD: {url}\n"
            f"- Resume: {resume_pdf}\n"
            f"- CL: {cl_pdf}\n"
            f"- [x] apply\n"
        )

        # 4. Patch PROFILE_DIR to a tmp dir that exists (bypasses the exists() guard)
        import pipeline.apply_flow_poc as poc_mod
        fake_profile_dir = tmp_path / "chrome-profile"
        fake_profile_dir.mkdir()
        monkeypatch.setattr(poc_mod, "PROFILE_DIR", fake_profile_dir)

        # 5. Patch _resolve_simplify_extension_path (safe fallback; not actually invoked
        #    in the patched Playwright path, but present in case the code path changes)
        monkeypatch.setattr(
            poc_mod,
            "_resolve_simplify_extension_path",
            lambda: fake_profile_dir,
        )

        # 6. Patch override_greenhouse_artifacts: the thanks page has no file inputs,
        #    so set_input_files would error. We record the paths it was called with.
        called_with: dict = {}

        def fake_override(page, resume_path, cl_path):
            called_with["resume"] = str(resume_path)
            called_with["cl"] = str(cl_path)

        monkeypatch.setattr(poc_mod, "override_greenhouse_artifacts", fake_override)

        # 7. Patch detect_confirmation to bypass the host-dispatch (localhost is not
        #    "greenhouse.io"). Call greenhouse_confirmed directly so the real DOM
        #    poller runs against our fake page and detects the signal.
        from pipeline import ats_signals
        monkeypatch.setattr(
            ats_signals,
            "detect_confirmation",
            lambda page, url, timeout_seconds=10: ats_signals.greenhouse_confirmed(
                page, timeout_seconds=timeout_seconds
            ),
        )

        # 8. Patch sync_playwright to launch headless Chromium (no profile/extension)
        import playwright.sync_api as _pw_sync_api
        monkeypatch.setattr(_pw_sync_api, "sync_playwright", _headless_playwright)

        # 9. Stub _prompt_user to always return "p" (proceed / submitted)
        from pipeline import execute as exec_mod
        monkeypatch.setattr(exec_mod, "_prompt_user", lambda *a, **kw: "p")

        # 10. Run main()
        rc = exec_mod.main([
            str(triage_path),
            "--simplify-wait", "0",
            "--tracker-path", str(tracker_path),
            "--ledger-path", str(ledger_path),
        ])
        assert rc == 0, "execute.main returned non-zero"

    # 11. Assert override was called with the correct artifact paths
    assert called_with.get("resume") == str(resume_pdf), (
        f"override not called with correct resume path. Got: {called_with}"
    )
    assert called_with.get("cl") == str(cl_pdf), (
        f"override not called with correct CL path. Got: {called_with}"
    )

    # 12. Assert checkbox flipped to [x] applied (confirmed path)
    text = triage_path.read_text()
    assert "[x] applied" in text, (
        f"Expected '[x] applied' in triage note after confirmed submission.\n"
        f"Actual content:\n{text}"
    )
    assert "[x] apply\n" not in text, (
        "Old '[x] apply' line still present — flip did not occur."
    )

    # 13. Assert tracker row appended with Applied status
    tracker_text = tracker_path.read_text()
    assert "| FakeCo |" in tracker_text, (
        f"Expected tracker row with FakeCo.\nTracker:\n{tracker_text}"
    )
    assert "Applied" in tracker_text, (
        f"Expected Applied status in tracker.\nTracker:\n{tracker_text}"
    )
