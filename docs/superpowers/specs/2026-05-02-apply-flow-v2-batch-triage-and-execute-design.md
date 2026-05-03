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

## Locked Decisions (from brainstorming + 2026-05-02 ai-chat pressure-test)

| Question | Decision |
|---|---|
| Markdown shape | Option A: one section per card, verbose, vault-side |
| Triage path | `~/Documents/Second Brain/99_System/Job Search/Daily Triage YYYY-MM-DD.md` |
| Unresolved-URL strategy | Strategy C: surface in markdown with disabled checkbox + warning, execute skips |
| State authority | **Ledger is truth.** Markdown is intent. `build_queue` filters by ledger state (see "State Authority + Uncertainty Model" below) |
| Persistence | Markdown checkbox transitions (`[x] apply` → `[x] applied`) PLUS authoritative ledger row with status enum + last_attempt_at + attempt_count |
| Submit mode | Pause-before-submit per card (Q4 option A) |
| Submit verification | Post-Enter, poll for ATS-specific confirmation signal (Greenhouse only Plan 2) for ~10s. Hit → `applied`. Miss → `unverified` |
| Tier A pitch routing | End-of-session prompt with company list (Q5 option B) |
| Outreach hook | Skip — Application Tracker only (Q6 option A) |
| CL preview source | First 200 chars of `cover_letters/output/{name}.md` |
| Tracker integration | Extract `/apply` skill's tracker-write logic to `pipeline/tracker.py` shared helper. Tracker is append-only attempt log (one row per submission attempt) |
| Simplify wait | `simplify_wait_seconds` config (default 3s) + `--simplify-wait` flag + `PIPELINE_EXECUTE_SIMPLIFY_WAIT` env. Sleep is the floor; poll for Simplify-done up to 2x as a ceiling |

## State Authority + Uncertainty Model

The ai-chat pressure-test (2026-05-02) surfaced two structural issues with the original brainstorm: (1) "human Enter = submitted" trusts a fact never verified, and (2) the tracker/ledger schema couldn't represent uncertainty even if verification existed. This section locks the resolution.

### Schema

**Application Tracker (`R - Application Tracker.md`)** — append-only attempt log:
- Status column accepts: `Applied | Unverified | Failed`
- One row per *submission attempt*, not per (company, role). Retries produce additional rows.
- Existing rows (all `Applied`) need no migration; new enum values are forward-only.

**Dedup ledger (`pipeline/data/ledger.tsv`)** — current-state record, one row per (company, normalized_role):
- Existing columns: `url, company, normalized_title, location, date_first_seen, score, grade, status`
- New columns: `last_attempt_at` (ISO timestamp), `attempt_count` (int)
- Status enum: `applied | unverified | failed | skipped` (was: `applied`, plus pre-existing `seen | pitched` from `/scout`/`/pitch`)
- Migration: one-shot script (`pipeline/migrate_ledger.py`) adds the two new columns; backfills `last_attempt_at = date_first_seen`, `attempt_count = 1`. Idempotent (no-op if columns already present).

### Authority rules

`build_queue` filters cards by both markdown intent and ledger state:

```
queue = [card for card in markdown
         if card.state == APPLY
         and ledger_eligible(card)]

ledger_eligible(card):
    row = ledger.find(company, normalized_role)
    if row is None:                                            return True   # never attempted
    if row.status == applied:                                  return False  # done; blocks always
    if row.status == failed:                                   return True   # user explicitly re-ticked
    if row.status == unverified and row.last_attempt_at < 24h: return False  # cooling down
    if row.status == unverified and row.last_attempt_at > 24h: return True   # auto-retry eligible
    if row.status == skipped:                                  return True   # nothing happened last time
```

Markdown's `[x] apply` is *intent*. Ledger decides whether to act on intent. Drift between them resolves toward ledger every time.

### Per-card outcome flow

1. Pre-flight CL flag scan (warn-only, unchanged).
2. Navigate, override artifacts.
3. Pause for human submit (`[Enter] / [s] / [q]`, unchanged).
4. **On Enter:** poll `pipeline.ats_signals.greenhouse_confirmed(page)` for ~10s.
   - **Confirmed:** ledger.upsert(status=applied, ...); tracker.append(Applied); flip markdown `[x] apply` → `[x] applied`.
   - **Not confirmed:** ledger.upsert(status=unverified, ...); tracker.append(Unverified); markdown stays `[x] apply` (so 24h auto-retry path works); add to end-of-session unverified list.
5. **On exception (page load, override, etc):** ledger.upsert(status=failed, ...); tracker.append(Failed); markdown rewrites to `[x] apply error: <msg>`.
6. **On 's':** ledger.upsert(status=skipped, ...); tracker no-op; markdown rewrites to `[ ] apply skipped`.

`ledger.upsert` always increments `attempt_count` and updates `last_attempt_at`.

### Confirmation signals (Greenhouse only, Plan 2)

`pipeline/ats_signals.py` exposes a typed dispatch table:

```python
def detect_confirmation(page, url: str, timeout_seconds: int = 10) -> bool:
    host = urlparse(url).netloc
    if "greenhouse.io" in host:
        return greenhouse_confirmed(page, timeout_seconds)
    # Lever, Ashby, etc. → Plan 3
    return False  # unknown ATS → conservative miss
```

`greenhouse_confirmed`:
- URL match: `/confirmation`, `/applications/[0-9]+/thanks`, OR query `?application_submitted=true` (research-confirmed Greenhouse patterns)
- DOM match: `h1:has-text("Thank you")`, `[data-application-confirmation]`, OR text "We've received your application" within iframe-aware locator
- Poll every 500ms up to `timeout_seconds`. First match wins. No match → return False.

False positives (rare): generic Thank-you page mid-flow → tracker rows logged as `applied`. Mitigation: signals are conservative (combination of URL + DOM, not either).

False negatives (more likely): Greenhouse changes thank-you copy → tracker rows logged as `unverified`. Mitigation: 24h auto-retry; if it's a real false-negative, retry will hit the same condition and stay unverified — at which point user manually verifies and edits the ledger or marks it Applied via /apply.

### End-of-session reporting

```
Session done: 5 attempts → 3 applied · 1 unverified · 1 failed

Unverified (manual reconciliation may be needed):
  - [B] Orkes — Product Manager
    URL: https://...
    Status: ledger unverified, 24h auto-retry eligible at 2026-05-03 14:32
    To force-resolve: edit ledger.tsv or run `/apply --status applied "Orkes - PM"`

Failed (user re-tick to retry):
  - [B] BrokenCo — PM (selector miss)

Tier A applied today — run /pitch for:
  - AcmeCo
```

## Architecture

```
/pipeline review --batch
  └─ writes Daily Triage YYYY-MM-DD.md from manifest + scored JSON
       (markdown writer; no Playwright; safe to run any time)

/pipeline execute [<note-path>]
  └─ reads Daily Triage YYYY-MM-DD.md → markdown intent ([x] apply cards)
  └─ filters by ledger_eligible(card) → ledger-authoritative queue
  └─ for each queued card:
       1. Pre-flight: CL flag-pattern scan (warn-only)
       2. Launch persistent Chrome (POC pattern)
       3. Override resume + CL via set_input_files
       4. Wait for human submit
       5. ats_signals.detect_confirmation() poll (~10s)
       6. ledger.upsert(applied | unverified | failed | skipped)
       7. tracker.append_row(status from #6)
       8. markdown flip ONLY on confirmed-applied
  └─ end-of-session: confirmed/unverified/failed counts + Tier A pitch
```

### New modules

- `pipeline/triage_writer.py` — manifest + scored JSON → daily triage markdown
- `pipeline/execute.py` — markdown reader + Playwright driver + state writer
- `pipeline/tracker.py` — shared helper for Application Tracker append + dedup ledger upsert
- `pipeline/tracker_cli.py` — thin `python -m` wrapper around `tracker.append_row()` so the `/apply` skill can call it as a subprocess without importing
- `pipeline/ats_signals.py` — typed dispatch table for post-submit confirmation detection. Plan 2 ships `greenhouse_confirmed()`; Plan 3 adds Lever/Ashby
- `pipeline/migrate_ledger.py` — one-shot idempotent migration adding `last_attempt_at` + `attempt_count` columns to existing ledger.tsv

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

**Queue construction (ledger-authoritative):**

`build_queue(triage_text, ledger_path)` returns the cards in markdown `[x] apply` AND `ledger_eligible(card)` (see "State Authority + Uncertainty Model" above). Cards in markdown but blocked by ledger (already applied, unverified <24h, etc.) are surfaced in the dry-run report but not queued.

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
   - Call `ats_signals.detect_confirmation(page, url, timeout_seconds=10)` — polls for ATS-specific confirmation signal.
   - **Confirmed:**
     - `tracker.append_row(status=Applied)` — append-only attempt log entry
     - `tracker.upsert_ledger_row(status=applied)` — increments attempt_count, sets last_attempt_at
     - Rewrite markdown `[x] apply` → `[x] applied` (best-effort cosmetic; ledger is truth)
     - Add to confirmed list for end-of-session summary
   - **Not confirmed (timeout, unknown ATS, signal mismatch):**
     - `tracker.append_row(status=Unverified)`
     - `tracker.upsert_ledger_row(status=unverified)`
     - Markdown stays `[x] apply` (24h auto-retry path requires this)
     - Add to unverified list for end-of-session summary

8. **On 's':**
   - `tracker.upsert_ledger_row(status=skipped)` — records the skip without a tracker row
   - Rewrite markdown `[x] apply` → `[ ] apply skipped`

9. **On 'q':** stop loop. Remaining `[x] apply` cards stay queued for next run.

**On per-card exception (page load fail, override fail, etc):**
- `tracker.append_row(status=Failed)`
- `tracker.upsert_ledger_row(status=failed)`
- Rewrite markdown `[x] apply` → `[x] apply error: <msg>`
- Continue queue.

**End-of-session output:** see "State Authority + Uncertainty Model" → "End-of-session reporting" section above for full format. Counts breakdown by confirmed/unverified/failed; unverified list shows auto-retry eligibility timestamp; Tier A pitch prompt covers grade-A confirmed submits only (not unverified).

### `pipeline/tracker.py`

Public API:
- `append_row(tracker_path, *, company, role, source, date, status, notes) -> AppendResult` — append-only. Status is enum (Applied | Unverified | Failed). Each call adds one row.
- `upsert_ledger_row(ledger_path, *, url, company, role, location, date, score, grade, status) -> LedgerOp` — finds existing row by (company, normalized_role); updates status, increments attempt_count, sets last_attempt_at. Creates new row if absent.
- `ledger_eligible(ledger_path, company, role, *, now=None) -> bool` — encodes the authority rules from "State Authority + Uncertainty Model".
- `normalize_title(title) -> str` — pure helper.

`/apply` skill is rewritten to invoke this via `python -m pipeline.tracker_cli --status applied` (default). The shared logic lives in `tracker.py`; the CLI lives in `tracker_cli.py` so test imports stay clean.

### `pipeline/ats_signals.py`

Public API:
- `detect_confirmation(page, url: str, timeout_seconds: int = 10) -> bool` — typed dispatch on URL host.
- `greenhouse_confirmed(page, timeout_seconds: int) -> bool` — polls every 500ms for URL match (`/confirmation`, `/applications/[0-9]+/thanks`) OR DOM match (`h1:has-text("Thank you")`, `[data-application-confirmation]`, "We've received your application" text).
- Plan 3 will add `lever_confirmed` and `ashby_confirmed` to the same dispatch table.

### `pipeline/migrate_ledger.py`

One-shot, idempotent script. Adds `last_attempt_at` and `attempt_count` columns to existing `ledger.tsv`. Backfills existing rows: `last_attempt_at = date_first_seen`, `attempt_count = 1`. No-op if columns are already present. Run once after upgrading; not part of normal /pipeline flow.

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
1. **First:** `ats_signals.detect_confirmation()` poll determines status
2. **Then:** `tracker.append_row(status=...)` (append-only attempt log)
3. **Then:** `tracker.upsert_ledger_row(status=...)` (current-state, increments attempt_count)
4. **Last:** rewrite markdown `[x] apply` → `[x] applied` (only on confirmed; cosmetic)

If we crash between (3) and (4): ledger says applied, markdown still says `[x] apply`. Next run: `ledger_eligible(card)` returns False (status=applied blocks), card is skipped. No double-apply.

If we crash between (2) and (3): tracker has an Applied row, ledger doesn't have the upsert. Next run: card has `[x] apply`, no ledger row → eligible → re-attempts. Tracker gets a second Applied row. Cost: one extra application attempt; the dedup-via-ledger usually catches before submit, but here the ledger is missing so it doesn't. **Mitigation:** tracker.append_row + upsert_ledger_row are wrapped in a single function `record_attempt(card, status)` that calls them in a try/except — partial failure rolls back the tracker row. (See "Atomicity" below.)

### Atomicity

`record_attempt(card, status)` is the single entry point execute uses to commit a state change:

```python
def record_attempt(card, status, *, tracker_path, ledger_path, date):
    # Tracker write
    tracker.append_row(tracker_path, ..., status=status, date=date)
    try:
        tracker.upsert_ledger_row(ledger_path, ..., status=status, date=date)
    except Exception:
        # Roll back the tracker row to keep states consistent
        tracker.remove_last_row(tracker_path, expected_company=card.company)
        raise
```

This isn't true ACID, but it bounds the failure mode: either both succeed or both fail. The "remove_last_row" helper deletes the most recent row matching `(expected_company, today)` — defensive against a race where another process appended in between (won't be the case for solo CLI use, but cheap to guard).

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

**`test_tracker.py`** (10-12 tests)
- Append produces row matching existing tracker convention exactly
- Append accepts status enum: Applied | Unverified | Failed
- `upsert_ledger_row` creates new row when (company, normalized_role) absent
- `upsert_ledger_row` updates existing row's status, increments attempt_count, sets last_attempt_at
- `ledger_eligible` returns True for missing row
- `ledger_eligible` returns False for status=applied
- `ledger_eligible` returns False for status=unverified within 24h
- `ledger_eligible` returns True for status=unverified after 24h
- `ledger_eligible` returns True for status=failed (user re-tick path)
- `record_attempt` rolls back tracker row if ledger write fails
- Tracker file missing → creates it with header

**`test_ats_signals.py`** (5-6 tests)
- `greenhouse_confirmed` matches `/confirmation` URL
- `greenhouse_confirmed` matches `/applications/N/thanks` URL
- `greenhouse_confirmed` matches "Thank you" h1 DOM
- `greenhouse_confirmed` returns False after timeout with no signal
- `detect_confirmation` dispatches greenhouse hosts to greenhouse_confirmed
- `detect_confirmation` returns False for unknown ATS host

**`test_migrate_ledger.py`** (3-4 tests)
- Adds last_attempt_at and attempt_count columns to header
- Backfills last_attempt_at = date_first_seen for existing rows
- Backfills attempt_count = 1 for existing rows
- Idempotent: running twice is a no-op

### Integration test (1, gated by `@pytest.mark.slow`)

**`test_execute_e2e.py`**
- Boots fake Greenhouse-shape HTML on `localhost:0` via `http.server`
- Runs execute against a triage note pointing at the fake URL
- Asserts: `set_input_files` received the right paths, checkbox flips, tracker row written
- No real ATS, no real Simplify

### Total target

42 (Plan 1) → ~85 tests. All network-free except the gated e2e.

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
5. **Confirmation false positives** (added 2026-05-02 post-pressure-test). A generic Thank-you page mid-flow could trigger `greenhouse_confirmed`, marking unsubmitted attempts as Applied. Mitigation: signals require URL OR a specific DOM combination (not bare "thank you" text); empirical validation against 5+ real Greenhouse confirmation pages before Plan 2 ships.
6. **Confirmation false negatives** (added 2026-05-02). Greenhouse changes thank-you copy → real submits log as Unverified. Mitigation: 24h auto-retry, plus end-of-session reconciliation list with manual `/apply --status applied` escape hatch.
7. **Schema migration on shared ledger** (added 2026-05-02). `migrate_ledger.py` runs against `~/code/the-dossier/pipeline/data/ledger.tsv` which is shared with the main worktree. Run migration on the main worktree's ledger BEFORE the Plan 2 branch merges, so post-merge the new code can read the new schema. Document explicitly in operator README.

## Estimate

| Component | Hours |
|---|---|
| Schema migration (`migrate_ledger.py` + tests) | 1.0 |
| `tracker.py` extraction + status enum + upsert + atomicity + tests | 2.5 |
| `tracker_cli.py` + skill rewrite | 0.7 |
| CL `.md` persistence + flag scan + tests | 1.0 |
| `triage_writer.py` + tests | 2.5 |
| `execute.py` parser/state + tests | 1.5 |
| `ats_signals.py` + tests | 1.5 |
| `execute.py` Playwright loop (with verification + status-aware writes + atomicity) | 2.5 |
| `/pipeline` skill markdown + e2e + README | 1.5 |
| **Total** | **~14-15 hrs** |

(Original estimate was 9 hrs; pre-pressure-test plan extrapolated to 11 hrs. The +5-6 reflects: schema migration as its own task, status enum threading through tracker + tracker_cli + skill, atomicity wrapper, ats_signals module + tests, and the additional execute.py logic for verification poll + uncertainty-aware writes. The dialogue suggested 28 hrs which over-corrected; 14-15 is the honest number for the actual scope expansion.)

## Predecessors and Dependents

- **Plan 1 (merged):** provides the manifest contract this plan reads.
- **Plan 3 (post-Plan 2):** multi-ATS adapters, LLM essay pass, programmatic Simplify trigger. Will reuse the Plan 2 execute loop and add ATS-specific override functions.

---

*Design approved 2026-05-02 via brainstorming. Next: spec review loop, then writing-plans skill.*
