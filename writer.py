"""
writer.py — Safety guard, backup, and hot cue write logic for RekordCue.

Exports:
    require_rekordbox_closed()       — raises RuntimeError if rekordbox.exe is running
    backup_master_db(db_path)        — creates timestamped .bak before any write
    write_hot_cue(db, content, ms)   — inserts DjmdCue row via pyrekordbox ORM
    safe_write_sequence(db, content, ms) -> Path  — chains all three in correct order
"""

import shutil
import time
import uuid
from pathlib import Path

import psutil

from pyrekordbox.db6.tables import DjmdCue


def require_rekordbox_closed() -> None:
    """Raise RuntimeError if rekordbox.exe is currently running.

    Iterates the OS process list via psutil.  Silently skips any process that
    vanishes or is inaccessible mid-iteration.
    """
    for proc in psutil.process_iter(['name']):
        try:
            name = proc.info.get('name') or ''
            if 'rekordbox' in name.lower():
                raise RuntimeError(
                    f"rekordbox.exe is running (PID {proc.pid}). "
                    "Close Rekordbox before writing cue points."
                )
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            # Process vanished or is inaccessible — skip silently.
            continue


def backup_master_db(db_path: Path) -> Path:
    """Create a timestamped backup of master.db before any write.

    Args:
        db_path: Absolute path to master.db.

    Returns:
        Path to the newly created backup file.

    Raises:
        RuntimeError: If shutil.copy2 fails for any reason.
    """
    timestamp = time.strftime('%Y%m%d_%H%M%S')
    backup_path = db_path.parent / f'master.db.rekordcue_{timestamp}.bak'
    try:
        shutil.copy2(db_path, backup_path)
    except Exception as exc:
        raise RuntimeError(
            f"Backup failed — write aborted. No changes made. "
            f"(source={db_path}, dest={backup_path}): {exc}"
        ) from exc
    return backup_path


def write_hot_cue(db, content, position_ms: int) -> None:
    """Insert one hot cue (slot A) row into DjmdCue for the given track.

    Field values match live Rekordbox 7.2.3 rows as documented in RESEARCH.md:
        Kind=1            — hot cue slot A
        Color=255         — default hot cue colour (NOT the 0–8 palette index)
        ColorTableIndex=22 — default appearance index (most common in live data)
        CueMicrosec       — InMsec * 1000 (microsecond precision field)

    created_at / updated_at are intentionally omitted — the StatsFull mixin
    sets them to datetime.now automatically.

    Args:
        db:           Open Rekordbox6Database instance.
        content:      DjmdContent ORM row for the target track.
        position_ms:  Cue position in milliseconds (integer).
    """
    cue_id = str(db.generate_unused_id(DjmdCue))

    cue = DjmdCue(
        ID=cue_id,
        ContentID=content.ID,
        ContentUUID=content.UUID,
        InMsec=round(position_ms),
        InFrame=0,
        InMpegFrame=0,
        InMpegAbs=0,
        OutMsec=-1,
        OutFrame=-1,
        OutMpegFrame=-1,
        OutMpegAbs=-1,
        Kind=1,                                 # hot cue slot A
        Color=255,                              # default hot cue colour
        ColorTableIndex=22,                     # default appearance index
        ActiveLoop=0,
        Comment='',                             # no label — native Rekordbox behaviour
        BeatLoopSize=-1,
        CueMicrosec=round(position_ms) * 1000,  # microseconds
        UUID=str(uuid.uuid4()),
    )

    db.add(cue)
    db.commit()   # pyrekordbox commit() has built-in rekordbox process guard + USN management


def safe_write_sequence(db, content, position_ms: int) -> Path:
    """Full safety sequence: process guard -> backup -> write.

    Order is deliberate:
        1. require_rekordbox_closed() — early, clean error before any mutation.
        2. backup_master_db()         — filesystem copy; if this fails, no DB changes made.
        3. write_hot_cue()            — ORM insert + commit.

    Args:
        db:           Open Rekordbox6Database instance.
        content:      DjmdContent ORM row for the target track.
        position_ms:  Cue position in milliseconds (integer).

    Returns:
        Path to the backup file created before the write.

    Raises:
        RuntimeError: From require_rekordbox_closed() or backup_master_db() on failure.
        Exception:    Propagates from write_hot_cue() on commit failure; backup still exists.
    """
    require_rekordbox_closed()

    db_path = db.db_directory / 'master.db'
    backup = backup_master_db(db_path)
    print(f"Backup created: {backup}")

    try:
        write_hot_cue(db, content, position_ms)
    except Exception as exc:
        print(f"Write failed — backup available at {backup}")
        raise

    return backup
