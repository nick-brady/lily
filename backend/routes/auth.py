"""Auth and account routes: OTP/Google sign-in, session cookie, /me."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

import account_deletion
from auth import (
    ChallengeCooldownError,
    apply_session_cookie,
    clear_session_cookie,
    get_active_messenger,
    get_current_user,
    google_verify,
    normalize_identifier,
    request_challenge,
    verify_challenge,
)
from db import get_db
from messenger import ChallengeDeliveryError
from models import (
    AuthIdentifierKind,
    Birth,
    Family,
    FamilyMembership,
    FamilyRole,
    User,
)
from repositories import users as users_repo
from schemas import (
    AuthRequestIn,
    AuthRequestOut,
    AuthVerifyIn,
    BirthOut,
    FamilyMembershipOut,
    FamilyWithBirthsOut,
    GoogleAuthIn,
    MeOut,
    MeUpdateIn,
    NotifyPhoneIn,
    TokenOut,
    UserOut,
)

router = APIRouter()


@router.post("/auth/request", response_model=AuthRequestOut)
def auth_request(payload: AuthRequestIn, db: Session = Depends(get_db)) -> AuthRequestOut:
    try:
        return request_challenge(payload, db)
    except ChallengeCooldownError:
        raise HTTPException(
            status_code=429, detail="A code was just sent — give it a moment"
        )
    except ChallengeDeliveryError:
        # identifier-neutral: the failure is provider trouble, not a signal
        # about whether the identifier exists
        raise HTTPException(
            status_code=503,
            detail="We couldn't send your code — try again in a minute",
        )


@router.post("/auth/verify", response_model=TokenOut)
def auth_verify(
    payload: AuthVerifyIn, response: Response, db: Session = Depends(get_db)
) -> TokenOut:
    result = verify_challenge(payload, db)
    # The httpOnly cookie is the browser's session (localStorage is
    # ITP-purgeable); the body token remains for tests and scripts.
    apply_session_cookie(response, result.access_token)
    return result


@router.post("/auth/google", response_model=TokenOut)
def auth_google(
    payload: GoogleAuthIn, response: Response, db: Session = Depends(get_db)
) -> TokenOut:
    """'Continue with Google' — a login method, not a separate identity;
    resolves to the same email-keyed user as the OTP path."""
    result = google_verify(payload, db)
    apply_session_cookie(response, result.access_token)
    return result


@router.post("/auth/logout", status_code=204)
def auth_logout(response: Response) -> None:
    # Mutations on the injected response (the delete-cookie header) are
    # carried onto the empty 204.
    clear_session_cookie(response)


@router.get("/me", response_model=MeOut)
def me(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MeOut:
    memberships = users_repo.list_memberships(db, current_user.id)

    families: list[FamilyWithBirthsOut] = []
    for membership in memberships:
        family = db.get(Family, membership.family_id)
        if family is None:
            continue
        births = db.scalars(
            select(Birth)
            .where(Birth.family_id == family.id, Birth.deleted_at.is_(None))
            .order_by(Birth.created_at.asc())
        ).all()
        # Who else is in here. Membership is family-wide, so this is exactly
        # the set of people a new page added to this family would inherit.
        others = db.execute(
            select(FamilyMembership.role, User.display_name)
            .join(User, User.id == FamilyMembership.user_id)
            .where(
                FamilyMembership.family_id == family.id,
                FamilyMembership.user_id != current_user.id,
            )
        ).all()
        co_parent_names = [
            (name or "").strip()
            for role, name in others
            if role in (FamilyRole.owner, FamilyRole.co_parent)
        ]
        families.append(
            FamilyWithBirthsOut(
                id=family.id,
                display_name=family.display_name,
                role=membership.role,
                births=[BirthOut.model_validate(b) for b in births],
                co_parent_names=[n for n in co_parent_names if n],
                viewer_count=sum(
                    1 for role, _ in others if role is FamilyRole.family_viewer
                ),
            )
        )

    return MeOut(
        user=UserOut.model_validate(current_user),
        memberships=[FamilyMembershipOut.model_validate(m) for m in memberships],
        families=families,
    )


@router.patch("/me", response_model=UserOut)
def update_me(
    payload: MeUpdateIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserOut:
    """Set the name family sees on your comments and in the family list."""
    users_repo.set_display_name(db, user=current_user, name=payload.display_name)
    db.commit()
    db.refresh(current_user)
    return UserOut.model_validate(current_user)


@router.put("/me/notify-phone", response_model=UserOut)
def set_notify_phone(
    payload: NotifyPhoneIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserOut:
    """The birth-events text opt-in — "Want a text the moment labor
    begins?" Sends the confirmation text first (it verifies the number is
    real and delivers the STOP language); only a successful send records
    the consent. Scoped to birth events only, forever — this is what keeps
    SMS legally boring (no marketing consent needed)."""
    identifier, kind = normalize_identifier(payload.phone)
    if kind is not AuthIdentifierKind.phone:
        raise HTTPException(status_code=400, detail="Enter a phone number")
    try:
        get_active_messenger().send_notify_optin(identifier)
    except ChallengeDeliveryError:
        raise HTTPException(
            status_code=503,
            detail="We couldn't text that number — check it and try again",
        )
    current_user.notify_phone = identifier
    current_user.notify_phone_opted_in_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(current_user)
    return UserOut.model_validate(current_user)


@router.delete("/me/notify-phone", response_model=UserOut)
def clear_notify_phone(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserOut:
    current_user.notify_phone = None
    current_user.notify_phone_opted_in_at = None
    db.commit()
    db.refresh(current_user)
    return UserOut.model_validate(current_user)


@router.delete("/me", status_code=204)
def delete_me(
    remove_contributions: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """Self-serve account deletion — always available, never behind any
    paywall. See account_deletion.py for exactly what happens per family.
    Sync def on purpose: row deletes + S3 batch deletes block, so FastAPI
    runs this in its threadpool (same rationale as the export route).
    """
    account_deletion.delete_account(
        db, current_user, remove_contributions=remove_contributions
    )
    return Response(status_code=204)
