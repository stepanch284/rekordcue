# Roadmap: RekordCue

## Overview

RekordCue is built in three distinct layers that must be proven in order: first a CLI proof-of-concept validates the entire pipeline on real data (read DB, parse waveform, detect structure, write cue, confirm in Rekordbox); then the full detection and cue logic is hardened across all structural sections; finally a PyQt6 desktop UI wraps the proven engine. The GUI is never built before the detection algorithm is validated.

## Phases

- [x] **Phase 1: CLI Proof-of-Concept** - One track, one hot cue, full safety pipeline, confirmed in Rekordbox
- [x] **Phase 2: Waveform Parser Hardening** - PSSI phrase shortcut, graceful handling of missing/incomplete ANLZ files
- [ ] **Phase 3: Beat Grid & Bar Math** - Timing foundation — beat grid anchor, bar boundaries, 8-bar alignment
- [ ] **Phase 4: Full Section Detection** - Energy-based detection of Drop 1, Breakdown, Drop 2, Outro with confidence scoring
- [ ] **Phase 5: Hot Cue Position Generator** - Compute hot cue A/B/C positions per spec, bar-snapped, no labels
- [ ] **Phase 6: Cue Writer & Idempotency** - Non-destructive writes, idempotent re-runs, graceful error handling
- [ ] **Phase 7: Memory Cues** - Write all four memory cue positions (Drop 1, Breakdown, Drop 2, Outro)
- [ ] **Phase 8: Desktop UI — Track List & Apply** - PyQt6 window with track list, selection, Apply button, progress, backup path
- [ ] **Phase 9: Desktop UI — Preview & Settings** - Proposed cue preview before apply, settings panel for color/intro toggle/overwrite policy

## Phase Details

### Phase 1: CLI Proof-of-Concept
**Goal**: Prove the full read-detect-write pipeline works on a single real track and the result loads correctly in Rekordbox.
**Depends on**: Nothing (first phase)
**Requirements**: FOUND-01, FOUND-02, FOUND-03, FOUND-04, FOUND-05, FOUND-06, WAVE-01, WAVE-02, SAFE-01
**Success Criteria** (what must be TRUE):
  1. Running `python main.py <track_id>` on a real DnB track opens master.db without error and without corrupting it
  2. The script locates and parses the ANLZ `.DAT` file for that track and reads a non-empty PWAV amplitude array
  3. A rough energy onset is detected from the PWAV data and the script prints the bar position it would place the cue at
  4. A single hot cue is written to master.db: backup created first, psutil guard blocks if rekordbox.exe is running, write uses BEGIN EXCLUSIVE transaction with full rollback on error
  5. Schema validated at startup via PRAGMA user_version and PRAGMA table_info(DjmdCue) before any write; unrecognized schema aborts cleanly
  6. After closing and re-opening Rekordbox, the written hot cue appears on the correct track at the correct position
**Plans:** 2 plans
Plans:
- [x] 01-01-PLAN.md — Read pipeline: DB open, schema validation, ANLZ/PWAV parsing, energy onset detection
- [x] 01-02-PLAN.md — Write pipeline: process guard, backup, hot cue write, CLI entry point, Rekordbox verification

### Phase 2: Waveform Parser Hardening
**Goal**: Make waveform loading production-grade by exploiting Rekordbox's own phrase analysis when available and handling all missing-file scenarios gracefully.
**Depends on**: Phase 1
**Requirements**: WAVE-03, WAVE-04
**Success Criteria** (what must be TRUE):
  1. When a track's `.EXT` file contains a PSSI tag, the app reads it and uses Rekordbox's own phrase section data instead of running energy analysis
  2. When a track has no `.DAT` or `.EXT` file (unanalyzed track), the app skips it with a visible per-track warning message and continues processing other tracks
  3. When a ANLZ file exists but is truncated or malformed, the app catches the parse error, warns the user, and does not crash
**Plans**: TBD

### Phase 3: Beat Grid & Bar Math
**Goal**: Establish precise bar-level timing from the Rekordbox beat grid so every cue position can be anchored to a musically correct bar boundary.
**Depends on**: Phase 1
**Requirements**: DETECT-01, DETECT-02, DETECT-03, DETECT-08
**Success Criteria** (what must be TRUE):
  1. The app reads DjmdBeat for a track and derives first_beat_ms and BPM, producing a list of bar start times in milliseconds that are audibly on-grid when previewed in Rekordbox
  2. Given a raw detection position in milliseconds, the app snaps it to the nearest 8-bar boundary using the beat grid anchor
  3. Tracks where the beat grid BPM falls outside 155–185 BPM are flagged with a visible warning ("likely mis-detected BPM") before any cue is written
  4. Energy-per-bar values computed from the PWAV array using the derived bar boundaries produce a meaningful signal that visually correlates with the track's loud/quiet sections
**Plans**: TBD

### Phase 4: Full Section Detection
**Goal**: Reliably detect all structural sections of a DnB track — Drop 1, Breakdown, Drop 2, and Outro — from PWAV energy data, with per-section confidence scores.
**Depends on**: Phase 3
**Requirements**: DETECT-04, DETECT-05, DETECT-06, DETECT-07, DETECT-09
**Success Criteria** (what must be TRUE):
  1. Running the detector on 10 test DnB tracks produces a Drop 1 position that lands on or within 2 bars of the audible first drop for at least 8 of 10 tracks
  2. The detector identifies a Breakdown region (energy valley after Drop 1) and aligns its start to the nearest 8-bar boundary
  3. Drop 2 is detected as the second major energy onset following the Breakdown
  4. Outro is detected as the final sustained low-energy region in the last quarter of the track
  5. Each detected section has a confidence score (0–100%); sections with confidence below a threshold are flagged in CLI output for manual review
  6. When no Breakdown is detectable (full-power roller), the detector omits the Breakdown and Drop 2 cues and logs the reason rather than placing a wrong cue
**Plans**: TBD

### Phase 5: Hot Cue Position Generator
**Goal**: Translate detected section positions into the exact hot cue slot assignments and bar-snapped millisecond positions specified for the project.
**Depends on**: Phase 4
**Requirements**: CUE-01, CUE-02, CUE-03, CUE-08, CUE-11
**Success Criteria** (what must be TRUE):
  1. Hot cue A (slot 0) is always placed at bar 0 regardless of detection results, position snapped to the beat grid first-bar millisecond
  2. Hot cue B (slot 1) is always placed at bar 16, computed from the beat grid anchor and BPM
  3. Hot cue C (slot 2) is placed 8 bars before Drop 1 when Drop 1 is beyond bar 8; when Drop 1 is at bar 8 or earlier, slot 2 is omitted
  4. All three hot cue positions are snapped to the nearest bar boundary using the beat grid, not raw millisecond computation
  5. Generated cue records have no Comment text — the Comment field is empty exactly as Rekordbox sets it when a user manually places a hot cue
**Plans**: TBD

### Phase 6: Cue Writer & Idempotency
**Goal**: Write cues to master.db safely, preserving all user-placed cues, and guarantee that re-running the tool produces the same end state without duplicating or corrupting cues.
**Depends on**: Phase 5
**Requirements**: CUE-09, CUE-10, SAFE-02
**Success Criteria** (what must be TRUE):
  1. Running the tool twice on the same track produces exactly the same set of cues in master.db with no duplicates — hot cue slots A/B/C and memory cues at the same bar positions are replaced, not added again
  2. Hot cue slots D–H and any memory cues at positions the tool did not generate are untouched after a write
  3. When a track has existing hot cues in slots A, B, or C placed manually by the user, the tool replaces only its own prior cues (identified by position + color match) and does not delete the user's cues in other slots
  4. Tracks with missing or corrupt ANLZ files, empty beat grids, or unanalyzed state are skipped cleanly without writing any rows or triggering a rollback on other tracks in the same batch
**Plans**: TBD

### Phase 7: Memory Cues
**Goal**: Write all four memory cue positions — Drop 1, Breakdown, Drop 2, and Outro — in addition to the hot cues, completing the full cue set for each processed track.
**Depends on**: Phase 6
**Requirements**: CUE-04, CUE-05, CUE-06, CUE-07
**Success Criteria** (what must be TRUE):
  1. After processing a track, four memory cues appear in Rekordbox at Drop 1, Breakdown start, Drop 2, and Outro start — each at a bar-snapped position
  2. Memory cues have no Comment text, consistent with how Rekordbox writes manually placed memory cues
  3. When a structural section was not detected (e.g., no Breakdown found), the corresponding memory cue is omitted rather than placed at a fallback position
  4. Memory cues at the same bar positions survive an idempotent re-run (same result as Phase 6 behaviour for hot cues)
**Plans**: TBD

### Phase 8: Desktop UI — Track List & Apply
**Goal**: Deliver a functional PyQt6 desktop window where the user can browse their Rekordbox library, select tracks, and apply cue points with progress feedback and backup confirmation.
**Depends on**: Phase 7
**Requirements**: UI-01, UI-02, UI-04, UI-06
**Success Criteria** (what must be TRUE):
  1. The app opens a window showing a table of all tracks from DjmdContent with columns for title, artist, BPM, duration, and cue status (whether RekordCue cues already exist)
  2. The user can select one or more tracks from the table using standard click/shift-click/ctrl-click
  3. Clicking Apply runs the full detection and write pipeline for all selected tracks, showing a progress indicator that updates per-track
  4. After a successful write, the window displays the backup file path so the user knows where the pre-write backup is stored
  5. If rekordbox.exe is running when Apply is clicked, a modal dialog blocks the operation and tells the user to close Rekordbox; the write does not proceed
**Plans**: TBD
**UI hint**: yes

### Phase 9: Desktop UI — Preview & Settings
**Goal**: Let the user inspect proposed cue positions before committing them, and configure section colors, intro length, and overwrite policy through a settings panel.
**Depends on**: Phase 8
**Requirements**: UI-03, UI-05
**Success Criteria** (what must be TRUE):
  1. When a track is selected, the UI shows a list of proposed cue positions (bar number and timestamp for each section) before the user clicks Apply
  2. The settings panel allows the user to choose a color for each section type (intro anchor, pre-drop, drop, breakdown, outro) and the chosen colors are used on the next Apply
  3. The settings panel includes a 16-bar / 32-bar intro toggle that shifts the bar-16 and bar-0 hot cue anchor expectations when enabled
  4. The settings panel exposes an overwrite policy: "replace existing RekordCue cues" vs "skip tracks that already have RekordCue cues"
**Plans**: TBD
**UI hint**: yes

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. CLI Proof-of-Concept | 2/2 | Complete | 2026-04-08 |
| 2. Waveform Parser Hardening | 1/1 | Complete | 2026-04-09 |
| 3. Beat Grid & Bar Math | 0/TBD | Not started | - |
| 4. Full Section Detection | 0/TBD | Not started | - |
| 5. Hot Cue Position Generator | 0/TBD | Not started | - |
| 6. Cue Writer & Idempotency | 0/TBD | Not started | - |
| 7. Memory Cues | 0/TBD | Not started | - |
| 8. Desktop UI — Track List & Apply | 0/TBD | Not started | - |
| 9. Desktop UI — Preview & Settings | 0/TBD | Not started | - |
