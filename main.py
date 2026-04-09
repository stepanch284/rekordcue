"""
main.py — RekordCue CLI entry point.

Usage:
    python main.py <track_id>

Cue placement spec:
    Hot cue A (kind=1) — bar 0 (always)
    Hot cue B (kind=2) — bar 16 (always)
    Hot cue C (kind=3) — 8 bars before Drop 1 (if Drop 1 is beyond bar 8)
    Memory cue (kind=0) — Drop 1
    Memory cue (kind=0) — Breakdown start
    Memory cue (kind=0) — Drop 2
    Memory cue (kind=0) — Outro start
"""

import sys

from db import open_database, validate_schema, get_track
from waveform import get_pwav_amplitudes, get_beat_grid, get_pssi_sections
from detect import detect_sections_from_pssi, detect_first_onset
from writer import safe_write_all
from bar_math import (
    validate_bpm_range, snap_to_8bar_boundary, compute_bar_energies,
    detect_grid_offset, shift_bar_times, detect_intro_length,
    DNB_BPM_MIN, DNB_BPM_MAX
)


def main():
    if len(sys.argv) != 2:
        print("Usage: python main.py <track_id>")
        sys.exit(1)

    track_id = sys.argv[1]
    db = None

    try:
        db = open_database()
        validate_schema(db)
        print("Schema validated OK")

        content = get_track(db, track_id)

        amplitudes, length_s = get_pwav_amplitudes(db, content)
        bar_times_s, bpm, all_beat_times_s = get_beat_grid(db, content)
        print(f"Beat grid: {len(bar_times_s)} bars, BPM={bpm:.1f}")

        # BPM validation (hard-block per DETECT-08)
        bpm_val, bpm_ok = validate_bpm_range(content)
        if not bpm_ok:
            print(f"WARNING: BPM {bpm_val:.1f} is outside DnB range {DNB_BPM_MIN:.0f}–{DNB_BPM_MAX:.0f}.")
            print(f"         Likely mis-detected BPM. Fix in Rekordbox before placing cues.")
            # Continue with warning (fail-safe per FEATURE_DECISIONS)

        # Convert to ms for offset detection
        bar_times_ms = bar_times_s * 1000.0

        # Detect grid offset (DETECT-10)
        offset_ms = detect_grid_offset(bar_times_ms)
        if offset_ms > 0:
            print(f"[DEBUG] Grid offset detected: bar 0 is at {offset_ms:.0f}ms. Auto-shifting to 0ms.")
            bar_times_ms = shift_bar_times(bar_times_ms, offset_ms)
            bar_times_s = bar_times_ms / 1000.0

        # Compute bar energies (for logging & future use)
        try:
            bar_energies = compute_bar_energies(db, content, bar_times_s)
            print(f"[DEBUG] Bar energies computed: {len(bar_energies)} bars, "
                  f"range [{bar_energies.min():.1f}, {bar_energies.max():.1f}]")
        except ValueError as exc:
            print(f"[DEBUG] Could not compute bar energies: {exc}")
            bar_energies = None

        # Detect sections
        pssi_sections = get_pssi_sections(db, content, all_beat_times_s)
        if pssi_sections:
            sections = detect_sections_from_pssi(pssi_sections)
        else:
            print("[main] No PSSI — using energy fallback for Drop 1 only")
            drop1_s, _ = detect_first_onset(amplitudes, bar_times_s, length_s)
            sections = {"drop1_s": drop1_s, "breakdown_s": None, "drop2_s": None, "outro_s": None}

        # Detect intro length (DETECT-11)
        intro_bars = 16  # default
        if bar_energies is not None:
            intro_bars = detect_intro_length(bar_energies)
            print(f"[DEBUG] Detected intro length: {intro_bars} bars")

        # Snap all section positions to 8-bar boundaries (DETECT-03)
        drop1_ms, drop1_bar = (None, None)
        if sections["drop1_s"] is not None:
            drop1_ms, drop1_bar = snap_to_8bar_boundary(sections["drop1_s"] * 1000.0, bar_times_ms)

        breakdown_ms, breakdown_bar = (None, None)
        if sections["breakdown_s"] is not None:
            breakdown_ms, breakdown_bar = snap_to_8bar_boundary(sections["breakdown_s"] * 1000.0, bar_times_ms)

        drop2_ms, drop2_bar = (None, None)
        if sections["drop2_s"] is not None:
            drop2_ms, drop2_bar = snap_to_8bar_boundary(sections["drop2_s"] * 1000.0, bar_times_ms)

        outro_ms, outro_bar = (None, None)
        if sections["outro_s"] is not None:
            outro_ms, outro_bar = snap_to_8bar_boundary(sections["outro_s"] * 1000.0, bar_times_ms)

        # Hot cue A and B (always at bar 0 and bar 16)
        bar0_ms = int(bar_times_ms[0])
        bar16_ms = int(bar_times_ms[16]) if len(bar_times_ms) > 16 else None

        # Hot cue C: 8 bars before Drop 1, but respect intro length
        hot_cue_c_ms = None
        if drop1_ms is not None and drop1_bar is not None:
            if drop1_bar > 8:  # if drop1 is beyond bar 8
                hot_cue_c_ms = int(bar_times_ms[drop1_bar - 8])
                print(f"[DEBUG] Hot cue C placed at bar {drop1_bar - 8}")
            else:
                print(f"[DEBUG] Hot cue C omitted: Drop 1 at bar {drop1_bar} <= 8")

        # Build cue list — (position_ms, kind)
        # kind: 1=A, 2=B, 3=C, 0=memory
        cues = []

        # Hot cue A — bar 0 (always)
        cues.append((bar0_ms, 1))
        print(f"  Cue A (hot)    bar 0      {bar0_ms}ms")

        # Hot cue B — bar 16 (always)
        if bar16_ms is not None:
            cues.append((bar16_ms, 2))
            print(f"  Cue B (hot)    bar 16     {bar16_ms}ms")

        # Hot cue C — 8 bars before Drop 1
        if hot_cue_c_ms is not None:
            cues.append((hot_cue_c_ms, 3))
            print(f"  Cue C (hot)    pre-drop   {hot_cue_c_ms}ms")



        # Memory cue — Drop 1
        if drop1_ms is not None:
            cues.append((drop1_ms, 0))
            print(f"  Mem cue        Drop 1     {drop1_ms}ms")

        # Memory cue — Breakdown
        if breakdown_ms is not None:
            cues.append((breakdown_ms, 0))
            print(f"  Mem cue        Breakdown  {breakdown_ms}ms")

        # Memory cue — Drop 2
        if drop2_ms is not None:
            cues.append((drop2_ms, 0))
            print(f"  Mem cue        Drop 2     {drop2_ms}ms")

        # Memory cue — Outro
        if outro_ms is not None:
            cues.append((outro_ms, 0))
            print(f"  Mem cue        Outro      {outro_ms}ms")

        print(f"\nWriting {len(cues)} cues...")
        safe_write_all(db, content, cues)
        print("Done.")

    except FileNotFoundError as exc:
        print(f"WARNING: Track has no ANLZ analysis data — skipping. ({exc})")
        sys.exit(0)
    except ValueError as exc:
        print(f"WARNING: ANLZ file malformed or incomplete — skipping. ({exc})")
        sys.exit(0)
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
