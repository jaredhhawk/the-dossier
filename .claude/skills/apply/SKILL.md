name: apply
description: Log a job application to the Application Tracker and dedup ledger, with a clipboard package for form filling.
version: 1.0.0
---

# /apply

Log a job application and generate a clipboard-ready package for form filling.

## Usage

`/apply Company - Role Title`
`/apply Company - Role Title --source indeed`
`/apply` (interactive -- prompts for details)

### Flags

| Flag | Default | Description |
|------|---------|-------------|
| `--source` | `Pipeline` | Where the listing was found (Adzuna, LinkedIn, Indeed, Referral, etc.) |
| `--url` | -- | Application URL (opens in browser if provided) |
| `--archetype` | auto-detect | Resume archetype override (pm, ops, gov, cs, ai) |
| `--no-clipboard` | false | Skip clipboard package, just log |
| `--no-ledger` | false | Skip ledger update (for manual retroactive logging) |

## Dependencies

- Application Tracker: `~/Documents/Second Brain/02_Projects/Job Search/R - Application Tracker.md`
- Dedup ledger: `~/code/the-dossier/pipeline/data/ledger.tsv`
- Config: `~/code/the-dossier/pipeline/config.yaml`

## Steps

### Step 1: Parse Input

If invoked with arguments, parse company name and role title from the input.
If invoked bare (`/apply`), prompt for:
1. Company name
2. Role title
3. Source (default: Pipeline)
4. Application URL (optional)

### Step 2: Check Dedup Ledger

Read `~/code/the-dossier/pipeline/data/ledger.tsv`.

Check if company + normalized role title already exists with status `applied`.
- If found: warn "Already applied to [Role] at [Company] on [date]. Log duplicate? (y/n)"
- If not found: continue

### Step 3: Detect Archetype

If `--archetype` flag provided, use it.

Otherwise, read `~/code/the-dossier/pipeline/config.yaml` archetype routing keywords.
Match against the role title. First keyword match wins.
If no match, default to `operations`.

Report: "Archetype: [name]"

### Step 4: Generate Clipboard Package

Unless `--no-clipboard` is set:

Read `form_answers` from `~/code/the-dossier/pipeline/config.yaml`.

Display the clipboard package:

```
━━━ Clipboard Package ━━━━━━━━━━━━━━━━━━━━━━━
Company:    [company]
Role:       [role title]
Archetype:  [archetype name]
Resume:     ~/code/the-dossier/pipeline/data/resumes/output/[Company]-[Role]-[date].pdf
            (if file exists, otherwise: generate it now -- see Step 4b)

Salary expectation: [from config]
Visa/auth:          [from config]
LinkedIn:           [from config]
Location:           [from config]
Portfolio:          [from config, if set]

Why this company: [Generate 1-2 sentences based on what you know about the company.
                   If invoked from /pipeline, use the scorer rationale.
                   If invoked standalone, do a quick web search for the company.]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Step 4b: Generate Tailored Resume (if not exists)

If the resume PDF does not exist at the expected path:

```bash
cd ~/code/the-dossier && pipeline/.venv/bin/python3 pipeline/resume.py \
  --archetype [archetype] --company "[Company]" --role "[Role Title]"
```

If a JD text file is available (e.g., from /pipeline scored data), add `--jd path/to/jd.txt` for keyword-aware tailoring.

Report the generated path in the clipboard package.

### Step 5: Open Application URL

If `--url` was provided or is available from pipeline card data:
- Open the URL in the user's browser: `open [url]`
- Say: "Application page opened. Fill the form, then confirm when submitted."

If no URL: say "No application URL provided. Find the listing and apply, then confirm when submitted."

Wait for user to confirm they've submitted the application.

### Step 6: Log to Application Tracker

Read `~/Documents/Second Brain/02_Projects/Job Search/R - Application Tracker.md`.

Find the markdown table under the active applications section.

Append a new row:

```
| [Company] | [Role Title] | [Source] | [YYYY-MM-DD] | Applied | | | Pipeline logged |
```

Rules:
- Company and Role should match exactly what the user provided (preserve casing)
- Date is today's date
- Status is always "Applied" for new entries
- Notes field: "Pipeline logged" if from /pipeline, otherwise blank
- Do NOT add wikilinks to the company name in the table (breaks table alignment)

Use the Edit tool to append the row. Find the last `|` row in the active applications table and add the new row after it.

Confirm: "Application Tracker updated."

### Step 7: Update Dedup Ledger

Unless `--no-ledger` is set:

Read `~/code/the-dossier/pipeline/data/ledger.tsv`.

Append a new row:

```
[url]\t[company]\t[normalized_title]\t[location]\t[YYYY-MM-DD]\t[score]\t[grade]\tapplied
```

Where:
- url: the application URL if provided, otherwise empty
- normalized_title: lowercase, stripped of Sr./Senior, req IDs, trailing location
- score/grade: empty if standalone, filled if from /pipeline
- status: `applied`

If the company already exists in the ledger with a different status (e.g., `seen`, `pitched`), update the existing row's status to `applied` instead of adding a duplicate.

Use the Edit tool or Bash (`echo >> ledger.tsv`) to append.

Confirm: "Ledger updated."

### Step 8: Summary

Print:

```
Logged: [Role Title] at [Company]
Tracker: updated
Ledger:  updated
Source:  [source]
```

## Error Handling

- If Application Tracker file not found: warn and skip tracker update, still update ledger
- If ledger.tsv not found: warn "Run pipeline/bootstrap.py first to create the ledger"
- If config.yaml not found: skip clipboard package, warn user

## Integration with /pipeline

When invoked from /pipeline during card queue triage:
- Company, role, source, URL, archetype, score, and grade are passed automatically
- No prompting needed -- all data comes from the card
- Clipboard package still displays
- "Why this company" uses the scorer's rationale instead of a web search

## Report Format

When done, report:
- **Status:** DONE | BLOCKED | NEEDS_CONTEXT
- Files created
- Symlink verified
