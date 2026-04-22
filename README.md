# The Dossier

A three-agent agentic pipeline for pre-emptive job search outreach, built on Claude Code.

**Scout** monitors the market for hiring signals across 6 signal types and maintains a deduplicated, urgency-scored pipeline of target companies. **Pitch** takes a company and a signal and produces a credible first-touch cold email with light research (~3k tokens). **Dossier** runs deep research + strategy on a company when it's earned: a reply landed, you're applying through a portal, or you're prepping a real conversation.

---

## Why Three Skills

Cold outreach has a ~10-15% reply rate. If you run a full research brief on every contact before sending, you're paying deep-research tokens on the 85-90% who never reply.

The split tiers research to where it belongs:
- **`/pitch`** (~3k tokens) — enough to send a credible first-touch; 1 angle, 1 war story, no deep analysis
- **`/dossier`** (~10k tokens) — full Strategic Pivot Gaps, multi-angle comparison, war story scoring; run on the contacts who matter

Across a realistic funnel (10 cold touches, 1 reply → 1 dossier), this saves ~60% of tokens vs. running `/dossier` on everything upfront — without sacrificing depth where it counts.

---

## How It Works

```
/scout                          →  finds companies with hiring signals
                                   →  logs them to the outreach pipeline

/pitch [company]                →  light research (3 sources max)
                                   →  pick 1 angle + 1 war story
                                   →  draft ~100-word email + LinkedIn snippet
                                   →  optional Gmail draft

/dossier [company]              →  deep research (up to 12 sources + GitHub signals)
                                   →  full "what we know / infer / don't know"
                                   →  angle comparison + war story scoring
                                   →  no cold email drafting (that's /pitch's job)

/dossier [company] --apply      →  deep research + cover letter + resume tweaks
                                   →  + LinkedIn snippet to recruiter
                                   →  optional Gmail draft of cover letter
```

Skills share state: Scout seeds the outreach log; Pitch and Dossier read signal context from the last Scout run, check the log for existing threads, and update log notes with depth markers (`Pitch [date]` / `Dossier [date]`) so you can see at a glance which contacts had lite vs. deep research.

---

## Scout

Scans for hiring signals across your target industries and stages. Filters negatives before surfacing results.

### Signal Types

**Tier 1 — Act fast**
- **Funding** — Series A/B/C announcements (surfaced within days of announcement)
- **Exec Hires** — New CPO, CTO, VP Product/Engineering (7-day action window — new execs build teams fast)
- **Product Launches** — Major product or platform announcements

**Tier 2 — Strong signal, longer window**
- **YC / Accelerator Graduates** — Actively hiring, founder-accessible
- **Strategic Pivots / AI Rebrands** — Companies announcing AI-native direction or new platform plays
- **Enterprise Customer Wins** — Major deal or partnership signals scaling demand

### Negative Signal Filtering

Before surfacing results, Scout queries for negative signals and applies them automatically:

- **Skip list** — Companies with confirmed layoffs (queried directly from layoffs.fyi) are excluded entirely
- **Flag list** — Companies with exec departures or acquisition announcements are surfaced with a `⚠️ Risk` note rather than silently dropped

### GitHub Enrichment

For every company found, Scout calls a local helper (`~/.scout/github_signals.py`) that fuzzy-matches the company to a public GitHub org and pulls:
- Primary stack (top languages)
- New repos created in last 30 days
- Contributor trend on the main product repo (≥ ±50% changes are called out explicitly)
- Main repo last-push date if recent

Silent when the org isn't found. Cached 7 days.

### Deduplication

Scout maintains a seen list (`~/.scout/seen.md`) and reads your Outreach Log on every run. Companies already in your pipeline are filtered out automatically — you only see net-new leads.

### Urgency Scoring

Every result is assigned an urgency flag based on days since the signal:

| Flag | Window | Label |
|------|--------|-------|
| 🔥 | 0–7 days | Act now |
| ⚠️ | 8–30 days | Move fast |
| 📌 | 31–90 days | Still relevant |
| 🗓️ | 90+ days | Stale — review before acting |

---

## Pitch

Fast first-touch cold outreach. Pairs with Scout (pulls signal context from the last Scout run) and hands off to Dossier when someone replies.

### Usage

```bash
/pitch [company]                         # Signal + contact + email + LinkedIn snippet
/pitch [company] --with-gmail            # + Gmail draft
/pitch [company] --no-log                # Skip Outreach Log update
/pitch [company] --follow-up             # Headless follow-up (FU1/FU2 auto-detected)
/pitch [company] --follow-up --with-gmail
```

### What Pitch Produces

**Signal + Angle** — Line-item reference to the signal with date + source, one-sentence implication, the selected pitch angle, the selected war story. Stale-signal guardrail: if the signal is >90 days old, Pitch refuses and recommends Dossier instead.

**Contact** — Name + LinkedIn search string + email with a confidence tag (`HIGH` found on contact page, `MEDIUM` pattern inference with confirmed domain, `LOW` pattern inference with uncertain domain).

**Email Draft** — ~100-word cold email: signal-specific hook, war story with metric and named functional parallel, close calibrated to your `outreach_posture` (Direct/Advisory/Exploratory). No em-dashes, no banned words, always signed with a fractional-PM P.S. by default.

**LinkedIn Snippet** — 50–75 word DM version of the same angle, cast for how LinkedIn gets skimmed.

### Research Discipline

Pitch is capped at 3 sources:
1. Company homepage (confirm positioning)
2. Signal confirmation (verify the Scout signal is real and current)
3. Contact / About page (email format)

Never pulls GitHub, SEC filings, exec LinkedIn backgrounds, or multiple news articles — those are Dossier's domain.

### Follow-Up and Bounce Recovery

Pitch inherits the follow-up and bounce-recovery protocols from the original Dossier:
- **5+ business days, no reply** — offers follow-up mode: ≤75-word reply to the original thread with one new piece of value
- **Bounced email** — offers bounce recovery: alternate email patterns or LinkedIn DM fallback, fresh draft on the new channel

---

## Dossier

Deep company research + strategy, on demand. **Does not draft cold outreach** (that's Pitch). Used when:
- Someone replied and you need the full picture before responding
- You're applying through the job portal and need a tailored cover letter + resume tweaks
- You want to prep an angle for an inbound conversation

### Usage

```bash
/dossier [company]                                # Sections 1-4: research + strategy + arsenal
/dossier [company] --apply                        # + Cover letter + LinkedIn (to recruiter) + resume tweaks
/dossier [company] --apply --resume=[path]        # + line-level resume suggestions
/dossier [company] --apply --with-gmail           # + Gmail draft of cover letter
/dossier [company] --depth=[lean|standard|deep]   # Override research depth
```

### What Dossier Produces

**Section 1 — Company Intelligence**
Structured research brief with sourced facts (≥3 non-signal facts, ≥1 third-party), confidence-scored inferences (High/Medium/Low with rationale, ≥1 addressing execution risk), and named Strategic Pivot Gaps in a required "if A then Angle X / if B then Angle Y" format. Flags conflicting signals (e.g., funding announcement alongside LinkedIn hiring freeze mention) with a `⚠️ HIGH RISK` banner before proceeding.

**Section 2 — Recommended Contact**
Target title derived from your seniority preference and the recommended angle. LinkedIn search string. Email pattern with confidence rating. Notes that actually drafting the email is `/pitch`'s job.

**Section 3 — Angle Analysis**
2–3 genuinely distinct angles, each scored by confidence and mapped to your background. Ranking is influenced by your persona settings (`outreach_posture`, `risk_tolerance`). Includes a timing window specific to signal type (exec hire: 7 days; funding: 14 days; launch: 30 days).

**Section 4 — Your Arsenal**
Your war stories scored against the company context on 4 dimensions: industry overlap, stage similarity, functional similarity, signal alignment. Top 2–3 surfaced with scores and a rationale that names the functional parallel explicitly (not just "both PropTech").

**Apply mode only:**

**Section 5 — Cover Letter**
200–250 word cover letter opening with a company-specific observation (never "I am applying for"), mapping the top two JD requirements to your war stories. Same no-em-dashes / no-banned-words rules as Pitch.

**Section 6 — LinkedIn Snippet to Recruiter / Hiring Manager**
50–75 word LinkedIn DM to the recruiter or hiring manager — the "double-tap" on the application, aimed at getting it noticed. Distinct audience from Pitch's cold-outreach snippet.

**Section 7 — Resume Tweaks**
Direct yes/no on whether customization is worth it, followed by up to 5 targeted suggestions with current text, suggested replacement, and rationale. Flags ATS keyword gaps specific to this JD.

### Research Depth

| Depth | Max Sources | Token Budget | Extras |
|-------|-------------|--------------|--------|
| lean | 5 | ~3k | No GitHub enrichment |
| standard | 8 | ~6k | GitHub enrichment, technical posture |
| deep | 12 | ~10k | + exec backgrounds, product docs, competitor comparison |

### Outreach Log Behavior

Dossier never creates new rows in the Outreach Log — that's Pitch's job. Dossier only appends `; Dossier [date]` to the Notes column of an existing row, signaling that deep research was done on this contact. Rows with `Pitch [date]` but no `Dossier [date]` = lite research only; run Dossier before responding to a reply.

---

## Profile-Driven Personalization

All three skills read `~/.scout/profile.md` — a single file where you define:

- Target industries, company stages, geography
- Background summary and pitch angles
- War stories in Situation/Action/Result format (scored and ranked per company)
- Persona calibration: `outreach_posture` (Direct/Advisory/Exploratory), `target_seniority`, `risk_tolerance`
- Tone notes
- Research depth default

See `templates/profile-template.md` for the full format.

---

## Architecture

```
the-dossier/
├── .claude/skills/
│   ├── scout/SKILL.md            # Scout — signal detection
│   ├── pitch/SKILL.md            # Pitch — first-touch cold outreach
│   ├── dossier/SKILL.md          # Dossier — deep research + apply mode
│   ├── pipeline/SKILL.md         # Pipeline — daily orchestration (v1.1.0)
│   └── apply/SKILL.md            # Apply — application logging
├── pipeline/
│   ├── discover.py               # Adzuna API + career page discovery
│   ├── careers.py                # Career page monitor + seeding
│   ├── dedup.py                  # Three-level dedup engine
│   ├── resume.py                 # Per-archetype resume tailoring + PDF
│   ├── bootstrap.py              # One-time ledger seeder
│   ├── scoring_prompt.md         # Scoring dimensions reference
│   ├── config.yaml               # All configuration
│   └── data/
│       ├── ledger.tsv            # Dedup ledger
│       ├── listings/             # Daily discovery CSVs
│       ├── scored/               # Daily scored JSONs
│       └── resumes/
│           ├── source.json       # Structured resume
│           └── output/           # Generated PDFs
├── templates/
│   └── profile-template.md       # User profile template
├── scenarios/
│   └── dossier-scenarios.md      # Behavioral test cases
└── README.md

~/.scout/
├── profile.md                    # Your profile (not in repo — personal)
├── seen.md                       # Dedup list across Scout runs
├── blacklist.md                  # Permanent exclusions
├── github_signals.py             # GitHub enrichment helper
├── github_token                  # Optional PAT (raises API ceiling 60 → 5000/hr)
└── runs/
    └── YYYY-MM-DD.md             # Scout run archives
```

Skills are invoked via Claude Code (`/scout`, `/pitch`, `/dossier`, `/pipeline`, `/apply`). The pipeline requires an Adzuna API key (free tier); everything else runs entirely within your local Claude Code session.

---

## Example: End-to-End Flow

```bash
# Morning
$ /scout
# → 8 new companies appended to Outreach Log as `Stage=New Lead`

# Pick 3 worth pursuing
$ /pitch Meridian --with-gmail
# → Signal + contact + 100-word email; Gmail draft created; log row updated to
#   `Stage=Drafted`, Notes: `; Pitch 2026-04-14; draft_id: r8721...`

$ /pitch Fieldstone --with-gmail
$ /pitch BuildPath --with-gmail
# → Review in Gmail, edit if needed, send manually

# A week later — Meridian replies
$ /dossier Meridian
# → Full research brief; Notes updated: `; Pitch 2026-04-14; Dossier 2026-04-21`
# → Read the brief, draft a personal reply in Gmail

# Found a Fieldstone job posting you want to apply to
$ /dossier Fieldstone --apply --resume=~/resume.md --with-gmail
# → Brief + cover letter + resume tweaks + LinkedIn snippet to recruiter;
#   Gmail draft of cover letter created

$ /apply
# → Logs the submitted application to the Application Tracker
```

---

## Status

**Scout:** v2.2 — Production
**Pitch:** v1.0 — Production (split from Dossier on 2026-04-14)
**Dossier:** v2.0 — Production (scope narrowed; no longer drafts cold outreach)
**Pipeline:** v1.1.0 — Production (all 5 phases complete as of 2026-04-21)
**Apply:** v1.0.0 — Production

The pipeline went live on 2026-04-21 after a speed-first redesign. Five build phases delivered in a single session: /apply + clipboard, resume system, discovery engine, scoring + card queue, and outreach agent. The three original skills (Scout, Pitch, Dossier) remain standalone and are also invoked by the pipeline during automated outreach.

---

## Pipeline

Automated daily job search pipeline. Discovers listings from three channels, deduplicates against all known sources, scores each listing against your resume, presents a fast card-based triage queue, generates tailored resumes, logs applications, and fires parallel cold outreach via `/pitch`.

### Quick Start

```bash
# 1. One-time setup
cd pipeline && python3 bootstrap.py          # Seed dedup ledger from existing data
# Edit pipeline/config.yaml:
#   - Add Adzuna API creds (free: developer.adzuna.com)
#   - Review search queries, form answers, salary expectation

# 2. Optional: seed career page monitoring
pipeline/.venv/bin/python3 pipeline/careers.py --seed   # Probes ~130 companies for careers URLs

# 3. Optional: set up email alert channel
# Create "Job Alerts" Gmail label, set up filters for LinkedIn/Indeed/Built In alerts

# 4. Run the pipeline
/pipeline                    # Full daily run
/pipeline discover           # Discovery + dedup only
/pipeline review             # Score + triage from most recent discovery
/pipeline resume             # Jump to card queue (no scoring)
/pipeline --grade A          # Filter to A-grade cards only
```

### Daily Flow

```
/pipeline
  ├─ Stage 1: Discover
  │   ├─ Channel A: Adzuna API (30 queries across PM/Ops/Govt/CS/AI)
  │   ├─ Channel B: Gmail email alerts (parsed by Claude via MCP)
  │   └─ Channel C: Career page monitoring (HTML diff + job link extraction)
  │   └─ Three-level dedup (URL, company+title, 85% fuzzy match)
  │
  ├─ Breakpoint 1: "52 new, 34 after dedup. Continue?"
  │
  ├─ Stage 2: Score (10 weighted dimensions per listing)
  │   └─ Grades: A (4.0+), B (3.5-3.9), C (2.5-3.4), D/F (filtered out)
  │
  ├─ Breakpoint 2: "8 A, 12 B, 9 C, 5 D/F. Review 29 cards?"
  │
  ├─ Stage 3: Card queue triage
  │   ├─ [a]pply → tailored resume + clipboard package + open URL
  │   │            + background /pitch outreach (Gmail draft)
  │   ├─ [s]kip → log and move on
  │   ├─ [o]pen → view full JD in browser
  │   └─ [q]uit → save progress, resume later with /pipeline review
  │
  ├─ Outreach summary: "Dispatched 8. Drafted 5, no contact 2, cooldown 1."
  │
  └─ Stage 4: Obsidian daily note (stats + decisions + outreach table)
```

### Skills

| Skill | Version | Description |
|-------|---------|-------------|
| `/pipeline` | v1.1.0 | Full daily orchestration (discover, score, triage, outreach, note) |
| `/apply` | v1.0.0 | Log applications + clipboard package + ledger update |

### Pipeline Architecture

```
pipeline/
  discover.py          # Adzuna API + career page delegation + auto-dedup
  careers.py           # Career page monitor (--seed from ~/.scout/seen.md)
  dedup.py             # Three-level dedup (URL, title, fuzzy)
  resume.py            # Per-archetype resume tailoring + PDF generation
  bootstrap.py         # One-time ledger seeder from tracker/outreach/scout
  scoring_prompt.md    # Scoring dimensions reference (tunable)
  config.yaml          # Queries, API creds, form answers, archetypes, career URLs
  data/
    ledger.tsv         # Dedup ledger (grows over time, never truncated)
    listings/          # Daily discovery CSVs
    scored/            # Daily scored JSONs (scoring checkpoints)
    resumes/
      source.json      # Structured resume (single source of truth)
      output/          # Generated PDFs (Company-Role-Date.pdf)
```

### Scoring Dimensions

| Dimension | Weight | What it measures |
|-----------|--------|-----------------|
| Role match | 3x | Title + responsibilities align? |
| Skills alignment | 3x | Required skills match experience? |
| Interview likelihood | 3x | Realistic shot at a screen? |
| Seniority fit | 2x | Right level? |
| Compensation | 2x | Meets salary floor? |
| Domain resonance | 2x | Industry connects to background? |
| Timeline/urgency | 2x | Fresh posting, likely still open? |
| Geographic fit | 1x | Seattle, remote, or hybrid? |
| Company stage | 1x | Reasonable company? |
| Growth trajectory | 1x | Career advancement potential? |

### Resume Archetypes

| Archetype | Covers |
|-----------|--------|
| Product Management | PM, Product Owner, AI PM, TPM |
| Operations | Ops, Program Manager, Chief of Staff, RevOps |
| Government | Federal, state, county, municipal, higher ed |
| Customer Success | CS, Account Mgmt, TAM, Solutions |
| AI Technical | AI/ML product, technical advisory, fractional |

### Dedup Sources

The pipeline checks five sources before surfacing a listing:

| Source | Check | Behavior |
|--------|-------|----------|
| `ledger.tsv` | URL + company/title | Skip (already seen) |
| Application Tracker | Company + role | Skip (already applied) |
| Outreach Log | Company | Surface new roles, skip same role |
| `~/.scout/blacklist.md` | Company name | Hard filter (never surface) |
| `~/.scout/seen.md` | Company name | Soft filter (new roles only) |
