# RekordCue — Auto Cue Point Tool for Rekordbox

## What This Is

A Windows desktop application for Rekordbox DJs that automatically analyzes track waveform data and places both hot cues and memory cues at musically meaningful structural points. It targets Drum & Bass and Jungle music (16-bar structures), detecting sections like intro, first drop, breakdown, and second drop by parsing Rekordbox's internal waveform files and writing cue data directly to the Rekordbox SQLite database.

## Core Value

A DJ should be able to select tracks from their Rekordbox library and get correctly placed structural cue points without manually scrubbing through each track.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Parse Rekordbox's internal waveform data files (Windows: `%APPDATA%\Pioneer\rekordbox\`) to extract energy/amplitude data per track
- [ ] Detect structural sections from waveform: intro, first drop, breakdown, second drop using energy analysis
- [ ] Use Rekordbox beat grid analysis (first bar = bar 0) as the timing anchor for cue placement
- [ ] Place cues on 16-bar boundaries aligned to detected section starts (DnB/Jungle convention)
- [ ] Write both hot cues (color-coded by section type) and memory cues to the Rekordbox SQLite `master.db`
- [ ] Desktop UI: track list from Rekordbox library, preview cue positions, apply button
- [ ] Windows support (Rekordbox AppData paths)

### Out of Scope

- macOS support — deferred, Windows-first
- Web app version — future milestone after desktop is stable
- Genre auto-detection — targeting DnB/Jungle only for v1
- 32-bar structures — DnB uses 16-bar, add later if needed
- Rekordbox XML export/import — using direct DB access instead

## Context

- Rekordbox stores its library in a SQLite database (`master.db`) under `%APPDATA%\Pioneer\rekordbox\`
- Waveform data is stored as binary files in Rekordbox's internal format alongside the database
- Cue points in Rekordbox have: position (milliseconds), type (hot cue / memory cue), color, label
- Beat grid data (BPM + first beat position) is already computed by Rekordbox's own analysis — we anchor to this
- DnB/Jungle typically has 16-bar phrases; structural sections align to these boundaries
- Project started in Python (`main.py` exists); desktop UI framework TBD (likely Tkinter or PyQt)
- Future goal: web app version for broader accessibility

## Constraints

- **Platform**: Windows only for v1 — Rekordbox paths are Windows-specific
- **Data source**: Rekordbox's internal files only — no external audio analysis APIs
- **Compatibility**: Must not corrupt the Rekordbox database — always backup before writing
- **Database**: Rekordbox uses SQLite — must reverse-engineer the cue point schema

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Parse internal waveform files | More reliable than screenshots; no UI dependency | — Pending |
| Direct SQLite DB writes | Fastest integration path vs XML round-trip | — Pending |
| DnB/Jungle first (16-bar) | User's primary genre; simplest structure to target | — Pending |
| Python desktop app | Existing main.py, fast prototyping | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-08 after initialization*
