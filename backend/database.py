import sqlite3
from datetime import datetime
from typing import Optional, List
from pathlib import Path

DB_PATH = Path(__file__).parent / "contractions.db"


def get_connection():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS contractions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            start_time TEXT NOT NULL,
            end_time TEXT,
            duration_seconds INTEGER,
            ignore_interval_before INTEGER DEFAULT 0
        )
    """)
    # Add ignore_interval_before column if it doesn't exist (for existing databases)
    cursor.execute("PRAGMA table_info(contractions)")
    columns = [col[1] for col in cursor.fetchall()]
    if "ignore_interval_before" not in columns:
        cursor.execute("ALTER TABLE contractions ADD COLUMN ignore_interval_before INTEGER DEFAULT 0")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS updates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            type TEXT NOT NULL,
            content TEXT,
            photo_filename TEXT,
            audio_filename TEXT,
            milestone TEXT
        )
    """)
    # Add audio_filename column if it doesn't exist (for existing databases)
    cursor.execute("PRAGMA table_info(updates)")
    columns = [col[1] for col in cursor.fetchall()]
    if "audio_filename" not in columns:
        cursor.execute("ALTER TABLE updates ADD COLUMN audio_filename TEXT")
    conn.commit()
    conn.close()


def create_contraction(start_time: datetime, end_time: Optional[datetime] = None) -> dict:
    conn = get_connection()
    cursor = conn.cursor()

    duration_seconds = None
    if end_time:
        duration_seconds = int((end_time - start_time).total_seconds())

    cursor.execute(
        "INSERT INTO contractions (start_time, end_time, duration_seconds) VALUES (?, ?, ?)",
        (start_time.isoformat(), end_time.isoformat() if end_time else None, duration_seconds)
    )
    conn.commit()

    contraction_id = cursor.lastrowid
    conn.close()

    return {
        "id": contraction_id,
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat() if end_time else None,
        "duration_seconds": duration_seconds
    }


def update_contraction(contraction_id: int, end_time: datetime) -> Optional[dict]:
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT start_time FROM contractions WHERE id = ?", (contraction_id,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        return None

    start_time = datetime.fromisoformat(row["start_time"])
    duration_seconds = int((end_time - start_time).total_seconds())

    cursor.execute(
        "UPDATE contractions SET end_time = ?, duration_seconds = ? WHERE id = ?",
        (end_time.isoformat(), duration_seconds, contraction_id)
    )
    conn.commit()
    conn.close()

    return {
        "id": contraction_id,
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
        "duration_seconds": duration_seconds
    }


def get_all_contractions() -> List[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM contractions ORDER BY start_time DESC")
    rows = cursor.fetchall()
    conn.close()

    def ensure_utc_marker(ts):
        # Add Z suffix if timestamp doesn't have timezone info
        if ts and not ts.endswith('Z') and '+' not in ts:
            return ts + 'Z'
        return ts

    return [
        {
            "id": row["id"],
            "start_time": ensure_utc_marker(row["start_time"]),
            "end_time": ensure_utc_marker(row["end_time"]),
            "duration_seconds": row["duration_seconds"],
            "ignore_interval_before": bool(row["ignore_interval_before"]) if row["ignore_interval_before"] is not None else False
        }
        for row in rows
    ]


def delete_contraction(contraction_id: int) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM contractions WHERE id = ?", (contraction_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


def toggle_ignore_interval(contraction_id: int) -> Optional[dict]:
    """Toggle the ignore_interval_before flag on a contraction"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM contractions WHERE id = ?", (contraction_id,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        return None

    new_value = 0 if row["ignore_interval_before"] else 1
    cursor.execute(
        "UPDATE contractions SET ignore_interval_before = ? WHERE id = ?",
        (new_value, contraction_id)
    )
    conn.commit()

    def ensure_utc_marker(ts):
        if ts and not ts.endswith('Z') and '+' not in ts:
            return ts + 'Z'
        return ts

    result = {
        "id": row["id"],
        "start_time": ensure_utc_marker(row["start_time"]),
        "end_time": ensure_utc_marker(row["end_time"]),
        "duration_seconds": row["duration_seconds"],
        "ignore_interval_before": bool(new_value)
    }
    conn.close()
    return result


# Update functions
def create_update(timestamp: datetime, update_type: str, content: str = None,
                  photo_filename: str = None, audio_filename: str = None, milestone: str = None) -> dict:
    conn = get_connection()
    cursor = conn.cursor()

    # Store with Z suffix to indicate UTC
    timestamp_str = timestamp.isoformat() + 'Z' if not timestamp.tzinfo else timestamp.isoformat()

    cursor.execute(
        """INSERT INTO updates (timestamp, type, content, photo_filename, audio_filename, milestone)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (timestamp_str, update_type, content, photo_filename, audio_filename, milestone)
    )
    conn.commit()

    update_id = cursor.lastrowid
    conn.close()

    return {
        "id": update_id,
        "timestamp": timestamp_str,
        "type": update_type,
        "content": content,
        "photo_filename": photo_filename,
        "audio_filename": audio_filename,
        "milestone": milestone
    }


def get_all_updates() -> List[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM updates ORDER BY timestamp DESC")
    rows = cursor.fetchall()
    conn.close()

    def ensure_utc_marker(ts):
        # Add Z suffix if timestamp doesn't have timezone info
        if ts and not ts.endswith('Z') and '+' not in ts:
            return ts + 'Z'
        return ts

    return [
        {
            "id": row["id"],
            "timestamp": ensure_utc_marker(row["timestamp"]),
            "type": row["type"],
            "content": row["content"],
            "photo_filename": row["photo_filename"],
            "audio_filename": row["audio_filename"],
            "milestone": row["milestone"]
        }
        for row in rows
    ]


def update_update(update_id: int, content: str) -> Optional[dict]:
    """Update the content/caption of an update"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM updates WHERE id = ?", (update_id,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        return None

    cursor.execute("UPDATE updates SET content = ? WHERE id = ?", (content, update_id))
    conn.commit()

    cursor.execute("SELECT * FROM updates WHERE id = ?", (update_id,))
    row = cursor.fetchone()
    conn.close()

    return {
        "id": row["id"],
        "timestamp": row["timestamp"],
        "type": row["type"],
        "content": row["content"],
        "photo_filename": row["photo_filename"],
        "audio_filename": row["audio_filename"],
        "milestone": row["milestone"]
    }


def delete_update(update_id: int) -> Optional[dict]:
    """Delete an update and return the media filenames if it had any"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT photo_filename, audio_filename FROM updates WHERE id = ?", (update_id,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        return None

    result = {
        "photo_filename": row["photo_filename"],
        "audio_filename": row["audio_filename"]
    }
    cursor.execute("DELETE FROM updates WHERE id = ?", (update_id,))
    conn.commit()
    conn.close()

    return result


# Initialize database on module import
init_db()
