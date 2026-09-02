"""The logging tree: what a record carries, what gets redacted, how the
table writer batches, and what the middleware does with a request.

The SQL behind `/admin/logs` is exercised end-to-end locally against
postgres, as with the admin stats; here the pieces are tested directly.
"""
from __future__ import annotations

import json
import logging
import queue
import threading
import time
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

import observability as obs
from repositories import app_logs as app_logs_repo


def _record(msg, *args, name="lily.test", level=logging.INFO, exc_info=None, **extra):
    record = logging.LogRecord(name, level, "x.py", 1, msg, args, exc_info)
    for k, v in extra.items():
        setattr(record, k, v)
    return record


def _with_exc(msg, exc):
    try:
        raise exc
    except Exception as caught:  # noqa: BLE001
        import sys

        return _record(msg, level=logging.ERROR, exc_info=sys.exc_info())


# --------------------------------------------------------------------------
# redaction


class TestRedact:
    def test_email_phone_and_tokens_become_placeholders(self):
        text = (
            "sent to nick@example.com and +1 (555) 123-4567, "
            "url ?token=abc.def&x=1 header Bearer eyJhbGci.xyz"
        )
        out = obs.redact(text)
        assert "nick@example.com" not in out
        assert "555" not in out
        assert "abc.def" not in out
        assert "eyJhbGci" not in out
        assert out.count("<email>") == 1
        assert out.count("<phone>") == 1
        assert "token=<redacted>&x=1" in out
        assert "Bearer <redacted>" in out

    def test_uuids_timestamps_and_prose_are_untouched(self):
        text = (
            "media 3f2504e0-4f89-11d3-9a0c-0305e82c3301 failed at "
            "2026-09-01 12:00:00,123 after 1600 px; 97 contractions in 24 hours"
        )
        assert obs.redact(text) == text

    def test_bare_ten_digit_phone(self):
        assert obs.redact("call 5551234567 now") == "call <phone> now"


# --------------------------------------------------------------------------
# enrich + fingerprint


class TestEnrich:
    def test_fingerprint_ignores_interpolated_arguments(self):
        a = _record("media %s failed", "one")
        b = _record("media %s failed", "two")
        assert obs.fingerprint(a) == obs.fingerprint(b)

    def test_fingerprint_changes_with_exception_type(self):
        a = _with_exc("boom", ValueError("x"))
        b = _with_exc("boom", KeyError("x"))
        assert obs.fingerprint(a) != obs.fingerprint(b)

    def test_enrich_redacts_message_and_traceback_once(self):
        record = _with_exc("owner %s", RuntimeError("phone 555-123-4567 leaked"))
        record.args = ("nick@example.com",)
        enrich = obs.Enrich()
        assert enrich.filter(record) is True
        assert record.getMessage() == "owner <email>"
        assert "555-123-4567" not in record.exc_text
        assert "RuntimeError" in record.exc_text
        assert record.fingerprint  # computed before the template was replaced
        # a second handler running the same filter changes nothing
        before = (record.msg, record.exc_text, record.fingerprint)
        enrich.filter(record)
        assert (record.msg, record.exc_text, record.fingerprint) == before

    def test_enrich_carries_the_request_scope(self):
        scope = obs.begin_request("req123")
        obs.set_current_user("11111111-1111-1111-1111-111111111111")
        record = _record("hello")
        obs.Enrich().filter(record)
        assert record.request_id == "req123"
        assert record.user_id == "11111111-1111-1111-1111-111111111111"
        assert scope.user_id == record.user_id

    def test_bad_format_string_does_not_lose_the_line(self):
        record = _record("%d things", "not-a-number")
        obs.Enrich().filter(record)
        assert "not-a-number" in record.getMessage()


# --------------------------------------------------------------------------
# formatting


class TestJsonFormatter:
    def test_documented_fields_and_extras(self):
        record = _record("GET %s", "/health", name=obs.ACCESS_LOGGER, method="GET", status=200)
        obs.Enrich().filter(record)
        doc = json.loads(obs.JsonFormatter().format(record))
        assert doc["msg"] == "GET /health"
        assert doc["level"] == "INFO"
        assert doc["logger"] == obs.ACCESS_LOGGER
        assert doc["method"] == "GET" and doc["status"] == 200
        assert set(doc) >= {"ts", "level", "logger", "service", "msg", "request_id", "user_id", "fingerprint"}
        datetime.fromisoformat(doc["ts"])
        assert doc["ts"].endswith("+00:00")

    def test_row_of_shapes_a_table_row(self):
        record = _with_exc("refund failed for %s", ValueError("no"))
        record.args = ("pi_123",)
        obs.begin_request("abc")
        obs.set_current_user("11111111-1111-1111-1111-111111111111")
        obs.Enrich().filter(record)
        row = obs.row_of(record)
        assert row["message"] == "refund failed for pi_123"
        assert row["level"] == "ERROR"
        assert "ValueError" in row["exception"]
        assert row["request_id"] == "abc"
        assert str(row["user_id"]) == "11111111-1111-1111-1111-111111111111"
        assert row["logged_at"].tzinfo is not None
        assert row["extra"] is None


# --------------------------------------------------------------------------
# the table writer


class _Sink:
    def __init__(self, fail_first=False):
        self.batches: list[list[dict]] = []
        self.fail_first = fail_first
        self.calls = 0
        self.got = threading.Event()

    def __call__(self, rows):
        self.calls += 1
        if self.fail_first and self.calls == 1:
            raise RuntimeError("db down")
        self.batches.append(rows)
        self.got.set()


def _enriched(msg, *args, **kw):
    record = _record(msg, *args, **kw)
    obs.Enrich().filter(record)
    return record


class TestDbLogWriter:
    def test_flushes_on_batch_size(self):
        q: queue.Queue = queue.Queue()
        sink = _Sink()
        writer = obs.DbLogWriter(q, sink, batch_size=3, flush_seconds=60)
        writer.start()
        for i in range(3):
            q.put(_enriched("line %d", i))
        assert sink.got.wait(2)
        writer.stop()
        assert [r["message"] for r in sink.batches[0]] == ["line 0", "line 1", "line 2"]

    def test_flushes_on_time_with_a_partial_batch(self):
        q: queue.Queue = queue.Queue()
        sink = _Sink()
        writer = obs.DbLogWriter(q, sink, batch_size=50, flush_seconds=0.05)
        writer.start()
        q.put(_enriched("alone"))
        assert sink.got.wait(2)
        writer.stop()
        assert sink.batches[0][0]["message"] == "alone"

    def test_a_failing_sink_loses_one_batch_and_carries_on(self, capsys):
        q: queue.Queue = queue.Queue()
        sink = _Sink(fail_first=True)
        writer = obs.DbLogWriter(q, sink, batch_size=1, flush_seconds=60)
        writer.start()
        q.put(_enriched("first"))
        q.put(_enriched("second"))
        assert sink.got.wait(2)
        writer.stop()
        assert writer.failures == 1
        assert [r["message"] for b in sink.batches for r in b] == ["second"]
        assert "dropped 1 log rows" in capsys.readouterr().err

    def test_stop_flushes_what_is_pending(self):
        q: queue.Queue = queue.Queue()
        sink = _Sink()
        writer = obs.DbLogWriter(q, sink, batch_size=50, flush_seconds=60)
        writer.start()
        q.put(_enriched("pending"))
        writer.stop()
        assert sink.batches and sink.batches[0][0]["message"] == "pending"

    def test_queue_handler_drops_when_full(self):
        q: queue.Queue = queue.Queue(maxsize=1)
        handler = obs.DropOnFullQueueHandler(q)
        handler.handle(_record("one"))
        handler.handle(_record("two"))
        assert handler.dropped == 1
        assert q.qsize() == 1

    def test_access_and_sqlalchemy_lines_stay_out_of_the_table(self):
        assert not obs.not_for_db(_record("GET /", name=obs.ACCESS_LOGGER))
        assert not obs.not_for_db(_record("SELECT 1", name="sqlalchemy.engine.Engine"))
        assert not obs.not_for_db(_record("hit", name="uvicorn.access"))
        assert obs.not_for_db(_record("refund failed", name="gift_fulfillment"))
        assert obs.not_for_db(_record("media done", name="media_worker"))


# --------------------------------------------------------------------------
# configure_logging is repeatable and honours the switches


class TestConfigure:
    def test_reconfiguring_replaces_handlers_and_writes_a_file(self, tmp_path, monkeypatch):
        monkeypatch.setenv("LOG_DIR", str(tmp_path))
        monkeypatch.setenv("LOG_TO_DB", "1")
        sink = _Sink()
        obs.configure_logging("web", sink=sink)
        obs.configure_logging("web", sink=sink)
        root = logging.getLogger()
        kinds = [type(h).__name__ for h in root.handlers]
        assert kinds.count("StreamHandler") == 1
        assert kinds.count("WatchedFileHandler") == 1
        assert kinds.count("DropOnFullQueueHandler") == 1

        logging.getLogger("lily.test").info("to file and table, %s", "please")
        logging.getLogger(obs.ACCESS_LOGGER).info("GET /x 200")
        obs.shutdown_logging()

        lines = [json.loads(l) for l in (tmp_path / "web.jsonl").read_text().splitlines()]
        assert [l["msg"] for l in lines] == ["to file and table, please", "GET /x 200"]
        assert lines[0]["service"] == "web"
        messages = [r["message"] for b in sink.batches for r in b]
        assert messages == ["to file and table, please"]  # no access line
        monkeypatch.delenv("LOG_DIR")
        monkeypatch.setenv("LOG_TO_DB", "0")
        obs.configure_logging("web")


# --------------------------------------------------------------------------
# the middleware


def _client(**kwargs):
    from main import app

    return TestClient(app, **kwargs)


@pytest.fixture
def boom_route():
    from main import app

    @app.get("/__boom")
    def boom():
        raise RuntimeError("kaboom for nick@example.com")

    yield
    app.router.routes[:] = [r for r in app.router.routes if getattr(r, "path", None) != "/__boom"]


class TestRequestScope:
    def test_every_response_carries_a_request_id(self):
        r = _client().get("/")
        assert r.status_code == 200
        assert len(r.headers["x-request-id"]) == 12

    def test_an_inbound_request_id_is_kept(self):
        r = _client().get("/", headers={"X-Request-Id": "from-nginx"})
        assert r.headers["x-request-id"] == "from-nginx"

    def test_unhandled_exception_becomes_a_500_with_the_id(self, boom_route, caplog):
        caplog.set_level(logging.INFO)
        r = _client(raise_server_exceptions=False).get("/__boom?token=secret")
        assert r.status_code == 500
        body = r.json()
        assert body["request_id"] == r.headers["x-request-id"]
        assert "kaboom" not in body["detail"]

        errors = [rec for rec in caplog.records if rec.levelno == logging.ERROR]
        assert len(errors) == 1
        assert errors[0].exc_info is not None
        assert errors[0].method == "GET" and errors[0].path == "/__boom"

        access = [rec for rec in caplog.records if rec.name == obs.ACCESS_LOGGER]
        assert len(access) == 1
        assert access[0].path == "/__boom"
        assert "secret" not in access[0].getMessage()
        assert access[0].status == 500
        assert access[0].duration_ms >= 0

    def test_a_deliberate_5xx_is_noted(self, caplog):
        from main import app

        from fastapi import HTTPException

        @app.get("/__unavailable")
        def unavailable():
            raise HTTPException(status_code=503, detail="mail is down")

        try:
            caplog.set_level(logging.INFO)
            r = _client().get("/__unavailable")
            assert r.status_code == 503
            warnings = [rec for rec in caplog.records if rec.levelno == logging.WARNING]
            assert len(warnings) == 1 and warnings[0].status == 503
        finally:
            app.router.routes[:] = [
                r for r in app.router.routes if getattr(r, "path", None) != "/__unavailable"
            ]


# --------------------------------------------------------------------------
# /health and /admin/logs


class TestHealth:
    def test_ok_when_db_answers_and_worker_is_fresh(self, monkeypatch):
        from routes import observability as route_mod

        now = datetime.now(timezone.utc)
        monkeypatch.setattr(route_mod.app_logs_repo, "last_seen", lambda db, s: now)

        class FakeDb:
            def execute(self, stmt):
                class R:
                    def scalar(self):
                        return "0043"

                return R()

        from main import app
        from db import get_db

        app.dependency_overrides[get_db] = lambda: FakeDb()
        try:
            r = _client().get("/health")
        finally:
            app.dependency_overrides.pop(get_db, None)
        assert r.status_code == 200
        assert r.json()["revision"] == "0043"
        assert r.json()["worker"]["ok"] is True

    def test_503_when_the_worker_is_stale(self, monkeypatch):
        from routes import observability as route_mod

        stale = datetime.now(timezone.utc) - timedelta(minutes=10)
        monkeypatch.setattr(route_mod.app_logs_repo, "last_seen", lambda db, s: stale)

        class FakeDb:
            def execute(self, stmt):
                class R:
                    def scalar(self):
                        return "0043"

                return R()

        from main import app
        from db import get_db

        app.dependency_overrides[get_db] = lambda: FakeDb()
        try:
            r = _client().get("/health")
        finally:
            app.dependency_overrides.pop(get_db, None)
        assert r.status_code == 503
        assert r.json() == {
            "status": "degraded",
            "db": "ok",
            "revision": "0043",
            "worker": {"seen_at": stale.isoformat().replace("+00:00", "Z"), "ok": False},
        }

    def test_503_when_the_db_raises(self):
        class FakeDb:
            def execute(self, stmt):
                raise RuntimeError("connection refused")

        from main import app
        from db import get_db

        app.dependency_overrides[get_db] = lambda: FakeDb()
        try:
            r = _client().get("/health")
        finally:
            app.dependency_overrides.pop(get_db, None)
        assert r.status_code == 503
        assert r.json()["db"] == "error"
        assert r.json()["revision"] is None

    def test_freshness_window(self):
        now = datetime.now(timezone.utc)
        assert app_logs_repo.is_fresh(now - timedelta(seconds=90), now)
        assert not app_logs_repo.is_fresh(now - timedelta(seconds=121), now)
        assert not app_logs_repo.is_fresh(None, now)


class TestAdminLogs:
    def test_requires_a_token(self):
        assert _client().get("/admin/logs").status_code == 401

    def test_non_admin_is_refused(self, monkeypatch):
        import admin
        from models import User

        monkeypatch.setattr(admin, "ADMIN_EMAILS", {"boss@example.com"})
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc:
            admin.get_admin_user(User(email="someone@example.com"))
        assert exc.value.status_code == 403

    def test_filters_reach_the_repository(self, monkeypatch):
        import admin
        from main import app
        from db import get_db
        from models import User
        from routes import observability as route_mod

        seen = {}

        def fake_recent(db, **kw):
            seen.update(kw)
            return []

        monkeypatch.setattr(route_mod.app_logs_repo, "recent", fake_recent)
        monkeypatch.setattr(route_mod.app_logs_repo, "counts_by_level", lambda db, **kw: {"ERROR": 2})
        monkeypatch.setattr(route_mod.app_logs_repo, "counts_by_service", lambda db, **kw: {"web": 2})
        monkeypatch.setattr(route_mod.app_logs_repo, "last_seen", lambda db, s: None)
        app.dependency_overrides[admin.get_admin_user] = lambda: User(email="boss@example.com")
        app.dependency_overrides[get_db] = lambda: object()
        try:
            r = _client().get("/admin/logs?levels=warning,ERROR&services=Web&q=refund&limit=50")
        finally:
            app.dependency_overrides.clear()
        assert r.status_code == 200
        assert seen["levels"] == ["WARNING", "ERROR"]
        assert seen["services"] == ["web"]
        assert seen["q"] == "refund"
        assert seen["limit"] == 50
        assert seen["since"] is not None
        body = r.json()
        assert body["level_counts"] == {"ERROR": 2}
        assert body["service_counts"] == {"web": 2}
        assert body["worker"] == {"seen_at": None, "ok": False}
        assert body["items"] == []
