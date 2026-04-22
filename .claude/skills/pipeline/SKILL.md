---
name: pipeline
description: Automated job search pipeline. Discover, score, triage, apply, and outreach in one daily flow.
version: 0.3.0
---

# /pipeline

Automated job search pipeline with breakpoints.

## Usage

`/pipeline` -- full daily run (discover + dedup + breakpoint)
`/pipeline discover` -- discovery + dedup only
`/pipeline review` -- score + triage from most recent discovery (Phase 4)
`/pipeline --grade A` -- filter card queue to A-only (Phase 4)

## Available Now

- `/apply Company - Role Title` -- log an application with clipboard package
- Resume generation:
  ```bash
  cd ~/code/the-dossier && pipeline/.venv/bin/python3 pipeline/resume.py \
    --archetype product_management --company "Company" --role "Role"
  ```
  Archetypes: `product_management`, `operations`, `government`, `customer_success`, `ai_technical`
  Optional: `--jd path/to/jd.txt` for keyword-aware tailoring, `--markdown-only` to skip PDF

## Full Run Flow

### Stage 1: Discovery

1. Run Python discovery (Channels A + C):
   ```bash
   cd ~/code/the-dossier && python3 pipeline/discover.py --no-dedup
   ```

2. Run Channel B (email alerts) -- see "Channel B: Email Alert Processing" below.

3. Run dedup:
   ```bash
   cd ~/code/the-dossier && python3 pipeline/dedup.py pipeline/data/listings/$(date +%Y-%m-%d).csv
   ```

4. **Breakpoint 1:** Report stats and ask to continue.
   ```
   Discovery complete.
   - Channel A (Adzuna): X listings
   - Channel B (Email): Y listings
   - Channel C (Career pages): Z listings
   - After dedup: N new listings

   Continue to scoring? (y/n)
   ```

### Stage 2: Scoring (Phase 4 -- not yet implemented)

### Stage 3: Card Queue (Phase 4 -- not yet implemented)

### Stage 4: Outreach (Phase 5 -- not yet implemented)

## Channel B: Email Alert Processing

When running discovery (full run or `/pipeline discover`):

1. Use Gmail MCP to search for unread emails with label "Job Alerts":
   - `mcp__gmail__search_emails` with query: `label:Job Alerts is:unread`

2. For each email found:
   - Read the email body using `mcp__gmail__read_email`
   - Extract job listings: title, company, URL, location (if available)
   - Source field: use the sender name (e.g., "LinkedIn", "Indeed", "Built In")

3. Append extracted listings to today's CSV at `~/code/the-dossier/pipeline/data/listings/YYYY-MM-DD.csv`
   - Use the same column format: source, title, company, location, salary, url, description, discovered_at
   - If the CSV doesn't exist yet, create it with headers

4. Mark processed emails as read using `mcp__gmail__modify_email`

5. Report: "Email alerts: processed N emails, extracted M listings"

If Gmail MCP is unavailable, skip Channel B and continue with other channels.

## Error Handling

- Adzuna API down: skip Channel A, continue with B + C, warn user
- Gmail MCP unavailable: skip Channel B, continue with A + C, warn user
- Career page fetch fails: logged per-page, never fatal
- No channels return results: "No new listings today. Try adjusting search queries?"

## Coming Soon

- Phase 4: Scoring + card queue (this skill becomes fully functional)
- Phase 5: Outreach agent (background /pitch dispatch)
