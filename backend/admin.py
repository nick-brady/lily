"""Admin authorization + the dashboard overview aggregation.

Authorization is an env-var email allowlist (`ADMIN_EMAILS`, comma
separated) rather than an `is_admin` column: one admin, managed at deploy
time, and nothing in the API surface can escalate into it. Emails are
compared against `User.email`, which auth already lowercase-normalizes.
A phone-only account can therefore never be admin — deliberate.
"""
from __future__ import annotations

import os
from datetime import date, datetime, time, timedelta, timezone

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from auth import get_current_user
from models import User
from repositories import stats as stats_repo
from schemas import (
    ActivationStatsOut,
    ActiveUsersOut,
    AdminOverviewOut,
    ConversionStatsOut,
    DailyCount,
    DailySourceCount,
    InviteStatsOut,
    RevenueStatsOut,
    SignupStatsOut,
    SourceCount,
    VisitStatsOut,
)


ADMIN_EMAILS = {
    e.strip().lower()
    for e in os.environ.get("ADMIN_EMAILS", "").split(",")
    if e.strip()
}

DEFAULT_RANGE_DAYS = 30


def get_admin_user(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.email or current_user.email.lower() not in ADMIN_EMAILS:
        raise HTTPException(status_code=403, detail="Not authorized")
    return current_user


def overview_stats(
    db: Session, start_date: date | None, end_date: date | None
) -> AdminOverviewOut:
    """Everything the dashboard shows, in one response. Each aggregate is
    milliseconds at this scale; one endpoint keeps it one auth check and
    one frontend loader. Dates are inclusive UTC calendar days."""
    now = datetime.now(timezone.utc)
    if end_date is None:
        end_date = now.date()
    if start_date is None:
        start_date = end_date - timedelta(days=DEFAULT_RANGE_DAYS - 1)
    if start_date > end_date:
        raise HTTPException(status_code=400, detail="start_date is after end_date")

    start = datetime.combine(start_date, time.min, tzinfo=timezone.utc)
    end = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=timezone.utc)

    signup_days = stats_repo.signups_by_day(db, start, end)
    signup_sources = stats_repo.signups_by_source(db, start, end)
    visit_day_sources = stats_repo.visits_by_day_by_source(db, start, end)
    visit_sources = stats_repo.visits_by_source(db, start, end)
    activated, signup_total = stats_repo.activation(db, start, end)
    invites = stats_repo.invite_stats(db, start, end)
    became_owners, all_redeemers = stats_repo.redeemer_owner_conversion(db)
    dau, wau = stats_repo.active_users(db, now)
    rev = stats_repo.revenue(db, start, end)

    return AdminOverviewOut(
        start_date=start_date,
        end_date=end_date,
        signups=SignupStatsOut(
            total=signup_total,
            by_day=[DailyCount(day=r.day, count=r.count) for r in signup_days],
            by_source=[
                SourceCount(source=r.source, count=r.count) for r in signup_sources
            ],
        ),
        visits=VisitStatsOut(
            total=sum(r.count for r in visit_sources),
            by_day_by_source=[
                DailySourceCount(day=r.day, source=r.source, count=r.count)
                for r in visit_day_sources
            ],
            by_source=[
                SourceCount(source=r.source, count=r.count) for r in visit_sources
            ],
        ),
        activation=ActivationStatsOut(
            activated=activated,
            signups=signup_total,
            rate=activated / signup_total if signup_total else None,
        ),
        invites=InviteStatsOut(**invites),
        conversion=ConversionStatsOut(
            became_owners=became_owners,
            all_redeemers=all_redeemers,
            rate=became_owners / all_redeemers if all_redeemers else None,
        ),
        active_users=ActiveUsersOut(dau=dau, wau=wau),
        revenue=RevenueStatsOut(
            **rev, total_cents=rev["unlock_cents"] + rev["gift_cents"]
        ),
    )
