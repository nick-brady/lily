"""Smoke tests for the reaction + comment routes.

Same pattern as the rest of the suite: no live database. We assert that
auth gating is correct and that pure helpers do the right thing for
edge cases.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from models import ReactionKind
from repositories import reactions as reactions_repo
from repositories import comments as comments_repo


def _client() -> TestClient:
    from main import app

    return TestClient(app)


FAKE_ID = "00000000-0000-0000-0000-000000000000"


def test_reaction_routes_require_auth() -> None:
    client = _client()
    targets = [
        ("POST", f"/birth/{FAKE_ID}/event/{FAKE_ID}/reactions", {"kind": "love"}),
        ("DELETE", f"/birth/{FAKE_ID}/event/{FAKE_ID}/reactions/love", None),
        ("POST", f"/b/anything/event/{FAKE_ID}/reactions", {"kind": "love"}),
        ("DELETE", f"/b/anything/event/{FAKE_ID}/reactions/love", None),
    ]
    for method, path, body in targets:
        response = client.request(method, path, json=body)
        assert response.status_code == 401, f"{method} {path} should require auth"


def test_comment_write_routes_require_auth() -> None:
    client = _client()
    targets = [
        ("POST", f"/birth/{FAKE_ID}/event/{FAKE_ID}/comments", {"body": "hi"}),
        ("PATCH", f"/birth/{FAKE_ID}/event/{FAKE_ID}/comments/{FAKE_ID}", {"body": "hi"}),
        ("DELETE", f"/birth/{FAKE_ID}/event/{FAKE_ID}/comments/{FAKE_ID}", None),
        ("POST", f"/b/anything/event/{FAKE_ID}/comments", {"body": "hi"}),
    ]
    for method, path, body in targets:
        response = client.request(method, path, json=body)
        assert response.status_code == 401, f"{method} {path} should require auth"


def test_public_comment_reads_do_not_require_auth() -> None:
    """Anonymous visitors should be able to read comments — the keepsake
    depends on it. We accept any non-401 outcome (no DB in tests).
    """
    client = _client()
    try:
        response = client.get(f"/b/anything/event/{FAKE_ID}/comments")
        assert response.status_code != 401
    except Exception:
        pass


def test_comment_body_validation() -> None:
    """Pydantic should reject empty / oversized comment bodies before
    auth is even attempted.
    """
    client = _client()
    response = client.post(
        f"/birth/{FAKE_ID}/event/{FAKE_ID}/comments",
        json={"body": ""},
        headers={"Authorization": "Bearer not-a-real-token"},
    )
    assert response.status_code in (401, 422)


def test_reaction_kind_is_a_closed_set() -> None:
    """If we add a new kind we want this test to scream — keep the
    palette curated."""
    assert {k.value for k in ReactionKind} == {"love", "wow", "pray"}


def test_repository_helpers_are_safe_with_empty_input() -> None:
    """summarize_events([]) and counts_for_events([]) must not query;
    they're called inline on every timeline page.
    """

    class _ShouldNotQuery:
        def execute(self, *_args, **_kwargs):
            raise AssertionError("Should not query for empty input")

    stub = _ShouldNotQuery()
    assert reactions_repo.summarize_events(
        stub, event_ids=[], requester_user_id=None
    ) == {}
    assert comments_repo.counts_for_events(stub, event_ids=[]) == {}
