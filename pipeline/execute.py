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
