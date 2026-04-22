#!/usr/bin/env python3
"""
Three-level deduplication engine for the job search pipeline.

Reads a daily listings CSV, checks against ledger + vault sources,
and writes a filtered CSV of genuinely new listings.

Levels:
  1. Exact URL match (hash lookup)
  2. Company + normalized title match
  3. Fuzzy title match (85% similarity, same company)

Sources checked:
  - pipeline/data/ledger.tsv (primary)
  - R - Application Tracker.md (live check)
  - R - Outreach Log.md (live check)
  - ~/.scout/blacklist.md (hard filter)
  - ~/.scout/seen.md (soft filter)

Usage:
    python3 dedup.py pipeline/data/listings/2026-04-21.csv
    python3 dedup.py pipeline/data/listings/2026-04-21.csv --stats
"""

import argparse
import csv
import os
import re
import sys
from datetime import date
from difflib import SequenceMatcher
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("pyyaml required: pip install pyyaml")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).parent
CONFIG_PATH = SCRIPT_DIR / "config.yaml"
LEDGER_PATH = SCRIPT_DIR / "data" / "ledger.tsv"

# Reuse normalize_title from bootstrap
from bootstrap import normalize_title, parse_markdown_table, parse_all_markdown_tables


def load_config() -> dict:
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# Load known data sources
# ---------------------------------------------------------------------------

def load_ledger() -> tuple[set, dict, set]:
    """Load ledger.tsv. Returns (url_set, company_title_dict, blacklisted_companies)."""
    urls = set()
    company_titles = {}
    blacklisted = set()

    if not LEDGER_PATH.exists():
        print("  WARNING: ledger.tsv not found. Run bootstrap.py first.")
        return urls, company_titles, blacklisted

    with open(LEDGER_PATH, newline='') as f:
        reader = csv.DictReader(f, delimiter='\t')
        for row in reader:
            url = row.get("url", "").strip()
            company = row.get("company", "").strip().lower()
            title = row.get("normalized_title", "").strip()
            status = row.get("status", "").strip()

            if url:
                urls.add(url)
            if company and title:
                company_titles[(company, title)] = status
            if status == "blacklisted":
                blacklisted.add(company)

    return urls, company_titles, blacklisted


def load_tracker_companies() -> dict:
    """Load Application Tracker for live dedup. Returns {(company_lower, normalized_title): date}."""
    config = load_config()
    path = os.path.expanduser(config.get("vault", {}).get("application_tracker", ""))
    if not path or not os.path.exists(path):
        return {}

    with open(path) as f:
        text = f.read()

    result = {}
    for table in parse_all_markdown_tables(text):
        if not table or "Company" not in table[0]:
            continue
        for row in table:
            company = row.get("Company", "").strip().lower()
            role = normalize_title(row.get("Role", ""))
            applied = row.get("Applied", "").strip()
            if company and role:
                result[(company, role)] = applied
    return result


def load_outreach_companies() -> set:
    """Load Outreach Log companies. Returns set of company_lower."""
    config = load_config()
    path = os.path.expanduser(config.get("vault", {}).get("outreach_log", ""))
    if not path or not os.path.exists(path):
        return set()

    with open(path) as f:
        text = f.read()

    companies = set()
    for row in parse_markdown_table(text):
        company = row.get("Company", "").strip().lower()
        if company:
            companies.add(company)
    return companies


def load_blacklist() -> set:
    """Load blacklist. Returns set of company_lower."""
    config = load_config()
    path = os.path.expanduser(config.get("scout", {}).get("blacklist", ""))
    if not path or not os.path.exists(path):
        return set()

    companies = set()
    with open(path) as f:
        for line in f:
            match = re.match(r'^[-*]\s+(.+)$', line.strip())
            if match:
                name = match.group(1).strip()
                name = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', name)
                name = re.sub(r'\[\[([^\]]+)\]\]', r'\1', name)
                companies.add(name.lower())
    return companies


def load_seen() -> set:
    """Load seen companies. Returns set of company_lower."""
    config = load_config()
    path = os.path.expanduser(config.get("scout", {}).get("seen", ""))
    if not path or not os.path.exists(path):
        return set()

    companies = set()
    with open(path) as f:
        for line in f:
            match = re.match(r'^[-*]\s+(.+?)(?:\s*\([\d-]+\))?$', line.strip())
            if match:
                companies.add(match.group(1).strip().lower())
    return companies


# ---------------------------------------------------------------------------
# Dedup logic
# ---------------------------------------------------------------------------

def deduplicate(input_csv: str, stats_only: bool = False) -> str:
    """Run three-level dedup on a listings CSV. Returns path to filtered CSV."""

    print("Loading dedup sources...")
    ledger_urls, ledger_titles, ledger_blacklisted = load_ledger()
    tracker = load_tracker_companies()
    outreach_companies = load_outreach_companies()
    blacklist = load_blacklist() | ledger_blacklisted
    seen = load_seen()

    print(f"  Ledger: {len(ledger_urls)} URLs, {len(ledger_titles)} company/title pairs")
    print(f"  Tracker: {len(tracker)} applications")
    print(f"  Outreach: {len(outreach_companies)} companies")
    print(f"  Blacklist: {len(blacklist)} companies")
    print(f"  Seen: {len(seen)} companies")

    with open(input_csv, newline='') as f:
        reader = csv.DictReader(f)
        listings = list(reader)

    print(f"\nInput: {len(listings)} listings")

    stats = {
        "total": len(listings),
        "duplicate_url": 0,
        "duplicate_title": 0,
        "duplicate_fuzzy": 0,
        "already_applied": 0,
        "blacklisted": 0,
        "seen_same_role": 0,
        "new": 0,
    }

    batch_titles = {}
    filtered = []

    for listing in listings:
        url = listing.get("url", "").strip()
        company = listing.get("company", "").strip()
        title = listing.get("title", "").strip()
        company_lower = company.lower()
        norm_title = normalize_title(title)

        # Level 0: Blacklist hard filter
        if company_lower in blacklist:
            stats["blacklisted"] += 1
            listing["dedup_status"] = "blacklisted"
            continue

        # Level 1: Exact URL
        if url and url in ledger_urls:
            stats["duplicate_url"] += 1
            listing["dedup_status"] = "duplicate_url"
            continue

        # Level 2: Company + normalized title (ledger + tracker)
        if (company_lower, norm_title) in ledger_titles:
            existing_status = ledger_titles[(company_lower, norm_title)]
            if existing_status == "applied":
                stats["already_applied"] += 1
                listing["dedup_status"] = "already_applied"
            else:
                stats["duplicate_title"] += 1
                listing["dedup_status"] = "duplicate_title"
            continue

        if (company_lower, norm_title) in tracker:
            stats["already_applied"] += 1
            listing["dedup_status"] = "already_applied"
            continue

        # Intra-batch dedup
        if (company_lower, norm_title) in batch_titles:
            stats["duplicate_title"] += 1
            listing["dedup_status"] = "duplicate_title"
            continue

        # Seen company soft filter: skip only if same role
        if company_lower in seen:
            if (company_lower, norm_title) in ledger_titles:
                stats["seen_same_role"] += 1
                listing["dedup_status"] = "seen_same_role"
                continue

        # Level 3: Fuzzy match (85% SequenceMatcher, same company)
        fuzzy_match = False
        for (known_company, known_title), known_status in ledger_titles.items():
            if known_company != company_lower:
                continue
            if not known_title or not norm_title:
                continue
            ratio = SequenceMatcher(None, norm_title, known_title).ratio()
            if ratio >= 0.85:
                fuzzy_match = True
                break

        if not fuzzy_match:
            for (batch_company, batch_title) in batch_titles:
                if batch_company != company_lower:
                    continue
                if not batch_title or not norm_title:
                    continue
                ratio = SequenceMatcher(None, norm_title, batch_title).ratio()
                if ratio >= 0.85:
                    fuzzy_match = True
                    break

        if fuzzy_match:
            stats["duplicate_fuzzy"] += 1
            listing["dedup_status"] = "duplicate_fuzzy"
            continue

        # Passed all checks
        stats["new"] += 1
        listing["dedup_status"] = "new"
        batch_titles[(company_lower, norm_title)] = True
        filtered.append(listing)

    print(f"\nDedup results:")
    print(f"  New (pass):           {stats['new']}")
    print(f"  Blacklisted:          {stats['blacklisted']}")
    print(f"  Duplicate URL:        {stats['duplicate_url']}")
    print(f"  Duplicate title:      {stats['duplicate_title']}")
    print(f"  Duplicate fuzzy:      {stats['duplicate_fuzzy']}")
    print(f"  Already applied:      {stats['already_applied']}")
    print(f"  Seen (same role):     {stats['seen_same_role']}")

    if stats_only:
        return ""

    output_path = input_csv.replace(".csv", "-deduped.csv")
    out_columns = list(filtered[0].keys()) if filtered else []

    with open(output_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=out_columns)
        writer.writeheader()
        writer.writerows(filtered)

    print(f"\nFiltered output: {output_path}")
    print(f"  {len(filtered)} listings ready for scoring")
    return output_path


def main():
    parser = argparse.ArgumentParser(description="Three-level dedup engine")
    parser.add_argument("input_csv", help="Path to daily listings CSV")
    parser.add_argument("--stats", action="store_true",
                        help="Print stats only, don't write filtered CSV")
    args = parser.parse_args()

    if not os.path.exists(args.input_csv):
        print(f"Error: {args.input_csv} not found")
        sys.exit(1)

    deduplicate(args.input_csv, stats_only=args.stats)


if __name__ == "__main__":
    main()
