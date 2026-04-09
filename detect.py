"""
detect.py — Section detection for RekordCue.

Primary path: PSSI phrase analysis from Rekordbox (kind 2 = Drop, kind 3 = Breakdown, kind 6 = Outro).
Fallback: energy onset detection on PWAV waveform data (used only when PSSI unavailable).

PSSI kind values:
  1 = Intro
  2 = Up / Drop (high energy)
  3 = Down / Breakdown (low energy)
  5 = Verse / Mid
  6 = Outro
"""

import numpy as np


def detect_sections_from_pssi(sections: list) -> dict:
    """Detect structural sections from PSSI phrase data.

    Finds the first Drop (kind=2), first Breakdown (kind=3) after that drop,
    second Drop (kind=2) after that breakdown, and Outro (kind=6).

    Args:
        sections: List of dicts from get_pssi_sections():
                  [{"kind": int, "beat": int, "time_s": float}, ...]

    Returns:
        Dict with keys (any can be None if not found):
          "drop1_s"     — time in seconds of first drop
          "breakdown_s" — time in seconds of breakdown before drop 2
          "drop2_s"     — time in seconds of second drop
          "outro_s"     — time in seconds of outro
    """
    result = {"drop1_s": None, "breakdown_s": None, "drop2_s": None, "outro_s": None}

    drop1_beat = None
    breakdown_beat = None

    for s in sections:
        kind = s["kind"]
        beat = s["beat"]
        time_s = s["time_s"]

        if kind == 2 and drop1_beat is None:
            # First Up/Drop
            result["drop1_s"] = time_s
            drop1_beat = beat
            print(f"[detect] Drop 1 at beat {beat} ({time_s:.2f}s) via PSSI")

        elif kind == 3 and drop1_beat is not None and breakdown_beat is None:
            # First Breakdown after Drop 1
            result["breakdown_s"] = time_s
            breakdown_beat = beat
            print(f"[detect] Breakdown at beat {beat} ({time_s:.2f}s) via PSSI")

        elif kind == 2 and breakdown_beat is not None and result["drop2_s"] is None:
            # Second Drop after Breakdown
            result["drop2_s"] = time_s
            print(f"[detect] Drop 2 at beat {beat} ({time_s:.2f}s) via PSSI")

        elif kind == 6 and result["outro_s"] is None:
            result["outro_s"] = time_s
            print(f"[detect] Outro at beat {beat} ({time_s:.2f}s) via PSSI")

    return result


def detect_first_onset(
    amplitudes: np.ndarray,
    bar_times_s: np.ndarray,
    track_length_s: float,
    pwav_len: int = 400,
) -> tuple:
    """Fallback: detect first major energy onset from PWAV data.

    Used only when PSSI is unavailable. Returns (onset_time_s, bar_idx).
    """
    n_bars = len(bar_times_s)

    bar_indices = np.floor(bar_times_s / track_length_s * pwav_len).astype(int)
    bar_indices = np.clip(bar_indices, 0, pwav_len - 1)

    bar_energies = []
    for i in range(n_bars):
        start = int(bar_indices[i])
        end = int(bar_indices[i + 1]) if i + 1 < n_bars else pwav_len
        window = amplitudes[start:end]
        bar_energies.append(float(np.mean(window)) if len(window) > 0 else 0.0)

    bar_energies = np.array(bar_energies)

    nonzero_mask = bar_energies > 0
    if nonzero_mask.any():
        nonzero_energies = bar_energies[nonzero_mask]
        threshold = nonzero_energies.mean() + 0.5 * nonzero_energies.std()
    else:
        threshold = 0.0

    print(f"[detect] Fallback energy detection: threshold={threshold:.3f}")

    onset_bar_index = None
    for i in range(4, n_bars):
        if bar_energies[i] >= threshold:
            onset_bar_index = i
            break

    if onset_bar_index is None:
        onset_bar_index = min(4, n_bars - 1)
        print(f"[detect] No bar exceeded threshold — using fallback bar {onset_bar_index}")

    onset_time_s = float(bar_times_s[onset_bar_index])
    print(f"[detect] Fallback onset at bar {onset_bar_index}, {onset_time_s:.3f}s")

    return onset_time_s, onset_bar_index
