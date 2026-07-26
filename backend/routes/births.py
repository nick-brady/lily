"""Birth creation, birth reads/updates, and the timeline listings for both
the authed (`/birth/{id}`) and public (`/b/{slug}`) surfaces."""
from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from auth import get_current_user
from db import get_db
from models import Family, FamilyMembership, FamilyRole, User
from repositories import births as births_repo
from repositories import families as families_repo
from repositories import timeline as timeline_repo
from routes.deps import (
    BirthAccess,
    require_birth_access,
    require_parent_access,
    resolve_public_birth,
    scope_set_for_visitor,
)
from routes.serializers import serialize_events_with_engagement
from schemas import (
    BirthCreateIn,
    BirthOut,
    BirthUpdateIn,
    SlugAvailableOut,
    TimelineEventOut,
)

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
    )
    db.commit()
    db.refresh(access.birth)
    return BirthOut.model_validate(access.birth)


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
def public_birth(slug: str, db: Session = Depends(get_db)) -> BirthOut:
    return BirthOut.model_validate(resolve_public_birth(db, slug))


@router.get("/b/{slug}/timeline", response_model=list[TimelineEventOut])
def public_timeline(
    slug: str,
    after_sequence_id: int | None = None,
    limit: int = 1000,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[TimelineEventOut]:
    birth = resolve_public_birth(db, slug)
    visible = scope_set_for_visitor(db, birth, current_user)
    events = timeline_repo.list_events(
        db,
        birth_id=birth.id,
        after_sequence_id=after_sequence_id,
        limit=limit,
        audience_scopes=visible,
    )
    return serialize_events_with_engagement(
        db,
        events,
        requester_user_id=current_user.id if current_user else None,
    )
