# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-08)

**Core value:** A DnB DJ can select tracks from their Rekordbox library and get correctly placed structural cue points without manually scrubbing through each track.
**Current focus:** Phase 2 — Waveform Parser Hardening (complete)

## Current Position

Phase: 2 of 9 (Waveform Parser Hardening)
Status: Complete
Last activity: 2026-04-09 — Phase 2 complete: parse error wrapping in waveform.py, graceful skip in main.py

Progress: [██░░░░░░░░] ~10%

## Performance Metrics

**Velocity:**
- Total plans completed: 2
- Average duration: ~22 minutes
- Total execution time: ~0.75 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1 | 2 | ~45 min | ~22 min |

**Recent Trend:**
- Last 5 plans: 01-01 (~20 min), 01-02 (~25 min)
- Trend: Stable

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
- 01-01: db.get_content(ID=) returns ORM object directly (not a Query) — .first() must NOT be called
- 01-01: Onset threshold computed on non-silent bars only to avoid intro silence skewing stats
- 01-02: Hot cue A is written at bar 0 (bar_times_s[0]), not at the detected onset — onset is informational only
- 01-02: Color=255 / ColorTableIndex=22 confirmed from live Rekordbox row inspection (not palette index)
- 01-02: StatsFull mixin auto-sets created_at/updated_at — omit from DjmdCue constructor

### Pending Todos

None.

### Blockers/Concerns

- Phase 3: Half-tempo BPM detection is a known Rekordbox issue with DnB (PITFALLS.md Pitfall 7) — BPM range check is mandatory before bar math

### Resolved (from prior state)

- RESOLVED 01-01: PRAGMA table_info(DjmdCue) confirmed — 29 columns, all 11 required present, Number column absent, user_version=0
- RESOLVED 01-01: pyrekordbox can open encrypted master.db for Rekordbox 7.2.3 — verified against live DB

## Session Continuity

Last session: 2026-04-08
Stopped at: Plan 01-02 complete. writer.py and main.py created and committed. Hot cue A write verified in Rekordbox 7.2.3.
Resume at: Next plan in Phase 1 (TBD)
Resume file: None
