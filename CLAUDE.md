# The Dossier — Claude Code Project Context

**Project:** Three-skill pipeline for pre-emptive job search outreach
**Type:** Claude Code skills (markdown-only, no runtime dependencies)
**Status:** All three skills in production

---

## The Three Skills

- `.claude/skills/scout/SKILL.md` — finds companies with hiring signals, filters negatives, enriches with GitHub data, seeds the outreach log
- `.claude/skills/pitch/SKILL.md` — first-touch cold outreach (lite research, 1 angle, 1 war story, ~100-word email). Also owns follow-up and bounce-recovery workflows.
- `.claude/skills/dossier/SKILL.md` — deep research + strategy. No cold-outreach drafting. Apply mode generates cover letter + resume tweaks + LinkedIn snippet to recruiter.

**Companion user skills** (live in the user's vault, not this repo): `/apply`, `/outreach`, `/prep`, `/story`.

---

## Architecture

```
User runs:
  /scout             → finds candidates, appends to Outreach Log
  /pitch [company]   → ~3k tokens, drafts first-touch email
  /dossier [company] → ~10k tokens, full research + strategy (no email)
  /dossier --apply   → + cover letter + resume tweaks + recruiter LinkedIn

Data flow:
  ~/.scout/profile.md       → identity, pitch angles, war stories, persona
  ~/.scout/runs/*.md        → Scout run archives (Pitch/Dossier read these)
  ~/.scout/seen.md          → Scout dedup list
  ~/.scout/blacklist.md     → permanent exclusions
  ~/.scout/github_signals.py → GitHub enrichment helper
  [Vault]/R - Outreach Log.md → cold outreach pipeline (shared state)
```

Skills are hard-linked between this repo and `~/.claude/skills/` so edits to either location stay in sync automatically. Check with `stat -f "%i %N" ~/.claude/skills/<skill>/SKILL.md .claude/skills/<skill>/SKILL.md` — identical inode confirms hard link.

---

## Why Three Skills (Not Two)

The skill was originally a single `/dossier` that did everything: research, strategy, cold email, LinkedIn snippet, Gmail draft, follow-ups, bounces, apply mode, interview context. That bloated every cold-outreach attempt to ~10k tokens, even though cold-outreach reply rates run 10-15% and most of the "strategic" output never got read.

The 2026-04-14 split:
- Cold outreach moved to `/pitch` (~3k tokens, 3 sources, one angle, one war story)
- `/dossier` kept deep research + apply mode (~10k tokens, 8+ sources, multi-angle comparison, war story scoring)
- Follow-up and bounce-recovery moved to `/pitch` (they're cold-outreach operations)
- `/dossier` no longer creates new Outreach Log rows — only appends `; Dossier [date]` to existing ones

Estimated funnel savings: ~60% at 10% reply rate.

---

## Key Constraints

- **No em-dashes** (—) in any draft output. Use period, comma, or restructure. Non-negotiable — comes from user preference.
- **Banned words list** in both /pitch and /dossier --apply drafts. Includes: passionate, excited to, leverage (as verb), robust, streamline, delve, cutting-edge, synergy, multifaceted, comprehensive, meticulous, etc.
- **Research caps are hard.** /pitch = 3 sources max. /dossier lean = 5, standard = 8, deep = 12. Stop when cap hit OR 2 consecutive sources yield no new facts.
- **Section 1 is frozen** in /dossier. No backward revision after it's written. Gaps get flagged in "What we don't know," not re-researched.
- **Confidence tags on email pattern inference** are non-negotiable — every recommended contact email needs `[source: ... → HIGH|MEDIUM|LOW]`.
- **Never auto-send email.** `--with-gmail` creates drafts, never sends. Sending requires manual action in Gmail.

---

## Development Approach

- **Edits flow through hard links** — editing `~/.claude/skills/<skill>/SKILL.md` or `.claude/skills/<skill>/SKILL.md` updates both. Always commit from this repo to track history.
- **Version bump in frontmatter** when behavior changes materially.
- **Atomic commits per material change.** Don't batch a flag addition + a protocol rewrite into one commit.
- **Companion vault doc** (`Second Brain/02_Projects/Job Search/Scout + Dossier/R - Scout Dossier Quick Start.md`) must stay in sync with any flag or behavior change.
- **User profile lives at `~/.scout/profile.md`** — personal, never committed. Template at `templates/profile-template.md` is the shippable version.

---

## When Working on the Skills

1. **Check both sides of hard link** if editing outside this repo — they should always agree.
2. **Flag-matrix discipline:** `/pitch` flags and `/dossier` flags should stay orthogonal. If they overlap, think hard before adding.
3. **Don't re-add cold-outreach drafting to /dossier.** That's the whole point of the split. If a use case pushes toward it, the right move is usually a new flag on `/pitch` or a chained call pattern, not a scope creep on `/dossier`.
4. **Apply mode stays in /dossier.** Cover letters are a different beast from cold outreach — different audience, different structure, different trigger — and they benefit from the deep research /dossier already does.
5. **The Outreach Log is shared state.** `/scout` creates rows (`Stage=New Lead`), `/pitch` drafts & follow-ups manage rows, `/dossier` only annotates Notes on existing rows. Don't break this contract.

---

## Related Files

- **Scout Skill Development (vault, historical):** `02_Projects/Job Search/Scout + Dossier/P - Scout Skill Development.md`
- **Scout + Dossier Hub (vault):** `02_Projects/Job Search/Scout + Dossier/P - Scout + Dossier Skills.md`
- **Quick Start (vault, user-facing ref):** `02_Projects/Job Search/Scout + Dossier/R - Scout Dossier Quick Start.md`
- **Automation plans (vault):** `02_Projects/Job Search/Scout + Dossier/P - Outreach Automation.md`
- **Outreach Log (vault, runtime):** `02_Projects/Job Search/Scout + Dossier/R - Outreach Log.md`
