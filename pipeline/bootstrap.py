#!/usr/bin/env python3
"""
One-time bootstrap: seed the dedup ledger from existing vault data.

Reads:
  - R - Application Tracker.md (company + role → status: applied)
  - R - Outreach Log.md (company + role/contact → status: pitched)
  - ~/.scout/blacklist.md (company → status: blacklisted)
  - ~/.scout/seen.md (company → status: seen)

Writes:
  - pipeline/data/ledger.tsv
"""

import os
import re
import csv
from pathlib import Path
from datetime import date

VAULT = os.path.expanduser("~/Documents/Second Brain")
TRACKER_PATH = os.path.join(VAULT, "02_Projects/Job Search/R - Application Tracker.md")
OUTREACH_PATH = os.path.join(VAULT, "02_Projects/Job Search/Scout + Dossier/R - Outreach Log.md")
BLACKLIST_PATH = os.path.expanduser("~/.scout/blacklist.md")
SEEN_PATH = os.path.expanduser("~/.scout/seen.md")
LEDGER_PATH = os.path.join(os.path.dirname(__file__), "data/ledger.tsv")

LEDGER_COLUMNS = [
    "url", "company", "normalized_title", "location",
    "date_first_seen", "score", "grade", "status"
]


def normalize_title(title: str) -> str:
    """Strip Sr./Senior, req IDs, trailing location, lowercase."""
    t = title.strip().lower()
    t = re.sub(r'\b(sr\.?|senior|junior|jr\.?)\b', '', t)
    t = re.sub(r'\b[A-Z]{2,}-\d+\b', '', t, flags=re.IGNORECASE)  # req IDs
    t = re.sub(r'\s*[\(\-–]\s*(remote|hybrid|seattle|wa|washington).*$', '', t, flags=re.IGNORECASE)
    t = re.sub(r'\s+', ' ', t).strip()
    return t


def parse_markdown_table(text: str) -> list[dict]:
    """Parse a pipe-delimited markdown table into list of dicts.
    Returns rows from the FIRST table found."""
    lines = [l.strip() for l in text.splitlines() if l.strip().startswith('|')]
    if len(lines) < 2:
        return []

    # First line is header
    headers = [h.strip() for h in lines[0].split('|')[1:-1]]
    # Second line is separator (skip)
    rows = []
    for line in lines[2:]:
        cells = [c.strip() for c in line.split('|')[1:-1]]
        if len(cells) == len(headers):
            rows.append(dict(zip(headers, cells)))
    return rows


def parse_all_markdown_tables(text: str) -> list[list[dict]]:
    """Parse ALL pipe-delimited markdown tables in a document.
    Returns a list of tables, each table being a list of row dicts."""
    all_lines = text.splitlines()
    tables = []
    i = 0
    while i < len(all_lines):
        line = all_lines[i].strip()
        if line.startswith('|'):
            # Collect contiguous pipe lines
            block = []
            while i < len(all_lines) and all_lines[i].strip().startswith('|'):
                block.append(all_lines[i].strip())
                i += 1
            if len(block) >= 3:  # header + separator + at least one row
                headers = [h.strip() for h in block[0].split('|')[1:-1]]
                rows = []
                for row_line in block[2:]:
                    cells = [c.strip() for c in row_line.split('|')[1:-1]]
                    if len(cells) == len(headers):
                        rows.append(dict(zip(headers, cells)))
                if rows:
                    tables.append(rows)
        else:
            i += 1
    return tables


def read_tracker() -> list[dict]:
    """Read Application Tracker, return ledger rows.
    Parses all tables and picks those with a Company column."""
    if not os.path.exists(TRACKER_PATH):
        print(f"  Warning: {TRACKER_PATH} not found, skipping")
        return []

    with open(TRACKER_PATH) as f:
        text = f.read()

    entries = []
    for table in parse_all_markdown_tables(text):
        if not table or "Company" not in table[0]:
            continue
        for row in table:
            company = row.get("Company", "").strip()
            role = row.get("Role", "").strip()
            applied_date = row.get("Applied", "").strip()
            if company and role:
                entries.append({
                    "url": "",
                    "company": company,
                    "normalized_title": normalize_title(role),
                    "location": "",
                    "date_first_seen": applied_date or str(date.today()),
                    "score": "",
                    "grade": "",
                    "status": "applied"
                })

    print(f"  Tracker: {len(entries)} entries")
    return entries


def read_outreach_log() -> list[dict]:
    """Read Outreach Log, return ledger rows."""
    if not os.path.exists(OUTREACH_PATH):
        print(f"  Warning: {OUTREACH_PATH} not found, skipping")
        return []

    with open(OUTREACH_PATH) as f:
        text = f.read()

    entries = []
    for row in parse_markdown_table(text):
        company = row.get("Company", "").strip()
        contact = row.get("Contact", "").strip()
        log_date = row.get("Date", "").strip()
        if company:
            entries.append({
                "url": "",
                "company": company,
                "normalized_title": "",
                "location": "",
                "date_first_seen": log_date or str(date.today()),
                "score": "",
                "grade": "",
                "status": "pitched"
            })

    print(f"  Outreach Log: {len(entries)} entries")
    return entries


def read_list_file(path: str, status: str) -> list[dict]:
    """Read a simple markdown list file (blacklist or seen), return ledger rows."""
    if not os.path.exists(path):
        print(f"  Warning: {path} not found, skipping")
        return []

    with open(path) as f:
        text = f.read()

    entries = []
    for line in text.splitlines():
        line = line.strip()
        # Match lines like "- Company Name" or "* Company Name"
        match = re.match(r'^[-*]\s+(.+)$', line)
        if match:
            company = match.group(1).strip()
            # Strip any markdown links
            company = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', company)
            company = re.sub(r'\[\[([^\]]+)\]\]', r'\1', company)
            if company:
                entries.append({
                    "url": "",
                    "company": company,
                    "normalized_title": "",
                    "location": "",
                    "date_first_seen": str(date.today()),
                    "score": "",
                    "grade": "",
                    "status": status
                })

    print(f"  {os.path.basename(path)}: {len(entries)} entries")
    return entries


def deduplicate(entries: list[dict]) -> list[dict]:
    """Remove duplicate companies (keep first occurrence, prefer applied > pitched > seen)."""
    status_priority = {"applied": 0, "pitched": 1, "blacklisted": 2, "seen": 3}
    entries.sort(key=lambda e: status_priority.get(e["status"], 99))

    seen_companies = set()
    unique = []
    for entry in entries:
        key = entry["company"].lower()
        if key not in seen_companies:
            seen_companies.add(key)
            unique.append(entry)

    return unique


def write_ledger(entries: list[dict]):
    """Write entries to ledger.tsv."""
    os.makedirs(os.path.dirname(LEDGER_PATH), exist_ok=True)

    with open(LEDGER_PATH, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=LEDGER_COLUMNS, delimiter='\t')
        writer.writeheader()
        writer.writerows(entries)

    print(f"\nLedger written: {LEDGER_PATH}")
    print(f"Total entries: {len(entries)}")


def main():
    print("Bootstrapping dedup ledger from existing data...\n")

    entries = []
    entries.extend(read_tracker())
    entries.extend(read_outreach_log())
    entries.extend(read_list_file(BLACKLIST_PATH, "blacklisted"))
    entries.extend(read_list_file(SEEN_PATH, "seen"))

    print(f"\nRaw total: {len(entries)}")
    entries = deduplicate(entries)
    print(f"After dedup: {len(entries)}")

    write_ledger(entries)


if __name__ == "__main__":
    main()
