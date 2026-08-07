"""Birth creation, birth reads/updates, and the timeline listings for both
the authed (`/birth/{id}`) and public (`/b/{slug}`) surfaces."""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

import storage
from account_deletion import erase_birth

from auth import get_current_user, get_optional_current_user
from db import get_db
from models import Birth, Family, FamilyMembership, FamilyRole, User
from repositories import births as births_repo
from repositories import families as families_repo
from repositories import gifts as gifts_repo
from repositories import timeline as timeline_repo
from routes.deps import (
    BirthAccess,
    member_scopes_or_404,
    require_birth_access,
    require_birth_member,
    require_parent_access,
    resolve_public_birth,
)
from routes.serializers import serialize_events_with_engagement
from schemas import (
    BirthCreateIn,
    BirthOut,
    BirthUpdateIn,
    SlugAvailableOut,
    TimelineEventOut,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _clean_slug(raw: str) -> str:
    slug = raw.lower().strip()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"[\s-]+", "-", slug)
    return slug.strip("-")


@router.get("/births/slug-available", response_model=SlugAvailableOut)
def check_slug_available(slug: str, db: Session = Depends(get_db)) -> SlugAvailableOut:
    clean = _clean_slug(slug)
    if not clean:
        return SlugAvailableOut(available=False)
    if births_repo.get_birth_by_slug(db, clean) is None:
        return SlugAvailableOut(available=True)
    for n in range(2, 100):
        candidate = f"{clean}-{n}"
        if births_repo.get_birth_by_slug(db, candidate) is None:
            return SlugAvailableOut(available=False, suggestion=candidate)
    return SlugAvailableOut(available=False)


def _resolve_birth_family(
    db: Session, *, payload: BirthCreateIn, current_user: User
) -> Family:
    """A fresh family for a first birth; an existing one (second child,
    twins) when `family_id` is given — the caller must already be an
    owner/co-parent there, so co-parents and viewers on the first birth
    carry over automatically."""
    if payload.family_id is None:
        family = Family(
            primary_owner_user_id=current_user.id,
            display_name=f"{payload.baby_name} Family",
        )
        db.add(family)
        db.flush()
        db.add(FamilyMembership(
            family_id=family.id,
            user_id=current_user.id,
            role=FamilyRole.owner,
        ))
        db.flush()
        return family

    family = db.get(Family, payload.family_id)
    if family is None:
        raise HTTPException(status_code=404, detail="Family not found")
    membership = families_repo.get_membership(
        db, family_id=family.id, user_id=current_user.id
    )
    if membership is None or not births_repo.is_parent(membership.role):
        raise HTTPException(status_code=403, detail="Parents only")
    return family


@router.post("/births", response_model=BirthOut)
def create_birth(
    payload: BirthCreateIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BirthOut:
    slug = _clean_slug(payload.slug)
    if not slug:
        raise HTTPException(status_code=400, detail="Invalid slug")
    if births_repo.get_birth_by_slug(db, slug) is not None:
        raise HTTPException(status_code=409, detail="Slug already taken")

    family = _resolve_birth_family(db, payload=payload, current_user=current_user)

    birth = births_repo.create_birth(
        db,
        family_id=family.id,
        child_name=payload.baby_name,
        slug=slug,
        theme=payload.theme,
        due_date=payload.due_date,
    )
    db.commit()
    db.refresh(birth)
    return BirthOut.model_validate(birth)


@router.get("/birth/{birth_id}", response_model=BirthOut)
def get_birth(access: BirthAccess = Depends(require_birth_access)) -> BirthOut:
    return BirthOut.model_validate(access.birth)


@router.patch("/birth/{birth_id}", response_model=BirthOut)
def update_birth(
    payload: BirthUpdateIn,
    access: BirthAccess = Depends(require_parent_access),
    db: Session = Depends(get_db),
) -> BirthOut:
    births_repo.update_birth(
        db,
        birth=access.birth,
        theme=payload.theme,
        child_weight_lbs=payload.child_weight_lbs,
        child_length_in=payload.child_length_in,
        due_date=payload.due_date,
        gender_pool_enabled=payload.gender_pool_enabled,
        child_sex=payload.child_sex,
    )
    # The measurements are drawn on the keepsake, and they're usually recorded
    # hours after the birth — so settling the pool is one of the likeliest
    # reasons existing artwork is now out of date.
    if (
        payload.child_weight_lbs is not None
        or payload.child_length_in is not None
        or payload.child_sex is not None
    ):
        gifts_repo.mark_stale(db, birth_id=access.birth.id)
    db.commit()
    db.refresh(access.birth)
    return BirthOut.model_validate(access.birth)


@router.delete("/birth/{birth_id}", status_code=204)
def delete_birth(
    access: BirthAccess = Depends(require_parent_access),
    db: Session = Depends(get_db),
) -> Response:
    """The settings danger zone: erase this page and everything on it.

    Owner-only — a co-parent shouldn't be able to take the page away from
    the person who made it. Reuses the account-deletion erase (same
    commerce guard: births with gift orders soft-delete + scrub so Stripe
    payment records survive), and follows the same commit-before-S3
    ordering — the failure mode is orphaned-but-logged S3 objects, never
    DB rows pointing at deleted files."""
    if access.role is not FamilyRole.owner:
        raise HTTPException(
            status_code=403, detail="Only the page owner can delete it"
        )
    # After a hard delete + commit the ORM object is unloadable — grab the
    # ids while the row still exists.
    birth_id = access.birth.id
    family_id = access.birth.family_id
    now = datetime.now(timezone.utc)
    s3_keys, hard_deleted = erase_birth(db, access.birth, now)

    # A family with no pages left is not a thing anyone should have to manage.
    # It used to survive the last deletion, invisible (the account page bounces
    # you to /setup when you have no births) but still offered in the setup
    # wizard as somewhere to "add this baby to" — quietly re-admitting every
    # co-parent and viewer who was ever on it. Same rule as account deletion:
    # the family goes only when the birth went completely, because a
    # soft-deleted birth (one with gift orders, kept so Stripe records survive)
    # still points at it and the FK cascades.
    remaining = db.scalar(
        select(func.count())
        .select_from(Birth)
        .where(Birth.family_id == family_id, Birth.deleted_at.is_(None))
    )
    if remaining == 0:
        if hard_deleted:
            db.execute(delete(Family).where(Family.id == family_id))  # memberships CASCADE
        else:
            family = db.get(Family, family_id)
            if family is not None:
                family.display_name = "Deleted"
            db.execute(
                delete(FamilyMembership).where(FamilyMembership.family_id == family_id)
            )
    db.commit()

    failed = storage.delete_objects(s3_keys)
    if failed:
        logger.error(
            "birth-deletion: %d S3 objects not deleted for birth %s: %s",
            len(failed),
            birth_id,
            failed,
        )
    return Response(status_code=204)


@router.get("/birth/{birth_id}/timeline", response_model=list[TimelineEventOut])
def list_timeline(
    access: BirthAccess = Depends(require_birth_access),
    current_user: User = Depends(get_current_user),
    after_sequence_id: int | None = None,
    limit: int = 1000,
    db: Session = Depends(get_db),
) -> list[TimelineEventOut]:
    visible = births_repo.visible_scopes_for_role(access.role)
    events = timeline_repo.list_events(
        db,
        birth_id=access.birth.id,
        after_sequence_id=after_sequence_id,
        limit=limit,
        audience_scopes=visible,
    )
    return serialize_events_with_engagement(
        db, events, requester_user_id=current_user.id
    )


@router.get("/b/{slug}", response_model=BirthOut)
def public_birth(
    slug: str,
    current_user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
) -> BirthOut:
    """The birth behind a slug — members only.

    Optional auth rather than required, so that a caller with no session
    gets the same 404 as an unused slug instead of a 401 announcing that
    something is here worth signing in for. The preview a stranger used to
    see lives on `/invite/{token}` now.
    """
    birth = resolve_public_birth(db, slug)
    require_birth_member(db, birth, current_user)
    return BirthOut.model_validate(birth)


@router.get("/b/{slug}/timeline", response_model=list[TimelineEventOut])
def public_timeline(
    slug: str,
    after_sequence_id: int | None = None,
    limit: int = 1000,
    current_user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
) -> list[TimelineEventOut]:
    birth = resolve_public_birth(db, slug)
    visible = member_scopes_or_404(db, birth, current_user)
    events = timeline_repo.list_events(
        db,
        birth_id=birth.id,
        after_sequence_id=after_sequence_id,
        limit=limit,
        audience_scopes=visible,
    )
    return serialize_events_with_engagement(
        db, events, requester_user_id=current_user.id
    )
