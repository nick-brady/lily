"""User and family-membership reads."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from models import FamilyMembership, User


def get_user(db: Session, user_id: uuid.UUID) -> User | None:
    return db.get(User, user_id)


def list_memberships(db: Session, user_id: uuid.UUID) -> list[FamilyMembership]:
    return list(
        db.scalars(
            select(FamilyMembership).where(FamilyMembership.user_id == user_id)
        ).all()
    )
