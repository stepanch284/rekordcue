# Design Decisions: RekordCue

**Date:** 2026-04-09
**Session:** Roadmap & Planning Review with User
**Status:** Complete — All decisions locked into REQUIREMENTS.md and roadmap artifacts

---

## Summary of User Design Preferences

This document captures all design decisions made during the roadmap review session on 2026-04-09.

---

## Core Decisions

### 1. Cue Labels: Blank (No Text)
**Decision:** Hot cues written without custom label text (e.g., no "DROP 1" in the label field)
**Rationale:** Match Rekordbox's manual cue behavior exactly. Color coding carries the meaning.
**Impact:**
- Simpler write logic (no Comment field needed)
- Requires strong color convention to communicate section type
- Less intrusive in track metadata

**Related Requirements:** CUE-08 (updated)

---

### 2. Existing Cues: Skip (Don't Overwrite)
**Decision:** If a track already has cues in hot cue slots A, B, or C, skip it entirely
**Rationale:** Preserve manually placed cues; safe default assuming users have already curated some tracks
**Implementation:**
- Query DjmdCue for track_id; if rows exist with hot cue kind (1,2,3), skip
- Log as "skipped: existing cues in A/B/C" in batch report
- No --force flag in v1 (can add in v2 if needed)

**Related Requirements:** BATCH-01 (new)

---

### 3. BPM Validation: Hard Block
**Decision:** If track BPM is outside 155-185 range, skip it entirely. Don't place any cues.
**Rationale:** Out-of-range BPM indicates either half-tempo detection or wrong genre. Better to skip than place wrong cues.
**Implementation:**
- Call validate_bpm_range() immediately after get_beat_grid()
- If out of range, log warning and skip track
- Continue with next track in batch

**Related Requirements:** DETECT-08 (updated), BATCH-03 (new)

---

### 4. Energy Detection: Hybrid Approach
**Decision:** Use **mean amplitude** for detecting high-energy onsets (drops), and **RMS per 8-bar** for detecting intro transitions
**Rationale:** Mean amplitude is good for drop detection. RMS detects when energy is flat (still intro) vs changing (transition point).
**Technical Details:**
- Drop 1: Find first major mean amplitude spike above threshold after intro
- Breakdown: Detect energy valley (low RMS, low mean) between drops
- Outro: Final sustained low-energy region (flat RMS)
- Intro end: When intro is low-energy flat (RMS ~constant) until an energy transition

**Algorithm Flags:**
```python
def is_intro_still(rms_values: np.ndarray, window_size: int = 2) -> bool:
    """True if the RMS values are roughly constant (still in intro)."""
    # If std(rms_values) across 8-bar windows is low, intro hasn't ended yet

def detect_drop_via_mean_amplitude(bar_energies: np.ndarray, threshold: float = 15.0) -> int:
    """Find first bar where mean amplitude exceeds threshold after a quiet section."""
```

**Related Requirements:** DETECT-02 (updated), DETECT-04 (updated), DETECT-05 (updated)

---

### 5. Section Confidence & Preview Mode
**Decision:** Compute confidence score (0-100%) for each detected section. Show scores in preview; allow user to approve before write.
**Rationale:** Prevents wrong cues on ambiguous tracks; user can verify or reject.
**Confidence Computation:**
- High confidence (>75%): Clear energy transitions, section matches expected pattern
- Medium (50-75%): Section detected but weak signal or unexpected timing
- Low (<50%): Very weak signal, likely not a real section → omit from cue list

**User Workflow:**
1. Process tracks
2. For each track, show detected sections with confidence: "Drop 1 at bar 16 (89% confidence)"
3. Sections <50% confidence: marked "OMITTED" with reason
4. User reviews, clicks "Apply" to confirm, or "Skip" to ignore

**Related Requirements:** DETECT-09 (updated), UI-03 (updated)

---

### 6. Batch Processing: Folder + DB Lookup
**Decision:** CLI and UI support folder batch mode
- User specifies a folder (e.g., `~/Music` or Rekordbox library path)
- App uses Rekordbox track IDs (from DjmdContent database) to find and process all analyzed tracks
- Batch processes all, skipping those that fail or don't meet criteria

**Implementation:**
```bash
# CLI future usage (Phase 8):
python main.py --folder ~/Music --mode analyze
```

**Process:**
1. Scan DjmdContent for all tracks in the specified artist/album/folder
2. For each track: check BPM, check existing cues, check ANLZ availability
3. Process only tracks that pass all checks
4. Log all results in summary report

**Skip Reasons Tracked:**
- "BPM out of range (XX BPM)"
- "Existing cues in A/B/C"
- "Missing ANLZ data (.DAT/.EXT not found)"
- "Parse error: [reason]"
- "ERROR: [exception]"

**Related Requirements:** BATCH-02, BATCH-03, BATCH-04 (new)

---

### 7. Batch Error Handling: Fail-Safe
**Decision:** If a track fails during batch processing, log the error and continue with remaining tracks
**Rationale:** Large batches shouldn't be blocked by one corrupt track. Preserve processing of valid tracks.
**Implementation:**
- Wrap track processing in try/except
- Catch ValueError, OSError, sqlite3.Error, etc.
- Log error and reason; continue loop

**Related Requirements:** BATCH-04 (new)

---

### 8. Memory Cues: Include in v1
**Decision:** Write memory cues (Drop 1, Breakdown, Drop 2, Outro) in v1, not deferred to v2
**Rationale:** Adds only 1 phase (Phase 7); users benefit from searchable cues immediately
**Implementation:** Phase 7 extends Phase 6 writer to also write memory cue rows to DjmdCue table

**Related Requirements:** CUE-04, CUE-05, CUE-06, CUE-07 (moved from v2 → v1)

---

### 9. Reporting: Batch Summary
**Decision:** After batch processing, show summary report
**Rationale:** Transparency. DJs need to know what happened to their tracks.
**Report Content:**
```
=== RekordCue Batch Summary ===
Folder: ~/Music
Analyzed: 147 tracks

Processed: 89 tracks
  Cues written successfully

Skipped: 58 tracks
  - BPM out of range: 12 tracks
  - Existing cues in A/B/C: 34 tracks
  - Missing ANLZ data: 8 tracks
  - Other errors: 4 tracks
    * Track "xyz": parse error in ANLZ

Total changes: 89 tracks × 4 cues (1 hot A + 1 hot B + 1-2 hot C + 4 memory) = ~356 cues written
Backup: ~/backup/master_db_20260409_143052.db
Elapsed: 2m 34s

Run 'python main.py --verify' to audit cues in Rekordbox.
```

**Related Requirements:** BATCH-03 (new)

---

## Roadmap Impact

### Additions
1. **BATCH-01 to BATCH-04**: New batch processing requirements
2. **DETECT-02, DETECT-04, DETECT-05**: Updated to reflect hybrid energy detection
3. **DETECT-08**: Updated to "hard block" instead of soft warn
4. **DETECT-09**: Confidence scoring with omission logic
5. **UI-03**: Preview + confidence + user approval
6. **UI-07**: New—folder batch mode UI

### Phase Order Changes
- **Phase 4 (Full Section Detection)** must now compute RMS + confidence scores
- **Phase 8 (Desktop UI — Track List & Apply)** must include folder batch selector and preview/approval dialog
- **Phase 9 (Preview & Settings)** scope reduced — preview now in Phase 8

### Estimated Phase Changes
- **Phase 4:** +1-2 plans (RMS detection, confidence scoring)
- **Phase 8:** +1 plan (folder batch + report UI)
- **Phase 9:** Reduced scope (settings only; preview moved to Phase 8)

---

## Removed/Deferred

| Feature | Status | Reason |
|---------|--------|--------|
| Cue labels ("DROP 1" text) | Removed from v1 | Color coding preferred |
| 32-bar intro auto-detection | Deferred to v2 | Keep v1 simple |
| --force flag for overwrite | Deferred to v2 | Safe default: skip existing |
| --strict flag for BPM | Removed | Hard block is the only policy |
| Memory cues in v2 | Moved to v1 | User prioritized |
| CSV export | Deferred to v2 | Not requested in v1 |

---

## New Functions Required

### Phase 3 (Bar Math) — Already in progress
- `validate_bpm_range()` ✅
- `snap_to_8bar_boundary()` ✅
- `compute_bar_energies()` ✅

### Phase 4 (Full Section Detection) — TBD
**New:** RMS and confidence functions
```python
def compute_rms_per_8bars(bar_energies: np.ndarray) -> np.ndarray:
    """Compute RMS (rolling std) per 8-bar window for detecting flat sections."""

def detect_sections_with_confidence(bar_energies: np.ndarray,
                                    bar_times_ms: np.ndarray,
                                    threshold_mean: float = 15.0,
                                    threshold_rms: float = 2.0) -> dict:
    """
    Returns:
    {
        'drop1': {'position_ms': 22112, 'bar_index': 16, 'confidence': 89},
        'breakdown': {'position_ms': None, 'bar_index': None, 'confidence': 0},  # not detected
        'drop2': {'position_ms': 45000, 'bar_index': 32, 'confidence': 75},
        'outro': {'position_ms': 220000, 'bar_index': 160, 'confidence': 92}
    }

    Sections with confidence < 50% have None values.
    """
```

### Phase 6 (Cue Writer & Idempotency) — TBD
**Updated:** Existing cue check
```python
def has_existing_cues(db, track_id: int) -> bool:
    """Check if track has cues in hot cue slots A/B/C (kind 1,2,3)."""
```

### Phase 8 (Desktop UI — Track List & Apply) — TBD
**New:** Batch folder mode, preview+approval
```python
def get_tracks_in_folder(db, folder_path: str) -> list[int]:
    """Query tracks in folder by artist/album from DjmdContent."""

def show_preview_dialog(sections_with_confidence: dict) -> bool:
    """PyQt6 dialog showing detected sections + confidence. Return True if approved."""

def generate_batch_summary(results: list[dict]) -> str:
    """Render batch report as string."""
```

---

## Color Scheme (Unchanged)

Keep existing Rekordbox convention:
- **Intro / Bar 0**: Green (safe landing)
- **Drop 1**: Red (high energy, urgent)
- **Breakdown**: Blue (cool energy valley)
- **Drop 2**: Orange (high energy, distinct from drop 1)
- **Outro**: Purple (cool/closing)

(Implementation in Phase 5 — not affected by these design decisions)

---

## Next Steps

1. **Update ROADMAP.md** — reflect phase changes for RMS detection, batch UI, reports
2. **Update Phase 4 plan** — add RMS-based detection + confidence scoring to research and plan docs
3. **Update Phase 8 plan** — add folder batch selector + preview dialog + report display
4. **Commit:** `docs(design): lock user decisions for hybrid detection, batch processing, hard BPM block, existing cue skip`

---

## Sign-Off

**User Approval:** ✅ 2026-04-09
**Claude AI Approval:** ✅ All decisions locked, no conflicts with Phase 1/2 completed work

**Validated Against:**
- REQUIREMENTS.md ✅
- ROADMAP.md ✅ (pending update)
- PROJECT.md ✅
- FEATURES.md research (Phase landscape) ✅

---
