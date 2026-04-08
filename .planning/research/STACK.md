# Technology Stack

**Project:** RekordCue — Auto Cue Point Tool for Rekordbox
**Researched:** 2026-04-08
**Confidence note:** WebSearch and WebFetch were blocked during research. All findings are from training data (cutoff August 2025). Version numbers and GitHub activity MUST be verified before pinning.

---

## Recommended Stack

### Core Framework / Runtime

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Python | 3.11+ | Application runtime | 3.11 delivers meaningful perf gains for struct/binary parsing; 3.12 fine too. Avoid 3.13 until library ecosystem catches up. |
| pyrekordbox | 0.3.x (verify) | Rekordbox DB + ANLZ file abstraction | The only dedicated Python library for Rekordbox internals. Wraps both the SQLite database and the ANLZ binary waveform/cue files. See critical notes below. |

### Database Access

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| sqlite3 | stdlib | Direct SQLite reads/writes to master.db | Built into Python. No extra dependency. Use for fallback or low-level writes if pyrekordbox's write path is incomplete. |
| pyrekordbox | (same) | ORM-style access to master.db tables | Provides mapped Python objects for tracks, cue points, beat grids instead of raw SQL. |

### Waveform / Analysis File Parsing

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| pyrekordbox | (same) | Parse ANLZ .DAT and .EXT files | Handles the binary tag structure (PWAV, PWV2, PWV3, PQTZ beat grid tags) without manual struct unpacking. |
| construct | 2.10.x | Binary struct parsing fallback | If pyrekordbox's ANLZ coverage is incomplete for a specific tag type, `construct` lets you define declarative binary schemas. Much cleaner than raw `struct.unpack`. |
| struct | stdlib | Last-resort byte parsing | Use only if construct is overkill for a specific small blob. |

### Section Detection / Signal Processing

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| numpy | 1.26.x / 2.x | Array operations on waveform energy data | The waveform energy values from ANLZ are essentially a 1D array; numpy is the right tool for sliding windows, percentile thresholds, diff/gradient operations. |
| scipy | 1.12.x | Peak detection, smoothing | `scipy.signal.find_peaks` and `scipy.ndimage.uniform_filter1d` handle energy envelope smoothing and onset/boundary detection cleanly. |

**Do NOT use librosa for this project.** Reason: librosa operates on raw PCM audio (loading actual audio files). This project reads Rekordbox's pre-computed waveform energy data from ANLZ files — that data is already a reduced representation (not PCM). Pulling in librosa adds a large audio I/O dependency for zero benefit. It would also require access to the original audio files, which is not a project requirement.

### GUI Framework

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| PyQt6 | 6.6.x+ | Desktop UI | Best native-looking Windows UI in Python. Supports proper table views (QTableView + model), custom item delegates for color-coded cue preview, and a clean layout system. |
| QtAwesome | 0.8.x | Icons | Font Awesome icon sets for buttons without bundling image assets. Optional. |

**Tkinter is not recommended.** It is stdlib-simple but produces visually dated UIs, has no proper model/view separation for table data, and custom drawing (cue position preview) requires significant boilerplate on Canvas. The project has a real UI requirement (track list, preview, apply); PyQt6 is the right tool.

**PySide6 is an acceptable alternative** to PyQt6 — same Qt6 bindings, LGPL license vs PyQt6's GPL/commercial. If licensing matters, use PySide6. API is nearly identical; the choice does not affect architecture.

**Dear PyGui is not recommended.** Immediate-mode GPU-accelerated GUI is overkill and less intuitive for a data-table-centric UI.

### Packaging / Distribution

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| PyInstaller | 6.x | Bundle to .exe | Most battle-tested Python-to-exe tool. Handles PyQt6 well with spec file tuning. |
| pyproject.toml + pip | stdlib | Dependency management | Use pyproject.toml with a `[project]` table. No need for Poetry for a single-app project. |

---

## The pyrekordbox Library — Critical Details

**Confidence: MEDIUM** (training data, must verify current state on GitHub/PyPI)

pyrekordbox (`pip install pyrekordbox`) is a Python library specifically built for Rekordbox's internal data formats. Key capabilities as of training data:

**What it covers:**
- Reading and writing `master.db` (the Rekordbox 6 SQLite library database)
- Parsing ANLZ files: `.DAT` (waveform, beat grid, cue points on USB exports) and `.EXT` (extended data including colored waveform, phrase analysis)
- Python object model for tracks (`DjmdContent`), cue points (`DjmdCue`), beat grids
- The database is encrypted/obfuscated in Rekordbox 6+ — pyrekordbox handles the key derivation

**What it may NOT cover (verify):**
- Write path for cue points may be read-optimized; test round-trip before relying on it
- ANLZ waveform tag `PWAV`/`PWV2` energy byte arrays — the library exposes these but you may need to interpret the encoding yourself (each byte = energy level for a waveform column; blue channel = low freq, red = high freq for colored waveform)
- Rekordbox 7 schema changes — verify pyrekordbox is tested against your installed Rekordbox version

**GitHub:** `https://github.com/dylanaraps/pyrekordbox` — CHECK current maintenance status. If the repo has gone stale, fall back to direct sqlite3 + construct.

---

## Rekordbox master.db Schema — Cue Points

**Confidence: MEDIUM** (reverse-engineered community knowledge, may have column name variations by RB version)

The relevant tables in `master.db` for this project:

| Table | Purpose |
|-------|---------|
| `DjmdContent` | Track library — one row per track. Contains `ID`, `Title`, `FileNameL` (filename), `Length` (ms), `BPM`, `StockDate` |
| `DjmdCue` | Cue points — hot cues and memory cues. Foreign key to `DjmdContent` via `ContentID` |
| `DjmdSongPlaylist` / `DjmdPlaylist` | Playlists — needed to show library in UI |

**DjmdCue key columns:**

| Column | Type | Meaning |
|--------|------|---------|
| `ID` | INTEGER PK | Row identifier |
| `ContentID` | INTEGER FK | References `DjmdContent.ID` |
| `InMsec` | INTEGER | Cue position in milliseconds |
| `InFrame` | INTEGER | Sub-frame precision (usually 0 for programmatic writes) |
| `Kind` | INTEGER | 0 = memory cue, 1 = hot cue |
| `Number` | INTEGER | Hot cue slot (0–7 for A–H); -1 or 0 for memory cues |
| `Color` | INTEGER | Color index (0 = none; 1–8 = color palette) |
| `Comment` | TEXT | Cue label text |
| `UUID` | TEXT | Rekordbox internal UUID — must be generated as a valid UUID4 when inserting |

**Beat grid table:** Beat grid data is stored in ANLZ files (PQTZ tag), not in `master.db` directly. `DjmdContent` has `BPM` as an integer * 100 (e.g., 17400 = 174.00 BPM) and `FirstBarBeat` or similar — verify exact column name by inspecting your own `master.db` schema with `sqlite3 master.db ".schema DjmdContent"`.

---

## Rekordbox ANLZ Waveform Files — Format Reference

**Confidence: MEDIUM** (community reverse-engineering documentation, confirmed by multiple independent sources including the Beat Link Trigger / Deep Symmetry project)

**File locations (Windows):**
```
%APPDATA%\Pioneer\rekordbox\share\PIONEER\USBANLZ\<hex_path>\
  ANLZ<nnnn>.DAT   — beat grid, cue points (USB export format)
  ANLZ<nnnn>.EXT   — colored waveform, phrase data (Rekordbox 6+)
```

The path within USBANLZ is derived from the track's file path — typically a hex-encoded directory structure. pyrekordbox resolves this mapping from `master.db`.

**ANLZ file structure:**
- File header: magic bytes `PMAI` followed by header length, type, total length
- Series of tagged sections, each with a 4-byte tag type, length, and data body

**Key tag types for this project:**

| Tag | File | Content |
|-----|------|---------|
| `PQTZ` | .DAT | Beat grid — array of (beat number, BPM * 100, sample offset) entries. This is the timing anchor. |
| `PWAV` | .DAT | Waveform preview — 400-byte array, 1 byte per column, height = energy (0–31), used for overview |
| `PWV2` | .DAT | Waveform detail — higher resolution, same encoding |
| `PWV3` | .EXT | Colored waveform — 3 bytes per column (R/G/B height values); blue = low freq, red = high freq |
| `PWV5` | .EXT | High-res colored waveform (Rekordbox 6+) |
| `PSSI` | .EXT | Song structure / phrase analysis — intro, verse, chorus, outro markers (if Rekordbox analyzed it) |
| `PCOB` | .DAT | Cue points (in USB export format — note: not the same as master.db cues) |

**Waveform energy interpretation for section detection:**
- Each byte in PWAV/PWV2 encodes the column height (amplitude envelope)
- For PWV3 (colored), the red channel approximates high-frequency content (snare, crash) and the blue channel approximates bass/kick presence
- Section boundaries in DnB will show: intro = moderate energy, drop = high red (snare) + high blue (bass), breakdown = low blue + moderate red
- The `PSSI` tag (phrase analysis) in .EXT may already provide structural labels — check if Rekordbox's own "phrase analysis" has been run on the tracks before building custom detection

**Authoritative reverse-engineering resource:**
Deep Symmetry / Beat Link Trigger project by James Elliott documents the full ANLZ binary format:
`https://djl-analysis.deepsymmetry.org/rekordbox-export-analysis/anlz-files.html`
This is the most complete public specification. It covers every tag type with byte-level offsets.

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| GUI | PyQt6 | Tkinter | No proper model/view table; primitive custom drawing |
| GUI | PyQt6 | Dear PyGui | Overkill, immediate-mode paradigm doesn't fit data tables |
| GUI | PyQt6 | wxPython | Smaller ecosystem, less community support, more brittle packaging |
| Audio analysis | numpy + scipy on ANLZ data | librosa | librosa requires PCM audio; we have pre-computed waveform data |
| Audio analysis | numpy + scipy on ANLZ data | essentia | Same problem as librosa, plus heavier C++ dependency chain |
| Binary parsing | pyrekordbox + construct | manual struct.unpack | struct.unpack is fragile for complex hierarchical binary formats |
| DB access | pyrekordbox + sqlite3 | SQLAlchemy | Adds ORM abstraction over a known schema; not needed for a single-db app |
| Packaging | PyInstaller | cx_Freeze | PyInstaller has better PyQt6 support and wider community |
| Packaging | PyInstaller | Nuitka | Compile-to-C is useful for perf-critical apps; not justified here |

---

## Installation

```bash
# Create virtualenv
python -m venv .venv
.venv\Scripts\activate

# Core
pip install pyrekordbox numpy scipy PyQt6

# Binary parsing fallback (add if pyrekordbox ANLZ coverage is incomplete)
pip install construct

# Optional: icon set for GUI
pip install qtawesome

# Packaging
pip install pyinstaller
```

**pyproject.toml dependencies section:**
```toml
[project]
requires-python = ">=3.11"
dependencies = [
    "pyrekordbox>=0.3",
    "numpy>=1.26",
    "scipy>=1.12",
    "PyQt6>=6.6",
    "construct>=2.10",  # optional, add if needed
]
```

---

## What NOT to Use

| Library | Reason to Avoid |
|---------|----------------|
| librosa | Requires loading PCM audio. Project reads pre-computed ANLZ waveform data. Wrong abstraction layer. |
| madmom | Beat tracking from audio — same wrong layer as librosa |
| essentia | Audio feature extraction from PCM — same problem, heavier C++ build chain |
| SQLAlchemy | ORM overhead for a known single-database schema. Use sqlite3 directly. |
| Tkinter | stdlib-convenient but produces visually weak UIs; inadequate for table+preview layout |
| Rekordbox XML export/import | PROJECT.md explicitly rules this out — slower, loses internal ID relationships |
| rekordcrate (Rust) | Wrong language for this project |

---

## Critical Risk: Rekordbox Database Encryption

**Confidence: HIGH** (well-documented, multiple independent sources)

Rekordbox 6 encrypts or obfuscates the `master.db` SQLite file. It is NOT a plain SQLite file you can open directly with the `sqlite3` CLI or DB Browser for SQLite without the correct key.

pyrekordbox handles this transparently — it performs the key derivation and opens the database through the appropriate SQLite cipher extension. If you attempt to open `master.db` directly via Python's stdlib `sqlite3` module without pyrekordbox's setup, you will get a "file is not a database" or corrupted-data error.

**Action required before writing code:** Run `python -c "import pyrekordbox; pyrekordbox.show_rekordbox_settings()"` (or equivalent pyrekordbox utility) to confirm the library can locate and open your specific Rekordbox installation. The key derivation is version-specific.

---

## Critical Risk: Write Safety

**Confidence: HIGH** (first-principles reasoning)

`master.db` is the live Rekordbox library database. A botched write (wrong ContentID, malformed UUID, duplicate cue slot) can corrupt a DJ's library.

Mitigation strategy for the implementation phase:
1. Always `shutil.copy2(master_db_path, master_db_path + ".bak")` before any write session
2. Use a SQLite transaction and commit only after all cue inserts for a track succeed
3. Provide a dry-run / preview mode in the UI that shows what will be written before committing
4. Consider writing to a test copy of master.db first during development

---

## Sources

All findings are from training data (cutoff August 2025). No live web verification was possible in this session.

Key resources to consult directly:

- **pyrekordbox PyPI / GitHub**: `https://github.com/dylanaraps/pyrekordbox` and `https://pypi.org/project/pyrekordbox/` — verify current version, maintenance status, Rekordbox 6/7 compatibility notes
- **Deep Symmetry ANLZ spec**: `https://djl-analysis.deepsymmetry.org/rekordbox-export-analysis/anlz-files.html` — byte-level binary format documentation for all ANLZ tag types
- **Beat Link Trigger project**: `https://github.com/Deep-Symmetry/beat-link` — Java implementation that parses the same formats; useful as a cross-reference implementation
- **PyQt6 docs**: `https://www.riverbankcomputing.com/static/Docs/PyQt6/`
- **construct library**: `https://construct.readthedocs.io/en/latest/`
