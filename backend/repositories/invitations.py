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
    User,
    ViewerInvitation,
    ViewerInvitationRedemption,
)


INVITATION_TTL = timedelta(days=90)

# Higher rank = more privilege. Used by `redeem` to upgrade an existing
# membership (e.g. a family viewer who later accepts a co-parent invite)
# without ever downgrading one.
_ROLE_RANK: dict[FamilyRole, int] = {
    FamilyRole.family_viewer: 0,
    FamilyRole.co_parent: 1,
    FamilyRole.owner: 2,
}


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
    # Keep the plaintext so the link can be re-copied later (see model note).
    invitation.token = plaintext_token
    db.flush()
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


def list_for_family(
    db: Session,
    *,
    family_id: uuid.UUID,
    role: FamilyRole | None = None,
) -> list[ViewerInvitation]:
    stmt = select(ViewerInvitation).where(ViewerInvitation.family_id == family_id)
    if role is not None:
        stmt = stmt.where(ViewerInvitation.role == role)
    return list(db.scalars(stmt.order_by(ViewerInvitation.created_at.desc())).all())


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
    role. Idempotent — if the membership already exists we keep it, but
    *upgrade* its role when the invitation grants a higher one (e.g. a
    family viewer who later accepts a co-parent invite). We never
    downgrade, so an owner who follows a viewer link stays an owner.
    Either way we bump `redemption_count` so parents can see the link
    was followed.
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
    elif _ROLE_RANK[invitation.role] > _ROLE_RANK[membership.role]:
        membership.role = invitation.role
        db.flush()

    # Record *who* redeemed, once per person per link, so parents can see
    # the names behind the redemption count.
    already = db.scalars(
        select(ViewerInvitationRedemption).where(
            ViewerInvitationRedemption.invitation_id == invitation.id,
            ViewerInvitationRedemption.user_id == user_id,
        )
    ).first()
    if already is None:
        db.add(
            ViewerInvitationRedemption(invitation_id=invitation.id, user_id=user_id)
        )
        # Count distinct people, not clicks — re-following a link you've
        # already redeemed shouldn't inflate the number.
        invitation.redemption_count += 1
        db.flush()
    return membership


def list_redemptions(
    db: Session, *, invitation: ViewerInvitation
) -> list[tuple[ViewerInvitationRedemption, User, FamilyRole | None]]:
    """Who redeemed this link, with their user and *current* family role,
    in the order they joined. The role comes from a left join on the
    membership so the UI can tell a plain viewer (removable) apart from a
    co-parent/owner who happened to follow the link. It's None only if the
    membership is somehow gone while a redemption row lingers.
    """
    rows = db.execute(
        select(ViewerInvitationRedemption, User, FamilyMembership.role)
        .join(User, User.id == ViewerInvitationRedemption.user_id)
        .outerjoin(
            FamilyMembership,
            (FamilyMembership.user_id == ViewerInvitationRedemption.user_id)
            & (FamilyMembership.family_id == invitation.family_id),
        )
        .where(ViewerInvitationRedemption.invitation_id == invitation.id)
        .order_by(ViewerInvitationRedemption.redeemed_at.asc())
    ).all()
    return [(r, u, role) for r, u, role in rows]


def remove_member(
    db: Session,
    *,
    family_id: uuid.UUID,
    user_id: uuid.UUID,
    roles: frozenset[FamilyRole] | None = frozenset({FamilyRole.family_viewer}),
) -> bool:
    """Remove a member's access. Deletes their family membership (access is
    re-derived from membership on every request, so this cuts them off
    immediately) and drops their redemption rows across all of this
    family's links — keeping each link's `redemption_count` honest and
    making them vanish from every "who joined" list.

    `roles` restricts which membership roles are removable; the default
    matches the moderation route (plain viewers only, so a co-parent or
    owner who followed a viewer link is left untouched). Pass `roles=None`
    to remove any membership — account deletion uses that. The invite link
    itself is *not* revoked — if they still have it they can rejoin, which
    re-inserts the redemption row and re-increments the count. Returns
    True if a membership was removed, False otherwise.
    """
    membership = db.scalars(
        select(FamilyMembership).where(
            FamilyMembership.family_id == family_id,
            FamilyMembership.user_id == user_id,
        )
    ).first()
    if membership is None or (roles is not None and membership.role not in roles):
        return False
    db.delete(membership)
    redemptions = db.execute(
        select(ViewerInvitationRedemption, ViewerInvitation)
        .join(
            ViewerInvitation,
            ViewerInvitation.id == ViewerInvitationRedemption.invitation_id,
        )
        .where(
            ViewerInvitation.family_id == family_id,
            ViewerInvitationRedemption.user_id == user_id,
        )
    ).all()
    for redemption, invitation in redemptions:
        invitation.redemption_count = max(0, invitation.redemption_count - 1)
        db.delete(redemption)
    db.flush()
    return True


def remove_viewer(
    db: Session, *, family_id: uuid.UUID, user_id: uuid.UUID
) -> bool:
    """Moderation-route wrapper: only plain family_viewer memberships."""
    return remove_member(db, family_id=family_id, user_id=user_id)
