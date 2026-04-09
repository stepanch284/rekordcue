# Feature Decisions — RekordCue Session 2026-04-09

**Date:** 2026-04-09
**Status:** Collected from comprehensive feature review
**Scope:** v1 feature set, UX decisions, technical approach

---

## Summary of Decisions

### Core Algorithm & Analysis

| Decision | Choice | Rationale |
|----------|--------|-----------|
| PSSI phrase analysis | Use PSSI if available, require Rekordbox pre-analysis | Rekordbox's phrase detection is Genre-aware; user must analyze tracks first in Rekordbox |
| Energy detection fallback | Research + test multiple approaches, possibly ML-based | Will evaluate threshold-based, RMS hybrid, ML image classification on waveforms |
| Grid offset correction | Auto-detect + auto-shift to bar 0 | Handles Rekordbox's occasional misaligned beat grids (5-10% of library) |
| Intro length | Auto-detect per track (16 vs 32 bars) | DnB variance: some label-style tracks use 32-bar intros; detect via energy analysis |
| Silence handling | Ignore leading silence, rely on beat grid | White-label tracks may have silence; beat grid anchor is more reliable than audio onset |
| Half-tempo tracks | Warn user to fix in Rekordbox, do not attempt process | Hard to detect; BPM validation flags these; user must correct source material |

---

### Cue Placement & Memory

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Hot cue A/B placement | Always: bar 0, bar 16 | Structural anchors regardless of detection |
| Hot cue C placement | 8 bars before Drop 1 (if Drop 1 > bar 8) | Pre-drop mixing point per DJ workflow |
| Hot cue naming | No text labels, color coding only | Simpler, visual muscle memory during performance |
| Memory cue positions | Drop 1, Breakdown, Drop 2, Outro | Mark energy changes; use in addition to hot cues |
| Memory cue naming | No text labels | Consistent with hot cue approach |

---

### Track Processing

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Show in track list | All tracks (with analysis status indicator) | User can see what's been analyzed; skip if unanalyzed with clear message |
| Existing cue detection | Skip if hot cue slots A, B, or C already filled | Preserves prior work without asking |
| Batch error handling | Fail-safe: skip failed track, continue batch | One track's missing ANLZ shouldn't block entire library |
| Confidence threshold | No hard cut-off; place all detected sections | User can delete afterward if needed (simpler than guessing threshold) |
| Unusual structure (remixes) | Attempt analysis anyway | Let energy detection try; worst case is wrong cues user deletes |
| Short tracks (< 2 min) | Place only cues that fit | Partial cue sets are better than none |

---

### User Interface & Settings

| Decision | Choice | Rationale |
|----------|--------|-----------|
| UI framework | Research phase required before committing | Evaluate PyQt6 vs wxPython vs Electron; need to prototype waveform canvas |
| Cue preview display | Visual waveform with overlaid cue markers | User can see proposed cues against track structure before applying |
| Color customization | Configurable in settings panel | DJs have established color conventions; must not override |
| Settings storage | JSON file (Windows: %APPDATA%/RekordCue/) | Simple, version-able, human-readable |
| Batch report | CLI summary only (v1) | "X tracks processed, Y skipped (reasons), Z failed" printed to console |
| Undo feature | Manual restore from timestamped backup | User locates .bak file if needed; automatic undo is out of scope |

---

### Data Flow & Processing

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Track pre-requisite | Rekordbox analysis required | PSSI phrase tags only exist if Rekordbox has analyzed the track |
| Analysis pipeline | PSSI → sections, fallback to energy detection | Try Rekordbox first; energy analysis is backup |
| Config approach | Per-track intro override at UI (Phase 9) | System default = 16-bar; user can toggle per-track if needed |
| Batch mode scope | Process selected tracks or folder (Phase 8-9) | Start with track selection; expand to folder scan later |

---

## New Requirements (From This Session)

### Phase 3: Beat Grid & Bar Math

- [ ] **DETECT-10**: App detects when beat grid bar 0 is offset from track audio start (position > ~100ms), auto-shifts all bar times to align bar 0 with 0ms, prints "Grid offset detected: shifted by Xms" to CLI
- [ ] **DETECT-11**: App auto-detects intro length (16 vs 32 bars) per track via energy analysis; if intro energy remains low at bar 16, continue checking through bar 32

### Phase 4: Full Section Detection

- [ ] **DETECT-12**: App attempts PSSI phrase analysis first (from .EXT PHRS tag if available); if no PSSI, falls back to energy-based detection
- [ ] **DETECT-13**: App warns user "This track has not been analyzed in Rekordbox yet. Phrase analysis requires Rekordbox BPA/phrase analysis. Please analyze in Rekordbox first."

### Phase 8: Desktop UI — Track List & Apply

- [ ] **UI-08**: Track list shows analysis status indicator per track (checkmark = Rekordbox analyzed, "?" = not analyzed)
- [ ] **UI-09**: Settings panel with hotkey/button to launch Rekordbox if needed ("Click to open Rekordbox and analyze tracks")

### Phase 9: Desktop UI — Preview & Settings

- [ ] **UI-10**: Color picker per section type in settings; defaults to Green/Red/Blue/Orange; persisted to JSON config
- [ ] **UI-11**: Per-track intro length toggle UI (before Apply) — radio button 16-bar / 32-bar
- [ ] **UI-12**: Waveform canvas renders PWAV data with vertical cue marker lines; cue colors match section type

---

## Deferred to v2+

- Advanced edge case handling (re-intros, extended breakdowns, fade-in detection)
- Machine learning exploration for detection (research phase for Phase 4, but defer implementation)
- HTML/detailed report export (use CLI summary for v1)
- Waveform visual feedback beyond basic marker lines
- Multi-library support (Rekordbox + Serato/Traktor)
- Auto-launch Rekordbox for analysis

---

## Research Tasks Before Implementation

### Phase 3 (Beat Grid & Bar Math)
- [ ] Test grid offset detection on 20 misaligned tracks; verify shift calculation
- [ ] Verify 16/32-bar detection algorithm on diverse DnB library

### Phase 4 (Full Section Detection)
- [ ] Research & test energy detection algorithms: simple threshold vs RMS vs ML image classification
- [ ] Benchmark against ground truth (manually cued reference tracks)
- [ ] Compare PSSI results vs energy detection on same tracks
- [ ] Document ML approach if chosen (training data source, model architecture, inference)

### Phase 8-9 (Desktop UI)
- [ ] Prototype waveform canvas in PyQt6 + wxPython to compare rendering performance
- [ ] Benchmark startup time with 500-5000 track libraries
- [ ] Test JSON config round-trip with user customizations

---

## Impact on Roadmap

**Phase 3:** Add 2 new tasks for grid offset + intro length detection
**Phase 4:** Add 2-3 tasks for energy research + PSSI integration
**Phase 8:** Add track status indicator + analysis prompts
**Phase 9:** Add UI research, color picker, per-track toggles, waveform canvas

**Total impact:** +8-10 tasks, estimated +2-3 weeks of research + implementation

---

## Next Steps (Recommended Order)

1. **Immediate:** Update REQUIREMENTS.md with DETECT-10 through DETECT-13, UI-08 through UI-12
2. **Phase 3 Plan 03:** Add grid offset detection task + intro length auto-detect task
3. **Phase 4 Research:** Deep dive on energy detection algorithms (spawn research agent)
4. **Phase 8-9 Research:** UI framework prototyping + waveform canvas feasibility studies

---

*Created: 2026-04-09 during comprehensive feature review*
