---
name: pipeline
description: Automated job search pipeline. Discover, score, triage, apply, and outreach in one daily flow.
version: 1.1.0
---

# /pipeline

Automated job search pipeline with breakpoints. Discovers listings, scores them against your resume, presents a fast triage queue, dispatches applications, and fires parallel outreach.

## Usage

```
/pipeline                  Full daily run (discover + score + triage + note)
/pipeline discover         Discovery + dedup only, stop after Breakpoint 1
/pipeline review           Skip discovery, score + triage from most recent data
/pipeline resume           Jump to card queue from most recent scored JSON (no scoring)
/pipeline --grade A        Filter card queue to A-grade only
/pipeline --grade A,B      Filter to A and B grades
```

## Flag Handling

### `/pipeline` (no flags)
Full run: Stage 1 (Discovery) -> Stage 2 (Scoring) -> Stage 3 (Card Queue) -> Stage 4 (Daily Note)

### `/pipeline discover`
Run Stage 1 only. Stop after Breakpoint 1 (dedup stats). Do not score or triage.

### `/pipeline review`
Skip Stage 1. Look for data to work with:
1. Check `pipeline/data/scored/` for today's JSON with `new` status listings -> go to Stage 3.
2. Check `pipeline/data/listings/` for a deduped CSV that hasn't been scored -> run Stage 2, then Stage 3.
3. If neither found: "No pending listings. Run `/pipeline` for a full discovery."

### `/pipeline resume`
Skip discovery and scoring. Load most recent scored JSON, show only cards with status `new`. If none: "No cards to review."

### `/pipeline --grade A` (or `A,B`, `C`, etc.)
Run normally but filter card queue to only show the specified grades. Still scores everything. Works with any subcommand: `/pipeline --grade A`, `/pipeline review --grade A,B`.

---

## Full Run Flow

### Stage 1: Discovery

1. Run Python discovery (Channels A + C):
   ```bash
   cd ~/code/the-dossier && pipeline/.venv/bin/python3 pipeline/discover.py --no-dedup
   ```
   Capture the output. Note the per-channel counts.

2. Run Channel B (email alerts) -- see "Channel B: Email Alert Processing" below.

3. Run dedup:
   ```bash
   cd ~/code/the-dossier && pipeline/.venv/bin/python3 pipeline/dedup.py pipeline/data/listings/$(date +%Y-%m-%d).csv
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

   If user says no, stop here. If `/pipeline discover`, stop here regardless.

---

### Stage 2: Scoring

1. **Load deduped CSV:**
   ```
   ~/code/the-dossier/pipeline/data/listings/YYYY-MM-DD-deduped.csv
   ```
   If not found, look for the most recent `-deduped.csv` in the listings directory.

2. **Check for prior scoring progress:**
   If `pipeline/data/scored/YYYY-MM-DD.json` exists, load it. Find listings that have been scored (have a `weighted_score`). Cross-reference with the deduped CSV. Only score listings not yet in the scored JSON. This enables resume-from-interruption.

3. **Load scoring context (once):**
   - Read `~/code/the-dossier/pipeline/data/resumes/source.json` -- the candidate's structured resume.
   - Read archetype keywords from `~/code/the-dossier/pipeline/config.yaml` under `archetypes:`.

4. **Score each unscored listing.**

   For each listing, evaluate across 10 weighted dimensions (rate 1-5 each):

   | Dimension | Weight | Question |
   |-----------|--------|----------|
   | Role match | 3x | Title + responsibilities align with experience? |
   | Skills alignment | 3x | Required skills match what they've done? |
   | Interview likelihood | 3x | Realistic shot at a screen? |
   | Seniority fit | 2x | Right level? |
   | Compensation | 2x | Meets $100K+ floor? |
   | Domain resonance | 2x | Industry/domain connects to experience? |
   | Timeline/urgency | 2x | Recent posting, likely still open? |
   | Geographic fit | 1x | Seattle, remote, or hybrid? |
   | Company stage | 1x | Reasonable company? |
   | Growth trajectory | 1x | Career advancement potential? |

   **Negative factors** (deduct from weighted score):
   - Known layoff signals, poor Glassdoor (<3.0), CEO churn: -0.5 to -1.0
   - Backfill red flags: -0.3
   - Unicorn requirements (10 conflicting skills): -0.5

   **Weighted score formula:**
   ```
   (3*(role_match + skills_alignment + interview_likelihood)
    + 2*(seniority_fit + compensation + domain_resonance + timeline_urgency)
    + 1*(geographic_fit + company_stage + growth_trajectory)) / 20
    + negative_adjustment
   ```

   **Grades:** A: 4.0+, B: 3.5-3.9, C: 2.5-3.4, D: 1.5-2.4, F: <1.5

   **Archetype:** Match title + description against archetype keywords in config.yaml. First match wins. Default: operations.

   **Output per listing:**
   ```json
   {
     "title": "...",
     "company": "...",
     "location": "...",
     "salary": "...",
     "url": "...",
     "source": "...",
     "description": "...",
     "scores": {
       "role_match": 4,
       "skills_alignment": 3,
       "interview_likelihood": 4,
       "seniority_fit": 4,
       "compensation": 3,
       "domain_resonance": 3,
       "timeline_urgency": 4,
       "geographic_fit": 5,
       "company_stage": 3,
       "growth_trajectory": 3
     },
     "negative_adjustment": 0,
     "weighted_score": 3.7,
     "grade": "B",
     "archetype": "product_management",
     "rationale": "Strong PM fit. Roadmap ownership + platform experience align.",
     "red_flags": [],
     "status": "new"
   }
   ```

5. **Save after every 15 listings** (chunk checkpoint):
   Write the full scored array to `~/code/the-dossier/pipeline/data/scored/YYYY-MM-DD.json`.
   If scoring is interrupted mid-batch, the next run picks up from the last checkpoint.

6. **Resolve real employer URLs for Grade A + B listings:**
   Aggregator listings (Adzuna in particular) point to tracking URLs that now land on interstitial promos (ApplyIQ) rather than the real employer form. This step searches Brave / DuckDuckGo for `"{company}" "{title}"` and stores the first ATS / employer-native result as `resolved_url` on each listing, so Stage 3 opens the right page.

   ```bash
   cd ~/code/the-dossier && pipeline/.venv/bin/python3 pipeline/resolve_urls.py \
     pipeline/data/scored/$(date +%Y-%m-%d).json --grades A,B
   ```

   - Resolves only Grade A + B listings (typically 40-60/day). Grade C is resolved lazily at `/apply` time.
   - Default: 12s delay between searches with small jitter; wall time ~10 min for 44 listings. Tuned to stay under Brave + DDG rate limits; bursts trigger 429s.
   - Stores `resolved_url` + `resolved_status` on success; marks `resolved_url_failed: true` on failure (user can rerun with `--retry-failed` on the next day).
   - Report: "Resolved: X  Failed: Y" from the script output.
   - Full docs: `~/Documents/Second Brain/04_Resources/Development/R - Pipeline URL Resolution.md`.

   If this step fails entirely (both search engines 429'd, network down), continue to Breakpoint 2 anyway -- `/apply` will fall back to a Google search URL at apply time.

7. **Breakpoint 2:** After all listings scored, report grade distribution:
   ```
   Scoring complete.
   - A (4.0+): 8 listings
   - B (3.5-3.9): 12 listings
   - C (2.5-3.4): 9 listings
   - D/F (<2.5): 5 listings (filtered out)

   Review 29 cards? (y/n)
   ```

---

### Stage 3: Card Queue Triage

Load scored JSON. Filter to A, B, and C grades (or as specified by `--grade` flag). Sort by weighted score, highest first. D/F grades are never shown.

**Outreach tracking (initialize before card loop):**
- `outreach_dispatched = 0`
- `outreach_max = 20` (rate limit per session)
- `outreach_agents = []` (track dispatched agent IDs for summary collection)

**Card format:**

```
━━━ Card 3/29 ━━━━━━━━━━━━━━━━━━━━━━��━━━━━━━━
Senior PM, Platform -- Acme Corp (Seattle)
Grade: A (4.3)  |  Archetype: Product Management
Source: Adzuna  |  Salary: $120-140K

Key fit:  Roadmap ownership + platform experience match
Red flag: None
━━━━━━��━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[a]pply  [s]kip  [o]pen JD  [q]uit
```

Only show cards with status `new`. Cards already `applied` or `skipped` from a prior session are excluded.

**Actions:**

**[a] Apply:**
1. Generate tailored resume:
   ```bash
   cd ~/code/the-dossier && pipeline/.venv/bin/python3 pipeline/resume.py \
     --archetype {archetype} --company "{company}" --role "{title}"
   ```
   If PDF already exists for this company+role+date, skip generation and report the existing path.

2. Display clipboard package:
   ```
   ━━━ Clipboard Package ━━━━━━━━━━━━━━━━━━━━━━━
   Company:    {company}
   Role:       {title}
   Archetype:  {archetype}
   Tier:       {grade} -- {A: custom cover + /pitch, B: stock blurb, C: low fit}
   Resume:     ~/code/the-dossier/pipeline/data/resumes/output/Jared-Hawkins-{Company}-{Role}-{date}.pdf

   Salary expectation: {form_answers.salary_expectation from config}
   Visa/auth:          {form_answers.visa_status}
   LinkedIn:           {form_answers.linkedin}
   Location:           {form_answers.location}
   Why this company:   {rationale from scorer}
   ━━━━━━��━━━━━━���━━━━━━━━━━━━━��━━━━━━━��━━━━━━━━━
   ```

3. Pick the URL to open:
   - If card has `resolved_url` (set by Stage 2 step 6), use it.
   - Else do a lazy search resolution:
     ```bash
     cd ~/code/the-dossier && pipeline/.venv/bin/python3 pipeline/url_resolver.py "{company}" "{title}"
     ```
     If the output status starts with `ok`, use the returned URL.
   - Else build a Google search URL: `https://www.google.com/search?q=` + urlencode(`"{company}" "{title}" careers`). Tell the user: "Couldn't resolve automatically -- opened a Google search; click the right result."
4. Open the chosen URL in Chrome (not the default browser, which may be cmux's internal browser without Simplify.jobs / Gmail login):
   ```bash
   open -a "Google Chrome" "{final_url}"
   ```
   Print: `-> Opening: {final_url}` so the user can see the target before the tab loads.
5. Say: "Application page opened. Fill the form, then confirm when submitted."
6. Wait for user confirmation.
7. After confirmation, log the application:
   - Append to Application Tracker (`R - Application Tracker.md`):
     `| {Company} | {Title} | Pipeline | {YYYY-MM-DD} | Applied | | | Pipeline logged |`
   - Update ledger (`pipeline/data/ledger.tsv`): append or update row with status `applied`
   - Update scored JSON: set this listing's status to `applied`

8. **Dispatch background outreach agent** (if `outreach_dispatched < outreach_max`):

   Use the Agent tool with `run_in_background: true`:

   ```
   Agent({
     description: "Outreach: {company}",
     prompt: "You are a background outreach agent for the job search pipeline.

     Task: Attempt cold outreach for this application:
     - Company: {company}
     - Role: {title}
     - URL: {url}
     - Archetype: {archetype}
     - Scorer rationale: {rationale}

     Steps:

     1. Read the Outreach Log at ~/Documents/Second Brain/02_Projects/Job Search/Scout + Dossier/R - Outreach Log.md
        - If {company} appears with a date within the last 30 days, STOP and output: 'Skipped: {company} pitched within 30 days.'
        - If {company} has an existing contact (name + email), note it for step 3.

     2. Read ~/.scout/blacklist.md
        - If {company} is listed, STOP and output: 'Skipped: {company} is blacklisted.'

     3. Find a contact:
        - If the Outreach Log already has a contact for {company}, reuse that name and email.
        - Otherwise, do a quick contact search:
          a. Web search: '{company} {title} hiring manager' or '{company} VP Product linkedin'
          b. Check the company website About/Team page for names and email patterns.
          c. If a name is found but no email, infer from the domain (but note low confidence).
        - If no contact found after these checks, output: 'No contact: {company} -- portal application only.' and STOP.

     4. Run /pitch:
        Invoke the /pitch skill: /pitch {company} --with-gmail
        The /pitch skill will research the company, pick an angle, draft the email, and create a Gmail draft.

     5. Output: 'Outreach: drafted email to [contact] at {company}'

     IMPORTANT: /pitch creates Gmail DRAFTS only. Never send emails directly.",
     run_in_background: true
   })
   ```

   Increment `outreach_dispatched`. Add agent ID to `outreach_agents`.
   If `outreach_dispatched >= outreach_max`, skip silently for remaining cards.

9. Move to next card.

**[s] Skip:**
1. Update scored JSON: set status to `skipped`.
2. Append to ledger with status `skipped` (if not already present).
3. Move to next card.

**[o] Open JD:**
1. Open listing URL: `open "{url}"`
2. Re-present the same card for action.

**[q] Quit:**
1. Remaining cards keep status `new` in scored JSON.
2. Save scored JSON.
3. Report: "Triage paused. {N} cards remaining. Run `/pipeline review` to continue."
4. Proceed to Stage 4 (daily note).

---

### Outreach Summary

After triage completes (all cards processed or user quits), before generating the daily note:

1. Collect results from all background outreach agents in `outreach_agents`.
   Most should have completed by now (they run in parallel during triage).
   If any are still running, note them as "pending" in the summary.

2. Tally results:
   - Drafts created (contact found, /pitch ran successfully)
   - No contact found (search failed)
   - Skipped -- cooldown (company pitched within 30 days)
   - Skipped -- blacklisted
   - Skipped -- rate limit (outreach_dispatched hit cap)
   - Pending (still running)

3. Report:
   ```
   Outreach summary:
   - Dispatched: N agents
   - Drafts created: X
   - No contact found: Y
   - Skipped (cooldown/blacklist): Z
   - Rate limited: W
   ```

---

### Stage 4: Obsidian Daily Note

After outreach summary (or immediately after triage if no outreach was dispatched):

Generate note at `~/Documents/Second Brain/99_System/Daily Notes/Pipeline - YYYY-MM-DD.md`:

```markdown
---
Domain: "[[D - Career & Job Search]]"
tags:
  - pipeline
  - daily-note
created: YYYY-MM-DD
---
Related: [[R - Application Tracker]] | [[R - Outreach Log]] | [[P - Job Search Pipeline (Speed)|Pipeline Spec]]

# Pipeline Run -- YYYY-MM-DD

## Summary
- **Discovered:** X listings (Adzuna: _, Email: _, Career pages: _)
- **After dedup:** Y new listings
- **Scored:** Z listings (A: _, B: _, C: _, D/F: _)
- **Triaged:** N cards reviewed
- **Applied:** M applications submitted
- **Skipped:** K listings skipped

## Applications

| Company | Role | Grade | Archetype |
|---------|------|-------|-----------|
| {rows for each applied listing} |

## Skipped

| Company | Role | Grade | Rationale |
|---------|------|-------|-----------|
| {rows for each skipped listing} |

## Outreach

| Company | Contact | Status |
|---------|---------|--------|
| {rows for each outreach attempt: company, contact name or "N/A", Draft created / No contact / Cooldown / Blacklisted} |

**Summary:** {X} drafts created, {Y} no contact, {Z} skipped

## Remaining

{N} cards with status `new`. Resume with `/pipeline review`.
```

Confirm: "Daily note written to Pipeline - YYYY-MM-DD.md"

---

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

---

## Error Handling

- **Adzuna API down:** skip Channel A, continue with B + C, warn user
- **Gmail MCP unavailable:** skip Channel B, continue with A + C, warn user
- **Career page fetch fails:** logged per-page, never fatal
- **Scoring interrupted:** progress saved every 15 listings. Resume with `/pipeline review`.
- **No channels return results:** "No new listings today. Try adjusting search queries?"
- **Deduped CSV empty:** "All listings matched existing entries. Nothing new to score."
- **source.json missing:** "Resume source not found. Run Phase 2 setup first."

## Dependencies

- `/apply` skill -- application logging
- `/pitch` skill -- cold outreach email drafting (must have `~/.scout/profile.md` configured)
- `pipeline/resume.py` -- per-archetype resume generation
- `pipeline/discover.py` + `dedup.py` -- listing discovery
- Gmail MCP -- email alerts (Channel B) and outreach drafts (/pitch --with-gmail)
