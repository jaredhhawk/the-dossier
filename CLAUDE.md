# Scout Skill - Claude Code Project Context

**Project:** Scout - Hiring Signal Detection for Job Search
**Type:** Claude Code Skill
**Status:** In Development (Task 1)

---

## What This Is

A Claude Code skill that finds companies with recent hiring signals (funding, exec hires, product launches) and generates personalized outreach templates for pre-emptive job search.

**Problem:** Jobs at startups are often filled before postings exist. Signal-based outreach gets you in the room first.

**Solution:** Automated signal detection + personalized outreach generation.

---

## Project Documentation

- **Vault Doc:** `~/Documents/Second Brain/02_Projects/P - Scout Skill Development.md`
- **Strategy Context:** `~/Documents/Second Brain/02_Projects/Project Backlog/P - The Dossier/`
- **Integration Target:** `~/Documents/Second Brain/02_Projects/Job Search/R - Outreach Log.md`

---

## Tech Stack

- **Platform:** Claude Code skill system
- **Language:** Markdown-based prompts + Claude's tools (WebSearch, WebFetch, Read, Edit)
- **Data Sources:** Google News, TechCrunch, Crunchbase (via web search)
- **Integration:** Appends to Outreach Log markdown table
- **No external dependencies:** Pure Claude Code skill (no npm, no API keys, no hosting)

---

## Architecture

```
.claude/skills/scout/
├── SKILL.md              # Skill definition + main logic
├── signals.md            # Signal detection prompts (per signal type)
├── outreach.md           # Outreach template generation prompt
└── README.md             # User documentation

~/Documents/Second Brain/02_Projects/Job Search/
└── R - Outreach Log.md   # Integration target (markdown table)
```

**Skill invocation flow:**
1. User runs `/scout`
2. Read user profile from `~/.scout/profile.md` (optional for v1)
3. Search for signals (funding, exec hires, launches) via WebSearch
4. Parse results → structured data
5. Generate outreach templates
6. Return markdown output
7. Optional: `/scout log N` appends to Outreach Log

---

## Signal Types (Tier 1 - v1 Focus)

| Signal | Search Query Pattern | Freshness | Why It Works |
|--------|---------------------|-----------|--------------|
| **Funding** | `"PropTech" "Series B" "funding" site:techcrunch.com` | 30 days | New money = hiring within 30-90 days |
| **Exec Hires** | `"Real Estate Tech" "Chief Product Officer" "joins"` | 14 days | New execs build teams fast (14-60 days) |
| **Launches** | `"PropTech" "launches" "new product" -job` | 30 days | New products need dedicated teams |

---

## Development Approach

**Atomic commits:** Each task gets its own commit immediately when working.

**Task breakdown:**
1. **Task 1:** Funding signal detection only
2. **Task 2:** Add exec hire + launch signals
3. **Task 3:** Outreach template generation
4. **Task 4:** Outreach Log integration
5. **Task 5:** Real-world testing

**Verification before moving on:** Each task has clear test criteria.

**Fresh context between tasks:** Use `/clear` after completing each major task.

---

## Key Constraints

### v1 Scope Decisions

**✅ IN:**
- Tier 1 signals only (funding, exec hires, launches)
- Last 30 days freshness
- Web search as primary data source
- Manual review (no auto-filtering by relevance)
- Markdown output
- Simple Outreach Log integration

**❌ OUT (v2+):**
- Tier 2 signals (pivots, accelerators, etc.)
- War story matching/filtering
- Relevance scoring
- Automated monitoring/scheduling
- Gmail MCP integration
- Contact email discovery

### Design Principles

1. **Broad over filtered:** v1 shows all signals, user decides relevance (avoid premature optimization)
2. **Simple over automated:** v1 generates templates, user sends manually (build trust first)
3. **Testable pieces:** Each signal type can be tested independently
4. **No dependencies:** Pure Claude Code skill, no external APIs/packages

---

## User Profile (Optional for v1)

If `~/.scout/profile.md` exists, read it for context. Otherwise, use defaults.

**Expected format:**
```markdown
## Target Industries
- PropTech
- Real Estate Tech
- Construction Tech

## Company Stage
Series A - Series C

## Location
Seattle, Remote-first

## Your Pitch
Senior PM who built 0-to-1 products in PropTech
```

**v1 behavior:** If profile missing, just search "PropTech" broadly.

---

## Output Format

```markdown
# Scout Results - 2026-02-17

Found 8 companies with recent hiring signals:

---

## 1. Acme PropTech

**Signal:** Series B funding ($25M) announced Feb 15, 2026
**Source:** [TechCrunch](https://...)
**Company:** PropTech platform for commercial real estate
**Stage:** Series B, ~30 employees
**Why relevant:** Series B companies typically hire product leaders 30-90 days post-funding

**Suggested Outreach:**

Subject: Series B → Product Scaling

Hi [Founder name],

Saw the Series B news—congrats. The timing caught my attention because I led a similar inflection point at [Company]: took a vertical SaaS product from concept to $2M ARR in 18 months as first PM.

[Company]'s focus on [specific pain point] resonates—I solved a similar problem in [domain] by [specific approach].

If product scaling is on the roadmap post-raise, happy to share what worked.

[Your name]

---

## 2. [Next company...]
```

---

## Outreach Log Integration

**File:** `~/Documents/Second Brain/02_Projects/Job Search/R - Outreach Log.md`

**Current format:**
```markdown
| Date | Company | Contact | Title | Channel | Status | Follow-up | Notes |
|------|---------|---------|-------|---------|--------|-----------|-------|
```

**Scout appends:**
```markdown
| 2026-02-17 | Acme PropTech | TBD | Founder/CPO | LinkedIn | Drafted | 2026-02-24 | Signal: Series B $25M |
```

**Command:** `/scout log 1` (logs company #1 from results)

---

## Testing Approach

**Each task has clear success criteria:**

**Task 1 (Funding):**
- Run search → get 5+ funding announcements
- All within 30 days
- Source URLs work

**Task 2 (Exec + Launches):**
- Get mix of signal types (not just funding)
- At least 2 exec hires, 2 launches

**Task 3 (Outreach):**
- Generate for 3 different signals
- Each feels specific (mentions signal, company details)
- Tone is conditional ("if X is on roadmap"), not presumptuous

**Task 4 (Logging):**
- Log 3 companies
- Rows appear in correct format
- Follow-up date = today + 7 days

---

## Common Pitfalls to Avoid

1. **Don't over-engineer:** v1 is deliberately simple. Resist adding filtering, scoring, automation.
2. **Don't hallucinate dates:** LLMs are bad at dates. Always use `date:` operators in search queries.
3. **Don't send generic templates:** Each template must reference the specific signal + company.
4. **Don't auto-send anything:** v1 just generates templates. User sends manually.

---

## Git Workflow

**Branch:** main (no feature branches for solo project)

**Commit pattern:**
```bash
git add .
git commit -m "feat: funding signal detection"
```

**Commit after each working task.** Don't wait to batch commits.

---

## Success Criteria

**v1 is done when:**
- [ ] All 5 tasks complete (detection, templates, logging)
- [ ] User has run `/scout` 2+ times for real job search
- [ ] User has sent at least 1 outreach based on Scout results
- [ ] Code is committed and documented

**Then decide:** v2 (expand signals) or v3 (automation)?

---

## Related Files

- **Strategy:** See The Dossier project docs for product vision
- **Outreach Log:** Integration target at `~/Documents/Second Brain/02_Projects/Job Search/R - Outreach Log.md`
- **Vibe Coding:** Best practices at `~/Documents/Second Brain/04_Resources/R - Vibe Coding Best Practices.md`
