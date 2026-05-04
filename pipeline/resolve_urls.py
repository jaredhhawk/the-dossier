#!/usr/bin/env python3
"""Post-score URL resolution for scored listings.

Reads a scored JSON file, searches for the real employer apply URL for each
listing that matches the grade filter, and writes the result back with a
`resolved_url` field added (or `resolved_url_failed: true` on failure).

Resolution is a DuckDuckGo HTML search for `"{company}" "{title}"` -- we never
hit the listing's original aggregator URL at this stage. ATS domains
(greenhouse/lever/ashby/workday) are preferred over company careers pages and
over other aggregators.

Single-worker by default; DDG tolerates polite scraping but challenges bursts.

Usage:
  python3 resolve_urls.py pipeline/data/scored/2026-04-23.json
  python3 resolve_urls.py pipeline/data/scored/2026-04-23.json --grades A,B,C
  python3 resolve_urls.py pipeline/data/scored/2026-04-23.json --retry-failed
"""
import argparse
import json
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from url_resolver import search_employer_url


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scored_json", help="Path to scored JSON file")
    parser.add_argument("--grades", default="A,B",
                        help="Comma-separated grades to resolve (default: A,B)")
    parser.add_argument("--delay", type=float, default=12.0,
                        help="Seconds to sleep between searches (default: 12.0). "
                             "Search engines rate-limit bursts aggressively; "
                             "12s keeps 44 listings under ~10 min wall time without tripping 429s.")
    parser.add_argument("--timeout", type=int, default=20,
                        help="Per-request HTTP timeout seconds (default: 20)")
    parser.add_argument("--retry-failed", action="store_true",
                        help="Re-attempt listings previously marked failed")
    parser.add_argument("--sources", default="",
                        help="Comma-separated source filter (default: all sources). "
                             "Typical: --sources Adzuna")
    args = parser.parse_args()

    path = Path(args.scored_json)
    if not path.exists():
        print(f"ERROR: {path} not found", file=sys.stderr)
        sys.exit(1)

    data = json.loads(path.read_text())
    grades = {g.strip().upper() for g in args.grades.split(",") if g.strip()}
    sources = {s.strip() for s in args.sources.split(",") if s.strip()}

    targets = []
    for i, item in enumerate(data):
        if sources and item.get("source") not in sources:
            continue
        if item.get("grade") not in grades:
            continue
        if item.get("resolved_url"):
            continue
        if item.get("resolved_url_failed") and not args.retry_failed:
            continue
        if not item.get("company") or not item.get("title"):
            continue
        targets.append((i, item))

    if not targets:
        print(f"No listings to resolve "
              f"(grades={','.join(sorted(grades))}"
              f"{', sources=' + ','.join(sorted(sources)) if sources else ''}).")
        return

    print(f"Resolving {len(targets)} listings "
          f"(grades={','.join(sorted(grades))}, "
          f"delay={args.delay}s, timeout={args.timeout}s)...")

    resolved = 0
    failed = 0
    status_counts = {}

    for n, (i, item) in enumerate(targets, 1):
        company = item["company"]
        title = item["title"]
        try:
            real_url, status = search_employer_url(company, title, timeout=args.timeout)
        except Exception as e:
            real_url, status = None, f"error:{type(e).__name__}"

        status_counts[status] = status_counts.get(status, 0) + 1

        if real_url and status.startswith("ok"):
            data[i]["resolved_url"] = real_url
            data[i]["resolved_status"] = status
            data[i].pop("resolved_url_failed", None)
            resolved += 1
            marker = "OK"
        else:
            data[i]["resolved_url_failed"] = True
            data[i]["resolved_status"] = status
            failed += 1
            marker = "--"

        print(f"  [{marker}] {n:>3}/{len(targets)} {status:15s} "
              f"{company[:30]:30s} | {(title or '')[:40]:40s}"
              + (f" -> {real_url[:70]}" if real_url else ""))

        # Save after every 10 to survive interruption
        if n % 10 == 0:
            path.write_text(json.dumps(data, indent=2))

        if n < len(targets):
            # Small jitter (+/- 25%) so we don't look like a metronome
            jitter = args.delay * (0.75 + 0.5 * random.random())
            time.sleep(jitter)

    path.write_text(json.dumps(data, indent=2))
    print(f"\nResolved: {resolved}  Failed: {failed}")
    for status, count in sorted(status_counts.items(), key=lambda x: -x[1]):
        print(f"  {status}: {count}")


if __name__ == "__main__":
    main()
