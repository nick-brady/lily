"""Self-serve account deletion — the counterpart of the always-free export.

Identity is always fully erased: email/phone/name/avatar wiped, login
challenges purged, and the row disabled via `deleted_at` (auth fails
closed on it). The row itself survives as a PII-free sentinel because
five RESTRICT FKs point at users wherever authored content remains —
and content legitimately remains on pages shared with a co-parent.

Per family, the user's membership decides what happens:
- **owner with a co-parent** → ownership transfers (oldest co-parent by
  joined_at), their content stays with authorship anonymized, they leave.
- **sole parent** → the family's births are fully erased: timeline,
  comments/reactions, guesses, invitations, media rows AND S3 objects.
  Births that have commerce rows (gift orders — they CASCADE on birth
  delete, and Stripe payment records must survive for refunds/disputes)
  are soft-deleted + scrubbed instead of hard-deleted;
  their content is erased identically either way.
- **co_parent / family_viewer** → they leave: membership + redemption
  rows removed, their unrevoked invite links revoked, shipping_address
  scrubbed on families where they were a parent (it may be their home).

Contributions on OTHER families' pages stay by default, anonymized via
the sentinel (comment authors render as "Someone"); `remove_contributions`
hard-deletes their comments/reactions/guesses everywhere instead — the
bodies must actually go, so no soft-delete.

In-flight Stripe webhooks are safe throughout: purchase rows are never
deleted (soft-delete path guards them), `purchased_by_user_id` is
SET NULL / sentinel, and fulfillment keys off birth/Stripe ids.

Ordering: all row changes commit in ONE transaction, then S3 deletion
runs (commit-before-external, same as the auth messenger). The failure
mode is orphaned-but-logged S3 objects, never DB rows pointing at
deleted files.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

from sqlalchemy import delete, exists, select, update
from sqlalchemy.orm import Session

import storage
from models import (
    AuthChallenge,
    Birth,
    BirthGuess,
    Family,
    FamilyMembership,
    FamilyRole,
    GiftOrder,
    GiftRendering,
    GiftRenderingMockup,
    MediaAsset,
    TimelineEvent,
    TimelineEventComment,
    TimelineEventReaction,
    User,
    ViewerInvitation,
)
from repositories import invitations as invitations_repo

logger = logging.getLogger(__name__)

SENTINEL_DOMAIN = "deleted.arrivalstory.invalid"


def sentinel_email(user_id: uuid.UUID) -> str:
    """Per-user sentinel: users must keep email-or-phone (check constraint)
    and email is unique-indexed, so a shared constant can't work."""
    return f"deleted+{user_id}@{SENTINEL_DOMAIN}"


@dataclass(frozen=True)
class FamilyAction:
    family_id: uuid.UUID
    kind: Literal["erase", "transfer", "leave"]
    was_parent: bool
    new_owner_user_id: uuid.UUID | None = None


def bucket_families(
    user_id: uuid.UUID,
    memberships: list,
    parents_by_family: dict,
) -> list[FamilyAction]:
    """Pure decision logic: one action per membership.

    `parents_by_family` maps family_id -> the families_repo.list_parents
    result (memberships joined to users, oldest joined_at first) — the
    oldest other parent becomes the new owner on transfer.
    """
    actions: list[FamilyAction] = []
    for membership in memberships:
        family_id = membership.family_id
        if membership.role is FamilyRole.owner:
            other_parents = [
                m
                for m, _user in parents_by_family.get(family_id, [])
                if m.user_id != user_id
            ]
            if other_parents:
                actions.append(
                    FamilyAction(
                        family_id=family_id,
                        kind="transfer",
                        was_parent=True,
                        new_owner_user_id=other_parents[0].user_id,
                    )
                )
            else:
                actions.append(
                    FamilyAction(family_id=family_id, kind="erase", was_parent=True)
                )
        elif membership.role is FamilyRole.co_parent:
            actions.append(
                FamilyAction(family_id=family_id, kind="leave", was_parent=True)
            )
        else:
            actions.append(
                FamilyAction(family_id=family_id, kind="leave", was_parent=False)
            )
    return actions


def collect_media_keys(assets: list) -> list[str]:
    """All S3 keys an asset may hold. Legacy `local:` keys are not S3
    objects — the erase path deletes their rows but leaves the (dev-era)
    files on disk; nothing routable references them afterward."""
    keys: list[str] = []
    for asset in assets:
        for key in (
            asset.original_s3_key,
            asset.hot_s3_key,
            asset.cold_s3_key,
            asset.display_s3_key,
            asset.thumbnail_s3_key,
        ):
            if key and not key.startswith("local:"):
                keys.append(key)
    return keys


def split_renderings(
    renderings: list, referenced_ids: set
) -> tuple[list, list, list[str]]:
    """(soft_delete, hard_delete, s3_keys). Renderings referenced by a
    gift order (RESTRICT FK) can't be hard-deleted — they soft-delete
    with their key columns NULLed; the rest hard-delete. Either way the
    artwork/mockup objects come out of S3."""
    soft, hard, keys = [], [], []
    for rendering in renderings:
        for key in (rendering.artwork_s3_key, rendering.mockup_s3_key):
            if key:
                keys.append(key)
        if rendering.id in referenced_ids:
            soft.append(rendering)
        else:
            hard.append(rendering)
    return soft, hard, keys


def erase_birth(db: Session, birth: Birth, now: datetime) -> tuple[list[str], bool]:
    """Erase one birth's content: timeline, comments/reactions, guesses,
    invitations, media rows, gift renderings. Returns (S3 keys to delete
    after commit, whether the birth row itself was hard-deleted — births
    with commerce rows are soft-deleted + scrubbed so Stripe payment
    records survive). Uses Core deletes so DB-level ON DELETE CASCADE
    fires (the ORM has no cascade config for these).

    Shared by account deletion (sole-parent erase) and the parent-facing
    delete-this-page route."""
    s3_keys: list[str] = []
    assets = list(
        db.scalars(
            select(MediaAsset).where(MediaAsset.birth_id == birth.id)
        ).all()
    )
    s3_keys += collect_media_keys(assets)

    renderings = list(
        db.scalars(
            select(GiftRendering).where(GiftRendering.birth_id == birth.id)
        ).all()
    )
    rendering_ids = [r.id for r in renderings]
    referenced_ids = set()
    mockup_rows = []
    if rendering_ids:
        referenced_ids = set(
            db.scalars(
                select(GiftOrder.gift_rendering_id).where(
                    GiftOrder.gift_rendering_id.in_(rendering_ids)
                )
            ).all()
        )
        mockup_rows = list(
            db.scalars(
                select(GiftRenderingMockup).where(
                    GiftRenderingMockup.gift_rendering_id.in_(rendering_ids)
                )
            ).all()
        )
    s3_keys += [m.mockup_s3_key for m in mockup_rows if m.mockup_s3_key]
    soft, hard, rendering_keys = split_renderings(renderings, referenced_ids)
    s3_keys += rendering_keys
    if mockup_rows:
        db.execute(
            delete(GiftRenderingMockup).where(
                GiftRenderingMockup.gift_rendering_id.in_(rendering_ids)
            )
        )
    for rendering in soft:
        rendering.deleted_at = now
        rendering.artwork_s3_key = None
        rendering.mockup_s3_key = None
    if hard:
        db.execute(
            delete(GiftRendering).where(
                GiftRendering.id.in_([r.id for r in hard])
            )
        )

    # Content: leaves before parents. Comments/reactions CASCADE off
    # events; redemptions CASCADE off invitations.
    db.execute(delete(MediaAsset).where(MediaAsset.birth_id == birth.id))
    db.execute(delete(TimelineEvent).where(TimelineEvent.birth_id == birth.id))
    db.execute(delete(BirthGuess).where(BirthGuess.birth_id == birth.id))
    db.execute(
        delete(ViewerInvitation).where(ViewerInvitation.birth_id == birth.id)
    )

    has_commerce = db.scalar(
        select(exists().where(GiftOrder.birth_id == birth.id))
    )
    if has_commerce:
        # Hard delete would CASCADE away Stripe payment records; keep
        # the shell, scrub everything personal, free the slug.
        birth.deleted_at = now
        birth.child_name = None
        birth.child_dob = None
        birth.child_weight_lbs = None
        birth.child_length_in = None
        birth.shipping_address = None
        birth.slug = f"deleted-{birth.id}"
        return s3_keys, False
    db.execute(delete(Birth).where(Birth.id == birth.id))
    return s3_keys, True


def _erase_family(db: Session, family_id: uuid.UUID, now: datetime) -> list[str]:
    """Erase every birth's content in a sole-parent family; returns S3 keys
    to delete after commit."""
    s3_keys: list[str] = []
    births = list(db.scalars(select(Birth).where(Birth.family_id == family_id)).all())
    all_hard = True
    for birth in births:
        birth_keys, hard_deleted = erase_birth(db, birth, now)
        s3_keys += birth_keys
        if not hard_deleted:
            all_hard = False

    if all_hard:
        db.execute(delete(Family).where(Family.id == family_id))  # memberships CASCADE
    else:
        family = db.get(Family, family_id)
        family.display_name = "Deleted"
        db.execute(
            delete(FamilyMembership).where(FamilyMembership.family_id == family_id)
        )
    return s3_keys


def _leave_family(
    db: Session, action: FamilyAction, user: User, now: datetime
) -> None:
    if action.was_parent:
        # The saved shipping address may be the deleter's home.
        db.execute(
            update(Birth)
            .where(Birth.family_id == action.family_id)
            .values(shipping_address=None)
        )
        db.execute(
            update(ViewerInvitation)
            .where(
                ViewerInvitation.family_id == action.family_id,
                ViewerInvitation.invited_by_user_id == user.id,
                ViewerInvitation.revoked_at.is_(None),
            )
            .values(revoked_at=now)
        )
    invitations_repo.remove_member(
        db, family_id=action.family_id, user_id=user.id, roles=None
    )


def delete_account(db: Session, user: User, *, remove_contributions: bool) -> None:
    from repositories import families as families_repo
    from repositories import users as users_repo

    # Serialize concurrent deletes and make the whole thing idempotent.
    user = db.execute(
        select(User).where(User.id == user.id).with_for_update()
    ).scalar_one()
    if user.deleted_at is not None:
        return

    now = datetime.now(timezone.utc)
    memberships = users_repo.list_memberships(db, user.id)
    parents_by_family = {
        m.family_id: families_repo.list_parents(db, family_id=m.family_id)
        for m in memberships
    }
    actions = bucket_families(user.id, memberships, parents_by_family)

    s3_keys: list[str] = []
    for action in actions:
        if action.kind == "erase":
            s3_keys += _erase_family(db, action.family_id, now)
        elif action.kind == "transfer":
            family = db.get(Family, action.family_id)
            family.primary_owner_user_id = action.new_owner_user_id
            new_owner_membership = db.scalars(
                select(FamilyMembership).where(
                    FamilyMembership.family_id == action.family_id,
                    FamilyMembership.user_id == action.new_owner_user_id,
                )
            ).first()
            if new_owner_membership is not None:
                new_owner_membership.role = FamilyRole.owner
            _leave_family(db, action, user, now)
        else:
            _leave_family(db, action, user, now)

    if remove_contributions:
        # Full erasure on request: bodies must go, so hard deletes —
        # soft-delete would keep the text in the row.
        db.execute(
            delete(TimelineEventComment).where(
                TimelineEventComment.user_id == user.id
            )
        )
        db.execute(
            delete(TimelineEventReaction).where(
                TimelineEventReaction.user_id == user.id
            )
        )
        db.execute(delete(BirthGuess).where(BirthGuess.user_id == user.id))

    # Identity erasure. Challenges key off the raw identifier string.
    for identifier in filter(None, (user.email, user.phone)):
        db.execute(
            delete(AuthChallenge).where(AuthChallenge.identifier == identifier)
        )
    user.email = sentinel_email(user.id)
    user.phone = None
    user.display_name = None
    user.avatar_url = None
    user.deleted_at = now

    # One transaction for every row change; S3 only after it holds.
    db.commit()

    failed = storage.delete_objects(s3_keys)
    if failed:
        logger.error(
            "account-deletion: %d S3 objects not deleted for user %s: %s",
            len(failed),
            user.id,
            failed,
        )
