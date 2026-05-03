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
