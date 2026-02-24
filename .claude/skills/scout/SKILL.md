---
name: scout
description: Find companies with hiring signals and generate outreach templates
version: 1.1.0-alpha
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

## Step 1: Read User Profile and Seen List

**Profile:** Try to read `~/.scout/profile.md`. If exists, parse:
- Target Industries (for search queries)
- Company Stage (for filtering)
- Your Pitch (for outreach context)

If file doesn't exist or can't be read, use defaults:
- Industries: ["PropTech", "Real Estate Tech", "FinTech", "B2B SaaS", "Enterprise Software"]
- Stages: ["Series A", "Series B", "Series C"]
- Pitch: "Experienced product leader"

**Seen list:** Try to read `~/.scout/seen.md`. If exists, extract the list of company names. These will be filtered out of results in Step 3 to avoid showing the same companies across runs. If the file doesn't exist, proceed with no filter.

## Step 2: Search for Hiring Signals

Run all three signal type searches. Combine and deduplicate results across signal types before formatting.

### 2a. Funding Signals (last 30 days)

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

**What to extract:**
- Company name, industry, funding amount, series, date, lead investor, source URL

**Parsing hints:**
- Look for patterns like: "[Company] raises $XM Series Y"
- Or: "[Company] closes $XM Series Y led by [VC]"

### 2b. Exec Hire Signals (last 14 days)

New executives build teams fast — this is a tighter, more urgent window.

**Search query pattern:**
```
"[Industry]" ("Chief Product Officer" OR "VP Product" OR "VP Engineering" OR "CTO" OR "Chief Revenue Officer") ("joins" OR "named" OR "appointed" OR "hires") date:last14days
```

**Example searches:**
```
"PropTech" ("Chief Product Officer" OR "VP Product" OR "VP Engineering") ("joins" OR "named" OR "appointed") date:last14days

"Real Estate Tech" ("CTO" OR "Chief Revenue Officer" OR "VP Sales") ("joins" OR "hired" OR "appointed") date:last14days

site:techcrunch.com ("Chief Product Officer" OR "VP Product") "startup" ("joins" OR "named") date:last14days
```

**What to extract:**
- Company name, industry, exec name, exec title, hire date, source URL
- Any context about why they were hired or what they'll build

**Parsing hints:**
- Look for patterns like: "[Company] names [Person] as [Title]"
- Or: "[Person] joins [Company] as [Title]"

### 2c. Product Launch Signals (last 30 days)

New product launches signal growth and team-building ahead.

**Search query pattern:**
```
"[Industry]" ("launches" OR "announces" OR "introduces" OR "unveils") ("new product" OR "new platform" OR "new feature" OR "new service") -job -hiring date:last30days
```

**Example searches:**
```
"PropTech" ("launches" OR "announces" OR "unveils") ("new platform" OR "new product" OR "new service") -job date:last30days

"Real Estate Tech" ("launches" OR "introduces") ("AI" OR "platform" OR "tool") -job -hiring date:last30days

site:techcrunch.com "PropTech" "launches" date:last30days
```

**What to extract:**
- Company name, industry, what was launched, launch date, source URL
- Any context about the product and team behind it

## Step 3: De-duplicate and Format Results

**Before formatting:** Remove any company from the results whose name appears in `~/.scout/seen.md`. If a company is filtered, note the count at the top of the output (e.g., "Filtered 2 previously-seen companies").

Return results in this format:

```markdown
# Scout Results - [TODAY'S DATE]

Found [N] companies with recent hiring signals:

**Search criteria:**
- Industries: [list from profile or defaults]
- Signal types: Funding (30d), Exec Hires (14d), Product Launches (30d)

[If any companies were filtered:] Filtered [X] previously-seen companies.

---

## 1. [Company Name]

**Signal:** [One of the three formats below depending on signal type]

  Funding:  Series [X] funding ($[Amount]) announced [Date]
  Exec Hire: [Person] named [Title] ([Date])
  Launch:   Launched [product/feature name] ([Date])

**Signal Type:** [Funding | Exec Hire | Launch]
**Source:** [URL]
**Industry:** [Industry/sector from article]

[For funding only:]  **Lead Investor:** [VC name if mentioned]
[For exec hire only:] **Exec:** [Name], [Title]

**Context:**
[Any additional context from the article: what they do, team size, why this matters]

**Why relevant:**
[One sentence on the hiring implication: e.g. "New CPO typically builds a product team within 30-60 days" or "Series B companies typically hire product leaders 30-90 days post-funding"]

**Suggested Outreach:**

Subject: [Signal-specific subject line]

Hi [decision maker name or "there"],

[Opening: reference the specific signal — funding announcement, exec hire, or product launch. Be specific, not generic.]

[Middle: connect their situation to the user's experience. Use one concrete detail from the user's pitch. Make a specific parallel.]

[Close: conditional ask — "If [relevant challenge] is on the roadmap, I'd love to connect." Don't be presumptuous.]

[User name]

---

## 2. [Next company...]

[Same format]

---

## Summary

- Total signals found: [N]
- By signal type: Funding ([X]), Exec Hires ([Y]), Launches ([Z])
- By industry: [breakdown]

**Recommended next steps:**
1. Review each company's website
2. Identify decision makers (LinkedIn, company About page)
3. Draft outreach referencing the specific signal
4. Prioritize: Exec Hires (act within 7 days) > Funding (act within 14 days) > Launches (act within 30 days)
```

## Step 3.5: Generate Outreach Templates

For each company in the results, generate a personalized outreach email using the signal type and company context. If the profile has multiple "Pitch Angles," select the one most relevant to what this company does and what the signal implies they need — don't use the same angle for every company. Keep every template to 3 short paragraphs (~100 words total).

**Core principles:**
- Reference the specific signal (not generic "I saw your company") — use the actual funding amount, exec name, or product name
- Select the pitch angle from profile that best matches this company's domain and situation
- One concrete metric or achievement from the user's background that parallels their situation
- Conditional close — "if X is on the roadmap" — never assume they're hiring
- Placeholders in [brackets] for things the user must fill in (contact name, personal details)
- Write like a human, not AI. No buzzwords, no "I'm passionate about," no generic praise.
- Short. Founders don't read long emails.

---

### Template: Funding Signal

**Subject:** `[Series X] → [Relevant challenge: e.g. "Product Scaling" or "Platform Build"]`

```
Hi [Founder/CPO name],

Saw the [Series X] news—congrats on the raise. [One specific detail about what they do or their market focus].

[User pitch, adapted]: I [specific achievement relevant to their stage]. [Draw a parallel: "That inflection point—going from [X] to [Y]—is exactly what you're navigating now."]

If [product scaling / building out the team / platform expansion] is on the roadmap post-raise, happy to share what worked.

[User name]
```

---

### Template: Exec Hire Signal

**Subject:** `[Company] [exec role] → [relevant angle]`

```
Hi [Exec name],

Saw you just joined [Company] as [Title]—congrats. [One observation about what new [Title]s typically focus on in the first 90 days, or what this hire signals about the company's direction].

[User pitch, adapted]: I [specific experience relevant to what this exec will be building]. [Make a specific parallel to their likely priorities.]

If you're building your team, I'd love to be on your radar.

[User name]
```

---

### Template: Product Launch Signal

**Subject:** `[Company]'s [product name] → [relevant angle]`

```
Hi [Founder/CPO name],

Saw [Company] just launched [product/feature]. [One specific observation about what this launch signals — market move, new customer segment, scaling moment].

[User pitch, adapted]: I [specific experience with similar launch or product type]. [Draw a parallel to their situation.]

If finding [PMs / engineers / etc.] to grow [product name] is on the agenda, I'd love to connect.

[User name]
```

---

### Personalization Rules

1. **Always name the signal explicitly** — "the Series B news", "your new CPO hire", "the [product] launch"
2. **Use company-specific context** from the article — don't write generic praise
3. **Adapt user pitch to the signal** — funding = scaling experience, exec hire = team-building experience, launch = 0-to-1 experience
4. **Keep conditional language** — "if X is on the roadmap", "if you're building your team", "if this is on the agenda"
5. **Subject line formula:** `[What happened] → [Why it's relevant to them]`
6. **Length:** 3 paragraphs, ~100 words total. Founders don't read long emails.

---

## Step 4: Execution Notes

**Search strategy:**
- Run 6-9 searches total: 2-3 per signal type (one per major industry + one general)
- Combine and deduplicate results across all signal types
- Sort by date (most recent first), with exec hires prioritized within same date
- Return top 10-15 results

**If few results:**
- Expand to last 60 days for funding/launches (mention this in output)
- Broaden industry terms (e.g., "startup" instead of specific industry)

**If many results (>15):**
- Return top 15 most recent
- Note at bottom: "Found [total] signals, showing most recent 15"

**Signal type prioritization (when trimming):**
- Exec hires first (shortest action window)
- Funding second
- Launches third

## Step 5: Save Run Output and Update Tracking

After displaying results to the user, do all three of the following:

### 5a. Write run file

Create (or overwrite) `~/.scout/runs/YYYY-MM-DD.md` with the full formatted output from Step 3, exactly as displayed to the user. Create the `~/.scout/runs/` directory if it doesn't exist.

### 5b. Append to Outreach Log

File: `~/Documents/Second Brain/02_Projects/Job Search/R - Outreach Log.md`

For each company in the results (new companies only — skip any already in the Outreach Log's Company column), append a row to the **Active Outreach** table:

```
| [YYYY-MM-DD] | [Company] | TBD | TBD | | New Lead | [YYYY-MM-DD + 7 days] | Signal: [type] [amount] |
```

- Date = today
- Contact, Title = TBD (user fills in)
- Channel = blank (not sent yet)
- Status = "New Lead"
- Follow-up = today + 7 days
- Notes = "Signal: [funding/exec/launch] [amount if applicable]"

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

**v1.2-alpha - Task 3: Outreach Template Generation**

✅ Configurable via user profile
✅ Searches multiple industries
✅ Funding signals (last 30 days)
✅ Exec hire signals (last 14 days)
✅ Product launch signals (last 30 days)
✅ Mixed signal type output with "Why relevant" per entry
✅ De-duplicates via ~/.scout/seen.md
✅ Writes run file to ~/.scout/runs/YYYY-MM-DD.md
✅ Appends new leads to R - Outreach Log.md
✅ Signal-specific outreach templates per company (funding / exec hire / launch)
✅ Templates personalized from user profile pitch
✅ Conditional tone throughout ("if X is on roadmap")

---

When user runs `/scout`, execute all steps above and return formatted markdown results.
