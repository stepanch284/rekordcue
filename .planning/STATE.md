# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-08)

**Core value:** A DnB DJ can select tracks from their Rekordbox library and get correctly placed structural cue points without manually scrubbing through each track.
**Current focus:** Phase 4 — Full Section Detection (complete)

## Current Position

Phase: 4 of 9 (Full Section Detection)
Status: Complete (all 3 plans done)
Last activity: 2026-04-09 — Phase 4 complete: section detection engine (PSSI + Simple Threshold), integrated into main.py, RMS research completed

Progress: [████░░░░░░] ~40%

## Performance Metrics

**Velocity:**
- Total plans completed: 8 (04-01, 04-02, 04-03, Phase 3, Phase 2, Phase 1)
- Average duration: ~45 minutes
- Total execution time: ~6 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan | Status |
|-------|-------|-------|----------|--------|
| 1 | 2 | ~45 min | ~22 min | Complete |
| 2 | 1 | ~30 min | ~30 min | Complete |
| 3 | 3 | ~90 min | ~30 min | Complete |
| 4 | 3 | ~135 min | ~45 min | Complete |

**Recent Trend:**
- Last 3 plans (Phase 4): 04-01 (~45 min), 04-02 (~30 min), 04-03 (~30 min)
- Trend: Accelerating with better TDD practices + research insights

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

Last session: 2026-04-09
Stopped at: Phase 4 complete (all 3 plans: 04-01 section detection engine, 04-02 main.py integration, 04-03 RMS research)
Resume at: Phase 5 — Hot Cue Position Generator
Resume file: None

**Phase 4 Completion Notes:**
- Created detect.py with PSSI reader + Simple Threshold + RMS Hybrid algorithms
- 37 unit tests passing (21 Simple + 16 RMS)
- Integrated detect_sections_hybrid() into main.py CLI with confidence display
- Recommendation: Ship Simple Threshold for v1, defer RMS to v1.1+ if needed
- All sections snapped to 8-bar boundaries
- Confidence scores 0-100% calibrated per section type
