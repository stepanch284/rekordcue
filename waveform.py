"""
waveform.py — ANLZ file parsing for RekordCue.

Provides:
  get_pwav_amplitudes()  — extract the 400-sample PWAV amplitude array and track length
  get_beat_grid()        — extract bar start times (seconds) and BPM from PQTZ tag

CRITICAL (pyrekordbox 0.4.4 bug):
  Never call len(anlz) or anlz.keys() — triggers infinite recursion.
  Always use anlz.tag_types (property) or anlz.tags (list) for tag presence checks.
"""

from pathlib import Path

import numpy as np
from pyrekordbox import AnlzFile


def get_pwav_amplitudes(db, content) -> tuple:
    """Parse the PWAV waveform tag from a track's ANLZ .DAT file.

    The PWAV tag is a fixed-width 400-sample amplitude thumbnail — always exactly
    400 samples regardless of track duration.
    Index i maps to time: t_seconds = (i / 400) * track_length_s

    Args:
        db:      An open Rekordbox6Database instance.
        content: A DjmdContent ORM row (from get_track()).

    Returns:
        Tuple of (amplitudes, track_length_s) where amplitudes is a float64
        numpy array of shape (400,) and track_length_s is the track duration in seconds.

    Raises:
        FileNotFoundError: If the .DAT file cannot be located or does not exist.
        ValueError:        If the PWAV tag is absent from the .DAT file.
    """
    dat_path = db.get_anlz_path(content, 'DAT')
    if dat_path is None or not Path(dat_path).exists():
        raise FileNotFoundError(
            f"No DAT ANLZ file for track {content.ID}: {dat_path}"
        )

    anlz = AnlzFile.parse_file(dat_path)

    # CRITICAL: do NOT call len(anlz) or anlz.keys() — infinite recursion in 0.4.4
    if 'PWAV' not in anlz.tag_types:
        raise ValueError(f"No PWAV tag in ANLZ file: {dat_path}")

    pwav = anlz.get_tag('PWAV')
    data = pwav.get()  # returns (amplitudes_array, unknown_array), both shape (400,) int8
    amplitudes = data[0].astype(float)

    track_length_s = content.Length  # Length is in SECONDS
    print(
        f"[waveform] PWAV: {len(amplitudes)} samples, "
        f"track length: {track_length_s}s"
    )
    return amplitudes, track_length_s


def get_beat_grid(db, content) -> tuple:
    """Extract bar start times and BPM from the PQTZ beat grid tag in a track's ANLZ file.

    PQTZ times are in SECONDS (not milliseconds). Multiply by 1000 for cue InMsec values.
    Bar starts are where beats == 1 (beat number within the 4/4 bar).

    Args:
        db:      An open Rekordbox6Database instance.
        content: A DjmdContent ORM row (from get_track()).

    Returns:
        Tuple of (bar_times_s, avg_bpm) where bar_times_s is a numpy array of
        bar start times in SECONDS and avg_bpm is the track BPM as a float.

    Raises:
        FileNotFoundError: If the .DAT file cannot be located or does not exist.
        ValueError:        If the PQTZ tag is absent from the .DAT file.
    """
    dat_path = db.get_anlz_path(content, 'DAT')
    if dat_path is None or not Path(dat_path).exists():
        raise FileNotFoundError(
            f"No DAT ANLZ file for track {content.ID}: {dat_path}"
        )

    anlz = AnlzFile.parse_file(dat_path)

    # CRITICAL: do NOT call len(anlz) or anlz.keys() — infinite recursion in 0.4.4
    if 'PQTZ' not in anlz.tag_types:
        raise ValueError(f"No PQTZ tag in ANLZ file: {dat_path}")

    pqtz = anlz.get_tag('PQTZ')

    times = pqtz.times   # numpy array of beat times IN SECONDS
    beats = pqtz.beats   # numpy array: 1, 2, 3, 4 (beat number within bar)
    bpms = pqtz.bpms     # numpy array of BPM at each beat

    # Bar starts are beats where the beat number within the bar is 1
    bar_mask = (beats == 1)
    bar_times_s = times[bar_mask]

    avg_bpm = float(bpms[0])  # assume constant tempo for DnB

    print(
        f"[waveform] Beat grid: {len(bar_times_s)} bars, "
        f"BPM: {avg_bpm:.1f}, first bar at {bar_times_s[0]:.3f}s"
    )
    return bar_times_s, avg_bpm
