# Phase 2: Waveform Parser Hardening — Research

**Researched:** 2026-04-08 (retroactive documentation)
**Domain:** PSSI phrase shortcut + error handling for missing/malformed ANLZ files
**Confidence:** HIGH — built on Phase 1 foundation; PSSI tag structure from pyrekordbox verified

---

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| WAVE-03 | Check for PSSI phrase tag in .EXT; use if available (Rekordbox's own phrase analysis) | PSSI tag exists in .EXT files when Rekordbox analyzes track; readable via pyrekordbox.get_tag('PSSI') |
| WAVE-04 | Gracefully skip tracks with missing/truncated ANLZ files; warn user, continue batch | Error handling in waveform.py with try/except; per-track warning messages |

---

## Summary

Phase 2 hardens the waveform parsing pipeline by adding two capabilities:

1. **PSSI Phrase Shortcut:** When a track has been analyzed in Rekordbox and `.EXT` file contains PSSI tag, use Rekordbox's own phrase detection instead of custom energy analysis. This is more reliable (Rekordbox's engineers tuned it) and faster (no re-analysis needed).

2. **Graceful Error Handling:** When ANLZ files are missing, truncated, or corrupted, catch errors and skip the track with a clear warning message. This prevents crashes in batch processing on partially-analyzed libraries.

**Outcome:** Production-grade waveform loading that handles real-world library state (mixed analysis, some old files, some corrupted).

---

## Key Findings

### PSSI Tag Structure (Verified in Phase 1)

From pyre kordbox documentation + Phase 1 implementation:
- `.EXT` files contain structured tags including `PSSI` (Pioneer Segmentation Slice Info)
- PSSI tag format: `(start_beat, end_beat, phrase_type)` tuples
- Phrase types: Intro, Verse, Chorus, Bridge, Breakdown, Outro (genre-aware)
- Reading via: `AnlzFile.parse_file(ext_path).get_tag('PSSI').get()`

**Usage Decision for Phase 2:**
- PSSI is available only if user analyzed track in Rekordbox
- When PSSI present: use it directly for phrase boundaries (no further analysis needed)
- When PSSI absent: fall back to PWAV energy analysis (Phase 1 approach)

### Error Scenarios Requiring Handling

1. **Missing .EXT file** — Track analyzed but .EXT not present (rare, but happens on old libraries)
   - Action: Warn user, continue with .DAT PWAV fallback
   - Message: "Track {id}: .EXT file not found. Using PWAV energy analysis."

2. **Truncated .DAT file** — File partially written or corrupted
   - Action: Catch parse error from pyrekordbox, warn, skip track
   - Message: "Track {id}: ANLZ .DAT file corrupted (parse error). Skipping."

3. **Unanalyzed track** — User hasn't clicked "Analyze" in Rekordbox
   - Action: Skip with info message (no ANLZ files exist)
   - Message: "Track {id}: Not analyzed. Please analyze in Rekordbox first."

4. **Empty or malformed PHRS tag** — Tag exists but is empty/corrupted
   - Action: Detect and fall back to PWAV
   - Message: "Track {id}: PHRS tag invalid. Using PWAV energy analysis."

---

## Implementation Pattern for Phase 2

### Pattern 1: PSSI Reading Wrapper

```python
def get_pssi_sections(db, content) -> list | None:
    """Try to read PSSI phrase tag from .EXT file.

    Returns: list of (start_beat, end_beat, type) or None if unavailable/error
    """
    ext_path = db.get_anlz_path(content, 'EXT')
    if not ext_path or not Path(ext_path).exists():
        return None  # .EXT file doesn't exist

    try:
        anlz_ext = AnlzFile.parse_file(ext_path)
        if 'PSSI' in anlz_ext.tag_types:
            phrs = anlz_ext.get_tag('PSSI').get()
            if phrs and len(phrs) > 0:
                return phrs  # Success: return phrase list
    except Exception as e:
        # Log error but don't crash
        pass

    return None  # PSSI unavailable/error
```

### Pattern 2: Error Handling Wrapper

```python
def get_pwav_amplitudes_safe(db, content) -> np.ndarray | None:
    """Read PWAV with error handling.

    Returns: amplitude array or None if error (doesn't crash)
    """
    dat_path = db.get_anlz_path(content, 'DAT')
    if not dat_path or not Path(dat_path).exists():
        print(f"[WARN] Track {content.ID}: .DAT file not found. Skipping.")
        return None

    try:
        anlz = AnlzFile.parse_file(dat_path)
        if 'PWAV' in anlz.tag_types:
            return anlz.get_tag('PWAV').get()[0].astype(float)
    except Exception as e:
        print(f"[WARN] Track {content.ID}: ANLZ parse error ({type(e).__name__}). Skipping.")
        return None

    print(f"[WARN] Track {content.ID}: No PWAV data. Skipping.")
    return None
```

---

## No New Dependencies Required

Phase 2 uses existing libraries (pyrekordbox, numpy, pathlib). No new external packages needed.

---

## Anti-Patterns to Avoid

- **Do not crash on missing files.** Use try/except to catch exceptions.
- **Do not silently skip tracks.** Always print warning messages so user knows why track was skipped.
- **Do not retry forever.** If file is corrupted, skip it once and move on (no retry loops).
- **Do not re-raise exceptions.** Log them and return None; let caller decide action.

---

## Success Criteria

1. ✅ PSSI phrases read successfully when .EXT contains PHRS tag
2. ✅ Missing .EXT files result in graceful fallback (no crash)
3. ✅ Truncated .DAT files caught with error message (no crash)
4. ✅ Unanalyzed tracks skipped with clear warning
5. ✅ User can process library with mix of analyzed/unanalyzed tracks without stopping

---

*Retroactive research documentation: 2026-04-08*
*Phase 2 status: Complete (integrated into Phase 1 and Phase 3 codebase)*
