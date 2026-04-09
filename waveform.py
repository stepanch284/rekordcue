"""
waveform.py — ANLZ file parsing for RekordCue.

Provides:
  get_pwav_amplitudes()  — extract the 400-sample PWAV amplitude array and track length
  get_beat_grid()        — extract bar start times (seconds) and BPM from PQTZ tag
  get_pssi_sections()    — extract phrase sections from PSSI tag in .EXT file

PSSI kind values (Rekordbox phrase analysis):
  1 = Intro
  2 = Up (Drop / high energy)
  3 = Down (Breakdown / low energy)
  5 = Verse (mid energy)
  6 = Outro

CRITICAL (pyrekordbox 0.4.4 bug):
  Never call len(anlz) or anlz.keys() — triggers infinite recursion.
  Always use anlz.tag_types (property) or anlz.tags (list) for tag presence checks.
"""

from pathlib import Path

import numpy as np
from pyrekordbox import AnlzFile

PSSI_INTRO = 1
PSSI_UP = 2      # Drop / high energy
PSSI_DOWN = 3    # Breakdown / low energy
PSSI_VERSE = 5   # Mid energy
PSSI_OUTRO = 6


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

    try:
        anlz = AnlzFile.parse_file(dat_path)
    except Exception as exc:
        raise ValueError(
            f"ANLZ DAT file is malformed or truncated for track {content.ID} "
            f"({dat_path}): {exc}"
        ) from exc

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
        Tuple of (bar_times_s, avg_bpm, all_beat_times_s) where:
          bar_times_s      — numpy array of bar-1 start times in SECONDS
          avg_bpm          — track BPM as float
          all_beat_times_s — numpy array of ALL beat times in SECONDS (needed for PSSI lookup)

    Raises:
        FileNotFoundError: If the .DAT file cannot be located or does not exist.
        ValueError:        If the PQTZ tag is absent from the .DAT file.
    """
    dat_path = db.get_anlz_path(content, 'DAT')
    if dat_path is None or not Path(dat_path).exists():
        raise FileNotFoundError(
            f"No DAT ANLZ file for track {content.ID}: {dat_path}"
        )

    try:
        anlz = AnlzFile.parse_file(dat_path)
    except Exception as exc:
        raise ValueError(
            f"ANLZ DAT file is malformed or truncated for track {content.ID} "
            f"({dat_path}): {exc}"
        ) from exc

    # CRITICAL: do NOT call len(anlz) or anlz.keys() — infinite recursion in 0.4.4
    if 'PQTZ' not in anlz.tag_types:
        raise ValueError(f"No PQTZ tag in ANLZ file: {dat_path}")

    pqtz = anlz.get_tag('PQTZ')

    times = pqtz.times   # numpy array of ALL beat times IN SECONDS
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
    return bar_times_s, avg_bpm, times


def get_pssi_sections(db, content, beat_times_s: np.ndarray) -> list:
    """Extract phrase sections from the PSSI tag in a track's ANLZ .EXT file.

    The PSSI tag contains Rekordbox's own phrase analysis. Each entry has:
      - beat: absolute beat number (1-based) where this phrase starts
      - kind: phrase type (1=Intro, 2=Up/Drop, 3=Down/Breakdown, 5=Verse, 6=Outro)

    Beat number is converted to time in seconds via the PQTZ beat_times_s array.

    Args:
        db:           An open Rekordbox6Database instance.
        content:      A DjmdContent ORM row (from get_track()).
        beat_times_s: Numpy array of ALL beat times in seconds from PQTZ
                      (not just bar-1 beats — all beats).

    Returns:
        List of dicts: [{"kind": int, "beat": int, "time_s": float}, ...]
        Sorted by beat. Returns empty list if no PSSI tag or no EXT file.
    """
    ext_path = db.get_anlz_path(content, "EXT")
    if ext_path is None or not Path(ext_path).exists():
        print("[waveform] No EXT file — PSSI unavailable, falling back to energy detection")
        return []

    try:
        anlz = AnlzFile.parse_file(ext_path)
    except Exception as exc:
        print(f"[waveform] EXT file malformed for track {content.ID} ({exc}) — falling back to energy detection")
        return []

    if "PSSI" not in anlz.tag_types:
        print("[waveform] No PSSI tag — phrase analysis not run, falling back to energy detection")
        return []

    pssi = anlz.get_tag("PSSI")
    data = pssi.get()
    entries = data.entries

    sections = []
    for e in entries:
        beat_idx = int(e.beat) - 1  # PSSI beats are 1-based
        if 0 <= beat_idx < len(beat_times_s):
            time_s = float(beat_times_s[beat_idx])
        else:
            # Beat index out of range — estimate from BPM
            time_s = None
        sections.append({"kind": int(e.kind), "beat": int(e.beat), "time_s": time_s})

    sections.sort(key=lambda x: x["beat"])
    print(f"[waveform] PSSI: {len(sections)} phrase sections found")
    for s in sections:
        kind_name = {1: "Intro", 2: "Up/Drop", 3: "Down/Breakdown", 5: "Verse", 6: "Outro"}.get(s["kind"], "Unknown")
        print(f"  beat={s['beat']:4d}  time={s['time_s']:.2f}s  kind={s['kind']} ({kind_name})")

    return sections
