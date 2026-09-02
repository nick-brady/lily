"""Where every log line goes, and what it carries with it.

Before this, the web process configured no logging at all: `logger.info`
from app code went to Python's last-resort handler and was dropped, and the
few warnings that did surface landed in journald with nothing to say which
request they belonged to. A failure in production was invisible unless
someone happened to be reading the journal at the time.

Now each process calls `configure_logging("web")` or `("worker")` once, and
every record from then on goes three ways:

    stderr      one line, for `journalctl` and `docker compose logs`
    $LOG_DIR/<service>.jsonl
                JSON lines, one object per record, rotated by logrotate.
                The per-request access line lives only here.
    app_logs    the table the admin site reads. INFO and up, minus the
                access lines, written in batches from a background thread
                that can never slow down or fail a request.

Every record picks up the request id and the user id of the request it was
written during (`RequestScope`), so a 500 handed to a user carries an id
that finds the traceback, and a stripped message such as `media %s failed`
gets a `fingerprint` from its *template*, so the same failure groups
together however many different ids it happens to.

What never goes anywhere: captions, note bodies, file names, emails, phones,
children's names, tokens. The callers keep those out of messages; the
`Enrich` filter redacts anything shaped like an email, a phone number, or a
token that slips through, in messages and tracebacks alike.
"""
from __future__ import annotations

import copy
import hashlib
import json
import logging
import logging.handlers
import os
import queue
import re
import sys
import threading
import time
import uuid
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

ACCESS_LOGGER = "lily.access"
WEB = "web"
WORKER = "worker"

# The table takes INFO and up. These loggers never go to the table: the
# access line is a per-request row the user chose to keep in files only,
# and the rest would let a failing insert log itself into a loop.
_NOT_FOR_DB = (ACCESS_LOGGER, "uvicorn.access", "sqlalchemy", __name__)
# Libraries that narrate every call at INFO — httpx prints each request URL,
# which for Printful and S3 can carry signed links.
_QUIET = ("httpx", "httpcore", "botocore", "boto3", "s3transfer", "urllib3", "PIL", "watchfiles")

DB_BATCH_SIZE = 50
DB_FLUSH_SECONDS = 1.0
QUEUE_SIZE = 10_000
MESSAGE_MAX = 4_000
EXCEPTION_MAX = 20_000

RowSink = Callable[[list[dict]], None]


# --------------------------------------------------------------------------
# request scope


@dataclass
class RequestScope:
    """What one request knows about itself, shared between the middleware
    task and the route task.

    A ContextVar set in the middleware is visible to the route (child tasks
    copy the context), but a value the route sets is not visible back in the
    middleware. Holding one mutable object in the var lets `_user_from_jwt`
    fill in the user id and the access line, written later by the
    middleware, still see it."""

    request_id: str
    user_id: str | None = None


_scope_var: ContextVar[RequestScope | None] = ContextVar("lily_request_scope", default=None)
_service = "unknown"


def new_request_id() -> str:
    return uuid.uuid4().hex[:12]


def begin_request(request_id: str | None = None) -> RequestScope:
    scope = RequestScope(request_id=request_id or new_request_id())
    _scope_var.set(scope)
    return scope


def current_request_id() -> str | None:
    scope = _scope_var.get()
    return scope.request_id if scope else None


def set_current_user(user_id) -> None:
    """Called once auth has resolved a user. A no-op outside a request."""
    scope = _scope_var.get()
    if scope is not None:
        scope.user_id = str(user_id)


# --------------------------------------------------------------------------
# redaction

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
# A phone: optional country code, then 3-3-4 with any of the usual
# separators. Anchored so the digit runs inside a UUID or a timestamp
# don't qualify.
_PHONE = re.compile(
    r"(?<![\w-])(?:\+?\d{1,3}[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}(?![\w-])"
)
_TOKEN = re.compile(r"(?i)(\btoken=)[^&\s\"']+")
_BEARER = re.compile(r"(?i)(\bBearer\s+)[A-Za-z0-9._~+/=-]+")


def redact(text: str) -> str:
    text = _EMAIL.sub("<email>", text)
    text = _PHONE.sub("<phone>", text)
    text = _TOKEN.sub(r"\1<redacted>", text)
    text = _BEARER.sub(r"\1<redacted>", text)
    return text


def fingerprint(record: logging.LogRecord) -> str:
    """A stable id for 'this line, from this place'. Built from the message
    *template* (`record.msg`, before `%` interpolation) so `media %s failed`
    is one fingerprint however many assets it happens to."""
    exc_type = ""
    if record.exc_info and record.exc_info[0] is not None:
        exc_type = record.exc_info[0].__name__
    key = f"{record.name}|{record.levelname}|{record.msg}|{exc_type}"
    return hashlib.sha1(key.encode("utf-8", "replace")).hexdigest()[:16]


class Enrich(logging.Filter):
    """Runs on every handler, does its work once per record.

    Stamps service, request id, user id, and fingerprint; then interpolates
    the message and redacts it, and pre-formats and redacts the traceback so
    no formatter ever sees the originals. Idempotent, because a record
    passes through every handler on the root."""

    def filter(self, record: logging.LogRecord) -> bool:
        if getattr(record, "_lily_enriched", False):
            return True
        scope = _scope_var.get()
        record.service = _service
        record.request_id = scope.request_id if scope else None
        record.user_id = scope.user_id if scope else None
        record.fingerprint = fingerprint(record)
        try:
            message = record.getMessage()
        except Exception:  # noqa: BLE001 - a bad %-format must not lose the line
            message = f"{record.msg!s} {record.args!r}"
        record.msg = redact(message)
        record.args = None
        if record.exc_info and not record.exc_text:
            record.exc_text = redact(logging.Formatter().formatException(record.exc_info))
        record._lily_enriched = True
        return True


# --------------------------------------------------------------------------
# formatting

_STANDARD_ATTRS = set(
    logging.LogRecord("", 0, "", 0, "", (), None).__dict__.keys()
) | {"message", "asctime", "service", "request_id", "user_id", "fingerprint", "_lily_enriched"}


def extras_of(record: logging.LogRecord) -> dict:
    """Whatever the caller passed as `extra=`, and nothing else."""
    return {
        k: v
        for k, v in record.__dict__.items()
        if k not in _STANDARD_ATTRS and not k.startswith("_")
    }


def _ts(record: logging.LogRecord) -> datetime:
    return datetime.fromtimestamp(record.created, tz=timezone.utc)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        doc = {
            "ts": _ts(record).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "service": getattr(record, "service", _service),
            "msg": record.getMessage(),
            "request_id": getattr(record, "request_id", None),
            "user_id": getattr(record, "user_id", None),
            "fingerprint": getattr(record, "fingerprint", None),
        }
        if record.exc_text:
            doc["exc"] = record.exc_text
        doc.update(extras_of(record))
        return json.dumps(doc, default=str, ensure_ascii=False)


def row_of(record: logging.LogRecord) -> dict:
    """One `app_logs` row from an enriched record."""
    extra = extras_of(record)
    return {
        "logged_at": _ts(record),
        "service": getattr(record, "service", _service),
        "level": record.levelname,
        "logger": record.name,
        "message": record.getMessage()[:MESSAGE_MAX],
        "fingerprint": getattr(record, "fingerprint", None) or fingerprint(record),
        "request_id": getattr(record, "request_id", None),
        "user_id": _uuid_or_none(getattr(record, "user_id", None)),
        "exception": record.exc_text[-EXCEPTION_MAX:] if record.exc_text else None,
        "extra": json.loads(json.dumps(extra, default=str)) if extra else None,
    }


def _uuid_or_none(value):
    try:
        return uuid.UUID(str(value)) if value else None
    except ValueError:
        return None


# --------------------------------------------------------------------------
# the table writer


class DropOnFullQueueHandler(logging.handlers.QueueHandler):
    """Puts a copy of the record on the queue and, when the queue is full,
    drops it rather than blocking the request. Counts what it dropped."""

    def __init__(self, q: queue.Queue) -> None:
        super().__init__(q)
        self.dropped = 0

    def prepare(self, record: logging.LogRecord) -> logging.LogRecord:
        # The stock prepare() throws the traceback away; ours has already
        # been formatted and redacted by Enrich, so keep the record whole.
        return copy.copy(record)

    def enqueue(self, record: logging.LogRecord) -> None:
        try:
            self.queue.put_nowait(record)
        except queue.Full:
            self.dropped += 1


def not_for_db(record: logging.LogRecord) -> bool:
    return not record.name.startswith(_NOT_FOR_DB)


class DbLogWriter(threading.Thread):
    """Drains the queue into the sink in batches: up to DB_BATCH_SIZE rows,
    or whatever has arrived after DB_FLUSH_SECONDS. A sink that raises
    loses that one batch and is reported to stderr once; the thread keeps
    going. The sink runs on its own connection, borrowed per batch."""

    def __init__(
        self,
        q: queue.Queue,
        sink: RowSink,
        *,
        batch_size: int = DB_BATCH_SIZE,
        flush_seconds: float = DB_FLUSH_SECONDS,
    ) -> None:
        super().__init__(name="lily-log-writer", daemon=True)
        self.queue = q
        self.sink = sink
        self.batch_size = batch_size
        self.flush_seconds = flush_seconds
        self.failures = 0
        self._stopping = threading.Event()

    def run(self) -> None:
        pending: list[dict] = []
        deadline = time.monotonic() + self.flush_seconds
        while True:
            timeout = max(0.0, deadline - time.monotonic())
            try:
                record = self.queue.get(timeout=timeout)
            except queue.Empty:
                record = None
            if record is _SENTINEL:
                self._flush(pending)
                return
            if record is not None:
                pending.append(row_of(record))
            if pending and (len(pending) >= self.batch_size or time.monotonic() >= deadline):
                self._flush(pending)
                deadline = time.monotonic() + self.flush_seconds
            elif not pending:
                deadline = time.monotonic() + self.flush_seconds
            if self._stopping.is_set() and self.queue.empty():
                self._flush(pending)
                return

    def _flush(self, pending: list[dict]) -> None:
        if not pending:
            return
        rows, pending[:] = list(pending), []
        try:
            self.sink(rows)
        except Exception as exc:  # noqa: BLE001 - logging must never take the app down
            self.failures += 1
            print(
                f"lily-log-writer: dropped {len(rows)} log rows: {exc!r}",
                file=sys.stderr,
                flush=True,
            )

    def stop(self, timeout: float = 5.0) -> None:
        self._stopping.set()
        try:
            self.queue.put_nowait(_SENTINEL)
        except queue.Full:
            pass
        self.join(timeout)


_SENTINEL = object()
_writer: DbLogWriter | None = None


# --------------------------------------------------------------------------
# configuration


def configure_logging(service: str, *, sink: RowSink | None = None) -> None:
    """Point the root logger at stderr, the JSON file, and the table.

    Safe to call again (uvicorn --reload, tests): handlers are replaced,
    not stacked. `LOG_DIR` unset means no file; `LOG_TO_DB=0` means no
    table, which is what the unit tests want."""
    global _service, _writer
    _service = service
    shutdown_logging()

    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)
        handler.close()
    root.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())
    enrich = Enrich()

    log_dir = os.getenv("LOG_DIR")

    stderr = logging.StreamHandler(sys.stderr)
    stderr.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    stderr.addFilter(enrich)
    if log_dir:
        # the file has the access lines; the journal needn't repeat them
        stderr.addFilter(lambda r: r.name != ACCESS_LOGGER)
    root.addHandler(stderr)

    if log_dir:
        os.makedirs(log_dir, exist_ok=True)
        file_handler = logging.handlers.WatchedFileHandler(
            os.path.join(log_dir, f"{service}.jsonl"), encoding="utf-8"
        )
        file_handler.setFormatter(JsonFormatter())
        file_handler.addFilter(enrich)
        root.addHandler(file_handler)

    if os.getenv("LOG_TO_DB", "1") != "0":
        if sink is None:
            from repositories import app_logs as app_logs_repo  # needs DATABASE_URL

            sink = app_logs_repo.insert_many
        q: queue.Queue = queue.Queue(QUEUE_SIZE)
        queue_handler = DropOnFullQueueHandler(q)
        queue_handler.setLevel(logging.INFO)
        queue_handler.addFilter(enrich)
        queue_handler.addFilter(not_for_db)
        root.addHandler(queue_handler)
        _writer = DbLogWriter(q, sink)
        _writer.start()

    for name in _QUIET:
        logging.getLogger(name).setLevel(logging.WARNING)


def shutdown_logging() -> None:
    """Flush what's queued for the table and stop the writer thread."""
    global _writer
    if _writer is not None:
        _writer.stop()
        _writer = None
