# Apply-Flow v2 — Batch Triage + Execute

Plan 2 of the apply-flow build. Adds two commands on top of Plan 1's pre-generation:
- `/pipeline review --batch` writes a daily triage markdown into the vault.
- `/pipeline execute` reads ticked cards and drives Playwright through them, with post-submit confirmation polling and ledger-first authority.

## Daily flow

1. **Overnight (or any time):** `/pipeline pregenerate` (Plan 1) — generates resume + CL PDFs and writes the manifest. CL `.md` sidecars now persist alongside PDFs (Plan 2 change).
2. **Morning:** `/pipeline review --batch` — writes `~/Documents/Second Brain/99_System/Job Search/Daily Triage YYYY-MM-DD.md`.
3. **Phone (anywhere, any time):** open the triage note in Obsidian. Tick `[x] apply` on cards to apply to.
4. **At desk:** `/pipeline execute` — runs through the queue, pauses per card for human submit.

End-of-session output: counts breakdown (applied/unverified/failed) + unverified reconciliation list + Tier A pitch list (Confirmed-Applied A grades only).

## One-time setup

```bash
# Build the venv
cd ~/code/the-dossier-apply-flow-v2/pipeline && python3.14 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/playwright install chromium

# Migrate the ledger schema (adds last_attempt_at + attempt_count columns)
.venv/bin/python3 -m pipeline.migrate_ledger

# Bootstrap the persistent Chrome profile + side-loaded Simplify + login
.venv/bin/python3 ~/code/the-dossier-apply-flow-v2/pipeline/apply_flow_poc.py bootstrap
```

The bootstrap step opens Chrome with the side-loaded Simplify extension. Log in to your Simplify account; cookies persist. You only do this once per machine.

The migration is idempotent and forward-compatible — old code (current main) reads via `csv.DictReader` and ignores unknown columns.

## Triage (`/pipeline review --batch`)

```bash
cd ~/code/the-dossier-apply-flow-v2 && pipeline/.venv/bin/python3 -m pipeline.triage_writer
```

Defaults:
- Most recent manifest in `pipeline/data/pregenerated/`.
- Output path keyed by manifest date in vault.
- Refuses to overwrite a triage note that has any `[x] apply`/`[x] applied` marks unless `--force`.

Output shape (Option A — section per card):

```markdown
## [A] AcmeCo — Senior PM
- Salary: $200,000 | Archetype: product_management | Lane: A
- Fit: Direct PM fit; strong AI tailwind.
- Risks: (none flagged)
- JD: https://job-boards.greenhouse.io/acmeco/jobs/123
- Resume: /abs/.../resume.pdf
- CL: /abs/.../cl.pdf
- CL preview: "Hello AcmeCo Hiring Team..."
- [ ] apply
- [ ] skip
```

Cards with unresolved (Adzuna redirector) URLs render with strikethrough checkboxes and a warning — they're not in the apply queue. Run `/pipeline resolve-urls` to convert them.

## Execute (`/pipeline execute`)

```bash
cd ~/code/the-dossier-apply-flow-v2 && pipeline/.venv/bin/python3 -m pipeline.execute
```

Defaults: today's triage note in vault. Pass a positional path to override.

Useful flags:
- `--dry-run` — parse + show queue (filtered by ledger eligibility), no Playwright
- `--simplify-wait N` — Simplify autofill wait floor in seconds
- `--tracker-path PATH` / `--ledger-path PATH` — override default vault paths

Per-card behavior:
1. CL pre-flight scan — warns if `[X`, `[INSERT`, `"fill in"`, or `"before sending"` appear in the CL prose. User decides proceed/skip/quit.
2. Navigate to URL. Wait for Simplify (floor + poll up to 2×).
3. Override resume + CL via `set_input_files`.
4. Pause with form on screen. `[Enter]` = submitted, `[s]` = skip, `[q]` = quit.
5. **On submit:** poll for ATS confirmation signal (~10s — Greenhouse only in Plan 2). Confirmed → log `Applied` + flip `[x] apply` to `[x] applied`. Miss → log `Unverified` + leave `[x] apply` (24h auto-retry).
6. **On skip:** log `Skipped` + flip to `[ ] apply skipped`.
7. **On exception (page load fail, override fail):** log `Failed` + flip to `[x] apply error: <msg>`.

## State authority + retry semantics

The ledger (`pipeline/data/ledger.tsv`) is the source of truth for retry decisions. Markdown checkbox state is intent; ledger drives `build_queue`.

| Ledger status | Eligible for retry? |
|---|---|
| `applied` | Never (always blocks) |
| `unverified` (within 24h) | No (cooling down) |
| `unverified` (>24h old) | Yes (auto-retry) |
| `failed` | Yes (user re-tick path) |
| `skipped` | Yes |

Resume mid-flight: re-running execute on the same note skips already-applied cards via `ledger_eligible`. If a session crashed mid-card, the ledger's `record_attempt` atomicity wrapper ensures tracker + ledger states match (rollback on partial failure).

## Configuration

`pipeline/config.yaml` may include:

```yaml
apply_flow:
  simplify_wait_seconds: 3
```

Resolution order for `simplify_wait_seconds`: `--simplify-wait` flag > `PIPELINE_EXECUTE_SIMPLIFY_WAIT` env > config > default 3.

## Tests

```bash
cd ~/code/the-dossier-apply-flow-v2 && pipeline/.venv/bin/python3 -m pytest pipeline/ -q -m "not slow"
```

131+ network-free unit tests. The slow gated tests (browser-real PDF render + e2e Playwright happy path) run with `-m slow`.

## Out of scope (Plan 3)

- Multi-ATS adapters (Lever, Ashby) — currently Greenhouse only via `pipeline/ats_signals.py` typed dispatch.
- LLM essay pass for textareas.
- Programmatic Simplify autofill triggering (currently waits for Simplify; doesn't click "Autofill this page").
- Fully unattended submit.
