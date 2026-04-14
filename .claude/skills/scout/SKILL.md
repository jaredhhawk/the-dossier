---
name: scout
description: Find companies with hiring signals and output structured signal data for /dossier
version: 2.2.0
---

# Scout - Hiring Signal Detection

Find companies with recent hiring signals (funding, exec hires, product launches, strategic pivots, and more) for pre-emptive job search outreach.

## Setup (Optional)

Create `~/.scout/profile.md` to customize your search:

```markdown
## Target Industries
- PropTech
- Real Estate Tech
- FinTech

## Company Stage
- Series A
- Series B

## Your Pitch
Senior PM who built 0-to-1 products in vertical SaaS
```

See `.claude/skills/scout/profile-template.md` for full example.

**If no profile:** Scout uses broad defaults (searches multiple industries).

## Usage

```bash
/scout                    # Find companies with hiring signals
```

---

# Implementation

## Step 1: Load Profile, Filters, and Negative Signals

### 1a. Profile, Seen List, Blacklist, Outreach Log

**Profile:** Try to read `~/.scout/profile.md`. If exists, parse:
- Target Industries (for search queries)
- Company Stage (for filtering)
- Your Pitch (for outreach context)

If file doesn't exist or can't be read, use defaults:
- Industries: ["PropTech", "Real Estate Tech", "FinTech", "B2B SaaS", "Enterprise Software"]
- Stages: ["Series A", "Series B", "Series C"]
- Pitch: "Experienced product leader"

**Seen list:** Try to read `~/.scout/seen.md`. Extract company names. These are filtered in Step 3 to avoid re-surfacing companies across runs. If file doesn't exist, proceed with no filter.

**Blacklist:** Try to read `~/.scout/blacklist.md`. Extract company names. Permanently excluded from all results — never surface, never add to seen list.

**Outreach Log pre-filter:** Try to read `~/Documents/Second Brain/02_Projects/Job Search/Scout + Dossier/R - Outreach Log.md`. Extract all company names present in any section. Filter these in Step 3 — no need to resurface companies already in the pipeline.

### 1b. Negative Signal Pre-Check

Before searching for positive signals, build a **skip list** and **flag list** from negative signals.

**Skip list (exclude from results entirely):**

Search for recent layoffs in target industries:
```
site:layoffs.fyi [Industry] 2025 OR 2026
site:layoffs.fyi "real estate" OR "proptech" OR "construction tech" 2025 OR 2026
"[Industry]" ("layoffs" OR "workforce reduction" OR "cuts jobs" OR "downsizing") 2025 OR 2026
```

Extract company names with confirmed layoffs. Add to skip list.

**Flag list (surface with ⚠️ warning, don't skip):**

Search for exec departures and acquisitions:
```
"[Industry]" ("CPO departs" OR "VP Product leaves" OR "Chief Product Officer resigns" OR "steps down") 2025 OR 2026
"[Industry]" ("acquired by" OR "acquisition" OR "to be acquired") 2025 OR 2026
```

Extract company names. These get surfaced in results with an ⚠️ flag and a note explaining the risk.

---

## Step 2: Search for Hiring Signals

Run all signal searches. Combine and deduplicate results across signal types before formatting. Add `2025 OR 2026` to all queries as a soft recency nudge — do not use `date:` filters.

### Tier 1 Signals

#### 2a. Funding Signals

Search for recent funding announcements across target industries:

**Search query pattern:**
```
"[Industry]" ("Series A" OR "Series B" OR "Series C") ("funding" OR "raised" OR "closes") "$" "million" 2025 OR 2026
```

**Example searches:**
```
"PropTech" ("Series A" OR "Series B" OR "Series C") "raised" "$" "million" 2025 OR 2026

"Real Estate Tech" ("Series A" OR "Series B" OR "Series C") "funding" "$" "million" 2025 OR 2026

site:techcrunch.com "startup" "funding" "Series B" "$" "million" 2025 OR 2026
```

**What to extract:**
- Company name, industry, funding amount, series, signal date, lead investor, source URL

**Parsing hints:**
- "[Company] raises $XM Series Y"
- "[Company] closes $XM Series Y led by [VC]"

---

#### 2b. Exec Hire Signals

New executives build teams fast — highest urgency signal type.

**Search query pattern:**
```
"[Industry]" ("Chief Product Officer" OR "VP Product" OR "VP Engineering" OR "CTO" OR "Chief Revenue Officer") ("joins" OR "named" OR "appointed" OR "hires") 2025 OR 2026
```

**Example searches:**
```
"PropTech" ("Chief Product Officer" OR "VP Product" OR "VP Engineering") ("joins" OR "named" OR "appointed") 2025 OR 2026

"Real Estate Tech" ("CTO" OR "Chief Revenue Officer" OR "VP Sales") ("joins" OR "hired" OR "appointed") 2025 OR 2026

site:techcrunch.com ("Chief Product Officer" OR "VP Product") "startup" ("joins" OR "named") 2025 OR 2026
```

**What to extract:**
- Company name, industry, exec name, exec title, signal date, source URL
- Any context about why they were hired or what they'll build

**Parsing hints:**
- "[Company] names [Person] as [Title]"
- "[Person] joins [Company] as [Title]"

---

#### 2c. Product Launch Signals

New product launches signal growth and team-building ahead.

**Search query pattern:**
```
"[Industry]" ("launches" OR "announces" OR "introduces" OR "unveils") ("new product" OR "new platform" OR "new feature" OR "AI") -job -hiring 2025 OR 2026
```

**Example searches:**
```
"PropTech" ("launches" OR "announces" OR "unveils") ("new platform" OR "new product" OR "AI") -job 2025 OR 2026

"Real Estate Tech" ("launches" OR "introduces") ("AI" OR "platform" OR "tool") -job -hiring 2025 OR 2026

site:techcrunch.com "PropTech" "launches" 2025 OR 2026
```

**What to extract:**
- Company name, industry, what was launched, signal date, source URL

---

### Tier 2 Signals

#### 2d. YC / Accelerator Graduates

Accelerator graduates are well-funded, founder-accessible, and actively hiring. Use explicit source queries for precision.

**Search queries:**
```
site:ycombinator.com/companies proptech 2025 OR 2026

site:ycombinator.com/companies "real estate" OR "construction" OR "property" 2025 OR 2026

"Y Combinator" OR "Techstars" OR "a16z Speedrun" ("proptech" OR "real estate tech" OR "construction tech") 2025 OR 2026
```

**What to extract:**
- Company name, batch (e.g., YC W25), what they build, signal date, source URL

---

#### 2e. Strategic Pivots / AI Rebrands

Companies announcing a pivot to AI, a new enterprise tier, or a platform expansion typically need a PM to lead the new direction.

**Search queries:**
```
"[Industry]" ("pivoting to AI" OR "AI-native" OR "launches enterprise" OR "expands into" OR "new platform strategy") 2025 OR 2026

"B2B SaaS" ("pivots" OR "transforms" OR "relaunches" OR "rebrands") ("AI" OR "enterprise" OR "platform") 2025 OR 2026
```

**What to extract:**
- Company name, what the pivot is, signal date, source URL

---

#### 2f. Enterprise Customer Wins

A major customer deal or partnership announcement signals the company is scaling to deliver — and needs product leadership to support it.

**Search queries:**
```
"[Industry]" ("signs" OR "wins" OR "selected by" OR "partners with") ("enterprise" OR "Fortune 500" OR "major deal") 2025 OR 2026

"Construction Tech" OR "PropTech" ("contract" OR "deal" OR "selected") ("city" OR "government" OR "enterprise") 2025 OR 2026
```

**What to extract:**
- Company name, customer/partner name, deal context, signal date, source URL

---

## Step 2.5: GitHub Signal Enrichment

For every company found in Steps 2a-2f, call the local helper to pull public GitHub activity:

```
python3 ~/.scout/github_signals.py "<company name>"
```

The helper fuzzy-matches the company name to a GitHub org slug, then returns the org's primary stack, recently active repos, new repos in the last 30 days, contributor trend on the main product repo, and top contributors in the last 90 days. Results are cached for 7 days.

**What to extract and include in Step 3 output:**
- **New repos (30d):** if any non-meta public repos were created in the last 30 days, list up to 3 by name with the one-line description.
- **Contributor trend:** if `change_pct` is ≥ +50% or ≤ -50% on the main repo, call it out (e.g., "Contributors on `main-repo` jumped from 6 to 14 in last 30d").
- **Primary stack:** top 2-3 languages.
- **Main repo activity:** name of the main repo and last commit date, only if the repo was pushed in the last 30 days.

**Silence rules:**
- If the helper reports "No public GitHub org found," skip the enrichment block entirely for that company. Do not invent or speculate.
- If the helper succeeds but all signals are null/empty, include a one-line "Primary stack" only, or skip if that is also absent.
- Never include raw JSON in the output. Convert to prose bullets.

**Rate limit:** the helper caps at ~5 API calls per company. Unauthenticated GitHub API allows 60 requests per hour. For runs larger than ~10 companies, add a Personal Access Token at `~/.scout/github_token` (single line, no scopes needed) to raise the ceiling to 5,000/hr.

---

## Step 3: Filter, Flag, and Format Results

### Filtering

Before formatting, remove or flag each company:

| Source | Action |
|--------|--------|
| `~/.scout/blacklist.md` | Skip — permanent exclusion |
| `~/.scout/seen.md` | Skip — already surfaced in a prior run |
| Outreach Log (any section) | Skip — already in pipeline |
| Negative skip list (Step 1b layoffs) | Skip — company contracting |
| Negative flag list (Step 1b departures/acquisitions) | Surface with ⚠️ and risk note |

Note filtered counts at top of output: "Filtered [X] companies: [breakdown by reason]"

### Urgency Flags

For each result, extract the signal date from the article. Assign an urgency flag based on days since signal:

| Days Since Signal | Flag | Label |
|-------------------|------|-------|
| 0–7 days | 🔥 | Act now |
| 8–30 days | ⚠️ | Move fast |
| 31–90 days | 📌 | Still relevant |
| 90+ days | 🗓️ | Stale — review before acting |

If signal date cannot be determined from the article, note "Date unknown" and assign 📌 by default.

### Output Format

```markdown
# Scout Results - [TODAY'S DATE]

**Filtered:** [X] companies removed ([breakdown: Y blacklisted, Z previously seen, W already in pipeline, V layoff/negative signal])
**Stale signals (90+ days):** [N] of [total shown] — [% stale]

---

## 1. [Company Name] [⚠️ if flagged]

**Signal:** [Description of the signal]
**Signal Type:** [Funding | Exec Hire | Launch | YC/Accelerator | Strategic Pivot | Customer Win]
**Signal Date:** [YYYY-MM-DD or "~Month YYYY"] [urgency flag]
**Source:** [URL]
**Industry:** [Industry/sector]

[For funding:] **Amount:** $[X]M Series [Y] | **Lead Investor:** [VC name if mentioned]
[For exec hire:] **Exec:** [Name], [Title]
[For YC:] **Batch:** [W25 / S24 / etc.]
[If flagged ⚠️:] **Risk:** [e.g., "CPO departure Feb 2026 — leadership in transition" or "Acquisition pending — runway uncertain"]

**Context:**
[2-3 sentences: what the company does, why this signal matters, team size if known]

**Why relevant:**
[One sentence on the hiring implication — e.g., "New CPO typically builds a product team within 30-60 days" or "YC W25 companies are actively hiring through demo day prep"]

[If GitHub enrichment returned signals, include this block. Omit entirely if no GitHub org found or no meaningful signals.]

**Engineering Signals (GitHub):**
- Primary stack: [Top 2-3 languages]
- [Only if new_repos_30d non-empty] New repos (30d): `repo-name` — [one-line description]
- [Only if contributor_trend change_pct ≥ +50% or ≤ -50%] Contributor trend on `main-repo`: [baseline] → [current] ([+/-change_pct]%) in last 30d
- [Only if main repo pushed in last 30d] Main repo: `main-repo` (last commit [YYYY-MM-DD])

---

## 2. [Next company...]

[Same format]

---

## Summary

- **Total shown:** [N]
- **By signal type:** Funding ([X]) | Exec Hires ([Y]) | Launches ([Z]) | YC/Accel ([A]) | Pivots ([B]) | Customer Wins ([C])
- **By urgency:** 🔥 Act now ([X]) | ⚠️ Move fast ([Y]) | 📌 Still relevant ([Z]) | 🗓️ Stale ([W])
- **Stale rate:** [W/N]% — [if >25%: "⚠️ Elevated stale rate — consider checking search query freshness"]
- **Filtered:** [X] companies removed
- **By industry:** [breakdown]

**Priority order for outreach:**
1. 🔥 Exec hires (act within 7 days — team builds fast)
2. 🔥/⚠️ YC/Accelerator graduates (founders accessible, active hiring)
3. ⚠️ Funding (act within 30 days — hiring wave incoming)
4. ⚠️ Strategic pivots (PM role often created for the new direction)
5. 📌 Launches + Customer wins (lower urgency, still valid)
```

---

## Step 4: Execution Notes

**Search strategy:**
- Run 8-12 searches total across Tier 1 and Tier 2 signal types
- Always add `2025 OR 2026` — no `date:` filters (unreliable)
- Combine and deduplicate across all signal types
- Sort by urgency flag first, then signal date (most recent first)
- No hard cap on results — return all companies that pass filtering

**Output format by urgency tier:**
- 🔥 and ⚠️ results: full detail format (signal, date, context, why relevant)
- 📌 and 🗓️ results: compact one-liner format (company, signal type, date, one sentence context)
- Group output: all 🔥 first, then ⚠️, then 📌/🗓️ as a compact block at the end
- This keeps the high-priority items readable without truncating the full pipeline

**If few results (< 8):**
- Broaden industry terms (e.g., "SaaS" instead of specific vertical)
- Try alternative phrasings ("raises" vs "funding" vs "closes round")
- Check YC batch list directly at ycombinator.com/companies

**Stale signal monitoring:**
- Track stale rate (90+ day signals / total shown) in every run summary
- If stale rate exceeds 25% across 2+ consecutive runs, note it to the user — may indicate search queries need freshening or a different industry mix
- The seen list prevents stale companies from re-surfacing, so a one-time stale result is fine

**Signal type prioritization (for urgency tier assignment when date is ambiguous):**
1. Exec hires (shortest action window)
2. YC/Accelerator graduates
3. Funding
4. Strategic pivots
5. Launches + Customer wins

---

## Step 5: Save Run Output and Update Tracking

After displaying results to the user, do all three of the following:

### 5a. Write run file

Save the full formatted output from Step 3 to **both** locations:

1. `~/.scout/runs/YYYY-MM-DD.md` — for automation/dedup (create directory if needed)
2. `~/Documents/Second Brain/02_Projects/Job Search/Scout + Dossier/Scout Runs/YYYY-MM-DD.md` — for Obsidian browsing

Then update the index file at `~/Documents/Second Brain/02_Projects/Job Search/Scout + Dossier/Scout Runs/R - Scout Runs Index.md` — prepend a new row to the Run History table:
```
| YYYY-MM-DD | [N companies] | [stale rate %] | [top signal — company + signal detail] | [[YYYY-MM-DD]] |
```

Note: add `Stale %` as a new column if it doesn't exist yet.

### 5b. Append to Outreach Log

File: `~/Documents/Second Brain/02_Projects/Job Search/Scout + Dossier/R - Outreach Log.md`

For each company in the results (new companies only — skip any already in the Outreach Log), append a row to the **## In Flight** section:

```
| [YYYY-MM-DD] | [Company] | TBD | [Signal Type] | | New Lead | [YYYY-MM-DD + 7 days] | Signal: [type] — [brief detail] [urgency flag] |
```

- Date = today
- Contact = TBD (user fills in via /dossier)
- Signal Type column = signal type from results
- Stage = "New Lead"
- FU1 = today + 7 days
- Notes = "Signal: [funding $XM / exec hire [name] / YC W25 / etc.] [urgency flag]"

### 5c. Update seen list

File: `~/.scout/seen.md`

Append each new company from this run's results to the seen list. Create the file if it doesn't exist.

Format:
```markdown
# Scout Seen Companies

- [Company Name] (YYYY-MM-DD)
- [Company Name] (YYYY-MM-DD)
```

---

# Current Status

### Changelog

**v2.2.0 — 2026-04-13 — GitHub enrichment, Claude Code as executor**
- Added Step 2.5: GitHub Signal Enrichment. Calls `~/.scout/github_signals.py` per company to pull primary stack, new repos, contributor trends, main repo activity.
- Enrichment is additive — does not gate filtering, ranking, or inclusion.
- Output format extended with "Engineering Signals (GitHub)" block per company (omitted when no data).
- Rate limit note: add a PAT at `~/.scout/github_token` for runs >10 companies.
- Scout now runs exclusively on Claude Code (Max plan). Gemini CLI copy at `.gemini/skills/scout/` is dormant.

**v2.1.0 — 2026-03-03 — No result cap, tiered output format**
- Removed hard 10-15 result cap — return all companies that pass filtering
- Full detail for 🔥/⚠️ results; compact one-liner for 📌/🗓️ results
- Output grouped by urgency tier (🔥 first, compact block at end)
- Rationale: scout feeds a batch pipeline; filtering already handles quality; urgency tiers make large lists scannable

**v2.0.0 — 2026-03-03 — Expanded signals, negative filtering, date ceiling removed**
- Tier 1 signals: Funding, Exec Hires, Product Launches (unchanged)
- Tier 2 signals added: YC/Accelerator graduates, Strategic pivots/AI rebrands, Enterprise customer wins
- Negative signal filtering: layoff skip list (layoffs.fyi queried explicitly), exec departure + acquisition flags (⚠️ surface with risk note, don't skip)
- Date ceiling removed — no hard cutoff, `2025 OR 2026` soft recency nudge instead of `date:` filters
- Signal date extracted per result with urgency flag (🔥 0-7d / ⚠️ 8-30d / 📌 31-90d / 🗓️ 90+d)
- Stale rate tracked per run — alerts if >25% across consecutive runs
- Explicit source targeting: site:ycombinator.com for YC, layoffs.fyi for negatives
- Scout Runs Index updated with Stale % column

**v1.3.0 — prior — Pipeline-ready signal output**
- Configurable via user profile
- Tier 1 signals: Funding (30d), Exec Hires (14d), Product Launches (30d)
- Pre-filter: blacklist, seen list, Outreach Log (pipeline dedup)
- De-duplicates via ~/.scout/seen.md
- Writes run file to ~/.scout/runs/YYYY-MM-DD.md + Obsidian vault
- Appends new leads to R - Outreach Log.md

**All versions:**
❌ Outreach copy not generated here — drafting is /dossier's responsibility

**Roadmap:** See vault → `02_Projects/Job Search/Scout + Dossier/P - Outreach Automation.md`

---

When user runs `/scout`, execute all steps above and return formatted markdown results.
