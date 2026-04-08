---
phase: 01-cli-proof-of-concept
plan: 02
subsystem: data-pipeline
tags: [pyrekordbox, djmdcue, psutil, sqlite, hot-cue, cli]
dependency_graph:
  requires: [01-01]
  provides: [writer.py, main.py]
  affects: []
tech_stack:
  added: [psutil]
  patterns:
    - psutil.process_iter(['name']) for rekordbox.exe process guard
    - shutil.copy2 timestamped backup before any DB mutation (YYYYMMDD_HHMMSS suffix)
    - pyrekordbox ORM DjmdCue insert via db.add() + db.commit() (StatsFull mixin handles timestamps)
    - db.generate_unused_id(DjmdCue) for collision-safe primary key generation
    - safe_write_sequence: guard -> backup -> write ordering (no mutation if any prior step fails)
    - Hot cue A anchored to bar 0 (bar_times_s[0]), not the detected onset position
key_files:
  created:
    - writer.py
    - main.py
  modified: []
decisions:
  - Hot cue A is written at bar 0 (track start anchor), not at the detected onset — onset detection is preserved in output but not used as the cue position for slot A
  - Comment field is empty string (no label text) — matches native Rekordbox manual cue behavior
  - Color=255 and ColorTableIndex=22 set from live Rekordbox row inspection (not palette index 0-8)
  - StatsFull mixin auto-sets created_at/updated_at — omit from DjmdCue constructor
  - db.commit() used for the write (pyrekordbox built-in USN management + second process guard layer)
metrics:
  duration: ~25 minutes
  completed: 2026-04-08T21:00:00Z
  tasks_completed: 3
  tasks_total: 3
  files_created: 2
  files_modified: 0
requirements_fulfilled:
  - FOUND-03
  - FOUND-04
  - SAFE-01
---

# Phase 1 Plan 2: Write Pipeline and CLI Entry Point Summary

**One-liner:** psutil process guard, timestamped master.db backup, and DjmdCue ORM insert wired into a single `python main.py <track_id>` CLI — hot cue A written at bar 0 and confirmed visible in Rekordbox 7.2.3 after reopen.

---

## What Was Built

Two Python modules completing the read-detect-write proof-of-concept for RekordCue.

### `writer.py`

- `require_rekordbox_closed()`: Iterates `psutil.process_iter(['name'])` checking for 'rekordbox' (case-insensitive). Raises `RuntimeError` with PID on match. Silently skips `NoSuchProcess` / `AccessDenied` mid-iteration.
- `backup_master_db(db_path: Path) -> Path`: Creates `master.db.rekordcue_YYYYMMDD_HHMMSS.bak` in the same directory via `shutil.copy2`. Re-raises any copy failure as `RuntimeError("Backup failed — write aborted. No changes made.")`.
- `write_hot_cue(db, content, position_ms: int)`: Constructs `DjmdCue` ORM object with verified field values (Kind=1, Color=255, ColorTableIndex=22, CueMicrosec=InMsec*1000, UUID from `uuid.uuid4()`). Calls `db.add(cue)` then `db.commit()`. Does not set `created_at`/`updated_at` — StatsFull mixin handles those.
- `safe_write_sequence(db, content, position_ms: int) -> Path`: Chains guard -> backup -> write. Returns backup path. If `write_hot_cue` raises, prints recovery path and re-raises; no mutation has been applied if backup itself failed.

### `main.py`

Full CLI entry point for `python main.py <track_id>`:

1. Parse `sys.argv` — exits 1 with usage if wrong argument count.
2. `open_database()` — encrypted master.db via pyrekordbox auto-locate.
3. `validate_schema(db)` — structural check; prints "Schema validated OK".
4. `get_track(db, track_id)` — prints Title, BPM, Length.
5. `get_pwav_amplitudes(db, content)` — prints "PWAV loaded: 400 samples".
6. `get_beat_grid(db, content)` — prints bar count and BPM.
7. `detect_first_onset(amplitudes, bar_times_s, length_s)` — prints detected onset bar and time (informational only).
8. Compute `bar0_ms = int(bar_times_s[0] * 1000)` — hot cue A anchored to bar 0.
9. `safe_write_sequence(db, content, bar0_ms)` — guard, backup, write.
10. Prints "Hot cue A written at bar 0 (Xms)".
11. `finally: db.close()` — always runs regardless of error path.

`RuntimeError` (process guard, schema, backup) exits 1 cleanly. Unexpected `Exception` exits 1 with "UNEXPECTED ERROR:".

---

## Verification Results (Live Rekordbox 7.2.3)

Human checkpoint APPROVED: hot cue A appeared at bar 0 in Rekordbox after close/reopen.

| Check | Result |
|-------|--------|
| `require_rekordbox_closed()` | PASS — no error when Rekordbox is closed |
| `backup_master_db()` | PASS — timestamped .bak file created in AppData rekordbox dir |
| `write_hot_cue()` | PASS — DjmdCue row inserted with correct Kind=1, Color=255, ColorTableIndex=22 |
| `python main.py <track_id>` | PASS — full pipeline executes, all stages print output |
| Rekordbox reopen verification | PASS — hot cue A visible at bar 0 on processed track (human-verified) |

---

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Hot cue A placed at bar 0, not at detected onset position**

- **Found during:** Task 2 / checkpoint verification
- **Issue:** The plan specified `onset_ms` (the detected energy onset) as the `position_ms` argument to `safe_write_sequence`. However, the project design intent (STATE.md decisions: "Hot cue A = bar 0") requires hot cue A to be a fixed track-start anchor, not the detected drop. Writing it at the onset position contradicted the intended cue layout.
- **Fix:** Changed `main.py` to compute `bar0_ms = int(bar_times_s[0] * 1000)` and pass that to `safe_write_sequence`. The onset detection result is still printed to console (informational) but not used as the cue position.
- **Files modified:** `main.py`
- **Commit:** `d29afd9`

---

## Known Stubs

None. Both modules are fully implemented and verified against live Rekordbox 7.2.3 data.

---

## Threat Flags

None. No new network endpoints, auth paths, or schema changes beyond what the plan's threat model covers. All T-01-xx mitigations are implemented:

- T-01-01: psutil process guard + backup via shutil.copy2 + pyrekordbox commit() second guard layer
- T-01-02: SQLAlchemy session transaction — commit failure leaves no persisted rows; backup exists for recovery
- T-01-04: backup_master_db() re-raises on copy failure; safe_write_sequence() calls backup BEFORE write
- T-01-05: track_id passed via ORM parameterized query (get_content(ID=track_id)); no raw SQL interpolation

---

## Commits

| Hash | Message |
|------|---------|
| `dac5882` | feat(01-02): add writer.py — process guard, backup, and hot cue write |
| `38ad51b` | feat(01-02): add main.py — full CLI entry point wiring all pipeline modules |
| `d29afd9` | fix(01-02): hot cue A placed at bar 0, not onset position |

---

## Self-Check: PASSED

- `writer.py` exists: FOUND
- `main.py` exists: FOUND
- Commit `dac5882` exists: FOUND
- Commit `38ad51b` exists: FOUND
- Commit `d29afd9` exists: FOUND
- Human checkpoint APPROVED: confirmed
