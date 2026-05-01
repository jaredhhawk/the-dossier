#!/usr/bin/env python3
"""Cover letter generator for the job search pipeline.

Produces a tailored CL PDF per (company, role, JD) using:
- Bio data from data/resumes/source.json
- Archetype headline from config.yaml (mirrors resume routing)
- Claude API for the prose body (Anthropic SDK, prompt caching on the
  static bio block since it's identical across all cards in a batch)
- Shared Playwright HTML→PDF renderer

Output: pipeline/data/cover_letters/output/{Name}-{Company}-{Role}-{date}.pdf
"""
from __future__ import annotations

import html
import re
import sys
from datetime import date
from pathlib import Path


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PIPELINE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PIPELINE_DIR / "data" / "cover_letters" / "output"


# ---------------------------------------------------------------------------
# Output path
# ---------------------------------------------------------------------------

def _slug(s: str) -> str:
    """Filesafe slug: drop punctuation except spaces/hyphens, then hyphenate."""
    cleaned = re.sub(r"[^\w\s-]", "", s).strip()
    return re.sub(r"\s+", "-", cleaned)


def build_cl_output_path(company: str, role: str, full_name: str,
                         date_str: str | None = None) -> Path:
    """Mirror resume.build_output_path naming: {Name}-{Company}-{Role}-{date}.pdf"""
    d = date_str or date.today().isoformat()
    name = f"{_slug(full_name)}-{_slug(company)}-{_slug(role)}-{d}.pdf"
    return OUTPUT_DIR / name


def cl_artifact_exists(path: Path) -> bool:
    return path.exists() and path.stat().st_size > 0


# ---------------------------------------------------------------------------
# HTML template
# ---------------------------------------------------------------------------

CL_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<style>
@page {{ size: Letter; margin: 0; }}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
  font-family: Arial, Helvetica, sans-serif;
  font-size: 11pt;
  line-height: 1.45;
  color: #1a1a1a;
  padding: 0.6in 0.75in;
  max-width: 8.5in;
}}
.header {{ margin-bottom: 18pt; }}
.name {{ font-size: 16pt; font-weight: bold; margin-bottom: 3pt; }}
.contact {{ font-size: 10pt; color: #444; }}
.contact a {{ color: #444; text-decoration: none; }}
.date {{ margin-bottom: 12pt; font-size: 11pt; }}
.addressee {{ margin-bottom: 14pt; font-size: 11pt; }}
p {{ margin-bottom: 9pt; text-align: left; }}
</style>
</head>
<body>
<div class="header">
  <div class="name">{name}</div>
  <div class="contact">{contact}</div>
</div>
<div class="date">{date_human}</div>
<div class="addressee">{company} Hiring Team<br>Re: {role}</div>
{paragraphs}
</body>
</html>
"""


def _format_date_human(date_str: str) -> str:
    """2026-04-22 → April 22, 2026."""
    try:
        d = date.fromisoformat(date_str)
        return d.strftime("%B %-d, %Y")
    except ValueError:
        return date_str


def _prose_to_paragraphs(prose: str) -> str:
    """Split on blank lines, wrap each chunk in <p>, escape HTML angle brackets minimally."""
    chunks = [c.strip() for c in re.split(r"\n\s*\n", prose.strip()) if c.strip()]
    parts = []
    for c in chunks:
        # Preserve single newlines as <br> within a paragraph
        body = c.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        body = body.replace("\n", "<br>")
        parts.append(f"<p>{body}</p>")
    return "\n".join(parts)


def render_cl_html(prose: str, source: dict, company: str, role: str,
                   date_str: str) -> str:
    """Render the CL HTML doc combining bio header + prose body."""
    meta = source["meta"]
    contact_items = []
    if meta.get("location"):
        contact_items.append(meta["location"])
    if meta.get("phone"):
        contact_items.append(meta["phone"])
    if meta.get("email"):
        contact_items.append(
            f'<a href="mailto:{meta["email"]}">{meta["email"]}</a>'
        )
    if meta.get("linkedin"):
        contact_items.append(f'<a href="{meta["linkedin"]}">LinkedIn</a>')
    contact = " | ".join(contact_items)

    return CL_HTML_TEMPLATE.format(
        name=html.escape(meta["name"]),
        contact=contact,  # intentionally NOT escaped — contains <a href=...> tags
        date_human=_format_date_human(date_str),
        company=html.escape(company),
        role=html.escape(role),
        paragraphs=_prose_to_paragraphs(prose),
    )
