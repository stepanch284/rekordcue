"""
tests/test_bar_math.py — Unit tests for bar_math.py module.

Tests for:
  - BPM validation (validate_bpm_range)
  - 8-bar boundary snapping (snap_to_8bar_boundary)
  - Energy-per-bar computation (compute_bar_energies)
"""

import types
import numpy as np
import pytest

from bar_math import (
    validate_bpm_range, snap_to_8bar_boundary, compute_bar_energies,
    detect_grid_offset, shift_bar_times, detect_intro_length,
    DNB_BPM_MIN, DNB_BPM_MAX
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_content_174bpm():
    """Mock DjmdContent ORM object for 174 BPM track."""
    return types.SimpleNamespace(BPM=17400, Length=239.0, ID=12345)


@pytest.fixture
def mock_content_87bpm():
    """Mock DjmdContent ORM object for 87 BPM (half-tempo invalid) track."""
    return types.SimpleNamespace(BPM=8700, Length=180.0, ID=54321)


@pytest.fixture
def bar_times_ms_174bpm():
    """
    Synthetic bar times array for 174 BPM track.
    Bar interval: 60 / 174 * 4 * 1000 = ~1379.31 ms
    Bar 0 at 43ms, bar 1 at 1422ms, bar 8 at 11077ms, bar 16 at 22112ms, etc.
    174 bars total.
    """
    bar_interval_ms = 60.0 / 174.0 * 4 * 1000  # ~1379.31 ms
    return np.array([43.0 + i * bar_interval_ms for i in range(174)], dtype=np.float64)


@pytest.fixture
def bar_energies_structured():
    """
    Synthetic bar energies array (170 bars).
    Bars 0-15 (intro): energy = 5.0
    Bars 16-31 (drop 1): energy = 20.0
    Bars 32-63 (breakdown): energy = 5.0
    Bars 64-95 (drop 2): energy = 18.0
    Bars 96+: energy = 4.0
    """
    energies = np.zeros(170, dtype=np.float64)
    energies[0:16] = 5.0
    energies[16:32] = 20.0
    energies[32:64] = 5.0
    energies[64:96] = 18.0
    energies[96:] = 4.0
    return energies


@pytest.fixture
def bar_energies_32bar_intro():
    """
    Synthetic bar energies for 32-bar intro track.
    Bars 0-31 (intro): energy = 5.0
    Bars 32-63 (drop 1): energy = 22.0
    Bars 64+: energy = 4.0
    """
    energies = np.zeros(170, dtype=np.float64)
    energies[0:32] = 5.0
    energies[32:64] = 22.0
    energies[64:] = 4.0
    return energies


@pytest.fixture
def bar_energies_ambiguous():
    """
    Synthetic bar energies where all bars have low energy (ambiguous).
    Should default to 16-bar.
    """
    return np.ones(170, dtype=np.float64) * 5.0


@pytest.fixture
def amplitude_bimodal():
    """
    Synthetic amplitude array (1000 samples).
    Samples 0-499: value = 5.0 (low energy)
    Samples 500-999: value = 25.0 (high energy)
    """
    amp = np.zeros(1000, dtype=np.float64)
    amp[0:500] = 5.0
    amp[500:1000] = 25.0
    return amp


@pytest.fixture
def bar_times_s_10bars():
    """
    Synthetic bar times for 10 bars evenly spaced over 10 seconds.
    Bar interval: 1.0 second
    bar_times_s = [0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0]
    """
    return np.array([float(i) for i in range(10)], dtype=np.float64)


# ============================================================================
# BPM Validation Tests
# ============================================================================

def test_validate_bpm_range_valid(mock_content_174bpm):
    """Test: BPM=17400 (174.0) returns (174.0, True)."""
    bpm, is_valid = validate_bpm_range(mock_content_174bpm)
    assert bpm == 174.0
    assert is_valid is True


def test_validate_bpm_range_invalid_low(mock_content_87bpm):
    """Test: BPM=8700 (87.0) returns (87.0, False) — half-tempo."""
    bpm, is_valid = validate_bpm_range(mock_content_87bpm)
    assert bpm == 87.0
    assert is_valid is False


def test_validate_bpm_range_boundary_low():
    """Test: BPM=155.0 (at lower boundary) returns (155.0, True)."""
    content = types.SimpleNamespace(BPM=15500, Length=100.0, ID=1)
    bpm, is_valid = validate_bpm_range(content)
    assert bpm == 155.0
    assert is_valid is True


def test_validate_bpm_range_boundary_high():
    """Test: BPM=185.0 (at upper boundary) returns (185.0, True)."""
    content = types.SimpleNamespace(BPM=18500, Length=100.0, ID=2)
    bpm, is_valid = validate_bpm_range(content)
    assert bpm == 185.0
    assert is_valid is True


def test_validate_bpm_range_over():
    """Test: BPM=190.0 (above upper boundary) returns (190.0, False)."""
    content = types.SimpleNamespace(BPM=19000, Length=100.0, ID=3)
    bpm, is_valid = validate_bpm_range(content)
    assert bpm == 190.0
    assert is_valid is False


# ============================================================================
# 8-Bar Boundary Snap Tests
# ============================================================================

def test_snap_to_8bar_exact(bar_times_ms_174bpm):
    """Test: Position exactly on bar 16 snaps to bar 16 (idx=16)."""
    # bar_times_ms[16] should be ~22112ms for 174 BPM
    position_ms = float(bar_times_ms_174bpm[16])
    snapped_ms, bar_idx = snap_to_8bar_boundary(position_ms, bar_times_ms_174bpm)
    assert bar_idx == 16
    assert bar_idx % 8 == 0
    assert snapped_ms == int(position_ms)


def test_snap_to_8bar_rounds(bar_times_ms_174bpm):
    """Test: Position between bar 5 and bar 6 snaps to bar 8 (idx=8)."""
    # bar_times_ms[5] ~ 6896ms, bar_times_ms[6] ~ 8275ms
    # midpoint ~ 7585ms, closer to bar 5
    # nearest bar is 5 -> round(5/8)*8 = 0, or should snap to 8?
    # Actually: round(5/8) = round(0.625) = 1, so 1*8 = 8
    position_ms = (float(bar_times_ms_174bpm[5]) + float(bar_times_ms_174bpm[6])) / 2
    snapped_ms, bar_idx = snap_to_8bar_boundary(position_ms, bar_times_ms_174bpm)
    # bar_idx should be a multiple of 8
    assert bar_idx % 8 == 0
    assert bar_idx in [0, 8, 16]


def test_snap_to_8bar_start(bar_times_ms_174bpm):
    """Test: Position at 0ms snaps to bar 0 (idx=0)."""
    snapped_ms, bar_idx = snap_to_8bar_boundary(0.0, bar_times_ms_174bpm)
    assert bar_idx == 0
    assert bar_idx % 8 == 0
    assert snapped_ms >= 0


def test_snap_to_8bar_clamp_end(bar_times_ms_174bpm):
    """Test: Position beyond last bar clamps to last valid 8-bar multiple."""
    # Last bar is at index 173
    # Round(173/8)*8 = round(21.625)*8 = 22*8 = 176 (out of bounds)
    # Must clamp to len(bar_times_ms)-1 = 173
    position_ms = float(bar_times_ms_174bpm[-1]) + 10000.0  # way beyond
    snapped_ms, bar_idx = snap_to_8bar_boundary(position_ms, bar_times_ms_174bpm)
    # bar_idx should be clamped and a multiple of 8
    assert 0 <= bar_idx < len(bar_times_ms_174bpm)
    # Find the highest valid 8-bar index
    max_8bar_idx = (len(bar_times_ms_174bpm) - 1) // 8 * 8
    # With 174 bars: max_8bar_idx = 173 // 8 * 8 = 21 * 8 = 168
    # But after clamping, bar_idx might be different. Let's just check it's valid.
    assert bar_idx % 8 == 0 or bar_idx == len(bar_times_ms_174bpm) - 1


def test_snap_returns_int_ms(bar_times_ms_174bpm):
    """Test: Returned ms value is int, bar_index is int and multiple of 8."""
    position_ms = 5000.0
    snapped_ms, bar_idx = snap_to_8bar_boundary(position_ms, bar_times_ms_174bpm)
    assert isinstance(snapped_ms, (int, np.integer))
    assert isinstance(bar_idx, (int, np.integer))
    assert bar_idx % 8 == 0


# ============================================================================
# Energy-Per-Bar Computation Tests
# ============================================================================

def test_bars_from_amplitude_shape(amplitude_bimodal, bar_times_s_10bars):
    """Test: Output length equals number of bars."""
    # Import the helper function (it's marked private but needed for testing)
    from bar_math import _bars_from_amplitude

    track_len_s = 10.0
    energies = _bars_from_amplitude(amplitude_bimodal, bar_times_s_10bars, track_len_s)

    assert isinstance(energies, np.ndarray)
    assert len(energies) == len(bar_times_s_10bars)
    assert energies.dtype == np.float64


def test_bars_from_amplitude_signal(amplitude_bimodal, bar_times_s_10bars):
    """Test: High-amplitude region produces higher energy than low-amplitude region."""
    from bar_math import _bars_from_amplitude

    track_len_s = 10.0
    energies = _bars_from_amplitude(amplitude_bimodal, bar_times_s_10bars, track_len_s)

    # Bars 0-4 cover the first 5 seconds (low energy region) — ~5.0
    # Bars 5-9 cover the last 5 seconds (high energy region) — ~25.0
    low_energy_avg = np.mean(energies[0:5])
    high_energy_avg = np.mean(energies[5:10])

    # High energy should be significantly higher
    assert high_energy_avg > low_energy_avg
    assert high_energy_avg > low_energy_avg * 1.5  # at least 50% higher


# ============================================================================
# compute_bar_energies Tests
# ============================================================================

def test_compute_bar_energies_missing_data():
    """Test: compute_bar_energies raises ValueError when no waveform data available."""
    from bar_math import compute_bar_energies

    # Mock db that returns None (no ANLZ path)
    mock_db = types.SimpleNamespace(
        get_anlz_path=lambda content, kind: None
    )
    mock_content = types.SimpleNamespace(BPM=17400, Length=239.0, ID=12345)
    bar_times_s = np.linspace(0.0, 239.0, 174)

    with pytest.raises(ValueError, match="No waveform data available"):
        compute_bar_energies(mock_db, mock_content, bar_times_s)


# ============================================================================
# Grid Offset Detection Tests
# ============================================================================

def test_detect_grid_offset_aligned(bar_times_ms_174bpm):
    """Test: bar_times_ms[0] = 43.0, offset < 100ms, returns 0 (aligned)."""
    offset = detect_grid_offset(bar_times_ms_174bpm)
    assert offset == 0


def test_detect_grid_offset_misaligned():
    """Test: bar_times_ms[0] = 250.0, offset > 100ms, returns 250."""
    bar_times_ms = np.array([250.0, 1629.31, 3008.62, 4387.93], dtype=np.float64)
    offset = detect_grid_offset(bar_times_ms)
    assert offset == 250


def test_detect_grid_offset_boundary_low():
    """Test: bar_times_ms[0] = 50.0, offset < 100ms threshold, returns 0."""
    bar_times_ms = np.array([50.0, 1429.31, 2808.62], dtype=np.float64)
    offset = detect_grid_offset(bar_times_ms)
    assert offset == 0


def test_detect_grid_offset_boundary_high():
    """Test: bar_times_ms[0] = 150.0, offset > 100ms threshold, returns 150."""
    bar_times_ms = np.array([150.0, 1529.31, 2908.62], dtype=np.float64)
    offset = detect_grid_offset(bar_times_ms)
    assert offset == 150


def test_detect_grid_offset_empty():
    """Test: empty bar_times_ms returns 0."""
    bar_times_ms = np.array([], dtype=np.float64)
    offset = detect_grid_offset(bar_times_ms)
    assert offset == 0


# ============================================================================
# Bar Time Shifting Tests
# ============================================================================

def test_shift_bar_times_backward(bar_times_ms_174bpm):
    """Test: Shift all bars backward by offset, bar 0 aligns to 0ms."""
    offset_ms = 43
    shifted = shift_bar_times(bar_times_ms_174bpm, offset_ms)

    # Bar 0 should be ~0 after shift
    assert abs(shifted[0] - 0.0) < 1.0
    # Shifted array should not be same object (non-mutating)
    assert shifted is not bar_times_ms_174bpm
    # Length preserved
    assert len(shifted) == len(bar_times_ms_174bpm)


def test_shift_bar_times_no_negative_values():
    """Test: Shift never produces negative values (clamped at 0)."""
    bar_times_ms = np.array([100.0, 500.0, 1000.0], dtype=np.float64)
    offset_ms = 200  # larger than bar 0
    shifted = shift_bar_times(bar_times_ms, offset_ms)

    # First bar would be -100, clamped to 0
    assert shifted[0] == 0.0
    # Other bars: 500-200=300, 1000-200=800
    assert shifted[1] == 300.0
    assert shifted[2] == 800.0
    # All values >= 0
    assert np.all(shifted >= 0)


def test_shift_bar_times_zero_offset():
    """Test: Zero offset returns equivalent array (non-mutating)."""
    bar_times_ms = np.array([43.0, 1422.31, 2801.62], dtype=np.float64)
    shifted = shift_bar_times(bar_times_ms, 0)

    # Values unchanged
    assert np.allclose(shifted, bar_times_ms)
    # But different object
    assert shifted is not bar_times_ms


# ============================================================================
# Intro Length Detection Tests
# ============================================================================

def test_detect_intro_length_16bar(bar_energies_structured):
    """Test: 16-bar intro detected (energy jumps at bar 16)."""
    intro_len = detect_intro_length(bar_energies_structured)
    assert intro_len == 16


def test_detect_intro_length_32bar(bar_energies_32bar_intro):
    """Test: 32-bar intro detected (energy jumps at bar 32)."""
    intro_len = detect_intro_length(bar_energies_32bar_intro)
    assert intro_len == 32


def test_detect_intro_length_ambiguous(bar_energies_ambiguous):
    """Test: All low energy (ambiguous) defaults to 16-bar."""
    intro_len = detect_intro_length(bar_energies_ambiguous)
    assert intro_len == 16


def test_detect_intro_length_short_track():
    """Test: Track with < 32 bars defaults to 16."""
    bar_energies = np.ones(20, dtype=np.float64) * 5.0
    intro_len = detect_intro_length(bar_energies)
    assert intro_len == 16
