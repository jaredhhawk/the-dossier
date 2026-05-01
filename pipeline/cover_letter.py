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

    TODO (post-Plan 1): swap for `_make_claude_cli_adapter` that shells out to
    `claude --print --append-system-prompt "..."` so generation bills against
    the user's Claude Max subscription instead of the API. The duck-typed
    `messages_create` interface in `generate_cl_text` was deliberately designed
    for this swap. Estimated effort ~30 min. Tradeoffs: ~2-5s subprocess
    overhead per call (vs. ~1s API), no prompt-cache observability, harder to
    mock in tests (subprocess.run instead of duck-typed client), Max rate
    limits apply (generous but exist for 38-card batch runs). Revisit after
    Task 8 ships and we see real batch cost behavior.
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


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _load_source_and_config():
    """Mirror resume.py's loading."""
    import json
    import yaml
    pipeline_dir = Path(__file__).resolve().parent
    with open(pipeline_dir / "data" / "resumes" / "source.json") as f:
        source = json.load(f)
    with open(pipeline_dir / "config.yaml") as f:
        config = yaml.safe_load(f)
    return source, config


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate a tailored cover-letter PDF for one role."
    )
    parser.add_argument("--archetype", required=True,
                        help="Archetype name (matches config.yaml.archetypes keys)")
    parser.add_argument("--company", required=True)
    parser.add_argument("--role", required=True)
    parser.add_argument("--jd", default=None,
                        help="Path to job description text file. Required unless --text-file is supplied.")
    parser.add_argument("--text-file", default=None,
                        help="Skip LLM. Use this hand-written prose file as the CL body.")
    parser.add_argument("--date", default=None,
                        help="Override the date used in the output filename (YYYY-MM-DD).")
    parser.add_argument("--force", action="store_true",
                        help="Regenerate even if PDF already exists.")
    parser.add_argument("--markdown-only", action="store_true",
                        help="Write .md instead of running PDF render. For inspection.")
    args = parser.parse_args()

    if not args.jd and not args.text_file:
        parser.error("must supply either --jd or --text-file")

    source, config = _load_source_and_config()
    archetypes = config.get("archetypes", {})
    if args.archetype not in archetypes:
        sys.exit(f"Unknown archetype '{args.archetype}'")
    archetype_template = archetypes[args.archetype]["template"]

    full_name = config.get("form_answers", {}).get("full_name") or source["meta"]["name"]
    out_path = build_cl_output_path(args.company, args.role, full_name, args.date)

    if cl_artifact_exists(out_path) and not args.force:
        print(f"[cover-letter] cached: {out_path}")
        return

    # Source the prose
    if args.text_file:
        with open(args.text_file) as f:
            prose = f.read()
    else:
        with open(args.jd) as f:
            jd_text = f.read()
        prompt = build_cl_prompt(source, archetype_template,
                                 args.company, args.role, jd_text)
        client = _make_anthropic_adapter()
        prose = generate_cl_text(prompt, client)

    if args.markdown_only:
        md_path = out_path.with_suffix(".md")
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(prose)
        print(f"[cover-letter] markdown: {md_path}")
        return

    html = render_cl_html(prose, source, args.company, args.role,
                          args.date or date.today().isoformat())
    from pipeline.pdf_render import html_to_pdf
    html_to_pdf(html, out_path)
    print(f"[cover-letter] generated: {out_path}")


if __name__ == "__main__":
    main()
