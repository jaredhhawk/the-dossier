---
name: dossier
description: Deep-dive company intelligence brief with outreach strategy
version: 1.0.0
---

# /dossier — Company Intelligence Brief

/dossier is the intelligence layer for pre-emptive job search outreach. Give it a company name or URL; it researches the company, maps your background to their situation, and drafts outreach calibrated to your persona.

**Depends on:** `~/.scout/profile.md` — required. If missing, the skill stops and tells you to create it.

## Usage

```
/dossier [company name or URL]                  # Standard run (brief + draft)
/dossier [company] --brief-only                 # Sections 1-4 only, no draft
/dossier [company] --with-gmail                 # Brief + draft + Gmail MCP
/dossier [company] --no-log                     # Skip Outreach Log for this run
/dossier [company] --lean                       # Override depth to lean for this run
/dossier [company] --depth=[lean|standard|deep] # Explicit depth override
```

---

# Implementation

## Step 0: Parse Inputs

Extract:
- **Company** — name or URL (required). If a URL is given, use the domain as the company identifier.
- **Flags** — parse from the invocation:
  - `--brief-only` → output mode: brief only (Sections 1–4, no draft)
  - `--with-gmail` → output mode: brief + draft + Gmail MCP
  - `--no-log` → skip Outreach Log auto-log for this run
  - `--lean` → override research depth to lean
  - `--depth=[lean|standard|deep]` → explicit depth override

**Default output mode (no flags):** brief + draft (Sections 1–5).

**Depth resolution order** (first match wins):
1. `--lean` flag → lean
2. `--depth=X` flag → X
3. Profile `Research Depth` setting → that value
4. Fallback → standard

## Step 1: Load Profile

Read `~/.scout/profile.md`.

**If file does not exist:** Stop immediately. Output:
> Profile not found. Create `~/.scout/profile.md` using the template at `templates/profile-template.md` in the job-search-skills repo, then re-run /dossier.

**If file exists, parse:**
- Background Summary
- Pitch Angles (name, one-liner, optional expanded context)
- War Stories (title, Situation/Action/Result, Tags)
- Key Metrics
- Tone Notes
- Research Depth setting
- Persona fields:
  - `outreach_posture` (Direct | Advisory | Exploratory)
  - `target_seniority` (IC | Manager | Director | VP | C-suite)
  - `risk_tolerance` (Conservative | Moderate | Bold)

**If persona fields are absent from profile:** Note this — you will surface the default notice at the top of Section 3. Defaults: `outreach_posture = Exploratory`, `target_seniority = VP`, `risk_tolerance = Moderate`.

**If War Stories section is empty or missing:** Note this — you will stop at Section 4 and tell the user to add war stories.

## Step 2: Check Outreach Log

Read `~/Documents/Second Brain/02_Projects/Job Search/R - Outreach Log.md`.

- **If company is in the log with status `sent` or `drafted`, no reply recorded, and ≥5 business days have passed since the outreach date:** Offer follow-up mode before proceeding (see Follow-Up Protocol below). Do not run the full brief unless user declines.
- **If company is in the log for any other reason (fresh run):** Note at top of output: "You've logged outreach to [Company] on [date]. Status: [status]."
- **If company is not in the log or the log can't be read:** Proceed normally.

## Step 3: Load Signal Context

Read the most recent file in `~/.scout/runs/` (files are named YYYY-MM-DD.md — latest date = most recent).

- **If the company name appears in the file:** Extract that company's full signal block (signal type, amount/name, date, source URL, context). Store as `signal_context`.
- **If not found:** Set `signal_context = none`. You will note in Section 1: "No signal context found in last Scout run. Timing urgency is unknown."
- **If `~/.scout/runs/` does not exist or is empty:** Same as not found.

## Step 4: Execute Research Protocol

Research executes before any section is generated. Extract structured facts only — never pass raw page content to the reasoning phase. Compress any source returning >5k words to bullet-point facts before using it.

**Research stops when:** target source count is reached OR 2 consecutive sources yield no new facts.

**Depth targets:**

| Depth    | Max Sources | Token Budget | Required Source Types |
|----------|-------------|--------------|----------------------|
| lean     | 5           | ~3k          | Company homepage, 1 job posting, 1 news item |
| standard | 8           | ~6k          | Company homepage, 2 job postings, 2 news articles (≥1 third-party), LinkedIn headcount trend if accessible |
| deep     | 12          | ~10k         | Company homepage, 3+ job postings, funding history, 2+ exec backgrounds, product docs, 1 competitor comparison |

**Valid sources:** company website / official blog, press release, reputable news outlet (TechCrunch, Bloomberg, WSJ, Reuters, etc.), job posting, SEC filing or public investor deck, LinkedIn (headcount and leadership changes only).

**Invalid sources:** random blog reposts, AI-generated summaries, unsourced listicles, sources >24 months old (flag staleness if used).

**If a required source type is unavailable:** Note it explicitly in Section 1 as a data limitation. Lower all inference confidence levels by one tier for the entire brief (High → Medium, Medium → Low).

**If research returns no useful facts (stealth company):** Note in Section 1. Reduce all confidence levels. Flag in recommendation.

## Step 5: Generate Section 1 — Company Intelligence

Generate this section completely, then freeze it. No backward revision after freezing. If a gap is discovered later, flag it in "What we don't know" — do not re-research.

**Conflicting signals check:** Before writing, check whether research surfaced contradictory signals (e.g., a funding announcement alongside a LinkedIn hiring-freeze mention). If found, prepend:

> ⚠️ **HIGH RISK:** [Describe the conflicting signals explicitly. State what the conflict implies for outreach timing and strategy.]

---

**What we know**

Facts sourced directly from research. Rules:
- Each fact must cite its source (link or publication name)
- Minimum 3 facts beyond the signal itself
- At least 1 fact must come from a third-party source (not the company's own domain)

**What we infer**

Hypotheses about the company's situation and needs. Rules:
- Each inference must derive from ≥1 fact in "What we know" — no new factual claims
- Each inference must include a confidence level (High / Medium / Low) and a one-line rationale citing the source fact(s)
- Maximum 3 inferences
- At least 1 must address execution risk, not just growth opportunity

**What we don't know**

Strategic Pivot Gaps only — named uncertainties where the answer would change which angle to recommend or the timing of outreach. Generic disclaimers fail this criterion.

Required format:
> "We don't know [X]. If [answer A], then [Angle N] is the play; if [answer B], then [Angle M] wins."

Each gap must name an angle implication. At least 1 gap required.

## Step 6: Generate Section 2 — Recommended Contact

Using Section 1 results and `target_seniority` from the profile.

For each contact (1–2 total):
- **Target title** — derived from the recommended angle + `target_seniority` preference
- **Name** — if found on the company's About/Team page. Do not scrape LinkedIn for names.
- **LinkedIn search string** — e.g., `"VP of Product" at [Company Name]`
- **Email pattern** — infer likely format from found emails or common patterns (e.g., `firstname@company.com`). Always flag as speculative.

If no contact can be identified: output 2 recommended titles + LinkedIn search strings, note the limitation.

## Step 7: Generate Section 3 — Outreach Strategy

Using Section 1 + user profile.

Generate 2–3 possible angles. Each angle must include:
- Angle name (maps to a pitch angle in the user's profile)
- One-line rationale connecting company context to user background
- Confidence level (High / Medium / Low)

**Angles must be genuinely distinct** — each must differ from the others in at least one of:
- Primary business problem addressed
- User capability emphasized
- Time horizon
- Org stakeholder targeted

**Persona effects on ranking:**
- `outreach_posture: Direct` → rank assertive, declarative angles higher
- `outreach_posture: Exploratory` → rank curiosity/question-framing angles higher
- `risk_tolerance: Bold` → recommend highest expected-value angle
- `risk_tolerance: Conservative` → recommend safest angle (highest confidence, lowest downside)

**If persona fields were absent from profile:** Note at top of this section: "Persona fields not found in profile — defaulting to Exploratory / VP / Moderate."

After the angles:
- **Recommended angle** — name it, explain why. Must reference: company context AND user background AND persona.
- **Timing window** — specific to signal type:
  - Exec hire: act within 7 days
  - Funding: act within 14 days
  - Product launch: act within 30 days
  - No signal context: "Timing urgency unknown — no signal detected in last Scout run."

## Step 8: Generate Section 4 — Your Arsenal

Using Section 1 + user profile war stories.

**If no war stories in profile:** Stop here. Output:
> No war stories found in profile. Add war stories to `~/.scout/profile.md` before running /dossier.

**If war stories exist:** Surface top 2–3, ordered by relevance score.

**Scoring — show all scores:**

| Dimension            | 0                   | 1                | 2                                     |
|----------------------|---------------------|------------------|---------------------------------------|
| Industry overlap     | Unrelated           | Adjacent         | Same vertical                         |
| Stage similarity     | Very different      | Similar          | Same stage                            |
| Functional similarity| Different function  | Overlapping      | Identical problem type                |
| Signal alignment     | Unrelated to signal | Loosely related  | Directly addresses signal implication |

Tie-breaking rule: functional similarity outranks industry overlap.

**If war stories exist but none score above 2/8:** Surface 2 closest anyway. Note low relevance in rationale.

For each story:
- Story title
- Score breakdown (e.g., Industry 1 / Stage 1 / Functional 2 / Signal 2 = 6)
- One-line relevance rationale naming the functional parallel explicitly (not just "both PropTech")

## Step 9: Determine Output Mode

Flag-driven — no prompt.

| Condition | Output |
|---|---|
| `--brief-only` | Sections 1–4 only, stop here |
| `--with-gmail` | Sections 1–5 + Gmail MCP (Step 14) |
| No flags | Sections 1–5 (brief + draft) |
| Recommended angle confidence = Low | Auto-stop at Sections 1–4 regardless of flags |

**Low-confidence auto-stop:** If the recommended angle's confidence is Low, stop at Sections 1–4 and output:
> Recommended angle confidence is Low due to [Strategic Pivot Gap]. Stopping at brief — verify [gap] before drafting outreach.

This override applies even if `--with-gmail` was passed.

## Step 10: Generate Section 5 — Draft Outreach

Only executes if output mode includes draft AND recommended angle confidence is not Low.

Uses recommended angle from Section 3 and top war story from Section 4.

**Structure — ~100 words, 3 paragraphs:**

- **Para 1:** Reference the specific signal by name (funding amount, exec name, product name). One observation about what it means for the company.
- **Para 2:** Connect their implied need (from Section 1) to one specific achievement from your background. The parallel must be explicit — name the functional similarity. Include a metric.
- **Para 3:** Close calibrated to `outreach_posture`:
  - Direct → specific ask ("I'd like 20 minutes to discuss how we handled X")
  - Exploratory → open conditional ("If [challenge] is on the roadmap, I'd love to swap notes")
  - Advisory → offer of value ("Happy to share what we learned about X if it would be useful")

Placeholders in [brackets] for anything the user must fill in (contact name, personal details).

**Banned words:** passionate, excited to, synergy, leverage, I'd love to learn more, deeply, significantly, expertly

## Step 11: Output Validation Pass

Before surfacing final output, verify all of the following:

- [ ] Section 1: ≥3 non-signal facts, each citing a source
- [ ] Section 1: ≥1 fact from a third-party source
- [ ] Section 1: all inferences have confidence level + rationale
- [ ] Section 1: ≥1 inference addresses execution risk
- [ ] Section 1: ≥1 Strategic Pivot Gap in required "if A / if B" format
- [ ] Section 3: ≥2 genuinely distinct angles
- [ ] Section 3: recommended angle references company context + user background + persona
- [ ] Section 3: timing window states specific number of days
- [ ] Section 4: ≥2 war stories with all 4 scores shown
- [ ] Section 4: rationale names functional parallel explicitly
- [ ] Section 5 (if generated): draft ≤150 words
- [ ] Section 5 (if generated): Para 1 names the specific signal
- [ ] Section 5 (if generated): Para 2 includes a metric and directly addresses the implied need from Section 1
- [ ] Section 5 (if generated): Para 3 close matches outreach posture
- [ ] No banned words
- [ ] Recommended angle is not a restatement of the signal (circular logic)

If any check fails → regenerate the affected section only, not the full brief.

## Step 12: Surface Final Output

Format:

```markdown
# Dossier — [Company Name]
[Date]

[If previously logged:] > Note: You've logged outreach to [Company] on [date]. Status: [status].

---

## Section 1: Company Intelligence

**What we know**
...

**What we infer**
...

**What we don't know**
...

---

## Section 2: Recommended Contact
...

---

## Section 3: Outreach Strategy
...

---

## Section 4: Your Arsenal
...

---

## Section 5: Draft Outreach
...
```

## Step 13: Auto-Log to Outreach Log

Skip this step if `--no-log` was passed.

1. Show the proposed row to append:
   ```
   | [YYYY-MM-DD] | [Company] | [Contact name or TBD] | [Target title] | | Drafted | [YYYY-MM-DD + 7 days] | Signal: [type] [detail]; Dossier [date] |
   ```
2. Confirm with user before writing.
3. If confirmed, append to the Active Outreach table in `~/Documents/Second Brain/02_Projects/Job Search/R - Outreach Log.md`.

**Extended columns** (add if not present in the log; note to user if schema update needed):
- `thread_id` — blank until Gmail MCP creates a draft
- `follow_up_1_date` — blank
- `follow_up_2_date` — blank

## Step 14: Gmail MCP Draft

Only runs if `--with-gmail` was passed AND output mode was not auto-stopped at brief-only.

- **If `thread_id` exists in Outreach Log for this company:** Create draft as a reply to that thread (`inReplyTo` + `threadId`).
- **Otherwise:** Create new draft.

Prompt user for: recipient name (if not found in Section 2), recipient email.

**Do not send.** Confirm by outputting: "Draft created: [Subject line]. Not sent."

After draft is created, update `thread_id` in the Outreach Log (show diff first, confirm before writing).

---

# Follow-Up Protocol

Triggered when the company is in the Outreach Log with status `sent` or `drafted`, no reply recorded, and ≥5 business days have passed since the initial outreach date.

When triggered, offer before running the full brief:
> "[Company] is in your Outreach Log (status: [status], sent [date] — [N] business days ago, no reply). Run follow-up mode instead of a fresh brief? [Y/n]"

If user accepts follow-up mode:

**Generate follow-up message:**
- ≤75 words
- Reply to original thread using `thread_id` from log. If no `thread_id`: create new draft, note that threading is not possible.
- Para 1: brief reference to the first message — what you said specifically, not "I reached out previously"
- Para 2: one new piece of value — a new signal about the company, a new observation, or a relevant development you've found
- Never "just checking in"

**Timing defaults:**
- Follow-up 1: 5 business days after initial outreach date
- Follow-up 2: 5 business days after follow-up 1
- After follow-up 2 is sent: update status to `closed`

**Update Outreach Log** (show diff first, confirm before writing):
- `follow_up_1_date` or `follow_up_2_date` → today
- If this is follow-up 2: status → `closed`

---

# Boundaries

**Always:**
- Pull signal context from last Scout run automatically — no prompt needed
- Surface multiple war stories with scores shown
- State confidence levels on every inference
- Name Strategic Pivot Gaps in the required "if A / if B" format
- Use conditional language unless `outreach_posture = Direct`
- Show Outreach Log diff before writing

**Require explicit confirmation every time:**
- Creating a Gmail draft (even if user has done it before — authorization does not carry over)
- Writing to Outreach Log (show diff, then confirm)

**Never:**
- Send an email without explicit confirmation
- Assume the company is hiring
- State an inference as a fact
- Use banned words in the draft
- Re-research after Section 1 is frozen — flag gaps in "What we don't know" instead
- Generate a draft before output mode is determined
