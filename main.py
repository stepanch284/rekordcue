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
import numpy as np

from db import open_database, validate_schema, get_track
from waveform import get_pwav_amplitudes, get_beat_grid, get_pssi_sections
from detect import detect_sections_from_pssi, detect_first_onset, detect_sections_hybrid
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

        # Compute bar energies (for logging & section detection)
        try:
            bar_energies = compute_bar_energies(db, content, bar_times_s)
            print(f"[DEBUG] Bar energies computed: {len(bar_energies)} bars, "
                  f"range [{bar_energies.min():.1f}, {bar_energies.max():.1f}]")
        except ValueError as exc:
            print(f"[DEBUG] Could not compute bar energies: {exc}")
            bar_energies = None

        # Detect intro length (DETECT-11)
        intro_bars = 16  # default
        if bar_energies is not None:
            intro_bars = detect_intro_length(bar_energies)
            print(f"[DEBUG] Detected intro length: {intro_bars} bars")

        # Detect sections using hybrid approach (DETECT-04, DETECT-05, DETECT-06, DETECT-07)
        pssi_sections = get_pssi_sections(db, content, all_beat_times_s)
        sections_detected = detect_sections_hybrid(
            db=db,
            content=content,
            pssi_sections=pssi_sections,
            bar_energies=bar_energies if bar_energies is not None else np.zeros(len(bar_times_ms)),
            bar_times_ms=bar_times_ms,
            intro_bars=intro_bars
        )

        print(f"\n[SECTIONS DETECTED]")
        if sections_detected.get('drop1_bar') is not None:
            print(f"  Drop 1:    bar {sections_detected['drop1_bar']:3d} ({sections_detected.get('drop1_confidence', 0):3d}% confidence)")
        else:
            print(f"  Drop 1:    NOT DETECTED")

        if sections_detected.get('breakdown_bar') is not None:
            print(f"  Breakdown: bar {sections_detected['breakdown_bar']:3d} ({sections_detected.get('breakdown_confidence', 0):3d}% confidence)")
        else:
            print(f"  Breakdown: NOT DETECTED")

        if sections_detected.get('drop2_bar') is not None:
            print(f"  Drop 2:    bar {sections_detected['drop2_bar']:3d} ({sections_detected.get('drop2_confidence', 0):3d}% confidence)")
        else:
            print(f"  Drop 2:    NOT DETECTED")

        if sections_detected.get('outro_bar') is not None:
            print(f"  Outro:     bar {sections_detected['outro_bar']:3d} ({sections_detected.get('outro_confidence', 0):3d}% confidence)")
        else:
            print(f"  Outro:     NOT DETECTED")

        # Warn on low-confidence sections (DETECT-12 compliance)
        for section_name in ['drop1', 'breakdown', 'drop2', 'outro']:
            conf_key = f'{section_name}_confidence'
            bar_key = f'{section_name}_bar'
            if sections_detected.get(bar_key) is not None:
                confidence = sections_detected.get(conf_key, 0)
                if confidence < 50:
                    print(f"  WARNING: {section_name.upper()} confidence {confidence}% — manual review recommended")

        # Extract bar indices for cue placement
        drop1_bar = sections_detected.get('drop1_bar')
        breakdown_bar = sections_detected.get('breakdown_bar')
        drop2_bar = sections_detected.get('drop2_bar')
        outro_bar = sections_detected.get('outro_bar')

        # Convert bar indices to milliseconds
        drop1_ms = int(bar_times_ms[drop1_bar]) if drop1_bar is not None else None
        breakdown_ms = int(bar_times_ms[breakdown_bar]) if breakdown_bar is not None else None
        drop2_ms = int(bar_times_ms[drop2_bar]) if drop2_bar is not None else None
        outro_ms = int(bar_times_ms[outro_bar]) if outro_bar is not None else None

        # Hot cue A and B (always at bar 0 and bar 16)
        bar0_ms = int(bar_times_ms[0])
        bar16_ms = int(bar_times_ms[16]) if len(bar_times_ms) > 16 else None

        # Hot cue C: 8 bars before Drop 1, but respect intro length
        hot_cue_c_ms = None
        if drop1_bar is not None:
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
