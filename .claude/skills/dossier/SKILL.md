---
name: dossier
description: Deep-dive company research and strategy for a single company. No cold-outreach drafting — use /pitch for that. Apply mode (--apply) generates cover letter and resume tweaks.
version: 2.0.0
---

# /dossier — Company Research & Strategy

`/dossier` is the deep-research tool for a single company. Use it when you need more than a first-touch hook — when a reply has landed, when you're applying through a portal, or when you need to prep an angle before a real conversation.

`/dossier` does **not** draft cold outreach emails. Use `/pitch [company]` for that — it does just enough research to produce a credible first-touch. Run `/dossier` after you get a reply, or when applying.

**Depends on:** `~/.scout/profile.md` — required. If missing, the skill stops and tells you to create it.

**Companion skills:**
- `/pitch` — first-touch cold outreach email (lite research, ~3k tokens)
- `/scout` — finds company signals that feed both /pitch and /dossier
- `/prep` — interview brief (use after dossier when interview is scheduled)

## Usage

```
/dossier [company name or URL]                    # Research + strategy brief (Sections 1-4)
/dossier [company] --apply                        # Brief + cover letter + LinkedIn (to recruiter) + resume tweaks
/dossier [company] --apply --resume=[path]        # Apply mode + line-level resume suggestions
/dossier [company] --apply --with-gmail           # Apply mode + Gmail draft of cover letter
/dossier [company] --no-log                       # Skip Outreach Log update
/dossier [company] --lean                         # Override depth to lean
/dossier [company] --depth=[lean|standard|deep]   # Explicit depth override
```

**Default output (no flags):** Sections 1-4 (Company Intelligence, Recommended Contact, Outreach Strategy, Your Arsenal). No drafts. Meant to inform a conversation, reply, or decision — not to ship an email.

---

# Implementation

## Step 0: Parse Inputs

Extract:
- **Company** — name or URL (required). If a URL is given, use the domain as the company identifier.
- **Flags:**
  - `--apply` → application mode: user is applying through the job portal. Adds Section 5 (Cover Letter), Section 6 (LinkedIn to recruiter/hiring manager), Section 7 (Resume Tweaks). Skips Outreach Log (application belongs in `/apply`). Prompts user to run `/apply` after.
  - `--resume=[path]` → path to user's current resume (PDF or markdown). Only valid with `--apply`. Enables line-level resume tweak suggestions in Section 7. Without it, Section 7 generates suggestions from profile only and notes the limitation.
  - `--with-gmail` → only valid with `--apply`. Creates Gmail draft of the cover letter. Ignored if `--apply` is absent (dossier no longer drafts cold outreach — that's `/pitch`).
  - `--no-log` → skip Outreach Log Notes update for this run
  - `--lean` → override research depth to lean
  - `--depth=[lean|standard|deep]` → explicit depth override

**Depth resolution order** (first match wins):
1. `--lean` flag → lean
2. `--depth=X` flag → X
3. Profile `Research Depth` setting → that value
4. Fallback → standard

## Step 1: Load Profile

Read `~/.scout/profile.md`.

**If file does not exist:** Stop. Output:
> Profile not found. Create `~/.scout/profile.md` before running /dossier.

**Parse:**
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

**If persona fields absent from profile:** Note this — surface the default notice at the top of Section 3. Defaults: `outreach_posture = Exploratory`, `target_seniority = VP`, `risk_tolerance = Moderate`.

**If War Stories section is empty:** Note this — you will stop at Section 3 and tell the user to add war stories.

## Step 2: Check Outreach Log

Read `~/Documents/Second Brain/02_Projects/Job Search/Scout + Dossier/R - Outreach Log.md`.

- **If company is in the log:** Note at top of output: "Already logged on [date], stage: [stage]. Notes: [relevant notes excerpt]." Proceed with the brief — no mode-switching.
- **If company is not in the log:** Proceed normally. No new row will be created by `/dossier` (that's `/pitch`'s responsibility).

**Note on follow-ups and bounces:** These are cold-outreach workflows and live in `/pitch`. If user wants to follow up on a stalled contact, they run `/pitch [company] --follow-up`, not `/dossier`.

## Step 3: Load Signal Context

Read the most recent file in `~/.scout/runs/` (files named YYYY-MM-DD.md — latest date wins).

- **If the company appears:** Extract the full signal block (signal type, amount/name, date, source URL, context). Store as `signal_context`.
- **If not found:** Set `signal_context = none`. Note in Section 1: "No signal context found in last Scout run. Timing urgency unknown."
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

**If a required source type is unavailable:** Note explicitly in Section 1 as a data limitation. Lower all inference confidence levels by one tier for the entire brief (High → Medium, Medium → Low).

**If research returns no useful facts (stealth company):** Note in Section 1. Reduce all confidence levels. Flag in recommendation.

## Step 4.5: GitHub Technical Posture

Gated on depth: run when depth is `standard` or `deep`. Skip on `lean`.

Run: `python3 ~/.scout/github_signals.py "<company>"`

The helper fuzzy-matches the company name to a public GitHub org and returns: primary stack, recently active repos, new repos in last 30 days, main product repo name and last commit date, contributor trend on the main repo (prior 90d baseline vs last 30d, with percent change), and top 10 contributors in the last 90 days. Responses cached 7 days.

**Use the output to enrich Section 1:**

Add a "Technical Posture" sub-block inside the "What we know" list. Minimum required content when the org is found:
- **Primary stack:** top 2-3 languages
- **Main product repo:** `<repo>` with last commit date
- **Recent engineering focus:** 1-2 most active repos with one-line description

Conditional additions:
- If `new_repos_30d` is non-empty: list up to 3 new repos with name and description. Call out anything that looks like a distinct product surface (not meta/docs).
- If `contributor_trend.change_pct` is ≥ +50% or ≤ -50%: surface the delta as an explicit bullet (e.g., "Contributors on `platform` jumped from 4 to 11 in last 30d — team scaling on that surface").
- If `top_contributors` has >3 names: you may reference specific humans in the strategy angle, but do NOT scrape LinkedIn. LinkedIn search strings are fine; direct profile scraping is not.

**Silence rules:**
- If the helper reports "No public GitHub org found," add a single bullet to "What we don't know": "GitHub posture unknown — no public org discoverable. Useful signals limited to non-engineering sources."
- If the org exists but has no product repos, note: "GitHub org exists but has no public product repos — engineering presumed private."
- Never fabricate. Never infer a stack from the company website.

**Citation:** All GitHub-derived facts cite `github.com/<org>` or `github.com/<org>/<repo>` as the source.

**Rate limit:** add a PAT at `~/.scout/github_token` for heavy use (lifts ceiling from 60/hr to 5,000/hr).

## Step 5: Generate Section 1 — Company Intelligence

Generate this section completely, then freeze it. No backward revision after freezing. If a gap is discovered later, flag it in "What we don't know" — do not re-research.

**Conflicting signals check:** Before writing, check whether research surfaced contradictory signals (e.g., funding announcement alongside a LinkedIn hiring-freeze mention). If found, prepend:

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
- **Email pattern** — before guessing, check the company's `/contact` and `/about` pages for any real email addresses. These reveal both the correct mail domain and the naming format. Only fall back to pattern inference (`firstname@company.com`) if no real email is found. Common failure mode: the company's mail domain differs from the product domain (e.g., `billdr.co` vs `billdr.ai`) — the contact page is the fastest way to catch this.

  After determining the email, append a confidence tag on the same line:
  - `[source: contact page → HIGH]` — address or format found directly on the company's own pages
  - `[source: pattern inference, domain confirmed → MEDIUM]` — format inferred, but the email domain matches the confirmed website domain
  - `[source: pattern inference, domain uncertain → LOW]` — format inferred and the email domain was not confirmed by any source, or differs from the website domain

  Example output: `` `bertrand@billdr.co` [source: contact page → HIGH] ``

If no contact can be identified: output 2 recommended titles + LinkedIn search strings, note the limitation.

**Note:** This section informs who to target — `/dossier` no longer drafts the email. Pass the contact and angle to `/pitch` (if doing cold outreach) or use it to prepare for a reply/call.

## Step 7: Generate Section 3 — Angle Analysis

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

Simple: apply mode or standard mode.

| Condition | Output |
|---|---|
| No flags | Sections 1–4 only. Stop here. |
| `--apply` | Sections 1–4 + Section 5 (Cover Letter) + Section 6 (LinkedIn to recruiter) + Section 7 (Resume Tweaks) |
| `--apply --with-gmail` | Same as `--apply` + Gmail MCP draft of cover letter (Step 15) |
| Recommended angle confidence = Low AND `--apply` present | Auto-stop at Sections 1–4. Do not generate cover letter. |

**Low-confidence auto-stop (apply mode only):** If `--apply` was passed but the recommended angle's confidence is Low, stop at Sections 1–4 and output:
> Recommended angle confidence is Low due to [Strategic Pivot Gap]. Stopping at brief — verify [gap] before drafting a cover letter.

## Step 10: Generate Cover Letter and Apply-Mode Artifacts

Only runs when `--apply` is present AND recommended angle confidence is not Low.

### Section 5 — Cover Letter

Uses the job posting details from research (Step 4) to map the user's background to specific JD requirements.

**If the job posting was not retrieved during research:** Note the gap and draft the cover letter based on general company context. Flag to user: "No JD retrieved — cover letter based on company context. Paste the JD to refine."

**Structure — 200–250 words, 4 paragraphs:**

- **Para 1 (Hook):** Open with one specific, concrete observation about the company or role — the signal, a product decision, a challenge visible from the outside. Do not open with "I am applying for" or "I am excited." Lead with the observation, then connect it to why you're reaching out. 2–3 sentences max.
- **Para 2 (Primary match):** Take the most important JD requirement and map it directly to the highest-scoring war story from Section 4. Name the functional parallel explicitly. Include a metric. 2–3 sentences.
- **Para 3 (Secondary match):** Take the second most important JD requirement and map it to a second war story or distinct capability. Keep it tight — 2 sentences.
- **Para 4 (Close):** Simple, direct close. No groveling. Something like "Happy to share more about how I've approached [X] — [contact name or 'feel free to reach out'] at [email]." 1–2 sentences.

**Signature — always end with:**
```
[First name from profile]
[email from profile]
[linkedin URL from profile, if present]
```

**Banned words:** passionate, excited to, synergy, leverage, I'd love to learn more, deeply, significantly, expertly, on your radar, thrilled, unique opportunity, fast-paced, results-driven

**Banned punctuation:** em-dashes (—) anywhere in the draft. Use commas, periods, or restructure the sentence instead.

**Voice:** Confident but not stiff. Write like a person who has actually read the job description and done work in this space. No AI slop. Reference the Tone Notes section of the profile before drafting.

### Section 6 — LinkedIn Snippet (recruiter / hiring manager)

The "double-tap" on the application — the goal is to get the application noticed. Target the recruiter or hiring manager for the specific role, not a cold-outreach VP target.

**Who to contact:**
- LinkedIn search string: `Recruiter at [Company]` or `[Team/Function] Hiring Manager at [Company]`
- Note: recruiter outreach after applying is expected behavior; hiring manager outreach is bolder but higher signal.

**Snippet structure — 50–75 words, 2–3 sentences:**
- Sentence 1: Brief, specific reference to the role. "Just applied to the [role] opening at [Company] — [one specific observation about the role or product]."
- Sentence 2: One credential — the most relevant achievement in one sentence. Include a metric.
- Sentence 3 (optional): Soft close. "Happy to share more if helpful."

**Format rules:**
- No em-dashes
- Same banned words as the cover letter
- Even shorter and more casual than the cover letter — LinkedIn DMs are skimmed
- Do NOT start with "Hi, I hope this message finds you well" or any variation

### Section 7 — Resume Tweaks

**Purpose:** Targeted, specific suggestions for tweaking the existing resume to improve fit for this specific role. This is NOT a rewrite — max 5 suggestions. Each suggestion must be actionable in under 10 minutes.

**If `--resume=[path]` was provided:**
1. Read the resume file.
2. Extract: headline/title, summary paragraph, bullet points per role, skills section.
3. Compare against JD requirements from research (Step 4) and recommended angle from Section 3.
4. Generate specific suggestions referencing the actual resume text.

**If no `--resume` provided:**
- Generate suggestions based on profile war stories vs. JD, noting: "No resume provided — suggestions based on profile. Run with `--resume=[path]` for line-level edits."

**Section structure:**

**Is customization worth it?**
One line: based on signal strength, acquisition risk, or role fit score — give a direct yes/no with brief rationale. Examples:
- "Yes — strong fit, high-signal role. 15 min of tweaks will meaningfully improve ATS pass-through."
- "Borderline — moon shot with acquisition risk. Cover letter does the heavy lifting; skip the resume edit."
- "No — generic role, low signal. Apply as-is."

**Suggested tweaks (only if answer above is yes/borderline):**

For each suggestion (max 5):
- **What:** The specific element to change (headline, summary sentence 2, Compass bullet 1, skills section, etc.)
- **Current:** The exact current text (quoted from resume if provided, or noted as "based on profile" if not)
- **Suggested:** The specific replacement text
- **Why:** One sentence — which JD requirement this improves and how

**Rules:**
- Never suggest adding buzzwords for their own sake — only add language that maps to a specific JD requirement
- Never suggest restructuring the whole resume — targeted changes only
- Prioritize: headline > summary > top bullet at most recent relevant role > ATS keywords
- ATS keywords: list 3–5 terms prominent in the JD that are absent from the current resume. Flag which are worth adding to the skills section vs. body text.
- Flag anything in the resume that might screen negatively for this specific role (e.g., a headline emphasizing infrastructure for a Growth PM role)

## Step 11: Validation Pass

Before surfacing final output, verify:

**Always checked:**
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
- [ ] Recommended angle is not a restatement of the signal (circular logic)

**Apply mode only:**
- [ ] Section 5 cover letter: 200–250 words
- [ ] Section 5: Para 1 opens with specific observation, not "I am applying"
- [ ] Section 5: Para 2 maps top JD requirement to war story with metric
- [ ] Section 5: Para 3 maps second JD requirement to distinct capability
- [ ] Section 6 LinkedIn snippet: 50–75 words, names specific role, includes a metric
- [ ] Section 7: opens with a direct yes/no on whether customization is worth it
- [ ] Section 7: max 5 suggestions, each with current/suggested/why
- [ ] Section 7: at least 1 suggestion addresses ATS keywords
- [ ] No banned words or em-dashes in any apply-mode draft

If any check fails → regenerate the affected section only, not the full brief.

## Step 12: Surface Final Output

Format:

```markdown
# Dossier — [Company Name]
[Date]

[If previously logged:] > Already logged on [date], stage: [stage].

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

## Section 3: Angle Analysis
...

---

## Section 4: Your Arsenal
...

[Apply mode only — otherwise stop here]

---

## Section 5: Cover Letter
...

---

## Section 6: LinkedIn Snippet (to recruiter / hiring manager)
**Who to contact:** [title + LinkedIn search string]
**Snippet:**
...

---

## Section 7: Resume Tweaks
**Worth customizing?** [Yes / Borderline / No] — [one-line rationale]

[Suggestions or skip notice]
```

**Closing line (standard mode):** "To draft outreach from this brief, run `/pitch [company]`. To prep for an interview, run `/prep [company]`."

**Closing line (apply mode):** "Run `/apply` to log this application to the tracker when you submit."

## Step 13: Save Dossier to Vault

After surfacing final output, always save the full dossier to the vault — no confirmation required.

**Save path:** `~/Documents/Second Brain/02_Projects/Job Search/Companies/Dossier Outputs/[Company Name] - Dossier YYYY-MM-DD.md`

**Steps:**
1. Write the complete dossier output (all sections generated) to the file.
2. Include a frontmatter block and header at the top:
   ```
   ---
   Domain: "[[D - Career & Job Search]]"
   tags:
     - dossier
     - job-search
     - company-intel
   created: YYYY-MM-DD
   ---
   Related: [[D - Career & Job Search]] | [[R - Application Tracker]] | [[R - Scout Dossier Quick Start]]

   # Dossier — [Company Name]
   [Date]

   Signal: [Signal type] — [Signal detail]
   Status: Research  ← use "Applied" if --apply was passed
   ```
3. After saving, note the file path: "Saved to vault: `Companies/Dossier Outputs/[Company Name] - Dossier YYYY-MM-DD.md`"

**If `--no-log` was passed:** Still save the dossier file — `--no-log` only skips the Outreach Log, not the vault save.
**If `--apply` was passed:** Status in frontmatter = `Applied`. Still save the full dossier including cover letter and LinkedIn snippet.

## Step 14: Update Outreach Log (Notes only)

Skip this step if `--no-log` or `--apply` was passed.

**Never create new rows from `/dossier`.** That's `/pitch`'s responsibility (cold outreach initiation). `/dossier` only enriches existing rows.

**If the company IS in the Outreach Log:** Update the row in place — set contact name if found in Section 2 and currently TBD, append `; Dossier [date]` to Notes. Do not change stage.

The `Dossier [date]` marker in Notes signals that deep research has been completed. When glancing at the log, rows with `Pitch [date]` but no `Dossier [date]` are ones where only lite research was done.

**If the company is NOT in the Outreach Log:** Do nothing. Output a one-line note: "Not in Outreach Log. Run `/pitch [company]` if you want to open an outreach thread."

After writing (if applicable), confirm: "Outreach Log Notes updated."

## Step 15: Gmail MCP Draft (apply mode only)

Only runs if `--apply --with-gmail` was passed AND output was not auto-stopped at Sections 1–4.

**Passing `--with-gmail` is explicit authorization to create the draft — no additional confirmation prompt.**

- Create a Gmail draft of the cover letter from Section 5.
- **Recipient:** Use the recruiter/hiring manager identified in Section 6. If no email was found, leave recipient blank and note it in the confirmation.
- **Subject:** "Application: [Role Name] — [First Name] [Last Name]"

**Do not send.** Confirm: "Cover letter draft created: [Subject line]. Not sent. (Email: [address used] — verify before sending)"

No Outreach Log update is made in apply mode — applications are logged via `/apply`.

---

# Boundaries

**Always:**
- Pull signal context from last Scout run automatically — no prompt needed
- Surface multiple war stories with scores shown
- State confidence levels on every inference
- Name Strategic Pivot Gaps in the required "if A / if B" format

**Require explicit confirmation every time:**
- Sending an email (never auto-send under any circumstances)

**No confirmation needed when flag is passed:**
- Creating a Gmail draft when `--apply --with-gmail` is present — the flag is the authorization

**Never:**
- Draft a cold outreach email — that's `/pitch`'s job
- Draft a LinkedIn snippet to a cold-outreach VP target — only the recruiter/hiring-manager snippet for apply mode
- Create a new row in the Outreach Log — only `/pitch` opens threads
- Run follow-up or bounce recovery workflows — those live in `/pitch`
- Send an email without explicit confirmation
- Assume the company is hiring
- State an inference as a fact
- Use banned words in a cover letter
- Re-research after Section 1 is frozen — flag gaps in "What we don't know" instead

**When to escalate or hand off:**
- User needs a cold outreach email → `/pitch [company]`
- User is following up on a stalled thread → `/pitch [company] --follow-up`
- Email bounced → `/pitch [company]` (it detects the bounce and offers recovery)
- Interview scheduled → `/prep [company]`
- Application submitted → `/apply`
