# Apply-Flow v1 — Resume Doc

> Handoff for the next session. POC is done; v1 starts here.

**Created:** 2026-05-01
**Branch:** `feat/apply-flow-v1` (in this worktree at `~/code/the-dossier-poc/`)
**Main worktree:** `~/code/the-dossier/` (don't work there for v1)

---

## What's done

- ✅ POC built + e2e validated on a real Greenhouse listing (LVT Sr Director PM)
- ✅ Override pattern proven: `set_input_files` injects tailored resume + CL PDFs into Greenhouse forms, no OS picker, no Simplify clobber
- ✅ Side-loaded Simplify works under Playwright control (Web Store install is blocked, so we side-load from user's regular Chrome)
- ✅ Persistent Chrome profile at `pipeline/.cache/chrome-profile/` survives across runs
- ✅ POC code in `pipeline/apply_flow_poc.py` (~170 lines, single file) + README
- ✅ All POC commits merged to main; this branch starts fresh from there

## What v1 needs to add

From the diagnostic at `~/Documents/Second Brain/02_Projects/Job Search Pipeline/Pipeline Apply-Flow Diagnostic.md`:

| Component | Estimate |
|---|---|
| CL PDF generator (UX §3 prereq — pipeline currently produces no CL PDFs) | 3-4 hrs |
| Pre-generation orchestration (overnight cron for resume + CL on every Grade A/B card) | 2-3 hrs |
| Batch triage UI (`/pipeline review --batch` writer + `/pipeline execute` reader, checkbox-marked apply queue) | 3-4 hrs |
| Multi-ATS adapters (Lever + Ashby in addition to Greenhouse) | 4-6 hrs |
| Programmatic Simplify autofill trigger (currently requires manual click — POC didn't automate this) | 2-3 hrs |
| Custom essay LLM pass (Claude API call with JD + CL as context, fills textareas) | 3-4 hrs |
| Tracker + ledger logging integration on submit | 2 hrs |
| **Total v1** | **~20-26 hrs** |

## Suggested v1 sequencing

Split into 3 plans (one per `/superpowers-writing-plans` invocation), each shippable:

1. **Plan 1: CL PDF generator + pre-generation cron.** Adds the missing artifact and overnight orchestration. ~5-7 hrs. Foundation for everything else.
2. **Plan 2: Batch triage UI + execute mode.** The two-pass design from UX §2. ~6-8 hrs. Replaces the per-card terminal loop.
3. **Plan 3: Multi-ATS + LLM essay + Simplify trigger.** The remaining adapter work. ~9-11 hrs. Last because it benefits from real apply-flow data from Plans 1+2.

## Open questions for v1

- **Simplify trigger:** programmatically click Simplify's "Autofill this page" button (need to inspect its sidebar DOM), or leave standard-field fill manual?
- **Submit mode:** pause-before-submit (POC default, safe), pause-on-difficulty (auto-submit clean fills, pause on essays), or fully unattended? Decided based on confidence after Plan 3.
- **Workday:** include or skip? POC cut Workday because of per-tenant brittleness. Diagnostic recommends skipping for v1.
- **Pitch routing:** when batch triage detects a Tier A card, auto-queue `/pitch` outreach in the same session, or surface as a separate end-of-session prompt?
- **CL PDF generator architecture:** reuse `resume.py`'s Playwright PDF stack (HTML → PDF), or use a simpler markdown-to-PDF path (pandoc, weasyprint)?

## Known v1 risks

- **Selector brittleness across ATSes.** Greenhouse, Lever, Ashby each have different DOM. Adapters will need real-form testing per ATS.
- **Simplify side-load and Google OAuth.** Already worked around for POC; verify nothing changes for v1.
- **Chrome version drift.** `--load-extension` behavior could change in future Chrome releases. Pin Chrome version or detect breakage.

## How to start v1 next session

1. `cd ~/code/the-dossier-poc/` (this worktree, on `feat/apply-flow-v1`)
2. Verify state: `git status` should show clean tree on `feat/apply-flow-v1`
3. Re-read the diagnostic in vault for full context
4. Pick a plan target (recommend Plan 1 first) and run `/superpowers-writing-plans`
5. Execute via `/superpowers-subagent-driven-development`

## Reference

- POC plan: `docs/superpowers/plans/2026-04-30-apply-flow-poc.md`
- POC code: `pipeline/apply_flow_poc.py` + `pipeline/apply_flow_poc_README.md`
- Diagnostic (vault): `02_Projects/Job Search Pipeline/Pipeline Apply-Flow Diagnostic.md`
- Backlog (vault): `02_Projects/Job Search Pipeline/Pipeline Scoring + Data Optimization Backlog.md`
- POC test command:
  ```
  cd ~/code/the-dossier && pipeline/.venv/bin/python3 ~/code/the-dossier-poc/pipeline/apply_flow_poc.py
  ```
- Test target (still works): https://job-boards.greenhouse.io/liveviewtechnologiesinc/jobs/5172740008
