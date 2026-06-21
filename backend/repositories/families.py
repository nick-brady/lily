"""Family and membership reads + creates."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from models import Family, FamilyMembership, FamilyRole, User
from repositories.births import PARENT_ROLES


def create_family(
    db: Session,
    *,
    display_name: str,
    primary_owner_user_id: uuid.UUID,
) -> Family:
    family = Family(
        display_name=display_name,
        primary_owner_user_id=primary_owner_user_id,
    )
    db.add(family)
    db.flush()
    return family


def add_member(
    db: Session,
    *,
    family_id: uuid.UUID,
    user_id: uuid.UUID,
    role: FamilyRole,
) -> FamilyMembership:
    membership = FamilyMembership(family_id=family_id, user_id=user_id, role=role)
    db.add(membership)
    db.flush()
    return membership


def list_parents(
    db: Session, *, family_id: uuid.UUID
) -> list[tuple[FamilyMembership, User]]:
    """Owner + co-parent memberships joined to their users, oldest first.
    Used to render the "Your family" block on the account page.
    """
    rows = db.execute(
        select(FamilyMembership, User)
        .join(User, User.id == FamilyMembership.user_id)
        .where(
            FamilyMembership.family_id == family_id,
            FamilyMembership.role.in_([r.value for r in PARENT_ROLES]),
        )
        .order_by(FamilyMembership.joined_at.asc())
    ).all()
    return [(m, u) for m, u in rows]


def get_membership(
    db: Session, *, family_id: uuid.UUID, user_id: uuid.UUID
) -> FamilyMembership | None:
    return db.scalars(
        select(FamilyMembership).where(
            FamilyMembership.family_id == family_id,
            FamilyMembership.user_id == user_id,
        )
    ).first()
