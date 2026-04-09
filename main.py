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

        # Detect sections
        pssi_sections = get_pssi_sections(db, content, all_beat_times_s)
        if pssi_sections:
            sections = detect_sections_from_pssi(pssi_sections)
        else:
            print("[main] No PSSI — using energy fallback for Drop 1 only")
            drop1_s, _ = detect_first_onset(amplitudes, bar_times_s, length_s)
            sections = {"drop1_s": drop1_s, "breakdown_s": None, "drop2_s": None, "outro_s": None}

        # Helper: snap a time in seconds to the nearest bar boundary, return ms
        def snap_to_bar(time_s):
            if time_s is None:
                return None
            diffs = [abs(float(t) - time_s) for t in bar_times_s]
            idx = diffs.index(min(diffs))
            return int(bar_times_s[idx] * 1000)  # type: ignore[arg-type]

        # Bar 0 and bar 16 times in ms
        bar0_ms = int(bar_times_s[0] * 1000)   # type: ignore[arg-type]
        bar16_ms = int(bar_times_s[16] * 1000) if len(bar_times_s) > 16 else None  # type: ignore[arg-type]

        # 8 bars before Drop 1 — find bar index of drop1, subtract 8
        drop1_ms = snap_to_bar(sections["drop1_s"])
        pre_drop_ms = None
        if drop1_ms is not None:
            drop1_bar_idx = min(
                range(len(bar_times_s)),
                key=lambda i: abs(int(bar_times_s[i] * 1000) - drop1_ms)  # type: ignore[arg-type]
            )
            if drop1_bar_idx >= 8:
                pre_drop_ms = int(bar_times_s[drop1_bar_idx - 8] * 1000)  # type: ignore[arg-type]

        breakdown_ms = snap_to_bar(sections["breakdown_s"])
        drop2_ms = snap_to_bar(sections["drop2_s"])
        outro_ms = snap_to_bar(sections["outro_s"])

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
        if pre_drop_ms is not None:
            cues.append((pre_drop_ms, 3))
            print(f"  Cue C (hot)    pre-drop   {pre_drop_ms}ms")

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
