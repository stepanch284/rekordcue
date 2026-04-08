# Architecture Patterns

**Domain:** Rekordbox auto cue point tool (Python, Windows desktop)
**Researched:** 2026-04-08
**Overall confidence:** MEDIUM-HIGH
**Source note:** WebSearch and WebFetch were unavailable during this session. All findings derive from training-data knowledge of pyrekordbox (digital-dj-tools/pyrekordbox, active through 2025), the deep-symmetry ANLZ reverse-engineering specification (djl-analysis.deepsymmetry.org), and community Rekordbox schema documentation. These are stable, well-documented sources with low staleness risk. Flag: verify exact column names against a live `master.db` before coding writes.

---

## Recommended Architecture

### System Overview

```
┌────────────────────────────────────────────────────────────────┐
│                        RekordCue App                           │
│                                                                │
│  ┌──────────┐    ┌───────────────┐    ┌──────────────────────┐ │
│  │  DB      │    │  Waveform     │    │  Section             │ │
│  │  Reader  │───▶│  Parser       │───▶│  Detector            │ │
│  └──────────┘    └───────────────┘    └──────────────────────┘ │
│       │                                         │              │
│       │                                         ▼              │
│  ┌──────────┐                         ┌──────────────────────┐ │
│  │  DB      │◀────────────────────────│  Cue Point           │ │
│  │  Writer  │                         │  Generator           │ │
│  └──────────┘                         └──────────────────────┘ │
│                                                                │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    GUI Layer                             │   │
│  │  Track List │ Waveform Canvas │ Cue Overlay │ Apply Btn │   │
│  └─────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────┘
```

### Component Boundaries

| Component | Responsibility | Communicates With |
|-----------|---------------|-------------------|
| `db_reader.py` | Open master.db read-only, query tracks, beat grids, existing cues | DB Writer, GUI |
| `waveform_parser.py` | Locate and parse ANLZ .DAT/.EXT files, extract waveform amplitude arrays | Section Detector, GUI |
| `section_detector.py` | Energy-based analysis, 16-bar boundary alignment, intro/drop/breakdown classification | Cue Generator |
| `cue_generator.py` | Map detected sections to Rekordbox cue point data model (type, color, position ms) | DB Writer |
| `db_writer.py` | Backup master.db, open in write mode, INSERT/UPDATE cue rows in a single transaction | GUI (result reporting) |
| `gui.py` | Track list, waveform canvas, proposed cue overlays, apply button, progress/error feedback | All components |

---

## Data Flow: DB Read → Waveform Parse → Section Detect → Cue Write

```
1. DB Read
   master.db (read-only copy or WAL snapshot)
   ├── DjmdContent → track list (ID, title, artist, file path, duration, BPM)
   ├── DjmdSongMyTag / DjmdMenuItems → for filtering if needed
   └── DjmdBeat → beat grid (track_id, BPM, first_beat_position_ms, measures list)

2. Waveform Locate
   track file path → derive ANLZ path:
   %APPDATA%\Pioneer\rekordbox\<version>\share\PIONEER\<hash_path>\ANLZ0000.DAT
   (see "ANLZ File Path Convention" section below)

3. Waveform Parse
   ANLZ0000.DAT → binary parse → PWAV tag → amplitude array (u8 per entry)
   ANLZ0000.EXT → binary parse → PWV2/PWV3 tags → high-resolution waveform (colored)

4. Section Detection
   amplitude_array + beat_grid → energy per 16-bar window → classify sections

5. Cue Generation
   sections → list of CuePoint(position_ms, type, color, label)

6. DB Write
   shutil.copy(master.db, master.db.bak)          # backup first
   BEGIN TRANSACTION
     DELETE FROM DjmdCue WHERE ContentID = ?      # remove app-generated cues
     INSERT INTO DjmdCue (...)                    # insert new cues
   COMMIT
   Rekordbox must be CLOSED during write (no WAL conflicts)
```

---

## Rekordbox Database Schema

### Database Location (Windows)

```
%APPDATA%\Pioneer\rekordbox\master.db
```

For Rekordbox 6+:
```
%APPDATA%\Pioneer\rekordbox6\master.db
```

**Confidence:** HIGH — stable across Rekordbox 5 and 6, confirmed by pyrekordbox source and community.

### Key Tables

**DjmdContent** — track metadata

| Column | Type | Notes |
|--------|------|-------|
| `ID` | INTEGER PK | Internal track ID (used as foreign key everywhere) |
| `Title` | TEXT | Track title |
| `ArtistName` | TEXT | Artist |
| `AlbumName` | TEXT | Album |
| `FolderPath` | TEXT | Full path to audio file on disk |
| `Length` | INTEGER | Duration in seconds |
| `BPM` | INTEGER | BPM × 100 (e.g., 17400 = 174.00 BPM) |
| `AnalysisDataPath` | TEXT | Relative path to ANLZ folder for this track |
| `FileSize` | INTEGER | |
| `ColorID` | INTEGER | Track color label |
| `Rating` | INTEGER | 0–5 stars |

**DjmdBeat** — beat grid per track

| Column | Type | Notes |
|--------|------|-------|
| `ID` | INTEGER PK | |
| `ContentID` | INTEGER FK → DjmdContent.ID | |
| `Seq` | INTEGER | Beat sequence number (0-indexed) |
| `Measure` | INTEGER | Bar number |
| `Tick` | INTEGER | Position in ticks (1 tick = 1 ms in Rekordbox 6 encoding, verify) |
| `BPM` | INTEGER | Local BPM × 100 at this beat |

In practice you mostly need the first beat's `Tick` value (= first_beat_ms) plus the track BPM to calculate all bar boundaries without reading every row.

**DjmdCue** — cue points (both hot cues and memory cues)

| Column | Type | Notes |
|--------|------|-------|
| `ID` | INTEGER PK AUTOINCREMENT | |
| `ContentID` | INTEGER FK → DjmdContent.ID | Track this cue belongs to |
| `InMsec` | INTEGER | Cue position in milliseconds from track start |
| `InFrame` | INTEGER | Sub-millisecond frame position (set to 0 for simplicity) |
| `InMpegFrame` | INTEGER | MPEG frame number (set to 0) |
| `InMpegAbs` | INTEGER | Absolute MPEG position (set to 0) |
| `OutMsec` | INTEGER | Loop out point in ms (-1 for non-loop cues) |
| `OutFrame` | INTEGER | Loop out frame (-1) |
| `OutMpegFrame` | INTEGER | (-1) |
| `OutMpegAbs` | INTEGER | (-1) |
| `Kind` | INTEGER | 0 = memory cue, 1 = hot cue |
| `Number` | INTEGER | Hot cue slot: 0–7 (A=0, B=1, …, H=7); -1 for memory cues |
| `Color` | INTEGER | Color ID (see color table below) |
| `ColorTableIndex` | INTEGER | Secondary color index |
| `ActiveLoop` | INTEGER | 0 = inactive, 1 = active loop |
| `Comment` | TEXT | Cue label string |
| `BeatLoopSize` | INTEGER | Loop size in beats (-1 for non-loop) |
| `CueMicrosec` | INTEGER | Position in microseconds (alternative precision) |
| `InPointSeekInfo` | TEXT | Seek optimization data (leave NULL) |
| `OutPointSeekInfo` | TEXT | (leave NULL) |
| `ContentUUID` | TEXT | UUID of content record |
| `UUID` | TEXT | UUID for this cue record |
| `rb_local_created_at` | INTEGER | Unix timestamp |
| `rb_local_updated_at` | INTEGER | Unix timestamp |
| `rbattributeChange` | INTEGER | Change tracking flag |

**Confidence for DjmdCue schema:** MEDIUM-HIGH. Core columns (`ContentID`, `InMsec`, `Kind`, `Number`, `Color`, `Comment`) are confirmed by pyrekordbox source code and multiple community reverse-engineering posts. Peripheral columns (seek info, UUID) should be verified against a live `master.db` with `PRAGMA table_info(DjmdCue)` before writing — their nullability matters.

### Hot Cue Color IDs

Rekordbox 6 uses a specific color palette. The integer `Color` field in DjmdCue maps to:

| Color Name | Color ID | RGB approx |
|------------|----------|------------|
| None/White | 0 | #FFFFFF |
| Pink | 1 | #FF007F |
| Red | 2 | #FF0000 |
| Orange | 3 | #FF8C00 |
| Yellow | 4 | #FFE000 |
| Green | 5 | #00C800 |
| Aqua | 6 | #00C8C8 |
| Blue | 7 | #0000FF |
| Violet | 8 | #8000FF |

**Recommended color coding for sections:**
- Intro: Green (5)
- First Drop: Red (2)
- Breakdown: Blue (7)
- Second Drop: Orange (3)

**Confidence:** MEDIUM. Color IDs confirmed by pyrekordbox's `RekordboxColor` enum but exact mapping may differ slightly across Rekordbox versions. Safe approach: expose color IDs as config constants so they can be corrected without code changes.

### Minimal INSERT for a memory cue

```python
INSERT INTO DjmdCue (
    ContentID, InMsec, InFrame, OutMsec, OutFrame,
    Kind, Number, Color, Comment,
    BeatLoopSize, ActiveLoop,
    rb_local_created_at, rb_local_updated_at
) VALUES (
    ?, ?, 0, -1, -1,
    0, -1, ?, ?,
    -1, 0,
    strftime('%s','now'), strftime('%s','now')
)
```

### Minimal INSERT for a hot cue

```python
INSERT INTO DjmdCue (
    ContentID, InMsec, InFrame, OutMsec, OutFrame,
    Kind, Number, Color, Comment,
    BeatLoopSize, ActiveLoop,
    rb_local_created_at, rb_local_updated_at
) VALUES (
    ?, ?, 0, -1, -1,
    1, ?, ?, ?,   -- Kind=1, Number=slot 0-7
    -1, 0,
    strftime('%s','now'), strftime('%s','now')
)
```

---

## ANLZ Waveform File Format

### File Location and Path Convention

Rekordbox stores analysis files alongside the database. For each track, a folder of ANLZ files is created. The path is stored in `DjmdContent.AnalysisDataPath` as a relative path. The base directory is:

```
%APPDATA%\Pioneer\rekordbox\share\PIONEER\USBANLZ\
```

Or for rekordbox6:
```
%APPDATA%\Pioneer\rekordbox6\share\PIONEER\USBANLZ\
```

`AnalysisDataPath` contains something like `share/PIONEER/USBANLZ/ab/cd/ANLZ0000` (forward slashes, no extension). Append `.DAT` or `.EXT` to get the actual file paths. The directory structure uses a 2-level hash derived from the track's content UUID.

**Practical lookup:**
```python
import os

appdata = os.environ['APPDATA']
rb_base = os.path.join(appdata, 'Pioneer', 'rekordbox6')
# AnalysisDataPath from DjmdContent is relative to rb_base
anlz_base = os.path.join(rb_base, row['AnalysisDataPath'].replace('/', os.sep))
dat_path = anlz_base + '.DAT'
ext_path = anlz_base + '.EXT'
```

**Confidence:** MEDIUM. Path convention confirmed by pyrekordbox's `RekordboxDatabase.get_anlz_path()` and community documentation. The exact base directory string may differ between Rekordbox 5 and 6 — always fall back to scanning `%APPDATA%\Pioneer\` if the primary path doesn't exist.

### ANLZ Binary File Structure

ANLZ files are a tagged chunk format. Every file begins with a file header, followed by zero or more typed tags.

**File Header (28 bytes):**

```
Offset  Size  Type    Field
0x00    4     u8[4]   Magic: 'PMAI' (0x504D4149)
0x04    4     u32be   Header length (always 28 / 0x1C)
0x08    4     u32be   Unknown / version
0x0C    4     u32be   File length in bytes
0x10    4     u32be   Number of tags
0x14    8     u8[8]   Unknown padding
```

**Tag Header (20 bytes, immediately follows file header or previous tag):**

```
Offset  Size  Type    Field
0x00    4     u8[4]   Tag type (4 ASCII chars, e.g. 'PWAV')
0x04    4     u32be   Tag header length (always 20 / 0x14)
0x08    4     u32be   Tag body length (bytes of payload, NOT including this header)
0x0C    8     u8[8]   Reserved / padding
```

Tag body immediately follows the tag header. Tags are contiguous — no alignment padding between them.

**All values are big-endian.**

### Tag Types Relevant to This Project

| Tag ID | File | Content |
|--------|------|---------|
| `PQTZ` | .DAT | Beat grid (sequence of beat entries with position and BPM) |
| `PWAV` | .DAT | Low-resolution waveform (half-frame, ~150px tall preview) |
| `PWV2` | .EXT | High-resolution waveform (3-byte entries: height, whiteness, blue-ness) |
| `PWV3` | .EXT | Full-color waveform (newer Rekordbox 6 format) |
| `PHBR` | .EXT | High-resolution beat grid (finer than PQTZ) |

### PWAV Tag — Low-Resolution Waveform (use this for section detection)

The PWAV body is a simple array of 1-byte amplitude values. Each byte represents the waveform height (energy) at that time slice.

```
Body layout:
  Byte 0:     Unknown header byte (usually 0x00 or 0x01, skip)
  Byte 1..N:  Amplitude values, u8, range 0–31 (or 0–63 in some versions)
```

Time-to-index mapping:
```
Each waveform entry = 1/150 second of audio (≈6.67ms per sample)
Index of position T (seconds): floor(T * 150)
```

**Confidence:** HIGH for PWAV 1-byte-per-entry structure — confirmed by deep-symmetry spec and multiple parser implementations including pyrekordbox.

**Amplitude scale:** Values 0–31 for the low-res waveform (5-bit values packed into one byte, upper 3 bits unused or contain color information in some variants). For energy analysis, read the lower 5 bits: `amplitude = byte & 0x1F`.

### PWV2 Tag — High-Resolution Waveform (optional, better visualization)

Each entry is 3 bytes:
```
Byte 0: height (u8) — amplitude, range 0–31
Byte 1: whiteness (u8) — how "white"/bright the column is (for display)
Byte 2: blue-ness (u8) — blue channel component (for display)
```

High-res waveform has more entries per second — approximately 1500 entries per second (10× PWAV). The exact ratio varies; derive it from `tag_body_length / 3 / track_duration`.

**Use PWV2 for the GUI waveform display** (better visual fidelity), **use PWAV for section detection** (faster, sufficient resolution at ~150 samples/sec).

### Parsing ANLZ in Python

```python
import struct

def parse_anlz(path: str) -> dict:
    """Parse ANLZ .DAT or .EXT file, return dict of tag_id -> bytes."""
    tags = {}
    with open(path, 'rb') as f:
        magic = f.read(4)
        assert magic == b'PMAI', f"Bad magic: {magic!r}"
        header_len, _, file_len, num_tags = struct.unpack('>IIII', f.read(16))
        f.read(8)  # reserved

        for _ in range(num_tags):
            tag_id = f.read(4).decode('ascii', errors='replace')
            tag_hdr_len, tag_body_len = struct.unpack('>II', f.read(8))
            f.read(8)  # reserved
            body = f.read(tag_body_len)
            tags[tag_id] = body

    return tags

def extract_waveform_lores(tags: dict) -> list[int]:
    """Extract amplitude array from PWAV tag. Returns list of u8 values."""
    body = tags.get('PWAV')
    if not body:
        return []
    # Skip 1-byte header, read remaining bytes as amplitudes
    return [b & 0x1F for b in body[1:]]
```

### Alternative: Use pyrekordbox

Instead of hand-rolling the parser, pyrekordbox provides:

```python
from pyrekordbox import Rekordbox6Database
from pyrekordbox.anlz import AnlzFile

db = Rekordbox6Database()  # auto-locates master.db
tracks = db.get_content()

anlz = AnlzFile.parse_file(dat_path)
waveform = anlz['PWAV'].entries  # list of WaveformEntry objects
beat_grid = anlz['PQTZ'].entries  # list of BeatGridEntry objects
```

**Recommendation:** Use pyrekordbox for the ANLZ parsing layer in v1. It handles endianness, tag iteration, and version differences. Roll custom parser only if pyrekordbox has a blocking issue. For DB writes, use raw sqlite3 (not pyrekordbox) to retain full control over transaction handling and to avoid any abstraction hiding write errors.

---

## Safe Database Read/Write Strategy

### The Core Risk

Rekordbox holds `master.db` open with a WAL (Write-Ahead Log) while running. Writing to a file Rekordbox has open risks:
1. WAL checkpoint conflicts — your write and Rekordbox's checkpoint race
2. Rekordbox discarding your changes on next DB flush
3. Schema version mismatch if Rekordbox upgrades the DB mid-session

**Rule: Rekordbox must be fully closed before RekordCue writes.**

### Backup Strategy

```python
import shutil
import time
from pathlib import Path

def backup_database(db_path: Path) -> Path:
    timestamp = time.strftime('%Y%m%d_%H%M%S')
    backup_path = db_path.parent / f'master.db.rekordcue_{timestamp}.bak'
    shutil.copy2(db_path, backup_path)
    return backup_path
```

Rules:
- **Always backup before any write.** Non-negotiable.
- Keep the last 5 backups only (prune older ones on startup).
- Show the backup path in the GUI so users know where to find it.
- If backup fails (disk full, permissions), abort the write and show an error.

### Detecting Whether Rekordbox Is Open (Windows)

```python
import psutil

def is_rekordbox_running() -> bool:
    for proc in psutil.process_iter(['name']):
        if proc.info['name'] and 'rekordbox' in proc.info['name'].lower():
            return True
    return False
```

Check before every write. If Rekordbox is running, block the write with a clear modal: "Please close Rekordbox before applying cue points."

### Transaction Pattern for Cue Writes

```python
import sqlite3
from pathlib import Path

def write_cues(db_path: Path, track_id: int, cues: list[CuePoint]) -> None:
    backup_database(db_path)

    con = sqlite3.connect(db_path, isolation_level=None)  # autocommit off
    con.execute('PRAGMA journal_mode=WAL')
    con.execute('PRAGMA foreign_keys=ON')

    try:
        con.execute('BEGIN EXCLUSIVE')  # exclusive lock — no readers during write

        # Remove existing app-generated cues for this track
        # Use a comment marker to distinguish RekordCue-generated cues
        con.execute(
            "DELETE FROM DjmdCue WHERE ContentID = ? AND Comment LIKE '[RC]%'",
            (track_id,)
        )

        for cue in cues:
            con.execute(
                """INSERT INTO DjmdCue
                   (ContentID, InMsec, InFrame, OutMsec, OutFrame,
                    Kind, Number, Color, Comment,
                    BeatLoopSize, ActiveLoop,
                    rb_local_created_at, rb_local_updated_at)
                   VALUES (?, ?, 0, -1, -1, ?, ?, ?, ?, -1, 0,
                           strftime('%s','now'), strftime('%s','now'))""",
                (track_id, cue.position_ms,
                 cue.kind, cue.number, cue.color, cue.comment)
            )

        con.execute('COMMIT')
    except Exception:
        con.execute('ROLLBACK')
        raise
    finally:
        con.close()
```

**Key design choices:**
- `BEGIN EXCLUSIVE` — prevents any concurrent reads while writing (safe; Rekordbox should be closed anyway)
- Comment prefix `[RC]` — marks RekordCue-generated cues so they can be cleanly replaced on re-run without deleting user's manual cues
- Single transaction per track — either all cues land or none do
- Never use `PRAGMA synchronous=OFF` for this use case — the database is too important

### Read-Only Access During Analysis

Use a `?mode=ro` URI for all read operations to guarantee you cannot accidentally modify the database:

```python
con = sqlite3.connect(f'file:{db_path}?mode=ro', uri=True)
```

---

## Algorithm Design: Energy-Based Section Detection

### Input

- `waveform`: list of u8 amplitudes at 150 samples/second (from PWAV)
- `bpm`: float (e.g., 174.0), from `DjmdContent.BPM / 100`
- `first_beat_ms`: int, position of beat 1 in milliseconds (from first DjmdBeat row)

### Step 1: Beat Grid Reconstruction

```python
samples_per_second = 150
beat_interval_ms = 60_000 / bpm
bar_interval_ms = beat_interval_ms * 4          # 4/4 time
phrase_interval_ms = bar_interval_ms * 16        # 16-bar DnB phrase

# List of all bar start times in ms
bar_starts_ms = [first_beat_ms + i * bar_interval_ms
                 for i in range(0, int(track_duration_ms / bar_interval_ms) + 1)]

# Convert to waveform sample indices
def ms_to_idx(ms):
    return int(ms / 1000 * samples_per_second)

bar_starts_idx = [ms_to_idx(t) for t in bar_starts_ms]
```

### Step 2: Energy Per Bar

```python
def bar_energy(waveform, bar_starts_idx, bar_idx):
    start = bar_starts_idx[bar_idx]
    end = bar_starts_idx[bar_idx + 1] if bar_idx + 1 < len(bar_starts_idx) else len(waveform)
    window = waveform[start:end]
    if not window:
        return 0
    return sum(window) / len(window)  # mean amplitude

bar_energies = [bar_energy(waveform, bar_starts_idx, i)
                for i in range(len(bar_starts_idx))]
```

### Step 3: 16-Bar Phrase Segmentation

Group bars into 16-bar phrases (the DnB structural unit):

```python
def phrase_energy(bar_energies, phrase_start_bar, phrase_length=16):
    bars = bar_energies[phrase_start_bar:phrase_start_bar + phrase_length]
    return sum(bars) / len(bars) if bars else 0

phrase_starts = range(0, len(bar_energies), 16)
phrase_energies = [phrase_energy(bar_energies, p) for p in phrase_starts]
```

### Step 4: Section Classification

DnB/Jungle structure:
- **Intro**: Low energy, steadily rising, before the main drop
- **First Drop**: First large energy peak (highest energy density)
- **Breakdown**: Energy drops significantly after first drop (drums out or half-time feel)
- **Second Drop**: Second large energy peak, usually equal or higher than first

```python
import statistics

def classify_sections(phrase_energies):
    if not phrase_energies:
        return {}

    mean_e = statistics.mean(phrase_energies)
    stdev_e = statistics.stdev(phrase_energies) if len(phrase_energies) > 1 else 1
    high_threshold = mean_e + 0.5 * stdev_e
    low_threshold = mean_e - 0.5 * stdev_e

    sections = {}
    drops_found = 0
    in_high = False
    in_low = False

    for i, energy in enumerate(phrase_energies):
        if energy < low_threshold and not in_low and drops_found == 0:
            sections['intro'] = i
            in_low = True
            in_high = False
        elif energy >= high_threshold and not in_high:
            drops_found += 1
            if drops_found == 1:
                sections['first_drop'] = i
            elif drops_found == 2:
                sections['second_drop'] = i
            in_high = True
            in_low = False
        elif energy < low_threshold and in_high:
            sections['breakdown'] = i
            in_low = True
            in_high = False

    return sections  # {section_name: phrase_index}
```

### Step 5: Map Back to Milliseconds

```python
def phrase_to_ms(phrase_idx, first_beat_ms, bpm):
    bar_interval_ms = 60_000 / bpm * 4
    phrase_interval_ms = bar_interval_ms * 16
    return first_beat_ms + phrase_idx * phrase_interval_ms

cue_positions = {
    name: phrase_to_ms(phrase_idx, first_beat_ms, bpm)
    for name, phrase_idx in sections.items()
}
```

### Calibration Notes

- The threshold constants (0.5 × stdev) will need tuning. Start permissive, adjust after testing on 10+ DnB tracks.
- Some tracks have a "re-intro" (energy briefly drops before the second drop) — the algorithm above will catch it as a second breakdown, which is usually correct.
- For tracks where BPM shifts mid-track: DjmdBeat provides per-beat BPM values. For v1, use a single BPM and note this as a known limitation.
- Silence at the very start/end (digital silence = amplitude 0) should be excluded from mean/stdev calculation to avoid skewing thresholds.

---

## Waveform Display in Python Desktop GUI

### Framework Recommendation: PyQt6 with a Custom QWidget Canvas

Use **PyQt6** (not Tkinter) for the GUI. Reasons:
- Tkinter's canvas is too limited for smooth waveform rendering at useful resolutions
- PyQt6 provides `QPainter` with hardware-accelerated rendering
- PyQt6's `QThreadPool` / `QRunnable` pattern handles background processing (waveform parse, section detect) without freezing the UI
- Better Windows DPI handling than Tkinter

**Confidence:** MEDIUM-HIGH. PyQt6 is the standard choice for this class of Python desktop tool. PySide6 is an equally valid alternative (same API, different license).

### Waveform Canvas Pattern

```python
from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QPainter, QColor, QPen
from PyQt6.QtCore import Qt, QRect

class WaveformCanvas(QWidget):
    """Renders waveform amplitudes with cue point overlays."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.amplitudes: list[int] = []         # raw u8 from PWAV
        self.cue_points: list[CuePoint] = []    # proposed cues with ms positions
        self.track_duration_ms: int = 0
        self.setMinimumHeight(80)

    def set_waveform(self, amplitudes, duration_ms):
        self.amplitudes = amplitudes
        self.track_duration_ms = duration_ms
        self.update()  # triggers paintEvent

    def set_cue_points(self, cues):
        self.cue_points = cues
        self.update()

    def paintEvent(self, event):
        if not self.amplitudes:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)  # pixel-perfect
        w, h = self.width(), self.height()

        # Draw waveform columns
        n = len(self.amplitudes)
        max_amp = 31  # PWAV range
        for i, amp in enumerate(self.amplitudes):
            x = int(i / n * w)
            bar_h = int(amp / max_amp * h)
            y = h - bar_h
            painter.fillRect(x, y, max(1, w // n), bar_h, QColor('#1E90FF'))

        # Draw cue markers
        for cue in self.cue_points:
            x = int(cue.position_ms / self.track_duration_ms * w)
            color = CUE_COLORS.get(cue.section, QColor('white'))
            pen = QPen(color)
            pen.setWidth(2)
            painter.setPen(pen)
            painter.drawLine(x, 0, x, h)
            # Label
            painter.setPen(QColor('white'))
            painter.drawText(x + 3, 14, cue.label)

        painter.end()
```

### Background Processing Pattern

Never run waveform parsing or section detection on the Qt main thread. Use `QThreadPool`:

```python
from PyQt6.QtCore import QRunnable, QThreadPool, pyqtSignal, QObject

class WorkerSignals(QObject):
    result = pyqtSignal(object)
    error = pyqtSignal(str)

class AnalysisWorker(QRunnable):
    def __init__(self, track_id, db_path, anlz_path):
        super().__init__()
        self.signals = WorkerSignals()
        self.track_id = track_id
        self.db_path = db_path
        self.anlz_path = anlz_path

    def run(self):
        try:
            waveform = parse_waveform(self.anlz_path)
            beat_grid = read_beat_grid(self.db_path, self.track_id)
            cues = detect_and_generate_cues(waveform, beat_grid)
            self.signals.result.emit(cues)
        except Exception as e:
            self.signals.error.emit(str(e))

# In main window:
pool = QThreadPool.globalInstance()
worker = AnalysisWorker(track_id, db_path, anlz_path)
worker.signals.result.connect(self.waveform_canvas.set_cue_points)
pool.start(worker)
```

### Layout Structure

```
QMainWindow
└── QSplitter (horizontal)
    ├── QTreeView / QTableView    — Track list (DjmdContent rows)
    └── QWidget (detail panel)
        ├── QLabel                — Track title / artist
        ├── WaveformCanvas        — Custom waveform widget
        ├── QLabel                — Detected sections summary
        └── QPushButton           — "Apply Cue Points"
```

---

## Scalability Considerations

This is a single-user desktop tool; scalability concerns are about batch processing and library size, not concurrency.

| Concern | Small library (< 500 tracks) | Large library (1000–5000 tracks) |
|---------|------------------------------|----------------------------------|
| DB read | Open single connection, load all content | Same — SQLite handles it |
| ANLZ parsing | Per-track on demand (lazy) | Per-track on demand, background thread pool |
| Batch "apply to all" | Sequential in background thread | Sequential in background thread; add progress bar |
| Startup time | < 1s | Pagination on track list |

No architectural changes needed for v1 regardless of library size. Lazy ANLZ parsing (only parse when user selects or queues a track) avoids loading hundreds of waveform files at startup.

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Writing While Rekordbox Is Open
**What:** Modifying `master.db` while Rekordbox has it open
**Why bad:** Rekordbox flushes its in-memory state periodically and will overwrite or corrupt your writes; WAL checkpointing creates race conditions
**Instead:** Check for running Rekordbox process (psutil) before every write; block with clear user message

### Anti-Pattern 2: No Backup Before Write
**What:** Directly modifying master.db without a backup copy
**Why bad:** Any bug in cue insertion (wrong ContentID, bad InMsec value, NULL constraint) can corrupt the entire library
**Instead:** `shutil.copy2()` to a timestamped backup file as the first step of every write operation; never skip even during development

### Anti-Pattern 3: Using Rekordbox XML Export Instead of Direct DB
**What:** Export XML from Rekordbox, modify it, re-import
**Why bad:** XML round-trip loses analysis data (waveforms, beat grids stay, but other metadata can drift); requires Rekordbox UI interaction; slow
**Instead:** Direct SQLite writes (already decided in PROJECT.md)

### Anti-Pattern 4: Loading All ANLZ Files at Startup
**What:** Parsing every track's .DAT file when the app starts
**Why bad:** A 1000-track library = 1000 file opens, hundreds of MB of binary data — 30+ seconds of startup time
**Instead:** Lazy load — only parse ANLZ when the user selects a track or explicitly queues it for batch processing

### Anti-Pattern 5: Overwriting User's Manual Cues
**What:** DELETE FROM DjmdCue WHERE ContentID = ? (deletes everything, including hand-placed cues)
**Why bad:** User's own cue points are destroyed without warning
**Instead:** Use the `[RC]` comment prefix to distinguish app-generated cues; only delete rows with that prefix; warn if hot cue slots conflict with user's existing cues

### Anti-Pattern 6: Hardcoding the Rekordbox Path
**What:** `C:\Users\username\AppData\Roaming\Pioneer\rekordbox6\master.db`
**Why bad:** Username varies; Rekordbox version (5 vs 6) changes the path; multi-user machines
**Instead:** Always resolve from `%APPDATA%` environment variable; try both `rekordbox` and `rekordbox6` subdirectories; allow user override in settings

### Anti-Pattern 7: Using Peak Amplitude Only for Section Detection
**What:** Classifying "drop" purely by maximum amplitude spike
**Why bad:** Fills, crashes, and one-shots create momentary peaks that don't represent the start of a section
**Instead:** Use mean energy per bar window (smoothed), not instantaneous peaks

---

## Sources and Confidence

| Finding | Confidence | Source Basis |
|---------|------------|--------------|
| DjmdCue table and core column names | MEDIUM-HIGH | pyrekordbox source code (training data); verify with PRAGMA table_info |
| ANLZ PMAI magic, tag format, big-endian | HIGH | deep-symmetry crate-digger spec (training data); multiple independent parsers confirm |
| PWAV 1-byte-per-entry, 150 samples/sec, 5-bit amplitude | HIGH | deep-symmetry spec; pyrekordbox WaveformEntry implementation |
| PWV2 3-bytes-per-entry, 10× resolution | MEDIUM-HIGH | deep-symmetry spec; confirmed by pyrekordbox |
| AnalysisDataPath column in DjmdContent | MEDIUM | pyrekordbox source; verify column name against live DB |
| Hot cue color IDs | MEDIUM | pyrekordbox RekordboxColor enum; may differ across versions |
| BPM × 100 encoding in DjmdContent | HIGH | Widely documented; consistent across all sources |
| DjmdBeat schema (Seq, Measure, Tick) | MEDIUM | pyrekordbox source; exact column names need live verification |
| Rekordbox 6 path (%APPDATA%\Pioneer\rekordbox6\) | MEDIUM-HIGH | Multiple community sources |
| Section detection algorithm | LOW-MEDIUM | Algorithm design is custom; threshold constants need empirical tuning |

**Critical verification step before writing cues:**
```sql
-- Run this against a live master.db before implementing DB writes:
PRAGMA table_info(DjmdCue);
PRAGMA table_info(DjmdContent);
PRAGMA table_info(DjmdBeat);
```
Cross-reference actual column names with those documented above. The schema is stable across Rekordbox versions but exact nullable columns and default values matter for INSERT statements.
