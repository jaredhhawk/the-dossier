# Apply-Flow v1 — CL Generator + Pre-Generation

Plan 1 of the apply-flow v1 build. Adds the missing cover-letter PDF artifact and an idempotent batch script that pre-generates resume + CL + cached JD for every Grade A/B card on a scored JSON.

## What this gives you

- Standalone CL generator (`pipeline/cover_letter.py`) — one-off CL PDFs via Claude (Max sub by default) or a hand-written prose file.
- Batch pre-generator (`pipeline/pregenerate.py`) — overnight-runnable script that turns a scored JSON into a manifest + a directory full of artifacts ready for Plan 2's `/pipeline execute` to consume.

## Prereqs

- **Claude Code CLI** on PATH and authenticated (run `claude` interactively at least once to sign in to your Max sub). This is the default backend.
- The shared venv at `~/code/the-dossier/pipeline/.venv` with deps installed (handled by `pip install -r pipeline/requirements.txt`).
- A scored JSON at `pipeline/data/scored/YYYY-MM-DD.json` (produced upstream by the existing `/pipeline` flow). For development, you can pass an absolute path to a scored JSON in any worktree via `--scored-file`.
- *(Only if using the `anthropic_sdk` fallback backend)* `ANTHROPIC_API_KEY` env var set.

## Invocation pattern

Always run from the POC worktree using `python3 -m`:
```bash
cd ~/code/the-dossier-poc && ~/code/the-dossier/pipeline/.venv/bin/python3 -m pipeline.<module> <args>
```
This ensures `from pipeline.X import Y` resolves to the POC's package and not the main worktree's.

Generated artifacts (PDFs, manifest, JD cache) land in **the POC tree** under `pipeline/data/...` (all gitignored).

## Backends

Cover-letter generation supports two backends. Pick via the `PIPELINE_CL_BACKEND` env var.

| Backend | Default? | Auth | Speed | Cost |
|---|---|---|---|---|
| `claude_cli` | yes | Claude Max sub (no key needed) | ~110s/card | $0 (Max sub) |
| `anthropic_sdk` | opt-in | `ANTHROPIC_API_KEY` env var | ~1-2s/card | ~$0.05/card (~$2/batch) |

```bash
# Default (Max sub):
~/code/the-dossier/pipeline/.venv/bin/python3 -m pipeline.pregenerate

# Anthropic SDK fallback:
PIPELINE_CL_BACKEND=anthropic_sdk ~/code/the-dossier/pipeline/.venv/bin/python3 -m pipeline.pregenerate
```

The Anthropic SDK path is the escape hatch: use it when Max is rate-limited, when you need API logging/observability, or when running in a headless environment without `claude` CLI installed.

`PIPELINE_CL_MODEL` env var selects the model for both backends (default: `claude-sonnet-4-6`). Useful if a model alias becomes invalid.

## One-off cover letter

```bash
cd ~/code/the-dossier-poc && ~/code/the-dossier/pipeline/.venv/bin/python3 -m pipeline.cover_letter \
  --archetype product_management --company "Acme" --role "Senior PM" \
  --jd path/to/jd.txt
```
Output: `pipeline/data/cover_letters/output/Jared-Hawkins-Acme-Senior-PM-{date}.pdf` (POC tree).

Skip the LLM and supply your own prose:
```bash
cd ~/code/the-dossier-poc && ~/code/the-dossier/pipeline/.venv/bin/python3 -m pipeline.cover_letter \
  --archetype product_management --company "Acme" --role "Senior PM" \
  --text-file path/to/my_prose.txt
```

`--markdown-only` writes the prose to `.md` instead of rendering to PDF (useful for inspection).

`--force` regenerates even if the PDF already exists (default behavior is to skip).

## Pre-gen batch

```bash
cd ~/code/the-dossier-poc && ~/code/the-dossier/pipeline/.venv/bin/python3 -m pipeline.pregenerate
```
Defaults: most recent scored JSON in **the POC tree's** `pipeline/data/scored/`, grades A+B, idempotent (skip cards whose artifacts exist). To run against the main worktree's scored data, pass an absolute `--scored-file`:
```bash
cd ~/code/the-dossier-poc && ~/code/the-dossier/pipeline/.venv/bin/python3 -m pipeline.pregenerate \
  --scored-file /Users/jhh/code/the-dossier/pipeline/data/scored/2026-04-22.json
```

Useful flags:
- `--scored-file <path>` — pin a specific scored JSON
- `--grades A` — only Grade A (default: `A,B`)
- `--limit 3` — cap card count, useful for smoke tests
- `--dry-run` — list what would be processed, exit 0 (no LLM calls)
- `--force` — regenerate even if cached

Output:
- Resume PDFs at `pipeline/data/resumes/output/`
- CL PDFs at `pipeline/data/cover_letters/output/`
- JD text cached at `pipeline/data/jd_cache/`
- **Manifest** at `pipeline/data/pregenerated/{date}-manifest.json` — this is what Plan 2's `/pipeline execute` reads
- Scored JSON updated in place: each processed card gets an `artifacts` field with the three paths

Expected wall time per card with the default `claude_cli` backend: ~110s. For a 38-card batch that's ~70 minutes — fine for an overnight cron, slow for interactive iteration. Switch to `anthropic_sdk` if you need faster turnaround (~1 min for the same batch).

## Cron installation (optional)

This script is built to run unattended. To install as a daily 4am cron:
```
0 4 * * * cd /Users/jhh/code/the-dossier-poc && /Users/jhh/code/the-dossier/pipeline/.venv/bin/python3 -m pipeline.pregenerate >> /tmp/pregenerate.log 2>&1
```

Cron environment requirements:
- **Default backend (`claude_cli`):** the `claude` binary must be on the cron shell's PATH, and you must have run `claude` interactively at least once to authenticate. Cron runs in a stripped environment by default — wrap the cron line in a script that sources `~/.zshrc` or explicitly sets PATH if needed. macOS may also require granting Full Disk Access to `cron` for keychain access.
- **SDK backend (`anthropic_sdk`):** export `ANTHROPIC_API_KEY` and `PIPELINE_CL_BACKEND=anthropic_sdk` in the cron environment.

The `cd` is essential in either case — `python3 -m` resolves the package relative to CWD.

## Tests

```bash
cd ~/code/the-dossier-poc && ~/code/the-dossier/pipeline/.venv/bin/python3 -m pytest pipeline/tests/ -v
```
Slow tests (real Playwright PDF render) can be skipped:
```bash
... -m 'not slow'
```

All tests are network-free. The CLI adapter is exercised via mocked `subprocess.run`; the SDK adapter is exercised via a duck-typed FakeClient.

## Out of scope (Plans 2 + 3)

- Batch triage UI / `/pipeline review --batch` writer / `/pipeline execute` reader
- Multi-ATS adapters beyond Greenhouse (Lever, Ashby)
- LLM essay pass for textareas
- Programmatic Simplify autofill trigger
