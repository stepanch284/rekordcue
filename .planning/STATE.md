# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-08)

**Core value:** A DnB DJ can select tracks from their Rekordbox library and get correctly placed structural cue points without manually scrubbing through each track.
**Current focus:** Phase 1 — CLI Proof-of-Concept

## Current Position

Phase: 1 of 9 (CLI Proof-of-Concept)
Plan: 0 of TBD in current phase
Status: Ready to plan
Last activity: 2026-04-08 — Roadmap created, STATE.md initialized

Progress: [░░░░░░░░░░] 0%

## Performance Metrics

**Velocity:**
- Total plans completed: 0
- Average duration: —
- Total execution time: 0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| - | - | - | - |

**Recent Trend:**
- Last 5 plans: —
- Trend: —

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- Init: Use pyrekordbox for reads (DB + ANLZ), raw sqlite3 for all writes — safer transaction control
- Init: CLI PoC must be proven before GUI is built (research mandate)
- Init: No [RC] comment prefix on cues — written exactly as Rekordbox places them manually (no Comment text)
- Init: Hot cue A = bar 0, B = bar 16, C = 8 bars before Drop 1 (omitted if Drop 1 <= bar 8)
- Init: Memory cues at Drop 1, Breakdown, Drop 2, Outro — no label text

### Pending Todos

None yet.

### Blockers/Concerns

- CRITICAL before Phase 1: Run `PRAGMA table_info(DjmdCue)` and `PRAGMA user_version` against the live master.db to verify schema assumptions — column names documented in ARCHITECTURE.md are MEDIUM confidence only
- Phase 1: Verify pyrekordbox can open the encrypted master.db for the installed Rekordbox version before writing any code
- Phase 3: Half-tempo BPM detection is a known Rekordbox issue with DnB (PITFALLS.md Pitfall 7) — BPM range check is mandatory before bar math

## Session Continuity

Last session: 2026-04-08
Stopped at: Roadmap and STATE.md created. No plans written yet.
Resume file: None
