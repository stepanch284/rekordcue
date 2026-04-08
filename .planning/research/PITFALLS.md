# Domain Pitfalls: Rekordbox Auto Cue Point Tool

**Domain:** Rekordbox library manipulation / Python desktop tool
**Researched:** 2026-04-08
**Confidence note:** Web search and WebFetch were unavailable during this session.
Findings are drawn from training knowledge of the Rekordbox reverse-engineering
community (DeepSymmetry project, pyrekordbox source and issue tracker, DJTT
forums, SQLite documentation). Confidence levels are assigned per-finding.

---

## Critical Pitfalls

Mistakes that cause data loss, database corruption, or silent breakage.

---

### Pitfall 1: Writing to master.db While Rekordbox Is Open

**What goes wrong:** Rekordbox holds an exclusive write lock on `master.db` while
running. If you open the same file with Python's sqlite3 and attempt a write, you
will receive `sqlite3.OperationalError: database is locked`. Worse, if you bypass
the lock by using WAL (Write-Ahead Log) mode or a shared-cache connection, you risk
writing rows that Rekordbox's in-memory state will overwrite when it next flushes
— silently discarding your changes, or producing a database with inconsistent row
state that Rekordbox detects and refuses to load.

**Why it happens:** Rekordbox does not observe the file in real time. It loads the
library into memory at startup and writes back periodically and on close. Your
writes may land on disk but get clobbered by Rekordbox's next flush.

**Consequences:**
- Cue points silently disappear after Rekordbox closes and re-opens.
- In rare cases (interrupted write + Rekordbox re-open mid-WAL), the database
  can end up in an inconsistent state that requires recovery from Pioneer's
  built-in backup.
- WAL journal files (`.wal`, `.shm`) can be left orphaned if your process
  crashes, which may confuse Rekordbox on next startup.

**Prevention:**
- Always require Rekordbox to be fully closed before writing. Enforce this with a
  process check (`psutil.process_iter()` looking for `rekordbox.exe`) and block
  the write operation with a clear user-facing message if it is running.
- Never open the database with `check_same_thread=False` or journal mode tricks
  as a workaround for the lock.
- After writing, instruct users to let Rekordbox re-open and load — do not write
  again until the next close cycle.

**Detection:** If cue points appear in the UI immediately after applying but
vanish after the user closes and re-opens Rekordbox, this is the cause.

**Confidence:** HIGH — this is SQLite's standard locking behavior, documented and
reproduced widely in the pyrekordbox issue tracker and DJTT forum threads.

---

### Pitfall 2: Database Schema Changes Between Rekordbox Versions

**What goes wrong:** Pioneer silently changes the `master.db` schema between major
Rekordbox versions (e.g., 5.x → 6.x was a large restructure; 6.x minor versions
have had table and column additions). Hardcoded column names, table names, or
INSERT statements that work on one version break on another — either raising an
exception or, more dangerously, inserting into the wrong columns.

**Known structural changes (MEDIUM confidence):**
- Rekordbox 6 reorganized cue point storage compared to 5. The table is named
  `djmdCue` in v6. The column set in v5 was different and pyrekordbox's v5 support
  is in a separate code path.
- The `djmdContent` table (tracks) gained columns across 6.x point releases.
  Inserting a row without knowing all NOT NULL columns will fail silently or raise
  an IntegrityError depending on SQLite defaults.
- `UUID` fields were introduced/changed in certain 6.x versions, meaning
  foreign key relationships between `djmdCue` and `djmdContent` must use the
  correct key type for the installed version.

**Consequences:**
- INSERT fails → no cue written, no feedback if exception is swallowed.
- INSERT into wrong column mapping → cue written at wrong position or with wrong
  type, appears as garbage in Rekordbox.
- Schema introspection at runtime may silently succeed on an unexpected version.

**Prevention:**
- At startup, read `PRAGMA user_version;` (or the `djmdSystemConfig` table if
  present) and map it to a known schema version. Refuse to write if the version
  is unrecognized.
- Never hardcode column positions; always use named parameter binding:
  `INSERT INTO djmdCue (ID, ContentID, ...) VALUES (:id, :content_id, ...)`.
- Maintain a version compatibility matrix in the code and fail loudly when the
  installed version is outside the tested range.
- Test against Rekordbox 6.5.x, 6.6.x, and 6.7.x minimum — these are the most
  common versions in the field as of early 2026.

**Detection:** Log `PRAGMA user_version;` at every run. If users report "cues not
appearing," first check version mismatch.

**Confidence:** MEDIUM — schema change history is documented in pyrekordbox
changelog and DeepSymmetry's reverse engineering notes, but exact version-by-version
diff requires live verification against each Rekordbox installer.

---

### Pitfall 3: Re-analysis Overwrites Cue Points

**What goes wrong:** When a user triggers "Analyze Tracks" in Rekordbox (or
enables auto-analysis on import), Rekordbox re-runs its analysis pipeline. The
exact behavior differs by analysis type:

- **Beat grid re-analysis:** Overwrites the `djmdBeat` table rows for that
  track. If your cue positions were anchored to the old beat grid, they now
  point to wrong bars — cues land between beats or on wrong bars.
- **Waveform re-analysis:** Rewrites the waveform binary files. Your parsed
  waveform data is stale but cue positions themselves survive (they are
  position-in-milliseconds, not position-in-bars in the DB).
- **Cue point behavior on re-analysis:** Rekordbox does NOT overwrite user-set
  cue points during standard re-analysis. Hot cues and memory cues persist.
  However, if the user selects "Delete Analysis Data" and re-analyzes from
  scratch, hot cues placed in an older session are cleared along with beat grids.

**Consequences:**
- Beat grid re-analysis shifts the timing reference without moving cues → all
  programmatically placed cues are now off by some number of bars.
- Users who delete and re-analyze will lose all auto-placed cues and need to
  re-run the tool.

**Prevention:**
- Store the beat grid anchor (BPM + first beat offset in ms) used when placing
  cues. Detect drift on next run and warn the user.
- Document clearly to users: "Do not re-analyze beat grids after placing cues.
  If you must re-analyze, re-run this tool afterward."
- Consider placing cues using absolute millisecond positions rather than derived
  bar counts where possible — ms positions survive beat grid changes (though they
  are now musically misaligned).

**Confidence:** HIGH for "cues persist through standard re-analysis." MEDIUM for
exact behavior on full delete+re-analyze (community-observed but not officially
documented by Pioneer).

---

### Pitfall 4: Hot Cue Count Limit (Hard Cap of 8)

**What goes wrong:** Rekordbox enforces a hard limit of 8 hot cues per track
(labeled A–H, or 1–8 depending on UI version). This is a hardware constraint
inherited from Pioneer CDJ firmware — CDJs only have 8 hot cue buttons. If you
attempt to write a 9th hot cue to `djmdCue` with `type = 0` (hot cue), Rekordbox
will silently ignore it on load or display an error.

**Memory cue limit:** Memory cues have a much higher practical limit. The commonly
cited figure is 8 memory cues per track in earlier firmware, but Rekordbox 6 on
desktop supports significantly more (tested at 36+ in community reports). The
effective limit is likely tied to what CDJs can sync over Link — CDJs typically
show only the first 5 memory cues in the waveform overview even if more exist in
the library. There is no authoritative Pioneer documentation of an absolute cap.

**Consequences:**
- Silently dropping cues if the tool generates more than 8 hot cues.
- Unexpected behavior on CDJ export if memory cues exceed hardware limits.

**Prevention:**
- Cap hot cue generation at 8. For DnB/Jungle with 4 structural sections, this
  is unlikely to be a constraint (4 section types × 1 cue each = 4 hot cues), but
  guard the limit explicitly.
- For memory cues, cap at a conservative 16 for safety.
- Check how many cues already exist for a track before writing — do not write
  if the remaining capacity would be exceeded. Report this to the user.

**Confidence:** HIGH for 8 hot cue hard limit. LOW for memory cue absolute limit
(community-observed variability; no official Pioneer spec found in training data).

---

### Pitfall 5: Waveform Binary Format Is Undocumented and Version-Dependent

**What goes wrong:** Rekordbox's internal waveform files (stored under
`%APPDATA%\Pioneer\rekordbox\share\` or similar) use a proprietary binary format.
The format has changed across versions:

- **EXT format vs. DAT format:** Rekordbox 6 uses `.EXT` analysis files
  (`ANLZ*.EXT`) which contain high-resolution color waveform data, and `.DAT`
  files (`ANLZ*.DAT`) for the standard waveform and beat grid. Both coexist.
- **Tag-based structure:** The `.DAT`/`.EXT` files use a tag-chunk structure
  (four-byte tag, four-byte length, variable data). Tag types include `PWAV`
  (preview waveform), `PWAV` detail, `PQTZ` (beat grid), `PCOB` (cue/loop),
  and others. pyrekordbox parses these via construct definitions.
- **Version drift:** The tag layouts have changed in minor versions. A parser
  written against Rekordbox 6.5 may misparse data from a file written by 6.7.
- **Missing files:** If Rekordbox has not yet analyzed a track, no `.DAT`/`.EXT`
  file exists. Your tool must handle this gracefully rather than crashing.

**Consequences:**
- Parsing wrong byte offsets → reading garbage amplitude data → wrong section
  detection → cues placed at incorrect bars.
- Crashes on unrecognized tag types if the parser doesn't use a lenient/skip-unknown
  mode.
- Tool silently fails on un-analyzed tracks.

**Prevention:**
- Use pyrekordbox's `AnlzFile` class rather than rolling your own parser.
  pyrekordbox tracks format changes and is the most current open-source
  implementation.
- Always validate that the analysis file exists before attempting to parse.
  Cross-reference `djmdContent.AnalysisDataPath` (or similar column) against
  filesystem existence.
- Log tag type + version from the file header on parse. Flag discrepancies.
- Use pyrekordbox in read-only mode for waveform files — never write back to
  `.DAT`/`.EXT` files; let Rekordbox own its analysis output.

**Confidence:** MEDIUM — tag structure is well-documented by DeepSymmetry and
implemented in pyrekordbox, but exact version-by-version delta requires live
testing.

---

### Pitfall 6: Windows AppData Path Variability and Permissions

**What goes wrong:** The Rekordbox data directory under Windows is not always
`%APPDATA%\Pioneer\rekordbox\`. Several variations exist:

- **Rekordbox 5.x:** `%APPDATA%\Pioneer\rekordbox5\` or `%APPDATA%\Pioneer\rekordbox\`
  depending on sub-version.
- **Rekordbox 6.x:** `%APPDATA%\Pioneer\rekordbox\` (but internal subfolder
  layout changed in 6.x vs 5.x).
- **Rekordbox installed from djay Pro or mixed installs:** Pioneer sometimes
  installs to non-standard locations when bundled with third-party software.
- **OneDrive folder redirection:** Windows users with OneDrive enabled may have
  `%APPDATA%` silently redirected to a OneDrive path, meaning the actual path is
  something like `C:\Users\<user>\OneDrive\AppData\Roaming\Pioneer\rekordbox\`.
  File locks and write permissions behave differently in synced OneDrive folders.
- **UAC / permissions:** On some Windows configurations, `%APPDATA%` requires
  elevated access for file writes even though it nominally belongs to the current
  user. This is rare but observed on corporate/school machines.

**Consequences:**
- Tool cannot find `master.db` → fails silently or with a confusing "file not found"
  error.
- Writes succeed to a non-synced local copy while Rekordbox reads from the
  OneDrive-redirected copy → cues never appear.
- Path with spaces or Unicode characters in Windows username breaks naive string
  concatenation paths.

**Prevention:**
- Use `os.environ.get('APPDATA')` to resolve the path, never hardcode it.
- Enumerate known candidate paths (v5, v6 sub-paths) and pick the one containing
  `master.db`.
- Warn the user explicitly if the resolved path is inside a OneDrive or Dropbox
  folder, as syncing during a write operation can cause database corruption.
- Use `pathlib.Path` throughout — never string concatenation — to handle spaces
  and Unicode username paths correctly.
- Test the resolved path's write permission before attempting DB writes
  (`os.access(path, os.W_OK)`).

**Confidence:** HIGH for path variability. MEDIUM for OneDrive interaction edge
cases (community-observed but not systematically documented).

---

## Moderate Pitfalls

---

### Pitfall 7: Beat Grid Anchor Accuracy and DnB BPM Edge Cases

**What goes wrong:** Rekordbox's beat grid analysis is not infallible. For DnB
and Jungle (typically 165–180 BPM), two common failure modes exist:

1. **Half-tempo detection:** Rekordbox occasionally detects DnB tracks at half
   BPM (82–90 BPM) and doubles the beat interval. A cue placed at "bar 17" using
   this grid lands at bar 33 in musical reality.
2. **First beat offset error:** The beat grid's "first beat" timestamp may be
   off by one or two beats, especially on tracks with long vinyl-crack intros or
   non-quantized live recordings (original Jungle from the early 90s). Even a 1-beat
   offset propagates to a full bar (4 beats) error per 4 bars of drift in 16-bar
   alignment.
3. **Variable BPM:** Tracks recorded without a click track (common in older Jungle)
   have natural tempo drift. Rekordbox's constant-BPM grid diverges from the actual
   downbeats as the track progresses. Cues placed at bar 65 may land 1–2 bars off.

**Prevention:**
- Always validate inferred bar positions against the waveform energy data.
  If you detect a drop at a position that does not align with the beat grid,
  log a warning rather than forcing the cue to the nearest grid point.
- Provide a "BPM sanity check" that flags tracks analyzed outside 155–185 BPM
  as likely mis-detected (for DnB library).
- Expose a "bar offset" correction field in the UI for users to nudge the grid
  anchor by ±4 beats before applying cues.

**Confidence:** HIGH — half-tempo detection is a well-known Rekordbox issue with
DnB/Jungle documented extensively on DJTT and Reddit.

---

### Pitfall 8: pyrekordbox Library Maturity and Maintenance Gaps

**What goes wrong:** pyrekordbox (by dylanljones) is a community-maintained
reverse-engineering project. As of training knowledge it is the best available
Python option, but has real constraints:

- **Write support is partial:** pyrekordbox's read support is well-tested; its
  write/modify support for `djmdCue` specifically has received less testing in
  real-world roundtrip scenarios. Direct `sqlite3` manipulation of `djmdCue` may
  be safer and more explicit than relying on pyrekordbox's ORM-style writes.
- **ORM foreign key handling:** pyrekordbox uses SQLAlchemy under the hood. If
  you create a `DjmdCue` ORM object and associate it incorrectly with a
  `DjmdContent` object, foreign key violations may be silently ignored (SQLite
  doesn't enforce foreign keys unless `PRAGMA foreign_keys = ON` is explicitly
  set).
- **Session state:** Using SQLAlchemy sessions without explicit `session.commit()`
  and `session.close()` leaves transactions open. Rekordbox opening the file while
  a SQLAlchemy session holds an implicit transaction lock causes a deadlock.
- **Version lag:** pyrekordbox's support for the latest Rekordbox release may be
  behind by several months. The library's schema definitions may not reflect the
  installed Rekordbox version.

**Prevention:**
- For cue point writes, prefer direct `sqlite3` with explicit transactions over
  pyrekordbox's ORM write path. Use pyrekordbox for reads (waveform parsing,
  content listing) where it excels.
- Always call `PRAGMA foreign_keys = ON` at connection open.
- Wrap all DB writes in explicit `with conn:` context managers.
- Pin pyrekordbox to a tested version in `requirements.txt` and treat upgrades
  as potentially breaking.
- Check pyrekordbox's GitHub issue tracker for "6.7" or whatever the current
  Rekordbox version is before relying on compatibility.

**Confidence:** MEDIUM — based on reading pyrekordbox source and issue tracker
patterns in training data; may have improved since.

---

### Pitfall 9: Cue Point ID and UUID Collision

**What goes wrong:** Each row in `djmdCue` requires a unique `ID` (integer
primary key) and in some Rekordbox versions a `UUID` (text field). If you generate
IDs naively (e.g., `SELECT MAX(ID) + 1`) under concurrent write conditions, or if
pyrekordbox auto-generates UUIDs that don't match Pioneer's format, you get:

- Duplicate primary key errors if another row was inserted between your SELECT
  and INSERT.
- UUID format mismatches causing Rekordbox to treat the row as foreign/corrupt data.

**Prevention:**
- Use `INSERT INTO djmdCue (...) VALUES (...)` within a single transaction with
  `SELECT MAX(ID) + 1` inside the same transaction (or use SQLite's
  `last_insert_rowid()` pattern with AUTOINCREMENT if the schema allows).
- Check what UUID format existing rows use (typically hyphenated UUID4 strings
  like `550e8400-e29b-41d4-a716-446655440000`) and match it exactly.
- Do not assume `AUTOINCREMENT` is set on the `ID` column — verify against the
  actual schema with `PRAGMA table_info(djmdCue)`.

**Confidence:** MEDIUM — UUID field presence is version-dependent; requires live
schema inspection to confirm.

---

### Pitfall 10: Cue Position Encoding (Milliseconds vs. Frames)

**What goes wrong:** Cue positions in `djmdCue` are stored in milliseconds as
integers (confirmed in multiple reverse-engineering sources). However, two subtle
encoding issues exist:

1. **Rounding:** Rekordbox rounds cue positions to the nearest millisecond
   internally. If you compute a cue position from BPM math as a float and truncate
   without rounding, cues can land systematically 1ms early, which is audible on
   tight drops.
2. **Memory cue vs. hot cue type field:** The `Type` column distinguishes hot
   cues (0) from memory cues (1) in most Rekordbox 6 schema descriptions. Using
   the wrong value here produces a cue that appears in the wrong section of
   Rekordbox's UI and behaves differently on CDJs.
3. **Hot cue index:** Hot cues have a `HotCueNumber` (or equivalent column) that
   maps to the A–H button assignment. If you insert two hot cues with the same
   index for a track, only one will be displayed. Always use indices 0–7 (A–H)
   and check for conflicts with existing cues.

**Prevention:**
- Use `round(position_ms)` not `int(position_ms)` when computing cue positions.
- Confirm the `Type` value encoding against a known-good row from an existing
  cue in the database before writing new rows.
- Before inserting hot cues, `SELECT HotCueNumber FROM djmdCue WHERE ContentID = ?`
  and avoid indices already in use.

**Confidence:** MEDIUM — millisecond encoding is widely confirmed; exact column
names require schema inspection against the installed version.

---

## Minor Pitfalls

---

### Pitfall 11: Backup Strategy — Pioneer's Own Backup Is Not Atomic

**What goes wrong:** Rekordbox has a built-in backup mechanism (Tools > Backup
Library). However, this backup is not taken continuously — it is user-initiated
or triggered on major events. If your tool corrupts `master.db`, the most recent
Pioneer backup may be days old.

**Prevention:**
- Your tool must create its own timestamped backup of `master.db` before every
  write operation: `shutil.copy2(db_path, db_path + ".rkbak." + timestamp)`.
- Keep the last 3 backups and rotate older ones.
- Show the backup path in the UI so users can find it.

**Confidence:** HIGH — this is standard practice; no Rekordbox-specific research
needed.

---

### Pitfall 12: Color Encoding for Hot Cues

**What goes wrong:** Rekordbox encodes hot cue colors as integers in `djmdCue`.
The mapping of integer → display color is not a simple RGB value — it is an index
into Pioneer's fixed color palette (approximately 8–16 predefined colors). Storing
an arbitrary RGB integer produces cues that either appear as the wrong color or
default to white.

**Prevention:**
- Map your 4 section types (intro, drop, breakdown, second drop) to Pioneer's
  known color palette values. Common palette entries are documented in pyrekordbox
  and DeepSymmetry's reverse engineering notes.
- Read the `ColorID` from an existing cue in the user's library to confirm the
  palette mapping before writing.

**Confidence:** MEDIUM — color index behavior is documented in community sources
but the exact integer values should be verified against a live database.

---

### Pitfall 13: Legal and ToS Considerations

**What goes wrong:** Pioneer DJ's Terms of Service for Rekordbox do not explicitly
authorize reverse-engineering or third-party database access. Building and
distributing a tool that writes to `master.db` exists in a legal gray area:

- EU Directive 2009/24/EC permits reverse engineering for interoperability
  purposes. Australia, Canada, and the US (under DMCA §1201(f)) have similar
  interoperability exceptions.
- Pioneer has historically tolerated the reverse-engineering community (pyrekordbox,
  DeepSymmetry, Mixxx's link implementation) without legal action.
- Distributing the tool does not violate the Rekordbox EULA on its own because
  you are not distributing Pioneer's binaries — you are distributing a tool that
  operates on user-owned data files.

**Residual risks:**
- Pioneer could issue a DMCA takedown for documentation of file formats (unlikely
  given the existing public reverse-engineering projects that have operated for
  years without action).
- If the tool causes data loss at scale and Pioneer receives support complaints,
  they may add technical countermeasures (DB checksums, encrypted schema) in a
  future version — this would break the tool but is not a legal risk.

**Recommendation:** Do not distribute Pioneer's binaries, file format magic numbers
as stand-alone documents, or claim official Pioneer support. Include a clear
disclaimer: "This tool is not affiliated with Pioneer DJ. Always back up your
library before use."

**Confidence:** MEDIUM — based on how analogous tools have operated historically;
not legal advice.

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| DB schema inspection | Schema differs from documented examples | `PRAGMA table_info` every table before writing; never hardcode column order |
| Waveform parsing | `.EXT` file absent for un-analyzed tracks | Check file existence; skip with user warning |
| Beat grid anchor | Half-tempo detection on DnB tracks | BPM range sanity check at analysis time |
| Cue writes | Rekordbox open during write | `psutil` process guard before any write |
| Windows path resolution | OneDrive redirection silently misdirects writes | Enumerate candidate paths; warn on cloud sync detection |
| UI "apply" action | No backup before write | Mandatory pre-write backup, show path in UI |
| CDJ export | Memory cue count exceeds CDJ display limit | Cap memory cues at 16; document hardware limit |
| First release / distribution | Users on non-tested Rekordbox versions | Startup version check with clear "unsupported version" message |

---

## Sources

All findings are from training knowledge (cutoff August 2025) covering:

- **pyrekordbox** (dylanljones): library source, README, issue tracker patterns —
  MEDIUM confidence (requires live verification against current version)
- **DeepSymmetry reverse-engineering documentation**: ANLZ file format, cue
  encoding — MEDIUM confidence (format known to drift across Rekordbox versions)
- **DJTT (DJ TechTools) forum threads**: half-tempo detection, cue limit behavior
  — MEDIUM confidence (community observation, not Pioneer official docs)
- **Pioneer DJ Rekordbox manual / release notes**: schema version changes not
  formally published by Pioneer; inferred from community tooling — LOW-MEDIUM
  confidence where stated
- **SQLite documentation**: locking, WAL mode, PRAGMA behavior — HIGH confidence
  (stable, authoritative)
- **Windows filesystem and NTFS documentation**: AppData path behavior, OneDrive
  redirection — HIGH confidence (Microsoft documentation, stable)

**Verification recommended before Phase 1:** Install Rekordbox 6.7.x and inspect
`PRAGMA user_version`, `PRAGMA table_info(djmdCue)`, and `PRAGMA table_info(djmdContent)`
against the schema assumptions above. Run pyrekordbox against a test library to
confirm read/write roundtrip on the current version.
