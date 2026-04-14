# /dossier — Test Scenarios

> ⚠️ **Stale as of 2026-04-14 — scenarios describe pre-split /dossier behavior.**
>
> Cold outreach drafting, LinkedIn snippet (standard mode), follow-up protocol, bounce recovery, `--with-gmail` (standard mode), `--follow-up`, and `--brief-only` all moved to `/pitch` on 2026-04-14. The scenarios below reference old behavior and will fail against the current skill.
>
> **Status:** Preserved as historical reference. Needs rewrite into two files: `pitch-scenarios.md` (cold outreach, follow-up, bounce) and `dossier-scenarios.md` (research + apply mode only). Tracked as follow-up work.

Behavioral test cases for the /dossier skill. Format: Given / When / Then.
Use these to verify skill behavior before and after changes.

---

## Scenario 1: Happy Path — Standard Run

**Given:**
- `~/.scout/profile.md` exists with: background summary, ≥2 pitch angles, ≥3 war stories, key metrics, tone notes, research depth = `standard`, all three persona fields present (`outreach_posture: Direct`, `target_seniority: VP`, `risk_tolerance: Moderate`)
- `~/.scout/runs/2026-02-20.md` exists and contains a funding signal block for "Acme PropTech" (Series B, $30M, source URL included)
- Acme PropTech is not in the Outreach Log
- Research returns a company homepage, 2 job postings, and 2 news articles (1 third-party)
- No conflicting signals in research

**When:**
- User runs `/dossier Acme PropTech`

**Then:**
- Section 1 is generated with ≥3 non-signal facts (each citing a source), ≤3 inferences (each with confidence + rationale, ≥1 addressing execution risk), and ≥1 Strategic Pivot Gap in "if A then Angle X; if B then Angle Y" format
- Section 2 names a VP-level target title, a LinkedIn search string, and a speculative email pattern
- Section 3 presents ≥2 genuinely distinct angles, identifies the recommended angle with reference to company context + user background + `outreach_posture: Direct` + `risk_tolerance: Moderate`, and states "act within 14 days" as the timing window
- Section 4 surfaces ≥2 war stories with all 4 scores shown and rationale naming a functional parallel
- Section 5 (draft) is generated because no flags were passed and recommended angle confidence is not Low
- Draft Para 3 closes with a specific ask (matching `outreach_posture: Direct`)
- Draft contains no banned words and is ≤150 words
- Output validation passes; no section regenerated
- Auto-log diff is shown; user is prompted to confirm before writing to Outreach Log

---

## Scenario 2: Missing Profile

**Given:**
- `~/.scout/profile.md` does not exist at `~/.scout/profile.md`

**When:**
- User runs `/dossier Acme PropTech`

**Then:**
- Skill stops immediately after Step 1
- Output is exactly: "Profile not found. Create `~/.scout/profile.md` using the template at `templates/profile-template.md` in the the-dossier repo, then re-run /dossier."
- No research is executed
- No sections are generated
- No Outreach Log entries are written

---

## Scenario 3: No Signal Context Found

**Given:**
- Profile exists with all required fields
- `~/.scout/runs/` is empty (no run files exist)
- Acme PropTech is not in the Outreach Log
- Research returns valid results

**When:**
- User runs `/dossier Acme PropTech`

**Then:**
- Step 3 sets `signal_context = none`
- Section 1 includes a note: "No signal context found in last Scout run. Timing urgency is unknown."
- Section 3 timing window states: "Timing urgency unknown — no signal detected in last Scout run." (no specific day count given)
- All other sections generate normally
- Draft is generated (default output mode, no flags)
- Signal alignment scores in Section 4 are 0 for all war stories (since no signal to align to)

---

## Scenario 4: Conflicting Signals

**Given:**
- Profile exists with all required fields
- Last Scout run contains a funding signal for "Acme PropTech" (Series B, $30M)
- Research returns a TechCrunch article announcing the Series B AND a LinkedIn post mentioning a hiring freeze at Acme PropTech (same week)

**When:**
- User runs `/dossier Acme PropTech`

**Then:**
- Section 1 opens with a `⚠️ HIGH RISK` banner
- The banner explicitly names both conflicting signals (Series B announcement AND hiring freeze mention) and states the implication for outreach timing
- Inferences in "What we infer" reflect the uncertainty — no inference presents the hiring freeze as confirmed or the funding as unambiguously positive for hiring
- Section 3 recommended angle references the HIGH RISK context; confidence level is not High
- If recommended angle confidence is Low (expected given conflicting signals), output auto-stops at Sections 1–4 with a note explaining the auto-stop
- No draft is generated when auto-stopped

---

## Scenario 5: Follow-Up Trigger

**Given:**
- Profile exists with all required fields
- Last Scout run contains a funding signal for "Acme PropTech"
- Outreach Log contains an entry for Acme PropTech: status = `sent`, outreach date = 9 business days ago, no reply recorded, no `follow_up_1_date` set

**When:**
- User runs `/dossier Acme PropTech`

**Then:**
- Step 2 detects: company in log, status = `sent`, no reply, ≥5 business days elapsed
- Before running the full brief, skill outputs: "Acme PropTech is in your Outreach Log (status: sent, sent [date] — 9 business days ago, no reply). Run follow-up mode instead of a fresh brief? [Y/n]"
- If user answers Y:
  - Skill generates a follow-up message ≤75 words
  - Message opens with a specific reference to the first outreach (not "I reached out previously")
  - Message adds one new piece of value (new signal, new observation, or relevant development)
  - Message does not include "just checking in"
  - Outreach Log diff is shown: `follow_up_1_date` → today
  - User is prompted to confirm before writing
  - If `thread_id` is blank in the log: note that threading is not possible, create new draft
- If user answers N:
  - Full dossier brief runs normally from Step 4

---

## Scenario 6: Persona Fields Absent from Profile

**Given:**
- Profile exists with background, pitch angles, war stories, key metrics, and tone notes
- Profile does NOT include `outreach_posture`, `target_seniority`, or `risk_tolerance` fields
- Signal context exists for the target company
- Research returns valid results

**When:**
- User runs `/dossier SomeCompany`

**Then:**
- Step 1 parses the profile successfully (does not error on missing persona fields)
- Section 3 opens with: "Persona fields not found in profile — defaulting to Exploratory / VP / Moderate."
- Angle ranking reflects Exploratory posture (curiosity/question-framing angles ranked higher)
- Recommended contact target title is VP-level
- Draft Para 3 closes with an open conditional (matching Exploratory default)
- Output is otherwise complete — skill does not stop or warn beyond the Section 3 note

---

## Scenario 7: --lean Flag with --brief-only

**Given:**
- Profile exists with all required fields, research depth = `deep`
- Signal context exists for the target company

**When:**
- User runs `/dossier SomeCompany --lean --brief-only`

**Then:**
- Depth resolution picks `lean` (flag takes precedence over profile setting)
- Research executes with max 5 sources (~3k token budget): homepage, 1 job posting, 1 news item
- Sections 1–4 are generated (brief only — `--brief-only` flag)
- Section 5 (draft) is not generated
- No output mode auto-stop message is shown (this is intentional --brief-only, not a confidence-based stop)
- Auto-log diff is shown after brief; user prompted to confirm (--no-log was not passed)
