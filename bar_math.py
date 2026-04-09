"""
bar_math.py — Beat grid math for RekordCue.

Pure functions operating on beat grid arrays from waveform.get_beat_grid().
No file I/O here except compute_bar_energies() which reads PWV3/PWAV.

Provides:
  - validate_bpm_range(content) → (bpm_float, is_valid)
  - snap_to_8bar_boundary(position_ms, bar_times_ms) → (snapped_ms, bar_index)
  - compute_bar_energies(db, content, bar_times_s) → np.ndarray
  - _bars_from_amplitude(amp, bar_times_s, track_len_s) → np.ndarray
"""

import numpy as np
from pathlib import Path
from pyrekordbox import AnlzFile

DNB_BPM_MIN = 155.0
DNB_BPM_MAX = 185.0


def validate_bpm_range(content) -> tuple:
    """Check BPM is in DnB range [155, 185].

    Args:
        content: DjmdContent ORM row (BPM stored as integer * 100).

    Returns:
        (bpm_float, is_valid): bpm_float is BPM as float, is_valid is True if in range.
    """
    bpm = content.BPM / 100.0
    is_valid = DNB_BPM_MIN <= bpm <= DNB_BPM_MAX
    return bpm, is_valid


def snap_to_8bar_boundary(position_ms: float, bar_times_ms: np.ndarray) -> tuple:
    """Snap a raw position in ms to the nearest 8-bar boundary.

    Args:
        position_ms:   Raw detection position in milliseconds.
        bar_times_ms:  Bar start times in ms (bar_times_s * 1000 from get_beat_grid).

    Returns:
        (snapped_ms, bar_index) where bar_index is a multiple of 8.
    """
    diffs = np.abs(bar_times_ms - position_ms)
    nearest_bar_idx = int(np.argmin(diffs))
    eight_bar_idx = round(nearest_bar_idx / 8) * 8
    eight_bar_idx = min(max(eight_bar_idx, 0), len(bar_times_ms) - 1)
    return int(bar_times_ms[eight_bar_idx]), eight_bar_idx


def compute_bar_energies(db, content, bar_times_s: np.ndarray) -> np.ndarray:
    """Compute mean amplitude per bar using PWV3 (preferred) or PWAV (fallback).

    PWV3 from .EXT: ~150 samples/sec → 207 samples/bar at 174 BPM (good signal).
    PWAV from .DAT: 400 total samples → ~2 samples/bar at 174 BPM (very coarse).

    Args:
        db:          Open Rekordbox6Database instance.
        content:     DjmdContent ORM row.
        bar_times_s: Bar start times in seconds from get_beat_grid().

    Returns:
        Float64 array of shape (n_bars,), values in [0, 31].

    Raises:
        ValueError: If neither PWV3 nor PWAV is available.
    """
    track_len_s = float(content.Length)

    # Try PWV3 first (high resolution: ~150 samples/sec)
    ext_path = db.get_anlz_path(content, 'EXT')
    if ext_path and Path(ext_path).exists():
        try:
            anlz_ext = AnlzFile.parse_file(ext_path)
            # CRITICAL: use tag_types property, never call len(anlz) or anlz.keys()
            if 'PWV3' in anlz_ext.tag_types:
                pwv3 = anlz_ext.get_tag('PWV3')
                amp = pwv3.get()[0].astype(float)  # shape: (N,)
                return _bars_from_amplitude(amp, bar_times_s, track_len_s)
        except Exception:
            pass  # fall through to PWAV

    # Fallback: PWAV (400 samples — coarse, but available)
    dat_path = db.get_anlz_path(content, 'DAT')
    if dat_path and Path(dat_path).exists():
        try:
            anlz = AnlzFile.parse_file(dat_path)
            if 'PWAV' in anlz.tag_types:
                pwav = anlz.get_tag('PWAV')
                amp = pwav.get()[0].astype(float)
                return _bars_from_amplitude(amp, bar_times_s, track_len_s)
        except Exception:
            pass

    raise ValueError(f"No waveform data available for track {content.ID}")


def _bars_from_amplitude(amp: np.ndarray, bar_times_s: np.ndarray,
                         track_len_s: float) -> np.ndarray:
    """Compute mean amplitude per bar window.

    Args:
        amp:          Amplitude array (arbitrary length).
        bar_times_s:  Bar start times in seconds.
        track_len_s:  Total track length in seconds.

    Returns:
        Float64 array of shape (n_bars,) with mean energy per bar.
    """
    n = len(amp)
    energies = np.zeros(len(bar_times_s), dtype=np.float64)
    for i in range(len(bar_times_s)):
        idx_start = int(bar_times_s[i] / track_len_s * n)
        idx_end = int(bar_times_s[i + 1] / track_len_s * n) if i + 1 < len(bar_times_s) else n
        window = amp[idx_start:idx_end]
        energies[i] = float(np.mean(window)) if len(window) > 0 else 0.0
    return energies
