---
name: pitch
description: First-touch cold outreach email for a company with a hiring signal. Light research, one angle, one war story, ~100-word draft.
version: 1.0.0
---

# /pitch — First-Touch Cold Outreach

`/pitch` is the fast path for cold outreach. Give it a company name; it does just enough research to produce a credible first-touch email, not a full company brief. Use this for the 90% of contacts who will never reply. When someone does reply, run `/dossier` for the deep research.

**Depends on:** `~/.scout/profile.md` — required. If missing, the skill stops and tells you to create it.

**Companion skills:**
- `/scout` — finds the signals that feed `/pitch`
- `/dossier` — deep research + strategy, run after a reply or before an interview
- `/outreach` — logs networking outreach to the tracker (standalone, not invoked by pitch)

## Usage

```
/pitch [company name or URL]                # Standard run (signal + contact + email + LinkedIn snippet)
/pitch [company] --with-gmail               # Standard run + Gmail draft
/pitch [company] --no-log                   # Skip Outreach Log update
/pitch [company] --follow-up                # Headless follow-up mode (no Y/n prompt)
/pitch [company] --follow-up --with-gmail   # Headless follow-up + Gmail draft
```

---

# Implementation

## Step 0: Parse Inputs

Extract:
- **Company** — name or URL (required). If a URL is given, use the domain as the company identifier.
- **Flags:**
  - `--with-gmail` → create Gmail draft via MCP
  - `--no-log` → skip Outreach Log update
  - `--follow-up` → skip interactive Y/n follow-up prompt; go directly to Follow-Up Protocol. Used by automation. Requires the company to already be in the Outreach Log with stage `Drafted` or `Sent` and ≥5 business days elapsed — if not, output an error and stop.

## Step 1: Load Profile

Read `~/.scout/profile.md`.

**If file does not exist:** Stop. Output:
> Profile not found. Create `~/.scout/profile.md` before running /pitch.

**Parse:**
- Background Summary (one-liner)
- Pitch Angles (name + one-liner each)
- War Stories (title, Situation/Action/Result, Tags)
- Key Metrics
- Tone Notes
- Persona fields:
  - `outreach_posture` (Direct | Advisory | Exploratory) — default Exploratory
  - `target_seniority` (IC | Manager | Director | VP | C-suite) — default VP
  - `risk_tolerance` (Conservative | Moderate | Bold) — default Moderate

**If War Stories is empty:** Stop. Output:
> No war stories in profile. Add war stories to `~/.scout/profile.md` before running /pitch.

## Step 2: Check Outreach Log

Read `~/Documents/Second Brain/02_Projects/Job Search/Scout + Dossier/R - Outreach Log.md`.

- **If company is in the log with stage `Drafted` or `Sent`, no reply recorded, and ≥5 business days have passed:** Offer follow-up mode (see Follow-Up Protocol). Do not run a fresh pitch unless user declines.
- **If company is in the log with stage `Bounced`:** Offer Bounce Recovery mode (see Bounce Recovery Protocol). Do not run fresh pitch unless user declines.
- **If company is in the log for any other reason (fresh run):** Note at top of output: "Already logged on [date], stage: [stage]. Running fresh pitch anyway."
- **If not in log or log unreadable:** Proceed normally.

## Step 3: Load Signal Context

Read the most recent file in `~/.scout/runs/` (files named YYYY-MM-DD.md — latest date wins).

- **If the company appears in the file:** Extract its full signal block (signal type, amount/name, date, source URL, context). Store as `signal_context`.
- **If not found in latest file:** Scan the 2 most recent scout run files before falling back.
- **If still not found:** Set `signal_context = none`. Proceed to Step 4 where you'll gather a minimal hook.

## Step 4: Light Research (3 sources max)

Budget: ~2k tokens of input. Stop as soon as you have: a verified signal/hook, an email format, and a sense of who to contact.

**Required sources (in order):**

1. **Company homepage** — confirm positioning, get product name, find About/Team page link.
2. **Signal confirmation** — verify the signal from Step 3. If no signal context, search for the most recent news/announcement/launch from the company (one query, take the first credible result). This becomes the hook.
3. **Contact page / About page** — find any real email address on the company's own site. This reveals both the correct mail domain and the naming format. Skip if Step 1 already surfaced this.

**Do NOT pull:**
- GitHub signals (not in lite mode — run `/dossier` for technical posture)
- Third-party news coverage beyond the one signal confirmation
- Exec backgrounds from LinkedIn
- Product docs, SEC filings, competitor comparisons

**If the signal confirmation fails (can't verify from Step 3):** Note the uncertainty in Section 1 output. Still proceed unless the signal is clearly stale (>90 days old) — in that case stop and recommend `/dossier` instead.

**If the company is stealth / no public information:** Stop. Output:
> No public signal found for [Company]. Not enough context for a credible first-touch — run `/dossier [company]` for deeper research or pick a different target.

## Step 5: Pick Angle and War Story (single best match, no scoring shown)

**Angle selection:**
- Read the Pitch Angles from profile.
- Pick the ONE angle whose subject matter most directly addresses the signal's implication. Example: funding + exec hire → "PM 0-to-1" angle. Enterprise customer win → "Operator/domain expertise" angle.
- Tie-break by `outreach_posture` and `risk_tolerance`: prefer declarative angles if Direct/Bold, prefer curiosity-framed if Exploratory/Conservative.

**War story selection:**
- Read War Stories from profile.
- Pick the ONE story that best matches on functional similarity (same problem type) first, then industry/stage. Functional match outranks industry match.
- **No scoring table output.** This is the lite version — just pick the best and use it.
- If no story scores a clear match, pick the closest and note in Section 1 output: "War story match is weak — if this angle matters, run `/dossier` for full scoring."

## Step 6: Generate Section 1 — Signal + Angle

Short, scannable. ~5 lines max.

**Format:**
```
**Signal:** [One-line description with date and source]
**Implication:** [One sentence on what this means for the company's hiring need]
**Angle:** [Pitch angle name] — [one-line rationale tying signal to your background]
**War story:** [Title] — [one-line functional parallel]
```

**If signal is >30 days old:** Add a one-line flag: `⚠️ Signal is [N] days old — timing window is closing.`

## Step 7: Generate Section 2 — Contact

For the contact (1 person):
- **Target title** — derived from angle + `target_seniority`
- **Name** — if found on About/Team page. Do not scrape LinkedIn for names.
- **LinkedIn search string** — e.g., `"VP of Product" at [Company]`
- **Email** — use real address from contact page if found. Otherwise pattern-infer (`firstname@company.com`).

Append a confidence tag on the same line as the email:
- `[source: contact page → HIGH]` — address or format found on company's own pages
- `[source: pattern inference, domain confirmed → MEDIUM]` — format inferred, domain matches website
- `[source: pattern inference, domain uncertain → LOW]` — format inferred, domain not confirmed

Common failure mode: mail domain differs from product domain (e.g., `billdr.co` vs `billdr.ai`) — the contact page catches this. If you can't confirm the mail domain, flag LOW and note in the Gmail draft: "(speculative — verify before sending)."

If no contact can be identified: output target title + LinkedIn search string only. Draft the email to `[First name]` placeholder and note the gap.

## Step 8: Generate Section 3 — Email Draft

~100 words, 3 paragraphs.

- **Para 1:** Reference the specific signal by name (funding amount, exec name, product name). One observation about what it means for the company.
- **Para 2:** Connect their implied need to one specific achievement from your war story. The parallel must be explicit — name the functional similarity. Include a metric.
- **Para 3:** Close calibrated to `outreach_posture`:
  - Direct → specific ask ("I'd like 20 minutes to discuss how we handled X")
  - Exploratory → open conditional ("If [challenge] is on the roadmap, I'd love to swap notes")
  - Advisory → offer of value ("Happy to share what we learned about X if it would be useful")

**Signature — always end with:**
```
[First name from profile]
[email from profile]
[linkedin URL from profile, if present]
```

**P.S. — always append after signature:**
```
P.S. If you're scaling without a dedicated PM, I also take on fractional work (roadmap audits, PRD sprints, strategy sessions). Happy to share more if useful.
```

**Banned words:** passionate, excited to, synergy, leverage (as verb), I'd love to learn more, deeply, significantly, expertly, on your radar, thrilled, unique opportunity, fast-paced, results-driven, delve, robust, streamline, cutting-edge, multifaceted, comprehensive, meticulous, pivotal, testament, utilize, facilitate, "it is worth noting", "it is important to note"

**Banned punctuation:** em-dashes (—) anywhere in the draft. Use commas, periods, or restructure.

**Voice:** Confident but not stiff. One person talking to one other person, not a brand writing to an audience. Match the Tone Notes section of the profile.

## Step 9: Generate Section 4 — LinkedIn Snippet

50–75 words, 2–3 sentences. Same contact as Section 2, LinkedIn channel instead of email.

**Structure:**
- Sentence 1: Brief, specific reference to the signal or role. Not "I saw your post." More like: "Noticed [specific signal detail] at [Company]."
- Sentence 2: One credential — most relevant achievement in one sentence. Include a metric.
- Sentence 3 (optional): Soft close. "Happy to connect if [X] is relevant."

**Rules:**
- No em-dashes
- Same banned words as the email
- Shorter and more casual than the email — LinkedIn DMs are skimmed
- Do NOT start with "Hi, I hope this message finds you well" or any variation

## Step 10: Validation Pass (lite)

Before surfacing output, verify:

- [ ] Email: ≤120 words
- [ ] Email Para 1: names the specific signal
- [ ] Email Para 2: includes a metric and an explicit functional parallel (not just "both SaaS")
- [ ] Email Para 3: close matches `outreach_posture`
- [ ] LinkedIn snippet: 50-75 words, names signal in sentence 1, includes a metric
- [ ] No banned words or em-dashes anywhere
- [ ] Email recipient email has a confidence tag

If any check fails → regenerate the affected section only.

## Step 11: Surface Final Output

Format:

```markdown
# Pitch — [Company Name]
[Date]

[If previously logged:] > Already logged on [date], stage: [stage].

---

## Signal + Angle
**Signal:** ...
**Implication:** ...
**Angle:** ...
**War story:** ...

## Contact
**Target:** [Name or title], [Title]
**LinkedIn:** [search string]
**Email:** [address] [confidence tag]

## Email Draft
Subject: [Specific, signal-referencing subject line under 60 chars]

Hi [First name],

[Para 1 — signal + observation]

[Para 2 — war story + metric + functional parallel]

[Para 3 — close calibrated to posture]

[First name]
[email]
[linkedin URL if present]

P.S. If you're scaling without a dedicated PM, I also take on fractional work (roadmap audits, PRD sprints, strategy sessions). Happy to share more if useful.

## LinkedIn Snippet
[50-75 word snippet]
```

## Step 12: Save to Vault

Save the full pitch output to the vault — no confirmation required.

**Save path:** `~/Documents/Second Brain/02_Projects/Job Search/Companies/Pitch Outputs/[Company Name] - Pitch YYYY-MM-DD.md`

Create the `Pitch Outputs/` folder if it doesn't exist.

Include frontmatter + header:
```
---
Domain: "[[D - Career & Job Search]]"
tags:
  - pitch
  - job-search
  - cold-outreach
created: YYYY-MM-DD
---
Related: [[D - Career & Job Search]] | [[R - Outreach Log]] | [[R - Scout Dossier Quick Start]]

# Pitch — [Company Name]
[Date]

Signal: [Signal type] — [Signal detail]
Status: Drafted (Pitch)
```

After saving, note the path to the user: "Saved to vault: `Companies/Pitch Outputs/[Company Name] - Pitch YYYY-MM-DD.md`"

**If `--no-log` was passed:** Still save the pitch file. `--no-log` only skips the Outreach Log.

## Step 13: Update Outreach Log

Skip this step if `--no-log` was passed.

Write immediately — no confirmation required.

**If the company is NOT in the Outreach Log:** Append a new row to the `## In Flight` section:
```
| [YYYY-MM-DD] | [Company] | [Contact name or TBD] | [Signal type] | [Angle name] | Drafted | | | Signal: [type] [detail]; Pitch [date] |
```
Column order: date | company | contact | signal_type | hook | stage | fu1 | fu2 | notes

**If the company IS already in the Outreach Log** (e.g., added by Scout): Update the row in place — set contact name if found, update stage to `Drafted`, append `; Pitch [date]` to Notes.

The `Pitch [date]` marker in Notes signals that lite research was done. When a reply comes in, run `/dossier` — it will append `; Dossier [date]` to Notes, making it clear at a glance which contacts have had deep research.

After writing, confirm: "Outreach Log updated."

## Step 14: Gmail MCP Draft

Only runs if `--with-gmail` was passed.

**Passing `--with-gmail` is explicit authorization to create the draft — no additional confirmation prompt.**

- Create a Gmail draft of the email from Section 3.
- **Recipient:** Use contact name and email from Section 2. If no email was found, use the speculative pattern (e.g., `firstname@company.com`) and note it is unverified in the confirmation.
- **If `thread_id` exists in Outreach Log for this company:** Create draft as a reply to that thread (`inReplyTo` + `threadId`).
- **Otherwise:** Create a new draft.

**Do not send.** Confirm: "Draft created: [Subject line]. Not sent. (Email: [address used] — verify before sending)"

After draft is created, extract `id`, `threadId`, and `subject` from the Gmail API response and append `; draft_id: [id]; thread_id: [threadId]; subject: [subject]` to the Notes column for this company in the Outreach Log. No confirmation required when `--with-gmail` was passed.

---

# Follow-Up Protocol

Triggered when the company is in the Outreach Log with stage `Drafted` or `Sent`, no reply recorded, and ≥5 business days have passed since the initial outreach date.

When triggered, offer before running a fresh pitch:
> "[Company] is in your Outreach Log (stage: [stage], sent [date] — [N] business days ago, no reply). Run follow-up mode instead of a fresh pitch? [Y/n]"

If user accepts (or `--follow-up` was passed):

**Determine follow-up number from log:**
- Check the Notes column for evidence FU1 was successfully sent:
  - "FU1 sent" → FU1 sent
  - "FU1 draft created" / "FU1 draft_id" / "FU1 draft: r" → FU1 draft created
  - "FU1 draft ... (token expired)" or "FU1 draft ... (failed)" → FU1 NOT sent; treat as FU1
  - Nothing matching → FU1 not yet sent; this is Follow-Up 1
- If FU1 confirmed sent/drafted and FU2 column blank → this is Follow-Up 2 (the last one)
- If FU1 confirmed and FU2 also set → nothing to send; output error and stop
- **Do NOT use the FU1 column date alone to infer FU1 was sent.** The Notes column is the source of truth.

**Check channel from log:**
- If log notes contain "LinkedIn DM" or no `thread_id` present and no email was sent:
  - Do NOT create a Gmail draft
  - Output the follow-up as plain text with: "Send via LinkedIn DM — no email thread exists."
- Otherwise: proceed with Gmail draft reply

**Generate follow-up message:**
- ≤75 words
- Reply to original thread using `thread_id` from log. If none: create new draft, note threading not possible.
- Para 1: brief reference to what you said specifically in the first message, not "I reached out previously."
- Para 2: one new piece of value — a new signal about the company, a new observation, or a relevant development.
- Never "just checking in."
- **If this is Follow-Up 2:** add a closing sentence after Para 2: "I'll leave it here if the timing doesn't work — happy to reconnect down the road."
- **Always append a P.S. after the signature:**
  ```
  P.S. If you're scaling without a dedicated PM, I also take on fractional work (roadmap audits, PRD sprints, strategy sessions). Happy to share more if useful.
  ```

**Timing defaults:**
- Follow-up 1: 5 business days after initial outreach date
- Follow-up 2: 5 business days after follow-up 1
- After follow-up 2 is sent: update stage to `Closed` — no further follow-ups

**Update Outreach Log** (show diff first, confirm before writing):
- FU1 → today (if follow-up 1), FU2 → today (if follow-up 2)
- If follow-up 2: stage → `Closed`, move row to `## Closed / Skipped / Archived` section

---

# Bounce Recovery Protocol

Triggered when the company is in the Outreach Log with stage `Bounced`.

When triggered, offer before running a fresh pitch:
> "[Company] is in your Outreach Log (stage: Bounced — [email that bounced]). Run bounce recovery mode? [Y/n]"

If user accepts:

**Step 1: Find alternate contact path**
- Check About/Team page for correct email format or contact form
- Check LinkedIn for the contact's profile (use prior LinkedIn search string if available)
- Try alternate email patterns: `first.last@`, `flast@`, `firstlast@`, `first@` — note all as speculative
- If contact has LinkedIn and no verified email can be found, recommend LinkedIn DM instead of email

**Step 2: Draft recovery outreach**
- ≤100 words
- Do NOT reference the bounce or the failed email — start fresh
- Same angle and war story as the original pitch (pull from saved pitch file if available at `Companies/Pitch Outputs/`)
- Channel: LinkedIn InMail if no verified email; email if alternate pattern found

**Step 3: Update Outreach Log** (show diff first, confirm before writing):
- Update Notes column to reflect new channel/email tried
- Stage → `Drafted` (if new draft created)

---

# Boundaries

**Always:**
- Pull signal context from last Scout run automatically — no prompt needed
- State confidence on the contact email
- Use conditional language unless `outreach_posture = Direct`
- Cap research at 3 sources

**Require explicit confirmation every time:**
- Sending an email (never auto-send under any circumstances)

**No confirmation needed when flag is passed:**
- Creating a Gmail draft when `--with-gmail` is present — the flag is the authorization

**Never:**
- Send an email without explicit confirmation
- Use banned words or em-dashes in the draft
- Generate multi-angle comparisons (that's `/dossier`)
- Generate war story scoring tables (that's `/dossier`)
- Pull GitHub signals, SEC filings, exec backgrounds (that's `/dossier`)
- Save the pitch without saving to `Companies/Pitch Outputs/`

**When to escalate to `/dossier`:**
- User got a reply and needs full prep → `/dossier [company]`
- User is applying through the job portal → `/dossier [company] --apply`
- War story match from Step 5 was weak → note and recommend `/dossier`
- Signal is >30 days stale and user wants a stronger hook → `/dossier` for deeper research
