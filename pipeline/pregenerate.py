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


# ---------------------------------------------------------------------------
# IO + subprocess work (manually smoke-tested, not unit-tested)
# ---------------------------------------------------------------------------

def find_most_recent_scored() -> Path | None:
    """Newest YYYY-MM-DD.json in pipeline/data/scored/."""
    if not SCORED_DIR.exists():
        return None
    candidates = sorted(SCORED_DIR.glob("[0-9]*.json"))
    return candidates[-1] if candidates else None


def cache_jd_text(card: dict, slug: str) -> Path:
    """Write the card's JD description to a cache file. Returns the path."""
    JD_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = JD_CACHE_DIR / f"{slug}.txt"
    if not path.exists():
        path.write_text(card.get("description") or "")
    return path


def generate_resume_for_card(card: dict, date_str: str, full_name: str,
                             config: dict, source: dict, force: bool) -> Path:
    """Generate the tailored resume PDF for one card. Returns the output path.

    Raises on failure (caller catches and records in failures list).
    """
    # Local imports to keep module load fast and avoid cycles
    from pipeline.resume import (
        resolve_archetype, select_bullets, generate_html, build_output_path,
    )
    from pipeline.pdf_render import html_to_pdf
    from pipeline.resume import extract_jd_terms

    archetype_name = card.get("archetype") or "operations"
    template = resolve_archetype(config, archetype_name)
    jd_text = card.get("description") or ""

    out_path = build_output_path(
        archetype_name, company=card["company"], role=card["title"],
        ext="pdf", full_name=full_name, date_str=date_str,
    )
    if out_path.exists() and not force:
        return out_path

    experience = select_bullets(source, archetype_name, template, jd_text)
    jd_terms = extract_jd_terms(jd_text) if jd_text else None
    html = generate_html(source, experience, template, jd_terms)
    html_to_pdf(html, out_path)
    return out_path


def generate_cl_for_card(card: dict, date_str: str, full_name: str,
                         config: dict, source: dict, anthropic_client,
                         force: bool) -> Path:
    from pipeline.cover_letter import (
        build_cl_output_path, build_cl_prompt, generate_cl_text,
        render_cl_html, cl_artifact_exists,
    )
    from pipeline.pdf_render import html_to_pdf

    out_path = build_cl_output_path(
        company=card["company"], role=card["title"],
        full_name=full_name, date_str=date_str,
    )
    if cl_artifact_exists(out_path) and not force:
        return out_path

    archetype_name = card.get("archetype") or "operations"
    archetype_template = config["archetypes"][archetype_name]["template"]
    jd_text = card.get("description") or ""

    prompt = build_cl_prompt(source, archetype_template,
                             card["company"], card["title"], jd_text)
    prose = generate_cl_text(prompt, anthropic_client)
    html = render_cl_html(prose, source, card["company"], card["title"], date_str)
    html_to_pdf(html, out_path)
    return out_path


def process_card(card: dict, date_str: str, full_name: str,
                 config: dict, source: dict, anthropic_client,
                 force: bool) -> tuple[str, dict]:
    """Process one card end-to-end. Returns (status, payload).

    status ∈ {"generated", "cached", "failed"}.
    payload is the manifest entry for this card.
    """
    slug = build_card_slug(card, date_str)
    apply_url = card.get("resolved_url") or card.get("url")
    base = {
        "company": card["company"],
        "role": card["title"],
        "url": apply_url,
        "grade": card.get("grade"),
        "archetype": card.get("archetype"),
    }
    try:
        jd_path = cache_jd_text(card, slug)
        # Track cache state BEFORE generation so we can classify the result
        from pipeline.cover_letter import (
            build_cl_output_path, cl_artifact_exists,
        )
        from pipeline.resume import build_output_path
        archetype_name = card.get("archetype") or "operations"
        resume_path_expected = build_output_path(
            archetype_name, company=card["company"], role=card["title"],
            ext="pdf", full_name=full_name, date_str=date_str,
        )
        cl_path_expected = build_cl_output_path(
            company=card["company"], role=card["title"],
            full_name=full_name, date_str=date_str,
        )
        was_cached = (
            resume_path_expected.exists()
            and cl_artifact_exists(cl_path_expected)
            and jd_path.exists()
        )

        resume_path = generate_resume_for_card(
            card, date_str, full_name, config, source, force,
        )
        cl_path = generate_cl_for_card(
            card, date_str, full_name, config, source, anthropic_client, force,
        )

        payload = {
            **base,
            "resume_pdf": str(resume_path),
            "cl_pdf": str(cl_path),
            "jd_cache": str(jd_path),
        }
        return ("cached" if (was_cached and not force) else "generated", payload)
    except (Exception, SystemExit) as e:
        # SystemExit caught explicitly: resume.py:resolve_archetype calls sys.exit
        # on unknown archetype, and we don't want one bad card to kill the batch.
        return ("failed", {**base, "reason": f"{type(e).__name__}: {e}"})


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scored-file", default=None,
                        help="Path to a scored JSON. Defaults to most recent in data/scored/.")
    parser.add_argument("--grades", default="A,B",
                        help="Comma-separated grades to include (default: A,B).")
    parser.add_argument("--force", action="store_true",
                        help="Regenerate artifacts even if they exist.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print cards that would be processed and exit.")
    parser.add_argument("--limit", type=int, default=None,
                        help="Cap number of cards processed (smoke testing).")
    args = parser.parse_args()

    # Resolve scored file
    scored_path = Path(args.scored_file) if args.scored_file else find_most_recent_scored()
    if not scored_path or not scored_path.exists():
        print(f"[pregenerate] no scored JSON found", file=sys.stderr)
        return 2

    date_str = derive_date_from_scored_path(scored_path)
    grades = tuple(g.strip().upper() for g in args.grades.split(",") if g.strip())

    with open(scored_path) as f:
        cards = json.load(f)

    filtered = filter_cards(cards, grades=grades)
    if args.limit:
        filtered = filtered[: args.limit]

    print(f"[pregenerate] scored={scored_path.name} date={date_str}")
    print(f"[pregenerate] grades={grades} candidates={len(filtered)}")

    if args.dry_run:
        for c in filtered:
            print(f"  - {c['grade']} | {c['company']} | {c['title']}")
        return 0

    # Lazy-load shared resources (config, source, anthropic) only when really running
    import yaml
    with open(PIPELINE_DIR / "config.yaml") as f:
        config = yaml.safe_load(f)
    with open(PIPELINE_DIR / "data" / "resumes" / "source.json") as f:
        source = json.load(f)
    full_name = config.get("form_answers", {}).get("full_name") or source["meta"]["name"]

    from pipeline.cover_letter import _make_anthropic_adapter
    anthropic_client = _make_anthropic_adapter()

    generated, cached, failures = [], [], []
    artifacts_by_url: dict[str, dict] = {}

    for i, card in enumerate(filtered, 1):
        label = f"{card['grade']} | {card['company']} | {card['title']}"
        print(f"[pregenerate] ({i}/{len(filtered)}) {label}")
        status, payload = process_card(
            card, date_str, full_name, config, source, anthropic_client,
            args.force,
        )
        if status == "generated":
            generated.append(payload)
            print(f"  → generated")
        elif status == "cached":
            cached.append(payload)
            print(f"  → cached")
        else:
            failures.append(payload)
            print(f"  → failed: {payload.get('reason')}")
            continue

        url_key = payload["url"]
        artifacts_by_url[url_key] = {
            "resume_pdf": payload["resume_pdf"],
            "cl_pdf": payload["cl_pdf"],
            "jd_cache": payload["jd_cache"],
        }

    # Write manifest
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    manifest_path = MANIFEST_DIR / f"{date_str}-manifest.json"
    manifest = build_manifest(
        date_str=date_str, scored_file=str(scored_path),
        generated=generated, cached=cached, failures=failures,
    )
    manifest_path.write_text(json.dumps(manifest, indent=2))
    print(f"[pregenerate] manifest: {manifest_path}")

    # Update scored JSON in place with artifact paths
    if artifacts_by_url:
        updated = update_scored_with_artifacts(cards, artifacts_by_url)
        scored_path.write_text(json.dumps(updated, indent=2))
        print(f"[pregenerate] scored JSON updated with artifact paths")

    print(f"[pregenerate] done: generated={len(generated)} cached={len(cached)} failed={len(failures)}")

    # Exit 0 if at least one succeeded OR nothing to do; 1 only if all attempts failed
    if filtered and not generated and not cached:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
