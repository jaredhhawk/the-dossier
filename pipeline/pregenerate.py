#!/usr/bin/env python3
"""Pre-generate tailored resume + CL PDFs for every Grade A/B card on a scored JSON.

Designed to run unattended (e.g., overnight cron). Idempotent: skips any card
whose resume PDF, CL PDF, and JD cache file all exist. One card's failure does
not stop the batch.

Output:
- Resume PDFs (via resume.py functions): pipeline/data/resumes/output/{Name}-{Co}-{Role}-{date}.pdf
- CL PDFs (via cover_letter.py): pipeline/data/cover_letters/output/{Name}-{Co}-{Role}-{date}.pdf
- JD cache: pipeline/data/jd_cache/{slug}.txt
- Manifest: pipeline/data/pregenerated/{date}-manifest.json  <- Plan 2's read interface

Usage (run from ~/code/the-dossier-poc using the shared venv at ~/code/the-dossier/pipeline/.venv):
    python3 -m pipeline.pregenerate                      # Most recent scored JSON, A+B grades
    python3 -m pipeline.pregenerate --scored-file FILE   # Specific file
    python3 -m pipeline.pregenerate --grades A           # Filter to A only
    python3 -m pipeline.pregenerate --force              # Regenerate even if cached
    python3 -m pipeline.pregenerate --dry-run            # List cards that would be processed
    python3 -m pipeline.pregenerate --limit 3            # Cap card count (smoke testing)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PIPELINE_DIR = Path(__file__).resolve().parent
SCORED_DIR = PIPELINE_DIR / "data" / "scored"
JD_CACHE_DIR = PIPELINE_DIR / "data" / "jd_cache"
MANIFEST_DIR = PIPELINE_DIR / "data" / "pregenerated"

DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})\.json$")


# ---------------------------------------------------------------------------
# Pure functions (unit-tested)
# ---------------------------------------------------------------------------

def filter_cards(cards: list[dict], grades: tuple[str, ...]) -> list[dict]:
    """Keep cards that are (a) in `grades`, (b) status == "new", (c) have a usable apply URL.

    "Usable" = resolved_status starts with "ok:" (URL resolver succeeded), OR
    resolved_status absent and the original `url` is a known direct ATS link.
    For the sample data we only require status==new and grade match — the URL
    check is enforced as: card has either resolved_url or url field truthy.
    """
    keep = []
    for c in cards:
        if c.get("grade") not in grades:
            continue
        if c.get("status") != "new":
            continue
        # Accept resolved or direct ATS URL
        rs = c.get("resolved_status", "")
        has_resolved = isinstance(rs, str) and rs.startswith("ok:")
        if not has_resolved and not c.get("url"):
            continue
        keep.append(c)
    return keep


def derive_date_from_scored_path(path: Path) -> str:
    """Extract YYYY-MM-DD from a scored JSON filename like `2026-04-22.json`."""
    m = DATE_RE.search(path.name)
    if not m:
        raise ValueError(f"Filename does not match YYYY-MM-DD.json: {path.name}")
    return m.group(1)


def _slug(s: str) -> str:
    cleaned = re.sub(r"[^\w\s-]", "", s).strip()
    return re.sub(r"\s+", "-", cleaned)


def build_card_slug(card: dict, date_str: str) -> str:
    """Deterministic slug for JD cache filename. Uses company + title + date.

    URL is hashed in only if title+company collide (rare). For now, simple form.
    """
    return f"{_slug(card['company'])}-{_slug(card['title'])}-{date_str}"


def build_manifest(date_str: str, scored_file: str,
                   generated: list[dict], cached: list[dict],
                   failures: list[dict]) -> dict:
    """Assemble the manifest object that Plan 2 will read."""
    return {
        "date": date_str,
        "scored_file": scored_file,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "counts": {
            "generated": len(generated),
            "cached": len(cached),
            "failures": len(failures),
        },
        "generated": generated,
        "cached": cached,
        "failures": failures,
    }


def update_scored_with_artifacts(cards: list[dict],
                                 artifacts_by_url: dict[str, dict]) -> list[dict]:
    """Return a new list of cards where matching ones have an `artifacts` field added.

    Match key is the canonical url (prefer resolved_url, fall back to url).
    Existing fields are preserved.
    """
    out = []
    for c in cards:
        key = c.get("resolved_url") or c.get("url")
        if key in artifacts_by_url:
            new_card = dict(c)
            new_card["artifacts"] = artifacts_by_url[key]
            out.append(new_card)
        else:
            out.append(c)
    return out
