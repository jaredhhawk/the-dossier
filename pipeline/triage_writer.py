"""Triage writer: manifest + scored JSON → daily triage markdown for the vault.

This module exposes pure functions only (no file I/O). The CLI wrapper that
reads files from disk and writes the output is added in Task 7.
"""
from __future__ import annotations

from pathlib import Path


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
            + "- URL unresolved (Adzuna redirect only) — run `/pipeline resolve-urls` first\n"
            + "- ~~[ ] apply~~ ~~[ ] skip~~\n"
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
        else "- CL preview: (no preview available)\n"
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
        + "- [ ] apply\n"
        + "- [ ] skip\n"
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


# ---------------------------------------------------------------------------
# File I/O wrapper, idempotency guard, and CLI (Task 7)
# ---------------------------------------------------------------------------
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
