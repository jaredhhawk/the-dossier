# Apply-Flow v2 — Resume Doc (mid-execution handoff)

> Handoff for the next session. 8 of 15 plan tasks done; 7 remaining. Replaces the prior 2026-05-01 RESUME.md (Plan 1 → Plan 2 transition); Plan 1 is merged to main and Plan 2 design + plan are revised and partially executed.

**Created:** 2026-05-03
**Branch:** `feat/apply-flow-v2` in worktree `~/code/the-dossier-apply-flow-v2/`
**Plan:** `docs/superpowers/plans/2026-05-02-apply-flow-v2-batch-triage-and-execute.md`
**Spec:** `docs/superpowers/specs/2026-05-02-apply-flow-v2-batch-triage-and-execute-design.md`

---

## What's done (Phases 0, A, B, C, D — Tasks 0-7)

| Task | What | Commit | Tests |
|---|---|---|---|
| 0 | `migrate_ledger.py` (one-shot ledger schema migration) | `baab478` + `1bfb2fa` (review fixes) | 8 |
| 1 | CL `.md` persistence in `cover_letter.py` + `pregenerate.py` | `2ce0158` | 1 |
| 2 | `tracker.py` with AppStatus enum, upsert, ledger_eligible, record_attempt atomicity | `080cfed` | 20 |
| 3 | `tracker_cli.py` with `--status` flag | `1497067` | 5 |
| 4 | `/apply` skill rewrite to delegate to `tracker_cli` | `550d495` | (markdown only) |
| 5 | `cl_flag_scan.py` placeholder regex | `ace6626` | 6 |
| 6 | `triage_writer.py` pure functions | `bbd8787` | 14 |
| 7 | `triage_writer.py` CLI + idempotency guard | `5d078a7` | 8 |

**Test count: 103 passed** (was 41 baseline before Task 0).

All commits on `feat/apply-flow-v2`. 9 commits ahead of `main`. Plus 6 docs commits (spec + plan + revisions).

## What's left (Phases E, F, G — Tasks 8-13)

| Task | What | Estimated hrs |
|---|---|---|
| 8 | `execute.py` parser + state writer (pure functions) | 1.5 |
| 9 | POC extraction: `override_greenhouse_artifacts()` wrapper in `apply_flow_poc.py` | 0.2 |
| 9.5 | `ats_signals.py` with `greenhouse_confirmed()` URL/DOM poll | 1.5 |
| 10 | `execute.py` Playwright loop + CLI (largest task — uses ats_signals + tracker.record_attempt) | 2.5 |
| 11 | `/pipeline` skill markdown additions for `review --batch` and `execute` | 0.3 |
| 12 | Gated e2e integration test | 1.0 |
| 13 | `apply_flow_v2_README.md` operator docs | 0.3 |
| **Total** | | **~7.3 hrs** |

Test count target: 130+ (after Task 12 — slow e2e is gated).

## How to resume

1. **Read this doc.** Skim the spec + plan files listed at top for full context.
2. **Re-invoke `superpowers-subagent-driven-development`** with a brief like:
   > Continue executing apply-flow v2 plan starting at Task 8. Tasks 0-7 are done at commits `baab478..5d078a7`. Worktree state is clean. Baseline: 103 tests passing. Plan: `docs/superpowers/plans/2026-05-02-apply-flow-v2-batch-triage-and-execute.md`.
3. **Or execute inline.** Tasks 4, 9, 11, 13 are tiny — controller can do them directly. Tasks 8, 9.5, 10 are substantial; dispatch implementer subagents.

## Code observations from this session

- **Task 0 review-fix lessons applied throughout.** All TSV writes use `newline=""` + `lineterminator="\n"` + `extrasaction="ignore"` + atomic temp+rename. Apply the same hardening to any new module that ships TSV writes.

- **`_render_to_disk` lifted to module level in `cover_letter.py`** so monkeypatch can target it. Plan 1's lazy import is now eager. Pregenerate uses the same helper.

- **CL `.md` persistence is forward-only.** Existing PDFs in `pipeline/data/cover_letters/output/` from Plan 1 don't have `.md` siblings. Triage_writer's `(no preview available)` fallback handles this gracefully. After re-running pregenerate, fresh CLs will get `.md` sidecars.

- **Real ledger migrated 2026-05-03.** Ran `migrate_ledger` against `/Users/jhh/code/the-dossier/pipeline/data/ledger.tsv` during Task 0 smoke testing. Header now has `last_attempt_at` + `attempt_count`. Forward-compatible: old code (current main branch) ignores unknown columns via `csv.DictReader`.

- **Triage_writer smoke test produces a real triage note** at `/tmp/test-triage.md` from the existing 2026-04-22 manifest. 5 cards, 0 unresolved (per the manifest), `(no preview available)` for CL previews (PDFs predate Task 1's change).

## Pacing tip for next session

Tasks 8 and 9 can ship together (parser/state + POC extraction). Task 9.5 (ats_signals) is genuinely independent — the unit tests use a mocked Playwright page. Task 10 (execute Playwright loop) depends on 8, 9, AND 9.5; do it last in Phase F. Tasks 11-13 are easy. Plan executor pacing: ~3 substantial dispatches (8/9 combined, 9.5, 10) + 3 quick ones (11, 12, 13).

## Open items / risks (carried over from spec)

1. ~~Plan 1 manifest schema may need `archetype`~~ — verified present.
2. Vault file write conflicts with active Obsidian sync — mitigation in place (line-based replacement).
3. Greenhouse selector drift — Plan-3 concern but log selector matches at info level for forensics in Task 10.
4. CL flag false-positive rate — empirical validation deferred (no real CL `.md`s exist yet; will refine after first execute run).
5. Confirmation false positives/negatives — Plan 2 ships conservative Greenhouse-only via Task 9.5; Plan 3 will refine.
6. Schema migration on shared ledger — done.

## Final-branch finishing checklist (when all 15 tasks done)

- [ ] All tests passing (`pytest -m "not slow"` ≥ 130)
- [ ] Slow tests pass (`pytest -m slow` — gated e2e + PDF render)
- [ ] Smoke test: `/pipeline review --batch` against real manifest works
- [ ] Smoke test: `/pipeline execute --dry-run` against ticked triage works
- [ ] Manual eyeball: triage note renders cleanly in Obsidian on phone
- [ ] PR description summarizes the 8-phase build + test count delta (41 → ~130)
- [ ] After merge: update vault index `R - Apply-Flow Plans Index.md` `file://` paths from `~/code/the-dossier-apply-flow-v2/` to `~/code/the-dossier/`

---

*Resume doc written 2026-05-03 mid-execution. Next session continues at Task 8.*
