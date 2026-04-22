#!/usr/bin/env python3
"""
Discovery engine for the job search pipeline.

Channels:
  A) Adzuna API -- primary automated source
  B) Email alerts -- Gmail MCP (handled by /pipeline skill, not this script)
  C) Career page monitoring -- delegates to careers.py

Usage:
    python3 discover.py                    # Run all channels, write daily CSV
    python3 discover.py --channel adzuna   # Adzuna only
    python3 discover.py --channel careers  # Career pages only
    python3 discover.py --dry-run          # Preview without writing CSV
"""

import argparse
import csv
import json
import os
import re
import sys
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, date
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
LISTINGS_DIR = SCRIPT_DIR / "data" / "listings"

LISTING_COLUMNS = [
    "source", "title", "company", "location", "salary",
    "url", "description", "discovered_at"
]


def load_config() -> dict:
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# Channel A: Adzuna API
# ---------------------------------------------------------------------------

ADZUNA_BASE = "https://api.adzuna.com/v1/api/jobs/{country}/search/{page}"


def fetch_adzuna(config: dict) -> list[dict]:
    """Run all search queries against Adzuna API, return raw listings."""
    adzuna_cfg = config.get("adzuna", {})
    app_id = adzuna_cfg.get("app_id", "")
    api_key = adzuna_cfg.get("api_key", "")

    if not app_id or not api_key:
        print("  WARNING: Adzuna app_id/api_key not set in config.yaml. Skipping Channel A.")
        return []

    country = adzuna_cfg.get("country", "us")
    per_page = adzuna_cfg.get("results_per_page", 50)
    max_pages = adzuna_cfg.get("max_pages", 3)
    queries = config.get("search_queries", [])

    if not queries:
        print("  WARNING: No search queries in config.yaml. Skipping Channel A.")
        return []

    all_listings = []
    seen_urls = set()

    print(f"  Adzuna: running {len(queries)} queries (up to {max_pages} pages each)...")

    for qi, q in enumerate(queries, 1):
        query_text = q.get("query", "")
        location = q.get("location", "")

        for page in range(1, max_pages + 1):
            url = ADZUNA_BASE.format(country=country, page=page)
            params = {
                "app_id": app_id,
                "app_key": api_key,
                "results_per_page": str(per_page),
                "what": query_text,
                "content-type": "application/json",
            }
            if location:
                params["where"] = location

            full_url = url + "?" + urllib.parse.urlencode(params)

            try:
                req = urllib.request.Request(full_url)
                with urllib.request.urlopen(req, timeout=15) as resp:
                    data = json.loads(resp.read().decode())
            except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as e:
                print(f"    Query {qi} page {page} failed: {e}")
                break

            results = data.get("results", [])
            if not results:
                break

            for r in results:
                listing_url = r.get("redirect_url", "")
                if listing_url in seen_urls:
                    continue
                seen_urls.add(listing_url)

                salary_min = r.get("salary_min")
                salary_max = r.get("salary_max")
                salary = ""
                if salary_min and salary_max:
                    salary = f"${int(salary_min):,}-${int(salary_max):,}"
                elif salary_min:
                    salary = f"${int(salary_min):,}+"

                all_listings.append({
                    "source": "Adzuna",
                    "title": r.get("title", "").strip(),
                    "company": (r.get("company", {}) or {}).get("display_name", "").strip(),
                    "location": (r.get("location", {}) or {}).get("display_name", "").strip(),
                    "salary": salary,
                    "url": listing_url,
                    "description": r.get("description", "").strip(),
                    "discovered_at": datetime.now().isoformat(timespec="seconds"),
                })

            # Stop paginating if fewer results than requested
            if len(results) < per_page:
                break

    print(f"  Adzuna: {len(all_listings)} listings from {len(queries)} queries")
    return all_listings


# ---------------------------------------------------------------------------
# Unified output
# ---------------------------------------------------------------------------

def write_daily_csv(listings: list[dict], dry_run: bool = False) -> str | None:
    """Write listings to daily CSV. Returns path or None if dry run."""
    if not listings:
        print("\nNo listings to write.")
        return None

    LISTINGS_DIR.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    csv_path = LISTINGS_DIR / f"{today}.csv"

    if dry_run:
        print(f"\n[DRY RUN] Would write {len(listings)} listings to {csv_path}")
        for l in listings[:5]:
            print(f"  {l['company']} -- {l['title']} ({l['source']})")
        if len(listings) > 5:
            print(f"  ... and {len(listings) - 5} more")
        return None

    # Append if CSV already exists (e.g., running multiple channels separately)
    file_exists = csv_path.exists()
    existing_urls = set()
    if file_exists:
        with open(csv_path, newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing_urls.add(row.get("url", ""))

    new_listings = [l for l in listings if l["url"] not in existing_urls]

    with open(csv_path, 'a', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=LISTING_COLUMNS)
        if not file_exists:
            writer.writeheader()
        writer.writerows(new_listings)

    added = len(new_listings)
    skipped = len(listings) - added
    print(f"\nWritten: {csv_path}")
    print(f"  Added: {added}, Skipped (already in CSV): {skipped}")
    return str(csv_path)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Job search discovery engine")
    parser.add_argument("--channel", choices=["adzuna", "careers", "all"],
                        default="all", help="Which channel to run")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview listings without writing CSV")
    parser.add_argument("--no-dedup", action="store_true",
                        help="Skip automatic dedup after discovery")
    args = parser.parse_args()

    config = load_config()
    all_listings = []

    print("Discovery engine starting...\n")

    if args.channel in ("adzuna", "all"):
        all_listings.extend(fetch_adzuna(config))

    if args.channel in ("careers", "all"):
        try:
            from careers import fetch_career_pages
            all_listings.extend(fetch_career_pages(config))
        except ImportError:
            print("  WARNING: careers.py not found. Skipping Channel C.")
        except Exception as e:
            print(f"  WARNING: Career page fetch failed: {e}. Continuing.")

    # Channel B (email alerts) is handled by the /pipeline skill via Gmail MCP,
    # not by this script.

    print(f"\nTotal raw listings: {len(all_listings)}")
    csv_path = write_daily_csv(all_listings, dry_run=args.dry_run)

    # Run dedup automatically after discovery
    if csv_path and not args.dry_run and not args.no_dedup:
        print("\n--- Running dedup ---")
        try:
            from dedup import deduplicate
            deduped_path = deduplicate(csv_path)
            if deduped_path:
                print(f"\nReady for scoring: {deduped_path}")
        except Exception as e:
            print(f"\nDedup failed: {e}")
            print(f"Run manually: python3 dedup.py {csv_path}")
    elif csv_path and not args.dry_run:
        print(f"\nNext step: python3 dedup.py {csv_path}")

    return 0 if all_listings else 1


if __name__ == "__main__":
    sys.exit(main())
