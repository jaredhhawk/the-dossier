# The Dossier

A two-agent agentic pipeline for pre-emptive job search outreach, built on Claude Code.

**Scout** monitors the market for hiring signals across 6 signal types and maintains a deduplicated, urgency-scored pipeline of target companies. **Dossier** takes any company from that pipeline — or one you specify — and produces a full intelligence brief, calibrated outreach strategy, and ready-to-send drafts, with Gmail integration and automatic CRM logging.

---

## How It Works

```
/scout  →  finds companies with hiring signals  →  logs to outreach pipeline
/dossier [company]  →  researches company  →  maps your background  →  drafts outreach
```

The two skills share state: Scout writes run files and seeds the outreach log; Dossier reads signal context from the last Scout run to inform timing and angle selection.

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

### Example Scout Output

```
# Scout Results - 2026-03-01

Filtered: 12 companies removed (3 blacklisted, 6 previously seen, 2 already in pipeline, 1 layoff)
Stale signals (90+ days): 1 of 9 — 11%

---

## 1. Meridian PropTech 🔥

Signal: Series B funding ($42M) announced Feb 28, 2026
Signal Type: Funding
Signal Date: 2026-02-28 🔥 Act now
Source: TechCrunch
Industry: PropTech / Real Estate Tech
Amount: $42M Series B | Lead Investor: Andreessen Horowitz

Context:
Meridian builds lease intelligence software for institutional landlords. The Series B is
their first institutional round after 18 months of bootstrapped growth. ~45 employees.
Funding earmarked for product and engineering expansion per the TechCrunch piece.

Why relevant:
Post-Series B companies typically hire a Head of Product or first PM team within 45 days
of close. No PM leadership visible on their About page — likely a gap.

---

## 2. Fieldstone AI ⚠️

Signal: New Chief Product Officer — Sarah Chen appointed Feb 18, 2026
Signal Type: Exec Hire
Signal Date: 2026-02-18 ⚠️ Move fast
Source: LinkedIn announcement
Industry: Construction Tech
Exec: Sarah Chen, CPO (previously VP Product at Procore)

Context:
Fieldstone automates field documentation for commercial construction. ~60 employees,
Series A. New CPO from Procore suggests a shift toward enterprise and platform expansion.

Why relevant:
New CPOs build product teams within 30–60 days. First outreach now positions you as
a candidate before the role exists.

...

Summary:
- Total shown: 9
- By signal type: Funding (3) | Exec Hires (2) | Launches (2) | YC/Accel (1) | Pivots (1)
- By urgency: 🔥 Act now (2) | ⚠️ Move fast (4) | 📌 Still relevant (2) | 🗓️ Stale (1)
- Stale rate: 11%
- Filtered: 12 companies removed

Priority order for outreach:
1. 🔥 Meridian PropTech — Funding, act within 14 days
2. 🔥 BuildPath — YC W26, founders accessible now
3. ⚠️ Fieldstone AI — Exec hire, act within 7 days
```

---

## Dossier

Deep company intelligence brief + calibrated outreach, on demand.

### Usage

```bash
/dossier [company]                        # Standard: brief + outreach email + LinkedIn snippet
/dossier [company] --apply                # Apply mode: cover letter + LinkedIn snippet + resume tweaks
/dossier [company] --apply --with-gmail   # Apply mode + Gmail draft
/dossier [company] --with-gmail           # Standard + Gmail draft
/dossier [company] --brief-only           # Intelligence brief only, no draft
/dossier [company] --depth=[lean|standard|deep]  # Override research depth
/dossier [company] --follow-up            # Follow-up mode for companies already contacted
```

### What Dossier Produces

**Section 1 — Company Intelligence**
Structured research brief with sourced facts, confidence-scored inferences, and named strategic gaps in a required "if A then Angle X / if B then Angle Y" format. Flags conflicting signals (e.g., funding announcement alongside LinkedIn hiring freeze mention) with a `⚠️ HIGH RISK` banner before proceeding.

**Section 2 — Recommended Contact**
Target title derived from your seniority preference and the recommended outreach angle. LinkedIn search string. Email pattern with confidence rating (`HIGH` if found on contact page, `MEDIUM` if inferred from confirmed domain, `LOW` if speculative).

**Section 3 — Outreach Strategy**
2–3 genuinely distinct outreach angles, each scored by confidence and mapped to your background. Ranking is influenced by your persona settings (`outreach_posture`, `risk_tolerance`). Includes a timing window specific to signal type (exec hire: 7 days; funding: 14 days; launch: 30 days).

**Section 4 — Your Arsenal**
Your war stories scored against the company context on 4 dimensions: industry overlap, stage similarity, functional similarity, signal alignment. Top 2–3 surfaced with scores and a rationale that names the functional parallel explicitly (not just "both PropTech").

**Section 5 — Draft Outreach or Cover Letter**
- Standard mode: ~100-word cold email referencing the specific signal, connecting to your top war story with a metric, and closing calibrated to your outreach posture
- Apply mode: 200–250 word cover letter opening with a company-specific observation (never "I am applying for"), mapping the top two JD requirements to your war stories

**Section 6 — LinkedIn Outreach Snippet**
50–75 word LinkedIn DM targeting the recruiter (apply mode) or cold contact (standard mode). Shorter and more casual than the email — written to be skimmed.

**Section 7 — Resume Tweaks** *(apply mode only)*
Direct yes/no on whether customization is worth it, followed by up to 5 targeted suggestions with current text, suggested replacement, and rationale. Flags ATS keyword gaps specific to this JD.

### Example Dossier Output (abbreviated)

```
# Dossier — Meridian PropTech
2026-03-01

---

## Section 1: Company Intelligence

**What we know**
- Closed $42M Series B led by a16z on Feb 28, 2026 (TechCrunch). First institutional round.
- Product: lease intelligence platform for institutional landlords — automates lease abstraction,
  obligation tracking, and portfolio benchmarking (meridianproptech.com)
- ~45 employees per LinkedIn headcount; engineering and product teams not yet publicly listed
- CEO quoted in TechCrunch: "This round lets us build the product team we've needed for two years"
- No PM leadership visible on About page or LinkedIn as of March 1, 2026

**What we infer**
- Product team is likely pre-PM or founder-led (High confidence — CEO quote + no PM on About page)
- Funding earmarked for product/engineering suggests a Head of Product or first PM hire is imminent
  (High confidence — explicit CEO quote; rationale: "build the product team" implies PM, not just eng)
- Institutional real estate focus suggests enterprise sales motion and compliance requirements will
  constrain product velocity (Medium confidence — inferred from customer segment, not confirmed)

**What we don't know**
- We don't know whether they want a generalist PM or a PropTech domain specialist. If generalist,
  Angle 1 (0-to-1 operator) wins; if domain specialist, Angle 3 (PropTech vertical) wins.

---

## Section 2: Recommended Contact

**Target:** Head of Product (likely first hire at this level) or CEO directly (if no PM org yet)
**LinkedIn search:** "Head of Product" OR "VP Product" at Meridian PropTech
**Email:** `[first]@meridianproptech.com` [source: pattern inference, domain confirmed → MEDIUM]
Note: verify before sending.

---

## Section 3: Outreach Strategy

**Angle 1 — First PM at a Funded Startup** (Confidence: High)
You've been the first PM at a funded company before. Meridian is about to be in that exact
situation. Rationale: CEO quote signals urgency; your 0-to-1 background is the direct analog.

**Angle 2 — Institutional Real Estate Operator** (Confidence: Medium)
Your property management background gives you end-user empathy for institutional landlords —
rare in PM candidates. Rationale: their customer is institutional RE; your HPM experience is
adjacent but not identical, hence Medium.

**Recommended angle:** Angle 1. Strongest signal-to-background match. CEO quote makes the timing
explicit — outreach in the next 14 days catches them before a search is formalized.

**Timing:** Act within 14 days (funding signal).

---

## Section 4: Your Arsenal

1. First PM at Knock (Series A) — Score: Industry 2 / Stage 2 / Functional 2 / Signal 2 = 8/8
   Functional parallel: led product from 0-to-1 at a funded PropTech startup, same stage as Meridian now.

2. HPM Platform — Score: Industry 2 / Stage 1 / Functional 1 / Signal 1 = 5/8
   Functional parallel: built ops tooling for property management, same end-user Meridian serves.

---

## Section 5: Draft Outreach

Subject: Series B → First PM

[First name],

Saw the a16z round close — congrats. The CEO quote about finally building the product team
caught my attention, because I've been that first PM: at Knock I took the self-guided tour product
from concept to 16% MoM adoption in a market nobody had cracked yet.

Meridian's problem space — making lease data legible for institutional landlords — is the kind of
hairy domain work I find most interesting. If you're figuring out what the first PM hire looks like,
happy to share how we structured it at Knock.

[Name]
[email]
[LinkedIn]

---

## Section 6: LinkedIn Snippet

Saw the Series B close — the CEO quote about building the product team finally was the part
that stuck. I was first PM at Knock (PropTech, Series A): self-guided tours from 0 to 16% MoM.
If you're mapping out that hire, happy to connect.

---

Saved to vault: Companies/Dossier Outputs/Meridian PropTech - Dossier 2026-03-01.md
Outreach Log updated.
```

---

## Automated Follow-Up & Bounce Recovery

Dossier tracks outreach state in your log. When you re-run `/dossier [company]` on a company you've already contacted:

- **5+ business days, no reply** — Offers follow-up mode: drafts a ≤75-word reply to the original thread with a new piece of value (never "just checking in")
- **Bounced email** — Offers bounce recovery mode: finds an alternate email pattern or recommends LinkedIn DM, drafts fresh outreach on the new channel

---

## Profile-Driven Personalization

Both skills read `~/.scout/profile.md` — a single file where you define:

- Target industries, company stages, geography
- Background summary and pitch angles
- War stories in Situation/Action/Result format (scored and ranked per company)
- Persona calibration: `outreach_posture` (Direct/Advisory/Exploratory), `target_seniority`, `risk_tolerance`
- Tone notes

See `templates/profile-template.md` for the full format.

---

## Architecture

```
the-dossier/
├── .claude/skills/
│   ├── scout/
│   │   └── SKILL.md          # Scout skill — signal detection logic
│   └── dossier/
│       └── SKILL.md          # Dossier skill — research + outreach logic
├── templates/
│   └── profile-template.md   # User profile template
├── scenarios/
│   └── dossier-scenarios.md  # Behavioral test cases
└── README.md

~/.scout/
├── profile.md                # Your profile (not in repo — personal)
├── seen.md                   # Dedup list across Scout runs
├── blacklist.md              # Permanent exclusions
└── runs/
    └── YYYY-MM-DD.md         # Scout run archives (Dossier reads these)
```

Skills are invoked via Claude Code (`/scout`, `/dossier`). No API keys, no hosting, no external dependencies — runs entirely within your local Claude Code session with web search access.

---

## Status

**Scout:** v2.1 — Production
**Dossier:** v1.0 — Production
Both skills are actively used in a real job search pipeline.
