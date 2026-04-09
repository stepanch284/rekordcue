# Requirements: RekordCue

**Defined:** 2026-04-08
**Core Value:** A DnB DJ can select tracks from their Rekordbox library and get correctly placed structural cue points without manually scrubbing through each track.

## v1 Requirements

### Foundation

- [x] **FOUND-01**: App reads Rekordbox's SQLite `master.db` via pyrekordbox without corrupting it
- [x] **FOUND-02**: App detects Rekordbox's AppData path on Windows (`%APPDATA%\Pioneer\rekordbox*`) with fallback enumeration for version differences
- [x] **FOUND-03**: App checks if `rekordbox.exe` is running before any write; if detected, shows a clear dialog telling the user to close Rekordbox and blocks the operation until they do
- [x] **FOUND-04**: App creates a timestamped backup of `master.db` before every write operation
- [x] **FOUND-05**: App validates the `master.db` schema version at startup (`PRAGMA user_version`) and refuses to write if unrecognized
- [x] **FOUND-06**: App inspects `PRAGMA table_info(DjmdCue)` at startup to verify expected schema before writing

### Waveform Analysis

- [x] **WAVE-01**: App locates ANLZ `.DAT` and `.EXT` files from `DjmdContent.AnalysisDataPath` in the database
- [x] **WAVE-02**: App parses the `PWAV` tag (amplitude array at ~150 samples/sec) from `.DAT` files using pyrekordbox
- [ ] **WAVE-03**: App checks for `PSSI` phrase tag in `.EXT` files and uses it as section data if available (Rekordbox's own phrase analysis shortcut)
- [ ] **WAVE-04**: App gracefully skips tracks with missing or incomplete ANLZ files with a user-visible warning

### Section Detection

- [ ] **DETECT-01**: App reads beat grid from PQTZ tag in ANLZ .DAT file (via pyrekordbox `get_beat_grid()`) to anchor timing at bar 0
- [ ] **DETECT-02**: App attempts PSSI phrase analysis first (reading PHRS tag from .EXT if available); falls back to energy-based detection if PSSI unavailable
- [ ] **DETECT-03**: App aligns all detected section start points to the nearest 8-bar boundary
- [ ] **DETECT-04**: App detects Drop 1 as the first major energy onset after the intro (mean amplitude threshold) — 16 or 32 bars from bar 0
- [ ] **DETECT-05**: App detects the Breakdown as the energy drop before Drop 2 (RMS drop + mean amplitude valley) — a multiple of 8 bars in duration
- [ ] **DETECT-06**: App detects Drop 2 as the second major energy onset following the breakdown
- [ ] **DETECT-07**: App detects the Outro as the final low-energy section at the end of the track
- [ ] **DETECT-08**: App validates BPM is in DnB range (155–185 BPM) and **hard-blocks** out-of-range tracks (does not place cues, skips processing)
- [ ] **DETECT-09**: App assigns a confidence score (0–100%) to each section detection; all sections placed regardless, user can delete if needed
- [ ] **DETECT-10**: App detects when beat grid bar 0 is offset > 100ms from track start, auto-shifts all bar times to align bar 0 with 0ms, prints offset message to CLI
- [ ] **DETECT-11**: App auto-detects intro length (16-bar vs 32-bar) per track via energy analysis; if intro is low-energy through bar 16, checks through bar 32
- [ ] **DETECT-12**: App warns user "This track has not been analyzed in Rekordbox yet. Phrase analysis requires Rekordbox analysis. Please analyze in Rekordbox first." and skips processing
- [ ] **DETECT-13**: App treats half-tempo and unusual BPM tracks as informational only; user sees warning but processing continues (user responsible for correction)

### Cue Writing

- [ ] **CUE-01**: Hot cue A (kind=1, slot 0) placed at bar 0 (track start / intro anchor) — always
- [ ] **CUE-02**: Hot cue B (kind=2, slot 1) placed at bar 16 (mid-intro navigation point) — always
- [ ] **CUE-03**: Hot cue C (kind=3, slot 2) placed 8 bars before Drop 1 (pre-drop mix-in point) — if Drop 1 is beyond bar 8
- [ ] **CUE-04**: Memory cue placed at Drop 1 (exact bar where first drop begins)
- [ ] **CUE-05**: Memory cue placed at the start of the Breakdown before Drop 2 (end of post-drop phrase, multiple of 8 bars)
- [ ] **CUE-06**: Memory cue placed at Drop 2
- [ ] **CUE-07**: Memory cue placed at the start of the Outro (final section of the track)
- [ ] **CUE-08**: Cues have **no custom text label** — written exactly as Rekordbox does when placing cues manually (hot cues use their slot, memory cues have no name); color coding carries the meaning
- [ ] **CUE-09**: App does not touch cues in hot cue slots D–H or memory cues outside its target bar positions (preserves manually placed cues)
- [ ] **CUE-10**: App is idempotent — re-running replaces hot cue slots A, B, C and memory cues at the same bar positions, identified by position + color match
- [ ] **CUE-11**: All cue positions are snapped to the nearest **8-bar boundary** (not arbitrary bar) using the Rekordbox beat grid

### Batch Processing & Existing Cues

- [ ] **BATCH-01**: App skips any track that already has cues in hot cue slots A, B, or C (preserves manual work)
- [ ] **BATCH-02**: App processes all analyzed tracks in a specified folder; looks up track IDs in Rekordbox database
- [ ] **BATCH-03**: App produces a summary report after batch processing: count of tracks processed, skipped (with reasons: BPM out of range, existing cues, missing ANLZ data), and failed
- [ ] **BATCH-04**: If a track fails during batch processing, app logs the error and continues with remaining tracks (fail-safe batch)

### Desktop UI

- [ ] **UI-01**: Main window shows track list from Rekordbox library (`DjmdContent`) with columns: title, artist, BPM, duration, **analysis status indicator** (checkmark if Rekordbox analyzed, "?" if not)
- [ ] **UI-02**: User can select one or more tracks for processing
- [ ] **UI-03**: Visual waveform canvas shows proposed cue positions as vertical marker lines with section colors before Apply button
- [ ] **UI-04**: Apply button writes cues to `master.db` for selected tracks with progress feedback
- [ ] **UI-05**: Settings panel: configurable colors per section type (Intro/Drop1/Breakdown/Drop2/Outro), persistent to JSON config file in `%APPDATA%\RekordCue\`
- [ ] **UI-06**: App shows backup file path and CLI summary after successful write ("X tracks processed, Y skipped, Z failed")
- [ ] **UI-07**: Folder batch mode: user specifies Rekordbox library folder; app processes all analyzed tracks, shows summary of processed/skipped
- [ ] **UI-08**: Per-track intro length toggle (16-bar / 32-bar) shown before Apply if auto-detection is ambiguous
- [ ] **UI-09** *(Phase 9)*: Settings panel shows "Analyze tracks in Rekordbox" prompt with direct link/button guidance
- [ ] **UI-10** *(Phase 9)*: Color picker UI per section type with preview of selected colors

### Safety & Reliability

- [x] **SAFE-01**: All DB writes use `BEGIN EXCLUSIVE` transactions with full rollback on any error
- [ ] **SAFE-02**: App handles missing/corrupt ANLZ files, unanalyzed tracks, and empty beat grids without crashing

## v2 Requirements

### Waveform Preview

- **PREV-01**: Waveform canvas renders PWAV amplitude data as a visual waveform with cue marker overlays
- **PREV-02**: Waveform canvas updates cue overlay positions before applying, giving visual confirmation

### Expanded Genre Support

- **GENRE-01**: 32-bar intro mode toggle for tracks with longer intros (optional override per track)
- **GENRE-02**: House/Techno mode with 32-bar phrase detection and adjusted section vocabulary

### Batch & Library Workflows

- **BATCH-01**: Process all tracks in a selected Rekordbox playlist
- **BATCH-02**: Process entire library, skipping tracks that already have `[RC]` cues
- **BATCH-03**: Export cue report (CSV: track, section, position_ms, confidence)

### Platform & Distribution

- **DIST-01**: PyInstaller-packaged Windows `.exe` (no Python installation required for users)
- **DIST-02**: macOS path support (`~/Library/Application Support/Pioneer/rekordbox/`)

## Out of Scope

| Feature | Reason |
|---------|--------|
| Audio file loading (librosa/madmom) | Rekordbox's waveform data is sufficient; reprocessing audio adds latency and complexity with no benefit |
| Rekordbox XML export/import | Direct DB access is faster and more reliable; XML round-trip loses sync with live DB state |
| macOS support | Windows-first per PROJECT.md; defer to v2 |
| Web app version | Future milestone after desktop is proven stable |
| ML-based section detection | Energy threshold on PWAV data is sufficient for DnB's predictable structure; ML is overkill and reduces trust |
| Rekordbox integration via API | No public API exists; reverse-engineered DB access is the only available path |
| Real-time library sync | One-way write tool; Rekordbox remains source of truth for all other library data |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| FOUND-01 | Phase 1 | Complete |
| FOUND-02 | Phase 1 | Complete |
| FOUND-03 | Phase 1 | Complete |
| FOUND-04 | Phase 1 | Complete |
| FOUND-05 | Phase 1 | Complete |
| FOUND-06 | Phase 1 | Complete |
| WAVE-01 | Phase 1 | Complete |
| WAVE-02 | Phase 1 | Complete |
| WAVE-03 | Phase 2 | Pending |
| WAVE-04 | Phase 2 | Pending |
| DETECT-01 | Phase 3 | Pending |
| DETECT-02 | Phase 3 | Pending |
| DETECT-03 | Phase 3 | Pending |
| DETECT-04 | Phase 4 | Pending |
| DETECT-05 | Phase 4 | Pending |
| DETECT-06 | Phase 4 | Pending |
| DETECT-07 | Phase 4 | Pending |
| DETECT-08 | Phase 3 | Pending |
| DETECT-09 | Phase 4 | Pending |
| DETECT-10 | Phase 3 | Pending |
| DETECT-11 | Phase 3 | Pending |
| DETECT-12 | Phase 4 | Pending |
| DETECT-13 | Phase 4 | Pending |
| CUE-01 | Phase 5 | Pending |
| CUE-02 | Phase 5 | Pending |
| CUE-03 | Phase 5 | Pending |
| CUE-04 | Phase 7 | Pending |
| CUE-05 | Phase 7 | Pending |
| CUE-06 | Phase 7 | Pending |
| CUE-07 | Phase 7 | Pending |
| CUE-08 | Phase 5 | Pending |
| CUE-09 | Phase 6 | Pending |
| CUE-10 | Phase 6 | Pending |
| CUE-11 | Phase 5 | Pending |
| BATCH-01 | Phase 8 | Pending |
| BATCH-02 | Phase 8 | Pending |
| BATCH-03 | Phase 8 | Pending |
| BATCH-04 | Phase 8 | Pending |
| UI-01 | Phase 8 | Pending |
| UI-02 | Phase 8 | Pending |
| UI-03 | Phase 9 | Pending |
| UI-04 | Phase 8 | Pending |
| UI-05 | Phase 9 | Pending |
| UI-06 | Phase 8 | Pending |
| UI-07 | Phase 8 | Pending |
| UI-08 | Phase 9 | Pending |
| UI-09 | Phase 9 | Pending |
| UI-10 | Phase 9 | Pending |
| SAFE-01 | Phase 1 | Complete |
| SAFE-02 | Phase 6 | Pending |

**Coverage:**
- v1 requirements: 48 total (added DETECT-10-13, BATCH-01-04, UI-08-10, plus existing)
- Mapped to phases: 48
- Unmapped: 0 ✓

---
*Requirements defined: 2026-04-08*
*Last updated: 2026-04-09 — Added hybrid energy detection, folder batch processing, existing cue skipping, and confidence preview per user design decisions*
