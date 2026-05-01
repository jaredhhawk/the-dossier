#!/usr/bin/env python3
"""Resume generation system for the job search pipeline.

Generates tailored resumes by selecting and reordering bullets from a structured
source file based on archetype templates. Outputs markdown, HTML, and ATS-friendly PDF.

Usage:
    python3 resume.py --archetype product_management
    python3 resume.py --archetype operations --company Acme --role "Program Manager"
    python3 resume.py --archetype ai_technical --jd path/to/jd.txt
    python3 resume.py --archetype product_management --markdown-only
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

from pipeline.pdf_render import html_to_pdf

try:
    import yaml
except ImportError:
    sys.exit("pyyaml required: pip install pyyaml")


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PIPELINE_DIR = Path(__file__).resolve().parent
DATA_DIR = PIPELINE_DIR / "data"
SOURCE_PATH = DATA_DIR / "resumes" / "source.json"
CONFIG_PATH = PIPELINE_DIR / "config.yaml"
OUTPUT_DIR = DATA_DIR / "resumes" / "output"


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_source() -> dict:
    """Load structured resume source JSON."""
    with open(SOURCE_PATH, encoding="utf-8") as f:
        return json.load(f)


def load_config() -> dict:
    """Load pipeline config YAML."""
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_jd(path: str) -> str:
    """Load job description text from a file."""
    with open(path, encoding="utf-8") as f:
        return f.read()


# ---------------------------------------------------------------------------
# Archetype resolution
# ---------------------------------------------------------------------------

def resolve_archetype(config: dict, archetype_name: str) -> dict:
    """Look up archetype config and validate it has a template."""
    archetypes = config.get("archetypes", {})
    if archetype_name not in archetypes:
        valid = ", ".join(archetypes.keys())
        sys.exit(f"Unknown archetype '{archetype_name}'. Valid: {valid}")

    archetype = archetypes[archetype_name]
    if "template" not in archetype:
        sys.exit(f"Archetype '{archetype_name}' has no template configuration.")

    return archetype["template"]


# ---------------------------------------------------------------------------
# Bullet scoring and selection
# ---------------------------------------------------------------------------

def score_bullet(bullet: dict, archetype_name: str, template: dict,
                 jd_terms: set[str] | None = None) -> float:
    """Score a single bullet for an archetype.

    Scoring factors:
    - Domain membership: bullet lists this archetype in its domains (+2.0)
    - Tag priority match: bonus for each tag matching the archetype's priority list,
      weighted higher for tags earlier in the list (+0.0 to +1.0 per match)
    - JD keyword overlap: bonus for matching JD terms (+0.3 per match, max +1.5)
    - Metric presence: small bonus for bullets with quantified results (+0.5)
    """
    score = 0.0

    # Domain membership
    if archetype_name in bullet.get("domains", []):
        score += 2.0

    # Tag priority matching
    tag_priority = template.get("tag_priority", [])
    bullet_tags = set(bullet.get("tags", []))
    for i, priority_tag in enumerate(tag_priority):
        if priority_tag in bullet_tags:
            # Earlier in priority list = higher bonus (1.0 down to 0.1)
            weight = max(0.1, 1.0 - (i * 0.09))
            score += weight

    # JD keyword overlap
    if jd_terms:
        text_lower = bullet.get("text", "").lower()
        tags_lower = {t.lower() for t in bullet.get("tags", [])}
        matches = 0
        for term in jd_terms:
            if term in text_lower or term in tags_lower:
                matches += 1
        score += min(1.5, matches * 0.3)

    # Metric bonus
    if bullet.get("metric"):
        score += 0.5

    return score


def select_bullets(source: dict, archetype_name: str, template: dict,
                   jd_text: str | None = None) -> list[dict]:
    """Score all bullets and select the top N, grouped by role.

    Returns a list of experience entries with filtered bullets.
    """
    max_bullets = template.get("max_bullets", 14)
    jd_terms = extract_jd_terms(jd_text) if jd_text else None

    # Score every bullet across all roles
    scored: list[tuple[float, str, int, dict]] = []
    for role in source["experience"]:
        for i, bullet in enumerate(role["bullets"]):
            s = score_bullet(bullet, archetype_name, template, jd_terms)
            scored.append((s, role["company"], i, bullet))

    # Sort by score descending, take top N
    scored.sort(key=lambda x: x[0], reverse=True)
    selected_ids = {item[3]["id"] for item in scored[:max_bullets]}

    # Rebuild experience structure preserving role order, filtering bullets
    result = []
    for role in source["experience"]:
        filtered = [b for b in role["bullets"] if b["id"] in selected_ids]
        if filtered:
            # Sort bullets within each role by their score (highest first)
            role_scores = {
                b["id"]: score_bullet(b, archetype_name, template, jd_terms)
                for b in filtered
            }
            filtered.sort(key=lambda b: role_scores[b["id"]], reverse=True)
            result.append({
                "company": role["company"],
                "title": role["title"],
                "dates": role["dates"],
                "location": role["location"],
                "bullets": filtered,
            })

    return result


# ---------------------------------------------------------------------------
# JD keyword extraction
# ---------------------------------------------------------------------------

def extract_jd_terms(jd_text: str) -> set[str]:
    """Extract meaningful terms from a job description for scoring.

    Simple approach: split into words and bigrams, filter stop words,
    normalize to lowercase.
    """
    stop_words = {
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
        "being", "have", "has", "had", "do", "does", "did", "will", "would",
        "could", "should", "may", "might", "shall", "can", "need", "must",
        "it", "its", "this", "that", "these", "those", "we", "you", "they",
        "our", "your", "their", "as", "if", "not", "no", "all", "any", "each",
        "about", "up", "out", "so", "than", "too", "very", "just", "also",
        "into", "over", "after", "before", "between", "through", "during",
        "above", "below", "such", "both", "own", "same", "other", "which",
        "who", "whom", "what", "when", "where", "how", "why", "more", "most",
        "some", "many", "much", "well", "back", "even", "still", "new",
        "able", "work", "role", "team", "experience", "years", "including",
        "strong", "working", "across", "ensure", "within",
    }

    text = jd_text.lower()
    # Remove punctuation except hyphens (preserve compound terms)
    text = re.sub(r"[^\w\s-]", " ", text)
    words = text.split()
    words = [w for w in words if w not in stop_words and len(w) > 2]

    terms = set(words)

    # Add bigrams for compound terms
    for i in range(len(words) - 1):
        bigram = f"{words[i]} {words[i+1]}"
        terms.add(bigram)

    return terms


# ---------------------------------------------------------------------------
# Keyword reformulation (synonym-based)
# ---------------------------------------------------------------------------

def reformulate_bullet(text: str, jd_terms: set[str] | None,
                       synonyms: dict[str, list[str]]) -> str:
    """Swap bullet wording to echo JD terminology using the synonym map.

    Only activates when a JD is provided. Finds terms in the bullet that have
    JD-matching synonyms and swaps to the JD's preferred phrasing.
    """
    if not jd_terms or not synonyms:
        return text

    result = text
    for source_term, alternatives in synonyms.items():
        # Check if any alternative appears in the JD
        jd_match = None
        for alt in alternatives:
            if alt.lower() in jd_terms:
                jd_match = alt
                break

        if jd_match and source_term.lower() in result.lower():
            # Replace source term with JD's preferred phrasing (case-preserving)
            pattern = re.compile(re.escape(source_term), re.IGNORECASE)
            result = pattern.sub(jd_match, result, count=1)

    return result


# ---------------------------------------------------------------------------
# Markdown generation
# ---------------------------------------------------------------------------

def generate_markdown(source: dict, experience: list[dict],
                      template: dict, jd_terms: set[str] | None = None) -> str:
    """Generate a clean markdown resume."""
    meta = source["meta"]
    synonyms = source.get("synonyms", {})
    summary_key = template.get("summary_variant", "product_management")
    summary = source["summary_variants"].get(summary_key, "")
    headline = template.get("headline", "")

    lines = []

    # Header
    lines.append(f"# {meta['name']}")
    contact_parts = []
    if meta.get("location"):
        contact_parts.append(meta["location"])
    if meta.get("phone"):
        contact_parts.append(meta["phone"])
    if meta.get("email"):
        contact_parts.append(meta["email"])
    if meta.get("linkedin"):
        contact_parts.append(f"[LinkedIn]({meta['linkedin']})")
    lines.append(" | ".join(contact_parts))
    lines.append("")

    # Headline
    if headline:
        lines.append(f"**{headline}**")
        lines.append("")

    # Summary
    if summary:
        lines.append(summary)
        lines.append("")

    # Experience
    lines.append("## Experience")
    lines.append("")

    for role in experience:
        lines.append(f"### {role['title']}")
        lines.append(f"*{role['company']} | {role['location']} | {role['dates']}*")
        lines.append("")
        for bullet in role["bullets"]:
            text = reformulate_bullet(bullet["text"], jd_terms, synonyms)
            lines.append(f"- {text}")
        lines.append("")

    # Education
    lines.append("## Education")
    lines.append("")
    for edu in source.get("education", []):
        lines.append(f"**{edu['degree']}** -- {edu['school']}")
    lines.append("")

    # Skills (filtered by archetype emphasis)
    skills_emphasis = template.get("skills_emphasis", [])
    all_categories = source.get("skills", {}).get("categories", [])

    if skills_emphasis:
        # Order categories by emphasis list, then append any remaining
        ordered = []
        for name in skills_emphasis:
            for cat in all_categories:
                if cat["name"] == name:
                    ordered.append(cat)
                    break
        remaining = [c for c in all_categories if c not in ordered]
        categories = ordered + remaining
    else:
        categories = all_categories

    lines.append("## Technical Skills")
    lines.append("")
    for cat in categories:
        items = ", ".join(cat["items"])
        lines.append(f"**{cat['name']}:** {items}")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# HTML template
# ---------------------------------------------------------------------------

HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<style>
@page {{
  size: Letter;
  margin: 0;
}}
* {{
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}}
body {{
  font-family: Arial, Helvetica, sans-serif;
  font-size: 10pt;
  line-height: 1.3;
  color: #1a1a1a;
  padding: 0.35in 0.55in 0.3in 0.55in;
  max-width: 8.5in;
}}
h1 {{
  font-size: 18pt;
  font-weight: bold;
  margin-bottom: 2pt;
}}
.contact {{
  font-size: 10pt;
  color: #333;
  margin-bottom: 6pt;
}}
.contact a {{
  color: #333;
  text-decoration: none;
}}
.headline {{
  font-size: 11pt;
  font-weight: bold;
  color: #2a2a2a;
  margin-bottom: 6pt;
}}
.summary {{
  font-size: 9.5pt;
  color: #333;
  margin-bottom: 8pt;
  line-height: 1.35;
}}
h2 {{
  font-size: 11pt;
  font-weight: bold;
  border-bottom: 1px solid #999;
  padding-bottom: 1pt;
  margin-top: 8pt;
  margin-bottom: 4pt;
  text-transform: uppercase;
  letter-spacing: 0.5pt;
}}
.role-header {{
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 1pt;
}}
.role-title {{
  font-size: 10.5pt;
  font-weight: bold;
}}
.role-dates {{
  font-size: 10pt;
  color: #555;
  white-space: nowrap;
}}
.role-company {{
  font-size: 9.5pt;
  color: #555;
  font-style: italic;
  margin-bottom: 2pt;
}}
ul {{
  list-style-type: disc;
  padding-left: 16pt;
  margin-bottom: 4pt;
}}
li {{
  margin-bottom: 1pt;
  font-size: 9.5pt;
  line-height: 1.3;
}}
.education-item {{
  font-size: 9.5pt;
  margin-bottom: 1pt;
}}
.skills-category {{
  font-size: 9.5pt;
  margin-bottom: 1pt;
}}
.skills-category strong {{
  font-weight: bold;
}}
</style>
</head>
<body>
{body}
</body>
</html>
"""


def generate_html(source: dict, experience: list[dict],
                  template: dict, jd_terms: set[str] | None = None) -> str:
    """Generate ATS-friendly HTML resume."""
    meta = source["meta"]
    synonyms = source.get("synonyms", {})
    summary_key = template.get("summary_variant", "product_management")
    summary = source["summary_variants"].get(summary_key, "")
    headline = template.get("headline", "")

    parts = []

    # Header
    parts.append(f"<h1>{meta['name']}</h1>")
    contact_items = []
    if meta.get("location"):
        contact_items.append(meta["location"])
    if meta.get("phone"):
        contact_items.append(meta["phone"])
    if meta.get("email"):
        contact_items.append(f'<a href="mailto:{meta["email"]}">{meta["email"]}</a>')
    if meta.get("linkedin"):
        contact_items.append(f'<a href="{meta["linkedin"]}">LinkedIn</a>')
    parts.append(f'<div class="contact">{" | ".join(contact_items)}</div>')

    if headline:
        parts.append(f'<div class="headline">{headline}</div>')
    if summary:
        parts.append(f'<div class="summary">{summary}</div>')

    # Experience
    parts.append("<h2>Experience</h2>")
    for role in experience:
        parts.append('<div class="role-header">')
        parts.append(f'  <span class="role-title">{role["title"]}</span>')
        parts.append(f'  <span class="role-dates">{role["dates"]}</span>')
        parts.append("</div>")
        parts.append(f'<div class="role-company">{role["company"]}, {role["location"]}</div>')
        parts.append("<ul>")
        for bullet in role["bullets"]:
            text = reformulate_bullet(bullet["text"], jd_terms, synonyms)
            parts.append(f"  <li>{text}</li>")
        parts.append("</ul>")

    # Education
    parts.append("<h2>Education</h2>")
    for edu in source.get("education", []):
        parts.append(f'<div class="education-item"><strong>{edu["degree"]}</strong> &mdash; {edu["school"]}</div>')

    # Skills
    skills_emphasis = template.get("skills_emphasis", [])
    all_categories = source.get("skills", {}).get("categories", [])
    if skills_emphasis:
        ordered = []
        for name in skills_emphasis:
            for cat in all_categories:
                if cat["name"] == name:
                    ordered.append(cat)
                    break
        remaining = [c for c in all_categories if c not in ordered]
        categories = ordered + remaining
    else:
        categories = all_categories

    parts.append("<h2>Technical Skills</h2>")
    for cat in categories:
        items = ", ".join(cat["items"])
        parts.append(f'<div class="skills-category"><strong>{cat["name"]}:</strong> {items}</div>')

    body = "\n".join(parts)
    return HTML_TEMPLATE.format(body=body)


# ---------------------------------------------------------------------------
# Output path
# ---------------------------------------------------------------------------

def build_output_path(archetype: str, company: str | None = None,
                      role: str | None = None, ext: str = "pdf",
                      full_name: str | None = None,
                      date_str: str | None = None) -> Path:
    """Build the output file path following naming conventions.

    date_str overrides today's date when supplied (used by pregenerate
    so re-running on later days doesn't churn filenames).
    """
    today = date_str or date.today().isoformat()
    if company and role:
        company_clean = re.sub(r"[^\w\s-]", "", company).strip().replace(" ", "-")
        role_clean = re.sub(r"[^\w\s-]", "", role).strip().replace(" ", "-")
        if full_name:
            name_clean = re.sub(r"[^\w\s-]", "", full_name).strip().replace(" ", "-")
            name = f"{name_clean}-{company_clean}-{role_clean}-{today}.{ext}"
        else:
            name = f"{company_clean}-{role_clean}-{today}.{ext}"
    else:
        name = f"{archetype}-{today}.{ext}"
    return OUTPUT_DIR / name


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a tailored resume for a given archetype."
    )
    parser.add_argument(
        "--archetype", required=True,
        help="Archetype name (product_management, operations, government, customer_success, ai_technical)"
    )
    parser.add_argument(
        "--jd", default=None,
        help="Path to job description text file for keyword-aware tailoring"
    )
    parser.add_argument(
        "--company", default=None,
        help="Company name (used in output filename)"
    )
    parser.add_argument(
        "--role", default=None,
        help="Role title (used in output filename)"
    )
    parser.add_argument(
        "--markdown-only", action="store_true",
        help="Output markdown only, skip HTML/PDF generation"
    )

    args = parser.parse_args()

    # Load data
    source = load_source()
    config = load_config()
    template = resolve_archetype(config, args.archetype)

    # Load JD if provided
    jd_text = load_jd(args.jd) if args.jd else None
    jd_terms = extract_jd_terms(jd_text) if jd_text else None

    # Select and score bullets
    experience = select_bullets(source, args.archetype, template, jd_text)

    # Count selected bullets
    total_bullets = sum(len(r["bullets"]) for r in experience)
    print(f"Archetype: {args.archetype}")
    print(f"Selected {total_bullets} bullets across {len(experience)} roles")

    full_name = config.get("form_answers", {}).get("full_name")

    if args.markdown_only:
        md = generate_markdown(source, experience, template, jd_terms)
        out_path = build_output_path(args.archetype, args.company, args.role, ext="md", full_name=full_name)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(md)
        print(f"Markdown written: {out_path}")
    else:
        html = generate_html(source, experience, template, jd_terms)
        out_path = build_output_path(args.archetype, args.company, args.role, ext="pdf", full_name=full_name)
        html_to_pdf(html, out_path)
        print(f"PDF generated: {out_path}")


if __name__ == "__main__":
    main()
