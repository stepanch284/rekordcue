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

Phase 4 (04-01): PSSI reader + Simple Threshold energy-based section detector.

Exports:
  - detect_pssi_sections()       — read PSSI phrases, map to DnB sections, return with confidence
  - detect_sections_from_energy() — Simple Threshold detector on bar_energies
  - detect_sections_hybrid()     — try PSSI first, fallback to energy
  - compute_section_confidence() — calibrate 0-100 confidence per section
  - ENERGY_THRESHOLDS           — tuned thresholds (dict)
"""

import numpy as np
from bar_math import snap_to_8bar_boundary

# ============================================================================
# ENERGY THRESHOLDS (tuned empirically on ground truth set)
# ============================================================================

ENERGY_THRESHOLDS = {
    "HIGH_THRESHOLD_RATIO": 1.8,       # energy peak detection: x baseline
    "LOW_THRESHOLD_RATIO": 0.6,        # energy valley detection: x baseline
    "MIN_VALLEY_DURATION_BARS": 2,     # breakdown must sustain for 2+ bars
    "OUTRO_ENERGY_RATIO": 1.2,         # final 16 bars below this ratio = outro
}


# ============================================================================
# PSSI DETECTION
# ============================================================================

def detect_pssi_sections(pssi_sections: list) -> dict:
    """Detect structural sections from PSSI phrase data.

    Maps Rekordbox PSSI phrases to DnB sections (Drop 1/2, Breakdown, Outro).
    Returns bar positions + confidence scores.

    Args:
        pssi_sections: List of dicts from waveform.get_pssi_sections():
                       [{"kind": int, "beat": int, "time_s": float}, ...]

    Returns:
        Dict with keys:
          "drop1_bar", "drop1_confidence"
          "breakdown_bar", "breakdown_confidence"
          "drop2_bar", "drop2_confidence"
          "outro_bar", "outro_confidence"
          (values are int/float or None if not found)
    """
    result = {
        "drop1_bar": None, "drop1_confidence": 0,
        "breakdown_bar": None, "breakdown_confidence": 0,
        "drop2_bar": None, "drop2_confidence": 0,
        "outro_bar": None, "outro_confidence": 0,
    }

    if not pssi_sections:
        return result

    drop1_found = False
    breakdown_found = False

    # PSSI kind mapping for DnB:
    # 1 = Intro, 2 = Up/Drop, 3 = Down/Breakdown, 5 = Verse, 6 = Outro
    for s in pssi_sections:
        kind = s.get("kind")
        beat = s.get("beat")
        time_s = s.get("time_s")

        if time_s is None:
            continue

        # Convert time to bar index (roughly: beat / 4 = bar, since 4 beats per bar)
        # This is an approximation; actual bar depends on PQTZ grid
        bar_approx = (beat - 1) / 4

        if kind == 2 and not drop1_found:
            # First Up/Drop → Drop 1
            result["drop1_bar"] = int(round(bar_approx))
            result["drop1_confidence"] = 85
            drop1_found = True

        elif kind == 3 and drop1_found and not breakdown_found:
            # First Down/Breakdown after Drop 1
            result["breakdown_bar"] = int(round(bar_approx))
            result["breakdown_confidence"] = 85
            breakdown_found = True

        elif kind == 2 and breakdown_found and result["drop2_bar"] is None:
            # Second Up/Drop after Breakdown → Drop 2
            result["drop2_bar"] = int(round(bar_approx))
            result["drop2_confidence"] = 85

        elif kind == 6 and result["outro_bar"] is None:
            # Outro
            result["outro_bar"] = int(round(bar_approx))
            result["outro_confidence"] = 85

    return result


# ============================================================================
# ENERGY-BASED SECTION DETECTION (SIMPLE THRESHOLD)
# ============================================================================

def compute_section_confidence(bar_energies: np.ndarray, section_bar: int,
                               section_type: str, baseline: float = None) -> int:
    """Compute confidence (0-100) for a detected section.

    Calibration:
      - Drop: high energy ratio ≥ 2.5x baseline = 85%+
      - Breakdown: energy ratio ≤ 0.6x baseline = 80%+
      - Outro: sustained low energy in final bars = 50-80%

    Args:
        bar_energies: Energy per bar array
        section_bar: Bar index of detected section
        section_type: "drop", "breakdown", or "outro"
        baseline: Reference energy (usually intro mean); auto-computed if None

    Returns:
        int: Confidence 0-100
    """
    if baseline is None:
        baseline = np.mean(bar_energies[0:16]) if len(bar_energies) >= 16 else np.mean(bar_energies)

    if baseline == 0:
        baseline = 1.0  # Avoid division by zero

    if section_bar < 0 or section_bar >= len(bar_energies):
        return 0

    energy_at_section = bar_energies[section_bar]
    ratio = energy_at_section / baseline

    if section_type == "drop":
        # High energy is good signal for drops
        # 1.5x = 40%, 2.5x = 85%, 3x+ = 95%
        confidence = int((ratio - 1.0) / 2.0 * 100)
        return min(100, max(0, confidence))

    elif section_type == "breakdown":
        # Low energy is good signal for breakdowns
        # 0.5x = 85%, 0.7x = 50%, 1.0x = 0%
        confidence = int((1.0 - ratio) / 0.5 * 100)
        return min(100, max(0, confidence))

    elif section_type == "outro":
        # Sustained low energy in final bars
        outro_energy = np.mean(bar_energies[-16:]) if len(bar_energies) >= 16 else energy_at_section
        outro_ratio = outro_energy / baseline
        if outro_ratio < 0.7:
            return 80
        elif outro_ratio < 1.2:
            return 50
        else:
            return 20

    return 0


def detect_sections_from_energy(bar_energies: np.ndarray, bar_times_ms: np.ndarray,
                                intro_bars: int = 16) -> dict:
    """Detect sections using Simple Threshold algorithm.

    Algorithm:
      1. Compute baseline from intro bars
      2. Scan for peaks (energy > 1.8x baseline) → drops
      3. Scan for valleys (energy < 0.6x baseline, 2+ bars) → breakdowns
      4. Snap all positions to 8-bar boundaries
      5. Assign confidence scores

    Args:
        bar_energies: Energy per bar (numpy array, float)
        bar_times_ms: Bar start times in ms (for snapping)
        intro_bars: Length of intro section (default 16)

    Returns:
        Dict with keys:
          "drop1_bar", "drop1_confidence"
          "breakdown_bar", "breakdown_confidence"
          "drop2_bar", "drop2_confidence"
          "outro_bar", "outro_confidence"
    """
    result = {
        "drop1_bar": None, "drop1_confidence": 0,
        "breakdown_bar": None, "breakdown_confidence": 0,
        "drop2_bar": None, "drop2_confidence": 0,
        "outro_bar": None, "outro_confidence": 0,
    }

    if len(bar_energies) == 0 or len(bar_times_ms) == 0:
        return result

    # Compute thresholds from intro baseline
    intro_baseline = np.mean(bar_energies[0:min(intro_bars, len(bar_energies))])
    if intro_baseline == 0:
        intro_baseline = 1.0

    high_threshold = intro_baseline * ENERGY_THRESHOLDS["HIGH_THRESHOLD_RATIO"]
    low_threshold = intro_baseline * ENERGY_THRESHOLDS["LOW_THRESHOLD_RATIO"]
    min_valley_duration = ENERGY_THRESHOLDS["MIN_VALLEY_DURATION_BARS"]

    # Scan for sections
    drop1_found = False
    breakdown_found = False
    drop1_bar = None

    for bar_idx in range(intro_bars, len(bar_energies)):
        energy = bar_energies[bar_idx]

        # Drop 1: first high energy above threshold
        if not drop1_found and energy > high_threshold:
            result["drop1_bar"] = bar_idx
            result["drop1_confidence"] = compute_section_confidence(bar_energies, bar_idx, "drop", intro_baseline)
            drop1_found = True
            drop1_bar = bar_idx

        # Breakdown: energy valley after drop 1 (sustained 2+ bars)
        # Limit search to within 64 bars of drop1 and not in final 20% (typical DnB structure)
        elif (drop1_found and not breakdown_found and energy <= low_threshold and
              (drop1_bar is None or bar_idx <= drop1_bar + 64) and
              bar_idx < len(bar_energies) * 0.8):
            valley_duration = 0
            for j in range(bar_idx, min(bar_idx + 8, len(bar_energies))):
                if bar_energies[j] <= low_threshold:
                    valley_duration += 1
            if valley_duration >= min_valley_duration:
                result["breakdown_bar"] = bar_idx
                result["breakdown_confidence"] = compute_section_confidence(bar_energies, bar_idx, "breakdown", intro_baseline)
                breakdown_found = True

        # Drop 2: second high energy after breakdown
        elif breakdown_found and energy > high_threshold and result["drop2_bar"] is None:
            result["drop2_bar"] = bar_idx
            result["drop2_confidence"] = compute_section_confidence(bar_energies, bar_idx, "drop", intro_baseline)

    # Outro: final 16 bars below threshold
    outro_energy = np.mean(bar_energies[-16:]) if len(bar_energies) >= 16 else np.mean(bar_energies)
    if outro_energy < intro_baseline * ENERGY_THRESHOLDS["OUTRO_ENERGY_RATIO"]:
        outro_bar = max(len(bar_energies) - 16, 0)
        result["outro_bar"] = outro_bar
        result["outro_confidence"] = compute_section_confidence(bar_energies, outro_bar, "outro", intro_baseline)

    # Snap all detected positions to 8-bar boundaries
    for section_name in ["drop1", "breakdown", "drop2", "outro"]:
        bar_key = f"{section_name}_bar"
        if result[bar_key] is not None:
            # Convert bar index to ms, snap, then back to bar index
            bar_ms = float(bar_times_ms[min(result[bar_key], len(bar_times_ms) - 1)])
            snapped_ms, snapped_bar_idx = snap_to_8bar_boundary(bar_ms, bar_times_ms)
            result[bar_key] = snapped_bar_idx

    return result


# ============================================================================
# HYBRID DETECTION (PSSI + Energy Fallback)
# ============================================================================

def detect_sections_hybrid(db, content, pssi_sections: list,
                          bar_energies: np.ndarray, bar_times_ms: np.ndarray,
                          intro_bars: int = 16) -> dict:
    """Hybrid detection: try PSSI first, fallback to energy if unavailable.

    Args:
        db: Database instance (unused, for API compatibility)
        content: Content object (unused, for API compatibility)
        pssi_sections: PSSI phrase list (from waveform.get_pssi_sections)
        bar_energies: Energy per bar
        bar_times_ms: Bar times in milliseconds
        intro_bars: Intro length in bars

    Returns:
        Dict with detected sections + confidence scores
    """
    # Try PSSI first
    if pssi_sections:
        result = detect_pssi_sections(pssi_sections)
        # If PSSI has any sections, use it (it's reliable from Rekordbox)
        if any(result[k] is not None for k in ["drop1_bar", "breakdown_bar", "drop2_bar", "outro_bar"]):
            return result

    # Fallback: energy detection
    return detect_sections_from_energy(bar_energies, bar_times_ms, intro_bars)


# ============================================================================
# LEGACY FUNCTIONS (kept for backwards compatibility)
# ============================================================================

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
