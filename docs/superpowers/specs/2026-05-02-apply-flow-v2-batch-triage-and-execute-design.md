# Apply-Flow v2 — Batch Triage UI + Execute Mode (Design)

**Date:** 2026-05-02
**Status:** Design approved (brainstorming complete)
**Branch:** `feat/apply-flow-v2`
**Worktree:** `~/code/the-dossier-apply-flow-v2/`
**Predecessor:** [Plan 1: CL PDF + Pregeneration](../plans/2026-05-01-apply-flow-v1-cl-pdf-pregeneration.md) (merged to main)

## Goal

Reduce per-application time from 8-12 min to 30-60 sec by adding two commands on top of the Plan 1 pre-generation manifest:

- `/pipeline review --batch` — write a daily triage note in the vault listing all A/B cards, with checkboxes for triage decisions (phone-friendly).
- `/pipeline execute` — read the triage note, drive a Playwright session through ticked cards, pause for human submit per card, log submitted cards to the Application Tracker.

This is State B from the [Pipeline Apply-Flow Diagnostic](../../../99_System/Job Search/Pipeline Apply-Flow Diagnostic.md): pre-generation overnight, triage on phone, then a focused 10-15 min apply session at the desk.

## Non-Goals (Plan 3 scope)

- Multi-ATS adapters beyond Greenhouse (Lever, Ashby)
- LLM essay pass for textareas
- Programmatic Simplify autofill triggering
- Fully unattended submit (Q4 option C, rejected)

## Locked Decisions (from brainstorming)

| Question | Decision |
|---|---|
| Markdown shape | Option A: one section per card, verbose, vault-side |
| Triage path | `~/Documents/Second Brain/99_System/Job Search/Daily Triage YYYY-MM-DD.md` |
| Unresolved-URL strategy | Strategy C: surface in markdown with disabled checkbox + warning, execute skips |
| Persistence | Markdown checkbox transitions (`[x] apply` → `[x] applied`); no sidecar state file |
| Submit mode | Pause-before-submit per card (Q4 option A) |
| Tier A pitch routing | End-of-session prompt with company list (Q5 option B) |
| Outreach hook | Skip — Application Tracker only (Q6 option A) |
| CL preview source | First 200 chars of `cover_letters/output/{name}.md` |
| Tracker integration | Extract `/apply` skill's tracker-write logic to `pipeline/tracker.py` shared helper |
| Simplify wait | `simplify_wait_seconds` config (default 3s) + `--simplify-wait` flag + `PIPELINE_EXECUTE_SIMPLIFY_WAIT` env. Sleep is the floor; poll for Simplify-done up to 2x as a ceiling |

## Architecture

```
/pipeline review --batch
  └─ writes Daily Triage YYYY-MM-DD.md from manifest + scored JSON
       (markdown writer; no Playwright; safe to run any time)

/pipeline execute [<note-path>]
  └─ reads Daily Triage YYYY-MM-DD.md → queues [x] apply cards
  └─ for each queued card:
       1. Pre-flight: CL flag-pattern scan (warn-only)
       2. Launch persistent Chrome (POC pattern)
       3. Override resume + CL via set_input_files
       4. Wait for human submit
       5. tracker.append_row() → flip [x] apply → [x] applied
  └─ end-of-session: print Tier A pitch prompt
```

### New modules

- `pipeline/triage_writer.py` — manifest + scored JSON → daily triage markdown
- `pipeline/execute.py` — markdown reader + Playwright driver + state writer
- `pipeline/tracker.py` — shared helper for Application Tracker append + dedup ledger check
- `pipeline/tracker_cli.py` — thin `python -m` wrapper around `tracker.append_row()` so the `/apply` skill can call it as a subprocess without importing

### Modified modules

- `pipeline/cover_letter.py` — write `.md` alongside `.pdf` unconditionally (currently only writes `.md` with `--markdown-only`)
- `pipeline/apply_flow_poc.py` — extract `override_greenhouse_artifacts(page, resume_path, cl_path)` as a reusable function imported by `execute.py`
- `.claude/skills/pipeline/SKILL.md` — add `review --batch` and `execute` subcommand sections
- `.claude/skills/apply/SKILL.md` — replace inlined tracker logic with a call into `pipeline/tracker.py`

### Unchanged

- `pipeline/pregenerate.py` — manifest is already the contract from Plan 1
- `/pipeline` Stage 1-3 (discovery, scoring, single-card review)
- `/scout`, `/dossier`, `/pitch` skills
- Application Tracker schema

## Components

### `pipeline/triage_writer.py`

**Inputs:**
- `--manifest <path>` (default: most recent `pipeline/data/pregenerated/{date}-manifest.json`) — provides `company`, `role`, `url`, `grade`, `archetype`, `resume_pdf`, `cl_pdf`, `jd_cache` per card.
- `--scored-file <path>` (default: the `scored_file` field inside the manifest) — provides `salary`, `rationale` (used as "Fit"), `red_flags` (used as "Risks"; may be empty list), and `lane` for each card, indexed by URL. The manifest is the artifact contract; the scored JSON is the editorial-content contract.
- `--output <path>` (default: `~/Documents/Second Brain/99_System/Job Search/Daily Triage {date}.md`)
- `--force` (default: false; overrides "triage in progress" guard)

**Output:** writes the triage markdown. Creates `99_System/Job Search/` folder on first run.

**Per-card section (Option A):**
```markdown
## [B] The Boeing Company — Senior Product Management Specialist
- Salary: $194,150-$194,150 | Archetype: ai_technical | Lane: A
- Fit: AI/analytics PM in Boeing defense group. AI experience differentiates. Defense hiring is slower but less saturated.
- Risks: (none flagged)
- JD: https://jobs.boeing.com/job/tukwila/senior-product-management-specialist/185/86976368080
- Resume: pipeline/data/resumes/output/Jared-Hawkins-The-Boeing-Company-Senior-Product-Management-Specialist-2026-04-22.pdf
- CL: pipeline/data/cover_letters/output/Jared-Hawkins-The-Boeing-Company-Senior-Product-Management-Specialist-2026-04-22.pdf
- CL preview: "Building a product-led analytics and AI org inside one of the world's most complex industrial enterprises is a genuinely hard problem..."
- [ ] apply
- [ ] skip
```

Field mapping from data sources:
- "Fit" line ← scored JSON `rationale` (verbatim)
- "Risks" line ← scored JSON `red_flags` (joined with `; `; `(none flagged)` if empty)
- "Salary" line ← scored JSON `salary` (verbatim; `not listed` if empty)

**Top-of-file:**
```markdown
---
created: 2026-05-02
tags: [job-search, triage]
---

# Daily Triage 2026-05-02

5 A/B cards · 0 unresolved · manifest: pregenerated/2026-04-22-manifest.json

Tick `[x] apply` on cards to apply to. Run `/pipeline execute` after.

---
```

**Unresolved-URL cards:**
```markdown
## [B] Triplenet Technologies — Product Manager
- URL unresolved (Adzuna redirect only) — run `/pipeline resolve-urls` first
- ~~[ ] apply~~ ~~[ ] skip~~
```
The strikethrough checkboxes are visual only — execute's parser ignores them either way (no `[x] apply` mark = not queued).

**Order:** A grades first, then B. Within grade, alphabetical by company.

**CL preview source:** first 200 chars of the persisted `.md` sibling of the CL PDF, ellipsis-suffixed if truncated. If the `.md` doesn't exist (e.g., manually-generated CL), preview line says `(no preview available)`.

**Idempotency:** if the target file exists AND contains any `[x] apply` or `[x] applied` marks, refuse to overwrite without `--force`. Prevents accidental wipe of mid-flight triage.

### `pipeline/execute.py`

**Inputs:**
- `<note-path>` positional (default: today's `Daily Triage {date}.md`)
- `--simplify-wait <seconds>` (overrides config default)
- `--dry-run` (parse + report queue, no Playwright)

**Per-card loop:**

1. **CL pre-flight scan.** Read `{cl_pdf_basename}.md`. Regex match against `\[X\b`, `\[INSERT\b`, `\bfill in\b`, `\bbefore sending\b` (case-insensitive). On match: print warning with matched fragment + 80 chars of context, prompt `[p]roceed / [s]kip / [q]uit`.

2. **Launch Chromium.** Persistent profile at `~/Library/Application Support/the-dossier-apply-flow/`. Side-loaded Simplify extension from `~/Library/Application Support/Google/Chrome/Default/Extensions/pbanhockgagggenencehbnadejlgchfc/`. (POC pattern, validated 2026-05-01.)

3. **Navigate** to the card's resolved URL.

4. **Wait + poll for Simplify.**
   - Sleep `simplify_wait_seconds` (default 3, configurable via flag/config/env).
   - Poll for Simplify-done signal up to `2 * simplify_wait_seconds`: either the "Autofill this page" button disappears OR the email field is populated.
   - If poll times out: log warning, proceed anyway.

5. **Override** resume + CL via `set_input_files` on Greenhouse selectors (`id*="resume"`, `id*="cover"`). Uses `override_greenhouse_artifacts()` extracted from `apply_flow_poc.py`.

6. **Pause.** Print `Form ready for {company} — {role}. [Enter] = submitted, [s] = skip, [q] = quit.` Wait for stdin.

7. **On Enter:**
   - Call `tracker.append_row(card)` first (returns `(True, "appended")` or `(False, "duplicate: applied YYYY-MM-DD")`).
   - On success or duplicate: rewrite `[x] apply` → `[x] applied` in the markdown via line-based replacement.
   - On unexpected tracker error: log to stderr, leave checkbox at `[x] apply`, continue queue.

8. **On 's':** rewrite `[x] apply` → `[ ] apply skipped`. No tracker write.

9. **On 'q':** stop loop. Remaining `[x] apply` cards stay queued for next run.

**End-of-session output:**
```
Submitted: 4/5 cards (1 skipped)
Tier A applied today — run /pitch for:
  - Orkes
  - Avante
```
Tier A = grade A only. B grade does not trigger pitch prompt.

### `pipeline/tracker.py`

Public API:
- `append_row(card: dict, source: str = "Pipeline") -> Tuple[bool, str]` — checks dedup ledger, appends row to `R - Application Tracker.md` if new, returns `(success, msg)`.
- `_format_row(card, source) -> str` — formatting helper, exported for testing.
- `_check_dedup(company, role) -> Optional[str]` — returns ISO date if previously applied, None otherwise.

`/apply` skill is rewritten to invoke this via `python -m pipeline.tracker_cli` (thin wrapper around `append_row` for skill use). The shared logic lives in `tracker.py`; the CLI lives in `tracker_cli.py` so test imports stay clean.

### `pipeline/cover_letter.py` change

Currently the `--markdown-only` flag is the only path that writes `.md`. Modify so that the PDF render path also writes `.md` as a side effect, before invoking the PDF renderer. ~3 LOC. The `--markdown-only` flag continues to mean "skip PDF render entirely."

### `apply_flow_poc.py` extraction

Pull the Greenhouse override sequence (clear-existing-file, then `set_input_files` on resume + CL) into:

```python
def override_greenhouse_artifacts(page, resume_path: Path, cl_path: Path) -> None:
    """Override Simplify-attached resume and CL on a Greenhouse form.
    POC-validated 2026-05-01. Single ATS only — Lever/Ashby in Plan 3."""
```

POC stays as a runnable smoke test; `execute.py` imports the function.

### Skill markdown updates

`.claude/skills/pipeline/SKILL.md` gains:
- New "Batch triage mode" section under Stage 3 documenting `/pipeline review --batch`
- New "Stage 4: Execute" section documenting `/pipeline execute`
- Pre-req chain noted: `pregenerate` → `review --batch` → `execute`

`.claude/skills/apply/SKILL.md` gains:
- Implementation note: Step 5 (tracker write) now invokes `python -m pipeline.tracker_cli` instead of inlining the markdown manipulation. User-facing behavior unchanged.

## Data Flow

```
pregenerate.py  ──→  manifest + resume.pdf + CL.pdf + CL.md + JD.txt
                          │
                          ▼
review --batch  ──→  Daily Triage YYYY-MM-DD.md (vault)
                          │
              [HUMAN: triage on phone, tick [x] apply]
                          │
                          ▼
execute  ──→  Playwright session
                  │
                  ├─→ tracker.append_row() ─→ Application Tracker.md (vault)
                  ├─→ rewrite [x] apply → [x] applied (vault)
                  └─→ end-of-session: Tier A pitch prompt to stdout
```

I/O surfaces:
- **Vault writes:** `Daily Triage YYYY-MM-DD.md` (created by writer; line-rewritten by execute) + `R - Application Tracker.md` (appended by tracker.py).
- **Manifest read-only.** Plan 2 never writes the manifest.
- **Browser state:** persistent Chromium profile at `~/Library/Application Support/the-dossier-apply-flow/` (gitignored, separate from user's regular Chrome). Side-loaded Simplify extension is read-only.

## Error Handling

### Recoverable per-card (queue continues)

| Failure | Behavior |
|---|---|
| CL flag-pattern hit | Warn + prompt proceed/skip/quit |
| Page load timeout | Mark `[x] apply error: page timeout`, continue |
| Selector miss (DOM changed) | Mark `[x] apply error: selector miss`, continue |
| `set_input_files` failure | Mark `[x] apply error: upload failed`, continue |
| Tracker write fails (file lock, sync conflict) | Log to stderr, surface at end-of-session, continue |

Error-state lines render as `[x] apply error: <msg>`. Parser treats them as "skipped, do not re-execute" — same as `[x] applied` for queue-skipping purposes, but distinguishable for forensics.

### Recoverable session-level (stop, queue intact)

| Failure | Behavior |
|---|---|
| Chromium fails to launch | Fail fast, no markdown writes, exit 1 |
| Persistent profile corrupted | Suggest profile reset, exit 1 |
| Manifest stale (PDF paths missing) | "Run /pipeline pregenerate first.", exit 1 |
| User hits 'q' | Stop loop, leave queued cards as-is |

### Unrecoverable

| Failure | Behavior |
|---|---|
| Daily triage note missing | "Run /pipeline review --batch first.", exit 1 |
| Triage note has `[x] applied` for unresolved-URL card | Markdown corruption, exit 1 |
| Tier A pitch list contains card with no metadata | Log warning, omit from list |

### Order-of-operations invariant

Within step 7 of execute (on Enter):
1. **First:** `tracker.append_row()`
2. **Then:** rewrite `[x] apply` → `[x] applied`

If we crash between (1) and (2), re-execute reattempts the card; tracker dedup catches the duplicate; cost is one extra Playwright cycle + a no-op tracker call. The reverse order would let an "applied" mark exist in the markdown without a corresponding tracker row, which is silent drift.

## Testing

Network-free. Same philosophy as Plan 1's 42 tests.

### Unit tests (~25-30 new)

**`test_triage_writer.py`** (8-10 tests)
- Manifest + scored JSON → expected markdown (golden file)
- CL preview reads first 200 chars, ellipsis-truncates correctly
- Unresolved-URL cards render with strikethrough checkboxes + warning line
- A grades sorted before B; alphabetical within grade
- Missing CL `.md` → `(no preview available)` instead of crashing
- Idempotency refuses overwrite when `[x] apply` marks exist; `--force` overrides
- Empty manifest → empty triage with "0 cards" banner, no crash

**`test_execute_parser.py`** (6-8 tests)
- Parses Option A sections back to card structs
- Skips `[x] applied`, `[x] apply error: *`, `[ ] apply`, `[x] skip` cards
- Includes `[x] apply` cards
- Tolerates trailing whitespace, tabs, blank lines, section ordering
- Handles disabled-checkbox (strikethrough) syntax — never queues those cards
- Round-trips: writer output → parser → writer output (stable)

**`test_execute_state.py`** (5-6 tests)
- Line-based rewrite changes only the target line
- Edge cases: tabs vs spaces, trailing whitespace, alternate bullet chars
- Error-state line `[x] apply error: <msg>` round-trips through parser as do-not-re-execute
- Idempotent: rewriting an already-`[x] applied` line is a no-op

**`test_cl_flag_scan.py`** (4-5 tests)
- Patterns match the four targets case-insensitively
- False-positive guard: bracketed legit fragments (e.g., `[X-Series]` in a real product name) do NOT match — pattern uses word boundaries
- Verified empirically against the 5 existing CL `.md` files in the worktree (zero false positives)

**`test_tracker.py`** (5-6 tests)
- Append produces row matching existing tracker convention exactly
- Dedup check returns date for previously-applied, None for new
- Concurrent append is safe (file-locking or last-write-wins documented)
- Tracker file missing → creates it with header

### Integration test (1, gated by `@pytest.mark.slow`)

**`test_execute_e2e.py`**
- Boots fake Greenhouse-shape HTML on `localhost:0` via `http.server`
- Runs execute against a triage note pointing at the fake URL
- Asserts: `set_input_files` received the right paths, checkbox flips, tracker row written
- No real ATS, no real Simplify

### Total target

42 (Plan 1) → ~70 tests. All network-free except the gated e2e.

### What's not tested

- Real Greenhouse pages (post-spike validation, manual)
- Lever / Ashby (Plan 3 scope)
- Custom essay LLM pass (Plan 3 scope)
- Phone-side Obsidian render (manual eyeball)

## Open Risks

1. ~~**Plan 1 manifest schema may need an `archetype` field that isn't there.**~~ Resolved 2026-05-02: confirmed `archetype` is present in `2026-04-22-manifest.json`. Manifest schema as documented in Plan 1 is sufficient.
2. **Vault file write conflicts with active Obsidian sync.** Mitigation: line-based replacement (not full-file rewrite) reduces collision surface. Surfaces at end-of-session if it happens.
3. **Greenhouse selector drift.** Plan-3-level concern but worth flagging — extracted `override_greenhouse_artifacts()` should log selector matches at info level for forensics on first regression.
4. **CL flag false-positive rate unknown until empirically validated against more than 5 CL `.md` files.** Plan: run scan against all CL `.md`s in `cover_letters/output/` as part of test fixture build.

## Estimate

| Component | Hours |
|---|---|
| `triage_writer.py` + tests | 2.5 |
| `execute.py` + tests | 3.5 |
| `tracker.py` extraction + skill rewrites | 1 |
| CL `.md` persistence + flag scan + tests | 1 |
| Skill markdown updates + integration test | 1 |
| **Total** | **~9 hrs** |

(RESUME.md estimated 6-8 hrs. The +1 reflects the tracker extraction and CL `.md` persistence sub-tasks that fell out of brainstorming.)

## Predecessors and Dependents

- **Plan 1 (merged):** provides the manifest contract this plan reads.
- **Plan 3 (post-Plan 2):** multi-ATS adapters, LLM essay pass, programmatic Simplify trigger. Will reuse the Plan 2 execute loop and add ATS-specific override functions.

---

*Design approved 2026-05-02 via brainstorming. Next: spec review loop, then writing-plans skill.*
