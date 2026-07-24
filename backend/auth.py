"""Email-OTP authentication with cookie sessions.

Identity is email — one identity path (spec: Key product decisions,
2026-07-23). Two ways to prove you own the address:
- OTP code: client posts `{identifier, code}` to `/auth/verify`.
- Google Sign-In: client posts the GIS ID token to `/auth/google`; both
  resolve to the same email-keyed user row.

No magic links (spam folders, cross-device breakage), no SMS login, no
passwords. Phone numbers exist only as an explicit notification opt-in
(`notify_phone` on User) scoped to birth events.

Sessions ride an httpOnly cookie, NOT localStorage — Safari's ITP deletes
script-writable storage after ~7 days without a visit, which would silently
log out exactly the occasional-visitor grandparents this product serves.
The cookie slides: middleware re-issues it on any authenticated request
once the token is older than SESSION_REFRESH_AFTER, so an active viewer's
session never expires. Bearer tokens are still accepted (tests, SSE query
fallback); the cookie is simply the path browsers use.

OTP lookups key by identifier (only one unconsumed challenge per
identifier at a time). Phone normalization sticks around for invitation
hints and the notify-phone opt-in.
"""
from __future__ import annotations

import hashlib
import os
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import httpx
import sqlalchemy as sa
from fastapi import Cookie, Depends, HTTPException, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from db import engine, get_db
from messenger import ChallengeDeliveryError, Messenger, get_messenger
from models import AuthChallenge, AuthIdentifierKind, User
from repositories import invitations as invitations_repo
from repositories import users as users_repo
from schemas import AuthRequestIn, AuthRequestOut, AuthVerifyIn, GoogleAuthIn, TokenOut, UserOut


JWT_SECRET_KEY = os.environ.get(
    "JWT_SECRET_KEY", "dev-only-change-me-in-production-or-the-build-will-fail"
)
JWT_ALGORITHM = "HS256"
# Sessions are sacred infrastructure (spec): the one auth event happens
# months before the birth and must never recur during it. 395 days ≈ the
# 400-day browser cookie cap with margin; the middleware slides it long
# before it matters.
SESSION_TTL = timedelta(days=395)
SESSION_REFRESH_AFTER = timedelta(days=7)
SESSION_COOKIE_NAME = "lily_session"
CHALLENGE_TTL = timedelta(minutes=15)
LAST_SEEN_STALENESS = timedelta(minutes=15)
MAX_ATTEMPTS_PER_CHALLENGE = 5
CHALLENGE_COOLDOWN_SECONDS = 30

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
_GOOGLE_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
_GOOGLE_ISSUERS = {"accounts.google.com", "https://accounts.google.com"}


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
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {"sub": str(user_id), "iat": now, "exp": now + SESSION_TTL},
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


# Secure cookies over plain-http dev would be silently dropped by some
# browsers; key off the deployed frontend scheme instead of a new env var.
_COOKIE_SECURE = FRONTEND_URL.startswith("https")


def apply_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE_NAME,
        token,
        max_age=int(SESSION_TTL.total_seconds()),
        httponly=True,
        secure=_COOKIE_SECURE,
        samesite="lax",
        path="/",
    )


def set_session_cookie(response: Response, user_id: uuid.UUID) -> str:
    token = _create_access_token(user_id)
    apply_session_cookie(response, token)
    return token


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")


def refreshed_session_token(raw_token: str) -> str | None:
    """If `raw_token` is a valid session older than SESSION_REFRESH_AFTER,
    return a fresh token to slide the session window; otherwise None.
    Called by the middleware on every request carrying the cookie — this is
    what turns a 395-day cap into a session that never expires for anyone
    who visits at least yearly."""
    try:
        payload = jwt.decode(raw_token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except JWTError:
        return None
    sub, iat = payload.get("sub"), payload.get("iat")
    if not sub or not isinstance(iat, (int, float)):
        return None
    issued = datetime.fromtimestamp(iat, tz=timezone.utc)
    if datetime.now(timezone.utc) - issued < SESSION_REFRESH_AFTER:
        return None
    try:
        return _create_access_token(uuid.UUID(sub))
    except (TypeError, ValueError):
        return None


def request_challenge(payload: AuthRequestIn, db: Session) -> AuthRequestOut:
    identifier, kind = normalize_identifier(payload.identifier)
    if kind is not AuthIdentifierKind.email:
        # Identity is email; phones are a notification opt-in, never a login.
        raise HTTPException(
            status_code=400,
            detail="Sign in with your email address — we use phone numbers only for birth-alert texts",
        )

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
    expires_at = datetime.now(timezone.utc) + CHALLENGE_TTL

    challenge = AuthChallenge(
        identifier=identifier,
        identifier_kind=kind,
        salt=salt,
        code_hash=_hash(salt, code),
        # Magic links are retired; the column is NOT NULL so it gets a hash
        # of a secret nobody ever sees. Dropping the column is a follow-up
        # migration once the dust settles.
        magic_link_token_hash=_hash(salt, _random_secret()),
        expires_at=expires_at,
    )
    db.add(challenge)
    db.flush()

    # Commit before sending: a provider hiccup must not roll back the
    # challenge (the next request invalidates it anyway), and the send
    # shouldn't sit inside an open transaction.
    db.commit()
    try:
        _messenger.send_challenge(identifier, kind, code)
    except ChallengeDeliveryError:
        raise
    except Exception as exc:  # a misbehaving messenger is still a 503
        raise ChallengeDeliveryError(str(exc)) from exc

    return AuthRequestOut(
        identifier_kind=kind,
        expires_in_seconds=int(CHALLENGE_TTL.total_seconds()),
    )


def _redeem_invite_if_any(db: Session, *, user: User, invite_token: str | None) -> None:
    if not invite_token:
        return
    invitation = invitations_repo.lookup_by_token(db, invite_token)
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


def verify_challenge(payload: AuthVerifyIn, db: Session) -> TokenOut:
    challenge = _resolve_challenge(payload, db)
    user = _find_or_create_user(challenge, db, attribution=payload)
    challenge.consumed_at = datetime.now(timezone.utc)
    _redeem_invite_if_any(db, user=user, invite_token=payload.invite_token)
    db.commit()
    return TokenOut(
        access_token=_create_access_token(user.id),
        user=UserOut.model_validate(user),
    )


def _resolve_challenge(payload: AuthVerifyIn, db: Session) -> AuthChallenge:
    now = datetime.now(timezone.utc)
    invalid = HTTPException(status_code=401, detail="Invalid or expired credentials")

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
        detail="Provide {identifier, code}",
    )


# ---- Google Sign-In ----
# GIS posts an RS256 ID token; we verify it against Google's published JWKS
# and resolve to the same email-keyed identity as the OTP path. OAuth is a
# login method, not a separate identity.

_google_jwks_cache: dict | None = None
_google_jwks_fetched_at: datetime | None = None
_GOOGLE_JWKS_TTL = timedelta(hours=6)


def _google_jwks() -> dict:
    global _google_jwks_cache, _google_jwks_fetched_at
    now = datetime.now(timezone.utc)
    if (
        _google_jwks_cache is None
        or _google_jwks_fetched_at is None
        or now - _google_jwks_fetched_at > _GOOGLE_JWKS_TTL
    ):
        resp = httpx.get(_GOOGLE_JWKS_URL, timeout=10.0)
        resp.raise_for_status()
        _google_jwks_cache = resp.json()
        _google_jwks_fetched_at = now
    return _google_jwks_cache


def _verify_google_credential(credential: str) -> str:
    """Validate a GIS ID token; returns the verified email address."""
    invalid = HTTPException(status_code=401, detail="Google sign-in failed")
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=503, detail="Google sign-in isn't configured"
        )
    try:
        header = jwt.get_unverified_header(credential)
        keys = [
            k for k in _google_jwks().get("keys", [])
            if k.get("kid") == header.get("kid")
        ]
        if not keys:
            # Key rotation between cache refreshes: refetch once.
            global _google_jwks_cache
            _google_jwks_cache = None
            keys = [
                k for k in _google_jwks().get("keys", [])
                if k.get("kid") == header.get("kid")
            ]
        if not keys:
            raise invalid
        claims = jwt.decode(
            credential,
            keys[0],
            algorithms=["RS256"],
            audience=GOOGLE_CLIENT_ID,
        )
    except HTTPException:
        raise
    except (JWTError, httpx.HTTPError):
        raise invalid
    if claims.get("iss") not in _GOOGLE_ISSUERS:
        raise invalid
    email = (claims.get("email") or "").lower()
    # An unverified Google email would break the "every identity has a
    # deliverable email" invariant Day Two depends on.
    if not email or not claims.get("email_verified"):
        raise invalid
    return email


def google_verify(payload: GoogleAuthIn, db: Session) -> TokenOut:
    email = _verify_google_credential(payload.credential)
    user = _find_or_create_user_by_email(email, db, attribution=payload)
    _redeem_invite_if_any(db, user=user, invite_token=payload.invite_token)
    db.commit()
    return TokenOut(
        access_token=_create_access_token(user.id),
        user=UserOut.model_validate(user),
    )


def _find_or_create_user_by_email(
    email: str, db: Session, attribution: AuthVerifyIn | GoogleAuthIn | None = None
) -> User:
    existing = db.scalars(select(User).where(User.email == email)).first()
    if existing:
        # Attribution is first-touch and set only at creation — a returning
        # user re-authenticating through a campaign link stays credited to
        # whatever brought them here originally.
        return existing

    user = User(email=email)
    if attribution is not None:
        user.signup_ref = attribution.ref
        user.signup_utm_source = attribution.utm_source
        user.signup_utm_medium = attribution.utm_medium
        user.signup_utm_campaign = attribution.utm_campaign
    db.add(user)
    db.flush()
    return user


def _find_or_create_user(
    challenge: AuthChallenge, db: Session, attribution: AuthVerifyIn | None = None
) -> User:
    # Challenges are email-only now (request_challenge rejects phones), but
    # fail loudly if a stray phone challenge ever gets this far.
    if challenge.identifier_kind is not AuthIdentifierKind.email:
        raise HTTPException(status_code=401, detail="Invalid or expired credentials")
    return _find_or_create_user_by_email(challenge.identifier, db, attribution)


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
    # long-lived session tokens have no revocation list (this DB check is
    # the revocation), and the response shouldn't reveal whether an
    # account existed.
    if user is None or user.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unknown user",
            headers={"WWW-Authenticate": "Bearer"},
        )
    _touch_last_seen(user)
    return user


def _touch_last_seen(user: User) -> None:
    """Throttled `last_seen_at` bump, at most once per LAST_SEEN_STALENESS.

    Runs on a separate connection: the request session's commit belongs to
    the route handler, and committing it here would expire loaded ORM state
    mid-request. The re-check in the WHERE clause makes concurrent stale
    requests idempotent, and analytics must never fail auth — hence the
    blanket except.
    """
    now = datetime.now(timezone.utc)
    if user.last_seen_at is not None and now - user.last_seen_at < LAST_SEEN_STALENESS:
        return
    try:
        with engine.begin() as conn:
            conn.execute(
                sa.update(User.__table__)
                .where(
                    User.id == user.id,
                    sa.or_(
                        User.last_seen_at.is_(None),
                        User.last_seen_at < now - LAST_SEEN_STALENESS,
                    ),
                )
                .values(last_seen_at=now)
            )
    except Exception:
        pass


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_security),
    session: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
    db: Session = Depends(get_db),
) -> User:
    """Browsers authenticate via the httpOnly session cookie; an explicit
    `Authorization: Bearer` (tests, scripts) wins when both are present."""
    raw_token = credentials.credentials if credentials else session
    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return _user_from_jwt(raw_token, db)


def get_optional_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_security),
    session: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
    token: str | None = None,
    db: Session = Depends(get_db),
) -> User | None:
    """Returns the authed user if a valid session is provided via the
    cookie, `Authorization: Bearer`, or `?token=...`, otherwise `None`.

    Used by routes (like `/media/{id}`) that are reachable to both
    anonymous preview visitors and signed-in viewers. A *malformed*
    token still raises 401 — silent fall-through to None would hide bugs.
    """
    raw_token = (credentials.credentials if credentials else None) or session or token
    if not raw_token:
        return None
    return _user_from_jwt(raw_token, db)


def get_current_user_stream(
    credentials: HTTPAuthorizationCredentials | None = Depends(_security),
    session: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
    token: str | None = None,
    db: Session = Depends(get_db),
) -> User:
    """SSE/download-friendly auth. EventSource and `<a download>` can't set
    headers, but they DO send same-origin cookies — the cookie is the
    normal path now. `?token=` survives as a fallback for tests and
    non-browser clients; it's no longer embedded in frontend URLs, so
    tokens stop appearing in access logs."""
    raw_token = (credentials.credentials if credentials else None) or session or token
    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return _user_from_jwt(raw_token, db)
