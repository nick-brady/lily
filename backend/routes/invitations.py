"""Viewer invitations, invite-link lookup/redemption, viewer removal, and
family-scoped co-parent management."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Body, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from auth import (
    FRONTEND_URL,
    get_active_messenger,
    get_current_user,
    normalize_identifier,
)
from db import get_db
from models import AuthIdentifierKind, Birth, Family, FamilyRole, User, ViewerInvitation
from repositories import births as births_repo
from repositories import invitations as invitations_repo
from repositories import users as users_repo
from routes.deps import (
    BirthAccess,
    FamilyAccess,
    require_family_parent,
    require_parent_access,
)
from schemas import (
    CoParentInviteCreateIn,
    CoParentMemberOut,
    CoParentsOut,
    InvitationContextOut,
    InvitationCreateIn,
    InvitationCreatedOut,
    InvitationOut,
    InvitationRedemptionOut,
    PendingCoParentInviteOut,
)
from repositories import families as families_repo

router = APIRouter()


_INVITE_ROLE_LABELS = {
    FamilyRole.co_parent: "co-parent",
    FamilyRole.family_viewer: "family member",
}


def _invitation_url(plaintext_token: str) -> str:
    return f"{FRONTEND_URL}/invite/{plaintext_token}"


def _resolve_invite_contact(
    email_hint: str | None, phone_hint: str | None
) -> tuple[str | None, str | None, AuthIdentifierKind | None]:
    """Validate+normalize a raw contact hint the same way auth does, so a
    bad address/number 400s immediately instead of silently failing to
    send later. Returns (email_hint, phone_hint, kind-to-send-to) — the
    third element is None when no contact was given at all."""
    raw = email_hint or phone_hint
    if not raw:
        return None, None, None
    identifier, kind = normalize_identifier(raw)
    if kind is AuthIdentifierKind.email:
        return identifier, None, kind
    return None, identifier, kind


def _create_and_send_invitation(
    db: Session,
    *,
    family_id: uuid.UUID,
    birth_id: uuid.UUID,
    birth_name: str | None,
    invited_by: User,
    display_name_hint: str | None,
    email_hint: str | None,
    phone_hint: str | None,
    role: FamilyRole = FamilyRole.family_viewer,
) -> InvitationCreatedOut:
    norm_email, norm_phone, send_kind = _resolve_invite_contact(email_hint, phone_hint)
    invitation, plaintext_token = invitations_repo.create_invitation(
        db,
        family_id=family_id,
        birth_id=birth_id,
        invited_by_user_id=invited_by.id,
        display_name_hint=display_name_hint,
        email_hint=norm_email,
        phone_hint=norm_phone,
        role=role,
    )
    db.commit()
    db.refresh(invitation)
    invite_url = _invitation_url(plaintext_token)

    # Best-effort: the link above already works regardless, so a delivery
    # failure shouldn't fail invite creation — it just means the parent
    # falls back to sharing the link themselves (same fallback the copy
    # button always offered).
    sent = False
    if send_kind is not None:
        try:
            get_active_messenger().send_invitation(
                norm_email or norm_phone,
                send_kind,
                inviter_name=invited_by.display_name or "A family member",
                birth_name=birth_name or "the family",
                role_label=_INVITE_ROLE_LABELS.get(role, "family member"),
                invite_url=invite_url,
            )
            sent = True
        except Exception:
            sent = False

    return InvitationCreatedOut(
        **InvitationOut.model_validate(invitation).model_dump(exclude={"invite_url"}),
        token=plaintext_token,
        invite_url=invite_url,
        sent=sent,
    )


@router.post(
    "/birth/{birth_id}/invitations",
    response_model=InvitationCreatedOut,
)
def create_invitation(
    payload: InvitationCreateIn = Body(default=InvitationCreateIn()),
    access: BirthAccess = Depends(require_parent_access),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InvitationCreatedOut:
    return _create_and_send_invitation(
        db,
        family_id=access.birth.family_id,
        birth_id=access.birth.id,
        birth_name=access.birth.child_name,
        invited_by=current_user,
        display_name_hint=payload.display_name_hint,
        email_hint=payload.email_hint,
        phone_hint=payload.phone_hint,
    )


@router.get(
    "/birth/{birth_id}/invitations",
    response_model=list[InvitationOut],
)
def list_invitations(
    access: BirthAccess = Depends(require_parent_access),
    db: Session = Depends(get_db),
) -> list[InvitationOut]:
    rows = invitations_repo.list_for_birth(db, birth_id=access.birth.id)
    out = []
    for r in rows:
        item = InvitationOut.model_validate(r)
        item.invite_url = _invitation_url(r.token) if r.token else None
        out.append(item)
    return out


@router.delete("/birth/{birth_id}/invitations/{invitation_id}", status_code=204)
def revoke_invitation(
    invitation_id: uuid.UUID,
    access: BirthAccess = Depends(require_parent_access),
    db: Session = Depends(get_db),
) -> Response:
    invitation = db.get(ViewerInvitation, invitation_id)
    if invitation is None or invitation.birth_id != access.birth.id:
        raise HTTPException(status_code=404, detail="Invitation not found")
    invitations_repo.revoke(db, invitation)
    db.commit()
    return Response(status_code=204)


@router.get(
    "/birth/{birth_id}/invitations/{invitation_id}/redemptions",
    response_model=list[InvitationRedemptionOut],
)
def list_invitation_redemptions(
    invitation_id: uuid.UUID,
    access: BirthAccess = Depends(require_parent_access),
    db: Session = Depends(get_db),
) -> list[InvitationRedemptionOut]:
    invitation = db.get(ViewerInvitation, invitation_id)
    if invitation is None or invitation.birth_id != access.birth.id:
        raise HTTPException(status_code=404, detail="Invitation not found")
    return [
        InvitationRedemptionOut(
            user_id=user.id,
            display_name=user.display_name,
            email=user.email,
            phone=user.phone,
            role=role or FamilyRole.family_viewer,
            redeemed_at=redemption.redeemed_at,
        )
        for redemption, user, role in invitations_repo.list_redemptions(
            db, invitation=invitation
        )
    ]


@router.delete("/birth/{birth_id}/viewers/{user_id}", status_code=204)
def remove_birth_viewer(
    user_id: uuid.UUID,
    access: BirthAccess = Depends(require_parent_access),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """Remove a family viewer's access to this family. Parents only. The
    invite link is left active — see `invitations_repo.remove_viewer`.
    """
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="You can't remove yourself")
    removed = invitations_repo.remove_viewer(
        db, family_id=access.birth.family_id, user_id=user_id
    )
    if not removed:
        raise HTTPException(status_code=404, detail="Viewer not found")
    db.commit()
    return Response(status_code=204)


@router.get("/invite/{token}", response_model=InvitationContextOut)
def lookup_invitation(token: str, db: Session = Depends(get_db)) -> InvitationContextOut:
    invitation = invitations_repo.lookup_by_token(db, token)
    if invitation is None or not invitations_repo.is_redeemable(invitation):
        raise HTTPException(status_code=404, detail="Invitation is invalid or expired")
    family = db.get(Family, invitation.family_id)
    birth = db.get(Birth, invitation.birth_id)
    if family is None or birth is None:
        raise HTTPException(status_code=404, detail="Invitation is invalid or expired")
    return InvitationContextOut(
        family_display_name=family.display_name,
        birth_id=birth.id,
        birth_slug=birth.slug,
        birth_child_name=birth.child_name,
        display_name_hint=invitation.display_name_hint,
        email_hint=invitation.email_hint,
        phone_hint=invitation.phone_hint,
        expires_at=invitation.expires_at,
        role=invitation.role,
    )


@router.post("/invite/{token}/redeem", status_code=204)
def redeem_invitation_authed(
    token: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """For users who are already signed in. The new-user flow goes
    through `/auth/verify` with `invite_token` instead.
    """
    invitation = invitations_repo.lookup_by_token(db, token)
    if invitation is None or not invitations_repo.is_redeemable(invitation):
        raise HTTPException(status_code=404, detail="Invitation is invalid or expired")
    invitations_repo.redeem(db, invitation=invitation, user_id=current_user.id)
    users_repo.set_display_name_if_empty(
        db, user=current_user, name=invitation.display_name_hint
    )
    db.commit()
    return Response(status_code=204)


# ============ Co-parents (family-scoped) ============


@router.get("/family/{family_id}/co-parents", response_model=CoParentsOut)
def list_co_parents(
    access: FamilyAccess = Depends(require_family_parent),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CoParentsOut:
    parents = families_repo.list_parents(db, family_id=access.family.id)
    members = [
        CoParentMemberOut(
            user_id=user.id,
            display_name=user.display_name,
            contact=user.email or user.phone,
            role=membership.role,
            is_self=user.id == current_user.id,
        )
        for membership, user in parents
    ]
    now = datetime.now(timezone.utc)
    pending = [
        PendingCoParentInviteOut.model_validate(inv)
        for inv in invitations_repo.list_for_family(
            db, family_id=access.family.id, role=FamilyRole.co_parent
        )
        if inv.revoked_at is None and inv.expires_at > now
    ]
    return CoParentsOut(members=members, pending=pending)


@router.post(
    "/family/{family_id}/co-parents/invitations",
    response_model=InvitationCreatedOut,
)
def invite_co_parent(
    payload: CoParentInviteCreateIn = Body(default=CoParentInviteCreateIn()),
    access: FamilyAccess = Depends(require_family_parent),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InvitationCreatedOut:
    birth = births_repo.primary_birth_for_family(db, access.family.id)
    if birth is None:
        raise HTTPException(
            status_code=400,
            detail="Add a birth before inviting a co-parent",
        )
    return _create_and_send_invitation(
        db,
        family_id=access.family.id,
        birth_id=birth.id,
        birth_name=birth.child_name,
        invited_by=current_user,
        display_name_hint=payload.display_name_hint,
        email_hint=payload.email_hint,
        phone_hint=payload.phone_hint,
        role=FamilyRole.co_parent,
    )


@router.delete(
    "/family/{family_id}/co-parents/invitations/{invitation_id}",
    status_code=204,
)
def revoke_co_parent_invitation(
    invitation_id: uuid.UUID,
    access: FamilyAccess = Depends(require_family_parent),
    db: Session = Depends(get_db),
) -> Response:
    invitation = db.get(ViewerInvitation, invitation_id)
    if (
        invitation is None
        or invitation.family_id != access.family.id
        or invitation.role != FamilyRole.co_parent
    ):
        raise HTTPException(status_code=404, detail="Invitation not found")
    invitations_repo.revoke(db, invitation)
    db.commit()
    return Response(status_code=204)
