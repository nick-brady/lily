"""Birth lookups + access control helpers."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from models import Birth, BirthStatus, FamilyMembership, FamilyRole


PARENT_ROLES: frozenset[FamilyRole] = frozenset(
    {FamilyRole.owner, FamilyRole.co_parent}
)


def create_birth(
    db: Session,
    *,
    family_id: uuid.UUID,
    child_name: str | None,
    slug: str,
    status: BirthStatus = BirthStatus.preparing,
    birth_started_at: datetime | None = None,
    birth_completed_at: datetime | None = None,
) -> Birth:
    birth = Birth(
        family_id=family_id,
        child_name=child_name,
        slug=slug,
        status=status,
        birth_started_at=birth_started_at,
        birth_completed_at=birth_completed_at,
    )
    db.add(birth)
    db.flush()
    return birth


def get_birth(db: Session, birth_id: uuid.UUID) -> Birth | None:
    return db.get(Birth, birth_id)


def get_birth_by_slug(db: Session, slug: str) -> Birth | None:
    return db.scalars(select(Birth).where(Birth.slug == slug)).first()


def user_role_for_birth(
    db: Session, *, user_id: uuid.UUID, birth: Birth
) -> FamilyRole | None:
    membership = db.scalars(
        select(FamilyMembership).where(
            FamilyMembership.family_id == birth.family_id,
            FamilyMembership.user_id == user_id,
        )
    ).first()
    return membership.role if membership else None


def is_parent(role: FamilyRole | None) -> bool:
    return role in PARENT_ROLES


def list_parent_user_ids(db: Session, family_id: uuid.UUID) -> Iterable[uuid.UUID]:
    rows = db.scalars(
        select(FamilyMembership.user_id).where(
            FamilyMembership.family_id == family_id,
            FamilyMembership.role.in_([r.value for r in PARENT_ROLES]),
        )
    ).all()
    return rows
