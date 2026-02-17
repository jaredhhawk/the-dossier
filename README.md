# Scout - Hiring Signal Detection for Job Search

A Claude Code skill that finds companies with recent hiring signals and generates personalized outreach templates.

---

## What Scout Does

**Problem:** Jobs at startups are often filled before postings exist.

**Solution:** Detect hiring signals (funding, exec hires, product launches) and reach out pre-emptively.

**Output:**
- List of companies with recent signals
- What the signal was (funding round, new CPO, product launch)
- Personalized outreach template for each
- One-command logging to your Outreach Log

---

## Quick Start

### Installation

1. Copy skill to Claude Code skills directory:
   ```bash
   cp -r .claude/skills/scout ~/.claude/skills/
   ```

2. (Optional) Create profile at `~/.scout/profile.md`:
   ```markdown
   ## Target Industries
   - PropTech
   - Real Estate Tech

   ## Company Stage
   Series A - Series C

   ## Location
   Seattle, Remote-first
   ```

### Usage

```bash
/scout              # Find companies with hiring signals
/scout log 1        # Log company #1 to your Outreach Log
```

---

## Example Output

```markdown
# Scout Results - 2026-02-17

Found 8 companies with recent hiring signals:

## 1. Acme PropTech

**Signal:** Series B funding ($25M) announced Feb 15, 2026
**Source:** TechCrunch
**Company:** PropTech platform for commercial real estate
**Stage:** Series B, ~30 employees

**Suggested Outreach:**

Subject: Series B → Product Scaling

Hi [Founder],

Saw the Series B news—congrats. The timing caught my attention
because I led a similar inflection at [Company]: took a vertical
SaaS product from concept to $2M ARR as first PM.

[Company]'s focus on [pain point] resonates—I solved similar
problems in [domain].

If product scaling is on the roadmap, happy to share what worked.
```

---

## Signal Types

### Tier 1 (v1)

- **Funding:** Series A/B/C announcements >$10M (last 30 days)
- **Exec Hires:** New CPO, CTO, VP Product/Eng (last 14 days)
- **Product Launches:** Major product announcements (last 30 days)

### Coming in v2

- Strategic pivots (AI integration, platform plays)
- Accelerator graduations
- Major customer wins
- Tech stack changes

---

## Development

See [CLAUDE.md](CLAUDE.md) for project context and development guidelines.

**Current status:** Task 1 (Funding signal detection)

**Roadmap:**
- [x] Task 1: Funding signals
- [ ] Task 2: Exec hire + launch signals
- [ ] Task 3: Outreach template generation
- [ ] Task 4: Outreach Log integration
- [ ] Task 5: Real-world testing

---

## Project Links

- **Vault Doc:** `~/Documents/Second Brain/02_Projects/P - Scout Skill Development.md`
- **Strategy:** `~/Documents/Second Brain/02_Projects/Project Backlog/P - The Dossier/`
- **Integration:** `~/Documents/Second Brain/02_Projects/Job Search/R - Outreach Log.md`

---

## License

Personal project - not for distribution.
