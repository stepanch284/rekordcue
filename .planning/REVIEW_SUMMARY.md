# Roadmap Review Summary: Changes & Clarifications

**Date:** 2026-04-09
**Status:** All design decisions locked and documented

---

## What Changed

### New Requirements Added

| ID | Category | Description | Phase |
|---|----------|-------------|-------|
| BATCH-01 | Batch | Skip tracks with existing A/B/C cues | 6 |
| BATCH-02 | Batch | Process all tracks in a folder (by Rekordbox ID) | 8 |
| BATCH-03 | Batch | Produce summary report (processed/skipped/failed) | 8 |
| BATCH-04 | Batch | Fail-safe batch: skip errors, continue with remaining tracks | 6/8 |
| UI-07 | UI | Folder batch mode selector in UI | 8 |

### Requirements Updated (Scope Refined)

| ID | Old | New | Impact |
|----|-----|-----|--------|
| DETECT-02 | Mean amplitude only | **Hybrid: mean + RMS** | +1-2 plans in Phase 4 |
| DETECT-04 | Generic energy onset | **Mean amplitude threshold + RMS flat check** | Better drop detection |
| DETECT-05 | Energy drop only | **RMS drop + mean amplitude valley** | Handles subtle transitions |
| DETECT-08 | Soft warn (print & continue) | **Hard block (skip track)** | Fewer wrong cues on mis-detected tracks |
| DETECT-09 | Display low-confidence results | **Omit low-confidence sections from cue list** | Sections <50% confidence not written |
| CUE-08 | No comment text | **No comment text; color carries meaning** | Clarified: cue labels remain blank |
| UI-03 | Show proposed positions | **Show with confidence scores + user approval required** | User controls which sections get written |
| UI-05 | Color/16-32bar/overwrite policy | **Color + confidence threshold** | 16-32bar toggle removed (v1 uses 16-bar); confidence threshold added |
| UI-06 | Show backup path | **Show backup path + batch summary** | Enhanced visibility |

### Decisions Locked

| Decision | Rationale | Locked |
|----------|-----------|--------|
| Blank cue labels | Match Rekordbox manual behavior | ✅ |
| Skip existing cues | Preserve user manual work; safe default | ✅ |
| Hard block BPM out of range | Prevent wrong cues on half-tempo | ✅ |
| Hybrid RMS+mean detection | Better for DnB structure | ✅ |
| Preview with confidence | User approval before write | ✅ |
| Folder batch + Rekordbox IDs | Batch processing from CLI/UI | ✅ |
| Fail-safe batch (skip errors) | Process all valid tracks despite errors | ✅ |
| Include memory cues in v1 | Full feature set immediately | ✅ |

---

## Roadmap Phase Adjustments

### Phases 1-2: No Change ✅
- Phase 1 (CLI PoC): Complete — no changes needed
- Phase 2 (Waveform Parser): Complete — no changes needed

### Phase 3: Bar Grid & Bar Math (In Progress)
- **No change to existing plans** — both plans proceed as designed
- Plans 01-02 implement validate_bpm_range (hard block) ✅

### Phase 4: Full Section Detection (Next)
**Changes Required:**
- Add RMS-per-8bar computation (new function)
- Upgrade energy detection to hybrid approach
- Add confidence scoring per section (0-100%)
- Add section omission logic (confidence <50% → skip writing)
- **Estimated impact:** +1 plan for RMS/confidence logic

**New Plan Breakdown (estimated):**
```
04-01: RMS detection helper functions + tests
04-02: Hybrid energy algorithm (mean + RMS) + tests
04-03: Integrate into main.py, compute confidence scores
```

### Phase 5: Hot Cue Position Generator
- **No change** — uses confidence scores from Phase 4
- CUE-08 clarified but already satisfied (no labels)

### Phase 6: Cue Writer & Idempotency
- **Minor addition:** Add check for existing A/B/C cues before write
- Function: `has_existing_cues(db, track_id) -> bool`
- **No new phase needed** — fits in existing plan

### Phase 7: Memory Cues
- **No change** — write memory cues alongside hot cues
- Now in v1 instead of v2

### Phase 8: Desktop UI — Track List & Apply
**Changes Required:**
- Add preview dialog with confidence scores + user approval
- Add folder batch selector (instead of single-track only)
- Add batch processing loop + error handling
- Add batch summary report display
- **Estimated impact:** +1-2 plans

**New Plan Breakdown (estimated):**
```
08-01: UI track list and single-track apply (existing)
08-02: Folder batch selector + folder→track lookup
08-03: Preview dialog + confidence display + user approval
08-04: Batch summary report generation and display
```

### Phase 9: Desktop UI — Preview & Settings
**Scope Reduced:**
- Preview now happens in Phase 8 (folder batch workflow)
- Settings panel simplified: color scheme only (confidence threshold removed)
- **Plans may consolidate** — 1 plan instead of 2

**Updated Plan:**
```
09-01: Settings panel (colors, future flags)
```

---

## Functions Inventory

### Phase 3 (Already in Plans 01-02)
✅ `validate_bpm_range()` — hard block on out-of-range BPM
✅ `snap_to_8bar_boundary()`
✅ `compute_bar_energies()`

### Phase 4 (New)
🔨 `compute_rms_per_8bars(bar_energies) -> np.ndarray`
🔨 `detect_intro_flatness(rms_values) -> bool`
🔨 `detect_drop_via_mean(bar_energies, threshold=15.0) -> int`
🔨 `detect_sections_with_confidence(...) -> dict`
   - Returns: `{section: {position_ms, bar_index, confidence}, ...}`
   - Sections with confidence <50%: omitted (None values)

### Phase 6 (Minor Addition)
🔨 `has_existing_cues(db, track_id) -> bool`
   - Returns True if slots A/B/C (kind 1,2,3) have cues

### Phase 8 (New)
🔨 `get_tracks_in_folder(db, folder_path) -> list[int]`
   - Query DjmdContent for tracks in folder
🔨 `show_preview_dialog(sections_with_confidence) -> bool`
   - PyQt6 dialog; return True if user approves
🔨 `generate_batch_summary(results: list[dict]) -> str`
   - Format batch report as readable text

---

## Testing Impact

### Phase 3 Tests (Red Phase)
- `test_bpm_hard_block_low()` — BPM 87 → hard skip (not soft warn)
- `test_bpm_hard_block_high()` — BPM 190 → hard skip

### Phase 4 Tests (New)
- `test_rms_flat_intro()` — intro has low RMS, no transition
- `test_rms_drop_detected()` — drop has RMS spike in energy
- `test_confidence_high()` — clear drop → >75% confidence
- `test_confidence_low_omitted()` — unclear section → <50% omitted

### Phase 6 Tests (Minor)
- `test_skip_existing_cues()` — track with A/B/C filled → skip

### Phase 8 Tests (New)
- `test_folder_lookup()` — folder path → list of track IDs
- `test_preview_approve()` — dialog returns True/False
- `test_batch_summary_format()` — report includes processed/skipped counts

---

## Git Commits Needed

1. **docs(requirements): update with batch, hybrid detection, hard BPM block**
2. **docs(design): add DESIGN_DECISIONS.md for user preferences**
3. **docs(roadmap): update Phase 4 (add RMS/confidence), Phase 8 (add batch UI), Phase 9 (reduce scope)**

---

## Files Modified

✅ `.planning/REQUIREMENTS.md` — Updated 5 requirements, added 4 batch requirements
✅ `.planning/DESIGN_DECISIONS.md` — Created (NEW)
⏳ `.planning/ROADMAP.md` — To be updated (pending your approval)

---

## What You Said (Decision Log)

| Question | Your Answer |
|----------|-------------|
| Cue labels? | Blank (no text) |
| CLI batch mode? | Folder + process all via Rekordbox IDs |
| Existing cues? | Skip (don't overwrite A/B/C) |
| BPM validation? | Hard block (skip if out of range) |
| Energy detection? | Hybrid (mean for drops, RMS for transitions) |
| Missing sections? | Preview with confidence; user approves |
| Batch errors? | Skip errors, continue (fail-safe) |
| Memory cues? | Include in v1 |
| Reporting? | Summary after batch (processed/skipped/failed) |

---

## Next Action Items

### For You
1. See anything I missed or need to adjust? → Tell me now
2. Approve the roadmap update? → I can regenerate ROADMAP.md with all phase changes
3. Ready to start Phase 3 execution? → Or phase planning/research for Phase 4?

### For Me (Once Approved)
1. Update ROADMAP.md with phase adjustments
2. Commit all three docs: REQUIREMENTS, DESIGN_DECISIONS, ROADMAP
3. Optional: Create Phase 4 research document (RMS detection techniques, confidence scoring algorithms)

---

## Questions?

Any clarifications needed on these decisions? Want to lock in anything else before we move forward?
