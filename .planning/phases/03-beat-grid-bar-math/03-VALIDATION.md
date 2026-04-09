---
phase: 3
slug: beat-grid-bar-math
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-09
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | none — Wave 0 installs |
| **Quick run command** | `python -m pytest tests/test_bar_math.py -q` |
| **Full suite command** | `python -m pytest tests/ -q` |
| **Estimated runtime** | ~3 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/test_bar_math.py -q`
- **After every plan wave:** Run `python -m pytest tests/ -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 3-01-01 | 01 | 0 | DETECT-01 | — | N/A | unit | `python -m pytest tests/test_bar_math.py::test_bar_times_ms -q` | ❌ W0 | ⬜ pending |
| 3-01-02 | 01 | 1 | DETECT-02 | — | N/A | unit | `python -m pytest tests/test_bar_math.py::test_snap_to_8bar -q` | ❌ W0 | ⬜ pending |
| 3-01-03 | 01 | 1 | DETECT-03 | — | N/A | unit | `python -m pytest tests/test_bar_math.py::test_bpm_range_check -q` | ❌ W0 | ⬜ pending |
| 3-01-04 | 01 | 1 | DETECT-08 | — | N/A | unit | `python -m pytest tests/test_bar_math.py::test_compute_bar_energies -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_bar_math.py` — stubs for DETECT-01, DETECT-02, DETECT-03, DETECT-08
- [ ] `tests/conftest.py` — shared fixtures (synthetic bar grid, amplitudes)
- [ ] `pytest` install if not already present (`pip install pytest`)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Bar boundaries audibly on-grid in Rekordbox | DETECT-01 | Requires loading track in Rekordbox and listening | Run `python main.py <track_id>`, open Rekordbox, verify cue A lands on the downbeat |
| Energy-per-bar signal visually correlates with structure | DETECT-08 | Requires human judgement of waveform vs energy curve | Print bar energies array to console, compare against track's visual waveform in Rekordbox |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
