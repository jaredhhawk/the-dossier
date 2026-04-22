#!/usr/bin/env python3
"""
Career page monitoring for the job search pipeline.

Fetches company career pages, detects changes via content hashing,
and extracts new listing URLs when changes are found.

Usage:
    python3 careers.py --seed              # Seed career URLs from ~/.scout/seen.md
    python3 careers.py                     # Check all pages for changes
    python3 careers.py --company "Acme"    # Check one company only
"""

import argparse
import hashlib
import json
import os
import re
import sys
import urllib.request
import urllib.error
from datetime import datetime, date
from html.parser import HTMLParser
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    import yaml
except ImportError:
    sys.exit("pyyaml required: pip install pyyaml")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).parent
CONFIG_PATH = SCRIPT_DIR / "config.yaml"
STATE_PATH = SCRIPT_DIR / "data" / "careers_state.json"
SEEN_PATH = os.path.expanduser("~/.scout/seen.md")

# Common careers page URL patterns
CAREERS_PATTERNS = [
    "{base}/careers",
    "{base}/jobs",
    "{base}/careers/openings",
    "{base}/about/careers",
    "{base}/join",
    "{base}/work-with-us",
]


class LinkExtractor(HTMLParser):
    """Extract href links and their text from HTML."""

    def __init__(self):
        super().__init__()
        self.links = []
        self._current_href = None
        self._current_text = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            for name, value in attrs:
                if name == "href":
                    self._current_href = value
                    self._current_text = []

    def handle_data(self, data):
        if self._current_href is not None:
            self._current_text.append(data.strip())

    def handle_endtag(self, tag):
        if tag == "a" and self._current_href:
            text = " ".join(self._current_text).strip()
            self.links.append((self._current_href, text))
            self._current_href = None
            self._current_text = []


def load_config() -> dict:
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def save_config(config: dict):
    with open(CONFIG_PATH, 'w') as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False, width=120)


def load_state() -> dict:
    if STATE_PATH.exists():
        with open(STATE_PATH) as f:
            return json.load(f)
    return {}


def save_state(state: dict):
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_PATH, 'w') as f:
        json.dump(state, f, indent=2)


def fetch_page(url: str, timeout: int = 15) -> str | None:
    """Fetch a URL and return HTML body, or None on failure."""
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        })
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception:
        return None


def hash_content(html: str) -> str:
    """Hash the text content of HTML, ignoring tags/scripts/styles."""
    cleaned = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', html, flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r'<[^>]+>', ' ', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip().lower()
    return hashlib.sha256(cleaned.encode()).hexdigest()[:16]


def extract_job_links(html: str, base_url: str) -> list[dict]:
    """Extract likely job listing links from career page HTML."""
    parser = LinkExtractor()
    try:
        parser.feed(html)
    except Exception:
        return []

    job_patterns = re.compile(
        r'/(jobs?|positions?|openings?|careers?|apply|roles?)/|'
        r'lever\.co|greenhouse\.io|ashbyhq\.com|workday\.com|'
        r'boards\.greenhouse|jobs\.lever|myworkdayjobs',
        re.IGNORECASE
    )
    title_keywords = re.compile(
        r'(manager|director|lead|engineer|analyst|coordinator|specialist|'
        r'head of|vp|vice president|product|operations|program)',
        re.IGNORECASE
    )

    results = []
    seen_urls = set()

    for href, text in parser.links:
        if not href or href.startswith(('#', 'mailto:', 'tel:', 'javascript:')):
            continue

        # Resolve relative URLs
        if href.startswith('/'):
            from urllib.parse import urlparse
            parsed = urlparse(base_url)
            href = f"{parsed.scheme}://{parsed.netloc}{href}"

        if href in seen_urls:
            continue

        if job_patterns.search(href) or (text and title_keywords.search(text)):
            seen_urls.add(href)
            results.append({
                "url": href,
                "title": text[:200] if text else "",
            })

    return results


def check_page(company: str, url: str, state: dict, timeout: int = 15) -> dict | None:
    """Check a single career page. Returns change info or None."""
    html = fetch_page(url, timeout)
    if html is None:
        return {"company": company, "url": url, "status": "fetch_failed"}

    new_hash = hash_content(html)
    old_hash = state.get(url, {}).get("hash", "")
    now = datetime.now().isoformat(timespec="seconds")

    state[url] = {
        "hash": new_hash,
        "company": company,
        "last_checked": now,
        "last_changed": state.get(url, {}).get("last_changed", now) if new_hash == old_hash else now,
    }

    if new_hash == old_hash:
        return None

    jobs = extract_job_links(html, url)

    return {
        "company": company,
        "url": url,
        "status": "changed",
        "new_links": jobs,
        "link_count": len(jobs),
    }


def fetch_career_pages(config: dict) -> list[dict]:
    """Run career page checks. Returns listings in unified format.
    Called by discover.py as Channel C."""
    careers_cfg = config.get("careers", {})
    urls_map = careers_cfg.get("urls", {})
    timeout = careers_cfg.get("fetch_timeout", 15)
    max_concurrent = careers_cfg.get("max_concurrent", 10)

    if not urls_map:
        print("  Career pages: no URLs configured. Run 'python3 careers.py --seed' first.")
        return []

    state = load_state()
    results = []
    changed = 0
    failed = 0

    print(f"  Career pages: checking {len(urls_map)} companies...")

    with ThreadPoolExecutor(max_workers=max_concurrent) as pool:
        futures = {
            pool.submit(check_page, company, url, state, timeout): company
            for company, url in urls_map.items()
        }
        for future in as_completed(futures):
            result = future.result()
            if result is None:
                continue
            if result["status"] == "fetch_failed":
                failed += 1
                continue
            if result["status"] == "changed":
                changed += 1
                for job in result.get("new_links", []):
                    results.append({
                        "source": "CareerPage",
                        "title": job["title"],
                        "company": result["company"],
                        "location": "",
                        "salary": "",
                        "url": job["url"],
                        "description": "",
                        "discovered_at": datetime.now().isoformat(timespec="seconds"),
                    })

    save_state(state)
    print(f"  Career pages: {changed} changed, {failed} failed, {len(results)} new links extracted")
    return results


def seed_from_seen():
    """Seed career page URLs from ~/.scout/seen.md.
    For each company, try common careers page URL patterns."""
    if not os.path.exists(SEEN_PATH):
        print(f"Error: {SEEN_PATH} not found")
        return

    with open(SEEN_PATH) as f:
        text = f.read()

    companies = []
    for line in text.splitlines():
        match = re.match(r'^[-*]\s+(.+?)(?:\s*\([\d-]+\))?$', line.strip())
        if match:
            companies.append(match.group(1).strip())

    print(f"Found {len(companies)} companies in seen.md")
    print("Looking up career page URLs (this takes a few minutes)...\n")

    config = load_config()
    if "careers" not in config:
        config["careers"] = {}
    if "urls" not in config["careers"]:
        config["careers"]["urls"] = {}

    found = 0
    for i, company in enumerate(companies, 1):
        slug = re.sub(r'[^a-z0-9]', '', company.lower())
        domains_to_try = [
            f"https://www.{slug}.com",
            f"https://{slug}.com",
            f"https://www.{slug}.io",
            f"https://{slug}.io",
        ]

        career_url = None
        for domain in domains_to_try:
            for pattern in CAREERS_PATTERNS[:3]:
                test_url = pattern.format(base=domain)
                html = fetch_page(test_url, timeout=5)
                if html and len(html) > 500:
                    career_url = test_url
                    break
            if career_url:
                break

        if career_url:
            config["careers"]["urls"][company] = career_url
            found += 1
            print(f"  [{i}/{len(companies)}] {company} -> {career_url}")
        else:
            print(f"  [{i}/{len(companies)}] {company} -- not found")

    save_config(config)
    print(f"\nSeeded {found}/{len(companies)} career page URLs into config.yaml")
    print("Review and fix any incorrect URLs, then run 'python3 careers.py' to start monitoring.")


def main():
    parser = argparse.ArgumentParser(description="Career page monitor")
    parser.add_argument("--seed", action="store_true",
                        help="Seed career URLs from ~/.scout/seen.md")
    parser.add_argument("--company", help="Check one company only")
    args = parser.parse_args()

    if args.seed:
        seed_from_seen()
        return

    config = load_config()
    listings = fetch_career_pages(config)

    if listings:
        print(f"\nFound {len(listings)} new job links:")
        for l in listings[:10]:
            print(f"  {l['company']} -- {l['title'][:60]}")
        if len(listings) > 10:
            print(f"  ... and {len(listings) - 10} more")
    else:
        print("\nNo career page changes detected.")


if __name__ == "__main__":
    main()
