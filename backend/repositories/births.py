"""Birth lookups + access control helpers."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from models import AudienceScope, Birth, BirthStatus, FamilyMembership, FamilyRole


PARENT_ROLES: frozenset[FamilyRole] = frozenset(
    {FamilyRole.owner, FamilyRole.co_parent}
)


def visible_scopes_for_role(role: FamilyRole | None) -> frozenset[AudienceScope]:
    """Which `AudienceScope`s a viewer can see, by membership role.

    - No membership: nothing. A birth page is private; being signed in is not
      a relationship to it. Callers 404 rather than serving an empty timeline.
    - family_viewer: group_targeted (the "Family" tier)
    - owner / co_parent: everything

    `AudienceScope.public` is retired — it stays in the enum so the old rows
    remain readable, but nothing is written with it and nobody is granted it.
    """
    if role is None:
        return frozenset()
    if role is FamilyRole.family_viewer:
        return frozenset({AudienceScope.public, AudienceScope.group_targeted})
    return frozenset(AudienceScope)


def create_birth(
    db: Session,
    *,
    family_id: uuid.UUID,
    child_name: str | None,
    slug: str,
    theme: str = "lily",
    status: BirthStatus = BirthStatus.preparing,
    birth_started_at: datetime | None = None,
    birth_completed_at: datetime | None = None,
    due_date: date | None = None,
) -> Birth:
    birth = Birth(
        family_id=family_id,
        child_name=child_name,
        slug=slug,
        theme=theme,
        status=status,
        birth_started_at=birth_started_at,
        birth_completed_at=birth_completed_at,
        due_date=due_date,
    )
    db.add(birth)
    db.flush()
    return birth


def update_birth(
    db: Session,
    *,
    birth: Birth,
    theme: str | None = None,
    child_weight_lbs: float | None = None,
    child_length_in: float | None = None,
    due_date: date | None = None,
    gender_pool_enabled: bool | None = None,
    child_sex: str | None = None,
) -> Birth:
    if theme is not None:
        birth.theme = theme
    if child_weight_lbs is not None:
        birth.child_weight_lbs = child_weight_lbs
    if child_length_in is not None:
        birth.child_length_in = child_length_in
    if due_date is not None:
        birth.due_date = due_date
    # Explicit is-not-None: False is a real value here (turning the
    # gender pool back off must work).
    if gender_pool_enabled is not None:
        birth.gender_pool_enabled = gender_pool_enabled
    if child_sex is not None:
        birth.child_sex = child_sex
    db.flush()
    return birth


def get_birth(db: Session, birth_id: uuid.UUID) -> Birth | None:
    return db.get(Birth, birth_id)


def get_birth_by_slug(db: Session, slug: str) -> Birth | None:
    return db.scalars(select(Birth).where(Birth.slug == slug)).first()


def begin_labor(db: Session, *, birth: Birth, when: datetime) -> bool:
    """Move a birth from `preparing` into `in_labor` (the gentle
    "something's happening" state). No-op once labor has begun or the
    baby is born. Returns True if it actually transitioned.
    """
    if birth.status is not BirthStatus.preparing:
        return False
    birth.status = BirthStatus.in_labor
    if birth.birth_started_at is None:
        birth.birth_started_at = when
    db.flush()
    return True


def mark_born(db: Session, *, birth: Birth, when: datetime) -> None:
    """The Baby Born! moment. Records arrival time and fills in a labor
    start if we never saw a contraction (e.g. a fast or unattended labor).
    """
    birth.status = BirthStatus.born
    birth.birth_completed_at = when
    if birth.birth_started_at is None:
        birth.birth_started_at = when
    db.flush()


def unmark_born(db: Session, *, birth: Birth, resume_labor: bool) -> None:
    """Undo the Baby Born! flip — the recovery path for a mistaken tap.
    Reached by deleting the Born milestone, which *is* the announcement.

    `resume_labor` says whether labor was genuinely underway beforehand
    (the caller checks for a real contraction). If it was, we land back in
    `in_labor` and keep `birth_started_at` — it's a recorded observation.
    If it wasn't, `mark_born` invented that timestamp from the arrival
    time, so returning to `preparing` has to clear it rather than leave a
    labor that never happened on the record.
    """
    birth.status = BirthStatus.in_labor if resume_labor else BirthStatus.preparing
    birth.birth_completed_at = None
    if not resume_labor:
        birth.birth_started_at = None
    db.flush()


def primary_birth_for_family(db: Session, family_id: uuid.UUID) -> Birth | None:
    """The birth used as welcome-screen context for a co-parent invite.
    The membership a co-parent invite grants is family-wide regardless;
    we just pick the most recent non-deleted birth so the redeem screen
    names a real child.
    """
    return db.scalars(
        select(Birth)
        .where(Birth.family_id == family_id, Birth.deleted_at.is_(None))
        .order_by(Birth.created_at.desc())
    ).first()


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
