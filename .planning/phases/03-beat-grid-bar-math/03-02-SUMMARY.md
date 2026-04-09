---
phase: 03-beat-grid-bar-math
plan: 02
type: tdd
date: 2026-04-09
status: completed
requirements_met:
  - DETECT-10
  - DETECT-11
---

# Phase 03-02 Summary: Grid Offset Detection & Intro Length Auto-Detection

## Objectives Completed

Implemented three new functions in `bar_math.py` to handle grid offset detection and intro length auto-detection. These functions address edge cases in ~5-10% of DnB library tracks where Rekordbox's beat grid analysis is misaligned.

### Functions Implemented

#### 1. `detect_grid_offset(bar_times_ms: np.ndarray) -> int`
- **Purpose**: Detect if beat grid bar 0 is offset from track start (0ms)
- **Logic**: Returns offset in ms if bar 0 position > 100ms threshold, else 0
- **Uses**: OFFSET_THRESHOLD_MS = 100 (per FEATURE_DECISIONS)
- **Handles**: Empty arrays, boundary conditions

#### 2. `shift_bar_times(bar_times_ms: np.ndarray, offset_ms: int) -> np.ndarray`
- **Purpose**: Shift all bar times backward to align bar 0 at 0ms
- **Logic**: Subtracts offset_ms from all values, clamps result >= 0
- **Safety**: Non-mutating (returns new array), prevents negative values
- **Returns**: np.ndarray with shifted times

#### 3. `detect_intro_length(bar_energies: np.ndarray) -> int`
- **Purpose**: Auto-detect intro length (16-bar or 32-bar)
- **Logic**: Compare energy windows:
  - If energy at bar 16 > bar 0-15 energy * 1.5 → return 16
  - Else if energy at bar 32 > bar 0-31 energy * 1.5 → return 32
  - Else → default to 16
- **Safety**: Handles short tracks (< 32 bars) by defaulting to 16

## Testing Results

**All 25 tests passed** (100% pass rate):
- 13 existing tests from Phase 03-01 (maintained backward compatibility)
- 12 new tests for grid offset, bar time shifting, and intro length detection

### New Test Coverage

**Grid Offset Detection (5 tests):**
- `test_detect_grid_offset_aligned` - bar_times_ms[0] = 43.0, returns 0
- `test_detect_grid_offset_misaligned` - bar_times_ms[0] = 250.0, returns 250
- `test_detect_grid_offset_boundary_low` - bar_times_ms[0] = 50.0, returns 0
- `test_detect_grid_offset_boundary_high` - bar_times_ms[0] = 150.0, returns 150
- `test_detect_grid_offset_empty` - empty array, returns 0

**Bar Time Shifting (3 tests):**
- `test_shift_bar_times_backward` - verify alignment to 0ms
- `test_shift_bar_times_no_negative_values` - clamping at 0
- `test_shift_bar_times_zero_offset` - non-mutating behavior

**Intro Length Detection (4 tests):**
- `test_detect_intro_length_16bar` - energy jump at bar 16
- `test_detect_intro_length_32bar` - energy jump at bar 32
- `test_detect_intro_length_ambiguous` - low energy throughout, defaults to 16
- `test_detect_intro_length_short_track` - < 32 bars, defaults to 16

## Code Quality

- **Docstrings**: All functions documented with purpose, args, returns
- **Type hints**: Full type annotations (np.ndarray, int)
- **Constants**: OFFSET_THRESHOLD_MS = 100ms for threshold management
- **Efficiency**: O(n) operations on arrays, O(1) for offset detection
- **Error handling**: Graceful defaults for edge cases

## Integration Points

- **Input format**: Accepts bar_times_ms from `waveform.get_beat_grid()`
- **Input format**: Accepts bar_energies from `bar_math.compute_bar_energies()`
- **Non-breaking**: All changes append to existing functions, no modifications to existing APIs
- **Ready for**: Phase 03-03 (beat grid validation & CLI integration)

## Threat Model

No new security concerns introduced:
- T-03-06 (Denial): O(n_bars) shift operation, acceptable (n_bars < 300 for any track)
- T-03-07 (Info): Offset values are non-sensitive timing data

## Verification Commands

```bash
# Run all tests
python -m pytest tests/test_bar_math.py -v

# Verify imports
python -c "from bar_math import detect_grid_offset, shift_bar_times, detect_intro_length"

# Count new functions
grep -c "^def detect\|^def shift" bar_math.py
```

## Files Modified

- `bar_math.py`: Added 3 new functions (~80 lines)
- `tests/test_bar_math.py`: Added 12 new test functions (~120 lines)

## Commit Hash

a8c4d03 feat(03-02): add grid offset detection and intro length auto-detection to bar_math

## Next Steps

1. Phase 03-03: Beat grid validation with alignment correction
2. Phase 03-04: CLI integration for grid offset auto-correction workflow
3. Performance testing on full DnB library (5-10% affected tracks)

---

**Status**: Ready for integration testing
