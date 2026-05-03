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


# ---------------------------------------------------------------------------
# Queue + summary helpers (pure; ledger-aware)
# ---------------------------------------------------------------------------

import argparse
import json
import os
import sys
import time
from datetime import date
from typing import Optional


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
        email = page.locator('input[type="email"], input[name*="email" i]')
        try:
            value = email.input_value(timeout=200)
            if value:
                return
        except Exception:
            pass
        # Autofill button still showing?
        autofill_btn = page.locator('button:has-text("Autofill")')
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
