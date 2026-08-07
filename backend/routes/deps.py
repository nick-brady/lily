"""Shared access-control dependencies for the route modules.

Birth-scoped routes pass through `BirthAccess` (parents only in PR 2).
Public routes (`/b/{slug}*`) resolve the birth by slug; the bare page
is unauthenticated, everything richer requires a session.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Path as PathParam
from sqlalchemy.orm import Session

from auth import get_current_user, get_current_user_stream
from db import get_db
from models import (
    AudienceScope,
    Birth,
    Family,
    FamilyMembership,
    FamilyRole,
    TimelineEvent,
    User,
)
from repositories import births as births_repo
from repositories import families as families_repo
from repositories import timeline as timeline_repo


@dataclass
class BirthAccess:
    birth: Birth
    role: FamilyRole


def _resolve_birth_access(
    db: Session, *, birth_id: uuid.UUID, current_user: User
) -> BirthAccess:
    birth = births_repo.get_birth(db, birth_id)
    if birth is None or birth.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Birth not found")
    role = births_repo.user_role_for_birth(db, user_id=current_user.id, birth=birth)
    if role is None:
        raise HTTPException(status_code=403, detail="Not a member of this family")
    return BirthAccess(birth=birth, role=role)


def require_birth_access(
    birth_id: uuid.UUID = PathParam(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BirthAccess:
    return _resolve_birth_access(db, birth_id=birth_id, current_user=current_user)


def require_parent_access(access: BirthAccess = Depends(require_birth_access)) -> BirthAccess:
    if not births_repo.is_parent(access.role):
        raise HTTPException(status_code=403, detail="Parents only")
    return access


def require_parent_access_stream(
    birth_id: uuid.UUID = PathParam(...),
    current_user: User = Depends(get_current_user_stream),
    db: Session = Depends(get_db),
) -> BirthAccess:
    """Parent gate for browser-navigated downloads: `get_current_user_stream`
    accepts the JWT via header *or* `?token=` (an <a download> can't set
    headers, same constraint as EventSource)."""
    access = _resolve_birth_access(db, birth_id=birth_id, current_user=current_user)
    if not births_repo.is_parent(access.role):
        raise HTTPException(status_code=403, detail="Parents only")
    return access


@dataclass
class FamilyAccess:
    family: Family
    membership: FamilyMembership


def require_family_parent(
    family_id: uuid.UUID = PathParam(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FamilyAccess:
    """Family-scoped sibling of `require_parent_access`. Co-parent
    management acts on a whole family (the grant is family-wide), so it
    gates on family membership rather than a single birth.
    """
    family = db.get(Family, family_id)
    if family is None:
        raise HTTPException(status_code=404, detail="Family not found")
    membership = families_repo.get_membership(
        db, family_id=family_id, user_id=current_user.id
    )
    if membership is None or not births_repo.is_parent(membership.role):
        raise HTTPException(status_code=403, detail="Parents only")
    return FamilyAccess(family=family, membership=membership)


# ============ Public birth ============
# "Public" is a routing shape here, not an access level. A birth page is
# private (2026-08-06 decision, superseding the 2026-07-23 one): every
# `/b/{slug}` surface — the birth itself, the timeline, the stream,
# engagement — requires family membership, and anyone else gets the same
# 404 as a slug that was never taken. Being signed in is not a
# relationship to a page.
#
# The way in is an invite link. `/invite/{token}` carries the preview that
# used to live on `/b/{slug}` — the baby's name, whether they're here, the
# theme — so a forwarded link still opens with the hook before the sign-in
# ask. The token is what distinguishes someone the family shared with from
# someone who guessed a name.


def resolve_public_birth(db: Session, slug: str) -> Birth:
    birth = births_repo.get_birth_by_slug(db, slug)
    if birth is None or birth.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Birth not found")
    if birth.is_locked_to_invited:
        # PR 2 has no viewer-token mechanism; locked births are unreachable
        # publicly until PR 3 lands viewer invitations.
        raise HTTPException(status_code=403, detail="This birth is invited-only")
    return birth


def require_birth_member(db: Session, birth: Birth, user: User | None) -> FamilyRole:
    """This user's role on this birth — or the same 404 an unused slug
    gives, so a page's existence never leaks to someone without a place on
    it. Anonymous callers land here too: no session is just another way of
    not being a member.
    """
    role = (
        births_repo.user_role_for_birth(db, user_id=user.id, birth=birth)
        if user is not None
        else None
    )
    if role is None:
        raise HTTPException(status_code=404, detail="Birth not found")
    return role


def member_scopes_or_404(
    db: Session, birth: Birth, user: User | None
) -> frozenset[AudienceScope]:
    """The audience scopes this user may see on this birth, or 404."""
    return births_repo.visible_scopes_for_role(require_birth_member(db, birth, user))


@dataclass
class PublicEngagementAccess:
    """Auth context for engagement on the slug-shaped surface.

    Aunt Linda still scans the QR card from a printed announcement and
    leaves a comment (Persona 1 Stage 9: "she wasn't even invited to the
    page originally") — the card carries an invite link, so redeeming it
    is what makes her a member. What no longer works is arriving with an
    account and no invitation.
    """

    birth: Birth
    user: User
    role: FamilyRole  # members only; non-members 404 before this is built


def require_public_engagement(
    slug: str = PathParam(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PublicEngagementAccess:
    birth = resolve_public_birth(db, slug)
    role = require_birth_member(db, birth, current_user)
    return PublicEngagementAccess(birth=birth, user=current_user, role=role)


def require_visible_event(
    db: Session,
    event_id: uuid.UUID,
    *,
    birth: Birth,
    role: FamilyRole | None,
) -> TimelineEvent:
    """Resolve a timeline event the caller is allowed to engage with.

    A reaction or comment on an event the caller can't see is meaningless
    (and would leak audience info via the existence-check). 404 keeps the
    audience scope opaque.

    `role=None` means an authed stranger who found the page via QR card
    or shared link — they get public-scope visibility only.
    """
    event = timeline_repo.get_event(db, event_id)
    if (
        event is None
        or event.birth_id != birth.id
        or event.deleted_at is not None
    ):
        raise HTTPException(status_code=404, detail="Event not found")
    visible = births_repo.visible_scopes_for_role(role)
    if event.audience_scope not in visible:
        raise HTTPException(status_code=404, detail="Event not found")
    return event
