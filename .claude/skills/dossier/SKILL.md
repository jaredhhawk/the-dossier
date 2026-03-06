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
/dossier [company name or URL]                  # Standard run (brief + outreach email + LinkedIn snippet)
/dossier [company] --apply                      # Application mode: cover letter + LinkedIn snippet, no cold outreach
/dossier [company] --apply --resume=[path]      # Application mode + targeted resume tweak suggestions
/dossier [company] --apply --with-gmail         # Application mode + Gmail draft of cover letter
/dossier [company] --brief-only                 # Sections 1-4 only, no draft
/dossier [company] --with-gmail                 # Brief + outreach email + LinkedIn snippet + Gmail MCP
/dossier [company] --no-log                     # Skip Outreach Log for this run
/dossier [company] --lean                       # Override depth to lean for this run
/dossier [company] --depth=[lean|standard|deep] # Explicit depth override
/dossier [company] --follow-up                  # Headless follow-up mode (no Y/n prompt)
/dossier [company] --follow-up --with-gmail     # Headless follow-up + Gmail draft
```

---

# Implementation

## Step 0: Parse Inputs

Extract:
- **Company** — name or URL (required). If a URL is given, use the domain as the company identifier.
- **Flags** — parse from the invocation:
  - `--apply` → application mode: user is applying through the job portal and handling outreach manually. Replaces outreach email (Section 5) with a cover letter. Skips Outreach Log. Adds LinkedIn snippet and resume tweak suggestions. Prompts user to run `/apply` after.
  - `--resume=[path]` → path to the user's current resume (PDF or markdown). Only valid with `--apply`. When provided, enables specific line-level resume suggestions in Section 7. When absent but `--apply` is set, Section 7 generates suggestions based on profile alone and notes the limitation.
  - `--brief-only` → output mode: brief only (Sections 1–4, no draft)
  - `--with-gmail` → output mode: brief + draft + Gmail MCP. In apply mode, creates Gmail draft of cover letter instead of outreach email.
  - `--no-log` → skip Outreach Log auto-log for this run
  - `--lean` → override research depth to lean
  - `--depth=[lean|standard|deep]` → explicit depth override
  - `--follow-up` → skip the interactive Y/n follow-up prompt; go directly to Follow-Up Protocol. Used by `automate.py` for headless runs. Requires the company to already be in the Outreach Log with status `sent` and ≥5 business days elapsed — if not, output an error and stop.

**Default output mode (no flags):** brief + draft (Sections 1–5).

**Depth resolution order** (first match wins):
1. `--lean` flag → lean
2. `--depth=X` flag → X
3. Profile `Research Depth` setting → that value
4. Fallback → standard

## Step 1: Load Profile

Read `~/.scout/profile.md`.

**If file does not exist:** Stop immediately. Output:
> Profile not found. Create `~/.scout/profile.md` using the template at `templates/profile-template.md` in the the-dossier repo, then re-run /dossier.

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

Read `~/Documents/Second Brain/02_Projects/Job Search/Scout + Dossier/R - Outreach Log.md`.

- **If company is in the log with stage `sent` or `drafted`, no reply recorded, and ≥5 business days have passed since the outreach date:** Offer follow-up mode before proceeding (see Follow-Up Protocol below). Do not run the full brief unless user declines.
- **If company is in the log with stage `bounced`:** Offer Bounce Recovery mode before proceeding (see Bounce Recovery Protocol below). Do not run the full brief unless user declines.
- **If company is in the log for any other reason (fresh run):** Note at top of output: "You've logged outreach to [Company] on [date]. Stage: [stage]."
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
- **Email pattern** — before guessing, check the company's `/contact` and `/about` pages for any real email addresses. These reveal both the correct mail domain and the naming format. Only fall back to pattern inference (`firstname@company.com`) if no real email is found. Common failure mode: the company's mail domain differs from the product domain (e.g., `billdr.co` vs `billdr.ai`) — the contact page is the fastest way to catch this.

  After determining the email, append a confidence tag on the same line:
  - `[source: contact page → HIGH]` — address or format found directly on the company's own pages
  - `[source: pattern inference, domain confirmed → MEDIUM]` — format inferred, but the email domain matches the confirmed website domain
  - `[source: pattern inference, domain uncertain → LOW]` — format inferred and the email domain was not confirmed by any source, or differs from the website domain

  Example output: `` `bertrand@billdr.co` [source: contact page → HIGH] ``

  Note in the Gmail draft confirmation: "(speculative — verify before sending)" for MEDIUM and LOW only.

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
| `--apply` | Sections 1–4 + Section 5 (Cover Letter) + Section 6 (LinkedIn Snippet) + Section 7 (Resume Tweaks). No outreach email. No Outreach Log. |
| `--apply --with-gmail` | Same as `--apply` + Gmail MCP draft of cover letter (Step 15) |
| `--with-gmail` | Sections 1–6 + Gmail MCP outreach email (Step 15) |
| No flags | Sections 1–6 (brief + outreach email + LinkedIn snippet) |
| Recommended angle confidence = Low | Auto-stop at Sections 1–4 regardless of flags |

**Low-confidence auto-stop:** If the recommended angle's confidence is Low, stop at Sections 1–4 and output:
> Recommended angle confidence is Low due to [Strategic Pivot Gap]. Stopping at brief — verify [gap] before drafting outreach.

This override applies even if `--with-gmail` was passed.

## Step 10: Generate Section 5 — Draft Outreach or Cover Letter

**If `--apply` flag is present:** Skip the outreach email. Generate Section 5 as a Cover Letter (see Step 10B).

**Otherwise:** Generate Section 5 as an outreach email (see Step 10A).

---

### Step 10A: Outreach Email (standard mode)

Only executes if output mode includes draft AND recommended angle confidence is not Low.

Uses recommended angle from Section 3 and top war story from Section 4.

**Structure — ~100 words, 3 paragraphs:**

- **Para 1:** Reference the specific signal by name (funding amount, exec name, product name). One observation about what it means for the company.
- **Para 2:** Connect their implied need (from Section 1) to one specific achievement from your background. The parallel must be explicit — name the functional similarity. Include a metric.
- **Para 3:** Close calibrated to `outreach_posture`:
  - Direct → specific ask ("I'd like 20 minutes to discuss how we handled X")
  - Exploratory → open conditional ("If [challenge] is on the roadmap, I'd love to swap notes")
  - Advisory → offer of value ("Happy to share what we learned about X if it would be useful")

**Signature — always end the draft with:**
```
[First name from profile]
[email from profile]
[linkedin URL from profile, if present]
```

Placeholders in [brackets] for anything the user must fill in (contact name, personal details).

---

### Step 10B: Cover Letter (apply mode)

Only executes when `--apply` is present AND recommended angle confidence is not Low.

Uses the job posting details from research (Step 4) to map the user's background to specific JD requirements.

**If the job posting was not retrieved during research:** Note the gap and draft the cover letter based on general company context only. Flag to user: "No JD retrieved — cover letter based on company context. Paste the JD to refine."

**Structure — 200-250 words, 4 paragraphs:**

- **Para 1 (Hook):** Open with one specific, concrete observation about the company or role — the signal, a product decision, a challenge visible from the outside. Do not open with "I am applying for" or "I am excited." Lead with the observation, then connect it to why you're reaching out. 2-3 sentences max.
- **Para 2 (Primary match):** Take the most important JD requirement and map it directly to the highest-scoring war story from Section 4. Name the functional parallel explicitly. Include a metric. 2-3 sentences.
- **Para 3 (Secondary match):** Take the second most important JD requirement and map it to a second war story or a distinct capability. Keep it tight — 2 sentences.
- **Para 4 (Close):** Simple, direct close. No groveling. Something like "Happy to share more about how I've approached [X] — [contact name or 'feel free to reach out'] at [email]." 1-2 sentences.

**Signature — always end with:**
```
[First name from profile]
[email from profile]
[linkedin URL from profile, if present]
```

**Banned words:** passionate, excited to, synergy, leverage, I'd love to learn more, deeply, significantly, expertly, on your radar, thrilled, unique opportunity, fast-paced, results-driven

**Banned punctuation:** em-dashes (—) anywhere in the draft. Use commas, periods, or restructure the sentence instead.

**Voice:** Confident but not stiff. Write like a person who has actually read the job description and done work in this space. No AI slop. Reference the Tone Notes section of the profile before drafting.

---

## Step 10C: Generate Section 6 — LinkedIn Outreach Snippet

Executes for all output modes that generate a draft (standard, apply, with-gmail) unless `--brief-only`.

**Who to contact:**
- **Apply mode:** Target the recruiter or hiring manager for the specific role (not the cold outreach VP target from Section 2). This is a "double-tap" on the application — the goal is to get the application noticed.
  - LinkedIn search string: `Recruiter at [Company]` or `[Team/Function] Hiring Manager at [Company]`
  - Note: recruiter outreach after applying is expected behavior; hiring manager outreach is bolder but higher signal.
- **Standard mode:** Same contact as Section 2 (cold outreach target), but via LinkedIn channel instead of email. Include the Section 2 LinkedIn search string.

**Snippet structure — 50-75 words, 2-3 sentences:**
- Sentence 1: Brief, specific reference to the role or company signal. Not "I saw your job posting." More like: "Came across the [role] opening at [Company] and [one specific observation about the role or product]."
- Sentence 2: One credential — the most relevant achievement in one sentence. Include a metric.
- Sentence 3 (optional): Soft close. "Happy to connect if [X] is relevant to what you're building."

**Format rules:**
- No em-dashes
- Same banned words as the outreach email
- Even shorter and more casual than the email draft — LinkedIn DMs are skimmed
- Do NOT start with "Hi, I hope this message finds you well" or any variation

## Step 10D: Generate Section 7 — Resume Tweaks

Only executes when `--apply` is present. Skip if `--brief-only`.

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
- ATS keywords: list 3-5 terms prominent in the JD that are absent from the current resume. Flag which are worth adding to the skills section vs. body text.
- Flag anything in the resume that might screen negatively for this specific role (e.g., a headline emphasizing infrastructure for a Growth PM role)

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
- [ ] Section 5 outreach email (if standard mode): draft ≤150 words
- [ ] Section 5 outreach email (if standard mode): Para 1 names the specific signal
- [ ] Section 5 outreach email (if standard mode): Para 2 includes a metric and directly addresses the implied need from Section 1
- [ ] Section 5 outreach email (if standard mode): Para 3 close matches outreach posture
- [ ] Section 5 cover letter (if apply mode): 200-250 words
- [ ] Section 5 cover letter (if apply mode): Para 1 opens with specific observation, not "I am applying"
- [ ] Section 5 cover letter (if apply mode): Para 2 maps top JD requirement to war story with metric
- [ ] Section 5 cover letter (if apply mode): Para 3 maps second JD requirement to distinct capability
- [ ] Section 6 LinkedIn snippet (if any draft mode): 50-75 words
- [ ] Section 6 LinkedIn snippet (if any draft mode): names specific role or signal in sentence 1
- [ ] Section 6 LinkedIn snippet (if any draft mode): includes a metric
- [ ] Section 7 (if apply mode): opens with a direct yes/no on whether customization is worth it
- [ ] Section 7 (if apply mode): max 5 suggestions, each with current/suggested/why
- [ ] Section 7 (if apply mode): at least 1 suggestion addresses ATS keywords
- [ ] No banned words or phrases in any draft
- [ ] No em-dashes (—) in any draft
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

## Section 5: [Draft Outreach | Cover Letter]
...

---

## Section 6: LinkedIn Outreach
**Who to contact:** [title + LinkedIn search string]
**Snippet:**
...

---

## Section 7: Resume Tweaks
**Worth customizing?** [Yes / Borderline / No] — [one-line rationale]

[Suggestions or skip notice]
```

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
   Status: Drafted  ← use "Applied" if --apply was passed
   ```
3. After saving, note the file path to the user: "Saved to vault: `Companies/Dossier Outputs/[Company Name] - Dossier YYYY-MM-DD.md`"

**If `--no-log` was passed:** Still save the dossier file — `--no-log` only skips the Outreach Log, not the vault save.
**If `--apply` was passed:** Status in frontmatter = `Applied`. Still save the full dossier including cover letter and LinkedIn snippet.

## Step 14: Auto-Log to Outreach Log

Skip this step if `--no-log` was passed.
**Skip this step entirely if `--apply` was passed.** Instead, output:
> Apply mode: Outreach Log skipped. Run `/apply` to log this to the Application Tracker when you submit.

Write immediately — no confirmation required.

**If the company is NOT in the Outreach Log:** Append a new row to the `## In Flight` section table:
```
| [YYYY-MM-DD] | [Company] | [Contact name or TBD] | [Signal type] | Insight | Drafted | | | Signal: [type] [detail]; Dossier [date] |
```
Column order: date | company | contact | signal_type | hook | stage | fu1 | fu2 | notes

**If the company IS already in the Outreach Log** (e.g., added by Scout): Update the existing row in place — set contact name if found in Section 2, update stage to Drafted, append `; Dossier [date]` to Notes.

After writing, confirm to the user with a one-line note: "Outreach Log updated."

## Step 15: Gmail MCP Draft

Only runs if `--with-gmail` was passed AND output mode was not auto-stopped at brief-only.

**Passing `--with-gmail` is explicit authorization to create the draft — no additional confirmation prompt.**

- **In apply mode (`--apply --with-gmail`):** Create a Gmail draft of the cover letter. Recipient = the hiring contact from Section 6 (recruiter/hiring manager), or leave recipient blank if none identified. Subject = "Application: [Role Name] — [First Name] [Last Name]".
- **In standard mode (`--with-gmail`):** Create a Gmail draft of the outreach email.
- **Recipient (standard mode):** Use contact name and speculative email from Section 2. If no email was found, use the speculative pattern (e.g., `firstname@company.com`) and note it is unverified.
- **If `thread_id` exists in Outreach Log for this company:** Create draft as a reply to that thread (`inReplyTo` + `threadId`).
- **Otherwise:** Create new draft.

**Do not send.** Confirm by outputting: "Draft created: [Subject line]. Not sent. (Email: [address used] — verify before sending)"

After draft is created, extract the `id`, `threadId` and `subject` from the Gmail API response and append `; draft_id: [draft.id]; thread_id: [threadId]; subject: [subject line]` to the Notes column for this company in the Outreach Log. No confirmation required when `--with-gmail` was passed.

---

# Follow-Up Protocol

Triggered when the company is in the Outreach Log with status `sent` or `drafted`, no reply recorded, and ≥5 business days have passed since the initial outreach date.

When triggered, offer before running the full brief:
> "[Company] is in your Outreach Log (stage: [stage], sent [date] — [N] business days ago, no reply). Run follow-up mode instead of a fresh brief? [Y/n]"

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
- FU1 → today (if follow-up 1), FU2 → today (if follow-up 2)
- If this is follow-up 2: stage → `Closed`, move row to `## Closed / Skipped / Archived` section

---

# Bounce Recovery Protocol

Triggered when the company is in the Outreach Log with stage `Bounced`.

When triggered, offer before running the full brief:
> "[Company] is in your Outreach Log (stage: Bounced — [email that bounced]). Run bounce recovery mode? [Y/n]"

If user accepts bounce recovery mode:

**Step 1: Find alternate contact path**
- Check company About/Team page for correct email format or contact form
- Check LinkedIn for the contact's profile (use LinkedIn search string from Section 2 of prior dossier)
- Try alternate email patterns: `first.last@`, `flast@`, `firstlast@`, `first@` — note all as speculative
- If contact has LinkedIn and no verified email can be found, recommend LinkedIn DM instead of email

**Step 2: Draft recovery outreach**
- ≤100 words
- Do NOT reference the bounce or the failed email — start fresh
- Same angle and war story as the original outreach (pull from saved dossier if available)
- Channel: LinkedIn InMail if no verified email; email if alternate pattern found

**Step 3: Update Outreach Log** (show diff first, confirm before writing):
- Update Notes column to reflect new channel/email tried
- Stage → `Drafted` (if new draft created)

---

# Boundaries

**Always:**
- Pull signal context from last Scout run automatically — no prompt needed
- Surface multiple war stories with scores shown
- State confidence levels on every inference
- Name Strategic Pivot Gaps in the required "if A / if B" format
- Use conditional language unless `outreach_posture = Direct`
**Require explicit confirmation every time:**
- Sending an email (never auto-send under any circumstances)

**No confirmation needed when flag is passed:**
- Creating a Gmail draft when `--with-gmail` is present — the flag is the authorization

**Never:**
- Send an email without explicit confirmation
- Assume the company is hiring
- State an inference as a fact
- Use banned words in the draft
- Re-research after Section 1 is frozen — flag gaps in "What we don't know" instead
- Generate a draft before output mode is determined
