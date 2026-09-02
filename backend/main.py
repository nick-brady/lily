"""App assembly for the multi-tenant Lily backend.

The route table lives in `routes/` — one APIRouter per domain. This
module owns the FastAPI app itself: logging, CORS, the request scope,
the sliding session cookie, and router registration.
"""
from __future__ import annotations

import logging
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import observability
from auth import SESSION_COOKIE_NAME, apply_session_cookie, refreshed_session_token
from routes import (
    auth as auth_routes,
    births as births_routes,
    checkout as checkout_routes,
    engagement as engagement_routes,
    gifts as gifts_routes,
    invitations as invitations_routes,
    media as media_routes,
    observability as observability_routes,
    stream as stream_routes,
    timeline as timeline_routes,
    tracking as tracking_routes,
)
from storage import ensure_bucket

# uvicorn imports `main:app`, so this runs once per process, before any
# request. The worker makes the same call with "worker".
observability.configure_logging(observability.WEB)
logger = logging.getLogger("lily.web")
access_logger = logging.getLogger(observability.ACCESS_LOGGER)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    ensure_bucket()
    logger.info("web started")
    yield
    logger.info("web stopping")
    observability.shutdown_logging()


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


@app.middleware("http")
async def request_scope(request: Request, call_next):
    """Every request gets an id, every log line written during it carries
    that id, and the response says what it was — so a 500 handed to a user
    is something they can quote and we can find.

    Also the one place an unhandled exception is turned into a response:
    logged once with its traceback, answered with a generic 500 and the id.
    And the access line, to the file only (see observability): method,
    path, status, and time to first byte — never the query string, which
    is where a token could sit.
    """
    scope = observability.begin_request(request.headers.get("x-request-id"))
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:  # noqa: BLE001 - this is the catch-all, by design
        logger.exception(
            "unhandled error",
            extra={"method": request.method, "path": request.url.path},
        )
        response = JSONResponse(
            status_code=500,
            content={
                "detail": "Something went wrong on our side.",
                "request_id": scope.request_id,
            },
        )
    duration_ms = round((time.perf_counter() - started) * 1000, 1)
    response.headers["X-Request-Id"] = scope.request_id
    fields = {
        "method": request.method,
        "path": request.url.path,
        "status": response.status_code,
        "duration_ms": duration_ms,
    }
    access_logger.info("%s %s %s", request.method, request.url.path, response.status_code, extra=fields)
    if response.status_code >= 500:
        # a deliberate 503 (say, the email provider is down) is worth a row
        # in the table even though nothing raised
        logger.warning("%s %s answered %s", request.method, request.url.path, response.status_code, extra=fields)
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
app.include_router(observability_routes.router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
