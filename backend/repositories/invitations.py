"""Viewer invitations: create / lookup / redeem.

The token format mirrors the auth-challenge magic link: `{id}.{secret}`.
Only the hash of `salt || secret` is stored.

Redemption is idempotent — if the user already has a membership in the
family, we just bump `redemption_count` and don't insert a duplicate.
"""
from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from models import (
    FamilyMembership,
    FamilyRole,
    ViewerInvitation,
)


INVITATION_TTL = timedelta(days=90)


def _random_salt() -> str:
    return secrets.token_hex(16)


def _random_secret() -> str:
    return secrets.token_urlsafe(32)


def _hash(salt: str, value: str) -> str:
    return hashlib.sha256(f"{salt}{value}".encode("utf-8")).hexdigest()


def create_invitation(
    db: Session,
    *,
    family_id: uuid.UUID,
    birth_id: uuid.UUID,
    invited_by_user_id: uuid.UUID,
    display_name_hint: str | None = None,
    email_hint: str | None = None,
    phone_hint: str | None = None,
    ttl: timedelta = INVITATION_TTL,
    role: FamilyRole = FamilyRole.family_viewer,
) -> tuple[ViewerInvitation, str]:
    """Insert a new invitation and return `(row, plaintext_token)`. The
    plaintext token only exists in memory — store the URL the caller
    builds, not this value.
    """
    salt = _random_salt()
    secret = _random_secret()
    invitation = ViewerInvitation(
        family_id=family_id,
        birth_id=birth_id,
        invited_by_user_id=invited_by_user_id,
        role=role,
        salt=salt,
        token_hash=_hash(salt, secret),
        display_name_hint=display_name_hint,
        email_hint=email_hint,
        phone_hint=phone_hint,
        expires_at=datetime.now(timezone.utc) + ttl,
    )
    db.add(invitation)
    db.flush()
    plaintext_token = f"{invitation.id}.{secret}"
    return invitation, plaintext_token


def lookup_by_token(db: Session, token: str) -> ViewerInvitation | None:
    invitation_id_str, _, secret = token.partition(".")
    if not invitation_id_str or not secret:
        return None
    try:
        invitation_id = uuid.UUID(invitation_id_str)
    except ValueError:
        return None
    invitation = db.get(ViewerInvitation, invitation_id)
    if invitation is None:
        return None
    if _hash(invitation.salt, secret) != invitation.token_hash:
        return None
    return invitation


def is_redeemable(invitation: ViewerInvitation, *, now: datetime | None = None) -> bool:
    now = now or datetime.now(timezone.utc)
    if invitation.revoked_at is not None:
        return False
    if invitation.expires_at < now:
        return False
    return True


def list_for_birth(db: Session, *, birth_id: uuid.UUID) -> list[ViewerInvitation]:
    return list(
        db.scalars(
            select(ViewerInvitation)
            .where(ViewerInvitation.birth_id == birth_id)
            .order_by(ViewerInvitation.created_at.desc())
        ).all()
    )


def revoke(db: Session, invitation: ViewerInvitation) -> ViewerInvitation:
    if invitation.revoked_at is None:
        invitation.revoked_at = datetime.now(timezone.utc)
    db.flush()
    return invitation


def redeem(
    db: Session,
    *,
    invitation: ViewerInvitation,
    user_id: uuid.UUID,
) -> FamilyMembership:
    """Attach `user_id` to the invitation's family with the invitation
    role. Idempotent — if the membership exists, we don't change its
    role (preserve existing higher privileges), but still bump
    `redemption_count` so parents can see the link was followed.
    """
    membership = db.scalars(
        select(FamilyMembership).where(
            FamilyMembership.family_id == invitation.family_id,
            FamilyMembership.user_id == user_id,
        )
    ).first()
    if membership is None:
        membership = FamilyMembership(
            family_id=invitation.family_id,
            user_id=user_id,
            role=invitation.role,
        )
        db.add(membership)
        db.flush()
    invitation.redemption_count += 1
    db.flush()
    return membership
