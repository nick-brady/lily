from datetime import datetime
from typing import Optional, List

from sqlalchemy import select

from db import session_scope
from models import Contraction, Update


def _ensure_utc_marker(ts: Optional[str]) -> Optional[str]:
    if ts and not ts.endswith("Z") and "+" not in ts:
        return ts + "Z"
    return ts


def _contraction_dict(c: Contraction) -> dict:
    return {
        "id": c.id,
        "start_time": _ensure_utc_marker(c.start_time),
        "end_time": _ensure_utc_marker(c.end_time),
        "duration_seconds": c.duration_seconds,
        "ignore_interval_before": bool(c.ignore_interval_before),
    }


def _update_dict(u: Update) -> dict:
    return {
        "id": u.id,
        "timestamp": _ensure_utc_marker(u.timestamp),
        "type": u.type,
        "content": u.content,
        "photo_filename": u.photo_filename,
        "audio_filename": u.audio_filename,
        "milestone": u.milestone,
    }


def create_contraction(start_time: datetime, end_time: Optional[datetime] = None) -> dict:
    duration_seconds = int((end_time - start_time).total_seconds()) if end_time else None

    with session_scope() as s:
        c = Contraction(
            start_time=start_time.isoformat(),
            end_time=end_time.isoformat() if end_time else None,
            duration_seconds=duration_seconds,
        )
        s.add(c)
        s.flush()
        return _contraction_dict(c)


def update_contraction(contraction_id: int, end_time: datetime) -> Optional[dict]:
    with session_scope() as s:
        c = s.get(Contraction, contraction_id)
        if not c:
            return None
        start_time = datetime.fromisoformat(c.start_time.rstrip("Z"))
        c.end_time = end_time.isoformat()
        c.duration_seconds = int((end_time - start_time).total_seconds())
        s.flush()
        return _contraction_dict(c)


def get_all_contractions() -> List[dict]:
    with session_scope() as s:
        rows = s.scalars(
            select(Contraction).order_by(Contraction.start_time.desc())
        ).all()
        return [_contraction_dict(c) for c in rows]


def delete_contraction(contraction_id: int) -> bool:
    with session_scope() as s:
        c = s.get(Contraction, contraction_id)
        if not c:
            return False
        s.delete(c)
        return True


def toggle_ignore_interval(contraction_id: int) -> Optional[dict]:
    with session_scope() as s:
        c = s.get(Contraction, contraction_id)
        if not c:
            return None
        c.ignore_interval_before = not c.ignore_interval_before
        s.flush()
        return _contraction_dict(c)


def create_update(
    timestamp: datetime,
    update_type: str,
    content: Optional[str] = None,
    photo_filename: Optional[str] = None,
    audio_filename: Optional[str] = None,
    milestone: Optional[str] = None,
) -> dict:
    timestamp_str = timestamp.isoformat() + "Z" if not timestamp.tzinfo else timestamp.isoformat()

    with session_scope() as s:
        u = Update(
            timestamp=timestamp_str,
            type=update_type,
            content=content,
            photo_filename=photo_filename,
            audio_filename=audio_filename,
            milestone=milestone,
        )
        s.add(u)
        s.flush()
        return _update_dict(u)


def get_all_updates() -> List[dict]:
    with session_scope() as s:
        rows = s.scalars(
            select(Update).order_by(Update.timestamp.desc())
        ).all()
        return [_update_dict(u) for u in rows]


def update_update(update_id: int, content: str) -> Optional[dict]:
    with session_scope() as s:
        u = s.get(Update, update_id)
        if not u:
            return None
        u.content = content
        s.flush()
        return _update_dict(u)


def delete_update(update_id: int) -> Optional[dict]:
    with session_scope() as s:
        u = s.get(Update, update_id)
        if not u:
            return None
        media = {"photo_filename": u.photo_filename, "audio_filename": u.audio_filename}
        s.delete(u)
        return media
