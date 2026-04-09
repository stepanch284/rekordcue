# User Cue Pattern Learning — Extended Concept

**Date:** 2026-04-09
**Type:** v2 Feature - Machine Learning Personalization

## Core Idea

Instead of just copying cue positions, analyze the **relationships between user's existing cue placements and signal processing variables** to reverse-engineer their implicit cuing rules.

## How It Works

### Phase 1: Analyze Existing Library
For each track with user-placed cues:
1. Extract cue positions (bar numbers, milliseconds)
2. Compute signal properties at those positions:
   - Energy (mean/RMS amplitude)
   - Frequency band distribution (kick-only, kick+bass, kick+synth, etc.)
   - Energy gradient (rising/falling)
   - Spectral centroid changes
   - Beat coherence / groove detection
3. Store as: `cue_position → [energy, frequency_profile, gradient, ...]`

### Phase 2: Extract Decision Rules
Create a mapping of user preferences:
- "User places Drop cues where energy > 15 AND spectral shift occurs"
- "User's Breakdown cues are at energy valleys with energy drop > 40%"
- "User places pre-drop cues 8 bars before energy peaks consistently"
- "User's intro anchors are always at bar 0, memory cue at bar 8-16 transition"

### Phase 3: Apply to New Tracks
For unprocessed tracks in same genre:
1. Compute same signal properties throughout track
2. Find positions matching user's learned patterns
3. Place cues using user's preferred method + bar snapping

## Example Application

**Scenario:** User has 50 DnB tracks with hand-curated hot cues.

Analysis reveals:
- Hot cue A: Always bar 0 ✓ (deterministic, skip ML)
- Hot cue B: 80% at bar 16, but 20% at bar 24 when "energy gradient low in bars 8-15"
- Hot cue C: 70% at "8 bars before energy peak", but 30% at "first safe mix point where breakdown ends"
- Memory cues: User places more memory cues in breakdown than in drops

**Result for new track:**
- Place cues using flexible rules learned from user, not rigid defaults
- If track structure matches "high energy drop at bar 16", use hot cue B at bar 16
- If track has "long fade-in", adjust pre-drop cue forward
- Memory cues placed where user typically places them relative to structure

## Technical Approach

**Option 1: Feature Vector + Simple Classification**
- Extract feature vectors (energy, spectral features) at bars 0-160
- Train simple classifier: "given features at bar X, what's probability user places a cue here?"
- Apply to new tracks at inference time

**Option 2: Time Series Clustering**
- Cluster waveforms of tracks where user places cues at same relative position
- Find similar waveform patterns in new tracks
- Suggest cue placement based on cluster membership

**Option 3: Reinforcement Learning (Advanced)**
- User feedback loop: "This cue placement is good / bad"
- Model learns optimal placement per user + genre + track character
- Improves over time with usage

## Data Required

Per user cue:
```
{
  "track_id": 12345,
  "cue_type": "hot_a" | "hot_b" | "hot_c" | "memory_drop1" | "memory_breakdown" | "memory_drop2" | "memory_outro",
  "position_bar": 16,
  "position_ms": 22112,
  "genre": "dnb",
  "signal_features": {
    "energy_window_0_16": 8.5,
    "energy_window_16_32": 22.3,
    "energy_gradient": "+0.87",
    "spectral_centroid_shift": "kick_to_synth",
    "frequency_dominance": ["kick", "bass"],
    "beat_coherence": 0.92
  }
}
```

## Deferred to v2+ Because

- Phase 1-7 (core engine) must be proven first — validation that default rules work for 80%+ of tracks
- ML adds complexity; must ensure core detection is reliable before learning
- Requires UI for model training/feedback (Phase 8-9 scope)
- Privacy: storing analysis of user's Rekordbox library locally (acceptable but adds storage)

## Future Considerations

- Multi-genre support: Train separate models per genre (DnB vs House vs Techno)
- Sub-genre refinement: Liquid vs Neurofunk vs Tech step each have different conventions
- Seasonal updates: Re-train model as user curates more tracks
- Export/import: Share learned models between users (with permission)
- Explainability: Show user "why this cue placement was suggested" to build trust

---

*Concept captured: 2026-04-09 during feature review session*
*Status: Backlog parking lot for v2 milestone*
