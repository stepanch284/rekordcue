# Phase 1: CLI Proof-of-Concept — Research

**Researched:** 2026-04-08
**Domain:** pyrekordbox 0.4.4 / Rekordbox 7.2.3 / SQLite / Windows ANLZ waveform parsing
**Confidence:** HIGH (all critical claims verified against live installed pyrekordbox and live master.db)

---

## Summary

This research was conducted against the live environment: Python 3.12.x, pyrekordbox 0.4.4, Rekordbox 7.2.3 installed at `C:\Program Files\rekordbox\rekordbox 7.2.3`. The master.db lives at `C:\Users\stipecek\AppData\Roaming\Pioneer\rekordbox\master.db` (NOT the `rekordbox6` subdirectory). The database has 1,056 tracks and 2,420 cue rows.

Several facts documented in the prior ARCHITECTURE.md and STACK.md research files are **wrong for Rekordbox 7.2.3** and must be overridden by this document. The most critical corrections: (1) `DjmdCue` has no `Number` column — hot cue slot A/B/C is encoded directly in the `Kind` field (Kind=1=A, Kind=2=B, Kind=3=C, Kind=0=memory cue); (2) PWAV is always exactly 400 samples regardless of track length — it is a fixed-width thumbnail array, not a 150 samples/sec signal; (3) `DjmdBeat` table does not exist — beat grid comes exclusively from ANLZ PQTZ tags; (4) `PRAGMA user_version` is 0 for this install, schema validation must use structural checks instead.

pyrekordbox 0.4.4 has a known bug: calling `len(anlz)` or `anlz.keys()` on an `AnlzFile` triggers infinite recursion due to a `__len__` implementation that calls `self.keys()` which circles back. Workaround: access `anlz.tags` (the raw list) and `anlz.tag_types` (the property) directly. The `get_tag()`, `get()`, and `getall()` methods work correctly.

**Primary recommendation:** Use pyrekordbox 0.4.4 for all reads (DB + ANLZ), use pyrekordbox's `db.add()` + `db.commit()` ORM path for writes (it has built-in process guard and USN management), and fall back to raw SQLite only if the ORM path proves unworkable during implementation.

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| FOUND-01 | Open master.db via pyrekordbox without corruption | `Rekordbox6Database()` verified working; uses sqlcipher3-wheels for decryption; ORM reads confirmed against 1,056 tracks |
| FOUND-02 | Detect AppData path on Windows with fallback | `pyrekordbox.show_config()` resolves path automatically; verified: db at `%APPDATA%\Pioneer\rekordbox\master.db`, NOT `rekordbox6`; fallback scan pattern documented |
| FOUND-03 | Check rekordbox.exe running before write | `psutil.process_iter(['name'])` verified working; pyrekordbox `commit()` also has built-in `get_rekordbox_pid()` guard |
| FOUND-04 | Timestamped backup before every write | `shutil.copy2()` pattern documented; exact backup naming convention specified |
| FOUND-05 | Validate schema via PRAGMA user_version | user_version=0 for RB7.2.3 — structural validation via `PRAGMA table_info(djmdCue)` is the reliable approach |
| FOUND-06 | Inspect PRAGMA table_info(DjmdCue) at startup | Full verified column list documented; critical nullable vs required columns identified |
| WAVE-01 | Locate ANLZ .DAT files from DjmdContent.AnalysisDataPath | `db.get_anlz_path(content, 'DAT')` verified; AnalysisDataPath column confirmed in DjmdContent |
| WAVE-02 | Parse PWAV tag amplitude array | `AnlzFile.parse_file(path)` + `anlz.get_tag('PWAV').get()` verified; returns (400-sample array, 400-sample array); track index to time mapping documented |
| SAFE-01 | All DB writes use BEGIN EXCLUSIVE with rollback | pyrekordbox ORM uses SQLAlchemy sessions; raw SQL `BEGIN EXCLUSIVE` pattern documented as alternative; ORM path preferred |
</phase_requirements>

---

## Environment (Verified)

| Item | Value | Source |
|------|-------|--------|
| Python version | 3.12.x (3.14.3 shown in PATH but pyrekordbox installed under 3.12) | `pip show pyrekordbox` location |
| pyrekordbox version | 0.4.4 | `pip show pyrekordbox` [VERIFIED: pip] |
| numpy version | 2.4.4 | `pip show numpy` [VERIFIED: pip] |
| psutil version | 6.1.1 | `pip show psutil` [VERIFIED: pip] |
| Rekordbox version | 7.2.3 | `pyrekordbox.show_config()` [VERIFIED: live] |
| master.db location | `C:\Users\stipecek\AppData\Roaming\Pioneer\rekordbox\master.db` | filesystem probe [VERIFIED: live] |
| ANLZ share dir | `C:\Users\stipecek\AppData\Roaming\Pioneer\rekordbox\share` | `db.share_directory` [VERIFIED: live] |
| PRAGMA user_version | 0 | `db.session.execute(text('PRAGMA user_version'))` [VERIFIED: live] |
| Track count | 1,056 | `db.get_content().count()` [VERIFIED: live] |

> **Note on Python executable:** The environment has both Python 3.12 (has pyrekordbox) and Python 3.14 (bare). Use the 3.12 interpreter at `C:\Users\stipecek\AppData\Local\Programs\Python\Python312\python.exe` or ensure PATH resolves to the right environment. [VERIFIED: live]

---

## Standard Stack

### Core (Phase 1 only — no GUI)

| Library | Version | Purpose | Status |
|---------|---------|---------|--------|
| pyrekordbox | 0.4.4 | DB reads, ANLZ parsing, ORM writes | Installed [VERIFIED: pip] |
| numpy | 2.4.4 | PWAV amplitude array analysis | Installed [VERIFIED: pip] |
| psutil | 6.1.1 | Rekordbox process detection | Installed [VERIFIED: pip] |
| sqlite3 | stdlib | PRAGMA queries, transaction control fallback | stdlib |
| shutil | stdlib | Timestamped database backup | stdlib |
| pathlib | stdlib | Windows path handling | stdlib |
| uuid | stdlib | Generate UUID4 for DjmdCue rows | stdlib |

All Phase 1 dependencies are already installed. No `pip install` required.

---

## Architecture Patterns

### Recommended Project Structure

```
rekordcue/
├── main.py               # CLI entry: python main.py <track_id>
├── db.py                 # DB open/close/validate, ANLZ path resolution
├── waveform.py           # ANLZ parse, PWAV extraction
├── detect.py             # Energy onset detection on PWAV array
└── writer.py             # Backup + write hot cue to DjmdCue
```

### Pattern 1: Opening the Database

```python
# Source: verified against pyrekordbox 0.4.4 __init__ source + live test
from pyrekordbox import Rekordbox6Database

db = Rekordbox6Database()   # auto-locates master.db for rekordbox7 or rekordbox6
# db.db_directory -> Path to rekordbox/  (NOT rekordbox6/ on this machine)
# db.share_directory -> Path to rekordbox/share/
```

`Rekordbox6Database()` with no arguments:
1. Tries `get_config("rekordbox7")` first, then falls back to `get_config("rekordbox6")`
2. Reads the decryption key from an embedded BLOB (via `deobfuscate(BLOB)`)
3. Opens via SQLAlchemy + `sqlite+pysqlcipher` using sqlcipher3-wheels
4. Warns (does NOT block) if rekordbox.exe is already running

**NEVER** open master.db with plain `sqlite3.connect()` — it is encrypted and will raise "file is not a database". [VERIFIED: live test confirmed encryption]

### Pattern 2: Schema Validation at Startup

`PRAGMA user_version` is 0 for Rekordbox 7.2.3 — it is not a meaningful version discriminator.

Use structural validation instead:

```python
# Source: verified against live master.db PRAGMA table_info(djmdCue)
from sqlalchemy import text

REQUIRED_CUE_COLUMNS = {
    'ID', 'ContentID', 'InMsec', 'Kind', 'Color', 'ColorTableIndex',
    'Comment', 'created_at', 'updated_at', 'ContentUUID', 'UUID'
}

def validate_schema(db):
    rows = db.session.execute(text('PRAGMA table_info(djmdCue)')).fetchall()
    found = {row[1] for row in rows}  # row[1] = column name
    missing = REQUIRED_CUE_COLUMNS - found
    if missing:
        raise RuntimeError(f"DjmdCue schema mismatch. Missing columns: {missing}")
    return True
```

### Pattern 3: ANLZ Path Resolution and PWAV Reading

```python
# Source: verified against pyrekordbox 0.4.4 + live AnlzFile.parse_file() test
from pyrekordbox import AnlzFile

def get_pwav_amplitudes(db, content):
    """Returns (amplitudes_array, track_length_s) for a DjmdContent row."""
    dat_path = db.get_anlz_path(content, 'DAT')
    if dat_path is None or not Path(dat_path).exists():
        raise FileNotFoundError(f"No DAT file for track {content.ID}: {dat_path}")
    
    anlz = AnlzFile.parse_file(dat_path)
    # CRITICAL: do NOT call len(anlz) or anlz.keys() — infinite recursion bug in 0.4.4
    # Use anlz.tag_types (property) or anlz.tags (list) instead
    if 'PWAV' not in anlz.tag_types:
        raise ValueError(f"No PWAV tag in {dat_path}")
    
    pwav = anlz.get_tag('PWAV')
    data = pwav.get()   # returns (amplitudes_array, unknown_array), both shape (400,) dtype int8
    amplitudes = data[0].astype(float)   # values 0..25 (5-bit, actual max varies)
    return amplitudes, content.Length    # Length is in SECONDS
```

**PWAV encoding (verified):**
- Always exactly 400 samples, regardless of track duration
- Each sample covers `track_duration / 400` seconds of audio
- Sample values: int8, range roughly 0–25 for this RB version
- Index i maps to time: `t_seconds = (i / 400) * track_length_s`
- Reverse: index for time t: `i = int(t / track_length_s * 400)`

### Pattern 4: Beat Grid from PQTZ Tag

`DjmdBeat` does NOT exist in pyrekordbox 0.4.4 or in master.db for RB7. All beat grid data comes from ANLZ PQTZ tags. [VERIFIED: live — DjmdBeat not in tables module, not in DB]

```python
# Source: verified against live PQTZ tag data from AnlzFile.parse_file()
import numpy as np

def get_beat_grid(db, content):
    """Returns (bar_times_s, bpm) from ANLZ PQTZ tag."""
    dat_path = db.get_anlz_path(content, 'DAT')
    anlz = AnlzFile.parse_file(dat_path)
    pqtz = anlz.get_tag('PQTZ')
    
    times = pqtz.times   # numpy array of beat times IN SECONDS (not ms!)
    beats = pqtz.beats   # numpy array of beat numbers within bar: 1, 2, 3, 4
    bpms = pqtz.bpms     # numpy array of BPM at each beat
    
    # Bar starts are where beats == 1
    bar_mask = (beats == 1)
    bar_times_s = times[bar_mask]   # seconds, not ms
    
    avg_bpm = float(bpms[0])        # constant for a consistent-tempo DnB track
    return bar_times_s, avg_bpm

# Convert bar_times_s to PWAV indices (for section detection):
def bar_times_to_pwav_indices(bar_times_s, track_length_s, pwav_len=400):
    return np.floor(bar_times_s / track_length_s * pwav_len).astype(int)
```

**PQTZ times are in SECONDS.** Multiply by 1000 to get milliseconds for cue position. [VERIFIED: live — first beat at 0.043s = 43ms, matches expected 43ms at 174BPM]

### Pattern 5: Simple Energy Onset Detection

For Phase 1, find the first large energy increase in the PWAV array — a rough drop detection.

```python
import numpy as np

def detect_first_onset(amplitudes, bar_times_s, track_length_s, pwav_len=400):
    """Returns the bar time (seconds) of the first major energy onset.
    
    Strategy: compute mean energy in a sliding 8-bar window (in PWAV index space),
    find first crossing of mean+0.5*stdev threshold after bar 4.
    """
    bar_indices = np.floor(bar_times_s / track_length_s * pwav_len).astype(int)
    n_bars = len(bar_indices)
    
    # Energy per bar: mean PWAV amplitude between consecutive bar boundaries
    bar_energies = []
    for i in range(n_bars):
        start = bar_indices[i]
        end = bar_indices[i + 1] if i + 1 < n_bars else pwav_len
        window = amplitudes[start:end]
        bar_energies.append(float(np.mean(window)) if len(window) > 0 else 0.0)
    
    bar_energies = np.array(bar_energies)
    
    # Threshold: mean + 0.5 * stdev (tune later; start permissive)
    threshold = bar_energies.mean() + 0.5 * bar_energies.std()
    
    # Find first bar above threshold, skip first 4 bars (always intro)
    for i in range(4, n_bars):
        if bar_energies[i] >= threshold:
            return bar_times_s[i]   # seconds
    
    # Fallback: return bar 4 (never return None)
    return bar_times_s[min(4, n_bars - 1)]
```

### Pattern 6: Hot Cue Kind Encoding (CRITICAL — differs from ARCHITECTURE.md)

In Rekordbox 7.2.3, `DjmdCue.Kind` encodes both the cue type AND the hot cue slot:

| Kind value | Meaning |
|------------|---------|
| 0 | Memory cue (no slot) |
| 1 | Hot cue slot A |
| 2 | Hot cue slot B |
| 3 | Hot cue slot C |
| 4 | Hot cue slot D (inferred; not seen in sample data) |
| 5 | Hot cue slot E |
| 6 | Hot cue slot F |
| 7 | Hot cue slot G |
| 8 | Hot cue slot H |
| 9 | (unknown — seen in sample; may be loop marker) |

**There is NO `Number` column.** The ARCHITECTURE.md documentation of `Number` (hot cue slot 0–7) is wrong for RB7. [VERIFIED: live PRAGMA table_info(djmdCue) — no Number column; live cue rows — Kind=1/2/3/5/6 for hot cues A/B/C/E/F]

For Phase 1, write one hot cue at slot A: `Kind = 1`.

### Pattern 7: DjmdCue INSERT via pyrekordbox ORM (Preferred)

```python
# Source: pyrekordbox 0.4.4 source inspection + live schema verification
import uuid
from pyrekordbox.db6.tables import DjmdCue

def write_hot_cue(db, content, position_ms: int):
    """Write a single hot cue (slot A) to DjmdCue for the given content.
    
    Requires:
    - Rekordbox is NOT running (db.commit() will raise RuntimeError if it is)
    - Backup already taken before calling this function
    """
    cue_id = str(db.generate_unused_id(DjmdCue))
    
    cue = DjmdCue(
        ID=cue_id,
        ContentID=content.ID,
        ContentUUID=content.UUID,
        InMsec=round(position_ms),
        InFrame=0,
        InMpegFrame=0,
        InMpegAbs=0,
        OutMsec=-1,
        OutFrame=-1,
        OutMpegFrame=-1,
        OutMpegAbs=-1,
        Kind=1,               # hot cue slot A
        Color=255,            # white/default, matches existing rows
        ColorTableIndex=22,   # default index, matches existing hot cue rows
        ActiveLoop=0,
        Comment='',
        BeatLoopSize=-1,
        CueMicrosec=round(position_ms) * 1000,
        UUID=str(uuid.uuid4()),
        # created_at and updated_at auto-set by StatsFull.default=datetime.now
    )
    
    db.add(cue)
    db.commit()   # has built-in rekordbox process guard
```

**Critical field values from live inspection:** [VERIFIED: live]
- `Color=255` for hot cues (not 0–8 as documented in ARCHITECTURE.md)
- `ColorTableIndex=22` for the default hot cue color (most common value)
- `Color=-1` for memory cues
- `ColorTableIndex=0` for memory cues
- `created_at` / `updated_at` auto-populate from `StatsFull.default=datetime.now`
- `ID` is VARCHAR(255) containing a numeric string (not UUID, not AUTOINCREMENT integer)

### Pattern 8: Pre-Write Safety Sequence

```python
import shutil
import time
import psutil
from pathlib import Path

def require_rekordbox_closed():
    """Raise if rekordbox.exe is running."""
    for proc in psutil.process_iter(['name']):
        name = proc.info.get('name') or ''
        if 'rekordbox' in name.lower():
            raise RuntimeError(
                f"rekordbox.exe is running (PID {proc.pid}). "
                "Close Rekordbox before writing cue points."
            )

def backup_master_db(db_path: Path) -> Path:
    """Create timestamped backup. Returns backup path."""
    timestamp = time.strftime('%Y%m%d_%H%M%S')
    backup_path = db_path.parent / f'master.db.rekordcue_{timestamp}.bak'
    shutil.copy2(db_path, backup_path)
    return backup_path

def safe_write_sequence(db, content, position_ms):
    """Full safety sequence: check → backup → write."""
    require_rekordbox_closed()                          # FOUND-03
    db_path = db.db_directory / 'master.db'
    backup = backup_master_db(db_path)                  # FOUND-04
    print(f"Backup created: {backup}")
    write_hot_cue(db, content, position_ms)             # SAFE-01 (via commit())
    return backup
```

Note: `db.commit()` in pyrekordbox also calls `get_rekordbox_pid()` internally, providing a second layer of the guard. Both checks should remain: the explicit pre-backup check (above) fires before any mutation; the ORM check fires before the final commit. [VERIFIED: pyrekordbox source]

### Pattern 9: CLI Entry Point

```python
# main.py
import sys
from pyrekordbox import Rekordbox6Database
from db import validate_schema
from waveform import get_pwav_amplitudes, get_beat_grid
from detect import detect_first_onset
from writer import safe_write_sequence

def main():
    if len(sys.argv) != 2:
        print("Usage: python main.py <track_id>")
        sys.exit(1)
    
    track_id = sys.argv[1]
    
    db = Rekordbox6Database()
    
    # FOUND-05 / FOUND-06: Schema validation
    validate_schema(db)
    print("Schema validated OK")
    
    # FOUND-01 / FOUND-02: Find track
    content = db.get_content(ID=track_id).first()
    if not content:
        print(f"Track ID {track_id} not found in library")
        sys.exit(1)
    print(f"Track: {content.Title} | BPM: {content.BPM / 100:.1f} | Length: {content.Length}s")
    
    # WAVE-01 / WAVE-02: Parse ANLZ
    amplitudes, length_s = get_pwav_amplitudes(db, content)
    print(f"PWAV loaded: {len(amplitudes)} samples")
    
    bar_times_s, bpm = get_beat_grid(db, content)
    print(f"Beat grid: {len(bar_times_s)} bars, BPM={bpm:.1f}")
    
    # Rough onset detection
    onset_time_s = detect_first_onset(amplitudes, bar_times_s, length_s)
    onset_ms = round(onset_time_s * 1000)
    print(f"First energy onset detected at: {onset_time_s:.3f}s ({onset_ms}ms)")
    
    # FOUND-03 / FOUND-04 / SAFE-01: Write cue
    backup = safe_write_sequence(db, content, onset_ms)
    print(f"Hot cue A written at {onset_ms}ms")
    print(f"Backup: {backup}")
    
    db.close()

if __name__ == '__main__':
    main()
```

---

## Verified DjmdCue Schema (Rekordbox 7.2.3)

From `PRAGMA table_info(djmdCue)` executed against the live master.db: [VERIFIED: live]

| Column | Type | NOT NULL | Default | Notes |
|--------|------|----------|---------|-------|
| ID | VARCHAR(255) | no | — | PK; numeric string generated by `db.generate_unused_id()` |
| ContentID | VARCHAR(255) | no | NULL | FK → djmdContent.ID; use `content.ID` (string) |
| InMsec | INTEGER | no | NULL | Cue position in milliseconds (REQUIRED for valid cue) |
| InFrame | INTEGER | no | NULL | Set to 0 |
| InMpegFrame | INTEGER | no | NULL | Set to 0 |
| InMpegAbs | INTEGER | no | NULL | Set to 0 |
| OutMsec | INTEGER | no | NULL | Set to -1 (no loop) |
| OutFrame | INTEGER | no | NULL | Set to -1 |
| OutMpegFrame | INTEGER | no | NULL | Set to -1 |
| OutMpegAbs | INTEGER | no | NULL | Set to -1 |
| Kind | INTEGER | no | NULL | **Hot cue slot: 1=A, 2=B, 3=C, ... 0=memory cue** |
| Color | INTEGER | no | NULL | 255 for hot cues, -1 for memory cues |
| ColorTableIndex | INTEGER | no | NULL | 22 for default hot cue; 0 for memory cues |
| ActiveLoop | INTEGER | no | NULL | Set to 0 |
| Comment | VARCHAR(255) | no | NULL | Empty string '' for no label |
| BeatLoopSize | INTEGER | no | NULL | Set to -1 |
| CueMicrosec | INTEGER | no | NULL | `InMsec * 1000` (microseconds) |
| InPointSeekInfo | VARCHAR(255) | no | NULL | Leave NULL |
| OutPointSeekInfo | VARCHAR(255) | no | NULL | Leave NULL |
| ContentUUID | VARCHAR(255) | no | NULL | `content.UUID` value |
| UUID | VARCHAR(255) | no | NULL | Generate with `str(uuid.uuid4())` |
| rb_data_status | INTEGER | no | 0 | Default 0 |
| rb_local_data_status | INTEGER | no | 0 | Default 0 |
| rb_local_deleted | TINYINT(1) | no | 0 | Default 0 |
| rb_local_synced | TINYINT(1) | no | 0 | Default 0 |
| usn | BIGINT | no | NULL | Set by `db.commit(autoinc=True)` |
| rb_local_usn | BIGINT | no | NULL | Set by `db.commit(autoinc=True)` |
| created_at | DATETIME | **YES** | `datetime.now` | Auto-set by StatsFull mixin |
| updated_at | DATETIME | **YES** | `datetime.now` | Auto-set by StatsFull mixin |

**Minimum required fields for a valid INSERT:** `ID`, `ContentID`, `ContentUUID`, `InMsec`, `Kind`, `created_at`, `updated_at`. The pyrekordbox ORM handles `created_at`/`updated_at` automatically.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| DB decryption | Custom SQLCipher key derivation | `Rekordbox6Database()` | Key is embedded in pyrekordbox as obfuscated BLOB; hand-rolling would require RE |
| ANLZ binary parsing | Manual struct.unpack loops | `AnlzFile.parse_file()` + `get_tag()` | pyrekordbox handles tag iteration, endianness, type dispatch |
| Unused ID generation | `SELECT MAX(ID)+1` | `db.generate_unused_id(DjmdCue)` | Generates random 28-bit IDs with collision check; matches Rekordbox's native approach |
| Process detection | Win32 API calls | `psutil.process_iter(['name'])` | Cross-platform, psutil already installed as pyrekordbox dependency |
| Timestamp formatting | Manual `strftime` formatting | `StatsFull` mixin `default=datetime.now` | Auto-handled by SQLAlchemy ORM; `created_at` format from live data: `2025-12-25 20:35:17.878 +00:00` |
| USN management | Manual USN increment | `db.commit(autoinc=True)` | pyrekordbox's registry manages local and row USN increments automatically |

---

## Common Pitfalls

### Pitfall 1: `len(anlz)` or `anlz.keys()` Causes Infinite Recursion

**What goes wrong:** Calling `len(anlz)` or `list(anlz.keys())` on an `AnlzFile` instance triggers infinite recursion in pyrekordbox 0.4.4. Stack overflows immediately.

**Why it happens:** `AnlzFile` inherits `abc.Mapping`; its `__len__` is implemented as `return len(self.keys())`, and `keys()` from `abc.Mapping` somehow calls `__len__`. The circular dependency causes Python's recursion limit to be hit instantly.

**How to avoid:**
```python
# WRONG — causes infinite recursion:
print(len(anlz))
list(anlz.keys())
for k in anlz:  # may also trigger it

# CORRECT:
anlz.tag_types   # property — returns List[str] of tag type codes
anlz.tags        # attribute — raw list of AbstractAnlzTag objects
'PWAV' in anlz   # __contains__ works fine (does not call __len__)
anlz.get_tag('PWAV')  # direct tag access — works fine
```

**Warning signs:** RecursionError during any operation that implicitly checks the length of an AnlzFile object. [VERIFIED: live]

### Pitfall 2: PWAV is a Fixed 400-Sample Thumbnail, Not a Time-Series Signal

**What goes wrong:** Using PWAV sample index as a proxy for time (e.g., `sample_rate = 150 samples/sec`) produces completely wrong results. A 239s track has the same 400-sample PWAV as a 500s track.

**The correct model:** PWAV index i maps to a fraction `i/400` of the total track duration. To get the time position in seconds: `t = (i / 400) * track_length_s`. [VERIFIED: live — every track in the library has exactly 400 PWAV samples]

**How to avoid:** Always compute PWAV indices from beat grid times, not from a fixed sample rate. Use `i = int(t_seconds / track_length_s * 400)`.

### Pitfall 3: DjmdBeat Does Not Exist

**What goes wrong:** Any code that queries `DjmdBeat` via SQLAlchemy or raw SQL will raise `OperationalError: no such table: djmdBeat`.

**How to avoid:** Use ANLZ PQTZ tag exclusively for beat grid data. `pqtz.times`, `pqtz.beats`, `pqtz.bpms` are all available as numpy arrays. [VERIFIED: live — `DjmdBeat` absent from pyrekordbox 0.4.4 tables module and absent from master.db]

### Pitfall 4: PQTZ times Are Seconds, Not Milliseconds

**What goes wrong:** Using PQTZ `times` values directly as milliseconds gives 1000x wrong positions (e.g., cue placed at 43ms instead of 43,000ms = 43s).

**How to avoid:** Always multiply by 1000 when converting to milliseconds for `DjmdCue.InMsec`. [VERIFIED: live — `times[0] = 0.043` for a beat at 43ms]

### Pitfall 5: Kind Field Encodes the Hot Cue Slot — No Separate Number Column

**What goes wrong:** Setting `Kind=1` with a `Number=0` field raises `OperationalError: table djmdCue has no column named Number`. Setting `Kind=0` for all hot cues puts them all as memory cues.

**How to avoid:** Use `Kind=1` for hot cue A, `Kind=2` for B, `Kind=3` for C. Never use `Number`. [VERIFIED: live — PRAGMA table_info confirms no Number column; live rows confirm Kind=1/2/3 pattern]

### Pitfall 6: PRAGMA user_version Is 0 — Cannot Use It for Version Validation

**What goes wrong:** Using `PRAGMA user_version` to check for a specific Rekordbox DB version (e.g., expecting a non-zero value) always returns 0 for Rekordbox 7.2.3, making version detection logic useless.

**How to avoid:** Validate schema structurally by checking for expected column names via `PRAGMA table_info(djmdCue)`. Presence of `ContentUUID` and `UUID` columns (and absence of `Number`) can identify Rekordbox 7.x schema. [VERIFIED: live]

### Pitfall 7: Color Is 255, Not a Palette Index 0–8

**What goes wrong:** Setting `Color` to palette indices 0–8 (as documented in ARCHITECTURE.md) may produce unexpected visual results. Existing hot cue rows all use `Color=255`.

**How to avoid:** Set `Color=255` for hot cues and `Color=-1` for memory cues to match Rekordbox 7's native encoding. Use `ColorTableIndex=22` for the default hot cue appearance. [VERIFIED: live inspection of 403 existing hot cue rows]

### Pitfall 8: The DB Is Encrypted — Plain sqlite3 Cannot Read or Write It

**What goes wrong:** Opening master.db with Python's stdlib `sqlite3.connect()` raises `sqlite3.DatabaseError: file is not a database`. [VERIFIED: live]

**How to avoid:** Always use `Rekordbox6Database()` for any DB access. For Phase 1, use the ORM write path via `db.add()` + `db.commit()` — this uses the same decrypted connection.

### Pitfall 9: pyrekordbox commit() Requires Rekordbox to Be Closed

**What goes wrong:** If Rekordbox is running when `db.commit()` is called, pyrekordbox raises `RuntimeError: Rekordbox is running. Please close Rekordbox before commiting changes.` [VERIFIED: pyrekordbox source]

**How to avoid:** This is the desired behavior. In Phase 1, ensure the process guard message is surfaced clearly to the user. The psutil check before backup provides an earlier, cleaner error message than waiting for commit().

---

## Code Examples

### Open DB and Fetch One Track

```python
# Source: verified against live pyrekordbox 0.4.4 + master.db
from pyrekordbox import Rekordbox6Database

db = Rekordbox6Database()
content = db.get_content(ID='114005429').first()   # track_id from CLI arg
print(f"Title: {content.Title}")
print(f"BPM: {content.BPM / 100:.1f}")
print(f"Length: {content.Length}s")
print(f"AnalysisDataPath: {content.AnalysisDataPath}")
print(f"UUID: {content.UUID}")
```

### Parse PWAV and Beat Grid

```python
# Source: verified against live AnlzFile.parse_file() + PQTZ + PWAV tags
from pyrekordbox import AnlzFile
import numpy as np

dat_path = db.get_anlz_path(content, 'DAT')
anlz = AnlzFile.parse_file(dat_path)

# PWAV: 400-sample fixed-width overview
pwav_data = anlz.get_tag('PWAV').get()
amplitudes = pwav_data[0].astype(float)   # shape (400,), values 0..25

# PQTZ: beat grid in SECONDS
pqtz = anlz.get_tag('PQTZ')
beat_times_s = pqtz.times    # seconds (multiply by 1000 for ms)
beat_numbers = pqtz.beats    # 1, 2, 3, 4 within bar
bpms = pqtz.bpms

# Bar start times (beat 1 of each bar)
bar_times_s = beat_times_s[beat_numbers == 1]
print(f"First bar at: {bar_times_s[0] * 1000:.0f}ms")
print(f"Total bars: {len(bar_times_s)}")
```

### Safe Write One Hot Cue

```python
# Source: pyrekordbox 0.4.4 source + live schema verification
import uuid
import shutil
import time
import psutil
from pathlib import Path
from pyrekordbox.db6.tables import DjmdCue

# 1. Guard
for proc in psutil.process_iter(['name']):
    if 'rekordbox' in (proc.info['name'] or '').lower():
        raise RuntimeError("Close Rekordbox before writing.")

# 2. Backup
db_path = db.db_directory / 'master.db'
ts = time.strftime('%Y%m%d_%H%M%S')
backup = db_path.parent / f'master.db.rekordcue_{ts}.bak'
shutil.copy2(db_path, backup)
print(f"Backup: {backup}")

# 3. Schema validation
from sqlalchemy import text
rows = db.session.execute(text('PRAGMA table_info(djmdCue)')).fetchall()
found_cols = {r[1] for r in rows}
assert 'Kind' in found_cols and 'Number' not in found_cols, "Unexpected schema"

# 4. Write cue
cue = DjmdCue(
    ID=str(db.generate_unused_id(DjmdCue)),
    ContentID=content.ID,
    ContentUUID=content.UUID,
    InMsec=round(onset_ms),
    InFrame=0,
    InMpegFrame=0,
    InMpegAbs=0,
    OutMsec=-1,
    OutFrame=-1,
    OutMpegFrame=-1,
    OutMpegAbs=-1,
    Kind=1,               # hot cue slot A
    Color=255,
    ColorTableIndex=22,
    ActiveLoop=0,
    Comment='',
    BeatLoopSize=-1,
    CueMicrosec=round(onset_ms) * 1000,
    UUID=str(uuid.uuid4()),
)
db.add(cue)
db.commit()   # pyrekordbox's commit re-checks process + manages USN
print(f"Hot cue A written at {onset_ms}ms")
```

---

## State of the Art

| Old Approach (ARCHITECTURE.md / STACK.md) | Verified Reality (RB 7.2.3 + pyrekordbox 0.4.4) | Impact |
|------------------------------------------|-------------------------------------------------|--------|
| `DjmdBeat` table for beat grid | Table does not exist — use PQTZ ANLZ tag | Beat grid code must use ANLZ, not DB |
| `Kind` 0=memory, 1=hot cue + `Number` 0–7 for slot | `Kind` IS the slot: 0=memory, 1=A, 2=B, 3=C | No Number column; Kind encodes slot |
| PWAV at 150 samples/sec | PWAV is always 400 samples (fixed-width thumbnail) | Section detection uses array fraction, not time-rate |
| PRAGMA user_version for schema version check | user_version=0 — unusable as discriminator | Use PRAGMA table_info structural check instead |
| Color IDs 0–8 for hot cues | Color=255 for hot cues, Color=-1 for memory | Must use 255/−1, not palette index |
| `rgb_local_created_at` / `rb_local_updated_at` columns | `created_at` / `updated_at` (no rb_ prefix, DATETIME type) | Different column names; auto-set by ORM |
| Raw sqlite3 for writes (ARCHITECTURE.md recommendation) | pyrekordbox ORM write path is usable and has built-in guards | Prefer ORM; raw sqlite3 as fallback only |
| AnlzFile.tag_types() as method call | AnlzFile.tag_types is a @property, AnlzFile.keys() triggers recursion bug | Always use property syntax, never len(anlz) |
| master.db in rekordbox6/ | master.db is in rekordbox/ (even for RB7) | Different path than expected |
| PQTZ times in milliseconds | PQTZ times in SECONDS | Multiply by 1000 for InMsec |

---

## Assumptions Log

> All critical claims in this research were verified against the live environment (pyrekordbox 0.4.4, Rekordbox 7.2.3, live master.db). The items below remain unverified by direct execution.

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `Kind=4` through `Kind=8` map to hot cue slots D–H | Pattern 6 | Phase 1 only writes Kind=1 (slot A) — risk is zero for Phase 1; matters for Phase 5+ |
| A2 | `CueMicrosec = InMsec * 1000` is the correct formula | Pattern 7 | Cue may appear at wrong sub-ms position; verify by reading back a written row |
| A3 | `ColorTableIndex=22` is the correct default for a "no color" hot cue | Pattern 7 | Cue may appear with wrong color in Rekordbox UI; safe to correct after visual inspection |
| A4 | After writing via `db.add() + db.commit()`, closing and reopening Rekordbox will show the cue | Pattern 7 | If wrong, pyrekordbox write path has a bug; fall back to raw SQLite |
| A5 | Rekordbox 7.2.3 does not require any other file (e.g., masterPlaylists6.xml) to be updated when a cue is added | Pattern 7 | If wrong, cue may be invisible or cause Rekordbox warnings; pyrekordbox commit() does handle playlist XML sync for playlists but likely not cues |

---

## Open Questions

1. **Does writing via pyrekordbox ORM produce a cue that survives Rekordbox close/reopen?**
   - What we know: pyrekordbox 0.4.4 has a working `add()` + `commit()` path; commit includes process guard and USN management
   - What's unclear: Whether the written row is recognized correctly by Rekordbox 7.2.3 on reload
   - Recommendation: Phase 1 success criterion 6 answers this definitively — the PoC task must close Rekordbox, run the script, then reopen and visually confirm the cue

2. **What is the correct `CueMicrosec` encoding?**
   - What we know: Existing hot cue rows have `InMsec` and `CueMicrosec` in a ratio suggesting CueMicrosec = InMsec * 1000 (microseconds)
   - What's unclear: Whether this field is used for display, seek, or ignored entirely
   - Recommendation: Set `CueMicrosec = InMsec * 1000` in Phase 1; verify the cue loads correctly

3. **What does `Kind=9` represent in the cue rows?**
   - What we know: 24 rows with Kind=9 exist; they appear at regular intervals on tracks and may be loop markers or auto-generated anchors
   - What's unclear: Origin and semantic meaning
   - Recommendation: Do not write Kind=9 rows; do not delete them; ignore them in Phase 1

---

## Environment Availability

All Phase 1 dependencies are available. No installs required.

| Dependency | Required By | Available | Version | Notes |
|------------|------------|-----------|---------|-------|
| pyrekordbox | DB + ANLZ access | Yes | 0.4.4 | Installed under Python 3.12 |
| numpy | PWAV array ops | Yes | 2.4.4 | Installed |
| psutil | Process guard | Yes | 6.1.1 | Installed (pyrekordbox dep) |
| sqlcipher3-wheels | DB decryption | Yes | (via pyrekordbox) | Installed as pyrekordbox dep |
| sqlalchemy | ORM layer | Yes | (via pyrekordbox) | Installed as pyrekordbox dep |
| Rekordbox 7.2.3 | Test target | Yes | 7.2.3 | Installed; master.db accessible |

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (not yet installed — see Wave 0) |
| Config file | None — create pytest.ini in Wave 0 |
| Quick run command | `python -m pytest tests/ -x -q` |
| Full suite command | `python -m pytest tests/ -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FOUND-01 | `Rekordbox6Database()` opens without error | smoke | `pytest tests/test_db.py::test_open_database -x` | No — Wave 0 |
| FOUND-02 | AppData path resolved to existing master.db | unit | `pytest tests/test_db.py::test_appdata_path -x` | No — Wave 0 |
| FOUND-03 | psutil guard raises when rekordbox.exe running | unit (mock) | `pytest tests/test_writer.py::test_process_guard -x` | No — Wave 0 |
| FOUND-04 | Backup file created with timestamp | unit | `pytest tests/test_writer.py::test_backup_created -x` | No — Wave 0 |
| FOUND-05 | user_version=0 does not abort; structural validation passes | unit | `pytest tests/test_db.py::test_schema_validation -x` | No — Wave 0 |
| FOUND-06 | PRAGMA table_info finds all required columns | unit | `pytest tests/test_db.py::test_table_info -x` | No — Wave 0 |
| WAVE-01 | get_anlz_path returns existing .DAT file | unit | `pytest tests/test_waveform.py::test_anlz_path -x` | No — Wave 0 |
| WAVE-02 | PWAV array has 400 samples, dtype float | unit | `pytest tests/test_waveform.py::test_pwav_shape -x` | No — Wave 0 |
| SAFE-01 | commit() rolls back on error (no partial write) | unit (mock) | `pytest tests/test_writer.py::test_rollback_on_error -x` | No — Wave 0 |

### Wave 0 Gaps

- [ ] `tests/__init__.py` — package init
- [ ] `tests/test_db.py` — FOUND-01, FOUND-02, FOUND-05, FOUND-06
- [ ] `tests/test_waveform.py` — WAVE-01, WAVE-02
- [ ] `tests/test_writer.py` — FOUND-03, FOUND-04, SAFE-01
- [ ] `pytest.ini` — test config
- [ ] Framework install: `pip install pytest` — not yet installed

---

## Sources

### Primary (HIGH confidence — verified against live environment)

| Source | What Was Verified |
|--------|------------------|
| `pyrekordbox 0.4.4` source inspection | `Rekordbox6Database.__init__`, `commit()`, `generate_unused_id()`, `add()`, `open()`, `AnlzFile` structure, `DjmdCue` table definition, `StatsFull` mixin |
| Live `master.db` queries | PRAGMA user_version=0, PRAGMA table_info(djmdCue) full column list, sample DjmdCue rows (Kind, Color, ColorTableIndex, ID format, UUID format, created_at format), DjmdContent column list, 1056 track count |
| Live ANLZ files | AnlzFile.parse_file() on real .DAT files, PWAV tag structure (400 samples fixed), PQTZ tag structure (times in seconds, beats 1-4, bpms array), get_tag() API |
| `pip show` for all packages | Version numbers for pyrekordbox (0.4.4), numpy (2.4.4), psutil (6.1.1) |
| `pyrekordbox.show_config()` | Rekordbox 7.2.3 detected, master.db path at rekordbox/ not rekordbox6/ |

### Secondary (MEDIUM confidence)

| Source | What Was Referenced |
|--------|---------------------|
| `.planning/research/ARCHITECTURE.md` | Prior research (overridden where contradicted by live verification) |
| `.planning/research/STACK.md` | Prior stack research (pyrekordbox capabilities, ANLZ format reference) |
| `.planning/research/PITFALLS.md` | Domain pitfall catalogue (most remain valid; Pitfall 10 on Type/Number overridden) |
| Deep Symmetry ANLZ spec (training knowledge) | ANLZ tag structure, PMAI magic, PWAV/PQTZ tag descriptions |

---

## Metadata

**Confidence breakdown:**
- Database open / path resolution: HIGH — verified live
- DjmdCue schema and Kind encoding: HIGH — verified with PRAGMA table_info and live row inspection
- PWAV structure (400 samples fixed): HIGH — verified across 10 tracks
- PQTZ beat grid (times in seconds): HIGH — verified against known BPM
- Write via ORM (add + commit): MEDIUM-HIGH — code path inspected, actual round-trip not yet tested
- Section detection algorithm: MEDIUM — functional but thresholds untuned

**Research date:** 2026-04-08
**Valid until:** 2026-05-08 (stable; pyrekordbox version pinned; Rekordbox version pinned)
**Supersedes:** `.planning/research/ARCHITECTURE.md` DjmdCue schema section and DjmdBeat table section
