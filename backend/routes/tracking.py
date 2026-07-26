"""Anonymous page-view tracking and the admin stats overview."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

import admin as admin_mod
from auth import get_optional_current_user
from db import get_db
from models import User
from repositories import stats as stats_repo
from schemas import AdminOverviewOut, TrackIn

router = APIRouter()


@router.post("/track", status_code=204)
def track_visit(
    payload: TrackIn,
    request: Request,
    current_user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """Anonymous page-view tracking (self-hosted; no cookies, no IPs).
    nginx rate-limits this path in production."""
    user_agent = request.headers.get("user-agent")
    stats_repo.record_visit(
        db,
        path=payload.path,
        referrer=payload.referrer,
        ref=payload.ref,
        utm_source=payload.utm_source,
        utm_medium=payload.utm_medium,
        utm_campaign=payload.utm_campaign,
        user_id=current_user.id if current_user else None,
        user_agent=user_agent[:256] if user_agent else None,
    )
    db.commit()
    return Response(status_code=204)


@router.get("/admin/stats/overview", response_model=AdminOverviewOut)
def admin_stats_overview(
    start_date: date | None = None,
    end_date: date | None = None,
    admin_user: User = Depends(admin_mod.get_admin_user),
    db: Session = Depends(get_db),
) -> AdminOverviewOut:
    """Everything the admin dashboard shows. Dates are inclusive UTC
    calendar days; defaults to the last 30 days."""
    return admin_mod.overview_stats(db, start_date, end_date)
