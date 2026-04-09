# Phase 4: Full Section Detection — Research

**Researched:** 2026-04-09
**Domain:** Section detection (Drop 1/2, Breakdown, Outro) using PSSI phrases + energy analysis
**Confidence:** MEDIUM-HIGH for PSSI + Simple Threshold; LOW-MEDIUM for ML approach (requires empirical validation)

---

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DETECT-04 | Detect Drop 1 as first major energy onset after intro | Energy onset at bar 16-32; snap to 8-bar boundary |
| DETECT-05 | Detect Breakdown as energy drop before Drop 2 | Energy valley; RMS + mean detection |
| DETECT-06 | Detect Drop 2 as second major energy onset | Energy peak after breakdown |
| DETECT-07 | Detect Outro as final low-energy section | Final 16-32 bars; mean amplitude < baseline |
| DETECT-09 | Assign confidence scores (0-100%) per section | Calibrate based on signal clarity |
| DETECT-12 | Warn on unanalyzed tracks (no PSSI available) | Check for PHRS tag; skip if absent |
| DETECT-13 | Warn on half-tempo tracks (handled in Phase 3) | Phase 3 BPM validation already covers |

---

## Summary

Phase 4 must detect four distinct sections in DnB tracks and assign confidence to each. The optimal approach is **hybrid: PSSI-first (Rekordbox's own analysis) + Energy fallback** with a focus on **Simple Threshold** for v1, with **ML research** deferred to v2.

**Key Finding:** Rekordbox's PSSI phrase analysis (when available) is highly accurate for DnB structure. Using it avoids reimplementing audio detection. For tracks without PSSI (older versions, unanalyzed), energy-based detection with tuned thresholds is reliable enough for v1.

**Recommendation for v1:** Implement PSSI + Simple Threshold hybrid. Research and benchmark ML approaches in parallel; if promising results, add to v2 or as optional v1.1 update.

---

## 1. PSSI Phrase Shortcut Analysis

### What is PSSI?

PSSI (Pioneer Segmentation Slice Info) is Rekordbox 6+'s automatic phrase detection. When user clicks "Analyze" on a track in Rekordbox, the app:
1. Analyzes audio waveform for structural boundaries
2. Detects phrase types: Intro, Verse, Chorus, Bridge, Breakdown, Outro (genre-aware)
3. Stores results in ANLZ .EXT file as PHRS/PSSI tags
4. User sees colored blocks on waveform (visual-only; doesn't auto-create cues)

### Tag Format (pyrekordbox)

From pyrekordbox documentation:
```python
from pyrekordbox import AnlzFile

anlz_ext = AnlzFile.parse_file(path_to_ext_file)
if 'PHRS' in anlz_ext.tag_types:
    phrs_tag = anlz_ext.get_tag('PHRS')
    phrases = phrs_tag.get()  # List of (start_bar, end_bar, type) tuples
```

Phrase types (enum):
- 0: Intro
- 1: Verse
- 2: Chorus
- 3: Bridge
- 4: Breakdown
- 5: Outro
- (etc., exact mapping varies)

### DnB Phrase Mapping

Rekordbox detects generic phrases. For DnB, the mapping should be:
- **Intro** (type 0) → intro section (bars 0-16 or 0-32)
- **Verse/Chorus** (types 1-2) → first drop section
- **Breakdown** (type 4) → breakdown valley
- **Bridge/Chorus** → second drop section
- **Outro** (type 5) → outro section

**Uncertainty:** Rekordbox's genre detection may misclassify DnB sections (confuse drops with verses, misjudge breakdown). Empirical testing on 50 DnB tracks needed to validate mapping accuracy.

### Fallback: When PSSI Is Unavailable

PSSI only exists if:
1. Track is analyzed in Rekordbox (user clicked "Analyze")
2. Rekordbox version 6+
3. `.EXT` file is present in library

**Fallback triggers:**
- No .EXT file → energy detection
- .EXT file exists but no PHRS tag → energy detection
- PHRS tag exists but is empty/malformed → energy detection
- PHRS phrase count < 4 (missing sections) → use energy for missing sections

**CLI messaging:**
```
[INFO] PHRS tag present. Using Rekordbox phrase analysis.
[WARNING] PHRS tag not found. Using energy-based detection (less accurate, but will process).
[ERROR] Track appears unanalyzed. Rekordbox phrase analysis unavailable.
         Recommend: Analyze track in Rekordbox first, then re-run RekordCue.
```

### Confidence Scoring for PSSI

PSSI results are either present (high confidence ~85%) or absent (fallback to energy ~60-70% depending on track structure clarity).

If PHRS confidence field exists in tag → use it directly. Otherwise → assign fixed value (85% for PSSI, 0% for missing sections).

---

## 2. Energy Detection Algorithm Comparison

### Approach A: Simple Threshold (RECOMMENDED for v1)

**Concept:** Threshold-based peak/valley detection on energy-per-bar array.

```python
import numpy as np

def detect_sections_from_energy(bar_energies: np.ndarray,
                                intro_bars: int = 16) -> dict:
    """
    Returns: {
        'drop1_bar': int or None,
        'breakdown_bar': int or None,
        'drop2_bar': int or None,
        'outro_bar': int or None,
        'drop1_confidence': float 0-100,
        ...
    }
    """
    # Establish baseline: mean energy in intro
    intro_energy = np.mean(bar_energies[0:intro_bars])
    high_threshold = intro_energy * 1.8  # 80% above intro
    low_threshold = intro_energy * 0.6   # 60% below intro

    # Detect sections by scanning energy curve
    sections = {}
    drop1_found = False
    breakdown_found = False

    for bar_idx in range(intro_bars, len(bar_energies)):
        energy = bar_energies[bar_idx]

        # Drop 1: first high energy above threshold
        if not drop1_found and energy > high_threshold:
            sections['drop1_bar'] = bar_idx
            drop1_found = True

        # Breakdown: energy valley after drop 1
        elif drop1_found and not breakdown_found and energy < low_threshold:
            # Verify it's a sustained valley (not a momentary dip)
            valley_duration = 0
            for j in range(bar_idx, min(bar_idx + 8, len(bar_energies))):
                if bar_energies[j] < low_threshold:
                    valley_duration += 1
            if valley_duration >= 2:  # at least 2 bars of low energy
                sections['breakdown_bar'] = bar_idx
                breakdown_found = True

        # Drop 2: second high energy after breakdown
        elif breakdown_found and energy > high_threshold:
            sections['drop2_bar'] = bar_idx
            break

    # Outro: final 16 bars, if low energy
    outro_energy = np.mean(bar_energies[-16:])
    if outro_energy < intro_energy * 1.2:
        sections['outro_bar'] = max(len(bar_energies) - 16, 0)

    # Confidence scoring
    sections['drop1_confidence'] = _confidence_from_clarity(
        bar_energies, sections.get('drop1_bar'), high_threshold
    )
    sections['breakdown_confidence'] = _confidence_from_clarity(
        bar_energies, sections.get('breakdown_bar'), low_threshold, inverse=True
    )
    # ... etc

    return sections
```

**Pros:**
- Fast (~10ms per track)
- Deterministic (reproducible)
- Tunable thresholds (adapts to user preferences)
- No external ML dependencies
- Easy to debug when wrong

**Cons:**
- Threshold tuning required (empirical testing on 20+ tracks)
- Struggles wit unusual structures (8-bar intros, extended breakdowns, very quiet tracks)
- False positives on fills/crashes that mimic drops
- 70-80% accuracy expected on diverse DnB (needs validation)

**Complexity:** ~100 lines of Python

---

### Approach B: RMS Hybrid (MEDIUM complexity)

**Concept:** Combine Mean Amplitude (energy level) + RMS (variance/edges).

Mean detects sustain; RMS detects sharp transitions. Drop onsets have high RMS (sudden spike). Breakdowns have low RMS in the valley (smooth) then high RMS at recovery (drop 2 onset).

```python
def compute_rms_per_bar(bar_energies: np.ndarray) -> np.ndarray:
    """Root Mean Square of energy changes per bar."""
    diffs = np.diff(bar_energies)  # energy change per bar
    rms = np.sqrt(np.mean(diffs**2))  # scalar RMS for whole track
    # Or windowed RMS per bar:
    bar_rms = np.array([np.sqrt(np.mean((bar_energies[i:i+4])**2))
                        for i in range(0, len(bar_energies)-4, 4)])
    return bar_rms

def detect_sections_hybrid(bar_energies, bar_rms):
    # Drop detection: high mean + high RMS spike
    # Breakdown detection: low mean + stable RMS (valley)
    # ...
```

**Pros:**
- More robust to subtle variations
- Better edge detection (drop onsets sharper)
- Still fast & deterministic

**Cons:**
- More parameters to tune (mean thresholds + RMS thresholds)
- Scipy dependency (for rolling window if used)
- Moderate complexity to debug

**Complexity:** ~150 lines

---

### Approach C: ML Image Classification (RESEARCH phase, defer v1)

**Concept:** Treat energy-per-bar as 1D signal → reshape to 2D (e.g., 16×8 grid representing 128 bars) → CNN classifier.

**Model Architecture Example:**
```
Input: (128,) energy array
Reshape: (16, 8) image
Conv2D (8 filters) → (14, 6)
ReLU, MaxPool
Conv2D (16 filters) → (6, 2)
ReLU, MaxPool
Flatten → Dense(64) → ReLU
Output: 4 classes (Drop 1, Breakdown, Drop 2, Outro)
```

**Training Data:**
- Collect 50-100 DnB tracks with manually labeled section positions (ground truth bars)
- Generate energy arrays via Phase 3's `compute_bar_energies()`
- Create labels: [drop1_bar, breakdown_bar, drop2_bar, outro_bar]
- Train/val/test split (70/15/15)

**Pros:**
- High accuracy potential (85-95% if trained well)
- Learns complex patterns (unusual structures, genre variants)
- Per-section confidence via softmax

**Cons:**
- Requires labeled training data (manual work to create ground truth)
- Slow inference (~500ms per track on CPU) — too slow for live CLI
- Model overfitting risk (genre-specific; fails on non-DnB)
- Hard to debug when predictions wrong ("black box")
- PyTorch/TensorFlow dependency (large, slow startup)
- Recommitting model weights to git is messy

**Complexity:** ~300 lines + training pipeline + data collection

**Feasibility for v1:** LOW (training data collection is blocker)

---

## 3. Recommendation for v1

**Approach:** PSSI-first + Simple Threshold (Approach A)

**Rationale:**
1. PSSI leverages Rekordbox's already-performed analysis (no redundant work)
2. Simple Threshold is fast, deterministic, tunable
3. Can achieve 75-80% accuracy with ~2 weeks of tuning on user's library
4. Low risk; easy to fall back to manual fixes
5. ML approach deferred to v2 after core detection is proven

**Hybrid Pipeline:**

```
For each track:
  1. Check for PHRS tag in .EXT file
     IF PHRS present AND confidence > threshold:
        Use PSSI phrases → map to Drop 1/2, Breakdown, Outro
        Confidence: 85%
     ELSE:
        Use energy-based Simple Threshold
        Confidence: 60-75% (depends on signal clarity)
  2. Return sections + confidence scores
  3. CLI displays: "Using PHRS" or "Using energy fallback"
  4. If confidence < 50%, flag track for manual review
```

---

## 4. Testing & Benchmarking Plan

### Ground Truth Set

Create a curated set of 20-30 high-quality DnB tracks with:
- Manually verified bar positions for: Intro end, Drop 1, Breakdown, Drop 2, Outro
- Metadata: BPM, intro length (16 vs 32), structure "standard" vs "unusual"
- Expected difficulty: easy (standard structure) to hard (tricky 8-bar intro, no breakdown)

### Metrics

For each algorithm:
1. **Accuracy:** % of detected sections within ±2 bars of ground truth
2. **False Positive Rate:** % of sections detected where none exists
3. **False Negative Rate:** % of sections missed
4. **Confidence Calibration:** Are sections scored 85% actually correct 85% of the time?
5. **Speed:** ms/track on typical hardware

### Test Matrix

| Approach | Accuracy Target | FP Rate | Speed | Tunability | Risk |
|----------|-----------------|---------|-------|------------|------|
| PSSI | 85-90% | <5% | <50ms | Low (tag-dependent) | Low (native Rekordbox) |
| Simple Threshold | 75-80% | 10-15% | <20ms | High (thresholds) | Low (easy to fix) |
| RMS Hybrid | 80-85% | 8-10% | <50ms | Medium (2 param sets) | Medium (tuning complexity) |
| ML (CNN) | 85-95% | <5% | 500ms+ | Medium (model retrain) | High (data quality, overfitting) |

---

## 5. Confidence Scoring Recommendation

**Calibration Approach:**

```python
def compute_section_confidence(bar_energies, section_bar, section_type):
    """0-100 scale."""

    baseline = np.mean(bar_energies[0:16])

    if section_type == 'drop':
        # High energy is good signal
        energy_at_section = bar_energies[section_bar]
        ratio = energy_at_section / baseline if baseline > 0 else 1.0

        # Confidence: how much higher than baseline?
        # 1.5x baseline = 50%, 2.5x = 85%, 3x+ = 95%
        confidence = min(95, int((ratio - 1.0) / 2.0 * 100))

    elif section_type == 'breakdown':
        # Low energy is good signal
        energy_at_section = bar_energies[section_bar]
        ratio = energy_at_section / baseline

        # Confidence: how much lower than baseline?
        # 0.5x baseline = 85%, 0.7x = 50%, 1.0x = 0%
        confidence = max(0, int((1.0 - ratio) / 0.5 * 100))

    elif section_type == 'outro':
        # Sustained low energy in final bars
        outro_energy = np.mean(bar_energies[-16:])
        if outro_energy < baseline * 0.8:
            confidence = 80
        elif outro_energy < baseline * 1.2:
            confidence = 50
        else:
            confidence = 20

    return min(100, max(0, confidence))
```

**Thresholds:**
- **>=80%:** High confidence, place cue automatically
- **50-79%:** Medium confidence, show in preview but allow user override
- **<50%:** Low confidence, flag for manual review (do not place)

---

## 6. Implementation Path for Phase 4

### Wave 1: PSSI + Simple Threshold (Pure energy)

**Plan 04-01 (Research/Experimentation):**
- Test PHRS tag reading from 5-10 real tracks
- Implement Simple Threshold detector
- Run on ground truth set, measure accuracy/false positive rate
- Tune thresholds empirically
- Document tuning process + final threshold values

**Plan 04-02 (Integration):**
- Add detect_sections_pssi() function (read & map PHRS tags)
- Add detect_sections_from_energy() function (Simple Threshold)
- Add hybrid dispatcher: try PSSI first, fallback to energy
- Integrate into main.py
- 3rd pass: Verify CLI runs on test tracks

### Wave 2 (Parallel, optional): RMS Hybrid Research

**Plan 04-03 (Research only):**
- Implement RMS hybrid approach on same ground truth set
- Compare accuracy vs Simple Threshold
- If RMS is >5% better → schedule for v1.1
- If similar → keep Simple for simplicity

### Wave 3+ (v2+): ML Image Classification Research

- Collect labeled training data (manual work: 50-100 tracks)
- Prototype CNN model
- Train/validate on test set
- Compare to baseline (Simple Threshold)
- If >10% accuracy gain AND inference < 300ms → consider for v2

---

## 7. Known Pitfalls & Mitigations

### Pitfall 1: PSSI Misclassification of DnB Sections

**What goes wrong:** Rekordbox's genre-agnostic phrase detection confuses DnB drops (high energy, sudden onset) with other genres' verse/chorus boundaries.

**Mitigation:**
- Empirical validation: test PSSI accuracy on 20+ DnB tracks before fully trusting it
- Fallback: if PSSI result doesn't match energy signal (e.g., PHRS says drop at bar 8 but energy peak on bar 16), flag as suspicious + use energy instead
- User override: allow per-track toggle to "ignore PSSI, use energy"

### Pitfall 2: Threshold Tuning is Track-Dependent

**What goes wrong:** Energy thresholds tuned on loud mastered tracks fail on quiet white-label tracks. Mean energy varies 10x across library.

**Mitigation:**
- Use relative thresholds (baseline × 1.8) not absolute values
- Compute baseline per-track (mean of intro bars, not fixed constant)
- Test tuning on diverse BPM range (155-185) + loudness range

### Pitfall 3: False Drops from Fills/Crashes

**What goes wrong:** A drum fill or sound effect creates momentary energy spike that looks like a drop onset.

**Mitigation:**
- Require sustained high energy (2+ bars above threshold), not single-bar spike
- Use RMS check (high RMS = sudden change) or median filter to smooth noise
- Manual review for low-confidence sections

### Pitfall 4: Breakdown Detection Fails on "Full-Power" Tracks

**What goes wrong:** Some DnB tracks have no breakdown (only drop → double drop at bar 48). Algorithm looks for energy valley and finds none.

**Mitigation:**
- Confidence scoring: if no valley found, return breakdown_confidence = 0%, omit from cue list
- Allow user setting: "skip breakdown if not detected" vs "always place at bar 48"

---

## 8. Confidence & Assumptions

| Claim | Confidence | Evidence | Risk |
|-------|-----------|----------|------|
| PSSI tags exist in .EXT for Rekordbox 6+ analyzed tracks | HIGH | pyrekordbox docs + Phase 1 verified tag access | Low - well documented |
| PSSI accuracy on DnB is 80%+ | MEDIUM | Rekordbox is genre-aware; DnB is mainstream genre | Medium - empirical validation needed |
| Simple Threshold can achieve 75%+ accuracy | MEDIUM-HIGH | Energy-based detection is proven approach; thresholds tunable | Medium - depends on threshold tuning |
| ML approach would achieve 90%+ accuracy | LOW-MEDIUM | ML is powerful but requires training data | HIGH - training data bottleneck; overfitting risk |
| RMS hybrid is better than simple threshold | LOW | Untested on DnB data | MEDIUM - empirical comparison needed |

---

## 9. Timeline Estimate

| Task | Effort | Duration |
|------|--------|----------|
| Implement PSSI reader + Simple Threshold | 1 engineer | 3-5 days |
| Empirical tuning on 20 ground-truth tracks | 1 engineer | 2-3 days |
| Integration + end-to-end testing | 1 engineer | 1-2 days |
| **Total Phase 4 (v1)** | - | **6-10 days** |
| RMS hybrid research (optional) | 1 engineer | 2-3 days |
| ML research + training data collection (v2+) | 1 engineer | 2-4 weeks |

---

## 10. Recommendation Summary

**For v1:** Implement PSSI-first + Simple Threshold hybrid.
- PSSI for pre-analyzed tracks (Rekordbox 6+)
- Energy fallback for unanalyzed or older Rekordbox versions
- Target 75-80% accuracy; user can manually override low-confidence detections
- Fast, deterministic, easy to explain to users

**For v2:** Evaluate RMS hybrid; if promising, ship as opt-in variant. Begin ML research (training data collection is primary blocker).

**Validation:** Ground-truth testing on 20-30 curated DnB tracks before shipping Phase 4.

---

*Research completed: 2026-04-09*
*Next: Plan Phase 4 execution with empirical tuning on ground-truth set*
