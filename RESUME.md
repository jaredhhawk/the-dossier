# Apply-Flow v1 — Plan 2 Resume Doc

> Handoff for the next session. Plan 1 is shipped to main; Plan 2 starts here.

**Created:** 2026-05-01
**Worktree:** `~/code/the-dossier/` on `main` (Plan 1 was merged here; POC worktree was cleaned up)
**Suggested:** create a fresh worktree for Plan 2 via `superpowers-using-git-worktrees`

---

## What's done (Plan 1)

- ✅ CL PDF generator (`pipeline/cover_letter.py`) — two backends behind `_make_default_adapter()` dispatcher:
  - `claude_cli` (default): subprocess to `claude --print`, bills against Max sub, ~110s/card
  - `anthropic_sdk` (opt-in via `PIPELINE_CL_BACKEND=anthropic_sdk`): API path, ~1-2s/card, escape hatch
- ✅ Shared `pipeline/pdf_render.py` for HTML→PDF (extracted from resume.py)
- ✅ Pre-generation orchestrator (`pipeline/pregenerate.py`) — idempotent batch script:
  - Filters scored JSON to A/B/new cards
  - Generates resume + CL + cached JD per card
  - Writes manifest at `pipeline/data/pregenerated/{date}-manifest.json` (Plan 2's read interface)
  - Mutates scored JSON in place to add `artifacts` field per processed card
- ✅ 42 pytest tests, all network-free (CLI adapter via mocked subprocess.run, SDK via duck-typed FakeClient)
- ✅ Operator README at `pipeline/apply_flow_v1_README.md`
- ✅ End-to-end smoke test verified on real Boeing card (no API charge, valid PDF, idempotent re-run)

## What Plan 2 needs to add

From the diagnostic at `~/Documents/Second Brain/02_Projects/Job Search Pipeline/Pipeline Apply-Flow Diagnostic.md`:

| Component | Estimate |
|---|---|
| `/pipeline review --batch` markdown writer (writes `99_System/Job Search/Daily Triage YYYY-MM-DD.md` with all A/B cards as sections, `[ ] apply` / `[ ] skip` checkboxes) | 2-3 hrs |
| `/pipeline execute <note>` reader (parses checkbox marks, queues `[x] apply` cards, drives apply-flow per card) | 3-4 hrs |
| Resume mid-flight after interruption (use `[x] apply` → `[x] applied` checkbox transition as state) | 1 hr |
| **Total Plan 2** | **~6-8 hrs** |

## Before writing the plan — vet with real-data observation (recommended)

Run `pregenerate.py` on a real 5-10 card batch on main first. This will inform Plan 2 UX decisions you can't predict abstractly:

```bash
cd ~/code/the-dossier && pipeline/.venv/bin/python3 -m pipeline.pregenerate \
  --scored-file pipeline/data/scored/2026-04-22.json --limit 10
```
~20 minutes wall time via Claude CLI backend (no API charge).

After that, eyeball the 10 CL PDFs. Questions to answer before designing Plan 2:
- **CL quality**: Are they good enough that you'd default to `[x] apply` checked, or do you want `[ ] apply` unchecked + a CL preview line in the markdown so you skim before checking?
- **Triage friction**: Is the bottleneck really the per-card decision, or is it the apply-flow click-through itself?
- **Cards without resolved_url**: ~28/38 cards in the existing scored JSON have only Adzuna redirector URLs. Plan 2 needs a strategy: skip them in the manifest? Trigger URL resolution as a pregenerate step? Surface them in the markdown but not in execute?

## Open questions for Plan 2 (per diagnostic)

- **Submit mode in execute**: pause-before-submit per card (safe), pause-on-difficulty (auto-submit clean fills, pause on essays), or fully unattended? Decide after seeing real CL quality.
- **Tier A pitch routing**: when execute hits a Tier A card, auto-queue `/pitch` outreach in the same session, or surface as a separate end-of-session prompt?
- **Persistence**: `[x] apply` → `[x] applied` after submit (use the markdown as the state file)? Or external `.state.json` next to it?
- **Outreach hook**: integrate `/outreach` log into post-submit step or leave to user?
- **Markdown shape**: one section per card with grade/title/company/salary/key fit/red flags/JD link/checkbox? Or a denser table format? Phone-friendly was a stated requirement.

## Manifest schema (Plan 2's input contract)

```json
{
  "date": "2026-04-22",
  "scored_file": "/abs/path/to/2026-04-22.json",
  "generated_at": "2026-05-01T13:28:44",
  "counts": {"generated": 1, "cached": 0, "failures": 0},
  "generated": [
    {
      "company": "...", "role": "...", "url": "...",
      "grade": "A|B", "archetype": "product_management|...",
      "resume_pdf": "/abs/path/...", "cl_pdf": "/abs/path/...", "jd_cache": "/abs/path/..."
    }
  ],
  "cached": [/* same shape */],
  "failures": [{"company": "...", "role": "...", "url": "...", "grade": "...", "archetype": "...", "reason": "..."}]
}
```

Plan 2 should treat `generated[] + cached[]` as the union of "ready to apply" cards. The scored JSON itself also has `artifacts` fields on processed cards (same data, indexed by URL) — pick one source of truth.

## How to start Plan 2 next session

1. Create a fresh worktree: `superpowers-using-git-worktrees` skill → branch `feat/apply-flow-v2`
2. Re-read this doc + the apply-flow diagnostic in vault for full context
3. Run pregenerate on 5-10 real cards (see "Before writing the plan" above)
4. Use `superpowers-brainstorming` skill to align on the open questions before coding
5. Use `superpowers-writing-plans` to spec out the implementation
6. Execute via `superpowers-subagent-driven-development`

## Reference

- Plan 1 main plan: `docs/superpowers/plans/2026-05-01-apply-flow-v1-cl-pdf-pregeneration.md`
- Plan 1 mid-execution pivot (CLI backend swap): `docs/superpowers/plans/2026-05-01-cl-cli-backend-pivot.md`
- Operator README: `pipeline/apply_flow_v1_README.md`
- POC code (still relevant for Plan 3 when adding Lever/Ashby selectors): `pipeline/apply_flow_poc.py`
- Diagnostic (vault): `02_Projects/Job Search Pipeline/Pipeline Apply-Flow Diagnostic.md`
- Backlog (vault): `02_Projects/Job Search Pipeline/Pipeline Scoring + Data Optimization Backlog.md`
- Memory entry: `~/.claude/projects/-Users-jhh-Documents-Second-Brain/memory/project_pipeline_cl_cost_followup.md` (CLI backend ship notes)

## Plan 3 reminder (post-Plan 2)

After Plan 2 ships, Plan 3 covers: multi-ATS adapters (Lever + Ashby beyond Greenhouse), LLM essay pass for textareas, programmatic Simplify autofill trigger. ~9-11 hrs.
