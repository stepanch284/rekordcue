# Feature Landscape: Rekordbox Auto Cue Point Tool

**Domain:** Rekordbox cue point automation for DnB/Jungle DJs
**Researched:** 2026-04-08
**Confidence note:** WebSearch and WebFetch were unavailable in this environment. All findings derive from training data (cutoff August 2025) plus explicit domain reasoning. Confidence levels reflect this.

---

## Existing Ecosystem

### Tools That Currently Exist

**pyrekordbox** (HIGH confidence)
The primary open-source Python library for interacting with Rekordbox's internal data. Maintained actively as of mid-2025. Provides:
- Parsing of `master.db` (SQLite) for tracks, cue points, beat grids
- Read/write access to ANLZ waveform files (`.DAT`, `.EXT` extensions)
- Structs for PHRS (phrase analysis), PWAV (waveform data), PQTZ (quantize/beat grid) chunks
- Access to hot cues and memory cues by type and position
pyrekordbox is the de-facto standard for Python-based Rekordbox tooling. Any new Python tool targeting Rekordbox should build on it rather than re-implement parsing.

**rekordcloud / Rekord Buddy** (MEDIUM confidence)
Commercial tools (not open source) for syncing Rekordbox libraries with Serato, Traktor, etc. They expose cue import/export but do not auto-generate cues from audio analysis. They are migration tools, not analysis tools.

**Mixed In Key** (HIGH confidence)
Commercial desktop application. Analyzes audio files for key and energy. Writes hot cues at detected energy peaks (downbeats, phrase changes) directly to Rekordbox via the XML import route. Color-codes cues by energy level. Widely used by DJs across genres. MIK is the dominant existing "auto cue" tool in the market.
- Limitation: Uses its own audio analysis, not Rekordbox's internal waveform data
- Limitation: Places cues at energy peaks only — not aware of structural section names (intro/drop/breakdown)
- Limitation: XML import route means user must reimport in Rekordbox; direct DB write is faster

**Cue point scripts on GitHub / DJ forums** (MEDIUM confidence)
Several community Python scripts exist (e.g., scripts that parse `master.db` directly to list or copy cue points across tracks). These are largely unmaintained one-off tools. Common capabilities seen: copy cue from one track to another (same BPM), bulk-shift cues by offset, export cue list as CSV.
None of the known community tools do structural analysis (intro/drop/breakdown detection). That makes RekordCue a genuine gap-fill.

**Rekordbox's built-in "Phrase Analysis"** (HIGH confidence)
Since Rekordbox 6.x, Pioneer added phrase analysis that detects "Intro," "Verse," "Chorus," "Outro" sections and displays them on the waveform. This is genre-aware but tuned for pop/electronic structures. For DnB/Jungle specifically:
- Phrase detection is inconsistent — DnB energy profiles differ from pop choruses
- Results are visual overlays only — they do NOT automatically create hot cues
- Users must manually look at phrase analysis and then place cues themselves
- This is the key gap RekordCue exploits: automate the cue placement step for DnB structures

**Lexicon DJ** (MEDIUM confidence)
Subscription-based library management tool. Supports cue import/export across DJ software but does not generate cues from audio analysis. Not a competitor for the analysis use case.

---

## What DnB/Jungle DJs Actually Want

Based on community knowledge from DJ forums (r/DJs, DnBForum, Serato/Rekordbox Facebook groups), the recurring requests are:

**The core frustration:** Large DnB libraries (hundreds to thousands of tracks) with no cues. Setting cues manually is 2-5 minutes per track. At 1000 tracks that is 33+ hours of manual work.

**What they ask for:**
1. Jump straight to the first drop without scrubbing — the single most-requested capability
2. Know where the breakdown is so they can plan energy management during a set
3. Know where the intro ends so they can mix in at the right point
4. Consistent cue colors across their library so muscle memory works across tracks

**What they do NOT want:**
- ML black-box analysis they cannot verify or correct
- Tools that require re-analyzing every track outside Rekordbox (they already ran Rekordbox analysis)
- Anything that risks corrupting their library database — DJs treat their Rekordbox library as irreplaceable
- Cues placed at random energy peaks (MIK-style) with no structural meaning
- Having to re-import via XML every time (the MIK round-trip friction is real)

**DnB-specific structural expectations:**
- Intro: bars 0–16 (sometimes 0–32 for label-style tracks)
- First Drop: typically bar 16 or bar 32
- Breakdown: typically 32–48 bars after the drop
- Second Drop: after the breakdown, usually bar 64 or bar 80
- Outro: last 16–32 bars
The 16-bar phrase grid is the bedrock assumption. Tracks that deviate (e.g., 8-bar intros, 24-bar breakdowns) are "unusual structure" tracks — DJs want to know when auto-detection may have failed.

---

## Table Stakes Features

Features users expect as baseline. Without these, the tool is not usable.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Detect first drop and place hot cue | Core value proposition — the #1 ask | Medium | Must be reliable >90% of the time or trust breaks |
| Detect intro end and place hot cue | Second most critical — mixing in cleanly | Medium | Derived from first drop position (intro ends where drop starts) |
| Detect breakdown and place hot cue | Energy management planning | Medium | Energy valley after first drop |
| Detect second drop and place hot cue | Full set planning | Medium | Energy peak after breakdown |
| Color-code cues by section type | Muscle memory during live performance | Low | Must be configurable; defaults must match community conventions |
| Place cues on beat-grid-aligned boundaries | Off-grid cues are unusable to DJs | Low | Already anchored to Rekordbox beat grid — must snap to nearest 16-bar boundary |
| Track list UI showing library tracks | Without this, users cannot select what to process | Medium | Pull from Rekordbox SQLite track table |
| Preview cue positions before writing | Safety requirement — DJs need to verify before committing | Medium | Show bar positions and timestamps alongside waveform-derived confidence score |
| Apply/write cues to Rekordbox database | The actual output — must write to master.db correctly | High | Requires correct schema reverse-engineering; schema not publicly documented |
| Database backup before any write operation | Non-negotiable safety net | Low | Copy master.db before first write; warn user if backup fails |
| Do not overwrite existing cues without confirmation | Library preservation — DJs may have hand-set cues on some tracks | Low | Check for existing cues; prompt before overwrite |

---

## Differentiating Features

Features that set this tool apart. Not baseline expectations, but create strong preference.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Section labels on cues (e.g., "DROP 1", "BRKDN") | Rekordbox shows cue labels in performance view; named cues are immediately readable | Low | Hot cue label field exists in schema — use it |
| Confidence score per detected section | Tells DJ "this detection is uncertain — check manually" | Low (display) / Medium (algorithm) | Flag tracks where energy profile is ambiguous |
| Batch processing (whole playlist / all tracks) | Processing one track at a time is friction for large libraries | Medium | Queue-based processing with progress indicator |
| Skip tracks that already have cues | Preserves manual work; makes re-running safe | Low | Check cue count before processing |
| Memory cues in addition to hot cues | Memory cues are visible during track browsing; hot cues require loading the deck | Low | Write both types at same positions; different type flag in DB |
| Adjustable structural assumptions (e.g., 32-bar intro mode) | Some DnB sub-styles use 32-bar intros instead of 16 | Low | Config option; default 16-bar |
| Visual waveform preview with proposed cue markers | Reduces verification time drastically | High | Not MVP — requires waveform rendering |
| Export cue report (CSV / text) | DJs who run radio shows or track lists want a record | Low | Nice-to-have, very easy to add |

---

## Anti-Features

Features to explicitly NOT build in v1, with reasoning.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| ML-based section detection (neural networks, transformers) | Training data for DnB-specific structures barely exists; inference latency is high; models are a black box DJs cannot trust | Stick to energy/amplitude analysis on Rekordbox waveform data — deterministic, fast, inspectable |
| Full audio file re-analysis (librosa, Essentia reading MP3/FLAC) | Slow, requires loading multi-hundred-MB audio files, duplicates work Rekordbox already did | Parse the Rekordbox `.DAT`/`.EXT` waveform summary files — already computed, fast to read |
| Genre detection | Adds a classifier problem on top of the cue problem; DnB/Jungle assumption is explicit | Document that the tool targets DnB/Jungle; do not attempt to auto-detect |
| Rekordbox XML round-trip import | Slower, requires user interaction inside Rekordbox UI, risk of duplicate cues | Write directly to master.db |
| macOS support in v1 | Path handling and DB location differ; doubles test surface | Windows-first; note macOS paths for future |
| Cloud sync / library backup | Out of scope and creates liability if sync corrupts data | Advise users to use Rekordbox's own cloud backup |
| BPM re-analysis | Rekordbox analysis is already correct for DnB; fighting it creates misalignment | Trust Rekordbox beat grid; anchor all cues to it |

---

## Section Detection Approaches (How Other Tools Do It)

### Beat/Bar Counting (LOW complexity, used by basic scripts)
Count bars from beat grid anchor (bar 0). Place cues at fixed bar numbers: bar 0 = intro, bar 16 = drop, bar 32 = drop 2, etc. No audio analysis required.
- Weakness: Assumes identical structure across all tracks — fails for tracks with 8-bar or 32-bar intros.
- Usefulness for RekordCue: Good fallback if energy analysis fails.

### Energy/Amplitude Threshold Analysis (MEDIUM complexity, recommended for RekordCue)
Read the Rekordbox waveform summary data (PWAV chunk in `.DAT` files). This gives amplitude per ~50ms window. Look for:
- High-energy onset after a low-energy region = drop
- Low-energy region after a high-energy region = breakdown
- Sustained high energy after breakdown = second drop
Snap results to nearest 16-bar boundary from the beat grid.
- Rekordbox stores waveform data at multiple resolutions; the "overview" waveform is the fastest to parse
- pyrekordbox exposes these as numpy arrays via `AnlzFile`
- This is the approach RekordCue should use (HIGH confidence this is correct path)

### Spectral Analysis (HIGH complexity, overkill for v1)
FFT analysis on raw audio — separate kick, bass, mid frequency bands. More accurate for ambiguous tracks. Requires loading audio files, significantly slower, large dependency footprint. Defer.

### ML/Deep Learning (VERY HIGH complexity, not recommended)
Models like Essentia's SVM classifiers or transformer-based beat trackers. State of the art for general music structure but massive overhead. DnB genre has limited labeled training data. The non-ML approach is already sufficient for a genre with predictable 16-bar structure.

---

## Hot Cue Color Conventions

Color use is subjective but strong community norms exist in the DnB/DJ space.

**Pioneer Rekordbox hot cue color palette** (the 8 selectable colors in older Rekordbox, expanded in v6):
Standard colors available: Pink/Magenta, Red, Orange, Yellow, Green, Aqua/Cyan, Blue, Purple

**Community conventions observed in DnB DJ forums and shared library setups** (MEDIUM confidence — no single authoritative standard, but these patterns repeat):

| Section | Commonly Used Color | Rationale |
|---------|---------------------|-----------|
| Intro start / Cue A | Green | "Go" signal, safe landing |
| First Drop | Red or Magenta/Pink | High energy, urgent — stands out immediately |
| Breakdown | Blue or Aqua | Cool energy, contrast with drop colors |
| Second Drop | Orange or Yellow | High energy but visually distinct from first drop |
| Outro | Purple | Cool/closing energy |

**Mixed In Key convention** (HIGH confidence — MIK is documented):
MIK uses energy level to assign colors — high energy = warm color (red/orange), low energy = cool color (blue/purple). This aligns loosely with the drop/breakdown convention above.

**Recommendation for RekordCue:**
Default to: Intro = Green, Drop 1 = Red, Breakdown = Blue, Drop 2 = Orange.
Make all colors configurable per section type in settings — some DJs have established personal conventions and will not change them.

**Rekordbox color encoding in the database** (MEDIUM confidence — from pyrekordbox and community reverse-engineering):
Hot cue colors are stored as RGB integers in `master.db`. The 16 "named" Rekordbox colors map to specific RGB values that Pioneer's UI renders as the hardware CDJ colors. Use the pyrekordbox color constants to ensure CDJ hardware displays the correct color — using arbitrary RGB values may render differently on CDJs vs the Rekordbox software.

---

## Edge Cases and Failure Modes

### Tracks with Unusual Structures

| Edge Case | Frequency in DnB | Impact | Mitigation |
|-----------|-----------------|--------|------------|
| 32-bar intro (label-style / radio edits) | Common (~15-20% of tracks) | First drop cue placed at bar 16, missing actual drop at bar 32 | Offer "32-bar intro mode" toggle; or detect by energy — if bar 16 is low-energy, advance to bar 32 |
| 8-bar intro (DJ tools / edits) | Common in DJ-specific edits | First drop placed too late | Energy analysis should catch this — sudden energy onset before bar 16 |
| No breakdown (full-power rollers) | Occasional | Breakdown cue placed incorrectly | Confidence threshold — if no clear energy valley detected, omit breakdown cue and flag track |
| Intro that fades in slowly (no hard energy onset) | Common in ambient/neurofunk | Energy onset detector finds wrong point | Use bar-count fallback when energy gradient is below threshold |
| Mixed BPM or half-time breakdowns | Rare but exists in liquid/neurofunk | Beat grid alignment off during breakdown | Trust Rekordbox beat grid throughout; note that Rekordbox handles variable BPM with warp points |
| Track with existing hot cues | Any track a DJ has already curated | Risk of overwriting hand-placed cues | Always check for existing hot cues; skip or prompt before overwriting |
| Beat grid misaligned by Rekordbox | Occasional — especially older vinyl rips | All 16-bar calculations wrong | Cannot detect from waveform data alone; surface as a known limitation; optionally warn if detected BPM seems inconsistent with grid |
| Remixes with non-standard structure | Common — remixes don't follow original structure | Section positions wrong | No reliable fix; flag as "remix" via track title heuristic (if title contains "remix" / "edit" / "VIP") |
| Very short tracks (DJ intros, stabs, < 2 min) | Occasional tool tracks | Not enough bars to have all 4 sections | Handle gracefully — place only the cues that fit within track length |
| Silence or near-silence leading in | White label / promotional tracks with long silence | Energy detection fires too late | Strip leading silence before analysis window, or use beat grid bar 0 as hard anchor regardless |

### Database / Technical Edge Cases

| Edge Case | Impact | Mitigation |
|-----------|--------|------------|
| Rekordbox is open while writing to master.db | SQLite write lock; potential DB corruption | Detect if Rekordbox process is running; warn user to close it before processing |
| master.db schema changes between Rekordbox versions | SQL writes fail silently or corrupt rows | Pin to known-good schema versions; validate schema on startup before any write |
| Track file has been moved or is offline | Track entry in DB but no waveform file | Gracefully skip with clear error message per track |
| Hot cue slot limit (8 hot cues in Rekordbox) | Only 4 sections but each section gets hot cue + possibly redundant | Use at most 4 hot cues (one per section); use memory cues for additional markers if needed |
| User has Rekordbox 5.x (legacy) vs 6.x / 7.x | DB schema differences between major versions | Detect Rekordbox version from DB metadata; support v6+ explicitly, warn on v5 |

---

## MVP Feature Recommendation

**Phase 1 — Core pipeline (no UI):**
1. Parse waveform data for a single track via pyrekordbox
2. Detect first drop via energy onset analysis
3. Write one hot cue (Red, label "DROP 1") to master.db at 16-bar-snapped drop position
4. Backup master.db before write
5. CLI invocation: `python main.py <track_id>`

Validate: Does the cue land on the right bar? Is the DB write correct? Does Rekordbox load it without issues?

**Phase 2 — Full section detection:**
5. Detect all 4 sections (intro end, drop 1, breakdown, drop 2)
6. Write hot cues (color-coded) + memory cues at all 4 positions
7. Label each cue ("INTRO", "DROP 1", "BRKDN", "DROP 2")
8. Confidence scoring per section — flag uncertain detections

**Phase 3 — Desktop UI:**
9. Track list pulled from master.db
10. Preview panel showing bar-level section positions and confidence
11. Batch processing queue
12. Settings: color scheme, 16/32-bar intro toggle, overwrite policy

**Defer to later phases:**
- Waveform rendering / visual preview (High complexity, significant UI work)
- Export reports
- Multiple Rekordbox library support
- macOS path support

---

## Sources

**HIGH confidence (from pyrekordbox documentation and Rekordbox reverse-engineering community, known as of August 2025):**
- pyrekordbox library: https://pyrekordbox.readthedocs.io — ANLZ file format, master.db schema, hot cue schema
- Rekordbox ANLZ format reverse-engineering: https://github.com/Deep-Symmetry/crate-digger (Java, but documents binary format authoritatively)

**MEDIUM confidence (community knowledge, training data only — verify before building):**
- DnB phrase structure conventions (16-bar) — consistent across DJ education resources and community discussion
- Hot cue color conventions — observed patterns in forum discussions, not a published standard
- Mixed In Key color behavior — documented in MIK marketing/support materials

**LOW confidence (needs direct verification):**
- Exact Rekordbox 7.x master.db cue schema column names — reverse-engineering is ongoing; verify with pyrekordbox source before writing
- Exact RGB values Pioneer uses for CDJ hardware colors — check pyrekordbox color constants, do not hardcode
- Phrase analysis feature behavior in Rekordbox 7.x — may have changed since training cutoff

**Cannot verify (tools unavailable in this research session):**
- Current GitHub stars / maintenance status of pyrekordbox (last known: active as of 2024)
- Whether any new auto-cue tools shipped in 2025-2026
- Current community discussion threads about DnB cue conventions
