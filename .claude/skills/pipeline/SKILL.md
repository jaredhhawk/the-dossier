---
name: pipeline
description: Automated job search pipeline. Discover, score, triage, apply, and outreach in one daily flow.
version: 0.1.0
---

# /pipeline

> **Status: Phase 1 (stub).** Full orchestration coming in Phase 4.
> Currently only /apply is functional. Run `/apply` directly for now.

## Planned Usage

`/pipeline` -- full daily run (discover → score → triage → apply → outreach)
`/pipeline discover` -- discovery + dedup only
`/pipeline review` -- score + triage from most recent discovery
`/pipeline --grade A` -- filter to A-grade only

## Available Now

- `/apply Company - Role Title` -- log an application with clipboard package

## Coming Soon

- Phase 2: Resume system (structured source, archetype generation, per-JD tailoring)
- Phase 3: Discovery engine (Adzuna API, email alerts, career page monitoring)
- Phase 4: Scoring + card queue (this skill becomes fully functional)
- Phase 5: Outreach agent (background /pitch dispatch)
