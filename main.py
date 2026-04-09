"""
main.py — RekordCue CLI entry point.

Usage:
    python main.py <track_id>

Runs the full read-detect-write pipeline for a single track:
    1. Open Rekordbox master.db
    2. Validate DjmdCue schema
    3. Load track metadata
    4. Parse ANLZ PWAV waveform and PQTZ beat grid
    5. Detect sections via PSSI phrase analysis (falls back to energy detection)
    6. Write hot cue A at bar 0
"""

import sys

from db import open_database, validate_schema, get_track
from waveform import get_pwav_amplitudes, get_beat_grid, get_pssi_sections
from detect import detect_sections_from_pssi, detect_first_onset
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

        # Step 4b: Parse PQTZ beat grid (bar times + all beat times for PSSI lookup)
        bar_times_s, bpm, all_beat_times_s = get_beat_grid(db, content)
        print(f"Beat grid: {len(bar_times_s)} bars, BPM={bpm:.1f}")

        # Step 5: Detect sections — PSSI first, fallback to energy
        pssi_sections = get_pssi_sections(db, content, all_beat_times_s)
        if pssi_sections:
            sections = detect_sections_from_pssi(pssi_sections)
            drop1_s = sections["drop1_s"]
        else:
            print("[main] No PSSI — using energy fallback")
            drop1_s, _ = detect_first_onset(amplitudes, bar_times_s, length_s)

        if drop1_s is not None:
            print(f"Drop 1 at {drop1_s:.3f}s ({int(drop1_s * 1000)}ms)")
        else:
            print("WARNING: Could not detect Drop 1")

        # Step 6: Guard, backup, write hot cue A at bar 0
        bar0_ms = int(bar_times_s[0] * 1000)  # type: ignore[arg-type]
        safe_write_sequence(db, content, bar0_ms)
        print(f"Hot cue A written at bar 0 ({bar0_ms}ms)")

    except RuntimeError as exc:
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
