"""
detect.py — Energy onset detection on PWAV waveform data for RekordCue.

Provides:
  detect_first_onset() — find the first major energy increase after the intro
                         using per-bar mean amplitude from the 400-sample PWAV array
"""

import numpy as np


def detect_first_onset(
    amplitudes: np.ndarray,
    bar_times_s: np.ndarray,
    track_length_s: float,
    pwav_len: int = 400,
) -> tuple:
    """Detect the first major energy onset bar after the intro.

    Strategy:
      1. Convert bar start times to PWAV indices (fixed 400-sample grid).
      2. Compute mean amplitude per bar window.
      3. Threshold = mean + 0.5 * stdev of non-silent bars.
      4. Return the first bar at index >= 4 that exceeds the threshold.
      5. Fallback to bar 4 (or last bar if track is very short) if none found.

    Args:
        amplitudes:     Float64 numpy array of shape (pwav_len,) — PWAV amplitudes.
        bar_times_s:    Numpy array of bar start times in SECONDS from PQTZ tag.
        track_length_s: Total track duration in seconds (DjmdContent.Length).
        pwav_len:       Number of PWAV samples (always 400 for Rekordbox).

    Returns:
        Tuple of (onset_time_seconds, onset_bar_index) where onset_time_seconds
        is the bar start time in seconds and onset_bar_index is the 0-based bar
        number. Multiply onset_time_seconds by 1000 for DjmdCue.InMsec.
    """
    n_bars = len(bar_times_s)

    # Convert bar start times to PWAV sample indices
    bar_indices = np.floor(bar_times_s / track_length_s * pwav_len).astype(int)
    bar_indices = np.clip(bar_indices, 0, pwav_len - 1)

    # Compute mean amplitude energy per bar
    bar_energies = []
    for i in range(n_bars):
        start = int(bar_indices[i])
        end = int(bar_indices[i + 1]) if i + 1 < n_bars else pwav_len
        window = amplitudes[start:end]
        energy = float(np.mean(window)) if len(window) > 0 else 0.0
        bar_energies.append(energy)

    bar_energies = np.array(bar_energies)

    # Threshold: mean + 0.5 * stdev, computed only on non-silent bars
    # to avoid silence at the start of the track skewing the stats downward
    nonzero_mask = bar_energies > 0
    if nonzero_mask.any():
        nonzero_energies = bar_energies[nonzero_mask]
        threshold = nonzero_energies.mean() + 0.5 * nonzero_energies.std()
    else:
        threshold = 0.0

    print(
        f"[detect] {n_bars} bars, energy threshold: {threshold:.3f} "
        f"(mean={bar_energies.mean():.3f}, std={bar_energies.std():.3f})"
    )

    # Find first bar >= index 4 that exceeds the threshold (skip intro)
    onset_bar_index = None
    for i in range(4, n_bars):
        if bar_energies[i] >= threshold:
            onset_bar_index = i
            break

    # Fallback: bar 4 (or last bar if track has fewer than 5 bars)
    if onset_bar_index is None:
        onset_bar_index = min(4, n_bars - 1)
        print(
            f"[detect] No bar exceeded threshold after bar 4 — "
            f"using fallback bar {onset_bar_index}"
        )

    onset_time_s = float(bar_times_s[onset_bar_index])
    onset_ms = round(onset_time_s * 1000)

    print(
        f"[detect] Onset detected at bar {onset_bar_index}, "
        f"{onset_time_s:.3f}s ({onset_ms}ms)"
    )

    return onset_time_s, onset_bar_index
