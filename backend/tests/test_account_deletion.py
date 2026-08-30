"""Account deletion decision logic. The DB work is exercised end-to-end
against the dev stack; here we pin the pure parts — family bucketing,
the sentinel identity, rendering/media key planning, and S3 batching.
"""
from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

import account_deletion
import storage
from models import FamilyRole


def _membership(family_id, user_id, role):
    return SimpleNamespace(family_id=family_id, user_id=user_id, role=role)


def _parents(*memberships):
    return [(m, SimpleNamespace(id=m.user_id)) for m in memberships]


# ---- bucket_families ----


def test_sole_owner_erases():
    me, fam = uuid.uuid4(), uuid.uuid4()
    mine = _membership(fam, me, FamilyRole.owner)
    actions = account_deletion.bucket_families(me, [mine], {fam: _parents(mine)})
    assert actions == [
        account_deletion.FamilyAction(family_id=fam, kind="erase", was_parent=True)
    ]


def test_owner_with_co_parent_transfers_to_oldest():
    me, fam = uuid.uuid4(), uuid.uuid4()
    older, younger = uuid.uuid4(), uuid.uuid4()
    mine = _membership(fam, me, FamilyRole.owner)
    # list_parents is ordered by joined_at asc — first other parent wins.
    parents = _parents(
        mine,
        _membership(fam, older, FamilyRole.co_parent),
        _membership(fam, younger, FamilyRole.co_parent),
    )
    (action,) = account_deletion.bucket_families(me, [mine], {fam: parents})
    assert action.kind == "transfer"
    assert action.new_owner_user_id == older
    assert action.was_parent is True


def test_co_parent_and_viewer_leave():
    me = uuid.uuid4()
    fam_a, fam_b = uuid.uuid4(), uuid.uuid4()
    memberships = [
        _membership(fam_a, me, FamilyRole.co_parent),
        _membership(fam_b, me, FamilyRole.family_viewer),
    ]
    a, b = account_deletion.bucket_families(me, memberships, {})
    assert (a.kind, a.was_parent) == ("leave", True)
    assert (b.kind, b.was_parent) == ("leave", False)


def test_owner_in_one_family_viewer_in_another_are_independent():
    me = uuid.uuid4()
    fam_a, fam_b = uuid.uuid4(), uuid.uuid4()
    own = _membership(fam_a, me, FamilyRole.owner)
    view = _membership(fam_b, me, FamilyRole.family_viewer)
    a, b = account_deletion.bucket_families(
        me, [own, view], {fam_a: _parents(own)}
    )
    assert a.kind == "erase"
    assert b.kind == "leave"


def test_no_memberships_no_actions():
    assert account_deletion.bucket_families(uuid.uuid4(), [], {}) == []


# ---- sentinel identity ----


def test_sentinel_email_is_per_user_and_nonempty():
    a, b = uuid.uuid4(), uuid.uuid4()
    ea, eb = account_deletion.sentinel_email(a), account_deletion.sentinel_email(b)
    assert ea != eb                      # unique index on email
    assert str(a) in ea
    assert ea.endswith("@" + account_deletion.SENTINEL_DOMAIN)
    assert ea                            # satisfies ck_users_email_or_phone


# ---- media/rendering key planning ----


def _asset(**kw):
    return SimpleNamespace(
        **{
            "original_s3_key": None, "hot_s3_key": None, "cold_s3_key": None,
            "display_s3_key": None, "thumbnail_s3_key": None, **kw,
        }
    )


def test_collect_media_keys_skips_nulls_and_local():
    assets = [
        _asset(original_s3_key="f/x/b/y/a.jpg", hot_s3_key="f/x/b/y/a-hot.jpg"),
        _asset(original_s3_key="local:uploads/old.jpg"),
    ]
    assert account_deletion.collect_media_keys(assets) == [
        "f/x/b/y/a.jpg",
        "f/x/b/y/a-hot.jpg",
    ]


def test_collect_media_keys_takes_the_smaller_copies_too():
    """Erasure has to remove the display and thumbnail copies as well — a
    deleted photo that survives at 320px is still a surviving photo."""
    assets = [
        _asset(
            original_s3_key="f/x/b/y/a.jpg",
            display_s3_key="f/x/b/y/variants/a-display.webp",
            thumbnail_s3_key="f/x/b/y/variants/a-thumbnail.webp",
        )
    ]
    assert account_deletion.collect_media_keys(assets) == [
        "f/x/b/y/a.jpg",
        "f/x/b/y/variants/a-display.webp",
        "f/x/b/y/variants/a-thumbnail.webp",
    ]


def test_split_renderings_by_gift_order_reference():
    referenced = SimpleNamespace(
        id=uuid.uuid4(), artwork_s3_key="art1.png", mockup_s3_key="mock1.png"
    )
    free = SimpleNamespace(
        id=uuid.uuid4(), artwork_s3_key="art2.png", mockup_s3_key=None
    )
    soft, hard, keys = account_deletion.split_renderings(
        [referenced, free], {referenced.id}
    )
    assert soft == [referenced] and hard == [free]
    assert sorted(keys) == ["art1.png", "art2.png", "mock1.png"]


# ---- storage.delete_objects batching ----


class _FakeS3:
    def __init__(self):
        self.calls = []

    def delete_objects(self, *, Bucket, Delete):
        self.calls.append(len(Delete["Objects"]))
        # Report the first key of every batch as failed, to test aggregation.
        return {"Errors": [{"Key": Delete["Objects"][0]["Key"]}]}


def test_delete_objects_chunks_at_1000(monkeypatch):
    fake = _FakeS3()
    monkeypatch.setattr(storage, "_internal_client", lambda: fake)
    keys = [f"k{i}" for i in range(2500)]
    failed = storage.delete_objects(keys)
    assert fake.calls == [1000, 1000, 500]
    assert failed == ["k0", "k1000", "k2000"]


def test_delete_objects_empty_is_noop(monkeypatch):
    monkeypatch.setattr(
        storage, "_internal_client",
        lambda: (_ for _ in ()).throw(AssertionError("must not build a client")),
    )
    assert storage.delete_objects([]) == []


# ---- auth fails closed on deleted users ----


def test_user_from_jwt_rejects_deleted_user(monkeypatch):
    import auth
    from fastapi import HTTPException

    user_id = uuid.uuid4()
    monkeypatch.setattr(auth, "_decode_access_token", lambda tok: user_id)
    fake_db = SimpleNamespace(
        get=lambda model, uid: SimpleNamespace(deleted_at="2026-07-13")
    )
    with pytest.raises(HTTPException) as exc:
        auth._user_from_jwt("token", fake_db)
    assert exc.value.status_code == 401
    assert exc.value.detail == "Unknown user"  # same as missing — no oracle