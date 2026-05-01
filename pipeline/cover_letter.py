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
import os
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


# ---------------------------------------------------------------------------
# Prompt building + Anthropic call
# ---------------------------------------------------------------------------

CL_SYSTEM_TEMPLATE = """\
You are a writing assistant helping Jared Hawkins draft cover letters for product/operations roles.

About Jared (use this as background; do not restate it verbatim):
{bio_summary}

Rules for every cover letter you produce:
- Voice: confident, direct, conversational. One person talking to one other person.
- No banned words: delve, leverage (verb), robust, streamline, cutting-edge, synergy, multifaceted, comprehensive, meticulous, pivotal, testament, utilize, facilitate, "it is worth noting", "it is important to note".
- No em-dashes (—). Use periods, commas, or restructure.
- Active voice. Short sentences. Break anything over 25 words.
- Three or four paragraphs total. Around 250 words.
- Open with a specific reason this role/company stands out (not "I am writing to apply for").
- One paragraph on the most relevant experience, with a concrete result.
- Close with a clear next step (interview, conversation).
- Do not invent companies or projects Jared has not done.
- Output plain text only. Do not use HTML tags or HTML entities (the rendering layer escapes everything; HTML in your output will appear as literal escaped text in the PDF).
- Output the letter body only. No subject line, no "Dear Hiring Manager" prelude (the template adds those). Start with the first paragraph of prose.
"""


DEFAULT_CL_MODEL = "claude-sonnet-4-6"  # Override via PIPELINE_CL_MODEL env var if Anthropic changes the alias.


def build_cl_prompt(source: dict, archetype_template: dict,
                    company: str, role: str, jd_text: str) -> dict:
    """Build the {system, user} prompt pair for the Anthropic call.

    The system block is intentionally invariant across cards in a batch
    so prompt caching can kick in. The user block carries everything that
    varies per-card (company, role, JD, archetype headline).
    """
    summary_key = archetype_template.get("summary_variant", "product_management")
    bio_summary = source.get("summary_variants", {}).get(summary_key, "")
    headline = archetype_template.get("headline", "")

    system = CL_SYSTEM_TEMPLATE.format(bio_summary=bio_summary)

    user = (
        f"Draft a cover letter for this role.\n\n"
        f"Company: {company}\n"
        f"Role: {role}\n"
        f"Positioning headline (use as a north star, do not quote): {headline}\n\n"
        f"Job description:\n{jd_text}\n"
    )

    return {"system": system, "user": user}


def generate_cl_text(prompt: dict, client, model: str | None = None,
                     max_tokens: int = 1200) -> str:
    """Call the Anthropic Messages API with prompt caching on the system block.

    `client` is anything with a `messages_create(**kwargs)` callable; the real
    Anthropic SDK uses `client.messages.create(...)` so we wrap it in
    `_make_anthropic_adapter` for prod use. Tests pass a fake.

    Model selection precedence: explicit arg > PIPELINE_CL_MODEL env var > DEFAULT_CL_MODEL.
    """
    chosen = model or os.environ.get("PIPELINE_CL_MODEL") or DEFAULT_CL_MODEL
    # NOTE: Anthropic prompt caching requires the system block to be ≥1024 tokens
    # for Sonnet to be cache-eligible. The current CL_SYSTEM_TEMPLATE renders to
    # ~400-500 tokens including bio summary, so caching is silently ignored —
    # cache_control here is forward-looking. Per-card cost is ~$0.05 (no cache hit)
    # vs. ~$0.01 (cache hit). For a 38-card batch that's ~$1.50 wasted per run.
    # If batch costs become painful, expand the system block (more bio context,
    # more concrete writing examples) to cross the threshold.
    response = client.messages_create(
        model=chosen,
        max_tokens=max_tokens,
        system=[
            {
                "type": "text",
                "text": prompt["system"],
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": prompt["user"]}],
    )
    # Anthropic SDK returns content as a list of blocks; first block is text.
    return response.content[0].text


def _make_anthropic_adapter():
    """Wrap the real Anthropic SDK so tests can inject a duck-typed fake.

    Raises RuntimeError if the anthropic package isn't installed. Callers
    (CLI entry points) should catch and convert to a user-facing exit.
    """
    try:
        from anthropic import Anthropic
    except ImportError as e:
        raise RuntimeError(
            "anthropic SDK required: pip install anthropic "
            "(set ANTHROPIC_API_KEY in env)"
        ) from e

    real = Anthropic()

    class Adapter:
        def messages_create(self, **kwargs):
            return real.messages.create(**kwargs)

    return Adapter()
