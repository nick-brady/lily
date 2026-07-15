"""Admin distribution-metrics aggregates, plus the page-visit insert.

All range-based functions take half-open UTC datetimes [start, end) and
bucket by UTC calendar day — evening US traffic lands on the "next" bar,
which the dashboard accepts and labels rather than juggling DST.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import sqlalchemy as sa
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models import (
    Birth,
    FamilyMembership,
    FamilyRole,
    GiftOrder,
    PageVisit,
    TimelineEvent,
    UnlockPurchase,
    User,
    ViewerInvitation,
    ViewerInvitationRedemption,
)


def _utc_day(col):
    return sa.cast(func.timezone("UTC", col), sa.Date)


# Where a visit came from, one label per row: explicit ?ref= wins, then
# utm_source, then referrer presence splits organic referral from direct.
_VISIT_SOURCE = func.coalesce(
    PageVisit.ref,
    PageVisit.utm_source,
    sa.case(
        (sa.or_(PageVisit.referrer.is_(None), PageVisit.referrer == ""), "direct"),
        else_="referral",
    ),
)

_SIGNUP_SOURCE = func.coalesce(User.signup_ref, User.signup_utm_source, "direct")


def record_visit(
    db: Session,
    *,
    path: str,
    referrer: str | None,
    ref: str | None,
    utm_source: str | None,
    utm_medium: str | None,
    utm_campaign: str | None,
    user_id: uuid.UUID | None,
    user_agent: str | None,
) -> None:
    db.add(
        PageVisit(
            path=path,
            referrer=referrer,
            ref=ref,
            utm_source=utm_source,
            utm_medium=utm_medium,
            utm_campaign=utm_campaign,
            user_id=user_id,
            user_agent=user_agent,
        )
    )
    db.flush()


def signups_by_day(db: Session, start: datetime, end: datetime) -> list[tuple]:
    day = _utc_day(User.created_at)
    return list(
        db.execute(
            select(day.label("day"), func.count().label("count"))
            .where(User.created_at >= start, User.created_at < end)
            .group_by(day)
            .order_by(day)
        ).all()
    )


def signups_by_source(db: Session, start: datetime, end: datetime) -> list[tuple]:
    return list(
        db.execute(
            select(_SIGNUP_SOURCE.label("source"), func.count().label("count"))
            .where(User.created_at >= start, User.created_at < end)
            .group_by(_SIGNUP_SOURCE)
            .order_by(func.count().desc())
        ).all()
    )


def visits_by_day_by_source(db: Session, start: datetime, end: datetime) -> list[tuple]:
    day = _utc_day(PageVisit.occurred_at)
    return list(
        db.execute(
            select(day.label("day"), _VISIT_SOURCE.label("source"), func.count().label("count"))
            .where(PageVisit.occurred_at >= start, PageVisit.occurred_at < end)
            .group_by(day, _VISIT_SOURCE)
            .order_by(day)
        ).all()
    )


def visits_by_source(db: Session, start: datetime, end: datetime) -> list[tuple]:
    return list(
        db.execute(
            select(_VISIT_SOURCE.label("source"), func.count().label("count"))
            .where(PageVisit.occurred_at >= start, PageVisit.occurred_at < end)
            .group_by(_VISIT_SOURCE)
            .order_by(func.count().desc())
        ).all()
    )


def activation(db: Session, start: datetime, end: datetime) -> tuple[int, int]:
    """(activated, signups) among users created in range. "Activated" =
    owner of a family that has a birth, OR posted a timeline event. Births
    carry no creator FK, so owner-of-a-family-with-a-birth is the proxy —
    a co-parent who joined an existing family counts too, which is fair.
    """
    in_range = sa.and_(
        User.created_at >= start,
        User.created_at < end,
        User.deleted_at.is_(None),
    )
    owns_birth = (
        select(sa.literal(1))
        .select_from(FamilyMembership)
        .join(Birth, Birth.family_id == FamilyMembership.family_id)
        .where(
            FamilyMembership.user_id == User.id,
            FamilyMembership.role == FamilyRole.owner,
        )
        .exists()
    )
    posted = (
        select(sa.literal(1))
        .where(TimelineEvent.posted_by_user_id == User.id)
        .exists()
    )
    activated = db.scalar(
        select(func.count()).select_from(User).where(in_range, sa.or_(owns_birth, posted))
    )
    signups = db.scalar(select(func.count()).select_from(User).where(in_range))
    return int(activated or 0), int(signups or 0)


def invite_stats(db: Session, start: datetime, end: datetime) -> dict:
    created = db.scalar(
        select(func.count())
        .select_from(ViewerInvitation)
        .where(ViewerInvitation.created_at >= start, ViewerInvitation.created_at < end)
    )
    # redemption_count counts authenticated redemptions (incl. the same
    # person re-following a link), never anonymous clicks — those come from
    # page_visits on /invite/ paths below.
    redemptions = db.scalar(
        select(func.coalesce(func.sum(ViewerInvitation.redemption_count), 0)).where(
            ViewerInvitation.created_at >= start, ViewerInvitation.created_at < end
        )
    )
    distinct_redeemers = db.scalar(
        select(func.count(func.distinct(ViewerInvitationRedemption.user_id))).where(
            ViewerInvitationRedemption.redeemed_at >= start,
            ViewerInvitationRedemption.redeemed_at < end,
        )
    )
    link_visits = db.scalar(
        select(func.count())
        .select_from(PageVisit)
        .where(
            PageVisit.path.like("/invite/%"),
            PageVisit.occurred_at >= start,
            PageVisit.occurred_at < end,
        )
    )
    return {
        "created": int(created or 0),
        "redemptions": int(redemptions or 0),
        "distinct_redeemers": int(distinct_redeemers or 0),
        "link_visits": int(link_visits or 0),
    }


def redeemer_owner_conversion(db: Session) -> tuple[int, int]:
    """(became_owners, all_redeemers), all-time — the viral loop. A
    "conversion" is someone who arrived through a share link and *later*
    became an owner (started their own birth story or joined as co-parent):
    owner membership joined_at strictly after their redemption.
    """
    became_owners = db.scalar(
        select(func.count(func.distinct(ViewerInvitationRedemption.user_id))).where(
            (
                select(sa.literal(1))
                .where(
                    FamilyMembership.user_id == ViewerInvitationRedemption.user_id,
                    FamilyMembership.role == FamilyRole.owner,
                    FamilyMembership.joined_at > ViewerInvitationRedemption.redeemed_at,
                )
                .exists()
            )
        )
    )
    all_redeemers = db.scalar(
        select(func.count(func.distinct(ViewerInvitationRedemption.user_id)))
    )
    return int(became_owners or 0), int(all_redeemers or 0)


def active_users(db: Session, now: datetime) -> tuple[int, int]:
    """(dau, wau) from throttled last_seen_at — 15-minute write granularity
    is invisible at day scale."""
    base = select(func.count()).select_from(User).where(User.deleted_at.is_(None))
    dau = db.scalar(base.where(User.last_seen_at >= now - timedelta(days=1)))
    wau = db.scalar(base.where(User.last_seen_at >= now - timedelta(days=7)))
    return int(dau or 0), int(wau or 0)


def revenue(db: Session, start: datetime, end: datetime) -> dict:
    unlock_count, unlock_cents = db.execute(
        select(func.count(), func.coalesce(func.sum(UnlockPurchase.amount_cents), 0)).where(
            UnlockPurchase.purchased_at >= start, UnlockPurchase.purchased_at < end
        )
    ).one()
    gift_count, gift_cents = db.execute(
        select(func.count(), func.coalesce(func.sum(GiftOrder.amount_cents), 0)).where(
            GiftOrder.status == "paid",
            GiftOrder.paid_at >= start,
            GiftOrder.paid_at < end,
        )
    ).one()
    return {
        "unlock_count": int(unlock_count),
        "unlock_cents": int(unlock_cents),
        "gift_count": int(gift_count),
        "gift_cents": int(gift_cents),
    }
