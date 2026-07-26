"""App assembly for the multi-tenant Lily backend.

The route table lives in `routes/` — one APIRouter per domain. This
module owns the FastAPI app itself: CORS, the sliding session cookie,
and router registration.
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from auth import SESSION_COOKIE_NAME, apply_session_cookie, refreshed_session_token
from routes import (
    auth as auth_routes,
    births as births_routes,
    checkout as checkout_routes,
    engagement as engagement_routes,
    gifts as gifts_routes,
    invitations as invitations_routes,
    media as media_routes,
    stream as stream_routes,
    timeline as timeline_routes,
    tracking as tracking_routes,
)
from storage import ensure_bucket


@asynccontextmanager
async def lifespan(_app: FastAPI):
    ensure_bucket()
    yield


app = FastAPI(title="Arrival Story", lifespan=lifespan)
# Wildcard in dev; production sets CORS_ALLOW_ORIGINS to the site origin.
# (In prod the API is same-origin behind nginx anyway — this is belt and
# braces, not the primary boundary.)
_cors_origins = [
    o.strip()
    for o in os.getenv("CORS_ALLOW_ORIGINS", "*").split(",")
    if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials="*" not in _cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def slide_session_cookie(request: Request, call_next):
    """Sessions are sacred infrastructure: any request carrying a session
    cookie older than SESSION_REFRESH_AFTER gets a fresh one, so the single
    auth event happens months before the birth and never recurs during it.
    """
    response = await call_next(request)
    raw = request.cookies.get(SESSION_COOKIE_NAME)
    if raw:
        fresh = refreshed_session_token(raw)
        if fresh:
            apply_session_cookie(response, fresh)
    return response


@app.get("/")
async def root() -> dict:
    return {"name": "arrival-story", "status": "running"}


app.include_router(auth_routes.router)
app.include_router(births_routes.router)
app.include_router(timeline_routes.router)
app.include_router(engagement_routes.router)
# checkout before gifts: `/birth/{id}/gifts/orders` must register ahead of
# `/birth/{id}/gifts/{rendering_id}` or "orders" gets eaten by the wildcard.
app.include_router(checkout_routes.router)
app.include_router(gifts_routes.router)
app.include_router(invitations_routes.router)
app.include_router(media_routes.router)
app.include_router(stream_routes.router)
app.include_router(tracking_routes.router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
