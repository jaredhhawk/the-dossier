---
name: scout
description: Find companies with hiring signals and generate outreach templates
version: 1.0.0-alpha
---

# Scout - Hiring Signal Detection

Find companies with recent hiring signals (funding, exec hires, product launches) for pre-emptive job search outreach.

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

## Step 1: Read User Profile (Optional)

Try to read `~/.scout/profile.md`. If exists, parse:
- Target Industries (for search queries)
- Company Stage (for filtering)
- Your Pitch (for outreach context)

If file doesn't exist or can't be read, use defaults:
- Industries: ["PropTech", "Real Estate Tech", "FinTech", "B2B SaaS", "Enterprise Software"]
- Stages: ["Series A", "Series B", "Series C"]
- Pitch: "Experienced product leader"

## Step 2: Search for Funding Signals

For each target industry, search for recent funding announcements:

**Search query pattern:**
```
"[Industry]" ("Series A" OR "Series B" OR "Series C") "funding" OR "raised" "$" "million" date:last30days
```

**Example searches:**
```
"PropTech" ("Series A" OR "Series B" OR "Series C") "funding" OR "raised" "$" "million" date:last30days

"Real Estate Tech" ("Series A" OR "Series B" OR "Series C") "funding" OR "raised" "$" "million" date:last30days

site:techcrunch.com "startup" "funding" "Series B" "$" "million" date:last30days
```

**What to extract from each result:**
- Company name
- Industry/sector
- Funding amount (e.g., "$25M")
- Series (A/B/C)
- Funding date (as specific as possible)
- Lead investor (if mentioned)
- Source URL

**Parsing hints:**
- Look for patterns like: "[Company] raises $XM Series Y"
- Or: "[Company] closes $XM Series Y led by [VC]"
- Dates might be relative ("yesterday", "last week") or absolute ("February 15")

## Step 3: Format Results

Return results in this format:

```markdown
# Scout Results - [TODAY'S DATE]

Found [N] companies with recent funding signals:

**Search criteria:**
- Industries: [list from profile or defaults]
- Stages: [list from profile or defaults]
- Timeframe: Last 30 days

---

## 1. [Company Name]

**Signal:** Series [X] funding ($[Amount]) announced [Date]
**Source:** [URL]
**Industry:** [Industry/sector from article]
**Lead Investor:** [VC name if mentioned]

**Context:**
[Any additional context from the article: what they do, team size, previous funding, etc.]

**Next Steps:**
- Find decision maker (CEO, CPO, VP Product)
- Research company website
- Draft personalized outreach referencing this signal

---

## 2. [Next company...]

[Same format]

---

## Summary

- Total signals found: [N]
- By stage: Series A ([X]), Series B ([Y]), Series C ([Z])
- By industry: [breakdown]

**Recommended next steps:**
1. Review each company's website
2. Identify decision makers (LinkedIn, company About page)
3. Draft outreach referencing the funding signal
4. Send within 7-14 days of announcement (sweet spot)
```

## Step 4: Execution Notes

**Search strategy:**
- Run 3-5 searches (one per industry + one general startup funding search)
- Combine and deduplicate results
- Sort by date (most recent first)
- Return top 10-15 results

**If few results:**
- Expand to last 60 days (mention this in output)
- Broaden industry terms (e.g., "startup" instead of specific industry)

**If many results (>15):**
- Return top 15 most recent
- Note at bottom: "Found [total] signals, showing most recent 15"

---

# Current Status

**v1.0-alpha - Task 1: Funding Signal Detection**

✅ Configurable via user profile
✅ Searches multiple industries
✅ Returns structured results
🔜 Next: Exec hire + product launch signals (Task 2)
🔜 Next: Outreach template generation (Task 3)
🔜 Next: Outreach Log integration (Task 4)

---

When user runs `/scout`, execute all steps above and return formatted markdown results.
