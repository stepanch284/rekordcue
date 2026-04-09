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


def write_cue(db, content, position_ms: int, kind: int) -> None:
    """Insert one cue row into DjmdCue for the given track.

    Kind values (verified from live Rekordbox 7.2.3 data):
        0 = memory cue
        1 = hot cue slot A
        2 = hot cue slot B
        3 = hot cue slot C

    Color=255, ColorTableIndex=22 for hot cues (native Rekordbox defaults).
    Memory cues use Color=0, ColorTableIndex=0.

    created_at / updated_at are set automatically by the StatsFull mixin.

    Args:
        db:           Open Rekordbox6Database instance.
        content:      DjmdContent ORM row for the target track.
        position_ms:  Cue position in milliseconds (integer).
        kind:         Cue kind (0=memory, 1=A, 2=B, 3=C).
    """
    is_hot_cue = kind > 0
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
        Kind=kind,
        Color=255 if is_hot_cue else 0,
        ColorTableIndex=22 if is_hot_cue else 0,
        ActiveLoop=0,
        Comment='',                              # no label — native Rekordbox behaviour
        BeatLoopSize=-1,
        CueMicrosec=round(position_ms) * 1000,  # microseconds
        UUID=str(uuid.uuid4()),
    )

    db.add(cue)
    db.commit()


def safe_write_all(db, content, cues: list) -> Path:
    """Full safety sequence: process guard -> backup -> write all cues.

    cues: list of (position_ms, kind) tuples, e.g.:
        [(0, 1), (4000, 2), (28000, 3), (30000, 0)]

    Order is deliberate:
        1. require_rekordbox_closed() — early, clean error before any mutation.
        2. backup_master_db()         — filesystem copy; abort if backup fails.
        3. write_cue() for each cue  — ORM insert + commit per cue.

    Returns:
        Path to the backup file.
    """
    require_rekordbox_closed()

    db_path = db.db_directory / 'master.db'
    backup = backup_master_db(db_path)
    print(f"Backup created: {backup}")

    try:
        for position_ms, kind in cues:
            write_cue(db, content, position_ms, kind)
    except Exception:
        print(f"Write failed — backup available at {backup}")
        raise

    return backup


def safe_write_sequence(db, content, position_ms: int) -> Path:
    """Legacy single-cue write — kept for compatibility. Writes hot cue A."""
    return safe_write_all(db, content, [(position_ms, 1)])
