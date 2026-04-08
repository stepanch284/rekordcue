---
phase: 01-cli-proof-of-concept
plan: 01
subsystem: data-pipeline
tags: [pyrekordbox, anlz, pwav, pqtz, sqlite, onset-detection]
dependency_graph:
  requires: []
  provides: [db.py, waveform.py, detect.py]
  affects: [01-02]
tech_stack:
  added: []
  patterns:
    - pyrekordbox Rekordbox6Database() auto-locate pattern
    - PRAGMA table_info structural schema validation (user_version=0 workaround)
    - AnlzFile.parse_file + anlz.tag_types safe access (recursion bug workaround)
    - PWAV 400-sample fixed-width thumbnail index-to-time mapping
    - PQTZ beats==1 filter for bar start times in seconds
    - Per-bar mean energy threshold detection (mean + 0.5*stdev of non-silent bars)
key_files:
  created:
    - db.py
    - waveform.py
    - detect.py
  modified:
    - db.py  # bug fix: get_content(ID=) returns ORM object directly, not a Query
decisions:
  - get_content(ID=track_id) returns DjmdContent object directly — .first() must NOT be called
  - Threshold computed on non-silent bars only to avoid intro silence skewing the mean downward
  - detect_first_onset returns (time_seconds, bar_index) tuple per plan spec (not just time)
metrics:
  duration: ~20 minutes
  completed: 2026-04-08T20:23:00Z
  tasks_completed: 3
  tasks_total: 3
  files_created: 3
  files_modified: 1
requirements_fulfilled:
  - FOUND-01
  - FOUND-02
  - FOUND-05
  - FOUND-06
  - WAVE-01
  - WAVE-02
---

# Phase 1 Plan 1: DB + Waveform Read Pipeline Summary

**One-liner:** SQLCipher DB open, structural DjmdCue schema validation, ANLZ PWAV 400-sample + PQTZ beat-grid extraction, and per-bar energy onset detection — all verified against live Rekordbox 7.2.3 data.

---

## What Was Built

Three Python modules implementing the read-and-detect pipeline for RekordCue:

### `db.py`
- `open_database()`: Opens encrypted `master.db` via `Rekordbox6Database()` (auto-locates for RB7 and RB6 configs). Prints resolved `db_directory` path.
- `validate_schema()`: Executes `PRAGMA table_info(djmdCue)`, checks all 11 required columns are present, and confirms the legacy `Number` column is absent (RB7 schema guard). Returns `True` on success; raises `RuntimeError` with specific missing columns if validation fails.
- `get_track()`: Retrieves a `DjmdContent` ORM row by track ID string. Raises `ValueError` if not found. Prints track title, BPM (divided by 100), and length in seconds.

### `waveform.py`
- `get_pwav_amplitudes()`: Resolves the `.DAT` ANLZ path via `db.get_anlz_path(content, 'DAT')`, parses with `AnlzFile.parse_file()`, and extracts the PWAV tag's first array (400 float samples). Returns `(amplitudes, track_length_s)`.
- `get_beat_grid()`: Same path resolution, extracts PQTZ tag, filters `beats == 1` entries for bar starts. Returns `(bar_times_s, avg_bpm)` where times are in seconds.

Both functions use `anlz.tag_types` for presence checks — never `len(anlz)` or `anlz.keys()` per the pyrekordbox 0.4.4 recursion bug workaround.

### `detect.py`
- `detect_first_onset()`: Converts bar start times to PWAV indices, computes per-bar mean amplitude, sets threshold as `mean + 0.5 * stdev` of non-silent bars, finds first bar at index >= 4 exceeding the threshold. Returns `(onset_time_seconds, onset_bar_index)`. Falls back to bar 4 if no bar exceeds threshold.

---

## Verification Results (Live Rekordbox 7.2.3)

Test track: "Void (Gino Remix)" — 174.0 BPM, 239s

| Check | Result |
|-------|--------|
| `open_database()` | PASS — master.db at `C:\Users\stipecek\AppData\Roaming\Pioneer\rekordbox` |
| `validate_schema()` | PASS — 29 columns found, all 11 required present, Number absent |
| `get_pwav_amplitudes()` | PASS — 400 float samples returned |
| `get_beat_grid()` | PASS — 174 bars, 174.0 BPM, first bar at 0.043s |
| `detect_first_onset()` | PASS — bar 22, 30.388s (30388ms), threshold 24.233 |

---

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `db.get_content(ID=)` returns ORM object directly, not a Query**

- **Found during:** Task 2 verification
- **Issue:** `db.py` called `.first()` on the result of `db.get_content(ID=track_id)`. The plan's `<interfaces>` section describes this as returning a query (`db.get_content(ID=track_id)` — returns SQLAlchemy query; call `.first()` for single result), but live testing against pyrekordbox 0.4.4 revealed `get_content(ID=...)` returns the `DjmdContent` object directly. `get_content()` with no arguments returns a Query.
- **Fix:** Removed the `.first()` call in `get_track()`. The None check still works correctly since pyrekordbox returns `None` when no matching row is found.
- **Files modified:** `db.py` line 99
- **Commit:** `bec5e51`

### Threshold Improvement (Rule 2 — correctness)

- **Issue:** The RESEARCH.md pattern computed threshold from all bars including silent ones (common at track start), which could skew the mean downward and make the threshold too easy to exceed.
- **Fix:** Computed mean and stdev on `bar_energies[bar_energies > 0]` only (non-silent bars). Falls back to threshold 0.0 if all bars are silent (degenerate case).
- **Files modified:** `detect.py`

---

## Known Stubs

None. All three functions are fully implemented and verified against live data.

---

## Threat Flags

None. All surfaces are read-only in this plan. No new network endpoints, auth paths, or write operations introduced. Threat mitigations T-01-03 (parameterized ORM query) and T-01-04 (recursion bug workaround) are implemented as specified.

---

## Commits

| Hash | Message |
|------|---------|
| `b6b5cc4` | feat(01-01): add db.py — database open, schema validation, track lookup |
| `bec5e51` | feat(01-01): add waveform.py — ANLZ PWAV and PQTZ beat grid extraction |
| `d098016` | feat(01-01): add detect.py — energy onset detection from 400-sample PWAV array |
