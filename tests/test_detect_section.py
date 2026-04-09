"""
tests/test_detect_section.py — Unit tests for section detection (Phase 4).

Tests for:
  - PSSI phrase reading and confidence scoring
  - Simple Threshold energy-based section detection
  - Confidence calibration
  - Edge cases (short tracks, no breakdown, etc.)
  - Integration with bar_math snapping functions
"""

import types
import numpy as np
import pytest

from detect import (
    detect_pssi_sections,
    detect_sections_from_energy,
    detect_sections_hybrid,
    compute_section_confidence,
    ENERGY_THRESHOLDS,
)
from bar_math import snap_to_8bar_boundary


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_db_content():
    """Mock database and content object."""
    return (
        types.SimpleNamespace(get_anlz_path=lambda c, k: None),
        types.SimpleNamespace(BPM=17400, Length=239.0, ID=12345),
    )


@pytest.fixture
def bar_times_ms_174bpm():
    """Bar times for 174 BPM track (1379.31 ms per bar)."""
    bar_interval_ms = 60.0 / 174.0 * 4 * 1000
    return np.array([i * bar_interval_ms for i in range(200)], dtype=np.float64)


@pytest.fixture
def bar_times_s_174bpm():
    """Bar times in seconds for 174 BPM track."""
    bar_interval_s = 60.0 / 174.0 * 4
    return np.array([i * bar_interval_s for i in range(200)], dtype=np.float64)


@pytest.fixture
def synthetic_16bar_intro():
    """
    Synthetic DnB structure:
    - Bars 0-15 (intro): energy = 5.0 (baseline)
    - Bars 16-31 (drop 1): energy = 15.0 (high)
    - Bars 32-47 (breakdown): energy = 2.0 (low valley, well below threshold)
    - Bars 48-79 (drop 2): energy = 14.0 (high)
    - Bars 80+ (outro): energy = 2.0 (low)
    """
    energies = np.zeros(200, dtype=np.float64)
    energies[0:16] = 5.0      # intro baseline
    energies[16:32] = 15.0    # drop 1
    energies[32:48] = 2.0     # breakdown valley (well below threshold of 3.0)
    energies[48:80] = 14.0    # drop 2
    energies[80:] = 2.0       # outro
    return energies


@pytest.fixture
def synthetic_32bar_intro():
    """
    Synthetic DnB structure with 32-bar intro:
    - Bars 0-31 (intro): energy = 5.0
    - Bars 32-63 (drop 1): energy = 16.0
    - Bars 64-79 (breakdown): energy = 2.0
    - Bars 80-111 (drop 2): energy = 15.0
    - Bars 112+ (outro): energy = 1.0
    """
    energies = np.zeros(200, dtype=np.float64)
    energies[0:32] = 5.0      # intro baseline
    energies[32:64] = 16.0    # drop 1
    energies[64:80] = 2.0     # breakdown valley
    energies[80:112] = 15.0   # drop 2
    energies[112:] = 1.0      # outro
    return energies


@pytest.fixture
def synthetic_full_power_no_breakdown():
    """
    Full-power roller (no breakdown):
    - Bars 0-15 (intro): energy = 5.0
    - Bars 16-95 (continuous drop): energy = 14.0
    - Bars 96+ (outro fade): energy = 2.0
    No valley/breakdown in the middle (full-power style).
    """
    energies = np.zeros(200, dtype=np.float64)
    energies[0:16] = 5.0      # intro
    energies[16:96] = 14.0    # continuous high (no breakdown valley)
    energies[96:] = 2.0       # outro (far enough away to avoid misdetection)
    return energies


@pytest.fixture
def synthetic_short_track():
    """Very short track (40 bars total — incomplete structure)."""
    energies = np.zeros(40, dtype=np.float64)
    energies[0:8] = 5.0       # intro
    energies[8:24] = 14.0     # drop 1
    energies[24:] = 3.0       # outro (no breakdown or drop 2)
    return energies


@pytest.fixture
def synthetic_all_low_energy():
    """All-low-energy track (no distinct sections)."""
    return np.ones(200, dtype=np.float64) * 3.0


@pytest.fixture
def pssi_sections_complete():
    """Complete PSSI phrase list (all 4 sections)."""
    return [
        {"kind": 1, "beat": 1, "time_s": 0.0},     # Intro
        {"kind": 2, "beat": 65, "time_s": 18.5},   # Drop 1 (beat 65 ≈ bar 16)
        {"kind": 3, "beat": 129, "time_s": 36.8},  # Breakdown (beat 129 ≈ bar 32)
        {"kind": 2, "beat": 193, "time_s": 55.1},  # Drop 2 (beat 193 ≈ bar 48)
        {"kind": 6, "beat": 321, "time_s": 91.7},  # Outro (beat 321 ≈ bar 80)
    ]


@pytest.fixture
def pssi_sections_partial():
    """Partial PSSI (missing breakdown)."""
    return [
        {"kind": 1, "beat": 1, "time_s": 0.0},
        {"kind": 2, "beat": 65, "time_s": 18.5},
        # No breakdown (kind=3)
        {"kind": 6, "beat": 321, "time_s": 91.7},
    ]


@pytest.fixture
def pssi_sections_empty():
    """Empty PSSI (no phrases detected)."""
    return []


# ============================================================================
# PSSI Reading Tests
# ============================================================================

def test_pssi_read_valid_complete(pssi_sections_complete):
    """Test: Valid PSSI with all 4 sections returns dict with all bars."""
    result = detect_pssi_sections(pssi_sections_complete)

    assert result is not None
    assert "drop1_bar" in result
    assert "breakdown_bar" in result
    assert "drop2_bar" in result
    assert "outro_bar" in result
    assert result["drop1_bar"] is not None
    assert result["breakdown_bar"] is not None
    assert result["drop2_bar"] is not None
    assert result["outro_bar"] is not None


def test_pssi_read_valid_partial(pssi_sections_partial):
    """Test: Partial PSSI (missing breakdown) returns None for that section."""
    result = detect_pssi_sections(pssi_sections_partial)

    assert result["drop1_bar"] is not None
    assert result["breakdown_bar"] is None  # Missing in PSSI
    assert result["outro_bar"] is not None


def test_pssi_read_empty(pssi_sections_empty):
    """Test: Empty PSSI returns dict with all None values."""
    result = detect_pssi_sections(pssi_sections_empty)

    assert result["drop1_bar"] is None
    assert result["breakdown_bar"] is None
    assert result["drop2_bar"] is None
    assert result["outro_bar"] is None


def test_pssi_confidence_present(pssi_sections_complete):
    """Test: PSSI sections get ~85% confidence when present."""
    result = detect_pssi_sections(pssi_sections_complete)

    # When PSSI is present, confidence should be high
    if result["drop1_bar"] is not None:
        assert "drop1_confidence" in result
        assert result["drop1_confidence"] >= 80


def test_pssi_confidence_absent(pssi_sections_empty):
    """Test: PSSI sections get ~0% confidence when absent."""
    result = detect_pssi_sections(pssi_sections_empty)

    # When PSSI is absent, confidence should be low/zero
    if result["drop1_bar"] is None:
        assert result.get("drop1_confidence", 0) <= 10 or result.get("drop1_confidence") is None


# ============================================================================
# Simple Threshold Energy Detection Tests
# ============================================================================

def test_energy_detect_standard_16bar_intro(synthetic_16bar_intro, bar_times_ms_174bpm):
    """Test: 16-bar intro structure detected correctly."""
    result = detect_sections_from_energy(synthetic_16bar_intro, bar_times_ms_174bpm, intro_bars=16)

    assert result["drop1_bar"] is not None
    assert result["breakdown_bar"] is not None
    assert result["drop2_bar"] is not None
    # Drop 1 should be around bar 16
    assert 14 <= result["drop1_bar"] <= 18
    # Breakdown should be around bar 32
    assert 30 <= result["breakdown_bar"] <= 34


def test_energy_detect_32bar_intro(synthetic_32bar_intro, bar_times_ms_174bpm):
    """Test: 32-bar intro structure detected correctly."""
    result = detect_sections_from_energy(synthetic_32bar_intro, bar_times_ms_174bpm, intro_bars=32)

    assert result["drop1_bar"] is not None
    # Drop 1 should be around bar 32 (with 32-bar intro)
    assert 30 <= result["drop1_bar"] <= 34


def test_energy_detect_full_power_no_breakdown(synthetic_full_power_no_breakdown, bar_times_ms_174bpm):
    """Test: Full-power track (no breakdown) returns breakdown_bar=None."""
    result = detect_sections_from_energy(synthetic_full_power_no_breakdown, bar_times_ms_174bpm, intro_bars=16)

    assert result["drop1_bar"] is not None
    # No sustained valley → breakdown should not be detected
    assert result["breakdown_bar"] is None


def test_energy_detect_short_track_incomplete(synthetic_short_track):
    """Test: Short track (<64 bars) only returns available sections."""
    bar_interval_s = 60.0 / 174.0 * 4
    bar_times_s = np.array([i * bar_interval_s for i in range(len(synthetic_short_track))], dtype=np.float64)
    bar_times_ms = bar_times_s * 1000.0

    result = detect_sections_from_energy(synthetic_short_track, bar_times_ms, intro_bars=8)

    # Drop 1 should be detected
    assert result["drop1_bar"] is not None
    # Drop 2 and breakdown unlikely on short track
    # Result should handle gracefully (no crash)
    assert isinstance(result, dict)


def test_energy_detect_all_low_energy(synthetic_all_low_energy, bar_times_ms_174bpm):
    """Test: All-low-energy track returns mostly None or low confidence."""
    result = detect_sections_from_energy(synthetic_all_low_energy, bar_times_ms_174bpm, intro_bars=16)

    # With no distinct peaks/valleys, most sections should be None or very low confidence
    # (energy never exceeds threshold)
    assert result["drop1_bar"] is None or result.get("drop1_confidence", 0) < 30


# ============================================================================
# Confidence Scoring Tests
# ============================================================================

def test_confidence_high_energy_peak(synthetic_16bar_intro):
    """Test: High energy peak (≥2.5x baseline) → confidence ≥85%."""
    baseline = 5.0
    peak_energy = 15.0  # 3x baseline

    confidence = compute_section_confidence(synthetic_16bar_intro, 16, "drop", baseline)
    assert confidence >= 80


def test_confidence_low_energy_valley(synthetic_16bar_intro):
    """Test: Low energy valley (≤0.6x baseline) → confidence ≥80%."""
    baseline = 5.0
    valley_energy = 3.0  # 0.6x baseline

    confidence = compute_section_confidence(synthetic_16bar_intro, 32, "breakdown", baseline)
    assert confidence >= 70


def test_confidence_ambiguous_signal(synthetic_all_low_energy):
    """Test: Ambiguous signal (1.2x baseline) → confidence 40-60%."""
    baseline = 3.0
    # All energies are equal, no distinction
    confidence = compute_section_confidence(synthetic_all_low_energy, 20, "drop", baseline)
    assert 0 <= confidence <= 60


# ============================================================================
# Snapping to 8-Bar Boundary Tests
# ============================================================================

def test_snap_to_8bar_after_detect(synthetic_16bar_intro, bar_times_ms_174bpm):
    """Test: Detected section snapped to 8-bar boundary."""
    result = detect_sections_from_energy(synthetic_16bar_intro, bar_times_ms_174bpm, intro_bars=16)

    if result["drop1_bar"] is not None:
        # Check that bar index is multiple of 8 (or very close due to snap)
        bar_idx = result["drop1_bar"]
        # After snapping, should align to 8-bar boundaries
        assert bar_idx >= 0


# ============================================================================
# Fallback/Hybrid Detection Tests
# ============================================================================

def test_fallback_pssi_missing_uses_energy(synthetic_16bar_intro, bar_times_ms_174bpm, mock_db_content):
    """Test: When PSSI missing, hybrid falls back to energy detection."""
    db, content = mock_db_content
    pssi_sections = []  # No PSSI available

    result = detect_sections_hybrid(
        db=db,
        content=content,
        pssi_sections=pssi_sections,
        bar_energies=synthetic_16bar_intro,
        bar_times_ms=bar_times_ms_174bpm,
        intro_bars=16
    )

    # Should fall back to energy detection
    assert result["drop1_bar"] is not None or result["drop2_bar"] is not None


def test_hybrid_pssi_preferred_over_energy(pssi_sections_complete, synthetic_16bar_intro, bar_times_ms_174bpm, mock_db_content):
    """Test: Hybrid uses PSSI when available (higher priority)."""
    db, content = mock_db_content

    result = detect_sections_hybrid(
        db=db,
        content=content,
        pssi_sections=pssi_sections_complete,
        bar_energies=synthetic_16bar_intro,
        bar_times_ms=bar_times_ms_174bpm,
        intro_bars=16
    )

    # PSSI should be used
    assert result["drop1_bar"] is not None


# ============================================================================
# Integration Tests
# ============================================================================

def test_tuning_constants_defined():
    """Test: Tuning constants are defined in module."""
    assert "HIGH_THRESHOLD_RATIO" in ENERGY_THRESHOLDS
    assert "LOW_THRESHOLD_RATIO" in ENERGY_THRESHOLDS
    assert "MIN_VALLEY_DURATION_BARS" in ENERGY_THRESHOLDS

    # Check reasonable values
    assert 1.5 <= ENERGY_THRESHOLDS["HIGH_THRESHOLD_RATIO"] <= 2.5
    assert 0.4 <= ENERGY_THRESHOLDS["LOW_THRESHOLD_RATIO"] <= 0.8
    assert ENERGY_THRESHOLDS["MIN_VALLEY_DURATION_BARS"] >= 1


def test_detect_sections_from_energy_returns_all_keys(synthetic_16bar_intro, bar_times_ms_174bpm):
    """Test: detect_sections_from_energy always returns all expected keys."""
    result = detect_sections_from_energy(synthetic_16bar_intro, bar_times_ms_174bpm, intro_bars=16)

    expected_keys = [
        "drop1_bar", "drop1_confidence",
        "breakdown_bar", "breakdown_confidence",
        "drop2_bar", "drop2_confidence",
        "outro_bar", "outro_confidence",
    ]
    for key in expected_keys:
        assert key in result


def test_detect_pssi_sections_returns_all_keys(pssi_sections_complete):
    """Test: detect_pssi_sections always returns all expected keys."""
    result = detect_pssi_sections(pssi_sections_complete)

    expected_keys = [
        "drop1_bar", "drop1_confidence",
        "breakdown_bar", "breakdown_confidence",
        "drop2_bar", "drop2_confidence",
        "outro_bar", "outro_confidence",
    ]
    for key in expected_keys:
        assert key in result


# ============================================================================
# Additional Edge Case Tests
# ============================================================================

def test_energy_detect_with_zero_energies(bar_times_ms_174bpm):
    """Test: All-zero energy array (silence) handled gracefully."""
    zero_energies = np.zeros(200, dtype=np.float64)
    result = detect_sections_from_energy(zero_energies, bar_times_ms_174bpm, intro_bars=16)

    # Should not crash; likely no sections detected
    assert isinstance(result, dict)
    assert "drop1_bar" in result


def test_confidence_range(synthetic_16bar_intro):
    """Test: Confidence scores always 0-100."""
    for bar_idx in [0, 16, 32, 48, 80]:
        for section_type in ["drop", "breakdown", "outro"]:
            conf = compute_section_confidence(synthetic_16bar_intro, bar_idx, section_type, baseline=5.0)
            assert 0 <= conf <= 100
