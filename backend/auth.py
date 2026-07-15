"""Magic-link + SMS-OTP authentication.

Two valid verification paths:
- Magic link: client follows `{FRONTEND_URL}/auth/verify?token=<challenge_id>.<secret>`
  and POSTs `{token: "<challenge_id>.<secret>"}` to `/auth/verify`.
- OTP code: client posts `{identifier, code}` to `/auth/verify`.

The challenge_id is encoded into the magic-link token so we know which salt
to use when hashing for comparison. OTP lookups instead key by identifier
(only one unconsumed challenge per identifier at a time).

Identifier normalization is intentionally permissive in PR 1; real E.164
phone parsing arrives with Twilio in a follow-up.
"""
from __future__ import annotations

import hashlib
import os
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from db import get_db
from messenger import ChallengeDeliveryError, Messenger, get_messenger
from models import AuthChallenge, AuthIdentifierKind, User
from repositories import invitations as invitations_repo
from repositories import users as users_repo
from schemas import AuthRequestIn, AuthRequestOut, AuthVerifyIn, TokenOut, UserOut


JWT_SECRET_KEY = os.environ.get(
    "JWT_SECRET_KEY", "dev-only-change-me-in-production-or-the-build-will-fail"
)
JWT_ALGORITHM = "HS256"
JWT_TTL = timedelta(days=30)
CHALLENGE_TTL = timedelta(minutes=15)
MAX_ATTEMPTS_PER_CHALLENGE = 5
CHALLENGE_COOLDOWN_SECONDS = 30


class ChallengeCooldownError(Exception):
    """A code was requested again too quickly for the same identifier."""

FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000")

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

_security = HTTPBearer(auto_error=False)
_messenger: Messenger = get_messenger()


def set_messenger(messenger: Messenger) -> None:
    """Override the default ConsoleMessenger (used in tests)."""
    global _messenger
    _messenger = messenger


def get_active_messenger() -> Messenger:
    """The messenger callers outside this module should send through —
    keeps invitation sends on the same (possibly test-overridden) instance
    as auth challenges, instead of constructing a second one."""
    return _messenger


def normalize_identifier(raw: str) -> tuple[str, AuthIdentifierKind]:
    candidate = raw.strip()
    if "@" in candidate:
        normalized = candidate.lower()
        if not EMAIL_RE.match(normalized):
            raise HTTPException(status_code=400, detail="Invalid email address")
        return normalized, AuthIdentifierKind.email

    digits = re.sub(r"\D", "", candidate)
    if len(digits) == 10:
        normalized = f"+1{digits}"
    elif len(digits) == 11 and digits.startswith("1"):
        normalized = f"+{digits}"
    elif len(digits) >= 8 and candidate.startswith("+"):
        normalized = f"+{digits}"
    else:
        raise HTTPException(status_code=400, detail="Invalid phone number")
    return normalized, AuthIdentifierKind.phone


def _random_salt() -> str:
    return secrets.token_hex(16)


def _random_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def _random_secret() -> str:
    return secrets.token_urlsafe(32)


def _hash(salt: str, value: str) -> str:
    return hashlib.sha256(f"{salt}{value}".encode("utf-8")).hexdigest()


def _create_access_token(user_id: uuid.UUID) -> str:
    expire = datetime.now(timezone.utc) + JWT_TTL
    return jwt.encode(
        {"sub": str(user_id), "exp": expire},
        JWT_SECRET_KEY,
        algorithm=JWT_ALGORITHM,
    )


def _decode_access_token(token: str) -> uuid.UUID | None:
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except JWTError:
        return None
    sub = payload.get("sub")
    if not sub:
        return None
    try:
        return uuid.UUID(sub)
    except (TypeError, ValueError):
        return None


def request_challenge(payload: AuthRequestIn, db: Session) -> AuthRequestOut:
    identifier, kind = normalize_identifier(payload.identifier)

    now = datetime.now(timezone.utc)
    priors = db.scalars(
        select(AuthChallenge).where(
            AuthChallenge.identifier == identifier,
            AuthChallenge.consumed_at.is_(None),
        )
    ).all()

    # Minimal per-identifier cooldown: with real SMS/email providers wired
    # up, an unthrottled request endpoint is a provider bill. A fuller
    # throttle (per-IP, captcha) is future work.
    for prior in priors:
        if (now - prior.created_at).total_seconds() < CHALLENGE_COOLDOWN_SECONDS:
            raise ChallengeCooldownError()

    # Invalidate the existing unconsumed challenges; only the most recent
    # challenge should be usable.
    for prior in priors:
        prior.consumed_at = now

    salt = _random_salt()
    code = _random_code()
    secret = _random_secret()
    expires_at = datetime.now(timezone.utc) + CHALLENGE_TTL

    challenge = AuthChallenge(
        identifier=identifier,
        identifier_kind=kind,
        salt=salt,
        code_hash=_hash(salt, code),
        magic_link_token_hash=_hash(salt, secret),
        expires_at=expires_at,
    )
    db.add(challenge)
    db.flush()

    magic_link_token = f"{challenge.id}.{secret}"
    magic_link_url = f"{FRONTEND_URL}/auth/verify?token={magic_link_token}"

    # Commit before sending: a provider hiccup must not roll back the
    # challenge (the next request invalidates it anyway), and the send
    # shouldn't sit inside an open transaction.
    db.commit()
    try:
        _messenger.send_challenge(identifier, kind, code, magic_link_url)
    except ChallengeDeliveryError:
        raise
    except Exception as exc:  # a misbehaving messenger is still a 503
        raise ChallengeDeliveryError(str(exc)) from exc

    return AuthRequestOut(
        identifier_kind=kind,
        expires_in_seconds=int(CHALLENGE_TTL.total_seconds()),
    )


def verify_challenge(payload: AuthVerifyIn, db: Session) -> TokenOut:
    challenge = _resolve_challenge(payload, db)
    user = _find_or_create_user(challenge, db)
    challenge.consumed_at = datetime.now(timezone.utc)

    if payload.invite_token:
        invitation = invitations_repo.lookup_by_token(db, payload.invite_token)
        if invitation is not None and invitations_repo.is_redeemable(invitation):
            invitations_repo.redeem(db, invitation=invitation, user_id=user.id)
            # Carry "Grandma Rose" from the invite onto the new account so
            # her comments are attributed immediately. Never overwrites a
            # name she already chose.
            users_repo.set_display_name_if_empty(
                db, user=user, name=invitation.display_name_hint
            )
        # Silently ignore unredeemable invites: the sign-in itself
        # succeeded; the user can ask their inviter for a fresh link.

    db.commit()
    return TokenOut(
        access_token=_create_access_token(user.id),
        user=UserOut.model_validate(user),
    )


def _resolve_challenge(payload: AuthVerifyIn, db: Session) -> AuthChallenge:
    now = datetime.now(timezone.utc)
    invalid = HTTPException(status_code=401, detail="Invalid or expired credentials")

    if payload.token:
        challenge_id_str, _, secret = payload.token.partition(".")
        if not challenge_id_str or not secret:
            raise invalid
        try:
            challenge_id = uuid.UUID(challenge_id_str)
        except ValueError:
            raise invalid
        challenge = db.get(AuthChallenge, challenge_id)
        if challenge is None or challenge.consumed_at is not None or challenge.expires_at < now:
            raise invalid
        if _hash(challenge.salt, secret) != challenge.magic_link_token_hash:
            challenge.attempt_count += 1
            db.commit()
            raise invalid
        return challenge

    if payload.identifier and payload.code:
        identifier, _ = normalize_identifier(payload.identifier)
        challenge = db.scalars(
            select(AuthChallenge)
            .where(
                AuthChallenge.identifier == identifier,
                AuthChallenge.consumed_at.is_(None),
            )
            .order_by(AuthChallenge.created_at.desc())
            .limit(1)
        ).first()
        if challenge is None or challenge.expires_at < now:
            raise invalid
        if challenge.attempt_count >= MAX_ATTEMPTS_PER_CHALLENGE:
            raise invalid
        if _hash(challenge.salt, payload.code) != challenge.code_hash:
            challenge.attempt_count += 1
            db.commit()
            raise invalid
        return challenge

    raise HTTPException(
        status_code=400,
        detail="Provide either {token} or {identifier, code}",
    )


def _find_or_create_user(challenge: AuthChallenge, db: Session) -> User:
    if challenge.identifier_kind is AuthIdentifierKind.email:
        existing = db.scalars(
            select(User).where(User.email == challenge.identifier)
        ).first()
    else:
        existing = db.scalars(
            select(User).where(User.phone == challenge.identifier)
        ).first()

    if existing:
        return existing

    user = User(
        email=challenge.identifier if challenge.identifier_kind is AuthIdentifierKind.email else None,
        phone=challenge.identifier if challenge.identifier_kind is AuthIdentifierKind.phone else None,
    )
    db.add(user)
    db.flush()
    return user


def _user_from_jwt(raw_token: str, db: Session) -> User:
    user_id = _decode_access_token(raw_token)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = db.get(User, user_id)
    # Deleted accounts fail closed with the same detail as a missing row —
    # outstanding 30-day JWTs have no revocation list, and the response
    # shouldn't reveal whether an account existed.
    if user is None or user.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unknown user",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_security),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return _user_from_jwt(credentials.credentials, db)


def get_optional_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_security),
    token: str | None = None,
    db: Session = Depends(get_db),
) -> User | None:
    """Returns the authed user if a valid JWT is provided via either
    `Authorization: Bearer` or `?token=...`, otherwise `None`.

    Used by routes (like `/media/{id}` and the public SSE stream) that
    are reachable to both anonymous public visitors and signed-in
    viewers. A *malformed* token still raises 401 — silent fall-through
    to None would hide bugs.
    """
    raw_token = credentials.credentials if credentials else token
    if not raw_token:
        return None
    return _user_from_jwt(raw_token, db)


def get_current_user_stream(
    credentials: HTTPAuthorizationCredentials | None = Depends(_security),
    token: str | None = None,
    db: Session = Depends(get_db),
) -> User:
    """SSE-friendly auth: accepts a JWT via `Authorization: Bearer` *or*
    via `?token=...` query param. EventSource can't set headers, so we
    fall back to the query string. The query token is logged in nginx
    access logs the same way a magic-link token would be — short-lived
    sessions only.
    """
    raw_token = credentials.credentials if credentials else token
    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return _user_from_jwt(raw_token, db)
