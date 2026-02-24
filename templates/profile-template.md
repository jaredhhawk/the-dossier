# Scout / Dossier Profile

<!-- This is the canonical profile template for /scout and /dossier.              -->
<!-- Copy to ~/.scout/profile.md and fill in your details.                        -->
<!-- Both skills read this file. Nothing here is hardcoded — name things freely.  -->

---

## Name
[Your name]

## Contact
[email] | [location]

---

## Targeting

### Industries
<!-- List your target industries. /scout uses these directly in search queries.   -->
- [Your industry 1]
- [Your industry 2]
- [Your industry 3]

### Company Stage
- [e.g., Series A]
- [e.g., Series B]
- [e.g., Series C]

### Geography
- [Your location 1]
- [e.g., Remote-first]

---

## Settings

### Research Depth
<!-- Controls how many web sources /dossier fetches per company.                  -->
<!-- lean (max 5 sources) | standard (max 8 sources) | deep (max 12 sources)      -->
<!-- Override per-run with --lean or --depth= flags.                              -->
standard

---

## Persona Calibration

<!-- These three fields control how /dossier ranks angles and closes drafts.      -->
<!-- outreach_posture: Direct | Advisory | Exploratory                            -->
<!--   Direct      → assertive angles ranked higher; draft closes with a specific ask -->
<!--   Advisory    → offer-of-value framing; draft closes with a resource or insight  -->
<!--   Exploratory → curiosity/question framing; draft closes with an open conditional -->
<!-- target_seniority: IC | Manager | Director | VP | C-suite                     -->
<!--   Determines which title /dossier recommends as your outreach contact.       -->
<!-- risk_tolerance: Conservative | Moderate | Bold                               -->
<!--   Conservative → safest angle (highest confidence, lowest downside)         -->
<!--   Moderate     → balanced; favor angles with solid evidence                  -->
<!--   Bold         → highest expected-value angle even if confidence is lower    -->

outreach_posture: Exploratory
target_seniority: VP
risk_tolerance: Moderate

---

## Background Summary

<!-- 3–5 sentences. Your career spine. /dossier uses this for context when        -->
<!-- writing outreach. Be specific: companies, roles, standout metrics.            -->
[Short career summary with specific companies, roles, and standout metrics.]

---

## Pitch Angles

<!-- Your distinct value propositions. /dossier selects the best angle based on   -->
<!-- company context and signal type.                                              -->
<!-- Aim for 2–4 genuinely distinct angles — not variations of the same thing.    -->
<!-- Each angle = a name + one-liner positioning statement + optional context.     -->
<!-- Angles must differ in at least one of: business problem, capability,         -->
<!-- time horizon, org stakeholder.                                                -->

### [Angle Name, e.g., "0-to-1 Product"]
"[One-sentence positioning statement.]"

[Optional: 2–3 sentences of expanded context. When does this angle apply? What makes it credible?]

### [Angle Name, e.g., "Scaling Operations"]
"[One-sentence positioning statement.]"

[Optional: 2–3 sentences of expanded context.]

### [Angle Name, e.g., "GTM Alignment"]
"[One-sentence positioning statement.]"

[Optional: 2–3 sentences of expanded context.]

---

## War Stories

<!-- Format: Situation / Action / Result + optional Tags                           -->
<!-- Situation: context and the problem at stake (1–2 sentences)                  -->
<!-- Action:    what you specifically did — concrete, not vague (2–3 sentences)   -->
<!-- Result:    measurable outcome where possible (1–2 sentences)                 -->
<!-- Tags:      free-form keywords to hint at matching (/dossier matches           -->
<!--            semantically — tags are a guide, not required)                    -->
<!--                                                                              -->
<!-- Aim for 5–10 stories. Specific and metric-rich beats comprehensive.          -->
<!-- Tip: if you have STAR stories elsewhere, reformat as SAR.                    -->
<!--                                                                              -->
<!-- /dossier scores each story on 4 axes:                                        -->
<!--   Industry overlap (0–2)     Stage similarity (0–2)                         -->
<!--   Functional similarity (0–2) Signal alignment (0–2)                        -->
<!-- Functional similarity outranks industry overlap in ties.                     -->

### [Story Title, e.g., "First PM hire at Series A"]
**Situation:** [Context and problem — what was at stake?]
**Action:** [What you specifically did — avoid vague verbs like "led" or "drove".]
**Result:** [Measurable outcome. Include a number if possible.]
**Tags:** [e.g., 0-to-1, Series A, product strategy, hiring]

---

### [Story Title]
**Situation:**
**Action:**
**Result:**
**Tags:**

---

### [Story Title]
**Situation:**
**Action:**
**Result:**
**Tags:**

---

## Key Metrics

<!-- Standout numbers for /dossier to reference in outreach.                      -->
<!-- One metric per line. Include context (not just "grew revenue 3x" but         -->
<!-- "grew ARR from $500k to $1.5M in 18 months as first PM").                   -->
- [Metric 1: context + number]
- [Metric 2: context + number]
- [Metric 3: context + number]

---

## Tone Notes

<!-- How /dossier should write outreach for you.                                   -->
<!-- These override default behavior when specified.                               -->
- Write like a human, not AI. No buzzwords.
- Reference the specific signal — not generic praise.
- Conditional close always: "if X is on the roadmap."
- [Add your own preferences here]
