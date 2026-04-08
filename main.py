"""
main.py — RekordCue CLI entry point.

Usage:
    python main.py <track_id>

Runs the full read-detect-write pipeline for a single track:
    1. Open Rekordbox master.db
    2. Validate DjmdCue schema
    3. Load track metadata
    4. Parse ANLZ PWAV waveform (400 samples) and PQTZ beat grid
    5. Detect first major energy onset
    6. Write one hot cue (slot A) to DjmdCue via safe_write_sequence
"""

import sys

from db import open_database, validate_schema, get_track
from waveform import get_pwav_amplitudes, get_beat_grid
from detect import detect_first_onset
from writer import safe_write_sequence


def main():
    if len(sys.argv) != 2:
        print("Usage: python main.py <track_id>")
        sys.exit(1)

    track_id = sys.argv[1]
    db = None

    try:
        # Step 1: Open database
        db = open_database()

        # Step 2: Validate schema — raises RuntimeError on mismatch
        validate_schema(db)
        print("Schema validated OK")

        # Step 3: Load track
        content = get_track(db, track_id)

        # Step 4a: Parse PWAV waveform
        amplitudes, length_s = get_pwav_amplitudes(db, content)
        print(f"PWAV loaded: {len(amplitudes)} samples")

        # Step 4b: Parse PQTZ beat grid
        bar_times_s, bpm = get_beat_grid(db, content)
        print(f"Beat grid: {len(bar_times_s)} bars, BPM={bpm:.1f}")

        # Step 5: Detect first energy onset
        onset_s, bar_idx = detect_first_onset(amplitudes, bar_times_s, length_s)
        onset_ms = round(onset_s * 1000)
        print(f"Detected onset at bar {bar_idx}, {onset_s:.3f}s ({onset_ms}ms)")

        # Step 6: Guard, backup, write
        safe_write_sequence(db, content, onset_ms)
        print(f"Hot cue A written at {onset_ms}ms")

    except RuntimeError as exc:
        # Covers: process guard blocked, schema mismatch, backup failure
        print(f"ERROR: {exc}")
        sys.exit(1)
    except Exception as exc:
        print(f"UNEXPECTED ERROR: {exc}")
        sys.exit(1)
    finally:
        if db is not None:
            db.close()


if __name__ == '__main__':
    main()
