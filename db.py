"""
db.py — Rekordbox database access layer for RekordCue.

Provides:
  open_database()    — open encrypted master.db via pyrekordbox
  validate_schema()  — confirm DjmdCue columns match RB7.2.3 expected schema
  get_track()        — look up a track by ID and return its DjmdContent row
"""

from sqlalchemy import text
from pyrekordbox import Rekordbox6Database


REQUIRED_CUE_COLUMNS = {
    'ID',
    'ContentID',
    'InMsec',
    'Kind',
    'Color',
    'ColorTableIndex',
    'Comment',
    'created_at',
    'updated_at',
    'ContentUUID',
    'UUID',
}


def open_database() -> Rekordbox6Database:
    """Open the encrypted Rekordbox master.db using pyrekordbox auto-location.

    Tries rekordbox7 config first, then falls back to rekordbox6.
    Prints the resolved db_directory path for confirmation.
    Never use plain sqlite3.connect() — the database is encrypted.

    Returns:
        A connected Rekordbox6Database instance.

    Raises:
        Exception: Re-raises any connection error after printing a clear message.
    """
    try:
        db = Rekordbox6Database()
        print(f"[db] Opened database at: {db.db_directory}")
        return db
    except Exception as exc:
        print(f"[db] ERROR: Failed to open Rekordbox database: {exc}")
        raise


def validate_schema(db: Rekordbox6Database) -> bool:
    """Validate that DjmdCue has the columns expected for Rekordbox 7.x schema.

    Uses PRAGMA table_info instead of user_version because user_version=0 on RB7.2.3.

    Args:
        db: An open Rekordbox6Database instance.

    Returns:
        True if the schema is valid.

    Raises:
        RuntimeError: If required columns are missing or the legacy Number column is present.
    """
    rows = db.session.execute(text('PRAGMA table_info(djmdCue)')).fetchall()
    found = {row[1] for row in rows}  # row[1] is the column name

    missing = REQUIRED_CUE_COLUMNS - found
    if missing:
        raise RuntimeError(
            f"DjmdCue schema mismatch — missing expected columns: {missing}"
        )

    if 'Number' in found:
        raise RuntimeError(
            "Detected older Rekordbox schema with Number column — "
            "this tool requires Rekordbox 7.x schema"
        )

    print(f"[db] Schema validation passed. Found {len(found)} columns in DjmdCue.")
    return True


def get_track(db: Rekordbox6Database, track_id: str):
    """Retrieve a track's DjmdContent row by its ID.

    Args:
        db:       An open Rekordbox6Database instance.
        track_id: The track ID as a string (DjmdContent.ID is VARCHAR).

    Returns:
        The DjmdContent ORM row.

    Raises:
        ValueError: If the track ID is not found in the library.
    """
    # get_content(ID=...) returns the ORM object directly (not a Query)
    # get_content() with no args returns a Query; filter_by + first() needed there
    content = db.get_content(ID=track_id)
    if content is None:
        raise ValueError(f"Track ID {track_id} not found in library")

    bpm_display = content.BPM / 100 if content.BPM else 0.0
    print(
        f"[db] Track: '{content.Title}' | BPM: {bpm_display:.1f} | "
        f"Length: {content.Length}s"
    )
    return content
