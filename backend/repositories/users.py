"""User and family-membership reads."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from models import FamilyMembership, User


def get_user(db: Session, user_id: uuid.UUID) -> User | None:
    return db.get(User, user_id)


def set_display_name(db: Session, *, user: User, name: str) -> User:
    user.display_name = name
    db.flush()
    return user


def set_display_name_if_empty(db: Session, *, user: User, name: str | None) -> bool:
    """Seed a name only when the user doesn't already have one — used to
    carry an invite's `display_name_hint` onto the new account ("Grandma
    Rose") without ever clobbering a name the user chose. Returns True if
    it set one.
    """
    if name and not user.display_name:
        cleaned = name.strip()
        if cleaned:
            user.display_name = cleaned
            db.flush()
            return True
    return False


def list_memberships(db: Session, user_id: uuid.UUID) -> list[FamilyMembership]:
    return list(
        db.scalars(
            select(FamilyMembership).where(FamilyMembership.user_id == user_id)
        ).all()
    )
