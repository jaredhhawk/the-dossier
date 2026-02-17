---
name: scout
description: Find companies with hiring signals and generate outreach templates
version: 1.0.0-alpha
---

# Scout - Hiring Signal Detection

Find companies with recent hiring signals (funding, exec hires, product launches) for pre-emptive job search outreach.

## Usage

```bash
/scout                    # Find companies with hiring signals
/scout log 1              # Log company #1 to Outreach Log (coming soon)
```

## What You Get

- Top 5-10 companies with recent hiring signals
- Signal type (funding, exec hire, launch) + date + source
- Company context (stage, product, team size)
- Personalized outreach template
- Ready to copy and send

## How It Works

1. Searches for Tier 1 hiring signals (last 30 days)
2. Parses company info from results
3. Generates personalized outreach for each
4. Returns formatted markdown

## Signal Types (v1)

- **Funding:** Series A/B/C announcements >$10M
- **Exec Hires:** New CPO, CTO, VP Product/Eng
- **Product Launches:** Major product announcements

---

# Implementation

When user runs `/scout`:

## Step 1: Search for Signals

Search for recent hiring signals in PropTech/Real Estate Tech:

**Funding signals:**
```
WebSearch: "PropTech" OR "Real Estate Tech" "Series A" OR "Series B" OR "Series C" "funding" "million" date:last30days
WebSearch: "PropTech" "raised" "$" "million" "led by" date:last30days site:techcrunch.com OR site:crunchbase.com
```

**Parse each result:**
- Company name
- Funding amount
- Funding date
- Series (A/B/C)
- Lead investor
- Source URL

## Step 2: Enrich Company Data (Optional)

For top results, fetch company homepage to get:
- Product description
- Team size
- Founded date
- Mission

Use WebFetch on company homepage URL.

## Step 3: Generate Outreach Templates

For each company, generate personalized outreach:

**Template structure:**
1. **Hook:** Reference the signal (funding/hire/launch)
2. **Connection:** "This reminds me of when I [relevant experience]"
3. **Value:** Specific problem you can solve
4. **Soft CTA:** "Happy to share what worked"

**Guardrails:**
- Use conditional language ("if X is on roadmap")
- Reference specific company details (not generic)
- Keep under 100 words
- Tone: peer-to-peer, not salesy

## Step 4: Format Output

Return markdown with:

```markdown
# Scout Results - [DATE]

Found [N] companies with recent hiring signals:

---

## 1. [Company Name]

**Signal:** [Type] ([Amount if funding]) announced [Date]
**Source:** [URL]
**Company:** [Description]
**Stage:** [Series X], ~[N] employees

**Suggested Outreach:**

Subject: [Hook related to signal]

[3-sentence template]

---

## 2. [Next company...]
```

---

# Current Implementation Status

**Task 1: Funding signal detection** ✅ IN PROGRESS
- Searches for funding announcements
- Parses company, amount, date, source
- Returns structured results

**Task 2: Exec + Launch signals** 🔜 NEXT
- Add exec hire search
- Add product launch search
- Combine with funding results

**Task 3: Outreach generation** 🔜 COMING
- Template generation prompt
- Personalization logic

**Task 4: Outreach Log integration** 🔜 COMING
- `/scout log N` command
- Append to R - Outreach Log.md
