# Phase 3: Beat Grid & Bar Math — Research

**Researched:** 2026-04-09
**Domain:** Beat grid extraction (PQTZ tag), 8-bar alignment math, BPM validation, energy-per-bar signal
**Confidence:** HIGH — all core findings verified against live master.db (Rekordbox 7.2.3) and live ANLZ files

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DETECT-01 | App reads beat grid to anchor timing at bar 0 | PQTZ tag in ANLZ .DAT file is the authoritative source; DjmdBeat does NOT exist in RB7 |
| DETECT-02 | Energy-per-bar from PWAV amplitude array | PWV3 (35956 samples at ~150/sec) gives 207 samples/bar at 174 BPM — far better than PWAV (400 total); use PWV3 from .EXT |
| DETECT-03 | Snap all detection positions to nearest 8-bar boundary | numpy argmin + round(idx/8)*8 pattern verified with real data |
| DETECT-08 | Validate BPM in DnB range 155–185, flag outliers | DjmdContent.BPM / 100 is the fast source; PQTZ bpms[0] is equivalent; half-tempo (87 BPM) confirmed flagged |
</phase_requirements>

---

## Summary

Phase 3 establishes the beat math foundation that all subsequent section detection and cue placement builds on. The central clarification is that **DjmdBeat does not exist in Rekordbox 7.2.3** — the ROADMAP success criterion wording is misleading. The PQTZ tag in the ANLZ .DAT file is the authoritative beat grid source, and Phase 1 already reads it correctly via `get_beat_grid()` in waveform.py. Phase 3 therefore does not require a new data source — it requires refining and exposing the PQTZ-derived data more cleanly.

The second key finding is that PWAV (400 fixed samples) is too coarse for energy-per-bar analysis. At 174 BPM, PWAV gives only about 2.3 samples per bar. The PWV3 tag in the .EXT file has ~35,956 samples (≈150 samples/sec) giving roughly 207 samples per bar — providing a meaningful signal. The energy-per-bar chart from PWV3 was verified against a live 174 BPM DnB track and clearly shows intro (low), drop (high), breakdown (low), second drop (high) with no ambiguity.

The 8-bar snap function is straightforward: find the nearest bar index via numpy argmin on the bar_times_ms array, round to the nearest multiple of 8, and clamp. BPM validation reads DjmdContent.BPM (stored as integer × 100) and checks whether BPM/100 falls within [155, 185].

**Primary recommendation:** Phase 3 adds three new functions to waveform.py or a new bar_math.py module: `get_bar_times_ms()`, `snap_to_8bar_boundary()`, `compute_bar_energies()`, and one guard function `validate_bpm_range()`. The existing `get_beat_grid()` is retained as-is; the new functions build on its output.

---

## Critical Finding: DjmdBeat Does Not Exist in Rekordbox 7.2.3

**VERIFIED against live master.db** — `SELECT * FROM DjmdBeat` raises `OperationalError: no such table: DjmdBeat`.

The complete table list for the live master.db was inspected. There is no `DjmdBeat` table. The ROADMAP success criterion "reads DjmdBeat" is based on older community documentation for Rekordbox 5/6 schema. Rekordbox 7 removed or renamed this table.

**The authoritative beat grid source in RB7 is the PQTZ tag in the ANLZ .DAT file**, which Phase 1 already reads correctly. `get_beat_grid()` in waveform.py returns `(bar_times_s, avg_bpm, all_beat_times_s)` — exactly what Phase 3 needs.

**Action for planner:** The DETECT-01 requirement ("reads DjmdBeat") must be implemented via PQTZ. No DB query for DjmdBeat should be written. The ROADMAP wording is a documentation artifact.

**Source:** `[VERIFIED: live master.db, Rekordbox 7.2.3, 2026-04-09]`

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pyrekordbox | 0.4.4 (installed) | AnlzFile.parse_file(), PQTZ/PWV3 tag access | Already in use; PQTZ.times/beats/bpms proven working |
| numpy | (installed) | Bar energy computation, argmin for snap | Array ops on 35k-sample waveform data |

No new libraries required for Phase 3.

**Source:** `[VERIFIED: existing codebase waveform.py, Phase 1]`

---

## Architecture Patterns

### Recommended Project Structure

Phase 3 adds to the existing flat module layout. Two options:

**Option A (preferred): Extend waveform.py**
Add `get_bar_times_ms()`, `compute_bar_energies()` alongside existing functions.
Keeps all ANLZ parsing in one module.

**Option B: New bar_math.py module**
Create `bar_math.py` with `snap_to_8bar_boundary()`, `validate_bpm_range()`, `compute_bar_energies()`.
Keeps pure math separate from file I/O.

**Recommendation:** Option B. Phase 4 (section detection) will import snap and energy functions heavily. A dedicated module with no file I/O dependencies is cleaner to test and import.

```
rekordcue/
  waveform.py       — ANLZ file I/O (get_beat_grid, get_pwav_amplitudes, get_pssi_sections)
  bar_math.py       — NEW: pure math on beat grid data (snap, energy, BPM check)
  detect.py         — Section detection (imports from bar_math)
  main.py           — CLI entry point
  db.py             — Database access
  writer.py         — Cue write pipeline
```

### Pattern 1: Beat Grid Extraction (Existing — No Change Needed)

`get_beat_grid()` in waveform.py already returns:
- `bar_times_s`: numpy array of bar-1 start times in seconds (from `pqtz.beats == 1` mask)
- `avg_bpm`: float from `pqtz.bpms[0]` — constant for DnB tracks
- `all_beat_times_s`: all beat times (needed for PSSI lookup)

```python
# Source: waveform.py (Phase 1, verified working)
bar_times_s, avg_bpm, all_beat_times_s = get_beat_grid(db, content)
bar_times_ms = bar_times_s * 1000.0   # convert to ms for cue writing
first_beat_ms = int(bar_times_ms[0])  # e.g., 43ms for this track
```

`[VERIFIED: live ANLZ file, PQTZ tag, Rekordbox 7.2.3]`

### Pattern 2: 8-Bar Boundary Snap

```python
# Source: verified with real data 2026-04-09
import numpy as np

def snap_to_8bar_boundary(position_ms: float, bar_times_ms: np.ndarray) -> tuple[int, int]:
    """Snap a raw position to the nearest 8-bar boundary.
    
    Args:
        position_ms:   Raw detection position in milliseconds.
        bar_times_ms:  Numpy array of bar start times in ms (from get_beat_grid).
    
    Returns:
        Tuple of (snapped_ms, bar_index) where bar_index is a multiple of 8.
    """
    diffs = np.abs(bar_times_ms - position_ms)
    nearest_bar_idx = int(np.argmin(diffs))
    eight_bar_idx = round(nearest_bar_idx / 8) * 8
    eight_bar_idx = min(max(eight_bar_idx, 0), len(bar_times_ms) - 1)
    return int(bar_times_ms[eight_bar_idx]), eight_bar_idx
```

**Verified behavior on live data:**
- Input 5000ms → bar #0 → 43ms (snaps backward to track start, correct)
- Input 22112ms → bar #16 → 22112ms (exactly on grid, zero drift)
- Input 25000ms → bar #16 → 22112ms (snaps to nearest 8-bar)
- Input 30000ms → bar #24 → 33147ms (snaps forward)

`[VERIFIED: live ANLZ, 174 BPM track, 2026-04-09]`

### Pattern 3: BPM Range Validation

```python
# Source: verified with live DjmdContent data 2026-04-09
DNB_BPM_MIN = 155.0
DNB_BPM_MAX = 185.0

def validate_bpm_range(content) -> tuple[float, bool]:
    """Check BPM is in DnB range. 
    
    Args:
        content: DjmdContent ORM row
    
    Returns:
        Tuple of (bpm_float, is_valid) where is_valid is True if in [155, 185].
    """
    bpm = content.BPM / 100.0  # stored as integer * 100 in DB
    is_valid = DNB_BPM_MIN <= bpm <= DNB_BPM_MAX
    return bpm, is_valid
```

**Why use DjmdContent.BPM rather than PQTZ bpms[0]:**
- DjmdContent.BPM is already available from the existing `get_track()` call — no extra ANLZ parse needed
- For all tested tracks, DjmdContent.BPM == PQTZ bpms[0] (they match exactly)
- The user sees DjmdContent.BPM in Rekordbox UI — using the same value means the warning is consistent with what the user observes

**Half-tempo confirmation:** Track "Where's Your Head At (1991 Remix)" has BPM=8700 (87.00 BPM) — visibly outside the DnB range. The validation flags it correctly. The flag message should say "likely mis-detected BPM — expected 155–185 for DnB" so the user can fix it in Rekordbox before re-running.

`[VERIFIED: live DjmdContent, Rekordbox 7.2.3, 2026-04-09]`

### Pattern 4: Energy-Per-Bar Computation

**CRITICAL: Use PWV3 from .EXT, not PWAV from .DAT**

PWAV has only 400 samples total. At 174 BPM, a 239-second track has ~174 bars. That's 400/174 ≈ 2.3 samples per bar — too coarse for meaningful per-bar energy.

PWV3 from the .EXT file has ~35,956 samples for a 239-second track = 150.4 samples/second. At 174 BPM (1.38s bar interval), that's 207 samples per bar — fully adequate.

```python
# Source: verified with live data 2026-04-09
import numpy as np
from pyrekordbox import AnlzFile
from pathlib import Path

def compute_bar_energies(db, content, bar_times_s: np.ndarray) -> np.ndarray:
    """Compute mean energy for each bar using PWV3 from the .EXT file.
    
    Falls back to PWAV from .DAT if EXT/PWV3 is unavailable.
    
    Args:
        db:           Open Rekordbox6Database instance.
        content:      DjmdContent ORM row.
        bar_times_s:  Bar start times in seconds from get_beat_grid().
    
    Returns:
        Numpy float64 array of shape (n_bars,), values in [0, 31].
    
    Raises:
        ValueError: If neither PWV3 nor PWAV is available.
    """
    track_len_s = float(content.Length)
    
    # Try PWV3 first (high resolution: ~150 samples/sec)
    ext_path = db.get_anlz_path(content, 'EXT')
    if ext_path and Path(ext_path).exists():
        try:
            anlz_ext = AnlzFile.parse_file(ext_path)
            if 'PWV3' in anlz_ext.tag_types:
                pwv3 = anlz_ext.get_tag('PWV3')
                amp = pwv3.get()[0].astype(float)  # shape: (N,)
                return _bars_from_amplitude(amp, bar_times_s, track_len_s)
        except Exception:
            pass  # fall through to PWAV
    
    # Fallback: PWAV (400 samples — coarse, but available)
    dat_path = db.get_anlz_path(content, 'DAT')
    if dat_path and Path(dat_path).exists():
        anlz = AnlzFile.parse_file(dat_path)
        if 'PWAV' in anlz.tag_types:
            amp = anlz.get_tag('PWAV').get()[0].astype(float)
            return _bars_from_amplitude(amp, bar_times_s, track_len_s)
    
    raise ValueError(f"No waveform data available for track {content.ID}")


def _bars_from_amplitude(amp: np.ndarray, bar_times_s: np.ndarray, 
                          track_len_s: float) -> np.ndarray:
    """Compute mean amplitude per bar window."""
    n = len(amp)
    energies = np.zeros(len(bar_times_s))
    for i in range(len(bar_times_s)):
        idx_start = int(bar_times_s[i] / track_len_s * n)
        idx_end = int(bar_times_s[i+1] / track_len_s * n) if i + 1 < len(bar_times_s) else n
        window = amp[idx_start:idx_end]
        energies[i] = float(np.mean(window)) if len(window) > 0 else 0.0
    return energies
```

**Verified output for "Void (Gino Remix)" at 174 BPM:**
```
Bars   0-  7 (0s):    5.4  (intro — low energy, correct)
Bars   8- 15 (11s):   4.4  (intro — low energy, correct)
Bars  16- 23 (22s):  23.9  (first drop — high energy, correct)
...
Bars 104-111 (143s):  8.3  (breakdown — energy valley, correct)
Bars 112-119 (155s): 21.5  (second drop — energy recovery, correct)
```

The signal clearly separates intro/drop/breakdown/drop2 — exactly what Phase 4 needs.

`[VERIFIED: live track "Void (Gino Remix)", PWV3 tag, 2026-04-09]`

### Anti-Patterns to Avoid

- **Do not use PWAV for per-bar energy**: 400 total samples is ~2.3 samples/bar at 174 BPM — noise, not signal. Use PWV3.
- **Do not query DjmdBeat**: Table does not exist in RB7. Any code that does `SELECT * FROM DjmdBeat` will raise OperationalError.
- **Do not reopen the ANLZ .DAT file in bar_math.py**: `get_beat_grid()` already returns bar_times_s; pass it as a parameter rather than re-parsing.
- **Do not use Python `round()` alone for snapping**: `round(nearest_bar_idx / 8) * 8` — the divide is float division, round() gives the right banker's rounding, but the result must be cast back to `int` and clamped before array indexing.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Beat-level timing | Custom beat detector from PWAV | PQTZ tag via pyrekordbox | Rekordbox already computed per-beat precise times; re-detecting is error-prone |
| Waveform parsing | Manual binary struct unpacking of PWV3 | `AnlzFile.parse_file()` + `.get_tag('PWV3').get()` | pyrekordbox handles endianness, tag length variations |
| BPM detection | Audio-based BPM analysis | DjmdContent.BPM | Already computed, stored, displayed in Rekordbox UI — no benefit to re-detecting |

---

## Common Pitfalls

### Pitfall 1: ROADMAP Says "DjmdBeat" — Table Does Not Exist

**What goes wrong:** Code written to `SELECT * FROM DjmdBeat` crashes with `OperationalError: no such table: DjmdBeat`.

**Why it happens:** The ROADMAP/ARCHITECTURE docs were written based on older community documentation covering Rekordbox 5/6 schema where DjmdBeat existed. Rekordbox 7 removed this table.

**How to avoid:** Use PQTZ from ANLZ .DAT (already working in Phase 1). The equivalent data is `pqtz.times[pqtz.beats == 1]` for bar starts and `pqtz.bpms[0]` for BPM.

**Confidence:** `[VERIFIED: live master.db 2026-04-09]`

---

### Pitfall 2: PWAV Resolution is Too Coarse for Per-Bar Energy

**What goes wrong:** Using PWAV (400 samples) for energy-per-bar computation produces ~2-3 samples per bar at 174 BPM. Most bars get the exact same energy value (integer mean of 2 samples). The signal is too quantized to detect structure.

**Why it happens:** PWAV is designed as a visual thumbnail overview (400px wide), not as a signal processing source.

**How to avoid:** Use PWV3 from the .EXT file (~150 samples/sec → 207 samples/bar at 174 BPM). Fall back to PWAV only if EXT/PWV3 is unavailable.

**Warning signs:** If bar_energies array has many identical consecutive values (e.g., 5.5, 7.0, 7.0) — that's the PWAV quantization artifact.

`[VERIFIED: measured 2.3 samples/bar from PWAV vs 207 samples/bar from PWV3 on live track]`

---

### Pitfall 3: pyrekordbox 0.4.4 Bug — Never Call len(anlz) or anlz.keys()

**What goes wrong:** Calling `len(anlz)` or `anlz.keys()` on an AnlzFile object triggers infinite recursion in pyrekordbox 0.4.4.

**How to avoid:** Always use `anlz.tag_types` (the property) to check for tag presence. This is already documented in waveform.py header and implemented correctly.

```python
# CORRECT
if 'PWV3' in anlz.tag_types:
    ...

# WRONG — infinite recursion
if 'PWV3' in anlz:  # calls __contains__ -> __len__ -> infinite loop
    ...
```

`[VERIFIED: waveform.py comment, confirmed Phase 1]`

---

### Pitfall 4: 8-Bar Snap at Track Boundaries

**What goes wrong:** `round(nearest_bar_idx / 8) * 8` can produce an index larger than `len(bar_times_ms) - 1` for positions near the end of the track. Unclamped indexing causes IndexError.

**How to avoid:** Always clamp: `eight_bar_idx = min(max(eight_bar_idx, 0), len(bar_times_ms) - 1)`.

---

### Pitfall 5: Half-Tempo Tracks — BPM Check Is Pre-Processing, Not Post

**What goes wrong:** Running energy-per-bar analysis on a half-tempo track (e.g., 87 BPM instead of 174) produces bar windows that are twice as long as expected. Section detection in Phase 4 will get the wrong boundaries. The track must be flagged BEFORE bar math is applied.

**How to avoid:** Run `validate_bpm_range()` immediately after `get_beat_grid()`, before any bar energy computation. If flagged, log a warning and skip further analysis for that track.

`[VERIFIED: BPM=8700 track in live library, 2026-04-09]`

---

### Pitfall 6: PQT2 (in .EXT) is NOT a Full Beat Grid

**What goes wrong:** The .EXT file contains a `PQT2` tag that looks like a beat grid but only has 2 entries (start anchor + end anchor). Using PQT2 instead of PQTZ gives you only 2 "bar" positions, not the full bar list.

**How to avoid:** Always use PQTZ from the .DAT file (696 entries for a 239-second track). PQT2 is the anchor-only representation, not the full sequence.

`[VERIFIED: PQT2 has 2 entries, PQTZ has 696 entries, same track, 2026-04-09]`

---

## Code Examples

### Complete bar_math.py Module Skeleton

```python
"""
bar_math.py — Beat grid math for RekordCue.

Pure functions operating on beat grid arrays from waveform.get_beat_grid().
No file I/O here — all ANLZ parsing stays in waveform.py.
"""

import numpy as np
from pathlib import Path
from pyrekordbox import AnlzFile

DNB_BPM_MIN = 155.0
DNB_BPM_MAX = 185.0


def validate_bpm_range(content) -> tuple:
    """Check BPM is in DnB range [155, 185].
    
    Args:
        content: DjmdContent ORM row (BPM stored as integer * 100).
    
    Returns:
        (bpm_float, is_valid): bpm_float is BPM as float, is_valid is True if in range.
    """
    bpm = content.BPM / 100.0
    return bpm, DNB_BPM_MIN <= bpm <= DNB_BPM_MAX


def snap_to_8bar_boundary(position_ms: float, bar_times_ms: np.ndarray) -> tuple:
    """Snap a raw position in ms to the nearest 8-bar boundary.
    
    Args:
        position_ms:   Raw detection position in milliseconds.
        bar_times_ms:  Bar start times in ms (bar_times_s * 1000 from get_beat_grid).
    
    Returns:
        (snapped_ms, bar_index) where bar_index is a multiple of 8.
    """
    diffs = np.abs(bar_times_ms - position_ms)
    nearest_bar_idx = int(np.argmin(diffs))
    eight_bar_idx = round(nearest_bar_idx / 8) * 8
    eight_bar_idx = min(max(eight_bar_idx, 0), len(bar_times_ms) - 1)
    return int(bar_times_ms[eight_bar_idx]), eight_bar_idx


def compute_bar_energies(db, content, bar_times_s: np.ndarray) -> np.ndarray:
    """Compute mean amplitude per bar using PWV3 (preferred) or PWAV (fallback).
    
    PWV3 from .EXT: ~150 samples/sec → 207 samples/bar at 174 BPM (good signal).
    PWAV from .DAT: 400 total samples → ~2 samples/bar at 174 BPM (very coarse).
    
    Returns:
        Float64 array of shape (n_bars,), values in [0, 31].
    """
    track_len_s = float(content.Length)

    ext_path = db.get_anlz_path(content, 'EXT')
    if ext_path and Path(ext_path).exists():
        try:
            anlz_ext = AnlzFile.parse_file(ext_path)
            if 'PWV3' in anlz_ext.tag_types:
                amp = anlz_ext.get_tag('PWV3').get()[0].astype(float)
                return _bars_from_amplitude(amp, bar_times_s, track_len_s)
        except Exception:
            pass

    dat_path = db.get_anlz_path(content, 'DAT')
    if dat_path and Path(dat_path).exists():
        anlz = AnlzFile.parse_file(dat_path)
        if 'PWAV' in anlz.tag_types:
            amp = anlz.get_tag('PWAV').get()[0].astype(float)
            return _bars_from_amplitude(amp, bar_times_s, track_len_s)

    raise ValueError(f"No waveform data available for track {content.ID}")


def _bars_from_amplitude(amp: np.ndarray, bar_times_s: np.ndarray,
                          track_len_s: float) -> np.ndarray:
    n = len(amp)
    energies = np.zeros(len(bar_times_s))
    for i in range(len(bar_times_s)):
        idx_start = int(bar_times_s[i] / track_len_s * n)
        idx_end = int(bar_times_s[i + 1] / track_len_s * n) if i + 1 < len(bar_times_s) else n
        window = amp[idx_start:idx_end]
        energies[i] = float(np.mean(window)) if len(window) > 0 else 0.0
    return energies
```

### Integration in main.py

```python
# After get_beat_grid():
bar_times_s, avg_bpm, all_beat_times_s = get_beat_grid(db, content)
bar_times_ms = bar_times_s * 1000.0

# 1. BPM range check (BEFORE any bar math)
bpm, bpm_ok = validate_bpm_range(content)
if not bpm_ok:
    print(f"WARNING: BPM {bpm:.1f} is outside DnB range {DNB_BPM_MIN}–{DNB_BPM_MAX}. "
          f"Likely mis-detected BPM. Fix in Rekordbox before placing cues.")
    # Depending on policy: sys.exit(0) or continue with warning

# 2. Compute bar energies (for Phase 4 detection)
bar_energies = compute_bar_energies(db, content, bar_times_s)

# 3. Snap a detection result to 8-bar boundary
raw_drop1_ms = sections["drop1_s"] * 1000.0
snapped_ms, bar_idx = snap_to_8bar_boundary(raw_drop1_ms, bar_times_ms)
```

---

## State of the Art

| Old Approach | Current Approach | Status |
|--------------|------------------|--------|
| DjmdBeat SQL query | PQTZ tag in ANLZ .DAT | DjmdBeat is absent in RB7; PQTZ is the only source |
| PWAV for energy analysis | PWV3 from .EXT | PWAV is a thumbnail (400px); PWV3 is full-resolution |

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.12 | Runtime | Yes | 3.12.x | — |
| pyrekordbox | PQTZ/PWV3 parsing | Yes | 0.4.4 | — |
| numpy | Bar energy array ops | Yes | installed | — |
| Rekordbox ANLZ .EXT files | PWV3 energy source | Yes | present for analyzed tracks | Fall back to PWAV (coarse) |
| DjmdBeat table | DETECT-01 (per ROADMAP) | NO | N/A | PQTZ tag (equivalent, better) |

**Missing dependencies with no fallback:** None — DjmdBeat is absent but PQTZ is a complete replacement.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (standard for this project) |
| Config file | none detected — add pytest.ini or pyproject.toml [tool.pytest.ini_options] in Wave 0 |
| Quick run command | `python -m pytest tests/test_bar_math.py -x` |
| Full suite command | `python -m pytest tests/ -x` |

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DETECT-01 | get_beat_grid() returns bar_times_s matching PQTZ | unit | `pytest tests/test_bar_math.py::test_beat_grid_extraction -x` | No — Wave 0 |
| DETECT-02 | compute_bar_energies() produces non-uniform signal for structured DnB track | unit | `pytest tests/test_bar_math.py::test_bar_energies_signal -x` | No — Wave 0 |
| DETECT-03 | snap_to_8bar_boundary() snaps to multiples of 8 | unit | `pytest tests/test_bar_math.py::test_8bar_snap -x` | No — Wave 0 |
| DETECT-08 | validate_bpm_range() returns False for 87 BPM, True for 174 BPM | unit | `pytest tests/test_bar_math.py::test_bpm_validation -x` | No — Wave 0 |

### Sampling Rate

- **Per task commit:** `python -m pytest tests/test_bar_math.py -x`
- **Per wave merge:** `python -m pytest tests/ -x`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/test_bar_math.py` — covers DETECT-01, DETECT-02, DETECT-03, DETECT-08
- [ ] `tests/conftest.py` — shared fixture loading a real ANLZ file (or providing fixture data from a real track)
- [ ] `bar_math.py` — new module (does not exist yet)

**Note on test fixtures:** The test for DETECT-02 requires either a real ANLZ .EXT file (PWV3 present) or a synthetic one. The simplest approach is to use the live ANLZ file from the known track "Void (Gino Remix)" (ID=72163764) in tests — it's always present on the dev machine. This is an integration-style unit test, not a pure unit test.

---

## Security Domain

This phase performs no writes, handles no user authentication, and processes only local ANLZ binary files already under pyrekordbox's read path. No new attack surface is introduced.

ASVS V5 (Input Validation) applies minimally: the BPM value from DjmdContent is an integer from a trusted local database. No external user input enters bar_math.py functions. The only validation needed is the existing `ValueError` raising for missing waveform data.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | DjmdContent.BPM == PQTZ bpms[0] for all tracks (verified on 2 tracks) | Pattern 3 | If they diverge on some track, BPM check would use DB value while bar grid uses PQTZ value — minor inconsistency, low impact |
| A2 | content.Length (in seconds) is accurate enough for PWAV/PWV3 index mapping | Pattern 4 | Off-by-one on last bar only; functionally irrelevant |
| A3 | PWV3 tag is present in .EXT for all analyzed tracks | Pattern 4 | If absent, falls back to PWAV — observed all 2 tested tracks have PWV3 |

---

## Open Questions

1. **Should BPM-out-of-range tracks be hard-blocked (exit) or soft-warned (continue)?**
   - What we know: DETECT-08 says "flagged with a visible warning before any cue is written"
   - What's unclear: Does "before any cue is written" mean block the whole run, or just print and continue?
   - Recommendation: Soft-warn by default (print warning, continue). Hard-block can be added as a CLI flag. Phase 3 implements the check; blocking behavior is a policy for Phase 5/6.

2. **Should compute_bar_energies() be exposed in waveform.py or bar_math.py?**
   - What we know: It requires ANLZ file I/O (db.get_anlz_path, AnlzFile.parse_file)
   - What's unclear: Whether to keep all ANLZ I/O in waveform.py or split by concern
   - Recommendation: Keep in bar_math.py since it's called as part of the analysis pipeline, not parsing. Accept the import of AnlzFile in bar_math.py.

---

## Sources

### Primary (HIGH confidence)
- Live master.db, Rekordbox 7.2.3 — DjmdBeat absence confirmed, DjmdContent.BPM encoding verified
- Live ANLZ .DAT files, PQTZ tag — beat times, bar mask, BPM values confirmed
- Live ANLZ .EXT files, PWV3 tag — 35,956 samples / 239s = 150.4 samples/sec confirmed
- Existing waveform.py (Phase 1) — get_beat_grid() returns correct bar_times_s

### Secondary (MEDIUM confidence)
- ARCHITECTURE.md (project research) — DjmdBeat schema documentation (now superseded by live verification)
- STACK.md (project research) — PWAV 150 samples/sec claim (VERIFIED: PWV3 matches this; PWAV is 400 total not per-second)

### Tertiary (LOW confidence)
- None — all core claims for this phase were verified against live data.

---

## Metadata

**Confidence breakdown:**
- DjmdBeat absence: HIGH — verified directly against live DB
- PQTZ as beat grid source: HIGH — verified, already working in Phase 1
- PWV3 resolution (~150 samples/sec): HIGH — measured from live .EXT file
- 8-bar snap algorithm: HIGH — tested with live bar_times_ms array
- BPM range validation logic: HIGH — tested with 174 BPM and 87 BPM tracks

**Research date:** 2026-04-09
**Valid until:** 2026-07-09 (stable — tied to pyrekordbox 0.4.4 and Rekordbox 7.2.3; update if either version changes)
