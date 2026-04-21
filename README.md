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
│   ├── scout/
│   │   ├── SKILL.md              # Scout skill — signal detection
│   │   └── profile-template.md   # Profile template
│   ├── pitch/
│   │   └── SKILL.md              # Pitch skill — first-touch cold outreach
│   └── dossier/
│       └── SKILL.md              # Dossier skill — deep research + apply mode
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
    └── YYYY-MM-DD.md             # Scout run archives (Pitch and Dossier read these)
```

Skills are invoked via Claude Code (`/scout`, `/pitch`, `/dossier`). No API keys, no hosting, no external dependencies — runs entirely within your local Claude Code session with web search access.

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

All three skills are actively used in a real job search pipeline. The three-skill architecture went live on 2026-04-14 after a token-cost audit showed that running full Dossier briefs on every cold contact was spending deep-research tokens on the 85-90% of contacts who never replied.

---

## Pipeline

Automated job search pipeline. Built in phases — each phase delivers standalone value.

### Available Skills

| Skill | Status | Description |
|-------|--------|-------------|
| `/apply` | Live | Log applications + clipboard package |
| `/pipeline` | Stub | Full daily orchestration (Phase 4) |

### Setup

1. Bootstrap the dedup ledger (one-time):
   ```bash
   cd pipeline && python3 bootstrap.py
   ```

2. Edit `pipeline/config.yaml` with your details (phone, portfolio, etc.)

3. Run `/apply Company - Role Title` to log applications.

### Directory Structure

```
pipeline/
  config.yaml          # Search queries, form answers, archetype routing
  bootstrap.py         # One-time ledger seeder
  data/
    ledger.tsv         # Dedup ledger (all seen listings + applications)
    resumes/output/    # Generated PDFs (Phase 2)
    listings/          # Discovery output (Phase 3)
    scored/            # Scored listings (Phase 4)
```
